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
            
            # Extract route_type if available (from routes serving this stop)
            # Transitland v2 API may include route_type in various locations:
            # - stop.route_type (direct)
            # - stop.routes[].route_type (from routes serving this stop)
            # - stop.route_types[] (array of route types)
            route_type = None
            if "route_type" in stop:
                route_type = stop.get("route_type")
            elif "route_types" in stop and isinstance(stop["route_types"], list) and len(stop["route_types"]) > 0:
                # Use first route_type from array (most common type for this stop)
                route_type = stop["route_types"][0]
            elif "routes" in stop and isinstance(stop["routes"], list) and len(stop["routes"]) > 0:
                # Try to get route_type from first route serving this stop
                first_route = stop["routes"][0]
                if isinstance(first_route, dict):
                    route_type = first_route.get("route_type")
            
            processed_stops.append({
                "id": stop.get("onestop_id"),
                "name": stop.get("stop_name"),
                "lat": stop_lat,
                "lon": stop_lon,
                "distance_m": round(distance, 0),
                "route_type": route_type  # Preserve route_type if available
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
            "all_stops": processed_stops,  # Include all stops for counting by route_type
            "count": len(processed_stops),
            "summary": summary
        }
        
    except Exception as e:
        print(f"Transitland API error: {e}")
        return None


def get_stop_departures(stop_onestop_id: str, limit: int = 200, service_date: Optional[str] = None) -> Optional[List[Dict]]:
    """
    Get scheduled departures for a stop using Transitland v2 stop departures endpoint.
    
    Args:
        stop_onestop_id: Stop OneStop ID (e.g., 's-dr72zxmq5p-centralparkave~tuckahoerd')
        limit: Maximum number of departures to return (default 200 for full day schedule)
        service_date: Optional service date in YYYY-MM-DD format. If None, uses next weekday.
                     Using a specific date returns full day schedule instead of just upcoming departures.
    
    Returns:
        List of departure dictionaries with schedule information, or None if unavailable
    """
    if not TRANSITLAND_API_KEY:
        return None
    
    try:
        from datetime import datetime, timedelta
        
        # If no service_date provided, use next weekday (Monday-Friday) for full schedule
        if service_date is None:
            today = datetime.now()
            # Find next weekday (Monday = 0, Friday = 4)
            days_ahead = 0
            if today.weekday() >= 5:  # Saturday or Sunday
                days_ahead = 7 - today.weekday()  # Days until Monday
            elif today.weekday() == 4:  # Friday
                days_ahead = 3  # Next Monday
            else:
                days_ahead = 1  # Next weekday
            service_date = (today + timedelta(days=days_ahead)).strftime('%Y-%m-%d')
        
        url = f"{TRANSITLAND_BASE_URL}/rest/stops/{stop_onestop_id}/departures"
        params = {
            "apikey": TRANSITLAND_API_KEY,
            "limit": limit,
            "service_date": service_date
        }
        
        response = requests.get(url, params=params, timeout=30)  # Increased timeout for larger responses
        
        if response.status_code != 200:
            return None
        
        data = response.json()
        stops = data.get("stops", [])
        
        if not stops:
            return None
        
        # Response structure: stops[0].departures[]
        stop = stops[0]
        departures = stop.get("departures", [])
        
        return departures
        
    except Exception as e:
        print(f"Transitland stop departures query error for {stop_onestop_id}: {e}")
        return None


def get_route_schedules(route_onestop_id: str, sample_stop_id: Optional[str] = None) -> Optional[Dict]:
    """
    Get schedule/service frequency data for a route using Transitland API.
    
    Uses stop departures endpoint to calculate frequency metrics from a representative stop.
    
    Args:
        route_onestop_id: Route OneStop ID (e.g., 'r-dr7-harlem')
        sample_stop_id: Optional stop ID on this route (if not provided, will try to find one)
    
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
        # If no sample stop provided, try to get one from the route
        stop_id = sample_stop_id
        if not stop_id:
            # Try to find a stop on this route by querying stops near a known location
            # For now, return None - caller should provide a stop_id
            return None
        
        # Get departures for this stop (use service_date to get full day schedule)
        departures = get_stop_departures(stop_id, limit=200, service_date=None)  # None = auto-select next weekday
        
        if not departures or len(departures) < 2:
            return None
        
        # Parse departure times
        departure_times = []
        for dep in departures:
            # Try different time fields - Transitland v2 structure
            # departure.scheduled is the primary field (format: "HH:MM:SS")
            time_str = None
            
            # Check departure object first (most reliable)
            dep_obj = dep.get("departure", {})
            if isinstance(dep_obj, dict):
                time_str = dep_obj.get("scheduled") or dep_obj.get("scheduled_local")
            
            # Fallback to other fields
            if not time_str:
                time_str = (dep.get("departure_time") or 
                           dep.get("arrival_time") or
                           (dep.get("arrival", {}) or {}).get("scheduled"))
            
            if time_str:
                # Parse time string (format: "HH:MM:SS", "HH:MM", or ISO datetime)
                try:
                    # Handle ISO datetime strings like "2025-06-16T12:48:16-04:00"
                    if "T" in time_str:
                        # ISO format - extract time part
                        time_part = time_str.split("T")[1].split("-")[0].split("+")[0]
                        parts = time_part.split(":")
                    else:
                        parts = time_str.split(":")
                    
                    if len(parts) >= 2:
                        hours = int(parts[0])
                        minutes = int(parts[1])
                        total_minutes = hours * 60 + minutes
                        departure_times.append(total_minutes)
                except (ValueError, IndexError):
                    continue
        
        if len(departure_times) < 2:
            return None
        
        departure_times.sort()
        
        # Calculate service span
        first_minutes = departure_times[0]
        last_minutes = departure_times[-1]
        service_span_hours = (last_minutes - first_minutes) / 60.0
        
        # Calculate headways (time between consecutive departures)
        headways = []
        for i in range(1, len(departure_times)):
            headway = departure_times[i] - departure_times[i-1]
            if headway > 0:  # Ignore same-time departures
                headways.append(headway)
        
        if not headways:
            return None
        
        # Peak period: 7-9 AM (420-540 min) and 5-7 PM (1020-1140 min)
        peak_headways = []
        off_peak_headways = []
        
        for i, headway in enumerate(headways):
            # Use the earlier departure time to determine if it's peak
            dep_time = departure_times[i]
            is_peak = (420 <= dep_time <= 540) or (1020 <= dep_time <= 1140)
            
            if is_peak:
                peak_headways.append(headway)
            else:
                off_peak_headways.append(headway)
        
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
            "weekday_trips": len(departure_times),  # Approximate - actual count may vary by day
            "first_departure": f"{first_hour:02d}:{first_min:02d}",
            "last_departure": f"{last_hour:02d}:{last_min:02d}",
            "departures": departures,  # Include raw departures for reuse (avoids redundant API call)
        }
        
    except Exception as e:
        print(f"Transitland schedule query error for {route_onestop_id}: {e}")
        return None