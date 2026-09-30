"""
People present in a place: residents plus workers for the share of the week
they are at work.  community_safety divides crime by this everywhere (city
neighborhoods, towns, and the national comparison scale) so a job center isn't
charged its crime against residents alone.

    people_present = max(residents, residents + WORK_WEEK_SHARE * (jobs_here - resident_workers))

Town-level counts come from ACS 5-year: B01003 (residents), B08604 (workers whose
workplace is here), B08301 (resident workers), available for every US place,
county subdivision, and county.  Visitors (tourists, shoppers, nightlife) are not
in any national dataset and are not counted.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional, Tuple

from data_sources.cache import CACHE_TTL, cached
from logging_config import get_logger

logger = get_logger(__name__)

# ~45 of 168 hours a week at the workplace.
WORK_WEEK_SHARE = 45.0 / 168.0

_TIGERWEB_CURRENT = "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/tigerWMS_Current/MapServer"
_LAYER_INCORPORATED_PLACES = 28
_LAYER_CDP = 30
_LAYER_COUNTY_SUBDIVISIONS = 22
_LAYER_COUNTIES = 82

_ACS_YEAR = 2022
_ACS_FIELDS = "B01003_001E,B08604_001E,B08301_001E"


def people_present(residents: float, jobs_here: float, resident_workers: float) -> float:
    """Residents plus workers for their share of the week, never below residents."""
    return max(float(residents), float(residents) + WORK_WEEK_SHARE * (float(jobs_here) - float(resident_workers)))


@cached(ttl_seconds=CACHE_TTL["census_data"])
def _geography_at(layer: int, lat: float, lon: float) -> Optional[Dict[str, str]]:
    """Attributes (GEOID, NAME) of the TIGERweb feature containing the point;
    {} when none, None when the lookup failed."""
    from data_sources.census_api import _make_post_request_with_retry

    data = {
        "f": "json",
        "geometry": json.dumps({"x": lon, "y": lat, "spatialReference": {"wkid": 4326}}),
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "GEOID,NAME",
        "returnGeometry": "false",
    }
    resp = _make_post_request_with_retry(f"{_TIGERWEB_CURRENT}/{layer}/query", data, timeout=30)
    if resp is None:
        return None
    try:
        feats = resp.json().get("features")
    except Exception:
        return None
    if feats is None:
        return None
    return {k: str(v) for k, v in feats[0]["attributes"].items()} if feats else {}


@cached(ttl_seconds=CACHE_TTL["census_data"])
def _acs_worker_counts(level: str, state_fips: str, county_fips: str = "") -> Dict[str, Tuple[int, int, int]]:
    """GEOID -> (residents, jobs_here, resident_workers) for every geography of `level`
    ('place', 'county subdivision', 'county') in a state (and county for subdivisions)."""
    import requests
    from data_sources.census_api import CENSUS_API_KEY, CENSUS_BASE_URL

    params = {"get": _ACS_FIELDS, "for": f"{level}:*", "in": f"state:{state_fips}", "key": CENSUS_API_KEY}
    if level == "county subdivision":
        params["in"] = f"state:{state_fips} county:{county_fips}"
    try:
        resp = requests.get(f"{CENSUS_BASE_URL}/{_ACS_YEAR}/acs/acs5", params=params, timeout=60)
        rows = resp.json() if resp.status_code == 200 else []
    except Exception as e:
        logger.warning("ACS worker counts failed for %s %s: %s", level, state_fips, e)
        return {}
    if len(rows) < 2:
        return {}
    header = rows[0]
    geo_cols = [c for c in ("state", "county", "county subdivision", "place") if c in header]
    out: Dict[str, Tuple[int, int, int]] = {}
    for row in rows[1:]:
        try:
            pop, jobs, rw = (int(row[header.index(f)]) for f in _ACS_FIELDS.split(","))
        except (TypeError, ValueError):
            continue
        geoid = "".join(row[header.index(c)] for c in geo_cols)
        out[geoid] = (pop, jobs, rw)
    return out


def people_present_multiplier(lat: float, lon: float, jurisdiction: str = "municipal") -> Tuple[float, Dict[str, Any]]:
    """
    people_present / residents for the jurisdiction containing the point:
    the city/town (incorporated place, else census-designated place, else county
    subdivision) for municipal agencies, the county for county agencies.
    Returns (1.0, meta) when the geography or counts are unavailable.
    """
    meta: Dict[str, Any] = {"jurisdiction": jurisdiction, "work_week_share": round(WORK_WEEK_SHARE, 3)}
    lat, lon = round(float(lat), 5), round(float(lon), 5)
    if jurisdiction == "county":
        layers = ((_LAYER_COUNTIES, "county"),)
    else:
        layers = ((_LAYER_INCORPORATED_PLACES, "place"), (_LAYER_CDP, "place"), (_LAYER_COUNTY_SUBDIVISIONS, "county subdivision"))
    for layer, level in layers:
        geo = _geography_at(layer, lat, lon)
        if not geo or not geo.get("GEOID"):
            continue
        geoid = geo["GEOID"]
        counts = _acs_worker_counts(level, geoid[:2], geoid[2:5] if level == "county subdivision" else "")
        row = counts.get(geoid)
        if not row or row[0] <= 0:
            continue
        residents, jobs, rw = row
        mult = people_present(residents, jobs, rw) / residents
        meta.update({"geography": geo.get("NAME"), "geoid": geoid, "residents": residents,
                     "jobs_here": jobs, "resident_workers": rw, "multiplier": round(mult, 4)})
        return mult, meta
    meta["multiplier"] = 1.0
    meta["skip_reason"] = "geography_or_counts_unavailable"
    return 1.0, meta
