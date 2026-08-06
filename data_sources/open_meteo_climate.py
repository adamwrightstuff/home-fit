"""
Open-Meteo ERA5 reanalysis client for monthly climate normals.
Free, no API key, gridded data (no station coverage gaps).

Uses daily variables for temp/precip/snow/sunshine/wind and hourly for humidity,
then averages into 12 monthly normals.
"""

import time
import requests
from collections import defaultdict
from typing import Optional, Dict, Any, List

from logging_config import get_logger

logger = get_logger(__name__)

ARCHIVE_BASE = "https://archive-api.open-meteo.com/v1/archive"

_DAILY_VARS = [
    "temperature_2m_max",
    "temperature_2m_min",
    "precipitation_sum",
    "snowfall_sum",
    "sunshine_duration",    # seconds/day
    "wind_speed_10m_mean",  # mph
]

_HOURLY_VARS = [
    "relative_humidity_2m",  # % — no daily mean available, average from hourly
]

_MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def get_climate_normals(
    lat: float,
    lon: float,
    start_date: str = "2021-08-01",
    end_date: str = "2026-08-01",  # API caps to today automatically
) -> Optional[Dict[str, Any]]:
    """
    Fetch ERA5 data and aggregate into monthly normals.
    Returns None on network failure; caller should tolerate None gracefully.
    """
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date,
        "end_date": end_date,
        "daily": ",".join(_DAILY_VARS),
        "hourly": ",".join(_HOURLY_VARS),
        "timezone": "auto",
        "temperature_unit": "fahrenheit",
        "precipitation_unit": "inch",
        "wind_speed_unit": "mph",
    }

    try:
        r = requests.get(ARCHIVE_BASE, params=params, timeout=30)
        if r.status_code == 429:
            logger.debug("open_meteo_climate: 429 rate limit, sleeping 60s then retrying once")
            time.sleep(60)
            r = requests.get(ARCHIVE_BASE, params=params, timeout=30)
        if r.status_code != 200:
            logger.warning(f"open_meteo_climate: HTTP {r.status_code} for {lat},{lon}: {r.text[:100]}")
            return None
        data = r.json()
    except Exception as e:
        logger.warning(f"open_meteo_climate: request failed for {lat},{lon}: {e}")
        return None

    daily = data.get("daily", {})
    hourly = data.get("hourly", {})
    daily_dates = daily.get("time", [])
    hourly_dates = hourly.get("time", [])

    if not daily_dates:
        return None

    def _avg(vals: list) -> Optional[float]:
        return round(sum(vals) / len(vals), 1) if vals else None

    # Bin daily values by calendar month
    day_buckets: Dict[int, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))
    for i, date_str in enumerate(daily_dates):
        try:
            month = int(date_str[5:7])
        except (ValueError, IndexError):
            continue
        for var in _DAILY_VARS:
            val = (daily.get(var) or [])[i] if i < len(daily.get(var) or []) else None
            if val is not None:
                day_buckets[month][var].append(float(val))

    # Bin hourly humidity by calendar month
    hr_buckets: Dict[int, List[float]] = defaultdict(list)
    rh_vals = hourly.get("relative_humidity_2m") or []
    for i, date_str in enumerate(hourly_dates):
        try:
            month = int(date_str[5:7])
        except (ValueError, IndexError):
            continue
        if i < len(rh_vals) and rh_vals[i] is not None:
            hr_buckets[month].append(float(rh_vals[i]))

    months_out = []
    for m in range(1, 13):
        b = day_buckets[m]
        raw_sunshine = b.get("sunshine_duration", [])
        sunshine_hrs = round(sum(raw_sunshine) / len(raw_sunshine) / 3600.0, 1) if raw_sunshine else None

        months_out.append({
            "month": m,
            "month_name": _MONTH_NAMES[m - 1],
            "avg_high_f": _avg(b.get("temperature_2m_max", [])),
            "avg_low_f": _avg(b.get("temperature_2m_min", [])),
            "avg_precip_in": _avg(b.get("precipitation_sum", [])),
            "avg_snow_in": _avg(b.get("snowfall_sum", [])),
            "sunshine_hrs_per_day": sunshine_hrs,
            "humidity_pct": _avg(hr_buckets[m]),
            "wind_mph": _avg(b.get("wind_speed_10m_mean", [])),
        })

    return {
        "source": "open_meteo_era5",
        "normals_period": f"{start_date[:4]}-{end_date[:4]}",
        "months": months_out,
    }
