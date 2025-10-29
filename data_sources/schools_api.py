"""
SchoolDigger API Client
Queries school ratings and data
"""

import os
import time
import requests
from typing import List, Optional, Dict
from .cache import cached, CACHE_TTL

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
    city: Optional[str] = None
) -> Optional[List[Dict]]:
    """
    Query SchoolDigger API for schools.
    
    Results are cached for 30 days to preserve API quota.
    
    NOTE: If data is obfuscated (generic IDs), it will NOT be cached
    to allow retry with valid rate limits.

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
    
    params = {
        "appID": app_id,
        "appKey": app_key,
        "st": state,  # State is REQUIRED
        "perPage": 50
    }

    # Try ZIP + State (most specific, includes required 'st')
    if zip_code:
        params_zip = {**params, "zip": zip_code}
        schools = _fetch_schools(params_zip)
        if schools:
            return schools

    # Try City + State (includes required 'st')
    if city:
        params_city = {**params, "city": city}
        # Also try with 'q' parameter for name/city search
        params_city_q = {**params, "q": city}
        schools = _fetch_schools(params_city)
        if not schools:
            schools = _fetch_schools(params_city_q)
        if schools:
            return schools
    
    # ZIP only without state will be obfuscated, but try if no other option
    if zip_code and not state:
        print("⚠️  Warning: ZIP-only query without state may return obfuscated data")
        params_zip_only = {**params, "zip": zip_code}
        schools = _fetch_schools(params_zip_only)
        if schools:
            return schools

    return None


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
