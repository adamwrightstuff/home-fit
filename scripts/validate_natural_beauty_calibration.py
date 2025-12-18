#!/usr/bin/env python3
"""
Validate natural_beauty calibration using existing calibration data.
This validates the calibration math directly without making API calls.
"""

import json
import sys
import os
from statistics import mean, stdev

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def validate_calibration():
    """Validate natural_beauty calibration."""
    print("=" * 80)
    print("Validating Natural Beauty Calibration")
    print("=" * 80)
    print()
    
    # Load calibration data
    with open('analysis/calibration_data_177_locations.json') as f:
        cal_data = json.load(f)
    
    # Load calibration results
    with open('analysis/natural_beauty_calibration_results.json') as f:
        cal_results = json.load(f)
    
    CAL_A = cal_results['calibration']['CAL_A']
    CAL_B = cal_results['calibration']['CAL_B']
    
    print(f"Calibration Parameters:")
    print(f"  CAL_A: {CAL_A:.6f}")
    print(f"  CAL_B: {CAL_B:.6f}")
    print()
    
    # Extract data for natural_beauty
    raw_scores = []
    target_scores = []
    calibrated_scores = []
    locations_with_data = []
    
    for loc in cal_data['locations']:
        nb = loc['pillars'].get('natural_beauty')
        target = loc['target_scores'].get('natural_beauty')
        
        if nb and target is not None:
            raw_total = nb.get('raw_total', 0)
            if raw_total is not None:
                raw_scores.append(raw_total)
                target_scores.append(target)
                
                # Apply calibration
                calibrated = CAL_A * raw_total + CAL_B
                calibrated = max(0.0, min(100.0, calibrated))
                calibrated_scores.append(calibrated)
                
                locations_with_data.append({
                    'name': loc['name'],
                    'raw': raw_total,
                    'target': target,
                    'calibrated': calibrated,
                    'error': abs(calibrated - target)
                })
    
    if len(raw_scores) < 3:
        print("ERROR: Need at least 3 locations with target scores")
        return
    
    print(f"Locations validated: {len(raw_scores)}")
    print()
    
    # Calculate statistics
    errors = [abs(c - t) for c, t in zip(calibrated_scores, target_scores)]
    mae = mean(errors)
    max_error = max(errors)
    mean_error = mean([c - t for c, t in zip(calibrated_scores, target_scores)])
    
    # Calculate R²
    ss_res = sum((c - t) ** 2 for c, t in zip(calibrated_scores, target_scores))
    ss_tot = sum((t - mean(target_scores)) ** 2 for t in target_scores)
    r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0
    
    print("Validation Statistics:")
    print(f"  Mean Absolute Error: {mae:.2f}")
    print(f"  Max Absolute Error: {max_error:.2f}")
    print(f"  Mean Error (bias): {mean_error:.2f}")
    print(f"  R²: {r_squared:.4f}")
    print()
    
    # Show variance improvement
    raw_std = stdev(raw_scores) if len(raw_scores) > 1 else 0.0
    calibrated_std = stdev(calibrated_scores) if len(calibrated_scores) > 1 else 0.0
    target_std = stdev(target_scores) if len(target_scores) > 1 else 0.0
    
    print("Variance Analysis:")
    print(f"  Raw scores std dev: {raw_std:.2f}")
    print(f"  Calibrated scores std dev: {calibrated_std:.2f}")
    print(f"  Target scores std dev: {target_std:.2f}")
    print()
    
    # Show sample predictions
    print("Sample Predictions (first 10):")
    print("-" * 80)
    print(f"{'Location':<40} {'Raw':>8} {'Target':>8} {'Calibrated':>10} {'Error':>8}")
    print("-" * 80)
    for loc_data in sorted(locations_with_data, key=lambda x: x['error'], reverse=True)[:10]:
        print(f"{loc_data['name']:<40} {loc_data['raw']:8.2f} {loc_data['target']:8.1f} {loc_data['calibrated']:10.2f} {loc_data['error']:8.2f}")
    
    print()
    print("=" * 80)
    print("Calibration Validation Complete")
    print("=" * 80)
    print()
    print("Note: Low R² (0.0242) indicates weak correlation between raw scores")
    print("and target scores. This may indicate:")
    print("  1. Raw scores need adjustment in component calculation")
    print("  2. Target scores may have systematic bias")
    print("  3. Additional factors not captured in raw scores")
    print()
    print("However, calibration is applied to align scores with targets.")
    print("Consider reviewing component weights or scoring methodology.")


if __name__ == '__main__':
    try:
        validate_calibration()
    except Exception as e:
        print(f"\n\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
