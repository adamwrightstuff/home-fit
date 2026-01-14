#!/usr/bin/env python3
"""
Built Beauty Research Data Collection

Collects built beauty feature values from diverse locations to establish
research-backed expected values for scoring.

This script:
1. Collects architectural diversity metrics from diverse neighborhoods
2. Groups results by area type
3. Calculates medians and percentiles for each metric
4. Outputs raw data and statistical analysis

Usage:
    python scripts/collect_built_beauty_research_data.py
"""

import sys
import os
import json
from pathlib import Path
from typing import Dict, List, Optional
from collections import defaultdict
import statistics

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data_sources.arch_diversity import compute_arch_diversity
from data_sources.data_quality import classify_morphology
from data_sources import census_api
from pillars.built_beauty import calculate_built_beauty

# Research locations - diverse neighborhoods across area types
# Goal: 10+ samples per area type for statistical significance
RESEARCH_LOCATIONS = [
    # Urban Core - Historic/Established neighborhoods (currently 5, need 5+ more)
    {"name": "Beacon Hill, Boston MA", "lat": 42.3588, "lon": -71.0707, "expected_area_type": "urban_core"},
    {"name": "Georgetown, Washington DC", "lat": 38.9096, "lon": -77.0634, "expected_area_type": "urban_core"},
    {"name": "Greenwich Village, New York NY", "lat": 40.7336, "lon": -74.0027, "expected_area_type": "urban_core"},
    {"name": "French Quarter, New Orleans LA", "lat": 29.9584, "lon": -90.0644, "expected_area_type": "urban_core"},
    {"name": "North Beach, San Francisco CA", "lat": 37.8060, "lon": -122.4100, "expected_area_type": "urban_core"},
    {"name": "Old San Juan, Puerto Rico", "lat": 18.4655, "lon": -66.1057, "expected_area_type": "urban_core"},
    {"name": "South Beach, Miami FL", "lat": 25.7907, "lon": -80.1300, "expected_area_type": "urban_core"},
    {"name": "Lincoln Park, Chicago IL", "lat": 41.9236, "lon": -87.6389, "expected_area_type": "urban_core"},
    {"name": "Adams Morgan, Washington DC", "lat": 38.9220, "lon": -77.0425, "expected_area_type": "urban_core"},
    {"name": "Mission District, San Francisco CA", "lat": 37.7599, "lon": -122.4148, "expected_area_type": "urban_core"},
    # Additional Urban Core locations
    {"name": "Back Bay, Boston MA", "lat": 42.3519, "lon": -71.0805, "expected_area_type": "urban_core"},
    {"name": "SoHo, New York NY", "lat": 40.7231, "lon": -74.0026, "expected_area_type": "urban_core"},
    {"name": "Union Square, San Francisco CA", "lat": 37.7879, "lon": -122.4075, "expected_area_type": "urban_core"},
    {"name": "Wicker Park, Chicago IL", "lat": 41.9067, "lon": -87.6775, "expected_area_type": "urban_core"},
    {"name": "Downtown, Portland OR", "lat": 45.5152, "lon": -122.6784, "expected_area_type": "urban_core"},
    {"name": "Historic Core, Los Angeles CA", "lat": 34.0505, "lon": -118.2442, "expected_area_type": "urban_core"},
    
    # Urban Residential - Cohesive residential neighborhoods (currently 3, need 7+ more)
    {"name": "Park Slope, Brooklyn NY", "lat": 40.6715, "lon": -73.9772, "expected_area_type": "urban_residential"},
    {"name": "German Village, Columbus OH", "lat": 39.9518, "lon": -82.9988, "expected_area_type": "urban_residential"},
    {"name": "Old Town, Alexandria VA", "lat": 38.8048, "lon": -77.0469, "expected_area_type": "urban_residential"},
    {"name": "Capitol Hill, Seattle WA", "lat": 47.6225, "lon": -122.3237, "expected_area_type": "urban_residential"},
    {"name": "Highland Park, Los Angeles CA", "lat": 34.1147, "lon": -118.1929, "expected_area_type": "urban_residential"},
    # Additional Urban Residential locations
    {"name": "Brooklyn Heights, New York NY", "lat": 40.6957, "lon": -73.9973, "expected_area_type": "urban_residential"},
    {"name": "Carroll Gardens, Brooklyn NY", "lat": 40.6790, "lon": -73.9910, "expected_area_type": "urban_residential"},
    {"name": "Cobble Hill, Brooklyn NY", "lat": 40.6895, "lon": -73.9963, "expected_area_type": "urban_residential"},
    {"name": "Mount Vernon, Baltimore MD", "lat": 39.2976, "lon": -76.6154, "expected_area_type": "urban_residential"},
    {"name": "Oakland, Pittsburgh PA", "lat": 40.4324, "lon": -79.9523, "expected_area_type": "urban_residential"},
    {"name": "Wicker Park, Chicago IL", "lat": 41.9067, "lon": -87.6775, "expected_area_type": "urban_residential"},
    {"name": "Ballard, Seattle WA", "lat": 47.6680, "lon": -122.3846, "expected_area_type": "urban_residential"},
    {"name": "Tremont, Cleveland OH", "lat": 41.4818, "lon": -81.6949, "expected_area_type": "urban_residential"},
    
    # Suburban - Diverse suburban patterns (currently 11, adequate but adding more for diversity)
    {"name": "Levittown, Pennsylvania", "lat": 40.1551, "lon": -74.8288, "expected_area_type": "suburban"},
    {"name": "Celebration, Florida", "lat": 28.3186, "lon": -81.5401, "expected_area_type": "suburban"},
    {"name": "Woodbridge, Irvine CA", "lat": 33.6253, "lon": -117.8399, "expected_area_type": "suburban"},
    {"name": "Reston, Virginia", "lat": 38.9586, "lon": -77.3570, "expected_area_type": "suburban"},
    {"name": "Coral Gables, Florida", "lat": 25.7214, "lon": -80.2684, "expected_area_type": "suburban"},
    {"name": "Evanston, Illinois", "lat": 42.0451, "lon": -87.6877, "expected_area_type": "suburban"},
    {"name": "Montclair, New Jersey", "lat": 40.8259, "lon": -74.2090, "expected_area_type": "suburban"},
    {"name": "Bellevue, Washington", "lat": 47.6101, "lon": -122.2015, "expected_area_type": "suburban"},
    # Additional Suburban locations
    {"name": "Scarsdale, New York", "lat": 40.9887, "lon": -73.7968, "expected_area_type": "suburban"},
    {"name": "Palo Alto, California", "lat": 37.4419, "lon": -122.1430, "expected_area_type": "suburban"},
    {"name": "Oak Park, Illinois", "lat": 41.8850, "lon": -87.7845, "expected_area_type": "suburban"},
    
    # Exurban - Smaller towns (currently 4, need 6+ more)
    {"name": "Carmel-by-the-Sea, California", "lat": 36.5552, "lon": -121.9233, "expected_area_type": "exurban"},
    {"name": "Sedona, Arizona", "lat": 34.8697, "lon": -111.7610, "expected_area_type": "exurban"},
    {"name": "Nantucket, Massachusetts", "lat": 41.2835, "lon": -70.0995, "expected_area_type": "exurban"},
    {"name": "Park City, Utah", "lat": 40.6461, "lon": -111.4980, "expected_area_type": "exurban"},
    # Additional Exurban locations
    {"name": "Aspen, Colorado", "lat": 39.1911, "lon": -106.8175, "expected_area_type": "exurban"},
    {"name": "Key West, Florida", "lat": 24.5551, "lon": -81.7826, "expected_area_type": "exurban"},
    {"name": "Bozeman, Montana", "lat": 45.6770, "lon": -111.0429, "expected_area_type": "exurban"},
    {"name": "Bend, Oregon", "lat": 44.0582, "lon": -121.3153, "expected_area_type": "exurban"},
    {"name": "Boulder, Colorado", "lat": 40.0150, "lon": -105.2705, "expected_area_type": "exurban"},
    {"name": "Santa Fe, New Mexico", "lat": 35.6870, "lon": -105.9378, "expected_area_type": "exurban"},
    
    # Rural - Rural areas (currently 4, need 6+ more)
    {"name": "Stowe, Vermont", "lat": 44.4654, "lon": -72.6874, "expected_area_type": "rural"},
    {"name": "Jackson, Wyoming", "lat": 43.4799, "lon": -110.7624, "expected_area_type": "rural"},
    {"name": "Estes Park, Colorado", "lat": 40.3772, "lon": -105.5217, "expected_area_type": "rural"},
    {"name": "Bar Harbor, Maine", "lat": 44.3876, "lon": -68.2039, "expected_area_type": "rural"},
    # Additional Rural locations
    {"name": "Telluride, Colorado", "lat": 37.9375, "lon": -107.8123, "expected_area_type": "rural"},
    {"name": "Big Sky, Montana", "lat": 45.2847, "lon": -111.3683, "expected_area_type": "rural"},
    {"name": "Sun Valley, Idaho", "lat": 43.6971, "lon": -114.3517, "expected_area_type": "rural"},
    {"name": "Taos, New Mexico", "lat": 36.4072, "lon": -105.5731, "expected_area_type": "rural"},
    {"name": "Moab, Utah", "lat": 38.5733, "lon": -109.5498, "expected_area_type": "rural"},
    {"name": "Cody, Wyoming", "lat": 44.5263, "lon": -109.0565, "expected_area_type": "rural"},
]

# Output directory
OUTPUT_DIR = Path(__file__).parent.parent / "analysis" / "research_data"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

RAW_DATA_FILE = OUTPUT_DIR / "built_beauty_raw_data.json"
STATISTICS_FILE = OUTPUT_DIR / "built_beauty_statistics.json"


def collect_location_data(location: Dict, radius_m: int = 2000) -> Optional[Dict]:
    """
    Collect built beauty features for a location.
    
    Returns:
        Dict with location info and feature values, or None if data collection failed
    """
    print(f"\n{'='*60}")
    print(f"Collecting data for: {location['name']}")
    print(f"Coordinates: {location['lat']}, {location['lon']}")
    print(f"{'='*60}")
    
    try:
        # Compute architectural diversity metrics
        arch_result = compute_arch_diversity(
            location["lat"],
            location["lon"],
            radius_m=radius_m
        )
        
        if not arch_result:
            print(f"❌ Failed to get architectural diversity data")
            return None
        
        # Get area type classification
        density = census_api.get_population_density(location["lat"], location["lon"]) or 0.0
        area_type = classify_morphology(
            density,
            arch_result.get("built_coverage_ratio"),
            business_count=None,
            metro_distance_km=None,
            city=None,
            location_input=location["name"]
        )
        
        # Get built beauty score (includes form metrics)
        built_result = calculate_built_beauty(
            location["lat"],
            location["lon"],
            location_name=location["name"]
        )
        
        # Extract form metrics if available
        arch_details = built_result.get("architectural_details", {})
        metrics = arch_details.get("metrics", {}) if isinstance(arch_details, dict) else {}
        
        # Build data record
        data = {
            "name": location["name"],
            "lat": location["lat"],
            "lon": location["lon"],
            "expected_area_type": location.get("expected_area_type"),
            "actual_area_type": area_type,
            "density": density,
            
            # Core diversity metrics
            "height_diversity": arch_result.get("levels_entropy"),
            "type_diversity": arch_result.get("building_type_diversity"),
            "footprint_variation": arch_result.get("footprint_area_cv"),
            "built_coverage_ratio": arch_result.get("built_coverage_ratio"),
            
            # Form metrics (from built beauty calculation)
            "block_grain": metrics.get("block_grain"),
            "streetwall_continuity": metrics.get("streetwall_continuity"),
            "setback_consistency": metrics.get("setback_consistency"),
            "facade_rhythm": metrics.get("facade_rhythm"),
            
            # Score components
            "component_score": built_result.get("component_score_0_50"),
            "final_score": built_result.get("score"),
            "confidence": arch_result.get("confidence_0_1"),
            "data_warning": arch_result.get("data_warning"),
        }
        
        print(f"✅ Collected data:")
        print(f"   Area Type: {area_type} (expected: {location.get('expected_area_type')})")
        print(f"   Height Diversity: {data['height_diversity']:.1f}")
        print(f"   Type Diversity: {data['type_diversity']:.1f}")
        print(f"   Footprint Variation: {data['footprint_variation']:.1f}")
        print(f"   Built Coverage: {data['built_coverage_ratio']:.3f}")
        print(f"   Component Score: {data['component_score']:.1f}")
        
        return data
        
    except Exception as e:
        print(f"❌ Error collecting data: {e}")
        import traceback
        traceback.print_exc()
        return None


def calculate_statistics(values: List[float]) -> Dict:
    """Calculate statistics for a list of values."""
    if not values:
        return {
            "count": 0,
            "median": None,
            "p25": None,
            "p75": None,
            "min": None,
            "max": None,
        }
    
    return {
        "count": len(values),
        "median": statistics.median(values),
        "p25": statistics.quantiles(values, n=4)[0] if len(values) >= 4 else min(values),
        "p75": statistics.quantiles(values, n=4)[2] if len(values) >= 4 else max(values),
        "min": min(values),
        "max": max(values),
    }


def analyze_by_area_type(all_data: List[Dict]) -> Dict:
    """Analyze data grouped by area type."""
    by_area_type = defaultdict(list)
    
    for item in all_data:
        if item:
            area_type = item.get("actual_area_type", "unknown")
            by_area_type[area_type].append(item)
    
    analysis = {}
    for area_type, items in sorted(by_area_type.items()):
        print(f"\nAnalyzing {area_type} (n={len(items)})...")
        
        # Extract values for each metric
        metrics = {
            "height_diversity": [i["height_diversity"] for i in items if i.get("height_diversity") is not None],
            "type_diversity": [i["type_diversity"] for i in items if i.get("type_diversity") is not None],
            "footprint_variation": [i["footprint_variation"] for i in items if i.get("footprint_variation") is not None],
            "built_coverage_ratio": [i["built_coverage_ratio"] for i in items if i.get("built_coverage_ratio") is not None],
            "block_grain": [i["block_grain"] for i in items if i.get("block_grain") is not None],
            "streetwall_continuity": [i["streetwall_continuity"] for i in items if i.get("streetwall_continuity") is not None],
            "setback_consistency": [i["setback_consistency"] for i in items if i.get("setback_consistency") is not None],
            "facade_rhythm": [i["facade_rhythm"] for i in items if i.get("facade_rhythm") is not None],
            "component_score": [i["component_score"] for i in items if i.get("component_score") is not None],
        }
        
        analysis[area_type] = {
            "n": len(items),
            "locations": [i["name"] for i in items],
            "statistics": {
                metric_name: calculate_statistics(values)
                for metric_name, values in metrics.items()
            }
        }
        
        # Print summary
        stats = analysis[area_type]["statistics"]
        print(f"  Height Diversity: median={stats['height_diversity']['median']:.1f} (p25={stats['height_diversity']['p25']:.1f}, p75={stats['height_diversity']['p75']:.1f})")
        print(f"  Type Diversity: median={stats['type_diversity']['median']:.1f} (p25={stats['type_diversity']['p25']:.1f}, p75={stats['type_diversity']['p75']:.1f})")
        print(f"  Footprint Variation: median={stats['footprint_variation']['median']:.1f} (p25={stats['footprint_variation']['p25']:.1f}, p75={stats['footprint_variation']['p75']:.1f})")
        print(f"  Built Coverage: median={stats['built_coverage_ratio']['median']:.3f} (p25={stats['built_coverage_ratio']['p25']:.3f}, p75={stats['built_coverage_ratio']['p75']:.3f})")
    
    return analysis


def load_existing_data() -> List[Dict]:
    """Load existing raw data if available."""
    if RAW_DATA_FILE.exists():
        try:
            with open(RAW_DATA_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️  Could not load existing data: {e}")
    return []


def save_data(all_data: List[Dict], analysis: Dict):
    """Save raw data and analysis to files."""
    # Save raw data
    with open(RAW_DATA_FILE, 'w') as f:
        json.dump(all_data, f, indent=2)
    print(f"\n✅ Saved raw data to {RAW_DATA_FILE}")
    
    # Save statistics
    with open(STATISTICS_FILE, 'w') as f:
        json.dump(analysis, f, indent=2)
    print(f"✅ Saved statistics to {STATISTICS_FILE}")


def main():
    """Main collection function."""
    print("="*60)
    print("Built Beauty Research Data Collection")
    print("="*60)
    print(f"Total locations: {len(RESEARCH_LOCATIONS)}")
    print(f"Output directory: {OUTPUT_DIR}")
    print("="*60)
    
    # Load existing data
    existing_data = load_existing_data()
    existing_names = {item["name"] for item in existing_data if item}
    
    # Collect data for all locations
    all_data = existing_data.copy()
    new_count = 0
    
    for location in RESEARCH_LOCATIONS:
        if location["name"] in existing_names:
            print(f"\n⏭️  Skipping {location['name']} (already collected)")
            continue
        
        data = collect_location_data(location)
        if data:
            all_data.append(data)
            new_count += 1
        
        # Small delay to avoid overwhelming APIs
        if new_count < len(RESEARCH_LOCATIONS) - len(existing_names):
            import time
            time.sleep(2)
    
    print(f"\n{'='*60}")
    print("COLLECTION SUMMARY")
    print(f"{'='*60}")
    print(f"Total locations collected: {len(all_data)}")
    print(f"New locations this run: {new_count}")
    print(f"Failed/empty: {len(RESEARCH_LOCATIONS) - len(all_data)}")
    
    # Analyze by area type
    print(f"\n{'='*60}")
    print("STATISTICAL ANALYSIS")
    print(f"{'='*60}")
    analysis = analyze_by_area_type(all_data)
    
    # Save results
    save_data(all_data, analysis)
    
    print(f"\n{'='*60}")
    print("NEXT STEPS")
    print(f"{'='*60}")
    print("1. Review statistics in: analysis/research_data/built_beauty_statistics.json")
    print("2. Compare medians to current CONTEXT_TARGETS values")
    print("3. Consider sample sizes (aim for n>=10 per area type for high confidence)")
    print("4. Create analysis document with recommendations")
    print("="*60)


if __name__ == "__main__":
    main()
