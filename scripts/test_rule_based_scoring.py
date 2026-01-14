#!/usr/bin/env python3
"""
Test Rule-Based Scoring (Wave 1 Active)

Quick test to compare rule-based scoring (with Wave 1) vs previous Ridge regression.
Uses cached data when available to avoid redundant API calls.

Usage:
    python scripts/test_rule_based_scoring.py
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pillars.built_beauty import calculate_built_beauty
from data_sources.data_quality import classify_morphology
from data_sources import census_api

# Test locations from previous test
TEST_LOCATIONS = [
    {"name": "Levittown, Pennsylvania", "lat": 40.1551, "lon": -74.8288, "expected_area_type": "exurban"},
    {"name": "Beacon Hill, Boston MA", "lat": 42.3588, "lon": -71.0707, "expected_area_type": "urban_core"},
    {"name": "Georgetown, Washington DC", "lat": 38.9096, "lon": -77.0634, "expected_area_type": "urban_core"},
    {"name": "Park Slope, Brooklyn NY", "lat": 40.6715, "lon": -73.9772, "expected_area_type": "urban_residential"},
    {"name": "Celebration, Florida", "lat": 28.3186, "lon": -81.5401, "expected_area_type": "suburban"},
    {"name": "Carmel-by-the-Sea, California", "lat": 36.5552, "lon": -121.9233, "expected_area_type": "exurban"},
]

def format_score(score):
    """Format score for display."""
    if score is None:
        return "N/A"
    return f"{score:.1f}"

def test_rule_based_scoring():
    """Test rule-based scoring with Wave 1 changes."""
    print("="*80)
    print("TESTING RULE-BASED SCORING (Wave 1 Active)")
    print("="*80)
    print(f"\nTesting {len(TEST_LOCATIONS)} locations with rule-based scoring...")
    print("(Uses cached data when available to speed up testing)\n")
    
    results = []
    
    for i, location in enumerate(TEST_LOCATIONS, 1):
        name = location['name']
        lat = location['lat']
        lon = location['lon']
        
        print(f"[{i}/{len(TEST_LOCATIONS)}] {name}...", end=" ", flush=True)
        
        try:
            # Get area type
            density = census_api.get_population_density(lat, lon) or 0.0
            area_type = classify_morphology(density, None, None, metro_distance_km=None)
            
            # Calculate built beauty (now uses rule-based scoring)
            result_dict = calculate_built_beauty(
                lat=lat,
                lon=lon,
                area_type=area_type,
                density=density
            )
            
            # Extract scores
            total_score = result_dict.get('score')
            details = result_dict.get('details', {})
            architectural_analysis = details.get('architectural_analysis', {})
            metrics = architectural_analysis.get('metrics', {})
            
            # Extract rule-based scores (now in architectural_analysis top level, not metrics)
            design_score = architectural_analysis.get('design_score')
            form_score = architectural_analysis.get('form_score')
            scoring_method = architectural_analysis.get('scoring_method', 'unknown')
            
            # Extract coherence and streetwall for analysis
            coherence_signal = metrics.get('age_coherence_signal') or metrics.get('coherence_signal')
            streetwall_value = metrics.get('streetwall_continuity')
            
            results.append({
                'name': name,
                'area_type': area_type,
                'total_score': total_score,
                'design_score': design_score,
                'form_score': form_score,
                'scoring_method': scoring_method,
                'coherence_signal': coherence_signal,
                'streetwall_value': streetwall_value,
                'expected_area_type': location.get('expected_area_type')
            })
            
            print(f"✓ Score: {format_score(total_score)} "
                  f"(Design: {format_score(design_score)}, Form: {format_score(form_score)})")
            
        except Exception as e:
            print(f"✗ Error: {e}")
            results.append({
                'name': name,
                'area_type': 'unknown',
                'total_score': None,
                'error': str(e)
            })
    
    # Print results table
    print("\n" + "="*80)
    print("RESULTS: RULE-BASED SCORING (Wave 1 Active)")
    print("="*80)
    print(f"{'Location':<35} {'Area Type':<20} {'Total':<8} {'Design':<8} {'Form':<8} {'Coherence':<10} {'Streetwall':<10}")
    print("-"*80)
    
    for result in results:
        if result.get('error'):
            print(f"{result['name']:<35} ERROR: {result['error']}")
            continue
            
        coherence_str = format_score(result.get('coherence_signal'))
        streetwall_str = format_score(result.get('streetwall_value'))
        
        print(f"{result['name']:<35} "
              f"{result['area_type']:<20} "
              f"{format_score(result['total_score']):<8} "
              f"{format_score(result.get('design_score')):<8} "
              f"{format_score(result.get('form_score')):<8} "
              f"{coherence_str:<10} "
              f"{streetwall_str:<10}")
    
    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    
    valid_results = [r for r in results if r.get('total_score') is not None]
    if valid_results:
        scores = [r['total_score'] for r in valid_results]
        design_scores = [r.get('design_score') for r in valid_results if r.get('design_score') is not None]
        form_scores = [r.get('form_score') for r in valid_results if r.get('form_score') is not None]
        
        print(f"Total Score Range: {min(scores):.1f} - {max(scores):.1f} (avg: {sum(scores)/len(scores):.1f})")
        if design_scores:
            print(f"Design Score Range: {min(design_scores):.1f} - {max(design_scores):.1f} (avg: {sum(design_scores)/len(design_scores):.1f})")
        if form_scores:
            print(f"Form Score Range: {min(form_scores):.1f} - {max(form_scores):.1f} (avg: {sum(form_scores)/len(form_scores):.1f})")
        
        # Compare to previous Ridge scores (from test output)
        print("\nComparison to Previous Ridge Regression Scores:")
        print("  Ridge: Scores clustered around 76-82 (narrow range)")
        print(f"  Rule-Based: Scores range from {min(scores):.1f} to {max(scores):.1f}")
        if max(scores) - min(scores) > 6:
            print("  ✓ Better differentiation with rule-based scoring!")
        else:
            print("  ⚠ Still clustering - may need further tuning")
        
        # Check scoring method
        methods = set(r.get('scoring_method') for r in valid_results if r.get('scoring_method'))
        print(f"\nScoring Method: {', '.join(methods) if methods else 'unknown'}")
        if 'rule_based' in methods:
            print("  ✓ Rule-based scoring is active!")
    
    print("\n" + "="*80)
    return results

if __name__ == "__main__":
    test_rule_based_scoring()
