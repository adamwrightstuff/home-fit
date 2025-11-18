"""
Geocoding API Client
Uses Nominatim (OpenStreetMap) for address geocoding
"""

import re
import requests
from typing import Optional, Tuple, Dict
from .cache import cached, CACHE_TTL

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

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


@cached(ttl_seconds=CACHE_TTL['geocoding'])
def geocode(address: str) -> Optional[Tuple[float, float, str, str, str]]:
    """
    Geocode an address to coordinates.

    Args:
        address: Address string or ZIP code

    Returns:
        (lat, lon, zip_code, state, city) or None if failed
    """
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
        
        # Validate state match if we extracted a state from query
        address_details = result.get("address", {})
        result_state = address_details.get("state", "")
        if query_state and not _validate_state_match(query_state, result_state):
            # State mismatch - this shouldn't happen with state prioritization,
            # but log it for debugging
            print(f"⚠️  State mismatch: query had '{query_state}' but got '{result_state}' for '{address}'")
        
        lat = float(result["lat"])
        lon = float(result["lon"])

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
    Geocode with full Nominatim response for neighborhood detection.
    
    Uses hybrid approach:
    1. Extract state code from query to prioritize results from that state
    2. Normal query with limit=1 (fast, works for most cases)
    3. If query suggests neighborhood but result is city, retry with limit=5
    4. Validate state match to prevent state mismatches
    5. Only retries when there's a clear mismatch
    
    Cached to avoid rate limits.

    Args:
        address: Address string or ZIP code

    Returns:
        (lat, lon, zip_code, state, city, full_result) or None if failed
        full_result: Complete Nominatim response including address structure
    """
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

        # Extract coordinates and address details
        lat = float(result["lat"])
        lon = float(result["lon"])

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
