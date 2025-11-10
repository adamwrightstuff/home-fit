"""
Neighborhood Beauty Pillar
Uses objective, real data sources:
- Trees (0-50): OSM tree count + Census canopy percentage
- Architectural Beauty (0-50): Building height, type, and footprint variation
  (Architectural beauty uses historic context to adjust scoring targets)
  Both components use native 0-50 ranges (no scaling needed)
"""

import os
from typing import Dict, Tuple, Optional
AREA_NORMALIZATION = {
    "historic_urban": {"shift": 8.0, "scale": 1.01, "max": 96.0},
    "suburban": {"shift": 9.5, "scale": 1.02, "max": 95.0},
    "urban_residential": {"shift": -2.5, "scale": 0.95, "max": 91.0},
    "urban_core": {"shift": -2.5, "scale": 0.95, "max": 93.0},
    "exurban": {"shift": 13.0, "scale": 1.02, "max": 94.0},
    "rural": {"shift": 10.0, "scale": 1.02, "max": 93.0},
    "urban_core_lowrise": {"shift": 3.0, "scale": 0.96, "max": 88.0},
}


def _normalize_beauty_score(score: float, area_type: Optional[str]) -> Tuple[float, Optional[Dict[str, float]]]:
    if not area_type:
        return score, None
    params = AREA_NORMALIZATION.get(area_type)
    if not params:
        return score, None
    scaled = score * params.get("scale", 1.0)
    shifted = scaled + params.get("shift", 0.0)
    capped = min(params.get("max", 100.0), shifted)
    return max(0.0, capped), params

from data_sources import osm_api, census_api, data_quality
from data_sources.radius_profiles import get_radius_profile
from logging_config import get_logger

logger = get_logger(__name__)

# Try to import NYC API (only available for NYC addresses)
try:
    from data_sources import nyc_api as nyc_api
except ImportError:
    nyc_api = None

# Try to import Street Tree API (for multiple cities)
try:
    from data_sources import street_tree_api
except ImportError:
    street_tree_api = None


def get_neighborhood_beauty_score(lat: float, lon: float, city: Optional[str] = None,
                                   beauty_weights: Optional[str] = None,
                                   location_scope: Optional[str] = None,
                                   area_type: Optional[str] = None,
                                   location_name: Optional[str] = None,
                                   test_overrides: Optional[Dict[str, float]] = None,
                                   test_mode: bool = False) -> Tuple[float, Dict]:
    """
    Calculate neighborhood beauty score (0-100) using real data.
    
    Scoring components:
    - Trees (0-50): OSM tree count + Census canopy percentage
    - Architectural Beauty (0-50): Building height, type, and footprint variation
      (Both components use native 0-50 ranges. Uses historic context to adjust scoring targets)
    
    Args:
        beauty_weights: Custom weights (e.g., "trees:0.5,architecture:0.5")
                       Default: trees=0.5, architecture=0.5 (context-aware by area type)
    
    Returns:
        (total_score, detailed_breakdown)
    """
    logger.info("Analyzing neighborhood beauty...")
    
    # Detect base area type up front (used for later defaults)
    default_area_type_for_weights = None
    if area_type is not None:
        default_area_type_for_weights = area_type
    else:
        from data_sources import census_api as ca
        density = ca.get_population_density(lat, lon) or 0.0
        default_area_type_for_weights = data_quality.detect_area_type(
            lat,
            lon,
            density,
            city=city,
            location_input=location_name
        )
    
    # Component 2: Architectural Beauty (0-50 native range, no scaling needed)
    # Get this first to determine effective area type for tree radius
    logger.debug("Analyzing architectural beauty...")
    arch_score, arch_details = _score_architectural_diversity(
        lat,
        lon,
        city,
        location_scope=location_scope,
        area_type=area_type,
        location_name=location_name,
        test_overrides=test_overrides
    )
    arch_details = arch_details or {}
    arch_score_value = arch_score if isinstance(arch_score, (int, float)) else None
    architecture_unavailable = arch_score_value is None
    arch_score_for_total = arch_score_value if arch_score_value is not None else 0.0
    
    # Get effective area type for tree radius and calibration guardrails
    effective_area_type = arch_details.get("classification", {}).get("effective_area_type") if arch_details else None
    if effective_area_type is None and area_type:
        effective_area_type = area_type
    
    # Component 1: Trees (0-50)
    # Use effective area type for radius if available (urban_historic/urban_residential get 800m)
    logger.debug("Analyzing tree canopy...")
    tree_score, tree_details = _score_trees(
        lat,
        lon,
        city,
        location_scope=location_scope,
        area_type=effective_area_type or area_type,
        location_name=location_name,
        overrides=test_overrides
    )
    
    # Resolve weights (context-aware defaults if none supplied)
    resolved_area_type = (effective_area_type or default_area_type_for_weights or "").lower() or None
    if beauty_weights is None:
        weights_config = _default_beauty_weights(resolved_area_type)
    else:
        weights_config = beauty_weights
    weights = _parse_beauty_weights(weights_config)
    
    # Apply weights: Scale each component to its weighted max points
    # Default: trees=0.5 (50 points), architecture=0.5 (50 points) out of 100
    # Both components now have same max (50 each), so weights directly apply
    max_tree_points = weights.get('trees', 0.5) * 100
    max_arch_points = weights.get('architecture', 0.5) * 100
    
    total_score = (
        (tree_score * (max_tree_points / 50)) +
        (arch_score_for_total * (max_arch_points / 50))
    )
    
    total_score, normalization_params = _normalize_beauty_score(
        total_score,
        (effective_area_type or area_type or default_area_type_for_weights or "").lower()
    )

    # Calibration guardrails: Flag results outside expected ranges
    calibration_alert = False
    if arch_score_value is not None:
        calibration_alert = _check_calibration_guardrails(
            effective_area_type or area_type,
            arch_score_value,
            tree_score
        )
    
    # Assess data quality
    arch_diversity_summary = {}
    arch_score_native = arch_details.get("score")
    if isinstance(arch_score_native, (int, float)):
        arch_diversity_summary = {
            "diversity_score": max(0.0, min(100.0, arch_score_native * 2.0)),
            "phase2_confidence": arch_details.get("phase2_confidence"),
            "phase3_confidence": arch_details.get("phase3_confidence"),
            "coverage_cap_applied": arch_details.get("coverage_cap_applied", False)
        }

    combined_data = {
        'tree_score': tree_score,
        'architectural_score': arch_score_value,
        'tree_details': tree_details,
        'architectural_details': arch_details,
        'architectural_diversity': arch_diversity_summary,
        'calibration_alert': calibration_alert,
        'test_overrides': test_overrides if test_overrides else {}
    }
    
    # Use passed area_type if available, otherwise detect it with city context
    if area_type is None:
        from data_sources import census_api as ca
        density = ca.get_population_density(lat, lon)
        area_type = data_quality.detect_area_type(
            lat,
            lon,
            density,
            city=city,
            location_input=location_name
        )
    else:
        # Still need density for quality assessment
        from data_sources import census_api as ca
        density = ca.get_population_density(lat, lon)
    
    quality_metrics = data_quality.assess_pillar_data_quality('neighborhood_beauty', combined_data, lat, lon, area_type)

    # If GEE canopy succeeded, reflect that in data_quality (no fallback; include source)
    try:
        tree_sources = tree_details.get('sources', [])
        used_gee = any(isinstance(s, str) and s.lower().startswith('gee') for s in tree_sources)
        if used_gee:
            quality_metrics['needs_fallback'] = False
            quality_metrics['fallback_score'] = None
            fm = quality_metrics.get('fallback_metadata', {}) or {}
            fm['fallback_used'] = False
            quality_metrics['fallback_metadata'] = fm
            # ensure data_sources lists gee
            ds = quality_metrics.get('data_sources', []) or []
            if 'gee' not in ds:
                ds.append('gee')
            quality_metrics['data_sources'] = ds
    except Exception:
        pass
    
    # Small beauty enhancers (viewpoints/artwork/fountains/waterfront)
    disable_enhancers = os.getenv("BEAUTY_DISABLE_ENHANCERS", "false").lower() == "true"
    try:
        from data_sources.osm_api import query_beauty_enhancers
        enhancers = query_beauty_enhancers(lat, lon, radius_m=1500)
        if disable_enhancers:
            beauty_bonus = 0.0
        else:
            beauty_bonus = min(8.0, enhancers.get('viewpoints',0)*2 + enhancers.get('artwork',0)*3 + enhancers.get('fountains',0)*1 + enhancers.get('waterfront',0)*2)
            arch_conf = arch_details.get("confidence_0_1") if isinstance(arch_details, dict) else None
            if arch_conf is not None:
                bonus_scale = 0.5 + 0.5 * max(0.0, min(1.0, arch_conf))
                beauty_bonus *= bonus_scale
        total_score = min(100.0, total_score + beauty_bonus)
    except Exception:
        enhancers = {"viewpoints":0, "artwork":0, "fountains":0, "waterfront":0}
        beauty_bonus = 0.0

    # Build response
    applied_override_summary = {}
    if test_overrides:
        if tree_details.get("overrides_applied"):
            applied_override_summary["trees"] = {
                "metrics": tree_details.get("overrides_applied"),
                "values": tree_details.get("override_values", {})
            }
        if arch_details.get("overrides"):
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
            "trees": round(tree_score, 1),
            "architectural_beauty": round(arch_score_value, 1) if arch_score_value is not None else None,  # Native 0-50 range
            "enhancer_bonus": round(beauty_bonus, 1)  # Add enhancer bonus to breakdown so components sum to total
        },
        "details": {
            "tree_analysis": tree_details,
            "architectural_analysis": arch_details,
            "enhancers": enhancers,
            "enhancer_bonus": beauty_bonus,
            "test_mode": test_mode,
            "weights": resolved_weights
        },
        "calibration_alert": calibration_alert,  # Flag if scores are outside expected ranges
        "weights": resolved_weights,
        "weight_metadata": {
            "input": beauty_weights or "default",
            "area_type": resolved_area_type
        },
        "normalization": normalization_params,
        "data_quality": quality_metrics
    }

    if architecture_unavailable:
        breakdown["details"]["architecture_status"] = {
            "available": False,
            "reason": arch_details.get("error") or arch_details.get("data_warning") or "unavailable",
            "retry_suggested": arch_details.get("retry_suggested", False)
        }
    else:
        breakdown["details"]["architecture_status"] = {
            "available": True
        }

    if applied_override_summary:
        breakdown["details"]["test_overrides_applied"] = applied_override_summary
    
    # Log results
    logger.info(f"Neighborhood Beauty Score: {total_score:.0f}/100")
    logger.debug(f"Trees: {tree_score:.0f}/50 | Architectural Beauty: {arch_score:.0f}/50 | Data Quality: {quality_metrics['quality_tier']} ({quality_metrics['confidence']}% confidence)")
    
    return round(total_score, 1), breakdown


def _parse_beauty_weights(weights_str: Optional[str]) -> Dict[str, float]:
    """Parse custom beauty weights or return defaults."""
    if weights_str is None:
        return {'trees': 0.5, 'architecture': 0.5}
    
    try:
        weights = {}
        total = 0.0
        
        for pair in weights_str.split(','):
            component, weight = pair.split(':')
            weight = float(weight.strip())
            
            if component.strip() in ['trees', 'architecture']:
                weights[component.strip()] = weight
                total += weight
        
        # Normalize to sum to 1.0
        if total > 0:
            weights = {k: v / total for k, v in weights.items()}
        else:
            # Fallback if no valid weights
            weights = {'trees': 0.5, 'architecture': 0.5}
        
        return weights
    except:
        return {'trees': 0.5, 'architecture': 0.5}


def _default_beauty_weights(area_type: Optional[str]) -> str:
    """
    Return default tree vs. architecture weight string for the supplied area type.
    """
    if not area_type:
        return "trees:0.5,architecture:0.5"
    
    area_type = area_type.lower()
    
    if area_type in ("urban_core", "urban_residential", "urban_core_lowrise"):
        return "trees:0.4,architecture:0.6"
    if area_type in ("historic_urban", "suburban"):
        return "trees:0.35,architecture:0.65"
    if area_type == "exurban":
        return "trees:0.4,architecture:0.6"
    if area_type == "rural":
        return "trees:0.5,architecture:0.5"
    return "trees:0.5,architecture:0.5"


def _score_trees(lat: float, lon: float, city: Optional[str], location_scope: Optional[str] = None,
                 area_type: Optional[str] = None, location_name: Optional[str] = None,
                 overrides: Optional[Dict[str, float]] = None) -> Tuple[float, Dict]:
    """Score trees from multiple real data sources (0-50)."""
    score = 0.0
    sources = []
    details = {}
    applied_overrides = []
    canopy_points = None
    street_tree_points = None
    osm_tree_points = None
    census_points = None

    overrides = overrides or {}

    def _clamp(value: float, min_val: float, max_val: float) -> float:
        return max(min_val, min(max_val, value))

    if "tree_score" in overrides:
        override_score = _clamp(float(overrides["tree_score"]), 0.0, 50.0)
        score = override_score
        details["sources"] = [f"override:tree_score={override_score}"]
        details["total_score"] = score
        details["override_values"] = {"tree_score": override_score}
        applied_overrides.append("tree_score")
        details["overrides_applied"] = applied_overrides
        return score, details

    if "tree_canopy_pct" in overrides:
        canopy_pct = _clamp(float(overrides["tree_canopy_pct"]), 0.0, 100.0)
        score = _score_tree_canopy(canopy_pct)
        details["gee_canopy_pct"] = canopy_pct
        details["sources"] = [f"override:tree_canopy_pct={canopy_pct}"]
        details["total_score"] = score
        details["override_values"] = {"tree_canopy_pct": canopy_pct}
        applied_overrides.append("tree_canopy_pct")
        details["overrides_applied"] = applied_overrides
        return score, details
    
    # Priority 1: GEE satellite tree canopy (most comprehensive)
    # Use larger radius for suburban/rural areas to capture neighborhood tree coverage
    try:
        from data_sources import census_api, data_quality
        density = census_api.get_population_density(lat, lon)
        detected_area_type = data_quality.detect_area_type(
            lat,
            lon,
            density,
            location_input=location_name,
            city=city
        )
        area_type = area_type or detected_area_type
        
        # Adjust radius based on centralized profile
        # area_type could be urban_historic, historic_urban, or urban_residential for 800m radius
        rp = get_radius_profile('neighborhood_beauty', area_type, location_scope)
        radius_m = int(rp.get('tree_canopy_radius_m', 1000))
        logger.debug(f"Radius profile (beauty): area_type={area_type}, scope={location_scope}, tree_canopy_radius={radius_m}m")
        
        from data_sources.gee_api import get_tree_canopy_gee
        gee_canopy = get_tree_canopy_gee(lat, lon, radius_m=radius_m, area_type=area_type)
        
        # Fallback: Only expand radius for cities (not neighborhoods)
        # Neighborhoods should stay within their boundaries
        if location_scope != 'neighborhood' and gee_canopy is not None and gee_canopy < 25.0 and area_type == 'urban_core':
            logger.debug(f"Urban core returned {gee_canopy:.1f}% - trying larger radius to capture residential neighborhoods...")
            gee_canopy_larger = get_tree_canopy_gee(lat, lon, radius_m=2000, area_type=area_type)
            if gee_canopy_larger is not None and gee_canopy_larger > gee_canopy:
                logger.debug(f"Larger radius (2km) found {gee_canopy_larger:.1f}% canopy (vs {gee_canopy:.1f}% at 1km)")
                gee_canopy = gee_canopy_larger
                # If still below 30%, try 3km (closer to city-wide assessments, only for cities)
                if gee_canopy < 30.0:
                    gee_canopy_3km = get_tree_canopy_gee(lat, lon, radius_m=3000, area_type=area_type)
                    if gee_canopy_3km is not None and gee_canopy_3km > gee_canopy:
                        logger.debug(f"Even larger radius (3km) found {gee_canopy_3km:.1f}% canopy (vs {gee_canopy:.1f}% at 2km)")
                        gee_canopy = gee_canopy_3km
        elif location_scope != 'neighborhood' and (gee_canopy is None or gee_canopy < 0.1) and area_type == 'urban_core':
            logger.debug(f"Urban core returned {gee_canopy if gee_canopy else 'None'}% - trying larger radius...")
            gee_canopy = get_tree_canopy_gee(lat, lon, radius_m=2000, area_type=area_type)
            if gee_canopy is not None and gee_canopy >= 0.1:
                logger.debug(f"Larger radius (2km) found {gee_canopy:.1f}% canopy")
        
        if gee_canopy is not None and gee_canopy >= 0.1:  # Threshold to avoid false zeros
            canopy_score = _score_tree_canopy(gee_canopy)
            score = canopy_score
            canopy_points = canopy_score
            sources.append(f"GEE: {gee_canopy:.1f}% canopy")
            details['gee_canopy_pct'] = gee_canopy
            logger.debug(f"Using GEE satellite data: {gee_canopy:.1f}%")
            
            # For dense urban areas, validate low GEE results with Census/USFS
            # GEE can underestimate in dense urban areas (buildings block satellite view)
            if gee_canopy < 15.0 and area_type in ['urban_core', 'urban_residential']:
                logger.debug(f"Dense urban area with low GEE canopy ({gee_canopy:.1f}%) - validating with Census/USFS...")
                census_canopy = census_api.get_tree_canopy(lat, lon)
                if census_canopy is not None and census_canopy > gee_canopy:
                    # Use the higher of the two (Census might be more accurate for dense urban)
                    census_score = _score_tree_canopy(census_canopy)
                    if census_score > score:
                        logger.debug(f"Census/USFS canopy ({census_canopy:.1f}%) is higher than GEE ({gee_canopy:.1f}%) - using Census")
                        score = census_score
                        canopy_points = census_score
                        sources.append(f"USFS Census: {census_canopy:.1f}% canopy (validated GEE)")
                        details['census_canopy_pct'] = census_canopy
                    else:
                        logger.debug(f"Census/USFS canopy ({census_canopy:.1f}%) confirms low coverage")
                elif census_canopy is not None:
                    logger.debug(f"Census/USFS canopy ({census_canopy:.1f}%) confirms GEE result")
            
            # For NYC: Check if GEE canopy is suspiciously low (<15%) and supplement with street trees
            # GEE canopy misses individual street trees in dense urban areas
            if nyc_api and city and ("New York" in city or "NYC" in city or "Brooklyn" in city):
                if gee_canopy < 15.0:
                    logger.debug(f"NYC location with low GEE canopy ({gee_canopy:.1f}%) - checking street trees...")
                    street_trees = nyc_api.get_street_trees(lat, lon, radius_deg=0.009)  # ~1000m
                    if street_trees:
                        tree_count = len(street_trees)
                        street_tree_score = _score_nyc_trees(tree_count)
                        # Use the higher of the two scores (street trees are more accurate for NYC)
                        if street_tree_score > score:
                            logger.debug(f"NYC Street Trees: {tree_count} trees → {street_tree_score:.1f}/50 (using street trees)")
                            score = street_tree_score
                            street_tree_points = street_tree_score
                            sources.append(f"NYC Street Trees: {tree_count} trees")
                            details['nyc_street_trees'] = tree_count
                        else:
                            logger.debug(f"NYC Street Trees: {tree_count} trees → {street_tree_score:.1f}/50 (GEE canopy higher)")
            
            # For dense urban areas with low canopy, try OSM individual trees as fallback
            # Only if still low after Census validation
            if score < 20.0 and area_type in ['urban_core', 'urban_residential']:
                logger.debug("Checking OSM individual trees/tree rows for dense urban area...")
                try:
                    from data_sources.osm_api import query_enhanced_trees
                    osm_trees = query_enhanced_trees(lat, lon, radius_m=1000)
                    if osm_trees:
                        individual_trees = len(osm_trees.get('individual_trees', []))
                        tree_rows = len(osm_trees.get('tree_rows', []))
                        street_tree_ways = len(osm_trees.get('street_trees', []))
                        # Tree rows represent ~10 trees each, street tree ways represent ~10 trees each
                        total_osm_trees = individual_trees + (tree_rows * 10) + (street_tree_ways * 10)
                        
                        if total_osm_trees > 0:
                            # Score OSM trees similar to NYC street trees
                            osm_tree_score = _score_nyc_trees(total_osm_trees)
                            if osm_tree_score > score:
                                logger.debug(f"OSM found {total_osm_trees} trees/tree features → {osm_tree_score:.1f}/50 (using OSM trees)")
                                score = osm_tree_score
                                osm_tree_points = osm_tree_score
                                sources.append(f"OSM: {total_osm_trees} individual trees/tree rows")
                                details['osm_individual_trees'] = total_osm_trees
                            else:
                                logger.debug(f"OSM found {total_osm_trees} trees/tree features → {osm_tree_score:.1f}/50 (current score higher)")
                except Exception as e:
                    logger.warning(f"OSM tree query failed: {e}")
        else:
            logger.warning(f"GEE returned {gee_canopy} - trying Census fallback")
    except Exception as e:
        logger.warning(f"GEE import error: {e}")
    
    # Priority 2: NYC Street Trees (if NYC and no score yet, or GEE was low)
    if score == 0.0 or (score < 30.0 and nyc_api and city and ("New York" in city or "NYC" in city or "Brooklyn" in city)):
        logger.debug("Checking NYC Street Tree Census...")
        street_trees = nyc_api.get_street_trees(lat, lon, radius_deg=0.009)  # ~1000m
        if street_trees:
            tree_count = len(street_trees)
            street_tree_score = _score_nyc_trees(tree_count)
            if street_tree_score > score:
                logger.debug(f"Using NYC Street Trees: {tree_count} trees → {street_tree_score:.1f}/50")
                score = street_tree_score
                street_tree_points = street_tree_score
                sources.append(f"NYC Street Trees: {tree_count} trees")
                details['nyc_street_trees'] = tree_count
    
    # Priority 2b: Other Cities Street Trees (if city has street tree API and score is low)
    if (score == 0.0 or score < 30.0) and street_tree_api and city:
        city_key = street_tree_api.is_city_with_street_trees(city, lat, lon)
        if city_key:
            logger.debug(f"Checking {city_key} Street Tree API...")
            street_trees = street_tree_api.get_street_trees(city, lat, lon, radius_m=1000)
            if street_trees:
                tree_count = len(street_trees)
                # Reuse NYC tree scoring function (same scoring logic)
                street_tree_score = _score_nyc_trees(tree_count)
                if street_tree_score > score:
                    logger.debug(f"Using {city_key} Street Trees: {tree_count} trees → {street_tree_score:.1f}/50")
                    score = street_tree_score
                    street_tree_points = street_tree_score
                    sources.append(f"{city_key} Street Trees: {tree_count} trees")
                    details[f'{city_key.lower()}_street_trees'] = tree_count
    
    # Priority 3: Census USFS Tree Canopy (if GEE unavailable or low)
    # Also check for dense urban areas when score is suspiciously low (< 20)
    if score == 0.0 or (score < 20.0 and area_type in ['urban_core', 'urban_residential']):
        logger.debug("Trying Census USFS tree canopy data...")
        canopy_pct = census_api.get_tree_canopy(lat, lon)
        if canopy_pct is not None and canopy_pct > 0:
            canopy_score = _score_tree_canopy(canopy_pct)
            if canopy_score > score:
                score = canopy_score
                census_points = canopy_score
                sources.append(f"USFS Census: {canopy_pct:.1f}% canopy")
                details['census_canopy_pct'] = canopy_pct
                logger.debug(f"Using Census canopy data: {canopy_pct:.1f}%")
            else:
                logger.debug(f"Census canopy ({canopy_pct:.1f}%) confirms low coverage")
        else:
            logger.warning(f"Census canopy returned {canopy_pct}")
    
    # Priority 3: OSM parks as proxy (fallback)
    if score == 0.0:
        # Use appropriate radius based on location scope
        parks_radius = 800 if location_scope == 'neighborhood' else 500
        tree_data = osm_api.query_green_spaces(lat, lon, radius_m=parks_radius)
        if tree_data:
            parks = tree_data.get('parks', [])
            if parks:
                park_count = len(parks)
                park_score = min(30, park_count * 5)  # 6 parks = 30 pts
                score = park_score
                osm_tree_points = max(osm_tree_points or 0.0, park_score)
                sources.append(f"OSM: {park_count} parks/green spaces")
                details['osm_parks'] = park_count
                logger.debug(f"Using OSM park data: {park_count} parks")
            else:
                logger.warning("No tree data available from any source")
                sources.append("No tree data available")
    
    details['sources'] = sources
    details['component_scores'] = {
        "canopy_score": canopy_points,
        "street_tree_score": street_tree_points,
        "osm_tree_score": osm_tree_points,
        "census_score": census_points
    }
    details['total_score'] = score
    
    return score, details


def _fetch_historic_data(lat: float, lon: float, radius_m: int = 1000) -> Dict:
    """
    Fetch historic data once (OSM landmarks + Census building age).
    
    Used by architectural diversity component to adjust scoring targets based on historic context.
    Historic data helps determine appropriate architectural scoring targets (e.g., historic areas
    get more forgiving targets for organic growth patterns).
    
    Args:
        lat, lon: Coordinates
        radius_m: Radius for OSM historic landmarks query (default 1000m)
    
    Returns:
        {
            'year_built_data': Optional[Dict],  # Full Census data or None
            'median_year_built': Optional[int],  # Extracted for convenience
            'vintage_pct': Optional[float],     # Extracted for convenience
            'charm_data': Optional[Dict],        # Full OSM data or None
            'historic_landmarks': List,          # Extracted landmarks list
            'historic_landmarks_count': int      # Extracted count (0 if None)
        }
    """
    # Fetch building age from Census
    year_built_data = census_api.get_year_built_data(lat, lon)
    median_year_built = year_built_data.get('median_year_built') if year_built_data else None
    vintage_pct = year_built_data.get('vintage_pct', 0) if year_built_data else None
    
    # Fetch OSM historic landmarks
    charm_data = osm_api.query_charm_features(lat, lon, radius_m=radius_m)
    if charm_data:
        historic_landmarks = charm_data.get('historic', []) if charm_data else []
        # Debug: Log if landmarks are found but filtered
        if len(historic_landmarks) == 0 and charm_data:
            logger.warning(f"No historic landmarks found in charm_data for {lat}, {lon}. Available keys: {list(charm_data.keys())}")
    else:
        logger.warning(f"charm_data query returned None for {lat}, {lon}")
        historic_landmarks = []
    historic_landmarks_count = len(historic_landmarks)
    
    return {
        'year_built_data': year_built_data,
        'median_year_built': median_year_built,
        'vintage_pct': vintage_pct,
        'charm_data': charm_data,
        'historic_landmarks': historic_landmarks,
        'historic_landmarks_count': historic_landmarks_count
    }


def _score_architectural_diversity(lat: float, lon: float, city: Optional[str] = None,
                                    location_scope: Optional[str] = None,
                                    area_type: Optional[str] = None,
                                    location_name: Optional[str] = None,
                                    test_overrides: Optional[Dict[str, float]] = None) -> Tuple[float, Dict]:
    """
    Score architectural beauty (0-50 points native range).
    
    Uses conditional adjustments for historic organic development patterns.
    
    Returns:
        (score_0-50, details_dict)
    """
    try:
        from data_sources import arch_diversity, census_api, data_quality, geocoding
        from data_sources.data_quality import get_effective_area_type
        
        # Get radius profile for architectural diversity
        # Standardize on 2km for neighborhood-level context (scales from address to city)
        # This captures neighborhood character and reduces coordinate variance
        radius_m = 2000  # Default radius for neighborhood-level context
        if area_type:
            rp = get_radius_profile('neighborhood_beauty', area_type, location_scope)
            radius_m = int(rp.get('architectural_diversity_radius_m', 2000))
        
        # Compute architectural diversity metrics
        diversity_metrics = arch_diversity.compute_arch_diversity(lat, lon, radius_m=radius_m)
        
        if 'error' in diversity_metrics:
            logger.warning(f"Architectural diversity computation failed: {diversity_metrics.get('error')}")
            user_message = diversity_metrics.get('user_message', 'OSM building data temporarily unavailable. Please try again.')
            retry_suggested = diversity_metrics.get('retry_suggested', False)
            details = {
                "error": diversity_metrics.get('error'), 
                "note": "OSM building data unavailable",
                "user_message": user_message,
                "retry_suggested": retry_suggested,
                # Include validation metadata even on error
                "beauty_valid": diversity_metrics.get("beauty_valid", False),
                "data_warning": diversity_metrics.get("data_warning", "api_error"),
                "confidence_0_1": diversity_metrics.get("confidence_0_1", 0.0),
                "score": None
            }
            return None, details
        
        # Get area type and density for classification
        if area_type is None:
            density = census_api.get_population_density(lat, lon) or 0.0
            if not city:
                city = geocoding.reverse_geocode(lat, lon)
            area_type = data_quality.detect_area_type(
                lat,
                lon,
                density,
                city=city,
                location_input=location_name
            )
        else:
            density = census_api.get_population_density(lat, lon) or 0.0
        
        # Get historic data for scoring adjustments (reuse shared helper)
        historic_data = _fetch_historic_data(lat, lon, radius_m=radius_m)
        historic_landmarks = historic_data.get('historic_landmarks_count', 0)
        median_year_built = historic_data.get('median_year_built')
        
        # Calculate beauty score using conditional adjustments
        # Returns (score, metadata) tuple with coverage cap info
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
                        logger.warning(f"Ignoring invalid architectural override {override_key}={test_overrides[override_key]!r}")

        beauty_score_result = arch_diversity.score_architectural_diversity_as_beauty(
            diversity_metrics.get("levels_entropy", 0),
            diversity_metrics.get("building_type_diversity", 0),
            diversity_metrics.get("footprint_area_cv", 0),
            area_type,
            density,
            diversity_metrics.get("built_coverage_ratio"),
            historic_landmarks=historic_landmarks,
            median_year_built=median_year_built,
            lat=lat,
            lon=lon,
            metric_overrides=metric_overrides if metric_overrides else None
        )
        
        # Handle both old (float) and new (tuple) return formats for backward compatibility
        if isinstance(beauty_score_result, tuple):
            beauty_score, coverage_cap_metadata = beauty_score_result
        else:
            beauty_score = beauty_score_result
            coverage_cap_metadata = {}
        
        # Get effective area type for details
        effective_area_type = get_effective_area_type(
            area_type,
            density,
            diversity_metrics.get("levels_entropy"),
            diversity_metrics.get("building_type_diversity"),
            historic_landmarks=historic_landmarks,
            median_year_built=median_year_built
        )
        
        details = {
            "score": round(beauty_score, 1),
            "max_score": 50.0,
            "metrics": {
                "height_diversity": diversity_metrics.get("levels_entropy", 0),
                "type_diversity": diversity_metrics.get("building_type_diversity", 0),
                "footprint_variation": diversity_metrics.get("footprint_area_cv", 0),
                "built_coverage_ratio": diversity_metrics.get("built_coverage_ratio", 0),
                # Phase 2 metrics
                "block_grain": coverage_cap_metadata.get("block_grain", 0),
                "streetwall_continuity": coverage_cap_metadata.get("streetwall_continuity", 0),
                # Phase 3 metrics
                "setback_consistency": coverage_cap_metadata.get("setback_consistency", 0),
                "facade_rhythm": coverage_cap_metadata.get("facade_rhythm", 0)
            },
            "classification": {
                "base_area_type": area_type,
                "effective_area_type": effective_area_type,
                "density": density
            },
            "historic_context": {
                "landmarks": historic_landmarks,
                "median_year_built": median_year_built
            },
            "sources": ["OSM"],
            # Pass through validation metadata from diversity metrics
            # beauty_valid is always True now (no hard failure)
            "beauty_valid": diversity_metrics.get("beauty_valid") if "beauty_valid" in diversity_metrics else True,
            "data_warning": diversity_metrics.get("data_warning"),
            "confidence_0_1": diversity_metrics.get("confidence_0_1") if "confidence_0_1" in diversity_metrics else 1.0,
            "osm_building_coverage": diversity_metrics.get("osm_building_coverage") or diversity_metrics.get("built_coverage_ratio", 0),
            # Include coverage cap metadata
            "coverage_cap_applied": coverage_cap_metadata.get("coverage_cap_applied", False),
            "original_score_before_cap": coverage_cap_metadata.get("original_score_before_cap"),
            "cap_reason": coverage_cap_metadata.get("cap_reason"),
            # Phase 2 & Phase 3 confidence metrics
            "phase2_confidence": {
                "block_grain": coverage_cap_metadata.get("block_grain_confidence", 0),
                "streetwall_continuity": coverage_cap_metadata.get("streetwall_confidence", 0)
            },
            "phase3_confidence": {
                "setback_consistency": coverage_cap_metadata.get("setback_confidence", 0),
                "facade_rhythm": coverage_cap_metadata.get("facade_rhythm_confidence", 0)
            }
        }

        if coverage_cap_metadata.get("overrides_applied"):
            details["overrides"] = coverage_cap_metadata.get("overrides_applied", [])
            details["override_values"] = coverage_cap_metadata.get("override_values", {})
        
        logger.debug(f"Architectural beauty: {beauty_score:.1f}/50.0 (effective: {effective_area_type})")
        
        return round(beauty_score, 1), details
        
    except Exception as e:
        logger.error(f"Architectural diversity scoring failed: {e}", exc_info=True)
        return 0.0, {"error": str(e), "note": "Architectural diversity unavailable"}


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
    if canopy <= 25.0:
        return canopy * 1.2
    if canopy <= 45.0:
        return 30.0 + (canopy - 25.0) * 0.75
    return 50.0
