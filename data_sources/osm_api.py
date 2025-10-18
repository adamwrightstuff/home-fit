"""
OpenStreetMap API Client
Queries Overpass API for green spaces and nature features
"""

import requests
import math
from typing import Dict, List, Tuple, Optional

OVERPASS_URL = "https://overpass-api.de/api/interpreter"


def query_green_spaces(lat: float, lon: float, radius_m: int = 1000) -> Optional[Dict]:
    """
    Query OSM for parks, playgrounds, and tree features.

    Returns:
        {
            "parks": [...],
            "playgrounds": [...],
            "tree_features": [...]
        }
    """
    query = f"""
    [out:json][timeout:25];
    (
      // PARKS & GREEN SPACES
      way["leisure"="park"](around:{radius_m},{lat},{lon});
      way["leisure"="garden"]["garden:type"!="private"](around:{radius_m},{lat},{lon});
      way["leisure"="dog_park"](around:{radius_m},{lat},{lon});
      way["landuse"="recreation_ground"](around:{radius_m},{lat},{lon});
      way["landuse"="village_green"](around:{radius_m},{lat},{lon});
      
      // LOCAL NATURE
      way["natural"="wood"](around:{radius_m},{lat},{lon});
      way["natural"="forest"](around:{radius_m},{lat},{lon});
      way["natural"="scrub"](around:{radius_m},{lat},{lon});
      
      // PLAYGROUNDS
      node["leisure"="playground"](around:{radius_m},{lat},{lon});
      way["leisure"="playground"](around:{radius_m},{lat},{lon});
      
      // TREES
      way["natural"="tree_row"](around:{radius_m},{lat},{lon});
      way["highway"]["trees"="yes"](around:{radius_m},{lat},{lon});
      way["highway"]["trees:both"="yes"](around:{radius_m},{lat},{lon});
      way["highway"]["trees:left"="yes"](around:{radius_m},{lat},{lon});
      way["highway"]["trees:right"="yes"](around:{radius_m},{lat},{lon});
    );
    out body;
    >;
    out skel qt;
    """

    try:
        resp = requests.post(
            OVERPASS_URL,
            data={"data": query},
            timeout=35,
            headers={"User-Agent": "HomeFit/1.0"}
        )

        if resp.status_code != 200:
            return None

        data = resp.json()
        elements = data.get("elements", [])

        parks, playgrounds, tree_features = _process_green_features(
            elements, lat, lon)

        return {
            "parks": parks,
            "playgrounds": playgrounds,
            "tree_features": tree_features
        }

    except Exception as e:
        print(f"OSM query error: {e}")
        return None


def query_nature_features(lat: float, lon: float, radius_m: int = 15000) -> Optional[Dict]:
    """
    Query OSM for outdoor recreation (hiking, swimming, camping).

    Returns:
        {
            "hiking": [...],
            "swimming": [...],
            "camping": [...]
        }
    """
    query = f"""
    [out:json][timeout:35];
    (
      // HIKING
      relation["route"="hiking"](around:{radius_m},{lat},{lon});
      way["boundary"="national_park"](around:{radius_m},{lat},{lon});
      relation["boundary"="national_park"](around:{radius_m},{lat},{lon});
      way["leisure"="nature_reserve"](around:{radius_m},{lat},{lon});
      relation["leisure"="nature_reserve"](around:{radius_m},{lat},{lon});
      way["boundary"="protected_area"](around:{radius_m},{lat},{lon});
      relation["boundary"="protected_area"](around:{radius_m},{lat},{lon});
      
      // SWIMMING
      way["natural"="beach"](around:{radius_m},{lat},{lon});
      relation["natural"="beach"](around:{radius_m},{lat},{lon});
      way["natural"="water"]["water"="lake"](around:{radius_m},{lat},{lon});
      relation["natural"="water"]["water"="lake"](around:{radius_m},{lat},{lon});
      way["natural"="coastline"](around:{radius_m},{lat},{lon});
      way["natural"="water"]["water"="bay"](around:{radius_m},{lat},{lon});
      relation["natural"="water"]["water"="bay"](around:{radius_m},{lat},{lon});
      way["leisure"="swimming_area"](around:{radius_m},{lat},{lon});
      relation["leisure"="swimming_area"](around:{radius_m},{lat},{lon});
      
      // CAMPING
      way["tourism"="camp_site"](around:{radius_m},{lat},{lon});
      relation["tourism"="camp_site"](around:{radius_m},{lat},{lon});
    );
    out body;
    >;
    out skel qt;
    """

    try:
        resp = requests.post(
            OVERPASS_URL,
            data={"data": query},
            timeout=50,
            headers={"User-Agent": "HomeFit/1.0"}
        )

        if resp.status_code != 200:
            return None

        data = resp.json()
        elements = data.get("elements", [])

        hiking, swimming, camping = _process_nature_features(
            elements, lat, lon)

        return {
            "hiking": hiking,
            "swimming": swimming,
            "camping": camping
        }

    except Exception as e:
        print(f"OSM nature query error: {e}")
        return None


def query_local_businesses(lat: float, lon: float, radius_m: int = 1000) -> Optional[Dict]:
    """
    Query OSM for indie local businesses within walking distance.
    Focuses on non-chain establishments.

    Returns:
        {
            "tier1_daily": [...],      # Coffee, bakeries, groceries
            "tier2_social": [...],     # Restaurants, bars, ice cream
            "tier3_culture": [...],    # Books, galleries, theaters, museums, markets
            "tier4_services": [...]    # Boutiques, salons, record stores, fitness, gardens
        }
    """


def query_charm_features(lat: float, lon: float, radius_m: int = 500) -> Optional[Dict]:
    """
    Query OSM for neighborhood charm features (historic buildings, fountains, public art).

    Returns:
        {
            "historic": [...],
            "artwork": [...]
        }
    """
    query = f"""
    [out:json][timeout:25];
    (
      // HISTORIC BUILDINGS
      node["historic"~"building|castle|church|monument|memorial|ruins|archaeological_site"](around:{radius_m},{lat},{lon});
      way["historic"~"building|castle|church|monument|memorial|ruins|archaeological_site"](around:{radius_m},{lat},{lon});
      
      // PUBLIC ART & FOUNTAINS
      node["tourism"="artwork"](around:{radius_m},{lat},{lon});
      way["tourism"="artwork"](around:{radius_m},{lat},{lon});
      node["amenity"="fountain"](around:{radius_m},{lat},{lon});
      way["amenity"="fountain"](around:{radius_m},{lat},{lon});
    );
    out body;
    >;
    out skel qt;
    """

    try:
        resp = requests.post(
            OVERPASS_URL,
            data={"data": query},
            timeout=35,
            headers={"User-Agent": "HomeFit/1.0"}
        )

        if resp.status_code != 200:
            return None

        data = resp.json()
        elements = data.get("elements", [])

        historic, artwork = _process_charm_features(elements, lat, lon)

        return {
            "historic": historic,
            "artwork": artwork
        }

    except Exception as e:
        print(f"OSM charm query error: {e}")
        return None


def query_local_businesses(lat: float, lon: float, radius_m: int = 1000) -> Optional[Dict]:
    """
    Query OSM for indie local businesses within walking distance.
    Focuses on non-chain establishments.

    Returns:
        {
            "tier1_daily": [...],      # Coffee, bakeries, groceries
            "tier2_social": [...],     # Restaurants, bars, ice cream
            "tier3_culture": [...],    # Books, galleries, theaters, museums, markets
            "tier4_services": [...]    # Boutiques, salons, record stores, fitness, gardens
        }
    """
    query = f"""
    [out:json][timeout:60];
    (
      // TIER 1: DAILY ESSENTIALS
      node["amenity"="cafe"]["name"]["brand"!~"."](around:{radius_m},{lat},{lon});
      way["amenity"="cafe"]["name"]["brand"!~"."](around:{radius_m},{lat},{lon});
      
      node["shop"="bakery"]["name"]["brand"!~"."](around:{radius_m},{lat},{lon});
      way["shop"="bakery"]["name"]["brand"!~"."](around:{radius_m},{lat},{lon});
      
      node["shop"~"supermarket|convenience|greengrocer"]["name"]["brand"!~"."](around:{radius_m},{lat},{lon});
      way["shop"~"supermarket|convenience|greengrocer"]["name"]["brand"!~"."](around:{radius_m},{lat},{lon});
      
      // TIER 2: SOCIAL & DINING
      node["amenity"="restaurant"]["name"]["brand"!~"."](around:{radius_m},{lat},{lon});
      way["amenity"="restaurant"]["name"]["brand"!~"."](around:{radius_m},{lat},{lon});
      
      node["amenity"~"bar|pub"]["name"]["brand"!~"."](around:{radius_m},{lat},{lon});
      way["amenity"~"bar|pub"]["name"]["brand"!~"."](around:{radius_m},{lat},{lon});
      
      node["amenity"="ice_cream"]["name"]["brand"!~"."](around:{radius_m},{lat},{lon});
      node["shop"="ice_cream"]["name"]["brand"!~"."](around:{radius_m},{lat},{lon});
      way["shop"="ice_cream"]["name"]["brand"!~"."](around:{radius_m},{lat},{lon});
      
      // TIER 3: CULTURE & LEISURE
      node["shop"="books"]["name"]["brand"!~"."](around:{radius_m},{lat},{lon});
      way["shop"="books"]["name"]["brand"!~"."](around:{radius_m},{lat},{lon});
      
      node["tourism"="gallery"]["name"](around:{radius_m},{lat},{lon});
      way["tourism"="gallery"]["name"](around:{radius_m},{lat},{lon});
      node["shop"="art"]["name"](around:{radius_m},{lat},{lon});
      way["shop"="art"]["name"](around:{radius_m},{lat},{lon});
      
      node["amenity"~"theatre|cinema"]["name"](around:{radius_m},{lat},{lon});
      way["amenity"~"theatre|cinema"]["name"](around:{radius_m},{lat},{lon});
      
      node["tourism"="museum"]["name"](around:{radius_m},{lat},{lon});
      way["tourism"="museum"]["name"](around:{radius_m},{lat},{lon});
      
      node["amenity"="marketplace"]["name"](around:{radius_m},{lat},{lon});
      way["amenity"="marketplace"]["name"](around:{radius_m},{lat},{lon});
      
      // TIER 4: SERVICES & RETAIL
      node["shop"~"clothes|fashion|boutique"]["name"]["brand"!~"."](around:{radius_m},{lat},{lon});
      way["shop"~"clothes|fashion|boutique"]["name"]["brand"!~"."](around:{radius_m},{lat},{lon});
      
      node["shop"~"hairdresser|beauty"]["name"]["brand"!~"."](around:{radius_m},{lat},{lon});
      way["shop"~"hairdresser|beauty"]["name"]["brand"!~"."](around:{radius_m},{lat},{lon});
      
      node["shop"="music"]["name"]["brand"!~"."](around:{radius_m},{lat},{lon});
      way["shop"="music"]["name"]["brand"!~"."](around:{radius_m},{lat},{lon});
      
      node["leisure"="fitness_centre"]["name"]["brand"!~"."](around:{radius_m},{lat},{lon});
      way["leisure"="fitness_centre"]["name"]["brand"!~"."](around:{radius_m},{lat},{lon});
      
      node["shop"~"garden_centre|florist"]["name"]["brand"!~"."](around:{radius_m},{lat},{lon});
      way["shop"~"garden_centre|florist"]["name"]["brand"!~"."](around:{radius_m},{lat},{lon});
    );
    out body;
    >;
    out skel qt;
    """

    try:
        resp = requests.post(
            OVERPASS_URL,
            data={"data": query},
            timeout=70,
            headers={"User-Agent": "HomeFit/1.0"}
        )

        if resp.status_code != 200:
            return None

        data = resp.json()
        elements = data.get("elements", [])

        businesses = _process_business_features(elements, lat, lon)
        return businesses

    except Exception as e:
        print(f"OSM business query error: {e}")
        return None


def _process_green_features(elements: List[Dict], center_lat: float, center_lon: float) -> Tuple[List[Dict], List[Dict], List[Dict]]:
    """Process OSM elements into parks, playgrounds, and tree features."""
    parks = []
    playgrounds = []
    tree_features = []
    nodes_dict = {}
    seen_park_ids = set()
    seen_playground_ids = set()

    # Build nodes dict
    for elem in elements:
        if elem.get("type") == "node":
            nodes_dict[elem["id"]] = elem

    # Process features
    for elem in elements:
        osm_id = elem.get("id")
        if not osm_id:
            continue

        tags = elem.get("tags", {})
        leisure = tags.get("leisure")
        landuse = tags.get("landuse")
        natural = tags.get("natural")
        highway = tags.get("highway")

        # Parks
        if leisure in ["park", "dog_park"] or \
           (leisure == "garden" and tags.get("garden:type") != "private") or \
           landuse in ["recreation_ground", "village_green"] or \
           natural in ["wood", "forest", "scrub"]:

            if osm_id in seen_park_ids:
                continue
            seen_park_ids.add(osm_id)

            elem_lat, elem_lon, area_sqm = _get_way_geometry(elem, nodes_dict)
            if elem_lat is None:
                continue

            distance_m = haversine_distance(
                center_lat, center_lon, elem_lat, elem_lon)

            parks.append({
                "name": tags.get("name", _get_park_type_name(leisure, landuse, natural)),
                "type": leisure or landuse or natural,
                "lat": elem_lat,
                "lon": elem_lon,
                "distance_m": round(distance_m, 0),
                "area_sqm": round(area_sqm, 0) if area_sqm else 0
            })

        # Playgrounds
        elif leisure == "playground":
            if osm_id in seen_playground_ids:
                continue
            seen_playground_ids.add(osm_id)

            elem_lat = elem.get("lat")
            elem_lon = elem.get("lon")

            if elem.get("type") == "way":
                elem_lat, elem_lon, _ = _get_way_geometry(elem, nodes_dict)

            if elem_lat is None:
                continue

            distance_m = haversine_distance(
                center_lat, center_lon, elem_lat, elem_lon)

            playgrounds.append({
                "name": tags.get("name"),
                "lat": elem_lat,
                "lon": elem_lon,
                "distance_m": round(distance_m, 0)
            })

        # Trees
        elif natural == "tree_row" or \
                (highway and any(tags.get(k) == "yes" for k in ["trees", "trees:both", "trees:left", "trees:right"])):

            tree_features.append({
                "type": "tree_row" if natural == "tree_row" else "street_trees",
                "name": tags.get("name")
            })

    # Deduplicate
    parks = _deduplicate_by_proximity(parks, 10)
    playgrounds = _deduplicate_by_proximity(playgrounds, 50)

    return parks, playgrounds, tree_features


def _process_nature_features(elements: List[Dict], center_lat: float, center_lon: float) -> Tuple[List[Dict], List[Dict], List[Dict]]:
    """Process OSM elements into hiking, swimming, and camping features."""
    hiking = []
    swimming = []
    camping = []
    nodes_dict = {}
    ways_dict = {}
    seen_ids = set()

    # Build nodes and ways dicts
    for elem in elements:
        if elem.get("type") == "node":
            nodes_dict[elem["id"]] = elem
        elif elem.get("type") == "way":
            ways_dict[elem["id"]] = elem

    # Process features
    for elem in elements:
        osm_id = elem.get("id")
        elem_type = elem.get("type")
        
        # Only process ways and relations, skip nodes
        if elem_type not in ["way", "relation"] or not osm_id or osm_id in seen_ids:
            continue

        tags = elem.get("tags", {})
        route = tags.get("route")
        boundary = tags.get("boundary")
        natural = tags.get("natural")
        leisure = tags.get("leisure")
        tourism = tags.get("tourism")
        water_type = tags.get("water")

        feature = None
        category = None

        # Categorize
        if route == "hiking":
            feature = {"type": "hiking_route", "name": tags.get("name")}
            category = "hiking"
        elif boundary == "national_park":
            feature = {"type": "national_park", "name": tags.get("name")}
            category = "hiking"
        elif leisure == "nature_reserve":
            feature = {"type": "nature_reserve", "name": tags.get("name")}
            category = "hiking"
        elif boundary == "protected_area":
            feature = {"type": "protected_area", "name": tags.get("name")}
            category = "hiking"
        elif natural == "beach":
            feature = {"type": "beach", "name": tags.get("name")}
            category = "swimming"
        elif natural == "water" and water_type == "lake":
            feature = {"type": "lake", "name": tags.get("name")}
            category = "swimming"
        elif natural == "coastline":
            feature = {"type": "coastline", "name": tags.get("name")}
            category = "swimming"
        elif natural == "water" and water_type == "bay":
            feature = {"type": "bay", "name": tags.get("name")}
            category = "swimming"
        elif leisure == "swimming_area":
            feature = {"type": "swimming_area", "name": tags.get("name")}
            category = "swimming"
        elif tourism == "camp_site":
            feature = {"type": "campsite", "name": tags.get("name")}
            category = "camping"

        if not feature:
            continue

        seen_ids.add(osm_id)

        # Get coordinates based on element type
        elem_lat = None
        elem_lon = None
        
        if elem_type == "way":
            elem_lat, elem_lon, _ = _get_way_geometry(elem, nodes_dict)
        elif elem_type == "relation":
            # For relations, get centroid from outer member ways
            elem_lat, elem_lon = _get_relation_centroid(elem, ways_dict, nodes_dict)

        if elem_lat is None:
            continue

        distance_m = haversine_distance(
            center_lat, center_lon, elem_lat, elem_lon)
        feature["distance_m"] = round(distance_m, 0)

        if category == "hiking":
            hiking.append(feature)
        elif category == "swimming":
            swimming.append(feature)
        elif category == "camping":
            camping.append(feature)

    return hiking, swimming, camping


def _process_business_features(elements: List[Dict], center_lat: float, center_lon: float) -> Dict:
    """Process OSM elements into categorized businesses by tier."""


def _process_charm_features(elements: List[Dict], center_lat: float, center_lon: float) -> Tuple[List[Dict], List[Dict]]:
    """Process OSM elements into historic buildings and artwork."""
    historic = []
    artwork = []
    nodes_dict = {}
    seen_ids = set()

    # Build nodes dict
    for elem in elements:
        if elem.get("type") == "node":
            nodes_dict[elem["id"]] = elem

    # Process features
    for elem in elements:
        osm_id = elem.get("id")
        if not osm_id or osm_id in seen_ids:
            continue

        tags = elem.get("tags", {})
        historic_tag = tags.get("historic")
        tourism_tag = tags.get("tourism")
        amenity_tag = tags.get("amenity")

        feature = None
        category = None

        # Categorize
        if historic_tag:
            feature = {
                "type": historic_tag,
                "name": tags.get("name")
            }
            category = "historic"
        elif tourism_tag == "artwork":
            feature = {
                "type": "artwork",
                "name": tags.get("name"),
                "artwork_type": tags.get("artwork_type")
            }
            category = "artwork"
        elif amenity_tag == "fountain":
            feature = {
                "type": "fountain",
                "name": tags.get("name")
            }
            category = "artwork"

        if not feature:
            continue

        seen_ids.add(osm_id)

        # Get coordinates
        elem_lat = elem.get("lat")
        elem_lon = elem.get("lon")

        if elem.get("type") == "way":
            elem_lat, elem_lon, _ = _get_way_geometry(elem, nodes_dict)

        if elem_lat is None:
            continue

        distance_m = haversine_distance(center_lat, center_lon, elem_lat, elem_lon)
        feature["distance_m"] = round(distance_m, 0)

        if category == "historic":
            historic.append(feature)
        elif category == "artwork":
            artwork.append(feature)

    return historic, artwork


def _process_business_features(elements: List[Dict], center_lat: float, center_lon: float) -> Dict:
    """Process OSM elements into categorized businesses by tier."""
    tier1_daily = []
    tier2_social = []
    tier3_culture = []
    tier4_services = []

    seen_ids = set()
    nodes_dict = {}

    # Build nodes dict
    for elem in elements:
        if elem.get("type") == "node":
            nodes_dict[elem["id"]] = elem

    # Process each business
    for elem in elements:
        osm_id = elem.get("id")
        if not osm_id or osm_id in seen_ids:
            continue

        tags = elem.get("tags", {})
        name = tags.get("name")

        # Skip if no name or is a chain
        if not name or tags.get("brand"):
            continue

        seen_ids.add(osm_id)

        # Get coordinates
        elem_lat = elem.get("lat")
        elem_lon = elem.get("lon")

        if elem.get("type") == "way":
            elem_lat, elem_lon, _ = _get_way_geometry(elem, nodes_dict)

        if elem_lat is None:
            continue

        distance_m = haversine_distance(
            center_lat, center_lon, elem_lat, elem_lon)

        amenity = tags.get("amenity", "")
        shop = tags.get("shop", "")
        tourism = tags.get("tourism", "")
        leisure = tags.get("leisure", "")

        business = {
            "name": name,
            "lat": elem_lat,
            "lon": elem_lon,
            "distance_m": round(distance_m, 0)
        }

        # Categorize into tiers
        # TIER 1: Daily Essentials
        if amenity == "cafe":
            business["type"] = "cafe"
            tier1_daily.append(business)
        elif shop == "bakery":
            business["type"] = "bakery"
            tier1_daily.append(business)
        elif shop in ["supermarket", "convenience", "greengrocer"]:
            business["type"] = "grocery"
            tier1_daily.append(business)

        # TIER 2: Social & Dining
        elif amenity == "restaurant":
            business["type"] = "restaurant"
            tier2_social.append(business)
        elif amenity in ["bar", "pub"]:
            business["type"] = "bar"
            tier2_social.append(business)
        elif amenity == "ice_cream" or shop == "ice_cream":
            business["type"] = "ice_cream"
            tier2_social.append(business)

        # TIER 3: Culture & Leisure
        elif shop == "books":
            business["type"] = "bookstore"
            tier3_culture.append(business)
        elif tourism == "gallery" or shop == "art":
            business["type"] = "gallery"
            tier3_culture.append(business)
        elif amenity in ["theatre", "cinema"]:
            business["type"] = "theater"
            tier3_culture.append(business)
        elif tourism == "museum":
            business["type"] = "museum"
            tier3_culture.append(business)
        elif amenity == "marketplace":
            business["type"] = "market"
            tier3_culture.append(business)

        # TIER 4: Services & Retail
        elif shop in ["clothes", "fashion", "boutique"]:
            business["type"] = "boutique"
            tier4_services.append(business)
        elif shop in ["hairdresser", "beauty"]:
            business["type"] = "salon"
            tier4_services.append(business)
        elif shop == "music":
            business["type"] = "records"
            tier4_services.append(business)
        elif leisure == "fitness_centre":
            business["type"] = "fitness"
            tier4_services.append(business)
        elif shop in ["garden_centre", "florist"]:
            business["type"] = "garden"
            tier4_services.append(business)

    return {
        "tier1_daily": tier1_daily,
        "tier2_social": tier2_social,
        "tier3_culture": tier3_culture,
        "tier4_services": tier4_services
    }


def _get_way_geometry(elem: Dict, nodes_dict: Dict) -> Tuple[Optional[float], Optional[float], float]:
    """Calculate centroid and area of a way."""
    if elem.get("type") != "way" or "nodes" not in elem:
        return None, None, 0

    coords = []
    for node_id in elem["nodes"]:
        if node_id in nodes_dict:
            node = nodes_dict[node_id]
            if "lat" in node and "lon" in node:
                coords.append((node["lat"], node["lon"]))

    if not coords:
        return None, None, 0

    # Centroid
    lat = sum(c[0] for c in coords) / len(coords)
    lon = sum(c[1] for c in coords) / len(coords)

    # Area (shoelace formula)
    area = 0
    if len(coords) >= 3:
        for i in range(len(coords)):
            j = (i + 1) % len(coords)
            area += coords[i][0] * coords[j][1]
            area -= coords[j][0] * coords[i][1]
        area = abs(area) / 2
        area = area * 111000 * 111000 * math.cos(math.radians(lat))

    return lat, lon, area


def _get_relation_centroid(elem: Dict, ways_dict: Dict, nodes_dict: Dict) -> Tuple[Optional[float], Optional[float]]:
    """Calculate centroid of a relation from its outer member ways."""
    if elem.get("type") != "relation":
        return None, None
    
    members = elem.get("members", [])
    if not members:
        return None, None
    
    # Collect coordinates from all outer member ways
    all_coords = []
    for member in members:
        if member.get("role") == "outer" and member.get("type") == "way":
            way_id = member.get("ref")
            if way_id in ways_dict:
                way = ways_dict[way_id]
                for node_id in way.get("nodes", []):
                    if node_id in nodes_dict:
                        node = nodes_dict[node_id]
                        if "lat" in node and "lon" in node:
                            all_coords.append((node["lat"], node["lon"]))
    
    # If no outer members found, try any member way
    if not all_coords:
        for member in members:
            if member.get("type") == "way":
                way_id = member.get("ref")
                if way_id in ways_dict:
                    way = ways_dict[way_id]
                    for node_id in way.get("nodes", []):
                        if node_id in nodes_dict:
                            node = nodes_dict[node_id]
                            if "lat" in node and "lon" in node:
                                all_coords.append((node["lat"], node["lon"]))
    
    if not all_coords:
        return None, None
    
    # Calculate centroid
    lat = sum(c[0] for c in all_coords) / len(all_coords)
    lon = sum(c[1] for c in all_coords) / len(all_coords)
    
    return lat, lon


def _deduplicate_by_proximity(features: List[Dict], max_distance_m: float) -> List[Dict]:
    """Remove duplicates within max_distance_m."""
    if len(features) <= 1:
        return features

    unique = []
    for feature in sorted(features, key=lambda x: x.get("area_sqm", 0), reverse=True):
        is_duplicate = False
        for existing in unique:
            dist = haversine_distance(
                feature["lat"], feature["lon"],
                existing["lat"], existing["lon"]
            )
            if dist < max_distance_m:
                is_duplicate = True
                break

        if not is_duplicate:
            unique.append(feature)

    return unique


def _get_park_type_name(leisure, landuse, natural):
    """Get readable name for park type."""
    if leisure:
        return leisure.replace("_", " ").title()
    elif landuse:
        return landuse.replace("_", " ").title()
    elif natural == "wood":
        return "Woods"
    elif natural == "forest":
        return "Forest"
    elif natural == "scrub":
        return "Natural Area"
    return "Green Space"


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points in meters."""
    R = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi/2)**2 + math.cos(phi1) * \
        math.cos(phi2) * math.sin(delta_lambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

    return R * c