#!/usr/bin/env python3
"""
Calibrate Transit Scoring Curve

This script analyzes research data and target scores to derive research-backed
scoring curve parameters that replace arbitrary breakpoints.

Methodology:
1. Load research data (route counts, actual scores)
2. Load target scores for known locations
3. Calculate route ratios (actual / expected)
4. Fit curve parameters to minimize error vs targets
5. Output calibrated breakpoints
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

# Target scores and actual route counts from user's test results
# Format: {location: {"target": score, "heavy_rail": count, "light_rail": count, "bus": count, "area_type": type}}
TEST_LOCATIONS = {
    "Midtown Manhattan NY": {
        "target": 100,
        "heavy_rail": 65,
        "light_rail": 1,
        "bus": 403,
        "area_type": "urban_core",
    },
    "The Loop Chicago IL": {
        "target": 97,
        "heavy_rail": 85,
        "light_rail": 3,
        "bus": 52,
        "area_type": "suburban",  # Note: classified as suburban but should be urban_core
    },
    "Back Bay Boston MA": {
        "target": 95,
        "heavy_rail": 85,
        "light_rail": 68,
        "bus": 85,
        "area_type": "urban_core",
    },
    "Pearl District Portland OR": {
        "target": 87,
        "heavy_rail": 3,
        "light_rail": 8,
        "bus": 51,
        "area_type": "urban_core",
    },
    "Uptown Charlotte NC": {
        "target": 55,
        "heavy_rail": 0,
        "light_rail": 2,
        "bus": 47,
        "area_type": "urban_residential",
    },
    "Midtown Atlanta GA": {
        "target": 78,
        "heavy_rail": 3,
        "light_rail": 0,
        "bus": 7,
        "area_type": "urban_residential",
    },
    "Koreatown Los Angeles CA": {
        "target": 73,
        "heavy_rail": 13,
        "light_rail": 2,
        "bus": 90,
        "area_type": "urban_core",
    },
    "Dupont Circle Washington DC": {
        "target": 90,
        "heavy_rail": 0,
        "light_rail": 0,
        "bus": 2,
        "area_type": "rural",  # Note: geocoding bug, should be urban_core
    },
}

# Research data path
RESEARCH_DATA_PATH = Path(__file__).parent.parent / "analysis" / "research_data_transit" / "expected_values_raw_data.json"


def load_research_data() -> List[Dict]:
    """Load research data from JSON file."""
    with open(RESEARCH_DATA_PATH, 'r') as f:
        data = json.load(f)
    return data.get("raw_data", [])


def get_expected_values(area_type: str) -> Dict[str, int]:
    """Get expected route counts for an area type."""
    expectations = get_contextual_expectations(area_type, "public_transit_access") or {}
    return {
        "heavy_rail": expectations.get("expected_heavy_rail_routes", 0),
        "light_rail": expectations.get("expected_light_rail_routes", 0),
        "bus": expectations.get("expected_bus_routes", 0),
    }


def calculate_route_ratios(location_data: Dict, expected: Dict[str, int]) -> Dict[str, float]:
    """Calculate route ratios (actual / expected) for each mode."""
    transit = location_data.get("transit", {})
    
    # Note: research data uses "stops" but they're actually route counts
    heavy_count = transit.get("heavy_rail_stops", 0) or 0
    light_count = transit.get("light_rail_stops", 0) or 0
    bus_count = transit.get("bus_stops", 0) or 0
    
    ratios = {}
    if expected["heavy_rail"] > 0:
        ratios["heavy_rail"] = heavy_count / float(expected["heavy_rail"])
    elif heavy_count > 0:
        ratios["heavy_rail"] = float('inf')  # Has routes but none expected
    else:
        ratios["heavy_rail"] = 0.0
    
    if expected["light_rail"] > 0:
        ratios["light_rail"] = light_count / float(expected["light_rail"])
    elif light_count > 0:
        ratios["light_rail"] = float('inf')  # Has routes but none expected
    else:
        ratios["light_rail"] = 0.0
    
    if expected["bus"] > 0:
        ratios["bus"] = bus_count / float(expected["bus"])
    elif bus_count > 0:
        ratios["bus"] = float('inf')  # Has routes but none expected
    else:
        ratios["bus"] = 0.0
    
    return ratios


def current_scoring_curve(ratio: float, max_score: float = 95.0) -> float:
    """Current scoring curve implementation."""
    if ratio <= 0.1:
        return 0.0
    if ratio < 1.0:
        return 60.0 * ratio
    if ratio < 2.0:
        return 60.0 + (ratio - 1.0) * 25.0
    if ratio >= 3.0:
        return max_score
    return 85.0 + (ratio - 2.0) * (max_score - 85.0)


def sigmoid_curve(ratio: float, k: float = 2.0, midpoint: float = 1.5, max_score: float = 95.0) -> float:
    """Sigmoid curve: score = max_score / (1 + e^(-k * (ratio - midpoint)))."""
    if ratio <= 0:
        return 0.0
    # Shift so that ratio=0 maps to score=0
    # Use: score = max_score * (1 / (1 + e^(-k * (ratio - midpoint))) - offset)
    # where offset = 1 / (1 + e^(k * midpoint)) to ensure score(0) = 0
    offset = 1 / (1 + math.exp(k * midpoint))
    sigmoid_value = 1 / (1 + math.exp(-k * (ratio - midpoint)))
    return max_score * (sigmoid_value - offset) / (1 - offset)


def piecewise_curve(ratio: float, breakpoints: Dict[str, float], max_score: float = 95.0) -> float:
    """
    Piecewise linear curve with research-backed breakpoints.
    
    Args:
        ratio: Route count ratio (actual / expected)
        breakpoints: Dict with keys: 'at_expected', 'at_good', 'at_excellent', 'at_exceptional'
        max_score: Maximum score cap
    """
    at_expected = breakpoints.get('at_expected', 50.0)
    at_good = breakpoints.get('at_good', 75.0)
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
    return min(max_score, at_exceptional + (ratio - ratio_exceptional) * (max_score - at_exceptional) / (ratio_exceptional * 0.5))


def find_best_mode_score(ratios: Dict[str, float], curve_func, **curve_params) -> Tuple[float, float]:
    """
    Find the best single mode score (max of all modes) and multimodal bonus.
    
    Returns:
        (base_score, multimodal_bonus)
    """
    scores = []
    for mode, ratio in ratios.items():
        if ratio == float('inf'):
            # Has routes but none expected - treat as exceptional
            ratio = 5.0  # Arbitrary high ratio
        if ratio > 0:
            score = curve_func(ratio, **curve_params)
            scores.append(score)
    
    base_score = max(scores) if scores else 0.0
    
    # Calculate multimodal bonus (same logic as in scoring function)
    strong_modes = [s for s in scores if s >= 30.0]
    mode_count = len(strong_modes)
    multimodal_bonus = 0.0
    if mode_count == 2:
        multimodal_bonus = 5.0
    elif mode_count >= 3:
        multimodal_bonus = 8.0
    
    return base_score, multimodal_bonus


def calibrate_curve(research_data: List[Dict], test_locations: Dict) -> Dict:
    """
    Calibrate scoring curve to minimize error vs target scores.
    
    Returns:
        Dict with calibrated breakpoints and error metrics
    """
    # Collect data points: (route_ratio, target_score, location)
    data_points = []
    
    # Use test locations with actual route counts
    for location_name, test_data in test_locations.items():
        area_type = test_data.get("area_type", "urban_core")
        target = test_data.get("target")
        
        if not target:
            continue
        
        expected = get_expected_values(area_type)
        
        # Calculate ratios from actual route counts
        ratios = {}
        if expected["heavy_rail"] > 0:
            ratios["heavy_rail"] = test_data.get("heavy_rail", 0) / float(expected["heavy_rail"])
        elif test_data.get("heavy_rail", 0) > 0:
            ratios["heavy_rail"] = 5.0  # Has routes but none expected - treat as high ratio
        else:
            ratios["heavy_rail"] = 0.0
        
        if expected["light_rail"] > 0:
            ratios["light_rail"] = test_data.get("light_rail", 0) / float(expected["light_rail"])
        elif test_data.get("light_rail", 0) > 0:
            ratios["light_rail"] = 5.0  # Has routes but none expected
        else:
            ratios["light_rail"] = 0.0
        
        if expected["bus"] > 0:
            ratios["bus"] = test_data.get("bus", 0) / float(expected["bus"])
        elif test_data.get("bus", 0) > 0:
            ratios["bus"] = 5.0  # Has routes but none expected
        else:
            ratios["bus"] = 0.0
        
        # Get best mode ratio (the one that would produce highest score)
        best_ratio = max([r for r in ratios.values() if r > 0], default=0.0)
        
        if best_ratio > 0:
            data_points.append({
                "location": location_name,
                "area_type": area_type,
                "best_ratio": best_ratio,
                "target_score": target,
                "ratios": ratios,
                "route_counts": {
                    "heavy_rail": test_data.get("heavy_rail", 0),
                    "light_rail": test_data.get("light_rail", 0),
                    "bus": test_data.get("bus", 0),
                },
                "expected": expected,
            })
    
    print(f"\n📊 Calibrating curve with {len(data_points)} locations with target scores:")
    for dp in data_points:
        route_counts = dp.get('route_counts', {})
        expected = dp.get('expected', {})
        print(f"   {dp['location']}:")
        print(f"      Routes: H={route_counts.get('heavy_rail', 0)}, L={route_counts.get('light_rail', 0)}, B={route_counts.get('bus', 0)}")
        print(f"      Expected: H={expected.get('heavy_rail', 0)}, L={expected.get('light_rail', 0)}, B={expected.get('bus', 0)}")
        print(f"      Best ratio={dp['best_ratio']:.2f}, target={dp['target_score']}")
    
    # Try different curve configurations
    best_config = None
    best_error = float('inf')
    
    # Test piecewise curves with different breakpoints
    test_configs = [
        # Conservative: lower scores at each breakpoint
        {
            'at_expected': 50.0, 'ratio_expected': 1.0,
            'at_good': 70.0, 'ratio_good': 1.5,
            'at_excellent': 85.0, 'ratio_excellent': 2.5,
            'at_exceptional': 95.0, 'ratio_exceptional': 4.0,
        },
        # Moderate: current-like but adjusted
        {
            'at_expected': 55.0, 'ratio_expected': 1.0,
            'at_good': 75.0, 'ratio_good': 1.8,
            'at_excellent': 88.0, 'ratio_excellent': 2.8,
            'at_exceptional': 95.0, 'ratio_exceptional': 4.5,
        },
        # Aggressive: higher scores
        {
            'at_expected': 60.0, 'ratio_expected': 1.0,
            'at_good': 80.0, 'ratio_good': 2.0,
            'at_excellent': 90.0, 'ratio_excellent': 3.0,
            'at_exceptional': 95.0, 'ratio_exceptional': 5.0,
        },
    ]
    
    for config in test_configs:
        errors = []
        for dp in data_points:
            base_score, multimodal_bonus = find_best_mode_score(dp['ratios'], piecewise_curve, breakpoints=config, max_score=95.0)
            predicted = min(100.0, base_score + multimodal_bonus)
            error = abs(predicted - dp['target_score'])
            errors.append(error)
        
        avg_error = statistics.mean(errors)
        max_error = max(errors)
        rmse = math.sqrt(statistics.mean([e**2 for e in errors]))
        
        print(f"\n   Config: {config}")
        print(f"   Avg error: {avg_error:.1f}, Max error: {max_error:.1f}, RMSE: {rmse:.1f}")
        
        if avg_error < best_error:
            best_error = avg_error
            best_config = config.copy()
            best_config['avg_error'] = avg_error
            best_config['max_error'] = max_error
            best_config['rmse'] = rmse
    
    # Also test sigmoid curves
    print(f"\n📈 Testing sigmoid curves...")
    for k in [1.5, 2.0, 2.5, 3.0]:
        for midpoint in [1.0, 1.5, 2.0]:
            errors = []
            for dp in data_points:
                base_score, multimodal_bonus = find_best_mode_score(dp['ratios'], sigmoid_curve, k=k, midpoint=midpoint, max_score=95.0)
                predicted = min(100.0, base_score + multimodal_bonus)
                error = abs(predicted - dp['target_score'])
                errors.append(error)
            
            avg_error = statistics.mean(errors)
            if avg_error < best_error:
                best_error = avg_error
                best_config = {
                    'type': 'sigmoid',
                    'k': k,
                    'midpoint': midpoint,
                    'avg_error': avg_error,
                    'max_error': max(errors),
                    'rmse': math.sqrt(statistics.mean([e**2 for e in errors])),
                }
                print(f"   Sigmoid k={k}, midpoint={midpoint}: avg_error={avg_error:.1f}")
    
    return best_config


def main():
    """Main calibration process."""
    print("🔬 Transit Scoring Curve Calibration")
    print("=" * 60)
    
    # Load research data
    research_data = load_research_data()
    print(f"\n✅ Loaded {len(research_data)} research locations")
    
    # Calibrate curve
    best_config = calibrate_curve(research_data, TEST_LOCATIONS)
    
    print(f"\n🎯 Best Configuration:")
    print(json.dumps(best_config, indent=2))
    
    # Validate against all research data
    print(f"\n📊 Validating against all research data...")
    all_errors = []
    for location_data in research_data:
        location_name = location_data.get("location", "")
        area_type = location_data.get("area_type", "unknown")
        expected = get_expected_values(area_type)
        ratios = calculate_route_ratios(location_data, expected)
        
        # Calculate predicted score
        if best_config.get('type') == 'sigmoid':
            base_score, multimodal_bonus = find_best_mode_score(
                ratios, sigmoid_curve,
                k=best_config['k'],
                midpoint=best_config['midpoint'],
                max_score=95.0
            )
            predicted = min(100.0, base_score + multimodal_bonus)
        else:
            base_score, multimodal_bonus = find_best_mode_score(
                ratios, piecewise_curve,
                breakpoints=best_config,
                max_score=95.0
            )
            predicted = min(100.0, base_score + multimodal_bonus)
        
        # Get actual score from research
        actual = location_data.get("transit", {}).get("transit_score")
        if actual:
            error = abs(predicted - actual)
            all_errors.append(error)
            if error > 10:  # Flag large errors
                print(f"   ⚠️  {location_name}: predicted={predicted:.1f}, actual={actual:.1f}, error={error:.1f}")
    
    if all_errors:
        print(f"\n✅ Validation complete:")
        print(f"   Mean error: {statistics.mean(all_errors):.1f}")
        print(f"   Median error: {statistics.median(all_errors):.1f}")
        print(f"   Max error: {max(all_errors):.1f}")
    
    # Save calibrated configuration
    output_path = Path(__file__).parent.parent / "analysis" / "transit_curve_calibration.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w') as f:
        json.dump({
        "calibrated_config": best_config,
        "test_locations": TEST_LOCATIONS,
            "validation_metrics": {
                "mean_error": statistics.mean(all_errors) if all_errors else None,
                "median_error": statistics.median(all_errors) if all_errors else None,
                "max_error": max(all_errors) if all_errors else None,
            }
        }, f, indent=2)
    
    print(f"\n💾 Saved calibration to {output_path}")


if __name__ == "__main__":
    main()

