#!/usr/bin/env python3
"""
Validation script for Natural Beauty strategic improvements.

Tests 8 locations before and after changes to validate:
- Water rarity bonus (3x when water < expected for climate)
- Water visibility heuristics (elevation + development proxy)
- Street tree bonus (capped at 5 points, only <10% canopy)
"""

import json
import sys
from typing import Dict, List, Tuple

# Test locations with expected improvements
TEST_LOCATIONS = [
    {
        "name": "Old Town Scottsdale AZ",
        "lat": 33.4995267,
        "lon": -111.9116911,
        "expected_improvement": "Water rarity bonus in arid context",
        "notes": "Arid, low water (0.4%), low canopy (2.1%)"
    },
    {
        "name": "Coconut Grove Miami FL",
        "lat": 25.7126013,
        "lon": -80.2569947,
        "expected_improvement": "High water (25.6%), tropical context",
        "notes": "Tropical, high water, moderate canopy (17.4%)"
    },
    {
        "name": "Garden District New Orleans LA",
        "lat": 29.9333,
        "lon": -90.0833,
        "expected_improvement": "Street tree bonus (low satellite canopy)",
        "notes": "Low satellite canopy (0.43%), mature street trees"
    },
    {
        "name": "Beacon Hill Boston MA",
        "lat": 42.3573,
        "lon": -71.0708,
        "expected_improvement": "Street tree bonus (urban historic)",
        "notes": "Urban historic, street trees, low satellite canopy"
    },
    {
        "name": "Manhattan Beach CA",
        "lat": 33.8847,
        "lon": -118.4109,
        "expected_improvement": "Water visibility (coastal, elevated)",
        "notes": "Coastal, moderate water, elevated visibility"
    },
    {
        "name": "Sedona AZ",
        "lat": 34.8697,
        "lon": -111.7610,
        "expected_improvement": "Water rarity bonus, scenic context",
        "notes": "Arid, scenic, low canopy"
    },
    {
        "name": "Pearl District Portland OR",
        "lat": 45.5300,
        "lon": -122.6800,
        "expected_improvement": "Maintain high score (no regression)",
        "notes": "Temperate, high canopy, should maintain 95-100"
    },
    {
        "name": "Georgetown DC",
        "lat": 38.9096,
        "lon": -77.0634,
        "expected_improvement": "Maintain high score (no regression)",
        "notes": "Urban historic, moderate canopy, should maintain high score"
    }
]


def extract_natural_beauty_score(response: Dict) -> Tuple[float, Dict]:
    """Extract natural beauty score and details from API response."""
    natural_beauty = response.get("livability_pillars", {}).get("natural_beauty", {})
    score = natural_beauty.get("score", 0.0)
    details = natural_beauty.get("details", {})
    return score, details


def extract_water_metrics(details: Dict) -> Dict:
    """Extract water-related metrics from natural beauty details."""
    tree_analysis = details.get("tree_analysis", {})
    natural_context = tree_analysis.get("natural_context", {})
    landcover_metrics = natural_context.get("landcover_metrics", {})
    context_bonus = details.get("context_bonus", {})
    
    return {
        "water_pct": landcover_metrics.get("water_pct", 0.0),
        "water_raw": natural_context.get("component_scores", {}).get("water_raw", 0.0),
        "water_score": natural_context.get("component_scores", {}).get("water", 0.0),
        "developed_pct": landcover_metrics.get("developed_pct", 0.0),
    }


def extract_street_tree_metrics(details: Dict) -> Dict:
    """Extract street tree bonus metrics."""
    tree_analysis = details.get("tree_analysis", {})
    bonus_breakdown = tree_analysis.get("bonus_breakdown", {})
    
    return {
        "street_tree_bonus": bonus_breakdown.get("street_tree_bonus", 0.0),
        "street_tree_count": tree_analysis.get("street_tree_feature_total", 0),
        "canopy_pct": tree_analysis.get("gee_canopy_pct", 0.0),
    }


def print_comparison(location: Dict, before_score: float, after_score: float,
                    before_details: Dict, after_details: Dict):
    """Print comparison of before/after scores and key metrics."""
    name = location["name"]
    change = after_score - before_score
    change_pct = (change / before_score * 100) if before_score > 0 else 0.0
    
    print(f"\n{'='*80}")
    print(f"Location: {name}")
    print(f"{'='*80}")
    print(f"Score: {before_score:.1f} → {after_score:.1f} ({change:+.1f}, {change_pct:+.1f}%)")
    print(f"Expected: {location['expected_improvement']}")
    print(f"Notes: {location['notes']}")
    
    # Water metrics
    before_water = extract_water_metrics(before_details)
    after_water = extract_water_metrics(after_details)
    print(f"\nWater Metrics:")
    print(f"  Water %: {before_water['water_pct']:.1f}%")
    print(f"  Water Raw: {before_water['water_raw']:.2f} → {after_water['water_raw']:.2f} ({after_water['water_raw'] - before_water['water_raw']:+.2f})")
    print(f"  Water Score: {before_water['water_score']:.2f} → {after_water['water_score']:.2f} ({after_water['water_score'] - before_water['water_score']:+.2f})")
    print(f"  Developed %: {before_water['developed_pct']:.1f}%")
    
    # Street tree metrics
    before_street = extract_street_tree_metrics(before_details)
    after_street = extract_street_tree_metrics(after_details)
    print(f"\nStreet Tree Metrics:")
    print(f"  Canopy %: {before_street['canopy_pct']:.2f}%")
    print(f"  Street Tree Count: {before_street['street_tree_count']} → {after_street['street_tree_count']}")
    print(f"  Street Tree Bonus: {before_street['street_tree_bonus']:.2f} → {after_street['street_tree_bonus']:.2f} ({after_street['street_tree_bonus'] - before_street['street_tree_bonus']:+.2f})")
    
    # Overall assessment
    if abs(change) > 5.0:
        status = "✓ SIGNIFICANT CHANGE" if change > 0 else "⚠ REGRESSION"
        print(f"\n{status}: Score changed by {abs(change):.1f} points")
    else:
        print(f"\n→ Minimal change: {change:+.1f} points")


def main():
    """Main validation function."""
    print("Natural Beauty Strategic Improvements - Validation")
    print("=" * 80)
    print("\nThis script validates the following improvements:")
    print("1. Climate-calibrated water expectations with rarity bonus (3x when water < expected)")
    print("2. Simple water visibility heuristics (elevation + development proxy)")
    print("3. Street tree bonus component (capped at 5 points, only <10% canopy)")
    print("\n" + "=" * 80)
    
    print("\n⚠️  NOTE: This script requires API responses.")
    print("To use this script:")
    print("1. Run API calls for all 8 locations BEFORE changes (save as JSON files)")
    print("2. Implement changes")
    print("3. Run API calls for all 8 locations AFTER changes (save as JSON files)")
    print("4. Update this script to load and compare the JSON files")
    print("\nExample usage:")
    print("  python test_natural_beauty_improvements.py before/ after/")
    
    if len(sys.argv) >= 3:
        before_dir = sys.argv[1]
        after_dir = sys.argv[2]
        
        print(f"\nLoading results from:")
        print(f"  Before: {before_dir}")
        print(f"  After: {after_dir}")
        
        # Load and compare results
        for location in TEST_LOCATIONS:
            name_safe = location["name"].replace(" ", "_").replace(",", "").lower()
            before_file = f"{before_dir}/{name_safe}.json"
            after_file = f"{after_dir}/{name_safe}.json"
            
            try:
                with open(before_file, 'r') as f:
                    before_response = json.load(f)
                with open(after_file, 'r') as f:
                    after_response = json.load(f)
                
                before_score, before_details = extract_natural_beauty_score(before_response)
                after_score, after_details = extract_natural_beauty_score(after_response)
                
                print_comparison(location, before_score, after_score, before_details, after_details)
                
            except FileNotFoundError as e:
                print(f"\n⚠️  Missing file: {e}")
                print(f"   Location: {location['name']}")
            except Exception as e:
                print(f"\n❌ Error processing {location['name']}: {e}")
        
        print("\n" + "=" * 80)
        print("Validation Complete")
        print("=" * 80)
    else:
        print("\n📋 Test Locations:")
        for i, loc in enumerate(TEST_LOCATIONS, 1):
            print(f"{i}. {loc['name']}")
            print(f"   Expected: {loc['expected_improvement']}")
            print(f"   Notes: {loc['notes']}\n")


if __name__ == "__main__":
    main()

