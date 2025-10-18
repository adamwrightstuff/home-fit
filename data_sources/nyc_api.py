"""
NYC Open Data API Client
Queries NYC Street Tree Census
"""

import requests
from typing import List, Optional

NYC_TREE_API = "https://data.cityofnewyork.us/resource/uvpi-gqnh.json"

# NYC Boundaries (tighter to exclude Westchester suburbs)
NYC_BOUNDS = {
    "lat_min": 40.4,
    "lat_max": 40.92,     # Just below Yonkers/Westchester
    "lon_min": -74.3,
    "lon_max": -73.7
}


def is_nyc(lat: float, lon: float) -> bool:
    """Check if coordinates are within NYC boundaries."""
    return (
        NYC_BOUNDS["lat_min"] <= lat <= NYC_BOUNDS["lat_max"] and
        NYC_BOUNDS["lon_min"] <= lon <= NYC_BOUNDS["lon_max"]
    )


def get_street_trees(lat: float, lon: float, radius_deg: float = 0.0045) -> Optional[List]:
    """
    Get street trees from NYC Street Tree Census within radius.

    Args:
        lat: Latitude
        lon: Longitude
        radius_deg: Search radius in degrees (~500m at NYC latitude)

    Returns:
        List of tree dicts or None if API fails
    """
    try:
        query_params = {
            "$where": (
                f"latitude between {lat - radius_deg} and {lat + radius_deg} "
                f"and longitude between {lon - radius_deg} and {lon + radius_deg}"
            ),
            "$limit": 5000
        }

        response = requests.get(NYC_TREE_API, params=query_params, timeout=10)

        if response.status_code != 200:
            return None

        return response.json()

    except Exception as e:
        print(f"NYC Tree API error: {e}")
        return None
