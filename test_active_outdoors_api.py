#!/usr/bin/env python3
"""
Quick test script to test Active Outdoors pillar via API.
Usage: python3 test_active_outdoors_api.py [location]
"""

import sys
import requests
import json

def test_active_outdoors(location: str = "Central Park, New York NY", base_url: str = "http://localhost:8000"):
    """
    Test Active Outdoors pillar via API.
    
    Args:
        location: Address or location name
        base_url: Base URL for the API (default: http://localhost:8000)
    """
    print(f"🧪 Testing Active Outdoors pillar for: {location}")
    print(f"📍 API URL: {base_url}/score")
    print()
    
    # Test with only active_outdoors pillar
    params = {
        "location": location,
        "only": "active_outdoors",  # Only test this pillar (API uses "only" parameter)
        "diagnostics": "true"  # Include diagnostics for detailed info
    }
    
    try:
        print("📡 Sending request...")
        response = requests.get(f"{base_url}/score", params=params, timeout=60)
        
        if response.status_code != 200:
            print(f"❌ Error: {response.status_code}")
            print(f"   {response.text}")
            return False
        
        data = response.json()
        
        # Extract Active Outdoors score
        active_outdoors = data.get("pillars", {}).get("active_outdoors", {})
        score = active_outdoors.get("score", 0)
        breakdown = active_outdoors.get("breakdown", {})
        summary = active_outdoors.get("summary", {})
        
        print("✅ Success!")
        print()
        print(f"📊 Active Outdoors Score: {score:.1f}/100")
        print()
        print("Component Breakdown:")
        print(f"  Daily Urban Outdoors: {breakdown.get('daily_urban_outdoors', 0):.1f}/30")
        print(f"  Wild Adventure: {breakdown.get('wild_adventure', 0):.1f}/50")
        print(f"  Waterfront Lifestyle: {breakdown.get('waterfront_lifestyle', 0):.1f}/20")
        print()
        
        # Show summary stats
        if summary:
            print("Summary Stats:")
            parks = summary.get("parks", 0)
            playgrounds = summary.get("playgrounds", 0)
            trails = summary.get("hiking_trails", 0)
            water = summary.get("swimming_features", 0)
            print(f"  Parks: {parks}")
            print(f"  Playgrounds: {playgrounds}")
            print(f"  Hiking Trails: {trails}")
            print(f"  Water Features: {water}")
            print()
        
        # Show area classification
        area_class = data.get("location", {}).get("area_classification", {})
        if area_class:
            area_type = area_class.get("area_type", "unknown")
            print(f"Area Type: {area_type}")
            print()
        
        # Show diagnostics if available
        diagnostics = data.get("diagnostics", {})
        if diagnostics:
            ao_diag = diagnostics.get("active_outdoors", {})
            if ao_diag:
                print("Diagnostics:")
                print(f"  Parks (2km): {ao_diag.get('parks_2km', 0)}")
                print(f"  Playgrounds (2km): {ao_diag.get('playgrounds_2km', 0)}")
                print(f"  Hiking Trails (total): {ao_diag.get('hiking_trails_total', 0)}")
                print(f"  Hiking Trails (5km): {ao_diag.get('hiking_trails_within_5km', 0)}")
                print(f"  Swimming Features: {ao_diag.get('swimming_features', 0)}")
                print(f"  Camp Sites: {ao_diag.get('camp_sites', 0)}")
                print(f"  Tree Canopy (5km): {ao_diag.get('tree_canopy_pct_5km', 0):.1f}%")
                print()
        
        return True
        
    except requests.exceptions.ConnectionError:
        print(f"❌ Connection Error: Could not connect to {base_url}")
        print("   Make sure the API server is running:")
        print("   uvicorn main:app --reload")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main entry point."""
    location = sys.argv[1] if len(sys.argv) > 1 else "Central Park, New York NY"
    base_url = sys.argv[2] if len(sys.argv) > 2 else "http://localhost:8000"
    
    success = test_active_outdoors(location, base_url)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()

