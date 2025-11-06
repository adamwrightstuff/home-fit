#!/usr/bin/env python3
"""
Test beauty scoring for specific neighborhoods with new area-type-specific weights.
"""

import requests
import json

BASE_URL = "http://localhost:8000"

neighborhoods = [
    "Larchmont, NY",
    "Savannah, GA",
    "Beverly Hills, CA",
    "Carmel-By-The-Sea, CA",
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
            print(response.text)
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
        
        # Get validation metadata
        beauty_valid = arch_details.get("beauty_valid", True)
        data_warning = arch_details.get("data_warning")
        confidence_0_1 = arch_details.get("confidence_0_1", 1.0)
        
        # Get metrics
        metrics = arch_details.get("metrics", {})
        height_diversity = metrics.get("height_diversity", 0)
        type_diversity = metrics.get("type_diversity", 0)
        footprint_variation = metrics.get("footprint_variation", 0)
        built_coverage = metrics.get("built_coverage_ratio", 0)
        
        # Get historic context
        historic_context = arch_details.get("historic_context", {})
        median_year_built = historic_context.get("median_year_built")
        
        print(f"\n📊 Classification: {classification}")
        print(f"   Effective area type: {effective_area_type}")
        print(f"\n✨ Beauty Score: {beauty_score:.1f}/100")
        print(f"   Trees: {tree_score:.1f}/50")
        print(f"   Architecture: {arch_score:.1f}/50")
        print(f"   Enhancer Bonus: {enhancer_bonus:.1f}")
        
        print(f"\n🏗️  Architectural Metrics:")
        print(f"   Height diversity: {height_diversity:.1f}")
        print(f"   Type diversity: {type_diversity:.1f}")
        print(f"   Footprint variation: {footprint_variation:.1f}")
        print(f"   Built coverage: {built_coverage:.1%}")
        print(f"   Median year built: {median_year_built}")
        
        print(f"\n✅ Validation:")
        print(f"   Beauty valid: {beauty_valid}")
        if data_warning:
            print(f"   ⚠️  Data warning: {data_warning}")
        print(f"   Confidence: {confidence_0_1:.2f}")
        
        if has_arch_error:
            print(f"\n   ⚠️  Architecture error: {arch_details.get('error', 'Unknown')}")
        
        return {
            "location": location,
            "classification": classification,
            "effective_area_type": effective_area_type,
            "beauty_score": beauty_score,
            "tree_score": tree_score,
            "arch_score": arch_score,
            "beauty_valid": beauty_valid,
            "data_warning": data_warning,
            "confidence_0_1": confidence_0_1,
            "height_diversity": height_diversity,
            "type_diversity": type_diversity,
            "footprint_variation": footprint_variation,
            "built_coverage": built_coverage,
            "median_year_built": median_year_built
        }
        
    except requests.exceptions.Timeout:
        print(f"⏱️  Timeout")
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    print("🎨 Testing Beauty Scores with Area-Type-Specific Weights")
    print("="*70)
    
    results = []
    for neighborhood in neighborhoods:
        result = test_neighborhood(neighborhood)
        if result:
            results.append(result)
    
    print(f"\n{'='*70}")
    print("📊 Summary")
    print('='*70)
    print(f"\n{'Location':<25} {'Class':<15} {'Beauty':<8} {'Trees':<8} {'Arch':<8} {'Valid':<6} {'Coverage':<10}")
    print("-"*70)
    for r in results:
        valid_mark = "✓" if r['beauty_valid'] else "✗"
        print(f"{r['location']:<25} {r['effective_area_type']:<15} {r['beauty_score']:<8.1f} {r['tree_score']:<8.1f} {r['arch_score']:<8.1f} {valid_mark:<6} {r['built_coverage']:<10.1%}")
    print('='*70)

