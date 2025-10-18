"""
SchoolDigger API Client
Queries school ratings and data
"""

import os
import requests
from typing import List, Optional, Dict

SCHOOLDIGGER_BASE = "https://api.schooldigger.com/v2.0"


def get_schools(
    zip_code: Optional[str] = None,
    state: Optional[str] = None,
    city: Optional[str] = None
) -> Optional[List[Dict]]:
    """
    Query SchoolDigger API for schools.

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
        state = state.strip().upper()
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
    try:
        url = f"{SCHOOLDIGGER_BASE}/schools"
        resp = requests.get(url, params=params, timeout=10)

        if resp.status_code == 200:
            data = resp.json()
            return data.get("schoolList", [])
        return None

    except Exception as e:
        print(f"SchoolDigger request failed: {e}")
        return None
