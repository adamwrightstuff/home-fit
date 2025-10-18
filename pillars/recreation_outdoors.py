"""
Recreation & Outdoors Pillar
Scores access to parks, beaches, trails, and outdoor activities
"""

from typing import Dict, Tuple, Optional
from data_sources import osm_api, nyc_api, census_api


def get_recreation_outdoors_score(lat: float, lon: float, city: Optional[str] = None) -> Tuple[float, Dict]:
    """
    Calculate recreation & outdoors score (0-100) based on access to outdoor activities.

    Scoring:
    - Local Parks & Playgrounds: 0-40 points (within 1km)
    - Water Access (beaches, lakes): 0-30 points (within 15km)
    - Trail Access (hiking, nature reserves): 0-20 points (within 15km)
    - Camping: 0-10 points (within 15km)

    Returns:
        (total_score, detailed_breakdown)
    """
    print(f"🌳 Analyzing recreation & outdoors access...")

    # Get local green spaces (1km)
    print(f"   📍 Querying local parks & playgrounds (1km)...")
    local_data = osm_api.query_green_spaces(lat, lon, radius_m=1000)
    
    # Get regional outdoor activities (15km)
    print(f"   🏔️  Querying regional outdoor activities (15km)...")
    regional_data = osm_api.query_nature_features(lat, lon, radius_m=15000)

    if local_data is None and regional_data is None:
        print("⚠️  OSM data unavailable")
        return 50, _estimated_breakdown()

    # Extract data
    parks = local_data.get("parks", []) if local_data else []
    playgrounds = local_data.get("playgrounds", []) if local_data else []
    
    hiking = regional_data.get("hiking", []) if regional_data else []
    swimming = regional_data.get("swimming", []) if regional_data else []
    camping = regional_data.get("camping", []) if regional_data else []

    # Score components
    local_score = _score_local_recreation(parks, playgrounds)
    water_score = _score_water_access(swimming)
    trail_score = _score_trail_access(hiking)
    camping_score = _score_camping(camping)

    total_score = local_score + water_score + trail_score + camping_score

    # Build response
    breakdown = {
        "score": round(total_score, 1),
        "breakdown": {
            "local_recreation": round(local_score, 1),
            "water_access": round(water_score, 1),
            "trail_access": round(trail_score, 1),
            "camping": round(camping_score, 1)
        },
        "summary": _build_summary(parks, playgrounds, swimming, hiking, camping)
    }

    # Log results
    print(f"✅ Recreation & Outdoors Score: {total_score:.0f}/100")
    print(f"   🏞️  Local Parks & Playgrounds: {local_score:.0f}/40")
    print(f"   🏊 Water Access: {water_score:.0f}/30")
    print(f"   🥾 Trail Access: {trail_score:.0f}/20")
    print(f"   🏕️  Camping: {camping_score:.0f}/10")

    return round(total_score, 1), breakdown


def _score_local_recreation(parks: list, playgrounds: list) -> float:
    """Score local parks and playgrounds (0-40 points)."""
    park_score = _score_parks(parks)  # 0-25
    playground_score = _score_playgrounds(playgrounds)  # 0-15
    return min(40, park_score + playground_score)


def _score_parks(parks: list) -> float:
    """Score parks (0-25 points) based on count and area."""
    if not parks:
        return 0.0

    count = len(parks)
    total_area_sqm = sum(p["area_sqm"] for p in parks)

    # Count score (3 pts per park, max 12)
    count_score = min(12, count * 3)

    # Area score (0-13 points)
    total_hectares = total_area_sqm / 10000
    if total_hectares >= 10:
        area_score = 13
    elif total_hectares >= 5:
        area_score = 10
    elif total_hectares >= 2:
        area_score = 8
    elif total_hectares >= 1:
        area_score = 5
    elif total_hectares >= 0.5:
        area_score = 3
    else:
        area_score = 1

    return min(25, count_score + area_score)


def _score_playgrounds(playgrounds: list) -> float:
    """Score playgrounds (0-15 points) based on count."""
    count = len(playgrounds)
    return min(15, count * 5)


def _score_water_access(swimming: list) -> float:
    """Score water access (0-30 points) based on beaches, lakes, etc."""
    if not swimming:
        return 0.0

    # Find closest water feature
    closest = min(swimming, key=lambda x: x["distance_m"])
    dist = closest["distance_m"]
    feature_type = closest["type"]

    # Score based on type and distance
    if feature_type == "beach":
        if dist <= 2000:
            return 30.0
        elif dist <= 5000:
            return 28.0
        elif dist <= 10000:
            return 25.0
        elif dist <= 15000:
            return 22.0

    elif feature_type in ["lake", "swimming_area"]:
        if dist <= 2000:
            return 28.0
        elif dist <= 5000:
            return 25.0
        elif dist <= 10000:
            return 22.0
        elif dist <= 15000:
            return 18.0

    elif feature_type in ["coastline", "bay"]:
        if dist <= 2000:
            return 15.0
        elif dist <= 5000:
            return 18.0
        elif dist <= 10000:
            return 20.0
        elif dist <= 15000:
            return 22.0

    return 0.0


def _score_trail_access(hiking: list) -> float:
    """Score trail access (0-20 points) based on hiking trails and nature reserves."""
    if not hiking:
        return 0.0

    closest = min(f["distance_m"] for f in hiking)

    if closest <= 2000:
        return 20.0
    elif closest <= 5000:
        return 18.0
    elif closest <= 10000:
        return 15.0
    elif closest <= 15000:
        return 12.0
    else:
        return 8.0


def _score_camping(camping: list) -> float:
    """Score camping access (0-10 points) based on distance."""
    if not camping:
        return 0.0

    closest = min(f["distance_m"] for f in camping)

    if closest <= 5000:
        return 10.0
    elif closest <= 10000:
        return 8.0
    elif closest <= 15000:
        return 6.0
    else:
        return 3.0


def _build_summary(parks: list, playgrounds: list, swimming: list, hiking: list, camping: list) -> Dict:
    """Build summary statistics."""
    summary = {
        "local_recreation": {
            "total_parks": len(parks),
            "total_playgrounds": len(playgrounds),
            "closest_park": None,
            "total_park_area_hectares": round(sum(p["area_sqm"] for p in parks) / 10000, 2) if parks else 0
        },
        "water_access": {
            "available": len(swimming) > 0,
            "nearest": None
        },
        "trail_access": {
            "available": len(hiking) > 0,
            "nearest": None
        },
        "camping": {
            "available": len(camping) > 0,
            "nearest": None
        }
    }

    if parks:
        closest = min(parks, key=lambda x: x["distance_m"])
        summary["local_recreation"]["closest_park"] = {
            "name": closest["name"],
            "distance_m": closest["distance_m"],
            "area_sqm": closest["area_sqm"]
        }

    if swimming:
        nearest = min(swimming, key=lambda x: x["distance_m"])
        summary["water_access"]["nearest"] = {
            "type": nearest["type"],
            "name": nearest.get("name"),
            "distance_km": round(nearest["distance_m"] / 1000, 1)
        }

    if hiking:
        nearest = min(hiking, key=lambda x: x["distance_m"])
        summary["trail_access"]["nearest"] = {
            "type": nearest["type"],
            "name": nearest.get("name"),
            "distance_km": round(nearest["distance_m"] / 1000, 1)
        }

    if camping:
        nearest = min(camping, key=lambda x: x["distance_m"])
        summary["camping"]["nearest"] = {
            "type": nearest["type"],
            "name": nearest.get("name"),
            "distance_km": round(nearest["distance_m"] / 1000, 1)
        }

    return summary


def _estimated_breakdown() -> Dict:
    """Return estimated breakdown when API fails."""
    return {
        "score": 50,
        "breakdown": {
            "local_recreation": 20,
            "water_access": 15,
            "trail_access": 10,
            "camping": 5
        },
        "summary": {
            "local_recreation": {
                "total_parks": 0,
                "total_playgrounds": 0,
                "closest_park": None,
                "total_park_area_hectares": 0
            },
            "water_access": {"available": False, "nearest": None},
            "trail_access": {"available": False, "nearest": None},
            "camping": {"available": False, "nearest": None}
        }
    }