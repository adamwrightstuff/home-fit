"""
Climate & Flood Risk pillar (Phase 1A: GEE only).

Scores forward-looking environmental risk: heat exposure (urban heat island) and
air quality (PM2.5 proxy from Sentinel-5P Aerosol Index). Flood zone and 30-year
trend are planned for a later phase (FEMA NFHL, First Street API).

All sub-scores are inverse: higher raw value = worse; pillar score 0 = very high risk,
100 = very low risk.
"""

from typing import Dict, Tuple, Optional

from data_sources.gee_api import get_heat_exposure_lst, get_air_quality_aer_ai, GEE_AVAILABLE
from data_sources.data_quality import assess_pillar_data_quality, detect_area_type
from logging_config import get_logger

logger = get_logger(__name__)

# PRD: Heat (0-30 pts). Score = max(0, 30 - (heat_excess_deg_c / 5) * 30). 5°C excess = 0 pts.
HEAT_MAX_PTS = 30.0
HEAT_EXCESS_FOR_ZERO = 5.0  # degrees C above regional = 0 pts

# PRD: Air (0-20 pts). Score = max(0, 20 - (pm25_ugm3 / 35) * 20). 35 ug/m3 = 0 pts.
AIR_MAX_PTS = 20.0
PM25_UNHEALTHY = 35.0  # EPA Unhealthy threshold (ug/m3)

# Phase 1: no FEMA, no First Street. Heat + Air max = 50 pts; scale to 0-100.
PHASE1_SCALE = 2.0  # (heat_pts + air_pts) * PHASE1_SCALE = pillar score, cap 100


def get_climate_risk_score(
    lat: float,
    lon: float,
    area_type: Optional[str] = None,
    density: Optional[float] = None,
    city: Optional[str] = None,
) -> Tuple[float, Dict]:
    """
    Compute Climate & Flood Risk pillar score (Phase 1A: GEE only).

    Returns:
        (score_0_100, details) where details has breakdown, summary, data_quality.
        Score is inverse risk: 100 = very low risk, 0 = very high risk.
    """
    heat_data = get_heat_exposure_lst(lat, lon)
    air_data = get_air_quality_aer_ai(lat, lon)

    no_heat = heat_data is None
    no_air = air_data is None
    no_data = no_heat and no_air
    if no_data:
        logger.warning(
            "Climate risk: no GEE data (heat=%s, air=%s). GEE_AVAILABLE=%s. "
            "Set GOOGLE_APPLICATION_CREDENTIALS_JSON in production for real scores.",
            no_heat, no_air, GEE_AVAILABLE,
        )

    # Heat exposure (0-30 pts). Inverse: lower heat_excess = higher score.
    if heat_data is not None:
        heat_excess = heat_data.get("heat_excess_deg_c", 0.0) or 0.0
        heat_pts = max(0.0, HEAT_MAX_PTS - (heat_excess / HEAT_EXCESS_FOR_ZERO) * HEAT_MAX_PTS)
        heat_pts = round(min(HEAT_MAX_PTS, heat_pts), 2)
    else:
        heat_excess = None
        heat_pts = 0.0

    # Air quality (0-20 pts). Inverse: lower pm25_proxy = higher score.
    if air_data is not None:
        pm25_proxy = air_data.get("pm25_proxy_ugm3", 35.0) or 35.0
        air_pts = max(0.0, AIR_MAX_PTS - (pm25_proxy / PM25_UNHEALTHY) * AIR_MAX_PTS)
        air_pts = round(min(AIR_MAX_PTS, air_pts), 2)
    else:
        pm25_proxy = None
        air_pts = 0.0

    # Phase 1: no flood, no 30-year trend. Scale heat+air (max 50) to 0-100.
    # When no GEE data (both None), use neutral score 50 so we don't show "worst risk" for missing data.
    total_raw = heat_pts + air_pts
    score = min(100.0, total_raw * PHASE1_SCALE) if not no_data else 50.0
    score = round(score, 1)

    # Sub-scores for API (0-100 scale for consistency)
    lst_score_0_100 = round((heat_pts / HEAT_MAX_PTS) * 100.0, 1) if HEAT_MAX_PTS else 0.0
    aqi_score_0_100 = round((air_pts / AIR_MAX_PTS) * 100.0, 1) if AIR_MAX_PTS else 0.0

    # Data quality
    combined_data = {
        "heat_data": heat_data,
        "air_data": air_data,
        "score": score,
        "heat_pts": heat_pts,
        "air_pts": air_pts,
    }
    area_type_dq = detect_area_type(lat, lon, density=density, city=city)
    quality_metrics = assess_pillar_data_quality(
        "climate_risk", combined_data, lat, lon, area_type_dq
    )

    breakdown = {
        "heat_exposure_pts": heat_pts,
        "air_quality_pts": air_pts,
        "flood_zone_pts": None,  # Phase 2
        "climate_trend_pts": None,  # Phase 4 optional
        "lst_score": lst_score_0_100,
        "aqi_score": aqi_score_0_100,
    }
    summary = {
        "heat_excess_deg_c": heat_excess,
        "local_lst_c": heat_data.get("local_lst_c") if heat_data else None,
        "regional_lst_c": heat_data.get("regional_lst_c") if heat_data else None,
        "pm25_proxy_ugm3": pm25_proxy,
        "aer_ai_mean": air_data.get("aer_ai_mean") if air_data else None,
        "flood_zone_score": None,
        "climate_trend_score": None,
        "data_available": not no_data,
    }
    details = {
        "breakdown": breakdown,
        "summary": summary,
        "data_quality": quality_metrics,
        "area_classification": {"area_type": area_type or area_type_dq},
        "phase": "1a_gee_only",
    }

    logger.info(
        "Climate Risk Score: %s/100 (heat_pts=%s, air_pts=%s)",
        score, heat_pts, air_pts,
    )
    return score, details
