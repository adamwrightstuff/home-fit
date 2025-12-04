#!/usr/bin/env python3
"""
Test script to verify healthcare access fixes on problematic locations.

Tests the fixes for:
1. Capitol Hill Seattle (PCP + pharmacy = 0)
2. Brickell Miami (primary care = 6.2)
3. Brooklyn Heights (clinic_count = 110)
4. Bar Harbor (pharmacy score = 0 despite pharmacy present)
5. Normal locations to ensure no regressions
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data_sources.geocoding import geocode_with_full_result
from data_sources.data_quality import detect_area_type, detect_location_scope
from data_sources import census_api
from pillars.healthcare_access import get_healthcare_access_score


# Test locations from the original issue list
TEST_LOCATIONS = [
    {
        "name": "Capitol Hill Seattle WA",
        "coords": (47.6238307, -122.318368),
        "issue": "PCP + pharmacy = 0"
    },
    {
        "name": "Brickell Miami FL",
        "coords": (25.7625951, -80.1952987),
        "issue": "Primary care = 6.2 (too low)"
    },
    {
        "name": "Brooklyn Heights Brooklyn NY",
        "coords": (40.6960849, -73.9950297),
        "issue": "Clinic_count = 110 (over-broad query)"
    },
    {
        "name": "Bar Harbor ME",
        "coords": (44.3876378, -68.2043361),
        "issue": "Pharmacy score = 0 despite pharmacy present"
    },
    {
        "name": "Back Bay Boston MA",
        "coords": (42.3507067, -71.0797297),
        "issue": "Control - should work well"
    },
    {
        "name": "Bethesda MD",
        "coords": (38.9846816, -77.0942447),
        "issue": "Control - should work well"
    }
]


def test_location(name: str, lat: float, lon: float, issue: str):
    """Test a single location and return key metrics."""
    print(f"\n{'='*70}")
    print(f"📍 {name}")
    print(f"   Issue: {issue}")
    print(f"   Coordinates: {lat}, {lon}")
    print(f"{'='*70}\n")
    
    # Get area type
    density = census_api.get_population_density(lat, lon) or 0.0
    area_type = detect_area_type(lat, lon, density=density)
    print(f"   Area type: {area_type}")
    
    # Get healthcare score
    score, breakdown = get_healthcare_access_score(
        lat=lat,
        lon=lon,
        area_type=area_type,
        location_scope=None
    )
    
    # Extract key metrics
    breakdown_data = breakdown.get("breakdown", {})
    summary = breakdown.get("summary", {})
    
    hospital_score = breakdown_data.get("hospital_access", 0)
    primary_score = breakdown_data.get("primary_care", 0)
    pharmacy_score = breakdown_data.get("pharmacies", 0)
    
    hospital_count = summary.get("hospital_count", 0)
    urgent_care_count = summary.get("urgent_care_count", 0)
    pharmacy_count = summary.get("pharmacy_count", 0)
    clinic_count = summary.get("clinic_count", 0)
    
    nearest_hospital = summary.get("nearest_hospital", {})
    nearest_pharmacy = summary.get("nearest_pharmacy", {})
    
    print(f"\n📊 Results:")
    print(f"   Total Score: {score:.1f}/100")
    print(f"   Hospital Access: {hospital_score:.1f}/35 ({hospital_count} hospitals)")
    print(f"   Primary Care: {primary_score:.1f}/25 ({clinic_count} clinics)")
    print(f"   Pharmacy: {pharmacy_score:.1f}/15 ({pharmacy_count} pharmacies)")
    print(f"   Urgent Care: {urgent_care_count} facilities")
    
    if nearest_hospital:
        print(f"   Nearest Hospital: {nearest_hospital.get('name', 'Unknown')} ({nearest_hospital.get('distance_km', 0):.1f} km)")
    if nearest_pharmacy:
        print(f"   Nearest Pharmacy: {nearest_pharmacy.get('name', 'Unknown')} ({nearest_pharmacy.get('distance_km', 0):.1f} km)")
    
    # Check for issues
    issues_found = []
    if pharmacy_count > 0 and pharmacy_score == 0:
        issues_found.append("⚠️  Pharmacy count > 0 but score = 0")
    if clinic_count > 100:
        issues_found.append(f"⚠️  Clinic count very high: {clinic_count}")
    if clinic_count == 0 and primary_score == 0 and area_type in ["urban_core", "urban_residential"]:
        issues_found.append("⚠️  No clinics found in urban area")
    if pharmacy_count == 0 and area_type in ["urban_core", "urban_residential", "suburban"]:
        issues_found.append("⚠️  No pharmacies found in urban/suburban area")
    
    if issues_found:
        print(f"\n   Issues detected:")
        for issue in issues_found:
            print(f"   {issue}")
    else:
        print(f"\n   ✅ No obvious issues detected")
    
    return {
        "name": name,
        "score": score,
        "hospital_score": hospital_score,
        "primary_score": primary_score,
        "pharmacy_score": pharmacy_score,
        "hospital_count": hospital_count,
        "clinic_count": clinic_count,
        "pharmacy_count": pharmacy_count,
        "urgent_care_count": urgent_care_count,
        "issues": issues_found
    }


def main():
    """Run tests on all locations."""
    print("🧪 Testing Healthcare Access Fixes")
    print("=" * 70)
    
    results = []
    for loc in TEST_LOCATIONS:
        try:
            result = test_location(
                loc["name"],
                loc["coords"][0],
                loc["coords"][1],
                loc["issue"]
            )
            results.append(result)
        except Exception as e:
            print(f"\n❌ Error testing {loc['name']}: {e}")
            import traceback
            traceback.print_exc()
            results.append({
                "name": loc["name"],
                "error": str(e)
            })
    
    # Summary
    print(f"\n\n{'='*70}")
    print("📋 Summary")
    print(f"{'='*70}\n")
    
    for result in results:
        if "error" in result:
            print(f"❌ {result['name']}: ERROR - {result['error']}")
        else:
            status = "✅" if not result["issues"] else "⚠️"
            print(f"{status} {result['name']}:")
            print(f"   Score: {result['score']:.1f}/100")
            print(f"   Clinics: {result['clinic_count']}, Pharmacies: {result['pharmacy_count']}")
            if result["issues"]:
                for issue in result["issues"]:
                    print(f"   {issue}")
    
    # Specific checks
    print(f"\n🔍 Specific Fix Checks:")
    
    # Check Capitol Hill
    capitol_hill = next((r for r in results if "Capitol Hill" in r.get("name", "")), None)
    if capitol_hill and "error" not in capitol_hill:
        if capitol_hill["pharmacy_count"] > 0 or capitol_hill["clinic_count"] > 0:
            print(f"   ✅ Capitol Hill: Now finding pharmacies/clinics (pharmacy={capitol_hill['pharmacy_count']}, clinic={capitol_hill['clinic_count']})")
        else:
            print(f"   ⚠️  Capitol Hill: Still no pharmacies/clinics found")
    
    # Check Brooklyn Heights
    brooklyn = next((r for r in results if "Brooklyn Heights" in r.get("name", "")), None)
    if brooklyn and "error" not in brooklyn:
        if brooklyn["clinic_count"] < 50:
            print(f"   ✅ Brooklyn Heights: Clinic count reduced to {brooklyn['clinic_count']} (was 110)")
        else:
            print(f"   ⚠️  Brooklyn Heights: Clinic count still high: {brooklyn['clinic_count']}")
    
    # Check Bar Harbor
    bar_harbor = next((r for r in results if "Bar Harbor" in r.get("name", "")), None)
    if bar_harbor and "error" not in bar_harbor:
        if bar_harbor["pharmacy_count"] > 0 and bar_harbor["pharmacy_score"] > 0:
            print(f"   ✅ Bar Harbor: Pharmacy score now > 0 ({bar_harbor['pharmacy_score']:.1f}) with {bar_harbor['pharmacy_count']} pharmacy")
        elif bar_harbor["pharmacy_count"] > 0:
            print(f"   ⚠️  Bar Harbor: Has {bar_harbor['pharmacy_count']} pharmacy but score still 0")
        else:
            print(f"   ⚠️  Bar Harbor: No pharmacies found")
    
    # Check Brickell
    brickell = next((r for r in results if "Brickell" in r.get("name", "")), None)
    if brickell and "error" not in brickell:
        if brickell["primary_score"] > 10:
            print(f"   ✅ Brickell: Primary care score improved to {brickell['primary_score']:.1f} (was 6.2)")
        else:
            print(f"   ⚠️  Brickell: Primary care score still low: {brickell['primary_score']:.1f}")


if __name__ == "__main__":
    main()

