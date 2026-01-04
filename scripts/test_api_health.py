#!/usr/bin/env python3
"""
Quick API health check script to verify the API is working and check calibration status
"""
import requests
import json
import sys

def test_api_health(base_url="http://localhost:8000"):
    """Test API endpoints and check calibration status"""
    
    print("=" * 80)
    print("API HEALTH CHECK")
    print("=" * 80)
    
    # Test 1: Root endpoint
    print("\n1. Testing root endpoint...")
    try:
        response = requests.get(f"{base_url}/", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Root endpoint working")
            print(f"   Service: {data.get('service')}")
            print(f"   Status: {data.get('status')}")
            print(f"   Version: {data.get('version')}")
        else:
            print(f"   ❌ Root endpoint returned status {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print(f"   ❌ Cannot connect to {base_url}")
        print(f"   Make sure the API server is running: uvicorn main:app --reload")
        return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False
    
    # Test 2: Health endpoint
    print("\n2. Testing health endpoint...")
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Health endpoint working")
            print(f"   Status: {data.get('status')}")
            checks = data.get('checks', {})
            for check_name, check_status in checks.items():
                print(f"   {check_name}: {check_status}")
        else:
            print(f"   ⚠️  Health endpoint returned status {response.status_code}")
    except Exception as e:
        print(f"   ⚠️  Health check error: {e}")
    
    # Test 3: Score endpoint with a simple location
    print("\n3. Testing score endpoint...")
    test_location = "Downtown Detroit MI"
    try:
        response = requests.get(
            f"{base_url}/score",
            params={"location": test_location, "enable_schools": "false"},
            timeout=120  # Longer timeout for scoring
        )
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Score endpoint working")
            print(f"   Test location: {test_location}")
            print(f"   Total Score: {data.get('total_score', 'N/A')}")
            print(f"   API Version: {data.get('version', 'N/A')}")
            
            # Check calibration status for active_outdoors
            print("\n4. Checking calibration status...")
            if 'pillars' in data and 'active_outdoors' in data['pillars']:
                ao = data['pillars']['active_outdoors']
                ao_score = ao.get('score', 'N/A')
                print(f"   Active Outdoors Score: {ao_score}")
                
                cal = ao.get('calibration', {})
                cal_a = cal.get('cal_a')
                cal_b = cal.get('cal_b')
                cal_note = cal.get('note', 'N/A')
                
                print(f"   Calibration cal_a: {cal_a}")
                print(f"   Calibration cal_b: {cal_b}")
                print(f"   Calibration note: {cal_note}")
                
                if cal_a is None and cal_b is None:
                    print("\n   ⚠️  CALIBRATION STATUS: Calibration has been removed")
                    print("   The API is using pure data-backed scoring (no calibration parameters)")
                else:
                    print("\n   ✅ Calibration parameters are present")
                    print(f"   cal_a={cal_a}, cal_b={cal_b}")
            
            # Show all pillar scores
            print("\n5. All pillar scores:")
            if 'pillars' in data:
                for pillar_name, pillar_data in data['pillars'].items():
                    if isinstance(pillar_data, dict) and 'score' in pillar_data:
                        score = pillar_data['score']
                        print(f"   {pillar_name}: {score}/100")
            
            return True
        else:
            print(f"   ❌ Score endpoint returned status {response.status_code}")
            print(f"   Response: {response.text[:500]}")
            return False
    except requests.exceptions.Timeout:
        print(f"   ⚠️  Score request timed out (this might be normal for first request)")
        return False
    except Exception as e:
        print(f"   ❌ Error testing score endpoint: {e}")
        return False
    
    return True

if __name__ == "__main__":
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
    success = test_api_health(base_url)
    
    print("\n" + "=" * 80)
    if success:
        print("✅ API HEALTH CHECK PASSED")
    else:
        print("❌ API HEALTH CHECK FAILED")
        print("\nIf the API isn't running, start it with:")
        print("  uvicorn main:app --reload --host 0.0.0.0 --port 8000")
    print("=" * 80)
    
    sys.exit(0 if success else 1)

