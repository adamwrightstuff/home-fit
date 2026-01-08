#!/usr/bin/env python3
"""
Test Active Outdoors scoring with debug logging
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pillars.active_outdoors import get_active_outdoors_score_v2
from data_sources.geocoding import geocode_with_full_result

# Test Larchmont, NY
location = "Larchmont, NY"
print(f"Testing: {location}")
print("="*80)

# Geocode
geo_result = geocode_with_full_result(location)
if not geo_result:
    print("Failed to geocode")
    sys.exit(1)

lat, lon, zip_code, state, city, geocode_data = geo_result
print(f"Coordinates: {lat}, {lon}")
print(f"Location: {city}, {state} {zip_code}")
print()

# Get score - test with suburban (as API shows)
print("Calculating Active Outdoors score...")
print("="*80)
print("Testing with area_type='suburban' (as shown in API response)...")
score, breakdown = get_active_outdoors_score_v2(
    lat=lat,
    lon=lon,
    city=city,
    area_type='suburban',  # Use suburban as API shows
    location_scope=None,
    precomputed_tree_canopy_5km=None
)

print()
print("="*80)
print("RESULTS")
print("="*80)
print(f"Total Score: {score}/100")
print(f"\nBreakdown:")
print(f"  daily_urban_outdoors: {breakdown['breakdown']['daily_urban_outdoors']:.1f}/30")
print(f"  wild_adventure: {breakdown['breakdown']['wild_adventure']:.1f}/50")
print(f"  waterfront_lifestyle: {breakdown['breakdown']['waterfront_lifestyle']:.1f}/20")

# Verify calculation
daily = breakdown['breakdown']['daily_urban_outdoors']
wild = breakdown['breakdown']['wild_adventure']
water = breakdown['breakdown']['waterfront_lifestyle']
calculated = 0.30 * daily + 0.50 * wild + 0.20 * water
print(f"\nVerification:")
print(f"  0.30 * {daily:.1f} + 0.50 * {wild:.1f} + 0.20 * {water:.1f} = {calculated:.1f}")
print(f"  Actual score: {score:.1f}")
print(f"  Match: {abs(calculated - score) < 0.1}")

