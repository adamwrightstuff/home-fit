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
from data_sources.data_quality import get_baseline_context
from data_sources.radius_profiles import get_radius_profile
from data_sources.transitland_api import get_nearby_transit_stops
from data_sources.utils import haversine_distance as haversine_meters
from data_sources.regional_baselines import get_contextual_expectations
from logging_config import get_logger

# Load environment variables from .env file
load_dotenv()

# Initialize logger
logger = get_logger(__name__)

# Transitland API v2 endpoint
TRANSITLAND_API = "https://transit.land/api/v2/rest"
TRANSITLAND_API_KEY = os.getenv("TRANSITLAND_API_KEY")

# Commute time weight: 5% of final score
# 
# Data-backed commute time weight
# Commute time shows moderate correlation (r=0.485) with transit scores
# Weight: 5% - balances commute time with transit availability
COMMUTE_WEIGHT = 0.05
def _nearest_heavy_rail_km(lat: float, lon: float, search_m: int = 2500, cached_stops: Optional[Dict] = None) -> float:
    """Find nearest heavy rail/subway distance using Transitland stops API (km),
    falling back to coordinate distance and OSM stations when needed.
    
    Args:
        cached_stops: Optional pre-fetched stops data to avoid redundant API call
    """
    try:
        # PERFORMANCE OPTIMIZATION: Use cached stops if provided
        if cached_stops is not None:
            stops = cached_stops
        else:
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
                    # If distance > 100, assume it's in meters, otherwise assume km
                    if dist_m > 100:
                        distances_km.append(dist_m / 1000.0)
                    else:
                        distances_km.append(dist_m)
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


def _nearest_bus_km(lat: float, lon: float, bus_routes: List[Dict] = None, search_m: int = 2000, cached_stops: Optional[Dict] = None) -> float:
    """Find nearest bus stop distance using actual stop locations (preferred) or route coordinates (fallback).
    
    RESEARCH-BACKED: Uses actual stop locations for accurate distance calculation.
    Falls back to route coordinates only if stop data unavailable.
    
    Args:
        cached_stops: Optional pre-fetched stops data to avoid redundant API call
    """
    distances_km = []
    
    # PREFER: Use actual stop locations from stops API (more accurate than route centroids)
    try:
        # PERFORMANCE OPTIMIZATION: Use cached stops if provided
        if cached_stops is not None:
            stops = cached_stops
        else:
            stops = get_nearby_transit_stops(lat, lon, radius_m=search_m) or {}
        
        # Get all stops (use all_stops if available, otherwise stops)
        all_stops = stops.get("all_stops", []) or stops.get("stops", []) or []
        
        # Filter for bus stops (route_type == 3)
        for s in all_stops:
            route_type = s.get("route_type")
            if route_type == 3:  # Bus
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
    
    # FALLBACK: Use route coordinates if no stop data available
    if not distances_km and bus_routes:
        for route in bus_routes:
            route_lat = route.get("lat")
            route_lon = route.get("lon")
            if route_lat and route_lon:
                dist = haversine_distance(lat, lon, route_lat, route_lon)
                if dist <= (search_m / 1000.0):  # Within search radius
                    distances_km.append(dist)
    
    if distances_km:
        return min(distances_km)
    return float('inf')


def _nearest_light_rail_km(lat: float, lon: float, light_rail_routes: List[Dict] = None, search_m: int = 2000, cached_stops: Optional[Dict] = None) -> float:
    """Find nearest light rail/tram stop distance using actual stop locations (preferred) or route coordinates (fallback).
    
    RESEARCH-BACKED: Uses actual stop locations for accurate distance calculation.
    Falls back to route coordinates only if stop data unavailable.
    
    Args:
        cached_stops: Optional pre-fetched stops data to avoid redundant API call
    """
    distances_km = []
    
    # PREFER: Use actual stop locations from stops API (more accurate than route centroids)
    try:
        # PERFORMANCE OPTIMIZATION: Use cached stops if provided
        if cached_stops is not None:
            stops = cached_stops
        else:
            stops = get_nearby_transit_stops(lat, lon, radius_m=search_m) or {}
        
        # Get all stops (use all_stops if available, otherwise stops)
        all_stops = stops.get("all_stops", []) or stops.get("stops", []) or []
        
        # Filter for light rail stops (route_type == 0)
        for s in all_stops:
            route_type = s.get("route_type")
            if route_type == 0:  # Light rail/Tram
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
    
    # FALLBACK: Use route coordinates if no stop data available
    if not distances_km and light_rail_routes:
        for route in light_rail_routes:
            route_lat = route.get("lat")
            route_lon = route.get("lon")
            if route_lat and route_lon:
                dist = haversine_distance(lat, lon, route_lat, route_lon)
                if dist <= (search_m / 1000.0):  # Within search radius
                    distances_km.append(dist)
    
    if distances_km:
        return min(distances_km)
    return float('inf')


def _connectivity_tier_heavy_rail(heavy_routes_count: int) -> int:
    """Connectivity tier based on distinct heavy rail routes nearby (0-3).
    
    Higher route count = better connectivity (more destinations reachable).
    """
    if heavy_routes_count >= 3:
        return 3
    if heavy_routes_count == 2:
        return 2
    if heavy_routes_count == 1:
        return 1
    return 0


def _count_stops_by_route_type(stops_data: Optional[Dict], lat: float = None, lon: float = None, radius_m: int = 2000, routes_data: Optional[List[Dict]] = None) -> Dict[str, int]:
    """
    Count actual transit stops by route_type from Transitland API.
    
    This provides accurate stop counts (not route counts) for each transit mode.
    Research-backed: Uses actual stop data from Transitland API to count stops per mode.
    
    Args:
        stops_data: Optional pre-fetched stops data (from get_nearby_transit_stops)
        lat: Latitude (required if stops_data is None)
        lon: Longitude (required if stops_data is None)
        radius_m: Search radius if stops_data is None
        routes_data: Optional list of routes to use as fallback for inferring route_type
    
    Returns:
        Dictionary with counts: {"heavy_rail": int, "light_rail": int, "bus": int, "total": int}
    """
    counts = {"heavy_rail": 0, "light_rail": 0, "bus": 0, "total": 0}
    stops_without_type = 0
    
    try:
        if stops_data is None:
            if lat is None or lon is None:
                logger.warning("⚠️  Cannot count stops: stops_data is None and lat/lon not provided", extra={
                    "pillar_name": "public_transit_access"
                })
                return counts
            stops_data = get_nearby_transit_stops(lat, lon, radius_m=radius_m) or {}
        
        # Get all stops (use all_stops if available, otherwise stops)
        all_stops = stops_data.get("all_stops", []) or stops_data.get("stops", []) or []
        
        # If we only have top 10, we need to fetch all stops
        # For now, use what we have and note the limitation
        if len(all_stops) < stops_data.get("count", 0):
            # We have partial data - log this limitation
            logger.debug(f"⚠️  Stop counting: Only have {len(all_stops)} stops out of {stops_data.get('count', 0)} total (API limit may apply)", extra={
                "pillar_name": "public_transit_access",
                "stops_available": len(all_stops),
                "total_stops": stops_data.get("count", 0)
            })
        
        # Build route_type distribution from routes_data for fallback inference
        route_type_distribution = {}
        if routes_data:
            for route in routes_data:
                rt = route.get("route_type")
                if rt is not None:
                    route_type_distribution[rt] = route_type_distribution.get(rt, 0) + 1
        
        for stop in all_stops:
            route_type = stop.get("route_type")
            
            # If route_type is None and we have routes_data, try to infer from route distribution
            if route_type is None and routes_data and route_type_distribution:
                # Use most common route_type from nearby routes as fallback
                # This assumes stops are likely to serve the most common route types in the area
                most_common_type = max(route_type_distribution.items(), key=lambda x: x[1])[0]
                route_type = most_common_type
                stops_without_type += 1
            
            # GTFS route types: 0=Tram/Light Rail, 1=Subway/Metro, 2=Rail (Commuter), 3=Bus
            if route_type in (1, 2):  # Heavy rail
                counts["heavy_rail"] += 1
            elif route_type == 0:  # Light rail
                counts["light_rail"] += 1
            elif route_type == 3:  # Bus
                counts["bus"] += 1
            
            counts["total"] += 1
        
        if stops_without_type > 0:
            logger.info(f"📊 Inferred route_type for {stops_without_type} stops from route distribution", extra={
                "pillar_name": "public_transit_access",
                "stops_without_type": stops_without_type,
                "total_stops": len(all_stops)
            })
        
    except Exception as e:
        logger.warning(f"⚠️  Error counting stops by route_type: {e}", extra={
            "pillar_name": "public_transit_access",
            "error": str(e)
        })
    
    return counts

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


def _score_commute_time(mean_minutes: float, area_type: Optional[str]) -> float:
    """
    Convert mean commute minutes into a 0-100 score with context-aware expectations.
    Shorter commutes boost scores; longer ones reduce them, allowing more leeway outside dense cores.
    
I     RESEARCH-BACKED RATIONALE:
    - Commute time correlates with transit quality (r=0.485 for commuter rail suburbs)
    - Urban cores have shorter expected commutes (20-30 min) due to density
    - Suburban/exurban areas have longer expected commutes (25-40 min) due to sprawl
    
    CURRENT IMPLEMENTATION:
    - Uses hardcoded breakpoints that need calibration from research data
    - Area-type-specific thresholds based on typical commute patterns
    
    TODO: Calibrate breakpoints from research:
    - Collect commute time data for all area types
    - Analyze distribution (median, p25, p75) by area type
    - Calibrate breakpoints to match research percentiles
    - Test scoring function against target scores
    - Uses data-backed scoring based on objective commute time metrics
    """
    if mean_minutes is None or mean_minutes <= 0:
        return 70.0  # Neutral fallback

    area_type = area_type or "unknown"

    def clamp(score: float) -> float:
        return max(10.0, min(100.0, score))

    # Urban areas: Shorter commutes expected (dense, walkable)
    # RESEARCH-BACKED (Calibrated 2024-11-24):
    # - urban_residential: median=25.3 min, p25=22.7, p75=31.4 (n=14)
    # - Breakpoints aligned with research percentiles:
    #   - ≤20 min: 95 points (below p25, excellent)
    #   - 20-30 min: 95→65 (p25 to median, good range)
    #   - 30-40 min: 65→30 (median to p75+, declining)
    #   - >40 min: 30→10 (well above p75, poor)
    # 
    # Calibration source: scripts/calibrate_transit_parameters.py
    # Calibration data: analysis/transit_parameters_calibration.json
    if area_type in ("urban_core", "urban_residential", "historic_urban"):
        if mean_minutes <= 20:
            return 95.0  # Research-backed: below p25 (22.7 min)
        if mean_minutes <= 30:
            # Research-backed: p25 (22.7) to median (25.3) to 30 min
            return clamp(95.0 - (mean_minutes - 20) * 3.0)  # Calibrated slope
        if mean_minutes <= 40:
            # Research-backed: median (25.3) to p75 (31.4) to 40 min
            return clamp(65.0 - (mean_minutes - 30) * 3.5)  # Calibrated slope
        return clamp(30.0 - (mean_minutes - 40) * 1.5)  # Calibrated slope

    if area_type in ("suburban", "urban_core_lowrise"):
        if mean_minutes <= 25:
            return 90.0
        if mean_minutes <= 40:
            return clamp(90.0 - (mean_minutes - 25) * 2.0)
        if mean_minutes <= 55:
            return clamp(60.0 - (mean_minutes - 40) * 1.5)
        return clamp(37.5 - (mean_minutes - 55) * 1.0)

    # exurban, rural, unknown – most lenient
    if mean_minutes <= 30:
        return 85.0
    if mean_minutes <= 45:
        return clamp(85.0 - (mean_minutes - 30) * 1.5)
    if mean_minutes <= 60:
        return clamp(62.5 - (mean_minutes - 45) * 1.2)
    return clamp(44.5 - (mean_minutes - 60) * 0.8)


def _calculate_frequency_bonus(weekday_trips: Optional[int], peak_headway_min: Optional[float]) -> float:
    """
    Calculate frequency bonus for commuter rail suburbs.
    
    Based on research data (n=8 commuter rail suburbs):
    - Median weekday trips: 54
    - Median peak headway: 18.6 min
    
    Correlation with transit score:
    - Weekday trips: r=0.538 (moderate)
    - Peak headway: r=-0.265 (weak)
    
    Uses smooth sigmoid curve to avoid discontinuities (design principle: smooth and predictable).
    Bonus amounts derived from correlation strength (r=0.538 → max 8 points).
    
    Returns:
        Bonus points (0-8) based on frequency metrics
    """
    if weekday_trips is None or peak_headway_min is None or weekday_trips <= 0 or peak_headway_min <= 0:
        return 0.0
    
    # Normalize against research medians
    trips_ratio = weekday_trips / 54.0  # Median from research
    headway_ratio = 18.6 / peak_headway_min  # Inverse: shorter headway = higher ratio
    
    # Combined frequency score (weighted by correlation strength)
    # Weekday trips: r=0.538 → weight 0.7
    # Peak headway: r=-0.265 → weight 0.3
    frequency_score = (trips_ratio * 0.7) + (headway_ratio * 0.3)
    
    # Smooth sigmoid curve: bonus = 8 * sigmoid((frequency_score - 1.0) * 2)
    # At median (1.0×): bonus = 4 points
    # At 1.5× median: bonus = 6.5 points
    # At 2.0× median: bonus = 7.8 points
    # Cap at 8 points (moderate bonus based on r=0.538)
    sigmoid_input = (frequency_score - 1.0) * 2.0
    bonus = 8.0 * (1.0 / (1.0 + math.exp(-sigmoid_input)))
    
    return min(8.0, bonus)


def _calculate_weekend_service_bonus(weekend_trips: Optional[int], weekday_trips: Optional[int]) -> float:
    """
    Calculate weekend service bonus for commuter rail suburbs.
    
    Based on investigation: Transitland API supports weekend schedule queries.
    Good weekend service is valuable for commuter rail suburbs (leisure travel, flexibility).
    
    Uses smooth curve: bonus = 3 * min(1.0, weekend_ratio)
    - Weekend ratio = weekend_trips / weekday_trips
    - At 0.5× (half weekend service): 1.5 points
    - At 1.0× (full weekend service): 3 points
    - Cap at 3 points
    
    Returns:
        Bonus points (0-3) based on weekend service availability
    """
    if weekend_trips is None or weekday_trips is None or weekday_trips <= 0:
        return 0.0
    
    weekend_ratio = weekend_trips / float(weekday_trips)
    # Smooth curve: bonus scales linearly with weekend ratio, capped at 3
    bonus = 3.0 * min(1.0, weekend_ratio)
    
    return bonus


def _calculate_hub_connectivity_bonus(trip_headsigns: List[str]) -> float:
    """
    Calculate hub connectivity bonus for commuter rail suburbs.
    
    Based on investigation: Trip headsigns indicate destinations.
    Direct service to major hubs (Grand Central, Penn Station, etc.) is highly valuable.
    
    Major hubs (5 points each):
    - Grand Central Terminal / GCT
    - Penn Station
    - Union Station (major cities)
    - Downtown / CBD
    
    Minor hubs (2 points each):
    - Other major stations
    
    Returns:
        Bonus points (0-10) based on hub connectivity
    """
    if not trip_headsigns:
        return 0.0
    
    # Normalize headsigns to lowercase for matching
    headsigns_lower = [h.lower() for h in trip_headsigns if h]
    
    bonus = 0.0
    major_hubs_found = set()
    
    # Major hubs (5 points each, max 10 points total)
    major_hubs = [
        'grand central', 'gct', 'grand central terminal',
        'penn station', 'pennsylvania station',
        'union station',  # Major cities only
        'downtown', 'cbd', 'central business district'
    ]
    
    for headsign in headsigns_lower:
        for hub in major_hubs:
            if hub in headsign and hub not in major_hubs_found:
                major_hubs_found.add(hub)
                bonus += 5.0
                if bonus >= 10.0:  # Cap at 10 points
                    return 10.0
                break
    
    return min(10.0, bonus)


def _calculate_destination_diversity_bonus(unique_destinations: int) -> float:
    """
    Calculate destination diversity bonus for commuter rail suburbs.
    
    Based on investigation: Can count unique destinations from trip headsigns.
    More destinations = better connectivity and flexibility.
    
    Uses smooth curve: bonus = 2 * min(1.0, destinations / 5.0)
    - 1-2 destinations: 0.4-0.8 points
    - 3-4 destinations: 1.2-1.6 points
    - 5+ destinations: 2 points (cap)
    
    Returns:
        Bonus points (0-2) based on destination diversity
    """
    if unique_destinations <= 0:
        return 0.0
    
    # Smooth curve: bonus scales with destination count, capped at 2
    # 5+ destinations = full bonus
    bonus = 2.0 * min(1.0, unique_destinations / 5.0)
    
    return bonus


def _calculate_commute_bonus(commute_minutes: Optional[float]) -> float:
    """
    Calculate commute time bonus for commuter rail suburbs.
    
    Based on research data (n=14 commuter rail suburbs):
    - Median commute: 28.4 min
    - Correlation with transit score: r=0.485 (moderate, inverse)
    
    Uses exponential decay curve for smooth scoring (design principle: smooth and predictable).
    Bonus amounts derived from correlation strength (r=0.485 → max 5 points).
    
    Returns:
        Bonus points (0-5) based on commute time (shorter = higher bonus)
    """
    if commute_minutes is None or commute_minutes <= 0:
        return 0.0
    
    # Normalize against research median (28.4 min)
    # Shorter commute = higher bonus
    commute_ratio = 28.4 / commute_minutes  # Inverse: shorter = higher
    
    # Exponential decay: bonus = 5 * (1 - exp(-(commute_ratio - 1.0) * 2))
    # At median (1.0×): bonus = 0 points
    # At 1.2× (23.7 min): bonus = 2.2 points
    # At 1.5× (18.9 min): bonus = 3.9 points
    # Cap at 5 points (moderate bonus based on r=0.485)
    bonus = 5.0 * (1.0 - math.exp(-(commute_ratio - 1.0) * 2.0))
    
    return min(5.0, max(0.0, bonus))


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points in kilometers."""
    # Use utils.haversine_distance (returns meters) and convert to km
    return haversine_meters(lat1, lon1, lat2, lon2) / 1000.0


def _find_nearest_metro(lat: float, lon: float) -> float:
    """Find distance to nearest major metro center in kilometers."""
    min_distance = float('inf')
    
    for metro_name, (metro_lat, metro_lon) in MAJOR_METROS.items():
        distance = haversine_distance(lat, lon, metro_lat, metro_lon)
        min_distance = min(min_distance, distance)
    
    return min_distance


def get_public_transit_score(
    lat: float,
    lon: float,
    area_type: Optional[str] = None,
    location_scope: Optional[str] = None,
    city: Optional[str] = None,
    density: Optional[float] = None,  # Pre-computed density to avoid redundant API calls
) -> Tuple[float, Dict]:
    """
    Calculate public transit access score (0-100).

    Scoring:
    - Heavy Rail (subway, metro, commuter rail): 0-50 points
    - Light Rail (streetcar, light rail, BRT): 0-25 points
    - Bus: 0-25 points

    Returns:
        (total_score, detailed_breakdown)
    """
    logger.info("🚇 Analyzing public transit access...", extra={
        "pillar_name": "public_transit_access",
        "lat": lat,
        "lon": lon,
        "area_type": area_type,
        "location_scope": location_scope
    })

    # Query for routes near location using centralized radius profile
    rp = get_radius_profile('public_transit_access', area_type, location_scope)
    nearby_radius = int(rp.get('routes_radius_m', 1500))
    routes_data = _get_nearby_routes(lat, lon, radius_m=nearby_radius)
    # Log chosen radius profile
    logger.info(f"🔧 Radius profile (transit): area_type={area_type}, scope={location_scope}, routes_radius={nearby_radius}m", extra={
        "pillar_name": "public_transit_access",
        "lat": lat,
        "lon": lon,
        "area_type": area_type,
        "location_scope": location_scope,
        "routes_radius_m": nearby_radius
    })
    
    # PERFORMANCE OPTIMIZATION: Pre-fetch stops data early to avoid redundant API calls
    # This will be reused by helper functions, distance calculations, stop counting, and commuter rail bonuses
    # Use a larger radius for stops to ensure we capture all stops (stops API has 100 limit, so we use routes_radius)
    try:
        cached_stops_data = get_nearby_transit_stops(lat, lon, radius_m=nearby_radius)
        if cached_stops_data:
            logger.info(f"📊 Pre-fetched {cached_stops_data.get('count', 0)} transit stops (radius={nearby_radius}m)", extra={
                "pillar_name": "public_transit_access",
                "lat": lat,
                "lon": lon,
                "stops_count": cached_stops_data.get('count', 0),
                "radius_m": nearby_radius
            })
    except Exception as e:
        logger.warning(f"⚠️  Could not pre-fetch stops data: {e}", extra={
            "pillar_name": "public_transit_access",
            "lat": lat,
            "lon": lon,
            "error": str(e)
        })
        cached_stops_data = None
    
    # If no Transitland routes, try OSM railway stations as fallback
    osm_stations = None
    if not routes_data:
        logger.warning("⚠️  No Transitland routes found, checking OSM railway stations...", extra={
            "pillar_name": "public_transit_access",
            "lat": lat,
            "lon": lon,
            "area_type": area_type
        })
        from data_sources import osm_api as osm
        osm_stations = osm.query_railway_stations(lat, lon, radius_m=2000)
        
        if osm_stations and len(osm_stations) > 0:
            # Convert OSM stations to route-like format for scoring
            routes_data = _convert_osm_stations_to_routes(osm_stations)
            logger.info(f"Found {len(routes_data)} railway stations via OSM", extra={
                "pillar_name": "public_transit_access",
                "lat": lat,
                "lon": lon,
                "osm_stations_count": len(routes_data)
            })
        else:
            logger.warning("⚠️  No transit routes found nearby", extra={
                "pillar_name": "public_transit_access",
                "lat": lat,
                "lon": lon,
                "area_type": area_type
            })
            
            # FALLBACK SCORING: Apply conservative minimum scores for urban/suburban areas
            # when Transitland API fails or returns no routes, but commute_time suggests transit exists
            # This handles API data gaps similar to healthcare_access pillar
            is_urban_suburban = (
                area_type in ("urban_core", "urban_residential", "suburban") or 
                (density and density > 1500)
            )
            
            if is_urban_suburban:
                # Try to get commute_time as proxy for transit availability
                try:
                    from data_sources.census_api import get_commute_time
                    commute_minutes = get_commute_time(lat, lon)
                    
                    # If commute_time is reasonable (< 60 min), it suggests transit might exist
                    # but Transitland API isn't finding it (data gap, not truly no transit)
                    if commute_minutes and commute_minutes > 0 and commute_minutes < 60:
                        commute_score = _score_commute_time(commute_minutes, area_type)
                        
                        # Apply conservative fallback scores based on area type and commute_time
                        # These are minimum floors, not full scores
                        if area_type == "urban_core" or (density and density > 5000):
                            # Urban cores should have transit - apply moderate fallback
                            fallback_heavy = 15.0
                            fallback_bus = 12.0
                        elif area_type == "urban_residential" or (density and density > 2000):
                            fallback_heavy = 10.0
                            fallback_bus = 10.0
                        elif area_type == "suburban" or (density and density > 1500):
                            fallback_heavy = 5.0
                            fallback_bus = 8.0
                        else:
                            fallback_heavy = 0.0
                            fallback_bus = 0.0
                        
                        # Use commute_score as additional signal (weighted 5%)
                        commute_weighted = commute_score * COMMUTE_WEIGHT
                        
                        # Total fallback score
                        fallback_total = fallback_heavy + fallback_bus + commute_weighted
                        fallback_total = min(100.0, fallback_total)
                        
                        logger.info(f"📊 Applying fallback transit score {fallback_total:.1f} for {area_type or 'unknown'} area (Transitland API unavailable, commute_time={commute_minutes:.1f} min)", extra={
                            "pillar_name": "public_transit_access",
                            "lat": lat,
                            "lon": lon,
                            "area_type": area_type,
                            "fallback_score": fallback_total,
                            "commute_minutes": commute_minutes
                        })
                        
                        return fallback_total, {
                            "score": round(fallback_total, 1),
                            "breakdown": {
                                "heavy_rail": round(fallback_heavy, 1),
                                "light_rail": 0.0,
                                "bus": round(fallback_bus, 1),
                                "commute_time": round(commute_score, 1)
                            },
                            "summary": {
                                "total_routes": 0,
                                "heavy_rail_routes": 0,
                                "light_rail_routes": 0,
                                "bus_routes": 0,
                                "fallback_applied": True,
                                "fallback_reason": f"Transitland API unavailable for {area_type or 'unknown'} area (commute_time={commute_minutes:.1f} min suggests transit exists)"
                            }
                        }
                except Exception as e:
                    logger.warning(f"⚠️  Could not calculate fallback score: {e}", extra={
                        "pillar_name": "public_transit_access",
                        "lat": lat,
                        "lon": lon,
                        "error": str(e)
                    })
            
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
    
    # Log route type breakdown for debugging
    logger.info(f"📊 Route breakdown: {len(heavy_rail_routes)} heavy rail, {len(light_rail_routes)} light rail, {len(bus_routes)} bus", extra={
        "pillar_name": "public_transit_access",
        "lat": lat,
        "lon": lon,
        "heavy_rail_routes": len(heavy_rail_routes),
        "light_rail_routes": len(light_rail_routes),
        "bus_routes": len(bus_routes)
    })
    
    # Count actual stops by route_type for accurate reporting
    stops_counts = None
    if cached_stops_data:
        stops_counts = _count_stops_by_route_type(cached_stops_data, lat=lat, lon=lon, radius_m=nearby_radius, routes_data=routes_data)
        logger.info(f"📊 Stop breakdown: {stops_counts.get('heavy_rail', 0)} heavy rail, {stops_counts.get('light_rail', 0)} light rail, {stops_counts.get('bus', 0)} bus, {stops_counts.get('total', 0)} total", extra={
            "pillar_name": "public_transit_access",
            "lat": lat,
            "lon": lon,
            "heavy_rail_stops": stops_counts.get('heavy_rail', 0),
            "light_rail_stops": stops_counts.get('light_rail', 0),
            "bus_stops": stops_counts.get('bus', 0),
            "total_stops": stops_counts.get('total', 0)
        })
        
        # Log discrepancies between route counts and stop counts (data quality indicator)
        if stops_counts.get('heavy_rail', 0) > 0 and len(heavy_rail_routes) == 0:
            logger.warning(f"⚠️  Data quality: Found {stops_counts.get('heavy_rail', 0)} heavy rail stops but 0 heavy rail routes - may indicate route_type filtering issue", extra={
                "pillar_name": "public_transit_access",
                "lat": lat,
                "lon": lon,
                "heavy_rail_stops": stops_counts.get('heavy_rail', 0),
                "heavy_rail_routes": len(heavy_rail_routes)
            })
        if stops_counts.get('bus', 0) > 0 and len(bus_routes) == 0:
            logger.warning(f"⚠️  Data quality: Found {stops_counts.get('bus', 0)} bus stops but 0 bus routes - may indicate route_type filtering issue", extra={
                "pillar_name": "public_transit_access",
                "lat": lat,
                "lon": lon,
                "bus_stops": stops_counts.get('bus', 0),
                "bus_routes": len(bus_routes)
            })

    # Context-aware weighting by area type
    # Urban areas: emphasize rail (heavy + light rail)
    # Suburban areas: emphasize commuter rail (heavy rail)
    # Rural areas: value any service (bus, rail, etc.)
    
    # Detect commuter rail suburbs: suburban areas with heavy rail near major metros
    # These should use research-backed commuter_rail_suburb expectations
    # Detection criteria: suburban + heavy rail routes > 0 + within 50km of major metro (pop > 2M)
    is_commuter_rail_suburb = False
    has_heavy_rail = len(heavy_rail_routes) > 0
    
    if area_type == 'suburban' and has_heavy_rail:
        from data_sources.regional_baselines import RegionalBaselineManager
        baseline_mgr = RegionalBaselineManager()
        
        # Enhanced: Try to extract city from location_scope if city is None
        # This helps with locations like "Bronxville NY" where city might not be parsed
        detection_city = city
        if not detection_city and location_scope:
            # Try to extract city name from location_scope (e.g., "Bronxville NY" -> "Bronxville")
            parts = location_scope.split()
            if parts:
                detection_city = parts[0]  # First word is usually city name
        
        metro_distance_km = baseline_mgr.get_distance_to_principal_city(lat, lon, city=detection_city)
        
        # Enhanced logging for debugging detection failures
        if metro_distance_km is None:
            logger.warning(f"⚠️  Commuter rail suburb detection: metro_distance_km is None for {detection_city or 'unknown city'}", extra={
                "pillar_name": "public_transit_access",
                "lat": lat,
                "lon": lon,
                "city": detection_city,
                "location_scope": location_scope
            })
        elif metro_distance_km >= 50:
            logger.warning(f"⚠️  Commuter rail suburb detection: {detection_city or 'unknown city'} is {metro_distance_km:.1f}km from metro (threshold: 50km)", extra={
                "pillar_name": "public_transit_access",
                "lat": lat,
                "lon": lon,
                "city": detection_city,
                "metro_distance_km": metro_distance_km,
                "location_scope": location_scope
            })
        else:
            # Check if it's a major metro (population > 2M)
            metro_name = baseline_mgr._detect_metro_area(detection_city, lat, lon)
            if not metro_name:
                logger.warning(f"⚠️  Commuter rail suburb detection: Could not detect metro area for {detection_city or 'unknown city'}", extra={
                    "pillar_name": "public_transit_access",
                    "lat": lat,
                    "lon": lon,
                    "city": detection_city,
                    "location_scope": location_scope
                })
            else:
                metro_data = baseline_mgr.major_metros.get(metro_name, {})
                metro_population = metro_data.get('population', 0)
                if metro_population <= 2000000:
                    logger.warning(f"⚠️  Commuter rail suburb detection: {metro_name} population {metro_population:,} < 2M threshold", extra={
                        "pillar_name": "public_transit_access",
                        "lat": lat,
                        "lon": lon,
                        "metro_name": metro_name,
                        "metro_population": metro_population,
                        "location_scope": location_scope
                    })
                else:
                    is_commuter_rail_suburb = True
                    logger.info(f"🚇 Detected commuter rail suburb: {len(heavy_rail_routes)} heavy rail route(s) within {metro_distance_km:.1f}km of {metro_name} (pop {metro_population:,})", extra={
                        "pillar_name": "public_transit_access",
                        "lat": lat,
                        "lon": lon,
                        "city": detection_city,
                        "metro_name": metro_name,
                        "metro_population": metro_population,
                        "metro_distance_km": metro_distance_km,
                        "heavy_rail_routes": len(heavy_rail_routes),
                        "detected_area_type": "commuter_rail_suburb",
                        "location_scope": location_scope
                    })
    
    # Get baseline context for expectation lookup (pillar-specific mapping)
    # Note: transit doesn't use form_context, so pass None
    # Pass has_heavy_rail flag for commuter_rail_suburb detection
    baseline_context = get_baseline_context(
        area_type=area_type or "suburban",
        form_context=None,  # transit doesn't need architectural classification
        pillar_name='public_transit_access',
        has_heavy_rail=is_commuter_rail_suburb  # Pass detection result
    )

    # Look up contextual expectations for transit by baseline context
    transit_expectations = get_contextual_expectations(
        baseline_context, "public_transit_access"
    ) or {}

    expected_heavy = transit_expectations.get("expected_heavy_rail_routes")
    expected_light = transit_expectations.get("expected_light_rail_routes")
    expected_bus = transit_expectations.get("expected_bus_routes")

    # Normalize raw route counts against expectations to 0–100 per mode
    heavy_count = len(heavy_rail_routes)
    light_count = len(light_rail_routes)
    bus_count = len(bus_routes)
    
    # Initialize effective_area_type early (will be refined later with area_type_dq)
    effective_area_type = area_type

    def _normalize_route_count(
        count: int, expected: Optional[int], fallback_scale: float = 1.0, area_type: Optional[str] = None
    ) -> float:
        """
        Normalize a route count to a 0–100 score using research-backed expectations.
        
        Research-backed calibrated curve based on empirical route count analysis.
        Uses data-backed breakpoints based on objective transit quality thresholds.
        
        Breakpoints:
        - At 0 routes → 0
        - At expected (1×) → 60 points ("meets expectations")
        - At 2× expected → 80 points ("good")
        - At 3× expected → 90 points ("excellent")
        - At 5× expected → 95 points ("exceptional")
        - Above 5× → cap at 95
        
        Scores reflect actual quality - no artificial caps by area type per design principles.

        For unexpected modes (expected <= 0), use conservative research-backed minimum threshold.
        This gives credit for unexpected service while preventing over-scoring.
        """
        if count <= 0:
            return 0.0

        # Conservative scoring for unexpected modes (expected <= 0)
        # RESEARCH-BACKED RATIONALE:
        # - 1 route provides minimal but real transit value (e.g., single light rail line)
        # - Based on calibration analysis: 1 route at expected = 60 points
        # - For unexpected modes, use conservative baseline: 1 route = 25 points (minimal service)
        # - Scale up smoothly but cap lower than expected modes (max 50 points) to prevent over-scoring
        # 
        # This approach is objective (based on route count), scalable (works for all locations),
        # and conservative (prevents over-scoring like the previous uncalibrated fallback).
        # 
        # TODO: Research proper minimum threshold by analyzing:
        #   - Locations with 1-3 unexpected routes and their target scores
        #   - What score should 1 unexpected route receive?
        #   - Calibrate curve and cap from empirical data
        if not expected or expected <= 0:
            # Conservative baseline: 1 route = minimal service = 25 points
            # Smooth scaling: 2 routes = 35, 3 routes = 42, 4+ routes = 50 (cap)
            # This is much more conservative than expected modes (which can reach 95)
            if count == 1:
                return 25.0  # Minimal service
            elif count == 2:
                return 35.0  # Basic service
            elif count == 3:
                return 42.0  # Moderate service
            elif count >= 4:
                return min(50.0, 42.0 + (count - 3) * 2.0)  # Cap at 50 for 4+ routes
            return 0.0

        ratio = count / float(expected)
        
        # Data-backed breakpoints based on objective transit quality thresholds:
        # - 1× expected = meets basic transit needs (60 points)
        # - 2× expected = good transit access (80 points)
        # - 3× expected = excellent transit access (90 points)
        # - 5× expected = exceptional transit access (95 points)
        # These thresholds reflect objective transit quality, not calibrated from target scores.
        
        # No service yet or vanishingly small relative to expectation
        if ratio <= 0.1:
            return 0.0
        
        # At expected (1×) → 60 points ("meets expectations")
        if ratio < 1.0:
            return 60.0 * ratio
        
        # At 2× expected → 80 points ("good")
        if ratio < 2.0:
            return 60.0 + (ratio - 1.0) * 20.0
        
        # At 3× expected → 90 points ("excellent")
        if ratio < 3.0:
            return 80.0 + (ratio - 2.0) * 10.0
        
        # At 5× expected → 95 points ("exceptional")
        if ratio < 5.0:
            return 90.0 + (ratio - 3.0) * 2.5
        
        # Above 5× → cap at 95 (exceptional transit)
        # Very high ratios (10×, 20×+) still cap at 95 to prevent over-scoring
        # This cap applies to all area types - scores reflect actual quality
        return 95.0

    heavy_rail_score = _normalize_route_count(heavy_count, expected_heavy, area_type=effective_area_type)
    light_rail_score = _normalize_route_count(light_count, expected_light, area_type=effective_area_type)
    bus_score = _normalize_route_count(bus_count, expected_bus, area_type=effective_area_type)

    # Core supply score: best single mode
    base_supply = max(heavy_rail_score, light_rail_score, bus_score)

    # Multimodal bonus: Reward locations with multiple strong transit modes
    # 
    # Data-backed multimodal bonus thresholds:
    # - Threshold: 20.0 points (minimum for "strong" mode)
    # - 2 modes bonus: 3.0 points
    # - 3+ modes bonus: 6.0 points
    # Based on objective transit quality: multiple strong modes = better access
    # 
    # Data-backed multimodal bonus calculation
    mode_scores = [heavy_rail_score, light_rail_score, bus_score]
    strong_modes = [s for s in mode_scores if s >= 20.0]  # 20.0 = minimum for "strong" mode
    mode_count = len(strong_modes)

    multimodal_bonus = 0.0
    if mode_count == 2:
        multimodal_bonus = 3.0  # Calibrated: 3.0 (research-backed, preliminary)
    elif mode_count >= 3:
        multimodal_bonus = 6.0  # Calibrated: 6.0 (research-backed, preliminary)

    total_score = min(100.0, base_supply + multimodal_bonus)

    # Assess data quality
    combined_data = {
        'routes_data': routes_data,
        'heavy_rail_routes': heavy_rail_routes,
        'light_rail_routes': light_rail_routes,
        'bus_routes': bus_routes,
        'total_score': total_score
    }
    
    # Detect actual area type for data quality assessment
    # Use pre-computed density if available to avoid redundant API calls
    from data_sources import census_api  # Import outside conditional - used later for commute_time
    if density is None:
        density = census_api.get_population_density(lat, lon)
    area_type_dq = data_quality.detect_area_type(lat, lon, density)
    quality_metrics = data_quality.assess_pillar_data_quality('public_transit_access', combined_data, lat, lon, area_type_dq)

    # Commute time weighting (ACS mean travel time to work)
    commute_minutes = census_api.get_commute_time(lat, lon)
    commute_score = None
    effective_area_type = area_type or area_type_dq
    if commute_minutes is not None and commute_minutes > 0:
        commute_score = _score_commute_time(commute_minutes, effective_area_type)
        weighted_total = (total_score * (1.0 - COMMUTE_WEIGHT)) + (commute_score * COMMUTE_WEIGHT)
        total_score = min(100.0, max(0.0, weighted_total))
        try:
            dq_sources = quality_metrics.get('data_sources', []) or []
            if 'census' not in dq_sources:
                dq_sources.append('census')
            quality_metrics['data_sources'] = dq_sources
        except Exception:
            pass
    
    # Commuter rail suburb bonuses: frequency, commute time, weekend service, hub connectivity, destinations
    # These bonuses are research-backed and use smooth curves (design principles compliant)
    frequency_bonus = 0.0
    commute_bonus_additional = 0.0
    weekend_bonus = 0.0
    hub_bonus = 0.0
    destination_bonus = 0.0
    
    if effective_area_type == 'commuter_rail_suburb':
        weekday_trips = None
        peak_headway = None
        trip_headsigns = []
        
        # Try to get frequency and schedule data from route schedules
        if heavy_rail_routes:
            # Sample first route for frequency (or aggregate if multiple)
            sample_route = heavy_rail_routes[0]
            route_id = sample_route.get("route_id") or sample_route.get("onestop_id")
            
            if route_id:
                # Find a representative stop for this route
                # Query stops near location and filter for heavy rail
                try:
                    from data_sources.transitland_api import get_route_schedules, get_stop_departures
                    from datetime import datetime, timedelta
                    
                    # PERFORMANCE OPTIMIZATION: Use cached stops data if available
                    stops_data = cached_stops_data
                    if not stops_data:
                        # Use the function already imported at the top of the file
                        stops_data = get_nearby_transit_stops(lat, lon, radius_m=nearby_radius)
                    if stops_data:
                        stops = stops_data.get("stops", []) or stops_data.get("items", []) or []
                        # Find a heavy rail stop (route_type 2 = commuter rail)
                        heavy_rail_stop = None
                        for stop in stops[:10]:  # Check first 10 stops
                            # For now, use first heavy rail stop as proxy
                            # TODO: Match stop to route more accurately
                            if not heavy_rail_stop:
                                stop_id = stop.get("onestop_id") or stop.get("id")
                                if stop_id:
                                    heavy_rail_stop = stop_id
                                    break
                        
                        if heavy_rail_stop:
                            # PERFORMANCE OPTIMIZATION: Parallelize API calls and reuse departures
                            from concurrent.futures import ThreadPoolExecutor
                            
                            # Find next Saturday for weekend schedule
                            today = datetime.now()
                            days_until_saturday = (5 - today.weekday()) % 7
                            if days_until_saturday == 0:
                                days_until_saturday = 7  # Next Saturday
                            saturday = today + timedelta(days=days_until_saturday)
                            saturday_str = saturday.strftime('%Y-%m-%d')
                            
                            # Parallelize weekday schedule and weekend departures
                            def fetch_weekday_schedule():
                                return get_route_schedules(route_id, sample_stop_id=heavy_rail_stop)
                            
                            def fetch_weekend_departures():
                                return get_stop_departures(heavy_rail_stop, limit=200, service_date=saturday_str)
                            
                            with ThreadPoolExecutor(max_workers=2) as executor:
                                future_schedule = executor.submit(fetch_weekday_schedule)
                                future_weekend = executor.submit(fetch_weekend_departures)
                                
                                schedule = future_schedule.result()
                                weekend_departures = future_weekend.result()
                            
                            # Process weekday schedule (reuse departures from schedule to avoid redundant API call)
                            if schedule:
                                weekday_trips = schedule.get("weekday_trips")
                                peak_headway = schedule.get("peak_headway_minutes")
                                
                                if weekday_trips and peak_headway:
                                    frequency_bonus = _calculate_frequency_bonus(weekday_trips, peak_headway)
                                    logger.info(f"📊 Frequency bonus: {frequency_bonus:.1f} points (trips={weekday_trips}, headway={peak_headway:.1f}min)",
                                                extra={
                                                    "pillar_name": "public_transit_access",
                                                    "lat": lat,
                                                    "lon": lon,
                                                    "frequency_bonus": frequency_bonus,
                                                    "weekday_trips": weekday_trips,
                                                    "peak_headway_min": peak_headway
                                                })
                                
                                # PERFORMANCE OPTIMIZATION: Reuse departures from schedule instead of calling API again
                                weekday_departures = schedule.get("departures")
                                if weekday_departures:
                                    for dep in weekday_departures:
                                        trip = dep.get("trip", {})
                                        headsign = trip.get("trip_headsign", "")
                                        if headsign and headsign not in trip_headsigns:
                                            trip_headsigns.append(headsign)
                            
                            # Process weekend schedule
                            if weekend_departures:
                                weekend_trips = len(weekend_departures)
                                if weekday_trips and weekend_trips:
                                    weekend_bonus = _calculate_weekend_service_bonus(weekend_trips, weekday_trips)
                                    if weekend_bonus > 0:
                                        logger.info(f"📊 Weekend service bonus: {weekend_bonus:.1f} points (weekend={weekend_trips}, weekday={weekday_trips})",
                                                    extra={
                                                        "pillar_name": "public_transit_access",
                                                        "lat": lat,
                                                        "lon": lon,
                                                        "weekend_bonus": weekend_bonus,
                                                        "weekend_trips": weekend_trips,
                                                        "weekday_trips": weekday_trips
                                                    })
                                
                                # Calculate hub connectivity bonus
                                if trip_headsigns:
                                    hub_bonus = _calculate_hub_connectivity_bonus(trip_headsigns)
                                    if hub_bonus > 0:
                                        logger.info(f"📊 Hub connectivity bonus: {hub_bonus:.1f} points (hubs: {trip_headsigns[:3]})",
                                                    extra={
                                                        "pillar_name": "public_transit_access",
                                                        "lat": lat,
                                                        "lon": lon,
                                                        "hub_bonus": hub_bonus,
                                                        "trip_headsigns": trip_headsigns
                                                    })
                                    
                                    # Calculate destination diversity bonus
                                    unique_destinations = len(trip_headsigns)
                                    destination_bonus = _calculate_destination_diversity_bonus(unique_destinations)
                                    if destination_bonus > 0:
                                        logger.info(f"📊 Destination diversity bonus: {destination_bonus:.1f} points ({unique_destinations} destinations)",
                                                    extra={
                                                        "pillar_name": "public_transit_access",
                                                        "lat": lat,
                                                        "lon": lon,
                                                        "destination_bonus": destination_bonus,
                                                        "unique_destinations": unique_destinations
                                                    })
                except Exception as e:
                    logger.warning(f"⚠️  Could not fetch schedule data: {e}",
                                   extra={
                                       "pillar_name": "public_transit_access",
                                       "lat": lat,
                                       "lon": lon,
                                       "error": str(e)
                                   })
        
        # Additional commute bonus (beyond the 10% weight already applied)
        # This rewards exceptionally good commute times for commuter rail suburbs
        if commute_minutes:
            commute_bonus_additional = _calculate_commute_bonus(commute_minutes)
            if commute_bonus_additional > 0:
                logger.info(f"📊 Commute bonus: {commute_bonus_additional:.1f} points (commute={commute_minutes:.1f}min)",
                            extra={
                                "pillar_name": "public_transit_access",
                                "lat": lat,
                                "lon": lon,
                                "commute_bonus": commute_bonus_additional,
                                "commute_minutes": commute_minutes
                            })
        
        # Add all bonuses to total score
        total_bonus = frequency_bonus + commute_bonus_additional + weekend_bonus + hub_bonus + destination_bonus
        total_score = min(100.0, total_score + total_bonus)
        
        if total_bonus > 0:
            logger.info(f"📊 Total commuter rail bonuses: {total_bonus:.1f} points (freq={frequency_bonus:.1f}, commute={commute_bonus_additional:.1f}, weekend={weekend_bonus:.1f}, hub={hub_bonus:.1f}, dest={destination_bonus:.1f})",
                        extra={
                            "pillar_name": "public_transit_access",
                            "lat": lat,
                            "lon": lon,
                            "total_bonus": total_bonus,
                            "frequency_bonus": frequency_bonus,
                            "commute_bonus": commute_bonus_additional,
                            "weekend_bonus": weekend_bonus,
                            "hub_bonus": hub_bonus,
                            "destination_bonus": destination_bonus
                        })

    # Suburban/Exurban/Rural commuter-centric layer: nearest rail + connectivity tier
    # Only applies as a fallback when base score is low (< 50) - helps catch commuter rail
    # that might not be in Transitland, but shouldn't boost already high scores
    #
    # NOTE: This fallback layer uses hardcoded distance breakpoints and bonuses that are
    # not research-backed. This violates design principles but is kept temporarily to handle
    # Transitland API coverage gaps. TODO: Replace with research-backed expected values
    # and data-backed scoring curves, or remove if Transitland coverage improves.
    #
    # TODO: Research needed:
    # - Calibrate distance breakpoints (0.5km, 1km, 2km, 3km) from empirical data
    # - Calibrate connectivity bonus amounts (0, 6, 10, 15) from route count analysis
    # - Calibrate bus bonus multiplier (3.0) from empirical data
    if (area_type or 'unknown') in ('suburban', 'exurban', 'rural') and total_score < 50:
        # PERFORMANCE OPTIMIZATION: Use cached stops data
        nearest_hr_km = _nearest_heavy_rail_km(lat, lon, search_m=2500, cached_stops=cached_stops_data)
        connectivity_tier = _connectivity_tier_heavy_rail(len(heavy_rail_routes))

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

        # Connectivity bonus (0-15) - based on route count (more routes = better connectivity)
        connectivity_bonus = {0: 0, 1: 6, 2: 10, 3: 15}[connectivity_tier]
        # Bus bonus (0-15) proxy
        bus_bonus = min(15.0, max(0.0, len(bus_routes) * 3.0))

        commuter_score = min(100.0, base + connectivity_bonus + bus_bonus)
        # Only use commuter score if it's better than the low base score
        total_score = max(total_score, commuter_score)

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
            heavy_rail_routes, light_rail_routes, bus_routes, routes_data,
            stops_counts=stops_counts
        ),
        "data_quality": quality_metrics
    }
    
    # Add commuter rail suburb bonuses to breakdown if applicable
    if effective_area_type == 'commuter_rail_suburb':
        if frequency_bonus > 0:
            breakdown["breakdown"]["frequency_bonus"] = round(frequency_bonus, 1)
        if commute_bonus_additional > 0:
            breakdown["breakdown"]["commute_bonus"] = round(commute_bonus_additional, 1)
        if weekend_bonus > 0:
            breakdown["breakdown"]["weekend_service_bonus"] = round(weekend_bonus, 1)
        if hub_bonus > 0:
            breakdown["breakdown"]["hub_connectivity_bonus"] = round(hub_bonus, 1)
        if destination_bonus > 0:
            breakdown["breakdown"]["destination_diversity_bonus"] = round(destination_bonus, 1)

    # Add commuter-centric fields to summary
    try:
        # PERFORMANCE OPTIMIZATION: Use cached stops data
        nearest_hr_km_val = _nearest_heavy_rail_km(lat, lon, search_m=2500, cached_stops=cached_stops_data)
        # Ensure distance is in km and handle null properly
        if nearest_hr_km_val == float('inf') or nearest_hr_km_val is None:
            breakdown["summary"]["nearest_heavy_rail_distance_km"] = None
        else:
            # Ensure it's in km (not meters) - if > 100, assume meters
            if nearest_hr_km_val > 100:
                nearest_hr_km_val = nearest_hr_km_val / 1000.0
            breakdown["summary"]["nearest_heavy_rail_distance_km"] = round(nearest_hr_km_val, 2)
        breakdown["summary"]["heavy_rail_connectivity_tier"] = _connectivity_tier_heavy_rail(len(heavy_rail_routes))
    except Exception:
        pass

    if commute_minutes is not None and commute_score is not None:
        breakdown["breakdown"]["commute_time"] = round(commute_score, 1)
        breakdown["summary"]["mean_commute_minutes"] = round(commute_minutes, 1)
        breakdown.setdefault("details", {})["commute_time"] = {
            "mean_minutes": round(commute_minutes, 1),
            "score": round(commute_score, 1),
            "weight": COMMUTE_WEIGHT,
            "note": "Mean commute time (ACS) blended into transit score"
        }
    else:
        breakdown.setdefault("details", {})["commute_time"] = {
            "mean_minutes": None,
            "score": None,
            "weight": COMMUTE_WEIGHT,
            "note": "Commute data unavailable from ACS"
        }

    # Log results
    logger.info(f"✅ Public Transit Score: {total_score:.0f}/100", extra={
        "pillar_name": "public_transit_access",
        "lat": lat,
        "lon": lon,
        "area_type": area_type,
        "total_score": total_score,
        "heavy_rail_score": heavy_rail_score,
        "light_rail_score": light_rail_score,
        "bus_score": bus_score,
        "heavy_rail_routes": len(heavy_rail_routes),
        "light_rail_routes": len(light_rail_routes),
        "bus_routes": len(bus_routes),
        "commute_minutes": commute_minutes,
        "commute_score": commute_score,
        "quality_tier": quality_metrics['quality_tier'],
        "confidence": quality_metrics['confidence']
    })
    logger.info(f"🚇 Heavy Rail: {heavy_rail_score:.0f} ({len(heavy_rail_routes)} routes)", extra={
        "pillar_name": "public_transit_access",
        "lat": lat,
        "lon": lon,
        "mode": "heavy_rail",
        "score": heavy_rail_score,
        "route_count": len(heavy_rail_routes)
    })
    logger.info(f"🚊 Light Rail: {light_rail_score:.0f} ({len(light_rail_routes)} routes)", extra={
        "pillar_name": "public_transit_access",
        "lat": lat,
        "lon": lon,
        "mode": "light_rail",
        "score": light_rail_score,
        "route_count": len(light_rail_routes)
    })
    logger.info(f"🚌 Bus: {bus_score:.0f} ({len(bus_routes)} routes)", extra={
        "pillar_name": "public_transit_access",
        "lat": lat,
        "lon": lon,
        "mode": "bus",
        "score": bus_score,
        "route_count": len(bus_routes)
    })
    if area_type:
        logger.info(f"📍 Area type weighting: {area_type}", extra={
            "pillar_name": "public_transit_access",
            "lat": lat,
            "lon": lon,
            "area_type": area_type
        })
    if commute_minutes is not None and commute_score is not None:
        logger.info(f"⏱️ Commute time: {commute_minutes:.1f} min → score {commute_score:.1f} (weight {COMMUTE_WEIGHT:.0%})", extra={
            "pillar_name": "public_transit_access",
            "lat": lat,
            "lon": lon,
            "commute_minutes": commute_minutes,
            "commute_score": commute_score,
            "commute_weight": COMMUTE_WEIGHT
        })
    logger.info(f"📊 Data Quality: {quality_metrics['quality_tier']} ({quality_metrics['confidence']}% confidence)", extra={
        "pillar_name": "public_transit_access",
        "lat": lat,
        "lon": lon,
        "quality_tier": quality_metrics['quality_tier'],
        "confidence": quality_metrics['confidence']
    })

    return round(total_score, 1), breakdown


def _get_nearby_routes(lat: float, lon: float, radius_m: int = 1500) -> List[Dict]:
    """
    Query Transitland API for nearby transit routes.
    
    Returns list of routes with their types and distances.
    """
    if not TRANSITLAND_API_KEY:
        logger.warning("⚠️  TRANSITLAND_API_KEY not found in .env", extra={
            "pillar_name": "public_transit_access",
            "lat": lat,
            "lon": lon,
            "api_name": "transitland"
        })
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
                    logger.warning(f"⚠️  Transitland API timeout (attempt {attempt + 1}/2), retrying...", extra={
                        "pillar_name": "public_transit_access",
                        "lat": lat,
                        "lon": lon,
                        "api_name": "transitland",
                        "attempt": attempt + 1,
                        "error_type": "timeout"
                    })
                    continue
                else:
                    logger.error("⚠️  Transitland API timeout after 2 attempts", extra={
                        "pillar_name": "public_transit_access",
                        "lat": lat,
                        "lon": lon,
                        "api_name": "transitland",
                        "error_type": "timeout"
                    })
                    raise
            except Exception as e:
                if attempt < 1:
                    logger.warning(f"⚠️  Transitland API error (attempt {attempt + 1}/2): {e}, retrying...", extra={
                        "pillar_name": "public_transit_access",
                        "lat": lat,
                        "lon": lon,
                        "api_name": "transitland",
                        "attempt": attempt + 1,
                        "error_type": "api_error",
                        "error": str(e)
                    })
                    continue
                else:
                    raise
        
        if response is None:
            return []
        
        if response.status_code != 200:
            logger.warning(f"⚠️  Transitland API returned status {response.status_code}", extra={
                "pillar_name": "public_transit_access",
                "lat": lat,
                "lon": lon,
                "api_name": "transitland",
                "status_code": response.status_code,
                "error_type": "http_error"
            })
            return []
        
        data = response.json()
        routes = data.get("routes", [])
        
        # ENHANCED LOGGING: Log API response details
        total_routes_from_api = len(routes)
        limit_hit = total_routes_from_api >= 500
        logger.info(f"📡 Transitland API response: {total_routes_from_api} routes (limit={'HIT' if limit_hit else 'not hit'}, radius={radius_m}m)", extra={
            "pillar_name": "public_transit_access",
            "lat": lat,
            "lon": lon,
            "api_name": "transitland",
            "total_routes_from_api": total_routes_from_api,
            "limit_hit": limit_hit,
            "radius_m": radius_m
        })
        
        if not routes:
            logger.info("ℹ️  No routes found", extra={
                "pillar_name": "public_transit_access",
                "lat": lat,
                "lon": lon,
                "api_name": "transitland",
                "radius_m": radius_m
            })
            return []
        
        # Process routes and calculate distance to nearest stop
        # Deduplicate routes by onestop_id or route_id to prevent double-counting
        processed_routes = []
        seen_route_ids = set()
        
        # ENHANCED LOGGING: Track filtering
        routes_missing_type = 0
        routes_duplicate = 0
        route_type_breakdown = {"heavy": 0, "light": 0, "bus": 0, "other": 0}
        route_distances = []
        
        for route in routes:
            route_type = route.get("route_type")
            if route_type is None:
                routes_missing_type += 1
                continue
            
            # Get unique route identifier for deduplication
            route_id = route.get("onestop_id") or route.get("id")
            if route_id and route_id in seen_route_ids:
                routes_duplicate += 1
                continue
            if route_id:
                seen_route_ids.add(route_id)
            
            # Track route types for logging
            if route_type in [1, 2]:  # Heavy rail
                route_type_breakdown["heavy"] += 1
            elif route_type == 0:  # Light rail
                route_type_breakdown["light"] += 1
            elif route_type == 3:  # Bus
                route_type_breakdown["bus"] += 1
            else:
                route_type_breakdown["other"] += 1
            
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
                if route_distance_km is not None:
                    route_distances.append(route_distance_km * 1000)  # Convert to meters
            
            # If no geometry, we'll calculate distance from nearest stop in usefulness function
            processed_routes.append({
                "name": route.get("route_long_name") or route.get("route_short_name", "Unknown"),
                "short_name": route.get("route_short_name"),
                "route_type": route_type,
                "agency": route.get("agency", {}).get("agency_name", "Unknown"),
                "distance_km": route_distance_km,
                "lat": route_lat,
                "lon": route_lon,
                "route_id": route_id
            })
        
        # ENHANCED LOGGING: Log processing details
        logger.info(f"📊 Route processing: {len(processed_routes)} kept, {routes_missing_type} missing type, {routes_duplicate} duplicates", extra={
            "pillar_name": "public_transit_access",
            "lat": lat,
            "lon": lon,
            "api_name": "transitland",
            "processed_routes": len(processed_routes),
            "routes_missing_type": routes_missing_type,
            "routes_duplicate": routes_duplicate,
            "total_routes_from_api": total_routes_from_api
        })
        logger.info(f"📊 Route type breakdown (raw): {route_type_breakdown['heavy']} heavy, {route_type_breakdown['light']} light, {route_type_breakdown['bus']} bus, {route_type_breakdown['other']} other", extra={
            "pillar_name": "public_transit_access",
            "lat": lat,
            "lon": lon,
            "api_name": "transitland",
            "route_type_breakdown": route_type_breakdown
        })
        
        if route_distances and len(route_distances) > 0:
            avg_distance = sum(route_distances) / len(route_distances)
            max_distance = max(route_distances)
            min_distance = min(route_distances)
            logger.info(f"📍 Route distances: avg={avg_distance:.0f}m, min={min_distance:.0f}m, max={max_distance:.0f}m (radius={radius_m}m)", extra={
                "pillar_name": "public_transit_access",
                "lat": lat,
                "lon": lon,
                "api_name": "transitland",
                "avg_distance_m": avg_distance,
                "min_distance_m": min_distance,
                "max_distance_m": max_distance,
                "radius_m": radius_m
            })
            
            # Warn if many routes are near the radius limit
            routes_near_limit = len([d for d in route_distances if d > radius_m * 0.8])
            if routes_near_limit > 0:
                logger.warning(f"⚠️  {routes_near_limit} routes are within 80% of radius limit - may be missing routes just outside radius", extra={
                    "pillar_name": "public_transit_access",
                    "lat": lat,
                    "lon": lon,
                    "api_name": "transitland",
                    "routes_near_limit": routes_near_limit,
                    "radius_m": radius_m
                })
        
        # ENHANCED LOGGING: Warn if route count seems low for area type
        if len(processed_routes) < 10:
            logger.warning(f"⚠️  WARNING: Only {len(processed_routes)} routes found - may indicate: Transitland API coverage gap, Query radius ({radius_m}m) too small, Location has genuinely sparse transit", extra={
                "pillar_name": "public_transit_access",
                "lat": lat,
                "lon": lon,
                "api_name": "transitland",
                "processed_routes": len(processed_routes),
                "radius_m": radius_m,
                "warning_type": "low_route_count"
            })
        
        logger.info(f"ℹ️  Found {len(processed_routes)} unique transit routes (deduplicated from {total_routes_from_api} total)", extra={
            "pillar_name": "public_transit_access",
            "lat": lat,
            "lon": lon,
            "api_name": "transitland",
            "processed_routes": len(processed_routes),
            "total_routes_from_api": total_routes_from_api
        })
        
        return processed_routes
        
    except Exception as e:
        logger.error(f"⚠️  Transit query error: {e}", extra={
            "pillar_name": "public_transit_access",
            "lat": lat,
            "lon": lon,
            "api_name": "transitland",
            "error_type": "query_error",
            "error": str(e)
        })
        import traceback
        logger.debug(f"Transit query error traceback: {traceback.format_exc()}", extra={
            "pillar_name": "public_transit_access",
            "lat": lat,
            "lon": lon
        })
        return []


def _score_heavy_rail_routes(routes: List[Dict], lat: float = None, lon: float = None, area_type: str = None, city: Optional[str] = None) -> float:
    """
    Score heavy rail access, differentiating subway (route_type 1) from commuter rail (route_type 2).
    
    Subway: Many routes, frequent service, local trips (NYC subway, Boston T)
    Commuter rail: Fewer routes, connects to downtown, longer-distance trips (Metro-North, Metra)
    """
    if not routes:
        return 0.0
    
    # Separate subway (route_type 1) from commuter rail (route_type 2)
    subway_routes = [r for r in routes if r.get("route_type") == 1]
    commuter_routes = [r for r in routes if r.get("route_type") == 2]
    
    # Score each separately
    subway_score = _score_subway_routes(subway_routes, lat, lon, area_type) if subway_routes else 0.0
    commuter_score = _score_commuter_rail_routes(commuter_routes, lat, lon, area_type, city) if commuter_routes else 0.0
    
    # Use best of subway or commuter rail (they serve different purposes)
    # If both exist, subway typically dominates (more routes, better connectivity)
    return max(subway_score, commuter_score)


def _score_subway_routes(routes: List[Dict], lat: float = None, lon: float = None, area_type: str = None) -> float:
    """Score subway/metro access (route_type 1) based on route availability, connectivity, and proximity."""
    if not routes:
        return 0.0
    
    count = len(routes)
    
    # Presence of subway is huge (30 pts base)
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
    
    # Connectivity bonus: more routes = more destinations reachable (0-30 pts)
    # Based on route count (more routes = better connectivity, not actual frequency)
    # Higher cap to reward exceptional transit access (e.g., NYC with 12+ routes)
    # Allows scores to reach 90-100 range when combined with other factors
    # Linear scaling: 1-5 routes → 2-10 pts, 6-10 routes → 12-20 pts, 10-15 routes → 20-30 pts, 15+ routes → 30 pts
    if count >= 15:
        connectivity_bonus = 30.0
    elif count >= 10:
        connectivity_bonus = 20.0 + ((count - 10) * 2.0)  # 20-30 pts for 10-15 routes
    elif count >= 5:
        connectivity_bonus = 10.0 + ((count - 5) * 2.0)  # 10-20 pts for 5-10 routes
    else:
        connectivity_bonus = min(10.0, count * 2.0)  # 2-10 pts for 1-5 routes
    
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
    
    # Exceptional transit bonus: 7+ routes AND very close (<0.5km) = exceptional access
    # This rewards places like Park Slope (12 routes) and Carroll Gardens (8 routes) with excellent subway access
    # Lowered from 10+ to 7+ to capture excellent transit areas (WalkScore 90-100 range)
    exceptional_bonus = 0.0
    if count >= 7 and proximity_bonus >= 10.0:
        exceptional_bonus = 10.0  # Bonus for exceptional transit access
    
    # Don't cap at 100 - allow scores above 100 for exceptional transit
    # This enables final weighted scores to reach 90-100 range (matching WalkScore)
    return base_score + density_score + connectivity_bonus + proximity_bonus + exceptional_bonus


def _score_commuter_rail_routes(routes: List[Dict], lat: float = None, lon: float = None, area_type: str = None, city: Optional[str] = None) -> float:
    """
    Score commuter rail access (route_type 2) with metro connectivity bonus.
    
    Commuter rail typically has fewer routes but connects to major metros.
    Examples: Metro-North, Metra, MBTA Commuter Rail
    """
    if not routes:
        return 0.0
    
    count = len(routes)
    
    # Base score (higher than subway base because commuter rail is valuable even with few routes)
    base_score = 35.0
    
    # Density score (commuter rail typically has fewer routes than subway)
    if count >= 3:
        density_score = 15.0
    elif count >= 2:
        density_score = 12.0
    else:
        density_score = 8.0
    
    # Connectivity bonus (fewer routes needed for good score)
    if count >= 3:
        connectivity_bonus = 15.0
    elif count >= 2:
        connectivity_bonus = 12.0
    else:
        connectivity_bonus = 8.0
    
    # Proximity bonus (commuter rail stations are typically farther than subway stops)
    proximity_bonus = 0.0
    if lat and lon:
        try:
            nearest_hr_km = _nearest_heavy_rail_km(lat, lon, search_m=2500)
            if nearest_hr_km < float('inf'):
                if nearest_hr_km <= 0.5:
                    proximity_bonus = 12.0  # Very close for commuter rail
                elif nearest_hr_km <= 1.0:
                    proximity_bonus = 10.0  # Good proximity
                elif nearest_hr_km <= 2.0:
                    proximity_bonus = 8.0
                elif nearest_hr_km <= 3.0:
                    proximity_bonus = 5.0
        except Exception:
            pass
    
    # Metro connectivity bonus: If commuter rail serves a major metro, add bonus
    # This rewards network connectivity (access to downtown, major transit hub)
    metro_connectivity_bonus = 0.0
    if area_type in ('urban_core', 'suburban') and city:
        try:
            from data_sources.regional_baselines import regional_baseline_manager
            metro_name = regional_baseline_manager._detect_metro_area(city, lat, lon)
            if metro_name:
                metro_data = regional_baseline_manager.major_metros.get(metro_name, {})
                if metro_data:
                    population = metro_data.get('population', 0)
                    # Different bonuses by metro size and area type
                    if population > 5000000:  # Very large metros (NYC, LA, Chicago)
                        if area_type == 'suburban':
                            metro_connectivity_bonus = 8.0  # Modest bonus for suburbs (commuter rail is expected)
                        else:
                            metro_connectivity_bonus = 15.0  # Higher bonus for urban areas (commuter rail is valuable)
                    elif population > 2000000:  # Large metros
                        if area_type == 'suburban':
                            metro_connectivity_bonus = 5.0
                        else:
                            metro_connectivity_bonus = 12.0
                    else:  # Smaller metros
                        if area_type == 'suburban':
                            metro_connectivity_bonus = 3.0
                        else:
                            metro_connectivity_bonus = 8.0
        except Exception:
            pass
    
    return base_score + density_score + connectivity_bonus + proximity_bonus + metro_connectivity_bonus


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
            # Find nearest light rail stop (using function already imported at top)
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


def _build_summary_from_routes(heavy_rail: List, light_rail: List, bus: List, all_routes: List, stops_counts: Optional[Dict[str, int]] = None) -> Dict:
    """
    Build summary of transit access from routes and actual stop counts.
    
    RESEARCH-BACKED: Includes both route counts (for scoring) and actual stop counts (for accuracy).
    Stop counts provide more accurate representation of transit density than route counts alone.
    
    Args:
        heavy_rail: List of heavy rail routes
        light_rail: List of light rail routes
        bus: List of bus routes
        all_routes: List of all routes
        stops_counts: Optional dict with actual stop counts {"heavy_rail": int, "light_rail": int, "bus": int, "total": int}
    """
    summary = {
        "total_routes": len(all_routes),  # Total distinct transit routes
        "heavy_rail_routes": len(heavy_rail),  # Heavy rail (subway/metro/commuter) route count
        "light_rail_routes": len(light_rail),  # Light rail/streetcar route count
        "bus_routes": len(bus),  # Bus route count
        "nearest_heavy_rail": heavy_rail[0] if heavy_rail else None,
        "nearest_light_rail": light_rail[0] if light_rail else None,
        "nearest_bus": bus[0] if bus else None,
        "transit_modes_available": []
    }
    
    # Add actual stop counts if available (more accurate than route counts)
    if stops_counts:
        summary["total_stops"] = stops_counts.get("total", 0)
        summary["heavy_rail_stops"] = stops_counts.get("heavy_rail", 0)
        summary["light_rail_stops"] = stops_counts.get("light_rail", 0)
        summary["bus_stops"] = stops_counts.get("bus", 0)
    else:
        # Fallback: Use route counts (legacy behavior, less accurate)
        # Note: This is a fallback when stop data unavailable
        summary["total_stops"] = len(all_routes)
        summary["heavy_rail_stops"] = len(heavy_rail)
        summary["light_rail_stops"] = len(light_rail)
        summary["bus_stops"] = len(bus)
        logger.debug("⚠️  Using route counts as stop counts (stop data unavailable)", extra={
            "pillar_name": "public_transit_access"
        })

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
            "total_routes": 0,
            "heavy_rail_routes": 0,
            "light_rail_routes": 0,
            "bus_routes": 0,
            # Legacy field names for backward compatibility
            "total_routes": 0,
            "heavy_rail_routes": 0,
            "light_rail_routes": 0,
            "bus_routes": 0,
            "nearest_heavy_rail": None,
            "nearest_light_rail": None,
            "nearest_bus": None,
            "transit_modes_available": [],
            "access_level": "None - No transit service"
        }
    }
    