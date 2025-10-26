"""
Census API Client
Pure API wrapper for Census Bureau data sources
"""

import os
import requests
import time
from typing import Dict, Optional
from dotenv import load_dotenv
from .cache import cached, CACHE_TTL
from .error_handling import with_fallback, safe_api_call, handle_api_timeout, check_api_credentials

load_dotenv()

CENSUS_API_KEY = os.getenv("CENSUS_API_KEY")
CENSUS_BASE_URL = "https://api.census.gov/data"
GEOCODER_URL = "https://geocoding.geo.census.gov/geocoder/geographies/coordinates"

# Check if Census API key is available
if not CENSUS_API_KEY:
    print("⚠️  CENSUS_API_KEY not found - Census-dependent pillars will use fallback scores")


def _make_request_with_retry(url: str, params: Dict, timeout: int = 10, max_retries: int = 3):
    """
    Make an HTTP request with retry logic and rate limit handling.
    
    Args:
        url: URL to request
        params: Request parameters
        timeout: Request timeout in seconds
        max_retries: Maximum number of retry attempts
        
    Returns:
        Response object or None if all retries fail
    """
    last_exception = None
    
    for attempt in range(max_retries):
        try:
            response = requests.get(url, params=params, timeout=timeout)
            
            # Check for rate limiting (429 status code)
            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 2 ** attempt))
                print(f"⚠️  Census API rate limited, waiting {retry_after}s...")
                time.sleep(retry_after)
                continue  # Retry
            
            # Other errors
            if response.status_code != 200:
                print(f"⚠️  Census API returned status {response.status_code}")
                if response.status_code >= 500 and attempt < max_retries - 1:
                    # Server error, retry with backoff
                    time.sleep(2 ** attempt)
                    continue
                return None
            
            return response
            
        except requests.exceptions.Timeout:
            last_exception = "timeout"
            if attempt < max_retries - 1:
                print(f"⚠️  Census API timeout, retrying... ({attempt + 1}/{max_retries})")
                time.sleep(2 ** attempt)
            continue
            
        except requests.exceptions.RequestException as e:
            last_exception = str(e)
            if attempt < max_retries - 1:
                print(f"⚠️  Census API error: {e}, retrying... ({attempt + 1}/{max_retries})")
                time.sleep(2 ** attempt)
            continue
    
    print(f"⚠️  Census API failed after {max_retries} attempts: {last_exception}")
    return None


@cached(ttl_seconds=CACHE_TTL['census_data'])
@safe_api_call("census", required=False)
@handle_api_timeout(timeout_seconds=15)
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

        response = _make_request_with_retry(GEOCODER_URL, params, timeout=10)
        if response is None:
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

        response = _make_request_with_retry(base_url, params, timeout=10)
        if response is None:
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

        response = _make_request_with_retry(url, params, timeout=10)
        if response is None:
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


@cached(ttl_seconds=CACHE_TTL['census_data'])
@safe_api_call("census", required=False)
@handle_api_timeout(timeout_seconds=20)
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


def get_year_built_data(lat: float, lon: float, tract: Optional[Dict] = None) -> Optional[Dict]:
    """
    Get year built data from Census ACS 5-Year.
    
    Args:
        lat: Latitude
        lon: Longitude
        tract: Optional pre-fetched tract data
    
    Returns:
        {
            "median_year_built": int,
            "pre_1940_pct": float,
            "vintage_pct": float,
            "historic_character_score": float
        }
    """
    if tract is None:
        tract = get_census_tract(lat, lon)
    if not tract:
        return None

    try:
        print("🏛️ Fetching year built data from Census ACS...")

        url = f"{CENSUS_BASE_URL}/2022/acs/acs5"
        
        # Get year built variables + median
        variables = [
            "B25034_001E",  # Total
            "B25034_010E",  # Pre-1940
            "B25034_009E",  # 1940s
            "B25034_008E",  # 1950s
            "B25035_001E",  # Median year
            "NAME"
        ]
        
        params = {
            "get": ",".join(variables),
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
            print("   ⚠️  No year built data returned")
            return None

        # Parse values
        row = data[1]
        total_units = int(row[0]) if row[0] else 0
        
        if total_units == 0:
            return None
            
        pre_1940 = int(row[1]) if row[1] else 0
        decade_1940s = int(row[2]) if row[2] else 0
        decade_1950s = int(row[3]) if row[3] else 0
        median_year = int(row[4]) if row[4] and row[4] != "-666666666" else None

        # Calculate vintage housing percentage (pre-1960)
        vintage_units = pre_1940 + decade_1940s + decade_1950s
        vintage_pct = (vintage_units / total_units) * 100
        
        # Score historic character (0-100)
        if vintage_pct >= 60:
            historic_score = 100.0
        elif vintage_pct >= 40:
            historic_score = 85.0
        elif vintage_pct >= 25:
            historic_score = 70.0
        elif vintage_pct >= 15:
            historic_score = 55.0
        elif vintage_pct >= 10:
            historic_score = 40.0
        else:
            historic_score = 25.0

        result = {
            "median_year_built": median_year,
            "pre_1940_pct": round((pre_1940 / total_units) * 100, 1),
            "vintage_pct": round(vintage_pct, 1),
            "historic_character_score": historic_score
        }

        print(f"   ✅ Median year built: {median_year}")
        print(f"   🏛️ Vintage housing (pre-1960): {result['vintage_pct']}%")
        
        return result

    except Exception as e:
        print(f"   ⚠️  Year built lookup failed: {e}")
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