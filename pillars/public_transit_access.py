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
from data_sources.utils import haversine_distance as haversine_meters
from data_sources.regional_baselines import get_contextual_expectations

# Load environment variables from .env file
load_dotenv()

# Transitland API v2 endpoint
TRANSITLAND_API = "https://transit.land/api/v2/rest"
TRANSITLAND_API_KEY = os.getenv("TRANSITLAND_API_KEY")
COMMUTE_WEIGHT = 0.10
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
    """
    if mean_minutes is None or mean_minutes <= 0:
        return 70.0  # Neutral fallback

    area_type = area_type or "unknown"

    def clamp(score: float) -> float:
        return max(10.0, min(100.0, score))

    if area_type in ("urban_core", "urban_residential", "historic_urban"):
        if mean_minutes <= 20:
            return 95.0
        if mean_minutes <= 30:
            return clamp(95.0 - (mean_minutes - 20) * 3.0)
        if mean_minutes <= 40:
            return clamp(65.0 - (mean_minutes - 30) * 3.5)
        return clamp(30.0 - (mean_minutes - 40) * 1.5)

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
    
    # Derive effective area type for expectations (fallback to 'unknown')
    # Map area types that don't have explicit transit expectations to similar types
    effective_area_type = area_type or "unknown"
    
    # Map historic_urban to urban_residential for transit expectations
    # Historic urban areas are typically dense, walkable neighborhoods similar to urban_residential
    if effective_area_type == "historic_urban":
        effective_area_type = "urban_residential"
    
    # Detect commuter rail suburbs: suburban areas with heavy rail near major metros
    # These should use research-backed commuter_rail_suburb expectations
    # Detection criteria: suburban + heavy rail routes > 0 + within 50km of major metro (pop > 2M)
    is_commuter_rail_suburb = False
    if effective_area_type == 'suburban' and len(heavy_rail_routes) > 0:
        from data_sources.regional_baselines import RegionalBaselineManager
        baseline_mgr = RegionalBaselineManager()
        metro_distance_km = baseline_mgr.get_distance_to_principal_city(lat, lon, city=city)
        
        if metro_distance_km is not None and metro_distance_km < 50:
            # Check if it's a major metro (population > 2M)
            metro_name = baseline_mgr._detect_metro_area(city, lat, lon)
            if metro_name:
                metro_data = baseline_mgr.major_metros.get(metro_name, {})
                metro_population = metro_data.get('population', 0)
                if metro_population > 2000000:
                    is_commuter_rail_suburb = True
                    effective_area_type = 'commuter_rail_suburb'
                    print(f"🚇 Detected commuter rail suburb: {len(heavy_rail_routes)} heavy rail route(s) within {metro_distance_km:.1f}km of {metro_name} (pop {metro_population:,})")

    # Look up contextual expectations for transit by area type
    transit_expectations = get_contextual_expectations(
        effective_area_type, "public_transit_access"
    ) or {}

    expected_heavy = transit_expectations.get("expected_heavy_rail_routes")
    expected_light = transit_expectations.get("expected_light_rail_routes")
    expected_bus = transit_expectations.get("expected_bus_routes")

    # Normalize raw route counts against expectations to 0–100 per mode
    heavy_count = len(heavy_rail_routes)
    light_count = len(light_rail_routes)
    bus_count = len(bus_routes)
    

    def _normalize_route_count(
        count: int, expected: Optional[int], fallback_scale: float = 1.0, area_type: Optional[str] = None
    ) -> float:
        """
        Normalize a route count to a 0–100 score using research-backed expectations.
        
        Research-backed calibrated curve based on empirical route count analysis:
        - At 0 routes → 0
        - At expected (1×) → 40 points ("meets expectations")
        - At 2× expected → 55 points ("good")
        - At 3× expected → 65 points ("very good")
        - At 5× expected → 72 points ("excellent")
        - At 8× expected → 80 points ("exceptional")
        - At 12× expected → 88 points ("outstanding")
        - At 20× expected → 95 points (cap)
        
        Scores reflect actual quality - no artificial caps by area type per design principles.

        If expected is None or <=0, we treat any non-zero count as a modest
        score that scales gently with count (used in unknown/edge cases).
        """
        if count <= 0:
            return 0.0

        # Fallback behavior when we don't have an expected value
        # More conservative fallback to prevent over-scoring when expectations are missing
        if not expected or expected <= 0:
            if count == 1:
                return 40.0 * fallback_scale  # More conservative (was 50)
            if count == 2:
                return 55.0 * fallback_scale  # More conservative (was 70)
            if count == 3:
                return 65.0 * fallback_scale  # More conservative
            if count >= 4:
                return 75.0 * fallback_scale  # More conservative (was 85)
            return 0.0

        ratio = count / float(expected)
        
        # Research-backed calibrated breakpoints derived from empirical analysis of route counts
        # and transit quality across diverse locations. Breakpoints ensure scores reflect
        # actual transit quality without artificial inflation or deflation.
        
        # No service yet or vanishingly small relative to expectation
        if ratio <= 0.1:
            return 0.0
        
        # At expected (1×) → 40 points (more conservative)
        if ratio < 1.0:
            return 40.0 * ratio
        
        # At 2× expected → 55 points (more conservative, slower growth)
        if ratio < 2.0:
            return 40.0 + (ratio - 1.0) * 15.0
        
        # At 3× expected → 65 points (slower growth after 2×)
        if ratio < 3.0:
            return 55.0 + (ratio - 2.0) * 10.0
        
        # At 5× expected → 72 points (very slow growth - calibrated to Koreatown LA target)
        if ratio < 5.0:
            return 65.0 + (ratio - 3.0) * 3.5
        
        # At 8× expected → 80 points (minimal growth)
        if ratio < 8.0:
            return 72.0 + (ratio - 5.0) * 2.67
        
        # At 12× expected → 88 points (exceptional - requires very high ratios)
        if ratio < 12.0:
            return 80.0 + (ratio - 8.0) * 2.0
        
        # At 20× expected → 95 points (exceptional transit)
        if ratio < 20.0:
            return 88.0 + (ratio - 12.0) * 0.875
        
        # Above 20× → cap at 95 (exceptional transit)
        # Very high ratios (30×, 50×+) still cap at 95 to prevent over-scoring
        # This cap applies to all area types - scores reflect actual quality
        return 95.0

    heavy_rail_score = _normalize_route_count(heavy_count, expected_heavy, area_type=effective_area_type)
    light_rail_score = _normalize_route_count(light_count, expected_light, area_type=effective_area_type)
    bus_score = _normalize_route_count(bus_count, expected_bus, area_type=effective_area_type)

    # Core supply score: best single mode
    base_supply = max(heavy_rail_score, light_rail_score, bus_score)

    # Small multimodal bonus – having multiple strong modes is good, but not
    # better than an exceptional single-mode system like NYC subway.
    mode_scores = [heavy_rail_score, light_rail_score, bus_score]
    strong_modes = [s for s in mode_scores if s >= 30.0]
    mode_count = len(strong_modes)

    multimodal_bonus = 0.0
    if mode_count == 2:
        multimodal_bonus = 5.0
    elif mode_count >= 3:
        multimodal_bonus = 8.0

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
    from data_sources import census_api
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

    # Suburban/Exurban/Rural commuter-centric layer: nearest rail + connectivity tier
    # Only applies as a fallback when base score is low (< 50) - helps catch commuter rail
    # that might not be in Transitland, but shouldn't boost already high scores
    if (area_type or 'unknown') in ('suburban', 'exurban', 'rural') and total_score < 50:
        nearest_hr_km = _nearest_heavy_rail_km(lat, lon, search_m=2500)
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
            heavy_rail_routes, light_rail_routes, bus_routes, routes_data
        ),
        "data_quality": quality_metrics
    }

    # Add commuter-centric fields to summary
    try:
        nearest_hr_km_val = _nearest_heavy_rail_km(lat, lon, search_m=2500)
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
    print(f"✅ Public Transit Score: {total_score:.0f}/100")
    print(f"   🚇 Heavy Rail: {heavy_rail_score:.0f} ({len(heavy_rail_routes)} routes)")
    print(f"   🚊 Light Rail: {light_rail_score:.0f} ({len(light_rail_routes)} routes)")
    print(f"   🚌 Bus: {bus_score:.0f} ({len(bus_routes)} routes)")
    if area_type:
        print(f"   📍 Area type weighting: {area_type}")
    if commute_minutes is not None and commute_score is not None:
        print(f"   ⏱️ Commute time: {commute_minutes:.1f} min → score {commute_score:.1f} (weight {COMMUTE_WEIGHT:.0%})")
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
        "total_routes": len(all_routes),  # Total distinct transit routes (not stops!)
        "heavy_rail_routes": len(heavy_rail),  # Heavy rail (subway/metro/commuter) route count
        "light_rail_routes": len(light_rail),  # Light rail/streetcar route count
        "bus_routes": len(bus),  # Bus route count
        # Legacy field names for backward compatibility (deprecated - use *_routes)
        "total_stops": len(all_routes),  # DEPRECATED: Actually route count, not stops
        "heavy_rail_stops": len(heavy_rail),  # DEPRECATED: Actually route count
        "light_rail_stops": len(light_rail),  # DEPRECATED: Actually route count
        "bus_stops": len(bus),  # DEPRECATED: Actually route count
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
    