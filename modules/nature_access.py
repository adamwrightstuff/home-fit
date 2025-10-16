import requests
from typing import Dict, List, Tuple
import math

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
SEARCH_RADIUS_KM = 10.0  # Driveable for day trips

def get_nature_access_score(lat: float, lon: float) -> Tuple[float, Dict]:
    """
    Analyze access to natural recreation areas (forests, water, mountains).
    Focuses on weekend/outdoor recreation opportunities.
    
    Args:
        lat: Latitude
        lon: Longitude
    
    Returns:
        (total_score, detailed_breakdown)
    """
    print(f"🏔️  Analyzing nature access within {SEARCH_RADIUS_KM}km...")
    
    radius_m = SEARCH_RADIUS_KM * 1000
    
    # Query for wilderness and water features
    query = f"""
    [out:json][timeout:30];
    (
      node["natural"="wood"](around:{radius_m},{lat},{lon});
      way["natural"="wood"](around:{radius_m},{lat},{lon});
      relation["natural"="wood"](around:{radius_m},{lat},{lon});
      
      node["landuse"="forest"](around:{radius_m},{lat},{lon});
      way["landuse"="forest"](around:{radius_m},{lat},{lon});
      relation["landuse"="forest"](around:{radius_m},{lat},{lon});
      
      node["leisure"="nature_reserve"](around:{radius_m},{lat},{lon});
      way["leisure"="nature_reserve"](around:{radius_m},{lat},{lon});
      relation["leisure"="nature_reserve"](around:{radius_m},{lat},{lon});
      
      node["natural"="water"](around:{radius_m},{lat},{lon});
      way["natural"="water"](around:{radius_m},{lat},{lon});
      relation["natural"="water"](around:{radius_m},{lat},{lon});
      
      node["waterway"="river"](around:{radius_m},{lat},{lon});
      way["waterway"="river"](around:{radius_m},{lat},{lon});
      
      node["natural"="beach"](around:{radius_m},{lat},{lon});
      way["natural"="beach"](around:{radius_m},{lat},{lon});
      
      node["natural"="peak"](around:{radius_m},{lat},{lon});
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
            print(f"⚠️  Overpass timeout for nature access...")
            return 0, _empty_breakdown()
        
        if resp.status_code != 200:
            print(f"⚠️  Overpass API error: HTTP {resp.status_code}")
            return 0, _empty_breakdown()
        
        data = resp.json()
        elements = data.get("elements", [])
        
        wilderness_features, water_features = _process_nature_features(elements, lat, lon)
        
        # Calculate scores
        wilderness_score = _calculate_wilderness_score(wilderness_features)
        water_score = _calculate_water_score(water_features)
        variety_score = _calculate_variety_score(wilderness_features, water_features)
        
        total_score = wilderness_score + water_score + variety_score
        
        # Build breakdown
        breakdown = {
            "score": round(total_score, 1),
            "breakdown": {
                "wilderness_proximity": round(wilderness_score, 1),
                "water_access": round(water_score, 1),
                "variety": round(variety_score, 1)
            },
            "summary": _build_summary(wilderness_features, water_features)
        }
        
        # Log results
        print(f"✅ Nature Access Score: {total_score:.0f}/100")
        print(f"   🌲 Wilderness: {wilderness_score:.0f}/40")
        print(f"   🌊 Water: {water_score:.0f}/40")
        print(f"   🎨 Variety: {variety_score:.0f}/20")
        
        return round(total_score, 1), breakdown
        
    except Exception as e:
        print(f"⚠️  Nature access analysis failed: {e}")
        return 0, _empty_breakdown()


def _process_nature_features(elements: List[Dict], center_lat: float, center_lon: float) -> Tuple[List[Dict], List[Dict]]:
    """Process OSM elements into wilderness and water features."""
    wilderness_features = []
    water_features = []
    seen_ids = set()
    nodes_dict = {}
    
    # Collect nodes
    for elem in elements:
        if elem.get("type") == "node":
            nodes_dict[elem["id"]] = elem
    
    # Process features
    for elem in elements:
        osm_id = elem.get("id")
        if not osm_id or osm_id in seen_ids:
            continue
        
        tags = elem.get("tags", {})
        
        # Determine feature type
        natural_tag = tags.get("natural")
        landuse_tag = tags.get("landuse")
        leisure_tag = tags.get("leisure")
        waterway_tag = tags.get("waterway")
        
        feature_type = None
        category = None  # wilderness or water
        
        # Wilderness features
        if natural_tag == "wood":
            feature_type = "forest"
            category = "wilderness"
        elif landuse_tag == "forest":
            feature_type = "forest"
            category = "wilderness"
        elif leisure_tag == "nature_reserve":
            feature_type = "nature_reserve"
            category = "wilderness"
        elif natural_tag == "peak":
            feature_type = "mountain"
            category = "wilderness"
        
        # Water features
        elif natural_tag == "water":
            feature_type = "lake"
            category = "water"
        elif waterway_tag == "river":
            feature_type = "river"
            category = "water"
        elif natural_tag == "beach":
            feature_type = "beach"
            category = "water"
        
        if not feature_type:
            continue
        
        seen_ids.add(osm_id)
        
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
        
        # Get name if available
        name = tags.get("name", None)
        
        feature = {
            "type": feature_type,
            "distance_m": round(distance_m, 0),
            "name": name
        }
        
        if category == "wilderness":
            wilderness_features.append(feature)
        elif category == "water":
            water_features.append(feature)
    
    return wilderness_features, water_features


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


def _calculate_wilderness_score(features: List[Dict]) -> float:
    """Score based on proximity to wilderness (0-40 points)."""
    if not features:
        return 0.0
    
    distances = sorted([f["distance_m"] for f in features])
    closest = distances[0]
    
    # Within 2km - excellent access
    if closest <= 2000:
        return 40.0
    # Within 5km - good access
    elif closest <= 5000:
        return 30.0
    # Within 10km - moderate access
    elif closest <= 10000:
        return 20.0
    else:
        return 10.0


def _calculate_water_score(features: List[Dict]) -> float:
    """Score based on proximity to water (0-40 points)."""
    if not features:
        return 0.0
    
    distances = sorted([f["distance_m"] for f in features])
    closest = distances[0]
    
    # Check if it's a beach (premium)
    has_beach = any(f["type"] == "beach" and f["distance_m"] <= 5000 for f in features)
    
    if has_beach:
        if closest <= 2000:
            return 40.0
        elif closest <= 5000:
            return 35.0
    
    # Regular water bodies
    if closest <= 2000:
        return 35.0
    elif closest <= 5000:
        return 25.0
    elif closest <= 10000:
        return 15.0
    else:
        return 5.0


def _calculate_variety_score(wilderness: List[Dict], water: List[Dict]) -> float:
    """Score based on variety of nature types (0-20 points)."""
    types = set()
    
    for f in wilderness:
        types.add(f["type"])
    for f in water:
        types.add(f["type"])
    
    # 4+ types = full points
    return min(20.0, len(types) * 5.0)


def _build_summary(wilderness: List[Dict], water: List[Dict]) -> Dict:
    """Build summary statistics."""
    summary = {
        "wilderness": None,
        "water": None,
        "nature_types": []
    }
    
    # Find nearest wilderness
    if wilderness:
        nearest_wild = min(wilderness, key=lambda x: x["distance_m"])
        summary["wilderness"] = {
            "name": nearest_wild.get("name", f"{nearest_wild['type'].title()}"),
            "type": nearest_wild["type"],
            "distance_m": nearest_wild["distance_m"],
            "distance_km": round(nearest_wild["distance_m"] / 1000, 1)
        }
    
    # Find nearest water
    if water:
        nearest_water = min(water, key=lambda x: x["distance_m"])
        summary["water"] = {
            "name": nearest_water.get("name", f"{nearest_water['type'].title()}"),
            "type": nearest_water["type"],
            "distance_m": nearest_water["distance_m"],
            "distance_km": round(nearest_water["distance_m"] / 1000, 1)
        }
    
    # Collect unique types
    types = set()
    for f in wilderness:
        types.add(f["type"])
    for f in water:
        types.add(f["type"])
    summary["nature_types"] = list(types)
    
    return summary


def _empty_breakdown() -> Dict:
    """Return empty breakdown when no data."""
    return {
        "score": 0,
        "breakdown": {
            "wilderness_proximity": 0,
            "water_access": 0,
            "variety": 0
        },
        "summary": {
            "wilderness": None,
            "water": None,
            "nature_types": []
        }
    }