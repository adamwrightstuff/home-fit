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
    
    # REMOVED: Irvine special case - hardcoded city exceptions violate design principles
    # If Irvine needs different classification, improve the classification logic itself
    
    # Calculate intensity and context scores
    intensity = _calculate_intensity_score(density, coverage, business_count)
    context = _calculate_context_score(metro_distance_km, city)
    
    # Check if within major metro area (by distance OR city name)
    # This handles planned communities (Irvine, Reston) that have low coverage but are in major metros
    is_major_metro = False
    if metro_distance_km is not None and metro_distance_km < 50:
        # Within 50km of a major metro principal city = major metro area
        is_major_metro = True
        context = max(context, 0.6)
    elif city:
        try:
            from .regional_baselines import RegionalBaselineManager
            baseline_mgr = RegionalBaselineManager()
            city_lower = city.lower().strip()
            for metro_name in baseline_mgr.major_metros.keys():
                if metro_name.lower() == city_lower:
                    is_major_metro = True
                    context = max(context, 0.6)
                    break
        except Exception:
            pass
    
    # Apply metro proximity boost for planned communities (spacious but in major metros)
    if is_major_metro:
        # If coverage is moderate (0.10-0.18), boost intensity for planned communities
        # This ensures suburban classification for spacious planned communities in major metros
        if coverage and 0.10 <= coverage < 0.18:
            intensity = max(intensity, 0.40)  # Ensure suburban classification
        # Also boost if intensity is very low but we're in a major metro
        elif intensity < 0.30:
            intensity = max(intensity, 0.35)  # At least moderate intensity for major metro areas
    
    # Handle missing density explicitly
    if density is None:
        # If we have strong coverage/business signals, assume moderate intensity
        if coverage and coverage >= 0.22:
            intensity = max(intensity, 0.4)
        if business_count and business_count >= 75:
            intensity = max(intensity, 0.5)
    
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
    # Also catch planned communities (high context, moderate coverage) that might score lower on intensity
    if intensity >= 0.30:
        return "suburban"
    elif intensity >= 0.20 and context >= 0.4:
        return "suburban"
    elif intensity >= 0.15 and context >= 0.6:
        # Planned communities in major metros: lower intensity (spacious) but high context
        return "suburban"
    
    # exurban: low-moderate intensity
    if intensity >= 0.15:
        return "exurban"
    elif intensity >= 0.10:
        return "exurban"
    
    # rural: very low intensity
    if density and density < 450 and (coverage is None or coverage < 0.08):
        return "rural"
    
    # Default fallback when density is None
    # Use other signals to make a reasonable guess instead of "unknown"
    if density is None:
        # If we have business or coverage data, use that to classify
        if business_count is not None or coverage is not None:
            # Use the intensity score we calculated (which uses coverage/business)
            if intensity >= 0.15:
                return "exurban"
            elif intensity >= 0.10:
                return "exurban"
            elif intensity >= 0.05:
                return "rural"
            else:
                return "rural"
        # If no signals at all, default to exurban (better than unknown)
        # Most small towns without census data are exurban/rural
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
    pre_1940_pct: Optional[float] = None
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


# ============================================================================
# MULTINOMIAL REGRESSION MODEL FOR AREA TYPE CLASSIFICATION
# Data-driven classification using normalized Built Beauty features
# Source: Statistical modeling using Target Area Types and normalized features
# Method: Multinomial logistic regression (8 features, independent of Built Beauty scoring)
# ============================================================================

MULTINOMIAL_AREA_TYPE_COEFFICIENTS = {
    "exurban": {
        "intercept": 0.20761405025624194,
        "coefficients": {
            "Norm Built Cov": 0.3590586545936481,
            "Norm Type Div": -0.3115619631157194,
            "Norm Height Div": -0.2766447795166732,
            "Norm Footprint Var": -0.2590696996291898,
            "Norm Landmark": -0.2370934280893511,
            "Norm Year Built": 0.01577499531380857,
            "Norm Brick Share": -0.18937413861284594,
            "Norm Rowhouse": -0.021474180002737275,
        }
    },
    "historic_urban": {
        "intercept": 0.6914806445450764,
        "coefficients": {
            "Norm Built Cov": 0.020289523686234268,
            "Norm Type Div": 0.1592729062407413,
            "Norm Height Div": -0.13220763939436003,
            "Norm Footprint Var": -0.12800627087300052,
            "Norm Landmark": 1.3315674582072535,
            "Norm Year Built": -0.12099243183682491,
            "Norm Brick Share": 0.6980389363234232,
            "Norm Rowhouse": -0.017140960595401198,
        }
    },
    "rural": {
        "intercept": -0.8348309204849941,
        "coefficients": {
            "Norm Built Cov": -0.31387392860898457,
            "Norm Type Div": 0.46153392817709175,
            "Norm Height Div": 0.28145598925730713,
            "Norm Footprint Var": 0.45814393487553254,
            "Norm Landmark": -0.19819514865300725,
            "Norm Year Built": 0.4113015309298016,
            "Norm Brick Share": 0.06862705290186479,
            "Norm Rowhouse": 0.08153023750915208,
        }
    },
    "suburban": {
        "intercept": 0.933302707412065,
        "coefficients": {
            "Norm Built Cov": 0.3783281292212452,
            "Norm Type Div": 0.3763232115736111,
            "Norm Height Div": -0.07761092769097764,
            "Norm Footprint Var": -0.15678112903848674,
            "Norm Landmark": -0.050653919033229545,
            "Norm Year Built": 0.032920229711637355,
            "Norm Brick Share": -0.3188935163798173,
            "Norm Rowhouse": -0.10679403459775803,
        }
    },
    "urban_core": {
        "intercept": -0.4024504113915743,
        "coefficients": {
            "Norm Built Cov": 0.503502527902884,
            "Norm Type Div": -0.3142197350669519,
            "Norm Height Div": 0.06811726226017253,
            "Norm Footprint Var": 0.21608310198742707,
            "Norm Landmark": -0.15318717007103323,
            "Norm Year Built": -0.07395833581147823,
            "Norm Brick Share": -0.17736691312343665,
            "Norm Rowhouse": -0.06406004803009237,
        }
    },
    "urban_core_lowrise": {
        "intercept": -0.8750944244875635,
        "coefficients": {
            "Norm Built Cov": -0.9823934820644601,
            "Norm Type Div": 0.6683892937428421,
            "Norm Height Div": -0.6819633143108803,
            "Norm Footprint Var": -0.23117086282771,
            "Norm Landmark": -0.11727739137567907,
            "Norm Year Built": -0.16291977268409908,
            "Norm Brick Share": -0.12362125252289846,
            "Norm Rowhouse": 0.2569813611254871,
        }
    },
    "urban_residential": {
        "intercept": 0.27997835415074795,
        "coefficients": {
            "Norm Built Cov": 0.2119219624687688,
            "Norm Type Div": -0.503827181413187,
            "Norm Height Div": 0.031651517289995046,
            "Norm Footprint Var": 0.23979929346426093,
            "Norm Landmark": 0.6326910200126681,
            "Norm Year Built": -0.09852647004872206,
            "Norm Brick Share": -0.1012760498589381,
            "Norm Rowhouse": 0.5718355805910625,
        }
    },
}


def _normalize_features_for_classification(
    built_coverage_ratio: Optional[float],
    building_type_diversity: Optional[float],
    levels_entropy: Optional[float],
    footprint_area_cv: Optional[float],
    historic_landmarks: Optional[int],
    median_year_built: Optional[int],
    material_profile: Optional[Dict[str, Any]],
    rowhouse_indicator: float = 0.0
) -> Dict[str, float]:
    """
    Normalize features for multinomial regression area type classification.
    
    Normalizes 8 features to 0-1 range for use with multinomial regression model.
    All features are available early (independent of Built Beauty scoring).
    
    Args:
        built_coverage_ratio: Building coverage ratio (0.0-1.0)
        building_type_diversity: Building type diversity (0-100)
        levels_entropy: Height diversity (0-100)
        footprint_area_cv: Footprint coefficient of variation (0-100)
        historic_landmarks: Count of historic landmarks
        median_year_built: Median year buildings were built
        material_profile: Material profile dict with brick share
        rowhouse_indicator: Rowhouse indicator (0.0-1.0)
    
    Returns:
        Dict of normalized feature values (0-1 range)
    """
    def _clamp01(value: float) -> float:
        return max(0.0, min(1.0, value))
    
    normalized = {}
    
    # Norm Built Cov: built_coverage_ratio (0.0-1.0) → already normalized
    normalized["Norm Built Cov"] = _clamp01(built_coverage_ratio if built_coverage_ratio is not None else 0.0)
    
    # Norm Type Div: building_type_diversity (0-100) → 0-1
    normalized["Norm Type Div"] = _clamp01(building_type_diversity / 100.0 if building_type_diversity is not None else 0.0)
    
    # Norm Height Div: levels_entropy (0-100) → 0-1
    normalized["Norm Height Div"] = _clamp01(levels_entropy / 100.0 if levels_entropy is not None else 0.0)
    
    # Norm Footprint Var: footprint_area_cv (0-100) → 0-1
    normalized["Norm Footprint Var"] = _clamp01(footprint_area_cv / 100.0 if footprint_area_cv is not None else 0.0)
    
    # Norm Landmark: historic_landmarks count → 0-1 (normalize 0-20 landmarks)
    normalized["Norm Landmark"] = _clamp01((historic_landmarks or 0) / 20.0)
    
    # Norm Year Built: median_year_built → 0-1 (inverted: older = higher)
    # Normalize: 0 years old (2024) = 0.0, 224 years old (1800) = 1.0
    if median_year_built is not None:
        from datetime import datetime
        current_year = datetime.utcnow().year
        age_years = max(0.0, current_year - median_year_built)
        normalized["Norm Year Built"] = _clamp01(age_years / 224.0)
    else:
        normalized["Norm Year Built"] = 0.0
    
    # Norm Brick Share: extract from material_profile
    brick_share = 0.0
    if material_profile and isinstance(material_profile, dict):
        materials = material_profile.get("materials", {})
        if isinstance(materials, dict):
            total_tagged = sum(materials.values())
            if total_tagged > 0:
                brick_count = materials.get("brick", 0) + materials.get("stone", 0)  # Stone often similar aesthetic
                brick_share = brick_count / total_tagged
    normalized["Norm Brick Share"] = _clamp01(brick_share)
    
    # Norm Rowhouse: rowhouse_indicator (0.0-1.0) → already normalized
    normalized["Norm Rowhouse"] = _clamp01(rowhouse_indicator)
    
    return normalized


def predict_area_type_with_multinomial(
    normalized_features: Dict[str, float]
) -> Tuple[str, Dict[str, float]]:
    """
    Predict area type using multinomial logistic regression.
    
    This is a data-driven alternative to rule-based classification.
    Uses normalized features (8 features, independent of Built Beauty scoring).
    
    Args:
        normalized_features: Dict of normalized feature values (0-1 range)
            Required keys: All 8 feature names from MULTINOMIAL_AREA_TYPE_COEFFICIENTS
    
    Returns:
        Tuple of (predicted_area_type, class_probabilities_dict)
    """
    # Compute logits for each class
    logits = {}
    for class_name, class_data in MULTINOMIAL_AREA_TYPE_COEFFICIENTS.items():
        intercept = class_data["intercept"]
        coefficients = class_data["coefficients"]
        
        # Compute: intercept + sum(coefficient * feature)
        logit = intercept
        for feature_name, coefficient in coefficients.items():
            feature_value = normalized_features.get(feature_name, 0.0)
            logit += coefficient * feature_value
        
        logits[class_name] = logit
    
    # Apply softmax to get probabilities
    # Softmax: exp(logit) / sum(exp(logit) for all classes)
    max_logit = max(logits.values())
    exp_logits = {k: math.exp(v - max_logit) for k, v in logits.items()}  # Subtract max for numerical stability
    sum_exp = sum(exp_logits.values())
    probabilities = {k: v / sum_exp for k, v in exp_logits.items()}
    
    # Return class with highest probability
    predicted_class = max(probabilities.items(), key=lambda x: x[1])[0]
    
    return predicted_class, probabilities


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


def _compute_rowhouse_indicator(
    levels_entropy: Optional[float],
    building_type_diversity: Optional[float],
    footprint_area_cv: Optional[float]
) -> float:
    """
    Compute rowhouse indicator (0.0-1.0) from architectural diversity metrics.
    
    Rowhouse districts have uniform architecture with consistent footprints.
    Based on get_contextual_tags() logic for rowhouse detection.
    
    Args:
        levels_entropy: Height diversity (0-100)
        building_type_diversity: Type diversity (0-100)
        footprint_area_cv: Footprint coefficient of variation (0-100)
    
    Returns:
        Rowhouse indicator (0.0-1.0)
    """
    if levels_entropy is None or building_type_diversity is None:
        return 0.0
    
    # Check for consistent footprint pattern (low CV = uniform sizes)
    if footprint_area_cv is not None and footprint_area_cv < 50:
        if levels_entropy < 20 and building_type_diversity < 35:
            return 1.0
    
    # Also check if very uniform (very low diversity) even without footprint data
    if levels_entropy < 15 and building_type_diversity < 25:
        return 0.8  # High confidence but slightly lower without footprint confirmation
    
    return 0.0


def get_effective_area_type(
    area_type: str,
    density: Optional[float],
    levels_entropy: Optional[float] = None,
    building_type_diversity: Optional[float] = None,
    historic_landmarks: Optional[int] = None,
    median_year_built: Optional[int] = None,
    built_coverage_ratio: Optional[float] = None,
    footprint_area_cv: Optional[float] = None,
    business_count: Optional[int] = None,
    pre_1940_pct: Optional[float] = None,
    material_profile: Optional[Dict[str, Any]] = None,
    use_multinomial: bool = True
) -> str:
    """
    Determine effective area type using multinomial logistic regression.
    
    **NEW SYSTEM (use_multinomial=True, default):** Uses data-driven multinomial regression
    model trained on normalized Built Beauty features. This replaces rule-based mapping
    with statistical modeling per DESIGN_PRINCIPLES.md Addendum.
    
    **FALLBACK SYSTEM (use_multinomial=False):** Uses rule-based tag mapping for backward
    compatibility when features are missing.
    
    The multinomial model predicts effective types directly:
    - urban_core, suburban, exurban, rural (base types)
    - historic_urban, urban_core_lowrise, urban_residential (architectural subtypes)
    
    Args:
        area_type: Base area type from detect_area_type() ('urban_core', 'suburban', etc.)
        density: Population density (people/km²)
        levels_entropy: Optional height diversity metric (0-100)
        building_type_diversity: Optional type diversity metric (0-100)
        historic_landmarks: Optional count of historic landmarks from OSM
        median_year_built: Optional median year buildings were built
        built_coverage_ratio: Optional coverage ratio (0.0-1.0)
        footprint_area_cv: Optional coefficient of variation for building footprints (0-100)
        business_count: Optional business count (for mixed-use tag)
        pre_1940_pct: Optional pre-1940 percentage (for historic detection)
        material_profile: Optional material profile dict (for brick share)
        use_multinomial: If True (default), use multinomial regression model
    
    Returns:
        Effective area type string:
        - 'urban_core', 'suburban', 'exurban', 'rural' (base types)
        - 'historic_urban', 'urban_core_lowrise', 'urban_residential' (architectural subtypes)
    """
    # MULTINOMIAL REGRESSION SYSTEM (default)
    if use_multinomial:
        # Check if we have minimum required features for multinomial regression
        # Need: built_coverage_ratio, building_type_diversity, levels_entropy, footprint_area_cv
        has_minimum_features = (
            built_coverage_ratio is not None and
            building_type_diversity is not None and
            levels_entropy is not None and
            footprint_area_cv is not None
        )
        
        if has_minimum_features:
            try:
                # Compute rowhouse indicator
                rowhouse_indicator = _compute_rowhouse_indicator(
                    levels_entropy,
                    building_type_diversity,
                    footprint_area_cv
                )
                
                # Normalize features
                normalized_features = _normalize_features_for_classification(
                    built_coverage_ratio,
                    building_type_diversity,
                    levels_entropy,
                    footprint_area_cv,
                    historic_landmarks,
                    median_year_built,
                    material_profile,
                    rowhouse_indicator
                )
                
                # Predict using multinomial regression
                predicted_type, probabilities = predict_area_type_with_multinomial(normalized_features)
                
                logger.debug(
                    f"Multinomial regression predicted: {predicted_type} "
                    f"(probabilities: {probabilities})"
                )
                
                return predicted_type
                
            except Exception as e:
                logger.warning(f"Multinomial regression failed, using fallback: {e}")
                # Fall through to fallback system
    
    # FALLBACK SYSTEM: Use rule-based tag mapping (backward compatibility)
    tags = get_contextual_tags(
        area_type, density, built_coverage_ratio, median_year_built,
        historic_landmarks, business_count, levels_entropy,
        building_type_diversity, footprint_area_cv, pre_1940_pct
    )
    
    # Map tags to legacy effective types for backward compatibility
    if 'historic' in tags and area_type in ('urban_core', 'urban_residential'):
        if 'rowhouse' in tags or 'uniform' in tags:
            return "urban_residential"
        else:
            return "historic_urban"
    elif 'lowrise' in tags and area_type == 'urban_core':
        return "urban_core_lowrise"
    elif 'rowhouse' in tags and area_type == 'urban_core':
        return "urban_residential"
    
    # No special tags, return base type
    return area_type


def get_form_context(
    area_type: str,
    density: Optional[float],
    levels_entropy: Optional[float] = None,
    building_type_diversity: Optional[float] = None,
    historic_landmarks: Optional[int] = None,
    median_year_built: Optional[int] = None,
    built_coverage_ratio: Optional[float] = None,
    footprint_area_cv: Optional[float] = None,
    business_count: Optional[int] = None,
    pre_1940_pct: Optional[float] = None,
    material_profile: Optional[Dict[str, Any]] = None,
    use_multinomial: bool = True
) -> Optional[str]:
    """
    Get form context for beauty pillars (architectural classification).
    
    This is computed once and shared by built_beauty, natural_beauty, and neighborhood_beauty.
    Returns None if beauty pillars are not requested (no architectural features needed).
    
    Args:
        area_type: Base morphological area type
        density: Population density
        levels_entropy: Optional height diversity metric
        building_type_diversity: Optional type diversity metric
        historic_landmarks: Optional count of historic landmarks
        median_year_built: Optional median year buildings were built
        built_coverage_ratio: Optional coverage ratio
        footprint_area_cv: Optional footprint coefficient of variation
        business_count: Optional business count
        pre_1940_pct: Optional pre-1940 percentage
        material_profile: Optional material profile dict
        use_multinomial: If True, use multinomial regression model
    
    Returns:
        Form context string (e.g., 'historic_urban', 'urban_core_lowrise', 'urban_residential')
        or None if architectural features are not available
    """
    # Use get_effective_area_type() which handles multinomial regression
    return get_effective_area_type(
        area_type,
        density,
        levels_entropy=levels_entropy,
        building_type_diversity=building_type_diversity,
        historic_landmarks=historic_landmarks,
        median_year_built=median_year_built,
        built_coverage_ratio=built_coverage_ratio,
        footprint_area_cv=footprint_area_cv,
        business_count=business_count,
        pre_1940_pct=pre_1940_pct,
        material_profile=material_profile,
        use_multinomial=use_multinomial
    )


def get_baseline_context(
    area_type: str,
    form_context: Optional[str],
    pillar_name: str,
    **pillar_specific_data
) -> str:
    """
    Get pillar-specific baseline context for expectation table lookup.
    
    This maps area_type + form_context to a baseline context key that exists
    in the expectation tables. Different pillars may map the same area_type
    to different baseline contexts based on their specific needs.
    
    Args:
        area_type: Base morphological area type (always consistent)
        form_context: Optional form context from beauty pillars (e.g., 'historic_urban')
        pillar_name: Name of the pillar requesting the context
        **pillar_specific_data: Pillar-specific data (e.g., has_heavy_rail for transit)
    
    Returns:
        Baseline context string from ALLOWED_BASELINE_CONTEXTS
    """
    # Pillar-specific mappings
    if pillar_name == 'active_outdoors':
        if form_context == 'historic_urban':
            return 'urban_core'
        elif form_context == 'urban_core_lowrise':
            return 'suburban'
        elif form_context == 'urban_residential':
            return 'suburban'
        # Default: use area_type if it's in allowed set
        return area_type if area_type in ALLOWED_BASELINE_CONTEXTS else 'suburban'
    
    elif pillar_name == 'public_transit_access':
        # Map historic_urban to urban_residential for transit expectations
        if form_context == 'historic_urban':
            return 'urban_residential'
        
        # Dynamic detection for commuter_rail_suburb
        if area_type == 'suburban' and pillar_specific_data.get('has_heavy_rail'):
            # Additional checks: within 50km of major metro (pop > 2M)
            # These checks are done in the pillar itself before calling this function
            return 'commuter_rail_suburb'
        
        # Default: use area_type if it's in allowed set
        return area_type if area_type in ALLOWED_BASELINE_CONTEXTS else 'suburban'
    
    elif pillar_name in ('built_beauty', 'natural_beauty', 'neighborhood_beauty'):
        # Beauty pillars use form_context directly (if available) or area_type
        # But form_context values like 'historic_urban' are not in ALLOWED_BASELINE_CONTEXTS
        # So we need to map them back to base types for expectation lookups
        # Actually, beauty pillars don't use baseline contexts for expectations
        # They use form_context for normalization/calibration
        # Return area_type as fallback (beauty pillars may not need baseline_context)
        return area_type if area_type in ALLOWED_BASELINE_CONTEXTS else 'suburban'
    
    else:
        # Other pillars (healthcare_access, neighborhood_amenities, etc.)
        # Use area_type directly
        return area_type if area_type in ALLOWED_BASELINE_CONTEXTS else 'suburban'
    
    # Validation: ensure we always return a valid baseline context
    # (This should never be reached due to the return statements above, but added for safety)
    if area_type in ALLOWED_BASELINE_CONTEXTS:
        return area_type
    else:
        logger.warning(
            f"Invalid baseline_context computed for pillar '{pillar_name}', "
            f"falling back to 'suburban'. area_type={area_type}, form_context={form_context}"
        )
        return 'suburban'


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
        elif pillar_name == 'built_beauty':
            return self._assess_built_beauty_completeness(data, expected_minimums)
        elif pillar_name == 'natural_beauty':
            return self._assess_natural_beauty_completeness(data, expected_minimums)
        elif pillar_name == 'public_transit_access':
            return self._assess_transit_completeness(data, expected_minimums)
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
    
    def _assess_built_beauty_completeness(self, data: Dict, expected: Dict) -> Tuple[float, str]:
        """Assess built beauty data completeness."""
        arch_analysis = data.get('architectural_analysis', {})
        enhancers = data.get('enhancers', {})
        
        if not arch_analysis:
            return 0.0, 'very_poor'
        
        # Check for key architectural metrics
        has_score = 'score' in arch_analysis
        has_metrics = bool(arch_analysis.get('metrics', {}))
        has_classification = 'classification' in arch_analysis
        has_confidence = 'confidence_0_1' in arch_analysis
        
        # Check for enhancer data
        has_enhancers = bool(enhancers)
        
        # Calculate completeness: architectural analysis is primary (80%), enhancers secondary (20%)
        arch_score = sum([has_score, has_metrics, has_classification, has_confidence]) / 4.0
        enhancer_score = 1.0 if has_enhancers else 0.0
        
        completeness = (arch_score * 0.8) + (enhancer_score * 0.2)
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
    
    # Validation: Ensure quality_tier is always a string
    valid_tiers = ['excellent', 'good', 'fair', 'poor', 'very_poor']
    if not isinstance(quality_tier, str) or quality_tier not in valid_tiers:
        logger.warning(f"Invalid quality_tier '{quality_tier}' (type: {type(quality_tier)}), defaulting to 'fair'")
        quality_tier = 'fair'
    
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
