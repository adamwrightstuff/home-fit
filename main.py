from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv
import time
import json
from typing import Optional, Dict, Tuple, Any, List
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
from pillars.active_outdoors import get_active_outdoors_score_v2
from pillars import built_beauty, natural_beauty
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


# Batch processing models
class BatchLocationRequest(BaseModel):
    locations: List[str]
    tokens: Optional[str] = None
    priorities: Optional[str] = None
    include_chains: bool = True
    enable_schools: Optional[bool] = None
    max_batch_size: int = 10
    adaptive_delays: bool = True  # Use telemetry to adjust delays


class BatchLocationResult(BaseModel):
    location: str
    success: bool
    result: Optional[Dict] = None
    error: Optional[str] = None
    response_time: Optional[float] = None
    retry_count: int = 0


def _get_optimal_delay(telemetry_stats: Optional[Dict] = None) -> float:
    """
    Calculate optimal delay between batch requests based on historical performance.
    
    Uses telemetry data to determine safe delay that avoids rate limits while
    maintaining reasonable throughput.
    """
    # Base delay: OSM minimum query interval (0.5s) + safety margin
    base_delay = 0.5
    
    if telemetry_stats:
        perf_metrics = telemetry_stats.get("performance_metrics", {})
        avg_response_time = perf_metrics.get("average_response_time", 0)
        error_rate = telemetry_stats.get("system_metrics", {}).get("error_rate", 0)
        timeout_rate = telemetry_stats.get("system_metrics", {}).get("timeout_rate", 0)
        
        # If we have response time data, use it to calculate delay
        if avg_response_time > 0:
            # Delay should be at least 50% of average response time to avoid overlap
            # But cap at reasonable maximum (10s)
            calculated_delay = max(base_delay, min(avg_response_time * 0.5, 10.0))
        else:
            calculated_delay = base_delay
        
        # Increase delay if error/timeout rates are high (indicates rate limiting)
        if error_rate > 10 or timeout_rate > 5:
            # High error rate - be more conservative
            calculated_delay = max(calculated_delay * 1.5, 2.0)
        elif error_rate > 5 or timeout_rate > 2:
            # Moderate error rate - slightly increase delay
            calculated_delay = max(calculated_delay * 1.2, 1.0)
        
        return round(calculated_delay, 2)
    
    # Default: conservative 2s delay if no telemetry data
    return 2.0


def _compute_scoring_hash() -> str:
    """
    Compute a hash of key scoring files to auto-generate API version.
    This ensures cache invalidation when scoring logic changes.
    
    Returns:
        Short hash string (first 8 characters of MD5 hash)
    """
    import hashlib
    import os
    
    # Key files that affect scoring results
    scoring_files = [
        # Pillar scoring logic
        "pillars/active_outdoors.py",
        "pillars/built_beauty.py",
        "pillars/natural_beauty.py",
        "pillars/neighborhood_amenities.py",
        "pillars/air_travel_access.py",
        "pillars/public_transit_access.py",
        "pillars/healthcare_access.py",
        "pillars/housing_value.py",
        "pillars/schools.py",
        "pillars/beauty_common.py",
        # Expected values and baselines
        "data_sources/regional_baselines.py",
        # Area type classification
        "data_sources/data_quality.py",
        # Token allocation logic (in main.py)
        "main.py",
    ]
    
    hasher = hashlib.md5()
    
    for file_path in scoring_files:
        try:
            if os.path.exists(file_path):
                with open(file_path, 'rb') as f:
                    hasher.update(f.read())
        except Exception as e:
            logger.warning(f"Could not hash {file_path} for versioning: {e}")
    
    # Return first 8 characters of hash (short but unique enough)
    return hasher.hexdigest()[:8]


# API Version - automatically generated from scoring file hash
# Format: "3.0.0-{hash}" where hash changes when scoring logic changes
# This ensures request-level caching invalidates old responses automatically
_BASE_VERSION = "3.0.0"
_SCORING_HASH = _compute_scoring_hash()
API_VERSION = f"{_BASE_VERSION}-{_SCORING_HASH}"

# Log the auto-generated version on startup
logger.info(f"API Version: {API_VERSION} (auto-generated from scoring file hash)")


def parse_priority_allocation(priorities: Optional[Dict[str, str]]) -> Dict[str, float]:
    """
    Parse priority allocation dictionary and convert to 100-token allocation.
    
    Priority mapping:
    - "None" → weight 0
    - "Low" → weight 1
    - "Medium" → weight 2
    - "High" → weight 3
    
    Args:
        priorities: Dict mapping pillar names to priority strings (e.g., {"active_outdoors": "High", "built_beauty": "Medium"})
    
    Returns:
        Dict mapping pillar names to token counts (sums to exactly 100)
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
    
    # Priority to weight mapping
    priority_weights = {
        "none": 0,
        "low": 1,
        "medium": 2,
        "high": 3
    }
    
    if priorities is None:
        # Default equal distribution (100 tokens / 9 pillars = 11.11...)
        equal_tokens = 100.0 / len(primary_pillars)
        default_allocation = {}
        remainder = 100.0
        for i, pillar in enumerate(primary_pillars):
            if i < len(primary_pillars) - 1:
                tokens = int(equal_tokens)
                default_allocation[pillar] = float(tokens)
                remainder -= tokens
            else:
                # Last pillar gets remainder to ensure exact 100
                default_allocation[pillar] = remainder
        return default_allocation
    
    # Convert priorities to weights
    weight_dict = {}
    total_weight = 0.0
    
    for pillar in primary_pillars:
        priority_str = priorities.get(pillar, "none").lower().strip()
        weight = priority_weights.get(priority_str, 0)
        weight_dict[pillar] = weight
        total_weight += weight
    
    # Handle edge case: all priorities are "None" (total_weight = 0)
    if total_weight == 0:
        # Default to equal distribution
        equal_tokens = 100.0 / len(primary_pillars)
        default_allocation = {}
        remainder = 100.0
        for i, pillar in enumerate(primary_pillars):
            if i < len(primary_pillars) - 1:
                tokens = int(equal_tokens)
                default_allocation[pillar] = float(tokens)
                remainder -= tokens
            else:
                default_allocation[pillar] = remainder
        return default_allocation
    
    # Calculate proportional tokens
    token_dict = {}
    fractional_parts = []
    
    for pillar in primary_pillars:
        weight = weight_dict[pillar]
        if weight > 0:
            # Calculate proportional token allocation
            proportional = (weight / total_weight) * 100.0
            token_dict[pillar] = proportional
            fractional_parts.append((pillar, proportional - int(proportional)))
        else:
            token_dict[pillar] = 0.0
    
    # Round down to integers and calculate remainder
    rounded_tokens = {pillar: int(tokens) for pillar, tokens in token_dict.items()}
    total_rounded = sum(rounded_tokens.values())
    remainder = 100 - total_rounded
    
    # Distribute remainder to pillars with largest fractional parts (largest remainder method)
    if remainder > 0:
        # Sort by fractional part (descending)
        fractional_parts.sort(key=lambda x: x[1], reverse=True)
        # Add 1 token to top 'remainder' pillars
        for i in range(remainder):
            pillar = fractional_parts[i][0]
            rounded_tokens[pillar] += 1
    
    return {pillar: float(rounded_tokens.get(pillar, 0)) for pillar in primary_pillars}


def _extract_built_beauty_summary(built_details: Dict) -> Dict:
    """Extract summary data from built beauty details for display in UI."""
    summary = {}
    arch_analysis = built_details.get("architectural_analysis", {})
    
    if isinstance(arch_analysis, dict):
        summary["height_diversity"] = round(arch_analysis.get("height_diversity", 0), 2)
        summary["type_diversity"] = round(arch_analysis.get("type_diversity", 0), 2)
        summary["footprint_variation"] = round(arch_analysis.get("footprint_variation", 0), 2)
        summary["built_coverage_ratio"] = round(arch_analysis.get("built_coverage_ratio", 0), 3)
        summary["diversity_score"] = round(arch_analysis.get("diversity_score", 0), 2)
        if arch_analysis.get("median_year_built"):
            summary["median_year_built"] = int(arch_analysis.get("median_year_built", 0))
        if arch_analysis.get("pre_1940_pct") is not None:
            summary["pre_1940_pct"] = round(arch_analysis.get("pre_1940_pct", 0), 1)
    
    summary["component_score"] = round(built_details.get("component_score_0_50", 0), 2)
    summary["enhancer_bonus"] = round(built_details.get("enhancer_bonus_scaled", 0), 2)
    
    return summary


def _extract_natural_beauty_summary(natural_details: Dict) -> Dict:
    """Extract summary data from natural beauty details for display in UI."""
    summary = {}
    tree_analysis = natural_details.get("tree_analysis", {})
    multi_radius = natural_details.get("multi_radius_canopy", {})
    
    if isinstance(multi_radius, dict):
        # FIX: Use correct key names from multi_radius_canopy dict
        # Keys are: micro_400m, neighborhood_1000m, macro_2000m
        summary["neighborhood_canopy_pct"] = round(multi_radius.get("neighborhood_1000m", 0), 1)
        summary["local_canopy_pct"] = round(multi_radius.get("micro_400m", 0), 1)  # Fixed: was local_400m
        summary["extended_canopy_pct"] = round(multi_radius.get("macro_2000m", 0), 1)  # Fixed: was extended_2000m
        # Add weighted canopy if available
        if isinstance(tree_analysis, dict) and "weighted_canopy_pct" in tree_analysis:
            summary["weighted_canopy_pct"] = round(tree_analysis.get("weighted_canopy_pct", 0), 1)
    
    if isinstance(tree_analysis, dict):
        # Show base tree score (canopy only) and adjusted (with bonuses)
        base_score = tree_analysis.get("tree_base_score", 0)
        adjusted_score = tree_analysis.get("adjusted_tree_score", 0)
        summary["tree_score"] = round(adjusted_score, 2) if adjusted_score else round(base_score, 2)
        summary["tree_base_score"] = round(base_score, 2)  # NEW: Show base separately
        summary["green_view_index"] = round(tree_analysis.get("green_view_index", 0), 2) if tree_analysis.get("green_view_index") else None
        # Add local green spaces
        if "local_green_score" in tree_analysis:
            summary["local_green_score"] = round(tree_analysis.get("local_green_score", 0), 2)
    
    summary["scenic_bonus"] = round(natural_details.get("enhancer_bonus_scaled", 0), 2)
    summary["context_bonus"] = round(natural_details.get("context_bonus_raw", 0), 2)
    
    return summary


def parse_token_allocation(tokens: Optional[str]) -> Dict[str, float]:
    """
    Parse token allocation string or return default equal distribution.
    
    Format: "active_outdoors:5,built_beauty:4,natural_beauty:4,air_travel:3,..."
    Default: Equal distribution across all 9 pillars (~11.11 tokens each, totaling 100).
    
    Note: This function now uses 100 tokens total (migrated from 20 tokens).
    For priority-based allocation, use parse_priority_allocation() instead.
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
    pillar_names = primary_pillars
    
    if tokens is None:
        # Default equal distribution (100 tokens / 9 pillars = 11.11...)
        equal_tokens = 100.0 / len(primary_pillars)
        default_allocation = {}
        remainder = 100.0
        for i, pillar in enumerate(primary_pillars):
            if i < len(primary_pillars) - 1:
                tokens = int(equal_tokens)
                default_allocation[pillar] = float(tokens)
                remainder -= tokens
            else:
                # Last pillar gets remainder to ensure exact 100
                default_allocation[pillar] = remainder
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
        
        # Auto-normalize to 100 tokens (preserve user intent ratios)
        if total_allocated > 0:
            normalization_factor = 100.0 / total_allocated
            token_dict = {k: v * normalization_factor for k, v in token_dict.items()}
            
            # Round to ensure exact 100 tokens using largest remainder method
            fractional_parts = [(pillar, tokens - int(tokens)) for pillar, tokens in token_dict.items() if tokens > 0]
            rounded_tokens = {pillar: int(tokens) for pillar, tokens in token_dict.items()}
            total_rounded = sum(rounded_tokens.values())
            remainder = 100 - total_rounded
            
            if remainder > 0:
                fractional_parts.sort(key=lambda x: x[1], reverse=True)
                for i in range(remainder):
                    pillar = fractional_parts[i][0]
                    rounded_tokens[pillar] = rounded_tokens.get(pillar, 0) + 1
            
            token_dict = {pillar: float(rounded_tokens.get(pillar, 0)) for pillar in primary_pillars}
        
        # Fill missing pillars with 0
        for pillar in primary_pillars:
            if pillar not in token_dict:
                token_dict[pillar] = 0.0
    except Exception:
        # Fallback to equal distribution on parsing error
        equal_tokens = 100.0 / len(pillar_names)
        token_dict = {}
        remainder = 100.0
        for i, pillar in enumerate(pillar_names):
            if i < len(pillar_names) - 1:
                tokens = int(equal_tokens)
                token_dict[pillar] = float(tokens)
                remainder -= tokens
            else:
                token_dict[pillar] = remainder
    
    return token_dict


app = FastAPI(
    title="HomeFit API",
    description="Purpose-driven livability scoring API with 9 pillars",
    version=API_VERSION
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
        "version": API_VERSION,
        "pillars": [
            "active_outdoors",
            "built_beauty",
            "natural_beauty",
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


def _generate_request_cache_key(location: str, tokens: Optional[str], priorities: Optional[Dict[str, str]], 
                                include_chains: bool, enable_schools: Optional[bool]) -> str:
    """Generate cache key for request-level caching with API version."""
    import hashlib
    import json
    key_parts = [
        f"api_response:v{API_VERSION}",
        location.lower().strip(),
        str(tokens) if tokens else "default",
        json.dumps(priorities, sort_keys=True) if priorities else "default",
        str(include_chains),
        str(enable_schools) if enable_schools is not None else "default"
    ]
    key_str = ":".join(key_parts)
    key_hash = hashlib.md5(key_str.encode()).hexdigest()
    return f"api_response:v{API_VERSION}:{key_hash}"


def _compute_single_score_internal(
    location: str,
    tokens: Optional[str] = None,
    priorities_dict: Optional[Dict[str, str]] = None,
    include_chains: bool = True,
    enable_schools: Optional[bool] = None,
    test_mode: bool = False,
    request: Optional[Request] = None
) -> Dict[str, Any]:
    """
    Internal function to compute score for a single location.
    Extracted from get_livability_score for reuse in batch processing.
    
    This contains the core scoring logic without FastAPI-specific caching.
    """
    # Determine if school scoring should be enabled for this request
    use_school_scoring = enable_schools if enable_schools is not None else ENABLE_SCHOOL_SCORING
    
    start_time = time.time()
    logger.info(f"HomeFit Score Request: {location}")
    if enable_schools is not None:
        logger.info(f"School scoring: {'enabled' if use_school_scoring else 'disabled'} (via query parameter)")

    test_mode_enabled = bool(test_mode)
    
    override_params: Dict[str, float] = {}
    if test_mode_enabled and request:
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

    only_pillars: Optional[set[str]] = None
    if request and hasattr(request, 'query_params'):
        only_param = request.query_params.get("only")
        if only_param:
            raw_only = {part.strip() for part in only_param.split(",") if part.strip()}
            if raw_only:
                expanded_only = set()
                for name in raw_only:
                    if name == "neighborhood_beauty":
                        expanded_only.update({"built_beauty", "natural_beauty"})
                    else:
                        expanded_only.add(name)
                only_pillars = expanded_only
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
    census_tract = None
    density = 0.0
    try:
        from data_sources import census_api as _ca
        from data_sources import data_quality as _dq
        from data_sources import osm_api
        from data_sources.arch_diversity import compute_arch_diversity
        from data_sources.regional_baselines import RegionalBaselineManager
        
        # Parallelize independent API calls that don't depend on each other
        def _fetch_census_tract():
            try:
                return _ca.get_census_tract(lat, lon)
            except Exception as e:
                logger.warning(f"Census tract lookup failed (non-fatal): {e}")
                return None
        
        def _fetch_density(tract):
            try:
                return _ca.get_population_density(lat, lon, tract=tract) or 0.0
            except Exception as e:
                logger.warning(f"Density lookup failed (non-fatal): {e}")
                return 0.0
        
        def _fetch_business_count():
            if only_pillars is not None and "neighborhood_amenities" not in only_pillars:
                return 0
            try:
                business_data = osm_api.query_local_businesses(lat, lon, radius_m=1000)
                if business_data:
                    all_businesses = (business_data.get("tier1_daily", []) + 
                                    business_data.get("tier2_social", []) +
                                    business_data.get("tier3_culture", []) +
                                    business_data.get("tier4_services", []))
                    return len(all_businesses)
                return 0
            except Exception as e:
                logger.warning(f"Business count query failed (non-fatal): {e}")
                return 0
        
        def _fetch_built_coverage():
            if only_pillars is not None and "built_beauty" not in only_pillars:
                logger.debug("Skipping arch_diversity computation (built_beauty not requested)")
                return None
            try:
                arch_diversity = compute_arch_diversity(lat, lon, radius_m=2000)
                return arch_diversity
            except Exception as e:
                logger.warning(f"Built coverage query failed (non-fatal): {e}")
                return None
        
        def _fetch_metro_distance():
            try:
                baseline_mgr = RegionalBaselineManager()
                return baseline_mgr.get_distance_to_principal_city(lat, lon, city=city)
            except Exception as e:
                logger.warning(f"Metro distance calculation failed (non-fatal): {e}")
                return None
        
        # Execute independent calls in parallel
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_census_tract = executor.submit(_fetch_census_tract)
            future_business_count = executor.submit(_fetch_business_count)
            future_metro_distance = executor.submit(_fetch_metro_distance)
            
            need_built_coverage = only_pillars is None or "built_beauty" in only_pillars
            if need_built_coverage:
                future_built_coverage = executor.submit(_fetch_built_coverage)
            else:
                future_built_coverage = None
            
            census_tract = future_census_tract.result()
            future_density = executor.submit(_fetch_density, census_tract)
            
            density = future_density.result()
            business_count = future_business_count.result()
            metro_distance_km = future_metro_distance.result()
            arch_diversity_data = future_built_coverage.result() if future_built_coverage else None
        
        built_coverage = arch_diversity_data.get("built_coverage_ratio") if arch_diversity_data else None
        
        area_type = _dq.detect_area_type(
            lat, lon, 
            density=density, 
            city=city,
            location_input=location,
            business_count=business_count,
            built_coverage=built_coverage,
            metro_distance_km=metro_distance_km
        )
    except Exception:
        area_type = "unknown"
        arch_diversity_data = None
        density = 0.0

    # Step 2: Calculate all pillar scores in parallel
    logger.debug("Calculating pillar scores in parallel...")

    def _execute_pillar(name: str, func, **kwargs) -> Tuple[str, Optional[Tuple[float, Dict]], Optional[Exception]]:
        try:
            result = func(**kwargs)
            return (name, result, None)
        except Exception as e:
            logger.error(f"{name} pillar failed: {e}")
            return (name, None, e)

    def _include_pillar(name: str) -> bool:
        return only_pillars is None or name in only_pillars

    # Pre-compute tree canopy (5km) once for pillars that need it
    tree_canopy_5km = None
    if _include_pillar('active_outdoors') or _include_pillar('natural_beauty'):
        try:
            from data_sources.gee_api import get_tree_canopy_gee
            tree_canopy_5km = get_tree_canopy_gee(lat, lon, radius_m=5000, area_type=area_type)
            logger.debug(f"Pre-computed tree canopy (5km): {tree_canopy_5km}%")
        except Exception as e:
            logger.warning(f"Tree canopy pre-computation failed (non-fatal): {e}")
            tree_canopy_5km = None

    # Compute form_context once when beauty pillars are requested
    form_context = None
    need_built_beauty = _include_pillar('built_beauty')
    need_natural_beauty = _include_pillar('natural_beauty')
    need_neighborhood_beauty = _include_pillar('neighborhood_beauty')
    
    if need_built_beauty or need_natural_beauty or need_neighborhood_beauty:
        try:
            from data_sources.data_quality import get_form_context
            from data_sources import census_api
            from data_sources import osm_api
            
            if arch_diversity_data:
                levels_entropy = arch_diversity_data.get("levels_entropy")
                building_type_diversity = arch_diversity_data.get("building_type_diversity")
                built_coverage_ratio = arch_diversity_data.get("built_coverage_ratio")
                footprint_area_cv = arch_diversity_data.get("footprint_area_cv")
                material_profile = arch_diversity_data.get("material_profile")
            else:
                levels_entropy = None
                building_type_diversity = None
                built_coverage_ratio = None
                footprint_area_cv = None
                material_profile = None
            
            charm_data = osm_api.query_charm_features(lat, lon, radius_m=1000)
            historic_landmarks = len(charm_data.get('historic', [])) if charm_data else 0
            
            year_built_data = census_api.get_year_built_data(lat, lon) if census_api else None
            median_year_built = year_built_data.get('median_year_built') if year_built_data else None
            pre_1940_pct = year_built_data.get('pre_1940_pct') if year_built_data else None
            
            form_context = get_form_context(
                area_type=area_type,
                density=density,
                levels_entropy=levels_entropy,
                building_type_diversity=building_type_diversity,
                historic_landmarks=historic_landmarks,
                median_year_built=median_year_built,
                built_coverage_ratio=built_coverage_ratio,
                footprint_area_cv=footprint_area_cv,
                pre_1940_pct=pre_1940_pct,
                material_profile=material_profile,
                use_multinomial=True
            )
            logger.debug(f"Computed form_context: {form_context}")
        except Exception as e:
            logger.warning(f"Form context computation failed (non-fatal): {e}")
            form_context = None

    pillar_tasks = []
    if _include_pillar('active_outdoors'):
        pillar_tasks.append(
            ('active_outdoors', get_active_outdoors_score_v2, {
                'lat': lat, 'lon': lon, 'city': city, 'area_type': area_type,
                'location_scope': location_scope,
                'precomputed_tree_canopy_5km': tree_canopy_5km
            })
        )
    if need_built_beauty:
        pillar_tasks.append(
            ('built_beauty', built_beauty.calculate_built_beauty, {
                'lat': lat, 'lon': lon, 'city': city, 'area_type': area_type,
                'location_scope': location_scope, 'location_name': location,
                'test_overrides': beauty_overrides if beauty_overrides else None,
                'precomputed_arch_diversity': arch_diversity_data,
                'density': density,
                'form_context': form_context
            })
        )
    if need_natural_beauty:
        pillar_tasks.append(
            ('natural_beauty', natural_beauty.calculate_natural_beauty, {
                'lat': lat, 'lon': lon, 'city': city, 'area_type': area_type,
                'location_scope': location_scope, 'location_name': location,
                'overrides': beauty_overrides if beauty_overrides else None,
                'precomputed_tree_canopy_5km': tree_canopy_5km,
                'form_context': form_context
            })
        )
    
    if _include_pillar('neighborhood_amenities'):
        pillar_tasks.append(
            ('neighborhood_amenities', get_neighborhood_amenities_score, {
                'lat': lat, 'lon': lon, 'include_chains': include_chains,
                'location_scope': location_scope, 'area_type': area_type,
                'density': density
            })
        )
    if _include_pillar('air_travel_access'):
        pillar_tasks.append(
            ('air_travel_access', get_air_travel_score, {
                'lat': lat, 'lon': lon, 'area_type': area_type,
                'density': density
            })
        )
    if _include_pillar('public_transit_access'):
        pillar_tasks.append(
            ('public_transit_access', get_public_transit_score, {
                'lat': lat, 'lon': lon, 'area_type': area_type, 'location_scope': location_scope, 
                'city': city, 'density': density
            })
        )
    if _include_pillar('healthcare_access'):
        pillar_tasks.append(
            ('healthcare_access', get_healthcare_access_score, {
                'lat': lat, 'lon': lon, 'area_type': area_type, 'location_scope': location_scope, 'city': city,
                'density': density
            })
        )
    if _include_pillar('housing_value'):
        pillar_tasks.append(
            ('housing_value', get_housing_value_score, {
                'lat': lat, 'lon': lon, 'census_tract': census_tract, 'density': density, 'city': city
            })
        )

    if use_school_scoring and _include_pillar('quality_education'):
        pillar_tasks.append(
            ('quality_education', get_school_data, {
                'zip_code': zip_code, 'state': state, 'city': city,
                'lat': lat, 'lon': lon, 'area_type': area_type
            })
        )

    # Execute all pillars in parallel
    pillar_results = {}
    exceptions = {}

    with ThreadPoolExecutor(max_workers=8) as executor:
        future_to_pillar = {
            executor.submit(_execute_pillar, name, func, **kwargs): name
            for name, func, kwargs in pillar_tasks
        }
        
        for future in as_completed(future_to_pillar):
            pillar_name = future_to_pillar[future]
            name, result, error = future.result()
            
            if error:
                exceptions[pillar_name] = error
                pillar_results[pillar_name] = None
            else:
                pillar_results[pillar_name] = result

    # Handle school scoring separately
    schools_found = False
    school_breakdown = {
        "base_avg_rating": 0.0,
        "quality_boost": 0.0,
        "early_ed_bonus": 0.0,
        "college_bonus": 0.0,
        "total_schools_rated": 0,
        "excellent_schools_count": 0
    }
    if use_school_scoring:
        if 'quality_education' in pillar_results and pillar_results['quality_education']:
            result = pillar_results['quality_education']
            if len(result) == 3:
                school_avg, schools_by_level, school_breakdown = result
            else:
                # Handle legacy return format (backward compatibility)
                school_avg, schools_by_level = result
                school_breakdown = {
                    "base_avg_rating": 0.0,
                    "quality_boost": 0.0,
                    "early_ed_bonus": 0.0,
                    "college_bonus": 0.0,
                    "total_schools_rated": 0,
                    "excellent_schools_count": 0
                }
        else:
            school_avg = None
            schools_by_level = {"elementary": [], "middle": [], "high": []}
    else:
        logger.info("School scoring disabled (preserving API quota)")
        school_avg = None
        schools_by_level = {"elementary": [], "middle": [], "high": []}

    # Extract results with error handling
    active_outdoors_score, active_outdoors_details = pillar_results.get('active_outdoors') or (0.0, {"breakdown": {}, "summary": {}, "data_quality": {}, "area_classification": {}})
    amenities_score, amenities_details = pillar_results.get('neighborhood_amenities') or (0.0, {"breakdown": {}, "summary": {}, "data_quality": {}})
    air_travel_score, air_travel_details = pillar_results.get('air_travel_access') or (0.0, {"primary_airport": {}, "summary": {}, "data_quality": {}})
    transit_score, transit_details = pillar_results.get('public_transit_access') or (0.0, {"breakdown": {}, "summary": {}, "data_quality": {}})
    healthcare_score, healthcare_details = pillar_results.get('healthcare_access') or (0.0, {"breakdown": {}, "summary": {}, "data_quality": {}})
    housing_score, housing_details = pillar_results.get('housing_value') or (0.0, {"breakdown": {}, "summary": {}, "data_quality": {}})

    # Extract built/natural beauty from parallel results
    built_calc = pillar_results.get('built_beauty')
    natural_calc = pillar_results.get('natural_beauty')
    
    if built_calc:
        built_score = built_calc["score"]
        built_details = built_calc["details"]
    else:
        built_score = 0.0
        built_details = {
            "component_score_0_50": 0.0,
            "enhancer_bonus_raw": 0.0,
            "enhancer_bonus_scaled": 0.0,
            "score_before_normalization": 0.0,
            "normalization": None,
            "source": "built_beauty",
            "architectural_analysis": {},
            "enhancer_bonus": {"built_raw": 0.0, "built_scaled": 0.0, "scaled_total": 0.0}
        }

    if natural_calc:
        tree_details = natural_calc["details"]
        natural_score = natural_calc["score"]
        natural_details = {
            "tree_score_0_50": round(natural_calc["tree_score_0_50"], 2),
            "enhancer_bonus_raw": round(natural_calc["natural_bonus_raw"], 2),
            "enhancer_bonus_scaled": round(natural_calc["natural_bonus_scaled"], 2),
            "context_bonus_raw": round(natural_calc["context_bonus_raw"], 2),
            "score_before_normalization": round(natural_calc["score_before_normalization"], 2),
            "normalization": natural_calc["normalization"],
            "source": "natural_beauty",
            "tree_analysis": tree_details,
            "scenic_proxy": natural_calc["scenic_metadata"],
            "enhancer_bonus": tree_details.get("enhancer_bonus", {}),
            "context_bonus": tree_details.get("natural_context", {}),
            "bonus_breakdown": tree_details.get("bonus_breakdown", {}),
            "green_view_index": tree_details.get("green_view_index"),
            "multi_radius_canopy": tree_details.get("multi_radius_canopy"),
            "gvi_metrics": tree_details.get("gvi_metrics"),
            "expectation_effect": tree_details.get("expectation_effect"),
            "data_availability": tree_details.get("data_availability", {}),
            "gvi_available": natural_calc.get("gvi_available", False),
            "gvi_source": natural_calc.get("gvi_source", "unknown"),
        }
    else:
        natural_score = 0.0
        natural_details = {
            "tree_score_0_50": 0.0,
            "enhancer_bonus_raw": 0.0,
            "enhancer_bonus_scaled": 0.0,
            "context_bonus_raw": 0.0,
            "score_before_normalization": 0.0,
            "normalization": None,
            "source": "natural_beauty",
            "tree_analysis": {},
            "scenic_proxy": {},
            "enhancer_bonus": {"natural_raw": 0.0, "natural_scaled": 0.0, "scaled_total": 0.0},
            "context_bonus": {
                "components": {},
                "total_applied": 0.0,
                "total_before_cap": 0.0,
                "cap": 0.0,
                "metrics": {}
            }
        }

    pillar_results['built_beauty'] = (built_score, built_details)
    pillar_results['natural_beauty'] = (natural_score, natural_details)

    if school_avg is None:
        school_avg = 0.0

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

    if exceptions:
        logger.warning(f"{len(exceptions)} pillar(s) failed:")
        for pillar_name, error in exceptions.items():
            logger.warning(f"  - {pillar_name}: {error}")

    # Calculate weighted total using token allocation
    if priorities_dict:
        token_allocation = parse_priority_allocation(priorities_dict)
        allocation_type = "priority_based"
        # Store original priority levels for response (normalize to proper case: None/Low/Medium/High)
        priority_levels = {}
        primary_pillars = [
            "active_outdoors", "built_beauty", "natural_beauty", "neighborhood_amenities",
            "air_travel_access", "public_transit_access", "healthcare_access",
            "quality_education", "housing_value"
        ]
        for pillar in primary_pillars:
            original_priority = priorities_dict.get(pillar, "none")
            if original_priority:
                priority_str = original_priority.strip().lower()
                # Normalize to proper case
                if priority_str == "none":
                    priority_levels[pillar] = "None"
                elif priority_str == "low":
                    priority_levels[pillar] = "Low"
                elif priority_str == "medium":
                    priority_levels[pillar] = "Medium"
                elif priority_str == "high":
                    priority_levels[pillar] = "High"
                else:
                    priority_levels[pillar] = "None"  # Default for invalid values
            else:
                priority_levels[pillar] = "None"
    else:
        token_allocation = parse_token_allocation(tokens)
        allocation_type = "token_based" if tokens else "default_equal"
        priority_levels = None  # No priority levels when using tokens
    
    if only_pillars:
        for pillar_name in list(token_allocation.keys()):
            if pillar_name not in only_pillars:
                token_allocation[pillar_name] = 0.0
        remaining = sum(token_allocation.values())
        if remaining > 0:
            scale = 100.0 / remaining
            token_allocation = {k: v * scale for k, v in token_allocation.items()}
            rounded = {pillar: int(tokens) for pillar, tokens in token_allocation.items()}
            total_rounded = sum(rounded.values())
            remainder = 100 - total_rounded
            if remainder > 0:
                fractional_parts = [(pillar, tokens - int(tokens)) for pillar, tokens in token_allocation.items() if tokens > 0]
                if fractional_parts:
                    fractional_parts.sort(key=lambda x: x[1], reverse=True)
                    for i in range(remainder):
                        pillar = fractional_parts[i][0]
                        rounded[pillar] = rounded.get(pillar, 0) + 1
            token_allocation = {pillar: float(rounded.get(pillar, 0)) for pillar in token_allocation.keys()}
        else:
            equal = 100.0 / len(only_pillars)
            token_allocation = {pillar_name: equal if pillar_name in only_pillars else 0.0 
                             for pillar_name in token_allocation.keys()}

    total_score = (
        (active_outdoors_score * token_allocation["active_outdoors"] / 100) +
        (built_score * token_allocation["built_beauty"] / 100) +
        (natural_score * token_allocation["natural_beauty"] / 100) +
        (amenities_score * token_allocation["neighborhood_amenities"] / 100) +
        (air_travel_score * token_allocation["air_travel_access"] / 100) +
        (transit_score * token_allocation["public_transit_access"] / 100) +
        (healthcare_score * token_allocation["healthcare_access"] / 100) +
        (school_avg * token_allocation["quality_education"] / 100) +
        (housing_score * token_allocation["housing_value"] / 100)
    )

    logger.info(f"Final Livability Score: {total_score:.1f}/100")

    # Build livability_pillars dict
    livability_pillars = {
        "active_outdoors": {
            "score": active_outdoors_score,
            "weight": token_allocation["active_outdoors"],
            "importance_level": priority_levels.get("active_outdoors") if priority_levels else None,
            "contribution": round(active_outdoors_score * token_allocation["active_outdoors"] / 100, 2),
            "breakdown": active_outdoors_details["breakdown"],
            "summary": active_outdoors_details["summary"],
            "confidence": active_outdoors_details.get("data_quality", {}).get("confidence", 0),
            "data_quality": active_outdoors_details.get("data_quality", {}),
            "area_classification": active_outdoors_details.get("area_classification", {})
        },
        "built_beauty": {
            "score": built_score,
            "weight": token_allocation["built_beauty"],
            "importance_level": priority_levels.get("built_beauty") if priority_levels else None,
            "contribution": round(built_score * token_allocation["built_beauty"] / 100, 2),
            "breakdown": {
                "component_score_0_50": built_details["component_score_0_50"],
                "enhancer_bonus_raw": built_details["enhancer_bonus_raw"]
            },
            "summary": _extract_built_beauty_summary(built_details),
            "details": built_details,
            "confidence": built_calc.get("data_quality", {}).get("confidence", 0) if built_calc else (built_details.get("architectural_analysis", {}).get("confidence_0_1", 0) if isinstance(built_details.get("architectural_analysis"), dict) else 0),
            "data_quality": built_calc.get("data_quality", {}) if built_calc else {},
            "area_classification": {}
        },
        "natural_beauty": {
            "score": natural_score,
            "weight": token_allocation["natural_beauty"],
            "importance_level": priority_levels.get("natural_beauty") if priority_levels else None,
            "contribution": round(natural_score * token_allocation["natural_beauty"] / 100, 2),
            "breakdown": {
                "tree_score_0_50": natural_details["tree_score_0_50"],
                "enhancer_bonus_raw": natural_details["enhancer_bonus_raw"]
            },
            "summary": _extract_natural_beauty_summary(natural_details),
            "details": natural_details,
            "confidence": natural_calc.get("data_quality", {}).get("confidence", 0) if natural_calc else (natural_details.get("tree_analysis", {}).get("confidence", 0) if isinstance(natural_details.get("tree_analysis"), dict) else 0),
            "data_quality": natural_calc.get("data_quality", {}) if natural_calc else {},
            "area_classification": {}
        },
        "neighborhood_amenities": {
            "score": amenities_score,
            "weight": token_allocation["neighborhood_amenities"],
            "importance_level": priority_levels.get("neighborhood_amenities") if priority_levels else None,
            "contribution": round(amenities_score * token_allocation["neighborhood_amenities"] / 100, 2),
            "breakdown": amenities_details.get("breakdown", {}),
            "summary": amenities_details.get("summary", {}),
            "confidence": amenities_details.get("data_quality", {}).get("confidence", 0),
            "data_quality": amenities_details.get("data_quality", {}),
            "area_classification": amenities_details.get("area_classification", {})
        },
        "air_travel_access": {
            "score": air_travel_score,
            "weight": token_allocation["air_travel_access"],
            "importance_level": priority_levels.get("air_travel_access") if priority_levels else None,
            "contribution": round(air_travel_score * token_allocation["air_travel_access"] / 100, 2),
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
            "importance_level": priority_levels.get("public_transit_access") if priority_levels else None,
            "contribution": round(transit_score * token_allocation["public_transit_access"] / 100, 2),
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
            "importance_level": priority_levels.get("healthcare_access") if priority_levels else None,
            "contribution": round(healthcare_score * token_allocation["healthcare_access"] / 100, 2),
            "breakdown": healthcare_details["breakdown"],
            "summary": healthcare_details["summary"],
            "confidence": healthcare_details.get("data_quality", {}).get("confidence", 0),
            "data_quality": healthcare_details.get("data_quality", {}),
            "area_classification": healthcare_details.get("area_classification", {})
        },
        "quality_education": {
            "score": school_avg,
            "weight": token_allocation["quality_education"],
            "importance_level": priority_levels.get("quality_education") if priority_levels else None,
            "contribution": round(school_avg * token_allocation["quality_education"] / 100, 2),
            "breakdown": school_breakdown,
            "summary": {
                "base_avg_rating": round(school_breakdown.get("base_avg_rating", 0), 2),
                "total_schools_rated": school_breakdown.get("total_schools_rated", 0),
                "excellent_schools_count": school_breakdown.get("excellent_schools_count", 0),
                "quality_boost": round(school_breakdown.get("quality_boost", 0), 2),
                "early_ed_bonus": round(school_breakdown.get("early_ed_bonus", 0), 2),
                "college_bonus": round(school_breakdown.get("college_bonus", 0), 2)
            },
            "by_level": {
                "elementary": schools_by_level.get("elementary", []),
                "middle": schools_by_level.get("middle", []),
                "high": schools_by_level.get("high", [])
            },
            "total_schools_rated": total_schools,
            "confidence": 50 if not use_school_scoring else 85,
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
            "importance_level": priority_levels.get("housing_value") if priority_levels else None,
            "contribution": round(housing_score * token_allocation["housing_value"] / 100, 2),
            "breakdown": housing_details["breakdown"],
            "summary": housing_details["summary"],
            "confidence": housing_details.get("data_quality", {}).get("confidence", 0),
            "data_quality": housing_details.get("data_quality", {}),
            "area_classification": housing_details.get("area_classification", {})
        }
    }

    # Build response
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
        "allocation_type": allocation_type,
        "overall_confidence": _calculate_overall_confidence(livability_pillars),
        "data_quality_summary": _calculate_data_quality_summary(livability_pillars, area_type=area_type, form_context=form_context),
        "metadata": {
            "version": API_VERSION,
            "architecture": "9 Purpose-Driven Pillars",
            "note": "Total score = weighted average of 9 pillars. Equal token distribution by default.",
            "test_mode": test_mode_enabled
        }
    }

    if test_mode_enabled and beauty_overrides:
        arch_override_keys = {
            "levels_entropy",
            "building_type_diversity",
            "footprint_area_cv",
            "block_grain",
            "streetwall_continuity",
            "setback_consistency",
            "facade_rhythm",
            "architecture_score"
        }
        tree_override_keys = {
            "tree_canopy_pct",
            "tree_score"
        }
        overrides_payload = {}
        built_overrides = {k: beauty_overrides[k] for k in sorted(beauty_overrides) if k in arch_override_keys}
        natural_overrides = {k: beauty_overrides[k] for k in sorted(beauty_overrides) if k in tree_override_keys}
        if built_overrides:
            overrides_payload["built_beauty"] = built_overrides
        if natural_overrides:
            overrides_payload["natural_beauty"] = natural_overrides
        if overrides_payload:
            response["metadata"]["overrides_applied"] = overrides_payload
    if only_pillars:
        response["metadata"]["pillars_requested"] = sorted(only_pillars)

    return response


@app.get("/score")
def get_livability_score(request: Request,
                         location: str,
                         tokens: Optional[str] = None,
                         priorities: Optional[str] = None,
                         include_chains: bool = True,
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
                Default: Equal distribution across all pillars (100 tokens total)
                Note: Deprecated in favor of 'priorities' parameter
        priorities: Optional priority-based allocation (JSON string or query param)
                   Format: JSON object mapping pillar names to priority levels
                   Priority levels: "None" (0), "Low" (1), "Medium" (2), "High" (3)
                   Example: '{"active_outdoors":"High","built_beauty":"Medium",...}'
                   Default: Equal distribution across all pillars (100 tokens total)
        include_chains: Include chain/franchise businesses in amenities score (default: True)
        enable_schools: Enable school scoring for this request (default: uses global ENABLE_SCHOOL_SCORING flag)
                       Set to False to disable school scoring and preserve API quota

    Returns:
        JSON with pillar scores, token allocation, and weighted total
    """
    try:
        start_time = time.time()
        test_mode_enabled = bool(test_mode)
        
        # Parse priorities parameter (if provided as JSON string)
        priorities_dict: Optional[Dict[str, str]] = None
        if priorities:
            try:
                if isinstance(priorities, str):
                    priorities_dict = json.loads(priorities)
                else:
                    priorities_dict = priorities
            except (json.JSONDecodeError, TypeError):
                logger.warning(f"Invalid priorities format: {priorities}, ignoring")
                priorities_dict = None
        
        # REQUEST-LEVEL CACHING: Check cache first (skip if test_mode)
        if not test_mode_enabled:
            from data_sources.cache import _redis_client, _cache, _cache_ttl
            
            cache_key = _generate_request_cache_key(location, tokens, priorities_dict, include_chains, enable_schools)
            # Differentiated cache TTL based on data stability
            # Use minimum TTL of requested pillars (conservative approach)
            # Stable data (Census, airports): 24-48h, Moderate (OSM amenities, transit routes): 1-6h, Dynamic (transit stops): 5-15min
            # For request-level cache, use 5min as baseline (covers dynamic data)
            # Individual data source caches have their own TTLs in cache.py
            request_cache_ttl = 300  # 5 minutes for request-level cache (conservative for dynamic data)
            
            # Check cache (Redis first, then in-memory)
            cached_response = None
            if _redis_client:
                try:
                    cached_data = _redis_client.get(cache_key)
                    if cached_data:
                        data = json.loads(cached_data)
                        cache_time = data.get('timestamp', 0)
                        if (time.time() - cache_time) < request_cache_ttl:
                            cached_response = data.get('value')
                            logger.info(f"Request cache hit for {location}")
                except Exception as e:
                    logger.warning(f"Redis cache read error: {e}")
            
            if cached_response is None and cache_key in _cache:
                cache_time = _cache_ttl.get(cache_key, 0)
                if (time.time() - cache_time) < request_cache_ttl:
                    cached_response = _cache[cache_key]
                    logger.info(f"Request cache hit (in-memory) for {location}")
            
            if cached_response:
                # Return cached response immediately
                # Add cache indicator to response metadata
                if isinstance(cached_response, dict) and "metadata" in cached_response:
                    cached_response["metadata"]["cache_hit"] = True
                    cached_response["metadata"]["cache_timestamp"] = time.time()
                return cached_response

        # Call internal scoring function
        response = _compute_single_score_internal(
            location=location,
            tokens=tokens,
            priorities_dict=priorities_dict,
            include_chains=include_chains,
            enable_schools=enable_schools,
            test_mode=test_mode_enabled,
            request=request
        )
        
        # Extract lat/lon for telemetry and caching
        lat = response.get("coordinates", {}).get("lat", 0)
        lon = response.get("coordinates", {}).get("lon", 0)
        
        # Record telemetry metrics
        try:
            response_time = time.time() - start_time
            record_request_metrics(location, lat, lon, response, response_time)
        except Exception as e:
            logger.warning(f"Failed to record telemetry: {e}")

        # REQUEST-LEVEL CACHING: Store response in cache (skip if test_mode)
        if not test_mode_enabled:
            try:
                from data_sources.cache import _redis_client, _cache, _cache_ttl
                
                cache_key = _generate_request_cache_key(location, tokens, priorities_dict, include_chains, enable_schools)
                request_cache_ttl = 300  # 5 minutes for request-level cache
                
                # Add cache indicator to response metadata
                if isinstance(response, dict) and "metadata" in response:
                    response["metadata"]["cache_hit"] = False
                    response["metadata"]["cache_timestamp"] = time.time()
                
                cache_data = {
                    'value': response,
                    'timestamp': time.time()
                }
                if _redis_client:
                    try:
                        _redis_client.setex(cache_key, request_cache_ttl, json.dumps(cache_data))
                    except Exception as e:
                        logger.warning(f"Redis cache write error: {e}")
                # Also store in in-memory cache
                _cache[cache_key] = response
                _cache_ttl[cache_key] = time.time()
            except Exception as e:
                logger.warning(f"Failed to cache response: {e}")

        return response
    except HTTPException:
        # Re-raise HTTP exceptions (like 400 for geocoding errors)
        raise
    except Exception as e:
        # Catch any unhandled exceptions and return a proper error response
        import traceback
        error_trace = traceback.format_exc()
        logger.error(f"Unhandled exception in get_livability_score: {e}\n{error_trace}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error while calculating livability score: {str(e)}"
        )


# OLD CODE REMOVED - Now using _compute_single_score_internal
# The following section was the old implementation that has been refactored
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
        # OPTIMIZATION: Parallelize independent API calls to reduce latency
        census_tract = None
        density = 0.0
        try:
            from data_sources import census_api as _ca
            from data_sources import data_quality as _dq
            from data_sources import osm_api
            from data_sources.arch_diversity import compute_arch_diversity
            from data_sources.regional_baselines import RegionalBaselineManager
            
            # Parallelize independent API calls that don't depend on each other
            # Note: get_population_density calls get_census_tract internally, so we fetch tract first
            # then use it for density to avoid redundant calls
            def _fetch_census_tract():
                try:
                    return _ca.get_census_tract(lat, lon)
                except Exception as e:
                    logger.warning(f"Census tract lookup failed (non-fatal): {e}")
                    return None
            
            def _fetch_density(tract):
                try:
                    # Use pre-fetched tract to avoid redundant get_census_tract call
                    return _ca.get_population_density(lat, lon, tract=tract) or 0.0
                except Exception as e:
                    logger.warning(f"Density lookup failed (non-fatal): {e}")
                    return 0.0
            
            def _fetch_business_count():
                if only_pillars is not None and "neighborhood_amenities" not in only_pillars:
                    return 0
                try:
                    business_data = osm_api.query_local_businesses(lat, lon, radius_m=1000)
                    if business_data:
                        all_businesses = (business_data.get("tier1_daily", []) + 
                                        business_data.get("tier2_social", []) +
                                        business_data.get("tier3_culture", []) +
                                        business_data.get("tier4_services", []))
                        return len(all_businesses)
                    return 0
                except Exception as e:
                    logger.warning(f"Business count query failed (non-fatal): {e}")
                    return 0
            
            def _fetch_built_coverage():
                # Only fetch full arch_diversity if built_beauty pillar is requested
                # Note: built_coverage_ratio is used for area_type detection, but it's just one factor
                # and area_type detection can work without it (other factors: density, business_count, metro_distance)
                if only_pillars is not None and "built_beauty" not in only_pillars:
                    # Skip expensive arch_diversity computation - area_type will work without built_coverage
                    logger.debug("Skipping arch_diversity computation (built_beauty not requested)")
                    return None
                try:
                    # Return full arch_diversity dict to reuse in built_beauty pillar
                    arch_diversity = compute_arch_diversity(lat, lon, radius_m=2000)
                    return arch_diversity  # Return full dict, not just built_coverage_ratio
                except Exception as e:
                    logger.warning(f"Built coverage query failed (non-fatal): {e}")
                    return None
            
            def _fetch_metro_distance():
                try:
                    baseline_mgr = RegionalBaselineManager()
                    return baseline_mgr.get_distance_to_principal_city(lat, lon, city=city)
                except Exception as e:
                    logger.warning(f"Metro distance calculation failed (non-fatal): {e}")
                    return None
            
            # Execute independent calls in parallel (tract first, then density uses it)
            # OPTIMIZATION: Only submit tasks that are actually needed
            with ThreadPoolExecutor(max_workers=5) as executor:
                future_census_tract = executor.submit(_fetch_census_tract)
                future_business_count = executor.submit(_fetch_business_count)
                future_metro_distance = executor.submit(_fetch_metro_distance)
                
                # Conditionally submit built_coverage task
                need_built_coverage = only_pillars is None or "built_beauty" in only_pillars
                if need_built_coverage:
                    future_built_coverage = executor.submit(_fetch_built_coverage)
                else:
                    future_built_coverage = None
                
                # Get census tract first (needed for density)
                census_tract = future_census_tract.result()
                
                # Now fetch density using pre-computed tract (avoids redundant get_census_tract call)
                future_density = executor.submit(_fetch_density, census_tract)
                
                # Wait for remaining results
                density = future_density.result()
                business_count = future_business_count.result()
                metro_distance_km = future_metro_distance.result()
                arch_diversity_data = future_built_coverage.result() if future_built_coverage else None
            
            # Extract built_coverage_ratio for area type detection
            built_coverage = arch_diversity_data.get("built_coverage_ratio") if arch_diversity_data else None
            
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
        except Exception:
            area_type = "unknown"
            arch_diversity_data = None  # Initialize to avoid NameError if exception occurs
            density = 0.0  # Initialize to avoid NameError if exception occurs

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

        # OPTIMIZATION: Pre-compute tree canopy (5km) once for pillars that need it
        # This avoids redundant API calls in active_outdoors and natural_beauty
        tree_canopy_5km = None
        if _include_pillar('active_outdoors') or _include_pillar('natural_beauty'):
            try:
                from data_sources.gee_api import get_tree_canopy_gee
                tree_canopy_5km = get_tree_canopy_gee(lat, lon, radius_m=5000, area_type=area_type)
                logger.debug(f"Pre-computed tree canopy (5km): {tree_canopy_5km}%")
            except Exception as e:
                logger.warning(f"Tree canopy pre-computation failed (non-fatal): {e}")
                tree_canopy_5km = None

        # Compute form_context once when beauty pillars are requested (shared across beauty pillars)
        form_context = None
        need_built_beauty = _include_pillar('built_beauty')
        need_natural_beauty = _include_pillar('natural_beauty')
        need_neighborhood_beauty = _include_pillar('neighborhood_beauty')
        
        if need_built_beauty or need_natural_beauty or need_neighborhood_beauty:
            try:
                from data_sources.data_quality import get_form_context
                from data_sources import census_api
                
                # Get required data for form_context computation
                if arch_diversity_data:
                    levels_entropy = arch_diversity_data.get("levels_entropy")
                    building_type_diversity = arch_diversity_data.get("building_type_diversity")
                    built_coverage_ratio = arch_diversity_data.get("built_coverage_ratio")
                    footprint_area_cv = arch_diversity_data.get("footprint_area_cv")
                    material_profile = arch_diversity_data.get("material_profile")
                else:
                    levels_entropy = None
                    building_type_diversity = None
                    built_coverage_ratio = None
                    footprint_area_cv = None
                    material_profile = None
                
                # Get historic data for form_context
                from data_sources import osm_api
                charm_data = osm_api.query_charm_features(lat, lon, radius_m=1000)
                historic_landmarks = len(charm_data.get('historic', [])) if charm_data else 0
                
                year_built_data = census_api.get_year_built_data(lat, lon) if census_api else None
                median_year_built = year_built_data.get('median_year_built') if year_built_data else None
                pre_1940_pct = year_built_data.get('pre_1940_pct') if year_built_data else None
                
                form_context = get_form_context(
                    area_type=area_type,
                    density=density,
                    levels_entropy=levels_entropy,
                    building_type_diversity=building_type_diversity,
                    historic_landmarks=historic_landmarks,
                    median_year_built=median_year_built,
                    built_coverage_ratio=built_coverage_ratio,
                    footprint_area_cv=footprint_area_cv,
                    pre_1940_pct=pre_1940_pct,
                    material_profile=material_profile,
                    use_multinomial=True
                )
                logger.debug(f"Computed form_context: {form_context}")
            except Exception as e:
                logger.warning(f"Form context computation failed (non-fatal): {e}")
                form_context = None

        pillar_tasks = []
        if _include_pillar('active_outdoors'):
            pillar_tasks.append(
                ('active_outdoors', get_active_outdoors_score_v2, {
                    'lat': lat, 'lon': lon, 'city': city, 'area_type': area_type,
                    'location_scope': location_scope,
                    'precomputed_tree_canopy_5km': tree_canopy_5km  # Optional: pre-computed tree canopy
                })
            )
        # Add built_beauty and natural_beauty to parallel execution
        if need_built_beauty:
            pillar_tasks.append(
                ('built_beauty', built_beauty.calculate_built_beauty, {
                    'lat': lat, 'lon': lon, 'city': city, 'area_type': area_type,
                    'location_scope': location_scope, 'location_name': location,
                    'test_overrides': beauty_overrides if beauty_overrides else None,
                    'precomputed_arch_diversity': arch_diversity_data,  # Pass precomputed data
                    'density': density,  # Pass pre-computed density
                    'form_context': form_context  # Pass shared form_context
                })
            )
        if need_natural_beauty:
            pillar_tasks.append(
                ('natural_beauty', natural_beauty.calculate_natural_beauty, {
                    'lat': lat, 'lon': lon, 'city': city, 'area_type': area_type,
                    'location_scope': location_scope, 'location_name': location,
                    'overrides': beauty_overrides if beauty_overrides else None,
                    'precomputed_tree_canopy_5km': tree_canopy_5km,  # Optional: pre-computed tree canopy
                    'form_context': form_context  # Pass shared form_context
                })
            )
        
        if _include_pillar('neighborhood_amenities'):
            pillar_tasks.append(
                ('neighborhood_amenities', get_neighborhood_amenities_score, {
                    'lat': lat, 'lon': lon, 'include_chains': include_chains,
                    'location_scope': location_scope, 'area_type': area_type,
                    'density': density  # Pass pre-computed density
                })
            )
        if _include_pillar('air_travel_access'):
            pillar_tasks.append(
                ('air_travel_access', get_air_travel_score, {
                    'lat': lat, 'lon': lon, 'area_type': area_type,
                    'density': density  # Pass pre-computed density
                })
            )
        if _include_pillar('public_transit_access'):
            pillar_tasks.append(
                ('public_transit_access', get_public_transit_score, {
                    'lat': lat, 'lon': lon, 'area_type': area_type, 'location_scope': location_scope, 
                    'city': city, 'density': density  # Pass pre-computed density to avoid redundant API calls
                })
            )
        if _include_pillar('healthcare_access'):
            pillar_tasks.append(
                ('healthcare_access', get_healthcare_access_score, {
                    'lat': lat, 'lon': lon, 'area_type': area_type, 'location_scope': location_scope, 'city': city,
                    'density': density  # Pass pre-computed density
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
                    'zip_code': zip_code, 'state': state, 'city': city,
                    'lat': lat, 'lon': lon, 'area_type': area_type
                })
            )

        # Execute all pillars in parallel (including built/natural beauty)
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
        school_breakdown = {
            "base_avg_rating": 0.0,
            "quality_boost": 0.0,
            "early_ed_bonus": 0.0,
            "college_bonus": 0.0,
            "total_schools_rated": 0,
            "excellent_schools_count": 0
        }
        if use_school_scoring:
            if 'quality_education' in pillar_results and pillar_results['quality_education']:
                result = pillar_results['quality_education']
                if len(result) == 3:
                    school_avg, schools_by_level, school_breakdown = result
                else:
                    # Handle legacy return format (backward compatibility)
                    school_avg, schools_by_level = result
                    school_breakdown = {
                        "base_avg_rating": 0.0,
                        "quality_boost": 0.0,
                        "early_ed_bonus": 0.0,
                        "college_bonus": 0.0,
                        "total_schools_rated": 0,
                        "excellent_schools_count": 0
                    }
            else:
                school_avg = None  # Real failure, not fake score
                schools_by_level = {"elementary": [], "middle": [], "high": []}
        else:
            logger.info("School scoring disabled (preserving API quota)")
            school_avg = None  # Not computed, don't use fake score
            schools_by_level = {"elementary": [], "middle": [], "high": []}

        # Extract results with error handling (no fallback scores - use 0.0 if failed)
        active_outdoors_score, active_outdoors_details = pillar_results.get('active_outdoors') or (0.0, {"breakdown": {}, "summary": {}, "data_quality": {}, "area_classification": {}})
        amenities_score, amenities_details = pillar_results.get('neighborhood_amenities') or (0.0, {"breakdown": {}, "summary": {}, "data_quality": {}})
        air_travel_score, air_travel_details = pillar_results.get('air_travel_access') or (0.0, {"primary_airport": {}, "summary": {}, "data_quality": {}})
        transit_score, transit_details = pillar_results.get('public_transit_access') or (0.0, {"breakdown": {}, "summary": {}, "data_quality": {}})
        healthcare_score, healthcare_details = pillar_results.get('healthcare_access') or (0.0, {"breakdown": {}, "summary": {}, "data_quality": {}})
        housing_score, housing_details = pillar_results.get('housing_value') or (0.0, {"breakdown": {}, "summary": {}, "data_quality": {}})

        # Extract built/natural beauty from parallel results
        built_calc = pillar_results.get('built_beauty')
        natural_calc = pillar_results.get('natural_beauty')
        
        # Handle built_beauty result
        if built_calc:
            built_score = built_calc["score"]
            built_details = built_calc["details"]
        else:
            built_score = 0.0
            built_details = {
                "component_score_0_50": 0.0,
                "enhancer_bonus_raw": 0.0,
                "enhancer_bonus_scaled": 0.0,
                "score_before_normalization": 0.0,
                "normalization": None,
                "source": "built_beauty",
                "architectural_analysis": {},
                "enhancer_bonus": {"built_raw": 0.0, "built_scaled": 0.0, "scaled_total": 0.0}
            }
    
        # Handle natural_beauty result
        if natural_calc:
            tree_details = natural_calc["details"]
            natural_score = natural_calc["score"]
            natural_details = {
                "tree_score_0_50": round(natural_calc["tree_score_0_50"], 2),
                "enhancer_bonus_raw": round(natural_calc["natural_bonus_raw"], 2),
                "enhancer_bonus_scaled": round(natural_calc["natural_bonus_scaled"], 2),
                "context_bonus_raw": round(natural_calc["context_bonus_raw"], 2),
                "score_before_normalization": round(natural_calc["score_before_normalization"], 2),
                "normalization": natural_calc["normalization"],
                "source": "natural_beauty",
                "tree_analysis": tree_details,
                "scenic_proxy": natural_calc["scenic_metadata"],
                "enhancer_bonus": tree_details.get("enhancer_bonus", {}),
                "context_bonus": tree_details.get("natural_context", {}),
                "bonus_breakdown": tree_details.get("bonus_breakdown", {}),
                "green_view_index": tree_details.get("green_view_index"),
                "multi_radius_canopy": tree_details.get("multi_radius_canopy"),
                "gvi_metrics": tree_details.get("gvi_metrics"),
                "expectation_effect": tree_details.get("expectation_effect"),
                "data_availability": tree_details.get("data_availability", {}),  # NEW: expose data quality info
                "gvi_available": tree_details.get("gvi_available", False),  # NEW: GVI data availability
                "gvi_source": tree_details.get("gvi_source", "unknown"),  # NEW: GVI data source
            }
        else:
            natural_score = 0.0
            natural_details = {
                "tree_score_0_50": 0.0,
                "enhancer_bonus_raw": 0.0,
                "enhancer_bonus_scaled": 0.0,
                "context_bonus_raw": 0.0,
                "score_before_normalization": 0.0,
                "normalization": None,
                "source": "natural_beauty",
                "tree_analysis": {},
                "scenic_proxy": {},
                "enhancer_bonus": {"natural_raw": 0.0, "natural_scaled": 0.0, "scaled_total": 0.0},
                "context_bonus": {
                    "components": {},
                    "total_applied": 0.0,
                    "total_before_cap": 0.0,
                    "cap": 0.0,
                    "metrics": {}
                }
            }

        pillar_results['built_beauty'] = (built_score, built_details)
        pillar_results['natural_beauty'] = (natural_score, natural_details)

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
        # Priority: Use priorities if provided, otherwise fall back to tokens
        if priorities_dict:
            token_allocation = parse_priority_allocation(priorities_dict)
            allocation_type = "priority_based"
            # Store original priority levels for response (normalize to proper case: None/Low/Medium/High)
            priority_levels = {}
            primary_pillars = [
                "active_outdoors", "built_beauty", "natural_beauty", "neighborhood_amenities",
                "air_travel_access", "public_transit_access", "healthcare_access",
                "quality_education", "housing_value"
            ]
            for pillar in primary_pillars:
                original_priority = priorities_dict.get(pillar, "none")
                if original_priority:
                    priority_str = original_priority.strip().lower()
                    # Normalize to proper case
                    if priority_str == "none":
                        priority_levels[pillar] = "None"
                    elif priority_str == "low":
                        priority_levels[pillar] = "Low"
                    elif priority_str == "medium":
                        priority_levels[pillar] = "Medium"
                    elif priority_str == "high":
                        priority_levels[pillar] = "High"
                    else:
                        priority_levels[pillar] = "None"  # Default for invalid values
                else:
                    priority_levels[pillar] = "None"
        else:
            token_allocation = parse_token_allocation(tokens)
            allocation_type = "token_based" if tokens else "default_equal"
            priority_levels = None  # No priority levels when using tokens
        
        if only_pillars:
            # Zero-out tokens for pillars not requested
            for pillar_name in list(token_allocation.keys()):
                if pillar_name not in only_pillars:
                    token_allocation[pillar_name] = 0.0
            # Renormalize to 100 tokens if any remain
            remaining = sum(token_allocation.values())
            if remaining > 0:
                scale = 100.0 / remaining
                token_allocation = {k: v * scale for k, v in token_allocation.items()}
                # Round to ensure exact 100 tokens
                rounded = {pillar: int(tokens) for pillar, tokens in token_allocation.items()}
                total_rounded = sum(rounded.values())
                remainder = 100 - total_rounded
                if remainder > 0:
                    # Add remainder to pillar with largest fractional part
                    fractional_parts = [(pillar, tokens - int(tokens)) for pillar, tokens in token_allocation.items() if tokens > 0]
                    if fractional_parts:
                        fractional_parts.sort(key=lambda x: x[1], reverse=True)
                        for i in range(remainder):
                            pillar = fractional_parts[i][0]
                            rounded[pillar] = rounded.get(pillar, 0) + 1
                token_allocation = {pillar: float(rounded.get(pillar, 0)) for pillar in token_allocation.keys()}
            else:
                # Fallback: assign whole budget to requested pillars equally
                equal = 100.0 / len(only_pillars)
                token_allocation = {pillar_name: equal if pillar_name in only_pillars else 0.0 
                                 for pillar_name in token_allocation.keys()}

        total_score = (
        (active_outdoors_score * token_allocation["active_outdoors"] / 100) +
        (built_score * token_allocation["built_beauty"] / 100) +
        (natural_score * token_allocation["natural_beauty"] / 100) +
        (amenities_score * token_allocation["neighborhood_amenities"] / 100) +
        (air_travel_score * token_allocation["air_travel_access"] / 100) +
        (transit_score * token_allocation["public_transit_access"] / 100) +
        (healthcare_score * token_allocation["healthcare_access"] / 100) +
        (school_avg * token_allocation["quality_education"] / 100) +
        (housing_score * token_allocation["housing_value"] / 100)
        )

        logger.info(f"Final Livability Score: {total_score:.1f}/100")
        logger.debug(f"Active Outdoors: {active_outdoors_score:.1f}/100 | "
                f"Built Beauty: {built_score:.1f}/100 | "
                f"Natural Beauty: {natural_score:.1f}/100 | "
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
            "contribution": round(active_outdoors_score * token_allocation["active_outdoors"] / 100, 2),
            "breakdown": active_outdoors_details["breakdown"],
            "summary": active_outdoors_details["summary"],
            "confidence": active_outdoors_details.get("data_quality", {}).get("confidence", 0),
            "data_quality": active_outdoors_details.get("data_quality", {}),
            "area_classification": active_outdoors_details.get("area_classification", {})
        },
        "built_beauty": {
            "score": built_score,
            "weight": token_allocation["built_beauty"],
            "importance_level": priority_levels.get("built_beauty") if priority_levels else None,
            "contribution": round(built_score * token_allocation["built_beauty"] / 100, 2),
            "breakdown": {
                "component_score_0_50": built_details["component_score_0_50"],
                "enhancer_bonus_raw": built_details["enhancer_bonus_raw"]
            },
            "summary": _extract_built_beauty_summary(built_details),
            "details": built_details,
            "confidence": built_calc.get("data_quality", {}).get("confidence", 0) if built_calc else (built_details.get("architectural_analysis", {}).get("confidence_0_1", 0) if isinstance(built_details.get("architectural_analysis"), dict) else 0),
            "data_quality": built_calc.get("data_quality", {}) if built_calc else {},
            "area_classification": {}
        },
        "natural_beauty": {
            "score": natural_score,
            "weight": token_allocation["natural_beauty"],
            "importance_level": priority_levels.get("natural_beauty") if priority_levels else None,
            "contribution": round(natural_score * token_allocation["natural_beauty"] / 100, 2),
            "breakdown": {
                "tree_score_0_50": natural_details["tree_score_0_50"],
                "enhancer_bonus_raw": natural_details["enhancer_bonus_raw"]
            },
            "summary": _extract_natural_beauty_summary(natural_details),
            "details": natural_details,
            "confidence": natural_calc.get("data_quality", {}).get("confidence", 0) if natural_calc else (natural_details.get("tree_analysis", {}).get("confidence", 0) if isinstance(natural_details.get("tree_analysis"), dict) else 0),
            "data_quality": natural_calc.get("data_quality", {}) if natural_calc else {},
            "area_classification": {}
        },
        "neighborhood_amenities": {
            "score": amenities_score,
            "weight": token_allocation["neighborhood_amenities"],
            "importance_level": priority_levels.get("neighborhood_amenities") if priority_levels else None,
            "contribution": round(amenities_score * token_allocation["neighborhood_amenities"] / 100, 2),
            "breakdown": amenities_details.get("breakdown", {}),
            "summary": amenities_details.get("summary", {}),
            "confidence": amenities_details.get("data_quality", {}).get("confidence", 0),
            "data_quality": amenities_details.get("data_quality", {}),
            "area_classification": amenities_details.get("area_classification", {})
        },
        "air_travel_access": {
            "score": air_travel_score,
            "weight": token_allocation["air_travel_access"],
            "importance_level": priority_levels.get("air_travel_access") if priority_levels else None,
            "contribution": round(air_travel_score * token_allocation["air_travel_access"] / 100, 2),
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
            "importance_level": priority_levels.get("public_transit_access") if priority_levels else None,
            "contribution": round(transit_score * token_allocation["public_transit_access"] / 100, 2),
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
            "contribution": round(healthcare_score * token_allocation["healthcare_access"] / 100, 2),
            "breakdown": healthcare_details["breakdown"],
            "summary": healthcare_details["summary"],
            "confidence": healthcare_details.get("data_quality", {}).get("confidence", 0),
            "data_quality": healthcare_details.get("data_quality", {}),
            "area_classification": healthcare_details.get("area_classification", {})
        },
        "quality_education": {
            "score": school_avg,
            "weight": token_allocation["quality_education"],
            "contribution": round(school_avg * token_allocation["quality_education"] / 100, 2),
            "breakdown": school_breakdown,
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
            "contribution": round(housing_score * token_allocation["housing_value"] / 100, 2),
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
        "allocation_type": allocation_type,
        "overall_confidence": _calculate_overall_confidence(livability_pillars),
        "data_quality_summary": _calculate_data_quality_summary(livability_pillars, area_type=area_type, form_context=form_context),
        "metadata": {
            "version": API_VERSION,
            "architecture": "9 Purpose-Driven Pillars",
            "pillars": {
                "active_outdoors": "Can I be active outside regularly? (Parks, beaches, trails, camping)",
                "built_beauty": "Are the buildings and streets visually harmonious? (Architecture, form, materials, heritage)",
                "natural_beauty": "Is the landscape beautiful and calming? (Tree canopy, scenic adjacency, viewpoints)",
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
            "note": "Total score = weighted average of 9 pillars. Equal token distribution by default (~11.11 tokens each, totaling 100). Custom allocation via 'priorities' parameter (recommended) or 'tokens' parameter (legacy).",
            "test_mode": test_mode_enabled
        }
        }

        if test_mode_enabled and beauty_overrides:
            arch_override_keys = {
                "levels_entropy",
                "building_type_diversity",
                "footprint_area_cv",
                "block_grain",
                "streetwall_continuity",
                "setback_consistency",
                "facade_rhythm",
                "architecture_score"
            }
            tree_override_keys = {
                "tree_canopy_pct",
                "tree_score"
            }
            overrides_payload = {}
            built_overrides = {k: beauty_overrides[k] for k in sorted(beauty_overrides) if k in arch_override_keys}
            natural_overrides = {k: beauty_overrides[k] for k in sorted(beauty_overrides) if k in tree_override_keys}
            if built_overrides:
                overrides_payload["built_beauty"] = built_overrides
            if natural_overrides:
                overrides_payload["natural_beauty"] = natural_overrides
            if overrides_payload:
                response["metadata"]["overrides_applied"] = overrides_payload
        if only_pillars:
            response["metadata"]["pillars_requested"] = sorted(only_pillars)

        # Record telemetry metrics
        try:
            response_time = time.time() - start_time
            record_request_metrics(location, lat, lon, response, response_time)
        except Exception as e:
            logger.warning(f"Failed to record telemetry: {e}")

        # REQUEST-LEVEL CACHING: Store response in cache (skip if test_mode)
        if not test_mode_enabled:
            try:
                from data_sources.cache import _redis_client, _cache, _cache_ttl
                
                cache_key = _generate_request_cache_key(location, tokens, priorities_dict, include_chains, enable_schools)
                request_cache_ttl = 300  # 5 minutes for request-level cache
                
                # Add cache indicator to response metadata
                if isinstance(response, dict) and "metadata" in response:
                    response["metadata"]["cache_hit"] = False
                    response["metadata"]["cache_timestamp"] = time.time()
                
                cache_data = {
                    'value': response,
                    'timestamp': time.time()
                }
                if _redis_client:
                    try:
                        _redis_client.setex(cache_key, request_cache_ttl, json.dumps(cache_data))
                    except Exception as e:
                        logger.warning(f"Redis cache write error: {e}")
                # Also store in in-memory cache
                _cache[cache_key] = response
                _cache_ttl[cache_key] = time.time()
            except Exception as e:
                logger.warning(f"Failed to cache response: {e}")

        return response
    except HTTPException:
        # Re-raise HTTP exceptions (like 400 for geocoding errors)
        raise
    except Exception as e:
        # Catch any unhandled exceptions and return a proper error response
        import traceback
        error_trace = traceback.format_exc()
        logger.error(f"Unhandled exception in get_livability_score: {e}\n{error_trace}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error while calculating livability score: {str(e)}"
        )


def _generate_batch_results(batch_request: BatchLocationRequest):
    """Generator function that yields batch results incrementally with keep-alive messages."""
    try:
        # Get telemetry stats for adaptive delay calculation
        telemetry_stats = None
        if batch_request.adaptive_delays:
            try:
                telemetry_stats = get_telemetry_stats()
            except Exception as e:
                logger.warning(f"Could not fetch telemetry stats: {e}")
        
        # Calculate optimal delay based on historical performance
        base_delay = _get_optimal_delay(telemetry_stats)
        current_delay = base_delay
        
        # Parse priorities if provided
        priorities_dict = None
        if batch_request.priorities:
            try:
                priorities_dict = json.loads(batch_request.priorities) if isinstance(batch_request.priorities, str) else batch_request.priorities
            except Exception as e:
                logger.warning(f"Could not parse priorities: {e}")
                priorities_dict = None
        
        results = []
        total_start_time = time.time()
        consecutive_errors = 0
        rate_limit_detected = False
        last_keepalive = time.time()
        KEEPALIVE_INTERVAL = 25  # Send keep-alive every 25 seconds
        
        logger.info(f"Batch request: {len(batch_request.locations)} locations, base delay: {base_delay}s")
        
        # Send initial status
        yield json.dumps({"status": "processing", "total_locations": len(batch_request.locations), "message": "Starting batch processing..."}) + "\n"
        
        for i, location in enumerate(batch_request.locations):
            location_start_time = time.time()
            retry_count = 0
            location_success = False
            
            # Retry logic for individual locations (max 2 retries with backoff)
            max_location_retries = 2
            for retry_attempt in range(max_location_retries + 1):
                try:
                    # Call the internal scoring function
                    result = _compute_single_score_internal(
                        location=location,
                        tokens=batch_request.tokens,
                        priorities_dict=priorities_dict,
                        include_chains=batch_request.include_chains,
                        enable_schools=batch_request.enable_schools,
                        test_mode=False,
                        request=None  # No request object for batch processing
                    )
                    
                    location_time = time.time() - location_start_time
                    location_success = True
                    
                    # Check for rate limit indicators in response
                    if result.get("rate_limited") or "429" in str(result.get("error", "")):
                        rate_limit_detected = True
                        # Increase delay for subsequent requests
                        current_delay = min(current_delay * 2, 15.0)  # Cap at 15s
                        logger.warning(f"Rate limit detected for {location}, increasing delay to {current_delay}s")
                    
                    logger.info(f"Batch [{i+1}/{len(batch_request.locations)}]: {location} completed in {location_time:.1f}s (retry: {retry_attempt})")
                    
                    batch_result = BatchLocationResult(
                        location=location,
                        success=True,
                        result=result,
                        response_time=round(location_time, 2),
                        retry_count=retry_attempt
                    )
                    results.append(batch_result)
                    
                    # Yield result immediately
                    yield json.dumps({
                        "type": "result",
                        "index": i + 1,
                        "total": len(batch_request.locations),
                        "result": batch_result.dict()
                    }) + "\n"
                    
                    # Reset consecutive error counter on success
                    consecutive_errors = 0
                    
                    # Gradually reduce delay if no errors (adaptive backoff)
                    if not rate_limit_detected and current_delay > base_delay:
                        current_delay = max(base_delay, current_delay * 0.9)
                    
                    break  # Success, exit retry loop
                    
                except HTTPException as e:
                    # HTTP exceptions (like 429) - retry with backoff
                    if e.status_code == 429 or "rate limit" in str(e.detail).lower():
                        rate_limit_detected = True
                        current_delay = min(current_delay * 2, 15.0)
                        
                        if retry_attempt < max_location_retries:
                            wait_time = current_delay * (retry_attempt + 1)
                            logger.warning(f"Rate limited for {location}, waiting {wait_time}s before retry {retry_attempt + 1}")
                            time.sleep(wait_time)
                            retry_count += 1
                            continue
                        else:
                            # Max retries reached
                            location_time = time.time() - location_start_time
                            error_msg = f"Rate limited after {max_location_retries} retries"
                            logger.error(f"Batch [{i+1}/{len(batch_request.locations)}]: {location} failed: {error_msg}")
                            batch_result = BatchLocationResult(
                                location=location,
                                success=False,
                                error=error_msg,
                                response_time=round(location_time, 2),
                                retry_count=retry_count
                            )
                            results.append(batch_result)
                            yield json.dumps({
                                "type": "result",
                                "index": i + 1,
                                "total": len(batch_request.locations),
                                "result": batch_result.dict()
                            }) + "\n"
                            consecutive_errors += 1
                            break
                    else:
                        # Other HTTP errors - don't retry
                        location_time = time.time() - location_start_time
                        error_msg = str(e.detail)
                        logger.error(f"Batch [{i+1}/{len(batch_request.locations)}]: {location} failed: {error_msg}")
                        batch_result = BatchLocationResult(
                            location=location,
                            success=False,
                            error=error_msg,
                            response_time=round(location_time, 2),
                            retry_count=retry_count
                        )
                        results.append(batch_result)
                        yield json.dumps({
                            "type": "result",
                            "index": i + 1,
                            "total": len(batch_request.locations),
                            "result": batch_result.dict()
                        }) + "\n"
                        consecutive_errors += 1
                        break
                        
                except Exception as e:
                    # Other exceptions - retry once with backoff
                    if retry_attempt < max_location_retries:
                        wait_time = base_delay * (retry_attempt + 1)
                        logger.warning(f"Error for {location}: {e}, retrying in {wait_time}s")
                        time.sleep(wait_time)
                        retry_count += 1
                        continue
                    else:
                        # Max retries reached
                        location_time = time.time() - location_start_time
                        error_msg = str(e)
                        logger.error(f"Batch [{i+1}/{len(batch_request.locations)}]: {location} failed after {max_location_retries} retries: {error_msg}")
                        batch_result = BatchLocationResult(
                            location=location,
                            success=False,
                            error=error_msg,
                            response_time=round(location_time, 2),
                            retry_count=retry_count
                        )
                        results.append(batch_result)
                        yield json.dumps({
                            "type": "result",
                            "index": i + 1,
                            "total": len(batch_request.locations),
                            "result": batch_result.dict()
                        }) + "\n"
                        consecutive_errors += 1
                        break
            
            # Adaptive delay adjustment based on consecutive errors
            if consecutive_errors >= 3:
                # Multiple consecutive errors - significantly increase delay
                current_delay = min(current_delay * 1.5, 20.0)
                logger.warning(f"Multiple consecutive errors detected, increasing delay to {current_delay}s")
            elif consecutive_errors > 0:
                # Some errors - moderate increase
                current_delay = min(current_delay * 1.2, 10.0)
            
            # Wait before next request (except for last one)
            if i < len(batch_request.locations) - 1:
                # Use current_delay (which may have been adjusted)
                # Send keep-alive messages during long waits
                wait_start = time.time()
                while time.time() - wait_start < current_delay:
                    elapsed = time.time() - wait_start
                    remaining = current_delay - elapsed
                    sleep_time = min(remaining, KEEPALIVE_INTERVAL)
                    time.sleep(sleep_time)
                    
                    # Send keep-alive if needed
                    if time.time() - last_keepalive >= KEEPALIVE_INTERVAL:
                        yield json.dumps({
                            "type": "keepalive",
                            "message": f"Processing... {i+1}/{len(batch_request.locations)} locations completed",
                            "elapsed_seconds": round(time.time() - total_start_time, 1)
                        }) + "\n"
                        last_keepalive = time.time()
        
        total_time = time.time() - total_start_time
        successful = sum(1 for r in results if r.success)
        failed = len(results) - successful
        
        # Calculate performance metrics
        successful_results = [r for r in results if r.success]
        avg_response_time = sum(r.response_time for r in successful_results) / len(successful_results) if successful_results else 0
        total_retries = sum(r.retry_count for r in results)
        
        logger.info(f"Batch completed: {successful}/{len(batch_request.locations)} successful in {total_time:.1f}s (avg: {avg_response_time:.1f}s, retries: {total_retries})")
        
        # Yield final summary
        final_response = {
            "type": "complete",
            "batch_summary": {
                "batch_size": len(batch_request.locations),
                "successful": successful,
                "failed": failed,
                "success_rate": round((successful / len(batch_request.locations)) * 100, 1) if batch_request.locations else 0,
                "total_time_seconds": round(total_time, 2),
                "average_response_time": round(avg_response_time, 2),
                "total_retries": total_retries,
                "base_delay_used": base_delay,
                "final_delay_used": round(current_delay, 2)
            },
            "performance_insights": {
                "rate_limits_detected": rate_limit_detected,
                "adaptive_delay_adjustments": current_delay != base_delay,
                "consecutive_errors": consecutive_errors
            },
            "results": [r.dict() for r in results]
        }
        yield json.dumps(final_response) + "\n"
        
    except Exception as e:
        error_msg = f"Batch processing failed: {str(e)}"
        logger.error(f"Unhandled exception in batch generator: {e}", exc_info=True)
        yield json.dumps({"type": "error", "error": error_msg}) + "\n"


@app.post("/batch")
def batch_livability_scores(request: Request, batch_request: BatchLocationRequest):
    """
    Calculate livability scores for multiple locations in a batch.
    
    Uses historical performance data to optimize delays and error handling.
    Processes locations sequentially to avoid rate limits.
    Returns streaming results to prevent client timeouts.
    
    Parameters:
        locations: List of addresses or ZIP codes (max 10 per batch)
        tokens: Optional token allocation (same format as /score)
        priorities: Optional priority-based allocation (same format as /score)
        include_chains: Include chain/franchise businesses (default: True)
        enable_schools: Enable school scoring (default: uses global flag)
        max_batch_size: Maximum locations per batch (default: 10)
        adaptive_delays: Use telemetry to adjust delays (default: True)
    
    Returns:
        Streaming JSON with results for each location, including performance metrics.
        Each line is a JSON object. Types: "status", "result", "keepalive", "complete", "error"
    """
    # Validate batch size
    if len(batch_request.locations) > batch_request.max_batch_size:
        raise HTTPException(
            status_code=400,
            detail=f"Batch size limited to {batch_request.max_batch_size} locations. Received {len(batch_request.locations)}"
        )
    
    # Validate locations list is not empty
    if not batch_request.locations or len(batch_request.locations) == 0:
        raise HTTPException(
            status_code=400,
            detail="At least one location is required"
        )
    
    return StreamingResponse(
        _generate_batch_results(batch_request),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )


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


def _calculate_data_quality_summary(pillars: dict, area_type: str = None, form_context: str = None) -> dict:  # Changed from Dict to dict
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
        most_common_area = area_type or "unknown"
        metro_name = None
    
    # Compute baseline contexts for pillars that use them
    baseline_contexts = {}
    if area_type:
        from data_sources.data_quality import get_baseline_context
        
        # Compute baseline_context for each pillar that uses it
        for pillar_name in ['active_outdoors', 'public_transit_access']:
            if pillar_name in pillars:
                try:
                    baseline_contexts[pillar_name] = get_baseline_context(
                        area_type=area_type,
                        form_context=form_context,
                        pillar_name=pillar_name
                    )
                except Exception:
                    pass  # Non-fatal if computation fails
    
    # Compute deprecated effective_area_type (for backward compatibility)
    # Use form_context if available, otherwise use area_type
    effective_area_type = form_context if form_context is not None else area_type
    
    area_classification_dict = {
        "area_type": most_common_area,  # Universal morphological classification
        "form_context": form_context,  # Beauty pillars only (architectural classification)
        "metro_name": metro_name
    }
    
    # Add baseline_contexts for pillars that use them
    if baseline_contexts:
        area_classification_dict["baseline_contexts"] = baseline_contexts
    
    # Add deprecated effective_area_type for backward compatibility
    if effective_area_type:
        area_classification_dict["effective_area_type"] = effective_area_type  # DEPRECATED: Use form_context instead
    
    return {
        "data_sources_used": list(data_sources_used),
        "area_classification": area_classification_dict,
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
        "version": API_VERSION,
        "architecture": "9 Purpose-Driven Pillars",
        "pillars": [
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
        from pillars.built_beauty import _fetch_historic_data
        
        # Get historic markers for historic district detection using shared helper
        historic_data = _fetch_historic_data(lat, lon, radius_m=radius_m)
        historic_landmarks = historic_data.get('historic_landmarks_count')
        median_year_built = historic_data.get('median_year_built')
        
        # Get pre_1940_pct from year_built_data if available
        year_built_data = historic_data.get('year_built_data', {})
        pre_1940_pct = year_built_data.get('pre_1940_pct') if isinstance(year_built_data, dict) else None
        
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
            median_year_built=median_year_built,
            material_profile=diversity_metrics.get("material_profile"),
            heritage_profile=diversity_metrics.get("heritage_profile"),
            type_category_diversity=diversity_metrics.get("type_category_diversity"),
            height_stats=diversity_metrics.get("height_stats")
        )
        
        # Calculate individual components for breakdown (using simplified helpers)
        targets = CONTEXT_TARGETS.get(effective_area_type, CONTEXT_TARGETS["urban_core"])
        height_beauty = min(13.2, _score_band(diversity_metrics["levels_entropy"], targets["height"]))
        combined_type_div = diversity_metrics["building_type_diversity"]
        if diversity_metrics.get("type_category_diversity") is not None:
            combined_type_div = max(combined_type_div, diversity_metrics.get("type_category_diversity") or 0.0)
        type_beauty = min(13.2, _score_band(combined_type_div, targets["type"]))
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
        # Built beauty component score is capped at 33.0 to maintain balance with other pillars.
        # This cap is based on the architectural diversity scoring system where:
        # - Component scores (height, type, footprint, coherence) are additive
        # - The cap prevents any single component from dominating the overall livability score
        # - The multiplier (DENSITY_MULTIPLIER) already provides area-type context
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