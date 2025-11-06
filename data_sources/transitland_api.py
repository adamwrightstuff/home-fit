"""
Transitland API Client
Queries transit stops using Transitland v2 REST API
"""

import os
import requests
from typing import Dict, List, Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

TRANSITLAND_API_KEY = os.getenv("TRANSITLAND_API_KEY")
TRANSITLAND_BASE_URL = "https://transit.land/api/v2"


def get_nearby_transit_stops(
    lat: float,
    lon: float,
    radius_m: int = 800
) -> Optional[Dict]:
    """
    Get transit stops within radius using Transitland v2 API.
    
    Args:
        lat: Latitude
        lon: Longitude
        radius_m: Search radius in meters (max 10000)
    
    Returns:
        {
            "stops": [...],
            "count": int,
            "summary": {...}
        }
    """
    if not TRANSITLAND_API_KEY:
        print("⚠️  TRANSITLAND_API_KEY not found in .env file")
        return None
    
    try:
        url = f"{TRANSITLAND_BASE_URL}/rest/stops"
        
        params = {
            "lat": lat,
            "lon": lon,
            "radius": radius_m,
            "apikey": TRANSITLAND_API_KEY,
            "limit": 100
        }
        
        response = requests.get(url, params=params, timeout=15)
        
        if response.status_code != 200:
            print(f"⚠️  Transitland API returned status {response.status_code}")
            return None
        
        data = response.json()
        stops = data.get("stops", [])
        
        if not stops:
            print(f"⚠️  No transit stops found within {radius_m}m")
            return None
        
        # Process stops
        processed_stops = []
        for stop in stops:
            # Calculate distance
            from data_sources.utils import haversine_distance
            stop_lat = stop["geometry"]["coordinates"][1]
            stop_lon = stop["geometry"]["coordinates"][0]
            distance = haversine_distance(lat, lon, stop_lat, stop_lon)
            
            processed_stops.append({
                "id": stop.get("onestop_id"),
                "name": stop.get("stop_name"),
                "lat": stop_lat,
                "lon": stop_lon,
                "distance_m": round(distance, 0)
            })
        
        # Sort by distance
        processed_stops.sort(key=lambda x: x["distance_m"])
        
        # Build summary
        closest = processed_stops[0] if processed_stops else None
        
        summary = {
            "total_stops": len(processed_stops),
            "closest_stop": {
                "name": closest["name"],
                "distance_m": closest["distance_m"]
            } if closest else None,
            "within_400m": len([s for s in processed_stops if s["distance_m"] <= 400]),
            "within_800m": len([s for s in processed_stops if s["distance_m"] <= 800])
        }
        
        print(f"✅ Found {len(processed_stops)} transit stops within {radius_m}m")
        
        return {
            "stops": processed_stops[:10],  # Return top 10 closest
            "count": len(processed_stops),
            "summary": summary
        }
        
    except Exception as e:
        print(f"Transitland API error: {e}")
        return None