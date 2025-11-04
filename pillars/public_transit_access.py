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

# Load environment variables from .env file
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


def _nearest_bus_km(lat: float, lon: float, bus_routes: List[Dict] = None, search_m: int = 2000) -> float:
    """Find nearest bus stop distance using route coordinates or Transitland stops API (km)."""
    distances_km = []
    
    # First, try to use route coordinates if available
    if bus_routes:
        for route in bus_routes:
            route_lat = route.get("lat")
            route_lon = route.get("lon")
            if route_lat and route_lon:
                dist = haversine_distance(lat, lon, route_lat, route_lon)
                if dist <= (search_m / 1000.0):  # Within search radius
                    distances_km.append(dist)
    
    # Fallback to stops API if no route coordinates available
    if not distances_km:
        try:
            stops = get_nearby_transit_stops(lat, lon, radius_m=search_m) or {}
            items = stops.get("stops", []) or stops.get("items", []) or []
            # Use all stops as proxy (since we can't filter by route_type)
            # This is a reasonable approximation for distance calculation
            for s in items:
                dist_m = s.get("distance_m")
                if isinstance(dist_m, (int, float)):
                    distances_km.append(dist_m / 1000.0)
                    continue
                stop_lat = s.get("lat")
                stop_lon = s.get("lon")
                if isinstance(stop_lat, (int, float)) and isinstance(stop_lon, (int, float)):
                    distances_km.append(haversine_distance(lat, lon, float(stop_lat), float(stop_lon)))
        except Exception:
            pass
    
    if distances_km:
        return min(distances_km)
    return float('inf')


def _nearest_light_rail_km(lat: float, lon: float, light_rail_routes: List[Dict] = None, search_m: int = 2000) -> float:
    """Find nearest light rail/tram stop distance using route coordinates or Transitland stops API (km)."""
    distances_km = []
    
    # First, try to use route coordinates if available
    if light_rail_routes:
        for route in light_rail_routes:
            route_lat = route.get("lat")
            route_lon = route.get("lon")
            if route_lat and route_lon:
                dist = haversine_distance(lat, lon, route_lat, route_lon)
                if dist <= (search_m / 1000.0):  # Within search radius
                    distances_km.append(dist)
    
    # Fallback to stops API if no route coordinates available
    if not distances_km:
        try:
            stops = get_nearby_transit_stops(lat, lon, radius_m=search_m) or {}
            items = stops.get("stops", []) or stops.get("items", []) or []
            # Use all stops as proxy (since we can't filter by route_type)
            for s in items:
                dist_m = s.get("distance_m")
                if isinstance(dist_m, (int, float)):
                    distances_km.append(dist_m / 1000.0)
                    continue
                stop_lat = s.get("lat")
                stop_lon = s.get("lon")
                if isinstance(stop_lat, (int, float)) and isinstance(stop_lon, (int, float)):
                    distances_km.append(haversine_distance(lat, lon, float(stop_lat), float(stop_lon)))
        except Exception:
            pass
    
    if distances_km:
        return min(distances_km)
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

    # Context-aware weighting by area type
    # Urban areas: emphasize rail (heavy + light rail)
    # Suburban areas: emphasize commuter rail (heavy rail)
    # Rural areas: value any service (bus, rail, etc.)
    
    # Calculate base scores with frequency + proximity enhancements
    heavy_rail_score = _score_heavy_rail_routes(heavy_rail_routes, lat, lon, area_type)
    light_rail_score = _score_light_rail_routes(light_rail_routes, lat, lon, area_type)
    bus_score = _score_bus_routes(bus_routes, lat, lon, area_type)
    
    # Apply area-type-specific weighting
    # Note: Individual mode scores are on 0-100 scale, but we want final score 0-100
    # If you can get everywhere by one mode (e.g., subway), other modes are redundant
    # Score based on best mode, not weighted average of all modes
    if area_type == 'urban_core':
        # Urban: Use best mode (usually heavy rail if available)
        # If heavy rail is excellent (70+), use it - bus doesn't matter
        # Only consider bus if heavy rail is weak/missing
        if heavy_rail_score >= 70.0:
            # Excellent heavy rail = you can get everywhere, bus is redundant
            total_score = heavy_rail_score
        elif heavy_rail_score > 0:
            # Some heavy rail but not excellent - use best of heavy rail or bus
            total_score = max(heavy_rail_score, bus_score)
        else:
            # No heavy rail - use best available (bus or light rail)
            total_score = max(bus_score, light_rail_score)
        total_score = min(100.0, total_score)
    elif area_type in ('suburban', 'exurban'):
        # Suburban: Heavy rail (commuter) 75%, Light rail 5%, Bus 20%
        # Commuter rail is primary for suburban areas
        weighted_sum = (heavy_rail_score * 0.75) + (light_rail_score * 0.05) + (bus_score * 0.2)
        # If no light rail, reallocate that weight to heavy rail
        if light_rail_score == 0:
            total_score = (heavy_rail_score * 0.8) + (bus_score * 0.2)
        else:
            total_score = weighted_sum
        total_score = min(100.0, total_score)
    elif area_type == 'rural':
        # Rural: Any service valued equally (33% each, max 90, bonus for multiple modes)
        total_score = (heavy_rail_score * 0.33) + (light_rail_score * 0.33) + (bus_score * 0.33)
        # Bonus for having multiple modes (any combination)
        mode_count = sum([1 for score in [heavy_rail_score, light_rail_score, bus_score] if score > 0])
        if mode_count >= 2:
            total_score += 10.0  # Bonus for multimodal access in rural areas
        total_score = min(100.0, total_score)
    else:
        # Default: balanced weighting (simple sum, each mode 0-100, cap at 100)
        total_score = heavy_rail_score + light_rail_score + bus_score
        total_score = min(100.0, total_score)

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

    # Record data sources used
    try:
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
    print(f"   🚇 Heavy Rail: {heavy_rail_score:.0f} ({len(heavy_rail_routes)} routes)")
    print(f"   🚊 Light Rail: {light_rail_score:.0f} ({len(light_rail_routes)} routes)")
    print(f"   🚌 Bus: {bus_score:.0f} ({len(bus_routes)} routes)")
    if area_type:
        print(f"   📍 Area type weighting: {area_type}")
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
        
        # Process routes and calculate distance to nearest stop
        processed_routes = []
        for route in routes:
            route_type = route.get("route_type")
            if route_type is None:
                continue
            
            # Try to get distance from route geometry or nearest stop
            route_distance_km = None
            route_lat = None
            route_lon = None
            
            # Check if route has geometry/coordinates
            geometry = route.get("geometry")
            if geometry and geometry.get("coordinates"):
                coords = geometry["coordinates"][0] if isinstance(geometry["coordinates"][0], list) else geometry["coordinates"]
                route_lon = coords[0]
                route_lat = coords[1]
                route_distance_km = haversine_distance(lat, lon, route_lat, route_lon)
            
            # If no geometry, we'll calculate distance from nearest stop in usefulness function
            processed_routes.append({
                "name": route.get("route_long_name") or route.get("route_short_name", "Unknown"),
                "short_name": route.get("route_short_name"),
                "route_type": route_type,
                "agency": route.get("agency", {}).get("agency_name", "Unknown"),
                "distance_km": route_distance_km,
                "lat": route_lat,
                "lon": route_lon,
                "route_id": route.get("onestop_id") or route.get("id")
            })
        
        print(f"   ℹ️  Found {len(processed_routes)} transit routes")
        
        return processed_routes
        
    except Exception as e:
        print(f"   ⚠️  Transit query error: {e}")
        return []


def _calculate_distance_factor(distance_km: float) -> float:
    """
    Calculate distance decay factor (0-1) using WalkScore-style smooth decay curve.
    
    WalkScore uses: 1.0 at 0m, ~0.8 at 400m, ~0.5 at 800m, ~0 at 1600m+
    """
    if distance_km <= 0.4:
        return 1.0 - (distance_km / 0.4) * 0.2  # 1.0 to 0.8
    elif distance_km <= 0.8:
        return 0.8 - ((distance_km - 0.4) / 0.4) * 0.3  # 0.8 to 0.5
    elif distance_km <= 1.6:
        return 0.5 - ((distance_km - 0.8) / 0.8) * 0.5  # 0.5 to 0
    else:
        return 0.0


def _calculate_route_type_usefulness(route_count: int, distance_km: float, 
                                     route_type: int) -> float:
    """
    Calculate usefulness for a route type (not per route).
    
    Usefulness = Distance_Factor × Route_Count_Factor × Base_Score
    
    Args:
        route_count: Number of routes of this type
        distance_km: Distance to nearest stop of this type
        route_type: 0=light rail, 1=subway, 2=rail, 3=bus
    
    Returns:
        Usefulness score (0-100+)
    """
    if route_count == 0:
        return 0.0
    
    # 1. Distance decay factor (0-1)
    distance_factor = _calculate_distance_factor(distance_km)
    
    # 2. Route count factor with diminishing returns
    # More routes = more destinations reachable, but with diminishing returns
    # sqrt(count) to avoid linear scaling (e.g., 4 routes ≠ 4x usefulness)
    route_count_factor = min(10.0, (route_count ** 0.5) * 2.0)  # Cap at ~10 routes worth
    
    # 3. Base score per route type (frequency proxy)
    # Heavy rail typically has higher frequency than bus
    if route_type in (1, 2):  # Heavy rail
        base_score = 10.0  # Higher base for heavy rail
    elif route_type == 0:  # Light rail
        base_score = 8.0
    else:  # Bus
        base_score = 6.0
    
    # Usefulness = Distance × Route_Count × Base
    usefulness = distance_factor * route_count_factor * base_score
    
    return usefulness


def _calculate_urban_transit_score(heavy_rail_routes: List[Dict],
                                   light_rail_routes: List[Dict],
                                   bus_routes: List[Dict],
                                   lat: float, lon: float) -> float:
    """
    Calculate urban transit score using route-type-based usefulness with area-type weighting.
    
    Calculate usefulness per route type, then combine with area-type-specific weights
    (matching suburban/rural logic for consistency).
    
    Args:
        heavy_rail_routes: List of heavy rail route dicts
        light_rail_routes: List of light rail route dicts
        bus_routes: List of bus route dicts
        lat, lon: Location coordinates
    
    Returns:
        Transit score (0-100)
    """
    # Get nearest stop distances for each route type
    # Use route coordinates if available, fallback to stops API
    nearest_hr_km = _nearest_heavy_rail_km(lat, lon, search_m=2500)
    nearest_lr_km = _nearest_light_rail_km(lat, lon, light_rail_routes, search_m=2000)
    nearest_bus_km = _nearest_bus_km(lat, lon, bus_routes, search_m=2000)
    
    # Calculate usefulness per route type
    heavy_rail_usefulness = _calculate_route_type_usefulness(
        len(heavy_rail_routes), 
        nearest_hr_km if nearest_hr_km < float('inf') else 2.0,
        1  # Heavy rail type
    )
    
    light_rail_usefulness = _calculate_route_type_usefulness(
        len(light_rail_routes),
        nearest_lr_km if nearest_lr_km < float('inf') else 2.0,
        0  # Light rail type
    )
    
    bus_usefulness = _calculate_route_type_usefulness(
        len(bus_routes),
        nearest_bus_km if nearest_bus_km < float('inf') else 2.0,
        3  # Bus type
    )
    
    # Normalize each usefulness to 0-100 scale
    # Useful values typically range 0-150+, so we normalize
    max_usefulness = 150.0  # Typical max for excellent transit
    heavy_rail_score = min(100.0, (heavy_rail_usefulness / max_usefulness) * 100.0)
    light_rail_score = min(100.0, (light_rail_usefulness / max_usefulness) * 100.0)
    bus_score = min(100.0, (bus_usefulness / max_usefulness) * 100.0)
    
    # Apply area-type-specific percentage weights (matching suburban logic)
    # Urban: Heavy rail 80%, Light rail 10%, Bus 20%
    # This matches suburban's emphasis on rail (75%/5%/20%)
    if light_rail_score == 0:
        # If no light rail, reallocate that weight to heavy rail
        total_score = (heavy_rail_score * 0.8) + (bus_score * 0.2)
    else:
        total_score = (heavy_rail_score * 0.8) + (light_rail_score * 0.1) + (bus_score * 0.2)
    
    return min(100.0, total_score)


def _score_heavy_rail_routes(routes: List[Dict], lat: float = None, lon: float = None, area_type: str = None) -> float:
    """Score heavy rail access based on route availability, frequency, and proximity."""
    if not routes:
        return 0.0
    
    count = len(routes)
    
    # Presence of heavy rail is huge (30 pts base)
    base_score = 30.0
    
    # Bonus for multiple lines (0-25 pts)
    # Higher cap to reward exceptional transit access (e.g., NYC with 12+ routes)
    if count >= 10:
        density_score = 25.0
    elif count >= 5:
        density_score = 20.0
    elif count >= 3:
        density_score = 15.0
    elif count >= 2:
        density_score = 10.0
    else:
        density_score = 5.0
    
    # Frequency bonus: more routes = higher frequency (0-30 pts)
    # Higher cap to reward exceptional transit access (e.g., NYC with 12+ stops)
    # Allows scores to reach 90-100 range when combined with other factors
    # Linear scaling: 1-5 stops → 2-10 pts, 6-10 stops → 12-20 pts, 10-15 stops → 20-30 pts, 15+ stops → 30 pts
    if count >= 15:
        frequency_bonus = 30.0
    elif count >= 10:
        frequency_bonus = 20.0 + ((count - 10) * 2.0)  # 20-30 pts for 10-15 stops
    elif count >= 5:
        frequency_bonus = 10.0 + ((count - 5) * 2.0)  # 10-20 pts for 5-10 stops
    else:
        frequency_bonus = min(10.0, count * 2.0)  # 2-10 pts for 1-5 stops
    
    # Proximity bonus: calculate distance to nearest stop (0-15 pts)
    # Higher bonus for very close stops (walking distance)
    proximity_bonus = 0.0
    if lat and lon:
        try:
            nearest_hr_km = _nearest_heavy_rail_km(lat, lon, search_m=2500)
            if nearest_hr_km < float('inf'):
                if nearest_hr_km <= 0.2:
                    proximity_bonus = 15.0  # Very close (<200m)
                elif nearest_hr_km <= 0.4:
                    proximity_bonus = 12.0  # Close (<400m)
                elif nearest_hr_km <= 0.5:
                    proximity_bonus = 10.0  # Walking distance
                elif nearest_hr_km <= 1.0:
                    proximity_bonus = 8.0
                elif nearest_hr_km <= 2.0:
                    proximity_bonus = 5.0
                elif nearest_hr_km <= 3.0:
                    proximity_bonus = 3.0
        except Exception:
            pass
    
    # Exceptional transit bonus: 10+ routes AND very close (<0.5km) = exceptional access
    # This rewards places like Park Slope with excellent subway access
    exceptional_bonus = 0.0
    if count >= 10 and proximity_bonus >= 10.0:
        exceptional_bonus = 10.0  # Bonus for exceptional transit access
    
    # Don't cap at 100 - allow scores above 100 for exceptional transit
    # This enables final weighted scores to reach 90-100 range (matching WalkScore)
    return base_score + density_score + frequency_bonus + proximity_bonus + exceptional_bonus


def _score_light_rail_routes(routes: List[Dict], lat: float = None, lon: float = None, area_type: str = None) -> float:
    """Score light rail access based on route availability, frequency, and proximity."""
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
    
    # Frequency bonus (0-5 pts)
    frequency_bonus = min(5.0, count * 1.5)
    
    # Proximity bonus (0-5 pts)
    proximity_bonus = 0.0
    if lat and lon:
        try:
            # Find nearest light rail stop
            from data_sources.transitland_api import get_nearby_transit_stops
            stops = get_nearby_transit_stops(lat, lon, radius_m=2000) or {}
            items = stops.get("stops", []) or stops.get("items", []) or []
            distances_km = []
            for s in items:
                rt = s.get("route_type")
                if rt == 0:  # Light rail/tram
                    dist_m = s.get("distance") or s.get("distance_m")
                    if isinstance(dist_m, (int, float)):
                        distances_km.append(dist_m / 1000.0)
            if distances_km:
                nearest_km = min(distances_km)
                if nearest_km <= 0.5:
                    proximity_bonus = 5.0
                elif nearest_km <= 1.0:
                    proximity_bonus = 3.0
                elif nearest_km <= 2.0:
                    proximity_bonus = 1.0
        except Exception:
            pass
    
    return min(100, base_score + density_score + frequency_bonus + proximity_bonus)


def _score_bus_routes(routes: List[Dict], lat: float = None, lon: float = None, area_type: str = None) -> float:
    """Score bus access based on route availability, frequency, and proximity."""
    if not routes:
        return 0.0
    
    count = len(routes)
    
    # Base score from route count (frequency proxy)
    if count >= 20:
        base_score = 25.0
    elif count >= 15:
        base_score = 23.0
    elif count >= 10:
        base_score = 20.0
    elif count >= 7:
        base_score = 17.0
    elif count >= 5:
        base_score = 15.0
    elif count >= 3:
        base_score = 12.0
    elif count >= 2:
        base_score = 10.0
    else:
        base_score = 7.0
    
    # Frequency bonus: more routes = higher frequency (0-5 pts)
    frequency_bonus = min(5.0, count * 0.25)
    
    # Proximity bonus (0-5 pts) - buses are more common, so proximity matters less
    proximity_bonus = 0.0
    if lat and lon and count > 0:
        # In urban areas, assume bus stops are nearby if routes exist
        if area_type == 'urban_core':
            proximity_bonus = 5.0  # Urban areas have dense bus coverage
        elif area_type in ('suburban', 'exurban'):
            proximity_bonus = 3.0  # Moderate proximity assumed
        else:
            proximity_bonus = 1.0
    
    return min(100, base_score + frequency_bonus + proximity_bonus)


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
    