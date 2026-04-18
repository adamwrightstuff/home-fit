#!/usr/bin/env python3
"""
Script to make batch API requests with schools disabled
Uses /score endpoint for each location since /batch may not be available
"""
import requests
import json
import sys
import time

def make_score_request(location, enable_schools=False, base_url="http://localhost:8000"):
    """
    Make a single score request to the /score endpoint
    
    Args:
        location: Location string
        enable_schools: Whether to enable school scoring (default: False)
        base_url: Base URL of the API server
    """
    url = f"{base_url}/score"
    
    params = {
        "location": location,
        "enable_schools": "true" if enable_schools else "false"
    }
    
    try:
        response = requests.get(url, params=params, timeout=300)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error making request for {location}: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response status: {e.response.status_code}")
            print(f"Response body: {e.response.text}")
        return None

def make_batch_requests(locations, enable_schools=False, base_url="http://localhost:8000", delay=2):
    """
    Make score requests for multiple locations
    
    Args:
        locations: List of location strings
        enable_schools: Whether to enable school scoring (default: False)
        base_url: Base URL of the API server
        delay: Delay between requests in seconds
    """
    print(f"Making batch requests to {base_url}/score")
    print(f"Locations: {locations}")
    print(f"Schools enabled: {enable_schools}")
    print("-" * 80)
    
    results = []
    for i, location in enumerate(locations):
        print(f"\n[{i+1}/{len(locations)}] Processing: {location}")
        result = make_score_request(location, enable_schools, base_url)
        if result:
            results.append({
                "location": location,
                "success": True,
                "result": result
            })
            print(f"✓ Success")
        else:
            results.append({
                "location": location,
                "success": False,
                "result": None
            })
            print(f"✗ Failed")
        
        # Add delay between requests (except for last one)
        if i < len(locations) - 1:
            time.sleep(delay)
    
    print("\n" + "=" * 80)
    print("BATCH SUMMARY")
    print("=" * 80)
    print(json.dumps(results, indent=2))
    
    return results

if __name__ == "__main__":
    locations = [
        "Durham NC",
        "Fairlawn OH",
        "Federal Triangle Washington DC",
        "Fells Point Baltimore MD"
    ]
    
    make_batch_requests(locations, enable_schools=False)

