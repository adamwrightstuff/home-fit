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
from data_sources.radius_profiles import get_radius_profile
from data_sources.transitland_api import get_nearby_transit_stops

load_dotenv()

# Transitland API v2 endpoint
TRANSITLAND_API = "https://transit.land/api/v2/rest"
TRANSITLAND_API_KEY = os.getenv("TRANSITLAND_API_KEY")
def _nearest_heavy_rail_km(lat: float, lon: float, search_m: int = 2500) -> float:
    """Find nearest heavy rail/subway distance using Transitland stops API (km),
    falling back to coordinate distance and OSM stations when needed."""
    try:
        stops = get_nearby_transit_stops(lat, lon, radius_m=search_m) or {}
        # stops may be shaped as {"stops": [...]} or {"items": [...]}
        items = stops.get("stops", []) or stops.get("items", []) or []
        distances_km = []
        for s in items:
            rt = s.get("route_type")
            if rt in (1, 2):  # 1=subway/metro, 2=rail (commuter)
                # Prefer server-provided distance if present
                dist_m = s.get("distance") or s.get("distance_m")
                if isinstance(dist_m, (int, float)):
                    distances_km.append(dist_m / 1000.0)
                    continue
                # Otherwise compute from coordinates when available
                stop_lat = s.get("lat") or (s.get("stop") or {}).get("lat")
                stop_lon = s.get("lon") or (s.get("stop") or {}).get("lon")
                if isinstance(stop_lat, (int, float)) and isinstance(stop_lon, (int, float)):
                    distances_km.append(haversine_distance(lat, lon, float(stop_lat), float(stop_lon)))
        if distances_km:
            return min(distances_km)
        # Fallback to OSM railway stations if Transitland stop distances unavailable
        try:
            from data_sources import osm_api as osm
            stations = osm.query_railway_stations(lat, lon, radius_m=search_m)
            if stations:
                # stations include distance_m already
                station_dists_km = [st.get("distance_m", 1e12) / 1000.0 for st in stations if isinstance(st.get("distance_m"), (int, float))]
                if station_dists_km:
                    return min(station_dists_km)
        except Exception:
            pass
        return float('inf')
    except Exception:
        return float('inf')


def _frequency_tier_heavy_rail(heavy_routes_count: int) -> int:
    """Simple proxy frequency tier from distinct heavy rail routes nearby (0-3)."""
    if heavy_routes_count >= 3:
        return 3
    if heavy_routes_count == 2:
        return 2
    if heavy_routes_count == 1:
        return 1
    return 0

# Major metro centers for proximity-based fallback scoring
MAJOR_METROS = {
    "New York": (40.7128, -74.0060),
    "Los Angeles": (34.0522, -118.2437),
    "Chicago": (41.8781, -87.6298),
    "Houston": (29.7604, -95.3698),
    "Phoenix": (33.4484, -112.0740),
    "Philadelphia": (39.9526, -75.1652),
    "San Antonio": (29.4241, -98.4936),
    "San Diego": (32.7157, -117.1611),
    "Dallas": (32.7767, -96.7970),
    "San Jose": (37.3382, -121.8863),
    "Austin": (30.2672, -97.7431),
    "Jacksonville": (30.3322, -81.6557),
    "San Francisco": (37.7749, -122.4194),
    "Columbus": (39.9612, -82.9988),
    "Seattle": (47.6062, -122.3321),
    "Boston": (42.3601, -71.0589),
    "Miami": (25.7617, -80.1918),
    "Portland": (45.5152, -122.6784),
    "Denver": (39.7392, -104.9903),
    "Atlanta": (33.7490, -84.3880),
}


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points in kilometers."""
    R = 6371  # Earth radius in km
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    
    a = math.sin(delta_phi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    
    return R * c


def _find_nearest_metro(lat: float, lon: float) -> float:
    """Find distance to nearest major metro center in kilometers."""
    min_distance = float('inf')
    
    for metro_name, (metro_lat, metro_lon) in MAJOR_METROS.items():
        distance = haversine_distance(lat, lon, metro_lat, metro_lon)
        min_distance = min(min_distance, distance)
    
    return min_distance


def get_public_transit_score(lat: float, lon: float,
                             area_type: Optional[str] = None,
                             location_scope: Optional[str] = None) -> Tuple[float, Dict]:
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

    # Query for routes near location using centralized radius profile
    rp = get_radius_profile('public_transit_access', area_type, location_scope)
    nearby_radius = int(rp.get('routes_radius_m', 1500))
    routes_data = _get_nearby_routes(lat, lon, radius_m=nearby_radius)
    # Log chosen radius profile
    print(f"   🔧 Radius profile (transit): area_type={area_type}, scope={location_scope}, routes_radius={nearby_radius}m")
    
    # If no Transitland routes, try OSM railway stations as fallback
    osm_stations = None
    if not routes_data:
        print("⚠️  No Transitland routes found, checking OSM railway stations...")
        from data_sources import osm_api as osm
        osm_stations = osm.query_railway_stations(lat, lon, radius_m=2000)
        
        if osm_stations and len(osm_stations) > 0:
            # Convert OSM stations to route-like format for scoring
            routes_data = _convert_osm_stations_to_routes(osm_stations)
            print(f"   Found {len(routes_data)} railway stations via OSM")
        else:
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

    # Adaptive scoring: For commuter towns with excellent heavy rail access,
    # don't penalize for missing light rail/bus. Heavy rail alone can achieve high scores.
    if heavy_rail_score >= 40 and (light_rail_score == 0 or bus_score < 15):
        # Excellent heavy rail in commuter town - scale up to 80-100 range
        # Heavy rail gets 60-70, light rail/bus are bonus (not required)
        base_score = min(70, heavy_rail_score + 10)  # Heavy rail worth more
        bonus_score = light_rail_score + bus_score
        total_score = min(100, base_score + (bonus_score * 0.4))  # Bus/LR are bonus
    else:
        # Urban areas or areas with multiple modes - use additive scoring
        total_score = heavy_rail_score + light_rail_score + bus_score

    # Assess data quality
    combined_data = {
        'routes_data': routes_data,
        'heavy_rail_routes': heavy_rail_routes,
        'light_rail_routes': light_rail_routes,
        'bus_routes': bus_routes,
        'total_score': total_score
    }
    
    # Detect actual area type for data quality assessment
    from data_sources import census_api
    density = census_api.get_population_density(lat, lon)
    area_type_dq = data_quality.detect_area_type(lat, lon, density)
    quality_metrics = data_quality.assess_pillar_data_quality('public_transit_access', combined_data, lat, lon, area_type_dq)

    # Suburban/Exurban/Rural commuter-centric layer: nearest rail + frequency tier
    if (area_type or 'unknown') in ('suburban', 'exurban', 'rural'):
        nearest_hr_km = _nearest_heavy_rail_km(lat, lon, search_m=2500)
        freq_tier = _frequency_tier_heavy_rail(len(heavy_rail_routes))

        # Distance-based base (max ~70)
        if nearest_hr_km <= 0.5:
            base = 70
        elif nearest_hr_km <= 1.0:
            base = 65
        elif nearest_hr_km <= 2.0:
            base = 60
        elif nearest_hr_km <= 3.0:
            base = 50
        elif nearest_hr_km < float('inf'):
            base = 40
        else:
            base = 20  # no rail nearby

        # Frequency bonus (0-15)
        freq_bonus = {0: 0, 1: 6, 2: 10, 3: 15}[freq_tier]
        # Bus bonus (0-15) proxy
        bus_bonus = min(15.0, max(0.0, len(bus_routes) * 3.0))

        total_score = max(total_score, min(100.0, base + freq_bonus + bus_bonus))

        # Augment quality to reflect successful data retrieval, not mode variety
        try:
            if (routes_data and len(routes_data) > 0) or nearest_hr_km < float('inf'):
                quality_metrics['quality_tier'] = 'good'
                quality_metrics['confidence'] = max(quality_metrics.get('confidence', 0), 70)
        except Exception:
            pass

    # Correct data_quality fallback flags and record data sources used
    try:
        found_any = (len(heavy_rail_routes) + len(light_rail_routes) + len(bus_routes)) > 0
        quality_metrics['needs_fallback'] = not found_any
        quality_metrics['fallback_score'] = 30.0 if not found_any else None
        fm = quality_metrics.get('fallback_metadata', {}) or {}
        fm['fallback_used'] = not found_any
        quality_metrics['fallback_metadata'] = fm
        ds = quality_metrics.get('data_sources', []) or []
        # Prefer Transitland when routes_data came from API; if we used OSM stations, include 'osm'
        if routes_data and not ds:
            ds.append('transitland')
        if osm_stations:
            if 'osm' not in ds:
                ds.append('osm')
        quality_metrics['data_sources'] = ds
    except Exception:
        pass

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

    # Add commuter-centric fields to summary
    try:
        nearest_hr_km_val = _nearest_heavy_rail_km(lat, lon, search_m=2500)
        breakdown["summary"]["nearest_heavy_rail_distance_km"] = None if nearest_hr_km_val == float('inf') else round(nearest_hr_km_val, 2)
        breakdown["summary"]["heavy_rail_frequency_tier"] = _frequency_tier_heavy_rail(len(heavy_rail_routes))
    except Exception:
        pass

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
        
        # Increase timeout and add retry for reliability
        response = None
        for attempt in range(2):  # 2 attempts
            try:
                response = requests.get(url, params=params, timeout=30)  # Increased to 30s
                if response.status_code == 200:
                    break
            except requests.exceptions.Timeout:
                if attempt < 1:  # Retry once
                    print(f"   ⚠️  Transitland API timeout (attempt {attempt + 1}/2), retrying...")
                    continue
                else:
                    print(f"   ⚠️  Transitland API timeout after 2 attempts")
                    raise
            except Exception as e:
                if attempt < 1:
                    print(f"   ⚠️  Transitland API error (attempt {attempt + 1}/2): {e}, retrying...")
                    continue
                else:
                    raise
        
        if response is None:
            return []
        
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


def _convert_osm_stations_to_routes(osm_stations: List[Dict]) -> List[Dict]:
    """
    Convert OSM railway stations to route-like format for scoring.
    
    Args:
        osm_stations: List of OSM station dictionaries
    
    Returns:
        List of route-like dictionaries
    """
    routes = []
    
    for station in osm_stations:
        railway_type = station.get("railway_type", "").lower()
        
        # Map railway types to GTFS route types
        if railway_type in ["station", "halt"]:
            route_type = 2  # Rail
        elif railway_type in ["subway_entrance", "subway"]:
            route_type = 1  # Subway/Metro
        elif railway_type in ["tram_stop"]:
            route_type = 0  # Tram/Light Rail
        else:
            route_type = 3  # Bus (default fallback)
        
        routes.append({
            "name": station.get("name", "Unknown Station"),
            "short_name": None,
            "route_type": route_type,
            "agency": "Unknown Agency",
            "distance_m": station.get("distance_m", 0)
        })
    
    return routes


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
    