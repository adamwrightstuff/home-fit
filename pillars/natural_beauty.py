"""
Natural Beauty pillar implementation (trees, scenic context, and enhancers).
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

from logging_config import get_logger

from data_sources import osm_api
from data_sources.radius_profiles import get_radius_profile
from pillars.beauty_common import NATURAL_ENHANCER_CAP, normalize_beauty_score

logger = get_logger(__name__)

# Try optional data sources that are only available in specific cities.
try:
    from data_sources import nyc_api as nyc_api
except ImportError:  # pragma: no cover - optional dependency
    nyc_api = None  # type: ignore

try:
    from data_sources import street_tree_api
except ImportError:  # pragma: no cover - optional dependency
    street_tree_api = None  # type: ignore

# Feature flags for new calibration features
# Set to False to disable new features for rollback capability
ENABLE_CANOPY_SATURATION = True  # Reduce returns above 50% canopy
ENABLE_WATER_TYPE_DIFF = False  # Disabled until OSM water type data validated
ENABLE_TOPOGRAPHY_BOOST_ARID = True  # Increase topography weight in arid regions
ENABLE_COMPONENT_DOMINANCE_GUARD = False  # Phase 2: Prevent single component from dominating
ENABLE_VISIBILITY_PENALTY_REDUCTION = True  # Reduce visibility penalty in coastal areas

# Natural context scoring constants.
TOPOGRAPHY_BONUS_MAX = 12.0
LANDCOVER_BONUS_MAX = 8.0
WATER_BONUS_MAX = 40.0  # Increased to make water a primary visual element and prevent capping high-water coastal locations
NATURAL_CONTEXT_BONUS_CAP = 20.0

# Component dominance guard (prevents single component from exceeding 60% of context bonus)
MAX_COMPONENT_DOMINANCE_RATIO = 0.6

GVI_BONUS_MAX = 8.0
BIODIVERSITY_BONUS_MAX = 4.0
CANOPY_EXPECTATION_BONUS_MAX = 6.0
CANOPY_EXPECTATION_PENALTY_MAX = 6.0
STREET_TREE_BONUS_MAX = 5.0

MULTI_RADIUS_CANOPY = {
    "micro_400m": 400,
    "neighborhood_1000m": 1000,
    "macro_2000m": 2000,
}

# Legacy: Area-type-based expectations (deprecated - use climate-first approach)
CANOPY_EXPECTATIONS = {
    "urban_core": 18.0,
    "urban_core_lowrise": 22.0,
    "historic_urban": 26.0,
    "urban_residential": 28.0,
    "suburban": 32.0,
    "exurban": 36.0,
    "rural": 38.0,
    "unknown": 25.0,
}

# Climate-first base expectations (from research synthesis)
# These represent achievable targets by climate zone, not current state
CLIMATE_BASE_EXPECTATIONS = {
    "arid": 8.0,           # Research: 1.5-10% urban, 7-15% suburban (mid-point)
    "mediterranean": 25.0,  # Research: 20-30% typical, target 25-35% (lower end)
    "temperate": 35.0,      # Research: 30-40% typical (mid-point)
    "humid_temperate": 40.0, # Research: 30-40% + humid boost
    "tropical": 35.0,       # Research: 30%+ (mid-range)
    "continental": 32.0,    # Research: 25-40% (mid-point)
    "unknown": 30.0,        # Default fallback
}

# Area type adjustments within climate zones
# Applied as multipliers to climate base expectations
AREA_TYPE_ADJUSTMENTS = {
    "urban_core": 0.75,         # Denser, less space for trees
    "urban_core_lowrise": 0.80, # Slightly more space
    "historic_urban": 0.85,     # Moderate density
    "urban_residential": 0.85,  # Moderate density
    "suburban": 1.0,            # Baseline
    "exurban": 1.15,            # More space, higher canopy
    "rural": 1.25,              # Most space, highest potential
    "unknown": 1.0,             # Default
}

# Base water expectations by area type (percentage)
# Adjusted by climate: arid regions have lower natural water expectations
WATER_EXPECTATIONS = {
    "urban_core": 3.0,
    "urban_core_lowrise": 3.5,
    "historic_urban": 4.0,
    "urban_residential": 4.0,
    "suburban": 5.0,
    "exurban": 7.0,
    "rural": 8.0,
    "unknown": 5.0,
}

GREEN_VIEW_WEIGHTS = {
    "urban_core": 1.15,
    "historic_urban": 1.2,
    "urban_residential": 1.05,
    "suburban": 1.0,
    "exurban": 0.9,
    "rural": 0.85,
    "urban_core_lowrise": 1.1,
    "unknown": 1.0,
}

CONTEXT_SCALERS = {
    "urban_core": 0.85,
    "historic_urban": 0.95,
    "urban_core_lowrise": 0.95,
    "urban_residential": 1.0,
    "suburban": 1.05,
    "exurban": 1.1,
    "rural": 1.15,
    "unknown": 1.0,
}

BIODIVERSITY_WEIGHTS = {
    "forest": 0.5,
    "wetland": 0.2,
    "shrub": 0.2,
    "grass": 0.1,
}

# Climate adjustments are now calculated dynamically based on lat/lon/elevation
# No hardcoded metro lists required - fully scalable and works globally

# Area-type-specific context bonus weights
# Adjusts how much topography, landcover, and water contribute to context bonus
# Updated to increase water weights reflecting its importance for natural beauty
CONTEXT_BONUS_WEIGHTS = {
    "urban_core": {
        "topography": 0.30,   # Decreased from 0.3 (maintained)
        "landcover": 0.35,    # Decreased from 0.4
        "water": 0.35         # Increased from 0.3
    },
    "urban_core_lowrise": {
        "topography": 0.35,   # Maintained
        "landcover": 0.30,    # Decreased from 0.4
        "water": 0.35         # Increased from 0.25
    },
    "historic_urban": {
        "topography": 0.35,   # Decreased from 0.4
        "landcover": 0.30,    # Decreased from 0.35
        "water": 0.35         # Increased from 0.25
    },
    "urban_residential": {
        "topography": 0.25,   # Decreased to prioritize water
        "landcover": 0.30,    # Decreased to prioritize water
        "water": 0.45         # CRITICAL: Increased significantly - water as primary visual element
    },
    "suburban": {
        "topography": 0.30,   # Decreased to prioritize water
        "landcover": 0.30,    # Decreased to prioritize water
        "water": 0.40         # CRITICAL: Increased significantly - water as primary visual element
    },
    "exurban": {
        "topography": 0.40,   # Decreased from 0.6
        "landcover": 0.35,    # Increased from 0.25
        "water": 0.25         # Increased from 0.15
    },
    "rural": {
        "topography": 0.45,   # Decreased from 0.65
        "landcover": 0.35,    # Increased from 0.2
        "water": 0.20         # Increased from 0.15 (lower priority in rural)
    },
    "unknown": {
        "topography": 0.4,
        "landcover": 0.35,
        "water": 0.25
    }
}


def _get_climate_adjustment(lat: float, lon: float, elevation_m: Optional[float] = None) -> float:
    """
    Dynamically determine climate adjustment based on geographic coordinates.
    Uses simplified Köppen-Geiger climate zone approximation via lat/lon + elevation.
    
    Elevation adjustment (applied to base multiplier):
    - >1500m: 1.10x (higher = cooler, more precipitation potential)
    - 800-1500m: 1.05x
    - <800m: 1.00x (default)
    
    Base multipliers by region:
    - Arid/Desert (SW US): 0.65-0.85
    - Tropical/Subtropical (South): 1.15-1.30
    - Temperate/Humid (NW, NE): 1.05-1.15
    - Mid-latitude (default): 0.95-1.05
    
    Args:
        lat: Latitude (-90 to 90)
        lon: Longitude (-180 to 180)
        elevation_m: Optional elevation in meters (clamped 0-8848)
    
    Returns:
        Multiplier (0.65-1.43) for canopy expectations
    """
    
    # Clamp and validate inputs
    lat = max(-90.0, min(90.0, lat))
    lon = ((lon + 180) % 360) - 180  # Normalize longitude to -180 to 180
    elevation_m = max(0, min(8848, elevation_m or 0))  # Clamp elevation
    
    # Elevation adjustment factor
    elevation_factor = 1.0
    if elevation_m > 1500:
        elevation_factor = 1.10
    elif elevation_m > 800:
        elevation_factor = 1.05
    
    # Tropical/Subtropical (South Florida, Gulf Coast, Hawaii)
    if lat < 30:
        if -100 <= lon <= -80:  # Gulf Coast, Florida
            return 1.30
        elif lon < -150 or lon > -120:  # Hawaii, Caribbean periphery
            return 1.30
        else:  # Broader subtropical
            return 1.15
    
    # Northern temperate/boreal (lat > 45)
    if lat > 45:
        if lon < -100:  # Pacific Northwest
            return 1.15 * elevation_factor
        elif lon > -80:  # Northeast
            return 1.10 * elevation_factor
        else:  # Interior North
            return 1.05 * elevation_factor
    
    # Coastal California and Oregon (30-45°N, west of -117°)
    # Check this BEFORE arid zone to exclude coastal areas
    # Includes San Diego (-117°), LA area (-118°), San Francisco (-122°)
    if 30 <= lat <= 45 and lon <= -117:
        return 1.0  # Temperate coastal
    
    # Arid/Desert zones (Southwest US, interior West)
    # Includes Arizona, Nevada, interior California, New Mexico, Utah
    # Excludes coastal California (lon < -120)
    if 25 <= lat <= 40 and -125 <= lon <= -100:
        # Interior Southwest (Arizona, Nevada, interior California)
        if elevation_m < 800:
            return 0.65 * elevation_factor
        elif elevation_m < 1500:
            return 0.80 * elevation_factor
        else:
            return 0.85 * elevation_factor
    
    # Mid-latitude temperate (30-45°N, the bulk of continental US)
    if 30 <= lat <= 45:
        if lon >= -118 and lon < -100:  # Interior West (not coastal, not arid)
            return 0.95
        elif lon > -85:  # East Coast (more humid/humid subtropical)
            return 1.05
        else:  # Interior (less humid)
            return 0.95
    
    # Default fallback (unexpected regions)
    return 1.0


def _get_climate_zone_name(lat: float, lon: float, elevation_m: Optional[float] = None) -> str:
    """
    Get climate zone name for climate-first expectation calculation.
    
    Returns simplified climate zone name based on multiplier value.
    This enables climate-first architecture where climate determines base expectations.
    
    Args:
        lat: Latitude
        lon: Longitude
        elevation_m: Optional elevation in meters
    
    Returns:
        Climate zone name: "arid", "mediterranean", "temperate", "humid_temperate", "tropical", "continental", "unknown"
    """
    multiplier = _get_climate_adjustment(lat, lon, elevation_m)
    
    # Mediterranean climate detection (coastal California, 30-40°N, west of -117°)
    # Characterized by dry summers, wet winters, moderate canopy expectations
    if 30 <= lat <= 40 and lon <= -117:
        return "mediterranean"
    
    # Classify by multiplier ranges
    if multiplier < 0.75:
        return "arid"
    elif multiplier < 0.90:
        return "semi_arid"  # Falls back to arid in expectations
    elif multiplier < 1.05:
        return "temperate"
    elif multiplier < 1.20:
        return "humid_temperate"
    elif multiplier >= 1.20:
        return "tropical"
    else:
        # Continental climates (interior, seasonal extremes)
        # Typically 0.95-1.05 multiplier range
        if 40 <= lat <= 50:
            return "continental"
        return "unknown"


def _get_adjusted_canopy_expectation(area_type: str, lat: float, lon: float, 
                                     elevation_m: Optional[float] = None) -> float:
    """
    Get canopy expectation using climate-first architecture.
    
    CLIMATE-FIRST APPROACH:
    1. Climate determines base expectation (what's achievable in that climate)
    2. Area type adjusts within climate (urban core lower, rural higher)
    
    This is more scalable and fair than area-type-first approach.
    
    Args:
        area_type: Base area type (for adjustment factor)
        lat: Latitude
        lon: Longitude
        elevation_m: Optional elevation in meters (from topography data)
    
    Returns:
        Adjusted canopy expectation percentage
    """
    # Step 1: Get climate zone and base expectation
    climate_zone = _get_climate_zone_name(lat, lon, elevation_m)
    
    # Handle semi-arid as arid (similar expectations)
    if climate_zone == "semi_arid":
        climate_zone = "arid"
    
    climate_base = CLIMATE_BASE_EXPECTATIONS.get(climate_zone, CLIMATE_BASE_EXPECTATIONS["unknown"])
    
    # Step 2: Apply area type adjustment within climate
    area_type_key = area_type.lower() if area_type else "unknown"
    area_adjustment = AREA_TYPE_ADJUSTMENTS.get(area_type_key, AREA_TYPE_ADJUSTMENTS["unknown"])
    
    # Step 3: Calculate final expectation
    expectation = climate_base * area_adjustment
    
    # Ensure reasonable bounds (don't go below 3% or above 60%)
    return max(3.0, min(60.0, expectation))


def _get_water_expectation(area_type: str, lat: float, lon: float, 
                          elevation_m: Optional[float] = None) -> float:
    """
    Get water expectation adjusted for regional climate.
    
    Arid regions have lower natural water expectations, so water presence is rarer and more valuable.
    Tropical regions have higher natural water expectations, so water is more common.
    
    Args:
        area_type: Base area type
        lat: Latitude
        lon: Longitude
        elevation_m: Optional elevation in meters (from topography data)
    
    Returns:
        Adjusted water expectation percentage
    """
    base_expectation = WATER_EXPECTATIONS.get(area_type.lower(), WATER_EXPECTATIONS["unknown"])
    climate_multiplier = _get_climate_adjustment(lat, lon, elevation_m)
    
    # For water, invert the climate logic: arid = lower expectation (water is rare)
    # Arid regions (0.65 multiplier) should have 0.5x water expectation
    # Tropical regions (1.3 multiplier) should have 1.5x water expectation
    if climate_multiplier < 0.8:  # Arid/semi-arid
        water_multiplier = 0.5
    elif climate_multiplier > 1.2:  # Tropical/humid
        water_multiplier = 1.5
    else:  # Temperate
        water_multiplier = 1.0
    
    adjusted = base_expectation * water_multiplier
    
    # Ensure reasonable bounds (don't go below 1% or above 15%)
    return max(1.0, min(15.0, adjusted))


def _score_tree_canopy(canopy_pct: float) -> float:
    """
    Improved tree canopy scoring curve addressing low-canopy area underestimation.
    
    Rationale: Arid (Scottsdale, Sedona) and dense urban (Manhattan Beach, Beacon Hill) 
    areas should not be penalized for inherently low canopy while still rewarding higher coverage.
    
    With ENABLE_CANOPY_SATURATION: Reduces returns above 50% canopy to prevent over-rewarding
    extremely dense forest areas that may not be more beautiful than well-balanced landscapes.
    """
    canopy = max(0.0, min(100.0, canopy_pct))
    
    # Tier 1: Very low canopy (0-10%)
    # More generous for desert and dense urban cores
    if canopy <= 10.0:
        base_score = canopy * 1.5  # Increased from 1.1 (0-15 points instead of 0-11)
    
    # Tier 2: Low to moderate (10-20%)
    # Smooth transition with better rewards for marginal increases
    elif canopy <= 20.0:
        base_score = 15.0 + (canopy - 10.0) * 0.7  # 15-22 points
    
    # Tier 3: Moderate (20-50%)
    # Original curve, slightly adjusted
    elif canopy <= 50.0:
        base_score = 22.0 + (canopy - 20.0) * 0.7  # 22-43 points
    
    # Tier 4: High (50-70%)
    # Reduced returns above 50% if saturation enabled
    elif canopy <= 70.0:
        if ENABLE_CANOPY_SATURATION:
            # Reduced slope: 43-48 points (was 43-50)
            base_score = 43.0 + (canopy - 50.0) * 0.25  # 43-48 points
        else:
            # Original curve: 43-50 points
            base_score = 43.0 + (canopy - 50.0) * 0.35  # 43-50 points
    
    # Tier 5: Very high (70%+)
    else:
        if ENABLE_CANOPY_SATURATION:
            # Cap at 48 instead of 50 to reduce over-rewarding dense forest
            base_score = 48.0
        else:
            base_score = 50.0  # Cap at 50
    
    return base_score


def _calculate_street_tree_bonus(canopy_pct: float, street_tree_count: int, area_type: Optional[str] = None) -> float:
    """
    Calculate street tree bonus for low-canopy urban areas with mature street trees.
    
    Only applies when satellite canopy is very low (<10%) and street trees are present.
    This helps urban historic places (Garden District, Beacon Hill) get credit for
    street-level greenery even when satellite canopy is sparse.
    
    Args:
        canopy_pct: Primary canopy percentage from satellite data
        street_tree_count: Number of street trees found
        area_type: Optional area type for context
    
    Returns:
        Bonus points (0-5.0), capped at STREET_TREE_BONUS_MAX
    """
    # Only apply when canopy is very low (<10%)
    if canopy_pct >= 10.0 or street_tree_count <= 0:
        return 0.0
    
    # Bonus formula: 20 trees = full 5 points
    # Linear scaling: 1 tree = 0.25 points, 20 trees = 5.0 points
    bonus = min(STREET_TREE_BONUS_MAX, (street_tree_count / 20.0) * STREET_TREE_BONUS_MAX)
    
    return bonus


def _score_nyc_trees(tree_count: int) -> float:
    """
    Score street trees using NYC Street Tree Census heuristic.
    """
    if tree_count <= 0:
        return 0.0
    # Diminishing returns as tree counts grow.
    score = min(50.0, 12.0 * math.log1p(tree_count))
    return score


def _compute_viewshed_proxy(viewpoints: List[Dict], radius_m: int = 1500,
                            natural_context_bonus: float = 0.0,
                            landcover_metrics: Optional[Dict] = None) -> Tuple[float, Dict]:
    """
    Compute a lightweight scenic bonus based on nearby viewpoint features.
    
    Deduplication: Reduces scenic bonus if natural context already captures
    similar features (e.g., viewpoints near water/parks already counted in context bonus).
    
    Args:
        viewpoints: List of viewpoint features from OSM
        radius_m: Search radius
        natural_context_bonus: Total natural context bonus (for deduplication)
        landcover_metrics: Optional landcover metrics (to detect water/parks overlap)
    
    Returns:
        Tuple of (scenic_bonus, metadata_dict)
    """
    if not viewpoints:
        return 0.0, {
            "count": 0,
            "closest_distance_m": None,
            "weights_sum": 0.0,
            "top_viewpoints": [],
            "deduplication_applied": False
        }

    radius_m = max(radius_m, 1)
    weights_sum = 0.0
    viewpoint_summaries: List[Dict] = []

    for feature in viewpoints:
        distance = feature.get("distance_m", radius_m)
        try:
            distance = float(distance)
        except (TypeError, ValueError):
            distance = radius_m
        distance = max(0.0, distance)

        normalized = max(0.0, 1.0 - min(distance, radius_m) / radius_m)
        weight = max(0.05, normalized)
        weights_sum += weight

        viewpoint_summaries.append({
            "name": feature.get("name"),
            "distance_m": round(distance, 1)
        })

    viewpoint_summaries.sort(key=lambda item: item.get("distance_m", float("inf")))
    viewpoint_summaries = viewpoint_summaries[:5]

    scenic_bonus_raw = min(6.0, weights_sum * 3.0)
    
    # Deduplication: Reduce scenic bonus if natural context already captures similar features
    deduplication_factor = 1.0
    deduplication_reason = None
    
    # If we have significant natural context bonus (water, parks, topography),
    # reduce scenic bonus to avoid double-counting
    if natural_context_bonus > 8.0:
        # High context bonus suggests natural features already captured
        # Reduce scenic bonus by up to 40% if context bonus is very high
        deduplication_factor = max(0.6, 1.0 - (natural_context_bonus / 20.0) * 0.4)
        deduplication_reason = f"High natural context bonus ({natural_context_bonus:.1f})"
    elif landcover_metrics:
        # Check if viewpoints are near water features (already counted in water bonus)
        water_pct = float(landcover_metrics.get("water_pct", 0.0))
        if water_pct > 10.0:
            # Significant water coverage - viewpoints likely water-related
            deduplication_factor = max(0.7, 1.0 - (water_pct / 50.0) * 0.3)
            deduplication_reason = f"Water features present ({water_pct:.1f}%)"
    
    scenic_bonus = scenic_bonus_raw * deduplication_factor
    
    metadata = {
        "count": len(viewpoints),
        "closest_distance_m": viewpoint_summaries[0]["distance_m"] if viewpoint_summaries else None,
        "weights_sum": round(weights_sum, 3),
        "top_viewpoints": viewpoint_summaries,
        "scenic_bonus_raw": round(scenic_bonus_raw, 2),
        "deduplication_factor": round(deduplication_factor, 3),
        "deduplication_applied": deduplication_factor < 1.0,
        "deduplication_reason": deduplication_reason
    }
    return scenic_bonus, metadata


def _score_trees(lat: float, lon: float, city: Optional[str], location_scope: Optional[str] = None,
                 area_type: Optional[str] = None, location_name: Optional[str] = None,
                 overrides: Optional[Dict[str, float]] = None,
                 density: Optional[float] = None) -> Tuple[float, Dict]:
    """Score trees from multiple real data sources (0-50)."""
    score = 0.0
    sources: List[str] = []
    details: Dict = {}
    applied_overrides: List[str] = []
    canopy_points: Optional[float] = None
    street_tree_points: Optional[float] = None
    osm_tree_points: Optional[float] = None
    census_points: Optional[float] = None
    tree_radius_used: Optional[int] = None
    street_tree_feature_total = 0
    primary_canopy_pct: Optional[float] = None
    canopy_multi: Dict[str, Optional[float]] = {}
    gvi_metrics: Optional[Dict[str, float]] = None
    gvi_bonus = 0.0
    biodiversity_entropy = 0.0
    biodiversity_bonus = 0.0
    expectation_adjustment = 0.0
    expectation_penalty = 0.0
    area_type_key = (area_type or "").lower() or "unknown"
    gvi_radius_used: Optional[int] = None

    overrides = overrides or {}

    def _clamp(value: float, min_val: float, max_val: float) -> float:
        return max(min_val, min(max_val, value))

    def _score_topography_component(metrics: Dict) -> float:
        if not metrics:
            return 0.0
        relief = float(metrics.get("relief_range_m") or 0.0)
        slope_mean = float(metrics.get("slope_mean_deg") or 0.0)
        steep_fraction = float(metrics.get("steep_fraction") or 0.0)

        relief_factor = min(1.0, relief / 600.0)  # 600m relief → full credit
        slope_factor = min(1.0, max(0.0, (slope_mean - 3.0) / 17.0))  # 20° mean slope → full
        steep_factor = min(1.0, max(0.0, (steep_fraction - 0.05) / 0.35))  # >40% steep terrain

        combined = max(0.0, min(1.0, (0.5 * relief_factor) + (0.3 * slope_factor) + (0.2 * steep_factor)))
        return TOPOGRAPHY_BONUS_MAX * combined

    def _score_landcover_component(metrics: Dict, context_area_type: Optional[str], 
                                   lat: Optional[float] = None, lon: Optional[float] = None,
                                   elevation_m: Optional[float] = None,
                                   topography_metrics: Optional[Dict] = None) -> Tuple[float, float]:
        if not metrics:
            return 0.0, 0.0

        forest_pct = float(metrics.get("forest_pct") or 0.0)
        wetland_pct = float(metrics.get("wetland_pct") or 0.0)
        shrub_pct = float(metrics.get("shrub_pct") or 0.0)
        grass_pct = float(metrics.get("grass_pct") or 0.0)
        developed_pct = float(metrics.get("developed_pct") or 0.0)
        water_pct = float(metrics.get("water_pct") or 0.0)

        forest_factor = min(1.0, forest_pct / 40.0)  # 40% forest → full
        wetland_factor = min(1.0, wetland_pct / 10.0)
        shrub_factor = min(1.0, shrub_pct / 25.0)
        grass_factor = min(1.0, grass_pct / 30.0)

        natural_index = (0.6 * forest_factor) + (0.2 * wetland_factor) + (0.1 * shrub_factor) + (0.1 * grass_factor)

        # Developed land reduces the boost, but not below zero
        developed_penalty = min(0.8, developed_pct / 120.0)
        natural_index = max(0.0, natural_index * (1.0 - developed_penalty))

        # Suburban/rural contexts get a small lift
        if context_area_type in ("rural", "exurban"):
            natural_index = min(1.0, natural_index * 1.15)

        landcover_score = LANDCOVER_BONUS_MAX * min(1.0, natural_index)

        # Climate-calibrated water scoring: use expectation-adjusted base factor
        # This makes water scoring proportional to what's achievable in each climate
        water_expectation = 5.0  # Default fallback
        if lat is not None and lon is not None and context_area_type:
            water_expectation = _get_water_expectation(context_area_type, lat, lon, elevation_m)
        
        # Base water score: use climate-adjusted expectation as denominator
        # This means water is scored relative to regional norms, not absolute thresholds
        if water_expectation > 0:
            base_water_factor = min(2.0, water_pct / water_expectation)  # Allow up to 2x for abundant water
        else:
            base_water_factor = min(1.0, water_pct / 25.0)  # Fallback to old logic
        
        base_water_score = base_water_factor * 12.0
        
        # Coastal bonus (additive, capped) - consistent with built beauty pattern
        coastal_bonus = 0.0
        if water_pct > 25.0:
            coastal_bonus = 6.0  # Major waterfront (>25%): 6.0 bonus
        elif water_pct > 15.0:
            coastal_bonus = 4.0  # Substantial water (15-25%): 4.0 bonus
        elif water_pct > 5.0:
            coastal_bonus = 2.0  # Moderate water (5-15%): 2.0 bonus
        
        # Area-type bonus (additive, capped) - consistent with built beauty pattern
        area_bonus = 0.0
        if context_area_type in ("historic_urban", "urban_core_lowrise", "suburban", "urban_residential"):
            area_bonus = 3.0  # Fixed bonus for these area types
        
        # Climate-calibrated water rarity/abundance bonus (additive, capped)
        # Water is valuable both when rare (arid) and when abundant (coastal)
        rarity_bonus = 0.0
        if lat is not None and lon is not None and context_area_type and water_expectation > 0:
            water_rarity_ratio = water_pct / water_expectation
            # If water is significantly rarer than expected (ratio < 0.5), apply large bonus
            if water_rarity_ratio < 0.5:
                rarity_bonus = 8.0  # Very rare (arid regions with water)
            # If water is significantly more abundant than expected (ratio > 2.0), apply bonus
            elif water_rarity_ratio > 2.0:
                rarity_bonus = 4.0  # Abundant (coastal areas)
            # If water is moderately rare (0.5-1.0), apply smaller bonus
            elif water_rarity_ratio < 1.0:
                rarity_bonus = 3.0  # Moderately rare
        
        # Visibility bonus/penalty (additive, can be negative) - consistent with built beauty pattern
        visibility_bonus = 0.0
        if topography_metrics:
            elevation_mean = float(topography_metrics.get("elevation_mean_m", 0.0))
            # Elevation bonus: higher elevation = better visibility
            elevation_bonus = 2.0 if elevation_mean > 50.0 else 0.0
            # Development penalty: dense development = reduced visibility
            developed_penalty = -3.0 if developed_pct > 80.0 else (-1.5 if developed_pct > 60.0 else 0.0)
            visibility_bonus = elevation_bonus + developed_penalty
        
        # Calculate water score: base + bonuses (additive, like built beauty)
        # This is consistent with built beauty's pattern: base + material_bonus + heritage_bonus + etc.
        water_score = min(WATER_BONUS_MAX, base_water_score + coastal_bonus + area_bonus + rarity_bonus + visibility_bonus)

        return landcover_score, water_score

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

    # Priority 1: GEE satellite tree canopy
    try:
        from data_sources import census_api, data_quality

        # Use pre-computed density if provided, otherwise fetch it
        if density is None:
            density = census_api.get_population_density(lat, lon)
        
        if area_type is None:
            detected_area_type = data_quality.detect_area_type(
                lat,
                lon,
                density,
                location_input=location_name,
                city=city
            )
            area_type = detected_area_type
        
        area_type_key = (area_type or "").lower() or "unknown"

        radius_profile = get_radius_profile('natural_beauty', area_type, location_scope)
        radius_m = int(radius_profile.get('tree_canopy_radius_m', 1000))
        tree_radius_used = radius_m
        logger.debug("Radius profile (beauty): area_type=%s scope=%s tree_canopy_radius=%sm", area_type, location_scope, radius_m)

        from data_sources.gee_api import get_tree_canopy_gee, get_urban_greenness_gee

        # Use pre-computed 5km canopy if available and radius matches, otherwise fetch
        if precomputed_tree_canopy_5km is not None and radius_m == 5000:
            gee_canopy = precomputed_tree_canopy_5km
            logger.debug("Using pre-computed tree canopy (5km): %.1f%%", gee_canopy)
        else:
            gee_canopy = get_tree_canopy_gee(lat, lon, radius_m=radius_m, area_type=area_type)

        if location_scope != 'neighborhood' and gee_canopy is not None and gee_canopy < 25.0 and area_type == 'urban_core':
            gee_canopy_larger = get_tree_canopy_gee(lat, lon, radius_m=2000, area_type=area_type)
            if gee_canopy_larger is not None and gee_canopy_larger > gee_canopy:
                gee_canopy = gee_canopy_larger
                tree_radius_used = 2000
                if gee_canopy < 30.0:
                    gee_canopy_3km = get_tree_canopy_gee(lat, lon, radius_m=3000, area_type=area_type)
                    if gee_canopy_3km is not None and gee_canopy_3km > gee_canopy:
                        gee_canopy = gee_canopy_3km
                        tree_radius_used = 3000
        elif location_scope != 'neighborhood' and (gee_canopy is None or gee_canopy < 0.1) and area_type == 'urban_core':
            gee_canopy = get_tree_canopy_gee(lat, lon, radius_m=2000, area_type=area_type)
            if gee_canopy is not None and gee_canopy >= 0.1:
                tree_radius_used = 2000
                logger.debug("Larger radius (2km) found %.1f%% canopy", gee_canopy)

        if gee_canopy is not None and gee_canopy >= 0.1:
            canopy_score = _score_tree_canopy(gee_canopy)
            score = canopy_score
            canopy_points = canopy_score
            sources.append(f"GEE: {gee_canopy:.1f}% canopy")
            details['gee_canopy_pct'] = gee_canopy
            primary_canopy_pct = gee_canopy
            for label, rad in MULTI_RADIUS_CANOPY.items():
                value = None
                if tree_radius_used and rad == tree_radius_used:
                    value = gee_canopy
                elif rad == radius_m:
                    value = gee_canopy
                else:
                    try:
                        value = get_tree_canopy_gee(lat, lon, radius_m=rad, area_type=area_type)
                    except Exception as multi_error:
                        logger.debug("Optional canopy radius fetch (%s) failed: %s", label, multi_error)
                        value = None
                canopy_multi[label] = value

            if gee_canopy < 15.0 and area_type in ['urban_core', 'urban_residential']:
                logger.debug("Dense urban area with low GEE canopy (%.1f%%) - validating with Census/USFS...", gee_canopy)
                census_canopy = census_api.get_tree_canopy(lat, lon)
                if census_canopy is not None and census_canopy > gee_canopy:
                    census_score = _score_tree_canopy(census_canopy)
                    if census_score > score:
                        score = census_score
                        canopy_points = census_score
                        sources.append(f"USFS Census: {census_canopy:.1f}% canopy (validated GEE)")
                        details['census_canopy_pct'] = census_canopy
                        primary_canopy_pct = census_canopy
                elif census_canopy is not None:
                    logger.debug("Census/USFS canopy (%.1f%%) confirms GEE result", census_canopy)

            if nyc_api and city and ("New York" in city or "NYC" in city or "Brooklyn" in city):
                if gee_canopy < 15.0:
                    street_trees = nyc_api.get_street_trees(lat, lon, radius_deg=0.009)
                    if street_trees:
                        tree_count = len(street_trees)
                        street_tree_score = _score_nyc_trees(tree_count)
                        if street_tree_score > score:
                            score = street_tree_score
                            street_tree_points = street_tree_score
                            sources.append(f"NYC Street Trees: {tree_count} trees")
                            details['nyc_street_trees'] = tree_count
                        street_tree_feature_total += len(street_trees)
        else:
            logger.warning("GEE returned %s - trying Census fallback", gee_canopy)
        if tree_radius_used:
            gvi_radius = min(1200, tree_radius_used)
        else:
            gvi_radius = min(1200, radius_m)
        if gvi_radius and gvi_radius > 0:
            gvi_radius_used = gvi_radius
            try:
                gvi_metrics = get_urban_greenness_gee(lat, lon, radius_m=gvi_radius)
            except Exception as gvi_error:
                logger.warning("GEE greenness analysis error: %s", gvi_error)
                gvi_metrics = None
    except Exception as exc:
        logger.warning("GEE canopy lookup failed: %s", exc)

    # Priority 2: NYC Street Trees
    if score == 0.0 or (score < 30.0 and nyc_api and city and ("New York" in city or "NYC" in city or "Brooklyn" in city)):
        street_trees = nyc_api.get_street_trees(lat, lon, radius_deg=0.009) if nyc_api else None
        if street_trees:
            tree_count = len(street_trees)
            street_tree_score = _score_nyc_trees(tree_count)
            if street_tree_score > score:
                score = street_tree_score
                street_tree_points = street_tree_score
                sources.append(f"NYC Street Trees: {tree_count} trees")
                details['nyc_street_trees'] = tree_count
            street_tree_feature_total += tree_count

    # Priority 2b: Other cities street trees
    if (score == 0.0 or score < 40.0) and street_tree_api and city:
        city_key = street_tree_api.is_city_with_street_trees(city, lat, lon)
        if city_key:
            street_trees = street_tree_api.get_street_trees(city, lat, lon, radius_m=1000)
            if street_trees:
                tree_count = len(street_trees)
                street_tree_score = _score_nyc_trees(tree_count)
                if street_tree_score > score:
                    score = street_tree_score
                    street_tree_points = street_tree_score
                    sources.append(f"{city_key} Street Trees: {tree_count} trees")
                    details[f'{city_key.lower()}_street_trees'] = tree_count
                street_tree_feature_total += tree_count

    # Priority 3: Census USFS Tree Canopy
    try:
        from data_sources import census_api as _census_api
        if score == 0.0 or (score < 20.0 and area_type in ['urban_core', 'urban_residential']):
            canopy_pct = _census_api.get_tree_canopy(lat, lon)
            if canopy_pct is not None and canopy_pct > 0:
                canopy_score = _score_tree_canopy(canopy_pct)
                if canopy_score > score:
                    score = canopy_score
                    census_points = canopy_score
                    sources.append(f"USFS Census: {canopy_pct:.1f}% canopy")
                    details['census_canopy_pct'] = canopy_pct
                    if primary_canopy_pct is None or canopy_pct > primary_canopy_pct:
                        primary_canopy_pct = canopy_pct
    except Exception as exc:
        logger.warning("Census canopy lookup failed: %s", exc)

    # Priority 4: OSM parks fallback
    if score == 0.0:
        parks_radius = 800 if location_scope == 'neighborhood' else 500
        tree_data = osm_api.query_green_spaces(lat, lon, radius_m=parks_radius)
        if tree_data:
            parks = tree_data.get('parks', [])
            if parks:
                park_count = len(parks)
                park_score = min(30.0, park_count * 5.0)
                score = park_score
                osm_tree_points = max(osm_tree_points or 0.0, park_score)
                sources.append(f"OSM: {park_count} parks/green spaces")
                details['osm_parks'] = park_count
                street_tree_feature_total += park_count * 10
            else:
                sources.append("No tree data available")
        else:
            sources.append("No tree data available")

    base_tree_score = max(0.0, min(50.0, score))
    details['sources'] = sources
    details['component_scores'] = {
        "canopy_score": canopy_points,
        "street_tree_score": street_tree_points,
        "osm_tree_score": osm_tree_points,
        "census_score": census_points
    }

    natural_context_components: Dict[str, float] = {}
    natural_context_details: Dict[str, Dict] = {}
    context_bonus_total = 0.0

    try:
        from data_sources.gee_api import get_topography_context, get_landcover_context_gee
    except ImportError:  # pragma: no cover - optional dependency
        get_topography_context = None  # type: ignore
        get_landcover_context_gee = None  # type: ignore

    # Get area-type-specific context bonus weights
    area_type_key = (area_type or "").lower() or "unknown"
    context_weights = CONTEXT_BONUS_WEIGHTS.get(area_type_key, CONTEXT_BONUS_WEIGHTS["unknown"])
    
    topography_metrics = None
    if get_topography_context:
        try:
            topography_metrics = get_topography_context(lat, lon, radius_m=5000)
        except Exception as exc:
            logger.warning("Topography context lookup failed: %s", exc)
    if topography_metrics:
        topography_score_raw = _score_topography_component(topography_metrics)
        
        # Apply topography boost for arid regions if enabled
        topography_multiplier = 1.0
        if ENABLE_TOPOGRAPHY_BOOST_ARID and lat is not None and lon is not None:
            # Get climate adjustment to detect arid regions
            # Arid regions have multipliers < 0.9 (typically 0.65-0.85)
            try:
                elevation_m = topography_metrics.get("elevation_mean_m")
                climate_multiplier = _get_climate_adjustment(lat, lon, elevation_m)
                # Arid and semi-arid regions (multiplier < 0.9) get 1.3x boost to topography
                if climate_multiplier < 0.9:
                    topography_multiplier = 1.3
                    logger.debug("Applying arid topography boost (1.3x) for region with climate multiplier %.2f", climate_multiplier)
            except Exception:
                pass  # Fallback to 1.0 if climate detection fails
        
        # Apply area-type-specific weight, then arid boost
        topography_score = topography_score_raw * context_weights["topography"] * topography_multiplier
        natural_context_components["topography"] = round(topography_score, 2)
        natural_context_components["topography_raw"] = round(topography_score_raw, 2)
        natural_context_components["topography_multiplier"] = round(topography_multiplier, 2) if topography_multiplier != 1.0 else None
        natural_context_details["topography_metrics"] = topography_metrics
        context_bonus_total += topography_score

    landcover_metrics = None
    landcover_score = 0.0
    water_score = 0.0
    if get_landcover_context_gee:
        try:
            landcover_metrics = get_landcover_context_gee(lat, lon, radius_m=3000)
        except Exception as exc:
            logger.warning("Land cover context lookup failed: %s", exc)
    if landcover_metrics:
        natural_context_details["landcover_metrics"] = landcover_metrics
        natural_context_details["landcover_source"] = landcover_metrics.get("source")
        # Extract elevation from topography_metrics if available
        elevation_m_for_water = None
        if topography_metrics:
            elevation_m_for_water = topography_metrics.get("elevation_mean_m")
        
        landcover_score_raw, water_score_raw = _score_landcover_component(
            landcover_metrics, area_type, lat, lon, elevation_m_for_water, topography_metrics
        )
        # Apply area-type-specific weights
        landcover_score = landcover_score_raw * context_weights["landcover"]
        water_score = water_score_raw * context_weights["water"]
        natural_context_components["landcover"] = round(landcover_score, 2)
        natural_context_components["landcover_raw"] = round(landcover_score_raw, 2)
        natural_context_components["water"] = round(water_score, 2)
        natural_context_components["water_raw"] = round(water_score_raw, 2)
        context_bonus_total += landcover_score + water_score
        biodiversity_index = (
            BIODIVERSITY_WEIGHTS["forest"] * float(landcover_metrics.get("forest_pct", 0.0)) +
            BIODIVERSITY_WEIGHTS["wetland"] * float(landcover_metrics.get("wetland_pct", 0.0)) +
            BIODIVERSITY_WEIGHTS["shrub"] * float(landcover_metrics.get("shrub_pct", 0.0)) +
            BIODIVERSITY_WEIGHTS["grass"] * float(landcover_metrics.get("grass_pct", 0.0))
        )
        natural_context_details["biodiversity_index"] = round(min(100.0, biodiversity_index), 2)
        entropy_components = [
            float(landcover_metrics.get("forest_pct", 0.0)),
            float(landcover_metrics.get("wetland_pct", 0.0)),
            float(landcover_metrics.get("shrub_pct", 0.0)),
            float(landcover_metrics.get("grass_pct", 0.0))
        ]
        positive_components = [p for p in entropy_components if p > 0]
        if len(positive_components) > 1:
            total_pct = sum(positive_components)
            normalized = [p / total_pct for p in positive_components if total_pct > 0]
            if normalized:
                entropy_value = 0.0
                for val in normalized:
                    entropy_value -= val * math.log(val, 2)
                entropy_max = math.log(len(normalized), 2) if len(normalized) > 1 else 1.0
                if entropy_max > 0:
                    biodiversity_entropy = min(100.0, (entropy_value / entropy_max) * 100.0)
                    biodiversity_bonus = min(
                        BIODIVERSITY_BONUS_MAX,
                        (biodiversity_entropy / 100.0) * BIODIVERSITY_BONUS_MAX * CONTEXT_SCALERS.get(area_type_key, 1.0)
                    )
        natural_context_details["biodiversity_entropy"] = round(biodiversity_entropy, 2)
    else:
        natural_context_details["biodiversity_index"] = 0.0

    total_context_before_cap = context_bonus_total
    if context_bonus_total > NATURAL_CONTEXT_BONUS_CAP:
        context_bonus_total = NATURAL_CONTEXT_BONUS_CAP

    if natural_context_components:
        natural_context_details["component_scores"] = natural_context_components
        natural_context_details["total_bonus"] = round(context_bonus_total, 2)
        natural_context_details["total_before_cap"] = round(total_context_before_cap, 2)
        natural_context_details["cap"] = NATURAL_CONTEXT_BONUS_CAP
        natural_context_details["context_weights"] = context_weights  # Show area-type-specific weights
        details["natural_context"] = natural_context_details
    else:
        details["natural_context"] = {
            "component_scores": {},
            "total_bonus": 0.0,
            "total_before_cap": 0.0,
            "cap": NATURAL_CONTEXT_BONUS_CAP
        }
    normalized_multi = {}
    for label in MULTI_RADIUS_CANOPY.keys():
        val = canopy_multi.get(label)
        normalized_multi[label] = round(val, 2) if isinstance(val, (int, float)) else None
    details["multi_radius_canopy"] = normalized_multi
    if gvi_metrics:
        details["gvi_metrics"] = {
            "tree_canopy_pct": round(float(gvi_metrics.get("tree_canopy_pct") or 0.0), 2),
            "green_space_ratio": round(float(gvi_metrics.get("green_space_ratio") or 0.0), 2),
            "vegetation_health": round(float(gvi_metrics.get("vegetation_health") or 0.0), 3),
            "seasonal_variation": round(float(gvi_metrics.get("seasonal_variation") or 0.0), 3),
            "radius_m": gvi_radius_used
        }
    else:
        details["gvi_metrics"] = None
    details["biodiversity"] = {
        "entropy": round(biodiversity_entropy, 2),
        "bonus": round(biodiversity_bonus, 2),
        "index": natural_context_details.get("biodiversity_index")
    }

    area_type_key = (area_type or "").lower() or "unknown"
    # Extract elevation from topography_metrics if available (for climate adjustment)
    elevation_m = None
    if topography_metrics:
        elevation_m = topography_metrics.get("elevation_mean_m")
    
    # Use climate-first expectation architecture
    expectation = _get_adjusted_canopy_expectation(area_type_key, lat, lon, elevation_m)
    climate_zone = _get_climate_zone_name(lat, lon, elevation_m)
    climate_base = CLIMATE_BASE_EXPECTATIONS.get(climate_zone, CLIMATE_BASE_EXPECTATIONS["unknown"])
    if climate_zone == "semi_arid":
        climate_base = CLIMATE_BASE_EXPECTATIONS["arid"]
    area_adjustment = AREA_TYPE_ADJUSTMENTS.get(area_type_key, AREA_TYPE_ADJUSTMENTS["unknown"])
    
    # Legacy: Keep for backward compatibility
    legacy_base_expectation = CANOPY_EXPECTATIONS.get(area_type_key, CANOPY_EXPECTATIONS["unknown"])
    climate_multiplier = _get_climate_adjustment(lat, lon, elevation_m)
    
    if primary_canopy_pct is None:
        primary_canopy_pct = details.get("gee_canopy_pct") or details.get("census_canopy_pct") or 0.0
    canopy_expectation_ratio = None
    if expectation > 0:
        canopy_expectation_ratio = primary_canopy_pct / expectation
    details["canopy_expectation"] = {
        "climate_zone": climate_zone,
        "climate_base_pct": round(climate_base, 1),
        "area_type_adjustment": round(area_adjustment, 2),
        "final_expectation_pct": round(expectation, 1),
        # Legacy fields for backward compatibility
        "base_expected_pct": legacy_base_expectation,
        "climate_adjusted_pct": expectation,
        "climate_multiplier": round(climate_multiplier, 3),
        "observed_pct": round(primary_canopy_pct, 2),
        "ratio": round(canopy_expectation_ratio, 3) if canopy_expectation_ratio is not None else None
    }
    expectation_weight = CONTEXT_SCALERS.get(area_type_key, 1.0)
    if canopy_expectation_ratio is not None:
        if canopy_expectation_ratio >= 1.05:
            expectation_adjustment = min(
                CANOPY_EXPECTATION_BONUS_MAX,
                (canopy_expectation_ratio - 1.0) * 20.0 * expectation_weight
            )
        elif canopy_expectation_ratio <= 0.85:
            expectation_penalty = min(
                CANOPY_EXPECTATION_PENALTY_MAX,
                (0.85 - canopy_expectation_ratio) * 18.0 / max(expectation_weight, 0.65)
            )
    details["canopy_expectation"]["bonus"] = round(expectation_adjustment, 2)
    details["canopy_expectation"]["penalty"] = round(expectation_penalty, 2)
    details["expectation_effect"] = {
        "bonus": round(expectation_adjustment, 2),
        "penalty": round(expectation_penalty, 2),
        "net": round(expectation_adjustment - expectation_penalty, 2)
    }

    tree_radius_km = None
    if tree_radius_used:
        tree_radius_km = tree_radius_used / 1000.0
        details["tree_radius_m"] = tree_radius_used

    green_view_index = 0.0
    green_view_details: Dict[str, float] = {}
    gvi_weight = GREEN_VIEW_WEIGHTS.get(area_type_key, 1.0)

    if gvi_metrics:
        tree_canopy_vis = float(gvi_metrics.get("tree_canopy_pct") or 0.0)
        green_ratio = float(gvi_metrics.get("green_space_ratio") or 0.0)
        vegetation_health = float(gvi_metrics.get("vegetation_health") or 0.0) * 100.0
        seasonal_variation = float(gvi_metrics.get("seasonal_variation") or 0.0)
        gvi_raw = (
            tree_canopy_vis * 0.4 +
            green_ratio * 0.3 +
            vegetation_health * 0.2 +
            max(0.0, (1.0 - seasonal_variation)) * 10.0
        )
        green_view_index = min(100.0, max(0.0, gvi_raw))
        gvi_bonus = min(GVI_BONUS_MAX, (green_view_index / 100.0) * GVI_BONUS_MAX * gvi_weight)
        green_view_details = {
            "method": "gee_ndvi",
            "radius_m": gvi_radius_used,
            "components": {
                "tree_canopy_pct": round(tree_canopy_vis, 2),
                "green_space_ratio": round(green_ratio, 2),
                "vegetation_health_pct": round(vegetation_health, 2),
                "seasonal_variation": round(seasonal_variation, 3)
            },
            "weight": gvi_weight
        }
    else:
        canopy_component = (primary_canopy_pct or 0.0) * 0.6
        street_component = 0.0
        if street_tree_points:
            street_component += min(40.0, (street_tree_points / 50.0) * 40.0)
        if osm_tree_points:
            street_component += min(20.0, (osm_tree_points / 50.0) * 20.0)
        density_component = 0.0
        if tree_radius_km and street_tree_feature_total > 0:
            area_sq_km = math.pi * (tree_radius_km ** 2)
            density_component = min(20.0, (street_tree_feature_total / max(area_sq_km, 0.1)) * 0.5)
        green_view_index = min(100.0, max(0.0, canopy_component + street_component + density_component))
        gvi_bonus = min(GVI_BONUS_MAX, (green_view_index / 100.0) * GVI_BONUS_MAX * gvi_weight)
        green_view_details = {
            "method": "composite",
            "components": {
                "canopy_component": round(canopy_component, 2),
                "street_component": round(street_component, 2),
                "density_component": round(density_component, 2)
            },
            "weight": gvi_weight
        }

    details["green_view_index"] = round(green_view_index, 2)
    details["green_view_details"] = green_view_details
    details["street_tree_feature_total"] = street_tree_feature_total
    details["gvi_bonus"] = round(gvi_bonus, 2)
    # Calculate street tree bonus (only for low-canopy areas with street trees)
    street_tree_bonus = 0.0
    if primary_canopy_pct is not None and street_tree_feature_total > 0:
        street_tree_bonus = _calculate_street_tree_bonus(primary_canopy_pct, street_tree_feature_total, area_type)
    
    adjusted_score = base_tree_score + expectation_adjustment - expectation_penalty + gvi_bonus + biodiversity_bonus + street_tree_bonus
    score = max(0.0, min(50.0, adjusted_score))
    details["tree_base_score"] = round(base_tree_score, 2)
    details["adjusted_tree_score"] = round(adjusted_score, 2)
    details["bonus_breakdown"] = {
        "canopy_expectation_bonus": round(expectation_adjustment, 2),
        "canopy_expectation_penalty": round(-expectation_penalty, 2) if expectation_penalty else 0.0,
        "green_view_bonus": round(gvi_bonus, 2),
        "biodiversity_bonus": round(biodiversity_bonus, 2),
        "street_tree_bonus": round(street_tree_bonus, 2),
    }
    details["bonus_breakdown"]["net"] = round(
        expectation_adjustment - expectation_penalty + gvi_bonus + biodiversity_bonus + street_tree_bonus,
        2
    )

    details['context_bonus_applied'] = context_bonus_total
    details['total_score'] = score

    return score, details


def _validate_natural_beauty_score(score: float, details: Dict, 
                                    area_type: Optional[str],
                                    context_bonus_raw: float,
                                    component_scores: Dict) -> Dict:
    """
    Validate natural beauty score and detect anomalies.
    
    Returns:
        Dict with validation results including warnings and anomalies.
    """
    warnings = []
    anomalies = []
    
    # Check for extreme values
    if score > 95.0:
        warnings.append("Very high score (>95) - verify components are reasonable")
    if score < 5.0:
        warnings.append("Very low score (<5) - verify data quality and expectations")
    
    # Check component balance
    if context_bonus_raw > NATURAL_CONTEXT_BONUS_CAP * 1.1:
        warnings.append(f"Context bonus ({context_bonus_raw:.1f}) exceeds cap ({NATURAL_CONTEXT_BONUS_CAP}) - check calculation")
    
    # Component dominance guard (if enabled)
    if ENABLE_COMPONENT_DOMINANCE_GUARD and component_scores:
        max_component = max(component_scores.values()) if component_scores.values() else 0.0
        if context_bonus_raw > 0 and max_component / context_bonus_raw > MAX_COMPONENT_DOMINANCE_RATIO:
            dominant_component = max(component_scores.items(), key=lambda x: x[1])[0]
            anomalies.append({
                "type": "component_dominance",
                "component": dominant_component,
                "ratio": max_component / context_bonus_raw,
                "threshold": MAX_COMPONENT_DOMINANCE_RATIO
            })
    
    # Check for data quality issues
    tree_analysis = details.get("tree_analysis", {})
    if isinstance(tree_analysis, dict):
        canopy_pct = tree_analysis.get("gee_canopy_pct")
        if canopy_pct is not None and canopy_pct < 0:
            warnings.append("Negative canopy percentage detected - data quality issue")
    
    return {
        "valid": len(warnings) == 0 and len(anomalies) == 0,
        "warnings": warnings,
        "anomalies": anomalies,
        "score": score,
        "context_bonus": context_bonus_raw
    }


def _apply_component_dominance_guard(context_bonus_raw: float,
                                     component_scores: Dict) -> float:
    """
    Apply component dominance guard to prevent single component from exceeding threshold.
    
    If enabled, scales down dominant component if it exceeds MAX_COMPONENT_DOMINANCE_RATIO.
    """
    if not ENABLE_COMPONENT_DOMINANCE_GUARD or not component_scores:
        return context_bonus_raw
    
    max_component = max(component_scores.values()) if component_scores.values() else 0.0
    if context_bonus_raw > 0 and max_component / context_bonus_raw > MAX_COMPONENT_DOMINANCE_RATIO:
        # Scale down the dominant component
        scale_factor = (context_bonus_raw * MAX_COMPONENT_DOMINANCE_RATIO) / max_component
        # Apply gentle scaling (10% reduction) to prevent sudden jumps
        adjusted_bonus = context_bonus_raw * (1.0 - (1.0 - scale_factor) * 0.1)
        logger.warning(
            "Component dominance detected: max component %.1f (%.1f%% of total). "
            "Applying gentle scaling: %.1f -> %.1f",
            max_component,
            (max_component / context_bonus_raw) * 100,
            context_bonus_raw,
            adjusted_bonus
        )
        return adjusted_bonus
    
    return context_bonus_raw


def calculate_natural_beauty(lat: float,
                             lon: float,
                             city: Optional[str] = None,
                             area_type: Optional[str] = None,
                             location_scope: Optional[str] = None,
                             location_name: Optional[str] = None,
                             overrides: Optional[Dict[str, float]] = None,
                             enhancers_data: Optional[Dict] = None,
                             disable_enhancers: bool = False,
                             enhancer_radius_m: int = 1500,
                             precomputed_tree_canopy_5km: Optional[float] = None,
                             density: Optional[float] = None) -> Dict:
    """
    Compute natural beauty components prior to normalization.
    """
    tree_score, tree_details = _score_trees(
        lat,
        lon,
        city,
        location_scope=location_scope,
        area_type=area_type,
        location_name=location_name,
        overrides=overrides,
        density=density
    )

    context_info = tree_details.get("natural_context", {}) or {}
    tree_bonus_breakdown = tree_details.get("bonus_breakdown", {}) or {}
    context_bonus_raw = float(context_info.get("total_bonus") or 0.0)
    
    # Apply component dominance guard if enabled
    component_scores = context_info.get("component_scores", {}) or {}
    context_bonus_raw = _apply_component_dominance_guard(context_bonus_raw, component_scores)
    
    natural_bonus_raw = context_bonus_raw
    natural_bonus_scaled = min(NATURAL_ENHANCER_CAP, natural_bonus_raw)
    scenic_bonus_raw = 0.0
    scenic_meta = {
        "count": 0,
        "closest_distance_m": None,
        "weights_sum": 0.0,
        "top_viewpoints": []
    }

    if not disable_enhancers:
        if enhancers_data is None:
            enhancers_data = osm_api.query_beauty_enhancers(lat, lon, radius_m=enhancer_radius_m)
        # Pass context bonus and landcover metrics for deduplication
        landcover_metrics_for_dedup = tree_details.get("natural_context", {}).get("landcover_metrics")
        scenic_bonus_raw, scenic_meta = _compute_viewshed_proxy(
            enhancers_data.get("viewpoints_details", []),
            radius_m=enhancer_radius_m,
            natural_context_bonus=context_bonus_raw,
            landcover_metrics=landcover_metrics_for_dedup
        )
        natural_bonus_raw = scenic_bonus_raw + context_bonus_raw
        natural_bonus_scaled = min(NATURAL_ENHANCER_CAP, natural_bonus_raw)
    else:
        enhancers_data = enhancers_data or {"viewpoints_details": []}

    tree_details.setdefault("scenic_proxy", scenic_meta)
    tree_details.setdefault("enhancer_bonus", {})
    tree_details["enhancer_bonus"].update({
        "natural_raw": round(natural_bonus_raw, 2),
        "scenic_raw": round(scenic_bonus_raw, 2),
        "context_raw": round(context_bonus_raw, 2),
        "natural_scaled": round(natural_bonus_scaled, 2),
        "scaled_total": round(natural_bonus_scaled, 2)
    })
    tree_details["enhancer_breakdown"] = {
        "scenic_raw": round(scenic_bonus_raw, 2),
        "context_raw": round(context_bonus_raw, 2),
        "raw_total": round(natural_bonus_raw, 2),
        "scaled_total": round(natural_bonus_scaled, 2),
        "cap": NATURAL_ENHANCER_CAP,
        "components": context_info.get("component_scores", {})
    }

    natural_native = max(0.0, tree_score + natural_bonus_scaled)
    natural_score_raw = min(100.0, natural_native * 2.0)

    natural_score_norm, natural_norm_meta = normalize_beauty_score(
        natural_score_raw,
        area_type
    )
    
    # Validate score and detect anomalies
    validation_result = _validate_natural_beauty_score(
        natural_score_norm,
        tree_details,
        area_type,
        context_bonus_raw,
        component_scores
    )
    
    # Log warnings if validation detected issues
    if validation_result["warnings"]:
        for warning in validation_result["warnings"]:
            logger.warning("Natural beauty validation: %s", warning)
    
    if validation_result["anomalies"]:
        for anomaly in validation_result["anomalies"]:
            logger.warning("Natural beauty anomaly: %s", anomaly)

    return {
        "tree_score_0_50": tree_score,
        "details": tree_details,
        "enhancers": enhancers_data,
        "natural_bonus_raw": natural_bonus_raw,
        "natural_bonus_scaled": natural_bonus_scaled,
        "scenic_bonus_raw": scenic_bonus_raw,
        "context_bonus_raw": context_bonus_raw,
        "score_before_normalization": natural_score_raw,
        "scenic_metadata": scenic_meta,
        "score": natural_score_norm,
        "normalization": natural_norm_meta,
        "validation": validation_result,  # Include validation results in response
    }


def get_natural_beauty_score(lat: float,
                             lon: float,
                             city: Optional[str] = None,
                             area_type: Optional[str] = None,
                             location_scope: Optional[str] = None,
                             location_name: Optional[str] = None,
                             overrides: Optional[Dict[str, float]] = None,
                             enhancers_data: Optional[Dict] = None,
                             disable_enhancers: bool = False) -> Tuple[float, Dict]:
    """
    Public entry point for the natural beauty pillar.
    """
    result = calculate_natural_beauty(
        lat,
        lon,
        city=city,
        area_type=area_type,
        location_scope=location_scope,
        location_name=location_name,
        overrides=overrides,
        enhancers_data=enhancers_data,
        disable_enhancers=disable_enhancers
    )

    natural_score_raw = result["score_before_normalization"]
    tree_details = result["details"]

    natural_area_type = area_type
    if isinstance(tree_details, dict):
        natural_area_type = tree_details.get("classification", {}).get("effective_area_type", area_type)  # type: ignore

    natural_score_norm, natural_norm_meta = normalize_beauty_score(
        natural_score_raw,
        natural_area_type
    )

    details = {
        "tree_score_0_50": round(result["tree_score_0_50"], 2),
        "enhancer_bonus_raw": round(result["natural_bonus_raw"], 2),
        "enhancer_bonus_scaled": round(result["natural_bonus_scaled"], 2),
        "context_bonus_raw": round(result["context_bonus_raw"], 2),
        "score_before_normalization": round(natural_score_raw, 2),
        "normalization": natural_norm_meta,
        "tree_analysis": tree_details,
        "scenic_proxy": result["scenic_metadata"],
        "enhancer_bonus": {
            "natural_raw": round(result["natural_bonus_raw"], 2),
            "natural_scaled": round(result["natural_bonus_scaled"], 2),
            "scaled_total": round(result["natural_bonus_scaled"], 2)
        },
        "context_bonus": tree_details.get("natural_context") if isinstance(tree_details, dict) else {},
        "bonus_breakdown": tree_details.get("bonus_breakdown", {}),
        "green_view_index": tree_details.get("green_view_index"),
        "multi_radius_canopy": tree_details.get("multi_radius_canopy"),
        "gvi_metrics": tree_details.get("gvi_metrics"),
        "expectation_effect": tree_details.get("expectation_effect"),
    }

    return natural_score_norm, details

