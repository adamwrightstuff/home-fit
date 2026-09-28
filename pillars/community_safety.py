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
2. Blend: 65% violent slot + 35% property slot (15% property in retail-theft hubs).
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

from data_sources.crime_api import get_crime_rates
from data_sources.lodes_h8_commuter_context import compute_commuter_denominator_boost
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
    logger.warning("Failed to load community safety national scale: %s", e)


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
    "lasd_station":     "PRECINCT_PROXY",
    "ny_state_ucr":     "AGENCY_VERIFIED",
    "fbi_nibrs_agency": "AGENCY_VERIFIED",
    "fbi_ucr_agency":   "PRECINCT_PROXY",  # non-NIBRS agency with UCR summary data
    "ca_doj_ucr":       "PRECINCT_PROXY",  # CA DOJ per-agency UCR counts (non-NIBRS fallback) (e.g. county sheriff)
    "fbi_cde_state":    "DEGRADED",
}

_CONFIDENCE_BASE: Dict[str, int] = {
    "HYPER_LOCAL": 93,
    "PRECINCT_PROXY": 69,
    "AGENCY_VERIFIED": 82,
}

# Commercial/retail-hub detector: when property crime rate is this many times
# higher than violent crime AND violent rate is below this threshold, the area's
# crime profile is dominated by commercial theft (shoplifting, package theft,
# pickpocketing) rather than community violence.  Dampen property weight so
# a larceny-heavy commercial corridor doesn't score below a violent neighbourhood.
_COMMERCIAL_PROPERTY_RATIO = 8.0   # property_per_1k / violent_per_1k threshold
_COMMERCIAL_VIOLENT_CEILING = 8.0  # only apply dampening when violent_per_1k < this
_COMMERCIAL_PROPERTY_WEIGHT = 0.15  # reduced from default 0.35


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
        return 50.0
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

    # Commercial-hub dampening: reduce property weight when the crime profile
    # is dominated by property crime (retail theft, pickpockets) vs. violence.
    p_weight = _COMMERCIAL_PROPERTY_WEIGHT if (
        violent_per_1k < _COMMERCIAL_VIOLENT_CEILING
        and property_per_1k > 0
        and violent_per_1k > 0
        and property_per_1k / violent_per_1k >= _COMMERCIAL_PROPERTY_RATIO
    ) else 0.35
    v_weight = 1.0 - p_weight

    raw = v_weight * v_slot + p_weight * p_slot
    return v_slot, p_slot, raw, v_pct


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
                      Defaults to 10,000 when not supplied.
        population_denominator_meta: Optional telemetry from main (areal ACS disk estimate).
        fallback_city: Jurisdiction city for agency matching when `city` is a neighborhood.
    """
    pop = population or 10_000
    scale_meta = national_scale_meta()

    rates = get_crime_rates(
        lat, lon,
        city=city,
        state_abbr=state,
        area_type=area_type,
        population=pop,
        fallback_city=fallback_city,
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
        }
        return None, details

    violent_raw = float(rates["violent_per_1k"])
    property_raw = float(rates["property_per_1k"])
    commuter_mult, commuter_meta = compute_commuter_denominator_boost(
        lat, lon,
        violent_per_1k=violent_raw,
        property_per_1k=property_raw,
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
        "commuter_context": commuter_meta,
    }
    if commuter_meta.get("commuter_denominator_boost"):
        details["effective_pop_denominator_multiplier"] = commuter_meta.get("effective_pop_multiplier")
    if population_denominator_meta:
        details["population_denominator"] = population_denominator_meta
    return final_score, details
