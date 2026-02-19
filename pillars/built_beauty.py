"""
Built Beauty pillar implementation (architecture, form, and built enhancers).
"""

from __future__ import annotations

import math
import os
from typing import Dict, List, Optional, Tuple

from logging_config import get_logger

from data_sources import osm_api
from data_sources.data_quality import assess_pillar_data_quality, get_effective_area_type
from data_sources.radius_profiles import get_radius_profile
from pillars.beauty_common import BUILT_ENHANCER_CAP, normalize_beauty_score

logger = get_logger(__name__)


def _enhancer_linear_plus_tail(
    count: int,
    *,
    per_unit: float,
    linear_cap_count: int,
    tail_max_points: float,
    tail_halfsat: float,
) -> float:
    """
    Map a feature count to points with:
    - linear growth up to `linear_cap_count` (preserves current behavior)
    - diminishing returns above that, saturating to `tail_max_points` additional points
    """
    try:
        c = int(count)
    except (TypeError, ValueError):
        c = 0
    c = max(0, c)

    linear = min(c, linear_cap_count) * per_unit
    if c <= linear_cap_count:
        return float(linear)

    # Diminishing-returns tail: saturating exponential.
    # Tail starts at 0 when c == linear_cap_count.
    tail_count = float(c - linear_cap_count)
    halfsat = max(1e-6, float(tail_halfsat))
    tail = float(tail_max_points) * (1.0 - math.exp(-tail_count / halfsat))
    return float(linear + tail)


def _fetch_historic_data(lat: float, lon: float, radius_m: int = 1000) -> Dict:
    """
    Fetch historic data once (OSM landmarks + Census building age).
    """
    from data_sources import census_api
    from data_sources import nrhp

    year_built_data = census_api.get_year_built_data(lat, lon)
    median_year_built = year_built_data.get('median_year_built') if year_built_data else None
    vintage_pct = year_built_data.get('vintage_pct', 0) if year_built_data else None

    charm_data = osm_api.query_charm_features(lat, lon, radius_m=radius_m)
    if charm_data:
        historic_landmarks = charm_data.get('historic', [])
        if len(historic_landmarks) == 0:
            logger.warning("No historic landmarks found in charm_data for %s, %s. Keys: %s", lat, lon, list(charm_data.keys()))
    else:
        logger.warning("charm_data query returned None for %s, %s", lat, lon)
        historic_landmarks = []
    historic_landmarks_count = len(historic_landmarks)

    nrhp_result: Dict = {}
    try:
        nrhp_result = nrhp.query_nrhp(lat, lon, radius_m=radius_m) or {}
    except Exception as exc:
        logger.warning("NRHP lookup failed for %s, %s: %s", lat, lon, exc)
        nrhp_result = {}

    return {
        'year_built_data': year_built_data,
        'median_year_built': median_year_built,
        'vintage_pct': vintage_pct,
        'charm_data': charm_data,
        'historic_landmarks': historic_landmarks,
        'historic_landmarks_count': historic_landmarks_count,
        # Historic register (bundled dataset)
        'nrhp': nrhp_result,
        'nrhp_count': nrhp_result.get("count", 0) if isinstance(nrhp_result, dict) else 0,
        'nrhp_nearest_distance_m': nrhp_result.get("nearest_distance_m") if isinstance(nrhp_result, dict) else None,
        'nrhp_styles': nrhp_result.get("styles", []) if isinstance(nrhp_result, dict) else [],
        'nrhp_periods': nrhp_result.get("periods", []) if isinstance(nrhp_result, dict) else [],
    }


def _score_architectural_diversity(lat: float, lon: float, city: Optional[str] = None,
                                   location_scope: Optional[str] = None,
                                   area_type: Optional[str] = None,
                                   location_name: Optional[str] = None,
                                   test_overrides: Optional[Dict[str, float]] = None,
                                   precomputed_arch_diversity: Optional[Dict] = None,
                                   density: Optional[float] = None,
                                   form_context: Optional[str] = None) -> Tuple[Optional[float], Dict]:
    """
    Score architectural beauty (0-50 points native range).
    """
    try:
        from data_sources import arch_diversity, census_api, data_quality, geocoding
        from data_sources.data_quality import get_effective_area_type

        radius_m = 2000
        if area_type:
            rp = get_radius_profile('built_beauty', area_type, location_scope)
            radius_m = int(rp.get('architectural_diversity_radius_m', 2000))

        # Use precomputed data if available (from main.py initial call), otherwise compute
        if precomputed_arch_diversity is not None:
            diversity_metrics = precomputed_arch_diversity
        else:
            diversity_metrics = arch_diversity.compute_arch_diversity(lat, lon, radius_m=radius_m)

        if 'error' in diversity_metrics:
            logger.warning("Architectural diversity computation failed: %s", diversity_metrics.get('error'))
            # Check if this is a recoverable error (beauty_valid=True means we can continue with defaults)
            beauty_valid = diversity_metrics.get("beauty_valid", False)
            if not beauty_valid:
                # Hard failure - cannot continue
                user_message = diversity_metrics.get('user_message', 'OSM building data temporarily unavailable. Please try again.')
                retry_suggested = diversity_metrics.get('retry_suggested', False)
                details = {
                    "error": diversity_metrics.get('error'),
                    "note": "OSM building data unavailable",
                    "user_message": user_message,
                    "retry_suggested": retry_suggested,
                    "beauty_valid": False,
                    "data_warning": diversity_metrics.get("data_warning", "api_error"),
                    "confidence_0_1": diversity_metrics.get("confidence_0_1", 0.0),
                    "score": None
                }
                return None, details
            # Soft failure (beauty_valid=True) - continue with zero/default values
            # The diversity_metrics dict already has all metrics set to 0, so we can proceed
            logger.info("Continuing built beauty calculation with default values due to API error (beauty_valid=True)")

        # Use pre-computed density if provided, otherwise fetch it
        if density is None:
            density = census_api.get_population_density(lat, lon) or 0.0
        
        if area_type is None:
            if not city:
                city = geocoding.reverse_geocode(lat, lon)
            area_type = data_quality.detect_area_type(
                lat,
                lon,
                density,
                city=city,
                location_input=location_name
            )

        historic_data = _fetch_historic_data(lat, lon, radius_m=radius_m)
        historic_landmarks = historic_data.get('historic_landmarks_count', 0)
        median_year_built = historic_data.get('median_year_built')
        nrhp_count = historic_data.get("nrhp_count", 0)
        # Extract pre_1940_pct to distinguish historic neighborhoods with infill from modern areas
        year_built_data = historic_data.get('year_built_data', {})
        pre_1940_pct = year_built_data.get('pre_1940_pct') if isinstance(year_built_data, dict) else None

        metric_override_keys = {
            "levels_entropy",
            "building_type_diversity",
            "footprint_area_cv",
            "block_grain",
            "streetwall_continuity",
            "setback_consistency",
            "facade_rhythm",
            "architecture_score"
        }
        metric_overrides: Dict[str, float] = {}
        if test_overrides:
            for override_key in metric_override_keys:
                if override_key in test_overrides and test_overrides[override_key] is not None:
                    try:
                        metric_overrides[override_key] = float(test_overrides[override_key])
                    except (TypeError, ValueError):
                        logger.warning("Ignoring invalid architectural override %s=%r", override_key, test_overrides[override_key])

        # Get contextual tags (new system) for scoring and metadata
        # Compute this BEFORE calling scoring function so we can pass it
        from data_sources.data_quality import get_contextual_tags
        contextual_tags = get_contextual_tags(
            area_type,
            density,
            diversity_metrics.get("built_coverage_ratio"),
            median_year_built,
            historic_landmarks,
            business_count=None,  # Not available here, but tags will work without it
            levels_entropy=diversity_metrics.get("levels_entropy"),
            building_type_diversity=diversity_metrics.get("building_type_diversity"),
            footprint_area_cv=diversity_metrics.get("footprint_area_cv"),
            pre_1940_pct=pre_1940_pct
        )

        beauty_score_result = arch_diversity.score_architectural_diversity_as_beauty(
            diversity_metrics.get("levels_entropy", 0),
            diversity_metrics.get("building_type_diversity", 0),
            diversity_metrics.get("footprint_area_cv", 0),
            area_type,
            density,
            diversity_metrics.get("built_coverage_ratio"),
            historic_landmarks=historic_landmarks,
            median_year_built=median_year_built,
            vintage_share=historic_data.get('vintage_pct'),
            lat=lat,
            lon=lon,
            metric_overrides=metric_overrides if metric_overrides else None,
            material_profile=diversity_metrics.get("material_profile"),
            heritage_profile=diversity_metrics.get("heritage_profile"),
            type_category_diversity=diversity_metrics.get("type_category_diversity"),
            height_stats=diversity_metrics.get("height_stats"),
            contextual_tags=contextual_tags,
            pre_1940_pct=pre_1940_pct,
            nrhp_count=nrhp_count,
        )

        if isinstance(beauty_score_result, tuple):
            beauty_score, coverage_cap_metadata = beauty_score_result
            # Ensure coverage_cap_metadata is a dict, not None
            if coverage_cap_metadata is None:
                coverage_cap_metadata = {}
        else:
            beauty_score = beauty_score_result
            coverage_cap_metadata = {}

        # ------------------------------------------------------------------
        # Calibrated architecture scorer (0–100), mapped to 0–50 for Built Beauty.
        # Enabled by default; can be disabled via env for rollback.
        # ------------------------------------------------------------------
        use_calibrated = os.getenv("HOMEFIT_USE_CALIBRATED_BUILT_BEAUTY", "1").strip() == "1"
        legacy_beauty_score_0_50 = float(beauty_score or 0.0)
        calibrated_beauty_score_0_100 = None
        if use_calibrated and not (metric_overrides and "architecture_score" in metric_overrides):
            try:
                from pillars.architectural_beauty_calibrated import compute_calibrated_architectural_beauty_score

                # Map existing pipeline outputs to the calibrated model's proxy fields.
                parking_fraction = coverage_cap_metadata.get("parking_share_estimate")
                try:
                    parking_fraction = float(parking_fraction) if parking_fraction is not None else None
                except (TypeError, ValueError):
                    parking_fraction = None

                block_grain = coverage_cap_metadata.get("block_grain")
                try:
                    block_grain = float(block_grain) if block_grain is not None else None
                except (TypeError, ValueError):
                    block_grain = None

                # Heuristic conversion: higher block_grain (finer) -> smaller block size.
                block_size_m = None
                if block_grain is not None:
                    block_size_m = max(60.0, min(700.0, 420.0 - 3.5 * block_grain))

                frontage = coverage_cap_metadata.get("streetwall_continuity")
                try:
                    frontage = float(frontage) if frontage is not None else None
                except (TypeError, ValueError):
                    frontage = None

                # Coherence proxy: use model coherence signal when available (0–1 -> 0–100),
                # and boost when contextual tags indicate historic/rowhouse fabric.
                coherence = coverage_cap_metadata.get("age_coherence_signal")
                coherence_score = None
                try:
                    coherence_score = float(coherence) * 100.0 if coherence is not None else None
                except (TypeError, ValueError):
                    coherence_score = None
                if coherence_score is None:
                    coherence_score = 0.0
                if "historic" in (contextual_tags or []):
                    coherence_score = max(coherence_score, 92.0)
                if "rowhouse" in (contextual_tags or []):
                    coherence_score = max(coherence_score, 95.0)

                calibrated_beauty_score_0_100 = compute_calibrated_architectural_beauty_score(
                    {
                        "height_diversity": diversity_metrics.get("levels_entropy", 0),
                        "type_diversity": diversity_metrics.get("building_type_diversity", 0),
                        "footprint_variation": diversity_metrics.get("footprint_area_cv", 0),
                        "built_coverage": diversity_metrics.get("built_coverage_ratio", 0),
                        "ParkingFraction": parking_fraction,
                        "BlockSize": block_size_m,
                        "FrontageContinuity": frontage,
                        "StreetWidthToHeight": None,
                        "HistoricCoherence": coherence_score,
                    }
                )

                # Replace architecture score used by Built Beauty (0–50).
                beauty_score = float(calibrated_beauty_score_0_100) / 2.0
            except Exception as e:
                logger.warning("Calibrated Built Beauty scorer failed; falling back to legacy: %s", e)
                beauty_score = legacy_beauty_score_0_50
        
        # Use form_context if provided (computed once in main.py), otherwise compute it
        # This ensures form_context is shared across beauty pillars
        if form_context is None:
            # Fallback: compute form_context if not provided (for backward compatibility)
            effective_area_type = get_effective_area_type(
                area_type,
                density,
                levels_entropy=diversity_metrics.get("levels_entropy"),
                building_type_diversity=diversity_metrics.get("building_type_diversity"),
                historic_landmarks=historic_landmarks,
                median_year_built=median_year_built,
                built_coverage_ratio=diversity_metrics.get("built_coverage_ratio"),
                footprint_area_cv=diversity_metrics.get("footprint_area_cv"),
                pre_1940_pct=pre_1940_pct,
                material_profile=diversity_metrics.get("material_profile"),
                use_multinomial=True
            )
        else:
            effective_area_type = form_context

        def _r2(value):
            return round(value, 2) if isinstance(value, (int, float)) else None

        details = {
            "score": round(beauty_score, 1),
            "max_score": 50.0,
            "metrics": {
                "height_diversity": diversity_metrics.get("levels_entropy", 0),
                "type_diversity": diversity_metrics.get("building_type_diversity", 0),
                "type_category_diversity": diversity_metrics.get("type_category_diversity"),
                "footprint_variation": diversity_metrics.get("footprint_area_cv", 0),
                "built_coverage_ratio": diversity_metrics.get("built_coverage_ratio", 0),
                # This is the naive aggregate computed in `compute_arch_diversity` from
                # height/type/footprint. The UI expects it for debugging/interpretability.
                "diversity_score": diversity_metrics.get("diversity_score", 0),
                "block_grain": coverage_cap_metadata.get("block_grain", 0),
                "streetwall_continuity": coverage_cap_metadata.get("streetwall_continuity", 0),
                "setback_consistency": coverage_cap_metadata.get("setback_consistency", 0),
                "facade_rhythm": coverage_cap_metadata.get("facade_rhythm", 0)
            },
            # Rule-based scoring metadata (from Wave 1 switch)
            "design_score": coverage_cap_metadata.get("design_score"),
            "form_score": coverage_cap_metadata.get("form_score"),
            "scoring_method": coverage_cap_metadata.get("scoring_method"),
            "classification": {
                "base_area_type": area_type,
                "effective_area_type": effective_area_type,
                "density": density,
                "contextual_tags": contextual_tags  # New tagging system
            },
            "historic_context": {
                "landmarks": historic_landmarks,
                "median_year_built": median_year_built,
                "nrhp_count": historic_data.get("nrhp_count", 0),
                "nrhp_nearest_distance_m": historic_data.get("nrhp_nearest_distance_m"),
                "nrhp_styles": historic_data.get("nrhp_styles", []),
                "nrhp_periods": historic_data.get("nrhp_periods", []),
                "heritage_buildings": (coverage_cap_metadata.get("heritage_profile") or {}).get("count", 0),
                "heritage_designations": (coverage_cap_metadata.get("heritage_profile") or {}).get("designations", []),
                "historic_tagged": (coverage_cap_metadata.get("heritage_profile") or {}).get("historic_tagged", 0),
                "heritage_significance": (coverage_cap_metadata.get("heritage_profile") or {}).get("significance_score", 0)
            },
            "material_profile": coverage_cap_metadata.get("material_profile"),
            "heritage_profile": coverage_cap_metadata.get("heritage_profile"),
            "sources": ["OSM"],
            "beauty_valid": diversity_metrics.get("beauty_valid") if "beauty_valid" in diversity_metrics else True,
            "data_warning": diversity_metrics.get("data_warning"),
            "confidence_0_1": diversity_metrics.get("confidence_0_1") if "confidence_0_1" in diversity_metrics else 1.0,
            "error": diversity_metrics.get("error") if "error" in diversity_metrics else None,
            "retry_suggested": diversity_metrics.get("retry_suggested", False) if "error" in diversity_metrics else False,
            "osm_building_coverage": diversity_metrics.get("osm_building_coverage") or diversity_metrics.get("built_coverage_ratio", 0),
            "coverage_cap_applied": coverage_cap_metadata.get("coverage_cap_applied", False),
            "original_score_before_cap": coverage_cap_metadata.get("original_score_before_cap"),
            "cap_reason": coverage_cap_metadata.get("cap_reason"),
            "form_metrics_confidence": {
                "block_grain": coverage_cap_metadata.get("block_grain_confidence", 0),
                "streetwall_continuity": coverage_cap_metadata.get("streetwall_confidence", 0),
                "setback_consistency": coverage_cap_metadata.get("setback_confidence", 0),
                "facade_rhythm": coverage_cap_metadata.get("facade_rhythm_confidence", 0)
            },
            "height_stats": coverage_cap_metadata.get("height_stats") or diversity_metrics.get("height_stats"),
            "expected_coverage": coverage_cap_metadata.get("expected_coverage"),
            "material_entropy": coverage_cap_metadata.get("material_entropy"),
            "material_tagged_ratio": coverage_cap_metadata.get("material_tagged_ratio"),
            "bonus_breakdown": {
                "material": _r2(coverage_cap_metadata.get("material_bonus")),
                "heritage": _r2(coverage_cap_metadata.get("heritage_bonus")),
                "register": _r2(coverage_cap_metadata.get("register_bonus")),
                "age": _r2(coverage_cap_metadata.get("age_bonus")),
                "age_mix": _r2(coverage_cap_metadata.get("age_mix_bonus")),
                "modern_form": _r2(coverage_cap_metadata.get("modern_form_bonus")),
                "street_character": _r2(coverage_cap_metadata.get("street_character_bonus")),
                "rowhouse": _r2(coverage_cap_metadata.get("rowhouse_bonus") or 0.0),
                "serenity": _r2(coverage_cap_metadata.get("serenity_bonus")),
                "scenic": _r2(coverage_cap_metadata.get("scenic_bonus"))
            }
        }
        if coverage_cap_metadata.get("overrides_applied"):
            details["overrides"] = coverage_cap_metadata.get("overrides_applied", [])
            details["override_values"] = coverage_cap_metadata.get("override_values", {})

        logger.debug("Architectural beauty: %.1f/50.0 (effective: %s)", beauty_score, effective_area_type)

        return round(beauty_score, 1), details

    except Exception as exc:
        logger.error("Architectural diversity scoring failed: %s", exc, exc_info=True)
        return None, {"error": str(exc), "note": "Architectural diversity unavailable"}


def calculate_built_beauty(lat: float,
                           lon: float,
                           city: Optional[str] = None,
                           area_type: Optional[str] = None,
                           location_scope: Optional[str] = None,
                           location_name: Optional[str] = None,
                           test_overrides: Optional[Dict[str, float]] = None,
                           enhancers_data: Optional[Dict] = None,
                           disable_enhancers: bool = False,
                           enhancer_radius_m: int = 1500,
                           precomputed_arch_diversity: Optional[Dict] = None,
                           density: Optional[float] = None,
                           form_context: Optional[str] = None) -> Dict:
    """
    Compute built beauty components prior to normalization.
    """
    arch_score, arch_details = _score_architectural_diversity(
        lat,
        lon,
        city=city,
        location_scope=location_scope,
        area_type=area_type,
        location_name=location_name,
        test_overrides=test_overrides,
        precomputed_arch_diversity=precomputed_arch_diversity,
        density=density,
        form_context=form_context
    )

    if arch_score is None:
        arch_component = 0.0
    else:
        arch_component = arch_score

    arch_details = arch_details or {}
    effective_area_type = arch_details.get("classification", {}).get("effective_area_type", area_type) if isinstance(arch_details, dict) else area_type

    built_bonus_raw = 0.0
    built_bonus_scaled = 0.0
    artwork_count: int = 0
    fountain_count: int = 0
    artwork_points: float = 0.0
    fountain_points: float = 0.0
    if not disable_enhancers:
        if enhancers_data is None:
            enhancers_data = osm_api.query_beauty_enhancers(lat, lon, radius_m=enhancer_radius_m)
        try:
            artwork_count = int(enhancers_data.get("artwork", 0))
        except (TypeError, ValueError):
            artwork_count = 0
        try:
            fountain_count = int(enhancers_data.get("fountains", 0))
        except (TypeError, ValueError):
            fountain_count = 0

        # Preserve current behavior for small counts, but allow additional differentiation
        # at high counts via a diminishing-returns tail.
        artwork_points = _enhancer_linear_plus_tail(
            artwork_count,
            per_unit=1.5,
            linear_cap_count=3,      # current artwork cap point (3 * 1.5 = 4.5)
            tail_max_points=2.0,     # additional points beyond the linear cap
            tail_halfsat=8.0,        # how quickly the tail saturates
        )
        fountain_points = _enhancer_linear_plus_tail(
            fountain_count,
            per_unit=0.5,
            linear_cap_count=3,      # current fountain cap point (3 * 0.5 = 1.5)
            tail_max_points=1.0,
            tail_halfsat=6.0,
        )

        built_bonus_raw += artwork_points
        built_bonus_raw += fountain_points

        arch_conf = arch_details.get("confidence_0_1") if isinstance(arch_details, dict) else None
        built_scale = 1.0
        if arch_conf is not None:
            built_scale = 0.5 + 0.5 * max(0.0, min(1.0, arch_conf))

        built_bonus_scaled = min(BUILT_ENHANCER_CAP, built_bonus_raw * built_scale)
    else:
        enhancers_data = enhancers_data or {"artwork": 0, "fountains": 0}

    built_native = max(0.0, arch_component + built_bonus_scaled)
    # Cap at 100 to keep scores in 0-100 range while preserving natural distribution below 100
    # This only affects exceptional locations (built_native > 50) that would score > 100
    built_score_raw = min(100.0, built_native * 2.0)

    built_score_norm, built_norm_meta = normalize_beauty_score(
        built_score_raw,
        effective_area_type
    )

    enhancer_meta = {
        "artwork_count": int(artwork_count) if isinstance(artwork_count, (int, float)) else artwork_count,
        "fountain_count": int(fountain_count) if isinstance(fountain_count, (int, float)) else fountain_count,
        "artwork_points_raw": round(float(artwork_points), 2) if not disable_enhancers else 0.0,
        "fountain_points_raw": round(float(fountain_points), 2) if not disable_enhancers else 0.0,
        "built_raw": round(built_bonus_raw, 2),
        "built_scaled": round(built_bonus_scaled, 2),
        "scaled_total": round(built_bonus_scaled, 2)
    }

    details = {
        "component_score_0_50": round(arch_component, 2),
        "enhancer_bonus_raw": round(built_bonus_raw, 2),
        "enhancer_bonus_scaled": round(built_bonus_scaled, 2),
        "score_before_normalization": round(built_score_raw, 2),
        "normalization": built_norm_meta,
        "architectural_analysis": arch_details,
        "enhancer_bonus": enhancer_meta,
        "source": "built_beauty"
    }

    # Assess data quality (consistent with other pillars)
    combined_data = {
        "architectural_analysis": arch_details,
        "enhancers": enhancers_data or {},
    }
    quality_metrics = assess_pillar_data_quality(
        "built_beauty", combined_data, lat, lon, effective_area_type or area_type or "suburban"
    )

    return {
        "score": built_score_norm,
        "score_before_normalization": built_score_raw,
        "component_score_0_50": arch_component,
        "details": details,
        "architectural_details": arch_details,
        "enhancers": enhancers_data,
        "built_bonus_raw": built_bonus_raw,
        "built_bonus_scaled": built_bonus_scaled,
        "effective_area_type": effective_area_type,
        "data_quality": quality_metrics
    }


def get_built_beauty_score(lat: float,
                           lon: float,
                           city: Optional[str] = None,
                           area_type: Optional[str] = None,
                           location_scope: Optional[str] = None,
                           location_name: Optional[str] = None,
                           test_overrides: Optional[Dict[str, float]] = None,
                           enhancers_data: Optional[Dict] = None,
                           disable_enhancers: bool = False) -> Tuple[float, Dict]:
    """
    Public entry point for the built beauty pillar.
    """
    result = calculate_built_beauty(
        lat,
        lon,
        city=city,
        area_type=area_type,
        location_scope=location_scope,
        location_name=location_name,
        test_overrides=test_overrides,
        enhancers_data=enhancers_data,
        disable_enhancers=disable_enhancers
    )

    return result["score"], result["details"]

