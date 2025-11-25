#!/usr/bin/env python3
"""
Calibrate Transit Scoring Parameters

This script analyzes research data to calibrate:
1. Multimodal bonus threshold and amounts
2. Commute weight (currently 10%)
3. Commute time function breakpoints

Methodology:
- Load research data with transit scores, route counts, commute times
- Analyze correlations between parameters and target scores
- Test different parameter values to minimize error vs targets
- Output calibrated parameters
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

# Target scores for known locations (from calibration data and test results)
TARGET_SCORES = {
    "Uptown Charlotte NC": 55,
    "Midtown Atlanta GA": 78,
    "Dupont Circle Washington DC": 90,
    "The Loop Chicago IL": 97,
    "Midtown Manhattan NY": 100,
    "Back Bay Boston MA": 95,
    "Pearl District Portland OR": 87,
    "Koreatown Los Angeles CA": 73,
    "Bronxville NY": 85,
    # Additional locations from transit_curve_calibration.json
    "Times Square NY": 100,  # Urban core, likely similar to Midtown Manhattan
}

# Research data path
RESEARCH_DATA_PATH = Path(__file__).parent.parent / "analysis" / "research_data" / "expected_values_raw_data.json"


def load_research_data() -> List[Dict]:
    """Load research data from JSON file."""
    try:
        with open(RESEARCH_DATA_PATH, 'r') as f:
            data = json.load(f)
        return data.get("raw_data", [])
    except FileNotFoundError:
        print(f"⚠️  Research data not found at {RESEARCH_DATA_PATH}")
        return []


def calculate_mode_scores(route_counts: Dict, expected: Dict, area_type: str) -> Tuple[float, float, float]:
    """
    Calculate mode scores using current scoring logic.
    Returns (heavy_score, light_score, bus_score)
    """
    def normalize_route_count(count: int, expected_val: Optional[int]) -> float:
        """Current scoring logic."""
        if count <= 0:
            return 0.0
        
        # Unexpected modes (expected <= 0)
        if not expected_val or expected_val <= 0:
            if count == 1:
                return 25.0
            elif count == 2:
                return 35.0
            elif count == 3:
                return 42.0
            elif count >= 4:
                return min(50.0, 42.0 + (count - 3) * 2.0)
            return 0.0
        
        # Expected modes
        ratio = count / float(expected_val)
        if ratio <= 0.1:
            return 0.0
        if ratio < 1.0:
            return 60.0 * ratio
        if ratio < 2.0:
            return 60.0 + (ratio - 1.0) * 20.0
        if ratio < 3.0:
            return 80.0 + (ratio - 2.0) * 10.0
        if ratio < 5.0:
            return 90.0 + (ratio - 3.0) * 2.5
        return 95.0
    
    heavy_score = normalize_route_count(route_counts.get("heavy_rail_routes", 0), expected.get("expected_heavy_rail_routes"))
    light_score = normalize_route_count(route_counts.get("light_rail_routes", 0), expected.get("expected_light_rail_routes"))
    bus_score = normalize_route_count(route_counts.get("bus_routes", 0), expected.get("expected_bus_routes"))
    
    return heavy_score, light_score, bus_score


def test_multimodal_bonus(data_points: List[Dict], threshold: float, bonus_2: float, bonus_3: float) -> float:
    """Test multimodal bonus parameters and return average error."""
    from data_sources.regional_baselines import get_contextual_expectations
    
    errors = []
    for dp in data_points:
        location = dp.get("location", "")
        if location not in TARGET_SCORES:
            continue
        
        target = TARGET_SCORES[location]
        area_type = dp.get("area_type", "unknown")
        transit_data = dp.get("transit", {})
        
        if not transit_data:
            continue
        
        # Get expected values
        expected = get_contextual_expectations(area_type, "public_transit_access") or {}
        
        # Calculate mode scores
        route_counts = {
            "heavy_rail_routes": transit_data.get("heavy_rail_routes", 0),
            "light_rail_routes": transit_data.get("light_rail_routes", 0),
            "bus_routes": transit_data.get("bus_routes", 0),
        }
        
        heavy_score, light_score, bus_score = calculate_mode_scores(route_counts, expected, area_type)
        
        # Calculate multimodal bonus
        mode_scores = [heavy_score, light_score, bus_score]
        strong_modes = [s for s in mode_scores if s >= threshold]
        mode_count = len(strong_modes)
        
        multimodal_bonus = 0.0
        if mode_count == 2:
            multimodal_bonus = bonus_2
        elif mode_count >= 3:
            multimodal_bonus = bonus_3
        
        # Base score (without commute weight for now)
        base_supply = max(heavy_score, light_score, bus_score)
        total_score = min(100.0, base_supply + multimodal_bonus)
        
        error = abs(total_score - target)
        errors.append(error)
    
    return statistics.mean(errors) if errors else float('inf')


def test_commute_weight(data_points: List[Dict], weight: float) -> float:
    """Test commute weight and return average error."""
    from data_sources.regional_baselines import get_contextual_expectations
    
    errors = []
    for dp in data_points:
        location = dp.get("location", "")
        if location not in TARGET_SCORES:
            continue
        
        target = TARGET_SCORES[location]
        area_type = dp.get("area_type", "unknown")
        transit_data = dp.get("transit", {})
        
        if not transit_data:
            continue
        
        # Get expected values
        expected = get_contextual_expectations(area_type, "public_transit_access") or {}
        
        # Calculate mode scores
        # Note: Research data uses "heavy_rail_stops" but these are actually route counts
        route_counts = {
            "heavy_rail_routes": transit_data.get("heavy_rail_routes") or transit_data.get("heavy_rail_stops", 0),
            "light_rail_routes": transit_data.get("light_rail_routes") or transit_data.get("light_rail_stops", 0),
            "bus_routes": transit_data.get("bus_routes") or transit_data.get("bus_stops", 0),
        }
        
        heavy_score, light_score, bus_score = calculate_mode_scores(route_counts, expected, area_type)
        
        # Base score with multimodal bonus (using current values: 30.0 threshold, 5.0/8.0 bonuses)
        mode_scores = [heavy_score, light_score, bus_score]
        strong_modes = [s for s in mode_scores if s >= 30.0]
        mode_count = len(strong_modes)
        multimodal_bonus = 5.0 if mode_count == 2 else (8.0 if mode_count >= 3 else 0.0)
        base_supply = max(heavy_score, light_score, bus_score)
        transit_score = min(100.0, base_supply + multimodal_bonus)
        
        # Apply commute weight
        commute_minutes = transit_data.get("mean_commute_minutes")
        if commute_minutes and commute_minutes > 0 and commute_minutes < 200:  # Valid commute time
            # Use current commute scoring function (simplified)
            from pillars.public_transit_access import _score_commute_time
            commute_score = _score_commute_time(commute_minutes, area_type)
            total_score = (transit_score * (1.0 - weight)) + (commute_score * weight)
        else:
            total_score = transit_score
        
        error = abs(total_score - target)
        errors.append(error)
    
    return statistics.mean(errors) if errors else float('inf')


def analyze_multimodal_bonus(data_points: List[Dict]):
    """Analyze and calibrate multimodal bonus parameters."""
    print("\n" + "="*60)
    print("CALIBRATING MULTIMODAL BONUS")
    print("="*60)
    
    best_error = float('inf')
    best_params = None
    
    # Test different thresholds and bonus amounts
    thresholds = [20.0, 25.0, 30.0, 35.0, 40.0]
    bonus_2_values = [3.0, 4.0, 5.0, 6.0, 7.0]
    bonus_3_values = [6.0, 7.0, 8.0, 9.0, 10.0]
    
    print("\nTesting parameter combinations...")
    for threshold in thresholds:
        for bonus_2 in bonus_2_values:
            for bonus_3 in bonus_3_values:
                error = test_multimodal_bonus(data_points, threshold, bonus_2, bonus_3)
                if error < best_error:
                    best_error = error
                    best_params = {
                        "threshold": threshold,
                        "bonus_2_modes": bonus_2,
                        "bonus_3_modes": bonus_3,
                        "avg_error": error
                    }
    
    print(f"\n✅ Best parameters:")
    print(f"   Threshold: {best_params['threshold']:.1f} points")
    print(f"   Bonus (2 modes): {best_params['bonus_2_modes']:.1f} points")
    print(f"   Bonus (3+ modes): {best_params['bonus_3_modes']:.1f} points")
    print(f"   Average error: {best_params['avg_error']:.2f} points")
    
    return best_params


def analyze_commute_weight(data_points: List[Dict]):
    """Analyze and calibrate commute weight."""
    print("\n" + "="*60)
    print("CALIBRATING COMMUTE WEIGHT")
    print("="*60)
    
    best_error = float('inf')
    best_weight = None
    
    # Test different weights
    weights = [0.05, 0.10, 0.15, 0.20, 0.25]
    
    print("\nTesting commute weights...")
    for weight in weights:
        error = test_commute_weight(data_points, weight)
        print(f"   Weight {weight:.0%}: avg error = {error:.2f} points")
        if error < best_error:
            best_error = error
            best_weight = weight
    
    print(f"\n✅ Best commute weight: {best_weight:.0%}")
    print(f"   Average error: {best_error:.2f} points")
    
    return {"weight": best_weight, "avg_error": best_error}


def analyze_commute_time_breakpoints(data_points: List[Dict]):
    """Analyze commute time distribution by area type to calibrate breakpoints."""
    print("\n" + "="*60)
    print("ANALYZING COMMUTE TIME DISTRIBUTION")
    print("="*60)
    
    commute_by_area_type = defaultdict(list)
    
    for dp in data_points:
        area_type = dp.get("area_type", "unknown")
        transit_data = dp.get("transit", {})
        commute_minutes = transit_data.get("mean_commute_minutes")
        
        if commute_minutes and commute_minutes > 0 and commute_minutes < 200:  # Valid
            commute_by_area_type[area_type].append(commute_minutes)
    
    print("\nCommute time statistics by area type:")
    for area_type, commutes in commute_by_area_type.items():
        if commutes:
            print(f"\n{area_type} (n={len(commutes)}):")
            print(f"   Median: {statistics.median(commutes):.1f} min")
            print(f"   P25: {sorted(commutes)[len(commutes)//4]:.1f} min")
            print(f"   P75: {sorted(commutes)[3*len(commutes)//4]:.1f} min")
            print(f"   Min: {min(commutes):.1f} min")
            print(f"   Max: {max(commutes):.1f} min")
    
    return commute_by_area_type


def main():
    """Main calibration function."""
    print("🔬 Transit Parameters Calibration")
    print("="*60)
    
    # Load research data
    data_points = load_research_data()
    
    if not data_points:
        print("❌ No research data found. Run research script first:")
        print("   python scripts/research_expected_values.py --pillars transit")
        return
    
    print(f"✅ Loaded {len(data_points)} research data points")
    
    # Filter to locations with target scores
    locations_with_targets = [dp for dp in data_points if dp.get("location") in TARGET_SCORES]
    print(f"✅ {len(locations_with_targets)} locations have target scores")
    
    if len(locations_with_targets) < 3:
        print("⚠️  Need at least 3 locations with target scores for calibration")
        return
    
    # Calibrate multimodal bonus
    multimodal_params = analyze_multimodal_bonus(locations_with_targets)
    
    # Calibrate commute weight
    commute_weight_params = analyze_commute_weight(locations_with_targets)
    
    # Analyze commute time distribution
    commute_distribution = analyze_commute_time_breakpoints(data_points)
    
    # Save results
    output = {
        "multimodal_bonus": multimodal_params,
        "commute_weight": commute_weight_params,
        "commute_time_distribution": {
            area_type: {
                "median": statistics.median(commutes),
                "p25": sorted(commutes)[len(commutes)//4],
                "p75": sorted(commutes)[3*len(commutes)//4],
                "min": min(commutes),
                "max": max(commutes),
                "count": len(commutes)
            }
            for area_type, commutes in commute_distribution.items()
            if commutes
        }
    }
    
    output_file = Path(__file__).parent.parent / "analysis" / "transit_parameters_calibration.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\n✅ Calibration results saved to {output_file}")
    print("\n📋 Next steps:")
    print("   1. Review calibrated parameters")
    print("   2. Update code with calibrated values")
    print("   3. Test against all locations to verify improvements")


if __name__ == "__main__":
    main()

