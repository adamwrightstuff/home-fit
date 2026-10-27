"""
Community Safety pillar — 0-100 score reflecting how safe a place is compared
with US cities and towns nationally.  One national scale applies to every area
type: a resident's risk does not depend on whether the place is urban or rural.

Inputs
------
- Violent crime rate  (FBI Part I: murder, rape, robbery, aggravated assault) per 1,000 residents
- Property crime rate (FBI Part I: burglary, larceny-theft, motor vehicle theft) per 1,000 residents
- Year-over-year violent crime trend (optional, ±5-point modifier)

Scoring
-------
1. Each rate's slot = 100 - its percentile among a random national sample of US
   city/town police departments (safer than 90% of US towns → 90).
2. Blend: violent slot x (1 - w) + property slot x w, with w = the property share of total
   harm (about 0.098), derived from published cost-of-crime estimates and national offense
   rates (data/community_safety_harm_weights.json; scripts/baselines/derive_community_safety_weight.py;
   docs/PILLAR_COMMUNITY_SAFETY.md).  One weight for every place: no retail-hub exception.
3. Add capped trend modifier: improving trend → +up to 5pts, worsening → -up to 5pts.
4. Final = clip(blend + trend_delta, 0, 100).

Data sources
------------
- NYC / SF / LA city limits: NYPD, SFPD, LAPD incident open data (Part I offenses, last full year)
- All others: FBI Crime Data Explorer per-agency data (requires FBI_CRIME_API_KEY env var),
  NY State UCR, CA DOJ, LASD station totals
- Optional: Census LODES+H3 commuter context (Parquet) to adjust commercial-heavy denominators
- Degraded:   score=None when no data available; does not contribute to total.

National scale
--------------
Stored in data/community_safety_national_scale.json.
Override path via COMMUNITY_SAFETY_SCALE_PATH env var.
Rebuild with scripts/baselines/build_community_safety_national_scale.py.
"""

from __future__ import annotations

import bisect
import json
import os
from typing import Any, Dict, Optional, Tuple

from data_sources.crime_api import (
    MIN_NEIGHBORHOOD_RESIDENTS,
    NEIGHBORHOOD_RADII_M,
    get_crime_rates,
    neighborhood_incident_source,
)
from data_sources.lodes_h8_commuter_context import jobs_in_disk
from data_sources.people_present import WORK_WEEK_SHARE, people_present, people_present_multiplier
from logging_config import get_logger

logger = get_logger(__name__)

_BASE_DIR = os.path.dirname(os.path.dirname(__file__))
_DEFAULT_DATA_DIR = os.path.join(_BASE_DIR, "data")

_SCALE_PATH = os.getenv(
    "COMMUNITY_SAFETY_SCALE_PATH",
    os.path.join(_DEFAULT_DATA_DIR, "community_safety_national_scale.json"),
)

# ---------------------------------------------------------------------------
# Load national scale at import time
# ---------------------------------------------------------------------------

_scale: Dict[str, Any] = {}

try:
    with open(_SCALE_PATH, "r", encoding="utf-8") as _f:
        _scale = json.load(_f)
    logger.info(
        "Loaded community safety national scale (%s agencies, %s)",
        _scale.get("_meta", {}).get("agencies_used"), _scale.get("_meta", {}).get("data_year"),
    )
except Exception as e:
    logger.error("Failed to load community safety national scale: %s; community_safety will report no data", e)


# Property share of total harm (see module docstring).  Falls back to the derived value if the
# file is missing so scoring never silently reverts to an untested weight.
_HARM_WEIGHTS_PATH = os.getenv(
    "COMMUNITY_SAFETY_HARM_WEIGHTS_PATH",
    os.path.join(_DEFAULT_DATA_DIR, "community_safety_harm_weights.json"),
)
_PROPERTY_WEIGHT_FALLBACK = 0.098
try:
    with open(_HARM_WEIGHTS_PATH, "r", encoding="utf-8") as _f:
        PROPERTY_WEIGHT = float(json.load(_f)["property_weight"])
except Exception as e:
    logger.warning("Failed to load community safety harm weights (%s); using %.3f", e, _PROPERTY_WEIGHT_FALLBACK)
    PROPERTY_WEIGHT = _PROPERTY_WEIGHT_FALLBACK


# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------

_TREND_CAP_PTS = 5.0

# Precision level indicates how granular/reliable the underlying data source is.
# HYPER_LOCAL   — actual incidents within the scored radius (Socrata)
# PRECINCT_PROXY — station/patrol-area average (LASD, Nassau County PD)
# AGENCY_VERIFIED — per-agency annual report (NY UCR, FBI NIBRS)
# DEGRADED      — state-level aggregate; score is suppressed (null)
_PRECISION_MAP = {
    "nyc_open_data":    "HYPER_LOCAL",
    "la_open_data":     "HYPER_LOCAL",
    "sf_open_data":     "HYPER_LOCAL",
    "chicago_open_data":      "HYPER_LOCAL",
    "philadelphia_open_data": "HYPER_LOCAL",
    "austin_open_data":       "HYPER_LOCAL",
    "dallas_open_data":       "HYPER_LOCAL",
    "boston_open_data":       "HYPER_LOCAL",
    "denver_open_data":       "HYPER_LOCAL",
    "charlotte_open_data":    "HYPER_LOCAL",
    "las_vegas_open_data":    "HYPER_LOCAL",
    "lasd_open_data":   "HYPER_LOCAL",
    "lasd_station":     "PRECINCT_PROXY",
    "ny_state_ucr":     "AGENCY_VERIFIED",
    "fbi_nibrs_agency": "AGENCY_VERIFIED",
    "fbi_county_agency": "PRECINCT_PROXY",  # county sheriff rate mapped to an unincorporated/small place
    "fbi_ucr_agency":   "PRECINCT_PROXY",  # non-NIBRS agency with UCR summary data
    "ca_doj_ucr":       "PRECINCT_PROXY",  # CA DOJ per-agency UCR counts (non-NIBRS fallback) (e.g. county sheriff)
    "fbi_cde_state":    "DEGRADED",
}

_CONFIDENCE_BASE: Dict[str, int] = {
    "HYPER_LOCAL": 93,
    "PRECINCT_PROXY": 69,
    "AGENCY_VERIFIED": 82,
}

def _confidence_and_dqi(precision_level: str, commuter_meta: Dict[str, Any]) -> Tuple[int, float]:
    base = float(_CONFIDENCE_BASE.get(precision_level, 45))
    if precision_level == "DEGRADED":
        return 0, 0.0
    adj = 0.0
    if commuter_meta.get("commuter_denominator_boost"):
        adj -= 3.0
    if "extreme_workplace_jobs_ratio" in commuter_meta.get("flags", []):
        adj -= 6.0
    conf_f = max(22.0, min(97.0, base + adj))
    conf_i = int(round(conf_f))
    dqi = round(conf_i / 100.0, 3)
    return conf_i, dqi


def _national_percentile(rate: float, key: str) -> float:
    """Percentile (0-100) of `rate` among US towns, interpolated between the
    stored 0th..100th percentile breakpoints."""
    pts = _scale.get(key) or []
    if not pts:
        raise ValueError(f"community safety national scale has no '{key}' breakpoints")
    if rate <= pts[0]:
        return 0.0
    if rate >= pts[-1]:
        return 100.0
    lo = bisect.bisect_right(pts, rate) - 1
    # Flat stretches (many towns at the same rate, e.g. 0) take their midpoint.
    hi = bisect.bisect_left(pts, rate)
    if pts[lo] == rate or hi > lo + 1:
        return (bisect.bisect_left(pts, rate) + bisect.bisect_right(pts, rate) - 1) / 2
    return lo + (rate - pts[lo]) / (pts[lo + 1] - pts[lo])


def _scale_ready() -> bool:
    return bool(_scale.get("violent_per_1k_percentiles")) and bool(_scale.get("property_per_1k_percentiles"))


class _DenominatorUnavailable(Exception):
    """The residents-in-circle estimate rests on an assumed density, so the rate would be invented."""


def _no_data(reason: str, scale_meta: Dict[str, Any]) -> Tuple[None, Dict[str, Any]]:
    return None, {
        "violent_per_1k": None,
        "property_per_1k": None,
        "trend_pct": None,
        "trend_delta": 0.0,
        "source": "none",
        "precision_level": "DEGRADED",
        "status": "DEGRADED",
        "data_available": False,
        "national_scale": scale_meta,
        "confidence": 0,
        "data_quality_index": 0.0,
        "degraded_reasons": [reason],
    }


def national_scale_meta() -> Dict[str, Any]:
    meta = _scale.get("_meta", {})
    return {"data_year": meta.get("data_year"), "agencies_used": meta.get("agencies_used")}


def _score_rates(
    violent_per_1k: float,
    property_per_1k: float,
    area_type: Optional[str] = None,
) -> Tuple[float, float, float, float]:
    """
    Compute violent slot, property slot, and blended raw score against the
    national scale (area_type is accepted for call compatibility but unused).
    Returns (violent_slot, property_slot, raw_score, violent_percentile).
    """
    v_pct = _national_percentile(violent_per_1k, "violent_per_1k_percentiles")
    p_pct = _national_percentile(property_per_1k, "property_per_1k_percentiles")
    v_slot = 100.0 - v_pct
    p_slot = 100.0 - p_pct

    p_weight = PROPERTY_WEIGHT
    v_weight = 1.0 - p_weight

    raw = v_weight * v_slot + p_weight * p_slot
    return v_slot, p_slot, raw, v_pct


def _neighborhood_ambient_population(
    lat: float, lon: float, area_type: Optional[str], state: Optional[str] = None
) -> Tuple[int, int, Dict[str, Any]]:
    """
    For open-data city neighborhoods: pick the smallest radius holding
    MIN_NEIGHBORHOOD_RESIDENTS, then count residents plus workers for the share of
    the week they're at work (never fewer than residents).
    Returns (radius_m, ambient_population, denominator_meta).
    """
    from data_sources.census_api import estimate_community_safety_disk_population

    radius, residents, meta = NEIGHBORHOOD_RADII_M[-1], 0, {}
    for r in NEIGHBORHOOD_RADII_M:
        residents, meta = estimate_community_safety_disk_population(lat, lon, r, area_type=area_type)
        if (
            meta.get("population_denominator_method") == "density_disk_legacy"
            or meta.get("population_denominator_floor_applied")
            or meta.get("population_denominator_fragment_blend")
        ):
            reason = meta.get("population_denominator_skip_reason") or "assumed_density_or_floor"
            raise _DenominatorUnavailable(f"residents in the circle were assumed, not measured ({reason})")
        radius = r
        if residents >= MIN_NEIGHBORHOOD_RESIDENTS:
            break
    ambient = float(residents)
    jobs = jobs_in_disk(lat, lon, radius, state=state)
    adjustment = "applied" if jobs is not None else "unavailable"
    if jobs is not None:
        workplace_jobs, resident_workers = jobs
        ambient = people_present(residents, workplace_jobs, resident_workers)
        meta = {
            **meta,
            "workplace_jobs_in_radius": int(round(workplace_jobs)),
            "resident_workers_in_radius": int(round(resident_workers)),
        }
    meta = {
        **meta,
        "commuter_adjustment": adjustment,
        "population_denominator_method": "ambient_residents_plus_workers",
        "residents_in_radius": int(residents),
        "ambient_population": int(round(ambient)),
        "work_week_share": round(WORK_WEEK_SHARE, 3),
    }
    return radius, max(1, int(round(ambient))), meta


def _trend_delta(trend_pct: Optional[float]) -> float:
    """
    Convert year-over-year violent crime change percentage to a score modifier.
    Declining trend (negative %) → positive delta (up to +5 pts).
    Rising trend (positive %)  → negative delta (down to -5 pts).
    """
    if trend_pct is None:
        return 0.0
    # Normalise: ±30% change = ±3 pts; cap at ±100% → ±5 pts
    delta = -(trend_pct / 100.0) * _TREND_CAP_PTS
    return round(max(-_TREND_CAP_PTS, min(_TREND_CAP_PTS, delta)), 2)


# ---------------------------------------------------------------------------
# Public scoring function
# ---------------------------------------------------------------------------

def get_community_safety_score(
    lat: float,
    lon: float,
    *,
    area_type: Optional[str] = None,
    city: Optional[str] = None,
    state: Optional[str] = None,
    zip_code: Optional[str] = None,
    population: Optional[int] = None,
    population_denominator_meta: Optional[Dict[str, Any]] = None,
    fallback_city: Optional[str] = None,
) -> Tuple[Optional[float], Dict[str, Any]]:
    """
    Score community safety for a location.

    Returns (score, details_dict).
    score is None (DEGRADED) when no crime data is available.

    Args:
        lat, lon:     Coordinates.
        area_type:    Morphological area type (drives radius and baselines).
        city:         City or neighbourhood name.
        state:        Two-letter state abbreviation (for FBI CDE routing).
        zip_code:     ZIP code (unused currently, reserved for future data source).
        population:   Estimated residential population for per-1k conversion.
                      No default: with no population (and no incident-feed circle) the pillar returns no data.
        population_denominator_meta: Optional telemetry from main (areal ACS disk estimate).
        fallback_city: Jurisdiction city for agency matching when `city` is a neighborhood.
    """
    scale_meta = national_scale_meta()
    if not _scale_ready():
        return _no_data("community_safety_national_scale_unavailable: scale file missing or empty", scale_meta)
    pop = population if population and population > 0 else None

    # City neighborhoods with incident-level open data get a neighborhood-sized
    # radius and an ambient (residents + workers) denominator.
    radius_override: Optional[int] = None
    ambient_neighborhood = False
    incident_source = neighborhood_incident_source(lat, lon, city, fallback_city)
    if incident_source:
        try:
            radius_override, pop, population_denominator_meta = _neighborhood_ambient_population(lat, lon, area_type, state=state)
        except _DenominatorUnavailable as e:
            return _no_data(f"community_safety_denominator_unavailable: {e}", scale_meta)
        ambient_neighborhood = True

    if pop is None:
        return _no_data("community_safety_population_unavailable: no population estimate was supplied", scale_meta)

    rates = get_crime_rates(
        lat, lon,
        city=city,
        state_abbr=state,
        area_type=area_type,
        population=pop,
        fallback_city=fallback_city,
        radius_m=radius_override,
        incident_source=incident_source,
    )

    if rates is None:
        details: Dict[str, Any] = {
            "violent_per_1k": None,
            "property_per_1k": None,
            "trend_pct": None,
            "trend_delta": 0.0,
            "source": "none",
            "precision_level": "DEGRADED",
            "status": "DEGRADED",
            "data_available": False,
            "national_scale": scale_meta,
            "confidence": 0,
            "data_quality_index": 0.0,
        }
        return None, details

    if rates.get("coming_soon"):
        details = {
            "status": "COMING_SOON",
            "coming_soon": True,
            "data_available": False,
            "confidence": 0,
            "data_quality_index": 0.0,
        }
        return None, details

    source = rates.get("source", "unknown")
    precision_level = _PRECISION_MAP.get(source)
    if precision_level is None:
        precision_level = "AGENCY_VERIFIED"

    # Zero-tolerance: state-aggregate data produces misleading scores for
    # individual locations.  Return null so the pillar is excluded from the
    # composite rather than injecting a meaningless state-average score.
    if source == "fbi_cde_state":
        details = {
            "violent_per_1k": round(rates["violent_per_1k"], 3),
            "property_per_1k": round(rates["property_per_1k"], 3),
            "trend_pct": rates.get("trend_pct"),
            "trend_delta": 0.0,
            "source": source,
            "precision_level": precision_level,
            "status": "DEGRADED",
            "data_available": True,
            "national_scale": scale_meta,
            "agency_name": rates.get("agency_name"),
            "confidence": 0,
            "data_quality_index": 0.0,
            "degraded_reasons": [
                "community_safety_state_aggregate_only: no local agency crime data was found, "
                "and a state-wide average is not used as a place score"
            ],
        }
        return None, details

    violent_raw = float(rates["violent_per_1k"])
    property_raw = float(rates["property_per_1k"])
    if ambient_neighborhood and str(rates.get("source", "")).endswith("_open_data"):
        # Workers are already in the neighborhood's people-present denominator.
        commuter_mult, commuter_meta = 1.0, {}
    else:
        # Agency-wide rates are per resident: scale to people present in the
        # jurisdiction (the town, or the county for county-wide agencies).
        agency = str(rates.get("agency_name") or "").lower()
        county_wide = source == "lasd_station" or "sheriff" in agency or "county" in agency
        commuter_mult, commuter_meta = people_present_multiplier(
            lat, lon, "county" if county_wide else "municipal"
        )

    violent_per_1k = violent_raw / commuter_mult
    property_per_1k = property_raw / commuter_mult
    trend_pct = rates.get("trend_pct")

    v_slot, p_slot, raw_score, v_z = _score_rates(violent_per_1k, property_per_1k, area_type)
    td = _trend_delta(trend_pct)
    final_score = round(max(0.0, min(100.0, raw_score + td)), 1)

    conf_i, dqi = _confidence_and_dqi(precision_level, commuter_meta)

    details = {
        # Rates below match the denominator used after optional LODES commuter boost.
        "violent_per_1k": round(violent_per_1k, 3),
        "property_per_1k": round(property_per_1k, 3),
        "violent_per_1k_residential_radius": round(violent_raw, 3),
        "property_per_1k_residential_radius": round(property_raw, 3),
        "trend_pct": trend_pct,
        "trend_delta": td,
        "violent_slot": round(v_slot, 1),
        "property_slot": round(p_slot, 1),
        "raw_score": round(raw_score, 1),
        "source": source,
        "precision_level": precision_level,
        "status": "VERIFIED",
        "data_available": True,
        "national_scale": scale_meta,
        "incidents_current": rates.get("incidents_current"),
        "data_period": rates.get("data_period"),
        "agency_name": rates.get("agency_name"),
        "confidence": conf_i,
        "data_quality_index": dqi,
        "people_present": commuter_meta,
    }
    if commuter_mult != 1.0:
        details["effective_pop_denominator_multiplier"] = round(commuter_mult, 4)
    reasons: list = []
    warnings: list = []
    if population_denominator_meta:
        details["population_denominator"] = population_denominator_meta
        if population_denominator_meta.get("commuter_adjustment") == "unavailable":
            reasons.append("community_safety_commuter_adjustment_unavailable: no LODES grid cells near the place")
        if ambient_neighborhood:
            # Tracts with no population row (not zero population) leave the circle's denominator short.
            no_row = population_denominator_meta.get("population_denominator_missing_tract_pops") or 0
            if no_row:
                reasons.append(
                    f"community_safety_denominator_incomplete: {no_row} census tract(s) in the circle have no population row"
                )
        filled = population_denominator_meta.get("population_denominator_tracts_filled")
        if filled:
            warnings.append(
                "community_safety_denominator_older_vintage: tract population filled from an older ACS vintage "
                + ", ".join(f"{k} x{v}" for k, v in sorted(filled.items()))
            )
    if trend_pct is None:
        reasons.append("community_safety_trend_unavailable: no prior-year count, so no trend adjustment")
    if reasons:
        details["degraded_reasons"] = reasons
    if warnings:
        details["data_warnings"] = warnings
    return final_score, details
