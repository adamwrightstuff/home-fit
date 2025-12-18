#!/usr/bin/env python3
"""
Test script to verify natural beauty score fix - check that scores are differentiated
and not all clustering around 98.6.
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pillars.natural_beauty import calculate_natural_beauty

# Test locations
test_locations = [
    "Park Slope Brooklyn NY",
    "Hermosa Beach CA",
    "Hudson OH",
    "Georgetown Washington DC",
    "Fairlawn OH",
    "Fitler Square Philadelphia PA",
    "Bronxville NY",
    "Larchmont NY",
    "Carroll Gardens Brooklyn NY",
    "Manhattan Beach CA",
    "Redondo Beach CA",
]

def geocode_location(location_str):
    """Simple geocoding - returns (lat, lon, city) tuple"""
    from data_sources.geocoding import geocode
    result = geocode(location_str)
    if result:
        # geocode returns (lat, lon, city, state, country)
        return result[0], result[1], result[2]
    return None, None, None

def main():
    print("Testing Natural Beauty Score Fix")
    print("=" * 80)
    print(f"{'Location':<40} {'Score':<10} {'Tanh':<10} {'Linear':<10} {'Tree':<10} {'Context':<10}")
    print("-" * 80)
    
    results = []
    
    for location in test_locations:
        lat, lon, city = geocode_location(location)
        if lat is None or lon is None:
            print(f"{location:<40} {'ERROR':<10} {'Geocoding failed':<50}")
            continue
        
        try:
            result = calculate_natural_beauty(
                lat=lat,
                lon=lon,
                city=city,
                location_name=location
            )
            
            score = result.get("score", 0.0)
            linear_score = result.get("score_before_normalization", 0.0)
            tree_score = result.get("tree_score_0_50", 0.0)
            context_bonus = result.get("context_bonus_raw", 0.0)
            
            # Get actual linear prediction before tanh
            ridge_meta = result.get("details", {}).get("ridge_regression", {})
            linear_pred = ridge_meta.get("linear_prediction", linear_score)
            
            results.append({
                "location": location,
                "score": score,
                "linear": linear_score,
                "linear_pred": linear_pred,
                "tree": tree_score,
                "context": context_bonus
            })
            
            print(f"{location:<40} {score:<10.2f} {linear_score:<10.2f} {linear_pred:<10.2f} {tree_score:<10.2f} {context_bonus:<10.2f}")
            
        except Exception as e:
            print(f"{location:<40} {'ERROR':<10} {str(e):<50}")
    
    print("-" * 80)
    print("\nSummary:")
    if results:
        scores = [r["score"] for r in results]
        print(f"  Score range: {min(scores):.2f} - {max(scores):.2f}")
        print(f"  Score mean: {sum(scores)/len(scores):.2f}")
        print(f"  Score std dev: {(sum((s - sum(scores)/len(scores))**2 for s in scores) / len(scores))**0.5:.2f}")
        
        # Check for clustering around 98.6
        near_986 = [s for s in scores if abs(s - 98.6) < 1.0]
        print(f"  Scores near 98.6 (±1.0): {len(near_986)}/{len(scores)} ({100*len(near_986)/len(scores):.1f}%)")
        
        # Show unique scores
        unique_scores = sorted(set(round(s, 1) for s in scores))
        print(f"  Unique score values: {len(unique_scores)}")
        if len(unique_scores) <= 10:
            print(f"    Values: {unique_scores}")

if __name__ == "__main__":
    main()
