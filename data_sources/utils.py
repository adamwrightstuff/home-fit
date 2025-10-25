"""
Shared utilities for HomeFit data sources
Consolidates common functions like distance calculations and scoring helpers
"""

import math
from typing import List, Dict, Tuple, Optional


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate distance between two points in meters using the Haversine formula.
    
    Args:
        lat1, lon1: First point coordinates
        lat2, lon2: Second point coordinates
    
    Returns:
        Distance in meters
    """
    R = 6371000  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi/2)**2 + math.cos(phi1) * \
        math.cos(phi2) * math.sin(delta_lambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

    return R * c


def find_nearest_features(features: List[Dict], lat: float, lon: float, 
                         max_distance_m: Optional[float] = None) -> List[Dict]:
    """
    Find nearest features to a given location.
    
    Args:
        features: List of feature dictionaries with 'lat' and 'lon' keys
        lat, lon: Center coordinates
        max_distance_m: Optional maximum distance filter
    
    Returns:
        List of features sorted by distance, with 'distance_m' added
    """
    features_with_distance = []
    
    for feature in features:
        if 'lat' not in feature or 'lon' not in feature:
            continue
            
        distance_m = haversine_distance(lat, lon, feature['lat'], feature['lon'])
        
        if max_distance_m is None or distance_m <= max_distance_m:
            feature_copy = feature.copy()
            feature_copy['distance_m'] = round(distance_m, 0)
            features_with_distance.append(feature_copy)
    
    # Sort by distance
    features_with_distance.sort(key=lambda x: x['distance_m'])
    return features_with_distance


def calculate_distance_score(distance_m: float, thresholds: List[Tuple[float, float]]) -> float:
    """
    Calculate score based on distance using configurable thresholds.
    
    Args:
        distance_m: Distance in meters
        thresholds: List of (max_distance, score) tuples, sorted by distance
    
    Returns:
        Score based on distance
    """
    for max_distance, score in thresholds:
        if distance_m <= max_distance:
            return score
    
    # If distance exceeds all thresholds, return 0
    return 0.0


def calculate_count_score(count: int, thresholds: List[Tuple[int, float]]) -> float:
    """
    Calculate score based on count using configurable thresholds.
    
    Args:
        count: Number of items
        thresholds: List of (min_count, score) tuples, sorted by count
    
    Returns:
        Score based on count
    """
    for min_count, score in thresholds:
        if count >= min_count:
            return score
    
    # If count is below all thresholds, return 0
    return 0.0


def calculate_variety_score(categories: List[List], weights: List[float]) -> float:
    """
    Calculate variety score based on category diversity.
    
    Args:
        categories: List of category lists (e.g., [tier1, tier2, tier3, tier4])
        weights: List of weights for each category
    
    Returns:
        Variety score
    """
    if len(categories) != len(weights):
        raise ValueError("Categories and weights must have same length")
    
    total_score = 0.0
    
    for category, weight in zip(categories, weights):
        # Count unique types in this category
        unique_types = set(item.get('type', 'unknown') for item in category)
        type_count = len(unique_types)
        
        # Score based on variety (2+ types gets full weight)
        if type_count >= 2:
            category_score = weight
        elif type_count == 1:
            category_score = weight * 0.5
        else:
            category_score = 0.0
        
        total_score += category_score
    
    return total_score


def get_way_center(elem: Dict, nodes_dict: Dict) -> Tuple[Optional[float], Optional[float], float]:
    """
    Calculate centroid and area of a way from OSM data.
    
    Args:
        elem: OSM way element
        nodes_dict: Dictionary of node elements
    
    Returns:
        Tuple of (lat, lon, area_sqm)
    """
    if elem.get("type") != "way" or "nodes" not in elem:
        return None, None, 0

    coords = []
    for node_id in elem["nodes"]:
        if node_id in nodes_dict:
            node = nodes_dict[node_id]
            if "lat" in node and "lon" in node:
                coords.append((node["lat"], node["lon"]))

    if not coords:
        return None, None, 0

    lat = sum(c[0] for c in coords) / len(coords)
    lon = sum(c[1] for c in coords) / len(coords)

    area = 0
    if len(coords) >= 3:
        for i in range(len(coords)):
            j = (i + 1) % len(coords)
            area += coords[i][0] * coords[j][1]
            area -= coords[j][0] * coords[i][1]
        area = abs(area) / 2
        area = area * 111000 * 111000 * math.cos(math.radians(lat))

    return lat, lon, area


def deduplicate_by_proximity(features: List[Dict], max_distance_m: float) -> List[Dict]:
    """
    Remove duplicate features within a specified distance.
    
    Args:
        features: List of feature dictionaries
        max_distance_m: Maximum distance for considering duplicates
    
    Returns:
        List of unique features
    """
    if len(features) <= 1:
        return features

    unique = []
    for feature in sorted(features, key=lambda x: x.get("area_sqm", 0), reverse=True):
        is_duplicate = False
        for existing in unique:
            dist = haversine_distance(
                feature["lat"], feature["lon"],
                existing["lat"], existing["lon"]
            )
            if dist < max_distance_m:
                is_duplicate = True
                break

        if not is_duplicate:
            unique.append(feature)

    return unique


def build_summary_stats(features: List[Dict], center_lat: float, center_lon: float) -> Dict:
    """
    Build summary statistics for a list of features.
    
    Args:
        features: List of feature dictionaries
        center_lat, center_lon: Center coordinates for distance calculations
    
    Returns:
        Dictionary with summary statistics
    """
    if not features:
        return {
            "count": 0,
            "nearest_distance_m": None,
            "median_distance_m": None,
            "within_5min_walk": 0,
            "within_10min_walk": 0
        }
    
    distances = [f.get('distance_m', 0) for f in features]
    distances.sort()
    
    return {
        "count": len(features),
        "nearest_distance_m": min(distances) if distances else None,
        "median_distance_m": distances[len(distances) // 2] if distances else None,
        "within_5min_walk": len([d for d in distances if d <= 400]),
        "within_10min_walk": len([d for d in distances if d <= 800])
    }


def validate_coordinates(lat: float, lon: float) -> bool:
    """
    Validate that coordinates are within valid ranges.
    
    Args:
        lat, lon: Coordinates to validate
    
    Returns:
        True if coordinates are valid
    """
    return -90 <= lat <= 90 and -180 <= lon <= 180


def format_distance(distance_m: float) -> str:
    """
    Format distance in a human-readable way.
    
    Args:
        distance_m: Distance in meters
    
    Returns:
        Formatted distance string
    """
    if distance_m < 1000:
        return f"{int(distance_m)}m"
    else:
        return f"{distance_m/1000:.1f}km"
