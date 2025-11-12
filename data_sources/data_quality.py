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
    Detect area type using multi-factor classification:
    1. "Downtown" keyword check
    2. Distance to principal city + density (geographic relationship)
    3. Business density (high = urban core)
    4. Building coverage (high = urban core)
    5. Population density with city-size adjusted thresholds
    6. Standard density thresholds (fallback)
    
    Uses multi-factor approach: distance alone doesn't determine classification - density is required.
    Reference: Bureau of Justice Statistics and Esri Urbanicity criteria use density thresholds
    (>3,000 to >5,000 housing units/sq mi or equivalent people/sq mi) combined with principal city status.
    
    Args:
        lat, lon: Coordinates
        density: Optional pre-fetched density (for efficiency)
        city: Optional city name (used to identify major metros)
        location_input: Optional raw location input string (for "downtown" keyword check)
        business_count: Optional count of businesses in 1km radius (for business density)
        built_coverage: Optional building coverage ratio 0.0-1.0 (for building density)
        metro_distance_km: Optional distance to principal city in km (if None, will calculate)
    
    Returns:
        'urban_core', 'suburban', 'exurban', 'rural', or 'unknown'
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

    if density is None:
        density = get_population_density(lat, lon)
    
    # Get distance to principal city if not provided
    if metro_distance_km is None:
        try:
            from .regional_baselines import RegionalBaselineManager
            baseline_mgr = RegionalBaselineManager()
            metro_distance_km = baseline_mgr.get_distance_to_principal_city(lat, lon, city)
        except Exception:
            metro_distance_km = None
    
    # City-specific overrides for master-planned metros
    city_key = (city or "").lower().strip() if city else ""
    if city_key == "irvine" or (normalized_location and "irvine" in normalized_location):
        return _finalize("suburban")

    # Factor 1: "Downtown" keyword check = urban core
    # Even if density is low, downtown areas are urban cores
    if location_input and "downtown" in location_input.lower():
        if density and density > 2000:
            return _finalize("urban_core")
        elif density:
            # Even low density downtowns are urban cores (commercial districts)
            return _finalize("urban_core")
    
    # Factor 2: Distance to principal city + density (geographic relationship)
    # Multi-factor approach: distance alone doesn't determine classification - density is required
    # Handles edge cases like large low-density principal cities (e.g., Jacksonville, FL)
    if metro_distance_km is not None and density is not None:
        # Very close to principal city (<10km) + high density = urban_core
        # Examples: Hoboken (2km from NYC), Jersey City (5km from NYC), Santa Monica (15km from LA)
        if metro_distance_km < 10.0:
            if density > 5000:
                return _finalize("urban_core")  # High density + very close = urban extension
            elif density > 2500:
                return _finalize("urban_core")  # Moderate-high density + very close = urban vicinity
            elif density < 2500:
                # Low density even if close = exurban/rural (handles large low-density cities)
                if density > 1000:
                    return _finalize("exurban")
                else:
                    return _finalize("rural")
        
        # Close to principal city (10-20km) + high density = urban_core or suburban
        # Examples: Santa Monica (15km from LA) should be urban_core
        elif metro_distance_km < 20.0:
            if density > 5000:
                return _finalize("urban_core")  # High density + close = functional urban core
            elif density > 2500:
                return _finalize("suburban")  # Moderate density + close = suburban
            elif density > 1000:
                return _finalize("exurban")
            else:
                return _finalize("rural")
        
        # Medium distance (20-30km) + high density = suburban
        # Examples: Manhattan Beach (25km from LA) should be suburban
        elif metro_distance_km < 30.0:
            if density > 5000:
                return _finalize("suburban")  # High density but medium distance = suburban
            elif density > 2500:
                return _finalize("suburban")
            elif density > 1000:
                return _finalize("exurban")
            else:
                return _finalize("rural")
        
        # Far from principal city (30-50km) = suburban/exurban
        elif metro_distance_km < 50.0:
            if density > 2500:
                return _finalize("suburban")
            elif density > 1000:
                return _finalize("exurban")
            else:
                return _finalize("rural")
    
    # Factor 3: High business density = urban core (downtown/commercial district)
    # 150+ businesses in 1km = clearly downtown/urban core
    if business_count is not None and business_count > 150:
        return _finalize("urban_core")
    # 75-150 businesses = likely urban core, but check density
    elif business_count is not None and business_count > 75:
        if density and density > 2000:
            return _finalize("urban_core")
    
    # Factor 4: High building coverage = urban core (deprioritized for distance-based classification)
    # 20%+ building coverage = dense urban form
    # NOTE: This can misclassify beach towns - distance to principal city should take priority
    # Only apply if distance factor didn't already classify (i.e., metro_distance_km was None)
    # AND location is close to principal city (<=25km) OR no metro detected
    if built_coverage is not None and built_coverage > 0.20:
        # Only apply if distance factor didn't classify (metro_distance_km was None)
        # OR if very close to principal city (<=15km) where high building coverage is expected
        # If far from principal city (>25km), building coverage alone shouldn't make it urban_core
        if metro_distance_km is None:
            # No metro detected - use building coverage as fallback
            if density and density > 2000:
                return _finalize("urban_core")
        elif metro_distance_km <= 15.0:
            # Very close to principal city - high building coverage is expected
            if density and density > 2000:
                return _finalize("urban_core")
        # If 15-25km from principal city, distance factor should have already classified
        # If >25km, building coverage alone shouldn't make it urban_core
    
    # Factor 5: City-size adjusted density thresholds
    # Check if city is a major metro (even if density is missing)
    if city:
        from .regional_baselines import RegionalBaselineManager
        baseline_mgr = RegionalBaselineManager()
        # Check if city name matches any major metro (case-insensitive)
        city_lower = city.lower().strip()
        for metro_name in baseline_mgr.major_metros.keys():
            if metro_name.lower() == city_lower:
                # Major metros: lower threshold for urban core
                if density and density > 2500:
                    return _finalize("urban_core")
                elif density and density > 2000 and business_count and business_count > 50:
                    # Major metro with moderate density + businesses = urban core
                    return _finalize("urban_core")
                elif not density:
                    return _finalize("urban_core")  # Major city, assume urban_core even without density data
                else:
                    return _finalize("urban_core")  # Major city, low density but still urban core
    
    # Factor 6: Standard density thresholds (for non-major metros)
    # If density is missing and not a major city, return unknown
    if not density:
        return _finalize("unknown")
    
    # Urban core: >10,000 people/sq mi (e.g., Manhattan, Brooklyn)
    # But check business density first - dense suburbs can have high density but lower business density
    density_val = density or 0.0
    business = business_count or 0
    coverage = built_coverage
    metro_val = metro_distance_km if metro_distance_km is not None else float("inf")

    if density_val > 10000:
        result = "urban_core" if business > 75 else "suburban"
    elif density_val > 2500:
        result = "urban_core" if business > 100 else "suburban"
    elif density_val > 500:
        result = "exurban"
    else:
        result = "rural"

    # --- Post-classification refinements (deterministic, signal-based) ---
    if coverage is not None:
        dense_core_high = 0.24
        dense_core_low = 0.20
        leafy_low_high = 0.12
        leafy_low_low = 0.10
        metro_close = 12.0
        metro_far = 18.0

        # Dense, uniform grids that lack heavy commercial presence → urban_residential
        if result in ("urban_core", "historic_urban"):
            if coverage >= dense_core_high and business < 120 and density_val < 9000:
                result = "urban_residential"
            elif coverage >= dense_core_low and business < 80 and density_val < 7500:
                result = "urban_residential"

        # Leafy low-coverage suburbs beyond the core → exurban
        if result == "suburban":
            if coverage <= leafy_low_low and metro_val > metro_far and density_val < 2000:
                result = "exurban"
            elif coverage <= leafy_low_high and metro_val > (metro_far + 2.0) and density_val < 1600:
                result = "exurban"

        # Dense coastal/commercial strips near the core → urban_core
        if result == "suburban":
            if coverage >= dense_core_high and (metro_val <= metro_close or business >= 140):
                result = "urban_core"
            elif coverage >= dense_core_low and (metro_val <= (metro_close + 3.0) or business >= 180):
                result = "urban_core"

        # Historic low-coverage districts: very low coverage, moderate density, near core
        if coverage <= 0.08:
            density_ok = (600 <= density_val <= 8000) if density_val else True
            metro_ok = (metro_distance_km is not None) and (metro_val <= 25.0)
            business_ok = business <= 150
            if density_ok and metro_ok and business_ok:
                result = "historic_urban"
        elif result in ("suburban", "exurban") and 0.09 <= coverage <= 0.13:
            density_ok = (600 <= density_val <= 6000) if density_val else True
            metro_ok = (metro_distance_km is not None) and (metro_val <= 15.0)
            business_ok = business <= 120
            if density_ok and metro_ok and business_ok:
                result = "historic_urban"

    return _finalize(result)


def get_effective_area_type(area_type: str, density: Optional[float],
                           levels_entropy: Optional[float] = None,
                           building_type_diversity: Optional[float] = None,
                           historic_landmarks: Optional[int] = None,
                           median_year_built: Optional[int] = None,
                           built_coverage_ratio: Optional[float] = None) -> str:
    """
    Determine effective area type including architectural subtypes.
    
    This function handles architectural beauty-specific subtypes:
    - urban_residential: Dense urban core with uniform architecture (Park Slope brownstones)
    - historic_urban: Organic diversity historic neighborhoods (Greenwich Village, Georgetown)
    - urban_core_lowrise: Dense urban but not skyscraper dense (Santa Barbara, Old Town Alexandria)
    
    Priority order (first match wins):
    1. urban_residential (dense + uniform)
    2. historic_urban (historic + organic diversity)
    3. urban_core_lowrise (dense + moderate diversity)
    4. Original area_type
    
    Args:
        area_type: Base area type from detect_area_type() ('urban_core', 'suburban', etc.)
        density: Population density (people/km²)
        levels_entropy: Optional height diversity metric (for subtype detection)
        building_type_diversity: Optional type diversity metric (for subtype detection)
        historic_landmarks: Optional count of historic landmarks from OSM
        median_year_built: Optional median year buildings were built
        built_coverage_ratio: Optional coverage ratio (0-1) to distinguish leafy historic cores
    
    Returns:
        Effective area type, which may be:
        - 'urban_residential': Dense + uniform architecture
        - 'historic_urban': Historic + organic diversity (moderate variation)
        - 'urban_core_lowrise': Dense + moderate diversity (not uniform)
        - Original area_type: Otherwise
    """
    effective = area_type
    
    # Helper: Check if area is historic
    def is_historic() -> bool:
        if historic_landmarks is not None and historic_landmarks >= 10:
            return True
        if median_year_built is not None and median_year_built < 1950:
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
            # Prioritize Census data for historic detection (more stable than OSM landmarks)
            census_historic = median_year_built is not None and median_year_built < 1950
            
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
                if (10 < levels_entropy < 70 and 20 < building_type_diversity < 85):
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
