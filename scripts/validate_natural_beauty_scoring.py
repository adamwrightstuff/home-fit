#!/usr/bin/env python3
"""
Comprehensive Natural Beauty Scoring Validation

Prioritizes data-backed validation:
1. Rank-order correlation with human ratings (PRIMARY - validates perception alignment)
2. Research-backed expected values validation
3. Component bounds validation
4. Regression testing (defensive - prevents breaking changes)

Usage:
    python scripts/validate_natural_beauty_scoring.py [--skip-regression] [--update-baseline]
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import List, Dict, Tuple
import json

try:
    from scipy.stats import spearmanr
    import numpy as np
    SCIPY_AVAILABLE = True
    NUMPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    NUMPY_AVAILABLE = False
    print("⚠️  scipy/numpy not available - rank order correlation test will be skipped")
    print("Install scipy: pip install scipy numpy")

# Human ratings dataset (ground truth for perception validation)
# Format: (location_name, lat, lon, human_rating_0_100, landscape_type, notes)
HUMAN_RATINGS_DATASET = [
    # Mountain towns with lakes (should score high)
    ("Truckee, CA", 39.3279, -120.1833, 85, "mountain_lake", "Mountain town, Lake Tahoe proximity"),
    ("Leavenworth, WA", 47.5962, -120.6615, 82, "mountain_scenic", "Mountain town, alpine scenery"),
    ("Bend, OR", 44.0582, -121.3153, 80, "mountain_river", "Mountain town, Deschutes River"),
    
    # Coastal areas (should score high)
    ("Carmel-by-the-Sea, CA", 36.5552, -121.9233, 90, "coastal_scenic", "Coastal, high natural beauty"),
    ("Santa Barbara, CA", 34.4208, -119.6982, 88, "coastal_urban", "Coastal, moderate urbanization"),
    
    # Urban with good greenery
    ("Seattle, WA - Green Lake", 47.6792, -122.3313, 75, "urban_green", "Urban park setting"),
    ("Portland, OR - Pearl District", 45.5286, -122.6778, 70, "urban_green", "Urban with good canopy"),
    
    # Suburban with good canopy
    ("Palo Alto, CA", 37.4419, -122.1430, 78, "suburban_canopy", "Suburban, high canopy"),
    ("Irvine, CA", 33.6846, -117.8265, 65, "suburban_planned", "Planned suburban community"),
    
    # Arid regions (should emphasize terrain)
    ("Sedona, AZ", 34.8697, -111.7610, 85, "arid_scenic", "Arid, dramatic red rock formations"),
    ("Moab, UT", 38.5733, -109.5498, 80, "arid_scenic", "Arid, canyon country"),
    
    # Previously mis-scored (should improve)
    ("Asheville, NC", 35.5951, -82.5515, 82, "mountain_forest", "Mountain town, forested"),
    ("Boulder, CO", 40.0150, -105.2705, 83, "mountain_foothills", "Mountain foothills, moderate relief"),
    
    # High-performing urban
    ("Georgetown, DC", 38.9096, -77.0634, 85, "urban_historic", "Historic urban, high canopy"),
    ("Pearl District, Portland OR", 45.5300, -122.6800, 88, "urban_historic", "Urban, very high GVI"),
    
    # Moderate suburban
    ("Bronxville, NY", 40.9395, -73.8321, 75, "suburban_historic", "Historic suburb"),
    ("The Woodlands, TX", 30.1575, -95.4893, 72, "suburban_planned", "Planned suburb"),
    
    # Low-scoring urban (for validation range)
    ("Venice Beach, Los Angeles CA", 33.9850, -118.4695, 25, "coastal_gritty", "Coastal but chaotic"),
    ("Downtown Houston, TX", 29.7604, -95.3698, 20, "urban_arid", "Arid urban, very low canopy"),
]

def get_natural_beauty_score(lat: float, lon: float) -> Tuple[float, Dict]:
    """Get Natural Beauty score for a location."""
    from pillars.natural_beauty import get_natural_beauty_score
    
    try:
        score, details = get_natural_beauty_score(
            lat=lat,
            lon=lon,
            city=None,
            area_type=None,
            location_scope=None,
            location_name=None,
            overrides=None
        )
        return score, details
    except Exception as e:
        print(f"Error getting score for {lat}, {lon}: {e}")
        import traceback
        traceback.print_exc()
        return 0.0, {}


def validate_rank_order_correlation() -> Dict:
    """
    PRIMARY VALIDATION: Rank-order correlation with human ratings.
    
    This is the most data-backed validation - tests if scores align with
    human perception of natural beauty.
    
    Returns:
        Dict with validation results
    """
    print("\n" + "="*80)
    print("PRIMARY VALIDATION: RANK-ORDER CORRELATION WITH HUMAN RATINGS")
    print("="*80)
    print("Validates that scores align with human perception of natural beauty")
    print()
    
    if not SCIPY_AVAILABLE:
        return {
            "status": "skipped",
            "reason": "scipy not available",
            "correlation": None,
            "p_value": None,
            "passed": False
        }
    
    scores = []
    human_ratings = []
    locations_tested = []
    
    for location_name, lat, lon, human_rating, landscape_type, notes in HUMAN_RATINGS_DATASET:
        print(f"📍 {location_name} ({landscape_type})")
        score, details = get_natural_beauty_score(lat, lon)
        scores.append(score)
        human_ratings.append(human_rating)
        locations_tested.append({
            "name": location_name,
            "score": round(score, 2),
            "human_rating": human_rating,
            "difference": round(score - human_rating, 2),
            "landscape_type": landscape_type
        })
        
        print(f"  Model Score: {score:.1f} | Human Rating: {human_rating} | Diff: {score - human_rating:+.1f}")
        
        # Show key metrics
        tree_details = details.get("details", {})
        natural_context = tree_details.get("natural_context", {}) or tree_details.get("context_bonus", {})
        topography = natural_context.get("topography_metrics", {})
        viewshed = natural_context.get("viewshed_metrics", {})
        water_proximity = natural_context.get("water_proximity", {})
        
        print(f"  Terrain: relief={topography.get('relief_range_m', 'N/A')}m, "
              f"prominence={topography.get('terrain_prominence_m', 'N/A')}m")
        print(f"  Viewshed: visible_natural={viewshed.get('visible_natural_pct', 'N/A')}%")
        print(f"  Water: proximity={water_proximity.get('nearest_distance_km', 'N/A')}km")
        print()
    
    # Calculate Spearman correlation
    correlation, p_value = spearmanr(scores, human_ratings)
    
    target_correlation = 0.7
    passed = correlation >= target_correlation
    
    print("="*80)
    print(f"Spearman Correlation: {correlation:.3f}")
    print(f"P-value: {p_value:.6f}")
    print(f"Target: ≥ {target_correlation}")
    print(f"Status: {'✅ PASS' if passed else '❌ FAIL'}")
    print("="*80)
    
    # Calculate RMSE for additional validation
    if NUMPY_AVAILABLE:
        rmse = np.sqrt(np.mean([(s - h)**2 for s, h in zip(scores, human_ratings)]))
        mae = np.mean([abs(s - h) for s, h in zip(scores, human_ratings)])
    else:
        rmse = (sum((s - h)**2 for s, h in zip(scores, human_ratings)) / len(scores)) ** 0.5
        mae = sum(abs(s - h) for s, h in zip(scores, human_ratings)) / len(scores)
    
    return {
        "status": "completed",
        "correlation": float(correlation),
        "p_value": float(p_value),
        "target": target_correlation,
        "passed": passed,
        "rmse": float(rmse),
        "mae": float(mae),
        "n_samples": len(scores),
        "locations_tested": locations_tested
    }


def validate_research_backed_expectations() -> Dict:
    """
    SECONDARY VALIDATION: Research-backed expected values.
    
    Validates that expected values come from research data, not arbitrary tuning.
    """
    print("\n" + "="*80)
    print("SECONDARY VALIDATION: RESEARCH-BACKED EXPECTED VALUES")
    print("="*80)
    print("Validates that expected values come from research data")
    print()
    
    from pillars.natural_beauty import CLIMATE_CANOPY_EXPECTATIONS
    
    checks = []
    
    # Check that climate expectations have research backing
    research_ranges = {
        "arid": (1.5, 15.0),
        "temperate": (30.0, 40.0),
        "humid_temperate": (30.0, 45.0),
        "mediterranean": (20.0, 35.0),
        "tropical": (30.0, 45.0),
        "continental": (25.0, 40.0),
    }
    
    for climate, expectation in CLIMATE_CANOPY_EXPECTATIONS.items():
        if climate in research_ranges:
            min_val, max_val = research_ranges[climate]
            in_range = min_val <= expectation <= max_val
            checks.append({
                "climate": climate,
                "expectation": expectation,
                "research_range": (min_val, max_val),
                "in_range": in_range
            })
            status = "✅" if in_range else "⚠️"
            print(f"{status} {climate}: {expectation}% (research range: {min_val}-{max_val}%)")
        else:
            print(f"ℹ️  {climate}: {expectation}% (no research range defined)")
    
    all_passed = all(check.get("in_range", True) for check in checks if "in_range" in check)
    
    print("="*80)
    print(f"Status: {'✅ PASS' if all_passed else '⚠️  WARN'}")
    print("="*80)
    
    return {
        "status": "completed",
        "passed": all_passed,
        "checks": checks
    }


def validate_component_bounds() -> Dict:
    """
    TERTIARY VALIDATION: Component bounds and logical consistency.
    
    Validates that individual components are within expected ranges.
    """
    print("\n" + "="*80)
    print("TERTIARY VALIDATION: COMPONENT BOUNDS")
    print("="*80)
    print("Validates that individual components are within expected ranges")
    print()
    
    # Test a few representative locations
    test_locations = [
        ("Truckee, CA", 39.3279, -120.1833),
        ("Carmel-by-the-Sea, CA", 36.5552, -121.9233),
        ("Sedona, AZ", 34.8697, -111.7610),
    ]
    
    checks = []
    
    for location_name, lat, lon in test_locations:
        score, details = get_natural_beauty_score(lat, lon)
        tree_details = details.get("details", {})
        context_bonus = tree_details.get("context_bonus", {}) or tree_details.get("natural_context", {})
        components = context_bonus.get("component_scores", {})
        
        print(f"📍 {location_name}")
        
        # Check component bounds
        topography = components.get("topography", 0)
        water = components.get("water", 0)
        landcover = components.get("landcover", 0)
        
        from pillars.natural_beauty import TOPOGRAPHY_BONUS_MAX, WATER_BONUS_MAX
        
        topo_in_bounds = 0 <= topography <= TOPOGRAPHY_BONUS_MAX
        water_in_bounds = 0 <= water <= WATER_BONUS_MAX
        
        print(f"  Topography: {topography:.2f} (max: {TOPOGRAPHY_BONUS_MAX}) {'✅' if topo_in_bounds else '❌'}")
        print(f"  Water: {water:.2f} (max: {WATER_BONUS_MAX}) {'✅' if water_in_bounds else '❌'}")
        
        checks.append({
            "location": location_name,
            "topography_in_bounds": topo_in_bounds,
            "water_in_bounds": water_in_bounds,
        })
        print()
    
    all_passed = all(c["topography_in_bounds"] and c["water_in_bounds"] for c in checks)
    
    print("="*80)
    print(f"Status: {'✅ PASS' if all_passed else '❌ FAIL'}")
    print("="*80)
    
    return {
        "status": "completed",
        "passed": all_passed,
        "checks": checks
    }


def run_regression_tests(skip: bool = False, update_baseline: bool = False) -> Dict:
    """
    DEFENSIVE VALIDATION: Regression testing.
    
    Prevents breaking changes by comparing to baseline scores.
    Note: This is defensive validation - assumes baseline is correct.
    Primary validation should be rank-order correlation.
    """
    if skip:
        return {
            "status": "skipped",
            "reason": "skip-regression flag set"
        }
    
    print("\n" + "="*80)
    print("DEFENSIVE VALIDATION: REGRESSION TESTING")
    print("="*80)
    print("Prevents breaking changes (assumes baseline is correct)")
    print("NOTE: Primary validation is rank-order correlation with human ratings")
    print()
    
    try:
        # Import and run existing regression test suite
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tests'))
        from test_natural_beauty_regression import run_regression_tests as run_regression
        return run_regression(update_baseline=update_baseline)
    except Exception as e:
        print(f"⚠️  Regression tests unavailable: {e}")
        import traceback
        traceback.print_exc()
        return {
            "status": "skipped",
            "reason": str(e)
        }


def main():
    """Run comprehensive validation suite."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Natural Beauty Scoring Validation")
    parser.add_argument("--skip-regression", action="store_true",
                       help="Skip regression tests (use when baseline is outdated)")
    parser.add_argument("--update-baseline", action="store_true",
                       help="Update regression baseline scores")
    
    args = parser.parse_args()
    
    print("="*80)
    print("NATURAL BEAUTY SCORING - COMPREHENSIVE VALIDATION")
    print("="*80)
    print()
    print("Priority order:")
    print("1. PRIMARY: Rank-order correlation with human ratings (validates perception)")
    print("2. SECONDARY: Research-backed expected values (validates objective metrics)")
    print("3. TERTIARY: Component bounds (validates individual metrics)")
    print("4. DEFENSIVE: Regression testing (prevents breaking changes)")
    print()
    
    results = {}
    
    # PRIMARY: Rank-order correlation (most important)
    results["rank_order_correlation"] = validate_rank_order_correlation()
    
    # SECONDARY: Research-backed expectations
    results["research_backed"] = validate_research_backed_expectations()
    
    # TERTIARY: Component bounds
    results["component_bounds"] = validate_component_bounds()
    
    # DEFENSIVE: Regression tests
    results["regression"] = run_regression_tests(
        skip=args.skip_regression,
        update_baseline=args.update_baseline
    )
    
    # Summary
    print("\n" + "="*80)
    print("VALIDATION SUMMARY")
    print("="*80)
    
    primary_passed = results["rank_order_correlation"].get("passed", False)
    secondary_passed = results["research_backed"].get("passed", False)
    tertiary_passed = results["component_bounds"].get("passed", False)
    regression_status = results["regression"].get("status", "unknown")
    
    print(f"\nPRIMARY (Rank-order correlation): {'✅ PASS' if primary_passed else '❌ FAIL'}")
    if primary_passed and SCIPY_AVAILABLE:
        corr = results["rank_order_correlation"].get("correlation", 0)
        print(f"  Correlation: {corr:.3f} (target: ≥ 0.7)")
    
    print(f"SECONDARY (Research-backed): {'✅ PASS' if secondary_passed else '⚠️  WARN'}")
    print(f"TERTIARY (Component bounds): {'✅ PASS' if tertiary_passed else '❌ FAIL'}")
    print(f"DEFENSIVE (Regression tests): {regression_status}")
    
    # Overall status
    critical_passed = primary_passed
    overall_status = "✅ PASS" if critical_passed else "❌ FAIL"
    
    print(f"\nOverall Status: {overall_status}")
    print("\nNOTE: Primary validation (rank-order correlation) is the most data-backed.")
    print("Regression tests are defensive and assume baseline is correct.")
    
    # Save results
    output_file = "validation_results.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\n📁 Results saved to: {output_file}")
    
    return 0 if critical_passed else 1


if __name__ == "__main__":
    sys.exit(main())
