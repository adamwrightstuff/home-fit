#!/usr/bin/env python3
"""
Test script to check for restaurants/cafes in Coconut Grove with various tags.
"""

import sys
import requests
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data_sources.osm_api import get_overpass_url

def main():
    lat = 25.7126013
    lon = -80.2569947
    radius_m = 1500  # Larger radius
    
    # Query for restaurants, cafes, bars, etc. with various possible tags
    query = f"""
    [out:json][timeout:60];
    (
      node["amenity"~"restaurant|cafe|bar|pub|fast_food|food_court|bistro"](around:{radius_m},{lat},{lon});
      way["amenity"~"restaurant|cafe|bar|pub|fast_food|food_court|bistro"](around:{radius_m},{lat},{lon});
      node["shop"~"bakery|supermarket|convenience|greengrocer|deli|butcher"](around:{radius_m},{lat},{lon});
      way["shop"~"bakery|supermarket|convenience|greengrocer|deli|butcher"](around:{radius_m},{lat},{lon});
      node["cuisine"](around:{radius_m},{lat},{lon});
      way["cuisine"](around:{radius_m},{lat},{lon});
    );
    out body;
    >;
    out skel qt;
    """
    
    print("Testing for restaurants/cafes in Coconut Grove...")
    print(f"Coordinates: {lat}, {lon}")
    print(f"Radius: {radius_m}m\n")
    
    try:
        resp = requests.post(
            get_overpass_url(),
            data={"data": query},
            timeout=30,
            headers={"User-Agent": "HomeFit/1.0"}
        )
        
        if resp.status_code == 200:
            data = resp.json()
            elements = data.get("elements", [])
            print(f"✅ Found {len(elements)} elements\n")
            
            if elements:
                print("Found businesses:")
                for elem in elements[:20]:  # Show first 20
                    tags = elem.get("tags", {})
                    name = tags.get("name", "Unnamed")
                    amenity = tags.get("amenity", "")
                    shop = tags.get("shop", "")
                    cuisine = tags.get("cuisine", "")
                    brand = tags.get("brand", "")
                    
                    type_str = amenity or shop or cuisine or "unknown"
                    print(f"  - {name} ({type_str})" + (f" [brand: {brand}]" if brand else ""))
            else:
                print("❌ No restaurants, cafes, or food shops found in OSM for this location")
                print("   This suggests OSM data for Coconut Grove may be incomplete.")
        else:
            print(f"❌ OSM query failed with status {resp.status_code}")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

