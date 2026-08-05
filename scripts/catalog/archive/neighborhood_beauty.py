"""
Neighborhood Beauty: combined built_environment + natural_beauty pillar.

Replaces the two formerly-independent beauty pillars with a single density-weighted
blend. The blend weight is the validated formula from this session's
data/neighborhood_beauty_wip/blend_full.py work: log-normalized real
classification.density, with a categorical floor for architecturally-dense but
population-sparse area types (urban_core, historic_urban) so commercial cores
(Midtown, Red Hook, Manhattanville) aren't under-weighted on built character just
because few people live there.

BCR ceiling (2026-06-23): built_coverage_ratio (Microsoft footprint-derived) caps how
high density alone can push the built weight. Anchored at BCR_MAX=0.50, corresponding
to the NLCD Medium/High Intensity boundary (~65-80% impervious surface) — the point
where dense urban residential transitions to high-intensity built-over land per USGS
NLCD classification. A place physically covered by 50%+ building footprints has earned
full built-weight regardless of density; below that, density cannot claim more built
character than the land coverage actually supports.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from pillars import built_environment, natural_beauty

# Real catalog-wide density distribution (n=290): p25=5508, p50=11605, p95=95474.
# Anchored at p1-ish (500) through p95 (95474) so the curve spans the real range
# without being distorted by a handful of extreme outliers.
_LOG_LO = math.log10(500)
_LOG_HI = math.log10(95474)

_AREA_TYPE_FLOOR = {"urban_core": 0.65, "historic_urban": 0.65}

# BCR at which building footprint coverage fully justifies maximum built-weight.
# Anchored to NLCD Medium/High Intensity boundary (~65-80% impervious surface).
# Source: USGS National Land Cover Database developed land classification thresholds.
_BCR_MAX = 0.50


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _density_weight(density: Optional[float]) -> Optional[float]:
    if density is None or density <= 0:
        return None
    d = _clamp01((math.log10(density) - _LOG_LO) / (_LOG_HI - _LOG_LO))
    # Widened from a narrower band to 0.25-0.95: a true urban core should be judged
    # almost entirely on built character; low end leans mostly on natural_beauty.
    return 0.25 + 0.70 * d


def _bcr_ceiling(bcr: Optional[float]) -> Optional[float]:
    """Maximum built-weight justified by physical land coverage (Microsoft footprints)."""
    if bcr is None or bcr < 0:
        return None
    return 0.25 + 0.70 * _clamp01(bcr / _BCR_MAX)


def combined_weight(density: Optional[float], effective_area_type: Optional[str],
                    built_coverage_ratio: Optional[float] = None) -> float:
    """Public: density+area-type+BCR blend weight on built_environment (1-w applies to natural)."""
    return _combined_weight(density, effective_area_type, built_coverage_ratio)


def blend_scores(built_score: float,
                 natural_score: float,
                 density: Optional[float],
                 effective_area_type: Optional[str],
                 built_coverage_ratio: Optional[float] = None) -> Dict[str, Any]:
    """Public: combine already-computed built + natural scores into the blend.

    Used by the main scoring path, which runs both underlying scorers itself (so it
    can surface their preferences/details) and only needs the weighted combination.
    """
    w = _combined_weight(density, effective_area_type, built_coverage_ratio)
    return {
        "score": round(w * float(built_score) + (1.0 - w) * float(natural_score), 2),
        "built_weight": round(w, 3),
    }


def _combined_weight(density: Optional[float], effective_area_type: Optional[str],
                     built_coverage_ratio: Optional[float] = None) -> float:
    w = _density_weight(density)
    floor = _AREA_TYPE_FLOOR.get(effective_area_type or "")

    # Cap density-driven weight at what physical land coverage justifies.
    ceiling = _bcr_ceiling(built_coverage_ratio)
    if w is not None and ceiling is not None:
        w = min(w, ceiling)

    if w is None:
        return floor if floor is not None else 0.5
    if floor is not None:
        return max(w, floor)
    return w


def calculate_neighborhood_beauty(lat: float,
                                  lon: float,
                                  city: Optional[str] = None,
                                  area_type: Optional[str] = None,
                                  location_scope: Optional[str] = None,
                                  location_name: Optional[str] = None,
                                  density: Optional[float] = None,
                                  form_context: Optional[str] = None,
                                  built_test_overrides: Optional[Dict[str, float]] = None,
                                  built_enhancers_data: Optional[Dict] = None,
                                  precomputed_arch_diversity: Optional[Dict] = None,
                                  built_character_preference: Optional[str] = None,
                                  built_density_preference: Optional[str] = None,
                                  natural_overrides: Optional[Dict[str, float]] = None,
                                  natural_enhancers_data: Optional[Dict] = None,
                                  precomputed_tree_canopy_5km: Optional[float] = None,
                                  natural_beauty_preference: Optional[List[str]] = None,
                                  disable_enhancers: bool = False,
                                  enhancer_radius_m: int = 1500) -> Dict[str, Any]:
    """
    Compute the combined neighborhood beauty score by running both underlying
    scorers and blending them with a density+area-type weight.
    """
    built_result = built_environment.calculate_built_environment(
        lat, lon,
        city=city,
        area_type=area_type,
        location_scope=location_scope,
        location_name=location_name,
        test_overrides=built_test_overrides,
        enhancers_data=built_enhancers_data,
        disable_enhancers=disable_enhancers,
        enhancer_radius_m=enhancer_radius_m,
        precomputed_arch_diversity=precomputed_arch_diversity,
        density=density,
        form_context=form_context,
        built_character_preference=built_character_preference,
        built_density_preference=built_density_preference,
    )

    natural_result = natural_beauty.calculate_natural_beauty(
        lat, lon,
        city=city,
        area_type=area_type,
        location_scope=location_scope,
        location_name=location_name,
        overrides=natural_overrides,
        enhancers_data=natural_enhancers_data,
        disable_enhancers=disable_enhancers,
        enhancer_radius_m=enhancer_radius_m,
        precomputed_tree_canopy_5km=precomputed_tree_canopy_5km,
        density=density,
        form_context=form_context,
        natural_beauty_preference=natural_beauty_preference,
    )

    effective_area_type = built_result.get("effective_area_type") or area_type

    # Extract BCR from built_result for ceiling calculation (Microsoft footprint-derived).
    bcr: Optional[float] = None
    try:
        bcr = built_result["details"]["architectural_analysis"]["metrics"]["built_coverage_ratio"]
    except (KeyError, TypeError):
        pass

    weight = _combined_weight(density, effective_area_type, bcr)

    built_score = float(built_result["score"])
    natural_score = float(natural_result["score"])
    combined_score = weight * built_score + (1.0 - weight) * natural_score

    details = {
        "built_environment_score": built_score,
        "natural_beauty_score": natural_score,
        "built_weight": round(weight, 3),
        "built_coverage_ratio": bcr,
        "density": density,
        "effective_area_type": effective_area_type,
        "built_environment_details": built_result.get("details"),
        "natural_beauty_details": natural_result.get("details"),
        "source": "neighborhood_beauty",
    }

    return {
        "score": round(combined_score, 2),
        "details": details,
        "built_environment_full": built_result,
        "natural_beauty_full": natural_result,
        "effective_area_type": effective_area_type,
        "data_quality": built_result.get("data_quality"),
    }
