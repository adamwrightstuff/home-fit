#!/usr/bin/env python3
"""
Calculate calibration parameters for natural_beauty using target scores.
"""

import json
import sys
import os
from statistics import mean, stdev
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def calculate_calibration():
    """Calculate calibration parameters for natural_beauty."""
    print("=" * 80)
    print("Calculating Natural Beauty Calibration")
    print("=" * 80)
    print()
    
    # Load calibration data
    with open('analysis/calibration_data_177_locations.json') as f:
        cal_data = json.load(f)
    
    # Extract data for natural_beauty
    raw_scores = []
    target_scores = []
    locations_with_data = []
    
    for loc in cal_data['locations']:
        nb = loc['pillars'].get('natural_beauty')
        target = loc['target_scores'].get('natural_beauty')
        
        if nb and target is not None:
            raw_total = nb.get('raw_total', 0)
            if raw_total is not None:
                raw_scores.append(raw_total)
                target_scores.append(target)
                locations_with_data.append({
                    'name': loc['name'],
                    'raw': raw_total,
                    'target': target,
                    'current': nb.get('current_score')
                })
    
    if len(raw_scores) < 3:
        print("ERROR: Need at least 3 locations with target scores")
        return
    
    print(f"Locations with target scores: {len(raw_scores)}")
    print()
    
    # Calculate linear regression using numpy
    raw_array = np.array(raw_scores)
    target_array = np.array(target_scores)
    
    # Simple linear regression: y = ax + b
    # Using least squares: a = cov(x,y) / var(x), b = mean(y) - a * mean(x)
    cov_xy = np.cov(raw_array, target_array)[0, 1]
    var_x = np.var(raw_array, ddof=1)  # Sample variance
    
    CAL_A = cov_xy / var_x if var_x > 0 else 0.0
    CAL_B = np.mean(target_array) - CAL_A * np.mean(raw_array)
    
    # Calculate R²
    predicted = CAL_A * raw_array + CAL_B
    ss_res = np.sum((target_array - predicted) ** 2)
    ss_tot = np.sum((target_array - np.mean(target_array)) ** 2)
    r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0
    
    # Calculate standard error
    std_err = np.sqrt(ss_res / (len(raw_scores) - 2)) if len(raw_scores) > 2 else 0.0
    
    # Calculate errors
    predicted = [CAL_A * raw + CAL_B for raw in raw_scores]
    errors = [abs(p - t) for p, t in zip(predicted, target_scores)]
    mae = mean(errors)
    max_error = max(errors)
    
    print("Calibration Parameters:")
    print(f"  CAL_A: {CAL_A:.6f}")
    print(f"  CAL_B: {CAL_B:.6f}")
    print()
    
    print("Calibration Statistics:")
    print(f"  R²: {r_squared:.4f}")
    print(f"  Mean Absolute Error: {mae:.2f}")
    print(f"  Max Absolute Error: {max_error:.2f}")
    print(f"  Standard Error: {std_err:.4f}")
    print()
    
    # Show sample predictions
    print("Sample Predictions (first 10):")
    print("-" * 80)
    print(f"{'Location':<40} {'Raw':>8} {'Target':>8} {'Predicted':>10} {'Error':>8}")
    print("-" * 80)
    for loc_data in locations_with_data[:10]:
        predicted_score = CAL_A * loc_data['raw'] + CAL_B
        error = abs(predicted_score - loc_data['target'])
        print(f"{loc_data['name']:<40} {loc_data['raw']:8.2f} {loc_data['target']:8.1f} {predicted_score:10.2f} {error:8.2f}")
    
    if len(locations_with_data) > 10:
        print(f"... ({len(locations_with_data) - 10} more)")
    
    print()
    print("=" * 80)
    print("Calibration Parameters to Use")
    print("=" * 80)
    print(f"CAL_A = {CAL_A:.6f}")
    print(f"CAL_B = {CAL_B:.6f}")
    print()
    
    # Save calibration results
    calibration_results = {
        "pillar": "natural_beauty",
        "source": "perplexity_target_scores",
        "n_samples": len(raw_scores),
        "calibration": {
            "CAL_A": CAL_A,
            "CAL_B": CAL_B
        },
        "stats": {
            "r_squared": r_squared,
            "mean_abs_error": mae,
            "max_abs_error": max_error,
            "std_err": std_err
        },
        "sample_locations": locations_with_data[:10]
    }
    
    with open('analysis/natural_beauty_calibration_results.json', 'w') as f:
        json.dump(calibration_results, f, indent=2)
    
    print("✅ Saved calibration results to analysis/natural_beauty_calibration_results.json")
    
    return CAL_A, CAL_B


if __name__ == '__main__':
    try:
        calculate_calibration()
    except Exception as e:
        print(f"\n\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
