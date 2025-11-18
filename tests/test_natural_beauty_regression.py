#!/usr/bin/env python3
"""
Regression Test Suite for Natural Beauty Pillar

Tests natural beauty scoring across diverse locations to detect regressions
when calibration changes are made.

Usage:
    python tests/test_natural_beauty_regression.py [--update-baseline] [--location LOCATION]
"""

import json
import sys
import os
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from pillars import natural_beauty
except ImportError:
    print("⚠️  Cannot import natural_beauty module. Run from project root.")
    sys.exit(1)


@dataclass
class RegressionBaseline:
    """Baseline score and tolerance for a test location."""
    name: str
    lat: float
    lon: float
    city: Optional[str] = None
    area_type: Optional[str] = None
    baseline_score: float = 0.0
    tolerance: float = 5.0  # Acceptable change range
    expected_components: Optional[Dict[str, float]] = None  # Component score expectations
    notes: str = ""


# Regression test baseline - scores captured after latest stable deployment
# Update these when making intentional calibration changes
REGRESSION_BASELINE: List[RegressionBaseline] = [
    # Arid/Desert regions
    RegressionBaseline(
        name="Old Town Scottsdale AZ",
        lat=33.4995267,
        lon=-111.9116911,
        city="Scottsdale",
        area_type="urban_residential",
        baseline_score=13.3,
        tolerance=3.0,  # Higher tolerance for low scores
        notes="Arid, low water (0.4%), low canopy (1.63%)"
    ),
    RegressionBaseline(
        name="Sedona AZ",
        lat=34.8697,
        lon=-111.7610,
        city="Sedona",
        area_type="rural",
        baseline_score=61.16,
        tolerance=5.0,
        notes="Arid, scenic, low canopy (18.48%), striking topography (14.54° slope)"
    ),
    
    # Tropical/Coastal regions
    RegressionBaseline(
        name="Coconut Grove Miami FL",
        lat=25.7126013,
        lon=-80.2569947,
        city="Miami",
        area_type="suburban",
        baseline_score=51.92,
        tolerance=8.0,  # Higher tolerance - water scoring recently changed
        notes="Tropical, high water (25.63%), moderate canopy (17.37%)"
    ),
    RegressionBaseline(
        name="Manhattan Beach CA",
        lat=33.8847,
        lon=-118.4109,
        city="Manhattan Beach",
        area_type="suburban",
        baseline_score=30.5,
        tolerance=6.0,
        notes="Coastal, moderate water (11.63%), low canopy (7.87%)"
    ),
    RegressionBaseline(
        name="Carmel-by-the-Sea CA",
        lat=36.5552,
        lon=-121.9233,
        city="Carmel-by-the-Sea",
        area_type="suburban",
        baseline_score=91.09,
        tolerance=5.0,
        notes="Coastal, high water (25.1%), high canopy (25.5%), moderate topography"
    ),
    
    # Urban historic (low satellite canopy, street trees)
    RegressionBaseline(
        name="Garden District New Orleans LA",
        lat=29.9333,
        lon=-90.0833,
        city="New Orleans",
        area_type="suburban",
        baseline_score=20.07,
        tolerance=5.0,
        notes="Low satellite canopy (2%), moderate water (13.3%), mature street trees"
    ),
    RegressionBaseline(
        name="Beacon Hill Boston MA",
        lat=42.3573,
        lon=-71.0708,
        city="Boston",
        area_type="historic_urban",
        baseline_score=35.71,
        tolerance=5.0,
        notes="Urban historic, street trees, low satellite canopy (7.65%)"
    ),
    
    # High performers (should maintain)
    RegressionBaseline(
        name="Pearl District Portland OR",
        lat=45.5300,
        lon=-122.6800,
        city="Portland",
        area_type="historic_urban",
        baseline_score=100.0,
        tolerance=5.0,
        notes="Temperate, high canopy (5.06%), very high GVI (63.04%), should maintain high score"
    ),
    RegressionBaseline(
        name="Georgetown DC",
        lat=38.9096,
        lon=-77.0634,
        city="Washington",
        area_type="historic_urban",
        baseline_score=100.0,
        tolerance=5.0,
        notes="Urban historic, high canopy (16.64%), very high GVI (69.99%), should maintain high score"
    ),
    
    # Suburban examples
    RegressionBaseline(
        name="Bronxville NY",
        lat=40.9395,
        lon=-73.8321,
        city="Bronxville",
        baseline_score=75.0,  # Not in provided data - keep approximate
        tolerance=5.0,
        notes="Suburban, high canopy, historic"
    ),
    RegressionBaseline(
        name="The Woodlands TX",
        lat=30.1575,
        lon=-95.4893,
        city="The Woodlands",
        baseline_score=60.0,  # Not in provided data - keep approximate
        tolerance=5.0,
        notes="Suburban, planned community, moderate canopy"
    ),
    
    # Rural/Exurban examples
    RegressionBaseline(
        name="Stowe VT",
        lat=44.4654,
        lon=-72.6874,
        city="Stowe",
        baseline_score=70.0,  # Not in provided data - keep approximate
        tolerance=8.0,
        notes="Rural, scenic, high natural beauty"
    ),
    
    # Edge cases
    RegressionBaseline(
        name="Venice Beach Los Angeles CA",
        lat=33.9850,
        lon=-118.4695,
        city="Los Angeles",
        baseline_score=20.0,  # Not in provided data - keep approximate
        tolerance=5.0,
        notes="Gritty, chaotic, coastal but low natural beauty"
    ),
]


def get_natural_beauty_score(location: RegressionBaseline) -> Tuple[float, Dict]:
    """Get natural beauty score for a location."""
    try:
        result = natural_beauty.calculate_natural_beauty(
            lat=location.lat,
            lon=location.lon,
            city=location.city,
            area_type=location.area_type
        )
        score = result.get("score", 0.0)
        details = result.get("details", {})
        # Include validation results in details
        details["validation"] = result.get("validation", {})
        return score, details
    except Exception as e:
        print(f"❌ Error scoring {location.name}: {e}")
        import traceback
        traceback.print_exc()
        return 0.0, {}


def test_regression(location: RegressionBaseline, update_baseline: bool = False) -> Dict:
    """Test if score change is within acceptable tolerance."""
    current_score, details = get_natural_beauty_score(location)
    
    if update_baseline:
        return {
            "status": "baseline_updated",
            "location": location.name,
            "new_score": current_score,
            "old_baseline": location.baseline_score
        }
    
    change = current_score - location.baseline_score
    abs_change = abs(change)
    
    # Extract component scores for analysis
    tree_analysis = details.get("tree_analysis", {})
    context_bonus = details.get("context_bonus", {})
    component_scores = context_bonus.get("component_scores", {})
    
    result = {
        "location": location.name,
        "baseline_score": location.baseline_score,
        "current_score": round(current_score, 2),
        "change": round(change, 2),
        "abs_change": round(abs_change, 2),
        "tolerance": location.tolerance,
        "status": "pass" if abs_change <= location.tolerance else "regression",
        "components": {
            "water": component_scores.get("water", 0.0),
            "topography": component_scores.get("topography", 0.0),
            "landcover": component_scores.get("landcover", 0.0),
        },
        "canopy_pct": tree_analysis.get("gee_canopy_pct", 0.0),
        "water_pct": context_bonus.get("landcover_metrics", {}).get("water_pct", 0.0),
    }
    
    if result["status"] == "regression":
        result["warning"] = f"Score changed by {abs_change:.1f} points (tolerance: {location.tolerance})"
    
    return result


def run_regression_tests(update_baseline: bool = False, 
                         location_filter: Optional[str] = None) -> Dict:
    """Run regression tests for all or filtered locations."""
    results = []
    passed = 0
    regressions = 0
    errors = 0
    
    locations_to_test = REGRESSION_BASELINE
    if location_filter:
        locations_to_test = [loc for loc in REGRESSION_BASELINE 
                            if location_filter.lower() in loc.name.lower()]
    
    print("=" * 80)
    print("Natural Beauty Regression Test Suite")
    print("=" * 80)
    if update_baseline:
        print("⚠️  BASELINE UPDATE MODE - Scores will be updated, not validated")
    print()
    
    for location in locations_to_test:
        print(f"Testing: {location.name}")
        result = test_regression(location, update_baseline=update_baseline)
        results.append(result)
        
        if update_baseline:
            print(f"  New baseline: {result['new_score']:.1f} (was {result['old_baseline']:.1f})")
            continue
        
        status_icon = "✅" if result["status"] == "pass" else "❌"
        print(f"  {status_icon} Score: {result['current_score']:.1f} "
              f"(baseline: {result['baseline_score']:.1f}, change: {result['change']:+.1f})")
        
        if result["status"] == "regression":
            print(f"  ⚠️  {result['warning']}")
            regressions += 1
        elif result["status"] == "pass":
            passed += 1
        else:
            errors += 1
        print()
    
    summary = {
        "total": len(results),
        "passed": passed,
        "regressions": regressions,
        "errors": errors,
        "results": results
    }
    
    print("=" * 80)
    print("Summary")
    print("=" * 80)
    print(f"Total: {summary['total']}")
    print(f"✅ Passed: {summary['passed']}")
    print(f"❌ Regressions: {summary['regressions']}")
    print(f"⚠️  Errors: {summary['errors']}")
    
    if regressions > 0:
        print("\n⚠️  REGRESSIONS DETECTED - Review changes before deploying")
        return summary
    
    print("\n✅ All tests passed - no regressions detected")
    return summary


def save_baseline(results: List[Dict], output_file: str = "tests/natural_beauty_baseline.json"):
    """Save updated baseline scores to file."""
    baseline_data = {
        "version": "1.0.0",
        "updated": "auto-generated",
        "locations": []
    }
    
    for result in results:
        if result["status"] == "baseline_updated":
            baseline_data["locations"].append({
                "name": result["location"],
                "baseline_score": result["new_score"]
            })
    
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, 'w') as f:
        json.dump(baseline_data, f, indent=2)
    
    print(f"\n💾 Baseline saved to {output_file}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Natural Beauty Regression Test Suite")
    parser.add_argument("--update-baseline", action="store_true",
                       help="Update baseline scores instead of testing")
    parser.add_argument("--location", type=str,
                       help="Test specific location (partial name match)")
    parser.add_argument("--save", action="store_true",
                       help="Save updated baseline to file")
    
    args = parser.parse_args()
    
    results = run_regression_tests(
        update_baseline=args.update_baseline,
        location_filter=args.location
    )
    
    if args.update_baseline and args.save:
        save_baseline(results["results"])

