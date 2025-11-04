"""
Air Travel Access Pillar
Scores access to airports for air travel
"""

import json
import math
from typing import Dict, Tuple, List, Optional
from data_sources.data_quality import assess_pillar_data_quality
from data_sources.regional_baselines import get_area_classification, get_contextual_expectations

# Load comprehensive airport database
def _load_airport_database() -> List[Dict]:
    """Load comprehensive airport database from JSON file."""
    import os
    # Get the path relative to this file's location
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)  # Go up from 'pillars' to project root
    airport_file = os.path.join(project_root, 'data_sources', 'static', 'airports.json')
    
    try:
        with open(airport_file, 'r') as f:
            data = json.load(f)
            airports = data.get('airports', [])
            print(f"✅ Loaded {len(airports)} airports from {airport_file}")
            return airports
    except FileNotFoundError:
        print(f"⚠️  Airport database not found at {airport_file}, using fallback")
        return []
    except Exception as e:
        print(f"⚠️  Error loading airport database: {e}, using fallback")
        return []

# Load airports on module import
AIRPORT_DATABASE = _load_airport_database()

# Legacy airport data for backward compatibility
MAJOR_AIRPORTS = [
    # Format: (code, name, lat, lon, type)
    # Type: "large_airport" = international hub, "medium_airport" = regional
    
    # Northeast
    ("JFK", "John F Kennedy International", 40.6413, -73.7781, "large_airport"),
    ("EWR", "Newark Liberty International", 40.6895, -74.1745, "large_airport"),
    ("LGA", "LaGuardia", 40.7769, -73.8740, "large_airport"),
    ("BOS", "Boston Logan International", 42.3656, -71.0096, "large_airport"),
    ("PHL", "Philadelphia International", 39.8729, -75.2437, "large_airport"),
    ("BWI", "Baltimore/Washington International", 39.1754, -76.6683, "large_airport"),
    ("IAD", "Washington Dulles International", 38.9531, -77.4565, "large_airport"),
    ("DCA", "Ronald Reagan Washington National", 38.8521, -77.0377, "large_airport"),
    
    # Southeast
    ("ATL", "Hartsfield-Jackson Atlanta International", 33.6407, -84.4277, "large_airport"),
    ("MIA", "Miami International", 25.7959, -80.2870, "large_airport"),
    ("FLL", "Fort Lauderdale-Hollywood International", 26.0742, -80.1506, "large_airport"),
    ("MCO", "Orlando International", 28.4312, -81.3081, "large_airport"),
    ("TPA", "Tampa International", 27.9755, -82.5332, "large_airport"),
    ("CLT", "Charlotte Douglas International", 35.2144, -80.9473, "large_airport"),
    ("RDU", "Raleigh-Durham International", 35.8801, -78.7880, "large_airport"),
    
    # Midwest
    ("ORD", "Chicago O'Hare International", 41.9742, -87.9073, "large_airport"),
    ("MDW", "Chicago Midway International", 41.7868, -87.7522, "medium_airport"),
    ("DTW", "Detroit Metropolitan Wayne County", 42.2162, -83.3554, "large_airport"),
    ("MSP", "Minneapolis-St Paul International", 44.8848, -93.2223, "large_airport"),
    ("STL", "St Louis Lambert International", 38.7499, -90.3700, "large_airport"),
    ("CVG", "Cincinnati/Northern Kentucky International", 39.0533, -84.6630, "large_airport"),
    ("CLE", "Cleveland Hopkins International", 41.4057, -81.8498, "large_airport"),
    ("IND", "Indianapolis International", 39.7173, -86.2944, "large_airport"),
    ("CMH", "John Glenn Columbus International", 40.0799, -82.8872, "large_airport"),
    ("MKE", "Milwaukee Mitchell International", 42.9472, -87.8966, "medium_airport"),
    
    # Southwest
    ("DFW", "Dallas/Fort Worth International", 32.8998, -97.0403, "large_airport"),
    ("DAL", "Dallas Love Field", 32.8470, -96.8517, "medium_airport"),
    ("IAH", "George Bush Intercontinental Houston", 29.9902, -95.3368, "large_airport"),
    ("HOU", "William P Hobby Airport", 29.6454, -95.2789, "medium_airport"),
    ("AUS", "Austin-Bergstrom International", 30.1945, -97.6699, "large_airport"),
    ("SAT", "San Antonio International", 29.5337, -98.4698, "medium_airport"),
    ("MSY", "Louis Armstrong New Orleans International", 29.9934, -90.2580, "large_airport"),
    ("OKC", "Will Rogers World Airport", 35.3931, -97.6007, "medium_airport"),
    
    # Mountain West
    ("DEN", "Denver International", 39.8561, -104.6737, "large_airport"),
    ("SLC", "Salt Lake City International", 40.7899, -111.9791, "large_airport"),
    ("PHX", "Phoenix Sky Harbor International", 33.4484, -112.0740, "large_airport"),
    ("LAS", "Harry Reid International Las Vegas", 36.0840, -115.1537, "large_airport"),
    ("ABQ", "Albuquerque International Sunport", 35.0402, -106.6092, "medium_airport"),
    ("TUS", "Tucson International", 32.1161, -110.9410, "medium_airport"),
    ("BOI", "Boise Airport", 43.5644, -116.2228, "medium_airport"),
    
    # West Coast
    ("LAX", "Los Angeles International", 33.9416, -118.4085, "large_airport"),
    ("SFO", "San Francisco International", 37.6213, -122.3790, "large_airport"),
    ("SJC", "San Jose International", 37.3639, -121.9289, "large_airport"),
    ("OAK", "Oakland International", 37.7126, -122.2197, "large_airport"),
    ("SAN", "San Diego International", 32.7336, -117.1897, "large_airport"),
    ("SEA", "Seattle-Tacoma International", 47.4502, -122.3088, "large_airport"),
    ("PDX", "Portland International", 45.5898, -122.5951, "large_airport"),
    ("SMF", "Sacramento International", 38.6954, -121.5901, "medium_airport"),
    ("ONT", "Ontario International", 34.0560, -117.6012, "medium_airport"),
    ("SNA", "John Wayne Orange County", 33.6757, -117.8682, "medium_airport"),
    ("BUR", "Hollywood Burbank", 34.2007, -118.3590, "medium_airport"),
    ("LGB", "Long Beach", 33.8177, -118.1516, "medium_airport"),
    
    # Pacific
    ("HNL", "Daniel K Inouye International Honolulu", 21.3187, -157.9225, "large_airport"),
    
    # Alaska
    ("ANC", "Ted Stevens Anchorage International", 61.1743, -149.9962, "large_airport"),
]


def get_air_travel_score(lat: float, lon: float, area_type: Optional[str] = None) -> Tuple[float, Dict]:
    """
    Calculate air travel access score (0-100) based on multi-airport proximity.

    Scoring:
    - Considers best 3 airports within 100km
    - Weights by airport size and distance
    - Bonus for airport choice/redundancy
    - Smooth distance decay curves

    Args:
        area_type: Optional pre-computed area type (for consistency across pillars)

    Returns:
        (total_score, detailed_breakdown)
    """
    print(f"✈️  Analyzing air travel access...")

    # Get area classification for contextual scoring (use provided if available)
    if area_type:
        # Use provided area_type, but still need metro_name for metadata
        from data_sources.regional_baselines import regional_baseline_manager
        from data_sources.census_api import get_population_density
        density = get_population_density(lat, lon)
        metro_name = regional_baseline_manager._detect_metro_area(None, lat, lon)
        area_metadata = {
            'density': density,
            'metro_name': metro_name,
            'area_type': area_type,
            'classification_confidence': regional_baseline_manager._get_classification_confidence(density, metro_name)
        }
    else:
        # Fallback to computing classification if not provided
        area_type, metro_name, area_metadata = get_area_classification(lat, lon)
    
    expectations = get_contextual_expectations(area_type, 'air_travel_access')

    # Find all airports within 100km
    airports_with_distance = []
    
    # Use comprehensive database if available, otherwise fallback to legacy
    airport_list = AIRPORT_DATABASE if AIRPORT_DATABASE else MAJOR_AIRPORTS
    
    for airport in airport_list:
        if isinstance(airport, dict):
            # New format from JSON
            apt_lat = airport.get('lat')
            apt_lon = airport.get('lon')
            code = airport.get('code')
            name = airport.get('name')
            apt_type = airport.get('type')
        else:
            # Legacy format
            code, name, apt_lat, apt_lon, apt_type = airport
        
        # Skip if coordinates are missing
        if apt_lat is None or apt_lon is None:
            continue
        
        distance_km = _haversine_distance(lat, lon, apt_lat, apt_lon) / 1000
        
        # Only include airports within 100km
        if distance_km <= 100:
            airports_with_distance.append({
                "code": code,
                "name": name,
                "type": apt_type,
                "distance_km": round(distance_km, 1),
                "lat": apt_lat,
                "lon": apt_lon,
                "service_level": airport.get('service_level', 'unknown') if isinstance(airport, dict) else 'unknown'
            })

    # Sort by distance
    airports_with_distance.sort(key=lambda x: x["distance_km"])

    # Assess data quality
    airport_data = {'airports': airports_with_distance}
    quality_metrics = assess_pillar_data_quality('air_travel_access', airport_data, lat, lon, area_type)
    
    # Multi-airport scoring
    score, primary_airport, airport_category = _calculate_multi_airport_score(
        airports_with_distance, expectations
    )

    # Build response
    breakdown = {
        "score": round(score, 1),
        "primary_airport": {
            "code": primary_airport["code"],
            "name": primary_airport["name"],
            "distance_km": primary_airport["distance_km"],
            "type": airport_category
        } if primary_airport else None,
        "nearest_airports": airports_with_distance[:5],  # Top 5 nearest
        "summary": _build_summary(
            next((a for a in airports_with_distance if a["type"] == "large_airport"), None),
            next((a for a in airports_with_distance if a["type"] == "medium_airport"), None),
            score
        ),
        "data_quality": quality_metrics,
        "area_classification": area_metadata
    }

    # Log results
    if primary_airport:
        print(f"✅ Air Travel Score: {score:.0f}/100")
        print(f"   ✈️  Nearest: {primary_airport['name']} ({primary_airport['code']})")
        print(f"   📍 Distance: {primary_airport['distance_km']:.1f}km")
        print(f"   🏢 Type: {airport_category}")
        print(f"   📊 Data Quality: {quality_metrics['quality_tier']} ({quality_metrics['confidence']}% confidence)")
    else:
        print(f"⚠️  Air Travel Score: 0/100 - No major airports nearby")

    return round(score, 1), breakdown


def _calculate_multi_airport_score(airports: List[Dict], expectations: Dict) -> Tuple[float, Optional[Dict], str]:
    """
    Calculate score considering multiple airports with smooth decay curves.
    
    Args:
        airports: List of airports with distance information
        expectations: Contextual expectations for the area
    
    Returns:
        Tuple of (score, primary_airport, airport_category)
    """
    if not airports:
        return 0.0, None, "No nearby airports"
    
    # Score the best 3 airports within 100km
    best_airports = airports[:3]
    
    total_score = 0.0
    primary_airport = None
    airport_category = "Unknown"
    
    for i, airport in enumerate(best_airports):
        distance_km = airport["distance_km"]
        apt_type = airport["type"]
        service_level = airport.get("service_level", "unknown")
        
        # Weight decreases for further airports
        weight = 1.0 / (i + 1)  # 1.0, 0.5, 0.33
        
        # Calculate individual airport score
        if apt_type == "large_airport":
            base_score = _score_large_airport_smooth(distance_km, service_level)
            if i == 0:  # Primary airport
                primary_airport = airport
                airport_category = "International hub" if service_level == "international_hub" else "Major hub"
        elif apt_type == "medium_airport":
            base_score = _score_medium_airport_smooth(distance_km, service_level)
            if i == 0 and not primary_airport:  # Primary if no large airport
                primary_airport = airport
                airport_category = "Regional hub" if service_level == "regional_hub" else "Regional airport"
        else:
            base_score = _score_small_airport_smooth(distance_km)
            if i == 0 and not primary_airport:  # Primary if no better options
                primary_airport = airport
                airport_category = "Small airport"
        
        # Apply weight and add to total
        weighted_score = base_score * weight
        total_score += weighted_score
    
    # Bonus for multiple airport options (redundancy)
    if len(best_airports) >= 2:
        redundancy_bonus = min(10, len(best_airports) * 3)  # Up to 10 point bonus
        total_score += redundancy_bonus
    
    # Cap at 100
    final_score = min(100, total_score)
    
    return final_score, primary_airport, airport_category


def _score_large_airport_smooth(distance_km: float, service_level: str) -> float:
    """Score large airport using smooth decay curve."""
    # Base scores by service level
    base_scores = {
        "international_hub": 100.0,
        "major_hub": 90.0,
        "regional_hub": 80.0
    }
    
    max_score = base_scores.get(service_level, 85.0)
    optimal_distance = 25.0  # km
    decay_rate = 0.02  # Steeper decay for airports
    
    if distance_km <= optimal_distance:
        score = max_score
    else:
        # Exponential decay beyond optimal distance
        score = max_score * math.exp(-decay_rate * (distance_km - optimal_distance))
    
    return min(max_score, max(0, score))


def _score_medium_airport_smooth(distance_km: float, service_level: str) -> float:
    """Score medium airport using smooth decay curve."""
    max_score = 60.0
    optimal_distance = 30.0  # km
    decay_rate = 0.015
    
    if distance_km <= optimal_distance:
        score = max_score
    else:
        score = max_score * math.exp(-decay_rate * (distance_km - optimal_distance))
    
    return min(max_score, max(0, score))


def _score_small_airport_smooth(distance_km: float) -> float:
    """Score small airport using smooth decay curve."""
    max_score = 40.0
    optimal_distance = 20.0  # km
    decay_rate = 0.01
    
    if distance_km <= optimal_distance:
        score = max_score
    else:
        score = max_score * math.exp(-decay_rate * (distance_km - optimal_distance))
    
    return min(max_score, max(0, score))


def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points in meters."""
    R = 6371000  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi/2)**2 + math.cos(phi1) * \
        math.cos(phi2) * math.sin(delta_lambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

    return R * c


def _build_summary(nearest_large: Optional[Dict], nearest_medium: Optional[Dict], score: float) -> Dict:
    """Build summary of airport access."""
    summary = {
        "has_international_hub": nearest_large is not None,
        "has_regional_airport": nearest_medium is not None,
        "access_level": _get_access_level(score)
    }

    if nearest_large:
        summary["nearest_international"] = {
            "name": nearest_large["name"],
            "code": nearest_large["code"],
            "distance_km": nearest_large["distance_km"]
        }

    if nearest_medium:
        summary["nearest_regional"] = {
            "name": nearest_medium["name"],
            "code": nearest_medium["code"],
            "distance_km": nearest_medium["distance_km"]
        }

    return summary


def _get_access_level(score: float) -> str:
    """Get human-readable access level."""
    if score >= 80:
        return "Excellent - Major hub nearby"
    elif score >= 60:
        return "Very Good - Hub within 1 hour"
    elif score >= 40:
        return "Good - Hub accessible"
    elif score >= 30:
        return "Fair - Regional airport nearby"
    else:
        return "Limited - Far from major airports"