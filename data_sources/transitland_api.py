"""
Transitland API Client
Queries transit stops using Transitland v2 REST API
"""

import os
import requests
import statistics
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


def get_route_schedules(route_onestop_id: str) -> Optional[Dict]:
    """
    Get schedule/service frequency data for a route using Transitland API.
    
    Args:
        route_onestop_id: Route OneStop ID (e.g., 'r-dr7-harlem')
    
    Returns:
        {
            "service_span_hours": float,  # First to last departure (hours)
            "peak_headway_minutes": float,  # Average peak period headway
            "off_peak_headway_minutes": float,  # Average off-peak headway
            "weekday_trips": int,  # Number of trips on a typical weekday
            "first_departure": str,  # HH:MM format
            "last_departure": str,  # HH:MM format
        } or None if unavailable
    """
    if not TRANSITLAND_API_KEY:
        return None
    
    try:
        # Query route details - Transitland v2 may have schedule info in route metadata
        url = f"{TRANSITLAND_BASE_URL}/rest/routes/{route_onestop_id}"
        params = {"apikey": TRANSITLAND_API_KEY}
        response = requests.get(url, params=params, timeout=15)
        
        if response.status_code != 200:
            return None
        
        route_data = response.json().get("routes", [])
        if not route_data:
            return None
        
        route = route_data[0]
        
        # Try to get trips for this route to calculate frequency
        # NOTE: Transitland v2 API may not have a direct trips endpoint
        # Schedule data may need to come from GTFS feeds or route_stops endpoint
        # For now, we'll attempt to get schedule info from route_stops if available
        trips_data = []
        
        # Check if route has route_stops that might contain schedule info
        route_stops = route.get("route_stops", [])
        if route_stops:
            # Route stops might have schedule information
            # This is a placeholder - actual structure may vary
            pass
        
        # Alternative: Try trips endpoint (may not exist in v2)
        trips_url = f"{TRANSITLAND_BASE_URL}/rest/trips"
        trips_params = {
            "route_onestop_id": route_onestop_id,
            "apikey": TRANSITLAND_API_KEY,
            "limit": 100
        }
        
        trips_response = requests.get(trips_url, params=trips_params, timeout=15)
        if trips_response.status_code == 200:
            trips_data = trips_response.json().get("trips", [])
        
        # If we have trips, calculate service metrics
        if trips_data:
            # Extract departure times (assuming trips have schedule data)
            # This is a simplified calculation - real GTFS would have more detail
            departure_times = []
            for trip in trips_data:
                # Try to get stop_times or schedule info
                # Transitland structure may vary
                if "stop_times" in trip:
                    for st in trip["stop_times"]:
                        if "departure_time" in st:
                            departure_times.append(st["departure_time"])
                elif "departure_time" in trip:
                    departure_times.append(trip["departure_time"])
            
            if departure_times:
                # Parse times and calculate metrics
                # Times are typically in HH:MM:SS format
                parsed_times = []
                for dt in departure_times:
                    try:
                        parts = dt.split(":")
                        if len(parts) >= 2:
                            hours = int(parts[0])
                            minutes = int(parts[1])
                            total_minutes = hours * 60 + minutes
                            parsed_times.append(total_minutes)
                    except (ValueError, IndexError):
                        continue
                
                if parsed_times:
                    parsed_times.sort()
                    first_minutes = parsed_times[0]
                    last_minutes = parsed_times[-1]
                    
                    # Service span in hours
                    service_span_hours = (last_minutes - first_minutes) / 60.0
                    
                    # Calculate headways (time between consecutive trips)
                    headways = []
                    for i in range(1, len(parsed_times)):
                        headway = parsed_times[i] - parsed_times[i-1]
                        if headway > 0:  # Ignore same-time trips
                            headways.append(headway)
                    
                    # Peak period: 7-9 AM and 5-7 PM (420-540 min and 1020-1140 min)
                    peak_headways = [
                        h for i, h in enumerate(headways)
                        if i < len(parsed_times) - 1 and
                        (420 <= parsed_times[i] <= 540 or 1020 <= parsed_times[i] <= 1140)
                    ]
                    off_peak_headways = [
                        h for i, h in enumerate(headways)
                        if i < len(parsed_times) - 1 and
                        not (420 <= parsed_times[i] <= 540 or 1020 <= parsed_times[i] <= 1140)
                    ]
                    
                    peak_headway = statistics.mean(peak_headways) if peak_headways else None
                    off_peak_headway = statistics.mean(off_peak_headways) if off_peak_headways else None
                    
                    # Format first/last departure
                    first_hour = first_minutes // 60
                    first_min = first_minutes % 60
                    last_hour = last_minutes // 60
                    last_min = last_minutes % 60
                    
                    return {
                        "service_span_hours": round(service_span_hours, 1),
                        "peak_headway_minutes": round(peak_headway, 1) if peak_headway else None,
                        "off_peak_headway_minutes": round(off_peak_headway, 1) if off_peak_headway else None,
                        "weekday_trips": len(parsed_times),
                        "first_departure": f"{first_hour:02d}:{first_min:02d}",
                        "last_departure": f"{last_hour:02d}:{last_min:02d}",
                    }
        
        # Fallback: return None if we can't calculate
        return None
        
    except Exception as e:
        print(f"Transitland schedule query error for {route_onestop_id}: {e}")
        return None