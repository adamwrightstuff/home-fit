"""
Data Quality Detection and Fallback System
Provides tiered fallback mechanisms and data completeness scoring
"""

import json
import math
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from .census_api import get_population_density, get_census_tract
from logging_config import get_logger

logger = get_logger(__name__)

# REMOVED: TARGET_AREA_TYPES hardcoded overrides violate design principles
# Hardcoded location-to-area-type mappings are not scalable and create maintenance burden.
# If specific locations need different classifications, the classification logic itself
# should be improved, not bypassed with exceptions.
# 
# Previous overrides were used for calibration/testing but should not be in production.
TARGET_AREA_TYPES: Dict[str, str] = {}

AREA_TYPE_DIAGNOSTICS_PATH = Path("analysis/area_type_diagnostics.jsonl")

# Allowed baseline contexts for expectation table lookups
# These are the valid keys for get_contextual_expectations()
ALLOWED_BASELINE_CONTEXTS = {
    'urban_core',
    'urban_residential',
    'suburban',
    'commuter_rail_suburb',  # Transit-only context
    'exurban',
    'rural'
}


# ============================================================================
# NEW MORPHOLOGICAL CLASSIFICATION SYSTEM
# Replaces hard thresholds with continuous scoring and separates classification
# from aesthetic scoring via contextual tags.
# ============================================================================

def _continuous_density_score(density: Optional[float]) -> float:
    """
    Convert density to continuous 0.0-1.0 score.
    Uses smooth transitions instead of hard thresholds.
    """
    if density is None:
        return 0.0
    
    # Smooth sigmoid-like transitions
    if density >= 20000:
        return 1.0
    elif density >= 12000:
        # 12000-20000: linear interpolation
        return 0.7 + (density - 12000) / 8000 * 0.3
    elif density >= 8000:
        # 8000-12000: linear interpolation
        return 0.5 + (density - 8000) / 4000 * 0.2
    elif density >= 5000:
        # 5000-8000: linear interpolation
        return 0.3 + (density - 5000) / 3000 * 0.2
    elif density >= 2500:
        # 2500-5000: linear interpolation
        return 0.15 + (density - 2500) / 2500 * 0.15
    elif density >= 1000:
        # 1000-2500: linear interpolation
        return 0.05 + (density - 1000) / 1500 * 0.1
    elif density >= 450:
        # 450-1000: linear interpolation
        return 0.0 + (density - 450) / 550 * 0.05
    else:
        return 0.0


def _continuous_coverage_score(coverage: Optional[float]) -> float:
    """
    Convert coverage to continuous 0.0-1.0 score.
    Uses bands instead of hard 0.18 threshold.
    """
    if coverage is None:
        return 0.0
    
    # Smooth transitions around critical bands
    if coverage >= 0.30:
        return 1.0
    elif coverage >= 0.22:
        # 0.22-0.30: high coverage band
        return 0.8 + (coverage - 0.22) / 0.08 * 0.2
    elif coverage >= 0.18:
        # 0.18-0.22: transition zone (was hard cutoff)
        return 0.6 + (coverage - 0.18) / 0.04 * 0.2
    elif coverage >= 0.15:
        # 0.15-0.18: low-moderate coverage
        return 0.4 + (coverage - 0.15) / 0.03 * 0.2
    elif coverage >= 0.12:
        # 0.12-0.15: moderate-low coverage
        return 0.2 + (coverage - 0.12) / 0.03 * 0.2
    elif coverage >= 0.08:
        # 0.08-0.12: low coverage
        return 0.1 + (coverage - 0.08) / 0.04 * 0.1
    elif coverage >= 0.05:
        # 0.05-0.08: very low coverage
        return 0.0 + (coverage - 0.05) / 0.03 * 0.1
    else:
        return 0.0


def _continuous_business_score(business_count: Optional[int]) -> float:
    """
    Convert business count to continuous 0.0-1.0 score.
    Replaces hard 75/150 thresholds.
    """
    if business_count is None:
        return 0.0
    
    if business_count >= 180:
        return 1.0
    elif business_count >= 150:
        # 150-180: linear interpolation
        return 0.85 + (business_count - 150) / 30 * 0.15
    elif business_count >= 120:
        # 120-150: linear interpolation
        return 0.70 + (business_count - 120) / 30 * 0.15
    elif business_count >= 90:
        # 90-120: linear interpolation
        return 0.55 + (business_count - 90) / 30 * 0.15
    elif business_count >= 75:
        # 75-90: transition zone (was hard cutoff)
        return 0.40 + (business_count - 75) / 15 * 0.15
    elif business_count >= 50:
        # 50-75: moderate business
        return 0.25 + (business_count - 50) / 25 * 0.15
    elif business_count >= 25:
        # 25-50: low-moderate business
        return 0.10 + (business_count - 25) / 25 * 0.15
    elif business_count > 0:
        # 1-25: low business
        return business_count / 25 * 0.10
    else:
        return 0.0


def _continuous_metro_distance_score(metro_distance_km: Optional[float]) -> float:
    """
    Convert metro distance to continuous 0.0-1.0 score.
    Closer = higher score. Replaces hard 10/20/30km bands.
    """
    if metro_distance_km is None:
        return 0.5  # Neutral if unknown
    
    # Closer is better (higher score)
    if metro_distance_km <= 5.0:
        return 1.0
    elif metro_distance_km <= 10.0:
        # 5-10km: very close
        return 0.9 - (metro_distance_km - 5.0) / 5.0 * 0.1
    elif metro_distance_km <= 15.0:
        # 10-15km: close
        return 0.8 - (metro_distance_km - 10.0) / 5.0 * 0.1
    elif metro_distance_km <= 20.0:
        # 15-20km: moderate distance
        return 0.7 - (metro_distance_km - 15.0) / 5.0 * 0.1
    elif metro_distance_km <= 30.0:
        # 20-30km: far
        return 0.5 - (metro_distance_km - 20.0) / 10.0 * 0.2
    elif metro_distance_km <= 50.0:
        # 30-50km: very far
        return 0.3 - (metro_distance_km - 30.0) / 20.0 * 0.2
    else:
        return 0.1  # Extremely far


def _calculate_intensity_score(
    density: Optional[float],
    coverage: Optional[float],
    business_count: Optional[int]
) -> float:
    """
    Calculate overall intensity/urbanity score (0.0-1.0).
    Combines density, coverage, and business count with weighted average.
    
    Special handling for high-density, low-coverage cases (e.g., Sea Cliff, Bungalow Heaven):
    When density is very high (>7k), give it more weight to avoid misclassifying
    dense urban neighborhoods as suburban.
    """
    density_score = _continuous_density_score(density)
    coverage_score = _continuous_coverage_score(coverage)
    business_score = _continuous_business_score(business_count)

    # Treat missing coverage/business as unknown (not zero) — redistribute their weight
    # to density so batch scoring without OSM coverage data doesn't misclassify dense
    # urban neighborhoods (e.g. Los Feliz, Silver Lake) as suburban.
    have_coverage = coverage is not None
    have_business = business_count is not None

    # Adjust weights based on density level
    # High density (>7k) = more weight to density (handles low-coverage urban neighborhoods)
    # Moderate density = balanced weights
    # Low density = more weight to coverage/business (handles sparse areas)
    if density and density > 7000:
        # High density: density 60%, coverage 25%, business 15% — but redistribute missing
        w_d = 0.60 + (0 if have_coverage else 0.25) + (0 if have_business else 0.15)
        w_c = 0.25 if have_coverage else 0
        w_b = 0.15 if have_business else 0
        intensity = density_score * w_d + coverage_score * w_c + business_score * w_b
    elif density and density > 3000:
        # Moderate density: balanced weights
        w_d = 0.50 + (0 if have_coverage else 0.30) + (0 if have_business else 0.20)
        w_c = 0.30 if have_coverage else 0
        w_b = 0.20 if have_business else 0
        intensity = density_score * w_d + coverage_score * w_c + business_score * w_b
    else:
        # Low density: coverage and business more important
        w_d = 0.40 + (0 if have_coverage else 0.40) + (0 if have_business else 0.20)
        w_c = 0.40 if have_coverage else 0
        w_b = 0.20 if have_business else 0
        intensity = density_score * w_d + coverage_score * w_c + business_score * w_b
    
    return min(1.0, max(0.0, intensity))


def _calculate_context_score(
    metro_distance_km: Optional[float],
    city: Optional[str] = None
) -> float:
    """
    Calculate contextual/metro proximity score (0.0-1.0).
    Higher score = more urban context.
    """
    distance_score = _continuous_metro_distance_score(metro_distance_km)
    
    # Boost if in major metro (even if distance unknown)
    metro_boost = 0.0
    if city:
        try:
            from .regional_baselines import RegionalBaselineManager
            baseline_mgr = RegionalBaselineManager()
            city_lower = city.lower().strip()
            for metro_name in baseline_mgr.major_metros.keys():
                if metro_name.lower() == city_lower:
                    metro_boost = 0.2
                    break
        except Exception:
            pass
    
    return min(1.0, distance_score + metro_boost)


def classify_morphology(
    density: Optional[float],
    coverage: Optional[float],
    business_count: Optional[int],
    metro_distance_km: Optional[float],
    city: Optional[str] = None,
    location_input: Optional[str] = None
) -> str:
    """
    Morphological classification from residential population density and the
    business count within 1 km. 'urban_core' is no longer returned: its
    definition is subjective and differs by city, and no published cutoff
    exists (decision 2026-10-27, analysis/area_type_activity_density_proposal_2026-10-27.md).
    Places the old commercial-dominance rule called urban_core are
    urban_residential. business_count must be businesses within 1km
    (matches the live business_count signal and the catalog's
    businesses_within_walkable) — NOT a profile/area-type-dependent radius,
    which would make this circular.

    Args:
        density: Population density (people/sq mi)
        coverage: unused (kept for call-site compatibility)
        business_count: Number of businesses within 1km
        metro_distance_km: unused (kept for call-site compatibility)
        city: unused (kept for call-site compatibility)
        location_input: unused (kept for call-site compatibility)

    Returns:
        'urban_residential', 'suburban', 'exurban', 'rural',
        or 'unknown' when density is missing/zero or looks unreliable
        (e.g. a census tract with near-zero population but heavy commercial
        activity nearby — a "dead tract" point-sample artifact). Returning
        'unknown' rather than guessing is intentional: every pillar already
        has a safe default for an unrecognized area_type.
    """
    if density is None or density <= 0:
        return "unknown"

    walk = business_count or 0

    # Dead-tract guard: near-zero density but real commercial activity means
    # the density point-sample landed on an unrepresentative tract (park,
    # rail yard, low-population edge tract), not that the place is rural.
    if density < 2000 and walk >= 80:
        return "unknown"

    if density >= 25000:
        return "urban_residential"
    if density >= 12000 and walk >= 100:
        return "urban_residential"
    if walk >= 150:
        return "urban_residential"
    if density >= 3000:
        return "suburban"
    if density >= 800:
        return "exurban"
    return "rural"


def get_contextual_tags(
    base_area_type: str,
    density: Optional[float],
    coverage: Optional[float],
    median_year_built: Optional[int],
    historic_landmarks: Optional[int],
    business_count: Optional[int] = None,
    levels_entropy: Optional[float] = None,
    building_type_diversity: Optional[float] = None,
    footprint_area_cv: Optional[float] = None,
    pre_1940_pct: Optional[float] = None,
    nrhp_count: int = 0
) -> List[str]:
    """
    Determine contextual tags for a location.
    
    Tags are orthogonal attributes that adjust scoring, not separate classes.
    This separates "what it is" (morphology) from "how good it is" (aesthetic scoring).
    
    Args:
        base_area_type: Base morphological classification
        density: Population density
        coverage: Building coverage ratio
        median_year_built: Median year buildings were built
        historic_landmarks: Count of historic landmarks from OSM
        levels_entropy: Optional height diversity metric
        building_type_diversity: Optional type diversity metric
        footprint_area_cv: Optional footprint coefficient of variation
    
    Returns:
        List of tags: ['historic', 'coastal', 'lowrise', 'rowhouse', 'uniform', 'mixed_use', 'planned']
    """
    tags = []
    
    # Historic tag
    is_historic = False
    # Primary signal: Census median year < 1950 (definitely historic)
    if median_year_built is not None and median_year_built < 1950:
        is_historic = True
    # Secondary signal: Landmark count (only if median year is historic OR unknown)
    # This handles historic neighborhoods with modern infill (Georgetown, Back Bay)
    # But prevents modern areas (Downtown Austin 2007, SLU 1970) from being misclassified
    if historic_landmarks and historic_landmarks >= 10:
        # Use pre_1940_pct to distinguish historic neighborhoods with infill from modern areas:
        # - Historic neighborhoods with infill: Have pre-1940 buildings (historic core) → pre_1940_pct >= 5%
        # - Modern areas built in 1970s: No pre-1940 buildings → pre_1940_pct < 5%
        has_historic_core = pre_1940_pct is not None and pre_1940_pct >= 5.0
        
        if median_year_built is None:
            # Unknown median year: Use landmark count as fallback (preserves backward compatibility)
            is_historic = True
        elif median_year_built < 1950:
            # Definitely historic: Already handled above, but landmark count confirms it
            is_historic = True
        elif median_year_built < 1980:
            # Median year 1950-1979: Need to check if historic core exists
            # If pre_1940_pct >= 5%, it's a historic neighborhood with infill → allow historic tag
            # If pre_1940_pct < 5% or None, it's a modern area → do NOT allow historic tag
            if has_historic_core:
                is_historic = True
            # If pre_1940_pct is None and median_year < 1980, be conservative: don't use landmark count
            # This prevents modern areas (like South Lake Union 1970) from being misclassified
        # If median_year_built >= 1980: Do NOT use landmark count (modern areas)

    # NRHP fallback: high NRHP count + any pre-1940 stock overrides unreliable Census myr.
    # Handles inner-city neighborhoods where new construction skews Census myr upward
    # (e.g. Fort Greene: NRHP=14, Census myr=2010 due to condo development).
    if not is_historic and nrhp_count >= 10 and pre_1940_pct is not None and pre_1940_pct >= 1.0:
        is_historic = True

    if is_historic:
        tags.append('historic')
    
    # Lowrise tag: dense but low height diversity
    # Applies to urban areas with low height variation (intentional low-rise design)
    if base_area_type in ('urban_core', 'urban_residential'):
        if levels_entropy is not None and levels_entropy < 20:
            # Low coverage suggests intentional spacing (Sea Cliff, Bungalow Heaven pattern)
            if coverage and coverage < 0.25:
                tags.append('lowrise')
            # Or if density is high but coverage moderate (dense low-rise)
            elif density and density > 7000 and coverage and coverage < 0.28:
                tags.append('lowrise')
    
    # Rowhouse tag: uniform architecture with consistent footprints
    # Applies to cohesive rowhouse/brownstone districts (Park Slope pattern)
    if base_area_type in ('urban_residential', 'urban_core'):
        if (levels_entropy is not None and levels_entropy < 20 and
            building_type_diversity is not None and building_type_diversity < 35):
            # Check for consistent footprint pattern (low CV = uniform sizes)
            if footprint_area_cv is not None and footprint_area_cv < 50:
                tags.append('rowhouse')
            # Also tag if very uniform (very low diversity) even without footprint data
            elif (levels_entropy is not None and levels_entropy < 15 and
                  building_type_diversity is not None and building_type_diversity < 25):
                tags.append('rowhouse')
    
    # Uniform tag: very low diversity (distinct from rowhouse)
    if (levels_entropy is not None and levels_entropy < 15 and
        building_type_diversity is not None and building_type_diversity < 25):
        if 'rowhouse' not in tags:  # Don't double-tag
            tags.append('uniform')
    
    # Mixed-use tag: high business count relative to density
    if business_count and density:
        business_density_ratio = business_count / max(density / 1000, 1)  # businesses per 1k people
        if business_density_ratio > 15:  # High commercial mix
            tags.append('mixed_use')
    
    # Note: 'coastal' and 'planned' tags would require additional data sources
    # (coastline proximity, master-planned community detection)
    # Leaving these for future implementation
    
    return tags


def get_natural_landscape_tags(
    base_area_type: str,
    lat: float,
    lon: float,
    topography_metrics: Optional[Dict],
    landcover_metrics: Optional[Dict],
    water_proximity_data: Optional[Dict],
    elevation_m: Optional[float],
    climate_multiplier: Optional[float],
    canopy_pct: Optional[float],
    park_data: Optional[Dict] = None
) -> List[str]:
    """
    Determine natural landscape context tags for a location.
    
    Tags are orthogonal attributes that adjust Natural Beauty scoring,
    complementing the morphological area_type classification.
    This separates "what it is" (morphology) from "landscape context" (natural setting).
    
    Tag detection is fully algorithmic based on objective metrics - no hardcoded locations.
    
    Args:
        base_area_type: Base morphological classification (urban_core, suburban, rural, etc.)
        lat: Latitude
        lon: Longitude
        topography_metrics: Dict with relief_range_m, elevation_mean_m, ruggedness_index_m
        landcover_metrics: Dict with forest_pct, water_pct, developed_pct
        water_proximity_data: Dict with nearest_distance_km, nearest_waterbody (type, area_km2)
        elevation_m: Mean elevation in meters
        climate_multiplier: Climate adjustment multiplier (from _get_climate_adjustment)
        canopy_pct: Tree canopy percentage (primary radius)
        park_data: Optional dict with park_count, park_area_ha, local_green_score (for urban_park detection)
    
    Returns:
        List of landscape tags: ['coastal', 'mountain', 'desert', 'plains', 'forest', 'urban_park']
    """
    tags = []
    
    # Extract metrics with safe defaults
    relief_m = float(topography_metrics.get("relief_range_m", 0) or 0) if topography_metrics else 0.0
    elevation_mean_m = float(topography_metrics.get("elevation_mean_m", elevation_m or 0) or 0) if topography_metrics else (float(elevation_m) if elevation_m else 0.0)
    ruggedness_m = float(topography_metrics.get("ruggedness_index_m", 0) or 0) if topography_metrics else 0.0
    
    forest_pct = float(landcover_metrics.get("forest_pct", 0) or 0) if landcover_metrics else 0.0
    water_pct = float(landcover_metrics.get("water_pct", 0) or 0) if landcover_metrics else 0.0
    wetland_pct = float(landcover_metrics.get("wetland_pct", 0) or 0) if landcover_metrics else 0.0
    
    nearest_water_km = None
    water_proximity_type = None
    lake_area_km2 = None
    if water_proximity_data:
        nearest_water_km = water_proximity_data.get("nearest_distance_km")
        nearest_waterbody = water_proximity_data.get("nearest_waterbody", {})
        if isinstance(nearest_waterbody, dict):
            water_proximity_type = nearest_waterbody.get("type")
            lake_area_km2 = nearest_waterbody.get("area_km2")
    
    canopy_pct_val = float(canopy_pct) if canopy_pct is not None else 0.0
    climate_mult = float(climate_multiplier) if climate_multiplier is not None else 1.0
    
    # COASTAL: Open water / harbor proximity (<5km), very large lakes, or coastal-edge inference from landcover+relief.
    is_coastal = False
    if nearest_water_km is not None:
        if water_proximity_type in ("ocean", "bay") and nearest_water_km < 5.0:
            is_coastal = True
        elif water_proximity_type == "lake" and nearest_water_km < 10.0:
            # Very large lakes (Great Lakes scale) are coastal-like features
            # Use area_km2 if available, fallback to water_density as proxy when OSM area tag missing
            # water_density > 100 km² within 15km radius suggests very large lake (>500km² total)
            water_density = water_proximity_data.get("water_density", 0) if water_proximity_data else 0
            area_available = lake_area_km2 is not None and lake_area_km2 > 500.0
            density_indicates_large = water_density > 100.0  # High density within 15km suggests large lake
            if area_available or density_indicates_large:
                is_coastal = True
    # Parallel coastal inference independent of proximity object availability.
    # This catches shoreline edge cells where OSM proximity may fail but landcover is clearly coastal.
    if not is_coastal:
        if water_pct > 18.0 and (water_pct + wetland_pct) > 20.0 and relief_m < 120.0:
            is_coastal = True
    if is_coastal:
        tags.append('coastal')
    
    # MOUNTAIN: High relief (>300m) OR high elevation (>1000m) OR high ruggedness (>75m)
    # Priority check: mountains override plains
    is_mountain = False
    if relief_m > 300.0 or elevation_mean_m > 1000.0 or ruggedness_m > 75.0:
        is_mountain = True
    
    if is_mountain:
        tags.append('mountain')
    
    # FOREST: High canopy (>50%) OR high forest landcover (>60%)
    # Can coexist with mountain (mountain forests)
    if canopy_pct_val > 50.0 or forest_pct > 60.0:
        tags.append('forest')
    
    # DESERT: Arid climate (multiplier <0.7) AND low canopy (<15%) AND low relief (<200m)
    # Only tag if NOT mountain (mountains can be arid but aren't desert landscapes)
    if not is_mountain:
        if climate_mult < 0.7 and canopy_pct_val < 15.0 and relief_m < 200.0:
            tags.append('desert')
    
    # PLAINS: Low relief (<100m) AND low forest (<30%) AND low elevation (<500m)
    # Only tag if NOT mountain, NOT desert, and NOT coastal (avoid conflicting landscape labels).
    if not is_mountain and 'desert' not in tags and not is_coastal:
        if relief_m < 100.0 and forest_pct < 30.0 and elevation_mean_m < 500.0:
            tags.append('plains')
    
    # URBAN_PARK: Urban area with high park density
    # Detected using park_data from _score_local_green_spaces (park count, area, score)
    if park_data and base_area_type in ("urban_core", "urban_core_lowrise", "historic_urban", "urban_residential", "suburban"):
        park_count = park_data.get("park_count", 0)
        park_area_ha = park_data.get("park_area_ha", 0)
        local_green_score = park_data.get("local_green_score", 0)
        
        # Tag as urban_park if:
        # - 3+ parks within 400m OR
        # - Park area >2ha within 400m OR
        # - High local green score (>5.0)
        if park_count >= 3 or park_area_ha >= 2.0 or local_green_score >= 5.0:
            tags.append('urban_park')
    
    return tags


def _normalize_location_key(location: Optional[str]) -> Optional[str]:
    if not location:
        return None
    return " ".join(location.lower().split())


def _write_area_type_diagnostic(record: Dict[str, Any]) -> None:
    try:
        AREA_TYPE_DIAGNOSTICS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with AREA_TYPE_DIAGNOSTICS_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
    except Exception:
        # Logging failure should never break classification
        pass


def detect_area_type(lat: float, lon: float, density: Optional[float] = None,
                     city: Optional[str] = None, location_input: Optional[str] = None,
                     business_count: Optional[int] = None,
                     built_coverage: Optional[float] = None,
                     metro_distance_km: Optional[float] = None,
                     census_tract: Optional[Dict] = None) -> str:
    """
    Detect area type from the surrounding 1 km circle (see data_sources/surrounding_density.py):
    people per square mile over the tracts in the circle, and people plus jobs per gross acre.
    Measured from local tables, so the result does not depend on a Census call or on OSM completeness.

    Args:
        lat, lon: Coordinates (the inputs that matter)
        census_tract: the pin's own tract (state_fips, county_fips, tract_fips), used only when no tract
            center lies inside the circle, so a large rural tract is read as itself
        density, city, location_input, business_count, built_coverage, metro_distance_km:
            unused, kept for call-site compatibility. The tract density at the pin and the OSM
            business count no longer decide the type (proposal 2026-10-27, Option A).

    Returns:
        'urban_residential', 'suburban', 'exurban', 'rural', or 'unknown' when no tract is near enough
    """
    normalized_location = _normalize_location_key(location_input)
    
    # REMOVED: TARGET_AREA_TYPES override check - hardcoded location overrides violate design principles
    # If specific locations need different classifications, improve the classification logic itself
    
    diagnostic_record: Optional[Dict[str, Any]] = None
    if normalized_location or built_coverage is not None:
        diagnostic_record = {
            "location": normalized_location or "(unknown)",
            "density": density,
            "city": city,
            "business_count": business_count,
            "built_coverage": built_coverage,
            "metro_distance_km": metro_distance_km,
            "input": location_input
        }

    def _finalize(result: str) -> str:
        if diagnostic_record is not None:
            diagnostic_record["predicted_area_type"] = result
            _write_area_type_diagnostic(diagnostic_record)
        return result

    from .surrounding_density import surrounding_stats, classify_surrounding
    geoid = None
    if census_tract and all(census_tract.get(k) for k in ("state_fips", "county_fips", "tract_fips")):
        geoid = f"{census_tract['state_fips']}{census_tract['county_fips']}{census_tract['tract_fips']}"
    stats = surrounding_stats(lat, lon, tract_geoid=geoid)
    from .principal_city import principal_city_at
    in_pc = principal_city_at(lat, lon, (census_tract or {}).get("state_fips"))
    base_type = classify_surrounding(stats, in_pc)
    if diagnostic_record is not None and stats is not None:
        diagnostic_record.update({
            "surrounding_people_density": round(stats.people_density, 1),
            "activity_per_acre": round(stats.activity_per_acre, 2),
            "density_method": stats.density_method,
            "jobs_known": stats.jobs_known,
            "in_principal_city": in_pc,
        })
    return _finalize(base_type)








def get_baseline_context(
    area_type: str,
    pillar_name: str,
    **pillar_specific_data
) -> str:
    """
    Get the pillar's baseline context key for expectation table lookup.

    The shared area type is the context for every pillar, except that a suburban place with heavy rail is
    a commuter_rail_suburb for transit (the pillar checks the distance conditions before calling this).
    Falls back to 'suburban' when the area type is not in ALLOWED_BASELINE_CONTEXTS.
    """
    if (
        pillar_name == 'public_transit_access'
        and area_type == 'suburban'
        and pillar_specific_data.get('has_heavy_rail')
    ):
        return 'commuter_rail_suburb'
    return area_type if area_type in ALLOWED_BASELINE_CONTEXTS else 'suburban'


def detect_location_scope(lat: float, lon: float, geocode_result: Optional[Dict] = None) -> str:
    """
    Detect if location is a neighborhood within a larger city vs. standalone city.
    
    Uses Nominatim address structure + density - NO hardcoded city lists.
    
    Args:
        lat, lon: Coordinates
        geocode_result: Optional full Nominatim geocoding result (for efficiency)
    
    Returns:
        'neighborhood' or 'city' (American spelling)
    """
    # Method 1: Check Nominatim address structure (most reliable)
    if geocode_result and 'address' in geocode_result:
        address = geocode_result.get('address', {})
        
        # Nominatim uses British spelling "neighbourhood" in responses, but we check both
        if address.get('neighbourhood') or address.get('neighborhood') or address.get('suburb'):
            # Double-check: if there's also a city field above it, definitely a neighborhood
            if address.get('city') or address.get('town'):
                return "neighborhood"  # American spelling for our code
    
    # Method 2: Very high density (>30k) suggests neighborhood in major city
    density = get_population_density(lat, lon)
    if density and density > 30000:
        return "neighborhood"
    
    # Method 3: Check Census tract - neighborhoods often have smaller tracts
    tract = get_census_tract(lat, lon)
    if tract:
        props = tract.get('properties', {})
        tract_area_sqm = props.get('ALAND', 0)  # Area in sq meters
        if tract_area_sqm > 0:
            tract_area_sqkm = tract_area_sqm / 1_000_000
            # Very small tracts (<2 sq km) with high density = likely neighborhood
            if tract_area_sqkm < 2 and density and density > 15000:
                return "neighborhood"
    
    # Default: assume standalone city
    return "city"


class DataQualityManager:
    """Manages data quality assessment."""
    
    def __init__(self):
        self.quality_thresholds = {
            'excellent': 0.9,    # 90%+ data completeness
            'good': 0.7,         # 70-89% data completeness  
            'fair': 0.5,         # 50-69% data completeness
            'poor': 0.3,         # 30-49% data completeness
            'very_poor': 0.0     # <30% data completeness
        }
    
    def assess_data_completeness(self, pillar_name: str, data: Dict, 
                               expected_minimums: Dict) -> Tuple[float, str]:
        """
        Assess data completeness for a pillar.
        
        Args:
            pillar_name: Name of the pillar being assessed
            data: Dictionary containing the data to assess
            expected_minimums: Expected minimum counts/values for this area type
        
        Returns:
            Tuple of (completeness_score, quality_tier)
        """
        if not data:
            return 0.0, 'very_poor'
        
        # Calculate completeness based on pillar type
        if pillar_name in ('active_outdoors', 'active_outdoors_v2'):
            return self._assess_outdoors_completeness(data, expected_minimums)
        elif pillar_name == 'healthcare_access':
            return self._assess_healthcare_completeness(data, expected_minimums)
        elif pillar_name == 'air_travel_access':
            return self._assess_airport_completeness(data, expected_minimums)
        elif pillar_name == 'neighborhood_amenities':
            return self._assess_business_completeness(data, expected_minimums)
        elif pillar_name == 'economic_opportunity':
            return self._assess_economic_opportunity_completeness(data, expected_minimums)
        elif pillar_name == 'housing_value':
            return self._assess_housing_completeness(data, expected_minimums)
        elif pillar_name == 'natural_beauty':
            return self._assess_natural_beauty_completeness(data, expected_minimums)
        elif pillar_name == 'public_transit_access':
            return self._assess_transit_completeness(data, expected_minimums)
        elif pillar_name == 'climate_risk':
            return self._assess_climate_risk_completeness(data, expected_minimums)
        elif pillar_name == 'social_fabric':
            return self._assess_social_fabric_completeness(data, expected_minimums)
        elif pillar_name == 'diversity':
            return self._assess_diversity_completeness(data, expected_minimums)
        else:
            return self._assess_generic_completeness(data, expected_minimums)

    def _assess_economic_opportunity_completeness(self, data: Dict, expected: Dict) -> Tuple[float, str]:
        """
        Assess economic_opportunity completeness.

        This pillar is metric-driven (not count-driven), so completeness reflects how many
        submetrics were successfully computed.
        """
        if not data:
            return 0.0, 'very_poor'

        metrics_present = data.get("metrics_present", [])
        if not isinstance(metrics_present, list):
            metrics_present = []

        # Current pillar uses 6 scored submetrics (see pillars/economic_opportunity.py).
        total_expected = 6
        completeness = min(1.0, len(metrics_present) / max(1, total_expected))

        # Floor: if we have at least job-market + earnings basics, don't drop below fair.
        key_basics = {"unemployment_rate", "emp_pop_ratio", "median_earnings"}
        if key_basics.issubset(set(metrics_present)):
            completeness = max(completeness, 0.55)

        return completeness, self._get_quality_tier(completeness)
    
    def _assess_outdoors_completeness(self, data: Dict, expected: Dict) -> Tuple[float, str]:
        """Assess outdoor recreation data completeness."""
        parks = data.get('parks', [])
        playgrounds = data.get('playgrounds', [])
        hiking = data.get('hiking', [])
        swimming = data.get('swimming', [])
        camping = data.get('camping', [])
        
        # Calculate completeness
        # Prevent division by zero
        local_score = min(1.0, (len(parks) + len(playgrounds)) / max(1, expected.get('local_facilities', 5)))
        regional_score = min(1.0, (len(hiking) + len(swimming) + len(camping)) / max(1, expected.get('regional_facilities', 3)))
        
        completeness = (local_score * 0.6) + (regional_score * 0.4)
        return completeness, self._get_quality_tier(completeness)
    
    def _assess_healthcare_completeness(self, data: Dict, expected: Dict) -> Tuple[float, str]:
        """Assess healthcare data completeness."""
        hospitals = data.get('hospitals', [])
        urgent_care = data.get('urgent_care', [])
        pharmacies = data.get('pharmacies', [])
        clinics = data.get('clinics', [])
        
        # Prevent division by zero
        hospital_score = min(1.0, len(hospitals) / max(1, expected.get('hospitals', 1)))
        urgent_score = min(1.0, len(urgent_care) / max(1, expected.get('urgent_care', 3)))
        pharmacy_score = min(1.0, len(pharmacies) / max(1, expected.get('pharmacies', 2)))
        clinic_score = min(1.0, len(clinics) / max(1, expected.get('clinics', 2)))
        
        completeness = (hospital_score * 0.4) + (urgent_score * 0.3) + (pharmacy_score * 0.2) + (clinic_score * 0.1)
        return completeness, self._get_quality_tier(completeness)
    
    def _assess_airport_completeness(self, data: Dict, expected: Dict) -> Tuple[float, str]:
        """Assess airport data completeness."""
        airports = data.get('airports', [])
        if not airports:
            return 0.0, 'very_poor'
        
        # Check for major airports within reasonable distance
        major_airports = [a for a in airports if a.get('type') == 'large_airport' and a.get('distance_km', 999) <= 100]
        regional_airports = [a for a in airports if a.get('type') == 'medium_airport' and a.get('distance_km', 999) <= 50]
        
        # Prevent division by zero - use max(1, value) to ensure minimum divisor of 1
        major_score = min(1.0, len(major_airports) / max(1, expected.get('major_airports', 1)))
        regional_score = min(1.0, len(regional_airports) / max(1, expected.get('regional_airports', 1)))
        
        completeness = (major_score * 0.7) + (regional_score * 0.3)
        return completeness, self._get_quality_tier(completeness)
    
    def _assess_business_completeness(self, data: Dict, expected: Dict) -> Tuple[float, str]:
        """
        Assess amenity sample coverage vs area expectations (aggregate count + type variety).
        Not ground-truth “every business,” and not per walkability-tier minimums—see get_expected_minimums.
        """
        if data.get("fallback_applied"):
            # Imputed score when OSM returned no POIs — weak vs a real sample
            return 0.25, 'poor'
        # Try 'businesses' first, then 'all_businesses'
        businesses = data.get('businesses', []) or data.get('all_businesses', [])
        if not businesses:
            return 0.0, 'very_poor'
        
        # Check variety and density
        unique_types = len(set(b.get('type', 'unknown') for b in businesses))
        # Prevent division by zero
        density_score = min(1.0, len(businesses) / max(1, expected.get('business_count', 20)))
        variety_score = min(1.0, unique_types / max(1, expected.get('business_types', 8)))
        
        completeness = (density_score * 0.6) + (variety_score * 0.4)
        return completeness, self._get_quality_tier(completeness)
    
    def _assess_housing_completeness(self, data: Dict, expected: Dict) -> Tuple[float, str]:
        """Assess housing value data completeness."""
        housing_data = data.get('housing_data', {})
        
        if not housing_data:
            return 0.0, 'very_poor'
        
        # Check for key housing metrics
        has_median_value = 'median_home_value' in housing_data
        has_median_income = 'median_household_income' in housing_data
        has_median_rooms = 'median_rooms' in housing_data
        
        # Calculate completeness based on available metrics
        metric_score = sum([has_median_value, has_median_income, has_median_rooms]) / 3.0
        
        completeness = metric_score
        return completeness, self._get_quality_tier(completeness)
    
    def _assess_natural_beauty_completeness(self, data: Dict, expected: Dict) -> Tuple[float, str]:
        """Assess natural beauty data completeness."""
        tree_analysis = data.get('tree_analysis', {})
        enhancers = data.get('enhancers', {})
        scenic_metadata = data.get('scenic_metadata', {})
        
        if not tree_analysis:
            return 0.0, 'very_poor'
        
        # Check for key tree analysis metrics
        has_canopy = 'gee_canopy_pct' in tree_analysis or 'canopy_pct' in tree_analysis
        has_natural_context = 'natural_context' in tree_analysis
        has_data_availability = 'data_availability' in tree_analysis
        has_multi_radius = 'multi_radius_canopy' in tree_analysis
        
        # Check for enhancer data
        has_enhancers = bool(enhancers)
        has_scenic = bool(scenic_metadata)
        
        # Calculate completeness: tree analysis is primary (70%), enhancers (20%), scenic (10%)
        tree_score = sum([has_canopy, has_natural_context, has_data_availability, has_multi_radius]) / 4.0
        enhancer_score = 1.0 if has_enhancers else 0.0
        scenic_score = 1.0 if has_scenic else 0.0
        
        completeness = (tree_score * 0.7) + (enhancer_score * 0.2) + (scenic_score * 0.1)
        return completeness, self._get_quality_tier(completeness)
    
    def _assess_transit_completeness(self, data: Dict, expected: Dict) -> Tuple[float, str]:
        """Assess public transit access data completeness."""
        routes_data = data.get('routes_data', [])
        heavy_rail_routes = data.get('heavy_rail_routes', [])
        light_rail_routes = data.get('light_rail_routes', [])
        bus_routes = data.get('bus_routes', [])
        
        if not routes_data and not (heavy_rail_routes or light_rail_routes or bus_routes):
            return 0.0, 'very_poor'
        
        # Check for route data availability
        has_routes = len(routes_data) > 0
        has_heavy_rail = len(heavy_rail_routes) > 0
        has_light_rail = len(light_rail_routes) > 0
        has_bus = len(bus_routes) > 0
        
        # Calculate completeness based on route types found
        # Having any routes is good, having multiple types is better
        route_type_count = sum([has_heavy_rail, has_light_rail, has_bus])
        route_type_score = min(1.0, route_type_count / 3.0)  # 0-1 based on route types
        
        # Also consider total route count (normalized)
        total_routes = len(routes_data) if routes_data else (len(heavy_rail_routes) + len(light_rail_routes) + len(bus_routes))
        route_count_score = min(1.0, total_routes / 10.0)  # 10+ routes = full score
        
        # Weighted average: route types (60%), route count (40%)
        completeness = (route_type_score * 0.6) + (route_count_score * 0.4)
        
        # Minimum floor: if we have any routes, completeness should be at least 0.3
        if has_routes or route_type_count > 0:
            completeness = max(completeness, 0.3)
        
        return completeness, self._get_quality_tier(completeness)
    
    def _assess_climate_risk_completeness(self, data: Dict, expected: Dict) -> Tuple[float, str]:
        """Assess climate_risk (Phase 1A GEE-only) data completeness."""
        if not data:
            return 0.0, 'very_poor'
        present = data.get('components_present')
        if isinstance(present, (list, tuple)):
            completeness = len(present) / 4.0
            return completeness, self._get_quality_tier(completeness)
        heat_data = data.get('heat_data')
        air_data = data.get('air_data')
        has_heat = heat_data is not None and isinstance(heat_data, dict)
        has_air = air_data is not None and isinstance(air_data, dict)
        if has_heat and has_air:
            completeness = 1.0
        elif has_heat or has_air:
            completeness = 0.5
        else:
            completeness = 0.0
        return completeness, self._get_quality_tier(completeness)
    
    def _assess_social_fabric_completeness(self, data: Dict, expected: Dict) -> Tuple[float, str]:
        """
        Assess social_fabric completeness: Stability, Civic (OSM / Places / imputed), Engagement.

        Civic: Overpass error needs Places or (optional) imputed floor. For ok/empty OSM, zero nodes in areas
        with civic_nodes_min > 1 is incomplete unless Places ran or imputed floor applied.
        """
        if not data:
            return 0.0, 'very_poor'

        mobility = data.get("mobility")
        engagement_score = data.get("engagement_score")

        sm_acs = (data.get("source_status") or {}).get("stability_mobility_acs")
        stability_computed = bool(data.get("stability_computed"))
        if sm_acs is None:
            has_stability = mobility is not None or stability_computed
        else:
            has_stability = (sm_acs == "ok") or stability_computed
        ss = data.get("source_status") or {}
        civic_osm = ss.get("civic_osm")
        civic_places = ss.get("civic_places")
        civic_nodes = int(data.get("civic_nodes_count") or 0)
        civic_min = max(1, int(expected.get("civic_nodes_min") or 1))
        places_augmented = bool(data.get("places_civic_augmented"))
        imputed = bool(data.get("civic_imputed_floor_applied"))

        if civic_osm == "error":
            has_civic = civic_places in ("ok", "empty") or places_augmented or imputed
        elif civic_osm in ("ok", "empty", None):
            if civic_nodes > 0:
                has_civic = True
            elif civic_places in ("ok", "empty") or places_augmented or imputed:
                has_civic = True
            elif civic_min <= 1:
                has_civic = True
            else:
                has_civic = False
        else:
            has_civic = civic_places in ("ok", "empty") or places_augmented

        has_engagement = engagement_score is not None

        components_available = sum([has_stability, has_civic, has_engagement])
        completeness = components_available / 3.0

        if has_stability and has_civic and completeness < 0.55:
            completeness = max(completeness, 0.55)

        if data.get("participation_median_fallback") or (
            (data.get("participation_diag") or {}).get("median_fallback")
        ):
            completeness = min(completeness, 0.45)

        return completeness, self._get_quality_tier(completeness)

    def _assess_diversity_completeness(self, data: Dict, expected: Dict) -> Tuple[float, str]:
        """
        Census tract diversity: completeness = share of race / income / age
        entropy components computed (target 3).
        """
        if not data or not data.get("diversity_data_loaded"):
            return 0.0, 'very_poor'
        present = data.get("components_present") or []
        target = max(1, int(expected.get("diversity_components", 3)))
        completeness = min(1.0, len(present) / float(target))
        if len(present) >= 2:
            completeness = max(completeness, 0.55)
        return completeness, self._get_quality_tier(completeness)

    def _assess_generic_completeness(self, data: Dict, expected: Dict) -> Tuple[float, str]:
        """Generic completeness assessment."""
        if not data:
            return 0.0, 'very_poor'
        
        # Simple count-based assessment
        total_items = sum(len(v) if isinstance(v, list) else 1 for v in data.values())
        expected_items = sum(expected.values())
        
        completeness = min(1.0, total_items / max(expected_items, 1))
        return completeness, self._get_quality_tier(completeness)
    
    def _get_quality_tier(self, completeness: float) -> str:
        """Get quality tier based on completeness score."""
        for tier, threshold in self.quality_thresholds.items():
            if completeness >= threshold:
                return tier
        return 'very_poor'
    
    def get_expected_minimums(self, lat: float, lon: float, area_type: str, density: Optional[float] = None) -> Dict:
        """
        Get expected minimum data counts based on area type and density.
        
        Args:
            lat, lon: Coordinates
            area_type: 'urban_core', 'suburban', 'exurban', 'rural'
        
        Returns:
            Dictionary of expected minimums
        """
        # Get population density for more precise expectations. Callers that already hold the density pass it
        # in, so a Census timeout here cannot silently turn the expectations into the rural ones.
        if density is None:
            density = get_population_density(lat, lon)
        
        if area_type == 'urban_core' or (density and density > 10000):
            return {
                'local_facilities': 10,
                'regional_facilities': 5,
                'hospitals': 2,
                'urgent_care': 8,
                'pharmacies': 5,
                'clinics': 6,
                'major_airports': 1,
                'regional_airports': 2,
                'business_count': 50,
                'business_types': 12,
                'diversity_components': 3,
                'civic_nodes_min': 6,
            }
        elif area_type == 'suburban' or (density and density > 2500):
            return {
                'local_facilities': 5,
                'regional_facilities': 3,
                'hospitals': 1,
                'urgent_care': 4,
                'pharmacies': 3,
                'clinics': 3,
                'major_airports': 1,
                'regional_airports': 1,
                'business_count': 25,
                'business_types': 8,
                'diversity_components': 3,
                'civic_nodes_min': 3,
            }
        elif area_type == 'exurban' or (density and density > 1000):
            return {
                'local_facilities': 3,
                'regional_facilities': 2,
                'hospitals': 1,
                'urgent_care': 2,
                'pharmacies': 2,
                'clinics': 2,
                'major_airports': 0,
                'regional_airports': 1,
                'business_count': 15,
                'business_types': 6,
                'diversity_components': 3,
                'civic_nodes_min': 2,
            }
        else:  # rural
            return {
                'local_facilities': 1,
                'regional_facilities': 1,
                'hospitals': 0,
                'urgent_care': 1,
                'pharmacies': 1,
                'clinics': 1,
                'major_airports': 0,
                'regional_airports': 0,
                'business_count': 5,
                'business_types': 3,
                'diversity_components': 3,
                'civic_nodes_min': 1,
            }
    
    def create_confidence_score(self, data_completeness: float, 
                              data_sources: List[str], 
                              fallback_used: bool) -> int:
        """
        Create confidence score (0-100) based on data quality factors.
        
        Args:
            data_completeness: Completeness score (0-1)
            data_sources: List of data sources used
            fallback_used: Whether fallback scoring was used
        
        Returns:
            Confidence score (0-100)
        """
        # Base confidence from completeness
        confidence = int(data_completeness * 100)
        
        # Adjust for data source quality
        source_quality = {
            'osm': 0.9,
            'google_places': 0.9,
            'census': 0.95,
            'static': 0.8,
            'fallback': 0.5
        }
        
        if data_sources:
            avg_source_quality = sum(source_quality.get(source, 0.7) for source in data_sources) / len(data_sources)
            confidence = int(confidence * avg_source_quality)
        
        # Penalty for fallback usage
        if fallback_used:
            confidence = int(confidence * 0.8)
        
        return max(0, min(100, confidence))


# Global instance
data_quality_manager = DataQualityManager()

# OSM geometry/heuristic warnings that are common in real places (single-story suburbs,
# incomplete building footprints in dense areas). They should not flip the global
# "degraded" UI flag — see main._collect_degraded_signals.
INFORMATIONAL_DATA_WARNINGS = frozenset(
    {
        "suspiciously_low_height_diversity",
        "low_building_coverage",
    }
)

# Hard fetch/compute failures: the underlying signal is absent, not partial. Confidence
# must be floored low so the UI's <50 rescore warning fires instead of showing a
# cosmetically-discounted (~79-90%) "confident" score over no real data.
HARD_DATA_WARNINGS = frozenset(
    {
        "api_error",
        "timeout",
    }
)


def data_quality_indicates_fallback(dq: Any) -> bool:
    """True if dq indicates fallback (top-level fallback_used or legacy fallback_metadata only)."""
    if not isinstance(dq, dict):
        return False
    if dq.get("fallback_used") is True:
        return True
    meta = dq.get("fallback_metadata")
    if isinstance(meta, dict) and meta.get("fallback_used") is True:
        return True
    return False


def assess_pillar_data_quality(
    pillar_name: str,
    data: Dict,
    lat: float,
    lon: float,
    area_type: str,
    *,
    fallback_used: bool = False,
    density: Optional[float] = None,
) -> Dict:
    """
    Assess data quality for a pillar and return quality metrics.

    Args:
        pillar_name: Name of the pillar
        data: Data dictionary to assess
        lat, lon: Coordinates
        area_type: Area classification
        fallback_used: When True, apply extra confidence discount (imputed / weak evidence)
        density: Place density from the shared context; when None the expected minimums fetch their own

    Returns:
        Dictionary with quality metrics
    """
    expected_minimums = data_quality_manager.get_expected_minimums(lat, lon, area_type, density=density)
    completeness, quality_tier = data_quality_manager.assess_data_completeness(
        pillar_name, data, expected_minimums
    )
    
    # Create confidence score
    data_sources = ['osm'] if data else []
    if pillar_name == 'neighborhood_amenities' and data and data.get('places_augmented'):
        data_sources = ['osm', 'google_places']
    elif pillar_name == 'social_fabric' and data:
        if data.get('places_civic_augmented'):
            data_sources = (
                ['census', 'osm', 'google_places']
                if data.get('mobility') is not None
                else ['osm', 'google_places']
            )
        else:
            data_sources = ['census', 'osm'] if data.get('mobility') is not None else ['osm']
    elif pillar_name == 'diversity' and data:
        data_sources = ['census']
    confidence = data_quality_manager.create_confidence_score(
        completeness, data_sources, fallback_used
    )
    
    # Validation: Ensure quality_tier is always a string
    valid_tiers = ['excellent', 'good', 'fair', 'poor', 'very_poor']
    if not isinstance(quality_tier, str) or quality_tier not in valid_tiers:
        logger.warning(f"Invalid quality_tier '{quality_tier}' (type: {type(quality_tier)}), defaulting to 'fair'")
        quality_tier = 'fair'

    out = {
        'completeness': completeness,
        'quality_tier': quality_tier,
        'needs_fallback': False,
        'fallback_score': None,
        # Top-level: matches quality_education and main._set_pillar_status / UI / report scripts.
        'fallback_used': fallback_used,
        'fallback_metadata': {'fallback_used': fallback_used},
        'confidence': confidence,
        'expected_minimums': expected_minimums,
        'data_sources': data_sources
    }
    ss = data.get("source_status") if data else None
    se = data.get("source_errors") if data else None
    if isinstance(ss, dict) and ss:
        out["source_status"] = ss
    if isinstance(se, list) and se:
        out["source_errors"] = se

    return out
