#!/usr/bin/env python3
"""
Test Natural Beauty scoring for specified locations
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pillars.natural_beauty import get_natural_beauty_score
from data_sources.geocoding import geocode

# Test locations
TEST_LOCATIONS = [
    "Georgetown, DC",
    "Beacon Hill, Boston MA",
    "Park Slope, Brooklyn NY",
    "Manhattan Beach, CA",
    "The Woodlands, TX",
    "Silver Lake, Los Angeles CA",
    "Truckee, CA",
    "Stowe, VT",
    "Sedona, AZ",
    "Telluride, CO",
    "Old Town Scottsdale, AZ",
    "Carmel-by-the-Sea, CA",
    "Moab, UT",
    "Wynwood, Miami FL",
    "Venice Beach, Los Angeles CA",
    "New Orleans Garden District",
    "Brickell, Miami FL",
]

def test_locations():
    """Run Natural Beauty scoring for test locations."""
    print("Testing Natural Beauty Scoring")
    print("=" * 80)
    print(f"Testing {len(TEST_LOCATIONS)} locations\n")
    
    results = []
    
    for location in TEST_LOCATIONS:
        try:
            # Geocode location (returns tuple: (lat, lon, city, state))
            geocode_result = geocode(location)
            if not geocode_result:
                print(f"❌ {location}: Geocoding failed")
                results.append({
                    "location": location,
                    "score": None,
                    "error": "Geocoding failed"
                })
                continue
            
            # Handle tuple return from geocode (lat, lon, zip_code, state, city)
            if isinstance(geocode_result, tuple):
                lat, lon, zip_code, state, city = geocode_result
            else:
                # Fallback for dict (shouldn't happen, but handle it)
                lat = geocode_result.get("lat")
                lon = geocode_result.get("lon")
                city = geocode_result.get("city")
            
            # Get Natural Beauty score
            score, details = get_natural_beauty_score(
                lat=lat,
                lon=lon,
                city=city,
                location_name=location
            )
            
            # Extract key metrics
            tree_score = details.get("tree_score_0_50", 0)
            context_bonus = details.get("context_bonus_raw", 0)
            uplift_bonus = details.get("uplift_bonus", 0)
            score_before_uplift = details.get("score_before_uplift", score)
            
            # Get canopy data
            tree_details = details.get("tree_analysis", {})
            multi_radius = tree_details.get("multi_radius_canopy", {})
            neighborhood_canopy = multi_radius.get("neighborhood_1000m", 0) if multi_radius else 0
            
            results.append({
                "location": location,
                "score": score,
                "tree_score": tree_score,
                "context_bonus": context_bonus,
                "uplift_bonus": uplift_bonus,
                "score_before_uplift": score_before_uplift,
                "neighborhood_canopy": neighborhood_canopy,
                "lat": lat,
                "lon": lon
            })
            
            print(f"✅ {location}")
            print(f"   Score: {score:.1f}")
            print(f"   Tree Score: {tree_score:.1f}")
            print(f"   Context Bonus: {context_bonus:.2f}")
            print(f"   Uplift Bonus: {uplift_bonus:.2f}")
            print(f"   Score Before Uplift: {score_before_uplift:.1f}")
            print(f"   Neighborhood Canopy: {neighborhood_canopy:.1f}%")
            print()
            
        except Exception as e:
            print(f"❌ {location}: Error - {e}")
            import traceback
            traceback.print_exc()
            results.append({
                "location": location,
                "score": None,
                "error": str(e)
            })
            print()
    
    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"{'Location':<40} {'Score':<8} {'Tree':<8} {'Context':<10} {'Uplift':<8} {'Canopy%':<8}")
    print("-" * 80)
    
    for r in results:
        if r.get("score") is not None:
            print(f"{r['location']:<40} {r['score']:<8.1f} {r['tree_score']:<8.1f} {r['context_bonus']:<10.2f} {r['uplift_bonus']:<8.2f} {r['neighborhood_canopy']:<8.1f}")
        else:
            print(f"{r['location']:<40} ERROR: {r.get('error', 'Unknown')}")
    
    print("=" * 80)
    
    return results

if __name__ == "__main__":
    test_locations()
