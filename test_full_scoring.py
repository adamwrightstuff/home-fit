#!/usr/bin/env python3
"""Test full pillar scoring for Carroll Gardens (neighborhood) and Ann Arbor (city)."""

import sys
import os
import json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data_sources.geocoding import geocode_with_full_result
from data_sources.data_quality import detect_location_scope
from pillars.active_outdoors import get_active_outdoors_score
from pillars.neighborhood_beauty import get_neighborhood_beauty_score
from pillars.neighborhood_amenities import get_neighborhood_amenities_score
from pillars.air_travel_access import get_air_travel_score
from pillars.public_transit_access import get_public_transit_score
from pillars.healthcare_access import get_healthcare_access_score
from pillars.schools import get_school_data
from pillars.housing_value import get_housing_value_score

test_locations = [
    ("Carroll Gardens, Brooklyn", "neighborhood"),
    ("Ann Arbor, MI", "city"),
]

print("🏠 Full Pillar Testing with Neighborhood Detection")
print("=" * 80)
print()

for location_name, expected_scope in test_locations:
    print(f"\n{'='*80}")
    print(f"📍 {location_name}")
    print(f"{'='*80}\n")
    
    # Geocode with full result (cached)
    geo_result = geocode_with_full_result(location_name)
    
    if not geo_result:
        print(f"❌ Geocoding failed for {location_name}")
        continue
    
    lat, lon, zip_code, state, city, geocode_data = geo_result
    print(f"📍 Coordinates: {lat}, {lon}")
    print(f"📍 Location: {city}, {state} {zip_code}")
    
    # Detect location scope
    location_scope = detect_location_scope(lat, lon, geocode_data)
    print(f"📍 Location scope: {location_scope} (expected: {expected_scope})")
    if location_scope == expected_scope:
        print(f"   ✅ Detection correct!\n")
    else:
        print(f"   ⚠️  Detection differs (may be OK if density-based)\n")
    
    # Test all pillars
    print(f"{'-'*80}")
    print("PILLAR SCORES:")
    print(f"{'-'*80}\n")
    
    pillar_scores = {}
    
    # Pillar 1: Active Outdoors
    try:
        active_outdoors_score, active_outdoors_details = get_active_outdoors_score(lat, lon, city=city)
        pillar_scores['active_outdoors'] = active_outdoors_score
        print(f"1. 🏃 Active Outdoors: {active_outdoors_score:.1f}/100")
    except Exception as e:
        print(f"1. 🏃 Active Outdoors: ERROR - {e}")
        pillar_scores['active_outdoors'] = 0
    
    # Pillar 2: Neighborhood Beauty
    try:
        beauty_score, beauty_details = get_neighborhood_beauty_score(
            lat, lon, city=city, location_scope=location_scope
        )
        pillar_scores['neighborhood_beauty'] = beauty_score
        breakdown = beauty_details.get('breakdown', {})
        print(f"2. ✨ Neighborhood Beauty: {beauty_score:.1f}/100")
        print(f"   - Trees: {breakdown.get('trees', 0):.1f}/50")
        print(f"   - Historic: {breakdown.get('historic_character', 0):.1f}/50")
        
        # Show tree canopy details
        tree_analysis = beauty_details.get('details', {}).get('tree_analysis', {})
        canopy_pct = tree_analysis.get('gee_canopy_pct', 'N/A')
        if isinstance(canopy_pct, (int, float)):
            print(f"   - Tree Canopy: {canopy_pct:.1f}%")
    except Exception as e:
        print(f"2. ✨ Neighborhood Beauty: ERROR - {e}")
        pillar_scores['neighborhood_beauty'] = 0
    
    # Pillar 3: Neighborhood Amenities
    try:
        amenities_score, amenities_details = get_neighborhood_amenities_score(
            lat, lon, include_chains=False, location_scope=location_scope
        )
        pillar_scores['neighborhood_amenities'] = amenities_score
        summary = amenities_details.get('summary', {})
        total_businesses = summary.get('total_businesses', 0)
        print(f"3. 🍽️  Neighborhood Amenities: {amenities_score:.1f}/100")
        print(f"   - Total businesses: {total_businesses}")
        print(f"   - Within 1km: {summary.get('within_5min_walk', 0)}")
    except Exception as e:
        print(f"3. 🍽️  Neighborhood Amenities: ERROR - {e}")
        pillar_scores['neighborhood_amenities'] = 0
    
    # Pillar 4: Air Travel Access
    try:
        air_travel_score, air_travel_details = get_air_travel_score(lat, lon)
        pillar_scores['air_travel_access'] = air_travel_score
        primary = air_travel_details.get('primary_airport', {})
        print(f"4. ✈️  Air Travel Access: {air_travel_score:.1f}/100")
        if primary:
            print(f"   - Nearest: {primary.get('name', 'N/A')} ({primary.get('distance_km', 0):.1f}km)")
    except Exception as e:
        print(f"4. ✈️  Air Travel Access: ERROR - {e}")
        pillar_scores['air_travel_access'] = 0
    
    # Pillar 5: Public Transit Access
    try:
        transit_score, transit_details = get_public_transit_score(lat, lon)
        pillar_scores['public_transit_access'] = transit_score
        breakdown = transit_details.get('breakdown', {})
        print(f"5. 🚇 Public Transit Access: {transit_score:.1f}/100")
        print(f"   - Heavy Rail: {breakdown.get('heavy_rail', 0):.1f}")
        print(f"   - Light Rail: {breakdown.get('light_rail', 0):.1f}")
        print(f"   - Bus: {breakdown.get('bus', 0):.1f}")
    except Exception as e:
        print(f"5. 🚇 Public Transit Access: ERROR - {e}")
        pillar_scores['public_transit_access'] = 0
    
    # Pillar 6: Healthcare Access
    try:
        healthcare_score, healthcare_details = get_healthcare_access_score(lat, lon)
        pillar_scores['healthcare_access'] = healthcare_score
        breakdown = healthcare_details.get('breakdown', {})
        summary = healthcare_details.get('summary', {})
        print(f"6. 🏥 Healthcare Access: {healthcare_score:.1f}/100")
        print(f"   - Hospitals: {breakdown.get('hospital_access', 0):.1f}")
        print(f"   - Urgent Care: {breakdown.get('urgent_care', 0):.1f}")
        print(f"   - Pharmacies: {breakdown.get('pharmacies', 0):.1f}")
        print(f"   - Pharmacy count: {summary.get('pharmacy_count', 0)}")
    except Exception as e:
        print(f"6. 🏥 Healthcare Access: ERROR - {e}")
        pillar_scores['healthcare_access'] = 0
    
    # Pillar 7: Quality Education
    try:
        if zip_code and state:
            school_avg, schools_by_level = get_school_data(
                zip_code=zip_code,
                state=state,
                city=city
            )
            pillar_scores['quality_education'] = school_avg
            print(f"7. 📚 Quality Education: {school_avg:.1f}/100")
            total_schools = sum(len(schools) for schools in schools_by_level.values())
            print(f"   - Schools rated: {total_schools}")
            for level, schools in schools_by_level.items():
                if schools:
                    top_school = schools[0]
                    print(f"   - {level.capitalize()}: {top_school.get('name', 'N/A')} ({top_school.get('rating', 0):.0f}/100)")
        else:
            print(f"7. 📚 Quality Education: Skipped (no ZIP/state)")
            pillar_scores['quality_education'] = 0
    except Exception as e:
        print(f"7. 📚 Quality Education: ERROR - {e}")
        pillar_scores['quality_education'] = 0
    
    # Pillar 8: Housing Value
    try:
        housing_score, housing_details = get_housing_value_score(lat, lon)
        pillar_scores['housing_value'] = housing_score
        summary = housing_details.get('summary', {})
        print(f"8. 🏠 Housing Value: {housing_score:.1f}/100")
        print(f"   - Median home value: ${summary.get('median_home_value', 0):,}")
        print(f"   - Affordability: {summary.get('affordability_rating', 'N/A')}")
    except Exception as e:
        print(f"8. 🏠 Housing Value: ERROR - {e}")
        pillar_scores['housing_value'] = 0
    
    # Calculate average (equal weighting)
    valid_scores = [v for v in pillar_scores.values() if v > 0]
    if valid_scores:
        avg_score = sum(valid_scores) / len(valid_scores)
        print(f"\n{'='*80}")
        print(f"📊 AVERAGE SCORE (Equal Weighting): {avg_score:.1f}/100")
        print(f"{'='*80}\n")

print("\n✅ Full pillar testing complete (using cached results)")

