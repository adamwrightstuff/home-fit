"""
Public Transit Access Pillar
Scores access to public transportation (rail, light rail, bus)
"""

import os
import requests
import math
from typing import Dict, Tuple, List, Optional
from dotenv import load_dotenv
from data_sources import data_quality

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

    # Query for routes near location
    routes_data = _get_nearby_routes(lat, lon, radius_m=1500)
    
    if not routes_data:
        print("⚠️  No transit routes found nearby")
        return 0, _empty_breakdown()

    # Categorize routes by type
    heavy_rail_routes = []
    light_rail_routes = []
    bus_routes = []

    for route in routes_data:
        route_type = route.get("route_type")
        
        # GTFS route types: 0=Tram, 1=Subway, 2=Rail, 3=Bus
        if route_type in [1, 2]:  # Subway/Metro or Commuter Rail
            heavy_rail_routes.append(route)
        elif route_type == 0:  # Light rail/Tram
            light_rail_routes.append(route)
        elif route_type == 3:  # Bus
            bus_routes.append(route)

    # Score each component
    heavy_rail_score = _score_heavy_rail_routes(heavy_rail_routes)
    light_rail_score = _score_light_rail_routes(light_rail_routes)
    bus_score = _score_bus_routes(bus_routes)

    total_score = heavy_rail_score + light_rail_score + bus_score

    # Assess data quality
    combined_data = {
        'routes_data': routes_data,
        'heavy_rail_routes': heavy_rail_routes,
        'light_rail_routes': light_rail_routes,
        'bus_routes': bus_routes,
        'total_score': total_score
    }
    
    # Get area classification for data quality assessment
    area_type = "urban_core"  # Default, could be enhanced with actual area detection
    quality_metrics = data_quality.assess_pillar_data_quality('public_transit_access', combined_data, lat, lon, area_type)

    # Build response
    breakdown = {
        "score": round(total_score, 1),
        "breakdown": {
            "heavy_rail": round(heavy_rail_score, 1),
            "light_rail": round(light_rail_score, 1),
            "bus": round(bus_score, 1)
        },
        "summary": _build_summary_from_routes(
            heavy_rail_routes, light_rail_routes, bus_routes, routes_data
        ),
        "data_quality": quality_metrics
    }

    # Log results
    print(f"✅ Public Transit Score: {total_score:.0f}/100")
    print(f"   🚇 Heavy Rail: {heavy_rail_score:.0f}/50 ({len(heavy_rail_routes)} routes)")
    print(f"   🚊 Light Rail: {light_rail_score:.0f}/25 ({len(light_rail_routes)} routes)")
    print(f"   🚌 Bus: {bus_score:.0f}/25 ({len(bus_routes)} routes)")
    print(f"   📊 Data Quality: {quality_metrics['quality_tier']} ({quality_metrics['confidence']}% confidence)")

    return round(total_score, 1), breakdown


def _get_nearby_routes(lat: float, lon: float, radius_m: int = 1500) -> List[Dict]:
    """
    Query Transitland API for nearby transit routes.
    
    Returns list of routes with their types and distances.
    """
    if not TRANSITLAND_API_KEY:
        print("   ⚠️  TRANSITLAND_API_KEY not found in .env")
        return []
    
    try:
        url = f"{TRANSITLAND_API}/routes"
        
        params = {
            "lat": lat,
            "lon": lon,
            "radius": radius_m,
            "limit": 500,
            "apikey": TRANSITLAND_API_KEY
        }
        
        response = requests.get(url, params=params, timeout=15)
        
        if response.status_code != 200:
            print(f"   ⚠️  Transitland API returned status {response.status_code}")
            return []
        
        data = response.json()
        routes = data.get("routes", [])
        
        if not routes:
            print("   ℹ️  No routes found")
            return []
        
        # Process routes
        processed_routes = []
        for route in routes:
            route_type = route.get("route_type")
            if route_type is None:
                continue
            
            processed_routes.append({
                "name": route.get("route_long_name") or route.get("route_short_name", "Unknown"),
                "short_name": route.get("route_short_name"),
                "route_type": route_type,
                "agency": route.get("agency", {}).get("agency_name", "Unknown")
            })
        
        print(f"   ℹ️  Found {len(processed_routes)} transit routes")
        
        return processed_routes
        
    except Exception as e:
        print(f"   ⚠️  Transit query error: {e}")
        return []


def _score_heavy_rail_routes(routes: List[Dict]) -> float:
    """Score heavy rail access based on route availability."""
    if not routes:
        return 0.0
    
    count = len(routes)
    
    # Presence of heavy rail is huge (30 pts base)
    base_score = 30.0
    
    # Bonus for multiple lines (0-20 pts)
    if count >= 5:
        density_score = 20.0
    elif count >= 3:
        density_score = 15.0
    elif count >= 2:
        density_score = 10.0
    else:
        density_score = 5.0
    
    return min(50, base_score + density_score)


def _score_light_rail_routes(routes: List[Dict]) -> float:
    """Score light rail access based on route availability."""
    if not routes:
        return 0.0
    
    count = len(routes)
    
    # Presence of light rail (15 pts base)
    base_score = 15.0
    
    # Bonus for multiple lines (0-10 pts)
    if count >= 3:
        density_score = 10.0
    elif count >= 2:
        density_score = 7.0
    else:
        density_score = 3.0
    
    return min(25, base_score + density_score)


def _score_bus_routes(routes: List[Dict]) -> float:
    """Score bus access based on route availability."""
    if not routes:
        return 0.0
    
    count = len(routes)
    
    # Bus scoring based on route count
    if count >= 20:
        return 25.0
    elif count >= 15:
        return 23.0
    elif count >= 10:
        return 20.0
    elif count >= 7:
        return 17.0
    elif count >= 5:
        return 15.0
    elif count >= 3:
        return 12.0
    elif count >= 2:
        return 10.0
    else:
        return 7.0


def _build_summary_from_routes(heavy_rail: List, light_rail: List, bus: List, all_routes: List) -> Dict:
    """Build summary of transit access from routes."""
    summary = {
        "total_stops": len(all_routes),  # Using route count as proxy
        "heavy_rail_stops": len(heavy_rail),
        "light_rail_stops": len(light_rail),
        "bus_stops": len(bus),
        "nearest_heavy_rail": heavy_rail[0] if heavy_rail else None,
        "nearest_light_rail": light_rail[0] if light_rail else None,
        "nearest_bus": bus[0] if bus else None,
        "transit_modes_available": []
    }

    if heavy_rail:
        summary["transit_modes_available"].append("Heavy Rail (Subway/Metro)")

    if light_rail:
        summary["transit_modes_available"].append("Light Rail/Streetcar")

    if bus:
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
    