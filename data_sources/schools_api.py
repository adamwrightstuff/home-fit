"""
SchoolDigger API Client
Queries school ratings and data
"""

import os
import time
import requests
import math
from typing import List, Optional, Dict
from .cache import cached, CACHE_TTL
from .utils import haversine_distance
from .radius_profiles import get_radius_profile

SCHOOLDIGGER_BASE = "https://api.schooldigger.com/v2.1"

# Track API usage for quota management
_request_count = 0
_last_request_time = 0
QUOTA_WARNING_THRESHOLD = 15  # Warn before 20/day limit
RATE_LIMIT_SECONDS = 65  # 1 request per minute (65s to be safe)

# State name to abbreviation mapping
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
}


@cached(ttl_seconds=CACHE_TTL['school_data'])
def get_schools(
    zip_code: Optional[str] = None,
    state: Optional[str] = None,
    city: Optional[str] = None,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    area_type: Optional[str] = None
) -> Optional[List[Dict]]:
    """
    Query SchoolDigger API for schools using bulletproof approach.
    
    Priority order (most accurate first):
    1. District lookup by coordinates (most accurate - only schools in actual district)
    2. Coordinate-based query with conservative radius + distance filtering
    3. ZIP + State (fallback)
    4. City + State (last resort)
    
    Results are cached for 30 days to preserve API quota.
    
    NOTE: If data is obfuscated (generic IDs), it will NOT be cached
    to allow retry with valid rate limits.

    Args:
        zip_code, state, city: Traditional location identifiers
        lat, lon: Coordinates for district/coordinate-based queries
        area_type: For determining conservative search radius (urban_core, suburban, etc.)

    Returns:
        List of school dicts or None if API fails
    """
    app_id = os.getenv("SCHOOLDIGGER_APPID")
    app_key = os.getenv("SCHOOLDIGGER_APPKEY")

    if not app_id or not app_key:
        print("⚠️  SchoolDigger credentials missing")
        return None

    # Normalize inputs
    if zip_code:
        zip_code = zip_code.split("-")[0].strip()
    if state:
        state = state.strip()
        # Convert full state name to abbreviation if needed
        state_lower = state.lower()
        if state_lower in STATE_ABBREVIATIONS:
            state = STATE_ABBREVIATIONS[state_lower]
        state = state.upper()
    if city:
        city = city.strip()

    # CRITICAL: 'st' (state) parameter is REQUIRED for SchoolDigger API
    # Without it, or if rate limits exceeded, data is obfuscated (generic IDs)
    if not state:
        print("⚠️  State parameter required for SchoolDigger API - data may be obfuscated")
        return None
    
    base_params = {
        "appID": app_id,
        "appKey": app_key,
        "st": state,  # State is REQUIRED
        "perPage": 50
    }

    # PRIORITY 1: District lookup by coordinates (most accurate - only schools in actual district)
    if lat is not None and lon is not None:
        print(f"🎯 Attempting district lookup for coordinates ({lat}, {lon})...")
        district_ids = _find_districts_by_coordinates(lat, lon, state, base_params)
        if district_ids:
            print(f"✅ Found {len(district_ids)} district(s), querying schools by district...")
            schools = _fetch_schools_by_districts(district_ids, base_params, lat, lon)
            if schools:
                print(f"✅ District-based query returned {len(schools)} schools")
                return schools
            else:
                print("⚠️  District lookup found districts but no schools returned")

    # PRIORITY 2: Coordinate-based query with conservative radius + distance filtering
    if lat is not None and lon is not None:
        # Get conservative radius based on area type
        radius_profile = get_radius_profile("quality_education", area_type, None)
        search_radius_miles = radius_profile.get("search_radius_miles", 2.0)  # Default 2 miles
        
        print(f"📍 Attempting coordinate-based query (radius: {search_radius_miles} miles)...")
        schools = _fetch_schools_by_coordinates(lat, lon, search_radius_miles, base_params)
        if schools:
            # Filter by distance to ensure we only get schools that serve the neighborhood
            schools = _filter_schools_by_distance(schools, lat, lon, search_radius_miles)
            if schools:
                print(f"✅ Coordinate-based query returned {len(schools)} schools after distance filtering")
                return schools

    # PRIORITY 3: ZIP + State (fallback)
    if zip_code:
        print(f"📮 Attempting ZIP-based query ({zip_code})...")
        params_zip = {**base_params, "zip": zip_code}
        schools = _fetch_schools(params_zip)
        if schools:
            # If we have coordinates, filter by distance even for ZIP results
            if lat is not None and lon is not None:
                radius_profile = get_radius_profile("quality_education", area_type, None)
                search_radius_miles = radius_profile.get("search_radius_miles", 2.0)
                schools = _filter_schools_by_distance(schools, lat, lon, search_radius_miles)
            if schools:
                print(f"✅ ZIP-based query returned {len(schools)} schools")
                return schools

    # PRIORITY 4: City + State (last resort)
    if city:
        print(f"🏙️  Attempting city-based query ({city})...")
        params_city = {**base_params, "city": city}
        schools = _fetch_schools(params_city)
        if not schools:
            params_city_q = {**base_params, "q": city}
            schools = _fetch_schools(params_city_q)
        if schools:
            # If we have coordinates, filter by distance even for city results
            if lat is not None and lon is not None:
                radius_profile = get_radius_profile("quality_education", area_type, None)
                search_radius_miles = radius_profile.get("search_radius_miles", 2.0)
                schools = _filter_schools_by_distance(schools, lat, lon, search_radius_miles)
            if schools:
                print(f"✅ City-based query returned {len(schools)} schools")
                return schools

    print("⚠️  No schools found with any query method")
    return None


def _find_districts_by_coordinates(
    lat: float, lon: float, state: str, base_params: Dict
) -> List[str]:
    """
    Find school districts near the given coordinates.
    
    Returns:
        List of district IDs (as strings)
    """
    try:
        # Use districts endpoint with coordinate search
        # Note: v1 endpoint for districts, v2.1 for schools
        url = "https://api.schooldigger.com/v1/districts"
        params = {
            **base_params,
            "nearLatitude": lat,
            "nearLongitude": lon,
            "distanceMiles": 2.0,  # Conservative radius for district lookup
        }
        
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            districts = data.get("districtList", [])
            district_ids = [str(d.get("districtID", "")) for d in districts if d.get("districtID")]
            if district_ids:
                print(f"   Found districts: {district_ids}")
            return district_ids
    except Exception as e:
        print(f"   District lookup failed: {e}")
    return []


def _fetch_schools_by_districts(
    district_ids: List[str], base_params: Dict, lat: float, lon: float
) -> Optional[List[Dict]]:
    """
    Fetch schools by district IDs. If multiple districts, query each and combine.
    """
    all_schools = []
    for district_id in district_ids:
        params = {
            **base_params,
            "districtID": district_id,
        }
        schools = _fetch_schools(params)
        if schools:
            all_schools.extend(schools)
    
    if all_schools:
        # Remove duplicates (by schoolID if available, or by name)
        seen = set()
        unique_schools = []
        for school in all_schools:
            school_id = school.get("schoolID")
            school_name = school.get("schoolName", "")
            key = school_id if school_id else school_name
            if key and key not in seen:
                seen.add(key)
                unique_schools.append(school)
        return unique_schools
    
    return None


def _fetch_schools_by_coordinates(
    lat: float, lon: float, radius_miles: float, base_params: Dict
) -> Optional[List[Dict]]:
    """
    Fetch schools near coordinates using distance-based query.
    """
    params = {
        **base_params,
        "nearLatitude": lat,
        "nearLongitude": lon,
        "distanceMiles": radius_miles,
    }
    return _fetch_schools(params)


def _filter_schools_by_distance(
    schools: List[Dict], lat: float, lon: float, max_radius_miles: float
) -> List[Dict]:
    """
    Filter schools to only include those within max_radius_miles of the target coordinates.
    This ensures we don't catch schools from unrelated neighborhoods.
    """
    if not schools:
        return []
    
    max_radius_m = max_radius_miles * 1609.34  # Convert miles to meters
    
    filtered = []
    for school in schools:
        school_lat = school.get("latitude")
        school_lon = school.get("longitude")
        
        # If school doesn't have coordinates, include it (better to include than exclude)
        if school_lat is None or school_lon is None:
            filtered.append(school)
            continue
        
        distance_m = haversine_distance(lat, lon, school_lat, school_lon)
        distance_miles = distance_m / 1609.34
        
        if distance_m <= max_radius_m:
            filtered.append(school)
        else:
            print(f"   ⚠️  Filtered out school '{school.get('schoolName', 'Unknown')}' "
                  f"(distance: {distance_miles:.2f} miles, max: {max_radius_miles:.2f} miles)")
    
    if len(filtered) < len(schools):
        print(f"   📏 Distance filtering: {len(schools)} -> {len(filtered)} schools "
              f"(removed {len(schools) - len(filtered)} schools beyond {max_radius_miles:.2f} miles)")
    
    return filtered


def _fetch_schools(params: Dict) -> Optional[List[Dict]]:
    """
    Helper to fetch schools with error handling.
    
    NOTE: SchoolDigger free plan limits:
    - 20 requests per day
    - 1 request per minute
    Exceeding limits causes data obfuscation (generic IDs, no school names)
    """
    global _request_count, _last_request_time
    
    # Rate limiting: respect 1 request per minute limit
    current_time = time.time()
    time_since_last = current_time - _last_request_time
    if _last_request_time > 0 and time_since_last < RATE_LIMIT_SECONDS:
        wait_time = RATE_LIMIT_SECONDS - time_since_last
        print(f"⏳ Rate limiting: waiting {wait_time:.1f}s (1 req/min limit)...")
        time.sleep(wait_time)
    
    _request_count += 1
    _last_request_time = time.time()
    
    if _request_count >= QUOTA_WARNING_THRESHOLD:
        print(f"⚠️  SchoolDigger quota warning: {_request_count} API requests this session")
        print(f"⚠️  Free plan limit: 20/day, 1/min. Exceeding causes obfuscated data (generic IDs).")
    
    # Verify 'st' parameter is included (REQUIRED)
    if 'st' not in params or not params.get('st'):
        print(f"⚠️  ERROR: 'st' (state) parameter missing - request will fail or return obfuscated data")
        return None
    
    try:
        url = f"{SCHOOLDIGGER_BASE}/schools"
        resp = requests.get(url, params=params, timeout=10)

        if resp.status_code == 200:
            data = resp.json()
            schools = data.get("schoolList", [])
            
            # Check if data is obfuscated (generic IDs indicate rate limit exceeded)
            if schools and len(schools) > 0:
                sample = schools[0]
                sample_name = sample.get('schoolName', '')
                
                # DEBUG: Log what we're getting
                print(f"📊 SchoolDigger API Response:")
                print(f"   - Total schools: {len(schools)}")
                print(f"   - Sample school: {sample_name}")
                
                # Check for obfuscation (generic School #ID format)
                is_obfuscated = sample_name and sample_name.startswith("School #")
                if is_obfuscated:
                    print(f"   ⚠️  WARNING: Data appears obfuscated (generic IDs)")
                    print(f"   ⚠️  Possible causes: Rate limit exceeded (free plan: 20/day, 1/min)")
                    print(f"   ⚠️  Or: Missing required 'st' (state) parameter")
                    print(f"   ⚠️  Solution: Wait 1+ minute between requests or upgrade plan")
                    print(f"   ⚠️  NOTE: Obfuscated data will NOT be cached - will retry next call")
                    # Don't cache obfuscated data - return None to allow retry
                    # The @cached decorator won't cache None results
                    return None
                else:
                    print(f"   ✅ School names appear valid (not obfuscated)")
                
                # Log rank info
                if 'rankHistory' in sample:
                    rank_history = sample.get('rankHistory')
                    if rank_history is not None and len(rank_history) > 0:
                        rank_stars = rank_history[0].get('rankStars', 'N/A')
                        print(f"   - Sample rating: {rank_stars} stars")
                    print(f"   - School level: {sample.get('schoolLevel', 'Unknown')}")
            
            return schools
        else:
            print(f"⚠️  SchoolDigger API returned status {resp.status_code}")
            print(f"   Response: {resp.text[:500]}")
        return None

    except Exception as e:
        print(f"SchoolDigger request failed: {e}")
        import traceback
        traceback.print_exc()
        return None
