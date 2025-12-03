"""
Legacy neighborhood beauty aggregator (kept for backwards compatibility).

This module now composes the dedicated built_beauty and natural_beauty pillars
to provide the historic single "neighborhood_beauty" score.
"""

from __future__ import annotations

import os
from typing import Dict, Optional, Tuple

from logging_config import get_logger

from data_sources import census_api, data_quality, osm_api
from pillars import built_beauty, natural_beauty
from pillars.beauty_common import (
    BEAUTY_BONUS_CAP,
    BUILT_ENHANCER_CAP,
    NATURAL_ENHANCER_CAP,
    default_beauty_weights,
    normalize_beauty_score,
    parse_beauty_weights,
)

logger = get_logger(__name__)


def get_neighborhood_beauty_score(lat: float, lon: float, city: Optional[str] = None,
                                   beauty_weights: Optional[str] = None,
                                   location_scope: Optional[str] = None,
                                   area_type: Optional[str] = None,
                                   location_name: Optional[str] = None,
                                   test_overrides: Optional[Dict[str, float]] = None,
                                   test_mode: bool = False,
                                   precomputed_built: Optional[Dict] = None,
                                   precomputed_natural: Optional[Dict] = None,
                                   density: Optional[float] = None) -> Tuple[float, Dict]:
    """
    Calculate the legacy neighborhood beauty score (0-100) and detailed breakdown.
    """
    logger.info("Analyzing neighborhood beauty (legacy aggregate)...")

    disable_enhancers = os.getenv("BEAUTY_DISABLE_ENHANCERS", "false").lower() == "true"

    # Establish baseline area type for weighting defaults.
    # Use pre-computed density if provided, otherwise fetch it
    if density is None:
        density = census_api.get_population_density(lat, lon) or 0.0
    if area_type is None:
        default_area_type_for_weights = data_quality.detect_area_type(
            lat,
            lon,
            density,
            city=city,
            location_input=location_name
        )
    else:
        default_area_type_for_weights = area_type

    if precomputed_built is not None and precomputed_natural is not None:
        built_result = precomputed_built
        natural_result = precomputed_natural
        shared_enhancers = built_result.get("enhancers") or natural_result.get("enhancers")
    else:
        shared_enhancers = None
        if not disable_enhancers:
            try:
                shared_enhancers = osm_api.query_beauty_enhancers(lat, lon, radius_m=1500)
            except Exception as exc:  # pragma: no cover - network failures
                logger.warning("Beauty enhancer lookup failed (non-fatal): %s", exc)
                shared_enhancers = None

        built_result = built_beauty.calculate_built_beauty(
            lat,
            lon,
            city=city,
            area_type=area_type,
            location_scope=location_scope,
            location_name=location_name,
            test_overrides=test_overrides,
            enhancers_data=shared_enhancers,
            disable_enhancers=disable_enhancers
        )

        natural_result = natural_beauty.calculate_natural_beauty(
            lat,
            lon,
            city=city,
            area_type=area_type,
            location_scope=location_scope,
            location_name=location_name,
            overrides=test_overrides,
            enhancers_data=shared_enhancers,
            disable_enhancers=disable_enhancers
        )

    arch_component = built_result["component_score_0_50"]
    tree_component = natural_result["tree_score_0_50"]
    arch_details = built_result["architectural_details"]
    tree_details = natural_result["details"]
    enhancers = built_result["enhancers"] or natural_result["enhancers"] or {}

    built_bonus_scaled = built_result["built_bonus_scaled"]
    built_bonus_raw = built_result["built_bonus_raw"]
    natural_bonus_scaled = natural_result["natural_bonus_scaled"]
    natural_bonus_raw = natural_result["natural_bonus_raw"]
    scenic_bonus_raw = natural_result["scenic_bonus_raw"]

    effective_area_type = built_result["effective_area_type"] or area_type or default_area_type_for_weights
    resolved_area_type = (effective_area_type or "").lower() or None

    if beauty_weights is None:
        weights_config = default_beauty_weights(resolved_area_type)
    else:
        weights_config = beauty_weights
    weights = parse_beauty_weights(weights_config)

    max_tree_points = weights.get('trees', 0.5) * 100
    max_arch_points = weights.get('architecture', 0.5) * 100

    base_score = (
        (tree_component * (max_tree_points / 50.0)) +
        (arch_component * (max_arch_points / 50.0))
    )
    normalized_base, normalization_params = normalize_beauty_score(base_score, resolved_area_type)

    beauty_bonus = min(BEAUTY_BONUS_CAP, built_bonus_scaled + natural_bonus_scaled)
    total_score = min(100.0, normalized_base + beauty_bonus)

    calibration_alert = _check_calibration_guardrails(effective_area_type, arch_component, tree_component)

    arch_diversity_summary = {}
    arch_score_native = arch_details.get("score") if isinstance(arch_details, dict) else None
    if isinstance(arch_score_native, (int, float)):
        arch_diversity_summary = {
            "diversity_score": max(0.0, min(100.0, arch_score_native * 2.0)),
            "phase2_confidence": arch_details.get("phase2_confidence"),
            "phase3_confidence": arch_details.get("phase3_confidence"),
            "coverage_cap_applied": arch_details.get("coverage_cap_applied", False)
        }

    combined_data = {
        'tree_score': tree_component,
        'architectural_score': arch_component,
        'tree_details': tree_details,
        'architectural_details': arch_details,
        'architectural_diversity': arch_diversity_summary,
        'calibration_alert': calibration_alert,
        'test_overrides': test_overrides if test_overrides else {}
    }

    # Ensure area_type is available for data quality based on latest classification.
    final_area_type = area_type or effective_area_type or default_area_type_for_weights
    quality_metrics = data_quality.assess_pillar_data_quality('neighborhood_beauty', combined_data, lat, lon, final_area_type)

    try:
        tree_sources = tree_details.get('sources', []) if isinstance(tree_details, dict) else []
        used_gee = any(isinstance(src, str) and src.lower().startswith('gee') for src in tree_sources)
        if used_gee:
            quality_metrics['needs_fallback'] = False
            quality_metrics['fallback_score'] = None
            fm = quality_metrics.get('fallback_metadata', {}) or {}
            fm['fallback_used'] = False
            quality_metrics['fallback_metadata'] = fm
            ds = quality_metrics.get('data_sources', []) or []
            if 'gee' not in ds:
                ds.append('gee')
            quality_metrics['data_sources'] = ds
    except Exception:  # pragma: no cover - defensive
        pass

    enhancer_bonus_breakdown = {
        "built_bonus": round(built_bonus_scaled, 2),
        "natural_bonus": round(natural_bonus_scaled, 2),
        "scaled_bonus": round(beauty_bonus, 2),
        "scenic": natural_result["scenic_metadata"],
        "natural_breakdown": tree_details.get("enhancer_breakdown", {}) if isinstance(tree_details, dict) else {}
    }

    tree_details.setdefault("scenic_proxy", natural_result["scenic_metadata"])
    tree_details.setdefault("enhancer_bonus", {})
    tree_details["enhancer_bonus"].update({
        "natural_raw": round(natural_bonus_raw, 2),
        "scenic_raw": round(scenic_bonus_raw, 2),
        "context_raw": round(natural_result["context_bonus_raw"], 2),
        "natural_scaled": round(natural_bonus_scaled, 2),
        "scaled_total": round(natural_bonus_scaled, 2)
    })

    if isinstance(arch_details, dict):
        arch_details.setdefault("enhancer_bonus", {})
        arch_details["enhancer_bonus"].update({
            "built_raw": round(built_bonus_raw, 2),
            "scaled_total": round(built_bonus_scaled, 2)
        })

    applied_override_summary = {}
    if test_overrides:
        if isinstance(tree_details, dict) and tree_details.get("overrides_applied"):
            applied_override_summary["trees"] = {
                "metrics": tree_details.get("overrides_applied"),
                "values": tree_details.get("override_values", {})
            }
        if isinstance(arch_details, dict) and arch_details.get("overrides"):
            applied_override_summary["architecture"] = {
                "metrics": arch_details.get("overrides"),
                "values": arch_details.get("override_values", {})
            }

    resolved_weights = {
        "trees": round(weights.get('trees', 0.5), 4),
        "architecture": round(weights.get('architecture', 0.5), 4)
    }

    breakdown = {
        "score": round(total_score, 1),
        "breakdown": {
            "trees": round(tree_component, 1),
            "architectural_beauty": round(arch_component, 1),
            "enhancer_bonus": round(beauty_bonus, 1)
        },
        "details": {
            "tree_analysis": tree_details,
            "architectural_analysis": arch_details,
            "enhancers": enhancers or {},
            "enhancer_bonus": beauty_bonus,
            "enhancer_bonus_breakdown": enhancer_bonus_breakdown,
            "test_mode": test_mode,
            "weights": resolved_weights
        },
        "calibration_alert": calibration_alert,
        "weights": resolved_weights,
        "weight_metadata": {
            "input": beauty_weights or "default",
            "area_type": resolved_area_type
        },
        "normalization": normalization_params,
        "data_quality": quality_metrics
    }

    if arch_details.get("error") is not None:
        breakdown["details"]["architecture_status"] = {
            "available": False,
            "reason": arch_details.get("error") or arch_details.get("data_warning") or "unavailable",
            "retry_suggested": arch_details.get("retry_suggested", False)
        }
    else:
        breakdown["details"]["architecture_status"] = {"available": True}

    if applied_override_summary:
        breakdown["details"]["test_overrides_applied"] = applied_override_summary

    logger.info("Neighborhood Beauty Score: %.0f/100", total_score)
    logger.debug(
        "Trees: %.1f/50 | Architectural Beauty: %.1f/50 | Data Quality: %s (%s%% confidence)",
        tree_component,
        arch_component,
        quality_metrics.get('quality_tier', 'unknown'),
        quality_metrics.get('confidence', 'n/a')
    )

    return round(total_score, 1), breakdown


def _check_calibration_guardrails(area_type: str, arch_score: float, tree_score: float) -> bool:
    """
    Check if beauty scores are outside expected calibration ranges.
    
    Returns True if scores are outside expected bands (calibration_alert).
    
    Expected ranges by classification:
    - Urban Historic: Architecture 38-50, Trees 12-28
    - Suburban: Architecture 28-45, Trees 22-40
    - Estate Suburbs (Beverly Hills, River Oaks): Architecture 22-38, Trees 25-40
    """
    if not area_type:
        return False
    
    # Define expected calibration ranges
    calibration_ranges = {
        "urban_historic": {
            "arch": (38, 50),
            "trees": (12, 28)
        },
        "historic_urban": {  # Alias for urban_historic
            "arch": (38, 50),
            "trees": (12, 28)
        },
        "suburban": {
            "arch": (28, 45),
            "trees": (22, 40)
        },
        "urban_residential": {
            "arch": (38, 50),  # Similar to urban_historic
            "trees": (12, 28)
        },
        "urban_core": {
            # For estate suburbs like Beverly Hills, River Oaks
            # We'll check density/built_coverage to distinguish
            # For now, use broader range for urban_core
            "arch": (22, 50),
            "trees": (10, 50)
        },
    }
    
    # Get expected range for this area type
    ranges = calibration_ranges.get(area_type)
    if not ranges:
        # Unknown area type - no calibration check
        return False
    
    arch_min, arch_max = ranges["arch"]
    trees_min, trees_max = ranges["trees"]
    
    # Check if scores are outside expected ranges
    arch_out_of_range = arch_score < arch_min or arch_score > arch_max
    trees_out_of_range = tree_score < trees_min or tree_score > trees_max
    
    return arch_out_of_range or trees_out_of_range


def _score_nyc_trees(tree_count: int) -> float:
    """Score NYC street trees."""
    if tree_count >= 50:
        return 50.0
    elif tree_count >= 30:
        return 40.0
    elif tree_count >= 20:
        return 30.0
    elif tree_count >= 10:
        return 20.0
    else:
        return tree_count * 1.5


def _score_tree_canopy(canopy_pct: float) -> float:
    """Score tree canopy with a softened, piecewise-linear curve."""
    canopy = max(0.0, min(100.0, canopy_pct))
    if canopy <= 20.0:
        return canopy * 1.1
    if canopy <= 55.0:
        return 22.0 + (canopy - 20.0) * 0.7
    if canopy <= 70.0:
        return 46.5 + (canopy - 55.0) * 0.25
    return 50.0
