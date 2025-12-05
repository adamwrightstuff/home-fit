#!/usr/bin/env python3
"""
Active Outdoors v2 Calibration Script
Runs scoring on Round 12 (expanded) calibration panel and fits new calibration parameters.

RESEARCH-BACKED: Target scores from external research (Perplexity, Gemini, Claude).
These are used for calibration, NOT for tuning components to match specific scores.

Design Principle: Research-backed expected values, not target-tuned values.
"""

import sys
import os
import json
import time
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import numpy as np

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data_sources.geocoding import geocode
from pillars.active_outdoors import get_active_outdoors_score_v2

# Fallback coordinates for locations that frequently fail geocoding
# Format: location_name -> (lat, lon)
FALLBACK_COORDINATES = {
    "Boulder CO": (40.0150, -105.2705),
    "Times Square NY": (40.7580, -73.9855),
    "Telluride CO": (37.9375, -107.8123),
    "Jackson Hole WY": (43.4799, -110.7618),
    "Bend OR": (44.0582, -121.3153),
    "Flagstaff AZ": (35.1983, -111.6513),
    "Asheville NC": (35.5951, -82.5515),
    "Miami Beach FL": (25.7907, -80.1300),
    "Park Slope Brooklyn NY": (40.6715, -73.9782),
    "Upper West Side New York NY": (40.7870, -73.9754),
    "Truckee CA": (39.3280, -120.1833),
    "Walnut Creek CA": (37.9101, -122.0652),
    "Downtown Detroit MI": (42.3314, -83.0458),
    "Downtown Houston TX": (29.7604, -95.3698),
    "Downtown Indianapolis IN": (39.7684, -86.1581),
    "Downtown Minneapolis MN": (44.9778, -93.2650),
    "Centennial CO": (39.5807, -104.8777),
    "Hollywood FL": (26.0112, -80.1495),
    "Outer Banks NC": (35.2321, -75.6903),  # Nags Head area
}


# Expanded Calibration Panel (Round 12)
# RESEARCH-BACKED: Target scores from external research (Perplexity, Gemini, Claude)
# These are used for calibration, NOT for tuning components to match specific scores.
# Design Principle: Research-backed expected values, not target-tuned values.
#
# Area Type Mapping:
# - "Urban" or "Urban/Suburban" → urban_core
# - "Suburban" or "Suburban/Urban" → suburban (will be auto-detected)
# - "Suburban/Exurban" → exurban (will be auto-detected)
# - "Rural" or "Rural/Exurban" → rural or exurban (will be auto-detected)
# - Unspecified → None (will be auto-detected from location)
ROUND12_PANEL = [
    # Original Round 11 locations (validated with research)
    {"name": "Bethesda MD", "target": 80, "area_type": "suburban"},
    {"name": "Boston Back Bay MA", "target": 75, "area_type": "urban_core"},
    {"name": "Boulder CO", "target": 95, "area_type": "urban_core"},
    {"name": "Downtown Chicago IL", "target": 83, "area_type": "urban_core"},
    {"name": "Downtown Denver CO", "target": 92, "area_type": "urban_core"},
    {"name": "Downtown Las Vegas NV", "target": 42, "area_type": "suburban"},
    {"name": "Downtown Phoenix AZ", "target": 48, "area_type": "urban_core"},
    {"name": "Downtown Portland OR", "target": 88, "area_type": "urban_residential"},
    {"name": "Downtown Seattle WA", "target": 92, "area_type": "urban_core"},
    {"name": "Lake Placid NY", "target": 94, "area_type": "rural"},
    {"name": "Miami Beach FL", "target": 60, "area_type": "rural"},
    {"name": "Park City UT", "target": 92, "area_type": "exurban"},
    {"name": "Park Slope Brooklyn NY", "target": 70, "area_type": "urban_core"},
    {"name": "Santa Monica CA", "target": 78, "area_type": "urban_core"},
    {"name": "Times Square NY", "target": 35, "area_type": "urban_core"},
    {"name": "Truckee CA", "target": 95, "area_type": "rural"},
    {"name": "Upper West Side New York NY", "target": 72, "area_type": "urban_core"},
    {"name": "Walnut Creek CA", "target": 82, "area_type": "suburban"},
    
    # New locations from research (Round 12 additions)
    # Exurban/Mountain Towns
    {"name": "Asheville NC", "target": 95, "area_type": None},  # Will auto-detect (likely exurban)
    {"name": "Aspen CO", "target": 96, "area_type": "rural"},  # Rural/Exurban → rural
    {"name": "Bar Harbor ME", "target": 88, "area_type": "rural"},  # Rural/Exurban → rural
    {"name": "Bend OR", "target": 95, "area_type": "exurban"},  # Suburban/Exurban → exurban
    {"name": "Flagstaff AZ", "target": 90, "area_type": None},  # Will auto-detect (likely exurban)
    {"name": "Jackson Hole WY", "target": 96, "area_type": None},  # Will auto-detect (likely rural/exurban)
    {"name": "Missoula MT", "target": 88, "area_type": None},  # Will auto-detect (likely exurban)
    {"name": "Telluride CO", "target": 97, "area_type": None},  # Will auto-detect (likely rural/exurban)
    
    # Low/Mid-Range Urban Cores
    {"name": "Downtown Dallas TX", "target": 40, "area_type": "urban_core"},
    {"name": "Downtown Detroit MI", "target": 40, "area_type": "urban_core"},
    {"name": "Downtown Houston TX", "target": 35, "area_type": "urban_core"},
    {"name": "Downtown Indianapolis IN", "target": 45, "area_type": "urban_core"},
    {"name": "Downtown Kansas City MO", "target": 45, "area_type": "urban_core"},
    {"name": "Downtown Minneapolis MN", "target": 75, "area_type": "urban_core"},
    
    # Diverse Suburban
    {"name": "Centennial CO", "target": 70, "area_type": "suburban"},
    {"name": "Gilbert AZ", "target": 52, "area_type": "suburban"},
    {"name": "Hollywood FL", "target": 60, "area_type": "suburban"},
    
    # Edge Cases
    {"name": "Outer Banks NC", "target": 75, "area_type": "rural"},  # Coastal rural
]

# Use Round 12 panel (expanded)
ROUND11_PANEL = ROUND12_PANEL  # Keep variable name for compatibility


def geocode_location(name: str, max_retries: int = 3) -> Tuple[float, float]:
    """
    Geocode a location name to lat/lon with retry logic and fallback coordinates.
    
    Args:
        name: Location name to geocode
        max_retries: Maximum number of retry attempts
    
    Returns:
        (lat, lon) tuple
    
    Raises:
        ValueError: If geocoding fails after all retries and no fallback available
    """
    # Check fallback coordinates first
    if name in FALLBACK_COORDINATES:
        lat, lon = FALLBACK_COORDINATES[name]
        print(f"🔍 Using fallback coordinates for: {name}")
        print(f"   ✅ Found: {lat:.6f}, {lon:.6f}")
        return lat, lon
    
    # Try geocoding with retries
    for attempt in range(max_retries):
        try:
            print(f"🔍 Geocoding: {name}... (attempt {attempt + 1}/{max_retries})")
            result = geocode(name)
            if result:
                lat, lon, _, _, _ = result
                print(f"   ✅ Found: {lat:.6f}, {lon:.6f}")
                return lat, lon
        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                print(f"   ⚠️  Geocoding failed: {e}")
                print(f"   ⏳ Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                print(f"   ❌ Geocoding failed after {max_retries} attempts: {e}")
    
    # If all retries failed, raise error
    raise ValueError(f"Failed to geocode: {name} (after {max_retries} attempts)")


def run_calibration_panel() -> List[Dict]:
    """Run scoring on all calibration panel locations."""
    results = []
    
    for i, location in enumerate(ROUND11_PANEL, 1):
        name = location["name"]
        target = location["target"]
        area_type = location.get("area_type")
        
        print(f"\n{'='*60}")
        print(f"Location {i}/{len(ROUND11_PANEL)}: {name}")
        print(f"Target: {target}")
        print(f"{'='*60}")
        
        try:
            # Geocode
            lat, lon = geocode_location(name)
            
            # Run scoring
            print(f"🏃 Running Active Outdoors v2 scoring...")
            score, breakdown = get_active_outdoors_score_v2(
                lat=lat,
                lon=lon,
                city=None,
                area_type=area_type,
                location_scope=None
            )
            
            # Extract raw_total from breakdown
            raw_total = breakdown.get("raw_total_v2", None)
            if raw_total is None:
                # Calculate raw_total from component scores if not provided
                daily = breakdown["breakdown"]["daily_urban_outdoors"]
                wild = breakdown["breakdown"]["wild_adventure"]
                water = breakdown["breakdown"]["waterfront_lifestyle"]
                W_DAILY = 0.30
                W_WILD = 0.50
                W_WATER = 0.20
                raw_total = W_DAILY * daily + W_WILD * wild + W_WATER * water
            
            # Calculate error
            error = score - target
            
            result = {
                "name": name,
                "target": target,
                "score": score,
                "raw_total": raw_total,
                "error": error,
                "abs_error": abs(error),
                "area_type": area_type,
                "components": breakdown["breakdown"],
                "lat": lat,
                "lon": lon,
            }
            results.append(result)
            
            print(f"\n✅ Result for {name}:")
            print(f"   Target: {target}")
            print(f"   Score: {score:.1f}")
            print(f"   Raw Total: {raw_total:.2f}")
            print(f"   Error: {error:+.1f}")
            
        except Exception as e:
            print(f"❌ Error processing {name}: {e}")
            import traceback
            traceback.print_exc()
            results.append({
                "name": name,
                "target": target,
                "error": str(e),
                "failed": True
            })
    
    return results


def fit_calibration_parameters(results: List[Dict]) -> Tuple[float, float, Dict]:
    """Fit linear calibration parameters: target ≈ CAL_A * raw_total + CAL_B."""
    # Filter out failed results
    valid_results = [r for r in results if not r.get("failed") and r.get("raw_total") is not None]
    
    if len(valid_results) < 2:
        raise ValueError(f"Need at least 2 valid results, got {len(valid_results)}")
    
    # Extract data
    raw_totals = np.array([r["raw_total"] for r in valid_results])
    targets = np.array([r["target"] for r in valid_results])
    
    # Fit linear regression using least squares: target = CAL_A * raw_total + CAL_B
    # Using numpy polyfit for degree 1 (linear) regression
    # polyfit returns coefficients [slope, intercept] for y = slope*x + intercept
    coeffs = np.polyfit(raw_totals, targets, deg=1)
    CAL_A = coeffs[0]  # slope
    CAL_B = coeffs[1]  # intercept
    
    # Calculate fitted scores and errors
    fitted_scores = CAL_A * raw_totals + CAL_B
    errors = fitted_scores - targets
    abs_errors = np.abs(errors)
    
    # Calculate R-squared
    ss_res = np.sum((targets - fitted_scores) ** 2)
    ss_tot = np.sum((targets - np.mean(targets)) ** 2)
    r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0
    
    # Statistics
    mean_error = np.mean(errors)
    mean_abs_error = np.mean(abs_errors)
    max_abs_error = np.max(abs_errors)
    
    stats = {
        "n_samples": len(valid_results),
        "mean_error": float(mean_error),
        "mean_abs_error": float(mean_abs_error),
        "max_abs_error": float(max_abs_error),
        "r_squared": float(r_squared),
        "cal_a": float(CAL_A),
        "cal_b": float(CAL_B),
    }
    
    return CAL_A, CAL_B, stats


def print_calibration_report(results: List[Dict], stats: Dict):
    """Print calibration report."""
    print(f"\n{'='*60}")
    print("CALIBRATION REPORT")
    print(f"{'='*60}")
    print(f"\nCalibration Parameters:")
    print(f"  CAL_A = {stats['cal_a']:.6f}")
    print(f"  CAL_B = {stats['cal_b']:.6f}")
    print(f"\nStatistics:")
    print(f"  Samples: {stats['n_samples']}")
    print(f"  Mean Error: {stats['mean_error']:+.2f}")
    print(f"  Mean Absolute Error: {stats['mean_abs_error']:.2f}")
    print(f"  Max Absolute Error: {stats['max_abs_error']:.2f}")
    print(f"  R²: {stats['r_squared']:.4f}")
    
    print(f"\n{'='*60}")
    print("PER-LOCATION RESULTS")
    print(f"{'='*60}")
    print(f"{'Location':<30} {'Target':>6} {'Score':>6} {'Raw':>7} {'Error':>7}")
    print(f"{'-'*60}")
    
    for r in results:
        if r.get("failed"):
            print(f"{r['name']:<30} {'FAILED':>6}")
        else:
            print(f"{r['name']:<30} {r['target']:>6.0f} {r['score']:>6.1f} {r['raw_total']:>7.2f} {r['error']:>+7.1f}")
    
    print(f"\n{'='*60}")


def main():
    """Main calibration workflow."""
    print("Active Outdoors v2 Calibration (Round 12 - Expanded Panel)")
    print("=" * 60)
    print(f"Running calibration on {len(ROUND11_PANEL)} locations...")
    print("RESEARCH-BACKED: Target scores from external research (Perplexity, Gemini, Claude)")
    print("Design Principle: These are used for calibration, NOT for tuning components.")
    print("=" * 60)
    
    # Run calibration panel
    results = run_calibration_panel()
    
    # Fit calibration parameters
    print(f"\n{'='*60}")
    print("Fitting calibration parameters...")
    print(f"{'='*60}")
    
    CAL_A, CAL_B, stats = fit_calibration_parameters(results)
    
    # Print report
    print_calibration_report(results, stats)
    
    # Save results
    output_dir = project_root / "analysis"
    output_dir.mkdir(exist_ok=True)
    
    output_file = output_dir / "active_outdoors_calibration_round12.json"
    output_data = {
        "round": 12,
        "research_sources": ["Perplexity", "Gemini", "Claude"],
        "note": "Target scores from external research. Used for calibration, not component tuning.",
        "calibration": {
            "CAL_A": stats["cal_a"],
            "CAL_B": stats["cal_b"],
            "stats": stats,
        },
        "results": results,
    }
    
    with open(output_file, "w") as f:
        json.dump(output_data, f, indent=2)
    
    print(f"\n✅ Results saved to: {output_file}")
    print(f"\n📝 Next step: Update CAL_A and CAL_B in pillars/active_outdoors.py")
    print(f"   CAL_A = {stats['cal_a']:.6f}")
    print(f"   CAL_B = {stats['cal_b']:.6f}")


if __name__ == "__main__":
    main()

