"""
Geocoding API Client
Uses Nominatim (OpenStreetMap) for address geocoding
"""

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
        params = {
            "q": address,
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
        lat = float(result["lat"])
        lon = float(result["lon"])

        address_details = result.get("address", {})
        zip_code = address_details.get("postcode", "")
        state = address_details.get("state", "")
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
    1. Normal query with limit=1 (fast, works for most cases)
    2. If query suggests neighborhood but result is city, retry with limit=5
    3. Only retries when there's a clear mismatch
    
    Cached to avoid rate limits.

    Args:
        address: Address string or ZIP code

    Returns:
        (lat, lon, zip_code, state, city, full_result) or None if failed
        full_result: Complete Nominatim response including address structure
    """
    try:
        # First attempt: normal query with limit=1
        params = {
            "q": address,
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
        
        # Check if there's a mismatch: query suggests neighborhood but result is city
        is_neighborhood_query = _looks_like_neighborhood_query(address)
        is_city_result_type = _is_city_result(result)
        is_neighborhood_result_type = _is_neighborhood_result(result)
        
        # If query suggests neighborhood but we got a city, retry with higher limit
        if is_neighborhood_query and is_city_result_type and not is_neighborhood_result_type:
            # Retry with limit=5 to find neighborhood results
            params["limit"] = 5
            retry_response = requests.get(
                NOMINATIM_URL, params=params, headers=headers, timeout=10)
            
            if retry_response.status_code == 200:
                retry_data = retry_response.json()
                if retry_data:
                    # Try to find a neighborhood match
                    best_match = _find_best_neighborhood_match(retry_data)
                    if best_match:
                        result = best_match
                    # If no neighborhood found, keep original result (first from retry)

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
