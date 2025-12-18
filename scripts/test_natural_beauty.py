#!/usr/bin/env python3
"""
Test natural beauty scoring for a specific location.
"""

import json
import os
import sys
import requests
from typing import Dict, Optional

# API configuration from environment variables
HOMEFIT_BASE_URL = os.getenv("HOMEFIT_BASE_URL", "http://localhost:8000").strip()
HOMEFIT_API_KEY = os.getenv("HOMEFIT_API_KEY", None)


def test_location(location: str) -> Optional[Dict]:
    """Test a location and return the API response."""
    base_url = HOMEFIT_BASE_URL.rstrip('/')
    url = f"{base_url}/score"
    
    params = {
        "location": location,
        "enable_schools": "false"
    }
    
    headers = {}
    if HOMEFIT_API_KEY:
        headers["Authorization"] = f"Bearer {HOMEFIT_API_KEY}"
    
    try:
        print(f"Calling API for: {location}")
        print(f"URL: {url}")
        print()
        
        response = requests.get(url, params=params, headers=headers, timeout=300)
        
        if response.status_code != 200:
            print(f"ERROR: API returned status {response.status_code}")
            print(f"Response: {response.text[:500]}")
            return None
        
        return response.json()
    except Exception as e:
        print(f"ERROR: {e}")
        return None


def print_natural_beauty_breakdown(data: Dict):
    """Print natural beauty breakdown from API response."""
    pillars = data.get("livability_pillars", {})
    nb = pillars.get("natural_beauty", {})
    
    if not nb:
        print("❌ Natural beauty data not found in response")
        return
    
    print("=" * 80)
    print("Natural Beauty Breakdown")
    print("=" * 80)
    print()
    
    # Overall score
    score = nb.get("score", 0)
    weight = nb.get("weight", 0)
    contribution = nb.get("contribution", 0)
    
    print(f"Score: {score:.2f}/100")
    print(f"Weight: {weight}")
    print(f"Contribution: {contribution:.2f}")
    print()
    
    # Breakdown
    breakdown = nb.get("breakdown", {})
    details = nb.get("details", {})
    
    print("Component Scores:")
    print("-" * 80)
    tree_score = breakdown.get("tree_score_0_50", 0)
    enhancer_bonus_scaled = details.get("enhancer_bonus_scaled", 0)
    
    print(f"Tree Score (0-50): {tree_score:.2f}")
    print(f"Enhancer Bonus Scaled: {enhancer_bonus_scaled:.2f}")
    print()
    
    # Component weights
    component_weights = details.get("component_weights", {})
    if component_weights:
        print("Component Weights (New Formula):")
        print("-" * 80)
        print(f"Tree Weight: {component_weights.get('tree_weight', 0):.2f}")
        print(f"Scenic Weight: {component_weights.get('scenic_weight', 0):.2f}")
        print(f"Tree Max Contribution: {component_weights.get('tree_max_contribution', 0):.2f}")
        print(f"Scenic Max Contribution: {component_weights.get('scenic_max_contribution', 0):.2f}")
        print()
    
    # Raw score calculation
    raw_score = details.get("raw_score", details.get("score_before_normalization", 0))
    
    print("Score Calculation:")
    print("-" * 80)
    print(f"Raw Score: {raw_score:.2f}")
    print(f"Final Score: {score:.2f}")
    print()
    
    # Context bonus breakdown
    context_bonus = details.get("context_bonus", {})
    if context_bonus:
        components = context_bonus.get("component_scores", {})
        if components:
            print("Context Bonus Components:")
            print("-" * 80)
            print(f"Topography: {components.get('topography', 0):.2f}")
            print(f"Landcover: {components.get('landcover', 0):.2f}")
            print(f"Water: {components.get('water', 0):.2f}")
            print(f"Total Context Bonus: {context_bonus.get('total_bonus', 0):.2f}")
            print()
    
    # Tree analysis
    tree_analysis = details.get("tree_analysis", {})
    if tree_analysis:
        print("Tree Analysis:")
        print("-" * 80)
        canopy_pct = tree_analysis.get("gee_canopy_pct", 0)
        street_trees = tree_analysis.get("nyc_street_trees", 0)
        print(f"GEE Canopy %: {canopy_pct:.2f}%")
        if street_trees:
            print(f"NYC Street Trees: {street_trees}")
        print()


if __name__ == "__main__":
    location = sys.argv[1] if len(sys.argv) > 1 else "Park Slope Brooklyn NY"
    
    print("=" * 80)
    print(f"Testing Natural Beauty: {location}")
    print("=" * 80)
    print()
    
    data = test_location(location)
    
    if data:
        print_natural_beauty_breakdown(data)
        
        # Also show total score for context
        total_score = data.get("total_score", 0)
        print("=" * 80)
        print(f"Total Livability Score: {total_score:.2f}/100")
        print("=" * 80)
    else:
        print("Failed to get API response")
        sys.exit(1)
