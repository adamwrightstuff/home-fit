#!/usr/bin/env python3
"""
Debug script for Built Beauty pillar.
Tests OSM data retrieval and feature calculations step by step.
Step 6: Benchmark testing with expected score ranges.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data_sources.arch_diversity import compute_arch_diversity
from pillars.built_beauty import calculate_built_beauty
import json

# Test locations with expected score ranges
BEACON_HILL = {
    "name": "Beacon Hill",
    "lat": 42.3588,
    "lon": -71.0707,
    "radius_m": 2000,  # Use standard radius for full scoring
    "expected_score_range": (85, 95),
    "expected_score": 90  # Midpoint for error calculation
}

LEVITTOWN = {
    "name": "Levittown, PA",
    "lat": 40.1551,
    "lon": -74.8288,
    "radius_m": 2000,  # Standard radius
    "expected_score_range": (35, 50),
    "expected_score": 42.5  # Midpoint for error calculation
}

# Additional test cases for Step 7
GEORGETOWN_DC = {
    "name": "Georgetown, DC",
    "lat": 38.9096,
    "lon": -77.0634,
    "radius_m": 2000,
    "expected_score_range": (80, 92),
    "expected_score": 86.0
}

GERMAN_VILLAGE = {
    "name": "German Village, Columbus OH",
    "lat": 39.9518,
    "lon": -82.9988,
    "radius_m": 2000,
    "expected_score_range": (75, 88),
    "expected_score": 81.5
}

CELEBRATION_FL = {
    "name": "Celebration, FL",
    "lat": 28.3186,
    "lon": -81.5401,
    "radius_m": 2000,
    "expected_score_range": (70, 85),
    "expected_score": 77.5
}

WOODBRIDGE_IRVINE = {
    "name": "Woodbridge, Irvine CA",
    "lat": 33.6253,
    "lon": -117.8399,
    "radius_m": 2000,
    "expected_score_range": (65, 80),
    "expected_score": 72.5
}

TEST_LOCATIONS = [BEACON_HILL, LEVITTOWN, GEORGETOWN_DC, GERMAN_VILLAGE, CELEBRATION_FL, WOODBRIDGE_IRVINE]

def test_built_beauty_benchmark(location):
    """Step 6: Test Built Beauty scoring against benchmarks"""
    print(f"\n{'='*60}")
    print(f"Benchmark Test: {location['name']}")
    print(f"{'='*60}")
    print(f"Coordinates: {location['lat']}, {location['lon']}")
    print(f"Expected score range: {location['expected_score_range'][0]}-{location['expected_score_range'][1]}")
    print(f"Expected score (midpoint): {location['expected_score']}")
    
    try:
        # Calculate built beauty score
        result = calculate_built_beauty(
            location['lat'],
            location['lon'],
            location_name=location['name']
        )
        
        # Extract scores and features
        final_score = result.get('score', 0)
        score_before_norm = result.get('score_before_normalization', 0)
        component_score = result.get('component_score_0_50', 0)
        enhancer_bonus = result.get('built_bonus_scaled', 0)
        
        # Get architectural details
        arch_details = result.get('architectural_details', {})
        metrics = arch_details.get('metrics', {}) if isinstance(arch_details, dict) else {}
        
        height_diversity = metrics.get('height_diversity', 0)
        type_diversity = metrics.get('type_diversity', 0)
        footprint_variation = metrics.get('footprint_variation', 0)
        built_coverage_ratio = metrics.get('built_coverage_ratio', 0)
        block_grain = metrics.get('block_grain', 0)
        streetwall_continuity = metrics.get('streetwall_continuity', 0)
        setback_consistency = metrics.get('setback_consistency', 0)
        facade_rhythm = metrics.get('facade_rhythm', 0)
        
        print(f"\n{'─'*60}")
        print("FEATURE VALUES:")
        print(f"{'─'*60}")
        print(f"  Height Diversity:        {height_diversity:.2f}")
        print(f"  Type Diversity:          {type_diversity:.2f}")
        print(f"  Footprint Variation:     {footprint_variation:.2f}")
        print(f"  Built Coverage Ratio:    {built_coverage_ratio:.4f}")
        print(f"  Block Grain:             {block_grain:.2f}")
        print(f"  Streetwall Continuity:   {streetwall_continuity:.2f}")
        print(f"  Setback Consistency:     {setback_consistency:.2f}")
        print(f"  Facade Rhythm:           {facade_rhythm:.2f}")
        
        print(f"\n{'─'*60}")
        print("SCORING BREAKDOWN:")
        print(f"{'─'*60}")
        print(f"  Component Score (0-50):  {component_score:.2f}")
        print(f"  Enhancer Bonus:          {enhancer_bonus:.2f}")
        print(f"  Score Before Norm:       {score_before_norm:.2f}")
        print(f"  Final Score (0-100):     {final_score:.2f}")
        
        # Compare to expected range
        expected_min, expected_max = location['expected_score_range']
        in_range = expected_min <= final_score <= expected_max
        error = abs(final_score - location['expected_score'])
        
        print(f"\n{'─'*60}")
        print("VALIDATION:")
        print(f"{'─'*60}")
        if in_range:
            print(f"  ✅ Score {final_score:.1f} is within expected range [{expected_min}, {expected_max}]")
        else:
            print(f"  ❌ Score {final_score:.1f} is OUTSIDE expected range [{expected_min}, {expected_max}]")
            if final_score < expected_min:
                print(f"     Score is {expected_min - final_score:.1f} points too low")
            else:
                print(f"     Score is {final_score - expected_max:.1f} points too high")
        
        print(f"  Error (vs midpoint): {error:.2f} points")
        
        # Check for zero features (problem indicator)
        zero_features = []
        if height_diversity == 0:
            zero_features.append("height_diversity")
        if type_diversity == 0:
            zero_features.append("type_diversity")
        if footprint_variation == 0:
            zero_features.append("footprint_variation")
        if built_coverage_ratio == 0:
            zero_features.append("built_coverage_ratio")
        
        if zero_features:
            print(f"\n  ⚠️  Warning: {len(zero_features)} features are zero: {', '.join(zero_features)}")
        else:
            print(f"\n  ✅ All features are non-zero")
        
        return {
            "name": location['name'],
            "final_score": final_score,
            "expected_score": location['expected_score'],
            "expected_min": expected_min,
            "expected_max": expected_max,
            "in_range": in_range,
            "error": error,
            "features": {
                "height_diversity": height_diversity,
                "type_diversity": type_diversity,
                "footprint_variation": footprint_variation,
                "built_coverage_ratio": built_coverage_ratio,
                "block_grain": block_grain,
                "streetwall_continuity": streetwall_continuity,
                "setback_consistency": setback_consistency,
                "facade_rhythm": facade_rhythm
            },
            "component_score": component_score,
            "enhancer_bonus": enhancer_bonus
        }
        
    except Exception as e:
        print(f"\n❌ EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    print("Built Beauty Pillar Benchmark Testing")
    print("=" * 60)
    
    results = []
    
    # Test all locations
    for location in TEST_LOCATIONS:
        location_result = test_built_beauty_benchmark(location)
        if location_result:
            results.append(location_result)
        print(f"\n\n")
    
    # Summary
    print(f"\n\n{'='*60}")
    print("BENCHMARK SUMMARY")
    print(f"{'='*60}")
    
    if results:
        total_error = sum(r['error'] for r in results)
        mae = total_error / len(results)
        in_range_count = sum(1 for r in results if r['in_range'])
        
        print(f"\nLocations tested: {len(results)}")
        print(f"Locations in expected range: {in_range_count}/{len(results)}")
        print(f"Mean Absolute Error (MAE): {mae:.2f} points")
        print(f"\nGoal: MAE < 15 points")
        if mae < 15:
            print(f"✅ MAE {mae:.2f} meets goal (< 15)")
        else:
            print(f"❌ MAE {mae:.2f} exceeds goal (>= 15)")
        
        print(f"\nDetailed results:")
        for r in results:
            status = "✅" if r['in_range'] else "❌"
            print(f"  {status} {r['name']}: {r['final_score']:.1f} (expected: {r['expected_min']}-{r['expected_max']}, error: {r['error']:.1f})")
    
    print(f"\n{'='*60}")
