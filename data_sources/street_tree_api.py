"""
Street Tree API Client
Unified module for querying street tree data from various city open data APIs.
Supports ArcGIS Hub and Socrata API formats.

Proof of concept: 5 ArcGIS Hub cities
"""

import requests
from typing import List, Optional, Dict
from .cache import cached, CACHE_TTL

# City Registry: ArcGIS Hub API cities (Proof of Concept - 4 cities)
# All use similar REST API structure - no API keys required (public open data)
# Working cities: Washington DC, Seattle, Portland, Baltimore
STREET_TREE_CITIES = {
    "Washington": {
        "api_type": "arcgis_rest",
        "url": "https://maps2.dcgis.dc.gov/dcgis/rest/services/DCGIS_DATA/Transportation_WebMercator/MapServer/35/query",
        "state": "DC",
        "bounds": {
            "lat_min": 38.79,
            "lat_max": 38.995,
            "lon_min": -77.12,
            "lon_max": -76.91
        },
        "lat_field": "latitude",
        "lon_field": "longitude",
    },
    "Seattle": {
        "api_type": "arcgis_rest",
        "url": "https://services.arcgis.com/ZOyb2t4B0UYuYNYH/arcgis/rest/services/Combined_Tree_Point/FeatureServer/0/query",
        "state": "WA",
        "bounds": {
            "lat_min": 47.49,
            "lat_max": 47.73,
            "lon_min": -122.45,
            "lon_max": -122.24
        },
        "lat_field": "latitude",
        "lon_field": "longitude",
    },
    "Portland": {
        "api_type": "arcgis_rest",
        "url": "https://www.portlandmaps.com/arcgis/rest/services/Public/Parks_Street_Tree_Inventory_Active/MapServer/4/query",
        "state": "OR",
        "bounds": {
            "lat_min": 45.43,
            "lat_max": 45.65,
            "lon_min": -122.84,
            "lon_max": -122.47
        },
        "lat_field": "latitude",
        "lon_field": "longitude",
    },
    "Baltimore": {
        "api_type": "arcgis_rest",
        "url": "https://gis.baltimorecity.gov/egis/rest/services/Foresty/Trees/FeatureServer/0/query",
        "state": "MD",
        "bounds": {
            "lat_min": 39.20,
            "lat_max": 39.37,
            "lon_min": -76.71,
            "lon_max": -76.52
        },
        "lat_field": "latitude",
        "lon_field": "longitude",
    },
}


def is_city_with_street_trees(city: str, lat: float, lon: float) -> Optional[str]:
    """
    Check if coordinates are within a city that has street tree API data.
    
    Args:
        city: City name (e.g., "Washington", "Seattle", "Washington, DC")
        lat, lon: Coordinates
    
    Returns:
        City key if match found, None otherwise
    """
    if not city:
        return None
    
    city_lower = city.lower().strip()
    
    # Check each city in registry
    for city_key, city_data in STREET_TREE_CITIES.items():
        # Check bounds first (more efficient)
        bounds = city_data["bounds"]
        if not (bounds["lat_min"] <= lat <= bounds["lat_max"] and
                bounds["lon_min"] <= lon <= bounds["lon_max"]):
            continue
        
        # Then check city name match (partial match for "Washington, DC" -> "Washington")
        city_key_lower = city_key.lower()
        if (city_key_lower in city_lower or 
            city_lower in city_key_lower or
            city_lower.startswith(city_key_lower) or
            # Handle "Washington, DC" -> "Washington"
            city_lower.split(',')[0].strip() == city_key_lower):
            return city_key
    
    return None


@cached(ttl_seconds=CACHE_TTL['osm_queries'])  # Reuse OSM cache TTL (7 days)
def get_street_trees(city: str, lat: float, lon: float, radius_m: int = 1000) -> Optional[List[Dict]]:
    """
    Get street trees from city open data API.
    
    Only queries if city matches registry and coordinates are within bounds.
    Uses appropriate API format based on city.
    
    Args:
        city: City name
        lat, lon: Coordinates
        radius_m: Search radius in meters (default 1000m)
    
    Returns:
        List of tree dicts or None if no match or API fails
    """
    # Check if city has street tree API
    city_key = is_city_with_street_trees(city, lat, lon)
    if not city_key:
        return None
    
    city_data = STREET_TREE_CITIES[city_key]
    
    # Query based on API type
    if city_data["api_type"] in ("arcgis", "arcgis_rest"):
        return _query_arcgis_trees(city_data, lat, lon, radius_m)
    
    return None


def _query_arcgis_trees(city_data: Dict, lat: float, lon: float, radius_m: int) -> Optional[List[Dict]]:
    """
    Query ArcGIS Hub/REST API for street trees.
    
    ArcGIS APIs typically use:
    - Feature service endpoints (REST API)
    - Socrata-style endpoints (JSON)
    - GeoJSON formats
    
    Args:
        city_data: City configuration from STREET_TREE_CITIES
        lat, lon: Coordinates
        radius_m: Search radius in meters
    
    Returns:
        List of tree features or None if API fails
    """
    try:
        url = city_data["url"]
        lat_field = city_data.get("lat_field", "latitude")
        lon_field = city_data.get("lon_field", "longitude")
        
        # Convert radius_m to approximate degrees
        radius_deg_lat = radius_m / 111000  # ~111km per degree latitude
        radius_deg_lon = radius_m / (111000 * abs(lat) / 90)
        
        # Build bounding box
        lat_min = lat - radius_deg_lat
        lat_max = lat + radius_deg_lat
        lon_min = lon - radius_deg_lon
        lon_max = lon + radius_deg_lon
        
        # Try Feature Server format (ArcGIS REST API)
        if "/FeatureServer/" in url or "/MapServer/" in url:
            # Standard ArcGIS REST API query with spatial search
            # Use geometry point query with distance for radius search
            # IMPORTANT: Specify inSR and outSR for proper coordinate system handling
            params = {
                "geometry": f"{lon},{lat}",  # Point coordinates (lon,lat)
                "geometryType": "esriGeometryPoint",
                # Use esriSpatialRelIntersects (works for Seattle, DC, Portland, Baltimore)
                # Some APIs may prefer esriSpatialRelWithin - test both if needed
                "spatialRel": "esriSpatialRelIntersects",
                "distance": radius_m,
                "units": "esriSRUnit_Meter",
                "inSR": "4326",  # Input spatial reference: WGS84 (lat/lon)
                "outSR": "4326",  # Output spatial reference: WGS84 (lat/lon)
                "outFields": "*",
                "f": "json",
                "returnGeometry": "true",
                "resultRecordCount": 10000,  # Request up to 10k features (most APIs limit at ~2k)
            }
            # Increase timeout for slower APIs (e.g., Seattle's proxy server can be slow)
            response = requests.get(url, params=params, timeout=30)
            if response.status_code == 200:
                data = response.json()
                # Check for errors in response
                if "error" in data:
                    error_msg = data.get('error', {}).get('message', 'Unknown error')
                    print(f"⚠️  ArcGIS API error for {city_data.get('state', 'unknown')}: {error_msg}")
                    return None
                if "features" in data:
                    features = data["features"]
                    # Return list of feature attributes (not full features)
                    return features
        
        # Try Socrata-style endpoint (rows.json)
        elif "rows.json" in url:
            # Socrata API format with $where clause
            params = {
                "$where": (
                    f"{lat_field} between {lat_min} and {lat_max} "
                    f"and {lon_field} between {lon_min} and {lon_max}"
                ),
                "$limit": 5000
            }
            response = requests.get(url, params=params, timeout=15)
            if response.status_code == 200:
                data = response.json()
                # Socrata returns list of dicts
                if isinstance(data, list):
                    return data
                # Or wrapped in "data" field
                elif "data" in data:
                    return data["data"]
        
        # Try standard JSON endpoint
        else:
            response = requests.get(url, timeout=15)
            if response.status_code == 200:
                data = response.json()
                if "features" in data:
                    return data["features"]
                elif isinstance(data, list):
                    return data
        
        return None
        
    except Exception as e:
        print(f"⚠️  Street tree API error for {city_data.get('state', 'unknown')}: {e}")
        return None
