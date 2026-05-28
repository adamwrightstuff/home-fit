"""
Census API Client
Pure API wrapper for Census Bureau data sources
"""

import json
import math
import os
import requests
import time
from typing import Any, Dict, List, Optional, Tuple
from dotenv import load_dotenv
from .cache import cached, CACHE_TTL
from .error_handling import with_fallback, safe_api_call, handle_api_timeout, check_api_credentials

# Load environment variables from .env file
load_dotenv()

CENSUS_API_KEY = os.getenv("CENSUS_API_KEY")
CENSUS_BASE_URL = "https://api.census.gov/data"
GEOCODER_URL = "https://geocoding.geo.census.gov/geocoder/geographies/coordinates"
# ACS 2022 tract boundaries — point-in-polygon fallback when the coordinates geocoder fails.
TIGERWEB_TRACT_LAYER_URL = (
    "https://tigerweb.geo.census.gov/arcgis/rest/services/"
    "TIGERweb/tigerWMS_ACS2022/MapServer/6/query"
)


def _get_census_tract_tigerweb_point(lat: float, lon: float) -> Optional[Dict]:
    """
    Resolve tract via TIGERweb spatial query (WGS84 point in tract polygon).

    Used when geocoding.geo.census.gov returns no tract (timeouts, partial JSON, edge vintages).
    Does not attach CBSA/CSA; callers that need metro can rely on other fallbacks.
    """
    try:
        params = {
            "geometry": f"{lon},{lat}",
            "geometryType": "esriGeometryPoint",
            "inSR": "4326",
            "spatialRel": "esriSpatialRelIntersects",
            "where": "1=1",
            "outFields": "STATE,COUNTY,TRACT,GEOID,NAME,BASENAME",
            "returnGeometry": "false",
            "f": "json",
        }
        response = _make_request_with_retry(TIGERWEB_TRACT_LAYER_URL, params, timeout=12)
        if response is None:
            return None
        payload = response.json()
        feats = payload.get("features") or []
        if not feats:
            return None
        attrs = (feats[0].get("attributes") or {}) if isinstance(feats[0], dict) else {}
        state = attrs.get("STATE")
        county = attrs.get("COUNTY")
        tract_fips = attrs.get("TRACT")
        geoid = attrs.get("GEOID")
        if not state or not county or not tract_fips or not geoid:
            return None
        return {
            "state_fips": str(state),
            "county_fips": str(county),
            "tract_fips": str(tract_fips),
            "geoid": str(geoid),
            "name": str(attrs.get("NAME") or "Unknown"),
            "basename": str(attrs.get("BASENAME") or ""),
        }
    except Exception as e:
        print(f"TIGERweb tract lookup error: {e}")
        return None


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
            return _get_census_tract_tigerweb_point(lat, lon)

        data = response.json()
        if "result" not in data or "geographies" not in data["result"]:
            return _get_census_tract_tigerweb_point(lat, lon)

        geographies = data["result"]["geographies"]
        if "Census Tracts" not in geographies or not geographies["Census Tracts"]:
            return _get_census_tract_tigerweb_point(lat, lon)

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
        return _get_census_tract_tigerweb_point(lat, lon)


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


def _fetch_housing_acs(for_clause: str, in_clause: str) -> Optional[Dict]:
    """Fetch and parse ACS 5-year housing data for the given Census geography."""
    try:
        url = f"{CENSUS_BASE_URL}/2022/acs/acs5"
        params = {
            "get": "B25077_001E,B19013_001E,B25018_001E,B19025_001E,B19001_001E,B25064_001E,B25003_001E,B25003_003E,NAME",
            "for": for_clause,
            "in": in_clause,
            "key": CENSUS_API_KEY,
        }
        response = _make_request_with_retry(url, params, timeout=15, max_retries=3)
        if response is None:
            return None
        data = response.json()
        if len(data) < 2:
            return None

        def parse_census_value(value_str):
            if not value_str:
                return None
            value_str = str(value_str).strip()
            if value_str.startswith("-") or value_str in ["-666666666", "-999999999", "-888888888", "-555555555"]:
                return None
            try:
                value = float(value_str)
                if value < 0:
                    return None
                return value
            except (ValueError, TypeError):
                return None

        median_value = parse_census_value(data[1][0])
        median_income = parse_census_value(data[1][1])
        median_rooms = parse_census_value(data[1][2])
        aggregate_income = parse_census_value(data[1][3])
        total_households = parse_census_value(data[1][4])
        median_gross_rent = parse_census_value(data[1][5])
        total_occupied = parse_census_value(data[1][6])
        renter_occupied = parse_census_value(data[1][7])

        if not median_income:
            return None

        mean_household_income: Optional[float] = None
        if aggregate_income and total_households and total_households > 0:
            mean_household_income = aggregate_income / total_households

        if median_income < 30000:
            print(f"   ⚠️  WARNING: Median income ${int(median_income):,} seems unusually low")
            print(f"      This may indicate student housing or unrepresentative geography")
        if median_value is not None and median_value < 50000:
            print(f"   ⚠️  WARNING: Median home value ${int(median_value):,} seems unusually low")
        if median_value is not None:
            print(f"   ✅ Median home value: ${int(median_value):,}")
        else:
            print(f"   ℹ️  Median home value: not available (renter-dominant geography)")
        print(f"   💰 Median household income: ${int(median_income):,}")
        if median_rooms is not None:
            print(f"   🏡 Median rooms: {median_rooms:.1f}")
        if median_gross_rent is not None:
            print(f"   🏘️  Median gross rent: ${int(median_gross_rent):,}/mo")

        renter_pct: Optional[float] = None
        if total_occupied and total_occupied > 0 and renter_occupied is not None:
            renter_pct = renter_occupied / total_occupied

        result: Dict[str, Optional[float]] = {
            "median_home_value": median_value,
            "median_household_income": median_income,
            "median_rooms": median_rooms,
        }
        if median_gross_rent is not None:
            result["median_gross_rent"] = median_gross_rent
        if mean_household_income is not None:
            result["mean_household_income"] = mean_household_income
        if renter_pct is not None:
            result["renter_pct"] = renter_pct
        return result

    except Exception:
        return None


@cached(ttl_seconds=CACHE_TTL['census_data'])
@safe_api_call("census", required=False)
@handle_api_timeout(timeout_seconds=20)
def get_housing_data(lat: float, lon: float, tract: Optional[Dict] = None) -> Optional[Dict]:
    """
    Get housing value metrics from Census ACS 5-Year data.
    Uses place-level data for incorporated municipalities; falls back to Census tract.

    Args:
        lat: Latitude
        lon: Longitude
        tract: Optional pre-fetched tract data (for efficiency)

    Returns:
        {
            "median_home_value": float,
            "median_household_income": float,
            "median_rooms": float,
            "geo_level": "place" | "tract"
        }
    """
    if tract is None:
        tract = get_census_tract(lat, lon)
    if not tract:
        return None

    print("🏠 Fetching housing data from Census ACS...")

    # Use place-level data for incorporated municipalities only.
    # No tract fallback — tract data may bleed across municipal boundaries.
    place_geo = get_place_fips_for_coordinates(lat, lon)
    if not place_geo:
        return None

    result = _fetch_housing_acs(
        f"place:{int(place_geo['place_fips'])}",
        f"state:{place_geo['state_fips']}",
    )
    if result:
        result["geo_level"] = "place"
    return result


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


def _acs_mobility_int(val) -> int:
    """Parse ACS estimate; missing / suppressed sentinels → 0."""
    if val in (None, "", "-666666666", "-555555555", "-333333333"):
        return 0
    try:
        v = int(float(val))
        return v if v > 0 else 0
    except (TypeError, ValueError):
        return 0


def _mobility_from_tract_row(
    row: list,
    *,
    include_b07013: bool,
) -> Optional[Dict]:
    """Parse ACS tract row for B07003 (+ optional B07013 blend). Returns dict or None."""
    try:
        total_1yr = _acs_mobility_int(row[0])
        same_house = _acs_mobility_int(row[1])
        same_county = _acs_mobility_int(row[2])
        if include_b07013 and len(row) > 5:
            b13_total = _acs_mobility_int(row[3])
            b13_same_own = _acs_mobility_int(row[4])
            b13_same_rent = _acs_mobility_int(row[5])
        else:
            b13_total = b13_same_own = b13_same_rent = 0
    except (ValueError, TypeError):
        return None

    if total_1yr <= 0:
        return None

    same_house = max(0, min(same_house, total_1yr))
    same_county = max(0, min(same_county, total_1yr))
    rooted = min(same_house + same_county, total_1yr)

    same_house_pct_b07003 = (same_house / total_1yr) * 100.0
    rooted_pct = (rooted / total_1yr) * 100.0

    same_house_pct_b07013: Optional[float] = None
    if include_b07013 and b13_total > 0:
        sh13 = min(b13_same_own + b13_same_rent, b13_total)
        same_house_pct_b07013 = (sh13 / b13_total) * 100.0

    if same_house_pct_b07013 is not None:
        same_house_pct = 0.6 * float(same_house_pct_b07013) + 0.4 * float(same_house_pct_b07003)
    else:
        same_house_pct = same_house_pct_b07003

    return {
        "same_house_pct": same_house_pct,
        "same_house_pct_b07003": same_house_pct_b07003,
        "same_house_pct_b07013": same_house_pct_b07013,
        "rooted_pct": rooted_pct,
        "same_house_count": same_house,
        "same_county_count": same_county,
        "total_population_1yr": total_1yr,
    }


def _fetch_mobility_tract_acs(tract: Dict, *, include_b07013: bool) -> Optional[Dict]:
    """Single ACS GET for tract mobility; include_b07013=False uses B07003 only (fallback path)."""
    url = f"{CENSUS_BASE_URL}/2022/acs/acs5"
    if include_b07013:
        get = "B07003_001E,B07003_004E,B07003_007E,B07013_001E,B07013_005E,B07013_006E,NAME"
    else:
        get = "B07003_001E,B07003_004E,B07003_007E,NAME"
    params = {
        "get": get,
        "for": f"tract:{tract['tract_fips']}",
        "in": f"state:{tract['state_fips']} county:{tract['county_fips']}",
        "key": CENSUS_API_KEY,
    }
    response = _make_request_with_retry(url, params, timeout=15, max_retries=3)
    if response is None:
        return None
    data = response.json()
    if len(data) < 2:
        return None
    return _mobility_from_tract_row(data[1], include_b07013=include_b07013)


@cached(ttl_seconds=CACHE_TTL['census_data'])
@safe_api_call("census", required=False)
@handle_api_timeout(timeout_seconds=15)
def get_mobility_data(lat: float, lon: float, tract: Optional[Dict] = None) -> Optional[Dict]:
    """
    Get residential mobility data from ACS 5-year: B07003 plus B07013 tenure cross-tab.

    Returns:
        {
            "same_house_pct": float,   # tract same-house % for stability (B07003 + B07013 blend)
            "same_house_pct_b07003": float,
            "same_house_pct_b07013": Optional[float],  # None if B07013 unavailable
            "rooted_pct": float,       # same house + moved within same county (B07003 only)
            "same_house_count": int,
            "same_county_count": int,
            "total_population_1yr": int,
        }

    Tract same-house input blends B07013 (same-house owner+renter / household universe) with
    B07003 same-house at 0.6/0.4 when B07013 is available; rooted_pct stays B07003-based.

    If the combined B07003+B07013 request fails, retries with B07003-only for the same tract
    (some tracts return incomplete B07013 rows in the API).
    """
    if tract is None:
        tract = get_census_tract(lat, lon)
    if not tract:
        return None

    try:
        print("🏡 Fetching mobility data (B07003 + B07013) from Census ACS 5-year...")
        out = _fetch_mobility_tract_acs(tract, include_b07013=True)
        if out is not None:
            return out
        print("   ⚠️  ACS mobility (B07003+B07013) unavailable; retrying B07003-only for tract...")
        out = _fetch_mobility_tract_acs(tract, include_b07013=False)
        if out is not None:
            return out
        print("   ⚠️  Mobility data invalid or missing after B07003-only retry")
        return None
    except Exception as e:
        print(f"   ⚠️  Mobility data lookup failed: {e}")
        try:
            out = _fetch_mobility_tract_acs(tract, include_b07013=False)
            if out is not None:
                print("   ✅ B07003-only tract mobility recovered after exception")
                return out
        except Exception:
            pass
        return None


@cached(ttl_seconds=CACHE_TTL['census_data'])
@safe_api_call("census", required=False)
@handle_api_timeout(timeout_seconds=15)
def get_place_fips_for_coordinates(lat: float, lon: float) -> Optional[Dict[str, str]]:
    """
    State FIPS and Census place FIPS for an Incorporated Place, CDP, or Consolidated City
    containing the point.
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
        geographies = (data.get("result") or {}).get("geographies") or {}
        # Order: smaller / more specific place types first where applicable; include
        # Consolidated Cities for areas that are not in Incorporated Places / CDP alone.
        for key in (
            "Incorporated Places",
            "Census Designated Places",
            "Consolidated Cities",
        ):
            layer = geographies.get(key)
            if layer and len(layer) > 0:
                g = layer[0]
                st = g.get("STATE")
                pl = g.get("PLACE")
                if st and pl:
                    return {"state_fips": str(st).zfill(2), "place_fips": str(pl).zfill(5)}
        return None
    except Exception as e:
        print(f"   ⚠️  Place lookup failed: {e}")
        return None


@cached(ttl_seconds=CACHE_TTL['census_data'])
@safe_api_call("census", required=False)
@handle_api_timeout(timeout_seconds=15)
def get_place_same_house_pct(state_fips: str, place_fips: str) -> Optional[float]:
    """ACS B07003 same-house rate (0–100) for a Census place."""
    if not CENSUS_API_KEY or not state_fips or not place_fips:
        return None
    try:
        url = f"{CENSUS_BASE_URL}/2022/acs/acs5"
        pf = str(int(place_fips))  # Census place code without leading zeros
        params = {
            "get": "B07003_001E,B07003_004E,NAME",
            "for": f"place:{pf}",
            "in": f"state:{str(state_fips).zfill(2)}",
            "key": CENSUS_API_KEY,
        }
        response = _make_request_with_retry(url, params, timeout=15, max_retries=3)
        if response is None:
            return None
        data = response.json()
        if len(data) < 2:
            return None
        row = data[1]
        total_1yr = _acs_mobility_int(row[0])
        same_house = _acs_mobility_int(row[1])
        if total_1yr <= 0:
            return None
        same_house = max(0, min(same_house, total_1yr))
        return (same_house / total_1yr) * 100.0
    except Exception as e:
        print(f"   ⚠️  Place mobility lookup failed: {e}")
        return None


def _b25038_long_tenure_counts(row: list) -> Tuple[int, int]:
    """
    From ACS B25038 row (ordered estimates), return (long_tenure_hu, total_occupied).
    Long tenure = moved in 2010 or earlier buckets (owner 005-008, renter 012-015),
    excluding recent movers (2021+, 2018-2020). Matches 2022 ACS 5-year labels.
    """
    def cell(i: int) -> int:
        if i >= len(row):
            return 0
        return _acs_mobility_int(row[i])

    # row order must match get= below: 0=NAME, 1=001 ... or 0=001 if no NAME
    # Callers pass row without header; indices 0..14 for B25038_001E..015E
    total = cell(0)
    if total <= 0:
        return 0, 0
    # 001=total, 002 owner total, 003-004 recent owner, 005-008 long owner,
    # 009 renter total, 010-011 recent renter, 012-015 long renter
    long_o = cell(4) + cell(5) + cell(6) + cell(7)
    long_r = cell(11) + cell(12) + cell(13) + cell(14)
    long_hu = long_o + long_r
    return long_hu, total


@cached(ttl_seconds=CACHE_TTL["census_data"])
@safe_api_call("census", required=False)
@handle_api_timeout(timeout_seconds=15)
def get_tract_long_tenure_housing_pct(tract: Dict) -> Optional[float]:
    """
    % of occupied housing units where householder moved in 2010 or earlier (B25038),
    as a 5+ year rootedness anchor (housing universe, 0-100).
    """
    if not CENSUS_API_KEY or not tract:
        return None
    try:
        url = f"{CENSUS_BASE_URL}/2022/acs/acs5"
        params = {
            "get": (
                "B25038_001E,B25038_002E,B25038_003E,B25038_004E,B25038_005E,B25038_006E,"
                "B25038_007E,B25038_008E,B25038_009E,B25038_010E,B25038_011E,B25038_012E,"
                "B25038_013E,B25038_014E,B25038_015E"
            ),
            "for": f"tract:{tract['tract_fips']}",
            "in": f"state:{tract['state_fips']} county:{tract['county_fips']}",
            "key": CENSUS_API_KEY,
        }
        response = _make_request_with_retry(url, params, timeout=15, max_retries=3)
        if response is None:
            return None
        data = response.json()
        if len(data) < 2:
            return None
        row = data[1]
        long_hu, total = _b25038_long_tenure_counts(row)
        if total <= 0:
            return None
        return 100.0 * float(long_hu) / float(total)
    except Exception as e:
        print(f"   ⚠️  B25038 tract tenure lookup failed: {e}")
        return None


@cached(ttl_seconds=CACHE_TTL["census_data"])
@safe_api_call("census", required=False)
@handle_api_timeout(timeout_seconds=15)
def get_place_long_tenure_housing_pct(state_fips: str, place_fips: str) -> Optional[float]:
    """B25038 long-tenure % for a Census place (same definition as tract)."""
    if not CENSUS_API_KEY or not state_fips or not place_fips:
        return None
    try:
        url = f"{CENSUS_BASE_URL}/2022/acs/acs5"
        pf = str(int(place_fips))
        params = {
            "get": (
                "B25038_001E,B25038_002E,B25038_003E,B25038_004E,B25038_005E,B25038_006E,"
                "B25038_007E,B25038_008E,B25038_009E,B25038_010E,B25038_011E,B25038_012E,"
                "B25038_013E,B25038_014E,B25038_015E"
            ),
            "for": f"place:{pf}",
            "in": f"state:{str(state_fips).zfill(2)}",
            "key": CENSUS_API_KEY,
        }
        response = _make_request_with_retry(url, params, timeout=15, max_retries=3)
        if response is None:
            return None
        data = response.json()
        if len(data) < 2:
            return None
        row = data[1]
        long_hu, total = _b25038_long_tenure_counts(row)
        if total <= 0:
            return None
        return 100.0 * float(long_hu) / float(total)
    except Exception as e:
        print(f"   ⚠️  B25038 place tenure lookup failed: {e}")
        return None


def _offset_lat_lon_meters(lat: float, lon: float, bearing_deg: float, distance_m: float) -> Tuple[float, float]:
    """Return (lat, lon) at bearing (deg from north) and distance in meters."""
    import math

    r_earth = 6371000.0
    lat_rad = math.radians(lat)
    lon_rad = math.radians(lon)
    br = math.radians(bearing_deg)
    lat2 = math.asin(
        math.sin(lat_rad) * math.cos(distance_m / r_earth)
        + math.cos(lat_rad) * math.sin(distance_m / r_earth) * math.cos(br)
    )
    lon2 = lon_rad + math.atan2(
        math.sin(br) * math.sin(distance_m / r_earth) * math.cos(lat_rad),
        math.cos(distance_m / r_earth) - math.sin(lat_rad) * math.sin(lat2),
    )
    return math.degrees(lat2), math.degrees(lon2)


def get_acs_b02001_total_for_tract(tract: Dict) -> Optional[int]:
    """
    ACS 2022 B02001_001E (race-universe total) for a tract.

    Used to detect park / non-residential tract pins where full diversity tables are empty.
    Returns None if the request fails; 0 or negative sentinel counts as non-residential for snapping.
    """
    if not CENSUS_API_KEY:
        return None
    try:
        url = f"{CENSUS_BASE_URL}/2022/acs/acs5"
        params = {
            "get": "B02001_001E,NAME",
            "for": f"tract:{tract['tract_fips']}",
            "in": f"state:{tract['state_fips']} county:{tract['county_fips']}",
            "key": CENSUS_API_KEY,
        }
        response = _make_request_with_retry(url, params, timeout=12, max_retries=2)
        if response is None:
            return None
        data = response.json()
        if len(data) < 2:
            return None
        raw = data[1][0]
        if raw is None or raw == "" or str(raw) == "-666666666":
            return 0
        return int(raw)
    except (TypeError, ValueError, IndexError):
        return None


def snap_lat_lon_for_nonempty_race_acs(
    lat: float,
    lon: float,
    *,
    step_m: float = 220.0,
    bearings: Tuple[float, ...] = (0.0, 90.0, 180.0, 270.0, 45.0, 135.0, 225.0, 315.0),
) -> Tuple[float, float, Optional[Dict]]:
    """
    If the tract at (lat, lon) has no ACS race-universe population (B02001 total 0),
    try short offsets so neighborhood geocodes in parks / label points land in a residential tract.

    Returns (lat_out, lon_out, tract_at_out) where tract_at_out is the tract dict for the chosen point.
    """
    tract0 = get_census_tract(lat, lon)
    if not tract0:
        return lat, lon, None
    tot0 = get_acs_b02001_total_for_tract(tract0)
    if tot0 is not None and tot0 > 0:
        return lat, lon, tract0

    for br in bearings:
        lat2, lon2 = _offset_lat_lon_meters(lat, lon, br, step_m)
        t2 = get_census_tract(lat2, lon2)
        if not t2 or t2.get("geoid") == tract0.get("geoid"):
            continue
        tot = get_acs_b02001_total_for_tract(t2)
        if tot is not None and tot > 0:
            return lat2, lon2, t2

    return lat, lon, tract0


def get_diversity_data(lat: float, lon: float, tract: Optional[Dict] = None) -> Optional[Dict]:
    """
    Get race, income, age distributions, and education attainment for Social Fabric / Status Signal.

    Returns:
        {
            "race_counts": Dict[str, int],
            "income_counts": Dict[str, int],
            "age_counts": {
                "youth": int,
                "prime": int,
                "seniors": int,
            },
            "education_attainment": Optional[Dict] with population_25_plus (int), bachelor_pct (float 0-100)
        }
    """
    if tract is None:
        tract = get_census_tract(lat, lon)
    if not tract:
        return None

    # Prefer place-level data for incorporated municipalities
    place_geo = get_place_fips_for_coordinates(lat, lon)
    if place_geo:
        geo_for = f"place:{int(place_geo['place_fips'])}"
        geo_in = f"state:{place_geo['state_fips']}"
        geo_level = "place"
    else:
        geo_for = f"tract:{tract['tract_fips']}"
        geo_in = f"state:{tract['state_fips']} county:{tract['county_fips']}"
        geo_level = "tract"

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
            "for": geo_for,
            "in": geo_in,
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
            "for": geo_for,
            "in": geo_in,
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
            "for": geo_for,
            "in": geo_in,
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

        # ---- Education attainment: B15003 counts -> percentages (for Status Signal) ----
        # B15003_001E = Total pop 25+, 022 = Bachelor's, 023 = Master's, 024 = Professional, 025 = Doctorate
        # bachelor_pct = 100 * (022+023+024+025) / 001, grad_pct = 100 * (023+024+025) / 001
        education_attainment: Optional[Dict] = None
        edu_vars = ["B15003_001E", "B15003_022E", "B15003_023E", "B15003_024E", "B15003_025E"]
        params_edu = {
            "get": ",".join(edu_vars + ["NAME"]),
            "for": geo_for,
            "in": geo_in,
            "key": CENSUS_API_KEY,
        }
        resp_edu = _make_request_with_retry(base_acs5, params_edu, timeout=15, max_retries=3)
        if resp_edu is not None:
            try:
                data_edu = resp_edu.json()
                if isinstance(data_edu, list) and len(data_edu) >= 2:
                    header = data_edu[0]
                    row = data_edu[1]
                    idx = {name: i for i, name in enumerate(header)}
                    err = (None, "", "-666666666", "-999999999", "-888888888", "-555555555")

                    def _safe_int(name: str) -> Optional[int]:
                        if name not in idx:
                            return None
                        raw = row[idx[name]]
                        if raw in err:
                            return None
                        try:
                            return int(float(raw))
                        except (ValueError, TypeError):
                            return None

                    pop_25 = _safe_int("B15003_001E")
                    bach = _safe_int("B15003_022E")
                    master = _safe_int("B15003_023E")
                    prof = _safe_int("B15003_024E")
                    doc = _safe_int("B15003_025E")
                    if pop_25 is not None and pop_25 > 0:
                        bach_plus = (bach or 0) + (master or 0) + (prof or 0) + (doc or 0)
                        grad_count = (master or 0) + (prof or 0) + (doc or 0)
                        bach_pct = min(100.0, round(100.0 * bach_plus / pop_25, 2))
                        grad_pct = min(100.0, round(100.0 * grad_count / pop_25, 2))
                        education_attainment = {
                            "population_25_plus": pop_25,
                            "bachelor_pct": bach_pct,
                            "grad_pct": grad_pct,
                        }
            except Exception:
                pass

        # ---- Self-employed %: B24080 (for Status Signal) ----
        self_employed_pct: Optional[float] = None
        try:
            params_se = {
                "get": "B24080_001E,B24080_003E,B24080_004E",
                "for": geo_for,
                "in": geo_in,
                "key": CENSUS_API_KEY,
            }
            resp_se = _make_request_with_retry(base_acs5, params_se, timeout=15, max_retries=3)
            if resp_se is not None:
                data_se = resp_se.json()
                if isinstance(data_se, list) and len(data_se) >= 2:
                    row = data_se[1]
                    total_emp = row[0] if len(row) > 0 else None
                    se_incorp = row[1] if len(row) > 1 else None
                    se_not_incorp = row[2] if len(row) > 2 else None
                    err = (None, "", "-666666666", "-999999999", "-888888888", "-555555555")
                    if total_emp not in err and total_emp and float(total_emp) > 0:
                        t = float(total_emp)
                        s1 = float(se_incorp) if se_incorp not in err else 0
                        s2 = float(se_not_incorp) if se_not_incorp not in err else 0
                        self_employed_pct = round(100.0 * (s1 + s2) / t, 2)
        except Exception:
            pass

        return {
            "race_counts": race_counts,
            "income_counts": income_counts,
            "age_counts": age_counts,
            "education_attainment": education_attainment,
            "self_employed_pct": self_employed_pct,
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


# ---------------------------------------------------------------------------
# Community safety: population denominator matched to crime query disk
# ---------------------------------------------------------------------------

def _make_post_request_with_retry(
    url: str,
    data: Dict[str, str],
    timeout: int = 30,
    max_retries: int = 3,
):
    """POST with simple retry/backoff (ArcGIS TIGERweb polygon queries)."""
    last_exc = None
    for attempt in range(max_retries):
        try:
            resp = requests.post(url, data=data, timeout=timeout)
            if resp.status_code == 429:
                time.sleep(int(resp.headers.get("Retry-After", 2 ** attempt)))
                continue
            if resp.status_code != 200:
                if resp.status_code >= 500 and attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                return None
            return resp
        except requests.exceptions.RequestException as e:
            last_exc = e
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            continue
    print(f"⚠️  POST request failed after {max_retries} attempts: {last_exc}")
    return None


def _geodesic_circle_polygon_wgs84(lat: float, lon: float, radius_m: float, n: int = 48):
    """Closed lon/lat ring (degrees) approximating a geodesic circle."""
    try:
        from pyproj import Geod
    except ImportError:
        return None
    geod = Geod(ellps="WGS84")
    ring: List[List[float]] = []
    for i in range(n):
        az = 360.0 * i / n
        elon, elat, _ = geod.fwd(lon, lat, az, radius_m)
        ring.append([float(elon), float(elat)])
    if ring:
        ring.append(ring[0])
    return ring


def _esri_polygon_to_shapely(geom: Dict) -> Optional[Any]:
    """Convert Esri JSON geometry dict to a Shapely polygon (WGS84 lon/lat)."""
    try:
        from shapely.geometry import Polygon
    except ImportError:
        return None
    rings = geom.get("rings") if isinstance(geom, dict) else None
    if not rings or not isinstance(rings[0], list):
        return None
    shell = rings[0]
    holes = rings[1:] if len(rings) > 1 else []
    try:
        poly = Polygon(shell, holes)
        if not poly.is_valid:
            poly = poly.buffer(0)
        return poly
    except Exception:
        return None


def _project_geom_to_albers(geom):
    try:
        from pyproj import Transformer
        from shapely.ops import transform as shp_transform
    except ImportError:
        return None
    try:
        fwd = Transformer.from_crs("EPSG:4326", "EPSG:5070", always_xy=True)
        return shp_transform(fwd.transform, geom)
    except Exception:
        return None


@cached(ttl_seconds=CACHE_TTL["census_data"])
def _tigerweb_tracts_intersecting_disk(lat: float, lon: float, radius_m: int) -> Optional[Dict]:
    """
    Query TIGERweb ACS2022 tract layer for features intersecting a geodesic disk.

    Returns raw ArcGIS JSON payload (with features) or None.
    """
    ring = _geodesic_circle_polygon_wgs84(lat, lon, float(radius_m))
    if not ring:
        return None
    geom_obj = {"rings": [ring], "spatialReference": {"wkid": 4326}}
    data = {
        "f": "json",
        "where": "1=1",
        "geometryType": "esriGeometryPolygon",
        "spatialRel": "esriSpatialRelIntersects",
        "inSR": "4326",
        "outSR": "4326",
        "returnGeometry": "true",
        "outFields": "GEOID,STATE,COUNTY,TRACT,AREALAND,AREAWATER",
        "geometry": json.dumps(geom_obj),
        "resultRecordCount": "400",
    }
    resp = _make_post_request_with_retry(TIGERWEB_TRACT_LAYER_URL, data, timeout=35)
    if resp is None:
        return None
    try:
        return resp.json()
    except Exception:
        return None


def _acs_population_batch(state_fips: str, county_fips: str, tract_fips_list: List[str]) -> Dict[str, int]:
    """Return GEOID -> population for tracts in one county (batch ACS)."""
    out: Dict[str, int] = {}
    if not CENSUS_API_KEY or not tract_fips_list:
        return out
    # Census allows comma-separated tract list in `for=tract:...`
    chunk_size = 35
    for i in range(0, len(tract_fips_list), chunk_size):
        chunk = tract_fips_list[i : i + chunk_size]
        tf = ",".join(chunk)
        params = {
            "get": "B01001_001E,NAME",
            "for": f"tract:{tf}",
            "in": f"state:{state_fips} county:{county_fips}",
            "key": CENSUS_API_KEY,
        }
        resp = _make_request_with_retry(f"{CENSUS_BASE_URL}/2022/acs/acs5", params, timeout=20)
        if resp is None:
            continue
        try:
            rows = resp.json()
        except Exception:
            continue
        if not isinstance(rows, list) or len(rows) < 2:
            continue
        header = rows[0]
        try:
            idx_pop = header.index("B01001_001E")
            idx_st = header.index("state")
            idx_co = header.index("county")
            idx_tr = header.index("tract")
        except ValueError:
            continue
        for row in rows[1:]:
            if len(row) <= max(idx_pop, idx_st, idx_co, idx_tr):
                continue
            pop_raw = row[idx_pop]
            if pop_raw in (None, "", "-666666666", "-888888888", "-999999999"):
                continue
            st = str(row[idx_st]).zfill(2)
            co = str(row[idx_co]).zfill(3)
            tr = str(row[idx_tr]).zfill(6)
            geoid = st + co + tr
            try:
                out[geoid] = int(pop_raw)
            except (TypeError, ValueError):
                continue
    return out


def estimate_community_safety_disk_population(
    lat: float,
    lon: float,
    radius_m: int,
    *,
    tract: Optional[Dict] = None,
    density_people_per_sq_mi: Optional[float] = None,
    area_type: Optional[str] = None,
) -> Tuple[int, Dict[str, Any]]:
    """
    Residential population estimate for the **same geodesic disk** used by crime queries.

    Primary method: areal weighting — sum over intersecting census tracts of
    (tract_pop × min(1, area(circle ∩ tract_land) / tract_land_m²)).

    Falls back to the legacy disk formula (density × π r²) when disabled, on error,
    or when the areal estimate is implausibly tiny vs the legacy anchor.

    Env:
        HOMEFIT_COMMUNITY_SAFETY_AREAL_DENOM: default ``true``. Set ``false`` to
        force legacy density×disk only.
    """
    meta: Dict[str, Any] = {
        "population_denominator_radius_m": int(radius_m),
        "population_denominator_method": None,
    }
    dens = float(density_people_per_sq_mi or 0.0)
    if dens <= 0 and tract:
        p0 = get_population(tract)
        la0 = get_land_area(tract) or 2.0
        if p0 and la0 and la0 > 0:
            dens = float(p0) / float(la0)
    if dens <= 0:
        dens = 3000.0
    disk_sq_mi = math.pi * (radius_m / 1609.34) ** 2
    legacy = max(500, int(dens * disk_sq_mi))
    meta["population_denominator_legacy_estimate"] = legacy

    flag = os.getenv("HOMEFIT_COMMUNITY_SAFETY_AREAL_DENOM", "true").lower().strip()
    if flag in ("0", "false", "no", "off"):
        meta["population_denominator_method"] = "density_disk_legacy"
        return legacy, meta

    try:
        from shapely.geometry import Polygon
    except ImportError:
        meta["population_denominator_method"] = "density_disk_legacy"
        meta["population_denominator_skip_reason"] = "shapely_unavailable"
        return legacy, meta

    payload = _tigerweb_tracts_intersecting_disk(lat, lon, int(radius_m))
    if not payload or payload.get("error"):
        meta["population_denominator_method"] = "density_disk_legacy"
        meta["population_denominator_skip_reason"] = "tigerweb_empty_or_error"
        return legacy, meta

    feats = payload.get("features") or []
    if not feats:
        meta["population_denominator_method"] = "density_disk_legacy"
        meta["population_denominator_skip_reason"] = "no_intersecting_tracts"
        return legacy, meta

    if len(feats) > 350:
        meta["population_denominator_method"] = "density_disk_legacy"
        meta["population_denominator_skip_reason"] = "too_many_tract_features"
        return legacy, meta

    ring = _geodesic_circle_polygon_wgs84(lat, lon, float(radius_m), n=48)
    if not ring:
        meta["population_denominator_method"] = "density_disk_legacy"
        meta["population_denominator_skip_reason"] = "circle_build_failed"
        return legacy, meta
    circle_ll = Polygon(ring)
    circle_proj = _project_geom_to_albers(circle_ll)
    if circle_proj is None or circle_proj.is_empty:
        meta["population_denominator_method"] = "density_disk_legacy"
        meta["population_denominator_skip_reason"] = "projection_failed"
        return legacy, meta

    # Unique GEOIDs with overlap fractions
    overlap_by_geoid: Dict[str, float] = {}
    tract_meta_by_geoid: Dict[str, Dict[str, str]] = {}

    for feat in feats:
        if not isinstance(feat, dict):
            continue
        attrs = feat.get("attributes") or {}
        geom = feat.get("geometry")
        if not geom:
            continue
        geoid = str(attrs.get("GEOID") or "").strip()
        if not geoid or len(geoid) < 11:
            continue
        tract_poly_ll = _esri_polygon_to_shapely(geom)
        if tract_poly_ll is None or tract_poly_ll.is_empty:
            continue
        tract_proj = _project_geom_to_albers(tract_poly_ll)
        if tract_proj is None or tract_proj.is_empty:
            continue
        try:
            inter = circle_proj.intersection(tract_proj)
        except Exception:
            continue
        if inter.is_empty:
            continue
        inter_area = float(inter.area)
        aland = float(attrs.get("AREALAND") or 0.0)
        tract_land_m2 = aland if aland > 1000.0 else max(float(tract_proj.area), 1.0)
        frac = inter_area / tract_land_m2 if tract_land_m2 > 0 else 0.0
        frac = max(0.0, min(1.0, frac))
        if frac <= 0:
            continue
        overlap_by_geoid[geoid] = overlap_by_geoid.get(geoid, 0.0) + frac
        if geoid not in tract_meta_by_geoid:
            tract_meta_by_geoid[geoid] = {
                "state_fips": str(attrs.get("STATE", "")).zfill(2),
                "county_fips": str(attrs.get("COUNTY", "")).zfill(3),
                "tract_fips": str(attrs.get("TRACT", "")).zfill(6),
            }

    if not overlap_by_geoid:
        meta["population_denominator_method"] = "density_disk_legacy"
        meta["population_denominator_skip_reason"] = "zero_overlap"
        return legacy, meta

    # Batch ACS by county
    from collections import defaultdict

    by_county: Dict[Tuple[str, str], List[str]] = defaultdict(list)
    for gid, frac in overlap_by_geoid.items():
        if frac <= 0:
            continue
        tm = tract_meta_by_geoid.get(gid) or {}
        st = tm.get("state_fips") or gid[:2]
        co = tm.get("county_fips") or gid[2:5]
        tr = tm.get("tract_fips") or gid[5:11]
        if not (st and co and tr):
            continue
        by_county[(st, co)].append(tr)

    pop_by_geoid: Dict[str, int] = {}
    for (st, co), tr_list in by_county.items():
        uniq = sorted(set(tr_list))
        batch = _acs_population_batch(st, co, uniq)
        pop_by_geoid.update(batch)

    weighted = 0.0
    missing = 0
    for gid, frac in overlap_by_geoid.items():
        pop = pop_by_geoid.get(gid)
        if pop is None:
            tm = tract_meta_by_geoid.get(gid)
            if tm:
                td = {
                    "state_fips": tm["state_fips"],
                    "county_fips": tm["county_fips"],
                    "tract_fips": tm["tract_fips"],
                    "geoid": gid,
                    "name": "",
                    "basename": "",
                }
                pop = get_population(td)
        if pop is None or pop <= 0:
            missing += 1
            continue
        weighted += float(pop) * float(frac)

    if weighted <= 0:
        meta["population_denominator_method"] = "density_disk_legacy"
        meta["population_denominator_skip_reason"] = "acs_population_unavailable"
        meta["population_denominator_missing_tracts"] = missing
        return legacy, meta

    areal_int = max(1, int(round(weighted)))
    # Anti-fragment: if areal is tiny vs legacy in urban-ish types, blend up slightly
    at = (area_type or "").lower()
    urbanish = "urban" in at or "suburban" in at
    if urbanish and areal_int < 800 and legacy > areal_int * 3:
        blended = int(round(max(areal_int, legacy * 0.35)))
        meta["population_denominator_fragment_blend"] = True
        meta["population_denominator_areal_raw"] = areal_int
        areal_int = min(blended, legacy)

    final_pop = max(500, areal_int)
    meta["population_denominator_method"] = "areal_acs_tracts_in_disk"
    meta["population_denominator_tracts_overlapping"] = len(overlap_by_geoid)
    meta["population_denominator_weighted_estimate"] = int(round(weighted))
    meta["population_denominator_missing_tract_pops"] = missing
    return final_pop, meta