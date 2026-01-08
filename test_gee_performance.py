#!/usr/bin/env python3
"""
Test GEE tree canopy performance with parallel execution.
Tests Bellevue, WA to verify performance improvements and canopy accuracy.
"""

import sys
import time
from data_sources.gee_api import get_tree_canopy_gee

def test_location(name: str, lat: float, lon: float):
    """Test canopy retrieval for a location and measure performance."""
    print("=" * 80)
    print(f"Testing: {name}")
    print(f"Coordinates: {lat}, {lon}")
    print("=" * 80)
    print()
    
    start_time = time.time()
    result = get_tree_canopy_gee(lat, lon, radius_m=1000)
    elapsed = time.time() - start_time
    
    print()
    print("=" * 80)
    print("Results:")
    print("=" * 80)
    print(f"Final Canopy Percentage: {result:.1f}%" if result is not None else "Final Canopy Percentage: None")
    print(f"Total Time: {elapsed:.2f} seconds")
    print()
    
    return result, elapsed

if __name__ == "__main__":
    # Test Bellevue, WA (expected high canopy)
    bellevue_lat = 47.6101
    bellevue_lon = -122.2015
    
    result, elapsed = test_location("Bellevue, WA", bellevue_lat, bellevue_lon)
    
    if result is not None:
        print(f"✅ Success! Canopy: {result:.1f}%, Time: {elapsed:.2f}s")
        if elapsed < 15:
            print(f"✅ Performance check passed (under 15s target)")
        else:
            print(f"⚠️  Performance check failed (over 15s)")
    else:
        print("❌ Failed to get canopy data")
        sys.exit(1)
