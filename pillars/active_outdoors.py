"""
Active Outdoors Pillar
Scores access to outdoor activities and recreation
"""

import math
from typing import Dict, Tuple, Optional
from data_sources import osm_api
from data_sources.data_quality import assess_pillar_data_quality
from data_sources.regional_baselines import get_area_classification, get_contextual_expectations
from data_sources.radius_profiles import get_radius_profile


def get_active_outdoors_score(lat: float, lon: float, city: Optional[str] = None,
                              area_type: Optional[str] = None,
                              location_scope: Optional[str] = None,
                              include_diagnostics: bool = False) -> Tuple[float, Dict]:
    """
    Calculate active outdoors score (0-100) based on access to outdoor activities.

    Scoring:
    - Local Parks & Playgrounds: 0-40 points (within 1km - daily use)
    - Trail Access: 0-30 points (hiking, nature reserves within 15km)
    - Water Access: 0-20 points (beaches, lakes within 15km)
    - Camping Access: 0-10 points (campsites within 15km)

    Returns:
        (total_score, detailed_breakdown)
    """
    print(f"🏃 Analyzing active outdoors access...")

    # Get area classification for contextual scoring (allow override for consistency across pillars)
    detected_area_type, metro_name, area_metadata = get_area_classification(lat, lon, city=city)
    area_type = area_type or detected_area_type
    expectations = get_contextual_expectations(area_type, 'active_outdoors')
    
    # Use centralized radius profiles for unified defaults
    profile = get_radius_profile('active_outdoors', area_type, location_scope)
    local_radius = int(profile.get('local_radius_m', 1000))
    regional_radius = int(profile.get('regional_radius_m', 15000))
    print(f"   🔧 Radius profile (active_outdoors): area_type={area_type}, scope={location_scope}, local={local_radius}m, regional={regional_radius}m")
    
    print(f"   📍 Querying local parks & playgrounds ({local_radius/1000:.0f}km)...")
    local_data = osm_api.query_green_spaces(lat, lon, radius_m=local_radius)
    
    print(f"   🏔️  Querying regional outdoor activities ({regional_radius/1000:.0f}km)...")
    regional_data = osm_api.query_nature_features(lat, lon, radius_m=regional_radius)
    # Coastline fallback if nature query returns empty
    if not regional_data or (not regional_data.get('hiking') and not regional_data.get('swimming') and not regional_data.get('camping')):
        try:
            qc = f"""
            [out:json][timeout:15];
            way["natural"="coastline"](around:2000,{lat},{lon});
            out center 1;
            """
            from data_sources.osm_api import OVERPASS_URL, requests
            rc = requests.post(OVERPASS_URL, data={"data": qc}, timeout=20, headers={"User-Agent":"HomeFit/1.0"})
            if rc.status_code == 200 and rc.json().get("elements"):
                regional_data = regional_data or {"hiking": [], "swimming": [], "camping": []}
                regional_data["swimming"].append({"type":"coastline","name":None,"distance_m":0})
        except Exception:
            pass

    # Local path cluster bonus (small, capped)
    try:
        from data_sources.osm_api import query_local_paths_within_green_areas
        local_clusters = query_local_paths_within_green_areas(lat, lon, radius_m=local_radius)
        if regional_data is None:
            regional_data = {"hiking": [], "swimming": [], "camping": []}
        # Add synthetic local hiking entries to avoid scoring zero when trails exist informally
        for _ in range(min(5, int(local_clusters))):
            regional_data["hiking"].append({"type":"local_path_cluster","name":None,"distance_m":0})
    except Exception:
        pass

    # Combine data for quality assessment
    combined_data = {
        'parks': local_data.get("parks", []) if local_data else [],
        'playgrounds': local_data.get("playgrounds", []) if local_data else [],
        'hiking': regional_data.get("hiking", []) if regional_data else [],
        'swimming': regional_data.get("swimming", []) if regional_data else [],
        'camping': regional_data.get("camping", []) if regional_data else []
    }

    # Assess data quality
    quality_metrics = assess_pillar_data_quality('active_outdoors', combined_data, lat, lon, area_type)
    
    # Extract data
    parks = combined_data['parks']
    playgrounds = combined_data['playgrounds']
    hiking = combined_data['hiking']
    swimming = combined_data['swimming']
    camping = combined_data['camping']

    # Score components with smooth curves and contextual adjustments
    local_score = _score_local_recreation_smooth(parks, playgrounds, expectations)  # 0-40
    trail_score = _score_trail_access_smooth(hiking, expectations)  # 0-30
    water_score = _score_water_access_smooth(swimming, expectations)  # 0-20
    camping_score = _score_camping_smooth(camping, expectations)  # 0-10

    total_score = local_score + water_score + trail_score + camping_score

    # Build response with quality metrics
    breakdown = {
        "score": round(total_score, 1),
        "breakdown": {
            "local_parks_playgrounds": round(local_score, 1),
            "water_access": round(water_score, 1),
            "trail_access": round(trail_score, 1),
            "camping_access": round(camping_score, 1)
        },
        "summary": _build_summary(parks, playgrounds, swimming, hiking, camping),
        "data_quality": quality_metrics,
        "area_classification": area_metadata
    }

    if include_diagnostics:
        try:
            kept_parks = parks or []
            breakdown["diagnostics"] = {
                "parks_kept": [
                    {"name": p.get("name"), "osm_id": p.get("osm_id"), "distance_m": p.get("distance_m"), "area_sqm": p.get("area_sqm")}
                    for p in kept_parks
                ][:50]
            }
        except Exception:
            pass

    # Log results
    print(f"✅ Active Outdoors Score: {total_score:.0f}/100")
    print(f"   🏞️  Local Parks & Playgrounds: {local_score:.0f}/40")
    print(f"   🥾 Trail Access: {trail_score:.0f}/30")
    print(f"   🏊 Water Access: {water_score:.0f}/20")
    print(f"   🏕️  Camping: {camping_score:.0f}/10")
    print(f"   📊 Data Quality: {quality_metrics['quality_tier']} ({quality_metrics['confidence']}% confidence)")

    return round(total_score, 1), breakdown


def _score_local_recreation_smooth(parks: list, playgrounds: list, expectations: Dict) -> float:
    """Score local parks and playgrounds (0-40 points) using smooth curves."""
    park_score = _score_parks_smooth(parks, expectations)  # 0-25
    playground_score = _score_playgrounds_smooth(playgrounds, expectations)  # 0-15
    return min(40, park_score + playground_score)


def _score_local_recreation(parks: list, playgrounds: list) -> float:
    """Score local parks and playgrounds (0-40 points)."""
    park_score = _score_parks(parks)  # 0-25
    playground_score = _score_playgrounds(playgrounds)  # 0-15
    return min(40, park_score + playground_score)


def _score_parks_smooth(parks: list, expectations: Dict) -> float:
    """Score parks (0-25 points) using smooth curves based on count and area."""
    if not parks:
        return 0.0

    count = len(parks)
    total_area_sqm = sum(p["area_sqm"] for p in parks)
    total_hectares = total_area_sqm / 10000

    # Smooth count scoring (0-12 points)
    expected_count = expectations.get('expected_parks_within_1km', 3)
    count_score = min(12, (count / max(expected_count, 1)) * 12)
    
    # Smooth area scoring (0-13 points)
    expected_area = expectations.get('expected_park_area_hectares', 5)
    area_ratio = total_hectares / max(expected_area, 1)
    area_score = min(13, area_ratio * 13)

    return min(25, count_score + area_score)


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


def _score_playgrounds_smooth(playgrounds: list, expectations: Dict) -> float:
    """Score playgrounds (0-15 points) using smooth curves."""
    count = len(playgrounds)
    expected_count = expectations.get('expected_playgrounds_within_1km', 2)
    
    # Smooth scoring based on expected count
    ratio = count / max(expected_count, 1)
    score = min(15, ratio * 15)
    
    return score


def _score_playgrounds(playgrounds: list) -> float:
    """Score playgrounds (0-15 points) based on count."""
    count = len(playgrounds)
    return min(15, count * 5)


def _score_water_access_smooth(swimming: list, expectations: Dict) -> float:
    """Score water access (0-20 points) using smooth decay curves."""
    if not swimming:
        return 0.0

    # Find closest water feature
    closest = min(swimming, key=lambda x: x["distance_m"])
    dist = closest["distance_m"]
    feature_type = closest["type"]

    # Base scores by feature type
    base_scores = {
        "beach": 20.0,
        "lake": 18.0,
        "swimming_area": 18.0,
        "coastline": 16.0,
        "bay": 16.0
    }
    
    max_score = base_scores.get(feature_type, 15.0)
    
    # Smooth distance decay
    optimal_distance = 2000  # meters
    decay_rate = 0.0003
    
    if dist <= optimal_distance:
        score = max_score
    else:
        # Exponential decay beyond optimal distance
        score = max_score * math.exp(-decay_rate * (dist - optimal_distance))
    
    return min(max_score, max(0, score))


def _score_water_access(swimming: list) -> float:
    """Score water access (0-20 points) based on beaches, lakes, etc."""
    if not swimming:
        return 0.0

    # Find closest water feature
    closest = min(swimming, key=lambda x: x["distance_m"])
    dist = closest["distance_m"]
    feature_type = closest["type"]

    # Score based on type and distance (MAX 20 points)
    if feature_type == "beach":
        if dist <= 2000:
            return 20.0
        elif dist <= 5000:
            return 18.0
        elif dist <= 10000:
            return 16.0
        elif dist <= 15000:
            return 14.0

    elif feature_type in ["lake", "swimming_area"]:
        if dist <= 2000:
            return 18.0
        elif dist <= 5000:
            return 16.0
        elif dist <= 10000:
            return 14.0
        elif dist <= 15000:
            return 12.0

    elif feature_type in ["coastline", "bay"]:
        if dist <= 2000:
            return 10.0
        elif dist <= 5000:
            return 12.0
        elif dist <= 10000:
            return 14.0
        elif dist <= 15000:
            return 16.0

    return 0.0


def _score_trail_access_smooth(hiking: list, expectations: Dict) -> float:
    """Score trail access (0-30 points) using smooth decay curves."""
    if not hiking:
        return 0.0

    closest = min(f["distance_m"] for f in hiking)
    
    # Smooth distance decay
    max_score = 30.0
    optimal_distance = 2000  # meters
    decay_rate = 0.0002
    
    if closest <= optimal_distance:
        score = max_score
    else:
        # Exponential decay beyond optimal distance
        score = max_score * math.exp(-decay_rate * (closest - optimal_distance))
    
    return min(max_score, max(0, score))


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


def _score_camping_smooth(camping: list, expectations: Dict) -> float:
    """Score camping access (0-10 points) using smooth decay curves."""
    if not camping:
        return 0.0

    closest = min(f["distance_m"] for f in camping)
    
    # Smooth distance decay
    max_score = 10.0
    optimal_distance = 5000  # meters
    decay_rate = 0.0001
    
    if closest <= optimal_distance:
        score = max_score
    else:
        # Exponential decay beyond optimal distance
        score = max_score * math.exp(-decay_rate * (closest - optimal_distance))
    
    return min(max_score, max(0, score))


def _score_camping(camping: list) -> float:
    """Score camping access (0-20 points) based on distance."""
    if not camping:
        return 0.0

    closest = min(f["distance_m"] for f in camping)

    if closest <= 5000:
        return 20.0
    elif closest <= 10000:
        return 16.0
    elif closest <= 15000:
        return 12.0
    else:
        return 6.0


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
            "local_parks_playgrounds": 20,
            "water_access": 10,
            "trail_access": 10,
            "camping_access": 10
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