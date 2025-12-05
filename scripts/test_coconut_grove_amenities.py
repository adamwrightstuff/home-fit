#!/usr/bin/env python3
"""
Test script to diagnose why Coconut Grove is getting no amenities.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from data_sources import osm_api, geocoding
from pillars.neighborhood_amenities import get_neighborhood_amenities_score

def main():
    # Coconut Grove coordinates from the log
    lat = 25.7126013
    lon = -80.2569947
    
    print("=" * 80)
    print("Coconut Grove Amenities Diagnostic")
    print("=" * 80)
    print(f"Location: Coconut Grove, FL")
    print(f"Coordinates: {lat}, {lon}\n")
    
    # Test 1: Query OSM directly with chains included
    print("Test 1: Querying OSM with chains INCLUDED...")
    business_data_with_chains = osm_api.query_local_businesses(
        lat, lon, radius_m=1000, include_chains=True
    )
    
    if business_data_with_chains:
        total_with_chains = sum(len(business_data_with_chains.get(k, [])) 
                               for k in ["tier1_daily", "tier2_social", "tier3_culture", "tier4_services"])
        print(f"  ✅ Found {total_with_chains} businesses (with chains)")
        for tier, key in [("Tier 1", "tier1_daily"), ("Tier 2", "tier2_social"), 
                          ("Tier 3", "tier3_culture"), ("Tier 4", "tier4_services")]:
            count = len(business_data_with_chains.get(key, []))
            if count > 0:
                print(f"     {tier}: {count} businesses")
                # Show first few
                for b in business_data_with_chains.get(key, [])[:3]:
                    print(f"        - {b.get('name', 'Unnamed')} ({b.get('type', 'unknown')}) at {b.get('distance_m', 0):.0f}m")
    else:
        print("  ❌ No business data returned")
    
    print()
    
    # Test 2: Query OSM without chains (default)
    print("Test 2: Querying OSM WITHOUT chains (default)...")
    business_data_no_chains = osm_api.query_local_businesses(
        lat, lon, radius_m=1000, include_chains=False
    )
    
    if business_data_no_chains:
        total_no_chains = sum(len(business_data_no_chains.get(k, [])) 
                             for k in ["tier1_daily", "tier2_social", "tier3_culture", "tier4_services"])
        print(f"  ✅ Found {total_no_chains} businesses (no chains)")
        for tier, key in [("Tier 1", "tier1_daily"), ("Tier 2", "tier2_social"), 
                          ("Tier 3", "tier3_culture"), ("Tier 4", "tier4_services")]:
            count = len(business_data_no_chains.get(key, []))
            if count > 0:
                print(f"     {tier}: {count} businesses")
                # Show first few
                for b in business_data_no_chains.get(key, [])[:3]:
                    print(f"        - {b.get('name', 'Unnamed')} ({b.get('type', 'unknown')}) at {b.get('distance_m', 0):.0f}m")
    else:
        print("  ❌ No business data returned")
    
    print()
    
    # Test 3: Try with larger radius
    print("Test 3: Querying OSM with larger radius (1500m)...")
    business_data_large_radius = osm_api.query_local_businesses(
        lat, lon, radius_m=1500, include_chains=False
    )
    
    if business_data_large_radius:
        total_large = sum(len(business_data_large_radius.get(k, [])) 
                         for k in ["tier1_daily", "tier2_social", "tier3_culture", "tier4_services"])
        print(f"  ✅ Found {total_large} businesses (1500m radius)")
    else:
        print("  ❌ No business data returned")
    
    print()
    
    # Test 4: Get full amenities score
    print("Test 4: Getting full amenities score...")
    try:
        score, breakdown = get_neighborhood_amenities_score(
            lat=lat,
            lon=lon,
            include_chains=False,
            location_scope="neighborhood"
        )
        print(f"  ✅ Score: {score}/100")
        print(f"     Home Walkability: {breakdown.get('breakdown', {}).get('home_walkability', {}).get('score', 0) if isinstance(breakdown.get('breakdown', {}).get('home_walkability', {}), dict) else 0}")
        print(f"     Location Quality: {breakdown.get('breakdown', {}).get('location_quality', 0)}")
        print(f"     Total Businesses: {breakdown.get('summary', {}).get('total_businesses', 0)}")
    except Exception as e:
        print(f"  ❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    print()
    print("=" * 80)
    print("Diagnostic complete. Check logs for detailed OSM query diagnostics.")
    print("=" * 80)

if __name__ == "__main__":
    main()

