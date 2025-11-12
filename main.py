from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import time
from typing import Optional, Dict, Tuple, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
from logging_config import get_logger

logger = get_logger(__name__)

# UPDATED IMPORTS - 9 Purpose-Driven Pillars
from data_sources.geocoding import geocode
from data_sources.cache import clear_cache, get_cache_stats, cleanup_expired_cache
from data_sources.error_handling import check_api_credentials
from data_sources.telemetry import record_request_metrics, record_error, get_telemetry_stats
from pillars.schools import get_school_data
from pillars.active_outdoors import get_active_outdoors_score
from pillars.neighborhood_beauty import get_neighborhood_beauty_score, _normalize_beauty_score
from pillars.neighborhood_amenities import get_neighborhood_amenities_score
from pillars.air_travel_access import get_air_travel_score
from pillars.public_transit_access import get_public_transit_score
from pillars.healthcare_access import get_healthcare_access_score
from pillars.housing_value import get_housing_value_score
from data_sources.arch_diversity import compute_arch_diversity

##########################
# CONFIGURATION FLAGS
##########################
ENABLE_SCHOOL_SCORING = True  # Set to False to skip SchoolDigger API calls

# Load environment variables
load_dotenv()


def parse_token_allocation(tokens: Optional[str]) -> Dict[str, float]:
    """
    Parse token allocation string or return default equal distribution.
    
    Format: "active_outdoors:5,neighborhood_beauty:4,air_travel:3,..."
    Default: Equal distribution across all 9 pillars (~2.22 tokens each)
    """
    primary_pillars = [
        "active_outdoors",
        "built_beauty",
        "natural_beauty",
        "neighborhood_amenities",
        "air_travel_access",
        "public_transit_access",
        "healthcare_access",
        "quality_education",
        "housing_value"
    ]
    alias_pillars = {"neighborhood_beauty"}
    pillar_names = primary_pillars + list(alias_pillars)
    
    if tokens is None:
        # Default equal distribution
        equal_tokens = 20.0 / len(primary_pillars)
        default_allocation = {pillar: equal_tokens for pillar in primary_pillars}
        for alias in alias_pillars:
            default_allocation[alias] = 0.0
        return default_allocation
    
    # Parse custom allocation
    token_dict = {}
    total_allocated = 0.0
    
    try:
        for pair in tokens.split(','):
            pillar, count = pair.split(':')
            pillar = pillar.strip()
            count = float(count.strip())
            
            if pillar in primary_pillars:
                token_dict[pillar] = token_dict.get(pillar, 0.0) + count
                total_allocated += count
            elif pillar in alias_pillars:
                split = count / 2.0
                token_dict["built_beauty"] = token_dict.get("built_beauty", 0.0) + split
                token_dict["natural_beauty"] = token_dict.get("natural_beauty", 0.0) + split
                total_allocated += count
        
        # Auto-normalize to 20 tokens (preserve user intent ratios)
        if total_allocated > 0:
            normalization_factor = 20.0 / total_allocated
            token_dict = {k: v * normalization_factor for k, v in token_dict.items()}
        
        # Fill missing pillars with 0
        for pillar in primary_pillars:
            if pillar not in token_dict:
                token_dict[pillar] = 0.0
        for alias in alias_pillars:
            token_dict[alias] = 0.0
    except Exception:
        # Fallback to equal distribution on parsing error
        equal_tokens = 20.0 / len(pillar_names)
        token_dict = {pillar: equal_tokens for pillar in pillar_names}
    
    return token_dict


app = FastAPI(
    title="HomeFit API",
    description="Purpose-driven livability scoring API with 9 pillars",
    version="3.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    """Health check endpoint."""
    return {
        "service": "HomeFit API",
        "status": "running",
        "version": "3.0.0",
        "pillars": [
            "active_outdoors",
            "built_beauty",
            "natural_beauty",
            "neighborhood_beauty",
            "neighborhood_amenities",
            "air_travel_access",
            "public_transit_access",
            "healthcare_access",
            "quality_education",
            "housing_value"
        ],
        "endpoints": {
            "score": "/score?location=ADDRESS",
            "docs": "/docs"
        }
    }


@app.get("/score")
def get_livability_score(request: Request,
                         location: str,
                         tokens: Optional[str] = None,
                         include_chains: bool = False,
                         beauty_weights: Optional[str] = None,
                         diagnostics: Optional[bool] = False,
                         enable_schools: Optional[bool] = None,
                         test_mode: Optional[bool] = False):
    """
    Calculate livability score for a given address.

    Returns scores across 9 purpose-driven pillars:
    - Active Outdoors: Can I be active outside regularly?
    - Built Beauty: Are the buildings cohesive, historic, and well-crafted?
    - Natural Beauty: Is the landscape/tree canopy beautiful and calming?
    - Neighborhood Amenities: Can I walk to great local spots?
    - Air Travel Access: How easily can I fly somewhere?
    - Public Transit Access: Can I get around without a car?
    - Healthcare Access: Can I get medical care when needed?
    - Quality Education: Can I raise kids with good schools?
    - Housing Value: Can I afford a spacious home here?

    Parameters:
        location: Address or ZIP code
        tokens: Optional token allocation (format: "pillar:count,pillar:count,...")
                Default: Equal distribution across all pillars
        include_chains: Include chain/franchise businesses in amenities score (default: False)
        beauty_weights: Optional beauty component weights (format: "trees:0.5,architecture:0.5")
                       Default: trees=0.5, architecture=0.5
        enable_schools: Enable school scoring for this request (default: uses global ENABLE_SCHOOL_SCORING flag)
                       Set to False to disable school scoring and preserve API quota

    Returns:
        JSON with pillar scores, token allocation, and weighted total
    """
    # Determine if school scoring should be enabled for this request
    # Use query parameter if provided, otherwise fall back to global flag
    use_school_scoring = enable_schools if enable_schools is not None else ENABLE_SCHOOL_SCORING
    
    start_time = time.time()
    logger.info(f"HomeFit Score Request: {location}")
    if enable_schools is not None:
        logger.info(f"School scoring: {'enabled' if use_school_scoring else 'disabled'} (via query parameter)")

    test_mode_enabled = bool(test_mode)

    override_params: Dict[str, float] = {}
    if test_mode_enabled:
        for key, value in request.query_params.items():
            if key.startswith("override_"):
                try:
                    override_params[key] = float(value)
                except (TypeError, ValueError):
                    logger.warning(f"Ignoring invalid override parameter {key}={value!r}")

    beauty_override_map = {
        "override_tree_canopy": "tree_canopy_pct",
        "override_tree_canopy_pct": "tree_canopy_pct",
        "override_tree_score": "tree_score",
        "override_levels_entropy": "levels_entropy",
        "override_building_type_diversity": "building_type_diversity",
        "override_footprint_area_cv": "footprint_area_cv",
        "override_block_grain": "block_grain",
        "override_streetwall": "streetwall_continuity",
        "override_streetwall_continuity": "streetwall_continuity",
        "override_setback": "setback_consistency",
        "override_setback_consistency": "setback_consistency",
        "override_facade": "facade_rhythm",
        "override_facade_rhythm": "facade_rhythm",
        "override_architecture_score": "architecture_score"
    }

    beauty_overrides: Dict[str, float] = {}
    if test_mode_enabled:
        for raw_key, mapped_key in beauty_override_map.items():
            if raw_key in override_params:
                beauty_overrides[mapped_key] = override_params[raw_key]

    only_param = request.query_params.get("only")
    only_pillars: Optional[set[str]] = None
    if only_param:
        only_pillars = {
            part.strip() for part in only_param.split(",") if part.strip()
        }
        if not only_pillars:
            only_pillars = None

    # Step 1: Geocode the location (with full result for neighborhood detection)
    from data_sources.geocoding import geocode_with_full_result
    geo_result = geocode_with_full_result(location)

    if not geo_result:
        raise HTTPException(
            status_code=400,
            detail="Could not geocode the provided location. Please check the address."
        )

    lat, lon, zip_code, state, city, geocode_data = geo_result
    logger.info(f"Coordinates: {lat}, {lon}")
    logger.info(f"Location: {city}, {state} {zip_code}")
    
    # Detect if this is a neighborhood vs. standalone city
    from data_sources.data_quality import detect_location_scope
    location_scope = detect_location_scope(lat, lon, geocode_data)
    logger.info(f"Location scope: {location_scope}")

    # Compute a single area_type centrally for consistent radius profiles
    # Also pre-compute census_tract and density for pillars to avoid duplicate API calls
    # Use multi-factor classification: business density, building coverage, density, keywords
    census_tract = None
    density = 0.0
    try:
        from data_sources import census_api as _ca
        from data_sources import data_quality as _dq
        from data_sources import osm_api
        from data_sources.arch_diversity import compute_arch_diversity
        
        density = _ca.get_population_density(lat, lon) or 0.0
        
        # Get business count for classification (skip if amenities pillar not requested)
        business_count = 0
        if only_pillars is None or "neighborhood_amenities" in only_pillars:
            try:
                business_data = osm_api.query_local_businesses(lat, lon, radius_m=1000)
                if business_data:
                    all_businesses = (business_data.get("tier1_daily", []) + 
                                    business_data.get("tier2_social", []) +
                                    business_data.get("tier3_culture", []) +
                                    business_data.get("tier4_services", []))
                    business_count = len(all_businesses)
            except Exception as e:
                logger.warning(f"Business count query failed (non-fatal): {e}")
        
        # Get built coverage for classification (will be cached for beauty pillar)
        built_coverage = None
        try:
            arch_diversity = compute_arch_diversity(lat, lon, radius_m=2000)
            if arch_diversity:
                built_coverage = arch_diversity.get("built_coverage_ratio")
        except Exception as e:
            logger.warning(f"Built coverage query failed (non-fatal): {e}")
        
        # Get distance to principal city for classification
        metro_distance_km = None
        try:
            from data_sources.regional_baselines import RegionalBaselineManager
            baseline_mgr = RegionalBaselineManager()
            # Pass city parameter to help with metro detection, but geographic detection will work as fallback
            metro_distance_km = baseline_mgr.get_distance_to_principal_city(lat, lon, city=city)
        except Exception as e:
            logger.warning(f"Metro distance calculation failed (non-fatal): {e}")
        
        # Enhanced multi-factor classification with principal city distance
        area_type = _dq.detect_area_type(
            lat, lon, 
            density=density, 
            city=city,
            location_input=location,  # For "downtown" keyword check
            business_count=business_count,  # For business density
            built_coverage=built_coverage,  # For building coverage
            metro_distance_km=metro_distance_km  # Distance to principal city
        )
        
        # Pre-compute census tract for pillars (used by housing, beauty, etc.)
        try:
            census_tract = _ca.get_census_tract(lat, lon)
        except Exception as e:
            logger.warning(f"Census tract lookup failed: {e}")
            census_tract = None
    except Exception:
        area_type = "unknown"

    # Step 2: Calculate all pillar scores in parallel
    logger.debug("Calculating pillar scores in parallel...")

    # Pillar execution wrapper with error handling
    def _execute_pillar(name: str, func, **kwargs) -> Tuple[str, Optional[Tuple[float, Dict]], Optional[Exception]]:
        """
        Execute a pillar function with error handling.
        Returns: (pillar_name, (score, details) or None, exception or None)
        """
        try:
            result = func(**kwargs)
            return (name, result, None)
        except Exception as e:
            logger.error(f"{name} pillar failed: {e}")
            return (name, None, e)

    # Prepare all pillar tasks
    def _include_pillar(name: str) -> bool:
        return only_pillars is None or name in only_pillars

    pillar_tasks = []
    if _include_pillar('active_outdoors'):
        pillar_tasks.append(
            ('active_outdoors', get_active_outdoors_score, {
                'lat': lat, 'lon': lon, 'city': city, 'area_type': area_type,
                'location_scope': location_scope, 'include_diagnostics': bool(diagnostics)
            })
        )
    need_beauty_pillar = _include_pillar('neighborhood_beauty') or _include_pillar('built_beauty') or _include_pillar('natural_beauty')
    if need_beauty_pillar:
        pillar_tasks.append(
            ('neighborhood_beauty', get_neighborhood_beauty_score, {
                'lat': lat,
                'lon': lon,
                'city': city,
                'beauty_weights': beauty_weights,
                'location_scope': location_scope,
                'area_type': area_type,
                'location_name': location,
                'test_overrides': beauty_overrides if beauty_overrides else None,
                'test_mode': test_mode_enabled
            })
        )
    if _include_pillar('neighborhood_amenities'):
        pillar_tasks.append(
            ('neighborhood_amenities', get_neighborhood_amenities_score, {
                'lat': lat, 'lon': lon, 'include_chains': include_chains,
                'location_scope': location_scope, 'area_type': area_type
            })
        )
    if _include_pillar('air_travel_access'):
        pillar_tasks.append(
            ('air_travel_access', get_air_travel_score, {
                'lat': lat, 'lon': lon, 'area_type': area_type
            })
        )
    if _include_pillar('public_transit_access'):
        pillar_tasks.append(
            ('public_transit_access', get_public_transit_score, {
                'lat': lat, 'lon': lon, 'area_type': area_type, 'location_scope': location_scope, 'city': city
            })
        )
    if _include_pillar('healthcare_access'):
        pillar_tasks.append(
            ('healthcare_access', get_healthcare_access_score, {
                'lat': lat, 'lon': lon, 'area_type': area_type, 'location_scope': location_scope
            })
        )
    if _include_pillar('housing_value'):
        pillar_tasks.append(
            ('housing_value', get_housing_value_score, {
                'lat': lat, 'lon': lon, 'census_tract': census_tract, 'density': density, 'city': city
            })
        )

    # Add school scoring if enabled (check per-request parameter)
    if use_school_scoring and _include_pillar('quality_education'):
        pillar_tasks.append(
            ('quality_education', get_school_data, {
                'zip_code': zip_code, 'state': state, 'city': city
            })
        )

    # Execute all pillars in parallel
    pillar_results = {}
    exceptions = {}

    with ThreadPoolExecutor(max_workers=8) as executor:
        # Submit all tasks
        future_to_pillar = {
            executor.submit(_execute_pillar, name, func, **kwargs): name
            for name, func, kwargs in pillar_tasks
        }
        
        # Collect results as they complete
        for future in as_completed(future_to_pillar):
            pillar_name = future_to_pillar[future]
            name, result, error = future.result()
            
            if error:
                exceptions[pillar_name] = error
                pillar_results[pillar_name] = None
            else:
                pillar_results[pillar_name] = result

    # Handle school scoring separately (conditional)
    schools_found = False
    if use_school_scoring:
        if 'quality_education' in pillar_results and pillar_results['quality_education']:
            school_avg, schools_by_level = pillar_results['quality_education']
        else:
            school_avg = None  # Real failure, not fake score
            schools_by_level = {"elementary": [], "middle": [], "high": []}
    else:
        logger.info("School scoring disabled (preserving API quota)")
        school_avg = None  # Not computed, don't use fake score
        schools_by_level = {"elementary": [], "middle": [], "high": []}

    # Extract results with error handling (no fallback scores - use 0.0 if failed)
    active_outdoors_score, active_outdoors_details = pillar_results.get('active_outdoors') or (0.0, {"breakdown": {}, "summary": {}, "data_quality": {}, "area_classification": {}})
    beauty_score, beauty_details = pillar_results.get('neighborhood_beauty') or (0.0, {"breakdown": {}, "summary": {}, "data_quality": {}, "area_classification": {}, "details": {}})
    amenities_score, amenities_details = pillar_results.get('neighborhood_amenities') or (0.0, {"breakdown": {}, "summary": {}, "data_quality": {}})
    air_travel_score, air_travel_details = pillar_results.get('air_travel_access') or (0.0, {"primary_airport": {}, "summary": {}, "data_quality": {}})
    transit_score, transit_details = pillar_results.get('public_transit_access') or (0.0, {"breakdown": {}, "summary": {}, "data_quality": {}})
    healthcare_score, healthcare_details = pillar_results.get('healthcare_access') or (0.0, {"breakdown": {}, "summary": {}, "data_quality": {}})
    housing_score, housing_details = pillar_results.get('housing_value') or (0.0, {"breakdown": {}, "summary": {}, "data_quality": {}})

    beauty_details_details = beauty_details.get("details", {})
    enhancer_breakdown = beauty_details_details.get("enhancer_bonus_breakdown", {}) if isinstance(beauty_details_details, dict) else {}
    arch_enhancer_meta = beauty_details_details.get("architectural_analysis", {}).get("enhancer_bonus", {}) if isinstance(beauty_details_details.get("architectural_analysis"), dict) else {}
    if not isinstance(arch_enhancer_meta, dict):
        arch_enhancer_meta = {}
    built_bonus_raw = arch_enhancer_meta.get("built_raw", enhancer_breakdown.get("built_bonus", 0.0))
    built_bonus_scaled = enhancer_breakdown.get("built_bonus", built_bonus_raw)
    natural_breakdown_meta = enhancer_breakdown.get("natural_breakdown", {}) if isinstance(enhancer_breakdown, dict) else {}
    if not isinstance(natural_breakdown_meta, dict):
        natural_breakdown_meta = {}
    natural_bonus_raw = natural_breakdown_meta.get("raw_total", enhancer_breakdown.get("natural_bonus", 0.0))
    natural_bonus_scaled = natural_breakdown_meta.get("scaled_total", enhancer_breakdown.get("natural_bonus", natural_bonus_raw))
    scenic_meta = enhancer_breakdown.get("scenic", {})

    arch_component = beauty_details.get("breakdown", {}).get("architectural_beauty") or 0.0
    tree_component = beauty_details.get("breakdown", {}).get("trees") or 0.0

    built_native = max(0.0, arch_component + built_bonus_scaled)
    natural_native = max(0.0, tree_component + natural_bonus_scaled)

    beauty_area_type = beauty_details.get("weight_metadata", {}).get("area_type") if isinstance(beauty_details.get("weight_metadata"), dict) else None
    beauty_area_type = beauty_area_type or area_type

    built_score_raw = min(100.0, built_native * 2.0)
    natural_score_raw = min(100.0, natural_native * 2.0)

    built_score_norm, built_norm_meta = _normalize_beauty_score(built_score_raw, beauty_area_type)
    natural_score_norm, natural_norm_meta = _normalize_beauty_score(natural_score_raw, beauty_area_type)

    built_details = {
        "component_score_0_50": round(arch_component, 2),
        "enhancer_bonus_raw": round(built_bonus_raw, 2),
        "enhancer_bonus_scaled": round(built_bonus_scaled, 2),
        "score_before_normalization": round(built_score_raw, 2),
        "normalization": built_norm_meta,
        "source": "neighborhood_beauty",
        "architectural_analysis": beauty_details_details.get("architectural_analysis", {}),
        "enhancer_bonus": {
            "built_raw": round(built_bonus_raw, 2),
            "built_scaled": round(built_bonus_scaled, 2),
            "scaled_total": enhancer_breakdown.get("scaled_bonus"),
        }
    }

    tree_analysis_data = beauty_details_details.get("tree_analysis", {})
    if not isinstance(tree_analysis_data, dict):
        tree_analysis_data = {}
    natural_context = tree_analysis_data.get("natural_context") if isinstance(tree_analysis_data, dict) else {}
    if not isinstance(natural_context, dict):
        natural_context = {}
    context_bonus_raw = natural_context.get("total_bonus")

    natural_details = {
        "tree_score_0_50": round(tree_component, 2),
        "enhancer_bonus_raw": round(natural_bonus_raw, 2),
        "enhancer_bonus_scaled": round(natural_bonus_scaled, 2),
        "context_bonus_raw": round(context_bonus_raw, 2) if context_bonus_raw is not None else None,
        "score_before_normalization": round(natural_score_raw, 2),
        "normalization": natural_norm_meta,
        "source": "neighborhood_beauty",
        "tree_analysis": tree_analysis_data,
        "scenic_proxy": scenic_meta,
        "enhancer_bonus": {
            "natural_raw": round(natural_bonus_raw, 2),
            "natural_scaled": round(natural_bonus_scaled, 2),
            "scaled_total": enhancer_breakdown.get("scaled_bonus"),
        }
    }
    natural_details["context_bonus"] = {
        "components": (natural_context or {}).get("component_scores"),
        "total_applied": (natural_context or {}).get("total_bonus"),
        "total_before_cap": (natural_context or {}).get("total_before_cap"),
        "cap": (natural_context or {}).get("cap"),
        "metrics": {
            "topography": (natural_context or {}).get("topography_metrics"),
            "landcover": (natural_context or {}).get("landcover_metrics"),
            "landcover_source": (natural_context or {}).get("landcover_source")
        }
    }

    pillar_results['built_beauty'] = (built_score_norm, built_details)
    pillar_results['natural_beauty'] = (natural_score_norm, natural_details)

    # Note: For school_avg, if None (not computed or failed), set to 0 for calculation
    # but mark in response that it wasn't computed
    if school_avg is None:
        school_avg = 0.0

    # Count total schools if available
    if schools_by_level:
        total_schools = sum([
            len(schools_by_level.get("elementary", [])),
            len(schools_by_level.get("middle", [])),
            len(schools_by_level.get("high", []))
        ])
        schools_found = total_schools > 0
    else:
        total_schools = 0
        schools_found = False

    # Log any pillar failures
    if exceptions:
        logger.warning(f"{len(exceptions)} pillar(s) failed:")
        for pillar_name, error in exceptions.items():
            logger.warning(f"  - {pillar_name}: {error}")

    # Step 3: Calculate weighted total using token allocation
    token_allocation = parse_token_allocation(tokens)
    if only_pillars:
        # Zero-out tokens for pillars not requested
        for pillar_name in list(token_allocation.keys()):
            if pillar_name not in only_pillars:
                token_allocation[pillar_name] = 0.0
        # Renormalize to 20 tokens if any remain
        remaining = sum(token_allocation.values())
        if remaining > 0:
            scale = 20.0 / remaining
            for pillar_name in token_allocation:
                token_allocation[pillar_name] *= scale
        else:
            # Fallback: assign whole budget to requested pillars equally
            equal = 20.0 / len(only_pillars)
            for pillar_name in token_allocation:
                token_allocation[pillar_name] = equal if pillar_name in only_pillars else 0.0

    built_score = built_score_norm
    natural_score = natural_score_norm

    total_score = (
        (active_outdoors_score * token_allocation["active_outdoors"] / 20) +
        (built_score * token_allocation["built_beauty"] / 20) +
        (natural_score * token_allocation["natural_beauty"] / 20) +
        (beauty_score * token_allocation["neighborhood_beauty"] / 20) +
        (amenities_score * token_allocation["neighborhood_amenities"] / 20) +
        (air_travel_score * token_allocation["air_travel_access"] / 20) +
        (transit_score * token_allocation["public_transit_access"] / 20) +
        (healthcare_score * token_allocation["healthcare_access"] / 20) +
        (school_avg * token_allocation["quality_education"] / 20) +
        (housing_score * token_allocation["housing_value"] / 20)
    )

    logger.info(f"Final Livability Score: {total_score:.1f}/100")
    logger.debug(f"Active Outdoors: {active_outdoors_score:.1f}/100 | "
                f"Built Beauty: {built_score:.1f}/100 | "
                f"Natural Beauty: {natural_score:.1f}/100 | "
                f"Neighborhood Beauty: {beauty_score:.1f}/100 | "
                f"Neighborhood Amenities: {amenities_score:.1f}/100 | "
                f"Air Travel Access: {air_travel_score:.1f}/100 | "
                f"Public Transit Access: {transit_score:.1f}/100 | "
                f"Healthcare Access: {healthcare_score:.1f}/100 | "
                f"Quality Education: {school_avg:.1f}/100 | "
                f"Housing Value: {housing_score:.1f}/100")

    # Count total schools and check if any were found
    total_schools = sum([
        len(schools_by_level.get("elementary", [])),
        len(schools_by_level.get("middle", [])),
        len(schools_by_level.get("high", []))
    ])
    schools_found = total_schools > 0

    # Build livability_pillars dict first
    livability_pillars = {
        "active_outdoors": {
            "score": active_outdoors_score,
            "weight": token_allocation["active_outdoors"],
            "contribution": round(active_outdoors_score * token_allocation["active_outdoors"] / 20, 2),
            "breakdown": active_outdoors_details["breakdown"],
            "summary": active_outdoors_details["summary"],
            "confidence": active_outdoors_details.get("data_quality", {}).get("confidence", 0),
            "data_quality": active_outdoors_details.get("data_quality", {}),
            "area_classification": active_outdoors_details.get("area_classification", {})
        },
        "built_beauty": {
            "score": built_score,
            "weight": token_allocation["built_beauty"],
            "contribution": round(built_score * token_allocation["built_beauty"] / 20, 2),
            "breakdown": {
                "component_score_0_50": built_details["component_score_0_50"],
                "enhancer_bonus_raw": built_details["enhancer_bonus_raw"]
            },
            "summary": {},
            "details": built_details,
            "confidence": beauty_details.get("data_quality", {}).get("confidence", 0),
            "data_quality": beauty_details.get("data_quality", {}),
            "area_classification": beauty_details.get("area_classification", {})
        },
        "natural_beauty": {
            "score": natural_score,
            "weight": token_allocation["natural_beauty"],
            "contribution": round(natural_score * token_allocation["natural_beauty"] / 20, 2),
            "breakdown": {
                "tree_score_0_50": natural_details["tree_score_0_50"],
                "enhancer_bonus_raw": natural_details["enhancer_bonus_raw"]
            },
            "summary": {},
            "details": natural_details,
            "confidence": beauty_details.get("data_quality", {}).get("confidence", 0),
            "data_quality": beauty_details.get("data_quality", {}),
            "area_classification": beauty_details.get("area_classification", {})
        },
        "neighborhood_beauty": {
            "score": beauty_score,
            "weight": token_allocation["neighborhood_beauty"],
            "contribution": round(beauty_score * token_allocation["neighborhood_beauty"] / 20, 2),
            "breakdown": beauty_details.get("breakdown", {}),
            "summary": beauty_details.get("summary", {}),
            "details": beauty_details.get("details", {}),
            "weights": beauty_details.get("weights", {}),
            "enhanced": False,
            "scoring_note": beauty_details.get("scoring_note", ""),
            "confidence": beauty_details.get("data_quality", {}).get("confidence", 0),
            "data_quality": beauty_details.get("data_quality", {}),
            "area_classification": beauty_details.get("area_classification", {})
        },
        "neighborhood_amenities": {
            "score": amenities_score,
            "weight": token_allocation["neighborhood_amenities"],
            "contribution": round(amenities_score * token_allocation["neighborhood_amenities"] / 20, 2),
            "breakdown": amenities_details["breakdown"],
            "summary": amenities_details["summary"],
            "confidence": amenities_details.get("data_quality", {}).get("confidence", 0),
            "data_quality": amenities_details.get("data_quality", {}),
            "area_classification": amenities_details.get("area_classification", {})
        },
        "air_travel_access": {
            "score": air_travel_score,
            "weight": token_allocation["air_travel_access"],
            "contribution": round(air_travel_score * token_allocation["air_travel_access"] / 20, 2),
            "primary_airport": air_travel_details.get("primary_airport"),
            "nearest_airports": air_travel_details.get("nearest_airports", []),
            "summary": air_travel_details.get("summary", {}),
            "confidence": air_travel_details.get("data_quality", {}).get("confidence", 0),
            "data_quality": air_travel_details.get("data_quality", {}),
            "area_classification": air_travel_details.get("area_classification", {})
        },
        "public_transit_access": {
            "score": transit_score,
            "weight": token_allocation["public_transit_access"],
            "contribution": round(transit_score * token_allocation["public_transit_access"] / 20, 2),
            "breakdown": transit_details["breakdown"],
            "summary": transit_details["summary"],
            "details": transit_details.get("details", {}),
            "confidence": transit_details.get("data_quality", {}).get("confidence", 0),
            "data_quality": transit_details.get("data_quality", {}),
            "area_classification": transit_details.get("area_classification", {})
        },
        "healthcare_access": {
            "score": healthcare_score,
            "weight": token_allocation["healthcare_access"],
            "contribution": round(healthcare_score * token_allocation["healthcare_access"] / 20, 2),
            "breakdown": healthcare_details["breakdown"],
            "summary": healthcare_details["summary"],
            "confidence": healthcare_details.get("data_quality", {}).get("confidence", 0),
            "data_quality": healthcare_details.get("data_quality", {}),
            "area_classification": healthcare_details.get("area_classification", {})
        },
        "quality_education": {
            "score": school_avg,
            "weight": token_allocation["quality_education"],
            "contribution": round(school_avg * token_allocation["quality_education"] / 20, 2),
            "by_level": {
                "elementary": schools_by_level.get("elementary", []),
                "middle": schools_by_level.get("middle", []),
                "high": schools_by_level.get("high", [])
            },
            "total_schools_rated": total_schools,
            "confidence": 50 if not use_school_scoring else 85,  # Lower confidence when disabled
            "data_quality": {
                "fallback_used": not use_school_scoring or not schools_found,
                "reason": "School scoring disabled" if not use_school_scoring else ("No schools with ratings found" if not schools_found else "School data available"),
                "error": "Pillar execution failed" if 'quality_education' in exceptions else None
            },
            "error": exceptions.get('quality_education').__class__.__name__ if 'quality_education' in exceptions and exceptions.get('quality_education') else None
        },
        "housing_value": {
            "score": housing_score,
            "weight": token_allocation["housing_value"],
            "contribution": round(housing_score * token_allocation["housing_value"] / 20, 2),
            "breakdown": housing_details["breakdown"],
            "summary": housing_details["summary"],
            "confidence": housing_details.get("data_quality", {}).get("confidence", 0),
            "data_quality": housing_details.get("data_quality", {}),
            "area_classification": housing_details.get("area_classification", {})
        }
    }

    # Build response with enhanced metadata
    response = {
        "input": location,
        "coordinates": {
            "lat": lat,
            "lon": lon
        },
        "location_info": {
            "city": city,
            "state": state,
            "zip": zip_code
        },
        "livability_pillars": livability_pillars,
        "total_score": round(total_score, 2),
        "token_allocation": token_allocation,
        "allocation_type": "custom" if tokens else "default_equal",
        "overall_confidence": _calculate_overall_confidence(livability_pillars),
        "data_quality_summary": _calculate_data_quality_summary(livability_pillars),
        "metadata": {
            "version": "3.0.0",
            "architecture": "9 Purpose-Driven Pillars",
            "pillars": {
                "active_outdoors": "Can I be active outside regularly? (Parks, beaches, trails, camping)",
                "built_beauty": "Are the buildings and streets visually harmonious? (Architecture, form, materials, heritage)",
                "natural_beauty": "Is the landscape beautiful and calming? (Tree canopy, scenic adjacency, viewpoints)",
                "neighborhood_beauty": "Legacy composite of built and natural beauty for compatibility (Trees + architecture + enhancers)",
                "neighborhood_amenities": "Can I walk to great spots? (Indie cafes, restaurants, shops, culture)",
                "air_travel_access": "How easily can I fly? (Airport proximity and type)",
                "public_transit_access": "Can I move without a car? (Rail, light rail, bus access)",
                "healthcare_access": "Can I get medical care? (Hospitals, clinics, pharmacies)",
                "quality_education": "Can I raise kids well? (School ratings by level)",
                "housing_value": "Can I afford space? (Affordability relative to local income)"
            },
            "data_sources": [
                "Nominatim (geocoding)",
                "SchoolDigger API (schools)",
                "OpenStreetMap Overpass API (recreation, beauty, amenities, healthcare)",
                "Census Bureau ACS (housing, building age, tree canopy)",
                "NYC Open Data (street trees)",
                "OurAirports (airport database)",
                "Transitland API (public transit GTFS)"
            ],
            "note": "Total score = weighted average of 9 pillars. Equal token distribution by default (~2.22 tokens each). Custom token allocation available via 'tokens' parameter.",
            "test_mode": test_mode_enabled
        }
    }

    if test_mode_enabled and beauty_overrides:
        response["metadata"]["overrides_applied"] = {
            "neighborhood_beauty": {k: beauty_overrides[k] for k in sorted(beauty_overrides)}
        }
    if only_pillars:
        response["metadata"]["pillars_requested"] = sorted(only_pillars)

    if diagnostics:
        # Surface pillar diagnostics when available
        diag = {}
        try:
            parks_diag = active_outdoors_details.get("diagnostics", {})
            if parks_diag:
                diag["active_outdoors"] = parks_diag
        except Exception:
            pass
        try:
            beauty_diag = beauty_details.get("details", {}).get("enhancers", {})
            if beauty_diag:
                diag.setdefault("neighborhood_beauty", {})["enhancers"] = beauty_diag
                diag["neighborhood_beauty"]["enhancer_bonus"] = beauty_details.get("details", {}).get("enhancer_bonus", 0)
        except Exception:
            pass
        if diag:
            response["diagnostics"] = diag

    # Record telemetry metrics
    try:
        response_time = time.time() - start_time
        record_request_metrics(location, lat, lon, response, response_time)
    except Exception as e:
        logger.warning(f"Failed to record telemetry: {e}")

    return response


def _calculate_overall_confidence(pillars: dict) -> dict:  # Changed from Dict to dict
    """Calculate overall confidence metrics for the response."""
    confidences = []
    fallback_count = 0
    quality_tiers = []
    
    for pillar_name, pillar_data in pillars.items():
        confidence = pillar_data.get("confidence", 0)
        confidences.append(confidence)
        
        data_quality = pillar_data.get("data_quality", {})
        if data_quality.get("fallback_used", False):
            fallback_count += 1
        
        quality_tier = data_quality.get("quality_tier", "unknown")
        quality_tiers.append(quality_tier)
    
    # Calculate overall metrics
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0
    fallback_percentage = (fallback_count / len(pillars)) * 100
    
    # Quality tier distribution
    tier_counts = {}
    for tier in quality_tiers:
        tier_counts[tier] = tier_counts.get(tier, 0) + 1
    
    return {
        "average_confidence": round(avg_confidence, 1),
        "pillars_using_fallback": fallback_count,
        "fallback_percentage": round(fallback_percentage, 1),
        "quality_tier_distribution": tier_counts,
        "overall_quality": "excellent" if avg_confidence >= 85 else "good" if avg_confidence >= 70 else "fair" if avg_confidence >= 50 else "poor"
    }


def _calculate_data_quality_summary(pillars: dict) -> dict:  # Changed from Dict to dict
    """Calculate data quality summary for the response."""
    data_sources_used = set()
    area_classifications = []
    
    for pillar_name, pillar_data in pillars.items():
        data_quality = pillar_data.get("data_quality", {})
        area_classification = pillar_data.get("area_classification", {})
        
        # Collect data sources
        sources = data_quality.get("data_sources", [])
        data_sources_used.update(sources)
        
        # Collect area classifications
        if area_classification:
            area_classifications.append(area_classification)
    
    # Get most common area classification
    if area_classifications:
        area_types = [ac.get("area_type", "unknown") for ac in area_classifications]
        most_common_area = max(set(area_types), key=area_types.count)
        metro_name = area_classifications[0].get("metro_name") if area_classifications else None
    else:
        most_common_area = "unknown"
        metro_name = None
    
    return {
        "data_sources_used": list(data_sources_used),
        "area_classification": {
            "type": most_common_area,
            "metro_name": metro_name
        },
        "total_pillars": len(pillars),
        "data_completeness": "high" if len(data_sources_used) >= 3 else "medium" if len(data_sources_used) >= 2 else "low"
    }


@app.get("/health")
def health_check():
    """Detailed health check with API credential validation."""
    credentials = check_api_credentials()
    cache_stats = get_cache_stats()
    # GEE status
    try:
        from data_sources.gee_api import GEE_AVAILABLE
    except Exception:
        GEE_AVAILABLE = False
    import os
    gee_env_present = bool(os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON"))
    
    # Clean up expired cache entries
    cleanup_expired_cache()
    
    checks = {
        "geocoding": "✅ Nominatim (no credentials required)",
        "schools": "✅ SchoolDigger credentials configured" if credentials["schools"] else "❌ SchoolDigger credentials missing",
        "osm": "✅ OpenStreetMap (no credentials required)",
        "census": "✅ Census API key configured" if credentials["census"] else "❌ Census API key missing",
        "nyc_trees": "✅ NYC Open Data (no credentials required)",
        "airports": "✅ OurAirports database (static data)",
        "transit": "✅ Transitland API (no credentials required)",
        "gee": ("✅ Google Earth Engine initialized" if GEE_AVAILABLE else ("⚠️ GEE disabled - set GOOGLE_APPLICATION_CREDENTIALS_JSON" if not gee_env_present else "⚠️ GEE not initialized - check credentials / roles"))
    }

    return {
        "status": "healthy",
        "checks": checks,
        "cache_stats": cache_stats,
        "version": "3.0.0",
        "architecture": "9 Purpose-Driven Pillars",
        "pillars": [
            "active_outdoors",
            "neighborhood_beauty", 
            "neighborhood_amenities",
            "air_travel_access",
            "public_transit_access",
            "healthcare_access",
            "quality_education",
            "housing_value"
        ]
    }


@app.post("/cache/clear")
def clear_cache_endpoint(cache_type: str = None):
    """Clear cache entries."""
    try:
        clear_cache(cache_type)
        return {
            "status": "success",
            "message": f"Cache cleared for {cache_type or 'all'}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cache clear failed: {e}")


@app.get("/cache/stats")
def cache_stats_endpoint():
    """Get cache statistics."""
    try:
        stats = get_cache_stats()
        return {
            "status": "success",
            "cache_stats": stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cache stats failed: {e}")


@app.get("/telemetry")
def telemetry_endpoint():
    """Get telemetry and analytics data."""
    try:
        stats = get_telemetry_stats()
        return {
            "status": "success",
            "telemetry": stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Telemetry failed: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

# Sandbox endpoint (env-gated) for architectural diversity testing
@app.get("/sandbox/arch_diversity")
def sandbox_arch_diversity(lat: float, lon: float, radius_m: int = 1000):
    """
    Architectural Diversity (Sandbox)
    Enables testing on Railway/GitHub without wiring into pillar scoring.
    
    Returns diversity metrics and context-aware beauty score (0-33 points).

    Query params:
      - lat, lon (required)
      - radius_m (optional, default 1000)
    """
    enabled = os.getenv("SANDBOX_ARCH_ENABLED", "false").lower() == "true"
    if not enabled:
        raise HTTPException(status_code=403, detail="Sandbox endpoint disabled. Set SANDBOX_ARCH_ENABLED=true to enable.")

    try:
        # Get diversity metrics
        diversity_metrics = compute_arch_diversity(lat, lon, radius_m=radius_m)
        
        # Get area type for beauty scoring (reverse geocode to get city for classification)
        from data_sources import census_api, data_quality, geocoding
        density = census_api.get_population_density(lat, lon)
        # Reverse geocode to get city name for better classification
        city_for_classification = geocoding.reverse_geocode(lat, lon)
        area_type = data_quality.detect_area_type(lat, lon, density, city_for_classification)
        
        # Determine effective area type (may be urban_residential or urban_core_lowrise)
        # Use centralized helper function for consistency
        # Fetch historic data using shared helper to avoid duplicate API calls
        from data_sources.data_quality import get_effective_area_type
        from pillars.neighborhood_beauty import _fetch_historic_data
        
        # Get historic markers for historic district detection using shared helper
        historic_data = _fetch_historic_data(lat, lon, radius_m=radius_m)
        historic_landmarks = historic_data.get('historic_landmarks_count')
        median_year_built = historic_data.get('median_year_built')
        
        effective_area_type = get_effective_area_type(
            area_type,
            density,
            diversity_metrics["levels_entropy"],
            diversity_metrics["building_type_diversity"],
            historic_landmarks=historic_landmarks,
            median_year_built=median_year_built,
            built_coverage_ratio=diversity_metrics.get("built_coverage_ratio")
        )
        
        # Calculate beauty score using context-aware scoring
        # Note: Tree coverage is handled by neighborhood_beauty pillar; architectural diversity uses historic context for scoring adjustments
        from data_sources.arch_diversity import (
            score_architectural_diversity_as_beauty,
            _score_band,
            _coherence_bonus,
            _context_penalty,
            CONTEXT_TARGETS,
            DENSITY_MULTIPLIER
        )
        beauty_score = score_architectural_diversity_as_beauty(
            diversity_metrics["levels_entropy"],
            diversity_metrics["building_type_diversity"],
            diversity_metrics["footprint_area_cv"],
            area_type,
            density,
            diversity_metrics.get("built_coverage_ratio"),
            historic_landmarks=historic_landmarks,
            median_year_built=median_year_built
        )
        
        # Calculate individual components for breakdown (using simplified helpers)
        targets = CONTEXT_TARGETS.get(effective_area_type, CONTEXT_TARGETS["urban_core"])
        height_beauty = min(13.2, _score_band(diversity_metrics["levels_entropy"], targets["height"]))
        type_beauty = min(13.2, _score_band(diversity_metrics["building_type_diversity"], targets["type"]))
        footprint_beauty = min(13.2, _score_band(diversity_metrics["footprint_area_cv"], targets["footprint"]))
        
        # One bonus, one penalty
        coherence_bonus = _coherence_bonus(
            diversity_metrics["levels_entropy"],
            diversity_metrics["footprint_area_cv"],
            effective_area_type
        )
        
        penalty = _context_penalty(
            effective_area_type,
            diversity_metrics.get("built_coverage_ratio"),
            diversity_metrics["levels_entropy"],
            diversity_metrics["building_type_diversity"],
            diversity_metrics["footprint_area_cv"]
        )
        
        # Split penalty for display
        if effective_area_type == "suburban":
            sprawl_penalty = penalty
            coverage_penalty = 0.0
        elif effective_area_type in ["urban_core", "urban_core_lowrise"]:
            sprawl_penalty = 0.0
            coverage_penalty = penalty
        else:
            sprawl_penalty = 0.0
            coverage_penalty = 0.0
        
        raw_total = height_beauty + type_beauty + footprint_beauty + coherence_bonus - penalty
        mult = DENSITY_MULTIPLIER.get(effective_area_type, 1.0)
        normalized_score = min(33.0, raw_total * mult)
        
        return {
            "status": "success",
            "input": {"lat": lat, "lon": lon, "radius_m": radius_m},
            "context": {
                "area_type": area_type,
                "effective_area_type": effective_area_type,
                "density": density
            },
            "diversity_metrics": diversity_metrics,
            "beauty_score": round(normalized_score, 1),
            "beauty_max": 33.0,
            "beauty_breakdown": {
                "height_diversity": round(height_beauty, 1),
                "type_diversity": round(type_beauty, 1),
                "footprint_variation": round(footprint_beauty, 1),
                "coherence_bonus": round(coherence_bonus, 1),
                "sprawl_penalty": round(sprawl_penalty, 1),
                "coverage_penalty": round(coverage_penalty, 1),
                "raw_total": round(raw_total, 1),
                "normalization_factor": round(normalized_score / raw_total if raw_total > 0 else 1.0, 2)
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Architectural diversity computation failed: {e}")