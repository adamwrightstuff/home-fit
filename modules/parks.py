import requests
from typing import Dict, List, Tuple
import math

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
SEARCH_RADIUS_KM = 2

def get_park_data(lat: float, lon: float, radius_km: float = SEARCH_RADIUS_KM) -> Tuple[int, Dict]:
    """
    Analyze green spaces near coordinates using OpenStreetMap Overpass API.
    Returns a comprehensive score based on proximity, quantity, scale, and variety.
    
    Args:
        lat: Latitude
        lon: Longitude
        radius_km: Search radius in kilometers (default: 2)
    
    Returns:
        (total_score, detailed_breakdown)
    """
    print(f"🌳 Analyzing green spaces within {radius_km}km of ({lat}, {lon})…")
    
    # Convert km to meters for Overpass API
    radius_m = radius_km * 1000
    
    # Overpass QL query to find various green spaces with geometry
    query = f"""
    [out:json][timeout:25];
    (
      node["leisure"="park"](around:{radius_m},{lat},{lon});
      way["leisure"="park"](around:{radius_m},{lat},{lon});
      relation["leisure"="park"](around:{radius_m},{lat},{lon});
      
      node["leisure"="playground"](around:{radius_m},{lat},{lon});
      way["leisure"="playground"](around:{radius_m},{lat},{lon});
      
      node["leisure"="sports_centre"](around:{radius_m},{lat},{lon});
      way["leisure"="sports_centre"](around:{radius_m},{lat},{lon});
      
      node["leisure"="pitch"](around:{radius_m},{lat},{lon});
      way["leisure"="pitch"](around:{radius_m},{lat},{lon});
      
      node["leisure"="garden"](around:{radius_m},{lat},{lon});
      way["leisure"="garden"](around:{radius_m},{lat},{lon});
      
      node["leisure"="nature_reserve"](around:{radius_m},{lat},{lon});
      way["leisure"="nature_reserve"](around:{radius_m},{lat},{lon});
      relation["leisure"="nature_reserve"](around:{radius_m},{lat},{lon});
    );
    out body;
    >;
    out skel qt;
    """
    
    try:
        resp = requests.post(OVERPASS_URL, data={"data": query}, timeout=30)
        
        if resp.status_code != 200:
            print(f"⚠️  Overpass API error: HTTP {resp.status_code}")
            return 0, _empty_breakdown()
        
        data = resp.json()
        elements = data.get("elements", [])
        
        # Process green spaces
        green_spaces = _process_green_spaces(elements, lat, lon)
        
        if not green_spaces:
            print("⚠️  No green spaces found")
            return 0, _empty_breakdown()
        
        # Calculate scores (3-factor model: Proximity, Quantity, Variety)
        proximity_score = _calculate_proximity_score(green_spaces)
        quantity_score = _calculate_quantity_score(green_spaces)
        variety_score = _calculate_variety_score(green_spaces)
        
        total_score = proximity_score + quantity_score + variety_score
        
        # Build breakdown
        breakdown = {
            "score": round(total_score, 1),
            "breakdown": {
                "proximity_score": round(proximity_score, 1),
                "quantity_score": round(quantity_score, 1),
                "variety_score": round(variety_score, 1)
            },
            "summary": _build_summary(green_spaces)
        }
        
        # Log results
        print(f"✅ Green Space Analysis:")
        print(f"   Total Score: {total_score:.0f}/100")
        print(f"   📍 Proximity: {proximity_score:.0f}/50 ({breakdown['summary']['within_5min_walk']} within 5min walk)")
        print(f"   🔢 Quantity: {quantity_score:.0f}/25 ({breakdown['summary']['total_count']} total)")
        print(f"   🎨 Variety: {variety_score:.0f}/25 ({len(breakdown['summary']['types_available'])} types)")
        
        return round(total_score, 1), breakdown
        
    except Exception as e:
        print(f"⚠️  Overpass API request failed: {e}")
        return 0, _empty_breakdown()


def _process_green_spaces(elements: List[Dict], center_lat: float, center_lon: float) -> List[Dict]:
    """Process OSM elements into green space records with type, distance, and size."""
    green_spaces = []
    seen_ids = set()
    
    # First pass: collect all ways and relations with their nodes
    nodes_dict = {}
    ways_dict = {}
    
    for elem in elements:
        if elem.get("type") == "node":
            nodes_dict[elem["id"]] = elem
        elif elem.get("type") == "way":
            ways_dict[elem["id"]] = elem
    
    # Second pass: process green spaces
    for elem in elements:
        osm_id = elem.get("id")
        if not osm_id or osm_id in seen_ids:
            continue
        
        tags = elem.get("tags", {})
        leisure_type = tags.get("leisure")
        
        if not leisure_type:
            continue
        
        seen_ids.add(osm_id)
        
        # Map to simplified categories
        category = _map_to_category(leisure_type)
        
        # Calculate distance
        elem_lat = elem.get("lat")
        elem_lon = elem.get("lon")
        
        # For ways, use center point
        if elem.get("type") == "way" and "nodes" in elem:
            node_coords = []
            for node_id in elem["nodes"]:
                if node_id in nodes_dict:
                    node = nodes_dict[node_id]
                    if "lat" in node and "lon" in node:
                        node_coords.append((node["lat"], node["lon"]))
            
            if node_coords:
                elem_lat = sum(c[0] for c in node_coords) / len(node_coords)
                elem_lon = sum(c[1] for c in node_coords) / len(node_coords)
        
        if elem_lat is None or elem_lon is None:
            continue
        
        distance_m = _haversine_distance(center_lat, center_lon, elem_lat, elem_lon)
        
        green_spaces.append({
            "type": category,
            "distance_m": round(distance_m, 0)
        })
    
    return green_spaces


def _map_to_category(leisure_type: str) -> str:
    """Map OSM leisure types to simplified categories."""
    mapping = {
        "park": "park",
        "playground": "playground",
        "sports_centre": "sports_field",
        "pitch": "sports_field",
        "garden": "park",
        "nature_reserve": "nature_area"
    }
    return mapping.get(leisure_type, "park")


def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points in meters using Haversine formula."""
    R = 6371000  # Earth radius in meters
    
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    
    a = math.sin(delta_phi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    
    return R * c


def _calculate_proximity_score(green_spaces: List[Dict]) -> float:
    """Score based on closest green spaces (0-50 points)."""
    if not green_spaces:
        return 0.0
    
    # Find closest spaces
    distances = sorted([gs["distance_m"] for gs in green_spaces])
    
    score = 0.0
    
    # Within 400m (5 min walk) = 50 points max
    within_400m = [d for d in distances if d <= 400]
    if within_400m:
        # 3+ parks within 5min = full points
        score += min(50.0, len(within_400m) * 16.7)
    # Within 800m (10 min walk) = 35 points
    elif distances[0] <= 800:
        score += 35.0
    # Within 1200m (15 min walk) = 20 points
    elif distances[0] <= 1200:
        score += 20.0
    # Within 2000m = 10 points
    elif distances[0] <= 2000:
        score += 10.0
    
    return min(score, 50.0)


def _calculate_quantity_score(green_spaces: List[Dict]) -> float:
    """Score based on number of green spaces within 1km (0-25 points)."""
    within_1km = [gs for gs in green_spaces if gs["distance_m"] <= 1000]
    count = len(within_1km)
    
    # 10+ spaces = full points, scale linearly
    return min(25.0, count * 2.5)


def _calculate_variety_score(green_spaces: List[Dict]) -> float:
    """Score based on variety of green space types (0-25 points)."""
    types = set(gs["type"] for gs in green_spaces)
    
    # 4 types = full points, 6.25 points per type
    return min(25.0, len(types) * 6.25)


def _build_summary(green_spaces: List[Dict]) -> Dict:
    """Build summary statistics."""
    within_5min = len([gs for gs in green_spaces if gs["distance_m"] <= 400])
    within_10min = len([gs for gs in green_spaces if gs["distance_m"] <= 800])
    
    types = list(set(gs["type"] for gs in green_spaces))
    
    return {
        "total_count": len(green_spaces),
        "within_5min_walk": within_5min,
        "within_10min_walk": within_10min,
        "types_available": types
    }


def _empty_breakdown() -> Dict:
    """Return empty breakdown when no data."""
    return {
        "score": 0,
        "breakdown": {
            "proximity_score": 0,
            "quantity_score": 0,
            "variety_score": 0
        },
        "summary": {
            "total_count": 0,
            "within_5min_walk": 0,
            "within_10min_walk": 0,
            "types_available": []
        }
    }


# Legacy function for backward compatibility
def get_park_count(lat: float, lon: float, radius_km: float = SEARCH_RADIUS_KM) -> int:
    """Legacy function - returns simple count for backward compatibility."""
    score, breakdown = get_park_data(lat, lon, radius_km)
    return breakdown["summary"]["total_count"]