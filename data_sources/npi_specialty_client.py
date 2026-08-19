"""
NPI specialty lookup using NPPES registry API.

Provides specialty_count(city, state) for healthcare scoring when OSM
specialty tags are unavailable. Results are cached in
data/npi_specialty_by_city_state.json to avoid repeated API calls.

The NPPES (National Plan and Provider Enumeration System) registry is a free
federal dataset from CMS covering every licensed US provider by specialty.
API docs: https://npiregistry.cms.hhs.gov/search
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Dict, Optional

import requests

from logging_config import get_logger

logger = get_logger(__name__)

_CACHE_PATH = Path(__file__).parent.parent / "data" / "npi_specialty_by_city_state.json"
_NPPES_API = "https://npiregistry.cms.hhs.gov/api/"

# Clinical specialties to probe for — each maps to one or more NPPES taxonomy_description terms.
# We query NPPES for each term and count presence/absence to get a specialty count.
_SPECIALTY_PROBES: Dict[str, list[str]] = {
    "cardiology":       ["Cardiovascular Disease"],
    "neurology":        ["Neurology"],
    "oncology":         ["Oncology", "Hematology"],
    "orthopedics":      ["Orthopedic Surgery", "Orthopaedic Surgery"],
    "gastroenterology": ["Gastroenterology"],
    "urology":          ["Urology"],
    "pulmonology":      ["Pulmonary Disease"],
    "endocrinology":    ["Endocrinology, Diabetes"],
    "rheumatology":     ["Rheumatology"],
    "ophthalmology":    ["Ophthalmology"],
    "dermatology":      ["Dermatology"],
    "psychiatry":       ["Psychiatry & Neurology", "Psychiatry"],
    "ob_gyn":           ["Obstetrics & Gynecology"],
    "nephrology":       ["Nephrology"],
    "neurosurgery":     ["Neurosurgery"],
}

_MAX_SPECIALTIES = len(_SPECIALTY_PROBES)  # 15

_cache: Optional[Dict[str, int]] = None


def _load_cache() -> Dict[str, int]:
    global _cache
    if _cache is None:
        if _CACHE_PATH.exists():
            try:
                _cache = json.loads(_CACHE_PATH.read_text())
            except Exception:
                _cache = {}
        else:
            _cache = {}
    return _cache


def _save_cache() -> None:
    if _cache is not None:
        _CACHE_PATH.write_text(json.dumps(_cache, indent=2, sort_keys=True))


def _probe_specialty(city: str, state: str, taxonomy_description: str, timeout: float = 10.0) -> bool:
    """Return True if any NPI-1 provider with this taxonomy exists in city/state."""
    try:
        resp = requests.get(
            _NPPES_API,
            params={
                "version": "2.1",
                "enumeration_type": "NPI-1",
                "city": city,
                "state": state,
                "taxonomy_description": taxonomy_description,
                "limit": 5,
                "skip": 0,
            },
            timeout=timeout,
        )
        data = resp.json()
        return bool(data.get("results"))
    except Exception:
        return False


def _fetch_specialty_count(city: str, state: str) -> int:
    """Query NPPES for each target specialty; return count of those present."""
    count = 0
    for _label, terms in _SPECIALTY_PROBES.items():
        found = False
        for term in terms:
            if _probe_specialty(city, state, term):
                found = True
                break
            time.sleep(0.05)  # gentle rate limit
        if found:
            count += 1
    return count


def _nppes_city_from_latlon(lat: float, lon: float, state: str) -> Optional[str]:
    """Resolve NPPES-queryable city from coordinates for NYC-area locations."""
    if state != "NY":
        return None
    if not (40.4 < lat < 41.1 and -74.3 < lon < -73.6):
        return None  # Outside NYC metro bounding box
    # Manhattan: north of GW Bridge to Battery Park, east of Hudson
    if lon > -74.02 and lon < -73.93 and lat > 40.70:
        return "New York"
    # Staten Island: west of Narrows
    if lon < -74.04 and lat < 40.67:
        return "Staten Island"
    # Brooklyn: south of Queens, west of Belt Pkwy (rough)
    if lat < 40.74 and lon > -74.06 and lon < -73.82:
        return "Brooklyn"
    # Bronx: north of Manhattan, east of Harlem River, south of Westchester
    if 40.78 < lat < 40.92 and lon > -73.94 and lon < -73.75:
        return "Bronx"
    # Queens: remaining NYC area
    if lon > -73.96 and lon < -73.70:
        return None  # Return None so caller uses neighborhood name (often correct in Queens)
    return None


def _nppes_city_from_latlon_ca(lat: float, lon: float) -> Optional[str]:
    """Resolve NPPES city for California metro area locations.

    SF city neighborhoods → "San Francisco" (neighborhoods aren't valid NPPES city names).
    All other Bay Area and LA places: return None so the geocoded city name from the
    caller is used directly (Oakland, Berkeley, San Jose, Alameda etc. are valid NPPES cities).
    LA city neighborhoods → "Los Angeles".
    """
    # SF city proper (lat 37.70-37.83, lon -122.52 to -122.35) → "San Francisco"
    if 37.70 < lat < 37.83 and -122.52 < lon < -122.35:
        return "San Francisco"
    # Bay Area outside SF city: suburbs/cities have their own NPPES city names; return None
    # so get_specialty_count falls back to the geocoded city param (Alameda, Oakland, etc.)
    if -123.0 < lon < -121.5 and 37.0 < lat < 38.5:
        return None
    # LA city neighborhoods → "Los Angeles"
    if 33.90 < lat < 34.12 and -118.45 < lon < -118.10:
        return "Los Angeles"
    # LA metro outside inner city: suburbs have their own NPPES city names
    if -119.0 < lon < -117.0 and 33.0 < lat < 34.5:
        return None
    return None


def get_specialty_count(city: str, state: str, lat: Optional[float] = None, lon: Optional[float] = None) -> int:
    """
    Return count of distinct clinical specialties available in a city.

    When lat/lon is provided and the location is in NYC, resolves the correct
    NPPES city (borough) from coordinates to avoid neighborhood-name mismatches.

    Uses cached data when available; queries NPPES on cache miss and writes
    the result back. Returns 0 on any error.
    """
    if not state:
        return 0

    state_norm = (state or "").strip().upper()

    # Resolve NPPES city: lat/lon borough/metro resolution takes precedence over
    # the passed city/state (which may be a neighborhood name or have a wrong state).
    nppes_city: Optional[str] = None
    resolved_state = state_norm
    if lat is not None and lon is not None:
        # Try NYC borough resolution first — it overrides the caller's state guess
        nyc_city = _nppes_city_from_latlon(lat, lon, "NY")
        if nyc_city:
            nppes_city = nyc_city
            resolved_state = "NY"
        else:
            ca_city = _nppes_city_from_latlon_ca(lat, lon)
            if ca_city:
                nppes_city = ca_city
                resolved_state = "CA"
    if not nppes_city:
        nppes_city = (city or "").strip().title() if city else None
    if not nppes_city:
        return 0

    key = f"{nppes_city},{resolved_state}"
    cache = _load_cache()
    if key in cache:
        return cache[key]

    logger.info("NPI specialty probe: city=%s state=%s", nppes_city, state_norm)
    count = _fetch_specialty_count(nppes_city, state_norm)
    cache[key] = count
    _save_cache()
    logger.info("NPI specialty probe result: %s → %d specialties", key, count)
    return count


def state_from_latlon(lat: float, lon: float) -> str:
    """Rough state inference from coordinates for our three metro areas."""
    # CA must come first — CA longitudes (~-118 to -122) satisfy the NJ lon test (< -74.05)
    # Bay Area: CA
    if -123.0 < lon < -121.5 and 37.0 < lat < 38.5:
        return "CA"
    # LA: CA
    if -119.0 < lon < -117.0 and 33.0 < lat < 34.5:
        return "CA"
    # CT: east of ~-73.65 and north of 40.9 (tighter than -73.7 to avoid misclassifying Rye NY)
    if lon > -73.65 and lat > 40.9:
        return "CT"
    # Staten Island: western/southern SI (lon < -74.04) falls in the NJ lon range but is NY;
    # our NJ catalog places (Hoboken, Montclair, etc.) are all at lat > 40.65 or lon > -74.03
    if -74.27 < lon < -74.04 and 40.48 < lat < 40.65:
        return "NY"
    # NJ: west of -74.05 and south of 41.4 (tighter than -74.0 to avoid misclassifying Bay Ridge/Brooklyn)
    if lon < -74.05 and lat < 41.4:
        return "NJ"
    return "NY"


def nppes_city_from_catalog(name: str, county_borough: str, state_abbr: str) -> str:
    """Map a catalog place name to the NPPES-queryable city name."""
    cb = (county_borough or "").strip()
    if state_abbr == "NY":
        if cb == "Manhattan":
            return "New York"
        if cb in ("Brooklyn", "Bronx", "Staten Island"):
            return cb
        if cb == "Queens":
            # Queens neighborhoods often appear under their own name in NPPES
            return name
        # Westchester, Nassau, Suffolk, NJ counties, etc. — place name is the city
        return name
    if state_abbr == "CA":
        # For CA, county_borough is usually "Los Angeles", "San Francisco", etc.
        # Suburb cities (Burbank, Glendale, Pasadena, Palo Alto) are their own NPPES city.
        # Inner neighborhoods use county_borough (the major city) as NPPES city.
        inner_la_boroughs = {"Los Angeles"}
        inner_sf_boroughs = {"San Francisco"}
        if cb in inner_la_boroughs or cb in inner_sf_boroughs:
            return cb  # "Los Angeles" or "San Francisco"
        return name  # Suburb cities use their own name
    # NJ / CT — place name is the city
    return name
