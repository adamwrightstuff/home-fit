"""
Regional Baseline Scoring System
Provides area-specific scoring adjustments based on metro area and density
"""

import json
import math
from typing import Dict, List, Tuple, Optional
from .census_api import get_population_density, get_census_tract


class RegionalBaselineManager:
    """Manages regional baseline scores and area classification."""
    
    def __init__(self):
        # Top 50 US Metropolitan Statistical Areas (MSAs) by population
        self.major_metros = {
            'New York': {'state': 'NY', 'population': 20153634, 'density_threshold': 15000},
            'Los Angeles': {'state': 'CA', 'population': 13214799, 'density_threshold': 12000},
            'Chicago': {'state': 'IL', 'population': 9522434, 'density_threshold': 10000},
            'Houston': {'state': 'TX', 'population': 7047490, 'density_threshold': 8000},
            'Phoenix': {'state': 'AZ', 'population': 4864298, 'density_threshold': 6000},
            'Philadelphia': {'state': 'PA', 'population': 6107009, 'density_threshold': 9000},
            'San Antonio': {'state': 'TX', 'population': 2553853, 'density_threshold': 4000},
            'San Diego': {'state': 'CA', 'population': 3286069, 'density_threshold': 5000},
            'Dallas': {'state': 'TX', 'population': 7614347, 'density_threshold': 7000},
            'San Jose': {'state': 'CA', 'population': 2013502, 'density_threshold': 6000},
            'Austin': {'state': 'TX', 'population': 2163051, 'density_threshold': 4000},
            'Jacksonville': {'state': 'FL', 'population': 1555038, 'density_threshold': 3000},
            'Fort Worth': {'state': 'TX', 'population': 918915, 'density_threshold': 2500},
            'Columbus': {'state': 'OH', 'population': 2103093, 'density_threshold': 3500},
            'Charlotte': {'state': 'NC', 'population': 2648654, 'density_threshold': 4000},
            'San Francisco': {'state': 'CA', 'population': 4727357, 'density_threshold': 12000},
            'Indianapolis': {'state': 'IN', 'population': 2088452, 'density_threshold': 3000},
            'Seattle': {'state': 'WA', 'population': 4017693, 'density_threshold': 6000},
            'Denver': {'state': 'CO', 'population': 2968420, 'density_threshold': 4500},
            'Washington': {'state': 'DC', 'population': 6303090, 'density_threshold': 10000},
            'Boston': {'state': 'MA', 'population': 4953275, 'density_threshold': 8000},
            'El Paso': {'state': 'TX', 'population': 868859, 'density_threshold': 2000},
            'Nashville': {'state': 'TN', 'population': 1967890, 'density_threshold': 3000},
            'Detroit': {'state': 'MI', 'population': 4322056, 'density_threshold': 5000},
            'Oklahoma City': {'state': 'OK', 'population': 1428283, 'density_threshold': 2000},
            'Portland': {'state': 'OR', 'population': 2516121, 'density_threshold': 4000},
            'Las Vegas': {'state': 'NV', 'population': 2266715, 'density_threshold': 3500},
            'Memphis': {'state': 'TN', 'population': 1356080, 'density_threshold': 2500},
            'Louisville': {'state': 'KY', 'population': 1285729, 'density_threshold': 2000},
            'Baltimore': {'state': 'MD', 'population': 2807094, 'density_threshold': 4000},
            'Milwaukee': {'state': 'WI', 'population': 1573704, 'density_threshold': 3000},
            'Albuquerque': {'state': 'NM', 'population': 918018, 'density_threshold': 2000},
            'Tucson': {'state': 'AZ', 'population': 1047279, 'density_threshold': 2000},
            'Fresno': {'state': 'CA', 'population': 1001018, 'density_threshold': 2000},
            'Sacramento': {'state': 'CA', 'population': 2333861, 'density_threshold': 3500},
            'Mesa': {'state': 'AZ', 'population': 504258, 'density_threshold': 1500},
            'Kansas City': {'state': 'MO', 'population': 2144129, 'density_threshold': 3000},
            'Atlanta': {'state': 'GA', 'population': 6106112, 'density_threshold': 6000},
            'Long Beach': {'state': 'CA', 'population': 466742, 'density_threshold': 2000},
            'Colorado Springs': {'state': 'CO', 'population': 755105, 'density_threshold': 2000},
            'Raleigh': {'state': 'NC', 'population': 1448162, 'density_threshold': 2500},
            'Miami': {'state': 'FL', 'population': 6176801, 'density_threshold': 8000},
            'Virginia Beach': {'state': 'VA', 'population': 457672, 'density_threshold': 1500},
            'Omaha': {'state': 'NE', 'population': 967604, 'density_threshold': 2000},
            'Oakland': {'state': 'CA', 'population': 433823, 'density_threshold': 2000},
            'Minneapolis': {'state': 'MN', 'population': 3640697, 'density_threshold': 5000},
            'Tulsa': {'state': 'OK', 'population': 1004428, 'density_threshold': 2000},
            'Arlington': {'state': 'TX', 'population': 394266, 'density_threshold': 2000},
            'Tampa': {'state': 'FL', 'population': 3209489, 'density_threshold': 4000},
            'New Orleans': {'state': 'LA', 'population': 1271651, 'density_threshold': 2500},
            'Wichita': {'state': 'KS', 'population': 647610, 'density_threshold': 1500}
        }
        
        # Baseline scores by area type and pillar
        self.baseline_scores = {
            'urban_core': {
                'active_outdoors': 45,      # Limited green space
                'healthcare_access': 85,    # Excellent healthcare
                'air_travel_access': 90,    # Major airports
                'neighborhood_amenities': 80,        # Dense amenities
                'neighborhood_beauty': 40,  # Urban environment
                'public_transit_access': 85, # Excellent transit
                'quality_education': 70,    # Good schools
                'housing_value': 25         # Expensive housing
            },
            'suburban': {
                'active_outdoors': 65,      # Good parks
                'healthcare_access': 75,    # Good healthcare
                'air_travel_access': 70,    # Regional airports
                'neighborhood_amenities': 50,        # Moderate amenities
                'neighborhood_beauty': 60,  # Mixed environment
                'public_transit_access': 45, # Limited transit
                'quality_education': 80,    # Excellent schools
                'housing_value': 60        # Moderate housing
            },
            'exurban': {
                'active_outdoors': 75,      # Excellent outdoor access
                'healthcare_access': 55,    # Limited healthcare
                'air_travel_access': 40,    # Limited air access
                'neighborhood_amenities': 25,        # Few amenities
                'neighborhood_beauty': 75,  # Natural beauty
                'public_transit_access': 20, # No transit
                'quality_education': 65,    # Decent schools
                'housing_value': 75        # Affordable housing
            },
            'rural': {
                'active_outdoors': 85,      # Excellent outdoor access
                'healthcare_access': 35,   # Limited healthcare
                'air_travel_access': 20,    # No air access
                'neighborhood_amenities': 10,        # No amenities
                'neighborhood_beauty': 90,  # Natural beauty
                'public_transit_access': 5, # No transit
                'quality_education': 50,    # Limited schools
                'housing_value': 90        # Very affordable
            }
        }
    
    def classify_area(self, lat: float, lon: float, city: str = None) -> Tuple[str, str, Dict]:
        """
        Classify an area by type and metro region.
        
        Args:
            lat, lon: Coordinates
            city: Optional city name for metro detection
        
        Returns:
            Tuple of (area_type, metro_name, classification_metadata)
        """
        # Get population density
        density = get_population_density(lat, lon)
        
        # Determine metro area
        metro_name = self._detect_metro_area(city, lat, lon)
        
        # Classify area type based on density
        if density and density > 10000:
            area_type = 'urban_core'
        elif density and density > 2500:
            area_type = 'suburban'
        elif density and density > 1000:
            area_type = 'exurban'
        elif density is None and metro_name:
            # Fallback: if we can detect a major metro but density is unavailable, use suburban
            metro_data = self.major_metros.get(metro_name, {})
            if metro_data:
                area_type = 'suburban'
            else:
                area_type = 'rural'
        else:
            area_type = 'rural'
        
        # Adjust for metro context
        if metro_name and area_type == 'suburban':
            # Suburbs of major metros might have higher expectations
            metro_data = self.major_metros.get(metro_name, {})
            if metro_data.get('population', 0) > 2000000:
                area_type = 'suburban_major_metro'
        
        metadata = {
            'density': density,
            'metro_name': metro_name,
            'area_type': area_type,
            'classification_confidence': self._get_classification_confidence(density, metro_name)
        }
        
        return area_type, metro_name, metadata
    
    def _detect_metro_area(self, city: str, lat: float, lon: float) -> Optional[str]:
        """Detect which major metro area the location belongs to."""
        if not city:
            return None
        
        # Simple name matching for major metros
        city_lower = city.lower()
        for metro_name, metro_data in self.major_metros.items():
            if metro_name.lower() in city_lower or city_lower in metro_name.lower():
                return metro_name
        
        # Could add more sophisticated geographic detection here
        return None
    
    def _get_classification_confidence(self, density: Optional[float], metro_name: Optional[str]) -> float:
        """Get confidence in area classification."""
        confidence = 0.5  # Base confidence
        
        if density is not None:
            confidence += 0.3  # Density data available
        
        if metro_name:
            confidence += 0.2  # Metro area identified
        
        return min(1.0, confidence)
    
    def get_baseline_scores(self, area_type: str, metro_name: Optional[str] = None) -> Dict[str, float]:
        """
        Get baseline scores for an area type.
        
        Args:
            area_type: Area classification
            metro_name: Optional metro area name for adjustments
        
        Returns:
            Dictionary of baseline scores by pillar
        """
        # Get base scores for area type
        base_scores = self.baseline_scores.get(area_type, self.baseline_scores['suburban'])
        
        # Adjust for major metro areas
        if metro_name and metro_name in self.major_metros:
            metro_data = self.major_metros[metro_name]
            population = metro_data.get('population', 0)
            
            # Major metros get slight adjustments
            if population > 5000000:  # Very large metros
                adjustments = {
                    'neighborhood_amenities': 1.1,      # More amenities
                    'public_transit_access': 1.15,  # Better transit
                    'housing_value': 0.8       # More expensive
                }
            elif population > 2000000:  # Large metros
                adjustments = {
                    'neighborhood_amenities': 1.05,
                    'public_transit_access': 1.1,
                    'housing_value': 0.9
                }
            else:
                adjustments = {}
            
            # Apply adjustments
            for pillar, adjustment in adjustments.items():
                if pillar in base_scores:
                    base_scores[pillar] = min(100, base_scores[pillar] * adjustment)
        
        return base_scores.copy()
    
    def adjust_scoring_thresholds(self, area_type: str, pillar_name: str, 
                                 base_thresholds: Dict) -> Dict:
        """
        Adjust scoring thresholds based on area type.
        
        Args:
            area_type: Area classification
            pillar_name: Name of the pillar
            base_thresholds: Base scoring thresholds
        
        Returns:
            Adjusted thresholds
        """
        adjusted = base_thresholds.copy()
        
        if area_type == 'urban_core':
            # Urban areas: higher expectations for amenities, lower for space
            if pillar_name == 'active_outdoors':
                adjusted['park_distance_threshold'] *= 0.7  # Closer parks expected
                adjusted['park_count_threshold'] *= 1.5    # More parks expected
            elif pillar_name == 'neighborhood_amenities':
                adjusted['business_count_threshold'] *= 1.5  # More businesses expected
                adjusted['variety_threshold'] *= 1.2         # More variety expected
            elif pillar_name == 'housing_value':
                adjusted['price_to_income_threshold'] *= 1.3  # Higher ratios acceptable
        
        elif area_type == 'rural':
            # Rural areas: lower expectations for amenities, higher for space
            if pillar_name == 'active_outdoors':
                adjusted['park_distance_threshold'] *= 1.5  # Further parks acceptable
                adjusted['park_count_threshold'] *= 0.5     # Fewer parks acceptable
            elif pillar_name == 'neighborhood_amenities':
                adjusted['business_count_threshold'] *= 0.3  # Fewer businesses acceptable
                adjusted['variety_threshold'] *= 0.5         # Less variety acceptable
            elif pillar_name == 'housing_value':
                adjusted['price_to_income_threshold'] *= 0.7  # Lower ratios expected
        
        return adjusted
    
    def get_contextual_expectations(self, area_type: str, pillar_name: str) -> Dict:
        """
        Get contextual expectations for scoring.
        
        Args:
            area_type: Area classification
            pillar_name: Name of the pillar
        
        Returns:
            Dictionary of contextual expectations
        """
        expectations = {
            'urban_core': {
                'active_outdoors': {
                    'expected_parks_within_1km': 3,
                    'expected_parks_within_5km': 8,
                    'expected_playgrounds_within_1km': 2,
                    'expected_water_access_within_15km': 1,
                    'expected_trails_within_15km': 2
                },
                'healthcare_access': {
                    'expected_hospitals_within_10km': 2,
                    'expected_urgent_care_within_5km': 5,
                    'expected_pharmacies_within_2km': 3
                },
                'neighborhood_amenities': {
                    'expected_businesses_within_1km': 50,
                    'expected_business_types': 12,
                    'expected_restaurants_within_1km': 15
                }
            },
            'suburban': {
                'active_outdoors': {
                    'expected_parks_within_1km': 2,
                    'expected_parks_within_5km': 5,
                    'expected_playgrounds_within_1km': 1,
                    'expected_water_access_within_15km': 1,
                    'expected_trails_within_15km': 1
                },
                'healthcare_access': {
                    'expected_hospitals_within_10km': 1,
                    'expected_urgent_care_within_5km': 3,
                    'expected_pharmacies_within_2km': 2
                },
                'neighborhood_amenities': {
                    'expected_businesses_within_1km': 25,
                    'expected_business_types': 8,
                    'expected_restaurants_within_1km': 8
                }
            },
            'exurban': {
                'active_outdoors': {
                    'expected_parks_within_1km': 1,
                    'expected_parks_within_5km': 3,
                    'expected_playgrounds_within_1km': 0,
                    'expected_water_access_within_15km': 1,
                    'expected_trails_within_15km': 1
                },
                'healthcare_access': {
                    'expected_hospitals_within_10km': 0,
                    'expected_urgent_care_within_5km': 1,
                    'expected_pharmacies_within_2km': 1
                },
                'neighborhood_amenities': {
                    'expected_businesses_within_1km': 10,
                    'expected_business_types': 4,
                    'expected_restaurants_within_1km': 3
                }
            },
            'rural': {
                'active_outdoors': {
                    'expected_parks_within_1km': 0,
                    'expected_parks_within_5km': 1,
                    'expected_playgrounds_within_1km': 0,
                    'expected_water_access_within_15km': 1,
                    'expected_trails_within_15km': 1
                },
                'healthcare_access': {
                    'expected_hospitals_within_10km': 0,
                    'expected_urgent_care_within_5km': 0,
                    'expected_pharmacies_within_2km': 0
                },
                'neighborhood_amenities': {
                    'expected_businesses_within_1km': 3,
                    'expected_business_types': 2,
                    'expected_restaurants_within_1km': 1
                }
            }
        }
        
        return expectations.get(area_type, {}).get(pillar_name, {})


# Global instance
regional_baseline_manager = RegionalBaselineManager()


def get_area_classification(lat: float, lon: float, city: str = None) -> Tuple[str, str, Dict]:
    """
    Get area classification for a location.
    
    Args:
        lat, lon: Coordinates
        city: Optional city name
    
    Returns:
        Tuple of (area_type, metro_name, metadata)
    """
    return regional_baseline_manager.classify_area(lat, lon, city)


def get_baseline_scores(area_type: str, metro_name: str = None) -> Dict[str, float]:
    """
    Get baseline scores for an area type.
    
    Args:
        area_type: Area classification
        metro_name: Optional metro area name
    
    Returns:
        Dictionary of baseline scores
    """
    return regional_baseline_manager.get_baseline_scores(area_type, metro_name)


def get_contextual_expectations(area_type: str, pillar_name: str) -> Dict:
    """
    Get contextual expectations for scoring.
    
    Args:
        area_type: Area classification
        pillar_name: Name of the pillar
    
    Returns:
        Dictionary of expectations
    """
    return regional_baseline_manager.get_contextual_expectations(area_type, pillar_name)
