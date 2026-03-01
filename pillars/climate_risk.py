"""
Climate & Flood Risk pillar (Phase 2: heat, air, flood, climate trend).

Scores forward-looking environmental risk: heat exposure (urban heat island), air quality
(PM2.5 proxy from Sentinel-5P), FEMA flood zone, and 30-year temperature trend (TerraClimate).

All sub-scores are inverse: higher raw value = worse; pillar score 0 = very high risk,
100 = very low risk.
"""

from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Tuple, Optional

from data_sources.gee_api import (
    get_heat_exposure_lst,
    get_air_quality_aer_ai,
    get_climate_trend_terraclimate,
    GEE_AVAILABLE,
)
from data_sources.fema_flood import get_fema_flood_zone
from data_sources.data_quality import assess_pillar_data_quality, detect_area_type
from logging_config import get_logger

logger = get_logger(__name__)

# Heat (0-25 pts). Score = max(0, 25 - (heat_excess_deg_c / 5) * 25). 5°C excess = 0 pts.
HEAT_MAX_PTS = 25.0
HEAT_EXCESS_FOR_ZERO = 5.0  # degrees C above regional = 0 pts

# Air (0-20 pts). Score = max(0, 20 - (pm25_ugm3 / 35) * 20). 35 ug/m3 = 0 pts.
AIR_MAX_PTS = 20.0
PM25_UNHEALTHY = 35.0  # EPA Unhealthy threshold (ug/m3)

# Flood (0-30 pts). From FEMA NFHL; floodway=0, SFHA=15%, X/D/minimal scaled. Neutral when missing.
FLOOD_MAX_PTS = 30.0

# Climate trend (0-25 pts). 30-year TerraClimate tmax trend; 0°C/decade = max, 0.5°C/decade = 0.
TREND_MAX_PTS = 25.0
TREND_C_PER_DECADE_FOR_ZERO = 0.5  # °C per decade warming → 0 pts


def get_climate_risk_score(
    lat: float,
    lon: float,
    area_type: Optional[str] = None,
    density: Optional[float] = None,
    city: Optional[str] = None,
) -> Tuple[float, Dict]:
    """
    Compute Climate & Flood Risk pillar score (Phase 2: heat, air, flood, trend).

    Returns:
        (score_0_100, details) where details has breakdown, summary, data_quality.
        Score is inverse risk: 100 = very low risk, 0 = very high risk.
    """
    # Fetch all four data sources in parallel (same requests, less wall time; no extra error risk).
    with ThreadPoolExecutor(max_workers=4) as executor:
        f_heat = executor.submit(get_heat_exposure_lst, lat, lon)
        f_air = executor.submit(get_air_quality_aer_ai, lat, lon)
        f_flood = executor.submit(get_fema_flood_zone, lat, lon)
        f_trend = executor.submit(get_climate_trend_terraclimate, lat, lon)
        heat_data = f_heat.result()
        air_data = f_air.result()
        flood_data = f_flood.result()
        trend_data = f_trend.result()

    no_heat = heat_data is None
    no_air = air_data is None
    no_data = no_heat and no_air
    if no_data:
        logger.warning(
            "Climate risk: no GEE data (heat=%s, air=%s). GEE_AVAILABLE=%s. "
            "Set GOOGLE_APPLICATION_CREDENTIALS or GOOGLE_APPLICATION_CREDENTIALS_JSON in production for real scores.",
            no_heat, no_air, GEE_AVAILABLE,
        )

    # Heat exposure (0-30 pts). Inverse: lower heat_excess = higher score.
    if heat_data is not None:
        raw_heat = heat_data.get("heat_excess_deg_c")
        # Use 0 only when key is missing; 0 is valid (no excess = best)
        heat_excess = 0.0 if raw_heat is None else raw_heat
        try:
            heat_excess = float(heat_excess)
        except (TypeError, ValueError):
            heat_excess = None
        if heat_excess is not None and (heat_excess != heat_excess or abs(heat_excess) > 100):
            heat_excess = None
        if heat_excess is not None:
            heat_pts = max(0.0, HEAT_MAX_PTS - (heat_excess / HEAT_EXCESS_FOR_ZERO) * HEAT_MAX_PTS)
            heat_pts = round(min(HEAT_MAX_PTS, heat_pts), 2)
        else:
            heat_excess = None
            heat_pts = 0.0
    else:
        heat_excess = None
        heat_pts = 0.0

    # Air quality (0-20 pts). Inverse: lower pm25_proxy = higher score.
    if air_data is not None:
        raw_pm = air_data.get("pm25_proxy_ugm3")
        # Use 35 (worst) only when key is missing; 0 is valid (best air)
        pm25_proxy = 35.0 if raw_pm is None else raw_pm
        try:
            pm25_proxy = float(pm25_proxy)
        except (TypeError, ValueError):
            pm25_proxy = None
        if pm25_proxy is not None and (pm25_proxy != pm25_proxy or pm25_proxy < 0):
            pm25_proxy = None
        if pm25_proxy is not None and pm25_proxy > 35:
            pm25_proxy = min(35.0, pm25_proxy)
        if pm25_proxy is not None:
            air_pts = max(0.0, AIR_MAX_PTS - (pm25_proxy / PM25_UNHEALTHY) * AIR_MAX_PTS)
            air_pts = round(min(AIR_MAX_PTS, air_pts), 2)
        else:
            pm25_proxy = None
            air_pts = 0.0
    else:
        pm25_proxy = None
        air_pts = 0.0

    # Flood (0-30 pts). From FEMA NFHL; neutral when FEMA unavailable.
    if flood_data is not None:
        flood_pts = float(flood_data.get("flood_zone_pts", FLOOD_MAX_PTS * 0.5))
        flood_pts = round(min(FLOOD_MAX_PTS, max(0.0, flood_pts)), 2)
        risk_tier = flood_data.get("risk_tier")
        fld_zone = flood_data.get("fld_zone")
        flood_label = flood_data.get("label")
    else:
        flood_pts = round(FLOOD_MAX_PTS * 0.5, 2)  # neutral when missing
        risk_tier = None
        fld_zone = None
        flood_label = None

    # Climate trend (0-25 pts). Warming = fewer pts; neutral when GEE trend unavailable.
    if trend_data is not None:
        trend_c_per_decade = float(trend_data.get("trend_c_per_decade", 0.0) or 0.0)
        trend_pts = max(
            0.0,
            TREND_MAX_PTS - (max(0.0, trend_c_per_decade) / TREND_C_PER_DECADE_FOR_ZERO) * TREND_MAX_PTS,
        )
        trend_pts = round(min(TREND_MAX_PTS, trend_pts), 2)
    else:
        trend_c_per_decade = None
        trend_pts = round(TREND_MAX_PTS * 0.5, 2)  # neutral when missing

    # Total: heat 25 + air 20 + flood 30 + trend 25 = 100 max.
    total_raw = heat_pts + air_pts + flood_pts + trend_pts
    score = min(100.0, total_raw)
    if no_data and flood_data is None and trend_data is None:
        score = 50.0  # all data missing → neutral
    score = round(score, 1)

    # Sub-scores for API (0-100 scale for consistency)
    lst_score_0_100 = round((heat_pts / HEAT_MAX_PTS) * 100.0, 1) if HEAT_MAX_PTS else 0.0
    aqi_score_0_100 = round((air_pts / AIR_MAX_PTS) * 100.0, 1) if AIR_MAX_PTS else 0.0
    flood_score_0_100 = round((flood_pts / FLOOD_MAX_PTS) * 100.0, 1) if FLOOD_MAX_PTS else 0.0
    trend_score_0_100 = round((trend_pts / TREND_MAX_PTS) * 100.0, 1) if TREND_MAX_PTS else 0.0

    # Data quality
    combined_data = {
        "heat_data": heat_data,
        "air_data": air_data,
        "flood_data": flood_data,
        "trend_data": trend_data,
        "score": score,
        "heat_pts": heat_pts,
        "air_pts": air_pts,
        "flood_pts": flood_pts,
        "trend_pts": trend_pts,
    }
    area_type_dq = detect_area_type(lat, lon, density=density, city=city)
    quality_metrics = assess_pillar_data_quality(
        "climate_risk", combined_data, lat, lon, area_type_dq
    )

    breakdown = {
        "heat_exposure_pts": heat_pts,
        "air_quality_pts": air_pts,
        "flood_zone_pts": flood_pts,
        "climate_trend_pts": trend_pts,
        "lst_score": lst_score_0_100,
        "aqi_score": aqi_score_0_100,
        "flood_zone_score_0_100": flood_score_0_100,
        "climate_trend_score_0_100": trend_score_0_100,
    }
    summary = {
        "heat_excess_deg_c": heat_excess,
        "local_lst_c": heat_data.get("local_lst_c") if heat_data else None,
        "regional_lst_c": heat_data.get("regional_lst_c") if heat_data else None,
        "pm25_proxy_ugm3": pm25_proxy,
        "aer_ai_mean": air_data.get("aer_ai_mean") if air_data else None,
        "flood_zone_score": flood_score_0_100,
        "flood_risk_tier": risk_tier,
        "fld_zone": fld_zone,
        "flood_label": flood_label,
        "climate_trend_score": trend_score_0_100,
        "trend_c_per_decade": trend_c_per_decade,
        "data_available": not no_data,
    }
    details = {
        "breakdown": breakdown,
        "summary": summary,
        "data_quality": quality_metrics,
        "area_classification": {"area_type": area_type or area_type_dq},
        "phase": "2_heat_air_flood_trend",
    }

    logger.info(
        "Climate Risk Score: %s/100 (heat=%s, air=%s, flood=%s, trend=%s) heat_excess=%s pm25=%s flood_tier=%s trend_c_decade=%s",
        score, heat_pts, air_pts, flood_pts, trend_pts, heat_excess, pm25_proxy, risk_tier, trend_c_per_decade,
    )
    if score == 0 and not no_data:
        logger.warning(
            "Climate risk score 0 with data: heat_excess=%s pm25_proxy=%s (check units or thresholds)",
            heat_excess, pm25_proxy,
        )
    return score, details
