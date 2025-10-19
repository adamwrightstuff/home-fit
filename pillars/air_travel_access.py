"""
Air Travel Access Pillar
Scores access to airports for air travel
"""

import math
from typing import Dict, Tuple, List, Optional

# Major US airports database
# Data from OurAirports.com (simplified for key US airports)
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


def get_air_travel_score(lat: float, lon: float) -> Tuple[float, Dict]:
    """
    Calculate air travel access score (0-100) based on airport proximity.

    Scoring:
    - International hub <30km (25km): 100 points
    - International hub 30-50km: 80 points
    - International hub 50-75km: 60 points
    - International hub 75-100km: 40 points
    - Regional airport only: 30-40 points based on distance
    - >100km to any airport: 20 points

    Returns:
        (total_score, detailed_breakdown)
    """
    print(f"✈️  Analyzing air travel access...")

    # Find nearest airports
    airports_with_distance = []
    for code, name, apt_lat, apt_lon, apt_type in MAJOR_AIRPORTS:
        distance_km = _haversine_distance(lat, lon, apt_lat, apt_lon) / 1000
        airports_with_distance.append({
            "code": code,
            "name": name,
            "type": apt_type,
            "distance_km": round(distance_km, 1),
            "lat": apt_lat,
            "lon": apt_lon
        })

    # Sort by distance
    airports_with_distance.sort(key=lambda x: x["distance_km"])

    # Get nearest of each type
    nearest_large = next((a for a in airports_with_distance if a["type"] == "large_airport"), None)
    nearest_medium = next((a for a in airports_with_distance if a["type"] == "medium_airport"), None)
    nearest_any = airports_with_distance[0] if airports_with_distance else None

    # Calculate score
    if nearest_large:
        dist = nearest_large["distance_km"]
        if dist <= 25:
            score = 100.0
        elif dist <= 50:
            score = 80.0
        elif dist <= 75:
            score = 60.0
        elif dist <= 100:
            score = 40.0
        else:
            score = 20.0
        primary_airport = nearest_large
        airport_category = "International hub"
    elif nearest_medium:
        dist = nearest_medium["distance_km"]
        if dist <= 25:
            score = 40.0
        elif dist <= 50:
            score = 35.0
        elif dist <= 75:
            score = 30.0
        else:
            score = 20.0
        primary_airport = nearest_medium
        airport_category = "Regional airport"
    else:
        score = 0.0
        primary_airport = None
        airport_category = "No nearby airports"

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
        "summary": _build_summary(nearest_large, nearest_medium, score)
    }

    # Log results
    if primary_airport:
        print(f"✅ Air Travel Score: {score:.0f}/100")
        print(f"   ✈️  Nearest: {primary_airport['name']} ({primary_airport['code']})")
        print(f"   📍 Distance: {primary_airport['distance_km']:.1f}km")
        print(f"   🏢 Type: {airport_category}")
    else:
        print(f"⚠️  Air Travel Score: 0/100 - No major airports nearby")

    return round(score, 1), breakdown


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