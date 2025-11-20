"""
Geocoding API Client
Uses Census API (for US addresses) with Nominatim fallback
"""

import re
import requests
from typing import Optional, Tuple, Dict
from .cache import cached, CACHE_TTL

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
CENSUS_GEOCODER_URL = "https://geocoding.geo.census.gov/geocoder/locations/address"

# Keywords that suggest user is looking for a neighborhood, not a city
NEIGHBORHOOD_KEYWORDS = [
    "old", "historic", "district", "neighborhood", "neighbourhood",
    "village", "heights", "park", "slope", "village", "square",
    "commons", "commons", "quarter", "quarters", "downtown",
    "uptown", "midtown", "east", "west", "north", "south"
]

# State name to abbreviation mapping (for extracting state from query)
STATE_ABBREVIATIONS = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
    "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
    "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
    "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS",
    "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
    "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK",
    "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
    "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT",
    "vermont": "VT", "virginia": "VA", "washington": "WA", "west virginia": "WV",
    "wisconsin": "WI", "wyoming": "WY", "district of columbia": "DC",
    "puerto rico": "PR"
}

# Reverse mapping: abbreviation to full name (for Nominatim queries)
STATE_ABBREV_TO_NAME = {v: k for k, v in STATE_ABBREVIATIONS.items()}

# Valid 2-letter state codes
VALID_STATE_CODES = set(STATE_ABBREVIATIONS.values())


def _extract_state_from_query(address: str) -> Optional[str]:
    """
    Extract state code or name from query string.
    
    Args:
        address: Address string (e.g., "Charleston SC", "Downtown Charleston, South Carolina")
    
    Returns:
        State abbreviation (e.g., "SC") if found, None otherwise
    """
    address_lower = address.lower().strip()
    
    # First, try to find 2-letter state code at end of query (most common pattern)
    # Pattern: word boundary, 2 uppercase letters, end of string or followed by comma/punctuation
    state_code_match = re.search(r'\b([A-Z]{2})\b(?:\s*$|[,;])', address)
    if state_code_match:
        code = state_code_match.group(1).upper()
        if code in VALID_STATE_CODES:
            return code
    
    # Try to find full state name (check for multi-word states first, then single word)
    # Check for multi-word states (e.g., "new york", "south carolina")
    for state_name, code in STATE_ABBREVIATIONS.items():
        if ' ' in state_name:  # Multi-word states
            if state_name in address_lower:
                return code
    
    # Check for single-word states
    words = address_lower.split()
    for word in words:
        if word in STATE_ABBREVIATIONS:
            return STATE_ABBREVIATIONS[word]
    
    return None


def _validate_state_match(query_state: Optional[str], result_state: str) -> bool:
    """
    Validate that geocoding result matches the state from the query.
    
    Args:
        query_state: State code extracted from query (e.g., "SC")
        result_state: State name from Nominatim result
    
    Returns:
        True if states match, False otherwise
    """
    if not query_state or not result_state:
        return True  # Can't validate if either is missing
    
    result_state_lower = result_state.lower().strip()
    
    # Check if result state matches query state code
    if result_state_lower == query_state.lower():
        return True
    
    # Check if result state name matches query state code
    if query_state in STATE_ABBREV_TO_NAME:
        expected_state_name = STATE_ABBREV_TO_NAME[query_state]
        if expected_state_name in result_state_lower or result_state_lower in expected_state_name:
            return True
    
    # Check if result state abbreviation matches query state code
    if result_state_lower in STATE_ABBREVIATIONS:
        result_code = STATE_ABBREVIATIONS[result_state_lower]
        if result_code == query_state:
            return True
    
    return False


def _has_street_number(address: str) -> bool:
    """
    Check if address contains a street number (starts with digits).
    
    Args:
        address: Address string
    
    Returns:
        True if address appears to have a street number
    """
    # Remove common prefixes and check if starts with digits
    address_clean = address.strip()
    # Pattern: starts with 1-5 digits followed by space or comma
    return bool(re.match(r'^\d{1,5}[\s,]', address_clean))


def _find_city_relation_for_element(element_type: str, element_id: int, lat: float, lon: float) -> Optional[Tuple[float, float, str]]:
    """
    Find city relation containing a node/way and get its admin_centre.
    
    Args:
        element_type: "node" or "way"
        element_id: OSM ID
        lat, lon: Coordinates (for fallback)
    
    Returns:
        (lat, lon, source) or None
    """
    try:
        from data_sources.osm_api import get_overpass_url
        
        # Query for relations containing this element with place=city/town/municipality
        # Use rel(bn) for nodes, rel(bw) for ways
        rel_filter = "rel(bn)" if element_type == "node" else "rel(bw)"
        query = f"""
        [out:json][timeout:10];
        {element_type}({element_id});
        {rel_filter}[place~"^(city|town|municipality)$"];
        out body;
        >;
        out skel qt;
        """
        
        response = requests.post(
            get_overpass_url(),
            data={"data": query},
            headers={"User-Agent": "HomeFit/1.0"},
            timeout=15
        )
        
        if response.status_code != 200:
            return None
            
        data = response.json()
        if not data or "elements" not in data:
            return None
        
        # Find relation with place=city/town/municipality
        for elem in data["elements"]:
            if elem.get("type") == "relation":
                tags = elem.get("tags", {})
                if tags.get("place") in ("city", "town", "municipality"):
                    # Extract city name and state from relation tags
                    city_name = tags.get("name")
                    state = tags.get("addr:state") or tags.get("is_in:state")
                    # Get best coordinates for this relation (place=city node preferred)
                    return _get_relation_center_or_admin_centre(elem["id"], city_name, state)
        
        return None
    except Exception as e:
        print(f"Error finding city relation for {element_type} {element_id}: {e}")
        return None


def _find_place_node(name: str, place_type: str, state: Optional[str] = None) -> Optional[Tuple[float, float, str]]:
    """
    Find a place node (city, neighbourhood, suburb) by name.
    This is usually more accurate than geometric center for downtown/center locations.
    
    Args:
        name: Place name (e.g., "Bend", "Old San Juan")
        place_type: OSM place type ("city", "town", "neighbourhood", "suburb")
        state: Optional state code/name for filtering (e.g., "OR", "Oregon")
        
    Returns:
        (lat, lon, source) where source is "place_city", "place_neighbourhood", etc., or None
    """
    try:
        from data_sources.osm_api import get_overpass_url
        
        # Build query for place node
        # Try both exact name match and case-insensitive
        query = f"""
        [out:json][timeout:10];
        (
          node["place"="{place_type}"]["name"="{name}"];
          node["place"="{place_type}"]["name"~"^{name}$",i];
        );
        out;
        """
        
        response = requests.post(
            get_overpass_url(),
            data={"data": query},
            headers={"User-Agent": "HomeFit/1.0"},
            timeout=15
        )
        
        if response.status_code == 200:
            data = response.json()
            if data and "elements" in data:
                candidates = []
                for elem in data["elements"]:
                    if elem.get("type") == "node" and "lat" in elem and "lon" in elem:
                        elem_tags = elem.get("tags", {})
                        # If state provided, prefer matches in that state
                        if state:
                            elem_state = elem_tags.get("addr:state") or elem_tags.get("is_in:state")
                            if elem_state and state.lower() in str(elem_state).lower():
                                candidates.insert(0, elem)  # Prioritize state match
                            else:
                                candidates.append(elem)
                        else:
                            candidates.append(elem)
                
                if candidates:
                    best = candidates[0]
                    source_name = f"place_{place_type}"
                    print(f"✅ Found {place_type} node for '{name}': {best['lat']}, {best['lon']}")
                    return float(best["lat"]), float(best["lon"]), source_name
        
        return None
    except Exception as e:
        print(f"Error finding {place_type} node for {name}: {e}")
        return None


def _get_relation_center_or_admin_centre(osm_id: int, city_name: Optional[str] = None, state: Optional[str] = None) -> Optional[Tuple[float, float, str]]:
    """
    Query OSM Overpass to get the best city center point from a relation.
    
    Priority:
    1. place=city node (downtown marker - most accurate for cities)
    2. admin_centre or label node (official city center)
    3. relation geometric center (fallback)
    
    Args:
        osm_id: OSM relation ID
        city_name: Optional city name for place=city node lookup
        state: Optional state code/name for filtering
        
    Returns:
        (lat, lon, source) where source is "place_city", "admin_centre", "label", or "center", or None if failed
    """
    try:
        from data_sources.osm_api import get_overpass_url
        
        # Track if we already tried place=city node lookup
        tried_place_node = False
        
        # Priority 1: Try place=city node first (most accurate for downtown)
        if city_name:
            print(f"🔍 Trying place=city node for '{city_name}'...")
            tried_place_node = True
            place_city_coords = _find_place_node(city_name, "city", state)
            if place_city_coords:
                return place_city_coords
            # Also try place=town as fallback
            place_town_coords = _find_place_node(city_name, "town", state)
            if place_town_coords:
                return place_town_coords
        
        # Priority 2: Query Overpass for relation with full members
        # Use 'out body' to get relation with members, then recurse to get member nodes
        query = f"""
        [out:json][timeout:10];
        relation({osm_id});
        out body;
        >;
        out skel qt;
        """
        
        response = requests.post(
            get_overpass_url(),
            data={"data": query},
            headers={"User-Agent": "HomeFit/1.0"},
            timeout=15
        )
        
        if response.status_code != 200:
            return None
            
        data = response.json()
        if not data or "elements" not in data:
            return None
        
        elements = data["elements"]
        
        # First, look for relation element to get members
        relation = None
        for elem in elements:
            if elem.get("type") == "relation" and elem.get("id") == osm_id:
                relation = elem
                break
        
        if not relation:
            return None
        
        # Extract city name and state from relation tags if not provided
        relation_tags = relation.get("tags", {})
        if not city_name:
            city_name = relation_tags.get("name")
        if not state:
            state = relation_tags.get("addr:state") or relation_tags.get("is_in:state")
        
        # If we now have city_name from relation tags (and didn't try place=city node lookup yet), try it
        if city_name and not tried_place_node:
            print(f"🔍 Trying place=city node for '{city_name}' (from relation tags)...")
            place_city_coords = _find_place_node(city_name, "city", state)
            if place_city_coords:
                return place_city_coords
            # Also try place=town as fallback
            place_town_coords = _find_place_node(city_name, "town", state)
            if place_town_coords:
                return place_town_coords
        
        # Check for admin_centre or label members
        members = relation.get("members", [])
        admin_centre_id = None
        label_id = None
        
        for member in members:
            role = member.get("role", "")
            ref = member.get("ref")
            mtype = member.get("type")
            
            if role == "admin_centre" and mtype == "node" and ref:
                admin_centre_id = ref
            elif role == "label" and mtype == "node" and ref:
                label_id = ref
        
        # Look for admin_centre node in elements
        if admin_centre_id:
            admin_centre_found = False
            for elem in elements:
                if elem.get("type") == "node" and elem.get("id") == admin_centre_id:
                    if "lat" in elem and "lon" in elem:
                        print(f"✅ Found admin_centre node {admin_centre_id} in relation {osm_id}")
                        return float(elem["lat"]), float(elem["lon"]), "admin_centre"
                    admin_centre_found = True
            
            # If node ID found but coordinates missing, query it explicitly
            if not admin_centre_found:
                print(f"🔍 Admin_centre node {admin_centre_id} not in elements, querying explicitly...")
                node_query = f"""
                [out:json][timeout:10];
                node({admin_centre_id});
                out;
                """
                node_response = requests.post(
                    get_overpass_url(),
                    data={"data": node_query},
                    headers={"User-Agent": "HomeFit/1.0"},
                    timeout=15
                )
                if node_response.status_code == 200:
                    node_data = node_response.json()
                    if node_data and "elements" in node_data:
                        for elem in node_data["elements"]:
                            if elem.get("type") == "node" and elem.get("id") == admin_centre_id:
                                if "lat" in elem and "lon" in elem:
                                    print(f"✅ Found admin_centre node {admin_centre_id} via explicit query")
                                    return float(elem["lat"]), float(elem["lon"]), "admin_centre"
        
        # Look for label node in elements
        if label_id:
            label_found = False
            for elem in elements:
                if elem.get("type") == "node" and elem.get("id") == label_id:
                    if "lat" in elem and "lon" in elem:
                        print(f"✅ Found label node {label_id} in relation {osm_id}")
                        return float(elem["lat"]), float(elem["lon"]), "label"
                    label_found = True
            
            # If node ID found but coordinates missing, query it explicitly
            if not label_found:
                print(f"🔍 Label node {label_id} not in elements, querying explicitly...")
                node_query = f"""
                [out:json][timeout:10];
                node({label_id});
                out;
                """
                node_response = requests.post(
                    get_overpass_url(),
                    data={"data": node_query},
                    headers={"User-Agent": "HomeFit/1.0"},
                    timeout=15
                )
                if node_response.status_code == 200:
                    node_data = node_response.json()
                    if node_data and "elements" in node_data:
                        for elem in node_data["elements"]:
                            if elem.get("type") == "node" and elem.get("id") == label_id:
                                if "lat" in elem and "lon" in elem:
                                    print(f"✅ Found label node {label_id} via explicit query")
                                    return float(elem["lat"]), float(elem["lon"]), "label"
        
        # Priority 3: Fallback to relation center - query separately for center
        print(f"⚠️  No place=city/admin_centre/label found for relation {osm_id}, using geometric center")
        center_query = f"""
        [out:json][timeout:10];
        relation({osm_id});
        out center;
        """
        
        center_response = requests.post(
            get_overpass_url(),
            data={"data": center_query},
            headers={"User-Agent": "HomeFit/1.0"},
            timeout=15
        )
        
        if center_response.status_code == 200:
            center_data = center_response.json()
            if center_data and "elements" in center_data:
                for elem in center_data["elements"]:
                    if elem.get("type") == "relation" and elem.get("id") == osm_id:
                        if "center" in elem:
                            center = elem["center"]
                            if "lat" in center and "lon" in center:
                                return float(center["lat"]), float(center["lon"]), "center"
                        elif "lat" in elem and "lon" in elem:
                            # Some relations have lat/lon directly
                            return float(elem["lat"]), float(elem["lon"]), "center"
            
        return None
    except Exception as e:
        print(f"Error getting relation center for OSM ID {osm_id}: {e}")
        return None


def _geocode_census(address: str) -> Optional[Tuple[float, float, str, str, str]]:
    """
    Geocode using Census API (US addresses only).
    More accurate for US addresses than Nominatim.
    
    Args:
        address: Address string
        
    Returns:
        (lat, lon, zip_code, state, city) or None if failed
    """
    try:
        # Census API requires structured address components
        # For now, try to parse the address or use it as-is
        # Census API format: street, city, state, zip (all optional)
        
        # Extract state code if available
        query_state = _extract_state_from_query(address)
        
        # Parse address - try to extract components
        # Simple approach: if it looks like "City, State" or "City State", use that
        address_parts = address.split(',')
        if len(address_parts) >= 2:
            # Likely "City, State" format
            city_part = address_parts[0].strip()
            state_part = address_parts[1].strip()
            if state_part.upper() in VALID_STATE_CODES:
                query_state = state_part.upper()
                address = city_part
        
        params = {
            "street": "",  # Census API prefers structured, but we can try with full address
            "city": address if not query_state else address.split(',')[0].strip(),
            "state": query_state if query_state else "",
            "zip": "",
            "benchmark": "Public_AR_Current",
            "vintage": "Current_Current",
            "format": "json"
        }
        
        # If we have a state, use structured format
        if query_state:
            # Try structured format first
            if ',' in address:
                parts = [p.strip() for p in address.split(',')]
                params["city"] = parts[0]
                if len(parts) > 1:
                    params["state"] = parts[1] if parts[1].upper() in VALID_STATE_CODES else query_state
            else:
                params["city"] = address
                params["state"] = query_state
        else:
            # No state - try with full address as city
            params["city"] = address
        
        response = requests.get(
            CENSUS_GEOCODER_URL, params=params, headers={"User-Agent": "HomeFit/1.0"}, timeout=10)
        
        if response.status_code != 200:
            return None
        
        data = response.json()
        if not data or "result" not in data:
            return None
        
        result = data["result"]
        if "addressMatches" not in result or not result["addressMatches"]:
            return None
        
        match = result["addressMatches"][0]
        coordinates = match.get("coordinates", {})
        
        if "y" not in coordinates or "x" not in coordinates:
            return None
        
        lat = float(coordinates["y"])
        lon = float(coordinates["x"])
        
        # Extract address components
        address_components = match.get("addressComponents", {})
        zip_code = address_components.get("zip", "")
        state = address_components.get("state", query_state or "")
        city = address_components.get("city", "")
        
        return lat, lon, zip_code, state, city
        
    except Exception as e:
        # Census API failed - will fall back to Nominatim
        return None


@cached(ttl_seconds=CACHE_TTL['geocoding'])
def geocode(address: str) -> Optional[Tuple[float, float, str, str, str]]:
    """
    Geocode an address to coordinates.
    Uses Census API first (for US addresses with street numbers), falls back to Nominatim.

    Args:
        address: Address string or ZIP code

    Returns:
        (lat, lon, zip_code, state, city) or None if failed
    """
    # Try Census API first (for US addresses WITH street numbers)
    query_state = _extract_state_from_query(address)
    if query_state and _has_street_number(address):  # Only use Census if street number present
        census_result = _geocode_census(address)
        if census_result:
            return census_result
    
    # Fall back to Nominatim
    try:
        # Extract state code from query to prioritize results from that state
        query_state = _extract_state_from_query(address)
        
        # Build query string with state prioritization
        query_string = address
        if query_state and query_state in STATE_ABBREV_TO_NAME:
            # Add state name to query to help Nominatim prioritize
            state_name = STATE_ABBREV_TO_NAME[query_state]
            # Only add if not already in query (avoid duplication)
            if state_name not in address.lower():
                query_string = f"{address}, {state_name.title()}"
        
        params = {
            "q": query_string,
            "format": "json",
            "addressdetails": 1,
            "limit": 1
        }

        headers = {
            "User-Agent": "HomeFit/1.0"
        }

        response = requests.get(
            NOMINATIM_URL, params=params, headers=headers, timeout=10)

        if response.status_code != 200:
            return None

        data = response.json()

        if not data:
            return None

        result = data[0]
        
        # Log what Nominatim returned for debugging
        print(f"🔍 Nominatim result for '{address}': type={result.get('osm_type')}, id={result.get('osm_id')}, coords={result.get('lat')},{result.get('lon')}")
        
        # Check if this is a relation (city boundary) - if so, get better coordinates from OSM
        osm_type = result.get("osm_type")
        osm_id = result.get("osm_id")
        
        # Default to Nominatim coordinates
        lat = float(result["lat"])
        lon = float(result["lon"])
        coordinate_source = "nominatim"
        
        if osm_type == "relation" and osm_id:
            # This is likely a city boundary - get accurate center from OSM
            print(f"🔍 Found relation {osm_id} for '{address}', querying for best coordinates...")
            # Extract city name and state from result
            address_details = result.get("address", {})
            city_name = address_details.get("city") or address_details.get("town") or address_details.get("village")
            result_state = address_details.get("state", "")
            query_state = _extract_state_from_query(address) or result_state
            
            relation_coords = _get_relation_center_or_admin_centre(osm_id, city_name, query_state)
            if relation_coords:
                rel_lat, rel_lon, source = relation_coords
                # Use relation coordinates (place=city preferred, then admin_centre/label, then center)
                lat = rel_lat
                lon = rel_lon
                coordinate_source = source
                print(f"✅ Using OSM {source} for '{address}': {lat}, {lon}")
            else:
                # Fall back to Nominatim coordinates if relation query fails
                print(f"⚠️  OSM relation query failed for '{address}', using Nominatim coordinates: {lat}, {lon}")
        elif osm_type in ("node", "way") and osm_id:
            # Check if this is a neighborhood
            if _is_neighborhood_result(result):
                address_details = result.get("address", {})
                neighborhood_name = (address_details.get("neighbourhood") or 
                                    address_details.get("suburb") or
                                    address_details.get("city") or
                                    address_details.get("town"))
                result_state = address_details.get("state", "")
                query_state = _extract_state_from_query(address) or result_state
                
                if neighborhood_name:
                    print(f"🔍 Found neighborhood {osm_type} {osm_id} for '{address}', trying place node...")
                    # Try place=neighbourhood first, then place=suburb
                    neighborhood_coords = _find_place_node(neighborhood_name, "neighbourhood", query_state)
                    if not neighborhood_coords:
                        neighborhood_coords = _find_place_node(neighborhood_name, "suburb", query_state)
                    
                    if neighborhood_coords:
                        rel_lat, rel_lon, source = neighborhood_coords
                        lat = rel_lat
                        lon = rel_lon
                        coordinate_source = source
                        print(f"✅ Using OSM {source} for neighborhood '{address}': {lat}, {lon}")
                    else:
                        # For neighborhoods, Nominatim coordinates are usually accurate
                        print(f"✅ Using Nominatim coordinates for neighborhood '{address}': {lat}, {lon}")
                else:
                    print(f"✅ Using Nominatim coordinates for neighborhood '{address}': {lat}, {lon}")
            else:
                # For city queries that returned a node/way, try to find the city relation containing it
                print(f"🔍 Found {osm_type} {osm_id} for '{address}', searching for city relation...")
                relation_coords = _find_city_relation_for_element(osm_type, osm_id, lat, lon)
                if relation_coords:
                    rel_lat, rel_lon, source = relation_coords
                    lat = rel_lat
                    lon = rel_lon
                    coordinate_source = source
                    print(f"✅ Using OSM relation {source} (found via {osm_type}) for '{address}': {lat}, {lon}")
                else:
                    # For specific nodes/ways (addresses), use Nominatim coordinates directly
                    print(f"✅ Using Nominatim coordinates for {osm_type} '{address}': {lat}, {lon}")
        
        # Validate state match if we extracted a state from query
        address_details = result.get("address", {})
        result_state = address_details.get("state", "")
        if query_state and not _validate_state_match(query_state, result_state):
            # State mismatch - this shouldn't happen with state prioritization,
            # but log it for debugging
            print(f"⚠️  State mismatch: query had '{query_state}' but got '{result_state}' for '{address}'")

        zip_code = address_details.get("postcode", "")
        state = result_state
        city = address_details.get("city") or address_details.get(
            "town") or address_details.get("village", "")

        return lat, lon, zip_code, state, city

    except Exception as e:
        print(f"Geocoding error: {e}")
        return None


def _looks_like_neighborhood_query(address: str) -> bool:
    """
    Check if the query suggests user is looking for a neighborhood.
    
    Args:
        address: Address string
    
    Returns:
        True if query contains neighborhood keywords
    """
    address_lower = address.lower()
    return any(keyword in address_lower for keyword in NEIGHBORHOOD_KEYWORDS)


def _is_neighborhood_result(result: Dict) -> bool:
    """
    Check if Nominatim result is a neighborhood/suburb.
    
    Args:
        result: Nominatim result dict
    
    Returns:
        True if result is a neighborhood/suburb
    """
    result_type = result.get("type", "").lower()
    address_details = result.get("address", {})
    
    # Check result type
    if result_type in ("neighbourhood", "suburb", "quarter", "city_block"):
        return True
    
    # Check address structure
    if "neighbourhood" in address_details or "suburb" in address_details:
        return True
    
    return False


def _is_city_result(result: Dict) -> bool:
    """
    Check if Nominatim result is a city/administrative area.
    
    Args:
        result: Nominatim result dict
    
    Returns:
        True if result is a city/administrative area
    """
    result_type = result.get("type", "").lower()
    return result_type in ("city", "administrative", "town", "municipality")


def _find_best_neighborhood_match(results: list) -> Optional[Dict]:
    """
    Find the best neighborhood match from multiple results.
    Prefers results with neighbourhood/suburb in address structure.
    
    Args:
        results: List of Nominatim result dicts
    
    Returns:
        Best neighborhood result or None
    """
    # First, try to find a result with explicit neighbourhood/suburb
    for result in results:
        if _is_neighborhood_result(result):
            return result
    
    # If no explicit neighborhood, return None (will use first result)
    return None


@cached(ttl_seconds=CACHE_TTL['geocoding'])
def geocode_with_full_result(address: str) -> Optional[Tuple[float, float, str, str, str, Dict]]:
    """
    Geocode with full response for neighborhood detection.
    
    Uses hybrid approach:
    1. Try Census API first (for US addresses with state)
    2. Fall back to Nominatim with state prioritization
    3. If query suggests neighborhood but result is city, retry with limit=5
    4. Validate state match to prevent state mismatches
    
    Cached to avoid rate limits.

    Args:
        address: Address string or ZIP code

    Returns:
        (lat, lon, zip_code, state, city, full_result) or None if failed
        full_result: Complete geocoding response including address structure
    """
    # Try Census API first (for US addresses WITH street numbers)
    query_state = _extract_state_from_query(address)
    if query_state and _has_street_number(address):  # Only use Census if street number present
        census_result = _geocode_census(address)
        if census_result:
            lat, lon, zip_code, state, city = census_result
            # Create a Nominatim-like result structure for compatibility
            full_result = {
                "lat": str(lat),
                "lon": str(lon),
                "address": {
                    "postcode": zip_code,
                    "state": state,
                    "city": city or "",
                    "town": city or "",
                    "village": ""
                },
                "type": "city"  # Census doesn't provide type, default to city
            }
            return lat, lon, zip_code, state, city, full_result
    
    # Fall back to Nominatim
    try:
        # Extract state code from query to prioritize results from that state
        query_state = _extract_state_from_query(address)
        
        # Build query string with state prioritization
        query_string = address
        if query_state and query_state in STATE_ABBREV_TO_NAME:
            # Add state name to query to help Nominatim prioritize
            state_name = STATE_ABBREV_TO_NAME[query_state]
            # Only add if not already in query (avoid duplication)
            if state_name not in address.lower():
                query_string = f"{address}, {state_name.title()}"
        
        # First attempt: normal query with limit=1
        params = {
            "q": query_string,
            "format": "json",
            "addressdetails": 1,
            "limit": 1
        }

        headers = {
            "User-Agent": "HomeFit/1.0"
        }

        response = requests.get(
            NOMINATIM_URL, params=params, headers=headers, timeout=10)

        if response.status_code != 200:
            return None

        data = response.json()

        if not data:
            return None

        result = data[0]
        
        # Validate state match if we extracted a state from query
        address_details = result.get("address", {})
        result_state = address_details.get("state", "")
        state_mismatch = False
        if query_state and not _validate_state_match(query_state, result_state):
            # State mismatch detected - log for debugging
            print(f"⚠️  State mismatch: query had '{query_state}' but got '{result_state}' for '{address}'")
            state_mismatch = True
        
        # Check if there's a mismatch: query suggests neighborhood but result is city
        is_neighborhood_query = _looks_like_neighborhood_query(address)
        is_city_result_type = _is_city_result(result)
        is_neighborhood_result_type = _is_neighborhood_result(result)
        
        # If query suggests neighborhood but we got a city, retry with higher limit
        # OR if state mismatch detected, retry to find correct state
        if (is_neighborhood_query and is_city_result_type and not is_neighborhood_result_type) or state_mismatch:
            # Retry with limit=5 to find better matches
            params["limit"] = 5
            retry_response = requests.get(
                NOMINATIM_URL, params=params, headers=headers, timeout=10)
            
            if retry_response.status_code == 200:
                retry_data = retry_response.json()
                if retry_data:
                    # If state mismatch, prioritize results matching the query state
                    if state_mismatch:
                        for candidate in retry_data:
                            candidate_state = candidate.get("address", {}).get("state", "")
                            if _validate_state_match(query_state, candidate_state):
                                result = candidate
                                break
                    else:
                        # Try to find a neighborhood match
                        best_match = _find_best_neighborhood_match(retry_data)
                        if best_match:
                            result = best_match
                    # If no better match found, keep original result

        # Check if this is a relation (city boundary) - if so, get better coordinates from OSM
        osm_type = result.get("osm_type")
        osm_id = result.get("osm_id")
        
        # Default to Nominatim coordinates
        lat = float(result["lat"])
        lon = float(result["lon"])
        coordinate_source = "nominatim"
        
        if osm_type == "relation" and osm_id:
            # This is likely a city boundary - get accurate center from OSM
            # Extract city name and state from result for better place node lookup
            address_details = result.get("address", {})
            city_name = address_details.get("city") or address_details.get("town") or address_details.get("village")
            result_state = address_details.get("state", "")
            query_state = _extract_state_from_query(address) or result_state
            
            relation_coords = _get_relation_center_or_admin_centre(osm_id, city_name, query_state)
            if relation_coords:
                rel_lat, rel_lon, source = relation_coords
                # Use relation coordinates (place=city preferred, then admin_centre/label, then center)
                lat = rel_lat
                lon = rel_lon
                coordinate_source = source
                print(f"📍 Using OSM {source} for '{address}': {lat}, {lon}")
                # Update result dict with new coordinates for consistency
                result["lat"] = str(lat)
                result["lon"] = str(lon)
            else:
                # Fall back to Nominatim coordinates if relation query fails
                print(f"⚠️  OSM relation query failed for '{address}', using Nominatim coordinates")
        elif osm_type in ("node", "way") and osm_id:
            # Check if this is a neighborhood - if so, try to find place=neighbourhood/suburb node
            if _is_neighborhood_result(result):
                address_details = result.get("address", {})
                neighborhood_name = (address_details.get("neighbourhood") or 
                                    address_details.get("suburb") or
                                    address_details.get("city") or
                                    address_details.get("town"))
                result_state = address_details.get("state", "")
                query_state = _extract_state_from_query(address) or result_state
                
                if neighborhood_name:
                    # Try place=neighbourhood first, then place=suburb
                    neighborhood_coords = _find_place_node(neighborhood_name, "neighbourhood", query_state)
                    if not neighborhood_coords:
                        neighborhood_coords = _find_place_node(neighborhood_name, "suburb", query_state)
                    
                    if neighborhood_coords:
                        rel_lat, rel_lon, source = neighborhood_coords
                        lat = rel_lat
                        lon = rel_lon
                        coordinate_source = source
                        print(f"📍 Using OSM {source} for neighborhood '{address}': {lat}, {lon}")
                        result["lat"] = str(lat)
                        result["lon"] = str(lon)
                    else:
                        # For neighborhoods, Nominatim coordinates are usually accurate
                        print(f"📍 Using Nominatim coordinates for neighborhood '{address}': {lat}, {lon}")
            else:
                # For city queries that returned a node/way, try to find the city relation containing it
                relation_coords = _find_city_relation_for_element(osm_type, osm_id, lat, lon)
                if relation_coords:
                    rel_lat, rel_lon, source = relation_coords
                    lat = rel_lat
                    lon = rel_lon
                    coordinate_source = source
                    print(f"📍 Using OSM relation {source} (found via {osm_type}) for '{address}': {lat}, {lon}")
                    # Update result dict with new coordinates for consistency
                    result["lat"] = str(lat)
                    result["lon"] = str(lon)
                else:
                    # For specific nodes/ways (addresses), use Nominatim coordinates directly
                    print(f"📍 Using Nominatim coordinates for {osm_type} '{address}': {lat}, {lon}")

        # Extract address details
        address_details = result.get("address", {})
        zip_code = address_details.get("postcode", "")
        state = address_details.get("state", "")
        city = address_details.get("city") or address_details.get(
            "town") or address_details.get("village", "")

        return lat, lon, zip_code, state, city, result

    except Exception as e:
        print(f"Geocoding error: {e}")
        return None


@cached(ttl_seconds=CACHE_TTL['geocoding'])
def reverse_geocode(lat: float, lon: float) -> Optional[str]:
    """
    Reverse geocode coordinates to get city name.
    
    Args:
        lat, lon: Coordinates
    
    Returns:
        City name or None if failed
    """
    try:
        NOMINATIM_REVERSE_URL = "https://nominatim.openstreetmap.org/reverse"
        params = {
            "lat": lat,
            "lon": lon,
            "format": "json",
            "addressdetails": 1
        }
        
        headers = {
            "User-Agent": "HomeFit/1.0"
        }
        
        response = requests.get(
            NOMINATIM_REVERSE_URL, params=params, headers=headers, timeout=10)
        
        if response.status_code != 200:
            return None
        
        data = response.json()
        if not data or "address" not in data:
            return None
        
        address_details = data.get("address", {})
        city = (address_details.get("city") or 
                address_details.get("town") or 
                address_details.get("village") or 
                address_details.get("municipality", ""))
        
        return city if city else None
        
    except Exception as e:
        print(f"Reverse geocoding error: {e}")
        return None
