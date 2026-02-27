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

# Load environment variables from .env file
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
        
        # Extract CBSA/MSA + CSA data if available.
        # NOTE: The Census geocoder returns multiple geography layers. For economic/metro queries
        # we prefer Metropolitan/Micropolitan Statistical Areas (CBSA/MSA).
        cbsa_code = None
        cbsa_name = None
        csa_code = None
        csa_name = None

        # Prefer CBSA/MSA (Metropolitan Statistical Areas).
        # IMPORTANT: The default coordinates endpoint does NOT always include the MSA layer
        # unless explicitly requested via a `layers=` param. If missing, do a targeted
        # follow-up request for metro layers.
        def _try_extract_msa(geo_dict):
            nonlocal cbsa_code, cbsa_name
            msa_layer = geo_dict.get("Metropolitan Statistical Areas") or geo_dict.get("Metropolitan Statistical Area")
            if msa_layer:
                msa_data = msa_layer[0]
                cbsa_code = msa_data.get("GEOID")
                cbsa_name = msa_data.get("NAME")

        _try_extract_msa(geographies)

        if not cbsa_code:
            try:
                # Targeted metro request (Seattle/NYC require this)
                msa_params = dict(params)
                msa_params["layers"] = "Metropolitan Statistical Areas"
                msa_resp = _make_request_with_retry(GEOCODER_URL, msa_params, timeout=10)
                if msa_resp is not None:
                    msa_data = msa_resp.json()
                    msa_geos = (msa_data.get("result", {}) or {}).get("geographies", {}) or {}
                    _try_extract_msa(msa_geos)
            except Exception:
                pass

        # If still missing, try micropolitan layer (for smaller towns)
        if not cbsa_code:
            try:
                micro_params = dict(params)
                micro_params["layers"] = "Micropolitan Statistical Areas"
                micro_resp = _make_request_with_retry(GEOCODER_URL, micro_params, timeout=10)
                if micro_resp is not None:
                    micro_data = micro_resp.json()
                    micro_geos = (micro_data.get("result", {}) or {}).get("geographies", {}) or {}
                    layer = micro_geos.get("Micropolitan Statistical Areas") or micro_geos.get("Micropolitan Statistical Area")
                    if layer:
                        micro = layer[0]
                        cbsa_code = micro.get("GEOID")
                        cbsa_name = micro.get("NAME")
            except Exception:
                pass

        # Also capture Combined Statistical Areas (CSA) when present
        if "Combined Statistical Areas" in geographies and geographies["Combined Statistical Areas"]:
            csa_data = geographies["Combined Statistical Areas"][0]
            csa_code = csa_data.get("GEOID")
            csa_name = csa_data.get("NAME")
        
        result = {
            "state_fips": tract_data["STATE"],
            "county_fips": tract_data["COUNTY"],
            "tract_fips": tract_data["TRACT"],
            "geoid": tract_data["GEOID"],
            "name": tract_data.get("NAME", "Unknown"),
            "basename": tract_data.get("BASENAME", ""),
        }
        
        # Add metro geography data if available
        if cbsa_code:
            result["cbsa_code"] = cbsa_code
            result["cbsa_name"] = cbsa_name
        if csa_code:
            result["csa_code"] = csa_code
            result["csa_name"] = csa_name
        
        return result

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

        # Use retry logic for better timeout handling
        response = _make_request_with_retry(url, params, timeout=15, max_retries=3)
        if response is None:
            print(f"   ⚠️  ACS API request failed after retries")
            return None

        data = response.json()
        if len(data) < 2:
            print("   ⚠️  No housing data returned")
            return None

        # Parse values (handle nulls and error codes)
        # Census error codes: -666666666 (null), -999999999 (median cannot be calculated),
        # -888888888 (median falls in lowest interval), -555555555 (median falls in highest interval)
        def parse_census_value(value_str):
            """Parse Census value, handling error codes."""
            if not value_str:
                return None
            value_str = str(value_str).strip()
            # Check for error codes (all negative codes indicate data issues)
            if value_str.startswith("-") or value_str in ["-666666666", "-999999999", "-888888888", "-555555555"]:
                return None
            try:
                value = float(value_str)
                # Additional validation: reject negative values (except error codes already handled)
                if value < 0:
                    return None
                return value
            except (ValueError, TypeError):
                return None

        median_value = parse_census_value(data[1][0])
        median_income = parse_census_value(data[1][1])
        median_rooms = parse_census_value(data[1][2])

        if not median_value or not median_income or not median_rooms:
            print("   ⚠️  Incomplete housing data (missing or error-coded values)")
            return None

        # Validation: Flag suspiciously low income values
        # Income below $30k is suspicious for most areas (could be student housing, etc.)
        # This is a data quality warning, not a rejection
        if median_income < 30000:
            print(f"   ⚠️  WARNING: Median income ${int(median_income):,} seems unusually low")
            print(f"      This may indicate student housing or unrepresentative tract data")

        # Validation: Flag suspiciously low home values
        if median_value < 50000:
            print(f"   ⚠️  WARNING: Median home value ${int(median_value):,} seems unusually low")

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


@cached(ttl_seconds=CACHE_TTL['census_data'])
@safe_api_call("census", required=False)
@handle_api_timeout(timeout_seconds=15)
def get_commute_time(lat: float, lon: float, tract: Optional[Dict] = None) -> Optional[float]:
    """
    Get mean travel time to work (minutes) from Census ACS 5-Year profile data.
    
    Returns:
        Mean commute time in minutes, or None if unavailable.
    """
    if tract is None:
        tract = get_census_tract(lat, lon)
    if not tract:
        return None

    try:
        print("🚆 Fetching commute time from Census ACS profile...")

        url = f"{CENSUS_BASE_URL}/2022/acs/acs5/profile"
        params = {
            "get": "DP03_0025E,NAME",  # Mean travel time to work
            "for": f"tract:{tract['tract_fips']}",
            "in": f"state:{tract['state_fips']} county:{tract['county_fips']}",
            "key": CENSUS_API_KEY,
        }

        response = requests.get(url, params=params, timeout=10)
        if response.status_code != 200:
            print(f"   ⚠️  ACS profile API returned status {response.status_code}")
            return None

        data = response.json()
        if len(data) < 2:
            print("   ⚠️  No commute data returned")
            return None

        value = data[1][0]
        if not value or value in {"-666666666", "-222222222"}:
            print("   ⚠️  Commute time data is unavailable or suppressed")
            return None

        commute_minutes = float(value)
        print(f"   ✅ Mean commute time: {commute_minutes:.1f} minutes")
        return commute_minutes

    except Exception as e:
        print(f"   ⚠️  Commute time lookup failed: {e}")
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


@cached(ttl_seconds=CACHE_TTL['census_data'])
@safe_api_call("census", required=False)
@handle_api_timeout(timeout_seconds=15)
def get_mobility_data(lat: float, lon: float, tract: Optional[Dict] = None) -> Optional[Dict]:
    """
    Get residential mobility data (same house 1 year ago) from ACS B07003.

    Returns:
        {
            "same_house_pct": float,  # percent 0-100
            "same_house_count": int,
            "total_population_1yr": int,
        }
    """
    if tract is None:
        tract = get_census_tract(lat, lon)
    if not tract:
        return None

    try:
        print("🏡 Fetching mobility data (B07003) from Census ACS...")

        url = f"{CENSUS_BASE_URL}/2022/acs/acs5"
        # B07003_001E: Total population 1 year and over
        # B07003_002E: Same house 1 year ago
        params = {
            "get": "B07003_001E,B07003_002E,NAME",
            "for": f"tract:{tract['tract_fips']}",
            "in": f"state:{tract['state_fips']} county:{tract['county_fips']}",
            "key": CENSUS_API_KEY,
        }

        response = _make_request_with_retry(url, params, timeout=15, max_retries=3)
        if response is None:
            print("   ⚠️  ACS mobility request failed after retries")
            return None

        data = response.json()
        if len(data) < 2:
            print("   ⚠️  No mobility data returned")
            return None

        row = data[1]
        try:
            total_1yr = int(row[0]) if row[0] else 0
            same_house = int(row[1]) if row[1] else 0
        except (ValueError, TypeError):
            return None

        if total_1yr <= 0 or same_house < 0 or same_house > total_1yr:
            print("   ⚠️  Mobility data invalid or missing")
            return None

        same_house_pct = (same_house / total_1yr) * 100.0
        return {
            "same_house_pct": same_house_pct,
            "same_house_count": same_house,
            "total_population_1yr": total_1yr,
        }

    except Exception as e:
        print(f"   ⚠️  Mobility data lookup failed: {e}")
        return None


def get_diversity_data(lat: float, lon: float, tract: Optional[Dict] = None) -> Optional[Dict]:
    """
    Get race, income, and age distributions for Social Fabric Diversity scoring.

    Returns:
        {
            "race_counts": Dict[str, int],
            "income_counts": Dict[str, int],
            "age_counts": {
                "youth": int,
                "prime": int,
                "seniors": int,
            },
        }
    """
    if tract is None:
        tract = get_census_tract(lat, lon)
    if not tract:
        return None

    try:
        base_acs5 = f"{CENSUS_BASE_URL}/2022/acs/acs5"

        # ---- Race: B02001 (total + race categories) ----
        race_vars = [
            "B02001_001E",  # Total
            "B02001_002E",  # White alone
            "B02001_003E",  # Black or African American alone
            "B02001_004E",  # American Indian and Alaska Native alone
            "B02001_005E",  # Asian alone
            "B02001_006E",  # Native Hawaiian and Other Pacific Islander alone
            "B02001_007E",  # Some other race alone
            "B02001_008E",  # Two or more races
            "B02001_009E",  # Two races including some other race
            "B02001_010E",  # Two races excluding some other race, and 3+ races
        ]
        params_race = {
            "get": ",".join(race_vars),
            "for": f"tract:{tract['tract_fips']}",
            "in": f"state:{tract['state_fips']} county:{tract['county_fips']}",
            "key": CENSUS_API_KEY,
        }
        resp_race = _make_request_with_retry(base_acs5, params_race, timeout=15, max_retries=3)
        if resp_race is None:
            return None
        data_race = resp_race.json()
        if len(data_race) < 2:
            return None
        race_row = data_race[1]
        try:
            race_total = int(race_row[0]) if race_row[0] else 0
        except (ValueError, TypeError):
            race_total = 0
        race_counts: Dict[str, int] = {}
        for i, var in enumerate(race_vars[1:], start=1):
            try:
                v = int(race_row[i]) if race_row[i] else 0
            except (ValueError, TypeError):
                v = 0
            race_counts[var] = v

        # ---- Income: B19001 (total + 16 income brackets) ----
        income_vars = [
            "B19001_001E",  # Total
            "B19001_002E", "B19001_003E", "B19001_004E", "B19001_005E",
            "B19001_006E", "B19001_007E", "B19001_008E", "B19001_009E",
            "B19001_010E", "B19001_011E", "B19001_012E", "B19001_013E",
            "B19001_014E", "B19001_015E", "B19001_016E", "B19001_017E",
        ]
        params_inc = {
            "get": ",".join(income_vars),
            "for": f"tract:{tract['tract_fips']}",
            "in": f"state:{tract['state_fips']} county:{tract['county_fips']}",
            "key": CENSUS_API_KEY,
        }
        resp_inc = _make_request_with_retry(base_acs5, params_inc, timeout=15, max_retries=3)
        if resp_inc is None:
            return None
        data_inc = resp_inc.json()
        if len(data_inc) < 2:
            return None
        inc_row = data_inc[1]
        try:
            income_total = int(inc_row[0]) if inc_row[0] else 0
        except (ValueError, TypeError):
            income_total = 0
        income_counts: Dict[str, int] = {}
        for i, var in enumerate(income_vars[1:], start=1):
            try:
                v = int(inc_row[i]) if inc_row[i] else 0
            except (ValueError, TypeError):
                v = 0
            income_counts[var] = v

        # ---- Age buckets: aggregate B01001 into Youth / Prime / Seniors ----
        # Youth: <18 (Male B01001_003–006, Female B01001_027–030)
        # Prime: 18–64 (Male B01001_007–019, Female B01001_031–043)
        # Seniors: 65+ (Male B01001_020–025, Female B01001_044–049)
        age_vars = [
            "B01001_003E", "B01001_004E", "B01001_005E", "B01001_006E",  # Youth male
            "B01001_007E", "B01001_008E", "B01001_009E", "B01001_010E", "B01001_011E",
            "B01001_012E", "B01001_013E", "B01001_014E", "B01001_015E", "B01001_016E",
            "B01001_017E", "B01001_018E", "B01001_019E",  # Prime male
            "B01001_020E", "B01001_021E", "B01001_022E", "B01001_023E",
            "B01001_024E", "B01001_025E",  # Seniors male
            "B01001_027E", "B01001_028E", "B01001_029E", "B01001_030E",  # Youth female
            "B01001_031E", "B01001_032E", "B01001_033E", "B01001_034E", "B01001_035E",
            "B01001_036E", "B01001_037E", "B01001_038E", "B01001_039E", "B01001_040E",
            "B01001_041E", "B01001_042E", "B01001_043E",  # Prime female
            "B01001_044E", "B01001_045E", "B01001_046E", "B01001_047E",
            "B01001_048E", "B01001_049E",  # Seniors female
        ]
        params_age = {
            "get": ",".join(age_vars),
            "for": f"tract:{tract['tract_fips']}",
            "in": f"state:{tract['state_fips']} county:{tract['county_fips']}",
            "key": CENSUS_API_KEY,
        }
        resp_age = _make_request_with_retry(base_acs5, params_age, timeout=15, max_retries=3)
        if resp_age is None:
            return None
        data_age = resp_age.json()
        if len(data_age) < 2:
            return None
        age_row = data_age[1]

        def _val(idx: int) -> int:
            try:
                return int(age_row[idx]) if age_row[idx] else 0
            except (ValueError, TypeError, IndexError):
                return 0

        # Indices here are 0-based into age_row which aligns with age_vars order
        youth_male = sum(_val(i) for i in range(0, 4))        # 003–006
        prime_male = sum(_val(i) for i in range(4, 4 + 13))   # 007–019
        seniors_male = sum(_val(i) for i in range(17, 23))    # 020–025

        youth_female = sum(_val(i) for i in range(23, 27))    # 027–030
        prime_female = sum(_val(i) for i in range(27, 27 + 13))  # 031–043
        seniors_female = sum(_val(i) for i in range(40, 46))  # 044–049

        youth = youth_male + youth_female
        prime = prime_male + prime_female
        seniors = seniors_male + seniors_female

        age_counts = {"youth": youth, "prime": prime, "seniors": seniors}

        return {
            "race_counts": race_counts,
            "income_counts": income_counts,
            "age_counts": age_counts,
        }

    except Exception as e:
        print(f"   ⚠️  Diversity data lookup failed: {e}")
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