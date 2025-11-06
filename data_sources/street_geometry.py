"""
Street Geometry Metrics for Phase 2 & Phase 3 Beauty Scoring
Computes block grain, streetwall continuity, setback consistency, and facade rhythm 
from OSM road and building data.
"""

import math
import requests
from typing import Dict, List, Tuple, Optional
from .osm_api import OVERPASS_URL, _retry_overpass, haversine_distance
from .cache import cached, CACHE_TTL


@cached(ttl_seconds=CACHE_TTL['osm_queries'])
def _fetch_roads_and_buildings(lat: float, lon: float, radius_m: int = 1000) -> Optional[Dict]:
    """
    Shared OSM query for roads and buildings (used by Phase 2 & Phase 3 metrics).
    
    Returns:
        {
            "nodes_dict": Dict,
            "road_ways": List[Dict],
            "building_ways": List[Dict],
            "elements": List[Dict]  # Full response for caching
        }
    """
    try:
        query = f"""
        [out:json][timeout:30];
        (
          way["highway"~"^(residential|primary|secondary|tertiary|unclassified|service|living_street)$"](around:{radius_m},{lat},{lon});
          way["building"](around:{radius_m},{lat},{lon});
        );
        out body;
        >;
        out skel qt;
        """
        
        def _do_request():
            return requests.post(OVERPASS_URL, data={"data": query}, timeout=20,
                               headers={"User-Agent": "HomeFit/1.0"})
        
        resp = _retry_overpass(_do_request, attempts=2, base_wait=1.0)
        
        if resp is None or resp.status_code != 200:
            return None
        
        data = resp.json()
        elements = data.get("elements", [])
        
        # Separate roads and buildings
        nodes_dict = {}
        road_ways = []
        building_ways = []
        
        for elem in elements:
            if elem["type"] == "node":
                nodes_dict[elem["id"]] = elem
            elif elem["type"] == "way":
                tags = elem.get("tags", {})
                if "highway" in tags:
                    road_ways.append(elem)
                elif "building" in tags:
                    building_ways.append(elem)
        
        return {
            "nodes_dict": nodes_dict,
            "road_ways": road_ways,
            "building_ways": building_ways,
            "elements": elements
        }
    except Exception as e:
        print(f"⚠️  OSM roads/buildings query error: {e}")
        return None


def _compute_point_on_line(point: Tuple[float, float], line_start: Tuple[float, float], 
                          line_end: Tuple[float, float]) -> Tuple[float, float, float]:
    """
    Find the closest point on a line segment to a given point.
    
    Returns:
        (closest_lat, closest_lon, distance_m)
    """
    px, py = point[1], point[0]  # lon, lat
    x1, y1 = line_start[1], line_start[0]
    x2, y2 = line_end[1], line_end[0]
    
    # Vector from line_start to line_end
    dx = x2 - x1
    dy = y2 - y1
    
    # If line segment is a point
    if dx == 0 and dy == 0:
        closest_lat, closest_lon = line_start[0], line_start[1]
    else:
        # Parameter t where closest point is
        t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
        closest_lon = x1 + t * dx
        closest_lat = y1 + t * dy
    
    # Calculate distance
    distance_m = haversine_distance(point[0], point[1], closest_lat, closest_lon)
    
    return closest_lat, closest_lon, distance_m


@cached(ttl_seconds=CACHE_TTL['osm_queries'])
def compute_block_grain(lat: float, lon: float, radius_m: int = 1000) -> Dict[str, float]:
    """
    Compute block grain metric: measures street network fineness.
    
    Block grain = how fine-grained the street network is (higher = finer grain, more walkable).
    Based on:
    - Median block length (shorter = finer grain)
    - Intersection density (higher = finer grain)
    
    Args:
        lat, lon: Center coordinates
        radius_m: Search radius in meters
    
    Returns:
        {
            "block_grain": float (0-100, normalized),
            "median_block_length_m": float,
            "intersection_density_per_sqkm": float,
            "total_blocks": int,
            "total_intersections": int,
            "coverage_confidence": float (0.0-1.0)
        }
    """
    try:
        # Query OSM for road network (residential, primary, secondary, tertiary, unclassified)
        query = f"""
        [out:json][timeout:25];
        (
          way["highway"~"^(residential|primary|secondary|tertiary|unclassified|service|living_street)$"](around:{radius_m},{lat},{lon});
        );
        out body;
        >;
        out skel qt;
        """
        
        def _do_request():
            return requests.post(OVERPASS_URL, data={"data": query}, timeout=20, 
                               headers={"User-Agent": "HomeFit/1.0"})
        
        resp = _retry_overpass(_do_request, attempts=2, base_wait=1.0)
        
        if resp is None or resp.status_code != 200:
            return {
                "block_grain": 0.0,
                "median_block_length_m": 0.0,
                "intersection_density_per_sqkm": 0.0,
                "total_blocks": 0,
                "total_intersections": 0,
                "coverage_confidence": 0.0
            }
        
        data = resp.json()
        elements = data.get("elements", [])
        
        # Build node and way dictionaries
        nodes_dict = {}
        ways_dict = {}
        
        for elem in elements:
            if elem["type"] == "node":
                nodes_dict[elem["id"]] = elem
            elif elem["type"] == "way":
                ways_dict[elem["id"]] = elem
        
        if not ways_dict:
            return {
                "block_grain": 0.0,
                "median_block_length_m": 0.0,
                "intersection_density_per_sqkm": 0.0,
                "total_blocks": 0,
                "total_intersections": 0,
                "coverage_confidence": 0.0
            }
        
        # Reconstruct road segments and find intersections
        road_segments = []
        node_usage_count = {}  # Count how many ways use each node
        
        for way_id, way in ways_dict.items():
            nodes = way.get("nodes", [])
            if len(nodes) < 2:
                continue
            
            # Get coordinates for this way
            coords = []
            for node_id in nodes:
                if node_id in nodes_dict:
                    node = nodes_dict[node_id]
                    coords.append((node["lat"], node["lon"]))
                    node_usage_count[node_id] = node_usage_count.get(node_id, 0) + 1
            
            if len(coords) < 2:
                continue
            
            # Create segments from consecutive pairs
            for i in range(len(coords) - 1):
                segment = {
                    "start": coords[i],
                    "end": coords[i + 1],
                    "length_m": haversine_distance(coords[i][0], coords[i][1], 
                                                   coords[i + 1][0], coords[i + 1][1])
                }
                if segment["length_m"] > 0:
                    road_segments.append(segment)
        
        # Find intersections (nodes used by 2+ ways)
        intersections = []
        for node_id, usage_count in node_usage_count.items():
            if usage_count >= 2 and node_id in nodes_dict:
                node = nodes_dict[node_id]
                # Check if within radius
                dist = haversine_distance(lat, lon, node["lat"], node["lon"])
                if dist <= radius_m:
                    intersections.append((node["lat"], node["lon"]))
        
        # Calculate block lengths (distance between consecutive intersections along roads)
        block_lengths = []
        
        # For each intersection, find all road segments that connect to it
        # Then trace paths between intersections to estimate block perimeters
        # Simplified: use median segment length as proxy for block size
        if road_segments:
            segment_lengths = [seg["length_m"] for seg in road_segments]
            # Blocks are typically 2-4 segments, so median segment length * 2-3 ≈ block length
            median_segment_length = sorted(segment_lengths)[len(segment_lengths) // 2]
            # Estimate block length as ~2.5x median segment (typical block has 2-3 segments)
            estimated_block_length = median_segment_length * 2.5
            
            # Also use actual distance between nearby intersections
            # OPTIMIZATION: Limit to first 100 intersections to avoid O(n²) explosion
            # Most block length info comes from the first few intersections anyway
            intersections_to_check = intersections[:100] if len(intersections) > 100 else intersections
            for i, int1 in enumerate(intersections_to_check):
                # Only check nearby intersections (within 500m) to reduce computation
                for int2 in intersections_to_check[i + 1:]:
                    # Quick distance check - if too far, skip expensive calculation
                    # Use simpler lat/lon distance estimate first (rough but fast)
                    lat_diff = abs(int1[0] - int2[0])
                    lon_diff = abs(int1[1] - int2[1])
                    # Rough estimate: 1 degree ≈ 111km, so 0.005 degrees ≈ 500m
                    if lat_diff > 0.005 or lon_diff > 0.005:
                        continue
                    
                    dist = haversine_distance(int1[0], int1[1], int2[0], int2[1])
                    if dist < 500:  # Only consider nearby intersections
                        block_lengths.append(dist)
        
        # Use estimated block length if we don't have enough intersection pairs
        if not block_lengths and estimated_block_length:
            block_lengths = [estimated_block_length]
        
        # Calculate metrics
        median_block_length_m = sorted(block_lengths)[len(block_lengths) // 2] if block_lengths else 0.0
        
        # Intersection density per square km
        area_sqkm = math.pi * (radius_m / 1000) ** 2
        intersection_density = len(intersections) / area_sqkm if area_sqkm > 0 else 0.0
        
        # Normalize to 0-100 scale
        # Typical values:
        # - Fine-grained urban (Park Slope, Savannah): block_length < 100m, intersections > 50/sqkm → score > 80
        # - Suburban (Larchmont): block_length 100-200m, intersections 20-40/sqkm → score 50-70
        # - Coarse (rural): block_length > 300m, intersections < 10/sqkm → score < 40
        
        # Block length component (shorter = higher score)
        # 50m = 100, 100m = 80, 200m = 50, 300m = 30, 500m = 10
        if median_block_length_m > 0:
            if median_block_length_m <= 50:
                block_length_score = 100.0
            elif median_block_length_m <= 100:
                block_length_score = 80.0 + (50 - median_block_length_m) / 50 * 20
            elif median_block_length_m <= 200:
                block_length_score = 50.0 + (100 - median_block_length_m) / 100 * 30
            elif median_block_length_m <= 300:
                block_length_score = 30.0 + (200 - median_block_length_m) / 100 * 20
            elif median_block_length_m <= 500:
                block_length_score = 10.0 + (300 - median_block_length_m) / 200 * 20
            else:
                block_length_score = max(0.0, 10.0 - (median_block_length_m - 500) / 100)
        else:
            block_length_score = 0.0
        
        # Intersection density component (higher = higher score)
        # 50/sqkm = 100, 30/sqkm = 80, 20/sqkm = 60, 10/sqkm = 40, 5/sqkm = 20
        if intersection_density >= 50:
            intersection_score = 100.0
        elif intersection_density >= 30:
            intersection_score = 80.0 + (intersection_density - 30) / 20 * 20
        elif intersection_density >= 20:
            intersection_score = 60.0 + (intersection_density - 20) / 10 * 20
        elif intersection_density >= 10:
            intersection_score = 40.0 + (intersection_density - 10) / 10 * 20
        elif intersection_density >= 5:
            intersection_score = 20.0 + (intersection_density - 5) / 5 * 20
        else:
            intersection_score = max(0.0, intersection_density / 5 * 20)
        
        # Weighted combination (block length 60%, intersection density 40%)
        block_grain = 0.6 * block_length_score + 0.4 * intersection_score
        block_grain = max(0.0, min(100.0, block_grain))
        
        # Coverage confidence (based on road density)
        road_length_km = sum(seg["length_m"] for seg in road_segments) / 1000
        expected_road_length = area_sqkm * 10.0  # Typical: 10km roads per sqkm
        coverage_confidence = min(1.0, road_length_km / expected_road_length if expected_road_length > 0 else 0.0)
        
        return {
            "block_grain": round(block_grain, 1),
            "median_block_length_m": round(median_block_length_m, 1),
            "intersection_density_per_sqkm": round(intersection_density, 1),
            "total_blocks": len(block_lengths),
            "total_intersections": len(intersections),
            "coverage_confidence": round(coverage_confidence, 2)
        }
        
    except Exception as e:
        print(f"⚠️  Block grain calculation error: {e}")
        return {
            "block_grain": 0.0,
            "median_block_length_m": 0.0,
            "intersection_density_per_sqkm": 0.0,
            "total_blocks": 0,
            "total_intersections": 0,
            "coverage_confidence": 0.0
        }


def compute_streetwall_continuity(lat: float, lon: float, radius_m: int = 1000, 
                                   osm_data: Optional[Dict] = None) -> Dict[str, float]:
    """
    Compute streetwall continuity metric: measures building facade continuity along streets.
    
    Streetwall continuity = percentage of street frontage with buildings near the sidewalk.
    Higher = more continuous facade line, more urban/enclosed feel.
    
    Args:
        lat, lon: Center coordinates
        radius_m: Search radius in meters
    
    Returns:
        {
            "streetwall_continuity": float (0-100, normalized),
            "street_frontage_m": float,
            "built_frontage_m": float,
            "continuity_ratio": float (0.0-1.0),
            "coverage_confidence": float (0.0-1.0)
        }
    """
    try:
        # Use shared OSM data if provided, otherwise fetch
        if osm_data is None:
            osm_data = _fetch_roads_and_buildings(lat, lon, radius_m)
        
        if osm_data is None:
            return {
                "streetwall_continuity": 0.0,
                "street_frontage_m": 0.0,
                "built_frontage_m": 0.0,
                "continuity_ratio": 0.0,
                "coverage_confidence": 0.0
            }
        
        nodes_dict = osm_data["nodes_dict"]
        road_ways = osm_data["road_ways"]
        building_ways = osm_data["building_ways"]
        
        if not road_ways:
            return {
                "streetwall_continuity": 0.0,
                "street_frontage_m": 0.0,
                "built_frontage_m": 0.0,
                "continuity_ratio": 0.0,
                "coverage_confidence": 0.0
            }
        
        # Calculate total street frontage (sum of road segment lengths, doubled for both sides)
        street_frontage_m = 0.0
        
        for way in road_ways:
            nodes = way.get("nodes", [])
            if len(nodes) < 2:
                continue
            
            # Get coordinates
            coords = []
            for node_id in nodes:
                if node_id in nodes_dict:
                    node = nodes_dict[node_id]
                    coords.append((node["lat"], node["lon"]))
            
            if len(coords) < 2:
                continue
            
            # Sum segment lengths
            for i in range(len(coords) - 1):
                segment_length = haversine_distance(
                    coords[i][0], coords[i][1],
                    coords[i + 1][0], coords[i + 1][1]
                )
                street_frontage_m += segment_length
        
        # Count both sides of streets
        street_frontage_m *= 2.0
        
        # Calculate built frontage (buildings near streets)
        # For each building, find closest road segment and check distance
        # OPTIMIZATION: Pre-filter buildings by distance to any road node before expensive segment checks
        built_frontage_m = 0.0
        building_coverage_buffer = 30.0  # meters - buildings within 30m count as streetwall
        
        # Pre-compute all road node coordinates for spatial filtering
        all_road_nodes = []
        for road_way in road_ways:
            road_nodes = road_way.get("nodes", [])
            for node_id in road_nodes:
                if node_id in nodes_dict:
                    node = nodes_dict[node_id]
                    all_road_nodes.append((node["lat"], node["lon"]))
        
        # Pre-compute road segments once (instead of recomputing for each building)
        road_segments_precomputed = []
        for road_way in road_ways:
            road_nodes = road_way.get("nodes", [])
            if len(road_nodes) < 2:
                continue
            
            road_coords = []
            for node_id in road_nodes:
                if node_id in nodes_dict:
                    node = nodes_dict[node_id]
                    road_coords.append((node["lat"], node["lon"]))
            
            if len(road_coords) < 2:
                continue
            
            # Store all segments for this road
            for i in range(len(road_coords) - 1):
                segment_length = haversine_distance(
                    road_coords[i][0], road_coords[i][1],
                    road_coords[i + 1][0], road_coords[i + 1][1]
                )
                road_segments_precomputed.append({
                    "start": road_coords[i],
                    "end": road_coords[i + 1],
                    "length": segment_length
                })
        
        for building in building_ways:
            nodes = building.get("nodes", [])
            if not nodes:
                continue
            
            # Get building centroid
            building_coords = []
            for node_id in nodes:
                if node_id in nodes_dict:
                    node = nodes_dict[node_id]
                    building_coords.append((node["lat"], node["lon"]))
            
            if not building_coords:
                continue
            
            # Calculate centroid
            building_lat = sum(c[0] for c in building_coords) / len(building_coords)
            building_lon = sum(c[1] for c in building_coords) / len(building_coords)
            
            # OPTIMIZATION: Quick distance check to nearest road node first
            # If building is far from all road nodes, skip expensive segment checks
            min_node_distance = float('inf')
            for road_node_lat, road_node_lon in all_road_nodes:
                dist = haversine_distance(building_lat, building_lon, road_node_lat, road_node_lon)
                if dist < min_node_distance:
                    min_node_distance = dist
            
            # If building is >50m from all road nodes, it's definitely not a streetwall
            # (buffer is 30m, so 50m gives us a safe margin)
            if min_node_distance > 50.0:
                continue
            
            # Find closest road segment (now only checking precomputed segments)
            min_distance = float('inf')
            closest_segment_length = 0.0
            
            for segment in road_segments_precomputed:
                _, _, dist = _compute_point_on_line(
                    (building_lat, building_lon),
                    segment["start"],
                    segment["end"]
                )
                
                if dist < min_distance:
                    min_distance = dist
                    closest_segment_length = segment["length"]
            
            # If building is within buffer, count its frontage
            if min_distance <= building_coverage_buffer:
                # Estimate building frontage (simplified: use building perimeter / 4 as frontage)
                # Better: use building's closest edge to road
                building_perimeter = 0.0
                for i in range(len(building_coords)):
                    next_i = (i + 1) % len(building_coords)
                    building_perimeter += haversine_distance(
                        building_coords[i][0], building_coords[i][1],
                        building_coords[next_i][0], building_coords[next_i][1]
                    )
                
                # Assume ~25% of perimeter faces street (typical for rectangular lots)
                building_frontage = building_perimeter * 0.25
                built_frontage_m += min(building_frontage, closest_segment_length)
        
        # Calculate continuity ratio
        continuity_ratio = built_frontage_m / street_frontage_m if street_frontage_m > 0 else 0.0
        
        # Normalize to 0-100 scale
        # Typical values:
        # - Urban core (Park Slope): > 0.6 ratio → score > 80
        # - Urban historic (Savannah): > 0.5 ratio → score > 70
        # - Suburban (Larchmont): 0.3-0.5 ratio → score 40-60
        # - Estate suburbs (Beverly Hills): < 0.3 ratio → score < 40
        
        if continuity_ratio >= 0.6:
            streetwall_continuity = 80.0 + (continuity_ratio - 0.6) / 0.4 * 20
        elif continuity_ratio >= 0.5:
            streetwall_continuity = 70.0 + (continuity_ratio - 0.5) / 0.1 * 10
        elif continuity_ratio >= 0.3:
            streetwall_continuity = 40.0 + (continuity_ratio - 0.3) / 0.2 * 30
        elif continuity_ratio >= 0.1:
            streetwall_continuity = 20.0 + (continuity_ratio - 0.1) / 0.2 * 20
        else:
            streetwall_continuity = continuity_ratio / 0.1 * 20
        
        streetwall_continuity = max(0.0, min(100.0, streetwall_continuity))
        
        # Coverage confidence (based on building density near roads)
        area_sqkm = math.pi * (radius_m / 1000) ** 2
        buildings_per_sqkm = len(building_ways) / area_sqkm if area_sqkm > 0 else 0.0
        # Typical: 50-200 buildings/sqkm for urban, 20-50 for suburban
        expected_buildings = 50.0  # Minimum for good coverage
        coverage_confidence = min(1.0, buildings_per_sqkm / expected_buildings if expected_buildings > 0 else 0.0)
        
        return {
            "streetwall_continuity": round(streetwall_continuity, 1),
            "street_frontage_m": round(street_frontage_m, 1),
            "built_frontage_m": round(built_frontage_m, 1),
            "continuity_ratio": round(continuity_ratio, 3),
            "coverage_confidence": round(coverage_confidence, 2)
        }
        
    except Exception as e:
        print(f"⚠️  Streetwall continuity calculation error: {e}")
        return {
            "streetwall_continuity": 0.0,
            "street_frontage_m": 0.0,
            "built_frontage_m": 0.0,
            "continuity_ratio": 0.0,
            "coverage_confidence": 0.0
        }


def compute_setback_consistency(lat: float, lon: float, radius_m: int = 1000,
                                osm_data: Optional[Dict] = None) -> Dict[str, float]:
    """
    Compute setback consistency metric: measures uniformity of building setbacks along streets.
    
    Setback consistency = how uniform building setbacks are per road segment (lower variance = higher score).
    Higher = more consistent setbacks, more cohesive streetscape.
    
    Args:
        lat, lon: Center coordinates
        radius_m: Search radius in meters
    
    Returns:
        {
            "setback_consistency": float (0-100, normalized),
            "mean_setback_m": float,
            "setback_variance_m2": float,
            "setback_std_dev_m": float,
            "segments_analyzed": int,
            "buildings_analyzed": int,
            "coverage_confidence": float (0.0-1.0)
        }
    """
    try:
        # Use shared OSM data if provided, otherwise fetch
        if osm_data is None:
            osm_data = _fetch_roads_and_buildings(lat, lon, radius_m)
        
        if osm_data is None:
            return {
                "setback_consistency": 0.0,
                "mean_setback_m": 0.0,
                "setback_variance_m2": 0.0,
                "setback_std_dev_m": 0.0,
                "segments_analyzed": 0,
                "buildings_analyzed": 0,
                "coverage_confidence": 0.0
            }
        
        nodes_dict = osm_data["nodes_dict"]
        road_ways = osm_data["road_ways"]
        building_ways = osm_data["building_ways"]
        
        if not road_ways or not building_ways:
            return {
                "setback_consistency": 0.0,
                "mean_setback_m": 0.0,
                "setback_variance_m2": 0.0,
                "setback_std_dev_m": 0.0,
                "segments_analyzed": 0,
                "buildings_analyzed": 0,
                "coverage_confidence": 0.0
            }
        
        # Pre-compute road segments
        road_segments_precomputed = []
        for road_way in road_ways:
            road_nodes = road_way.get("nodes", [])
            if len(road_nodes) < 2:
                continue
            
            road_coords = []
            for node_id in road_nodes:
                if node_id in nodes_dict:
                    node = nodes_dict[node_id]
                    road_coords.append((node["lat"], node["lon"]))
            
            if len(road_coords) < 2:
                continue
            
            # Store all segments for this road
            for i in range(len(road_coords) - 1):
                segment_length = haversine_distance(
                    road_coords[i][0], road_coords[i][1],
                    road_coords[i + 1][0], road_coords[i + 1][1]
                )
                road_segments_precomputed.append({
                    "start": road_coords[i],
                    "end": road_coords[i + 1],
                    "length": segment_length,
                    "road_id": road_way.get("id")  # Group buildings by road
                })
        
        if not road_segments_precomputed:
            return {
                "setback_consistency": 0.0,
                "mean_setback_m": 0.0,
                "setback_variance_m2": 0.0,
                "setback_std_dev_m": 0.0,
                "segments_analyzed": 0,
                "buildings_analyzed": 0,
                "coverage_confidence": 0.0
            }
        
        # For each building, find closest road segment and calculate setback
        # Group setbacks by road segment for statistical analysis
        segment_setbacks = {}  # segment_id -> list of setbacks
        
        for building in building_ways:
            nodes = building.get("nodes", [])
            if not nodes:
                continue
            
            # Get building polygon coordinates
            building_coords = []
            for node_id in nodes:
                if node_id in nodes_dict:
                    node = nodes_dict[node_id]
                    building_coords.append((node["lat"], node["lon"]))
            
            if len(building_coords) < 3:  # Need at least 3 points for a polygon
                continue
            
            # Find closest edge of building to nearest road segment
            min_setback = float('inf')
            closest_segment_id = None
            
            for segment in road_segments_precomputed:
                # Find closest point on building edge to this road segment
                # For efficiency, check closest building edge (not all edges)
                # Find the closest edge of the building polygon to the road segment
                for i in range(len(building_coords)):
                    edge_start = building_coords[i]
                    edge_end = building_coords[(i + 1) % len(building_coords)]
                    
                    # Find closest point on building edge to road segment
                    # Use the midpoint of the building edge as proxy
                    edge_mid_lat = (edge_start[0] + edge_end[0]) / 2
                    edge_mid_lon = (edge_start[1] + edge_end[1]) / 2
                    
                    # Calculate distance from edge midpoint to road segment
                    _, _, dist = _compute_point_on_line(
                        (edge_mid_lat, edge_mid_lon),
                        segment["start"],
                        segment["end"]
                    )
                    
                    if dist < min_setback:
                        min_setback = dist
                        closest_segment_id = segment["road_id"]
            
            # Only consider buildings within reasonable distance (50m) of a road
            if min_setback <= 50.0 and closest_segment_id is not None:
                if closest_segment_id not in segment_setbacks:
                    segment_setbacks[closest_segment_id] = []
                segment_setbacks[closest_segment_id].append(min_setback)
        
        # Calculate variance per segment (need at least 3 buildings per segment for meaningful stats)
        MIN_BUILDINGS_PER_SEGMENT = 3
        all_setbacks = []
        segment_variances = []
        
        for segment_id, setbacks in segment_setbacks.items():
            if len(setbacks) >= MIN_BUILDINGS_PER_SEGMENT:
                # Calculate variance for this segment
                mean_setback = sum(setbacks) / len(setbacks)
                variance = sum((s - mean_setback) ** 2 for s in setbacks) / len(setbacks)
                segment_variances.append(variance)
                all_setbacks.extend(setbacks)
        
        # Calculate overall statistics
        if not all_setbacks:
            return {
                "setback_consistency": 0.0,
                "mean_setback_m": 0.0,
                "setback_variance_m2": 0.0,
                "setback_std_dev_m": 0.0,
                "segments_analyzed": 0,
                "buildings_analyzed": 0,
                "coverage_confidence": 0.0
            }
        
        mean_setback = sum(all_setbacks) / len(all_setbacks)
        overall_variance = sum((s - mean_setback) ** 2 for s in all_setbacks) / len(all_setbacks)
        std_dev = math.sqrt(overall_variance)
        
        # Use weighted average of segment variances (weight by number of buildings)
        if segment_variances and segment_setbacks:
            # Get segment IDs that have enough buildings
            valid_segment_ids = [seg_id for seg_id, setbacks in segment_setbacks.items() 
                               if len(setbacks) >= MIN_BUILDINGS_PER_SEGMENT]
            total_buildings_in_valid_segments = sum(len(segment_setbacks[seg_id]) for seg_id in valid_segment_ids)
            
            if total_buildings_in_valid_segments > 0:
                weighted_variance = sum(
                    segment_variances[i] * len(segment_setbacks[valid_segment_ids[i]])
                    for i in range(len(segment_variances))
                ) / total_buildings_in_valid_segments
            else:
                weighted_variance = overall_variance
        else:
            weighted_variance = overall_variance
        
        # Normalize to 0-100 scale (lower variance = higher score)
        # Typical values:
        # - Very consistent (urban core): std_dev < 2m → score > 90
        # - Consistent (suburban): std_dev 2-5m → score 70-90
        # - Moderate (exurban): std_dev 5-10m → score 50-70
        # - Inconsistent (rural): std_dev > 10m → score < 50
        
        std_dev_for_scoring = math.sqrt(weighted_variance) if weighted_variance > 0 else float('inf')
        
        if std_dev_for_scoring <= 2.0:
            setback_consistency = 90.0 + (2.0 - std_dev_for_scoring) / 2.0 * 10.0
        elif std_dev_for_scoring <= 5.0:
            setback_consistency = 70.0 + (5.0 - std_dev_for_scoring) / 3.0 * 20.0
        elif std_dev_for_scoring <= 10.0:
            setback_consistency = 50.0 + (10.0 - std_dev_for_scoring) / 5.0 * 20.0
        elif std_dev_for_scoring <= 15.0:
            setback_consistency = 30.0 + (15.0 - std_dev_for_scoring) / 5.0 * 20.0
        else:
            setback_consistency = max(0.0, 30.0 - (std_dev_for_scoring - 15.0) / 5.0 * 10.0)
        
        setback_consistency = max(0.0, min(100.0, setback_consistency))
        
        # Coverage confidence (based on number of segments with sufficient buildings)
        total_segments = len(road_segments_precomputed)
        analyzed_segments = len([s for s in segment_setbacks.values() if len(s) >= MIN_BUILDINGS_PER_SEGMENT])
        coverage_confidence = min(1.0, analyzed_segments / max(1, total_segments // 4))  # Expect ~25% of segments to have buildings
        
        return {
            "setback_consistency": round(setback_consistency, 1),
            "mean_setback_m": round(mean_setback, 2),
            "setback_variance_m2": round(weighted_variance, 2),
            "setback_std_dev_m": round(std_dev_for_scoring, 2),
            "segments_analyzed": analyzed_segments,
            "buildings_analyzed": len(all_setbacks),
            "coverage_confidence": round(coverage_confidence, 2)
        }
        
    except Exception as e:
        print(f"⚠️  Setback consistency calculation error: {e}")
        return {
            "setback_consistency": 0.0,
            "mean_setback_m": 0.0,
            "setback_variance_m2": 0.0,
            "setback_std_dev_m": 0.0,
            "segments_analyzed": 0,
            "buildings_analyzed": 0,
            "coverage_confidence": 0.0
        }


def compute_facade_rhythm(lat: float, lon: float, radius_m: int = 1000,
                          osm_data: Optional[Dict] = None) -> Dict[str, float]:
    """
    Compute facade rhythm metric: measures alignment of building facades along streets.
    
    Facade rhythm = proportion of buildings within tolerance of local mean setback (higher = more aligned).
    Higher = more rhythmic facade alignment, more cohesive visual cadence.
    
    Args:
        lat, lon: Center coordinates
        radius_m: Search radius in meters
    
    Returns:
        {
            "facade_rhythm": float (0-100, normalized),
            "alignment_percentage": float (0-100),
            "mean_setback_m": float,
            "tolerance_m": float,
            "segments_analyzed": int,
            "buildings_analyzed": int,
            "coverage_confidence": float (0.0-1.0)
        }
    """
    try:
        # Use shared OSM data if provided, otherwise fetch
        if osm_data is None:
            osm_data = _fetch_roads_and_buildings(lat, lon, radius_m)
        
        if osm_data is None:
            return {
                "facade_rhythm": 0.0,
                "alignment_percentage": 0.0,
                "mean_setback_m": 0.0,
                "tolerance_m": 0.0,
                "segments_analyzed": 0,
                "buildings_analyzed": 0,
                "coverage_confidence": 0.0
            }
        
        nodes_dict = osm_data["nodes_dict"]
        road_ways = osm_data["road_ways"]
        building_ways = osm_data["building_ways"]
        
        if not road_ways or not building_ways:
            return {
                "facade_rhythm": 0.0,
                "alignment_percentage": 0.0,
                "mean_setback_m": 0.0,
                "tolerance_m": 0.0,
                "segments_analyzed": 0,
                "buildings_analyzed": 0,
                "coverage_confidence": 0.0
            }
        
        # Pre-compute road segments
        road_segments_precomputed = []
        for road_way in road_ways:
            road_nodes = road_way.get("nodes", [])
            if len(road_nodes) < 2:
                continue
            
            road_coords = []
            for node_id in road_nodes:
                if node_id in nodes_dict:
                    node = nodes_dict[node_id]
                    road_coords.append((node["lat"], node["lon"]))
            
            if len(road_coords) < 2:
                continue
            
            # Store all segments for this road
            for i in range(len(road_coords) - 1):
                segment_length = haversine_distance(
                    road_coords[i][0], road_coords[i][1],
                    road_coords[i + 1][0], road_coords[i + 1][1]
                )
                road_segments_precomputed.append({
                    "start": road_coords[i],
                    "end": road_coords[i + 1],
                    "length": segment_length,
                    "road_id": road_way.get("id")  # Group buildings by road
                })
        
        if not road_segments_precomputed:
            return {
                "facade_rhythm": 0.0,
                "alignment_percentage": 0.0,
                "mean_setback_m": 0.0,
                "tolerance_m": 0.0,
                "segments_analyzed": 0,
                "buildings_analyzed": 0,
                "coverage_confidence": 0.0
            }
        
        # For each building, find closest road segment and calculate setback
        # Group setbacks by road segment
        segment_setbacks = {}  # segment_id -> list of setbacks
        
        for building in building_ways:
            nodes = building.get("nodes", [])
            if not nodes:
                continue
            
            # Get building polygon coordinates
            building_coords = []
            for node_id in nodes:
                if node_id in nodes_dict:
                    node = nodes_dict[node_id]
                    building_coords.append((node["lat"], node["lon"]))
            
            if len(building_coords) < 3:
                continue
            
            # Find closest edge of building to nearest road segment
            min_setback = float('inf')
            closest_segment_id = None
            
            for segment in road_segments_precomputed:
                # Find closest edge of building to road segment
                for i in range(len(building_coords)):
                    edge_start = building_coords[i]
                    edge_end = building_coords[(i + 1) % len(building_coords)]
                    
                    edge_mid_lat = (edge_start[0] + edge_end[0]) / 2
                    edge_mid_lon = (edge_start[1] + edge_end[1]) / 2
                    
                    _, _, dist = _compute_point_on_line(
                        (edge_mid_lat, edge_mid_lon),
                        segment["start"],
                        segment["end"]
                    )
                    
                    if dist < min_setback:
                        min_setback = dist
                        closest_segment_id = segment["road_id"]
            
            if min_setback <= 50.0 and closest_segment_id is not None:
                if closest_segment_id not in segment_setbacks:
                    segment_setbacks[closest_segment_id] = []
                segment_setbacks[closest_segment_id].append(min_setback)
        
        # Calculate alignment per segment (need at least 3 buildings per segment)
        MIN_BUILDINGS_PER_SEGMENT = 3
        TOLERANCE_M = 2.0  # Buildings within ±2m of mean count as aligned
        
        total_buildings = 0
        aligned_buildings = 0
        analyzed_segments = 0
        
        for segment_id, setbacks in segment_setbacks.items():
            if len(setbacks) >= MIN_BUILDINGS_PER_SEGMENT:
                analyzed_segments += 1
                mean_setback = sum(setbacks) / len(setbacks)
                
                # Count buildings within tolerance
                for setback in setbacks:
                    total_buildings += 1
                    if abs(setback - mean_setback) <= TOLERANCE_M:
                        aligned_buildings += 1
        
        # Calculate alignment percentage
        alignment_percentage = (aligned_buildings / total_buildings * 100.0) if total_buildings > 0 else 0.0
        
        # Normalize to 0-100 scale (alignment percentage = score)
        facade_rhythm = alignment_percentage
        
        # Coverage confidence
        total_segments = len(road_segments_precomputed)
        coverage_confidence = min(1.0, analyzed_segments / max(1, total_segments // 4))
        
        # Calculate overall mean setback
        all_setbacks = []
        for setbacks in segment_setbacks.values():
            all_setbacks.extend(setbacks)
        mean_setback = sum(all_setbacks) / len(all_setbacks) if all_setbacks else 0.0
        
        return {
            "facade_rhythm": round(facade_rhythm, 1),
            "alignment_percentage": round(alignment_percentage, 1),
            "mean_setback_m": round(mean_setback, 2),
            "tolerance_m": TOLERANCE_M,
            "segments_analyzed": analyzed_segments,
            "buildings_analyzed": total_buildings,
            "coverage_confidence": round(coverage_confidence, 2)
        }
        
    except Exception as e:
        print(f"⚠️  Facade rhythm calculation error: {e}")
        return {
            "facade_rhythm": 0.0,
            "alignment_percentage": 0.0,
            "mean_setback_m": 0.0,
            "tolerance_m": 0.0,
            "segments_analyzed": 0,
            "buildings_analyzed": 0,
            "coverage_confidence": 0.0
        }

