#!/usr/bin/env python3
"""
Test script to verify new Built Beauty scoring methodology.
Tests specific locations to compare with LLM targets.
"""

import requests
import json
from typing import Dict, List

# Test locations
TEST_LOCATIONS = [
    "Old Town Alexandria VA",
    "Downtown Charleston SC",
    "Carmel-by-the-Sea CA",
    "Telluride CO",
    "Durham NC Downtown",
    "Montclair NJ",
    "Irvine CA",
    "Fitler Square Philadelphia PA"
]

# LLM target scores (from user's data)
LLM_TARGETS = {
    "Old Town Alexandria VA": 85,
    "Downtown Charleston SC": 91,
    "Carmel-by-the-Sea CA": 89,
    "Telluride CO": 80,
    "Durham NC Downtown": 73,
    "Montclair NJ": 79,
    "Irvine CA": 48,
    "Fitler Square Philadelphia PA": 78
}

def test_location(location: str) -> Dict:
    """Test a single location and return Built Beauty score."""
    try:
        url = "http://localhost:8000/score"
        params = {
            "location": location,
            "diagnostics": True
        }
        
        response = requests.get(url, params=params, timeout=60)
        response.raise_for_status()
        data = response.json()
        
        built_beauty = data.get("livability_pillars", {}).get("built_beauty", {})
        score = built_beauty.get("score", 0)
        component = built_beauty.get("details", {}).get("component_score_0_50", 0)
        enhancer = built_beauty.get("details", {}).get("enhancer_bonus_scaled", 0)
        
        # Get detailed breakdown
        arch_details = built_beauty.get("details", {}).get("architectural_analysis", {})
        confidence = arch_details.get("confidence_0_1", 0)
        coverage = arch_details.get("metrics", {}).get("built_coverage_ratio", 0)
        effective_type = arch_details.get("classification", {}).get("effective_area_type", "unknown")
        
        # Get bonus breakdown
        bonus_breakdown = arch_details.get("bonus_breakdown", {})
        
        # Get data quality info
        data_quality = arch_details.get("data_quality", {}) or built_beauty.get("details", {}).get("data_quality", {})
        degradation = data_quality.get("degradation_applied", False)
        degradation_factor = data_quality.get("degradation_factor", 1.0)
        
        return {
            "location": location,
            "score": score,
            "component": component,
            "enhancer": enhancer,
            "confidence": confidence,
            "coverage": coverage,
            "effective_type": effective_type,
            "degradation_applied": degradation,
            "degradation_factor": degradation_factor,
            "bonus_breakdown": bonus_breakdown,
            "target": LLM_TARGETS.get(location, None),
            "gap": score - LLM_TARGETS.get(location, score) if location in LLM_TARGETS else None
        }
    except Exception as e:
        return {
            "location": location,
            "error": str(e),
            "score": None
        }

def main():
    """Run tests for all locations."""
    print("=" * 80)
    print("Testing New Built Beauty Scoring Methodology")
    print("=" * 80)
    print()
    
    results = []
    for location in TEST_LOCATIONS:
        print(f"Testing: {location}...")
        result = test_location(location)
        results.append(result)
        if "error" not in result:
            print(f"  Score: {result['score']:.1f} | Component: {result['component']:.1f} | Enhancer: {result['enhancer']:.1f}")
            if result.get("target"):
                gap = result.get("gap", 0)
                print(f"  Target: {result['target']} | Gap: {gap:+.1f}")
        else:
            print(f"  ERROR: {result['error']}")
        print()
    
    # Summary table
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"{'Location':<35} {'Score':<8} {'Target':<8} {'Gap':<8} {'Type':<20}")
    print("-" * 80)
    
    for result in results:
        if "error" not in result:
            location = result["location"]
            score = result["score"]
            target = result.get("target", "N/A")
            gap = result.get("gap", "N/A")
            area_type = result.get("effective_type", "unknown")
            
            gap_str = f"{gap:+.1f}" if isinstance(gap, (int, float)) else str(gap)
            target_str = str(target) if target else "N/A"
            
            print(f"{location:<35} {score:>7.1f} {target_str:>7} {gap_str:>7} {area_type:<20}")
        else:
            print(f"{result['location']:<35} ERROR: {result['error']}")
    
    print()
    print("=" * 80)
    print("DETAILED BREAKDOWN")
    print("=" * 80)
    
    for result in results:
        if "error" not in result:
            print(f"\n{result['location']}:")
            print(f"  Built Beauty Score: {result['score']:.1f}")
            print(f"  Component (0-50): {result['component']:.1f}")
            print(f"  Enhancer Bonus: {result['enhancer']:.1f}")
            print(f"  Effective Area Type: {result['effective_type']}")
            print(f"  Coverage Ratio: {result['coverage']:.3f}")
            print(f"  Confidence: {result['confidence']:.3f}")
            print(f"  Degradation Applied: {result['degradation_applied']}")
            if result['degradation_applied']:
                print(f"  Degradation Factor: {result['degradation_factor']:.3f}")
            
            bonus = result.get("bonus_breakdown", {})
            if bonus:
                print(f"  Bonuses:")
                for key, value in bonus.items():
                    if value and value != 0:
                        print(f"    {key}: {value:.2f}")
            
            if result.get("target"):
                print(f"  LLM Target: {result['target']}")
                print(f"  Gap: {result.get('gap', 0):+.1f}")

if __name__ == "__main__":
    main()


