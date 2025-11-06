#!/usr/bin/env python3
"""
Test classification for specific locations after principal city implementation.
"""

import sys
sys.path.insert(0, '.')

from data_sources.data_quality import detect_area_type
from data_sources import census_api, osm_api
from data_sources.regional_baselines import RegionalBaselineManager

# Test locations from user request
test_locations = [
    ("Bronxville, NY", 40.9382, -73.8321, "Village of Bronxville", "suburban"),
    ("Larchmont, NY", 40.9279, -73.7528, "Larchmont", "suburban"),
    ("Old Town Alexandria, VA", 38.8048, -77.0469, "Alexandria", "urban_core"),
    ("Georgetown, Washington DC", 38.9096, -77.0654, "Washington", "urban_core"),
    ("Redondo Beach, CA", 33.8492, -118.3883, "Redondo Beach", "suburban"),
    ("Beverly Hills, CA", 34.0736, -118.4004, "Beverly Hills", "urban_core"),
    ("Manhattan Beach, CA", 33.8877, -118.4100, "Manhattan Beach", "suburban"),
]

def test_classification():
    """Test classification for all requested locations."""
    print("="*70)
    print("Principal City Classification Test")
    print("="*70)
    
    baseline_mgr = RegionalBaselineManager()
    
    for name, lat, lon, city, expected in test_locations:
        print(f"\n📍 Testing: {name}")
        print(f"   City: {city}")
        print(f"   Coordinates: {lat}, {lon}")
        
        # Get data needed for classification
        density = census_api.get_population_density(lat, lon) or 0.0
        print(f"   Density: {density:.1f} people/sq mi")
        
        # Get business count
        try:
            business_data = osm_api.query_local_businesses(lat, lon, radius_m=1000)
            if business_data:
                all_businesses = (business_data.get("tier1_daily", []) + 
                                business_data.get("tier2_social", []) +
                                business_data.get("tier3_culture", []) +
                                business_data.get("tier4_services", []))
                business_count = len(all_businesses)
            else:
                business_count = None
        except Exception:
            business_count = None
        
        # Get built coverage
        try:
            from data_sources.arch_diversity import compute_arch_diversity
            arch_metrics = compute_arch_diversity(lat, lon, radius_m=2000)
            built_coverage = arch_metrics.get("built_coverage_ratio")
        except Exception:
            built_coverage = None
        
        # Get distance to principal city (detect metro first, then get distance)
        detected_metro = baseline_mgr._detect_metro_area(city, lat, lon)
        metro_distance_km = baseline_mgr.get_distance_to_principal_city(lat, lon, metro_name=detected_metro)
        if metro_distance_km:
            print(f"   Metro: {detected_metro}")
            print(f"   Distance to principal city: {metro_distance_km:.1f} km")
        else:
            print(f"   Metro: {detected_metro or 'Not found'}")
            print(f"   Distance to principal city: Not found")
        
        # Classify
        classification = detect_area_type(
            lat, lon,
            density=density,
            city=city,
            business_count=business_count,
            built_coverage=built_coverage,
            metro_distance_km=metro_distance_km
        )
        
        print(f"   Classification: {classification}")
        print(f"   Expected: {expected}")
        
        status = "✅ PASS" if classification == expected else "❌ FAIL"
        print(f"   {status}")
    
    print(f"\n{'='*70}")
    print("✅ Testing Complete")
    print('='*70)

if __name__ == "__main__":
    test_classification()

