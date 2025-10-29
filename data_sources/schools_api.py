"""
SchoolDigger API Client
Queries school ratings and data
"""

import os
import requests
from typing import List, Optional, Dict
from .cache import cached, CACHE_TTL

SCHOOLDIGGER_BASE = "https://api.schooldigger.com/v2.1"

# Track API usage for quota management
_request_count = 0
QUOTA_WARNING_THRESHOLD = 50

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

    params = {
        "appID": app_id,
        "appKey": app_key,
        "perPage": 50
    }

    # Try ZIP + State first
    if zip_code and state:
        params_zip = {**params, "zip": zip_code, "st": state}
        schools = _fetch_schools(params_zip)
        if schools:
            return schools

    # Try City + State
    if city and state:
        params_city = {**params, "city": city, "st": state}
        schools = _fetch_schools(params_city)
        if schools:
            return schools

    # Try ZIP only
    if zip_code:
        params_zip_only = {**params, "zip": zip_code}
        schools = _fetch_schools(params_zip_only)
        if schools:
            return schools

    return None


def _fetch_schools(params: Dict) -> Optional[List[Dict]]:
    """Helper to fetch schools with error handling."""
    global _request_count
    _request_count += 1
    
    if _request_count >= QUOTA_WARNING_THRESHOLD:
        print(f"⚠️  SchoolDigger quota warning: {_request_count} API requests this session")
    
    try:
        url = f"{SCHOOLDIGGER_BASE}/schools"
        resp = requests.get(url, params=params, timeout=10)

        if resp.status_code == 200:
            data = resp.json()
            
            # DEBUG: Log what we're getting
            print(f"📊 SchoolDigger API Response:")
            print(f"   - Total schools: {len(data.get('schoolList', []))}")
            
            # Check a sample school if available
            schools = data.get("schoolList", [])
            if schools and len(schools) > 0:
                sample = schools[0]
                print(f"   - Sample school: {sample.get('schoolName', 'Unknown')}")
                print(f"   - Has rankHistory: {'rankHistory' in sample}")
                if 'rankHistory' in sample:
                    rank_history = sample.get('rankHistory')
                    if rank_history is not None:
                        print(f"   - rankHistory length: {len(rank_history)}")
                        if len(rank_history) > 0:
                            print(f"   - First rank entry: {rank_history[0]}")
                    else:
                        print(f"   - rankHistory is None")
                print(f"   - School level: {sample.get('schoolLevel', 'Unknown')}")
                print(f"   - Available keys: {', '.join(sample.keys())}")
            
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
