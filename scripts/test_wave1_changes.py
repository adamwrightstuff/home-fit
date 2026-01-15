#!/usr/bin/env python3
"""
Test Wave 1 Changes - Built Beauty Scoring

Tests the Wave 1 improvements:
1. Diversity-coherence interaction (suburban/exurban)
2. Parking-aware footprint CV
3. Area-type-specific streetwall behavior

Usage:
    python scripts/test_wave1_changes.py
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pillars.built_beauty import calculate_built_beauty
from data_sources.data_quality import classify_morphology
from data_sources import census_api

# Test cases specifically designed to validate Wave 1 changes
TEST_LOCATIONS = [
    # Wave 1.1: Diversity-coherence interaction
    # Suburban/exurban with potentially high diversity but low coherence
    {"name": "Levittown, Pennsylvania", "lat": 40.1551, "lon": -74.8288, "focus": "diversity_coherence"},
    {"name": "Celebration, Florida", "lat": 28.3186, "lon": -81.5401, "focus": "diversity_coherence"},
    {"name": "Woodbridge, Irvine CA", "lat": 33.6253, "lon": -117.8399, "focus": "diversity_coherence"},
    
    # Wave 1.2: Parking-aware footprint CV
    # Areas likely to have strip malls or big box stores
    {"name": "Generic Strip Mall Area, Irvine CA", "lat": 33.6979, "lon": -117.7893, "focus": "parking_cv"},
    {"name": "Shopping District, Bellevue WA", "lat": 47.6101, "lon": -122.2015, "focus": "parking_cv"},
    
    # Wave 1.3: Area-type-specific streetwall
    # Rural/exurban areas that might have high continuity (strip malls)
    {"name": "Carmel-by-the-Sea, California", "lat": 36.5552, "lon": -121.9233, "focus": "streetwall"},
    {"name": "Sedona, Arizona", "lat": 34.8697, "lon": -111.7610, "focus": "streetwall"},
    {"name": "Nantucket, Massachusetts", "lat": 41.2835, "lon": -70.0995, "focus": "streetwall"},
    
    # Control: High-quality urban areas (should be mostly unaffected)
    {"name": "Beacon Hill, Boston MA", "lat": 42.3588, "lon": -71.0707, "focus": "control"},
    {"name": "Georgetown, Washington DC", "lat": 38.9096, "lon": -77.0634, "focus": "control"},
    {"name": "Park Slope, Brooklyn NY", "lat": 40.6715, "lon": -73.9772, "focus": "control"},
]

def format_score(score):
    """Format score for display."""
    if score is None:
        return "N/A"
    return f"{score:.1f}"

def print_results(results):
    """Print test results in a readable format."""
    print("\n" + "="*80)
    print("WAVE 1 TEST RESULTS")
    print("="*80)
    
    # Group by focus area
    by_focus = {}
    for result in results:
        focus = result['focus']
        if focus not in by_focus:
            by_focus[focus] = []
        by_focus[focus].append(result)
    
    # Print results by focus area
    focus_labels = {
        "diversity_coherence": "1.1 Diversity-Coherence Interaction (Suburban/Exurban)",
        "parking_cv": "1.2 Parking-Aware Footprint CV",
        "streetwall": "1.3 Area-Type-Specific Streetwall",
        "control": "Control: Urban Areas (Should be mostly unaffected)"
    }
    
    for focus, label in focus_labels.items():
        if focus not in by_focus:
            continue
            
        print(f"\n{label}")
        print("-" * 80)
        print(f"{'Location':<35} {'Area Type':<20} {'Score':<8} {'Arch':<8} {'Form':<8} {'Details'}")
        print("-" * 80)
        
        for result in by_focus[focus]:
            details = []
            if result.get('coherence_signal'):
                details.append(f"coh={result['coherence_signal']:.2f}")
            if result.get('parking_detected'):
                details.append(f"parking={result['parking_detected']}")
            if result.get('streetwall_value'):
                details.append(f"strw={result['streetwall_value']:.0f}")
            
            details_str = ", ".join(details) if details else "-"
            
            print(f"{result['name']:<35} {result['area_type']:<20} "
                  f"{format_score(result['total_score']):<8} "
                  f"{format_score(result.get('arch_score')):<8} "
                  f"{format_score(result.get('form_score')):<8} "
                  f"{details_str}")
    
    # Summary statistics
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    
    suburban_exurban = [r for r in results if r['area_type'] in ('suburban', 'exurban', 'rural')]
    urban = [r for r in results if r['area_type'] in ('urban_core', 'urban_residential', 'urban_core_lowrise', 'historic_urban')]
    
    if suburban_exurban:
        avg_score = sum(r['total_score'] for r in suburban_exurban if r['total_score']) / len(suburban_exurban)
        print(f"Suburban/Exurban/Rural Average Score: {avg_score:.1f} ({len(suburban_exurban)} locations)")
    
    if urban:
        avg_score = sum(r['total_score'] for r in urban if r['total_score']) / len(urban)
        print(f"Urban Average Score: {avg_score:.1f} ({len(urban)} locations)")

def test_wave1():
    """Run Wave 1 tests."""
    print("Testing Wave 1 changes...")
    print(f"Testing {len(TEST_LOCATIONS)} locations\n")
    
    results = []
    
    for i, location in enumerate(TEST_LOCATIONS, 1):
        name = location['name']
        lat = location['lat']
        lon = location['lon']
        focus = location['focus']
        
        print(f"[{i}/{len(TEST_LOCATIONS)}] Testing {name}...", end=" ", flush=True)
        
        try:
            # Get area type
            density = census_api.get_population_density(lat, lon) or 0.0
            # Use None for metro_distance_km (optional parameter)
            area_type = classify_morphology(density, None, None, metro_distance_km=None)
            
            # Calculate built beauty
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
            
            arch_score = None
            form_score = None
            coherence_signal = None
            streetwall_value = None
            parking_detected = None
            
            # Try to extract architectural score (rule-based, not Ridge)
            if 'design_score' in metrics:
                arch_score = metrics.get('design_score')
            elif 'architecture_score' in details:
                arch_score = details.get('architecture_score')
            
            if 'form_score' in metrics:
                form_score = metrics.get('form_score')
            
            # Extract coherence and streetwall for analysis
            if 'age_coherence_signal' in metrics:
                coherence_signal = metrics.get('age_coherence_signal')
            elif 'coherence_signal' in metrics:
                coherence_signal = metrics.get('coherence_signal')
            
            if 'block_grain' in metrics and 'streetwall_continuity' in metrics:
                streetwall_value = metrics.get('streetwall_continuity')
            
            # Check if parking was detected (would be in metadata or logs)
            # For now, we'll note if footprint CV was adjusted
            
            results.append({
                'name': name,
                'area_type': area_type,
                'total_score': total_score,
                'arch_score': arch_score,
                'form_score': form_score,
                'coherence_signal': coherence_signal,
                'streetwall_value': streetwall_value,
                'parking_detected': parking_detected,
                'focus': focus
            })
            
            print(f"✓ Score: {format_score(total_score)}")
            
        except Exception as e:
            print(f"✗ Error: {e}")
            results.append({
                'name': name,
                'area_type': 'unknown',
                'total_score': None,
                'error': str(e),
                'focus': focus
            })
    
    print_results(results)
    return results

if __name__ == "__main__":
    test_wave1()
