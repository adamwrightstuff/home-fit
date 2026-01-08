#!/usr/bin/env python3
"""
Test all locations with debug logging
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pillars.active_outdoors import get_active_outdoors_score_v2
from data_sources.geocoding import geocode_with_full_result

locations = [
    "Larchmont, NY",
    "111 2nd Street, Brooklyn, NY",
    "Redondo Beach, CA",
    "Culver City, CA"
]

print("="*80)
print("ACTIVE OUTDOORS DEBUG ANALYSIS - ALL LOCATIONS")
print("="*80)

for location in locations:
    print(f"\n{'='*80}")
    print(f"Testing: {location}")
    print(f"{'='*80}")
    
    # Geocode
    geo_result = geocode_with_full_result(location)
    if not geo_result:
        print(f"Failed to geocode {location}")
        continue
    
    lat, lon, zip_code, state, city, geocode_data = geo_result
    print(f"Coordinates: {lat}, {lon}")
    print(f"Location: {city}, {state} {zip_code}")
    
    # Get score
    try:
        score, breakdown = get_active_outdoors_score_v2(
            lat=lat,
            lon=lon,
            city=city,
            area_type=None,  # Let it detect
            location_scope=None,
            precomputed_tree_canopy_5km=None
        )
        
        daily = breakdown['breakdown']['daily_urban_outdoors']
        wild = breakdown['breakdown']['wild_adventure']
        water = breakdown['breakdown']['waterfront_lifestyle']
        calculated = 0.30 * daily + 0.50 * wild + 0.20 * water
        
        print(f"\nResults:")
        print(f"  Total Score: {score:.1f}/100")
        print(f"  daily_urban_outdoors: {daily:.1f}/30")
        print(f"  wild_adventure: {wild:.1f}/50")
        print(f"  waterfront_lifestyle: {water:.1f}/20")
        print(f"  Calculated: {calculated:.1f} (match: {abs(calculated - score) < 0.1})")
        
        # Show summary data if available
        if 'summary' in breakdown:
            summary = breakdown['summary']
            print(f"\nData Summary:")
            if 'local_parks' in summary:
                parks = summary['local_parks']
                print(f"  Parks: {parks.get('count', 0)}, Area: {parks.get('total_park_area_ha', 0):.1f} ha")
            if 'trails' in summary:
                trails = summary['trails']
                print(f"  Trails: {trails.get('count_total', 0)} total, {trails.get('count_within_5km', 0)} within 5km")
            if 'water' in summary:
                water_data = summary['water']
                print(f"  Water: {water_data.get('features', 0)} features, nearest: {water_data.get('nearest_km', 0):.2f} km")
            if 'camping' in summary:
                camping = summary['camping']
                print(f"  Camping: {camping.get('sites', 0)} sites")
            if 'environment' in summary:
                env = summary['environment']
                print(f"  Tree Canopy: {env.get('tree_canopy_pct_5km', 0):.1f}%")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

