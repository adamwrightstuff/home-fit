"""
Geocoding API Client
Uses Nominatim (OpenStreetMap) for address geocoding
"""

import requests
from typing import Optional, Tuple, Dict
from .cache import cached, CACHE_TTL

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"


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


@cached(ttl_seconds=CACHE_TTL['geocoding'])
def geocode_with_full_result(address: str) -> Optional[Tuple[float, float, str, str, str, Dict]]:
    """
    Geocode with full Nominatim response for neighborhood detection.
    
    Cached to avoid rate limits.

    Args:
        address: Address string or ZIP code

    Returns:
        (lat, lon, zip_code, state, city, full_result) or None if failed
        full_result: Complete Nominatim response including address structure
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

        return lat, lon, zip_code, state, city, result

    except Exception as e:
        print(f"Geocoding error: {e}")
        return None
