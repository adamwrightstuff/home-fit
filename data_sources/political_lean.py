"""
Political lean data source: precinct-level 2020/2024 presidential election results.

Lookup: given lat/lon + state, aggregate precincts within radius, return lean score.
Data files: data/election/<state_lower>_precincts.json — built by scripts/collectors/build_election_lookup.py

Lean = (dem - rep) / (dem + rep), range [-1, +1]. Positive = Democratic, negative = Republican.
"""

from __future__ import annotations

import json
import math
import os
from typing import Dict, List, Optional, Tuple

from logging_config import get_logger

logger = get_logger(__name__)

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "election")

# Cache: state_abbr.lower() → list of precinct dicts
_precinct_cache: Dict[str, List[dict]] = {}

# Full state name → 2-letter abbreviation (for geocoder output normalization)
_STATE_NAME_TO_ABBR: Dict[str, str] = {
    'alabama': 'AL', 'alaska': 'AK', 'arizona': 'AZ', 'arkansas': 'AR',
    'california': 'CA', 'colorado': 'CO', 'connecticut': 'CT', 'delaware': 'DE',
    'florida': 'FL', 'georgia': 'GA', 'hawaii': 'HI', 'idaho': 'ID',
    'illinois': 'IL', 'indiana': 'IN', 'iowa': 'IA', 'kansas': 'KS',
    'kentucky': 'KY', 'louisiana': 'LA', 'maine': 'ME', 'maryland': 'MD',
    'massachusetts': 'MA', 'michigan': 'MI', 'minnesota': 'MN', 'mississippi': 'MS',
    'missouri': 'MO', 'montana': 'MT', 'nebraska': 'NE', 'nevada': 'NV',
    'new hampshire': 'NH', 'new jersey': 'NJ', 'new mexico': 'NM', 'new york': 'NY',
    'north carolina': 'NC', 'north dakota': 'ND', 'ohio': 'OH', 'oklahoma': 'OK',
    'oregon': 'OR', 'pennsylvania': 'PA', 'rhode island': 'RI', 'south carolina': 'SC',
    'south dakota': 'SD', 'tennessee': 'TN', 'texas': 'TX', 'utah': 'UT',
    'vermont': 'VT', 'virginia': 'VA', 'washington': 'WA', 'west virginia': 'WV',
    'wisconsin': 'WI', 'wyoming': 'WY',
}

# Approx degrees per mile at mid-latitudes (used for bbox pre-filter)
_DEG_PER_MILE_LAT = 1.0 / 69.0
_DEG_PER_MILE_LON = 1.0 / 54.6  # at ~40° lat, conservative enough for NY/CA/NJ/CT


def _haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 3958.8
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return r * 2 * math.asin(math.sqrt(a))


def _load_state(state_abbr: str) -> List[dict]:
    # Normalize full state names ("California" → "CA") before cache lookup
    _s = state_abbr.strip()
    if len(_s) > 2:
        _s = _STATE_NAME_TO_ABBR.get(_s.lower(), _s)
    key = _s.lower()
    if key in _precinct_cache:
        return _precinct_cache[key]
    path = os.path.join(_DATA_DIR, f"{key}_precincts.json")
    if not os.path.isfile(path):
        logger.debug("No election data file for state %s at %s", state_abbr, path)
        _precinct_cache[key] = []
        return []
    try:
        with open(path, "r") as f:
            data = json.load(f)
        _precinct_cache[key] = data if isinstance(data, list) else []
        logger.info("Loaded %d precincts for %s", len(_precinct_cache[key]), state_abbr)
    except Exception as e:
        logger.warning("Failed to load election data for %s: %s", state_abbr, e)
        _precinct_cache[key] = []
    return _precinct_cache[key]


def lookup_political_lean(
    lat: float,
    lon: float,
    state_abbr: str,
    radius_miles: float = 1.0,
) -> Optional[Dict]:
    """
    Aggregate precinct results within radius_miles of lat/lon.

    Returns dict with keys: lean_2024, lean_2020, trend, dem_2024, rep_2024,
    dem_2020, rep_2020, precinct_count. Returns None if no data.
    """
    precincts = _load_state(state_abbr)
    if not precincts:
        return None

    # Bbox pre-filter to avoid O(n) haversine on every precinct
    lat_pad = radius_miles * _DEG_PER_MILE_LAT
    lon_pad = radius_miles * _DEG_PER_MILE_LON
    lat_min, lat_max = lat - lat_pad, lat + lat_pad
    lon_min, lon_max = lon - lon_pad, lon + lon_pad

    nearby = []
    for p in precincts:
        plat, plon = p["lat"], p["lon"]
        if not (lat_min <= plat <= lat_max and lon_min <= plon <= lon_max):
            continue
        if _haversine_miles(lat, lon, plat, plon) <= radius_miles:
            nearby.append(p)

    # Prefer granular data: use precinct/municipality-matched records when available;
    # fall back to county-matched records only if nothing better exists within radius.
    granular = [p for p in nearby if p.get("match_tier") not in ("county", "none")]
    pool = granular if granular else nearby

    dem_24 = rep_24 = dem_20 = rep_20 = 0
    count = 0
    for p in pool:
            dem_24 += p.get("dem_2024", 0)
            rep_24 += p.get("rep_2024", 0)
            dem_20 += p.get("dem_2020", 0)
            rep_20 += p.get("rep_2020", 0)
            count += 1

    if count == 0:
        return None

    total_24 = dem_24 + rep_24
    total_20 = dem_20 + rep_20
    lean_2024 = (dem_24 - rep_24) / total_24 if total_24 > 0 else 0.0
    lean_2020 = (dem_20 - rep_20) / total_20 if total_20 > 0 else 0.0

    return {
        "lean_2024": round(lean_2024, 4),
        "lean_2020": round(lean_2020, 4),
        "trend": round(lean_2024 - lean_2020, 4),
        "dem_2024": dem_24,
        "rep_2024": rep_24,
        "dem_2020": dem_20,
        "rep_2020": rep_20,
        "precinct_count": count,
    }


def lean_label(lean: float) -> str:
    if lean > 0.30:
        return "strong_d"
    if lean > 0.10:
        return "lean_d"
    if lean >= -0.10:
        return "competitive"
    if lean >= -0.30:
        return "lean_r"
    return "strong_r"
