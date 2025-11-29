#!/usr/bin/env python3
"""
Diagnose Active Outdoors v2 Outliers

This script investigates why certain locations are over/under-scoring
by examining component scores, OSM data, and expected values.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data_sources.geocoding import geocode
from data_sources.regional_baselines import get_contextual_expectations
from data_sources.radius_profiles import get_radius_profile
from pillars.active_outdoors import get_active_outdoors_score_v2
from data_sources import osm_api
from data_sources.gee_api import get_tree_canopy_gee
import json


# Outliers to investigate (from Round 13 test data)
OUTLIERS = {
    "Downtown Denver CO": {
        "target": None,  # Will use LLM range
        "score": 61.1,
        "error": -7.2,  # Alignment index
        "area_type": "urban_core",
        "issue": "Severe under-scoring - alignment index -7.2, Wild Adventure only 4.2/50"
    },
    "Boulder CO": {
        "target": None,
        "score": 79.1,
        "error": -2.2,  # Alignment index
        "area_type": "urban_residential",
        "issue": "Under-scoring - alignment index -2.2, mountain town"
    },
    "Bethesda MD": {
        "target": None,
        "score": 90.4,
        "error": +1.9,  # Alignment index
        "area_type": "urban_residential",
        "issue": "Over-scoring - alignment index +1.9, 221 parks seems high"
    },
    "Bar Harbor ME": {
        "target": None,
        "score": 94.1,
        "error": +1.1,  # Alignment index
        "area_type": "rural",
        "issue": "Over-scoring - alignment index +1.1, 972 water features seems very high"
    },
    "Aspen CO": {
        "target": None,
        "score": 82.7,
        "error": -0.5,  # Alignment index
        "area_type": "rural",
        "issue": "Slight under-scoring - alignment index -0.5"
    }
}


def diagnose_location(name: str, info: dict):
    """Diagnose a single outlier location."""
    print(f"\n{'='*80}")
    print(f"DIAGNOSING: {name}")
    print(f"Target: {info['target']}, Score: {info['score']}, Error: {info['error']:+.1f}")
    print(f"Issue: {info['issue']}")
    print(f"{'='*80}\n")
    
    # Geocode
    print("📍 Geocoding...")
    result = geocode(name)
    if not result:
        print(f"❌ Failed to geocode: {name}")
        return
    lat, lon, _, _, _ = result
    print(f"   Coordinates: {lat:.6f}, {lon:.6f}")
    
    area_type = info.get('area_type')
    
    # Get expectations
    print(f"\n📊 Expected Values (area_type: {area_type}):")
    expectations = get_contextual_expectations(area_type, 'active_outdoors') or {}
    for key, value in expectations.items():
        print(f"   {key}: {value}")
    
    # Get radius profile
    print(f"\n🔧 Radius Profile:")
    profile = get_radius_profile('active_outdoors', area_type, None)
    for key, value in profile.items():
        print(f"   {key}: {value}")
    
    # Query OSM data
    print(f"\n🗺️  Querying OSM Data...")
    local_radius = int(profile.get('local_radius_m', 2000))
    trail_radius = int(profile.get('trail_radius_m', 15000))
    regional_radius = int(profile.get('regional_radius_m', 50000))
    
    # Local parks & playgrounds
    print(f"   Local parks & playgrounds (radius: {local_radius}m)...")
    local = osm_api.query_green_spaces(lat, lon, radius_m=local_radius) or {}
    parks = local.get("parks", []) or []
    playgrounds = local.get("playgrounds", []) or []
    print(f"   Found: {len(parks)} parks, {len(playgrounds)} playgrounds")
    if parks:
        total_area = sum(p.get("area_sqm", 0.0) for p in parks) / 10000.0
        print(f"   Total park area: {total_area:.2f} hectares")
        closest_park = min(parks, key=lambda p: p.get("distance_m", 1e9))
        print(f"   Closest park: {closest_park.get('name', 'Unknown')} at {closest_park.get('distance_m', 0):.0f}m")
    
    # Nature features
    print(f"   Nature features - trails (radius: {trail_radius}m)...")
    nature_trail = osm_api.query_nature_features(lat, lon, radius_m=trail_radius) or {}
    hiking = nature_trail.get("hiking", []) or []
    print(f"   Found: {len(hiking)} hiking trails")
    if hiking:
        closest_trail = min(hiking, key=lambda h: h.get("distance_m", 1e9))
        print(f"   Closest trail: {closest_trail.get('name', 'Unknown')} at {closest_trail.get('distance_m', 0):.0f}m")
        near_trails = [h for h in hiking if h.get("distance_m", 1e9) <= 5000]
        print(f"   Trails within 5km: {len(near_trails)}")
    
    print(f"   Nature features - water/camping (radius: {regional_radius}m)...")
    nature_regional = osm_api.query_nature_features(lat, lon, radius_m=regional_radius) or {}
    swimming = nature_regional.get("swimming", []) or []
    camping = nature_regional.get("camping", []) or []
    print(f"   Found: {len(swimming)} water features, {len(camping)} camping sites")
    if swimming:
        closest_water = min(swimming, key=lambda s: s.get("distance_m", 1e9))
        print(f"   Closest water: {closest_water.get('type', 'Unknown')} ({closest_water.get('name', 'Unknown')}) at {closest_water.get('distance_m', 0):.0f}m")
    if camping:
        closest_camp = min(camping, key=lambda c: c.get("distance_m", 1e9))
        print(f"   Closest camping: {closest_camp.get('name', 'Unknown')} at {closest_camp.get('distance_m', 0):.0f}m")
    
    # Tree canopy
    print(f"\n🌳 Tree Canopy (5km radius):")
    try:
        canopy = get_tree_canopy_gee(lat, lon, radius_m=5000, area_type=area_type) or 0.0
        print(f"   Canopy percentage: {canopy:.1f}%")
    except Exception as e:
        print(f"   Error: {e}")
        canopy = 0.0
    
    # Run scoring to get component breakdown
    print(f"\n🏃 Running Active Outdoors v2 scoring...")
    score, breakdown = get_active_outdoors_score_v2(
        lat=lat,
        lon=lon,
        city=None,
        area_type=area_type,
        location_scope=None,
        include_diagnostics=True
    )
    
    print(f"\n📈 Component Scores:")
    components = breakdown.get("breakdown", {})
    daily = components.get("daily_urban_outdoors", 0)
    wild = components.get("wild_adventure", 0)
    water = components.get("waterfront_lifestyle", 0)
    raw_total = breakdown.get("raw_total_v2", 0)
    
    print(f"   Daily Urban Outdoors: {daily:.1f}/30")
    print(f"   Wild Adventure: {wild:.1f}/50")
    print(f"   Waterfront Lifestyle: {water:.1f}/20")
    print(f"   Raw Total: {raw_total:.2f}")
    print(f"   Calibrated Score: {score:.1f}/100")
    if info.get('target'):
        print(f"   Target: {info['target']}")
        print(f"   Error: {score - info['target']:+.1f}")
    if info.get('error'):
        print(f"   Alignment Index: {info['error']:+.1f}")
    
    # Analysis
    print(f"\n🔍 Analysis:")
    if info['error'] > 0:
        print(f"   ⚠️  OVER-SCORING by {info['error']:.1f} points")
        if daily > 20:
            print(f"   - Daily Urban Outdoors ({daily:.1f}) may be too high for this area type")
        if wild > 15:
            print(f"   - Wild Adventure ({wild:.1f}) may be too high for this area type")
        if water > 12:
            print(f"   - Waterfront Lifestyle ({water:.1f}) may be too high (check for false positives)")
    else:
        print(f"   ⚠️  UNDER-SCORING by {abs(info['error']):.1f} points")
        if wild < 30 and info['area_type'] in ['urban_core']:
            print(f"   - Wild Adventure ({wild:.1f}) may be too low for mountain town")
            print(f"   - Consider mountain town detection with higher trail expectations")
        if daily < 20:
            print(f"   - Daily Urban Outdoors ({daily:.1f}) may be too low")
    
    # Save detailed diagnostics
    diagnostics = {
        "name": name,
        "target": info.get('target'),
        "score": score,
        "error": score - info['target'] if info.get('target') else info.get('error'),
        "alignment_index": info.get('error'),
        "area_type": area_type,
        "coordinates": {"lat": lat, "lon": lon},
        "expectations": expectations,
        "radius_profile": profile,
        "osm_data": {
            "parks_count": len(parks),
            "playgrounds_count": len(playgrounds),
            "parks_total_area_ha": sum(p.get("area_sqm", 0.0) for p in parks) / 10000.0 if parks else 0,
            "hiking_trails_count": len(hiking),
            "hiking_trails_within_5km": len([h for h in hiking if h.get("distance_m", 1e9) <= 5000]) if hiking else 0,
            "water_features_count": len(swimming),
            "camping_sites_count": len(camping),
            "tree_canopy_pct_5km": canopy
        },
        "component_scores": {
            "daily_urban_outdoors": daily,
            "wild_adventure": wild,
            "waterfront_lifestyle": water,
            "raw_total": raw_total
        },
        "breakdown": breakdown
    }
    
    return diagnostics


def main():
    """Main diagnostic workflow."""
    print("Active Outdoors v2 Outlier Diagnosis")
    print("=" * 80)
    
    all_diagnostics = []
    
    for name, info in OUTLIERS.items():
        try:
            diag = diagnose_location(name, info)
            if diag:
                all_diagnostics.append(diag)
        except Exception as e:
            print(f"\n❌ Error diagnosing {name}: {e}")
            import traceback
            traceback.print_exc()
    
    # Save results
    output_file = project_root / "analysis" / "active_outdoors_outlier_diagnostics.json"
    with open(output_file, "w") as f:
        json.dump(all_diagnostics, f, indent=2)
    
    print(f"\n✅ Diagnostics saved to: {output_file}")
    print(f"\n📊 Summary:")
    print(f"   Diagnosed {len(all_diagnostics)} locations")
    print(f"   Review diagnostics file for detailed analysis")


if __name__ == "__main__":
    main()

