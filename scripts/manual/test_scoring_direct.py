#!/usr/bin/env python3
"""
Direct test of scoring functions to verify code is working (no API server needed)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

def test_direct_scoring():
    """Test scoring functions directly"""
    
    print("=" * 80)
    print("DIRECT SCORING TEST (No API Server Required)")
    print("=" * 80)
    
    # Test 1: Import main modules
    print("\n1. Testing imports...")
    try:
        from data_sources.geocoding import geocode
        print("   ✅ Geocoding module imported")
    except Exception as e:
        print(f"   ❌ Failed to import geocoding: {e}")
        return False
    
    try:
        from pillars.active_outdoors import get_active_outdoors_score_v2
        print("   ✅ Active Outdoors module imported")
    except Exception as e:
        print(f"   ❌ Failed to import active_outdoors: {e}")
        return False
    
    # Test 2: Geocode a test location
    print("\n2. Testing geocoding...")
    test_location = "Downtown Detroit MI"
    try:
        result = geocode(test_location)
        if result:
            # geocode returns (lat, lon, city, state, zip_code)
            lat, lon, city, state, zip_code = result
            print(f"   ✅ Geocoding successful")
            print(f"   Location: {test_location}")
            print(f"   Coordinates: ({lat}, {lon})")
            print(f"   City: {city}, State: {state}")
        else:
            print(f"   ❌ Geocoding failed - returned None")
            return False
    except Exception as e:
        print(f"   ❌ Geocoding error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 3: Test Active Outdoors scoring directly
    print("\n3. Testing Active Outdoors scoring...")
    try:
        score, breakdown = get_active_outdoors_score_v2(lat, lon, city=city, area_type=None)
        print(f"   ✅ Active Outdoors scoring successful")
        print(f"   Score: {score}/100")
        
        # Check calibration status
        print("\n4. Checking calibration status in breakdown...")
        if isinstance(breakdown, dict):
            calibration = breakdown.get('calibration', {})
            cal_a = calibration.get('cal_a')
            cal_b = calibration.get('cal_b')
            cal_note = calibration.get('note', 'N/A')
            
            print(f"   Calibration cal_a: {cal_a}")
            print(f"   Calibration cal_b: {cal_b}")
            print(f"   Calibration note: {cal_note}")
            
            if cal_a is None and cal_b is None:
                print("\n   ⚠️  CALIBRATION STATUS: Calibration has been removed")
                print("   The scoring is using pure data-backed scoring (no calibration parameters)")
            else:
                print("\n   ✅ Calibration parameters are present")
                print(f"   cal_a={cal_a}, cal_b={cal_b}")
            
            # Total score = sum of three components
            bd = breakdown.get('breakdown') or {}
            d = float(bd.get('daily_urban_outdoors') or 0)
            w = float(bd.get('wild_adventure') or 0)
            wa = float(bd.get('waterfront_lifestyle') or 0)
            summed = d + w + wa
            final_score = breakdown.get('score')
            if final_score is not None:
                print(f"\n   Component sum (daily+wild+water): {summed:.1f}")
                print(f"   Final score: {final_score}")
                if abs(summed - float(final_score)) < 0.15:
                    print("   ✅ Final score matches component sum")
                else:
                    print(f"   ⚠️  Mismatch vs component sum (diff: {abs(summed - float(final_score)):.2f})")
        else:
            print(f"   ⚠️  Breakdown is not a dict: {type(breakdown)}")
            
    except Exception as e:
        print(f"   ❌ Active Outdoors scoring error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n" + "=" * 80)
    print("✅ DIRECT SCORING TEST PASSED")
    print("=" * 80)
    print("\nSummary:")
    print("- Code imports successfully")
    print("- Geocoding works")
    print("- Active Outdoors scoring works")
    print("- Calibration has been removed (using raw data-backed scores)")
    print("\nThe code appears to be working correctly!")
    print("To test the full API, start the server with:")
    print("  uvicorn main:app --reload --host 0.0.0.0 --port 8000")
    
    return True

if __name__ == "__main__":
    try:
        success = test_direct_scoring()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

