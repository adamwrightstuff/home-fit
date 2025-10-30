"""
Data Quality Detection and Fallback System
Provides tiered fallback mechanisms and data completeness scoring
"""

import math
from typing import Dict, List, Tuple, Optional, Any
from .census_api import get_population_density, get_census_tract
from .error_handling import get_fallback_score


def detect_area_type(lat: float, lon: float, density: Optional[float] = None) -> str:
    """
    Detect area type based on population density.
    
    Args:
        lat, lon: Coordinates
        density: Optional pre-fetched density (for efficiency)
    
    Returns:
        'urban_core', 'suburban', 'exurban', 'rural', or 'unknown'
    """
    if density is None:
        density = get_population_density(lat, lon)
    
    if not density:
        return "unknown"
    
    # Urban core: >10,000 people/sq mi (e.g., Manhattan, Brooklyn)
    if density > 10000:
        return "urban_core"
    # Suburban: 2,500-10,000 people/sq mi (e.g., Westchester, Long Island suburbs)
    elif density > 2500:
        return "suburban"
    # Exurban: 500-2,500 people/sq mi (e.g., outer suburbs)
    elif density > 500:
        return "exurban"
    # Rural: <500 people/sq mi (e.g., rural towns, Marfa TX)
    else:
        return "rural"


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
    """Manages data quality assessment and fallback strategies."""
    
    # Major metro centers for transit fallback
    MAJOR_METROS = {
        "New York": (40.7128, -74.0060),
        "Los Angeles": (34.0522, -118.2437),
        "Chicago": (41.8781, -87.6298),
        "Houston": (29.7604, -95.3698),
        "Phoenix": (33.4484, -112.0740),
        "Philadelphia": (39.9526, -75.1652),
        "San Diego": (32.7157, -117.1611),
        "Dallas": (32.7767, -96.7970),
        "San Jose": (37.3382, -121.8863),
        "Austin": (30.2672, -97.7431),
        "San Francisco": (37.7749, -122.4194),
        "Columbus": (39.9612, -82.9988),
        "Seattle": (47.6062, -122.3321),
        "Boston": (42.3601, -71.0589),
        "Miami": (25.7617, -80.1918),
        "Portland": (45.5152, -122.6784),
        "Denver": (39.7392, -104.9903),
        "Atlanta": (33.7490, -84.3880),
    }
    
    def __init__(self):
        self.quality_thresholds = {
            'excellent': 0.9,    # 90%+ data completeness
            'good': 0.7,         # 70-89% data completeness  
            'fair': 0.5,         # 50-69% data completeness
            'poor': 0.3,         # 30-49% data completeness
            'very_poor': 0.0     # <30% data completeness
        }
    
    def _get_base_scores(self) -> Dict:
        """Get base fallback scores by area type."""
        return {
            'urban_core': {
                'active_outdoors': 60,
                'healthcare_access': 70,
                'air_travel_access': 80,
                'neighborhood_amenities': 75,
                'neighborhood_beauty': 50,
                'public_transit_access': 65,
                'quality_education': 60,
                'housing_value': 40
            },
            'suburban': {
                'active_outdoors': 50,
                'healthcare_access': 60,
                'air_travel_access': 60,
                'neighborhood_amenities': 45,
                'neighborhood_beauty': 55,
                'public_transit_access': 40,
                'quality_education': 65,
                'housing_value': 60
            },
            'exurban': {
                'active_outdoors': 40,
                'healthcare_access': 45,
                'air_travel_access': 30,
                'neighborhood_amenities': 25,
                'neighborhood_beauty': 60,
                'public_transit_access': 20,
                'quality_education': 55,
                'housing_value': 70
            },
            'rural': {
                'active_outdoors': 30,
                'healthcare_access': 30,
                'air_travel_access': 20,
                'neighborhood_amenities': 15,
                'neighborhood_beauty': 70,
                'public_transit_access': 10,
                'quality_education': 45,
                'housing_value': 80
            }
        }
    
    def _find_nearest_metro(self, lat: float, lon: float) -> float:
        """Find distance to nearest major metro center in kilometers."""
        min_distance = float('inf')
        
        for metro_name, (metro_lat, metro_lon) in self.MAJOR_METROS.items():
            distance = self._haversine_distance(lat, lon, metro_lat, metro_lon)
            min_distance = min(min_distance, distance)
        
        return min_distance
    
    def _haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance between two points in kilometers."""
        R = 6371  # Earth radius in km
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)
        
        a = math.sin(delta_phi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        return R * c
    
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
    
    def get_fallback_strategy(self, pillar_name: str, quality_tier: str, 
                            area_type: str, lat: Optional[float] = None, 
                            lon: Optional[float] = None) -> Tuple[float, Dict]:
        """
        Get fallback strategy based on data quality and area type.
        
        Args:
            pillar_name: Name of the pillar
            quality_tier: Quality assessment result
            area_type: Area classification
            lat, lon: Optional coordinates for metro proximity checks
        
        Returns:
            Tuple of (fallback_score, fallback_metadata)
        """
        # Special handling for transit pillar with metro proximity
        if pillar_name == 'public_transit_access' and quality_tier == 'very_poor' and lat and lon:
            metro_dist = self._find_nearest_metro(lat, lon)
            
            if metro_dist < 30:  # km
                fallback_score = 40.0
                reason = f"Within {metro_dist:.0f}km of major metro"
            elif metro_dist < 50:
                fallback_score = 30.0
                reason = f"Within {metro_dist:.0f}km of major metro"
            else:
                # Use standard suburban fallback
                base_scores = self._get_base_scores()
                base_score = base_scores.get(area_type, {}).get(pillar_name, 40)
                fallback_score = base_score * 0.6
                reason = "Standard suburban fallback"
            
            return fallback_score, {
                'fallback_used': True,
                'quality_tier': quality_tier,
                'area_type': area_type,
                'metro_distance_km': round(metro_dist, 1),
                'reason': reason
            }
        
        # Base fallback scores by area type
        base_scores = self._get_base_scores()
        
        # Adjust based on quality tier
        quality_adjustments = {
            'excellent': 1.0,
            'good': 0.9,
            'fair': 0.8,
            'poor': 0.7,
            'very_poor': 0.6
        }
        
        base_score = base_scores.get(area_type, {}).get(pillar_name, 50)
        adjustment = quality_adjustments.get(quality_tier, 0.6)
        
        fallback_score = base_score * adjustment
        
        metadata = {
            'fallback_used': True,
            'quality_tier': quality_tier,
            'area_type': area_type,
            'base_score': base_score,
            'adjustment_factor': adjustment,
            'reason': f'Data quality {quality_tier} in {area_type} area'
        }
        
        return fallback_score, metadata
    
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
    
    # Determine if fallback is needed
    needs_fallback = quality_tier in ['poor', 'very_poor']
    
    if needs_fallback:
        fallback_score, fallback_metadata = data_quality_manager.get_fallback_strategy(
            pillar_name, quality_tier, area_type, lat=lat, lon=lon
        )
    else:
        fallback_score = None
        fallback_metadata = {'fallback_used': False}
    
    # Create confidence score
    data_sources = ['osm'] if data else ['fallback']
    confidence = data_quality_manager.create_confidence_score(
        completeness, data_sources, needs_fallback
    )
    
    return {
        'completeness': completeness,
        'quality_tier': quality_tier,
        'needs_fallback': needs_fallback,  # Indicates data quality; actual score uses real data when available
        'fallback_score': fallback_score,  # Only used if actual data unavailable; shown for transparency
        'fallback_metadata': fallback_metadata,
        'confidence': confidence,
        'expected_minimums': expected_minimums,
        'data_sources': data_sources
    }
