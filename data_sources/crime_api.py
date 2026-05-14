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
import json
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

# NY State UCR per-agency dataset (Socrata, no key required)
# "Index Crimes by County and Agency: Beginning 1990"
_NY_STATE_CRIME_DS = "https://data.ny.gov/resource/ca8h-8gjq.json"

# ---------------------------------------------------------------------------
# LASD (LA County Sheriff) station-level crime data
# Pre-aggregated from lasd.org annual Part I & II Crimes CSV.
# Cities that contract LASD don't have their own ORI in the FBI database.
# ---------------------------------------------------------------------------
# Approximate total residential population served by each LASD patrol station.
# These are the combined Census populations of all cities + unincorporated
# communities within each station's primary service area.  Used as the
# denominator for per-1k rate calculations so that rolling-hills-sized cities
# aren't scored against crime from an entire multi-city patrol zone.
_LASD_STATION_POPULATIONS: Dict[str, int] = {
    "ALTADENA":          44_000,   # Altadena unincorporated
    "CERRITOS":          52_000,   # City of Cerritos
    "COMPTON":          107_000,   # Compton + adjacent unincorporated
    "CRESCENTA VALLEY":  40_000,   # La Cañada, La Crescenta, Montrose
    "LOMITA":            75_000,   # Lomita + RPV + Rolling Hills + RHE
    "MALIBU/LOST HILLS": 75_000,   # Malibu + Agoura Hills + Calabasas + unincorporated
    "MARINA DEL REY":     9_000,   # Marina del Rey unincorporated
    "NORWALK":          165_000,   # Norwalk + La Mirada + unincorporated
    "TEMPLE":           110_000,   # Temple City + Rosemead + unincorporated SGV
    "WEST HOLLYWOOD":    36_000,   # City of West Hollywood
}

_LASD_CITY_TO_STATION: Dict[str, str] = {
    # City name (lowercase) → LASD UNIT_NAME (as it appears in the CSV)
    "altadena":             "ALTADENA",
    "cerritos":             "CERRITOS",
    "compton":              "COMPTON",
    "la canada flintridge": "CRESCENTA VALLEY",
    "la cañada flintridge": "CRESCENTA VALLEY",
    "la crescenta":         "CRESCENTA VALLEY",
    "la mirada":            "NORWALK",
    "rolling hills estates":"LOMITA",
    "rancho palos verdes":  "LOMITA",
    "agoura hills":         "MALIBU/LOST HILLS",
    "malibu":               "MALIBU/LOST HILLS",
    "temple city":          "TEMPLE",
    "rosemead":             "TEMPLE",
    "west hollywood":       "WEST HOLLYWOOD",
    "marina del rey":       "MARINA DEL REY",
}

def _load_lasd_station_crimes() -> Dict:
    """Load pre-aggregated LASD station crime counts from data/lasd_station_crimes.json."""
    try:
        import os
        data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
        path = os.path.join(data_dir, "lasd_station_crimes.json")
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {}

_LASD_STATION_DATA: Dict = {}  # populated lazily on first use

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
    """
    Fetch all reporting agencies for a state (cached per state).
    The FBI CDE API returns a dict keyed by county name; we flatten to a list.
    """
    api_key = _get_fbi_key()
    if not api_key:
        return None
    try:
        url = f"{_FBI_CDE_BASE}/agency/byStateAbbr/{state_abbr.upper()}"
        resp = requests.get(url, params={"API_KEY": api_key}, timeout=_REQUEST_TIMEOUT)
        if resp.status_code != 200:
            logger.warning("FBI CDE agencies returned %d for %s", resp.status_code, state_abbr)
            return None
        raw = resp.json()
        # Response is a dict {county: [agency, ...]} — flatten to a single list
        if isinstance(raw, dict):
            agencies = []
            for county_agencies in raw.values():
                if isinstance(county_agencies, list):
                    agencies.extend(county_agencies)
            return agencies if agencies else None
        if isinstance(raw, list):
            return raw or None
        return None
    except Exception as e:
        logger.warning("FBI CDE agency fetch failed: %s", e)
        return None


@cached(ttl_seconds=CACHE_TTL["crime_data"])
def _fetch_fbi_rate(
    ori: str, offense_type: str, year: int, agency_name: Optional[str] = None
) -> Optional[float]:
    """
    Fetch an annual crime rate per 100k from the FBI CDE summarized/agency endpoint.

    For NIBRS-reporting agencies: if ``agency_name`` is provided and a matching
    agency-specific key exists in the response, that per-agency rate is returned
    (Tier 2 granularity).  Otherwise, the state-level rate is returned as a
    fallback (Tier 3).

    We take the December value of the rolling monthly series as the full-year
    figure, consistent with how we have always used this endpoint.
    """
    api_key = _get_fbi_key()
    if not api_key:
        return None
    try:
        url = f"{_FBI_CDE_BASE}/summarized/agency/{ori}/{offense_type}"
        params = {
            "API_KEY": api_key,
            "from": f"01-{year}",
            "to": f"12-{year}",
        }
        resp = requests.get(url, params=params, timeout=_REQUEST_TIMEOUT)
        if resp.status_code != 200:
            logger.warning("FBI CDE rate %s %d returned %d", offense_type, year, resp.status_code)
            return None
        data = resp.json()
        rates_by_label = data.get("offenses", {}).get("rates", {})

        def _extract(label: str) -> Optional[float]:
            month_vals = rates_by_label.get(label, {})
            if not month_vals:
                return None
            dec_key = f"12-{year}"
            vals = list(month_vals.values())
            return float(month_vals.get(dec_key) or vals[-1])

        # Tier 2: prefer agency-specific key when the caller supplies the expected
        # agency name (only reliable for NIBRS-reporting agencies whose name appears
        # explicitly in the response).
        if agency_name:
            # Normalise: "Beverly Hills Police Department" → look for that substring
            # in the Offenses key e.g. "Beverly Hills Police Department Offenses"
            ag_key = next(
                (k for k in rates_by_label
                 if "Offenses" in k
                 and "United States" not in k
                 and "California" not in k   # skip state aggregate
                 and agency_name.lower() in k.lower()),
                None,
            )
            if ag_key:
                val = _extract(ag_key)
                if val is not None:
                    logger.debug("FBI CDE agency rate for '%s' %s %d: %.2f", agency_name, offense_type, year, val)
                    return val

        # Tier 3: state-level aggregate
        for label in rates_by_label:
            if "Offenses" in label and "United States" not in label:
                val = _extract(label)
                if val is not None:
                    return val

        # Last-resort: national rate
        for label in rates_by_label:
            if "United States" in label and "Offenses" in label:
                val = _extract(label)
                if val is not None:
                    return val
        return None
    except Exception as e:
        logger.warning("FBI CDE rate fetch failed: %s", e)
        return None


# Keep the old name as an alias so existing callers don't break
def _fetch_fbi_state_rate(ori: str, offense_type: str, year: int) -> Optional[float]:
    return _fetch_fbi_rate(ori, offense_type, year)


# Keywords that identify transit, campus, and other special-purpose police
# agencies that should NOT be selected as the nearest agency for a municipality.
# These agencies have widespread or misregistered coordinates in the FBI database
# and serve specific infrastructure, not the surrounding residential community.
_SPECIAL_PURPOSE_AGENCY_SKIP = frozenset({
    "metropolitan transportation authority",
    "metropolitan transportation",
    "transit authority",
    "port authority",
    "railroad",
    "railway",
    "amtrak",
    "metro-north",
    "metro north",
    "new jersey transit",
    "mta police",
    "airport",
    "harbor",
    "university police",
    "college police",
    "campus police",
    "stevens institute",
    "housing authority",
})


def _is_special_purpose_agency(agency_name: str) -> bool:
    name_lower = agency_name.lower()
    return any(kw in name_lower for kw in _SPECIAL_PURPOSE_AGENCY_SKIP)


# Known unincorporated communities / suburbs that are served by the police
# department of a parent municipality rather than their own PD.
# Key: city hint (lowercase), Value: parent city name for agency name matching.
# This handles nibrs_city_match failures when the FBI geo coords are wrong
# or when the location is a hamlet within a larger municipality.
_SUBURB_TO_PARENT_CITY: Dict[str, str] = {
    # CT neighborhoods within Greenwich
    "cos cob":        "Greenwich",
    "old greenwich":  "Greenwich",
    "riverside":      "Greenwich",   # CT — not NJ Riverside
    # CT neighborhoods within Fairfield  
    "southport":      "Fairfield",
    # NJ communities served by township PD rather than own PD
    "short hills":    "Millburn",
}


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
    Skips transit, campus, and other special-purpose agencies that have
    misregistered coordinates in the FBI database or don't serve the
    residential community.
    Prefers city/municipal police over county sheriff when both are close.
    """
    best = None
    best_dist = float("inf")
    for ag in agencies:
        ag_lat = ag.get("latitude") or ag.get("lat")
        ag_lon = ag.get("longitude") or ag.get("lng") or ag.get("lon")
        if ag_lat is None or ag_lon is None:
            continue
        agency_display = (ag.get("agency_name") or ag.get("agencyName") or "").lower()
        if _is_special_purpose_agency(agency_display):
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


def _find_nibrs_agency_by_name(agencies: list, city_hint: str) -> Optional[Dict]:
    """
    Scan all agencies for a NIBRS-reporting PD whose name contains all words
    from city_hint (len > 3).  Used as a fallback when _find_nearest_agency
    selects the wrong agency due to bad lat/lon data in the FBI database.
    """
    if not city_hint or not agencies:
        return None
    words = [w.lower() for w in city_hint.split() if len(w) > 3]
    if not words:
        return None
    for ag in agencies:
        name = (ag.get("agency_name") or ag.get("agencyName") or "").lower()
        if all(w in name for w in words) and not _is_special_purpose_agency(name):
            if ag.get("is_nibrs"):
                return ag
    return None


@cached(ttl_seconds=CACHE_TTL["crime_data"])
def _fetch_ny_state_agency_crimes(
    town_keyword: str, county: str, year: int
) -> Optional[Dict]:
    """
    Query the NY State UCR per-agency dataset for a specific town in a county.

    Excludes county-wide entries ("County Total", "County PD", "County Sheriff",
    "State Police") so we always get a single-municipality figure.

    Returns the row dict with 'violent', 'property', 'months_reported', etc.,
    or None if not found or data is incomplete (<10 months reported).
    """
    try:
        # Escape any apostrophes in town keyword (e.g. "Sleepy Hollow")
        safe_kw = town_keyword.replace("'", "''")
        where = (
            f"upper(agency) like upper('%{safe_kw}%') "
            f"AND agency NOT LIKE '%County%' "
            f"AND agency NOT LIKE '%State Police%' "
            f"AND agency NOT LIKE '%SUNY%' "
            f"AND agency != 'County Total'"
        )
        params = {
            "$where": where,
            "county": county.title(),
            "year": str(year),
            "$order": "months_reported DESC, violent DESC",
            "$limit": 1,
        }
        resp = requests.get(_NY_STATE_CRIME_DS, params=params, timeout=_REQUEST_TIMEOUT)
        if resp.status_code != 200:
            logger.debug("NY state crime DS returned %d for %s/%s", resp.status_code, town_keyword, county)
            return None
        data = resp.json()
        if not data:
            return None
        row = data[0]
        months = int(row.get("months_reported", 0) or 0)
        if months < 10:
            return None  # reject partial-year reports
        return row
    except Exception as e:
        logger.warning("NY state crime fetch failed for '%s'/%s: %s", town_keyword, county, e)
        return None


def _rates_from_ny_state(
    row: Dict, prev_row: Optional[Dict], population: int
) -> Dict:
    """Convert NY state UCR row(s) to the standard rates dict."""
    violent = int(row.get("violent", 0) or 0)
    property_ = int(row.get("property", 0) or 0)
    pop = max(1, population)

    violent_rate = round(violent / pop * 1000, 3)
    property_rate = round(property_ / pop * 1000, 3)

    trend_pct: Optional[float] = None
    if prev_row:
        prev_v = int(prev_row.get("violent", 0) or 0)
        if prev_v >= 5 and violent_rate > 0:
            prev_rate = prev_v / pop * 1000
            if prev_rate > 0:
                raw_trend = (violent_rate - prev_rate) / prev_rate * 100
                trend_pct = round(max(-100.0, min(100.0, raw_trend)), 1)

    return {
        "violent_per_1k": violent_rate,
        "property_per_1k": property_rate,
        "trend_pct": trend_pct,
        "source": "ny_state_ucr",
        "agency_name": row.get("agency"),
        "incidents_current": violent + property_,
        "data_period": row.get("year"),
    }


def _get_lasd_rates(station: str, population: int) -> Optional[Dict]:
    """
    Return per-1k crime rates using pre-aggregated LASD station data.

    Uses 2024 as the current year and 2023 for trend calculation.

    Crime counts are divided by the *station* service-area population (not the
    individual city population) so that small contract cities like Rolling Hills
    Estates (8k residents, LOMITA station covers 75k total) get the correct
    patrol-area rate rather than an absurdly inflated per-city figure.
    """
    global _LASD_STATION_DATA
    if not _LASD_STATION_DATA:
        _LASD_STATION_DATA = _load_lasd_station_crimes()
    if not _LASD_STATION_DATA:
        return None

    cur = (_LASD_STATION_DATA.get("2024") or {}).get(station)
    prev = (_LASD_STATION_DATA.get("2023") or {}).get(station)
    if not cur:
        return None

    pop = max(1, _LASD_STATION_POPULATIONS.get(station, population))
    violent_rate = round(cur["violent"] / pop * 1000, 3)
    property_rate = round(cur["property"] / pop * 1000, 3)

    trend_pct: Optional[float] = None
    if prev and prev.get("violent", 0) >= 5 and violent_rate > 0:
        prev_rate = prev["violent"] / pop * 1000
        if prev_rate > 0:
            raw_trend = (violent_rate - prev_rate) / prev_rate * 100
            trend_pct = round(max(-100.0, min(100.0, raw_trend)), 1)

    return {
        "violent_per_1k": violent_rate,
        "property_per_1k": property_rate,
        "trend_pct": trend_pct,
        "source": "lasd_station",
        "agency_name": f"LASD {station.title()} Station",
        "incidents_current": cur["violent"] + cur["property"],
    }


# Known jurisdiction populations for large county-level agencies in the NY UCR dataset.
# These agencies serve wide areas; the local-radius population estimate is too small
# to produce accurate per-1k rates.  Values are approximate 2024 census estimates
# for the unincorporated/contract portion of each county served by the county PD.
_NY_COUNTY_PD_POPULATIONS: Dict[str, int] = {
    "Nassau County PD": 1_100_000,  # Nassau County unincorporated (county minus own-PD municipalities)
}


@cached(ttl_seconds=CACHE_TTL["crime_data"])
def _fetch_ny_state_nassau_pd(year: int) -> Optional[Dict]:
    """
    Fetch Nassau County PD crime row for unincorporated Nassau communities.
    Bypasses the standard _fetch_ny_state_agency_crimes filter that excludes
    county-level agencies, since Nassau County PD is the correct serving
    agency for dozens of unincorporated hamlets (Bellmore, Hewlett, etc.).
    """
    try:
        params = {
            "$where": "upper(agency) = 'NASSAU COUNTY PD'",
            "county": "Nassau",
            "year": str(year),
            "$limit": 1,
        }
        resp = requests.get(_NY_STATE_CRIME_DS, params=params, timeout=_REQUEST_TIMEOUT)
        if resp.status_code != 200:
            return None
        data = resp.json()
        if not data:
            return None
        row = data[0]
        # Accept partial-year reports for county-level PD (months_reported may be absent)
        return row
    except Exception as e:
        logger.warning("Nassau County PD fetch failed for year %d: %s", year, e)
        return None


def _get_fbi_rates(
    lat: float, lon: float, state_abbr: str, population: int,
    city_hint: Optional[str] = None,
) -> Optional[Dict]:
    """
    Return state-level FBI crime rates as a proxy for suburban/rural locations.

    The FBI CDE /summarized/agency endpoint returns state-level rates (not
    individual-agency rates) — this is a known limitation of the public API.
    State rates are a reasonable proxy: they reflect the crime environment
    of the broader region and enable meaningful cross-state comparisons.

    Rates are per 100k from the API; we divide by 100 to yield per-1k values
    consistent with the Socrata path.
    """
    agencies = _fetch_fbi_agencies(state_abbr)
    if not agencies:
        return None

    # Any ORI from the state works to query state-level rates; use the nearest.
    agency = _find_nearest_agency(agencies, lat, lon)
    if not agency:
        logger.debug("FBI CDE: no agency within 50 km for (%s, %s)", lat, lon)
        agency = agencies[0] if agencies else None
    if not agency:
        return None

    ori = agency.get("ori") or agency.get("ORI")
    if not ori:
        return None

    current_year = datetime.date.today().year
    data_year = current_year - 1
    prev_year = data_year - 1

    # -----------------------------------------------------------------------
    # Tier 2: NY State UCR per-agency data (more granular than FBI CDE state)
    # -----------------------------------------------------------------------
    if state_abbr.upper() == "NY" and city_hint:
        county = (agency.get("counties") or "").title()
        if county:
            ny_row = _fetch_ny_state_agency_crimes(city_hint, county, data_year)
            if ny_row is None:
                ny_row = _fetch_ny_state_agency_crimes(city_hint, county, data_year - 1)

            # Hamlets and unincorporated communities in New York are policed by TOWN
            # police departments, which appear in the state dataset under the town name
            # ("New Castle Town PD"), not the hamlet name ("Chappaqua").
            # Retry using the town name when the FBI agency is a TOWN PD.
            # Do NOT apply this to Village or City PDs — those have fixed boundaries
            # and don't cover adjacent unincorporated areas.
            if ny_row is None:
                agency_name_raw = agency.get("agency_name") or ""
                if " Town " in agency_name_raw and " Village " not in agency_name_raw:
                    town_kw = agency_name_raw.split(" Town ")[0].strip()
                    if town_kw and town_kw.lower() != city_hint.lower():
                        ny_row = _fetch_ny_state_agency_crimes(town_kw, county, data_year)
                        if ny_row is None:
                            ny_row = _fetch_ny_state_agency_crimes(town_kw, county, data_year - 1)

            # Tier 3 Nassau fallback: unincorporated Nassau communities are served
            # by Nassau County PD (not a dedicated city PD).  Use the county-wide
            # agency when the direct city lookup fails.  Use the known jurisdiction
            # population rather than the local-radius estimate so that the large
            # raw crime counts are divided by the correct denominator.
            if ny_row is None and county.lower() == "nassau":
                nassau_row = _fetch_ny_state_nassau_pd(data_year)
                if nassau_row is None:
                    nassau_row = _fetch_ny_state_nassau_pd(data_year - 1)
                if nassau_row is not None:
                    prev_nassau = _fetch_ny_state_nassau_pd(int(nassau_row["year"]) - 1)
                    nassau_pop = _NY_COUNTY_PD_POPULATIONS.get("Nassau County PD", population)
                    logger.debug(
                        "NY state UCR: Nassau County PD fallback for '%s' (pop=%d)",
                        city_hint, nassau_pop,
                    )
                    return _rates_from_ny_state(nassau_row, prev_nassau, nassau_pop)

            if ny_row is not None:
                prev_ny_row = _fetch_ny_state_agency_crimes(
                    ny_row.get("agency", city_hint)[:20], county, int(ny_row["year"]) - 1
                )
                return _rates_from_ny_state(ny_row, prev_ny_row, population)
            logger.debug(
                "NY state UCR: no per-agency row for '%s' in %s; falling back to CDE state rate",
                city_hint, county,
            )

    # -----------------------------------------------------------------------
    # Tier 2/3: FBI CDE.  For NIBRS-reporting agencies, pass the agency name
    # so _fetch_fbi_rate can extract per-agency rates rather than the state
    # aggregate.  For non-NIBRS agencies, agency_name_hint stays None and the
    # function falls through to the state-level rate.
    # -----------------------------------------------------------------------
    is_nibrs = bool(agency.get("is_nibrs"))
    agency_display_name = agency.get("agencyName") or agency.get("agency_name") or ""

    # Guard: only use per-agency NIBRS data when we're confident the right agency
    # was matched.  _find_nearest_agency picks by distance, so for a non-NIBRS
    # city it may return a nearby adjacent municipality.  Verify the city_hint
    # (e.g. "Beverly Hills") actually appears in the agency name.
    nibrs_city_match = (
        is_nibrs
        and city_hint
        and any(
            word.lower() in agency_display_name.lower()
            for word in (city_hint or "").split()
            if len(word) > 3  # skip short words like "San", "Los", "Del"
        )
    )

    # Tier 2b: unincorporated suburb → parent municipality matching.
    # e.g. "Short Hills" → "Millburn", "Cos Cob" → "Greenwich"
    if not nibrs_city_match and city_hint:
        parent_city = _SUBURB_TO_PARENT_CITY.get(city_hint.lower())
        if parent_city:
            parent_match = is_nibrs and any(
                word.lower() in agency_display_name.lower()
                for word in parent_city.split()
                if len(word) > 3
            )
            if parent_match:
                nibrs_city_match = True
                logger.debug(
                    "FBI CDE: suburb '%s' matched via parent city '%s' → %s",
                    city_hint, parent_city, agency_display_name,
                )

    # Tier 2b fallback: the nearest agency may have bad lat/lon in the FBI
    # database, causing _find_nearest_agency to pick the wrong PD.  Try a
    # direct name-based search as a second opinion.
    if not nibrs_city_match and city_hint and agencies:
        name_match_agency = _find_nibrs_agency_by_name(agencies, city_hint)
        if name_match_agency and name_match_agency.get("ori") != ori:
            ori = name_match_agency.get("ori") or name_match_agency.get("ORI")
            agency_display_name = (
                name_match_agency.get("agencyName") or name_match_agency.get("agency_name") or ""
            )
            is_nibrs = True
            nibrs_city_match = True
            logger.debug(
                "FBI CDE: name-based fallback for '%s' → %s (ORI %s)",
                city_hint, agency_display_name, ori,
            )

    agency_name_hint = agency_display_name if nibrs_city_match else None

    violent_rate_100k = _fetch_fbi_rate(ori, "violent-crime", data_year, agency_name_hint)
    if violent_rate_100k is None:
        violent_rate_100k = _fetch_fbi_rate(ori, "violent-crime", prev_year, agency_name_hint)
        prev_year -= 1

    if violent_rate_100k is None:
        return None

    property_rate_100k = _fetch_fbi_rate(ori, "property-crime", data_year, agency_name_hint)
    if property_rate_100k is None:
        property_rate_100k = _fetch_fbi_rate(ori, "property-crime", prev_year, agency_name_hint)

    # Convert per-100k → per-1k
    violent_rate = round(violent_rate_100k / 100.0, 3)
    property_rate = round((property_rate_100k or 0.0) / 100.0, 3)

    # Trend: compare current year violent to prior year
    trend_pct: Optional[float] = None
    prev_violent_100k = _fetch_fbi_rate(ori, "violent-crime", prev_year, agency_name_hint)
    if prev_violent_100k and prev_violent_100k > 0:
        raw_trend = (violent_rate_100k - prev_violent_100k) / prev_violent_100k * 100
        trend_pct = round(max(-100.0, min(100.0, raw_trend)), 1)

    source = "fbi_nibrs_agency" if nibrs_city_match else "fbi_cde_state"
    return {
        "violent_per_1k": violent_rate,
        "property_per_1k": property_rate,
        "trend_pct": trend_pct,
        "source": source,
        "agency_ori": ori,
        "agency_name": agency_display_name,
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

    # LASD station data: CA cities that contract with LA County Sheriff
    if city:
        lasd_station = _LASD_CITY_TO_STATION.get(city.lower())
        if lasd_station:
            result = _get_lasd_rates(lasd_station, population)
            if result:
                return result

    # FBI CDE / State UCR (suburbs and other metros)
    if state_abbr and _get_fbi_key():
        result = _get_fbi_rates(lat, lon, state_abbr, population, city_hint=city)
        if result:
            return result

    logger.debug("crime_api: no data for city=%s state=%s", city, state_abbr)
    return None
