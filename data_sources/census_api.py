"""
Census API Client
Pure API wrapper for Census Bureau data sources
"""

import os
import requests
from typing import Dict, Optional
from dotenv import load_dotenv

load_dotenv()

CENSUS_API_KEY = os.getenv("CENSUS_API_KEY")
CENSUS_BASE_URL = "https://api.census.gov/data"
GEOCODER_URL = "https://geocoding.geo.census.gov/geocoder/geographies/coordinates"

if not CENSUS_API_KEY:
    raise ValueError("CENSUS_API_KEY not found in .env file")


def get_census_tract(lat: float, lon: float) -> Optional[Dict]:
    """
    Convert lat/lon to Census tract FIPS codes.
    
    Returns:
        {
            "state_fips": str,
            "county_fips": str,
            "tract_fips": str,
            "geoid": str,
            "name": str,
            "basename": str
        }
    """
    try:
        params = {
            "x": lon,
            "y": lat,
            "benchmark": "Public_AR_Current",
            "vintage": "Current_Current",
            "format": "json",
        }

        response = requests.get(GEOCODER_URL, params=params, timeout=10)
        if response.status_code != 200:
            return None

        data = response.json()
        if "result" not in data or "geographies" not in data["result"]:
            return None

        geographies = data["result"]["geographies"]
        if "Census Tracts" not in geographies or not geographies["Census Tracts"]:
            return None

        tract_data = geographies["Census Tracts"][0]
        return {
            "state_fips": tract_data["STATE"],
            "county_fips": tract_data["COUNTY"],
            "tract_fips": tract_data["TRACT"],
            "geoid": tract_data["GEOID"],
            "name": tract_data.get("NAME", "Unknown"),
            "basename": tract_data.get("BASENAME", ""),
        }

    except Exception as e:
        print(f"Census tract lookup error: {e}")
        return None


def get_land_area(tract: Dict) -> Optional[float]:
    """
    Get land area in square miles for a Census tract from TIGERweb.
    
    Args:
        tract: Dict from get_census_tract()
    
    Returns:
        Land area in square miles
    """
    try:
        base_url = (
            "https://tigerweb.geo.census.gov/arcgis/rest/services/"
            "TIGERweb/tigerWMS_ACS2022/MapServer/6/query"
        )

        where = (
            f"STATE='{tract['state_fips']}' AND "
            f"COUNTY='{tract['county_fips']}' AND "
            f"TRACT='{tract['tract_fips']}'"
        )

        params = {
            "where": where,
            "outFields": "AREALAND,AREAWATER,NAME,GEOID",
            "returnGeometry": "false",
            "f": "json",
        }

        response = requests.get(base_url, params=params, timeout=10)
        if response.status_code != 200:
            return None

        data = response.json()
        features = data.get("features", [])
        if not features:
            return None

        attrs = features[0].get("attributes", {}) or {}
        aland_m2 = float(attrs.get("AREALAND", 0))
        if aland_m2 <= 0:
            return None

        land_sq_mi = aland_m2 / 2.59e6  # m² → mi²
        return land_sq_mi

    except Exception as e:
        print(f"Land area lookup error: {e}")
        return None


def get_population(tract: Dict) -> Optional[int]:
    """
    Get population for a Census tract from ACS 5-Year data.
    
    Args:
        tract: Dict from get_census_tract()
    
    Returns:
        Population count
    """
    try:
        url = f"{CENSUS_BASE_URL}/2022/acs/acs5"
        params = {
            "get": "B01001_001E,NAME",  # Total population
            "for": f"tract:{tract['tract_fips']}",
            "in": f"state:{tract['state_fips']} county:{tract['county_fips']}",
            "key": CENSUS_API_KEY,
        }

        response = requests.get(url, params=params, timeout=10)
        if response.status_code != 200:
            return None

        data = response.json()
        if len(data) < 2:
            return None

        population = int(data[1][0]) if data[1][0] else 0
        return population

    except Exception as e:
        print(f"Population lookup error: {e}")
        return None


def get_population_density(lat: float, lon: float, tract: Optional[Dict] = None) -> Optional[float]:
    """
    Get population density (people per sq mi).
    
    Args:
        lat: Latitude
        lon: Longitude
        tract: Optional pre-fetched tract data (for efficiency)
    
    Returns:
        Population density (people/sq mi)
    """
    if tract is None:
        tract = get_census_tract(lat, lon)
    if not tract:
        return None

    population = get_population(tract)
    if population is None:
        return None

    area_sq_mi = get_land_area(tract)
    if not area_sq_mi:
        area_sq_mi = 2.0  # Fallback estimate

    density = population / area_sq_mi if area_sq_mi > 0 else 0
    return density


def get_tree_canopy_usfs(lat: float, lon: float, tract: Optional[Dict] = None) -> Optional[float]:
    """
    Get tree canopy coverage % from USFS Urban Tree Canopy dataset.
    
    Args:
        lat: Latitude
        lon: Longitude
        tract: Optional pre-fetched tract data (for efficiency)
    
    Returns:
        Tree canopy percentage (0-100) or None if unavailable
    """
    if tract is None:
        tract = get_census_tract(lat, lon)
    if not tract:
        return None

    try:
        base_url = (
            "https://apps.fs.usda.gov/arcx/rest/services/RDS/"
            "UrbanTreeCanopy/MapServer/0/query"
        )

        params = {
            "where": f"GEOID='{tract['geoid']}'",
            "outFields": "GEOID,UTC_PERCEN,TREECAN_AC,TOTAL_AC",
            "returnGeometry": "false",
            "f": "json",
        }

        response = requests.get(base_url, params=params, timeout=10)
        if response.status_code != 200:
            return None

        data = response.json()
        features = data.get("features", [])
        if not features:
            return None

        attrs = features[0].get("attributes", {})
        canopy_percent = float(attrs.get("UTC_PERCEN", 0))
        return canopy_percent

    except Exception as e:
        print(f"USFS tree canopy lookup error: {e}")
        return None


# Alias for compatibility with greenery pillar
def get_tree_canopy(lat: float, lon: float, tract: Optional[Dict] = None) -> Optional[float]:
    """Alias for get_tree_canopy_usfs() for backward compatibility."""
    return get_tree_canopy_usfs(lat, lon, tract)


def get_housing_data(lat: float, lon: float, tract: Optional[Dict] = None) -> Optional[Dict]:
    """
    Get housing value metrics from Census ACS 5-Year data.
    
    Args:
        lat: Latitude
        lon: Longitude
        tract: Optional pre-fetched tract data (for efficiency)
    
    Returns:
        {
            "median_home_value": float,
            "median_household_income": float,
            "median_rooms": float
        }
    """
    if tract is None:
        tract = get_census_tract(lat, lon)
    if not tract:
        return None

    try:
        print("🏠 Fetching housing data from Census ACS...")

        url = f"{CENSUS_BASE_URL}/2022/acs/acs5"
        params = {
            "get": "B25077_001E,B19013_001E,B25018_001E,NAME",  # home value, income, rooms
            "for": f"tract:{tract['tract_fips']}",
            "in": f"state:{tract['state_fips']} county:{tract['county_fips']}",
            "key": CENSUS_API_KEY,
        }

        response = requests.get(url, params=params, timeout=10)
        if response.status_code != 200:
            print(f"   ⚠️  ACS API returned status {response.status_code}")
            return None

        data = response.json()
        if len(data) < 2:
            print("   ⚠️  No housing data returned")
            return None

        # Parse values (handle nulls)
        median_value = float(data[1][0]) if data[1][0] and data[1][0] != "-666666666" else None
        median_income = float(data[1][1]) if data[1][1] and data[1][1] != "-666666666" else None
        median_rooms = float(data[1][2]) if data[1][2] and data[1][2] != "-666666666" else None

        if not median_value or not median_income or not median_rooms:
            print("   ⚠️  Incomplete housing data")
            return None

        print(f"   ✅ Median home value: ${int(median_value):,}")
        print(f"   💰 Median household income: ${int(median_income):,}")
        print(f"   🏡 Median rooms: {median_rooms:.1f}")

        return {
            "median_home_value": median_value,
            "median_household_income": median_income,
            "median_rooms": median_rooms
        }

    except Exception as e:
        print(f"   ⚠️  Housing data lookup failed: {e}")
        return None


def classify_area_by_density(density: float) -> Dict[str, str]:
    """
    Classify area type based on population density.
    
    Args:
        density: Population density (people/sq mi)
    
    Returns:
        {
            "classification": str,  # urban_core, suburban, urban_cluster, rural
            "description": str
        }
    """
    if density >= 10000:
        return {
            "classification": "urban_core",
            "description": "Dense urban area"
        }
    elif density >= 2500:
        return {
            "classification": "suburban",
            "description": "Suburban area"
        }
    elif density >= 1000:
        return {
            "classification": "urban_cluster",
            "description": "Small city or town"
        }
    else:
        return {
            "classification": "rural",
            "description": "Rural area"
        }