#!/usr/bin/env python3
"""
Quick test script for Built Beauty Ridge regression weights.
Tests a few locations from the calibration panel.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pillars.built_beauty import calculate_built_beauty
from data_sources.geocoding import geocode

# Test locations from calibration panel (quick test - just 2 locations)
TEST_LOCATIONS = [
    {"name": "Beaufort SC", "location": "Beaufort, SC", "expected": 95.0},
    {"name": "French Quarter New Orleans LA", "location": "French Quarter, New Orleans, LA", "expected": 95.0},
]

def test_location(name: str, location: str, expected: float):
    """Test a single location."""
    print(f"\n{'='*60}")
    print(f"Testing: {name}")
    print(f"Location: {location}")
    print(f"Expected Score: {expected}")
    print(f"{'='*60}")
    
    try:
        # Geocode location
        geocode_result = geocode(location)
        if not geocode_result:
            print(f"❌ Failed to geocode: {location}")
            return
        
        # geocode returns (lat, lon, zip_code, state, city)
        lat, lon, zip_code, state, city = geocode_result
        
        print(f"Coordinates: {lat}, {lon}")
        print(f"City: {city}")
        
        # Calculate built beauty
        result = calculate_built_beauty(
            lat=lat,
            lon=lon,
            city=city,
            location_name=location
        )
        
        score = result['score']
        details = result['details']
        arch_details = result.get('architectural_details', {})
        
        # Extract Ridge regression info
        ridge_score = arch_details.get('ridge_score_0_100')
        feature_contributions = arch_details.get('feature_contributions', {})
        scoring_method = arch_details.get('scoring_method', 'unknown')
        
        print(f"\n📊 Results:")
        print(f"  Built Beauty Score: {score:.1f}/100")
        print(f"  Expected Score: {expected:.1f}/100")
        print(f"  Difference: {score - expected:+.1f}")
        print(f"  Scoring Method: {scoring_method}")
        
        if ridge_score:
            print(f"  Ridge Score (0-100): {ridge_score:.1f}")
            print(f"  Ridge Score (0-50): {ridge_score / 2.0:.1f}")
        
        # Show top feature contributions
        if feature_contributions:
            print(f"\n🔍 Top Feature Contributions:")
            sorted_features = sorted(
                feature_contributions.items(),
                key=lambda x: abs(x[1]),
                reverse=True
            )[:5]
            for feature, contribution in sorted_features:
                print(f"  {feature}: {contribution:+.2f}")
        
        # Show key metrics
        metrics = arch_details.get('metrics', {})
        if metrics:
            print(f"\n📐 Key Metrics:")
            print(f"  Height Diversity: {metrics.get('height_diversity', 0):.1f}")
            print(f"  Type Diversity: {metrics.get('type_diversity', 0):.1f}")
            print(f"  Streetwall Continuity: {metrics.get('streetwall_continuity', 0):.1f}")
            print(f"  Setback Consistency: {metrics.get('setback_consistency', 0):.1f}")
            print(f"  Block Grain: {metrics.get('block_grain', 0):.1f}")
        
        # Material profile
        material_profile = arch_details.get('material_profile', {})
        if material_profile:
            materials = material_profile.get('materials', {})
            if materials:
                total = sum(materials.values())
                brick = materials.get('brick', 0) + materials.get('stone', 0)
                brick_pct = (brick / total * 100) if total > 0 else 0
                print(f"  Material Share (Brick/Stone): {brick_pct:.1f}%")
        
        # Area type
        classification = arch_details.get('classification', {})
        area_type = classification.get('effective_area_type', 'unknown')
        print(f"  Area Type: {area_type}")
        
        # Success indicator
        error = abs(score - expected)
        if error < 5:
            print(f"\n✅ PASS (error: {error:.1f})")
        elif error < 10:
            print(f"\n⚠️  WARN (error: {error:.1f})")
        else:
            print(f"\n❌ FAIL (error: {error:.1f})")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

def main():
    """Run tests for all locations."""
    print("🧪 Built Beauty Ridge Regression Test")
    print("=" * 60)
    
    for test in TEST_LOCATIONS:
        test_location(
            name=test['name'],
            location=test['location'],
            expected=test['expected']
        )
    
    print(f"\n{'='*60}")
    print("✅ Testing complete!")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
