"""
NOAA Climate Data Online (CDO) API client.
Fetches 1991-2020 monthly climate normals for the nearest station to a lat/lon.
This is purely descriptive data — not scored, surfaced like status_signal.

Requires NOAA_CDO_API_KEY env var (free: https://www.ncdc.noaa.gov/cdo-web/token).
Gracefully degrades to None if key absent or API unavailable.
"""

import os
import time
import requests
from typing import Optional, Dict, Any, List
from logging_config import get_logger

logger = get_logger(__name__)

NOAA_CDO_BASE = "https://www.ncdc.noaa.gov/cdo-web/api/v2"
NOAA_CDO_API_KEY = os.getenv("NOAA_CDO_API_KEY", "")

# Monthly normal data types we care about
_DATATYPES = "MLY-TMAX-NORMAL,MLY-TMIN-NORMAL,MLY-PRCP-NORMAL,MLY-SNOW-NORMAL"

_MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# Simple in-process LRU-style cache keyed by rounded (lat, lon)
_STATION_CACHE: Dict[str, str] = {}
_PROFILE_CACHE: Dict[str, Optional[Dict]] = {}


def _noaa_get(path: str, params: Dict[str, Any], timeout: int = 10) -> Optional[Dict]:
    if not NOAA_CDO_API_KEY:
        return None
    try:
        r = requests.get(
            f"{NOAA_CDO_BASE}{path}",
            params=params,
            headers={"token": NOAA_CDO_API_KEY},
            timeout=timeout,
        )
        if r.status_code == 200:
            return r.json()
        logger.debug(f"NOAA CDO {path} returned {r.status_code}")
        return None
    except Exception as e:
        logger.debug(f"NOAA CDO request failed (non-fatal): {e}")
        return None


def _find_nearest_station(lat: float, lon: float) -> Optional[str]:
    """Return the GHCND station ID with monthly normal data nearest to lat/lon."""
    cache_key = f"{round(lat, 2)},{round(lon, 2)}"
    if cache_key in _STATION_CACHE:
        return _STATION_CACHE[cache_key]

    delta = 2.0  # Search within ~2° bounding box (~200km)
    params = {
        "datasetid": "NORMAL_MLY",
        "datatypeid": "MLY-TMAX-NORMAL",
        "extent": f"{lat - delta},{lon - delta},{lat + delta},{lon + delta}",
        "limit": 25,
    }
    data = _noaa_get("/stations", params)
    if not data or not data.get("results"):
        logger.debug(f"NOAA: no stations found near {lat},{lon}")
        return None

    # Pick the station with the minimum Euclidean distance to the target
    best_id = None
    best_dist = float("inf")
    for s in data["results"]:
        slat = s.get("latitude")
        slon = s.get("longitude")
        if slat is None or slon is None:
            continue
        dist = (slat - lat) ** 2 + (slon - lon) ** 2
        if dist < best_dist:
            best_dist = dist
            best_id = s.get("id")

    if best_id:
        _STATION_CACHE[cache_key] = best_id
    return best_id


def _fetch_normals(station_id: str) -> Optional[Dict[str, Any]]:
    """Fetch 12-month normals for a station. Returns structured monthly data."""
    params = {
        "datasetid": "NORMAL_MLY",
        "stationid": station_id,
        "datatypeid": _DATATYPES,
        # NORMAL_MLY uses year 2010 as a proxy for the 30-year normal period
        "startdate": "2010-01-01",
        "enddate": "2010-12-01",
        "limit": 200,
    }
    data = _noaa_get("/data", params)
    if not data or not data.get("results"):
        return None

    # Pivot results into per-month dict keyed by (month_index, datatype)
    monthly: Dict[int, Dict[str, Any]] = {i: {} for i in range(1, 13)}
    for item in data["results"]:
        date_str = item.get("date", "")
        try:
            month = int(date_str[5:7])  # "2010-03-01" → 3
        except (ValueError, IndexError):
            continue
        dtype = item.get("datatype", "")
        value = item.get("value")
        if value is not None and month in monthly:
            monthly[month][dtype] = value

    # Build output: list of 12 dicts, one per month
    months_out: List[Dict[str, Any]] = []
    for i in range(1, 13):
        m = monthly[i]

        def _temp_f(raw) -> Optional[float]:
            # NOAA normals are in tenths of °F
            if raw is None:
                return None
            try:
                v = float(raw)
                return round(v / 10.0, 1) if v != -9999.0 and v != -7777.0 else None
            except (TypeError, ValueError):
                return None

        def _precip_in(raw) -> Optional[float]:
            # NOAA precip normals: hundredths of inches
            if raw is None:
                return None
            try:
                v = float(raw)
                return round(v / 100.0, 2) if v != -9999.0 and v != -7777.0 else None
            except (TypeError, ValueError):
                return None

        tmax = _temp_f(m.get("MLY-TMAX-NORMAL"))
        tmin = _temp_f(m.get("MLY-TMIN-NORMAL"))
        prcp = _precip_in(m.get("MLY-PRCP-NORMAL"))
        snow = _precip_in(m.get("MLY-SNOW-NORMAL"))

        months_out.append({
            "month": i,
            "month_name": _MONTH_NAMES[i - 1],
            "avg_high_f": tmax,
            "avg_low_f": tmin,
            "avg_precip_in": prcp,
            "avg_snow_in": snow,
            "comfort": _comfort_label(tmax, prcp),
        })

    return {
        "station_id": station_id,
        "normals_period": "1991-2020",
        "months": months_out,
    }


def _comfort_label(avg_high_f: Optional[float], avg_precip_in: Optional[float]) -> str:
    """Derive a simple comfort band from average high temp and monthly precipitation."""
    if avg_high_f is None:
        return "unknown"
    precip = avg_precip_in or 0.0
    if avg_high_f >= 90:
        return "hot"
    if avg_high_f >= 75:
        return "warm" if precip < 4.0 else "warm_wet"
    if avg_high_f >= 55:
        return "pleasant" if precip < 4.0 else "mild_wet"
    if avg_high_f >= 35:
        return "cool"
    return "cold"


def get_climate_profile(lat: float, lon: float) -> Optional[Dict[str, Any]]:
    """
    Return monthly climate normals for the nearest NOAA station.
    Returns None if API key is missing or station lookup fails.
    Result is non-blocking — callers should run in a thread and tolerate None.
    """
    if not NOAA_CDO_API_KEY:
        return None

    cache_key = f"{round(lat, 2)},{round(lon, 2)}"
    if cache_key in _PROFILE_CACHE:
        return _PROFILE_CACHE[cache_key]

    t0 = time.perf_counter()
    station_id = _find_nearest_station(lat, lon)
    if not station_id:
        _PROFILE_CACHE[cache_key] = None
        return None

    profile = _fetch_normals(station_id)
    elapsed = time.perf_counter() - t0
    logger.info(f"[TIMING] noaa_climate_profile {elapsed:.3f}s station={station_id}")

    _PROFILE_CACHE[cache_key] = profile
    return profile
