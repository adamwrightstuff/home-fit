"""
Crime data for Community Safety pillar.

Data sources (in priority order for a given location):
  1. NYC Open Data — NYPD Complaint Data (Socrata, free, no key)
  2. LA Open Data  — LAPD Crime Data (Socrata, free, no key)
  3. FBI Crime Data Explorer (CDE) API — all other places (free, requires FBI_CRIME_API_KEY)

Returns per-1k-population violent and property crime rates plus a year-over-year
trend percentage.  All rates are incident-based; population is estimated from
the tract population supplied by the caller (from Census pre-pillar data).

Violent crime:  homicide, rape, robbery, aggravated assault
Property crime: burglary, motor-vehicle theft, larceny-theft (excl. shoplifting-only
                jurisdictions where this inflates suburban numbers)

Caching: 30 days (same as school_data) — crime statistics change slowly and API
         calls are expensive/quota-limited for the FBI endpoint.
"""

from __future__ import annotations

import datetime
import os
import time
from typing import Dict, Optional, Tuple

import requests

from data_sources.cache import cached, CACHE_TTL
from logging_config import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Socrata endpoints (no API key needed for <1 000 rows/request at this rate)
_NYC_SOCRATA = "https://data.cityofnewyork.us/resource/5uac-w243.json"
# Legacy LAPD dataset (SRS format) — updated through Dec 2024.
# The newer NIBRS dataset (y8y3-fqfu) lacks lat/lon fields; use legacy for coordinate queries.
_LA_SOCRATA = "https://data.lacity.org/resource/2nrs-mtv8.json"
_LA_DATA_MAX_DATE = "2024-12-31"  # Legacy dataset last update

# FBI Crime Data Explorer
_FBI_CDE_BASE = "https://api.usa.gov/crime/fbi/cde"

# Geographic bounding boxes for open-data routing.
# If coordinates fall within a box, use that metro's Socrata endpoint instead
# of the FBI CDE API. This handles sub-neighborhoods (Gowanus, Chinatown, etc.)
# that are not cities in their own right.

# NYC 5-borough bounding box (excludes NJ, Westchester, LI suburbs)
_NYC_BBOX = (40.47, -74.27, 40.92, -73.68)   # (lat_min, lon_min, lat_max, lon_max)

# LAPD jurisdiction bounding box (City of Los Angeles proper)
_LA_BBOX  = (33.70, -118.67, 34.34, -118.13)

# ±1 year search window for current period
_MONTHS_BACK = 12
# Minimum incident count to trust the data (low counts = unreliable rate)
_MIN_INCIDENTS = 5

# NYC offense description substrings → violent category
_NYC_VIOLENT = frozenset({
    "murder", "manslaughter", "rape", "robbery", "felony assault",
    "assault", "kidnap", "sex crimes",
})
_NYC_PROPERTY = frozenset({
    "burglary", "larceny", "grand larceny", "motor vehicle theft",
    "criminal mischief",
})

# LAPD crime code prefixes → category
# Codes 100-199 = homicide, 200-299 = sex/assault, 300-399 = robbery+burglary
# 400-499 = theft, 500-599 = vehicle
_LA_VIOLENT_CODES = frozenset({
    "110", "113", "121", "122", "210", "220", "230", "231", "235", "236",
    "250", "251", "761", "762",
})
_LA_PROPERTY_CODES = frozenset({
    "310", "320", "330", "331", "341", "343", "345", "350", "351", "352",
    "353", "354", "355", "356", "357", "358", "359", "510", "520",
})

# FBI UCR offense type keys → HomeFit category
_FBI_VIOLENT_KEYS = frozenset({
    "homicide", "rape", "robbery", "aggravated-assault",
})
_FBI_PROPERTY_KEYS = frozenset({
    "burglary", "motor-vehicle-theft", "larceny",
})

_REQUEST_TIMEOUT = 20


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_fbi_key() -> Optional[str]:
    return os.getenv("FBI_CRIME_API_KEY") or os.getenv("FBI_API_KEY")


def _date_range(
    months_back: int,
    offset_months: int = 0,
    max_date: Optional[datetime.date] = None,
) -> Tuple[str, str]:
    """
    Return ISO date strings for a rolling window ending `offset_months` ago,
    optionally capped at `max_date`.
    """
    now = datetime.date.today()
    end_month = now.month - offset_months
    end_year = now.year
    while end_month <= 0:
        end_month += 12
        end_year -= 1
    end = datetime.date(end_year, end_month, 1)
    if max_date and end > max_date:
        end = max_date.replace(day=1)

    start_month = end.month - months_back
    start_year = end.year
    while start_month <= 0:
        start_month += 12
        start_year -= 1
    start = datetime.date(start_year, start_month, 1)
    return start.isoformat(), end.isoformat()


def _classify_nyc(ofns_desc: str) -> Optional[str]:
    desc = ofns_desc.lower()
    for kw in _NYC_VIOLENT:
        if kw in desc:
            return "violent"
    for kw in _NYC_PROPERTY:
        if kw in desc:
            return "property"
    return None


def _classify_la(crm_cd: str) -> Optional[str]:
    code = str(crm_cd).strip()
    if code in _LA_VIOLENT_CODES:
        return "violent"
    if code in _LA_PROPERTY_CODES:
        return "property"
    return None


def _per_1k(count: int, population: int) -> float:
    if population <= 0:
        return 0.0
    return round(count / population * 1000, 3)


# ---------------------------------------------------------------------------
# NYC Open Data
# ---------------------------------------------------------------------------

@cached(ttl_seconds=CACHE_TTL["crime_data"])
def _fetch_nyc_crimes(lat: float, lon: float, radius_m: int, start_date: str, end_date: str) -> Optional[Dict]:
    """
    Query NYPD Complaint Data via Socrata SoQL within_circle.
    Returns raw dict with violent/property counts, or None on failure.
    """
    try:
        # SoQL: filter by circle and date range; return only needed fields
        where = (
            f"within_circle(lat_lon, {lat}, {lon}, {radius_m}) "
            f"AND cmplnt_fr_dt >= '{start_date}T00:00:00.000' "
            f"AND cmplnt_fr_dt < '{end_date}T00:00:00.000'"
        )
        params = {
            "$where": where,
            "$select": "ofns_desc,law_cat_cd,cmplnt_fr_dt",
            "$limit": 10000,
        }
        resp = requests.get(_NYC_SOCRATA, params=params, timeout=_REQUEST_TIMEOUT)
        if resp.status_code != 200:
            logger.warning("NYC crime API returned %d", resp.status_code)
            return None
        records = resp.json()
        violent, prop = 0, 0
        for r in records:
            cat = _classify_nyc(r.get("ofns_desc", ""))
            if cat == "violent":
                violent += 1
            elif cat == "property":
                prop += 1
        return {"violent": violent, "property": prop, "total": len(records)}
    except Exception as e:
        logger.warning("NYC crime fetch failed: %s", e)
        return None


def _get_nyc_rates(
    lat: float, lon: float, population: int, radius_m: int
) -> Optional[Dict]:
    """Get current + prior-year rates for NYC and compute trend."""
    start_cur, end_cur = _date_range(_MONTHS_BACK, offset_months=0)
    start_prv, end_prv = _date_range(_MONTHS_BACK, offset_months=_MONTHS_BACK)

    cur = _fetch_nyc_crimes(lat, lon, radius_m, start_cur, end_cur)
    prv = _fetch_nyc_crimes(lat, lon, radius_m, start_prv, end_prv)


    if cur is None:
        return None
    if cur["total"] < _MIN_INCIDENTS:
        logger.debug("NYC crime: too few incidents (%d) — unreliable", cur["total"])
        return None

    violent_rate = _per_1k(cur["violent"], population)
    property_rate = _per_1k(cur["property"], population)

    trend_pct: Optional[float] = None
    if prv is not None and prv["total"] >= _MIN_INCIDENTS and prv["violent"] >= 5:
        prv_violent = _per_1k(prv["violent"], population)
        if prv_violent > 0:
            raw_trend = (violent_rate - prv_violent) / prv_violent * 100
            # Cap at ±100% to prevent denominator-blowup nonsense
            trend_pct = round(max(-100.0, min(100.0, raw_trend)), 1)

    return {
        "violent_per_1k": violent_rate,
        "property_per_1k": property_rate,
        "trend_pct": trend_pct,
        "source": "nyc_open_data",
        "incidents_current": cur["total"],
    }


# ---------------------------------------------------------------------------
# LA Open Data
# ---------------------------------------------------------------------------

def _meters_to_degrees(meters: int) -> float:
    """Approximate conversion of a radius in meters to decimal degrees (lat/lon delta)."""
    return meters / 111_000.0


@cached(ttl_seconds=CACHE_TTL["crime_data"])
def _fetch_la_crimes(
    lat: float, lon: float, delta_deg: float, start_date: str, end_date: str
) -> Optional[Dict]:
    """
    Query LAPD legacy crime data via bounding box.
    The legacy dataset (2nrs-mtv8) has separate `lat` / `lon` numeric columns —
    Socrata's within_circle() does not work on them, so we use a bounding box.
    Data available through Dec 2024.
    """
    try:
        where = (
            f"lat >= {lat - delta_deg} AND lat <= {lat + delta_deg} "
            f"AND lon >= {lon - delta_deg} AND lon <= {lon + delta_deg} "
            f"AND date_occ >= '{start_date}T00:00:00.000' "
            f"AND date_occ < '{end_date}T00:00:00.000'"
        )
        params = {
            "$where": where,
            "$select": "crm_cd,date_occ",
            "$limit": 10000,
        }
        resp = requests.get(_LA_SOCRATA, params=params, timeout=_REQUEST_TIMEOUT)
        if resp.status_code != 200:
            logger.warning("LA crime API returned %d", resp.status_code)
            return None
        records = resp.json()
        violent, prop = 0, 0
        for r in records:
            cat = _classify_la(r.get("crm_cd", ""))
            if cat == "violent":
                violent += 1
            elif cat == "property":
                prop += 1
        return {"violent": violent, "property": prop, "total": len(records)}
    except Exception as e:
        logger.warning("LA crime fetch failed: %s", e)
        return None


def _get_la_rates(lat: float, lon: float, population: int, radius_m: int) -> Optional[Dict]:
    la_max = datetime.date(2024, 12, 31)
    # Current window: most recent 12 months within available data
    start_cur, end_cur = _date_range(_MONTHS_BACK, offset_months=0, max_date=la_max)
    start_prv, end_prv = _date_range(_MONTHS_BACK, offset_months=_MONTHS_BACK, max_date=la_max)

    delta_deg = _meters_to_degrees(radius_m)
    cur = _fetch_la_crimes(lat, lon, delta_deg, start_cur, end_cur)
    prv = _fetch_la_crimes(lat, lon, delta_deg, start_prv, end_prv)

    if cur is None:
        return None
    if cur["total"] < _MIN_INCIDENTS:
        logger.debug("LA crime: too few incidents (%d) — unreliable", cur["total"])
        return None

    import math as _math
    # Bounding box area = (2r)² = 4r²; circle area = π×r².
    # Scale population up by 4/π so per-1k rates are circle-equivalent (matching NYC).
    _adj_pop = max(1, int(population * (4.0 / _math.pi)))
    violent_rate = _per_1k(cur["violent"], _adj_pop)
    property_rate = _per_1k(cur["property"], _adj_pop)

    trend_pct: Optional[float] = None
    if prv is not None and prv["total"] >= _MIN_INCIDENTS and prv["violent"] >= 5:
        prv_violent = _per_1k(prv["violent"], population)
        if prv_violent > 0:
            raw_trend = (violent_rate - prv_violent) / prv_violent * 100
            trend_pct = round(max(-100.0, min(100.0, raw_trend)), 1)

    return {
        "violent_per_1k": violent_rate,
        "property_per_1k": property_rate,
        "trend_pct": trend_pct,
        "source": "la_open_data",
        "incidents_current": cur["total"],
        "data_period": f"{start_cur} to {end_cur}",
    }


# ---------------------------------------------------------------------------
# FBI Crime Data Explorer
# ---------------------------------------------------------------------------

@cached(ttl_seconds=CACHE_TTL["crime_data"])
def _fetch_fbi_agencies(state_abbr: str) -> Optional[list]:
    """Fetch all reporting agencies for a state (cached per state)."""
    api_key = _get_fbi_key()
    if not api_key:
        return None
    try:
        url = f"{_FBI_CDE_BASE}/agency/byStateAbbr/{state_abbr.upper()}"
        resp = requests.get(url, params={"API_KEY": api_key}, timeout=_REQUEST_TIMEOUT)
        if resp.status_code != 200:
            logger.warning("FBI CDE agencies returned %d for %s", resp.status_code, state_abbr)
            return None
        return resp.json()
    except Exception as e:
        logger.warning("FBI CDE agency fetch failed: %s", e)
        return None


@cached(ttl_seconds=CACHE_TTL["crime_data"])
def _fetch_fbi_offenses(ori: str, year_from: int, year_to: int) -> Optional[Dict]:
    """Fetch summarized offense counts for a specific agency ORI."""
    api_key = _get_fbi_key()
    if not api_key:
        return None
    try:
        url = f"{_FBI_CDE_BASE}/summarized/agency/{ori}/offenses/{year_from}/{year_to}"
        resp = requests.get(url, params={"API_KEY": api_key}, timeout=_REQUEST_TIMEOUT)
        if resp.status_code != 200:
            logger.warning("FBI CDE offenses returned %d for %s", resp.status_code, ori)
            return None
        return resp.json()
    except Exception as e:
        logger.warning("FBI CDE offense fetch failed: %s", e)
        return None


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    import math
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


def _find_nearest_agency(agencies: list, lat: float, lon: float) -> Optional[Dict]:
    """
    Find the closest law-enforcement agency to the given point.
    Prefers city/municipal police over county sheriff when both are close.
    """
    best = None
    best_dist = float("inf")
    for ag in agencies:
        ag_lat = ag.get("latitude") or ag.get("lat")
        ag_lon = ag.get("longitude") or ag.get("lng") or ag.get("lon")
        if ag_lat is None or ag_lon is None:
            continue
        try:
            dist = _haversine_km(lat, lon, float(ag_lat), float(ag_lon))
        except (TypeError, ValueError):
            continue
        agency_type = (ag.get("agencyType") or ag.get("agency_type") or "").lower()
        # Slight preference for city/municipal police over county sheriff
        if dist < best_dist or (abs(dist - best_dist) < 2.0 and "city" in agency_type):
            best_dist = dist
            best = ag
    return best if best_dist < 50 else None  # 50 km max


def _get_fbi_rates(
    lat: float, lon: float, state_abbr: str, population: int
) -> Optional[Dict]:
    """Look up FBI CDE rates for the nearest reporting agency."""
    agencies = _fetch_fbi_agencies(state_abbr)
    if not agencies:
        return None

    agency = _find_nearest_agency(agencies, lat, lon)
    if not agency:
        logger.debug("FBI CDE: no agency within 50 km for (%s, %s)", lat, lon)
        return None

    ori = agency.get("ori") or agency.get("ORI")
    if not ori:
        return None

    current_year = datetime.date.today().year
    prior_year = current_year - 1

    # FBI data lags ~1 year; try current year first, fall back to prior
    data = _fetch_fbi_offenses(ori, prior_year, prior_year)
    prev_data = _fetch_fbi_offenses(ori, prior_year - 1, prior_year - 1)

    if data is None:
        return None

    def _sum_offenses(raw, keys) -> int:
        if not raw:
            return 0
        total = 0
        for entry in (raw if isinstance(raw, list) else [raw]):
            for k in keys:
                total += int(entry.get(k, 0) or 0)
        return total

    violent_count = _sum_offenses(data, _FBI_VIOLENT_KEYS)
    property_count = _sum_offenses(data, _FBI_PROPERTY_KEYS)

    if violent_count + property_count == 0:
        return None

    violent_rate = _per_1k(violent_count, population)
    property_rate = _per_1k(property_count, population)

    trend_pct: Optional[float] = None
    if prev_data:
        prev_vc = _sum_offenses(prev_data, _FBI_VIOLENT_KEYS)
        if prev_vc >= 5:
            prev_violent = _per_1k(prev_vc, population)
            if prev_violent > 0:
                raw_trend = (violent_rate - prev_violent) / prev_violent * 100
                trend_pct = round(max(-100.0, min(100.0, raw_trend)), 1)

    return {
        "violent_per_1k": violent_rate,
        "property_per_1k": property_rate,
        "trend_pct": trend_pct,
        "source": "fbi_cde",
        "agency_ori": ori,
        "agency_name": agency.get("agencyName") or agency.get("agency_name"),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _radius_for_area_type(area_type: Optional[str]) -> int:
    """Search radius in meters by area type."""
    at = (area_type or "").lower()
    if "urban_core" in at or "urban" in at:
        return 800
    if "suburban" in at:
        return 2000
    if "exurban" in at:
        return 5000
    if "rural" in at:
        return 8000
    return 1500


def get_crime_rates(
    lat: float,
    lon: float,
    *,
    city: Optional[str] = None,
    state_abbr: Optional[str] = None,
    area_type: Optional[str] = None,
    population: int = 10000,
) -> Optional[Dict]:
    """
    Fetch violent and property crime rates per 1k population for a location.

    Returns a dict with keys:
        violent_per_1k, property_per_1k, trend_pct, source, [agency_ori, incidents_current]

    Returns None if no data source could provide rates (caller should treat as DEGRADED).

    Args:
        lat, lon:      Coordinates of the location centre.
        city:          City/neighbourhood name (used to route to Socrata vs FBI).
        state_abbr:    Two-letter state (used by FBI CDE path).
        area_type:     Morphological area type (drives search radius).
        population:    Estimated population in the scored area (for per-1k conversion).
    """
    radius_m = _radius_for_area_type(area_type)

    def _in_bbox(bbox):
        lat_min, lon_min, lat_max, lon_max = bbox
        return lat_min <= lat <= lat_max and lon_min <= lon <= lon_max

    # Route by coordinates — handles sub-neighborhoods that aren't named cities
    if _in_bbox(_NYC_BBOX):
        result = _get_nyc_rates(lat, lon, population, radius_m)
        if result:
            return result

    if _in_bbox(_LA_BBOX):
        result = _get_la_rates(lat, lon, population, radius_m)
        if result:
            return result

    # FBI CDE fallback (suburbs, other metros)
    if state_abbr and _get_fbi_key():
        result = _get_fbi_rates(lat, lon, state_abbr, population)
        if result:
            return result

    logger.debug("crime_api: no data for city=%s state=%s", city, state_abbr)
    return None
