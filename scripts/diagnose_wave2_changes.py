#!/usr/bin/env python3
"""
Wave 2 Diagnostic Script

Compares Wave 1 vs Wave 2 scoring on the 60-location research set to verify:
1. Coverage regression check: Urban/historic stable (±5%), suburban/exurban show differentiation
2. Block grain distribution check: Verify sweet spots align with data
3. Composite score movement: Expect 3-8 point shifts in suburban/exurban

Usage:
    python scripts/diagnose_wave2_changes.py
"""

import sys
import os
import json
from pathlib import Path
from typing import Dict, List, Optional
from collections import defaultdict
import statistics

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data_sources.arch_diversity import (
    compute_arch_diversity,
    score_architectural_diversity_as_beauty,
    _score_band,
    COVERAGE_TARGETS,
    DESIGN_FORM_SCALE
)
from data_sources.data_quality import classify_morphology
from data_sources import census_api
from data_sources.radius_profiles import get_radius_profile
from pillars.built_beauty import calculate_built_beauty

# Import Wave 2 functions for comparison
from data_sources.arch_diversity import (
    _score_coverage_with_hump,
    _score_block_grain_with_sweet_spot
)

# Load research locations
RESEARCH_LOCATIONS = [
    # Urban Core
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
    {"name": "Back Bay, Boston MA", "lat": 42.3519, "lon": -71.0805, "expected_area_type": "urban_core"},
    {"name": "SoHo, New York NY", "lat": 40.7231, "lon": -74.0026, "expected_area_type": "urban_core"},
    {"name": "Union Square, San Francisco CA", "lat": 37.7879, "lon": -122.4075, "expected_area_type": "urban_core"},
    {"name": "Wicker Park, Chicago IL", "lat": 41.9067, "lon": -87.6775, "expected_area_type": "urban_core"},
    {"name": "Downtown, Portland OR", "lat": 45.5152, "lon": -122.6784, "expected_area_type": "urban_core"},
    {"name": "Historic Core, Los Angeles CA", "lat": 34.0505, "lon": -118.2442, "expected_area_type": "urban_core"},
    
    # Urban Residential
    {"name": "Park Slope, Brooklyn NY", "lat": 40.6715, "lon": -73.9772, "expected_area_type": "urban_residential"},
    {"name": "German Village, Columbus OH", "lat": 39.9518, "lon": -82.9988, "expected_area_type": "urban_residential"},
    {"name": "Old Town, Alexandria VA", "lat": 38.8048, "lon": -77.0469, "expected_area_type": "urban_residential"},
    {"name": "Capitol Hill, Seattle WA", "lat": 47.6225, "lon": -122.3237, "expected_area_type": "urban_residential"},
    {"name": "Highland Park, Los Angeles CA", "lat": 34.1147, "lon": -118.1929, "expected_area_type": "urban_residential"},
    {"name": "Brooklyn Heights, New York NY", "lat": 40.6957, "lon": -73.9973, "expected_area_type": "urban_residential"},
    {"name": "Carroll Gardens, Brooklyn NY", "lat": 40.6790, "lon": -73.9910, "expected_area_type": "urban_residential"},
    {"name": "Cobble Hill, Brooklyn NY", "lat": 40.6895, "lon": -73.9963, "expected_area_type": "urban_residential"},
    {"name": "Mount Vernon, Baltimore MD", "lat": 39.2976, "lon": -76.6154, "expected_area_type": "urban_residential"},
    {"name": "Oakland, Pittsburgh PA", "lat": 40.4324, "lon": -79.9523, "expected_area_type": "urban_residential"},
    {"name": "Ballard, Seattle WA", "lat": 47.6680, "lon": -122.3846, "expected_area_type": "urban_residential"},
    {"name": "Tremont, Cleveland OH", "lat": 41.4818, "lon": -81.6949, "expected_area_type": "urban_residential"},
    
    # Suburban
    {"name": "Levittown, Pennsylvania", "lat": 40.1551, "lon": -74.8288, "expected_area_type": "suburban"},
    {"name": "Celebration, Florida", "lat": 28.3186, "lon": -81.5401, "expected_area_type": "suburban"},
    {"name": "Woodbridge, Irvine CA", "lat": 33.6253, "lon": -117.8399, "expected_area_type": "suburban"},
    {"name": "Reston, Virginia", "lat": 38.9586, "lon": -77.3570, "expected_area_type": "suburban"},
    {"name": "Coral Gables, Florida", "lat": 25.7214, "lon": -80.2684, "expected_area_type": "suburban"},
    {"name": "Evanston, Illinois", "lat": 42.0451, "lon": -87.6877, "expected_area_type": "suburban"},
    {"name": "Montclair, New Jersey", "lat": 40.8259, "lon": -74.2090, "expected_area_type": "suburban"},
    {"name": "Bellevue, Washington", "lat": 47.6101, "lon": -122.2015, "expected_area_type": "suburban"},
    {"name": "Scarsdale, New York", "lat": 40.9887, "lon": -73.7968, "expected_area_type": "suburban"},
    {"name": "Palo Alto, California", "lat": 37.4419, "lon": -122.1430, "expected_area_type": "suburban"},
    {"name": "Oak Park, Illinois", "lat": 41.8850, "lon": -87.7845, "expected_area_type": "suburban"},
    
    # Exurban
    {"name": "Carmel-by-the-Sea, California", "lat": 36.5552, "lon": -121.9233, "expected_area_type": "exurban"},
    {"name": "Sedona, Arizona", "lat": 34.8697, "lon": -111.7610, "expected_area_type": "exurban"},
    {"name": "Nantucket, Massachusetts", "lat": 41.2835, "lon": -70.0995, "expected_area_type": "exurban"},
    {"name": "Park City, Utah", "lat": 40.6461, "lon": -111.4980, "expected_area_type": "exurban"},
    {"name": "Aspen, Colorado", "lat": 39.1911, "lon": -106.8175, "expected_area_type": "exurban"},
    {"name": "Key West, Florida", "lat": 24.5551, "lon": -81.7826, "expected_area_type": "exurban"},
    {"name": "Bozeman, Montana", "lat": 45.6770, "lon": -111.0429, "expected_area_type": "exurban"},
    {"name": "Bend, Oregon", "lat": 44.0582, "lon": -121.3153, "expected_area_type": "exurban"},
    {"name": "Boulder, Colorado", "lat": 40.0150, "lon": -105.2705, "expected_area_type": "exurban"},
    {"name": "Santa Fe, New Mexico", "lat": 35.6870, "lon": -105.9378, "expected_area_type": "exurban"},
    
    # Rural
    {"name": "Stowe, Vermont", "lat": 44.4654, "lon": -72.6874, "expected_area_type": "rural"},
    {"name": "Jackson, Wyoming", "lat": 43.4799, "lon": -110.7624, "expected_area_type": "rural"},
    {"name": "Telluride, Colorado", "lat": 37.9375, "lon": -107.8123, "expected_area_type": "rural"},
    {"name": "Lake Placid, New York", "lat": 44.2795, "lon": -73.9833, "expected_area_type": "rural"},
    {"name": "Whitefish, Montana", "lat": 48.4111, "lon": -114.3376, "expected_area_type": "rural"},
    {"name": "Breckenridge, Colorado", "lat": 39.4817, "lon": -106.0384, "expected_area_type": "rural"},
    {"name": "Steamboat Springs, Colorado", "lat": 40.4850, "lon": -106.8317, "expected_area_type": "rural"},
    {"name": "Durango, Colorado", "lat": 37.2753, "lon": -107.8801, "expected_area_type": "rural"},
    {"name": "Vail, Colorado", "lat": 39.6403, "lon": -106.3742, "expected_area_type": "rural"},
    {"name": "Aspen, Colorado", "lat": 39.1911, "lon": -106.8175, "expected_area_type": "rural"},
    {"name": "Big Sky, Montana", "lat": 45.2847, "lon": -111.3680, "expected_area_type": "rural"},
    {"name": "Sun Valley, Idaho", "lat": 43.6801, "lon": -114.3616, "expected_area_type": "rural"},
    {"name": "Taos, New Mexico", "lat": 36.4072, "lon": -105.5731, "expected_area_type": "rural"},
    {"name": "Moab, Utah", "lat": 38.5733, "lon": -109.5498, "expected_area_type": "rural"},
    {"name": "Bozeman, Montana", "lat": 45.6770, "lon": -111.0429, "expected_area_type": "rural"},
]


def calculate_wave1_coverage_score(built_coverage_ratio: float, area_type: str, is_spacious_historic: bool) -> float:
    """Calculate Wave 1 coverage score (using _score_band)."""
    if is_spacious_historic:
        coverage_targets = (8, 15, 30, 40)
    else:
        coverage_targets = COVERAGE_TARGETS.get(area_type, COVERAGE_TARGETS["unknown"])
    
    coverage_max_points = 12.0
    if area_type in ("urban_core", "urban_core_lowrise"):
        coverage_max_points = 15.0
    elif area_type == "urban_residential":
        coverage_max_points = 13.0
    
    return _score_band(built_coverage_ratio * 100.0, coverage_targets, max_points=coverage_max_points)


def calculate_wave1_block_grain_score(block_grain_value: float) -> float:
    """Calculate Wave 1 block grain score (linear)."""
    return (block_grain_value / 100.0) * 16.67


def main():
    print("="*80)
    print("WAVE 2 DIAGNOSTIC: Comparing Wave 1 vs Wave 2 on 60-Location Set")
    print("="*80)
    print()
    
    results_by_area_type = defaultdict(list)
    
    for i, location in enumerate(RESEARCH_LOCATIONS, 1):
        name = location['name']
        lat = location['lat']
        lon = location['lon']
        expected_area_type = location.get('expected_area_type', 'unknown')
        
        print(f"[{i}/{len(RESEARCH_LOCATIONS)}] {name}...", end=" ", flush=True)
        
        try:
            # Get area type and density
            density = census_api.get_population_density(lat, lon) or 0.0
            area_type = classify_morphology(density, None, None, metro_distance_km=None)
            
            # Compute architectural diversity
            radius_m = 2000
            rp = get_radius_profile('built_beauty', area_type, None)
            radius_m = int(rp.get('architectural_diversity_radius_m', 2000))
            
            diversity_metrics = compute_arch_diversity(lat, lon, radius_m=radius_m)
            if 'error' in diversity_metrics:
                print(f"✗ Error: {diversity_metrics.get('error')}")
                continue
            
            built_coverage_ratio = diversity_metrics.get('built_coverage_ratio')
            # Block grain is computed in score_architectural_diversity_as_beauty via compute_form_metrics
            # We need to compute it separately to get the raw value
            from data_sources.street_geometry import compute_block_grain
            block_grain_result = compute_block_grain(lat, lon, radius_m=radius_m)
            block_grain_value = block_grain_result.get('value') if isinstance(block_grain_result, dict) else None
            
            # Get historic context for coverage scoring
            from pillars.built_beauty import _fetch_historic_data
            historic_data = _fetch_historic_data(lat, lon, radius_m=radius_m)
            median_year_built = historic_data.get('median_year_built')
            historic_landmarks = historic_data.get('historic_landmarks_count', 0)
            
            from data_sources.arch_diversity import _is_spacious_historic_district
            is_spacious_historic = False
            if built_coverage_ratio is not None:
                is_spacious_historic = _is_spacious_historic_district(
                    area_type,
                    built_coverage_ratio,
                    historic_landmarks,
                    median_year_built
                )
            
            # Calculate Wave 1 scores
            wave1_coverage = None
            if built_coverage_ratio is not None:
                wave1_coverage = calculate_wave1_coverage_score(built_coverage_ratio, area_type, is_spacious_historic)
            
            wave1_block_grain = None
            if block_grain_value is not None:
                wave1_block_grain = calculate_wave1_block_grain_score(block_grain_value)
            
            # Calculate Wave 2 scores
            wave2_coverage = None
            if built_coverage_ratio is not None:
                coverage_max_points = 12.0
                if area_type in ("urban_core", "urban_core_lowrise"):
                    coverage_max_points = 15.0
                elif area_type == "urban_residential":
                    coverage_max_points = 13.0
                wave2_coverage = _score_coverage_with_hump(
                    built_coverage_ratio * 100.0,
                    area_type,
                    max_points=coverage_max_points,
                    is_spacious_historic=is_spacious_historic
                )
            
            wave2_block_grain = None
            if block_grain_value is not None:
                wave2_block_grain = _score_block_grain_with_sweet_spot(block_grain_value, area_type)
            
            # Get full built beauty score (Wave 2)
            result = calculate_built_beauty(
                lat=lat,
                lon=lon,
                area_type=area_type,
                density=density
            )
            wave2_composite = result.get('score', 0.0)
            
            # Store results
            results_by_area_type[area_type].append({
                'name': name,
                'coverage_ratio': built_coverage_ratio,
                'block_grain': block_grain_value,
                'wave1_coverage': wave1_coverage,
                'wave2_coverage': wave2_coverage,
                'wave1_block_grain': wave1_block_grain,
                'wave2_block_grain': wave2_block_grain,
                'wave2_composite': wave2_composite,
                'coverage_diff': wave2_coverage - wave1_coverage if (wave1_coverage and wave2_coverage) else None,
                'block_grain_diff': wave2_block_grain - wave1_block_grain if (wave1_block_grain and wave2_block_grain) else None
            })
            
            print("✓")
            
        except Exception as e:
            print(f"✗ Error: {e}")
            import traceback
            traceback.print_exc()
    
    # Analyze results
    print()
    print("="*80)
    print("ANALYSIS RESULTS")
    print("="*80)
    print()
    
    # 1. Coverage regression check
    print("1. COVERAGE REGRESSION CHECK")
    print("-"*80)
    for area_type in sorted(results_by_area_type.keys()):
        locations = results_by_area_type[area_type]
        coverage_diffs = [r['coverage_diff'] for r in locations if r['coverage_diff'] is not None]
        if not coverage_diffs:
            continue
        
        avg_diff = statistics.mean(coverage_diffs)
        avg_pct_change = statistics.mean([
            (r['coverage_diff'] / r['wave1_coverage'] * 100) 
            for r in locations 
            if r['coverage_diff'] is not None and r['wave1_coverage'] > 0
        ])
        
        print(f"\n{area_type.upper()} (n={len(coverage_diffs)}):")
        print(f"  Average coverage score change: {avg_diff:+.2f} points")
        print(f"  Average percentage change: {avg_pct_change:+.1f}%")
        
        # Check stability for urban/historic
        if area_type in ('urban_core', 'urban_residential', 'historic_urban'):
            if abs(avg_pct_change) <= 5.0:
                print(f"  ✅ STABLE (within ±5%)")
            else:
                print(f"  ⚠️  NOT STABLE (outside ±5%)")
        else:
            # Check for differentiation for suburban/exurban
            if abs(avg_diff) >= 0.5:
                print(f"  ✅ SHOWS DIFFERENTIATION (change >= 0.5 points)")
            else:
                print(f"  ⚠️  MINIMAL CHANGE (may need tuning)")
    
    # 2. Block grain distribution check
    print()
    print("2. BLOCK GRAIN DISTRIBUTION CHECK")
    print("-"*80)
    for area_type in sorted(results_by_area_type.keys()):
        locations = results_by_area_type[area_type]
        block_grains = [r['block_grain'] for r in locations if r['block_grain'] is not None]
        if not block_grains:
            continue
        
        # Calculate percentiles
        block_grains_sorted = sorted(block_grains)
        p25 = block_grains_sorted[len(block_grains_sorted) // 4]
        median = block_grains_sorted[len(block_grains_sorted) // 2]
        p75 = block_grains_sorted[3 * len(block_grains_sorted) // 4]
        
        print(f"\n{area_type.upper()} (n={len(block_grains)}):")
        print(f"  Block grain distribution: p25={p25:.1f}, median={median:.1f}, p75={p75:.1f}")
        
        # Check against sweet spots
        if area_type in ('urban_core', 'urban_residential', 'urban_core_lowrise'):
            sweet_spot = (60, 85)
            if p25 >= sweet_spot[0] and p75 <= sweet_spot[1]:
                print(f"  ✅ ALIGNED (most in sweet spot 60-85)")
            else:
                print(f"  ⚠️  NEEDS ADJUSTMENT (sweet spot: 60-85, actual: {p25:.1f}-{p75:.1f})")
        elif area_type == 'suburban':
            sweet_spot = (40, 65)
            if p25 >= sweet_spot[0] and p75 <= sweet_spot[1]:
                print(f"  ✅ ALIGNED (most in sweet spot 40-65)")
            else:
                print(f"  ⚠️  NEEDS ADJUSTMENT (sweet spot: 40-65, actual: {p25:.1f}-{p75:.1f})")
        elif area_type in ('exurban', 'rural'):
            sweet_spot = (30, 45)
            if p25 >= sweet_spot[0] and p75 <= sweet_spot[1]:
                print(f"  ✅ ALIGNED (most in sweet spot 30-45)")
            else:
                print(f"  ⚠️  NEEDS ADJUSTMENT (sweet spot: 30-45, actual: {p25:.1f}-{p75:.1f})")
    
    # 3. Composite score movement (we only have Wave 2 composite, so we can't compare directly)
    # But we can analyze the distribution
    print()
    print("3. COMPOSITE SCORE ANALYSIS (Wave 2)")
    print("-"*80)
    for area_type in sorted(results_by_area_type.keys()):
        locations = results_by_area_type[area_type]
        scores = [r['wave2_composite'] for r in locations]
        if not scores:
            continue
        
        score_min = min(scores)
        score_max = max(scores)
        score_range = score_max - score_min
        score_avg = statistics.mean(scores)
        
        print(f"\n{area_type.upper()} (n={len(scores)}):")
        print(f"  Score range: {score_min:.1f} - {score_max:.1f} (span: {score_range:.1f} points)")
        print(f"  Average score: {score_avg:.1f}")
        
        if area_type in ('suburban', 'exurban'):
            if score_range >= 15.0:
                print(f"  ✅ GOOD DIFFERENTIATION (range >= 15 points)")
            else:
                print(f"  ⚠️  LIMITED DIFFERENTIATION (range < 15 points)")
        elif area_type in ('urban_core', 'urban_residential', 'historic_urban'):
            if score_range <= 25.0:
                print(f"  ✅ REASONABLE RANGE (not too wide)")
            else:
                print(f"  ⚠️  WIDE RANGE (may need review)")
    
    print()
    print("="*80)
    print("DIAGNOSTIC COMPLETE")
    print("="*80)


if __name__ == "__main__":
    main()
