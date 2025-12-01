#!/usr/bin/env python3
"""
Calibrate Neighborhood Amenities Scoring

This script analyzes the neighborhood_amenities calibration panel and compares
the current pillar scores to LLM-researched target scores.

Current focus:
- Evaluate how well the existing scoring aligns with target scores.
- Produce error metrics (average error, max error, RMSE).

Future work:
- Extend this script to fit calibrated curves for density, variety, proximity,
  and location quality, replacing hard thresholds and global linear calibration.

Usage:
    python scripts/calibrate_neighborhood_amenities_scoring.py
"""

import sys
import json
import math
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import statistics

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from data_sources.geocoding import geocode
from data_sources.regional_baselines import get_contextual_expectations
from pillars.neighborhood_amenities import get_neighborhood_amenities_score

CALIBRATION_PANEL_PATH = (
    Path(__file__).parent.parent
    / "analysis"
    / "neighborhood_amenities_calibration_panel.json"
)


def load_calibration_panel() -> List[Dict]:
    """Load calibration panel from JSON file."""
    with open(CALIBRATION_PANEL_PATH, "r") as f:
        data = json.load(f)
    return data.get("calibration_panel", [])


def _safe_geocode(location: str) -> Optional[Tuple[float, float]]:
    """
    Geocode a location string to (lat, lon).

    Returns None if geocoding fails.
    """
    try:
        result = geocode(location)
        if not result:
            return None
        # geocode() returns (lat, lon, zip_code, state, city)
        lat, lon = result[0], result[1]
        return lat, lon
    except Exception as e:
        print(f"⚠️  Geocoding failed for '{location}': {e}")
        return None


def evaluate_current_scoring(panel: List[Dict]) -> Dict:
    """
    Evaluate current neighborhood_amenities scoring against target scores.

    For each panel location:
    - Geocode the location string
    - Call get_neighborhood_amenities_score(include_chains=True)
    - Compare actual score to target_score

    Returns:
        Dict with error metrics and per-location results.
    """
    results: List[Dict] = []

    for entry in panel:
        location_name = entry.get("location")
        area_type = entry.get("area_type")
        target_score = entry.get("target_score")

        if target_score is None:
            continue

        print(f"\n📍 Evaluating: {location_name} (area_type={area_type}, target={target_score})")

        coords = _safe_geocode(location_name)
        if coords is None:
            print(f"   ⚠️  Skipping {location_name}: geocoding failed")
            continue

        lat, lon = coords

        try:
            # Use include_chains=True to reflect real-world amenity access
            score, breakdown = get_neighborhood_amenities_score(
                lat=lat,
                lon=lon,
                include_chains=True,
                location_scope=None,
                area_type=area_type,
            )
        except Exception as e:
            print(f"   ❌ neighborhood_amenities scoring failed for {location_name}: {e}")
            continue

        home = breakdown.get("breakdown", {}).get("home_walkability", {})
        loc_quality = breakdown.get("breakdown", {}).get("location_quality", 0.0)

        home_score = float(home.get("score", 0.0))
        density_score = float(home.get("breakdown", {}).get("density", 0.0))
        variety_score = float(home.get("breakdown", {}).get("variety", 0.0))
        proximity_score = float(home.get("breakdown", {}).get("proximity", 0.0))

        raw_total = float(breakdown.get("raw_total", home_score + float(loc_quality)))
        cal_a = breakdown.get("calibration", {}).get("a")
        cal_b = breakdown.get("calibration", {}).get("b")

        error = float(score) - float(target_score)

        print(
            f"   ✅ Actual score: {score:.1f} | Target: {target_score:.1f} | Error: {error:+.1f}"
        )
        print(
            f"   🏠 Home: {home_score:.1f}/60 (density={density_score:.1f}, variety={variety_score:.1f}, proximity={proximity_score:.1f})"
        )
        print(f"   🌆 Location quality: {loc_quality:.1f}/40")
        if cal_a is not None and cal_b is not None:
            print(f"   🔧 Calibration: raw_total={raw_total:.1f}, a={cal_a}, b={cal_b}")

        results.append(
            {
                "location": location_name,
                "area_type": area_type,
                "lat": lat,
                "lon": lon,
                "target": float(target_score),
                "actual": float(score),
                "error": error,
                "home_score": home_score,
                "density_score": density_score,
                "variety_score": variety_score,
                "proximity_score": proximity_score,
                "location_quality": float(loc_quality),
                "raw_total": raw_total,
                "calibration_a": cal_a,
                "calibration_b": cal_b,
            }
        )

    if not results:
        print("\n❌ No successful evaluations. Check geocoding or pillar errors.")
        return {"results": [], "avg_error": None, "max_error": None, "rmse": None}

    errors = [abs(r["error"]) for r in results]
    squared_errors = [e ** 2 for e in errors]

    avg_error = statistics.mean(errors)
    max_error = max(errors)
    rmse = math.sqrt(statistics.mean(squared_errors))

    print("\n" + "=" * 60)
    print("Neighborhood Amenities Calibration – Current Scoring vs Targets")
    print("=" * 60)
    print(f"Average absolute error: {avg_error:.2f} points")
    print(f"Max absolute error:     {max_error:.2f} points")
    print(f"RMSE:                   {rmse:.2f} points")

    print("\nLocation-by-location:")
    for r in results:
        print(
            f"  {r['location']:30s} "
            f"Target: {r['target']:5.1f}  "
            f"Actual: {r['actual']:5.1f}  "
            f"Error: {r['error']:5.1f}"
        )

    return {
        "results": results,
        "avg_error": avg_error,
        "max_error": max_error,
        "rmse": rmse,
    }


def get_expected_values(area_type: str) -> Dict[str, int]:
    """Get expected business counts for an area type."""
    expectations = get_contextual_expectations(area_type, "neighborhood_amenities") or {}
    return {
        "businesses_1km": expectations.get("expected_businesses_within_1km", 0),
        "business_types": expectations.get("expected_business_types", 0),
        "restaurants_1km": expectations.get("expected_restaurants_within_1km", 0),
    }


def calculate_ratios(breakdown: Dict, area_type: str) -> Dict[str, float]:
    """Calculate ratios (actual / expected) for density, variety, proximity."""
    expected = get_expected_values(area_type)
    
    summary = breakdown.get("summary", {})
    diagnostics = breakdown.get("diagnostics", {})
    
    # Density: businesses within walkable distance (typically 1km)
    businesses_walkable = summary.get("within_10min_walk", 0)  # ~800m-1km
    if businesses_walkable == 0:
        businesses_walkable = diagnostics.get("businesses_within_walkable", 0)
    
    # Variety: unique business types
    tier_counts = summary.get("by_tier", {})
    all_types = set()
    for tier in ["daily_essentials", "social_dining", "culture_leisure", "services_retail"]:
        tier_types = tier_counts.get(tier, {}).get("types", [])
        all_types.update(tier_types)
    business_types_count = len(all_types)
    
    # Proximity: median distance (lower is better, so we'll invert the ratio)
    median_distance_m = summary.get("downtown_center_distance_m", 0) or diagnostics.get("median_distance_m", 0)
    
    ratios = {}
    
    # Density ratio
    if expected["businesses_1km"] > 0:
        ratios["density"] = businesses_walkable / float(expected["businesses_1km"])
    elif businesses_walkable > 0:
        ratios["density"] = float('inf')
    else:
        ratios["density"] = 0.0
    
    # Variety ratio
    if expected["business_types"] > 0:
        ratios["variety"] = business_types_count / float(expected["business_types"])
    elif business_types_count > 0:
        ratios["variety"] = float('inf')
    else:
        ratios["variety"] = 0.0
    
    # Proximity: use expected median distance from research (invert: lower distance = higher ratio)
    # Research shows median_distance_m: urban_core=630.5, suburban=389.0, exurban=311.0, rural=662.0
    expected_median_m = {
        "urban_core": 630.5,
        "urban_residential": 630.5,
        "suburban": 389.0,
        "exurban": 311.0,
        "rural": 662.0,
    }.get(area_type, 500.0)
    
    if median_distance_m > 0 and expected_median_m > 0:
        # Invert: closer = better, so ratio = expected / actual
        ratios["proximity"] = expected_median_m / float(median_distance_m)
    else:
        ratios["proximity"] = 0.0
    
    return ratios


def piecewise_linear_curve(ratio: float, breakpoints: Dict[str, float], max_score: float = 100.0) -> float:
    """
    Piecewise linear curve with calibrated breakpoints.
    
    Similar to healthcare calibration pattern.
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
        return (at_expected / ratio_expected) * ratio
    if ratio < ratio_good:
        return at_expected + (ratio - ratio_expected) * (at_good - at_expected) / (ratio_good - ratio_expected)
    if ratio < ratio_excellent:
        return at_good + (ratio - ratio_good) * (at_excellent - at_good) / (ratio_excellent - ratio_good)
    if ratio < ratio_exceptional:
        return at_excellent + (ratio - ratio_excellent) * (at_exceptional - at_excellent) / (ratio_exceptional - ratio_excellent)
    return min(max_score, at_exceptional)


def fit_area_type_calibration(results: List[Dict], area_type: str) -> Optional[Dict]:
    """
    Fit calibration curves for a specific area type with non-negativity constraint.
    
    Constraint: calibrated_score >= 0 for all raw >= 0
    This ensures the calibration function is valid across its entire domain.
    
    Returns calibrated parameters for density, variety, proximity, and location_quality.
    """
    area_results = [r for r in results if r.get("area_type") == area_type]
    
    if len(area_results) < 3:
        print(f"   ⚠️  Not enough data for {area_type} (n={len(area_results)})")
        return None
    
    # Collect ratios and target scores
    data_points = []
    for r in area_results:
        # We need to recalculate ratios from the breakdown
        # For now, use raw scores as proxies - we'll need to extend evaluate_current_scoring
        # to also collect business counts
        data_points.append({
            "target": r["target"],
            "raw_total": r["raw_total"],
            "density_score": r["density_score"],
            "variety_score": r["variety_score"],
            "proximity_score": r["proximity_score"],
            "location_quality": r["location_quality"],
        })
    
    # Fit area-type-specific linear calibration: target = a * raw + b
    # Using least squares
    n = len(data_points)
    sum_raw = sum(p["raw_total"] for p in data_points)
    sum_target = sum(p["target"] for p in data_points)
    sum_raw_sq = sum(p["raw_total"] ** 2 for p in data_points)
    sum_raw_target = sum(p["raw_total"] * p["target"] for p in data_points)
    
    denominator = n * sum_raw_sq - sum_raw ** 2
    if abs(denominator) < 1e-6:
        return None
    
    cal_a = (n * sum_raw_target - sum_raw * sum_target) / denominator
    cal_b = (sum_target - cal_a * sum_raw) / n
    
    # Apply non-negativity constraint: ensure calibrated_score >= 0 for all raw >= 0
    # For linear function target = a * raw + b:
    # - At raw = 0: b >= 0
    # - For raw > 0: if a > 0 and b < 0, we need to ensure a * raw + b >= 0
    #   This means: raw >= -b/a (zero crossing)
    # To ensure non-negative for all raw >= 0, we need b >= 0
    # If b < 0, we constrain b = 0 and refit a
    constrained = False
    if cal_b < 0:
        constrained = True
        # Constrain b = 0, refit a using least squares: a = sum(raw * target) / sum(raw^2)
        # This ensures the calibration passes through (0, 0) and is non-negative
        cal_b = 0.0
        if sum_raw_sq > 1e-6:
            cal_a = sum_raw_target / sum_raw_sq
        else:
            # Fallback: use average ratio
            cal_a = sum_target / sum_raw if sum_raw > 1e-6 else 1.0
    
    # Calculate errors (using constrained calibration)
    errors = []
    for p in data_points:
        predicted = cal_a * p["raw_total"] + cal_b
        predicted = max(0.0, min(100.0, predicted))  # Cap at 0-100 for error calculation
        errors.append(abs(predicted - p["target"]))
    
    avg_error = statistics.mean(errors)
    max_error = max(errors)
    rmse = math.sqrt(statistics.mean([e ** 2 for e in errors]))
    
    result = {
        "area_type": area_type,
        "calibration_a": cal_a,
        "calibration_b": cal_b,
        "avg_error": avg_error,
        "max_error": max_error,
        "rmse": rmse,
        "n": n,
        "constrained": constrained,
    }
    
    if constrained:
        result["constraint_note"] = "Calibration constrained to ensure non-negative scores (b >= 0)"
    
    return result


def main() -> None:
    print("Loading neighborhood amenities calibration panel...")
    panel = load_calibration_panel()
    if not panel:
        print("❌ Calibration panel is empty. Ensure the JSON file is populated.")
        return

    print(f"✓ Loaded {len(panel)} locations from {CALIBRATION_PANEL_PATH}")

    results = evaluate_current_scoring(panel)
    
    # Fit area-type-specific calibrations
    print("\n" + "=" * 60)
    print("Fitting Area-Type-Specific Calibration Curves")
    print("=" * 60)
    
    area_type_calibrations = {}
    for area_type in ["urban_core", "urban_residential", "suburban", "exurban", "rural"]:
        cal = fit_area_type_calibration(results["results"], area_type)
        if cal:
            area_type_calibrations[area_type] = cal
            print(f"\n{area_type}:")
            print(f"  Calibration: target = {cal['calibration_a']:.4f} * raw + {cal['calibration_b']:.2f}")
            print(f"  Average error: {cal['avg_error']:.2f} points")
            print(f"  Max error:     {cal['max_error']:.2f} points")
            print(f"  RMSE:          {cal['rmse']:.2f} points")
            print(f"  Sample size:   {cal['n']} locations")

    # Save results for further analysis
    output_path = (
        Path(__file__).parent.parent
        / "analysis"
        / "neighborhood_amenities_calibration_results.json"
    )
    
    results["area_type_calibrations"] = area_type_calibrations
    
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\n✓ Detailed results saved to {output_path}")


if __name__ == "__main__":
    main()


