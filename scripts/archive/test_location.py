#!/usr/bin/env python3
"""
Quick test script to score a location with Active Outdoors v2
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data_sources.geocoding import geocode
from pillars.active_outdoors import get_active_outdoors_score_v2

def test_location(location_name: str, area_type: str = None):
    """Test a location and print detailed results."""
    print(f"Testing: {location_name}")
    print("=" * 60)
    
    # Geocode
    print(f"🔍 Geocoding...")
    result = geocode(location_name)
    if not result:
        print(f"❌ Failed to geocode: {location_name}")
        return
    
    lat, lon, zip_code, state, city = result
    print(f"   ✅ Found: {lat:.6f}, {lon:.6f} ({city}, {state})")
    
    # Score
    print(f"\n🏃 Running Active Outdoors v2 scoring...")
    score, breakdown = get_active_outdoors_score_v2(
        lat=lat,
        lon=lon,
        city=city,
        area_type=area_type,
        location_scope=None,
        include_diagnostics=True
    )
    
    # Print results
    print(f"\n{'='*60}")
    print(f"RESULTS FOR {location_name.upper()}")
    print(f"{'='*60}")
    print(f"\n📊 Total Score: {score:.1f}/100")
    
    print(f"\n📈 Component Scores:")
    comps = breakdown["breakdown"]
    print(f"   Daily Urban Outdoors: {comps['daily_urban_outdoors']:.1f}/30")
    print(f"   Wild Adventure: {comps['wild_adventure']:.1f}/50")
    print(f"   Waterfront Lifestyle: {comps['waterfront_lifestyle']:.1f}/20")
    
    # Raw total and calibration
    raw_total = breakdown.get("raw_total_v2", "N/A")
    cal = breakdown.get("calibration", {})
    print(f"\n🔧 Calibration Details:")
    print(f"   Raw Total (before calibration): {raw_total}")
    if cal:
        print(f"   CAL_A: {cal.get('a', 'N/A')}")
        print(f"   CAL_B: {cal.get('b', 'N/A')}")
    
    # Summary
    summary = breakdown.get("summary", {})
    if summary:
        print(f"\n📋 Summary:")
        if "local_parks" in summary:
            lp = summary["local_parks"]
            print(f"   Parks: {lp.get('count', 0)} (Playgrounds: {lp.get('playgrounds', 0)})")
            print(f"   Total Park Area: {lp.get('total_park_area_ha', 0):.2f} ha")
        if "trails" in summary:
            t = summary["trails"]
            print(f"   Trails: {t.get('count_total', 0)} total ({t.get('count_within_5km', 0)} within 5km)")
        if "water" in summary:
            w = summary["water"]
            print(f"   Water Features: {w.get('features', 0)} (Nearest: {w.get('nearest_km', 'N/A')} km)")
        if "camping" in summary:
            c = summary["camping"]
            print(f"   Camping Sites: {c.get('sites', 0)} (Nearest: {c.get('nearest_km', 'N/A')} km)")
        if "environment" in summary:
            e = summary["environment"]
            print(f"   Tree Canopy (5km): {e.get('tree_canopy_pct_5km', 0):.1f}%")
    
    # Diagnostics
    diag = breakdown.get("diagnostics", {})
    if diag:
        print(f"\n🔬 Diagnostics:")
        print(f"   Parks (2km): {diag.get('parks_2km', 0)}")
        print(f"   Playgrounds (2km): {diag.get('playgrounds_2km', 0)}")
        print(f"   Hiking Trails Total: {diag.get('hiking_trails_total', 0)}")
        print(f"   Hiking Trails (within 5km): {diag.get('hiking_trails_within_5km', 0)}")
        print(f"   Swimming Features: {diag.get('swimming_features', 0)}")
        print(f"   Camp Sites: {diag.get('camp_sites', 0)}")
        print(f"   Tree Canopy 5km: {diag.get('tree_canopy_pct_5km', 0):.1f}%")
    
    # Area classification
    area_class = breakdown.get("area_classification", {})
    if area_class:
        print(f"\n📍 Area Classification:")
        print(f"   Type: {area_class.get('area_type', 'N/A')}")
        print(f"   Metro: {area_class.get('metro_name', 'N/A')}")
    
    print(f"\n{'='*60}")
    
    return score, breakdown

if __name__ == "__main__":
    location = sys.argv[1] if len(sys.argv) > 1 else "Boulder CO"
    area_type = sys.argv[2] if len(sys.argv) > 2 else None
    test_location(location, area_type)

