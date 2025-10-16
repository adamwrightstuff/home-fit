import requests
from typing import Dict, List, Tuple
import math

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
SEARCH_RADIUS_KM = 1.0  # Walkable distance only

def get_green_neighborhood_score(lat: float, lon: float) -> Tuple[float, Dict]:
    """
    Analyze green spaces in the immediate neighborhood (walkable distance).
    Focuses on daily living environment: parks, playgrounds, sports fields.
    
    Args:
        lat: Latitude
        lon: Longitude
    
    Returns:
        (total_score, detailed_breakdown)
    """
    print(f"🏘️  Analyzing green neighborhood within {SEARCH_RADIUS_KM}km...")
    
    radius_m = SEARCH_RADIUS_KM * 1000
    
    # Query for neighborhood green spaces only
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
    );
    out body;
    >;
    out skel qt;
    """
    
    try:
        resp = requests.post(OVERPASS_URL, data={"data": query}, timeout=45, headers={
            "User-Agent": "HomeFit/1.0"
        })
        
        if resp.status_code == 504:
            print(f"⚠️  Overpass timeout - using fallback scoring...")
            return 50.0, _fallback_breakdown()
        
        if resp.status_code != 200:
            print(f"⚠️  Overpass API error: HTTP {resp.status_code}")
            return 0, _empty_breakdown()
        
        data = resp.json()
        elements = data.get("elements", [])
        
        green_spaces = _process_green_spaces(elements, lat, lon)
        
        if not green_spaces:
            print("⚠️  No green spaces found in neighborhood")
            return 0, _empty_breakdown()
        
        # Calculate 3-factor score
        proximity_score = _calculate_proximity_score(green_spaces)
        quantity_score = _calculate_quantity_score(green_spaces)
        variety_score = _calculate_variety_score(green_spaces)
        
        total_score = proximity_score + quantity_score + variety_score
        
        # Build breakdown
        breakdown = {
            "score": round(total_score, 1),
            "breakdown": {
                "proximity": round(proximity_score, 1),
                "quantity": round(quantity_score, 1),
                "variety": round(variety_score, 1)
            },
            "summary": _build_summary(green_spaces)
        }
        
        # Log results
        print(f"✅ Green Neighborhood Score: {total_score:.0f}/100")
        print(f"   📍 Proximity: {proximity_score:.0f}/40")
        print(f"   🔢 Quantity: {quantity_score:.0f}/30 ({len(green_spaces)} total)")
        print(f"   🎨 Variety: {variety_score:.0f}/30 ({len(breakdown['summary']['types'])} types)")
        
        return round(total_score, 1), breakdown
        
    except Exception as e:
        print(f"⚠️  Green neighborhood analysis failed: {e}")
        return 0, _empty_breakdown()


def _process_green_spaces(elements: List[Dict], center_lat: float, center_lon: float) -> List[Dict]:
    """Process OSM elements into green space records."""
    green_spaces = []
    seen_ids = set()
    nodes_dict = {}
    
    # Collect nodes
    for elem in elements:
        if elem.get("type") == "node":
            nodes_dict[elem["id"]] = elem
    
    # Process green spaces
    for elem in elements:
        osm_id = elem.get("id")
        if not osm_id or osm_id in seen_ids:
            continue
        
        tags = elem.get("tags", {})
        leisure_type = tags.get("leisure")
        
        if not leisure_type:
            continue
        
        seen_ids.add(osm_id)
        
        # Map to categories
        category = _map_to_category(leisure_type)
        
        # Get coordinates
        elem_lat = elem.get("lat")
        elem_lon = elem.get("lon")
        
        # For ways, calculate center
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
        "garden": "garden"
    }
    return mapping.get(leisure_type, "park")


def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points in meters."""
    R = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    
    a = math.sin(delta_phi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    
    return R * c


def _calculate_proximity_score(green_spaces: List[Dict]) -> float:
    """Score based on proximity to nearest parks (0-40 points)."""
    if not green_spaces:
        return 0.0
    
    distances = sorted([gs["distance_m"] for gs in green_spaces])
    
    # Within 400m (5 min walk)
    within_400m = [d for d in distances if d <= 400]
    if within_400m:
        # 3+ very close parks = full points
        return min(40.0, len(within_400m) * 13.3)
    
    # Within 600m (7-8 min walk)
    if distances[0] <= 600:
        return 30.0
    
    # Within 800m (10 min walk)
    if distances[0] <= 800:
        return 20.0
    
    # Within 1km
    if distances[0] <= 1000:
        return 10.0
    
    return 0.0


def _calculate_quantity_score(green_spaces: List[Dict]) -> float:
    """Score based on number of green spaces (0-30 points)."""
    count = len(green_spaces)
    
    # 15+ spaces = full points
    return min(30.0, count * 2.0)


def _calculate_variety_score(green_spaces: List[Dict]) -> float:
    """Score based on variety of space types (0-30 points)."""
    types = set(gs["type"] for gs in green_spaces)
    
    # 4 types = full points (park, playground, sports, garden)
    return min(30.0, len(types) * 7.5)


def _build_summary(green_spaces: List[Dict]) -> Dict:
    """Build summary statistics."""
    within_5min = len([gs for gs in green_spaces if gs["distance_m"] <= 400])
    within_10min = len([gs for gs in green_spaces if gs["distance_m"] <= 800])
    
    types = list(set(gs["type"] for gs in green_spaces))
    
    return {
        "total_count": len(green_spaces),
        "within_5min_walk": within_5min,
        "within_10min_walk": within_10min,
        "types": types
    }


def _empty_breakdown() -> Dict:
    """Return empty breakdown when no data."""
    return {
        "score": 0,
        "breakdown": {
            "proximity": 0,
            "quantity": 0,
            "variety": 0
        },
        "summary": {
            "total_count": 0,
            "within_5min_walk": 0,
            "within_10min_walk": 0,
            "types": []
        }
    }


def _fallback_breakdown() -> Dict:
    """Return fallback when API times out."""
    return {
        "score": 50,
        "breakdown": {
            "proximity": 20,
            "quantity": 15,
            "variety": 15
        },
        "summary": {
            "total_count": 0,
            "within_5min_walk": 0,
            "within_10min_walk": 0,
            "types": [],
            "note": "Estimated due to API timeout"
        }
    }