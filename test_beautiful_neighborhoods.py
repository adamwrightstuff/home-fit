#!/usr/bin/env python3
"""
Test beauty scoring for known beautiful neighborhoods.
"""

import requests
import json

BASE_URL = "http://localhost:8000"

neighborhoods = [
    "Bronxville, NY",
    "Larchmont, NY",
    "Georgetown, Washington DC",
    "Old Town Alexandria, VA",
    "Manhattan Beach, CA",
    "Beverly Hills, CA",
    "Redondo Beach, CA",
    "Bel Air, CA",
    "River Oaks, Houston, TX",
    "The Heights, Houston, TX",
    "Buckhead, Atlanta, GA",
    "Inman Park, Atlanta, GA",
    "German Village, Columbus, OH",
    "Greenwich Village, NYC",
    "Brooklyn Heights, NYC",
    "Park Slope, NYC",
    "Queen Anne, Seattle, WA",
    "Charleston Historic District, SC",
]

def test_neighborhood(location: str):
    print(f"\n{'='*70}")
    print(f"Testing: {location}")
    print('='*70)
    
    try:
        response = requests.get(
            f"{BASE_URL}/score",
            params={"location": location, "enable_schools": False},
            timeout=180
        )
        
        if response.status_code != 200:
            print(f"❌ Error: HTTP {response.status_code}")
            return None
        
        data = response.json()
        pillars = data.get("livability_pillars", {})
        
        # Get classification
        area_classification = data.get("data_quality_summary", {}).get("area_classification", {})
        classification = area_classification.get("type", "unknown")
        
        # Get beauty score
        beauty = pillars.get("neighborhood_beauty", {})
        beauty_score = beauty.get("score", 0)
        beauty_breakdown = beauty.get("breakdown", {})
        beauty_details = beauty.get("details", {})
        
        tree_score = beauty_breakdown.get("trees", 0)
        arch_score = beauty_breakdown.get("architectural_beauty", 0)
        enhancer_bonus = beauty_breakdown.get("enhancer_bonus", 0)
        
        # Get architectural details
        arch_details = beauty_details.get("architectural_analysis", {})
        has_arch_error = "error" in arch_details
        effective_area_type = arch_details.get("classification", {}).get("effective_area_type", "N/A")
        
        # Get tree details
        tree_details = beauty_details.get("tree_analysis", {})
        tree_canopy = tree_details.get("gee_canopy_pct", 0)
        
        print(f"\n📊 Classification: {classification}")
        print(f"✨ Beauty Score: {beauty_score:.1f}/100")
        print(f"   Trees: {tree_score:.1f}/50")
        print(f"   Architecture: {arch_score:.1f}/50")
        print(f"   Enhancer Bonus: {enhancer_bonus:.1f}")
        
        if has_arch_error:
            print(f"   ⚠️  Architecture error: {arch_details.get('error', 'Unknown')}")
        else:
            print(f"   Effective area type: {effective_area_type}")
            metrics = arch_details.get("metrics", {})
            if metrics:
                print(f"   Height diversity: {metrics.get('height_diversity', 0):.1f}")
                print(f"   Type diversity: {metrics.get('type_diversity', 0):.1f}")
                print(f"   Footprint variation: {metrics.get('footprint_variation', 0):.1f}")
        
        print(f"   Tree canopy: {tree_canopy:.2f}%")
        
        return {
            "location": location,
            "classification": classification,
            "beauty_score": beauty_score,
            "tree_score": tree_score,
            "arch_score": arch_score,
            "has_arch_error": has_arch_error,
            "effective_area_type": effective_area_type,
            "tree_canopy": tree_canopy
        }
        
    except requests.exceptions.Timeout:
        print(f"⏱️  Timeout")
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

if __name__ == "__main__":
    print("🎨 Testing Beauty Scores for Known Beautiful Neighborhoods")
    print("="*70)
    
    results = []
    for neighborhood in neighborhoods:
        result = test_neighborhood(neighborhood)
        if result:
            results.append(result)
    
    print(f"\n{'='*70}")
    print("📊 Summary")
    print('='*70)
    print(f"\n{'Location':<35} {'Class':<12} {'Beauty':<8} {'Trees':<8} {'Arch':<8} {'Error':<6}")
    print("-"*70)
    for r in results:
        error_mark = "⚠️" if r['has_arch_error'] else ""
        print(f"{r['location']:<35} {r['classification']:<12} {r['beauty_score']:<8.1f} {r['tree_score']:<8.1f} {r['arch_score']:<8.1f} {error_mark:<6}")
    print('='*70)
    
    # Analyze patterns
    print(f"\n📈 Analysis:")
    print(f"   Average beauty score: {sum(r['beauty_score'] for r in results) / len(results):.1f}")
    print(f"   Locations with arch errors: {sum(1 for r in results if r['has_arch_error'])}")
    print(f"   Locations scoring <50: {[r['location'] for r in results if r['beauty_score'] < 50]}")
    print(f"   Locations scoring >80: {[r['location'] for r in results if r['beauty_score'] > 80]}")

