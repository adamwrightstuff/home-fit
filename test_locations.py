#!/usr/bin/env python3
"""
Test script to run live scores on specific locations with schools disabled
"""
import requests
import json
import time
from datetime import datetime

# Use production API URL
API_BASE_URL = "https://home-fit-production.up.railway.app"

def test_location(location: str, enable_schools: bool = False):
    """Test a single location and return the result"""
    url = f"{API_BASE_URL}/score"
    
    params = {
        "location": location,
        "enable_schools": "true" if enable_schools else "false"
    }
    
    print(f"\n{'='*80}")
    print(f"Testing: {location}")
    print(f"Schools enabled: {enable_schools}")
    print(f"{'='*80}")
    
    start_time = time.time()
    
    try:
        response = requests.get(url, params=params, timeout=300)
        elapsed_time = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            
            print(f"✓ Success ({elapsed_time:.1f}s)")
            print(f"\nLocation: {data.get('location_info', {}).get('city')}, {data.get('location_info', {}).get('state')} {data.get('location_info', {}).get('zip')}")
            print(f"Coordinates: {data.get('coordinates', {}).get('lat')}, {data.get('coordinates', {}).get('lon')}")
            print(f"Total Score: {data.get('total_score', 0):.1f}/100")
            
            # Show pillar scores
            pillars = data.get('livability_pillars', {})
            print(f"\nPillar Scores:")
            for pillar_name, pillar_data in pillars.items():
                score = pillar_data.get('score', 0)
                weight = pillar_data.get('weight', 0)
                contribution = pillar_data.get('contribution', 0)
                confidence = pillar_data.get('confidence', 0)
                print(f"  {pillar_name:25s}: {score:5.1f} (weight: {weight:5.1f}%, contribution: {contribution:5.1f}, confidence: {confidence:3.0f}%)")
            
            # Check for errors or warnings
            metadata = data.get('metadata', {})
            if metadata.get('cache_hit'):
                print(f"\n⚠️  Cache hit (cached response)")
            
            # Check data quality
            overall_confidence = data.get('overall_confidence', {})
            print(f"\nOverall Confidence: {overall_confidence.get('average_confidence', 0):.0f}%")
            print(f"Pillars using fallback: {overall_confidence.get('pillars_using_fallback', 0)}")
            
            return {
                "location": location,
                "success": True,
                "elapsed_time": elapsed_time,
                "total_score": data.get('total_score', 0),
                "data": data
            }
        else:
            print(f"✗ Error: HTTP {response.status_code}")
            print(f"Response: {response.text[:500]}")
            return {
                "location": location,
                "success": False,
                "error": f"HTTP {response.status_code}",
                "response": response.text[:500]
            }
            
    except requests.exceptions.Timeout:
        elapsed_time = time.time() - start_time
        print(f"✗ Timeout after {elapsed_time:.1f}s")
        return {
            "location": location,
            "success": False,
            "error": "Timeout",
            "elapsed_time": elapsed_time
        }
    except Exception as e:
        elapsed_time = time.time() - start_time
        print(f"✗ Error: {str(e)}")
        return {
            "location": location,
            "success": False,
            "error": str(e),
            "elapsed_time": elapsed_time
        }

if __name__ == "__main__":
    locations = [
        "Larchmont, NY",
        "111 2nd Street, Brooklyn, NY",
        "Redondo Beach, CA",
        "Culver City, CA"
    ]
    
    print(f"\n{'='*80}")
    print(f"Testing {len(locations)} locations with schools DISABLED")
    print(f"API: {API_BASE_URL}")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*80}")
    
    results = []
    for i, location in enumerate(locations):
        result = test_location(location, enable_schools=False)
        results.append(result)
        
        # Add delay between requests (except for last one)
        if i < len(locations) - 1:
            print(f"\nWaiting 3 seconds before next request...")
            time.sleep(3)
    
    # Summary
    print(f"\n\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    
    successful = [r for r in results if r.get('success')]
    failed = [r for r in results if not r.get('success')]
    
    print(f"\nSuccessful: {len(successful)}/{len(results)}")
    if successful:
        avg_time = sum(r.get('elapsed_time', 0) for r in successful) / len(successful)
        print(f"Average response time: {avg_time:.1f}s")
        print(f"\nScores:")
        for r in successful:
            print(f"  {r['location']:35s}: {r.get('total_score', 0):5.1f}/100 ({r.get('elapsed_time', 0):.1f}s)")
    
    if failed:
        print(f"\nFailed: {len(failed)}/{len(results)}")
        for r in failed:
            print(f"  {r['location']:35s}: {r.get('error', 'Unknown error')}")
    
    # Save detailed results to file
    output_file = f"test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nDetailed results saved to: {output_file}")

