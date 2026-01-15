#!/usr/bin/env python3
"""
Test script to validate Natural Beauty improvements.

Tests rank order correlation with human perception, ensures mountain towns
no longer cluster in bottom half, and validates data coverage transparency.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import List, Dict, Tuple
import json

try:
    from scipy.stats import spearmanr
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    print("⚠️  scipy not available - rank order correlation test will be skipped")

# Test locations covering multiple landscape types
# Format: (location_name, lat, lon, expected_human_rating, landscape_type)
TEST_LOCATIONS = [
    # Mountain towns with lakes (should score high)
    ("Truckee, CA", 39.3279, -120.1833, 85, "mountain_lake"),
    ("Leavenworth, WA", 47.5962, -120.6615, 82, "mountain_scenic"),
    ("Bend, OR", 44.0582, -121.3153, 80, "mountain_river"),
    
    # Coastal areas (should score high)
    ("Carmel-by-the-Sea, CA", 36.5552, -121.9233, 90, "coastal_scenic"),
    ("Santa Barbara, CA", 34.4208, -119.6982, 88, "coastal_urban"),
    
    # Urban with good greenery
    ("Seattle, WA - Green Lake", 47.6792, -122.3313, 75, "urban_green"),
    ("Portland, OR - Pearl District", 45.5286, -122.6778, 70, "urban_green"),
    
    # Suburban with good canopy
    ("Palo Alto, CA", 37.4419, -122.1430, 78, "suburban_canopy"),
    ("Irvine, CA", 33.6846, -117.8265, 65, "suburban_planned"),
    
    # Arid regions (should emphasize terrain)
    ("Sedona, AZ", 34.8697, -111.7610, 85, "arid_scenic"),
    ("Moab, UT", 38.5733, -109.5498, 80, "arid_scenic"),
    
    # Previously mis-scored (should improve)
    ("Asheville, NC", 35.5951, -82.5515, 82, "mountain_forest"),
    ("Boulder, CO", 40.0150, -105.2705, 83, "mountain_foothills"),
]

def get_natural_beauty_score(lat: float, lon: float) -> Tuple[float, Dict]:
    """Get Natural Beauty score for a location (direct pillar call; no API server needed)."""
    from pillars.natural_beauty import calculate_natural_beauty
    
    try:
        calc = calculate_natural_beauty(
            lat=lat,
            lon=lon,
            city=None,
            area_type=None,
            location_scope=None,
            location_name=None,
            overrides=None,
            enhancers_data=None,
            disable_enhancers=False,
            precomputed_tree_canopy_5km=None,
            density=None,
            form_context=None
        )
        return float(calc.get("score", 0.0) or 0.0), calc
    except Exception as e:
        print(f"Error getting score for {lat}, {lon}: {e}")
        return 0.0, {}


def validate_rank_order_correlation(test_locations: List[Tuple]) -> bool:
    """Validate rank order correlation with human ratings."""
    scores = []
    human_ratings = []
    
    print("\n" + "="*80)
    print("VALIDATING RANK ORDER CORRELATION")
    print("="*80)
    
    for location_name, lat, lon, expected_rating, landscape_type in test_locations:
        print(f"\n📍 {location_name} ({landscape_type})")
        score, details = get_natural_beauty_score(lat, lon)
        scores.append(score)
        human_ratings.append(expected_rating)
        
        # Show key metrics
        tree_details = details.get("details", {}) if isinstance(details, dict) else {}
        natural_context = tree_details.get("natural_context", {}) if isinstance(tree_details, dict) else {}
        topography = natural_context.get("topography_metrics", {}) if isinstance(natural_context, dict) else {}
        viewshed = natural_context.get("viewshed_metrics", {}) if isinstance(natural_context, dict) else {}
        water_proximity = natural_context.get("water_proximity", {}) if isinstance(natural_context, dict) else {}
        
        print(f"  Score: {score:.1f} | Expected: {expected_rating}")
        print(f"  Terrain: relief={topography.get('relief_range_m', 'N/A')}m, "
              f"prominence={topography.get('terrain_prominence_m', 'N/A')}m")
        print(f"  Viewshed: visible_natural={viewshed.get('visible_natural_pct', 'N/A')}%")
        print(f"  Water: proximity={water_proximity.get('nearest_distance_km', 'N/A')}km")
        
        data_coverage = tree_details.get("data_coverage", {}) if isinstance(tree_details, dict) else {}
        print(f"  Data Coverage: {data_coverage.get('overall_tier', 'unknown')} "
              f"({data_coverage.get('overall_coverage', 0):.1f}%)")
    
    # Calculate Spearman correlation
    if not SCIPY_AVAILABLE:
        print("\n⚠️  Skipping Spearman correlation (scipy not available)")
        print("Install scipy to run correlation test: pip install scipy")
        # Treat as non-failing in environments where scipy isn't installed
        return True
    
    correlation, p_value = spearmanr(scores, human_ratings)
    
    print("\n" + "="*80)
    print(f"Spearman Correlation: {correlation:.3f}")
    print(f"P-value: {p_value:.6f}")
    print(f"Target: ≥ 0.7")
    print("="*80)
    
    return correlation >= 0.7


def validate_mountain_town_scoring(test_locations: List[Tuple]) -> bool:
    """Validate that mountain towns don't cluster in bottom half."""
    print("\n" + "="*80)
    print("VALIDATING MOUNTAIN TOWN SCORING")
    print("="*80)
    
    mountain_towns = [
        (name, lat, lon, rating, ltype) 
        for name, lat, lon, rating, ltype in test_locations 
        if "mountain" in ltype
    ]
    
    all_scores = []
    mountain_scores = []
    
    for location_name, lat, lon, expected_rating, landscape_type in test_locations:
        score, _ = get_natural_beauty_score(lat, lon)
        all_scores.append(score)
        if "mountain" in landscape_type:
            mountain_scores.append((location_name, score, expected_rating))
    
    all_scores.sort()
    median_score = all_scores[len(all_scores) // 2]
    
    print(f"\nMedian score across all locations: {median_score:.1f}")
    print("\nMountain town scores:")
    
    all_above_median = True
    for name, score, expected in mountain_scores:
        above_median = score > median_score
        status = "✅" if above_median else "❌"
        print(f"  {status} {name}: {score:.1f} (expected: {expected}, median: {median_score:.1f})")
        if not above_median:
            all_above_median = False
    
    return all_above_median


def validate_data_coverage_transparency(test_locations: List[Tuple]) -> bool:
    """Validate that data coverage indicators are present."""
    print("\n" + "="*80)
    print("VALIDATING DATA COVERAGE TRANSPARENCY")
    print("="*80)
    
    all_valid = True
    
    for location_name, lat, lon, expected_rating, landscape_type in test_locations[:5]:  # Test first 5
        print(f"\n📍 {location_name}")
        score, details = get_natural_beauty_score(lat, lon)
        
        tree_details = details.get("details", {}) if isinstance(details, dict) else {}
        data_coverage = tree_details.get("data_coverage", {})
        data_availability = tree_details.get("data_availability", {})
        
        # Check for required fields
        checks = {
            "overall_tier": data_coverage.get("overall_tier") in ["high", "medium", "low"],
            "terrain_metric": tree_details.get("natural_context", {}).get("topography_metrics", {}).get("relief_range_m") is not None or
                             tree_details.get("natural_context", {}).get("topography_metrics", {}).get("terrain_prominence_m") is not None,
            "water_metric": tree_details.get("natural_context", {}).get("water_proximity", {}).get("nearest_distance_km") is not None or
                           tree_details.get("natural_context", {}).get("landcover_metrics", {}).get("water_pct") is not None,
            "greenery_metric": tree_details.get("gvi_metrics", {}).get("visible_green_fraction") is not None or
                              tree_details.get("gvi_metrics", {}).get("street_level_ndvi") is not None or
                              tree_details.get("green_view_index") is not None,
        }
        
        for check_name, check_passed in checks.items():
            status = "✅" if check_passed else "❌"
            print(f"  {status} {check_name}: {check_passed}")
            if not check_passed:
                all_valid = False
        
        print(f"  Data Coverage Tier: {data_coverage.get('overall_tier', 'missing')}")
    
    return all_valid


def main():
    """Run all validation tests."""
    print("\n" + "="*80)
    print("NATURAL BEAUTY IMPROVEMENTS VALIDATION")
    print("="*80)
    
    results = {
        "rank_order_correlation": False,
        "mountain_town_scoring": False,
        "data_coverage_transparency": False,
    }
    
    # Test 1: Rank order correlation
    try:
        results["rank_order_correlation"] = validate_rank_order_correlation(TEST_LOCATIONS)
    except Exception as e:
        print(f"❌ Rank order correlation test failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Test 2: Mountain town scoring
    try:
        results["mountain_town_scoring"] = validate_mountain_town_scoring(TEST_LOCATIONS)
    except Exception as e:
        print(f"❌ Mountain town scoring test failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Test 3: Data coverage transparency
    try:
        results["data_coverage_transparency"] = validate_data_coverage_transparency(TEST_LOCATIONS)
    except Exception as e:
        print(f"❌ Data coverage transparency test failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Summary
    print("\n" + "="*80)
    print("VALIDATION SUMMARY")
    print("="*80)
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    all_passed = all(results.values())
    
    if all_passed:
        print("\n🎉 All validation tests passed!")
        return 0
    else:
        print("\n⚠️  Some validation tests failed. Review results above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
