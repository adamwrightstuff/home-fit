#!/usr/bin/env python3
"""
Test script to see if there are ANY businesses in OSM for Coconut Grove.
"""

import sys
import requests
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data_sources.osm_api import get_overpass_url

def main():
    lat = 25.7126013
    lon = -80.2569947
    radius_m = 1000
    
    # Very broad query - any amenity or shop
    query = f"""
    [out:json][timeout:60];
    (
      node["amenity"](around:{radius_m},{lat},{lon});
      way["amenity"](around:{radius_m},{lat},{lon});
      node["shop"](around:{radius_m},{lat},{lon});
      way["shop"](around:{radius_m},{lat},{lon});
    );
    out body;
    >;
    out skel qt;
    """
    
    print("Testing broad OSM query for Coconut Grove...")
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
            print(f"✅ Found {len(elements)} elements total\n")
            
            # Group by type
            amenities = {}
            shops = {}
            
            for elem in elements:
                tags = elem.get("tags", {})
                amenity = tags.get("amenity")
                shop = tags.get("shop")
                name = tags.get("name", "Unnamed")
                
                if amenity:
                    if amenity not in amenities:
                        amenities[amenity] = []
                    amenities[amenity].append(name)
                if shop:
                    if shop not in shops:
                        shops[shop] = []
                    shops[shop].append(name)
            
            if amenities:
                print("Amenities found:")
                for amenity, names in sorted(amenities.items()):
                    print(f"  {amenity}: {len(names)} ({', '.join(names[:5])}{'...' if len(names) > 5 else ''})")
            
            if shops:
                print("\nShops found:")
                for shop, names in sorted(shops.items()):
                    print(f"  {shop}: {len(names)} ({', '.join(names[:5])}{'...' if len(names) > 5 else ''})")
            
            if not amenities and not shops:
                print("❌ No amenities or shops found in OSM for this location")
        else:
            print(f"❌ OSM query failed with status {resp.status_code}")
            print(resp.text[:500])
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

