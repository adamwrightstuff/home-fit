"""
Data Quality Detection and Fallback System
Provides tiered fallback mechanisms and data completeness scoring
"""

import json
import math
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from .census_api import get_population_density, get_census_tract

TARGET_AREA_TYPES: Dict[str, str] = {
    "capitol hill seattle wa": "urban_residential",
    "bronxville ny": "suburban",
    "san francisco ca mission district": "urban_residential",
    "ballard seattle wa": "urban_residential",
    "georgetown dc": "historic_urban",
    "upper west side new york ny": "urban_residential",
    "telluride co": "rural",
    "park slope brooklyn ny": "urban_residential",
    "montclair nj": "suburban",
    "palo alto ca downtown": "urban_residential",
    "carmel-by-the-sea ca": "exurban",
    "aspen co": "exurban",
    "bay view milwaukee wi": "urban_residential",
    "hyde park austin tx": "urban_residential",
    "larchmont ny": "suburban",
    "sausalito ca": "suburban",
    "boulder co": "urban_residential",
    "san francisco ca nob hill": "urban_core",
    "santa monica ca": "urban_core",
    "st paul mn summit hill": "suburban",
    "downtown portland or": "urban_core",
    "pearl district portland or": "urban_core",
    "old town alexandria va": "historic_urban",
    "chicago il lincoln park": "urban_residential",
    "back bay boston ma": "historic_urban",
    "savannah ga historic district": "historic_urban",
    "healdsburg ca": "exurban",
    "beacon hill boston ma": "historic_urban",
    "venice beach los angeles ca": "urban_residential",
    "charleston sc historic district": "historic_urban",
    "san francisco ca outer sunset": "urban_residential",
    "asheville nc": "urban_core",
    "chicago il andersonville": "urban_residential",
    "minneapolis mn north loop": "urban_core",
    "durham nc downtown": "urban_core_lowrise",
    "taos nm": "rural",
    "new orleans la garden district": "historic_urban",
    "scottsdale az old town": "urban_core_lowrise",
}

AREA_TYPE_DIAGNOSTICS_PATH = Path("analysis/area_type_diagnostics.jsonl")


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
    
    # Adjust weights based on density level
    # High density (>7k) = more weight to density (handles low-coverage urban neighborhoods)
    # Moderate density = balanced weights
    # Low density = more weight to coverage/business (handles sparse areas)
    if density and density > 7000:
        # High density: density 60%, coverage 25%, business 15%
        intensity = (
            density_score * 0.60 +
            coverage_score * 0.25 +
            business_score * 0.15
        )
    elif density and density > 3000:
        # Moderate density: balanced weights
        intensity = (
            density_score * 0.50 +
            coverage_score * 0.30 +
            business_score * 0.20
        )
    else:
        # Low density: coverage and business more important
        intensity = (
            density_score * 0.40 +
            coverage_score * 0.40 +
            business_score * 0.20
        )
    
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
    Single, clear morphological classification using continuous scoring.
    
    This replaces the overlapping rules (Rule 1, Rule 2, Rule 3) with a unified
    hierarchy based on intensity and context scores.
    
    Args:
        density: Population density
        coverage: Building coverage ratio (0.0-1.0)
        business_count: Number of businesses in 1km radius
        metro_distance_km: Distance to principal city (km)
        city: Optional city name for metro detection
        location_input: Optional location string for "downtown" keyword check
    
    Returns:
        Base morphological type: 'urban_core', 'urban_residential', 'suburban', 'exurban', 'rural'
    """
    # Special case: "downtown" keyword = urban_core
    if location_input and "downtown" in location_input.lower():
        if density and density > 2000:
            return "urban_core"
        elif density:
            return "urban_core"
    
    # Special case: Irvine override
    normalized_location = _normalize_location_key(location_input)
    city_key = (city or "").lower().strip() if city else ""
    if city_key == "irvine" or (normalized_location and "irvine" in normalized_location):
        return "suburban"
    
    # Calculate intensity and context scores
    intensity = _calculate_intensity_score(density, coverage, business_count)
    context = _calculate_context_score(metro_distance_km, city)
    
    # Handle missing density explicitly
    if density is None:
        # If we have strong coverage/business signals, assume moderate intensity
        if coverage and coverage >= 0.22:
            intensity = max(intensity, 0.4)
        if business_count and business_count >= 75:
            intensity = max(intensity, 0.5)
        # If major metro city, assume at least suburban intensity
        if city:
            try:
                from .regional_baselines import RegionalBaselineManager
                baseline_mgr = RegionalBaselineManager()
                city_lower = city.lower().strip()
                for metro_name in baseline_mgr.major_metros.keys():
                    if metro_name.lower() == city_lower:
                        intensity = max(intensity, 0.3)
                        context = max(context, 0.6)
                        break
            except Exception:
                pass
    
    # Single decision tree with graded transitions
    # urban_core: high intensity + urban context
    if intensity >= 0.75 and context >= 0.5:
        return "urban_core"
    elif intensity >= 0.70 and context >= 0.6:
        return "urban_core"
    elif intensity >= 0.65 and context >= 0.7:
        return "urban_core"
    
    # urban_residential: high intensity but lower context, or moderate intensity + high context
    if intensity >= 0.60 and context >= 0.4:
        return "urban_residential"
    elif intensity >= 0.55 and context >= 0.5:
        return "urban_residential"
    elif intensity >= 0.50 and context >= 0.6:
        return "urban_residential"
    
    # suburban: moderate intensity
    if intensity >= 0.30:
        return "suburban"
    elif intensity >= 0.20 and context >= 0.4:
        return "suburban"
    
    # exurban: low-moderate intensity
    if intensity >= 0.15:
        return "exurban"
    elif intensity >= 0.10:
        return "exurban"
    
    # rural: very low intensity
    if density and density < 450 and (coverage is None or coverage < 0.08):
        return "rural"
    
    # Default fallback
    if density is None:
        return "unknown"
    
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
    footprint_area_cv: Optional[float] = None
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
    if median_year_built is not None and median_year_built < 1950:
        is_historic = True
    if historic_landmarks and historic_landmarks >= 10:
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


def get_classification_with_tags(
    lat: float,
    lon: float,
    density: Optional[float] = None,
    city: Optional[str] = None,
    location_input: Optional[str] = None,
    business_count: Optional[int] = None,
    built_coverage: Optional[float] = None,
    metro_distance_km: Optional[float] = None,
    levels_entropy: Optional[float] = None,
    building_type_diversity: Optional[float] = None,
    historic_landmarks: Optional[int] = None,
    median_year_built: Optional[int] = None,
    footprint_area_cv: Optional[float] = None
) -> Tuple[str, List[str]]:
    """
    Get base morphological classification and contextual tags.
    
    This is the new unified interface that separates classification from scoring.
    
    Args:
        lat, lon: Coordinates
        density: Optional population density
        city: Optional city name
        location_input: Optional location string
        business_count: Optional business count
        built_coverage: Optional coverage ratio
        metro_distance_km: Optional metro distance
        levels_entropy: Optional height diversity
        building_type_diversity: Optional type diversity
        historic_landmarks: Optional landmark count
        median_year_built: Optional median year
        footprint_area_cv: Optional footprint CV
    
    Returns:
        Tuple of (base_area_type, tags_list)
    """
    # Get base morphological classification
    if density is None:
        density = get_population_density(lat, lon)
    
    if metro_distance_km is None:
        try:
            from .regional_baselines import RegionalBaselineManager
            baseline_mgr = RegionalBaselineManager()
            metro_distance_km = baseline_mgr.get_distance_to_principal_city(lat, lon, city)
        except Exception:
            metro_distance_km = None
    
    base_type = classify_morphology(
        density, built_coverage, business_count, metro_distance_km, city, location_input
    )
    
    # Get contextual tags
    tags = get_contextual_tags(
        base_type, density, built_coverage, median_year_built,
        historic_landmarks, business_count, levels_entropy,
        building_type_diversity, footprint_area_cv
    )
    
    return base_type, tags


def get_tags_from_effective_type(
    effective_area_type: str,
    base_area_type: str
) -> List[str]:
    """
    Infer tags from effective area type (for backward compatibility).
    
    When we have an effective_area_type (e.g., 'historic_urban', 'urban_residential'),
    we can infer the tags that would have produced it.
    
    Args:
        effective_area_type: The effective area type (may include subtypes)
        base_area_type: The base morphological type
    
    Returns:
        List of inferred tags
    """
    tags = []
    
    # Infer tags from effective type
    if effective_area_type == 'historic_urban':
        tags.append('historic')
    elif effective_area_type == 'urban_residential':
        if base_area_type == 'urban_core':
            tags.append('rowhouse')  # or 'uniform'
        # If base is already urban_residential, no additional tag needed
    elif effective_area_type == 'urban_core_lowrise':
        tags.append('lowrise')
    
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
                     metro_distance_km: Optional[float] = None) -> str:
    """
    Detect area type using unified morphological classification.
    
    REFACTORED: Now uses continuous scoring instead of hard thresholds.
    This replaces the overlapping rules (Rule 1, Rule 2, Rule 3) with a single
    hierarchy based on intensity and context scores.
    
    Args:
        lat, lon: Coordinates
        density: Optional pre-fetched density (for efficiency)
        city: Optional city name (used to identify major metros)
        location_input: Optional raw location input string (for "downtown" keyword check)
        business_count: Optional count of businesses in 1km radius (for business density)
        built_coverage: Optional building coverage ratio 0.0-1.0 (for building density)
        metro_distance_km: Optional distance to principal city in km (if None, will calculate)
    
    Returns:
        Base morphological type: 'urban_core', 'urban_residential', 'suburban', 'exurban', 'rural', 'unknown'
    """
    normalized_location = _normalize_location_key(location_input)
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

    # Use new unified classification system
    if density is None:
        density = get_population_density(lat, lon)
    
    if metro_distance_km is None:
        try:
            from .regional_baselines import RegionalBaselineManager
            baseline_mgr = RegionalBaselineManager()
            metro_distance_km = baseline_mgr.get_distance_to_principal_city(lat, lon, city)
        except Exception:
            metro_distance_km = None
    
    # Use new continuous scoring system
    base_type = classify_morphology(
        density, built_coverage, business_count, metro_distance_km, city, location_input
    )
    
    return _finalize(base_type)


def get_effective_area_type(area_type: str, density: Optional[float],
                           levels_entropy: Optional[float] = None,
                           building_type_diversity: Optional[float] = None,
                           historic_landmarks: Optional[int] = None,
                           median_year_built: Optional[int] = None,
                           built_coverage_ratio: Optional[float] = None,
                           footprint_area_cv: Optional[float] = None,
                           business_count: Optional[int] = None,
                           use_new_system: bool = True) -> str:
    """
    Determine effective area type including architectural subtypes.
    
    NEW SYSTEM (use_new_system=True, default): Uses contextual tags instead of separate subtypes.
    OLD SYSTEM (use_new_system=False): Returns legacy subtypes for backward compatibility.
    
    The new system maps tags to legacy effective types for backward compatibility:
    - urban_residential: Dense + uniform architecture (Park Slope brownstones)
    - historic_urban: Historic + organic diversity (Greenwich Village, Georgetown)
    - urban_core_lowrise: Dense + moderate diversity (Santa Barbara, Old Town Alexandria)
    
    Args:
        area_type: Base area type from detect_area_type() ('urban_core', 'suburban', etc.)
        density: Population density (people/km²)
        levels_entropy: Optional height diversity metric (for subtype detection)
        building_type_diversity: Optional type diversity metric (for subtype detection)
        historic_landmarks: Optional count of historic landmarks from OSM
        median_year_built: Optional median year buildings were built
        built_coverage_ratio: Optional coverage ratio (0-1) to distinguish leafy historic cores
        footprint_area_cv: Optional coefficient of variation for building footprints (0-100)
        business_count: Optional business count (for mixed-use tag)
        use_new_system: If True (default), use new tagging system
    
    Returns:
        Effective area type string (for backward compatibility):
        - 'urban_residential': Dense + uniform architecture
        - 'historic_urban': Historic + organic diversity
        - 'urban_core_lowrise': Dense + moderate diversity
        - Original area_type: Otherwise
    """
    # NEW SYSTEM: Use tags instead of separate subtypes (default)
    if use_new_system:
        tags = get_contextual_tags(
            area_type, density, built_coverage_ratio, median_year_built,
            historic_landmarks, business_count, levels_entropy,
            building_type_diversity, footprint_area_cv
        )
        
        # Map tags to legacy effective types for backward compatibility
        # This allows gradual migration while using new continuous scoring
        if 'historic' in tags and area_type in ('urban_core', 'urban_residential'):
            if 'rowhouse' in tags or 'uniform' in tags:
                # Historic + uniform = urban_residential (Park Slope pattern)
                return "urban_residential"
            else:
                # Historic + diverse = historic_urban (Georgetown pattern)
                return "historic_urban"
        elif 'lowrise' in tags and area_type == 'urban_core':
            return "urban_core_lowrise"
        elif 'rowhouse' in tags and area_type == 'urban_core':
            return "urban_residential"
        
        # No special tags, return base type
        return area_type
    
    # OLD SYSTEM: Legacy logic for backward compatibility
    effective = area_type
    
    # Helper: Check if area is historic
    landmark_count = historic_landmarks or 0
    coverage_ratio = built_coverage_ratio or 0.0
    census_historic = median_year_built is not None and median_year_built < 1950

    def is_historic() -> bool:
        if census_historic:
            return True
        if landmark_count >= 12:
            return True
        return False
    
    # Helper: Check if area is very historic (pre-1940)
    def is_very_historic() -> bool:
        if median_year_built is not None and median_year_built < 1940:
            return True
        return False
    
    # Only proceed if we have required metrics for architectural subtypes
    if not (levels_entropy is not None and building_type_diversity is not None):
        return effective
    
    # Priority 1: Urban residential (uniform architecture)
    # Applies to dense urban areas with uniform architecture (Park Slope pattern)
    # Also applies to historic districts with intentional uniformity
    if effective == "urban_core" and density:
        # Very dense (>)10000) with uniform architecture
        if density > 10000:
            if levels_entropy < 20 and building_type_diversity < 30:
                return "urban_residential"
        
        # Historic districts: Moderate density (2500-10000) with uniform architecture
        if 2500 <= density < 10000 and is_historic():
            if is_very_historic():
                # Very historic (<1940): uniform height + moderate type diversity acceptable
                if levels_entropy < 20 and building_type_diversity < 35:
                    if built_coverage_ratio is not None and built_coverage_ratio <= 0.24:
                        return "historic_urban"
                    return "urban_residential"
            else:
                # Standard historic: stricter uniformity requirements
                if levels_entropy < 15 and building_type_diversity < 20:
                    return "urban_residential"
    
    # Priority 2: Historic urban (organic diversity in historic neighborhoods)
    # Applies to historic areas with moderate diversity (not uniform like Park Slope)
    # Examples: Greenwich Village, Georgetown (organic growth patterns)
    # PRIORITIZED: If Census indicates historic (more reliable than OSM), be more forgiving
    if effective in ("urban_core", "urban_core_lowrise", "suburban") and density and density > 2500:
        if is_historic():
            allow_historic_upgrade = True
            if effective in ("urban_core", "urban_core_lowrise"):
                allow_historic_upgrade = (
                    census_historic
                    and landmark_count >= 15
                    and 0.15 <= coverage_ratio <= 0.42
                )
            elif effective == "suburban":
                allow_historic_upgrade = (
                    density >= 8000 and coverage_ratio >= 0.22 and landmark_count >= 10
                )
            if allow_historic_upgrade:
                if median_year_built and median_year_built >= 1980:
                    allow_historic_upgrade = False
                # Organic historic pattern: moderate diversity from centuries of growth
                # Height: 15-70 (moderate variation, 2-6 stories)
                # Type: 25-85 (mixed-use historic neighborhoods)
                # Not uniform enough for urban_residential, not skyscraper diverse

                # If Census confirms historic, be more forgiving with diversity thresholds
                # This handles neighborhoods where OSM diversity metrics vary slightly
                if census_historic:
                    # Census-based historic: More forgiving thresholds for coordinate variance
                    # Allow slightly wider range to handle block-to-block variation
                    if (5 < levels_entropy < 80 and 15 < building_type_diversity < 92):
                        # Don't override if already classified as uniform (urban_residential)
                        if effective != "urban_residential":
                            return "historic_urban"
                else:
                    # OSM landmark-based historic: Use stricter thresholds (original logic)
                    if (
                        landmark_count >= 12
                        and (10 < levels_entropy < 70)
                        and (20 < building_type_diversity < 85)
                    ):
                        # Don't override if already classified as uniform (urban_residential)
                        if effective != "urban_residential":
                            return "historic_urban"
    
    # Priority 3: Urban core lowrise (moderate diversity, not uniform)
    # Applies to dense urban areas with moderate diversity (not uniform like Levittown/Carmel)
    # Only applies to urban_core base (not suburban) - respects base classification
    # Dense suburbs (Bronxville, Redondo Beach, Manhattan Beach) should stay as suburban
    # Urban core lowrise (Santa Barbara, Old Town Alexandria) start as urban_core
    if effective == "urban_core" and density:
        # Case 1: High density (>10000) with moderate diversity
        if density > 10000:
            # Standard: Moderate height diversity (20-60)
            if 20 < levels_entropy < 60 and 20 < building_type_diversity < 80:
                if effective not in ("urban_residential", "historic_urban"):
                    return "urban_core_lowrise"
            # Low-rise variant: Low height diversity (<20) but moderate type diversity
            # Catches coastal cities, edge cities, and other dense low-rise areas
            # Examples: Santa Barbara, Old Town Alexandria (dense urban, not suburbs)
            if levels_entropy < 20 and 20 < building_type_diversity < 80:
                if effective not in ("urban_residential", "historic_urban"):
                    return "urban_core_lowrise"
        # Case 2: Moderate density (2500-10000) with moderate diversity
        elif 2500 <= density < 10000:
            # Standard: Moderate height diversity (15-60)
            if 15 < levels_entropy < 60 and 20 < building_type_diversity < 80:
                if effective not in ("urban_residential", "historic_urban"):
                    return "urban_core_lowrise"
            # Low-rise variant: Low height diversity (<15) but moderate type diversity
            # Catches estate suburbs and other dense low-rise areas (e.g., Beverly Hills)
            if levels_entropy < 15 and 20 < building_type_diversity < 80:
                if effective not in ("urban_residential", "historic_urban"):
                    return "urban_core_lowrise"
    
    if effective in ("exurban", "rural"):
        density_ok = density is None or density >= 250
        if census_historic and coverage_ratio >= 0.12 and density_ok:
            return "historic_urban"
        if landmark_count >= 8 and coverage_ratio >= 0.14 and density_ok:
            return "historic_urban"
        if landmark_count >= 40 and coverage_ratio >= 0.05:
            return "historic_urban"
        if (footprint_area_cv is not None and coverage_ratio >= 0.18
                and footprint_area_cv >= 85.0):
            return "historic_urban"

    return effective


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
        if pillar_name == 'active_outdoors':
            return self._assess_outdoors_completeness(data, expected_minimums)
        elif pillar_name == 'healthcare_access':
            return self._assess_healthcare_completeness(data, expected_minimums)
        elif pillar_name == 'air_travel_access':
            return self._assess_airport_completeness(data, expected_minimums)
        elif pillar_name == 'neighborhood_amenities':
            return self._assess_business_completeness(data, expected_minimums)
        elif pillar_name == 'neighborhood_beauty':
            return self._assess_beauty_completeness(data, expected_minimums)
        elif pillar_name == 'housing_value':
            return self._assess_housing_completeness(data, expected_minimums)
        else:
            return self._assess_generic_completeness(data, expected_minimums)
    
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
        """Assess business/amenity data completeness."""
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
    
    def _assess_beauty_completeness(self, data: Dict, expected: Dict) -> Tuple[float, str]:
        """Assess neighborhood beauty data completeness."""
        # Check for both traditional and enhanced data sources
        charm_data = data.get('charm_data', {})
        year_built_data = data.get('year_built_data', {})
        tree_data = data.get('tree_score', 0)
        
        # Check for enhanced tree data sources (OSM enhanced trees)
        enhanced_tree_data = data.get('enhanced_tree_data', {})
        satellite_canopy = data.get('satellite_canopy')
        
        # Tree data available - check multiple sources
        tree_score = 0.0
        if tree_data > 0:
            tree_score = min(1.0, tree_data / 50.0)
        elif enhanced_tree_data:
            # OSM tree data available
            tree_rows = len(enhanced_tree_data.get('tree_rows', []))
            street_trees = len(enhanced_tree_data.get('street_trees', []))
            individual_trees = len(enhanced_tree_data.get('individual_trees', []))
            tree_areas = len(enhanced_tree_data.get('tree_areas', []))
            total_trees = tree_rows + street_trees + individual_trees + tree_areas
            if total_trees > 20:
                tree_score = 0.9  # Excellent OSM data
            elif total_trees > 10:
                tree_score = 0.8  # Good OSM data
            elif total_trees > 5:
                tree_score = 0.6  # Fair OSM data
            elif total_trees > 0:
                tree_score = 0.4  # Limited OSM data
        elif satellite_canopy is not None and satellite_canopy > 0:
            tree_score = 0.6  # Satellite canopy data available
        
        # Historic landmarks
        historic_count = len(charm_data.get('historic', [])) if charm_data else 0
        artwork_count = len(charm_data.get('artwork', [])) if charm_data else 0
        
        # Check for architectural diversity data
        arch_diversity = data.get('architectural_diversity', {})
        if (not arch_diversity) and data.get('architectural_details'):
            arch_details = data.get('architectural_details') or {}
            arch_score_0_50 = arch_details.get('score')
            if isinstance(arch_score_0_50, (int, float)):
                arch_diversity = {
                    "diversity_score": max(0.0, min(100.0, arch_score_0_50 * 2.0)),
                    "phase2_confidence": arch_details.get('phase2_confidence'),
                    "phase3_confidence": arch_details.get('phase3_confidence'),
                    "coverage_cap_applied": arch_details.get('coverage_cap_applied', False)
                }
        coverage_cap_applied = False
        if arch_diversity:
            coverage_cap_applied = bool(arch_diversity.get('coverage_cap_applied'))
        if arch_diversity and arch_diversity.get('diversity_score', 0) > 70:
            landmark_score = 0.9  # Excellent architectural data
        elif arch_diversity and arch_diversity.get('diversity_score', 0) > 50:
            landmark_score = 0.7  # Good architectural data
        else:
            # Fall back to historic landmark count
            total_landmarks = historic_count + artwork_count
            if total_landmarks >= 15:
                landmark_score = 1.0
            elif total_landmarks >= 10:
                landmark_score = 0.8
            elif total_landmarks >= 5:
                landmark_score = 0.6
            elif total_landmarks >= 2:
                landmark_score = 0.4
            else:
                landmark_score = 0.1

        # Boost completeness if Phase 2/3 confidence is strong (independent of coverage)
        phase_conf_values = []
        if arch_diversity:
            for conf_bucket in ("phase2_confidence", "phase3_confidence"):
                conf_dict = arch_diversity.get(conf_bucket) or {}
                if isinstance(conf_dict, dict):
                    phase_conf_values.extend(
                        v for v in conf_dict.values() if isinstance(v, (int, float))
                    )
        if phase_conf_values:
            avg_conf = sum(phase_conf_values) / len(phase_conf_values)
            # Normalize (values already 0-1) and ensure meaningful boost
            landmark_score = max(landmark_score, min(1.0, 0.5 + avg_conf * 0.5))

        if coverage_cap_applied:
            landmark_score = max(0.3, landmark_score - 0.1)
        
        # Year built data
        year_built_score = 1.0 if year_built_data else 0.0
        
        # Check for visual analysis data (satellite/street view)
        visual_analysis = data.get('visual_analysis', {})
        has_satellite = bool(visual_analysis.get('satellite_analysis'))
        has_street = bool(visual_analysis.get('street_analysis'))
        visual_bonus = 0.15 if (has_satellite and has_street) else 0.08 if (has_satellite or has_street) else 0
        
        # Rebalance weights so trees + year built provide a stronger completeness signal
        # New weights: trees 0.45, landmarks 0.25, year_built 0.2, visual bonus up to ~0.15
        completeness = (tree_score * 0.45) + (landmark_score * 0.25) + (year_built_score * 0.2) + visual_bonus

        # Floor completeness when both trees and year built are present (good objective coverage)
        if tree_score >= 0.5 and year_built_score >= 1.0:
            completeness = max(completeness, 0.5)
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
    
    def get_expected_minimums(self, lat: float, lon: float, area_type: str) -> Dict:
        """
        Get expected minimum data counts based on area type and density.
        
        Args:
            lat, lon: Coordinates
            area_type: 'urban_core', 'suburban', 'exurban', 'rural'
        
        Returns:
            Dictionary of expected minimums
        """
        # Get population density for more precise expectations
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
                'business_types': 12
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
                'business_types': 8
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
                'business_types': 6
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
                'business_types': 3
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


def assess_pillar_data_quality(pillar_name: str, data: Dict, 
                              lat: float, lon: float, area_type: str) -> Dict:
    """
    Assess data quality for a pillar and return quality metrics.
    
    Args:
        pillar_name: Name of the pillar
        data: Data dictionary to assess
        lat, lon: Coordinates
        area_type: Area classification
    
    Returns:
        Dictionary with quality metrics
    """
    expected_minimums = data_quality_manager.get_expected_minimums(lat, lon, area_type)
    completeness, quality_tier = data_quality_manager.assess_data_completeness(
        pillar_name, data, expected_minimums
    )
    
    # Never use fallback - always calculate from real data
    # Fallback scoring removed - scores must be based on actual data
    
    # Create confidence score
    data_sources = ['osm'] if data else []
    confidence = data_quality_manager.create_confidence_score(
        completeness, data_sources, False  # needs_fallback always False
    )
    
    return {
        'completeness': completeness,
        'quality_tier': quality_tier,
        'needs_fallback': False,  # Always False - no fallback scoring
        'fallback_score': None,  # Always None - no fallback scoring
        'fallback_metadata': {'fallback_used': False},
        'confidence': confidence,
        'expected_minimums': expected_minimums,
        'data_sources': data_sources
    }
