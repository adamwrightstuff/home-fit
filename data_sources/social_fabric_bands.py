"""
National and regional band calibration for Social Fabric pillar.

Maps substantive raw metrics (rootedness %, civic node counts) to 0–100 scores
using piecewise-linear anchors tied to documented quantile bands, not rank scores.
Regional adjustment nudges rooted % using national vs division medians so typical
mobility patterns inform the input without percentile ranking.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from logging_config import get_logger

logger = get_logger(__name__)

_BASE_DIR = os.path.dirname(os.path.dirname(__file__))
_DEFAULT_PATH = os.path.join(_BASE_DIR, "data", "social_fabric_bands.json")

_BANDS_PATH = os.getenv("SOCIAL_FABRIC_BANDS_PATH", _DEFAULT_PATH)

# Default score anchors at p10…p90 knots (substantive scale, not “your rank”).
_DEFAULT_SCORE_ANCHORS = (12.0, 30.0, 50.0, 70.0, 85.0)

_bands_cache: Optional[Dict[str, Any]] = None


def load_bands() -> Optional[Dict[str, Any]]:
    global _bands_cache
    if _bands_cache is not None:
        return _bands_cache
    if not _BANDS_PATH or not os.path.isfile(_BANDS_PATH):
        logger.info("Social Fabric bands file not found at %s", _BANDS_PATH)
        _bands_cache = None
        return None
    try:
        with open(_BANDS_PATH, "r", encoding="utf-8") as f:
            _bands_cache = json.load(f)
        logger.info("Loaded Social Fabric bands from %s", _BANDS_PATH)
        return _bands_cache
    except Exception as e:
        logger.warning("Failed to load Social Fabric bands from %s: %s", _BANDS_PATH, e)
        _bands_cache = None
        return None


def _anchors_from_bands(bands: Mapping[str, Any]) -> Tuple[float, ...]:
    sa = bands.get("score_anchors") or {}
    at = sa.get("at_knot")
    if isinstance(at, list) and len(at) >= 5:
        return tuple(float(x) for x in at[:5])
    return _DEFAULT_SCORE_ANCHORS


def interpolate_from_quantile_bands(
    x: float,
    quantiles: Mapping[str, Any],
    score_anchors: Sequence[float],
) -> float:
    """
    Map a raw value x to 0–100 using piecewise linear interpolation between
    (p10, s10)…(p90, s90), with linear tails from 0 and to 100.
    """
    try:
        v = float(x)
    except (TypeError, ValueError):
        return 0.0

    q10 = float(quantiles.get("p10", 0.0))
    q25 = float(quantiles.get("p25", q10))
    q50 = float(quantiles.get("p50", q25))
    q75 = float(quantiles.get("p75", q50))
    q90 = float(quantiles.get("p90", q75))

    s10, s25, s50, s75, s90 = (float(score_anchors[i]) for i in range(5))

    knots: List[Tuple[float, float]] = [
        (q10, s10),
        (q25, s25),
        (q50, s50),
        (q75, s75),
        (q90, s90),
    ]
    knots.sort(key=lambda t: t[0])

    if v <= knots[0][0]:
        x0, y0 = knots[0]
        if x0 <= 0:
            return max(0.0, min(100.0, y0))
        return max(0.0, min(100.0, (v / x0) * y0))

    if v >= knots[-1][0]:
        x9, y9 = knots[-1]
        p_upper = quantiles.get("p100")
        if p_upper is not None:
            try:
                upper = float(p_upper)
            except (TypeError, ValueError):
                upper = x9 + max(x9 - q75, 1.0) * 2.0
        else:
            # Extrapolate above p90: default upper knot for unbounded counts (civic nodes).
            upper = x9 + max(x9 - q75, 1.0) * 2.0
        if upper <= x9:
            upper = x9 + 1.0
        if v >= upper:
            return 100.0
        t = (v - x9) / (upper - x9)
        return max(0.0, min(100.0, y9 + t * (100.0 - y9)))

    for i in range(len(knots) - 1):
        x0, y0 = knots[i]
        x1, y1 = knots[i + 1]
        if x0 <= v <= x1:
            if x1 == x0:
                return max(0.0, min(100.0, y0))
            t = (v - x0) / (x1 - x0)
            return max(0.0, min(100.0, y0 + t * (y1 - y0)))

    return max(0.0, min(100.0, knots[-1][1]))


def adjust_rooted_pct_for_regional_bands(
    rooted_pct: float,
    division_code: Optional[str],
    bands: Mapping[str, Any],
) -> float:
    """
    Nudge rooted % using national vs division median so regional mobility norms
    inform the substantive input without percentile ranking.
    """
    ra = bands.get("regional_adjustment") or {}
    sub = ra.get("rooted_pct") or {}
    if not sub.get("enabled", True):
        return rooted_pct
    try:
        strength = float(sub.get("strength", 0.22))
    except (TypeError, ValueError):
        strength = 0.22

    nat = (bands.get("national") or {}).get("rooted_pct") or {}
    try:
        nat_p50 = float(nat.get("p50"))
    except (TypeError, ValueError):
        return rooted_pct

    div_map = bands.get("by_division") or {}
    div = div_map.get(division_code or "") if division_code else None
    if not isinstance(div, dict):
        return rooted_pct
    rp = div.get("rooted_pct") or {}
    try:
        div_p50 = float(rp.get("p50"))
    except (TypeError, ValueError):
        return rooted_pct

    adjusted = rooted_pct + strength * (nat_p50 - div_p50)
    return max(0.0, min(100.0, adjusted))


def score_stability_from_bands(
    rooted_pct: float,
    division_code: Optional[str],
    bands: Mapping[str, Any],
) -> float:
    """National anchored curve on adjusted rootedness; regional medians inform adjustment only."""
    adjusted = adjust_rooted_pct_for_regional_bands(rooted_pct, division_code, bands)
    anchors = _anchors_from_bands(bands)
    nat = (bands.get("national") or {}).get("rooted_pct") or {}
    return interpolate_from_quantile_bands(adjusted, nat, anchors)


def _civic_quantiles_for_area(
    bands: Mapping[str, Any],
    key: str,
    area_type: Optional[str],
) -> Dict[str, Any]:
    block = bands.get(key) or {}
    by_type = block.get("by_area_type") or {}
    at = area_type or "default"
    q = by_type.get(at) or by_type.get("default") or by_type.get("suburban")
    if not isinstance(q, dict):
        q = by_type.get("suburban") or {}
    return q


def civic_band_area_type_for_radius(radius_m: int) -> str:
    """Map search radius to band table (density tiers), independent of morphological area_type."""
    if radius_m <= 600:
        return "urban_core"
    if radius_m <= 1200:
        return "suburban"
    return "rural"


def score_civic_gathering_from_bands(
    count: int,
    area_type: Optional[str],
    bands: Mapping[str, Any],
    proximity: bool,
) -> float:
    key = "civic_nodes_proximity_1500m" if proximity else "civic_nodes_density_800m"
    quant = _civic_quantiles_for_area(bands, key, area_type)
    if not quant:
        return 0.0
    anchors = _anchors_from_bands(bands)
    return interpolate_from_quantile_bands(float(count), quant, anchors)
