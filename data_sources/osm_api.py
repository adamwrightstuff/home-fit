"""
OpenStreetMap API Client
Queries Overpass API for green spaces and nature features
"""

import requests
import math
import time
from typing import Dict, List, Tuple, Optional, Any
from .cache import cached, CACHE_TTL
from .error_handling import with_fallback, safe_api_call, handle_api_timeout

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

def _retry_overpass(request_fn, attempts: int = 3, base_wait: float = 0.8):
    """Simple retry with exponential backoff for Overpass requests."""
    import time
    for i in range(attempts):
        try:
            resp = request_fn()
            # Handle 429 rate limiting specifically
            if resp is not None and hasattr(resp, 'status_code'):
                if resp.status_code == 429:
                    # Rate limited - wait longer and retry
                    retry_after = int(resp.headers.get('Retry-After', base_wait * (2 ** i)))
                    if i < attempts - 1:
                        print(f"⚠️  OSM rate limited (429), waiting {retry_after}s before retry...")
                        time.sleep(retry_after)
                        continue
                    else:
                        print(f"⚠️  OSM rate limited (429), max retries reached")
                        return resp
            return resp
        except Exception as e:
            if i == attempts - 1:
                raise
            time.sleep(base_wait * (1.5 ** i))

DEBUG_PARKS = True  # Set False to silence park debugging


@cached(ttl_seconds=CACHE_TTL['osm_queries'])
@safe_api_call("osm", required=False)
@handle_api_timeout(timeout_seconds=30)
def query_green_spaces(lat: float, lon: float, radius_m: int = 1000) -> Optional[Dict]:
    """
    Query OSM for parks, playgrounds, and tree features.
    INCLUDES RELATIONS to catch all parks!

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
      // PARKS & GREEN SPACES - INCLUDING RELATIONS!
      way["leisure"="park"](around:{radius_m},{lat},{lon});
      relation["leisure"="park"](around:{radius_m},{lat},{lon});
      node["leisure"="park"](around:{radius_m},{lat},{lon});
      
      way["leisure"="garden"]["garden:type"!="private"](around:{radius_m},{lat},{lon});
      relation["leisure"="garden"]["garden:type"!="private"](around:{radius_m},{lat},{lon});
      
      way["leisure"="dog_park"](around:{radius_m},{lat},{lon});
      relation["leisure"="dog_park"](around:{radius_m},{lat},{lon});
      
      way["landuse"="recreation_ground"](around:{radius_m},{lat},{lon});
      relation["landuse"="recreation_ground"](around:{radius_m},{lat},{lon});
      
      way["landuse"="village_green"](around:{radius_m},{lat},{lon});
      relation["landuse"="village_green"](around:{radius_m},{lat},{lon});
      
      // LOCAL NATURE
      way["natural"="wood"](around:{radius_m},{lat},{lon});
      relation["natural"="wood"](around:{radius_m},{lat},{lon});
      
      way["natural"="forest"](around:{radius_m},{lat},{lon});
      relation["natural"="forest"](around:{radius_m},{lat},{lon});
      
      way["natural"="scrub"](around:{radius_m},{lat},{lon});
      relation["natural"="scrub"](around:{radius_m},{lat},{lon});
      
      // PLAYGROUNDS
      node["leisure"="playground"](around:{radius_m},{lat},{lon});
      way["leisure"="playground"](around:{radius_m},{lat},{lon});
      relation["leisure"="playground"](around:{radius_m},{lat},{lon});
      
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


@cached(ttl_seconds=CACHE_TTL['osm_queries'])
@safe_api_call("osm", required=False)
@handle_api_timeout(timeout_seconds=40)
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
        def _do_request():
            r = requests.post(
                OVERPASS_URL,
                data={"data": query},
                timeout=50,
                headers={"User-Agent": "HomeFit/1.0"}
            )
            if r.status_code != 200:
                raise RuntimeError(f"Overpass status={r.status_code}")
            return r

        resp = _retry_overpass(_do_request, attempts=3, base_wait=0.8)
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


def query_enhanced_trees(lat: float, lon: float, radius_m: int = 1000) -> Optional[Dict]:
    """
    Enhanced tree query with comprehensive tree data from OSM.
    
    Returns:
        {
            "tree_rows": [...],
            "street_trees": [...],
            "individual_trees": [...],
            "tree_areas": [...]
        }
    """
    query = f"""
    [out:json][timeout:30];
    (
      // TREE ROWS
      way["natural"="tree_row"](around:{radius_m},{lat},{lon});
      
      // STREET TREES
      way["highway"]["trees"="yes"](around:{radius_m},{lat},{lon});
      way["highway"]["trees:both"="yes"](around:{radius_m},{lat},{lon});
      way["highway"]["trees:left"="yes"](around:{radius_m},{lat},{lon});
      way["highway"]["trees:right"="yes"](around:{radius_m},{lat},{lon});
      
      // INDIVIDUAL TREES
      node["natural"="tree"](around:{radius_m},{lat},{lon});
      
      // TREE AREAS
      way["natural"="wood"](around:{radius_m},{lat},{lon});
      way["landuse"="forest"](around:{radius_m},{lat},{lon});
      way["leisure"="park"]["trees"="yes"](around:{radius_m},{lat},{lon});
    );
    out body;
    >;
    out skel qt;
    """

    try:
        resp = requests.post(
            OVERPASS_URL,
            data={"data": query},
            timeout=40,
            headers={"User-Agent": "HomeFit/1.0"}
        )

        if resp.status_code != 200:
            return None

        data = resp.json()
        elements = data.get("elements", [])

        tree_rows, street_trees, individual_trees, tree_areas = _process_enhanced_trees(
            elements, lat, lon)

        return {
            "tree_rows": tree_rows,
            "street_trees": street_trees,
            "individual_trees": individual_trees,
            "tree_areas": tree_areas
        }

    except Exception as e:
        print(f"OSM enhanced tree query error: {e}")
        return None


def query_cultural_assets(lat: float, lon: float, radius_m: int = 1000) -> Optional[Dict]:
    """
    Query OSM for cultural and artistic assets.
    
    Returns:
        {
            "museums": [...],
            "galleries": [...],
            "theaters": [...],
            "public_art": [...],
            "cultural_venues": [...]
        }
    """
    query = f"""
    [out:json][timeout:35];
    (
      // MUSEUMS
      node["tourism"="museum"](around:{radius_m},{lat},{lon});
      way["tourism"="museum"](around:{radius_m},{lat},{lon});
      
      // GALLERIES & ART SPACES
      node["tourism"="gallery"](around:{radius_m},{lat},{lon});
      way["tourism"="gallery"](around:{radius_m},{lat},{lon});
      node["shop"="art"](around:{radius_m},{lat},{lon});
      way["shop"="art"](around:{radius_m},{lat},{lon});
      
      // THEATERS & PERFORMANCE
      node["amenity"~"theatre|cinema"](around:{radius_m},{lat},{lon});
      way["amenity"~"theatre|cinema"](around:{radius_m},{lat},{lon});
      node["leisure"="arts_centre"](around:{radius_m},{lat},{lon});
      way["leisure"="arts_centre"](around:{radius_m},{lat},{lon});
      
      // PUBLIC ART
      node["tourism"="artwork"](around:{radius_m},{lat},{lon});
      way["tourism"="artwork"](around:{radius_m},{lat},{lon});
      node["amenity"="fountain"](around:{radius_m},{lat},{lon});
      way["amenity"="fountain"](around:{radius_m},{lat},{lon});
      
      // CULTURAL VENUES
      node["amenity"="community_centre"](around:{radius_m},{lat},{lon});
      way["amenity"="community_centre"](around:{radius_m},{lat},{lon});
      node["amenity"="library"](around:{radius_m},{lat},{lon});
      way["amenity"="library"](around:{radius_m},{lat},{lon});
    );
    out body;
    >;
    out skel qt;
    """

    try:
        resp = requests.post(
            OVERPASS_URL,
            data={"data": query},
            timeout=45,
            headers={"User-Agent": "HomeFit/1.0"}
        )

        if resp.status_code != 200:
            return None

        data = resp.json()
        elements = data.get("elements", [])

        museums, galleries, theaters, public_art, cultural_venues = _process_cultural_assets(
            elements, lat, lon)

        return {
            "museums": museums,
            "galleries": galleries,
            "theaters": theaters,
            "public_art": public_art,
            "cultural_venues": cultural_venues
        }

    except Exception as e:
        print(f"OSM cultural assets query error: {e}")
        return None


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


@cached(ttl_seconds=CACHE_TTL['osm_queries'])
@safe_api_call("osm", required=False)
@handle_api_timeout(timeout_seconds=60)
def query_local_businesses(lat: float, lon: float, radius_m: int = 1000, include_chains: bool = False) -> Optional[Dict]:
    """
    Query OSM for local businesses within walking distance.
    By default focuses on non-chain establishments.

    Args:
        include_chains: If True, include chain/franchise businesses

    Returns:
        {
            "tier1_daily": [...],
            "tier2_social": [...],
            "tier3_culture": [...],
            "tier4_services": [...]
        }
    """
    # Brand filter: exclude known chains by default
    if not include_chains:
        # Exclude major chains/franchises but allow local businesses with brand tags
        brand_filter = '''["brand"!~"McDonald's|Starbucks|Subway|KFC|Burger King|Pizza Hut|Domino's|Taco Bell|Wendy's|Dunkin'|Dunkin Donuts|7-Eleven|CVS|Walgreens|Rite Aid|Target|Walmart|Home Depot|Lowe's|Best Buy|Apple Store|AT&T|Verizon|T-Mobile|Chase|Bank of America|Wells Fargo|Citibank|FedEx|UPS|DHL|UPS Store|FedEx Office"]'''
    else:
        brand_filter = ''
    
    query = f"""
    [out:json][timeout:60];
    (
      // TIER 1: DAILY ESSENTIALS
      node["amenity"="cafe"]["name"]{brand_filter}(around:{radius_m},{lat},{lon});
      way["amenity"="cafe"]["name"]{brand_filter}(around:{radius_m},{lat},{lon});
      
      node["shop"="bakery"]["name"]{brand_filter}(around:{radius_m},{lat},{lon});
      way["shop"="bakery"]["name"]{brand_filter}(around:{radius_m},{lat},{lon});
      
      node["shop"~"supermarket|convenience|greengrocer"]["name"]{brand_filter}(around:{radius_m},{lat},{lon});
      way["shop"~"supermarket|convenience|greengrocer"]["name"]{brand_filter}(around:{radius_m},{lat},{lon});
      
      // TIER 2: SOCIAL & DINING
      node["amenity"="restaurant"]["name"]{brand_filter}(around:{radius_m},{lat},{lon});
      way["amenity"="restaurant"]["name"]{brand_filter}(around:{radius_m},{lat},{lon});
      
      node["amenity"~"bar|pub"]["name"]{brand_filter}(around:{radius_m},{lat},{lon});
      way["amenity"~"bar|pub"]["name"]{brand_filter}(around:{radius_m},{lat},{lon});
      
      node["amenity"="ice_cream"]["name"]{brand_filter}(around:{radius_m},{lat},{lon});
      node["shop"="ice_cream"]["name"]{brand_filter}(around:{radius_m},{lat},{lon});
      way["shop"="ice_cream"]["name"]{brand_filter}(around:{radius_m},{lat},{lon});
      
      // TIER 3: CULTURE & LEISURE
      node["shop"="books"]["name"]{brand_filter}(around:{radius_m},{lat},{lon});
      way["shop"="books"]["name"]{brand_filter}(around:{radius_m},{lat},{lon});
      
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
      node["shop"~"clothes|fashion|boutique"]["name"]{brand_filter}(around:{radius_m},{lat},{lon});
      way["shop"~"clothes|fashion|boutique"]["name"]{brand_filter}(around:{radius_m},{lat},{lon});
      
      node["shop"~"hairdresser|beauty"]["name"]{brand_filter}(around:{radius_m},{lat},{lon});
      way["shop"~"hairdresser|beauty"]["name"]{brand_filter}(around:{radius_m},{lat},{lon});
      
      node["shop"="music"]["name"]{brand_filter}(around:{radius_m},{lat},{lon});
      way["shop"="music"]["name"]{brand_filter}(around:{radius_m},{lat},{lon});
      
      node["leisure"="fitness_centre"]["name"]{brand_filter}(around:{radius_m},{lat},{lon});
      way["leisure"="fitness_centre"]["name"]{brand_filter}(around:{radius_m},{lat},{lon});
      
      node["shop"~"garden_centre|florist"]["name"]{brand_filter}(around:{radius_m},{lat},{lon});
      way["shop"~"garden_centre|florist"]["name"]{brand_filter}(around:{radius_m},{lat},{lon});
    );
    out body;
    >;
    out skel qt;
    """

    def _do_request():
        return requests.post(
            OVERPASS_URL,
            data={"data": query},
            timeout=70,
            headers={"User-Agent": "HomeFit/1.0"}
        )
    
    try:
        resp = _retry_overpass(_do_request, attempts=3, base_wait=1.0)

        if resp is None or resp.status_code != 200:
            if resp and resp.status_code == 429:
                print(f"⚠️  OSM business query rate limited (429)")
            return None

        data = resp.json()
        elements = data.get("elements", [])

        businesses = _process_business_features(elements, lat, lon, include_chains)
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
    ways_dict = {}
    seen_park_ids = set()
    seen_playground_ids = set()

    # Build nodes and ways dicts
    for elem in elements:
        if elem.get("type") == "node":
            nodes_dict[elem["id"]] = elem
        elif elem.get("type") == "way":
            ways_dict[elem["id"]] = elem

    debug_raw_candidates = []
    debug_kept_parks = []
    debug_skipped_parks = []

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
        elem_type = elem.get("type")

        # Parks (exclude natural woods/forests/scrub from parks)
        if leisure in ["park", "dog_park", "recreation_ground"] or \
           (leisure == "garden" and tags.get("garden:type") != "private") or \
           landuse in ["park", "recreation_ground", "village_green"]:

            if osm_id in seen_park_ids:
                continue
            seen_park_ids.add(osm_id)

            elem_lat, elem_lon, area_sqm = None, None, 0
            centroid_reason = "ok"
            if elem_type == "way":
                elem_lat, elem_lon, area_sqm = _get_way_geometry(elem, nodes_dict)
                if elem_lat is None:
                    centroid_reason = "way-geometry-fail"
            elif elem_type == "relation":
                elem_lat, elem_lon = _get_relation_centroid(elem, ways_dict, nodes_dict)
                area_sqm = 0
                if elem_lat is None:
                    centroid_reason = "relation-centroid-fail"
            elif elem_type == "node" and leisure == "park":
                elem_lat = elem.get("lat")
                elem_lon = elem.get("lon")
                area_sqm = 0
                if elem_lat is None or elem_lon is None:
                    centroid_reason = "node-coords-missing"

            distance_m = None
            if elem_lat is not None:
                distance_m = haversine_distance(center_lat, center_lon, elem_lat, elem_lon)

            park_debug = {
                "osm_id": osm_id,
                "name": tags.get("name"),
                "elem_type": elem_type,
                "centroid_reason": centroid_reason,
                "lat": elem_lat,
                "lon": elem_lon,
                "area_sqm": area_sqm,
                "distance_m": distance_m
            }

            # Exclude marinas/clubs from parks
            name_val = (tags.get("name") or "").lower()
            is_marina = (tags.get("leisure") == "marina") or (tags.get("amenity") == "marina")
            has_club_tag = any(k == "club" for k in tags.keys())
            name_is_club = any(term in name_val for term in ["yacht club", "shore club", "country club", "beach club"]) if name_val else False
            if is_marina or has_club_tag or name_is_club:
                debug_skipped_parks.append({**park_debug, "centroid_reason": "excluded-nonpublic"})
                if DEBUG_PARKS:
                    print(f"[PARK SKIP] id={osm_id} name={tags.get('name')} type={elem_type} reason=excluded-nonpublic")
                continue

            if elem_lat is None:
                debug_skipped_parks.append(park_debug)
                if DEBUG_PARKS:
                    print(f"[PARK SKIP] id={osm_id} name={tags.get('name')} type={elem_type} reason={centroid_reason}")
                continue

            debug_raw_candidates.append(park_debug)

            parks.append({
                "name": tags.get("name", _get_park_type_name(leisure, landuse, natural)),
                "type": leisure or landuse or natural,
                "lat": elem_lat,
                "lon": elem_lon,
                "distance_m": round(distance_m, 0) if distance_m is not None else None,
                "area_sqm": round(area_sqm, 0) if area_sqm else 0,
                "osm_id": osm_id
            })
    # Deduplicate (increase to 150m to collapse same-name multi-polygons)
    pre_dedup_count = len(parks)
    parks = _deduplicate_by_proximity(parks, 150)
    post_dedup_count = len(parks)
    for p in parks:
        debug_kept_parks.append({k: p[k] for k in ["osm_id", "name", "lat", "lon", "distance_m", "area_sqm"]})

    if DEBUG_PARKS:
        print("========= PARK DEBUG REPORT =========")
        print(f"Pre-dedup candidates: {pre_dedup_count}")
        for c in debug_raw_candidates:
            print(f"[CANDIDATE] id={c['osm_id']} name={c['name']} type={c['elem_type']} lat={c['lat']} lon={c['lon']} dist={c['distance_m']} area={c['area_sqm']}")
        print(f"Kept after dedup: {post_dedup_count}")
        for p in debug_kept_parks:
            print(f"[KEPT    ] id={p['osm_id']} name={p['name']} lat={p['lat']} lon={p['lon']} dist={p['distance_m']} area={p['area_sqm']}")
        if debug_skipped_parks:
            print(f"Skipped parks (not kept): {len(debug_skipped_parks)}")
            for s in debug_skipped_parks:
                print(f"[SKIPPED ] id={s['osm_id']} name={s['name']} reason={s['centroid_reason']}")
        print("=====================================")

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

        elem_lat = None
        elem_lon = None
        
        if elem_type == "way":
            elem_lat, elem_lon, _ = _get_way_geometry(elem, nodes_dict)
        elif elem_type == "relation":
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


def query_local_paths_within_green_areas(lat: float, lon: float, radius_m: int = 1500) -> int:
    """
    Count clusters of path/footway segments within local radius.
    Clusters are grouped by ~120m; return min(5, clusters).
    """
    try:
        q = f"""
        [out:json][timeout:25];
        (
          way["highway"~"^(path|footway)$"](around:{radius_m},{lat},{lon});
        );
        out geom;
        """
        resp = requests.post(OVERPASS_URL, data={"data": q}, timeout=25, headers={"User-Agent":"HomeFit/1.0"})
        if resp.status_code != 200:
            return 0
        ways = resp.json().get("elements", [])
        def _centroid(w):
            pts = [(n.get('lat'), n.get('lon')) for n in (w.get('geometry') or []) if 'lat' in n and 'lon' in n]
            pts = [(a,b) for a,b in pts if a is not None and b is not None]
            if not pts:
                return None
            return (sum(p[0] for p in pts)/len(pts), sum(p[1] for p in pts)/len(pts))
        centroids = []
        for w in ways:
            c = _centroid(w)
            if c:
                centroids.append(c)
        clusters = []
        from math import radians, sin, cos, asin, sqrt
        def dkm(a,b):
            R=6371
            lat1,lon1=a; lat2,lon2=b
            dlat=radians(lat2-lat1); dlon=radians(lon2-lon1)
            x=sin(dlat/2)**2+cos(radians(lat1))*cos(radians(lat2))*sin(dlon/2)**2
            return 2*R*asin(sqrt(x))
        for c in centroids:
            placed=False
            for group in clusters:
                if dkm(c, group['center']) <= 0.12:  # ~120m
                    group['points'].append(c)
                    lat = sum(p[0] for p in group['points'])/len(group['points'])
                    lon = sum(p[1] for p in group['points'])/len(group['points'])
                    group['center']=(lat,lon)
                    placed=True
                    break
            if not placed:
                clusters.append({'center':c,'points':[c]})
        return min(5, len(clusters))
    except Exception:
        return 0


def _process_charm_features(elements: List[Dict], center_lat: float, center_lon: float) -> Tuple[List[Dict], List[Dict]]:
    """Process OSM elements into historic buildings and artwork."""
    historic = []
    artwork = []
    nodes_dict = {}
    seen_ids = set()

    for elem in elements:
        if elem.get("type") == "node":
            nodes_dict[elem["id"]] = elem

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


def query_beauty_enhancers(lat: float, lon: float, radius_m: int = 1500) -> Dict[str, int]:
    """
    Return presence flags for aesthetics: viewpoints, artwork, fountains, waterfront.
    Lightweight and capped upstream.
    """
    out = {"viewpoints": 0, "artwork": 0, "fountains": 0, "waterfront": 0}
    try:
        q = f"""
        [out:json][timeout:20];
        (
          node["tourism"="viewpoint"](around:{radius_m},{lat},{lon});
          way["tourism"="viewpoint"](around:{radius_m},{lat},{lon});
          node["tourism"="artwork"](around:{radius_m},{lat},{lon});
          way["tourism"="artwork"](around:{radius_m},{lat},{lon});
          node["amenity"="fountain"](around:{radius_m},{lat},{lon});
          way["amenity"="fountain"](around:{radius_m},{lat},{lon});
        );
        out count;
        """
        r = requests.post(OVERPASS_URL, data={"data": q}, timeout=25, headers={"User-Agent":"HomeFit/1.0"})
        if r.status_code == 200:
            # If any returned, set presence flags (fast path). For exact counts, split queries.
            out["viewpoints"] = 1
            out["artwork"] = 1
            out["fountains"] = 1
    except Exception:
        pass
    # Coastline probe reused (2km)
    try:
        qc = f"""
        [out:json][timeout:15];
        way["natural"="coastline"](around:2000,{lat},{lon});
        out center 1;
        """
        rc = requests.post(OVERPASS_URL, data={"data": qc}, timeout=20, headers={"User-Agent":"HomeFit/1.0"})
        if rc.status_code == 200 and rc.json().get("elements"):
            out["waterfront"] = 1
    except Exception:
        pass
    return out

def _process_business_features(elements: List[Dict], center_lat: float, center_lon: float, include_chains: bool = False) -> Dict:
    """Process OSM elements into categorized businesses by tier."""
    tier1_daily = []
    tier2_social = []
    tier3_culture = []
    tier4_services = []

    seen_ids = set()
    nodes_dict = {}

    for elem in elements:
        if elem.get("type") == "node":
            nodes_dict[elem["id"]] = elem

    for elem in elements:
        osm_id = elem.get("id")
        if not osm_id or osm_id in seen_ids:
            continue

        tags = elem.get("tags", {})
        name = tags.get("name")

        if not name or (not include_chains and tags.get("brand")):
            continue

        seen_ids.add(osm_id)

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

        if amenity == "cafe":
            business["type"] = "cafe"
            tier1_daily.append(business)
        elif shop == "bakery":
            business["type"] = "bakery"
            tier1_daily.append(business)
        elif shop in ["supermarket", "convenience", "greengrocer"]:
            business["type"] = "grocery"
            tier1_daily.append(business)
        elif amenity == "restaurant":
            business["type"] = "restaurant"
            tier2_social.append(business)
        elif amenity in ["bar", "pub"]:
            business["type"] = "bar"
            tier2_social.append(business)
        elif amenity == "ice_cream" or shop == "ice_cream":
            business["type"] = "ice_cream"
            tier2_social.append(business)
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

    lat = sum(c[0] for c in coords) / len(coords)
    lon = sum(c[1] for c in coords) / len(coords)

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
    
    lat = sum(c[0] for c in all_coords) / len(all_coords)
    lon = sum(c[1] for c in all_coords) / len(all_coords)
    
    return lat, lon


def _deduplicate_by_proximity(features: List[Dict], max_distance_m: float) -> List[Dict]:
    """Remove duplicates within max_distance_m. Keep both if names differ and are both non-empty."""
    if len(features) <= 1:
        return features

    unique = []
    for feature in sorted(features, key=lambda x: x.get("area_sqm", 0), reverse=True):
        is_duplicate = False
        for existing in unique:
            dist = haversine_distance(
                feature["lat"], feature["lon"],
                existing["lat"], existing["lon"])
            names_differ = (
                (feature.get("name") or "").strip() != (existing.get("name") or "").strip()
                and (feature.get("name") or "").strip()
                and (existing.get("name") or "").strip()
            )
            if dist < max_distance_m and not names_differ:
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


def _process_enhanced_trees(elements: List[Dict], center_lat: float, center_lon: float) -> Tuple[List[Dict], List[Dict], List[Dict], List[Dict]]:
    """Process OSM elements into enhanced tree categories."""
    tree_rows = []
    street_trees = []
    individual_trees = []
    tree_areas = []
    nodes_dict = {}
    ways_dict = {}
    seen_ids = set()

    # Build nodes and ways dicts
    for elem in elements:
        if elem.get("type") == "node":
            nodes_dict[elem["id"]] = elem
        elif elem.get("type") == "way":
            ways_dict[elem["id"]] = elem

    for elem in elements:
        osm_id = elem.get("id")
        if not osm_id or osm_id in seen_ids:
            continue

        tags = elem.get("tags", {})
        natural = tags.get("natural")
        highway = tags.get("highway")
        leisure = tags.get("leisure")
        landuse = tags.get("landuse")
        elem_type = elem.get("type")

        seen_ids.add(osm_id)

        elem_lat = None
        elem_lon = None

        if elem_type == "node":
            elem_lat = elem.get("lat")
            elem_lon = elem.get("lon")
        elif elem_type == "way":
            elem_lat, elem_lon, _ = _get_way_geometry(elem, nodes_dict)

        if elem_lat is None:
            continue

        distance_m = haversine_distance(center_lat, center_lon, elem_lat, elem_lon)

        tree_feature = {
            "name": tags.get("name"),
            "lat": elem_lat,
            "lon": elem_lon,
            "distance_m": round(distance_m, 0),
            "type": natural or highway or leisure or landuse
        }

        # Categorize trees
        if natural == "tree_row":
            tree_rows.append(tree_feature)
        elif highway and any(tags.get(k) == "yes" for k in ["trees", "trees:both", "trees:left", "trees:right"]):
            street_trees.append(tree_feature)
        elif natural == "tree":
            individual_trees.append(tree_feature)
        elif natural in ["wood", "forest"] or landuse == "forest" or (leisure == "park" and tags.get("trees") == "yes"):
            tree_areas.append(tree_feature)

    # Limit individual trees to top 50 closest to prevent response bloat
    # This doesn't affect scoring since only count matters, not coordinates
    individual_trees = sorted(individual_trees, key=lambda x: x['distance_m'])[:50]
    
    return tree_rows, street_trees, individual_trees, tree_areas


def _process_cultural_assets(elements: List[Dict], center_lat: float, center_lon: float) -> Tuple[List[Dict], List[Dict], List[Dict], List[Dict], List[Dict]]:
    """Process OSM elements into cultural asset categories."""
    museums = []
    galleries = []
    theaters = []
    public_art = []
    cultural_venues = []
    nodes_dict = {}
    seen_ids = set()

    for elem in elements:
        if elem.get("type") == "node":
            nodes_dict[elem["id"]] = elem

    for elem in elements:
        osm_id = elem.get("id")
        if not osm_id or osm_id in seen_ids:
            continue

        tags = elem.get("tags", {})
        tourism = tags.get("tourism")
        amenity = tags.get("amenity")
        shop = tags.get("shop")
        leisure = tags.get("leisure")
        elem_type = elem.get("type")

        seen_ids.add(osm_id)

        elem_lat = None
        elem_lon = None

        if elem_type == "node":
            elem_lat = elem.get("lat")
            elem_lon = elem.get("lon")
        elif elem_type == "way":
            elem_lat, elem_lon, _ = _get_way_geometry(elem, nodes_dict)

        if elem_lat is None:
            continue

        distance_m = haversine_distance(center_lat, center_lon, elem_lat, elem_lon)

        cultural_feature = {
            "name": tags.get("name"),
            "lat": elem_lat,
            "lon": elem_lon,
            "distance_m": round(distance_m, 0),
            "type": tourism or amenity or shop or leisure
        }

        # Categorize cultural assets
        if tourism == "museum":
            museums.append(cultural_feature)
        elif tourism == "gallery" or shop == "art":
            galleries.append(cultural_feature)
        elif amenity in ["theatre", "cinema"] or leisure == "arts_centre":
            theaters.append(cultural_feature)
        elif tourism == "artwork" or amenity == "fountain":
            public_art.append(cultural_feature)
        elif amenity in ["community_centre", "library"]:
            cultural_venues.append(cultural_feature)

    return museums, galleries, theaters, public_art, cultural_venues


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


def validate_osm_completeness(lat: float, lon: float) -> Dict[str, Any]:
    """
    Validate OSM data completeness for a location.
    
    Args:
        lat: Latitude
        lon: Longitude
        
    Returns:
        {
            "parks_coverage": bool,
            "businesses_coverage": bool,
            "healthcare_coverage": bool,
            "transport_coverage": bool,
            "overall_coverage": str  # "excellent", "good", "fair", "poor"
        }
    """
    coverage = {
        "parks_coverage": False,
        "businesses_coverage": False,
        "healthcare_coverage": False,
        "transport_coverage": False
    }
    
    # Test parks coverage
    try:
        parks_data = query_green_spaces(lat, lon, radius_m=1000)
        coverage["parks_coverage"] = bool(parks_data and (parks_data.get("parks") or parks_data.get("playgrounds")))
    except:
        pass
    
    # Test businesses coverage
    try:
        businesses_data = query_local_businesses(lat, lon, radius_m=1000)
        coverage["businesses_coverage"] = bool(businesses_data and len(businesses_data.get("businesses", [])) > 0)
    except:
        pass
    
    # Test healthcare coverage
    try:
        healthcare_data = query_healthcare(lat, lon, radius_m=5000)
        coverage["healthcare_coverage"] = bool(healthcare_data and len(healthcare_data.get("facilities", [])) > 0)
    except:
        pass
    
    # Test transport coverage
    try:
        # Simple check for nearby roads
        query = f"""
        [out:json][timeout:10];
        (
          way["highway"~"^(primary|secondary|tertiary|residential)$"](around:500,{lat},{lon});
        );
        out count;
        """
        resp = requests.post(
            OVERPASS_URL,
            data={"data": query},
            timeout=15,
            headers={"User-Agent": "HomeFit/1.0"}
        )
        if resp.status_code == 200:
            data = resp.json()
            coverage["transport_coverage"] = len(data.get("elements", [])) > 5
    except:
        pass
    
    # Calculate overall coverage
    coverage_count = sum(1 for v in coverage.values() if v)
    if coverage_count >= 3:
        coverage["overall_coverage"] = "excellent"
    elif coverage_count == 2:
        coverage["overall_coverage"] = "good"
    elif coverage_count == 1:
        coverage["overall_coverage"] = "fair"
    else:
        coverage["overall_coverage"] = "poor"
    
    return coverage


@cached(ttl_seconds=CACHE_TTL['osm_queries'])
@safe_api_call("osm", required=False)
@handle_api_timeout(timeout_seconds=40)
def query_healthcare_facilities(lat: float, lon: float, radius_m: int = 10000) -> Optional[Dict]:
    """
    Query OSM for comprehensive healthcare facilities.
    
    Returns:
        {
            "hospitals": [...],
            "urgent_care": [...],
            "clinics": [...],
            "pharmacies": [...],
            "doctors": [...]
        }
    """
    query = f"""
    [out:json][timeout:40];
    (
      // HOSPITALS & MAJOR MEDICAL CENTERS - EXPANDED DETECTION
      node["amenity"="hospital"](around:{radius_m},{lat},{lon});
      way["amenity"="hospital"](around:{radius_m},{lat},{lon});
      relation["amenity"="hospital"](around:{radius_m},{lat},{lon});
      
      // Additional hospital tags
      node["healthcare"="hospital"](around:{radius_m},{lat},{lon});
      way["healthcare"="hospital"](around:{radius_m},{lat},{lon});
      relation["healthcare"="hospital"](around:{radius_m},{lat},{lon});
      
      // Medical centers and health centers
      node["amenity"="medical_centre"](around:{radius_m},{lat},{lon});
      way["amenity"="medical_centre"](around:{radius_m},{lat},{lon});
      relation["amenity"="medical_centre"](around:{radius_m},{lat},{lon});
      
      node["healthcare"="medical_centre"](around:{radius_m},{lat},{lon});
      way["healthcare"="medical_centre"](around:{radius_m},{lat},{lon});
      relation["healthcare"="medical_centre"](around:{radius_m},{lat},{lon});
      
      // URGENT CARE & EMERGENCY CARE - EXPANDED DETECTION
      node["amenity"="emergency_ward"](around:{radius_m},{lat},{lon});
      way["amenity"="emergency_ward"](around:{radius_m},{lat},{lon});
      
      node["emergency"="yes"]["amenity"~"clinic|hospital"](around:{radius_m},{lat},{lon});
      way["emergency"="yes"]["amenity"~"clinic|hospital"](around:{radius_m},{lat},{lon});
      
      // Urgent care specific tags
      node["healthcare"="urgent_care"](around:{radius_m},{lat},{lon});
      way["healthcare"="urgent_care"](around:{radius_m},{lat},{lon});
      node["healthcare"="emergency"](around:{radius_m},{lat},{lon});
      way["healthcare"="emergency"](around:{radius_m},{lat},{lon});
      
      // Walk-in clinics (often urgent care)
      node["amenity"="clinic"]["healthcare:speciality"~"urgent|emergency|walk.*in|walk-in"](around:{radius_m},{lat},{lon});
      way["amenity"="clinic"]["healthcare:speciality"~"urgent|emergency|walk.*in|walk-in"](around:{radius_m},{lat},{lon});
      
      // CLINICS & MEDICAL CENTERS
      node["amenity"="clinic"](around:{radius_m},{lat},{lon});
      way["amenity"="clinic"](around:{radius_m},{lat},{lon});
      relation["amenity"="clinic"](around:{radius_m},{lat},{lon});
      
      node["amenity"="doctors"](around:{radius_m},{lat},{lon});
      way["amenity"="doctors"](around:{radius_m},{lat},{lon});
      
      // PHARMACIES & DRUGSTORES
      node["amenity"="pharmacy"](around:{radius_m},{lat},{lon});
      way["amenity"="pharmacy"](around:{radius_m},{lat},{lon});
      
      node["shop"="pharmacy"](around:{radius_m},{lat},{lon});
      way["shop"="pharmacy"](around:{radius_m},{lat},{lon});
      
      // DENTAL & SPECIALTY CARE
      node["amenity"="dentist"](around:{radius_m},{lat},{lon});
      way["amenity"="dentist"](around:{radius_m},{lat},{lon});
      
      node["amenity"="veterinary"](around:{radius_m},{lat},{lon});
      way["amenity"="veterinary"](around:{radius_m},{lat},{lon});
    );
    out body;
    >;
    out skel qt;
    """
    
    def _do_request():
        return requests.post(OVERPASS_URL, data={"data": query}, timeout=45, headers={"User-Agent": "HomeFit/1.0"})
    
    try:
        print(f"🏥 Querying comprehensive healthcare facilities within {radius_m/1000:.0f}km...")
        resp = _retry_overpass(_do_request, attempts=3, base_wait=1.0)
        
        if resp is None or resp.status_code != 200:
            if resp and resp.status_code == 429:
                print(f"⚠️  Healthcare query rate limited (429) - max retries reached")
                print(f"   Consider: Increasing retry attempts or adding delay between requests")
            elif resp:
                print(f"⚠️  Healthcare query failed: HTTP {resp.status_code}")
                print(f"   Response preview: {resp.text[:200] if hasattr(resp, 'text') else 'N/A'}")
            else:
                print(f"⚠️  Healthcare query failed: No response (timeout or network error)")
            return None

        data = resp.json()
        elements = data.get("elements", [])
        
        hospitals = []
        urgent_care = []
        clinics = []
        pharmacies = []
        doctors = []
        
        for elem in elements:
            tags = elem.get("tags", {})
            amenity = tags.get("amenity", "")
            name = tags.get("name") or tags.get("brand") or "Unnamed Facility"
            
            # Calculate distance
            if "lat" in elem and "lon" in elem:
                distance_km = haversine_distance(lat, lon, elem["lat"], elem["lon"])
            else:
                # For ways/relations, use center point
                distance_km = 0.0
            
            facility = {
                "name": name,
                "lat": elem.get("lat"),
                "lon": elem.get("lon"),
                "distance_km": round(distance_km, 1),
                "amenity": amenity,
                "emergency": tags.get("emergency"),
                "beds": tags.get("beds"),
                "tags": tags
            }
            
            # Categorize facilities - IMPROVED LOGIC
            healthcare = tags.get("healthcare", "")
            healthcare_specialty = tags.get("healthcare:speciality", "").lower()
            name_lower = name.lower()
            
            # Hospitals and major medical centers (exclude if it's urgent care branded)
            if (amenity == "hospital" or healthcare == "hospital" or 
                (amenity == "medical_centre" and healthcare != "urgent_care")):
                hospitals.append(facility)
            # Urgent care - check multiple indicators
            elif (amenity == "emergency_ward" or 
                  healthcare == "urgent_care" or
                  healthcare == "emergency" or
                  (amenity == "clinic" and (
                      "urgent" in name_lower or
                      "walk-in" in name_lower or
                      "walk in" in name_lower or
                      "immediate" in name_lower or
                      "urgent" in healthcare_specialty or
                      "emergency" in healthcare_specialty
                  )) or
                  tags.get("emergency") == "yes"):
                urgent_care.append(facility)
            # Regular clinics and medical centers
            elif amenity in ["clinic", "doctors"]:
                if amenity == "clinic":
                    clinics.append(facility)
                else:
                    doctors.append(facility)
            # Pharmacies
            elif amenity == "pharmacy" or tags.get("shop") == "pharmacy":
                pharmacies.append(facility)
        
        return {
            "hospitals": hospitals,
            "urgent_care": urgent_care,
            "clinics": clinics,
            "pharmacies": pharmacies,
            "doctors": doctors
        }
            
    except Exception as e:
        print(f"Error querying healthcare facilities: {e}")
        return None



def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points in kilometers."""
    R = 6371  # Earth radius in km
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    
    a = math.sin(delta_phi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    
    return R * c


@cached(ttl_seconds=CACHE_TTL['osm_queries'])
@safe_api_call("osm", required=False)
@handle_api_timeout(timeout_seconds=30)
def query_railway_stations(lat: float, lon: float, radius_m: int = 2000) -> Optional[List[Dict]]:
    """
    Query OSM for railway stations within radius.
    
    Args:
        lat, lon: Coordinates
        radius_m: Search radius in meters (default 2km)
    
    Returns:
        List of railway stations with name, lat, lon, distance
    """
    query = f"""
    [out:json][timeout:25];
    (
      // Railway stations
      node["railway"="station"](around:{radius_m},{lat},{lon});
      node["railway"="halt"](around:{radius_m},{lat},{lon});
      
      // Metro/subway stations
      node["railway"="subway_entrance"](around:{radius_m},{lat},{lon});
      node["station"="subway"](around:{radius_m},{lat},{lon});
      
      // Tram stations
      node["railway"="tram_stop"](around:{radius_m},{lat},{lon});
      
      // Bus stations
      node["public_transport"="station"](around:{radius_m},{lat},{lon});
      node["amenity"="bus_station"](around:{radius_m},{lat},{lon});
    );
    out body;
    >;
    out skel qt;
    """
    
    try:
        print(f"🚂 Querying OSM for railway stations within {radius_m/1000:.1f}km...")
        resp = requests.post(OVERPASS_URL, data=query, timeout=30)
        
        if resp.status_code == 200:
            data = resp.json()
            elements = data.get("elements", [])
            
            stations = []
            for elem in elements:
                if "lat" in elem and "lon" in elem:
                    tags = elem.get("tags", {})
                    name = tags.get("name") or tags.get("operator") or "Unnamed Station"
                    railway_type = tags.get("railway") or tags.get("public_transport") or "station"
                    
                    # Calculate distance
                    distance_km = haversine_distance(lat, lon, elem["lat"], elem["lon"])
                    distance_m = distance_km * 1000
                    
                    stations.append({
                        "name": name,
                        "lat": elem["lat"],
                        "lon": elem["lon"],
                        "distance_m": round(distance_m),
                        "distance_km": round(distance_km, 2),
                        "railway_type": railway_type,
                        "tags": tags
                    })
            
            # Sort by distance
            stations.sort(key=lambda x: x["distance_m"])
            
            print(f"   Found {len(stations)} railway stations")
            return stations
        else:
            print(f"⚠️  OSM railway station query failed: {resp.status_code}")
            return None
            
    except Exception as e:
        print(f"Error querying OSM for railway stations: {e}")
        return None