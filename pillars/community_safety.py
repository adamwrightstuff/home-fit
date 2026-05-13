"""
Community Safety pillar — 0-100 score reflecting how safe a neighborhood is
relative to other places of the same area type.

Inputs
------
- Violent crime rate  (assault, robbery, homicide) per 1,000 residents
- Property crime rate (burglary, larceny, vehicle theft) per 1,000 residents
- Year-over-year violent crime trend (optional, ±5-point modifier)

Scoring
-------
1. Z-score each rate against area-type baselines (inverted: lower crime → higher z).
2. Blend: 65% violent slot + 35% property slot (both clipped ±2.5, mapped to 0-100).
3. Add capped trend modifier: improving trend → +up to 5pts, worsening → -up to 5pts.
4. Final = clip(blend + trend_delta, 0, 100).

Data sources
------------
- NYC metro:  NYPD Complaint Data via NYC Open Data (Socrata)
- LA metro:   LAPD Crime Data via LA Open Data (Socrata, legacy through 2024)
- All others: FBI Crime Data Explorer API (requires FBI_CRIME_API_KEY env var)
- Degraded:   score=None when no data available; does not contribute to total.

Baselines
---------
Stored in data/community_safety_baselines.json.
Override path via COMMUNITY_SAFETY_BASELINES_PATH env var.
Rebuild with scripts/baselines/build_community_safety_baselines.py.
"""

from __future__ import annotations

import json
import math
import os
from typing import Any, Dict, Optional, Tuple

from data_sources.crime_api import get_crime_rates
from logging_config import get_logger

logger = get_logger(__name__)

_BASE_DIR = os.path.dirname(os.path.dirname(__file__))
_DEFAULT_DATA_DIR = os.path.join(_BASE_DIR, "data")

_BASELINES_PATH = os.getenv(
    "COMMUNITY_SAFETY_BASELINES_PATH",
    os.path.join(_DEFAULT_DATA_DIR, "community_safety_baselines.json"),
)

# ---------------------------------------------------------------------------
# Load baselines at import time
# ---------------------------------------------------------------------------

_baselines: Dict[str, Dict[str, float]] = {}

try:
    if os.path.exists(_BASELINES_PATH):
        with open(_BASELINES_PATH, "r", encoding="utf-8") as _f:
            _raw = json.load(_f)
        for key, val in _raw.items():
            if key.startswith("_"):
                continue
            if isinstance(val, dict) and "violent_mean" in val:
                _baselines[key] = val
        if _baselines:
            logger.info("Loaded community safety baselines for %d area types", len(_baselines))
except Exception as e:
    logger.warning("Failed to load community safety baselines: %s", e)


# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------

_CLIP = 2.5
_TREND_CAP_PTS = 5.0

# Commercial/retail-hub detector: when property crime rate is this many times
# higher than violent crime AND violent rate is below this threshold, the area's
# crime profile is dominated by commercial theft (shoplifting, package theft,
# pickpocketing) rather than community violence.  Dampen property weight so
# a larceny-heavy commercial corridor doesn't score below a violent neighbourhood.
_COMMERCIAL_PROPERTY_RATIO = 8.0   # property_per_1k / violent_per_1k threshold
_COMMERCIAL_VIOLENT_CEILING = 8.0  # only apply dampening when violent_per_1k < this
_COMMERCIAL_PROPERTY_WEIGHT = 0.15  # reduced from default 0.35


def _z_to_slot(z: float) -> float:
    """Clip z to ±2.5 and map to 0–100 (higher is safer, so z is inverted)."""
    z_inv = -z  # lower crime → higher z_inv → higher score
    z_clipped = max(-_CLIP, min(_CLIP, z_inv))
    return ((z_clipped + _CLIP) / (2 * _CLIP)) * 100.0


def _get_baselines(area_type: Optional[str]) -> Dict[str, float]:
    at = (area_type or "").lower().replace(" ", "_") if area_type else None
    if at and at in _baselines:
        return _baselines[at]
    return _baselines.get("default", {
        "violent_mean": 3.5, "violent_std": 4.0,
        "property_mean": 12.0, "property_std": 9.0,
    })


def _score_rates(
    violent_per_1k: float,
    property_per_1k: float,
    area_type: Optional[str],
) -> Tuple[float, float, float, float]:
    """
    Compute violent slot, property slot, and blended raw score.
    Returns (violent_slot, property_slot, raw_score, violent_z).
    """
    bl = _get_baselines(area_type)
    v_mean = float(bl.get("violent_mean", 3.5))
    v_std = float(bl.get("violent_std", 4.0))
    p_mean = float(bl.get("property_mean", 12.0))
    p_std = float(bl.get("property_std", 9.0))

    v_z = (violent_per_1k - v_mean) / v_std if v_std > 0 else 0.0
    p_z = (property_per_1k - p_mean) / p_std if p_std > 0 else 0.0

    v_slot = _z_to_slot(v_z)
    p_slot = _z_to_slot(p_z)

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
    return v_slot, p_slot, raw, v_z


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
    """
    pop = population or 10_000
    bl = _get_baselines(area_type)

    rates = get_crime_rates(
        lat, lon,
        city=city,
        state_abbr=state,
        area_type=area_type,
        population=pop,
    )

    if rates is None:
        details: Dict[str, Any] = {
            "violent_per_1k": None,
            "property_per_1k": None,
            "trend_pct": None,
            "trend_delta": 0.0,
            "source": "none",
            "data_available": False,
            "area_type_baseline": bl,
        }
        return None, details

    violent_per_1k = rates["violent_per_1k"]
    property_per_1k = rates["property_per_1k"]
    trend_pct = rates.get("trend_pct")

    v_slot, p_slot, raw_score, v_z = _score_rates(violent_per_1k, property_per_1k, area_type)
    td = _trend_delta(trend_pct)
    final_score = round(max(0.0, min(100.0, raw_score + td)), 1)

    details = {
        "violent_per_1k": round(violent_per_1k, 3),
        "property_per_1k": round(property_per_1k, 3),
        "trend_pct": trend_pct,
        "trend_delta": td,
        "violent_slot": round(v_slot, 1),
        "property_slot": round(p_slot, 1),
        "raw_score": round(raw_score, 1),
        "source": rates.get("source", "unknown"),
        "data_available": True,
        "area_type_baseline": bl,
        "incidents_current": rates.get("incidents_current"),
        "data_period": rates.get("data_period"),
        "agency_name": rates.get("agency_name"),
    }
    return final_score, details
