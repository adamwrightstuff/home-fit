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
import re
import time
from typing import Dict, Optional, Tuple

import requests

from data_sources.cache import cached, CACHE_TTL
from logging_config import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# City open-data endpoints (Socrata, no key required).  Each is queried for the
# last complete calendar year, matching the FBI per-agency data year, and only
# FBI Part I offenses are counted so city neighborhoods and police-department
# totals measure the same crimes.
# NYPD Complaint Data Historic (full calendar years; the "Current" dataset is year-to-date only).
_NYC_SOCRATA = "https://data.cityofnewyork.us/resource/qgea-i56i.json"
# LAPD NIBRS offenses (2024+, with lat/lon).  The legacy SRS dataset stops mid-2024.
_LA_SOCRATA = "https://data.lacity.org/resource/y8y3-fqfu.json"
# SFPD "Police Department Incident Reports: 2018 to Present" (updated daily).
_SF_SOCRATA = "https://data.sf.gov/resource/wg3w-h783.json"

# FBI Crime Data Explorer
_FBI_CDE_BASE = "https://api.usa.gov/crime/fbi/cde"

# NY State UCR per-agency dataset (Socrata, no key required)
# "Index Crimes by County and Agency: Beginning 1990"
_NY_STATE_CRIME_DS = "https://data.ny.gov/resource/ca8h-8gjq.json"

# CA DOJ "Crimes and Clearances" — per-agency UCR counts for every CA LEA.
# Covers non-NIBRS agencies the FBI CDE no longer publishes individually.
# Downloaded from: https://openjustice.doj.ca.gov/data
_CA_DOJ_CSV = os.path.join(os.path.dirname(__file__), "static", "ca_doj_crimes_clearances.csv")

# Cities whose crimes are reported under a county sheriff or regional PD in the CA DOJ dataset.
# Maps city_hint (lowercase) → (ca_doj_agency_name, service_population).
# Service population = total population the agency serves (used as rate denominator).
# Marin County Sheriff service population derived from 2020 Census:
#   Marin County total ~258,826 minus cities with own PDs (Belvedere, Central Marin,
#   Fairfax, Mill Valley, Novato, Ross, San Rafael, Sausalito, Tiburon ≈ 182k) = ~77k.
_CA_DOJ_SERVING_AGENCIES: Dict[str, Tuple[str, int]] = {
    "san anselmo": ("Marin Co. Sheriff's Department", 77_000),
}

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
    "MARINA DEL REY":    29_000,   # Marina del Rey + Ladera Heights + View Park-Windsor Hills CDPs (ACS 2022: 28,983)
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

# City and County of San Francisco (SFPD jurisdiction; excludes Daly City/Brisbane)
_SF_BBOX = (37.703, -122.53, 37.835, -122.355)

# Census incorporated-place GEOIDs for the cities whose police publish incident
# data.  A bbox hit is only used when the point is inside that city, so nearby
# towns (Weehawken, Beverly Hills, Valley Stream) use their own police data.
_OPEN_DATA_CITY_GEOID = {"nyc": "3651000", "la": "0644000", "sf": "0667000"}

# City neighborhoods scored from incident data: the smallest of these radii whose
# disk holds MIN_NEIGHBORHOOD_RESIDENTS, so a pin in a thinly populated spot (hills,
# waterfront, commercial core) widens until the rate rests on enough residents.
NEIGHBORHOOD_RADII_M = (600, 800, 1000, 1200, 1500, 2000)
MIN_NEIGHBORHOOD_RESIDENTS = 10_000

# LAPD jurisdiction bounding box (City of Los Angeles proper)
_LA_BBOX  = (33.70, -118.67, 34.34, -118.13)

# Minimum incident count to trust the data (low counts = unreliable rate)
_MIN_INCIDENTS = 5

# FBI Part I definitions: violent = murder/non-negligent manslaughter, rape,
# robbery, aggravated assault; property = burglary, larceny-theft, motor vehicle
# theft.  Simple assault, vandalism, and other Part II offenses are excluded.
_NYC_VIOLENT_OFFENSES = (
    "MURDER & NON-NEGL. MANSLAUGHTER", "RAPE", "ROBBERY", "FELONY ASSAULT",
)
_NYC_PROPERTY_OFFENSES = (
    "BURGLARY", "GRAND LARCENY", "PETIT LARCENY",
    "GRAND LARCENY OF MOTOR VEHICLE", "PETIT LARCENY OF MOTOR VEHICLE",
)
# SFPD: only the Aggravated Assault subcategory of Assault is Part I.
_SF_VIOLENT_WHERE = (
    "(incident_category in ('Homicide', 'Rape', 'Robbery') "
    "OR incident_subcategory = 'Aggravated Assault')"
)
_SF_PROPERTY_WHERE = (
    "incident_category in ('Burglary', 'Larceny Theft', 'Motor Vehicle Theft', 'Motor Vehicle Theft?')"
)
# LAPD NIBRS offense codes (FBI NIBRS code list).
_LA_VIOLENT_NIBRS = ("09A", "11A", "11B", "11C", "120", "13A")
_LA_PROPERTY_NIBRS = ("220", "23A", "23B", "23C", "23D", "23E", "23F", "23G", "23H", "240")

# FBI UCR offense type keys → HomeFit category
_FBI_VIOLENT_KEYS = frozenset({
    "homicide", "rape", "robbery", "aggravated-assault",
})
_FBI_PROPERTY_KEYS = frozenset({
    "burglary", "motor-vehicle-theft", "larceny",
})

_REQUEST_TIMEOUT = 20
_AGENCIES_TIMEOUT = 45  # CA agencies list is 221KB and can exceed the default 20s


# ---------------------------------------------------------------------------
# CA DOJ per-agency lookup (lazy-loaded)
# ---------------------------------------------------------------------------

_ca_doj_index: Optional[Dict] = None  # {(agency_lower, year): {violent, property}}

def _load_ca_doj() -> Dict:
    global _ca_doj_index
    if _ca_doj_index is not None:
        return _ca_doj_index
    import csv
    idx: Dict = {}
    try:
        with open(_CA_DOJ_CSV, newline="", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                try:
                    year = int(row["Year"])
                    agency = (row.get("NCICCode") or "").strip().lower()
                    violent = int(row.get("Violent_sum") or 0)
                    prop = int(row.get("Property_sum") or 0)
                    if agency:
                        idx[(agency, year)] = {"violent": violent, "property": prop}
                except (ValueError, KeyError):
                    continue
        logger.debug("CA DOJ: loaded %d agency-year rows", len(idx))
    except Exception as exc:
        logger.warning("CA DOJ: failed to load %s: %s", _CA_DOJ_CSV, exc)
    _ca_doj_index = idx
    return idx


def _get_ca_doj_rates(city: str, population: int, data_year: int) -> Optional[Dict]:
    """Return per-1k crime rates from CA DOJ data for `city`, trying up to 3 years back."""
    idx = _load_ca_doj()
    # Check if this city's crimes are reported under a serving agency (e.g. county sheriff).
    override = _CA_DOJ_SERVING_AGENCIES.get(city.strip().lower())
    if override:
        agency_name, service_pop = override
        key = agency_name.strip().lower()
        population = service_pop
    else:
        key = city.strip().lower()
    for yr in range(data_year, data_year - 4, -1):
        row = idx.get((key, yr))
        if row is None:
            continue
        if row["violent"] == 0 and row["property"] == 0:
            continue
        pop = max(population, 1)
        violent_rate = round(row["violent"] / pop * 1000, 3)
        prop_rate = round(row["property"] / pop * 1000, 3)
        # trend: compare to prior year if available
        prev = idx.get((key, yr - 1))
        trend_pct: Optional[float] = None
        if prev and prev["violent"] > 0:
            raw = (row["violent"] - prev["violent"]) / prev["violent"] * 100
            trend_pct = round(max(-100.0, min(100.0, raw)), 1)
        return {
            "violent_per_1k": violent_rate,
            "property_per_1k": prop_rate,
            "trend_pct": trend_pct,
            "source": "ca_doj_ucr",
            "agency_name": city,
            "data_year": yr,
        }
    return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_fbi_key() -> Optional[str]:
    return os.getenv("FBI_CRIME_API_KEY") or os.getenv("FBI_API_KEY")


def _per_1k(count: int, population: int) -> float:
    if population <= 0:
        return 0.0
    return round(count / population * 1000, 3)


def _soql_list(values) -> str:
    return ", ".join("'" + v.replace("'", "''") + "'" for v in values)


def _open_data_year() -> int:
    """Last complete calendar year (same year the FBI per-agency path uses)."""
    return datetime.date.today().year - 1


def _socrata_count(url: str, select: str, where: str, label: str) -> Optional[int]:
    try:
        resp = requests.get(url, params={"$select": f"{select} as n", "$where": where},
                            timeout=_REQUEST_TIMEOUT)
        if resp.status_code != 200:
            logger.warning("%s crime API returned %d", label, resp.status_code)
            return None
        rows = resp.json()
        return int(rows[0].get("n", 0) or 0) if rows else 0
    except Exception as e:
        logger.warning("%s crime fetch failed: %s", label, e)
        return None


def _year_bounds(year: int, field: str) -> str:
    return f"{field} >= '{year}-01-01T00:00:00.000' AND {field} < '{year + 1}-01-01T00:00:00.000'"


# ---------------------------------------------------------------------------
# NYC Open Data
# ---------------------------------------------------------------------------

@cached(ttl_seconds=CACHE_TTL["crime_data"])
def _fetch_nyc_part1(lat: float, lon: float, radius_m: int, year: int) -> Optional[Dict]:
    """Part I violent/property complaint counts within a circle for one calendar year."""
    base = f"within_circle(lat_lon, {lat}, {lon}, {radius_m}) AND " + _year_bounds(year, "cmplnt_fr_dt")
    v = _socrata_count(_NYC_SOCRATA, "count(*)",
                       f"{base} AND ofns_desc in ({_soql_list(_NYC_VIOLENT_OFFENSES)})", "NYC")
    p = _socrata_count(_NYC_SOCRATA, "count(*)",
                       f"{base} AND ofns_desc in ({_soql_list(_NYC_PROPERTY_OFFENSES)})", "NYC")
    if v is None or p is None:
        return None
    return {"violent": v, "property": p}


# ---------------------------------------------------------------------------
# SF Open Data
# ---------------------------------------------------------------------------

@cached(ttl_seconds=CACHE_TTL["crime_data"])
def _fetch_sf_part1(lat: float, lon: float, radius_m: int, year: int) -> Optional[Dict]:
    """
    Part I violent/property incident counts within a circle for one calendar year.
    Only initial reports (II, VI) are counted, each incident once, so supplemental
    reports and multi-code incidents don't double-count.
    """
    base = (
        f"within_circle(point, {lat}, {lon}, {radius_m}) "
        f"AND report_type_code in ('II', 'VI') AND " + _year_bounds(year, "incident_datetime")
    )
    v = _socrata_count(_SF_SOCRATA, "count(distinct incident_id)", f"{base} AND {_SF_VIOLENT_WHERE}", "SF")
    p = _socrata_count(_SF_SOCRATA, "count(distinct incident_id)", f"{base} AND {_SF_PROPERTY_WHERE}", "SF")
    if v is None or p is None:
        return None
    return {"violent": v, "property": p}


# ---------------------------------------------------------------------------
# LA Open Data
# ---------------------------------------------------------------------------

def _meters_to_degrees(meters: int) -> float:
    """Approximate conversion of a radius in meters to decimal degrees (lat/lon delta)."""
    return meters / 111_000.0


@cached(ttl_seconds=CACHE_TTL["crime_data"])
def _fetch_la_part1(lat: float, lon: float, radius_m: int, year: int) -> Optional[Dict]:
    """
    Part I violent/property case counts within a bounding box for one calendar
    year.  The NIBRS dataset stores lat/lon as plain columns (within_circle does
    not apply), so a box is used; callers scale the population to the box area.
    """
    d = _meters_to_degrees(radius_m)
    base = (
        f"lat >= {lat - d} AND lat <= {lat + d} AND lon >= {lon - d} AND lon <= {lon + d} AND "
        + _year_bounds(year, "date_occ")
    )
    v = _socrata_count(_LA_SOCRATA, "count(distinct caseno)",
                       f"{base} AND nibr_code in ({_soql_list(_LA_VIOLENT_NIBRS)})", "LA")
    p = _socrata_count(_LA_SOCRATA, "count(distinct caseno)",
                       f"{base} AND nibr_code in ({_soql_list(_LA_PROPERTY_NIBRS)})", "LA")
    if v is None or p is None:
        return None
    return {"violent": v, "property": p}


def _open_data_rates(fetch, source: str, lat: float, lon: float, population: int,
                     radius_m: int) -> Optional[Dict]:
    """Annual Part I rates per 1k from a city open-data source, with YoY trend."""
    year = _open_data_year()
    cur = fetch(lat, lon, radius_m, year)
    if cur is None:
        return None
    if cur["violent"] + cur["property"] < _MIN_INCIDENTS:
        logger.debug("%s crime: too few incidents (%d) — unreliable", source,
                     cur["violent"] + cur["property"])
        return None
    prv = fetch(lat, lon, radius_m, year - 1)

    violent_rate = _per_1k(cur["violent"], population)
    property_rate = _per_1k(cur["property"], population)

    trend_pct: Optional[float] = None
    if prv is not None and prv["violent"] >= 5:
        prv_violent = _per_1k(prv["violent"], population)
        if prv_violent > 0:
            raw_trend = (violent_rate - prv_violent) / prv_violent * 100
            # Cap at ±100% to prevent denominator-blowup nonsense
            trend_pct = round(max(-100.0, min(100.0, raw_trend)), 1)

    return {
        "violent_per_1k": violent_rate,
        "property_per_1k": property_rate,
        "trend_pct": trend_pct,
        "source": source,
        "incidents_current": cur["violent"] + cur["property"],
        "data_period": str(year),
    }


def _get_nyc_rates(lat: float, lon: float, population: int, radius_m: int) -> Optional[Dict]:
    return _open_data_rates(_fetch_nyc_part1, "nyc_open_data", lat, lon, population, radius_m)


def _get_sf_rates(lat: float, lon: float, population: int, radius_m: int) -> Optional[Dict]:
    return _open_data_rates(_fetch_sf_part1, "sf_open_data", lat, lon, population, radius_m)


def _get_la_rates(lat: float, lon: float, population: int, radius_m: int) -> Optional[Dict]:
    import math as _math
    # Bounding box area = (2r)² = 4r²; circle area = π×r².
    # Scale population up by 4/π so per-1k rates are circle-equivalent (matching NYC).
    adj_pop = max(1, int(population * (4.0 / _math.pi)))
    return _open_data_rates(_fetch_la_part1, "la_open_data", lat, lon, adj_pop, radius_m)


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
        resp = requests.get(url, params={"API_KEY": api_key}, timeout=_AGENCIES_TIMEOUT)
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
def _fetch_fbi_agency_rate(
    ori: str, offense_type: str, year: int, agency_name: Optional[str] = None
) -> Optional[Tuple[float, str, Optional[int]]]:
    """
    Fetch an annual crime rate per 100k from the FBI CDE summarized/agency endpoint.
    An agency tier rate may be 0 (e.g. no violent crimes in a small town); callers
    decide whether the agency is actually reporting.  agency_population is the
    FBI service population for the matched agency (None for state/national tiers).

    Returns ``(rate, tier, agency_population)`` where tier is one of:
      ``"agency"``   — per-agency key found (works for NIBRS and UCR-reporting non-NIBRS agencies)
      ``"state"``    — state-level aggregate (fallback when no per-agency key)
      ``"national"`` — US national rate (last-resort)

    Old disk-cache entries may be bare floats; callers handle that via ``_unpack_fbi_rate``.
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
            # CDE returns monthly rates per 100k; annualize by summing the months.
            # If the agency reported fewer than 12 months, scale the mean to a year.
            month_vals = [
                float(v) for v in rates_by_label.get(label, {}).values() if v is not None
            ]
            if not month_vals:
                return None
            return round(sum(month_vals) / len(month_vals) * 12, 2)

        # Tier 2: per-agency key when the caller supplies the expected agency name.
        # Works for NIBRS agencies *and* non-NIBRS agencies that report UCR summary
        # data to the FBI (the CDE response always contains a per-agency Offenses key).
        if agency_name:
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
                    pops = (data.get("populations") or {}).get("population") or {}
                    ag_pops = [
                        float(v) for v in (pops.get(ag_key.replace(" Offenses", "")) or {}).values()
                        if v
                    ]
                    ag_pop = int(sum(ag_pops) / len(ag_pops)) if ag_pops else None
                    logger.debug("FBI CDE agency rate for '%s' %s %d: %.2f", agency_name, offense_type, year, val)
                    return (val, "agency", ag_pop)

        # Tier 3: state-level aggregate.  The response also carries the agency's
        # own series, so pick the non-national series with the largest population.
        pops = (data.get("populations") or {}).get("population") or {}

        def _label_pop(label: str) -> float:
            vals = [float(v) for v in (pops.get(label.replace(" Offenses", "")) or {}).values() if v]
            return max(vals) if vals else 0.0

        state_labels = sorted(
            (l for l in rates_by_label if "Offenses" in l and "United States" not in l),
            key=_label_pop, reverse=True,
        )
        for label in state_labels:
            val = _extract(label)
            if val is not None:
                return (val, "state", None)

        # Last-resort: national rate
        for label in rates_by_label:
            if "United States" in label and "Offenses" in label:
                val = _extract(label)
                if val is not None:
                    return (val, "national", None)
        return None
    except Exception as e:
        logger.warning("FBI CDE rate fetch failed: %s", e)
        return None


def _unpack_fbi_rate(result) -> Tuple[Optional[float], Optional[str]]:
    """Unpack (rate, tier) from _fetch_fbi_agency_rate, handling legacy bare-float cache entries."""
    if result is None:
        return None, None
    if isinstance(result, (list, tuple)) and len(result) >= 2:
        return result[0], result[1]
    # Legacy disk-cache entry: bare float
    return float(result), "state"


# Keep the old name as an alias so existing callers don't break
def _fetch_fbi_state_rate(ori: str, offense_type: str, year: int) -> Optional[float]:
    rate, _ = _unpack_fbi_rate(_fetch_fbi_agency_rate(ori, offense_type, year))
    return rate


# Generic place-type words that appear in both city names and agency names but
# don't identify a specific jurisdiction.  Excluded from city-name → agency-name
# matching so that "Rye City" doesn't match "Johnson City Village PD" via "City".
_CITY_HINT_GENERIC = frozenset({
    "city", "town", "village", "county", "township", "borough",
})

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
    "university",           # e.g. "University of California: San Francisco"
    "community college",    # e.g. "San Jose/Evergreen Community College"
    "school district",
    "highway patrol",       # CHP area offices patrol freeways, not neighborhoods
    "campus police",
    "stevens institute",
    "housing authority",
    "transit district",
    "rapid transit",
    "bart",
    "fire protection",
    "fire department",
    "department of forestry",
    "state park",
    "park police",
    "park department",
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

# CA suburbs → exact FBI agency name for the law enforcement agency that serves them.
# Used when _find_nearest_agency picks the wrong agency (bad lat/lon in FBI DB) or
# when the city's own PD is absent from the FBI database.
# Only include agencies confirmed to report real (non-zero) data to the FBI.
_CA_SUBURB_TO_AGENCY: Dict[str, str] = {
    # Unincorporated Alameda County — served by Alameda County Sheriff
    "castro valley":  "Alameda County Sheriff's Office",
    # Unincorporated Contra Costa County — served by Contra Costa Sheriff
    "alamo":          "Contra Costa County Sheriff's Office",
    # San Mateo County: unincorporated + small cities whose PD is absent from FBI DB
    "half moon bay":  "San Mateo County Sheriff's Office",
    "woodside":       "San Mateo County Sheriff's Office",
    "portola valley": "San Mateo County Sheriff's Office",
    "san carlos":     "San Mateo County Sheriff's Office",
    "millbrae":       "San Mateo County Sheriff's Office",
    # Marin County: Central Marin PD is the consolidated agency for Corte Madera + Larkspur
    "corte madera":   "Central Marin Police Department",
    "larkspur":       "Central Marin Police Department",
    # Marin County unincorporated — served by Marin County Sheriff
    "kentfield":      "Marin County Sheriff's Office",
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


_AGENCY_NAME_SUFFIX_WORDS = frozenset({
    "police", "department", "dept", "sheriff", "sheriff's", "public", "safety", "pd",
    "bureau", "division", "township", "twp", "village", "vg", "city", "town", "borough", "county",
})
_PLACE_PREFIX_RE = re.compile(r"^(?:city|town|township|village|borough)\s+of\s+", re.IGNORECASE)


def _agency_place_name(agency_name: str) -> str:
    """Place an agency is named for: "Twentynine Palms Police Department" ->
    "twentynine palms", "Weehawken Township Police Department" -> "weehawken"."""
    words = _PLACE_PREFIX_RE.sub("", agency_name or "").lower().split()
    place = []
    for w in words:
        if w in _AGENCY_NAME_SUFFIX_WORDS:
            break
        place.append(w)
    return " ".join(place)


def _find_nibrs_agency_by_name(
    agencies: list, city_hint: str, lat: Optional[float] = None, lon: Optional[float] = None,
) -> Optional[Dict]:
    """
    Scan all agencies for a PD named for exactly this place (so "Palms" never
    matches Twentynine Palms and "Rye" never matches Rye Brook).  NIBRS reporters are preferred, but legacy-UCR agencies (e.g.
    Oakland PD) are still returned since CDE publishes their per-agency rates.  Used as a fallback when _find_nearest_agency
    selects the wrong agency due to bad lat/lon data in the FBI database.

    Prefers city police departments over county sheriffs so that an incorporated
    city like Santa Clara gets its own PD rather than the county sheriff.

    When lat/lon are given, agencies with coordinates more than 50 km away are
    rejected so a same-named PD elsewhere in the state (Montclair in Oakland vs
    Montclair PD in San Bernardino County) is never matched.
    """
    if not city_hint or not agencies:
        return None
    place = _PLACE_PREFIX_RE.sub("", city_hint).strip().lower()
    if len(place) < 3:
        return None
    candidates = [
        ag for ag in agencies
        if not _is_special_purpose_agency(
            (ag.get("agency_name") or ag.get("agencyName") or "").lower()
        )
        and _agency_place_name(ag.get("agency_name") or ag.get("agencyName") or "") == place
    ]
    if lat is not None and lon is not None:
        def _near(ag: Dict) -> bool:
            ag_lat = ag.get("latitude") or ag.get("lat")
            ag_lon = ag.get("longitude") or ag.get("lng") or ag.get("lon")
            if ag_lat is None or ag_lon is None:
                return True
            try:
                return _haversine_km(lat, lon, float(ag_lat), float(ag_lon)) <= 50
            except (TypeError, ValueError):
                return True
        candidates = [ag for ag in candidates if _near(ag)]
    if not candidates:
        return None
    # Prefer city police departments over county sheriffs / other agencies,
    # and NIBRS reporters over legacy-UCR agencies.
    def _rank(ag: Dict) -> Tuple[int, int]:
        name = (ag.get("agency_name") or ag.get("agencyName") or "").lower()
        is_pd = "police department" in name or "police dept" in name
        return (0 if is_pd else 1, 0 if ag.get("is_nibrs") else 1)
    return min(candidates, key=_rank)


@cached(ttl_seconds=CACHE_TTL["crime_data"])
def _fetch_ny_state_agency_row(
    town_keyword: str, county: Optional[str], year: int
) -> Optional[Dict]:
    """
    Query the NY State UCR per-agency dataset for a specific town in a county.

    Excludes county-wide entries ("County Total", "County PD", "County Sheriff",
    "State Police") so we always get a single-municipality figure.

    Pass county=None to search across all NY counties (used when the geo-matched
    agency county is suspect, e.g. cross-county-border geo matches).

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
        params: Dict[str, str] = {
            "$where": where,
            "year": str(year),
            "$order": "months_reported DESC, violent DESC",
            "$limit": 20,
        }
        if county:
            params["county"] = county.title()
        resp = requests.get(_NY_STATE_CRIME_DS, params=params, timeout=_REQUEST_TIMEOUT)
        if resp.status_code != 200:
            logger.debug("NY state crime DS returned %d for %s/%s", resp.status_code, town_keyword, county)
            return None
        data = resp.json()
        if not data:
            return None
        # Prefer an agency whose town name equals the keyword, so "Rye" picks
        # "Rye City PD" rather than "Rye Brook Vg PD".
        kw = town_keyword.strip().lower()
        row = next(
            (r for r in data if _ny_town_keyword(r.get("agency", "")).lower() == kw),
            data[0],
        )
        months = int(row.get("months_reported", 0) or 0)
        if months < 10:
            return None  # reject partial-year reports
        return row
    except Exception as e:
        logger.warning("NY state crime fetch failed for '%s'/%s: %s", town_keyword, county, e)
        return None


def _ny_town_keyword(ny_agency: str) -> str:
    """"Yonkers City PD" → "Yonkers", "Rye Brook Vg PD" → "Rye Brook"."""
    return re.sub(r"\s+(City|Vg|Village|Town|Twn)?\s*PD$", "", ny_agency or "", flags=re.IGNORECASE).strip()


def _agency_population_by_name(
    agencies: list, town: str, lat: float, lon: float, year: int
) -> Optional[int]:
    """FBI service population for the municipal agency named after `town`
    (e.g. "Yonkers" → Yonkers Police Department), or None if not found."""
    if not town or not agencies:
        return None
    ag = _find_nibrs_agency_by_name(agencies, town, lat, lon)
    if not ag:
        return None
    ag_name = ag.get("agency_name") or ag.get("agencyName") or ""
    for y in (year, year - 1):
        res = _fetch_fbi_agency_rate(ag.get("ori") or ag.get("ORI"), "violent-crime", y, ag_name)
        if res and len(res) >= 3 and res[1] == "agency" and res[2]:
            return int(res[2])
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
    "Suffolk County PD": 1_200_000,  # Suffolk County — towns w/o own PD (Babylon, Islip, Brookhaven, Smithtown, Huntington)
}

# Villages/hamlets in NY policed by a covering town PD that reports to the state UCR.
# Key: city_hint (lowercase).  Value: (town_keyword, county, town_population).
# town_population is the full agency service population so per-1k rates are correct.
_NY_VILLAGE_TO_TOWN_PD: Dict[str, tuple] = {
    "nyack": ("Orangetown", "Rockland", 50_000),  # Nyack Village is within Town of Orangetown
}


@cached(ttl_seconds=CACHE_TTL["crime_data"])
def _fetch_ny_state_nassau_pd(year: int) -> Optional[Dict]:
    """
    Fetch Nassau County PD crime row for unincorporated Nassau communities.
    Bypasses the standard _fetch_ny_state_agency_row filter that excludes
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


@cached(ttl_seconds=CACHE_TTL["crime_data"])
def _fetch_ny_state_suffolk_pd(year: int) -> Optional[Dict]:
    """
    Fetch Suffolk County PD crime row for unincorporated Suffolk communities
    (Babylon, Islip, Brookhaven, Smithtown, Huntington towns) that lack a
    dedicated town-level PD in the state UCR dataset.
    """
    try:
        params = {
            "$where": "upper(agency) = 'SUFFOLK COUNTY PD'",
            "county": "Suffolk",
            "year": str(year),
            "$limit": 1,
        }
        resp = requests.get(_NY_STATE_CRIME_DS, params=params, timeout=_REQUEST_TIMEOUT)
        if resp.status_code != 200:
            return None
        data = resp.json()
        if not data:
            return None
        return data[0]
    except Exception as e:
        logger.warning("Suffolk County PD fetch failed for year %d: %s", year, e)
        return None


def _get_fbi_rates(
    lat: float, lon: float, state_abbr: str, population: int,
    city_hint: Optional[str] = None,
    fallback_city: Optional[str] = None,
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
        # Strip Nominatim prefixes ("Village of Ardsley" → "Ardsley", "Town of X" → "X")
        _city_kw = re.sub(r"^(?:Village|Town|City|Hamlet)\s+of\s+", "", city_hint, flags=re.IGNORECASE).strip()
        if county:
            ny_row = _fetch_ny_state_agency_row(_city_kw, county, data_year)
            if ny_row is None:
                ny_row = _fetch_ny_state_agency_row(_city_kw, county, data_year - 1)

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
                        ny_row = _fetch_ny_state_agency_row(town_kw, county, data_year)
                        if ny_row is None:
                            ny_row = _fetch_ny_state_agency_row(town_kw, county, data_year - 1)

            # Tier 3a: village-to-town mapping — villages policed by a covering
            # town PD that reports to the state UCR (e.g. Nyack → Orangetown).
            if ny_row is None:
                town_entry = _NY_VILLAGE_TO_TOWN_PD.get(_city_kw.lower())
                if town_entry:
                    town_kw, town_county, town_pop = town_entry
                    ny_row = _fetch_ny_state_agency_row(town_kw, town_county, data_year)
                    if ny_row is None:
                        ny_row = _fetch_ny_state_agency_row(town_kw, town_county, data_year - 1)
                    if ny_row is not None:
                        prev_town = _fetch_ny_state_agency_row(
                            ny_row.get("agency", town_kw)[:20], town_county, int(ny_row["year"]) - 1
                        )
                        logger.debug(
                            "NY state UCR: village→town fallback '%s'→'%s' for '%s' (pop=%d)",
                            _city_kw, town_kw, city_hint, town_pop,
                        )
                        return _rates_from_ny_state(ny_row, prev_town, town_pop)

            # Tier 3b Nassau fallback: unincorporated Nassau communities are served
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

            # Tier 3c Suffolk fallback: western Suffolk towns (Babylon, Islip,
            # Brookhaven, Smithtown, Huntington) lack their own town PD in the
            # UCR and are served by Suffolk County PD.
            if ny_row is None and county.lower() == "suffolk":
                suffolk_row = _fetch_ny_state_suffolk_pd(data_year)
                if suffolk_row is None:
                    suffolk_row = _fetch_ny_state_suffolk_pd(data_year - 1)
                if suffolk_row is not None:
                    prev_suffolk = _fetch_ny_state_suffolk_pd(int(suffolk_row["year"]) - 1)
                    suffolk_pop = _NY_COUNTY_PD_POPULATIONS.get("Suffolk County PD", population)
                    logger.debug(
                        "NY state UCR: Suffolk County PD fallback for '%s' (pop=%d)",
                        city_hint, suffolk_pop,
                    )
                    return _rates_from_ny_state(suffolk_row, prev_suffolk, suffolk_pop)

            if ny_row is None and county:
                # Cross-county-border fallback: geo-matched agency may be in the
                # wrong county (e.g. Tarrytown VPD selected for Nyack). Try the
                # city keyword without a county filter across all NY agencies.
                ny_row = _fetch_ny_state_agency_row(_city_kw, None, data_year)
                if ny_row is None:
                    ny_row = _fetch_ny_state_agency_row(_city_kw, None, data_year - 1)
                if ny_row is not None:
                    logger.debug(
                        "NY state UCR: county-agnostic fallback matched '%s' for '%s' (geo-county was %s)",
                        ny_row.get("agency"), city_hint, county,
                    )

            if ny_row is not None:
                prev_ny_row = _fetch_ny_state_agency_row(
                    ny_row.get("agency", city_hint)[:20], county, int(ny_row["year"]) - 1
                )
                # State UCR counts cover the whole municipality, so divide by the
                # agency's FBI service population rather than the local disk estimate
                # (a 1 km disk around Yonkers holds ~30k of its ~210k residents).
                juris_pop = _agency_population_by_name(
                    agencies, _ny_town_keyword(ny_row.get("agency", "")), lat, lon, int(ny_row["year"])
                )
                return _rates_from_ny_state(ny_row, prev_ny_row, juris_pop or population)
            logger.debug(
                "NY state UCR: no per-agency row for '%s' in %s; falling back to CDE state rate",
                city_hint, county,
            )

    # -----------------------------------------------------------------------
    # Tier 2/3: FBI CDE.  For NIBRS-reporting agencies, pass the agency name
    # so _fetch_fbi_agency_rate can extract per-agency rates rather than the state
    # aggregate.  For non-NIBRS agencies, agency_name_hint stays None and the
    # function falls through to the state-level rate.
    # -----------------------------------------------------------------------
    is_nibrs = bool(agency.get("is_nibrs"))
    agency_display_name = agency.get("agencyName") or agency.get("agency_name") or ""

    # Guard: only use per-agency data when we're confident the right agency was
    # matched.  _find_nearest_agency picks by distance, so verify the city_hint
    # (e.g. "Beverly Hills") actually appears in the agency name.  Works for
    # both NIBRS reporters and legacy UCR summary reporters.
    nibrs_city_match = (
        city_hint
        and any(
            word.lower() in agency_display_name.lower()
            for word in (city_hint or "").split()
            if len(word) >= 3 and word.lower() not in _CITY_HINT_GENERIC
        )
    )

    # Tier 2b: unincorporated suburb → parent municipality matching.
    # e.g. "Short Hills" → "Millburn", "Cos Cob" → "Greenwich"
    if not nibrs_city_match and city_hint:
        parent_city = _SUBURB_TO_PARENT_CITY.get(city_hint.lower())
        if parent_city:
            parent_match = any(
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
    # Also tries the parent municipality and the geocoded jurisdiction city, so a
    # neighborhood ("Rockridge", "Ballard") resolves to its city PD.
    if not nibrs_city_match and agencies:
        _name_hints = [
            h for h in (
                city_hint,
                _SUBURB_TO_PARENT_CITY.get((city_hint or "").lower()),
                fallback_city,
            ) if h
        ]
        for _hint in _name_hints:
            name_match_agency = _find_nibrs_agency_by_name(agencies, _hint, lat, lon)
            if name_match_agency:
                ori = name_match_agency.get("ori") or name_match_agency.get("ORI")
                agency_display_name = (
                    name_match_agency.get("agencyName") or name_match_agency.get("agency_name") or ""
                )
                is_nibrs = bool(name_match_agency.get("is_nibrs"))
                nibrs_city_match = True
                logger.debug(
                    "FBI CDE: name-based fallback for '%s' → %s (ORI %s)",
                    _hint, agency_display_name, ori,
                )
                break

    # Tier 2c: CA explicit suburb → serving agency.
    # Handles unincorporated communities (served by county sheriff) and small cities
    # whose own PD is absent from the FBI database.  Only agencies confirmed to
    # report real non-zero data are listed in _CA_SUBURB_TO_AGENCY.
    if not nibrs_city_match and city_hint and state_abbr.upper() == "CA":
        ca_agency_name = _CA_SUBURB_TO_AGENCY.get(city_hint.lower())
        if ca_agency_name:
            ca_ag = next(
                (ag for ag in agencies
                 if (ag.get("agency_name") or ag.get("agencyName") or "").lower()
                 == ca_agency_name.lower()),
                None,
            )
            if ca_ag:
                ori = ca_ag.get("ori") or ca_ag.get("ORI") or ori
                agency_display_name = ca_ag.get("agency_name") or ca_ag.get("agencyName") or agency_display_name
                is_nibrs = bool(ca_ag.get("is_nibrs"))
                nibrs_city_match = True
                logger.debug(
                    "FBI CDE: CA suburb '%s' → explicit agency %s (NIBRS=%s, ORI %s)",
                    city_hint, agency_display_name, is_nibrs, ori,
                )

    agency_name_hint = agency_display_name if nibrs_city_match else None

    def _agency_year(year: int):
        """Per-agency (violent, property) results for a year, or None when the
        agency did not report.  Zero violent crime is valid for a small town as
        long as the agency reported some crime that year."""
        v_res = _fetch_fbi_agency_rate(ori, "violent-crime", year, agency_name_hint)
        p_res = _fetch_fbi_agency_rate(ori, "property-crime", year, agency_name_hint)
        v_rate, v_tier = _unpack_fbi_rate(v_res)
        p_rate, p_tier = _unpack_fbi_rate(p_res)
        if v_tier == "agency" and p_tier == "agency" and (v_rate or 0) + (p_rate or 0) > 0:
            return v_res, p_res
        return None

    # FBI per-agency data is released 12-18 months after year end; non-NIBRS
    # legacy-UCR agencies often lag 2-3 years.  Walk back up to 3 years to find
    # the most recent year with per-agency data before falling back to state aggregate.
    v_result = p_result = None
    if agency_name_hint:
        for _year in range(data_year, data_year - 4, -1):
            _found = _agency_year(_year)
            if _found:
                v_result, p_result = _found
                prev_year = _year - 1
                break

    if v_result is None:
        agency_name_hint = None
        v_result = _fetch_fbi_agency_rate(ori, "violent-crime", data_year, None)
        if v_result is None:
            v_result = _fetch_fbi_agency_rate(ori, "violent-crime", prev_year, None)
            prev_year -= 1
        if v_result is None:
            return None
        p_result = _fetch_fbi_agency_rate(ori, "property-crime", prev_year + 1, None)

    violent_rate_100k, violent_tier = _unpack_fbi_rate(v_result)
    property_rate_100k, _ = _unpack_fbi_rate(p_result)

    # Convert per-100k → per-1k
    violent_rate = round(violent_rate_100k / 100.0, 3)
    property_rate = round((property_rate_100k or 0.0) / 100.0, 3)

    # Trend: compare current year violent to prior year
    trend_pct: Optional[float] = None
    pv_result = _fetch_fbi_agency_rate(ori, "violent-crime", prev_year, agency_name_hint)
    prev_violent_100k, prev_tier = _unpack_fbi_rate(pv_result)
    if prev_violent_100k and prev_violent_100k > 0 and prev_tier == violent_tier:
        raw_trend = (violent_rate_100k - prev_violent_100k) / prev_violent_100k * 100
        trend_pct = round(max(-100.0, min(100.0, raw_trend)), 1)

    # Source reflects actual data tier returned by _fetch_fbi_agency_rate:
    #   "agency" tier → per-agency key was found in the CDE response
    #   "state"/"national" tier → only state/national aggregate was available
    if nibrs_city_match and violent_tier == "agency":
        source = "fbi_nibrs_agency" if is_nibrs else "fbi_ucr_agency"
    else:
        # FBI CDE has no per-agency data for this location.  For CA cities,
        # try the CA DOJ "Crimes and Clearances" dataset which covers all CA
        # LEAs regardless of NIBRS participation.
        if city_hint and state_abbr.upper() == "CA":
            # DOJ counts cover the whole city: only use them when the place is that
            # city (a neighborhood like Oakland's "Montclair" must not match Montclair
            # in San Bernardino County), and divide by the city's FBI service population.
            doj_city = city_hint
            same_city = not fallback_city or fallback_city.strip().lower() == city_hint.strip().lower()
            ca_doj = None
            if same_city:
                doj_pop = population
                if doj_city.strip().lower() not in _CA_DOJ_SERVING_AGENCIES:
                    doj_pop = _agency_population_by_name(agencies, doj_city, lat, lon, data_year) or population
                ca_doj = _get_ca_doj_rates(doj_city, doj_pop, data_year)
            if ca_doj:
                logger.debug(
                    "CA DOJ fallback for '%s': violent=%.3f property=%.3f (year %d)",
                    city_hint, ca_doj["violent_per_1k"], ca_doj["property_per_1k"],
                    ca_doj.get("data_year", data_year),
                )
                return ca_doj
        source = "fbi_cde_state"

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
    """Search radius in meters by area type (must match main.py community_safety disk)."""
    at = (area_type or "").lower()
    if "rural" in at:
        return 8000
    if "exurban" in at:
        return 5000
    if "suburban" in at:
        return 2000
    # urban_residential contains "urban" — check before generic urban branch
    if "urban_residential" in at:
        return 1000
    if "urban_core" in at:
        return 800
    if "urban" in at:
        return 800
    return 1500


def open_data_city(lat: float, lon: float) -> Optional[str]:
    """'nyc' / 'la' / 'sf' when the point is inside a city whose police publish
    incident-level open data, else None."""
    boxes = (("nyc", _NYC_BBOX), ("la", _LA_BBOX), ("sf", _SF_BBOX))
    key = next(
        (k for k, (la0, lo0, la1, lo1) in boxes if la0 <= lat <= la1 and lo0 <= lon <= lo1),
        None,
    )
    if key is None:
        return None
    from data_sources.census_api import get_incorporated_place_geoid

    geoid = get_incorporated_place_geoid(round(lat, 5), round(lon, 5))
    if geoid is None:
        return key  # boundary lookup failed: fall back to the bbox
    return key if geoid == _OPEN_DATA_CITY_GEOID[key] else None


def community_safety_crime_radius_m(area_type: Optional[str]) -> int:
    """Public alias: crime query radius in meters (same footprint as population denominator)."""
    return _radius_for_area_type(area_type)


def get_crime_rates(
    lat: float,
    lon: float,
    *,
    city: Optional[str] = None,
    state_abbr: Optional[str] = None,
    area_type: Optional[str] = None,
    population: int = 10000,
    fallback_city: Optional[str] = None,
    radius_m: Optional[int] = None,
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
        fallback_city: Jurisdiction city to try for agency matching when `city` is a
                       neighborhood name (e.g. "Rockridge" → "Oakland").
        radius_m:      Incident-search radius for open-data cities (default: by area type).
    """
    if radius_m is None:
        radius_m = community_safety_crime_radius_m(area_type)

    # Route by coordinates — handles sub-neighborhoods that aren't named cities
    open_city = open_data_city(lat, lon)
    if open_city:
        getter = {"nyc": _get_nyc_rates, "la": _get_la_rates, "sf": _get_sf_rates}[open_city]
        result = getter(lat, lon, population, radius_m)
        if result:
            return result

    # LASD station data: CA cities that contract with LA County Sheriff
    if city:
        lasd_station = _LASD_CITY_TO_STATION.get(city.lower())
        if lasd_station:
            result = _get_lasd_rates(lasd_station, population)
            if result:
                return result

    # FBI CDE + NY State UCR fallback for all other jurisdictions
    if state_abbr:
        # Geocoder returns full state names ("California") — convert to 2-letter code
        _abbr = state_abbr.strip()
        if len(_abbr) > 2:
            from data_sources.geocoding import STATE_ABBREVIATIONS
            _abbr = STATE_ABBREVIATIONS.get(_abbr.lower(), _abbr)
        result = _get_fbi_rates(
            lat, lon, _abbr, population, city_hint=city, fallback_city=fallback_city,
        )
        if result:
            return result

    logger.debug("crime_api: no data source found — coming_soon (city=%s state=%s)", city, state_abbr)
    return {"coming_soon": True}
