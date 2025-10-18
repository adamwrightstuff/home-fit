"""
Nature Access Pillar
Scores outdoor recreation: hiking, swimming, camping
"""

from typing import Dict, Tuple
from data_sources import osm_api


def get_nature_access_score(lat: float, lon: float) -> Tuple[float, Dict]:
    """
    Calculate nature access score (0-100) based on outdoor recreation.

    Scoring:
    - Hiking: 0-40 points
    - Swimming: 0-40 points
    - Camping: 0-20 points

    Returns:
        (total_score, detailed_breakdown)
    """
    print(f"🏔️  Analyzing nature access within 15km...")

    # Get nature features from OSM
    nature_data = osm_api.query_nature_features(lat, lon, radius_m=15000)

    if nature_data is None:
        print("⚠️  OSM data unavailable")
        return 0, _empty_breakdown()

    hiking = nature_data["hiking"]
    swimming = nature_data["swimming"]
    camping = nature_data["camping"]

    # Score components
    hiking_score = _score_hiking(hiking)
    swimming_score = _score_swimming(swimming)
    camping_score = _score_camping(camping)

    total_score = hiking_score + swimming_score + camping_score

    # Build response
    breakdown = {
        "score": round(total_score, 1),
        "breakdown": {
            "hiking": round(hiking_score, 1),
            "swimming": round(swimming_score, 1),
            "camping": round(camping_score, 1)
        },
        "summary": _build_summary(hiking, swimming, camping)
    }

    # Log results
    print(f"✅ Nature Access Score: {total_score:.0f}/100")
    print(f"   🥾 Hiking: {hiking_score:.0f}/40 {'✓' if hiking else '✗'}")
    print(f"   🏊 Swimming: {swimming_score:.0f}/40 {'✓' if swimming else '✗'}")
    print(f"   🏕️  Camping: {camping_score:.0f}/20 {'✓' if camping else '✗'}")

    return round(total_score, 1), breakdown


def _score_hiking(features: list) -> float:
    """Score hiking access (0-40 points) based on distance."""
    if not features:
        return 0.0

    closest = min(f["distance_m"] for f in features)

    if closest <= 2000:
        return 40.0
    elif closest <= 5000:
        return 35.0
    elif closest <= 10000:
        return 28.0
    elif closest <= 15000:
        return 22.0
    else:
        return 12.0


def _score_swimming(features: list) -> float:
    """Score swimming access (0-40 points) based on closest feature type and distance."""
    if not features:
        return 0.0

    # Find closest water feature
    closest = min(features, key=lambda x: x["distance_m"])
    dist = closest["distance_m"]
    feature_type = closest["type"]

    # Score based on type and distance
    if feature_type == "beach":
        if dist <= 5000:
            return 40.0
        elif dist <= 10000:
            return 38.0
        elif dist <= 15000:
            return 36.0

    elif feature_type in ["lake", "swimming_area"]:
        if dist <= 5000:
            return 38.0
        elif dist <= 10000:
            return 35.0
        elif dist <= 15000:
            return 32.0

    elif feature_type in ["coastline", "bay"]:
        if dist <= 2000:
            return 18.0
        elif dist <= 5000:
            return 22.0
        elif dist <= 10000:
            return 25.0
        elif dist <= 15000:
            return 28.0

    return 0.0


def _score_camping(features: list) -> float:
    """Score camping access (0-20 points) based on distance."""
    if not features:
        return 0.0

    closest = min(f["distance_m"] for f in features)

    if closest <= 5000:
        return 20.0
    elif closest <= 10000:
        return 15.0
    elif closest <= 15000:
        return 10.0
    else:
        return 5.0


def _build_summary(hiking: list, swimming: list, camping: list) -> Dict:
    """Build summary of available activities."""
    summary = {
        "hiking_available": len(hiking) > 0,
        "swimming_available": len(swimming) > 0,
        "camping_available": len(camping) > 0,
        "nearest_hiking": None,
        "nearest_swimming": None,
        "nearest_camping": None
    }

    if hiking:
        nearest = min(hiking, key=lambda x: x["distance_m"])
        summary["nearest_hiking"] = {
            "type": nearest["type"],
            "name": nearest.get("name"),
            "distance_km": round(nearest["distance_m"] / 1000, 1)
        }

    if swimming:
        nearest = min(swimming, key=lambda x: x["distance_m"])
        summary["nearest_swimming"] = {
            "type": nearest["type"],
            "name": nearest.get("name"),
            "distance_km": round(nearest["distance_m"] / 1000, 1)
        }

    if camping:
        nearest = min(camping, key=lambda x: x["distance_m"])
        summary["nearest_camping"] = {
            "type": nearest["type"],
            "name": nearest.get("name"),
            "distance_km": round(nearest["distance_m"] / 1000, 1)
        }

    return summary


def _empty_breakdown() -> Dict:
    """Return empty breakdown when no data."""
    return {
        "score": 0,
        "breakdown": {
            "hiking": 0,
            "swimming": 0,
            "camping": 0
        },
        "summary": {
            "hiking_available": False,
            "swimming_available": False,
            "camping_available": False,
            "nearest_hiking": None,
            "nearest_swimming": None,
            "nearest_camping": None
        }
    }
