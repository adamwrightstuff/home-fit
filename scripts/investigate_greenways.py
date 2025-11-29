#!/usr/bin/env python3
"""
Diagnostic script to check how Hudson Greenway/East River Walkway are captured
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data_sources import osm_api
from data_sources.geocoding import geocode

def investigate_greenways():
    """Check what OSM features are captured for greenways."""
    
    # Test locations near Hudson Greenway and East River Walkway
    locations = [
        ("Hudson River Park, Manhattan NY", 40.7500, -74.0100),  # Near Hudson Greenway
        ("East River Park, Manhattan NY", 40.7200, -73.9800),     # Near East River Walkway
    ]
    
    for name, lat, lon in locations:
        print(f"\n{'='*70}")
        print(f"INVESTIGATING: {name}")
        print(f"Coordinates: {lat}, {lon}")
        print(f"{'='*70}\n")
        
        # 1. Check parks query
        print("1️⃣ PARKS QUERY (query_green_spaces):")
        parks_data = osm_api.query_green_spaces(lat, lon, radius_m=2000)
        if parks_data:
            parks = parks_data.get("parks", [])
            playgrounds = parks_data.get("playgrounds", [])
            print(f"   ✅ Found {len(parks)} parks, {len(playgrounds)} playgrounds")
            for i, park in enumerate(parks[:5], 1):
                print(f"      {i}. {park.get('name', 'Unnamed')} ({park.get('distance_m', 0):.0f}m away)")
        else:
            print("   ❌ No parks data")
        
        # 2. Check hiking trails query
        print("\n2️⃣ HIKING TRAILS QUERY (query_nature_features):")
        nature_data = osm_api.query_nature_features(lat, lon, radius_m=15000)
        if nature_data:
            hiking = nature_data.get("hiking", [])
            print(f"   ✅ Found {len(hiking)} hiking features")
            for i, trail in enumerate(hiking[:10], 1):
                trail_type = trail.get("type", "unknown")
                trail_name = trail.get("name", "Unnamed")
                distance = trail.get("distance_m", 0)
                print(f"      {i}. {trail_name} ({trail_type}) - {distance:.0f}m away")
        else:
            print("   ❌ No nature features data")
        
        # 3. Check what large parks exist (to see if greenways would be captured)
        print("\n3️⃣ LARGE PARKS CHECK (>50 hectares):")
        if parks_data:
            parks_list = parks_data.get("parks", [])
            # Sort by area to see largest parks
            sorted_parks = sorted(parks_list, key=lambda p: p.get("area_sqm", 0), reverse=True)
            large_parks = [p for p in sorted_parks if p.get("area_sqm", 0) >= 500000]  # 50 hectares
            print(f"   ✅ Found {len(large_parks)} large parks (>50 ha)")
            print(f"   📊 Top 5 largest parks (any size):")
            for i, park in enumerate(sorted_parks[:5], 1):
                area_ha = park.get("area_sqm", 0) / 10000
                name = park.get("name", "Unnamed")
                distance = park.get("distance_m", 0)
                print(f"      {i}. {name} - {area_ha:.1f} ha ({distance:.0f}m away)")
                if area_ha >= 50:
                    print(f"         ✅ Large enough for trails query")
        
        # 4. Check for cycleways/footways directly (what greenways are typically tagged as)
        print("\n4️⃣ CYCLEWAY/FOOTWAY CHECK (greenways):")
        print("   (Note: This requires a direct OSM query - checking if they exist in parks)")
        # We can't easily query cycleways/footways without modifying the API
        # But we can check if the parks we found might contain them
        if parks_data:
            # Check for parks with names suggesting greenways
            greenway_parks = [p for p in parks_data.get("parks", []) 
                            if any(keyword in (p.get("name", "") or "").lower() 
                                  for keyword in ["greenway", "walkway", "river", "waterfront"])]
            print(f"   ✅ Found {len(greenway_parks)} parks with greenway-related names:")
            for i, park in enumerate(greenway_parks[:5], 1):
                area_ha = park.get("area_sqm", 0) / 10000
                print(f"      {i}. {park.get('name', 'Unnamed')} - {area_ha:.1f} ha")
                if area_ha < 50:
                    print(f"         ⚠️  Too small for large park trails query (<50 ha)")
        
        print("\n" + "-"*70)

if __name__ == "__main__":
    investigate_greenways()

