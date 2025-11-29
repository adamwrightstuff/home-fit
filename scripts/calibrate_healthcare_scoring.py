#!/usr/bin/env python3
"""
Calibrate Healthcare Access Scoring Curve

This script analyzes calibration panel data and target scores to derive research-backed
scoring curve parameters that replace arbitrary breakpoints.

Methodology:
1. Load calibration panel (counts and target scores)
2. Get expected values for each area type
3. Calculate ratios (actual / expected) for each component
4. Fit curve parameters to minimize error vs targets
5. Output calibrated breakpoints

Usage:
    python scripts/calibrate_healthcare_scoring.py
"""

import sys
import json
import math
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
import statistics

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from data_sources.regional_baselines import get_contextual_expectations

# Calibration panel path
CALIBRATION_PANEL_PATH = Path(__file__).parent.parent / "analysis" / "healthcare_calibration_panel.json"


def load_calibration_panel() -> List[Dict]:
    """Load calibration panel from JSON file."""
    with open(CALIBRATION_PANEL_PATH, 'r') as f:
        data = json.load(f)
    return data.get("calibration_panel", [])


def get_expected_values(area_type: str) -> Dict[str, int]:
    """Get expected healthcare counts for an area type."""
    expectations = get_contextual_expectations(area_type, "healthcare_access") or {}
    return {
        "hospitals": expectations.get("expected_hospitals_within_10km", 0),
        "urgent_care": expectations.get("expected_urgent_care_within_5km", 0),
        "pharmacies": expectations.get("expected_pharmacies_within_2km", 0),
    }


def calculate_ratios(location_data: Dict, expected: Dict[str, int]) -> Dict[str, float]:
    """Calculate ratios (actual / expected) for each healthcare component."""
    data = location_data.get("data", {})
    
    hospital_count = data.get("hospital_count", 0) or 0
    urgent_care_count = data.get("urgent_care_count", 0) or 0
    pharmacy_count = data.get("pharmacy_count", 0) or 0
    
    ratios = {}
    
    # Hospitals
    if expected["hospitals"] > 0:
        ratios["hospitals"] = hospital_count / float(expected["hospitals"])
    elif hospital_count > 0:
        ratios["hospitals"] = float('inf')  # Has hospitals but none expected
    else:
        ratios["hospitals"] = 0.0
    
    # Urgent care
    if expected["urgent_care"] > 0:
        ratios["urgent_care"] = urgent_care_count / float(expected["urgent_care"])
    elif urgent_care_count > 0:
        ratios["urgent_care"] = float('inf')  # Has urgent care but none expected
    else:
        ratios["urgent_care"] = 0.0
    
    # Pharmacies
    if expected["pharmacies"] > 0:
        ratios["pharmacies"] = pharmacy_count / float(expected["pharmacies"])
    elif pharmacy_count > 0:
        ratios["pharmacies"] = float('inf')  # Has pharmacies but none expected
    else:
        ratios["pharmacies"] = 0.0
    
    return ratios


def saturation_curve(ratio: float, max_score: float = 100.0) -> float:
    """
    Exponential saturation curve: score = max_score * (1 - e^(-ratio))
    
    This is the _sat_ratio_v2 pattern from Active Outdoors.
    """
    if ratio <= 0:
        return 0.0
    return max_score * (1.0 - math.exp(-ratio))


def piecewise_linear_curve(ratio: float, breakpoints: Dict[str, float], max_score: float = 100.0) -> float:
    """
    Piecewise linear curve with research-backed breakpoints.
    
    Similar to transit calibration, but adapted for healthcare components.
    
    Args:
        ratio: Count ratio (actual / expected)
        breakpoints: Dict with keys: 'at_expected', 'at_good', 'at_excellent', 'at_exceptional'
        max_score: Maximum score cap
    """
    at_expected = breakpoints.get('at_expected', 60.0)
    at_good = breakpoints.get('at_good', 80.0)
    at_excellent = breakpoints.get('at_excellent', 90.0)
    at_exceptional = breakpoints.get('at_exceptional', 95.0)
    
    ratio_expected = breakpoints.get('ratio_expected', 1.0)
    ratio_good = breakpoints.get('ratio_good', 1.5)
    ratio_excellent = breakpoints.get('ratio_excellent', 2.0)
    ratio_exceptional = breakpoints.get('ratio_exceptional', 3.0)
    
    if ratio <= 0.1:
        return 0.0
    if ratio < ratio_expected:
        # Linear from 0 to at_expected
        return (at_expected / ratio_expected) * ratio
    if ratio < ratio_good:
        # Linear from at_expected to at_good
        return at_expected + (ratio - ratio_expected) * (at_good - at_expected) / (ratio_good - ratio_expected)
    if ratio < ratio_excellent:
        # Linear from at_good to at_excellent
        return at_good + (ratio - ratio_good) * (at_excellent - at_good) / (ratio_excellent - ratio_good)
    if ratio < ratio_exceptional:
        # Linear from at_excellent to at_exceptional
        return at_excellent + (ratio - ratio_excellent) * (at_exceptional - at_excellent) / (ratio_exceptional - ratio_excellent)
    # At or above exceptional
    return min(max_score, at_exceptional)


def calculate_component_scores(ratios: Dict[str, float], curve_func, **curve_params) -> Dict[str, float]:
    """
    Calculate scores for each healthcare component.
    
    Returns:
        Dict with scores for hospitals, urgent_care, pharmacies
    """
    scores = {}
    for component, ratio in ratios.items():
        if ratio == float('inf'):
            # Has facilities but none expected - treat as exceptional
            ratio = 5.0  # Arbitrary high ratio
        if ratio > 0:
            # Handle different curve function signatures
            if curve_func == piecewise_linear_curve:
                # piecewise_linear_curve expects breakpoints dict
                score = curve_func(ratio, breakpoints=curve_params, max_score=curve_params.get('max_score', 100.0))
            else:
                # saturation_curve expects max_score directly
                score = curve_func(ratio, **curve_params)
            scores[component] = score
        else:
            scores[component] = 0.0
    
    return scores


def calibrate_curve(panel_data: List[Dict], curve_func, initial_params: Dict) -> Dict:
    """
    Calibrate scoring curve to minimize error vs target scores.
    
    Args:
        panel_data: List of calibration panel entries with target scores
        curve_func: Function to use for scoring (saturation_curve or piecewise_linear_curve)
        initial_params: Initial parameters for curve function
    
    Returns:
        Dict with calibrated parameters and error metrics
    """
    # Filter to locations with target scores
    locations_with_targets = [loc for loc in panel_data if loc.get("target_score") is not None]
    
    if len(locations_with_targets) < 8:
        print(f"⚠️  Warning: Only {len(locations_with_targets)} locations have target scores.")
        print("   Need at least 8 locations for reliable calibration.")
        return {}
    
    # Collect data points: (ratios, target_score, location)
    data_points = []
    
    for location in locations_with_targets:
        area_type = location.get("area_type", "urban_core")
        expected = get_expected_values(area_type)
        ratios = calculate_ratios(location, expected)
        target = location.get("target_score")
        
        if target is not None:
            data_points.append({
                "location": location.get("location"),
                "area_type": area_type,
                "ratios": ratios,
                "target": target,
                "expected": expected
            })
    
    # Try different parameter combinations
    best_params = initial_params.copy()
    best_error = float('inf')
    best_results = None
    
    # Grid search for piecewise linear parameters
    if curve_func == piecewise_linear_curve:
        for at_expected in [50, 55, 60, 65]:
            for at_good in [75, 80, 85]:
                for at_excellent in [85, 90, 95]:
                    for ratio_good in [1.5, 2.0]:
                        for ratio_excellent in [2.0, 2.5, 3.0]:
                            params = {
                                'at_expected': float(at_expected),
                                'at_good': float(at_good),
                                'at_excellent': float(at_excellent),
                                'at_exceptional': 95.0,
                                'ratio_expected': 1.0,
                                'ratio_good': float(ratio_good),
                                'ratio_excellent': float(ratio_excellent),
                                'ratio_exceptional': 3.0,
                                'max_score': 100.0
                            }
                            
                            errors = []
                            for point in data_points:
                                # Calculate score for each component, then combine
                                component_scores = calculate_component_scores(
                                    point["ratios"], curve_func, **params
                                )
                                
                                # Simple combination: weighted average or max
                                # For now, use max (best component) + small bonus for multiple
                                base_score = max(component_scores.values()) if component_scores else 0.0
                                
                                # Small bonus for multiple strong components
                                strong_components = [s for s in component_scores.values() if s >= 20.0]
                                bonus = 3.0 if len(strong_components) >= 2 else 0.0
                                
                                predicted = min(100.0, base_score + bonus)
                                error = abs(predicted - point["target"])
                                errors.append(error)
                            
                            avg_error = statistics.mean(errors)
                            max_error = max(errors)
                            rmse = math.sqrt(statistics.mean([e**2 for e in errors]))
                            
                            if avg_error < best_error:
                                best_error = avg_error
                                best_params = params
                                best_results = {
                                    'avg_error': avg_error,
                                    'max_error': max_error,
                                    'rmse': rmse,
                                    'errors': errors,
                                    'data_points': data_points
                                }
    
    # For saturation curve, try different max_score values
    elif curve_func == saturation_curve:
        for max_score in [35, 40, 45, 50, 55, 60]:
            params = {'max_score': float(max_score)}
            
            errors = []
            for point in data_points:
                component_scores = calculate_component_scores(
                    point["ratios"], curve_func, **params
                )
                
                base_score = max(component_scores.values()) if component_scores else 0.0
                strong_components = [s for s in component_scores.values() if s >= 20.0]
                bonus = 3.0 if len(strong_components) >= 2 else 0.0
                
                predicted = min(100.0, base_score + bonus)
                error = abs(predicted - point["target"])
                errors.append(error)
            
            avg_error = statistics.mean(errors)
            max_error = max(errors)
            rmse = math.sqrt(statistics.mean([e**2 for e in errors]))
            
            if avg_error < best_error:
                best_error = avg_error
                best_params = params
                best_results = {
                    'avg_error': avg_error,
                    'max_error': max_error,
                    'rmse': rmse,
                    'errors': errors,
                    'data_points': data_points
                }
    
    if best_results:
        best_results['params'] = best_params
        return best_results
    
    return {}


def print_calibration_results(results: Dict, curve_name: str):
    """Print calibration results in a readable format."""
    if not results:
        print("No calibration results available.")
        return
    
    params = results.get('params', {})
    avg_error = results.get('avg_error', 0)
    max_error = results.get('max_error', 0)
    rmse = results.get('rmse', 0)
    
    print(f"\n{'='*60}")
    print(f"Calibration Results: {curve_name}")
    print(f"{'='*60}")
    print(f"Average Error: {avg_error:.2f} points")
    print(f"Max Error: {max_error:.2f} points")
    print(f"RMSE: {rmse:.2f} points")
    print(f"\nCalibrated Parameters:")
    for key, value in params.items():
        print(f"  {key}: {value}")
    
    print(f"\nLocation-by-Location Results:")
    data_points = results.get('data_points', [])
    errors = results.get('errors', [])
    
    for i, point in enumerate(data_points):
        location = point.get("location", "Unknown")
        target = point.get("target", 0)
        predicted = target - errors[i] if i < len(errors) else 0
        error = errors[i] if i < len(errors) else 0
        print(f"  {location:30s} Target: {target:5.1f}  Predicted: {predicted:5.1f}  Error: {error:5.1f}")


def main():
    """Main calibration function."""
    print("Loading calibration panel...")
    panel_data = load_calibration_panel()
    
    # Check for target scores
    locations_with_targets = [loc for loc in panel_data if loc.get("target_score") is not None]
    
    if len(locations_with_targets) == 0:
        print("❌ No target scores found in calibration panel.")
        print("   Please add target_score values to healthcare_calibration_panel.json")
        print("   Target scores should reflect real-world healthcare quality perception.")
        return
    
    if len(locations_with_targets) < 8:
        print(f"⚠️  Warning: Only {len(locations_with_targets)} locations have target scores.")
        print("   Recommended: 16+ locations for reliable calibration.")
        print("   Proceeding with available data...")
    
    print(f"✓ Loaded {len(panel_data)} locations ({len(locations_with_targets)} with target scores)")
    
    # Try piecewise linear curve (similar to transit)
    print("\nCalibrating piecewise linear curve...")
    initial_piecewise = {
        'at_expected': 60.0,
        'at_good': 80.0,
        'at_excellent': 90.0,
        'at_exceptional': 95.0,
        'ratio_expected': 1.0,
        'ratio_good': 1.5,
        'ratio_excellent': 2.0,
        'ratio_exceptional': 3.0,
        'max_score': 100.0
    }
    
    piecewise_results = calibrate_curve(panel_data, piecewise_linear_curve, initial_piecewise)
    if piecewise_results:
        print_calibration_results(piecewise_results, "Piecewise Linear")
    
    # Try saturation curve (similar to active outdoors)
    print("\nCalibrating saturation curve...")
    initial_saturation = {'max_score': 50.0}
    
    saturation_results = calibrate_curve(panel_data, saturation_curve, initial_saturation)
    if saturation_results:
        print_calibration_results(saturation_results, "Saturation (Exponential)")
    
    # Save results
    output_path = Path(__file__).parent.parent / "analysis" / "healthcare_calibration_results.json"
    output_data = {
        "piecewise_linear": piecewise_results,
        "saturation": saturation_results,
        "calibration_date": "2024-12-19",
        "panel_size": len(locations_with_targets)
    }
    
    with open(output_path, 'w') as f:
        json.dump(output_data, f, indent=2)
    
    print(f"\n✓ Results saved to {output_path}")


if __name__ == "__main__":
    main()

