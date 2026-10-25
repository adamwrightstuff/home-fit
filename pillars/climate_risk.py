"""
Climate & Flood Risk pillar (Phase 2: heat, air, flood, climate trend).

Scores forward-looking environmental risk: heat exposure (urban heat island), air quality
(annual PM2.5 by census tract, CDC / EPA Downscaler), FEMA flood zone, and 30-year temperature trend (TerraClimate).

All sub-scores are inverse: higher raw value = worse; pillar score 0 = very high risk,
100 = very low risk.
"""

from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Tuple, Optional

from data_sources.gee_api import (
    get_heat_exposure_lst,
    get_climate_trend_terraclimate,
    GEE_AVAILABLE,
)
from data_sources.air_quality_pm25 import get_pm25 as get_air_quality_pm25
from data_sources.fema_flood import get_fema_flood_zone
from data_sources.data_quality import assess_pillar_data_quality, detect_area_type
from logging_config import get_logger

logger = get_logger(__name__)

# Heat (0-25 pts). Linear in June-August Landsat land-surface temperature (LST): 25 points at 30 C down to 0 at 60 C.
# Both anchors are JUDGMENTS (2026-10-25). Surface temperature runs well above the air temperature that health evidence
# uses, so no published threshold maps onto it. The old zero point of 42 C sat inside the observed range (36% of catalog
# places, and 97-98% of Phoenix, Las Vegas and Dallas, scored 0); 60 C sits just above the hottest place (58.3 C).
# Sensitivity (tracker D13, analysis/launch_check_findings_2026-10-25.md): the change is a pure rescale of the heat part
# (rank agreement 0.97 for the climate score), it keeps Phoenix and Las Vegas about 12 points below Seattle and Boston,
# keeps urban cores below exurbs in the same metro, and raises the climate score about 13-16 points (about +1.1 on totals).
# A scale relative to the metro background was rejected because it erases real differences between metros.
HEAT_MAX_PTS = 25.0
HEAT_LST_BEST = 30.0   # C local LST: full points
HEAT_LST_WORST = 60.0  # C local LST: 0 points
HEAT_MIN_LAND_FRACTION = 0.3
# A June-August daytime land-surface temperature outside this range is a bad pixel (cloud, water, ice), not heat:
# 9 catalog places read below 15 C (Dunedin -21 C) and got full heat points. The bounds are a judgment about what is
# physically plausible for US land in summer; Pacifica's coastal-fog 19 C passes, 14 C inland Florida does not.
LST_PLAUSIBLE_MIN_C = 15.0
LST_PLAUSIBLE_MAX_C = 75.0

# Fewer present components than this and the pillar has no score (it raises, so the app marks it failed).
MIN_COMPONENTS = 3

# Air (0-20 pts). Annual mean PM2.5 by census tract, linear from full points at PM25_BEST to 0 at PM25_WORST.
# PM25_BEST is the WHO 2021 annual guideline (5 ug/m3), which is evidence-based. PM25_WORST (35, the WHO interim
# target 1 and the zero point the old proxy used) is a JUDGMENT: the mortality evidence supports a roughly linear
# risk (about +7% per 10 ug/m3, Di et al. 2017, NEJM) but does not say how many points a ug/m3 is worth, and no
# US place is near 35, so this choice only sets the slope (0.67 points per ug/m3). See tracker D13.
AIR_MAX_PTS = 20.0
PM25_BEST = 5.0
PM25_WORST = 35.0

# Flood (0-30 pts). From FEMA NFHL; floodway=0, SFHA=15%, X/D/minimal scaled. Neutral when missing.
FLOOD_MAX_PTS = 30.0

# Climate trend (0-25 pts). 30-year TerraClimate tmax trend; 0°C/decade = max, 0.5°C/decade = 0.
TREND_MAX_PTS = 25.0
# Zero point is a JUDGMENT (2026-10-25): the observed 30-year tmax trends run 0.15 to 0.58 C per decade, and the old
# zero point of 0.5 clipped 10% of places (Austin 97%, San Antonio 100%, Phoenix 39%). 0.8 keeps every place above 0.
# The trend is regional (a metro's places share a value), so it differentiates metros, not neighborhoods.
TREND_C_PER_DECADE_FOR_ZERO = 0.8  # C per decade warming: 0 pts


def heat_points(local_lst_c: float) -> float:
    """Heat points (0 to HEAT_MAX_PTS): linear from full at HEAT_LST_BEST to 0 at HEAT_LST_WORST."""
    frac = (HEAT_LST_WORST - float(local_lst_c)) / (HEAT_LST_WORST - HEAT_LST_BEST)
    return round(HEAT_MAX_PTS * max(0.0, min(1.0, frac)), 2)


def trend_points(trend_c_per_decade: float) -> float:
    """Warming-trend points (0 to TREND_MAX_PTS): full at no warming, 0 at TREND_C_PER_DECADE_FOR_ZERO per decade."""
    frac = 1.0 - max(0.0, float(trend_c_per_decade)) / TREND_C_PER_DECADE_FOR_ZERO
    return round(TREND_MAX_PTS * max(0.0, min(1.0, frac)), 2)


def air_quality_points(pm25_ugm3: float) -> float:
    """Air quality points (0 to AIR_MAX_PTS): linear from full points at PM25_BEST to 0 at PM25_WORST."""
    frac = (PM25_WORST - float(pm25_ugm3)) / (PM25_WORST - PM25_BEST)
    return round(AIR_MAX_PTS * max(0.0, min(1.0, frac)), 2)


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
        f_air = executor.submit(get_air_quality_pm25, lat, lon)
        f_flood = executor.submit(get_fema_flood_zone, lat, lon)
        f_trend = executor.submit(get_climate_trend_terraclimate, lat, lon)
        heat_data = f_heat.result()
        air_data = f_air.result()
        flood_data = f_flood.result()
        trend_data = f_trend.result()

    # Fail loudly: a component that cannot be measured is None (no data), never a neutral or invented
    # value. The score is built from the components that are present, scaled to their maximum points, and
    # the pillar is marked degraded with the reason. Fewer than MIN_COMPONENTS present means no score.
    no_heat = heat_data is None
    no_air = air_data is None
    if no_heat and no_air:
        logger.warning(
            "Climate risk: no GEE data (heat=%s, air=%s). GEE_AVAILABLE=%s. "
            "Set GOOGLE_APPLICATION_CREDENTIALS or GOOGLE_APPLICATION_CREDENTIALS_JSON in production for real scores.",
            no_heat, no_air, GEE_AVAILABLE,
        )

    # Heat exposure (0-25 pts). Absolute local LST: 30°C = full, 42°C = 0.
    # No data when the lookup failed or the 500 m buffer is mostly water (LST would describe water, not land).
    heat_pts: Optional[float] = None
    local_lst = None
    land_fraction = None
    heat_status = "no_data"
    local_lst_rejected = None
    if heat_data is not None:
        local_lst = heat_data.get("local_lst_c")
        land_fraction = heat_data.get("land_pixel_fraction", 1.0)
        try:
            local_lst = float(local_lst) if local_lst is not None else None
        except (TypeError, ValueError):
            local_lst = None
        if local_lst is not None and not (LST_PLAUSIBLE_MIN_C <= local_lst <= LST_PLAUSIBLE_MAX_C):
            logger.warning("Climate risk: implausible land-surface temperature %.1f C at (%s, %s); heat is no data", local_lst, lat, lon)
            heat_status = "implausible_lst"
            local_lst_rejected = local_lst
            local_lst = None
        elif local_lst is not None and land_fraction >= HEAT_MIN_LAND_FRACTION:
            heat_status = "ok"
            heat_pts = heat_points(local_lst)

    # Air quality (0-20 pts). Annual mean PM2.5 (ug/m3) for the tract; no data when the tract has no value.
    air_pts: Optional[float] = None
    pm25 = None
    if air_data is not None:
        try:
            pm25 = float(air_data.get("pm25_ugm3"))
        except (TypeError, ValueError):
            pm25 = None
        if pm25 is not None and (pm25 != pm25 or pm25 < 0):
            pm25 = None
        if pm25 is not None:
            air_pts = air_quality_points(pm25)

    # Flood (0-30 pts). From FEMA NFHL; no data when the FEMA lookup failed.
    flood_pts: Optional[float] = None
    risk_tier = None
    fld_zone = None
    flood_label = None
    if flood_data is not None and flood_data.get("flood_zone_pts") is not None:
        flood_pts = round(min(FLOOD_MAX_PTS, max(0.0, float(flood_data["flood_zone_pts"]))), 2)
        risk_tier = flood_data.get("risk_tier")
        fld_zone = flood_data.get("fld_zone")
        flood_label = flood_data.get("label")

    # Climate trend (0-25 pts). Warming = fewer pts; no data when the GEE trend is unavailable.
    trend_pts: Optional[float] = None
    trend_c_per_decade = None
    if trend_data is not None and trend_data.get("trend_c_per_decade") is not None:
        trend_c_per_decade = float(trend_data["trend_c_per_decade"])
        trend_pts = trend_points(trend_c_per_decade)

    component_pts = {"heat": heat_pts, "air": air_pts, "flood": flood_pts, "trend": trend_pts}
    component_max = {"heat": HEAT_MAX_PTS, "air": AIR_MAX_PTS, "flood": FLOOD_MAX_PTS, "trend": TREND_MAX_PTS}
    present = [k for k, v in component_pts.items() if v is not None]
    missing = [k for k in component_pts if k not in present]
    if len(present) < MIN_COMPONENTS:
        raise RuntimeError(
            f"Climate risk: only {len(present)} of 4 components available (missing: {', '.join(missing)})"
        )
    # Heat 25 + air 20 + flood 30 + trend 25 = 100 max; scaled to the present components' maximum.
    score = min(100.0, sum(component_pts[k] for k in present) / sum(component_max[k] for k in present) * 100.0)
    score = round(score, 1)

    # Sub-scores for API (0-100 scale for consistency); None when the component has no data.
    def _sub(pts, max_pts):
        return round((pts / max_pts) * 100.0, 1) if pts is not None else None

    lst_score_0_100 = _sub(heat_pts, HEAT_MAX_PTS)
    aqi_score_0_100 = _sub(air_pts, AIR_MAX_PTS)
    flood_score_0_100 = _sub(flood_pts, FLOOD_MAX_PTS)
    trend_score_0_100 = _sub(trend_pts, TREND_MAX_PTS)

    # Data quality
    combined_data = {
        "heat_data": heat_data,
        "air_data": air_data,
        "flood_data": flood_data,
        "trend_data": trend_data,
        "components_present": present,
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
    if air_data and air_data.get("match") == "nearest_centroid":
        quality_metrics["data_warnings"] = list(quality_metrics.get("data_warnings") or []) + [
            f"pm25_nearest_tract_centroid_{air_data.get('match_km')}km"
        ]
    if missing:
        quality_metrics["degraded"] = True
        quality_metrics["degraded_reasons"] = list(quality_metrics.get("degraded_reasons") or []) + [
            f"climate_risk_missing_components: {', '.join(missing)}"
        ]

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
        "local_lst_c": heat_data.get("local_lst_c") if heat_data else None,
        "land_pixel_fraction": heat_data.get("land_pixel_fraction") if heat_data else None,
        "heat_status": heat_status,
        "local_lst_rejected_c": local_lst_rejected,
        "pm25_ugm3": round(pm25, 2) if pm25 is not None else None,
        "pm25_years": air_data.get("years") if air_data else None,
        "pm25_source": air_data.get("source") if air_data else None,
        "pm25_match": air_data.get("match") if air_data else None,
        "pm25_match_km": air_data.get("match_km") if air_data else None,
        "flood_zone_score": flood_score_0_100,
        "flood_risk_tier": risk_tier,
        "fld_zone": fld_zone,
        "flood_label": flood_label,
        "climate_trend_score": trend_score_0_100,
        "trend_c_per_decade": trend_c_per_decade,
        "data_available": bool(present),
        "components_missing": missing,
    }
    details = {
        "breakdown": breakdown,
        "summary": summary,
        "data_quality": quality_metrics,
        "area_classification": {"area_type": area_type or area_type_dq},
        "phase": "2_heat_air_flood_trend",
    }

    logger.info(
        "Climate Risk Score: %s/100 (heat=%s, air=%s, flood=%s, trend=%s) missing=%s local_lst=%s land_frac=%s pm25=%s flood_tier=%s trend_c_decade=%s",
        score, heat_pts, air_pts, flood_pts, trend_pts, missing,
        local_lst, land_fraction, pm25, risk_tier, trend_c_per_decade,
    )
    return score, details
