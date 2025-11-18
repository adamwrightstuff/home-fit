#!/usr/bin/env python3
"""
Analyze tree canopy percentages by climate zone.

Samples diverse locations across climate zones, queries canopy data,
and aggregates statistics to inform climate-based expectation calibration.
"""

import sys
import os
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import csv
import statistics
from collections import defaultdict

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pillars.natural_beauty import _get_climate_adjustment, _get_adjusted_canopy_expectation
from data_sources.gee_api import get_tree_canopy_gee
from data_sources import data_quality

# Sample locations across climate zones
# Format: (name, lat, lon, expected_climate_zone)
SAMPLE_LOCATIONS = [
    # Arid/Desert (SW US)
    ("Phoenix AZ", 33.4484, -112.0740, "arid"),
    ("Tucson AZ", 32.2226, -110.9747, "arid"),
    ("Las Vegas NV", 36.1699, -115.1398, "arid"),
    ("Scottsdale AZ", 33.4995, -111.9117, "arid"),
    ("Palm Springs CA", 33.8303, -116.5453, "arid"),
    ("Albuquerque NM", 35.0844, -106.6504, "arid"),
    ("Reno NV", 39.5296, -119.8138, "arid"),
    ("El Paso TX", 31.7619, -106.4850, "arid"),
    
    # Mediterranean (Coastal CA)
    ("Los Angeles CA", 34.0522, -118.2437, "mediterranean"),
    ("San Diego CA", 32.7157, -117.1611, "mediterranean"),
    ("Santa Barbara CA", 34.4208, -119.6982, "mediterranean"),
    ("San Francisco CA", 37.7749, -122.4194, "mediterranean"),
    ("Santa Monica CA", 34.0195, -118.4912, "mediterranean"),
    ("Monterey CA", 36.6002, -121.8947, "mediterranean"),
    ("San Luis Obispo CA", 35.2828, -120.6596, "mediterranean"),
    
    # Temperate (Pacific Northwest, Northeast)
    ("Seattle WA", 47.6062, -122.3321, "temperate"),
    ("Portland OR", 45.5152, -122.6784, "temperate"),
    ("Boston MA", 42.3601, -71.0589, "temperate"),
    ("New York NY", 40.7128, -74.0060, "temperate"),
    ("Chicago IL", 41.8781, -87.6298, "temperate"),
    ("Philadelphia PA", 39.9526, -75.1652, "temperate"),
    ("Washington DC", 38.9072, -77.0369, "temperate"),
    ("Baltimore MD", 39.2904, -76.6122, "temperate"),
    ("Minneapolis MN", 44.9778, -93.2650, "temperate"),
    ("Milwaukee WI", 43.0389, -87.9065, "temperate"),
    
    # Tropical/Subtropical (South Florida, Gulf Coast)
    ("Miami FL", 25.7617, -80.1918, "tropical"),
    ("Key West FL", 24.5551, -81.7826, "tropical"),
    ("Tampa FL", 27.9506, -82.4572, "tropical"),
    ("Orlando FL", 28.5383, -81.3792, "tropical"),
    ("New Orleans LA", 29.9511, -90.0715, "tropical"),
    ("Houston TX", 29.7604, -95.3698, "tropical"),
    ("Atlanta GA", 33.7490, -84.3880, "tropical"),
    ("Charleston SC", 32.7765, -79.9311, "tropical"),
    
    # Continental (Interior, Mountain)
    ("Denver CO", 39.7392, -104.9903, "continental"),
    ("Salt Lake City UT", 40.7608, -111.8910, "continental"),
    ("Boise ID", 43.6150, -116.2023, "continental"),
    ("Kansas City MO", 39.0997, -94.5786, "continental"),
    ("St. Louis MO", 38.6270, -90.1994, "continental"),
    ("Detroit MI", 42.3314, -83.0458, "continental"),
    ("Cleveland OH", 41.4993, -81.6944, "continental"),
    ("Pittsburgh PA", 40.4406, -79.9959, "continental"),
    
    # Additional diverse locations
    ("Austin TX", 30.2672, -97.7431, "tropical"),
    ("Dallas TX", 32.7767, -96.7970, "tropical"),
    ("Nashville TN", 36.1627, -86.7816, "temperate"),
    ("Raleigh NC", 35.7796, -78.6382, "temperate"),
    ("Richmond VA", 37.5407, -77.4360, "temperate"),
    ("Columbus OH", 39.9612, -82.9988, "temperate"),
    ("Indianapolis IN", 39.7684, -86.1581, "temperate"),
]


def classify_climate_zone(lat: float, lon: float, elevation_m: float = 0) -> str:
    """
    Classify climate zone based on multiplier value.
    
    Returns simplified climate zone name for aggregation.
    """
    multiplier = _get_climate_adjustment(lat, lon, elevation_m)
    
    if multiplier < 0.75:
        return "arid"
    elif multiplier < 0.90:
        return "semi_arid"
    elif multiplier < 1.05:
        return "temperate"
    elif multiplier < 1.20:
        return "humid_temperate"
    else:
        return "tropical"


def analyze_location(name: str, lat: float, lon: float) -> Optional[Dict]:
    """Analyze a single location and return canopy data."""
    print(f"Analyzing: {name} ({lat:.4f}, {lon:.4f})...")
    
    try:
        # Get area type
        density = None
        try:
            from data_sources import census_api
            density = census_api.get_population_density(lat, lon)
        except Exception:
            pass
        
        area_type = data_quality.detect_area_type(lat, lon, density)
        
        # Get climate zone
        climate_zone = classify_climate_zone(lat, lon)
        climate_multiplier = _get_climate_adjustment(lat, lon, 0)
        
        # Get canopy data
        canopy_pct = get_tree_canopy_gee(lat, lon, radius_m=1000, area_type=area_type)
        
        if canopy_pct is None:
            print(f"  ⚠️  No canopy data available")
            return None
        
        # Get expectation
        expectation = _get_adjusted_canopy_expectation(area_type, lat, lon, 0)
        
        result = {
            "name": name,
            "lat": lat,
            "lon": lon,
            "area_type": area_type,
            "climate_zone": climate_zone,
            "climate_multiplier": round(climate_multiplier, 3),
            "canopy_pct": round(canopy_pct, 2),
            "expectation": round(expectation, 2),
            "ratio": round(canopy_pct / expectation, 3) if expectation > 0 else None,
        }
        
        print(f"  ✅ Canopy: {canopy_pct:.1f}%, Climate: {climate_zone} ({climate_multiplier:.2f}x), Area: {area_type}")
        return result
        
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return None


def aggregate_by_climate(results: List[Dict]) -> Dict:
    """Aggregate results by climate zone."""
    by_climate = defaultdict(list)
    
    for result in results:
        if result:
            by_climate[result["climate_zone"]].append(result["canopy_pct"])
    
    summary = {}
    for zone, canopy_values in by_climate.items():
        if len(canopy_values) > 0:
            summary[zone] = {
                "count": len(canopy_values),
                "mean": round(statistics.mean(canopy_values), 2),
                "median": round(statistics.median(canopy_values), 2),
                "min": round(min(canopy_values), 2),
                "max": round(max(canopy_values), 2),
            }
            if len(canopy_values) >= 4:
                sorted_values = sorted(canopy_values)
                q1_idx = len(sorted_values) // 4
                q3_idx = 3 * len(sorted_values) // 4
                summary[zone]["q25"] = round(sorted_values[q1_idx], 2)
                summary[zone]["q75"] = round(sorted_values[q3_idx], 2)
    
    return summary


def main():
    """Main analysis function."""
    print("=" * 80)
    print("Canopy Analysis by Climate Zone")
    print("=" * 80)
    print(f"Analyzing {len(SAMPLE_LOCATIONS)} locations...")
    print()
    
    results = []
    for name, lat, lon, expected_zone in SAMPLE_LOCATIONS:
        result = analyze_location(name, lat, lon)
        if result:
            results.append(result)
    
    print()
    print("=" * 80)
    print("Results Summary")
    print("=" * 80)
    print(f"Successfully analyzed: {len(results)}/{len(SAMPLE_LOCATIONS)} locations")
    print()
    
    # Aggregate by climate zone
    summary = aggregate_by_climate(results)
    
    print("Canopy Statistics by Climate Zone:")
    print("-" * 80)
    for zone in sorted(summary.keys()):
        stats = summary[zone]
        print(f"{zone.upper()}:")
        print(f"  Count: {stats['count']}")
        print(f"  Mean: {stats['mean']}%")
        print(f"  Median: {stats['median']}%")
        if 'q25' in stats:
            print(f"  Q25: {stats['q25']}%, Q75: {stats['q75']}%")
        print(f"  Range: {stats['min']}% - {stats['max']}%")
        print()
    
    # Save to CSV
    output_dir = Path(__file__).parent.parent / "analysis"
    output_dir.mkdir(exist_ok=True)
    
    csv_path = output_dir / "canopy_by_climate.csv"
    with open(csv_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            "name", "lat", "lon", "area_type", "climate_zone", 
            "climate_multiplier", "canopy_pct", "expectation", "ratio"
        ])
        writer.writeheader()
        writer.writerows(results)
    
    print(f"✅ Results saved to: {csv_path}")
    
    # Save summary
    summary_path = output_dir / "canopy_by_climate_summary.txt"
    with open(summary_path, 'w') as f:
        f.write("Canopy Statistics by Climate Zone\n")
        f.write("=" * 80 + "\n\n")
        for zone in sorted(summary.keys()):
            stats = summary[zone]
            f.write(f"{zone.upper()}:\n")
            f.write(f"  Count: {stats['count']}\n")
            f.write(f"  Mean: {stats['mean']}%\n")
            f.write(f"  Median: {stats['median']}%\n")
            if 'q25' in stats:
                f.write(f"  Q25: {stats['q25']}%, Q75: {stats['q75']}%\n")
            f.write(f"  Range: {stats['min']}% - {stats['max']}%\n")
            f.write("\n")
    
    print(f"✅ Summary saved to: {summary_path}")
    
    return results, summary


if __name__ == "__main__":
    main()

