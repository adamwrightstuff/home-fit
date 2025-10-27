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


class DataQualityManager:
    """Manages data quality assessment and fallback strategies."""
    
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
        elif pillar_name == 'walkable_town':
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
        # Check for tree data and historic data
        charm_data = data.get('charm_data', {})
        year_built_data = data.get('year_built_data', {})
        tree_data = data.get('tree_score', 0)
        
        # Tree data available
        tree_score = min(1.0, tree_data / 50.0) if tree_data > 0 else 0.0
        
        # Historic landmarks
        historic_count = len(charm_data.get('historic', [])) if charm_data else 0
        artwork_count = len(charm_data.get('artwork', [])) if charm_data else 0
        landmark_score = min(1.0, (historic_count + artwork_count) / 5.0)
        
        # Year built data
        year_built_score = 1.0 if year_built_data else 0.0
        
        completeness = (tree_score * 0.5) + (landmark_score * 0.3) + (year_built_score * 0.2)
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
                            area_type: str) -> Tuple[float, Dict]:
        """
        Get fallback strategy based on data quality and area type.
        
        Args:
            pillar_name: Name of the pillar
            quality_tier: Quality assessment result
            area_type: Area classification
        
        Returns:
            Tuple of (fallback_score, fallback_metadata)
        """
        # Base fallback scores by area type
        base_scores = {
            'urban_core': {
                'active_outdoors': 60,
                'healthcare_access': 70,
                'air_travel_access': 80,
                'walkable_town': 75,
                'neighborhood_beauty': 50,
                'public_transit_access': 65,
                'quality_education': 60,
                'housing_value': 40
            },
            'suburban': {
                'active_outdoors': 50,
                'healthcare_access': 60,
                'air_travel_access': 60,
                'walkable_town': 45,
                'neighborhood_beauty': 55,
                'public_transit_access': 40,
                'quality_education': 65,
                'housing_value': 60
            },
            'exurban': {
                'active_outdoors': 40,
                'healthcare_access': 45,
                'air_travel_access': 30,
                'walkable_town': 25,
                'neighborhood_beauty': 60,
                'public_transit_access': 20,
                'quality_education': 55,
                'housing_value': 70
            },
            'rural': {
                'active_outdoors': 30,
                'healthcare_access': 30,
                'air_travel_access': 20,
                'walkable_town': 15,
                'neighborhood_beauty': 70,
                'public_transit_access': 10,
                'quality_education': 45,
                'housing_value': 80
            }
        }
        
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
            pillar_name, quality_tier, area_type
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
        'needs_fallback': needs_fallback,
        'fallback_score': fallback_score,
        'fallback_metadata': fallback_metadata,
        'confidence': confidence,
        'expected_minimums': expected_minimums,
        'data_sources': data_sources
    }
