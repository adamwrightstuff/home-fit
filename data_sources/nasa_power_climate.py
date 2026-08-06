"""
NASA POWER climatology API client.
Free, no API key, 30-year monthly averages returned directly (no aggregation needed).
https://power.larc.nasa.gov/api/temporal/climatology/point
"""

import requests
from typing import Optional, Dict, Any

from logging_config import get_logger

logger = get_logger(__name__)

POWER_BASE = "https://power.larc.nasa.gov/api/temporal/climatology/point"

_PARAMS = "T2M,PRECTOTCORR,RH2M,ALLSKY_SFC_SW_DWN,WS10M,SNODP"

_MONTH_KEYS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
               "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
_MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def get_climate_normals(lat: float, lon: float) -> Optional[Dict[str, Any]]:
    """
    Return 30-year monthly climate normals from NASA POWER ERA5.
    Returns None on failure; caller should tolerate None gracefully.
    """
    params = {
        "latitude": lat,
        "longitude": lon,
        "community": "RE",
        "parameters": _PARAMS,
        "format": "JSON",
        "header": "false",
    }

    try:
        r = requests.get(POWER_BASE, params=params, timeout=20)
        if r.status_code != 200:
            logger.warning(f"nasa_power_climate: HTTP {r.status_code} for {lat},{lon}")
            return None
        data = r.json()
    except Exception as e:
        logger.warning(f"nasa_power_climate: request failed for {lat},{lon}: {e}")
        return None

    props = data.get("properties", {}).get("parameter", {})
    if not props:
        return None

    def _c_to_f(c) -> Optional[float]:
        return round(c * 9 / 5 + 32, 1) if c is not None else None

    def _mm_day_to_in_month(mm_day, month_idx) -> Optional[float]:
        days = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month_idx]
        return round(mm_day * days * 0.03937, 2) if mm_day is not None else None

    def _ms_to_mph(ms) -> Optional[float]:
        return round(ms * 2.237, 1) if ms is not None else None

    def _cm_to_in(cm) -> Optional[float]:
        return round(cm * 0.3937, 2) if cm is not None else None

    months_out = []
    for i, mk in enumerate(_MONTH_KEYS):
        t2m = props.get("T2M", {}).get(mk)
        prcp = props.get("PRECTOTCORR", {}).get(mk)
        months_out.append({
            "month": i + 1,
            "month_name": _MONTH_NAMES[i],
            "avg_temp_f": _c_to_f(t2m),
            "avg_precip_in": _mm_day_to_in_month(prcp, i),
            "humidity_pct": props.get("RH2M", {}).get(mk),
            "solar_kwh_m2_day": props.get("ALLSKY_SFC_SW_DWN", {}).get(mk),
            "wind_mph": _ms_to_mph(props.get("WS10M", {}).get(mk)),
            "snow_depth_in": _cm_to_in(props.get("SNODP", {}).get(mk)),
        })

    return {
        "source": "nasa_power_era5",
        "normals_period": "1991-2020",
        "months": months_out,
    }
