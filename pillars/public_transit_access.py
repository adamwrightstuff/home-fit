"""
Public Transit Access Pillar
Scores access to public transportation (rail, light rail, bus)
"""

import os
import requests
import math
from typing import Dict, Tuple, List, Optional
from dotenv import load_dotenv

load_dotenv()

# Transitland API v2 endpoint
TRANSITLAND_API = "https://transit.land/api/v2/rest"
TRANSITLAND_API_KEY = os.getenv("TRANSITLAND_API_KEY")


def get_public_transit_score(lat: float, lon: float) -> Tuple[float, Dict]:
    """
    Calculate public transit access score (0-100).

    Scoring:
    - Heavy Rail (subway, metro, commuter rail): 0-50 points
    - Light Rail (streetcar, light rail, BRT): 0-25 points
    - Bus: 0-25 points

    Returns:
        (total_score, detailed_breakdown)
    """
    print(f"🚇 Analyzing public transit access...")

    # Query Transitland for nearby stops
    stops = _get_nearby_stops(lat, lon, radius_m=1500)

    if not stops:
        print("⚠️  No transit stops found nearby")
        return 0, _empty_breakdown()

    # Categorize stops by mode
    heavy_rail_stops = []
    light_rail_stops = []
    bus_stops = []

    for stop in stops:
        route_types = stop.get("route_types", [])
        distance_m = stop.get("distance_m", 9999)

        # Categorize by route type (GTFS route_type codes)
        # 0=Tram/Light Rail, 1=Subway/Metro, 2=Rail/Commuter, 3=Bus
        # 4=Ferry, 5=Cable car, 6=Gondola, 7=Funicular

        if any(rt in [1, 2] for rt in route_types):  # Subway/Metro/Commuter Rail
            heavy_rail_stops.append(stop)
        elif any(rt in [0, 5, 7] for rt in route_types):  # Light rail/Tram/Cable car
            light_rail_stops.append(stop)
        elif 3 in route_types:  # Bus
            bus_stops.append(stop)

    # Score each component
    heavy_rail_score = _score_heavy_rail(heavy_rail_stops)
    light_rail_score = _score_light_rail(light_rail_stops)
    bus_score = _score_bus(bus_stops)

    total_score = heavy_rail_score + light_rail_score + bus_score

    # Build response
    breakdown = {
        "score": round(total_score, 1),
        "breakdown": {
            "heavy_rail": round(heavy_rail_score, 1),
            "light_rail": round(light_rail_score, 1),
            "bus": round(bus_score, 1)
        },
        "summary": _build_summary(heavy_rail_stops, light_rail_stops, bus_stops, stops)
    }

    # Log results
    print(f"✅ Public Transit Score: {total_score:.0f}/100")
    print(f"   🚇 Heavy Rail: {heavy_rail_score:.0f}/50 ({len(heavy_rail_stops)} stops)")
    print(f"   🚊 Light Rail: {light_rail_score:.0f}/25 ({len(light_rail_stops)} stops)")
    print(f"   🚌 Bus: {bus_score:.0f}/25 ({len(bus_stops)} stops)")

    return round(total_score, 1), breakdown


def _get_nearby_stops(lat: float, lon: float, radius_m: int = 1500) -> List[Dict]:
    """
    Query Transitland API for nearby transit stops.

    Args:
        lat: Latitude
        lon: Longitude
        radius_m: Search radius in meters (default 1500m = ~15 min walk)

    Returns:
        List of stops with distance and route types
    """
    if not TRANSITLAND_API_KEY:
        print("   ⚠️  TRANSITLAND_API_KEY not found in .env")
        return []
    
    try:
        # Transitland v2 API endpoint for stops
        url = f"{TRANSITLAND_API}/stops"

        params = {
            "lat": lat,
            "lon": lon,
            "radius": radius_m,
            "include_alerts": "false",
            "include_geometries": "false",
            "limit": 1000,  # Get many stops to analyze
            "apikey": TRANSITLAND_API_KEY  # Add API key
        }

        response = requests.get(url, params=params, timeout=15)

        if response.status_code != 200:
            print(f"   ⚠️  Transitland API returned status {response.status_code}")
            if response.status_code == 401:
                print(f"   ⚠️  API key authentication failed")
            return []

        data = response.json()
        stops_data = data.get("stops", [])

        if not stops_data:
            return []

        # Process stops
        stops = []
        for stop in stops_data:
            stop_lat = stop.get("geometry", {}).get("coordinates", [None, None])[1]
            stop_lon = stop.get("geometry", {}).get("coordinates", [None, None])[0]

            if not stop_lat or not stop_lon:
                continue

            distance_m = _haversine_distance(lat, lon, stop_lat, stop_lon)

            # Get route types from served routes
            route_types = []
            for route in stop.get("route_stops", []):
                rt = route.get("route", {}).get("route_type")
                if rt is not None:
                    route_types.append(rt)

            route_types = list(set(route_types))  # Deduplicate

            stops.append({
                "name": stop.get("stop_name", "Unknown"),
                "distance_m": round(distance_m, 0),
                "route_types": route_types,
                "lat": stop_lat,
                "lon": stop_lon
            })

        # Sort by distance
        stops.sort(key=lambda x: x["distance_m"])

        return stops

    except Exception as e:
        print(f"   ⚠️  Transit query error: {e}")
        return []


def _score_heavy_rail(stops: List[Dict]) -> float:
    """
    Score heavy rail access (0-50 points).
    Subway, metro, commuter rail.
    """
    if not stops:
        return 0.0

    closest = min(stops, key=lambda x: x["distance_m"])
    dist = closest["distance_m"]
    count = len(stops)

    # Distance score (0-30)
    if dist <= 400:  # 5 min walk
        distance_score = 30.0
    elif dist <= 800:  # 10 min walk
        distance_score = 25.0
    elif dist <= 1200:  # 15 min walk
        distance_score = 18.0
    elif dist <= 1500:
        distance_score = 12.0
    else:
        distance_score = 5.0

    # Density score (0-20) - more stops = better coverage
    if count >= 10:
        density_score = 20.0
    elif count >= 5:
        density_score = 15.0
    elif count >= 3:
        density_score = 10.0
    elif count >= 2:
        density_score = 5.0
    else:
        density_score = 2.0

    return min(50, distance_score + density_score)


def _score_light_rail(stops: List[Dict]) -> float:
    """
    Score light rail access (0-25 points).
    Streetcar, light rail, cable car.
    """
    if not stops:
        return 0.0

    closest = min(stops, key=lambda x: x["distance_m"])
    dist = closest["distance_m"]
    count = len(stops)

    # Distance score (0-15)
    if dist <= 400:
        distance_score = 15.0
    elif dist <= 800:
        distance_score = 12.0
    elif dist <= 1200:
        distance_score = 8.0
    else:
        distance_score = 4.0

    # Density score (0-10)
    if count >= 5:
        density_score = 10.0
    elif count >= 3:
        density_score = 7.0
    elif count >= 2:
        density_score = 4.0
    else:
        density_score = 2.0

    return min(25, distance_score + density_score)


def _score_bus(stops: List[Dict]) -> float:
    """
    Score bus access (0-25 points).
    Traditional bus service.
    """
    if not stops:
        return 0.0

    count_within_400m = len([s for s in stops if s["distance_m"] <= 400])

    # Bus scoring based on density (buses are everywhere in cities)
    if count_within_400m >= 10:
        return 25.0
    elif count_within_400m >= 7:
        return 22.0
    elif count_within_400m >= 5:
        return 20.0
    elif count_within_400m >= 3:
        return 15.0
    elif count_within_400m >= 2:
        return 10.0
    elif count_within_400m >= 1:
        return 7.0
    else:
        # Has bus stops but farther away
        if stops:
            return 3.0
        return 0.0


def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points in meters."""
    R = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi/2)**2 + math.cos(phi1) * \
        math.cos(phi2) * math.sin(delta_lambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

    return R * c


def _build_summary(heavy_rail: List, light_rail: List, bus: List, all_stops: List) -> Dict:
    """Build summary of transit access."""
    summary = {
        "total_stops": len(all_stops),
        "heavy_rail_stops": len(heavy_rail),
        "light_rail_stops": len(light_rail),
        "bus_stops": len(bus),
        "nearest_heavy_rail": None,
        "nearest_light_rail": None,
        "nearest_bus": None,
        "transit_modes_available": []
    }

    if heavy_rail:
        closest = min(heavy_rail, key=lambda x: x["distance_m"])
        summary["nearest_heavy_rail"] = {
            "name": closest["name"],
            "distance_m": closest["distance_m"]
        }
        summary["transit_modes_available"].append("Heavy Rail (Subway/Metro)")

    if light_rail:
        closest = min(light_rail, key=lambda x: x["distance_m"])
        summary["nearest_light_rail"] = {
            "name": closest["name"],
            "distance_m": closest["distance_m"]
        }
        summary["transit_modes_available"].append("Light Rail/Streetcar")

    if bus:
        closest = min(bus, key=lambda x: x["distance_m"])
        summary["nearest_bus"] = {
            "name": closest["name"],
            "distance_m": closest["distance_m"]
        }
        summary["transit_modes_available"].append("Bus")

    # Access level description
    if heavy_rail and light_rail and bus:
        summary["access_level"] = "Excellent - Multimodal transit"
    elif heavy_rail:
        summary["access_level"] = "Very Good - Rail transit available"
    elif light_rail or (bus and len(bus) >= 5):
        summary["access_level"] = "Good - Regular transit service"
    elif bus:
        summary["access_level"] = "Fair - Bus service available"
    else:
        summary["access_level"] = "Limited - No transit nearby"

    return summary


def _empty_breakdown() -> Dict:
    """Return empty breakdown when no transit found."""
    return {
        "score": 0,
        "breakdown": {
            "heavy_rail": 0,
            "light_rail": 0,
            "bus": 0
        },
        "summary": {
            "total_stops": 0,
            "heavy_rail_stops": 0,
            "light_rail_stops": 0,
            "bus_stops": 0,
            "nearest_heavy_rail": None,
            "nearest_light_rail": None,
            "nearest_bus": None,
            "transit_modes_available": [],
            "access_level": "None - No transit service"
        }
    }