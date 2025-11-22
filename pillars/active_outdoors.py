"""
Active Outdoors Pillar
Scores access to outdoor activities and recreation
"""

import math
from typing import Dict, Tuple, Optional, List

from data_sources import osm_api
from data_sources.data_quality import assess_pillar_data_quality
from data_sources.gee_api import get_tree_canopy_gee
from data_sources.regional_baselines import (
    get_area_classification,
    get_contextual_expectations,
)
from data_sources.radius_profiles import get_radius_profile


def get_active_outdoors_score(
    lat: float,
    lon: float,
    city: Optional[str] = None,
    area_type: Optional[str] = None,
    location_scope: Optional[str] = None,
    include_diagnostics: bool = False,
) -> Tuple[float, Dict]:
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
    trail_radius = int(profile.get('trail_radius_m', 2000))  # Separate trail radius
    regional_radius = int(profile.get('regional_radius_m', 15000))
    print(f"   🔧 Radius profile (active_outdoors): area_type={area_type}, scope={location_scope}, local={local_radius}m, trail={trail_radius}m, regional={regional_radius}m")
    
    print(f"   📍 Querying local parks & playgrounds ({local_radius/1000:.0f}km)...")
    local_data = osm_api.query_green_spaces(lat, lon, radius_m=local_radius)
    
    print(f"   🥾 Querying trail access ({trail_radius/1000:.0f}km)...")
    # Query trails separately with trail_radius
    trail_data = osm_api.query_nature_features(lat, lon, radius_m=trail_radius)
    trail_hiking = trail_data.get('hiking', []) if trail_data else []
    
    print(f"   🏔️  Querying regional outdoor activities ({regional_radius/1000:.0f}km)...")
    # Query water and camping with regional_radius
    regional_data = osm_api.query_nature_features(lat, lon, radius_m=regional_radius)
    regional_swimming = regional_data.get('swimming', []) if regional_data else []
    regional_camping = regional_data.get('camping', []) if regional_data else []
    # Coastline fallback if regional query returns empty
    if not regional_swimming and not regional_camping:
        try:
            qc = f"""
            [out:json][timeout:15];
            way["natural"="coastline"](around:2000,{lat},{lon});
            out center 1;
            """
            from data_sources.osm_api import get_overpass_url, requests
            rc = requests.post(get_overpass_url(), data={"data": qc}, timeout=20, headers={"User-Agent":"HomeFit/1.0"})
            if rc.status_code == 200 and rc.json().get("elements"):
                regional_swimming.append({"type":"coastline","name":None,"distance_m":0})
        except Exception:
            pass

    # Local path cluster bonus (small, capped) - add to hiking
    try:
        from data_sources.osm_api import query_local_paths_within_green_areas
        local_clusters = query_local_paths_within_green_areas(lat, lon, radius_m=local_radius)
        # Add synthetic local hiking entries to avoid scoring zero when trails exist informally
        for _ in range(min(5, int(local_clusters))):
            trail_hiking.append({"type":"local_path_cluster","name":None,"distance_m":0})
    except Exception:
        pass

    # Combine hiking from trail query with any local path clusters
    hiking = trail_hiking

    # Combine data for quality assessment
    combined_data = {
        'parks': local_data.get("parks", []) if local_data else [],
        'playgrounds': local_data.get("playgrounds", []) if local_data else [],
        'hiking': hiking,  # From trail_radius query
        'swimming': regional_swimming,  # From regional_radius query
        'camping': regional_camping  # From regional_radius query
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
    trail_score = _score_trail_access_smooth(hiking, expectations, area_type)  # 0-30 - pass area_type
    water_score = _score_water_access_smooth(swimming, expectations)  # 0-20
    camping_score = _score_camping_smooth(camping, expectations, area_type)  # 0-10 - pass area_type

    # ------------------------------------------------------------------
    # Aggregate components in a data-centric, normalized way.
    # - Keep component curves and expectations fully data-backed.
    # - Normalize each component to its max and blend with global weights.
    # - No post-hoc bonuses or penalties; total is a pure function of
    #   component scores to respect design principles.
    # ------------------------------------------------------------------
    # Global weights (sum to 1.0) for normalized components, learned from
    # the calibration panel with hybrid towns constrained as anchors.
    W_LOCAL = 0.15   # local parks / playgrounds
    W_TRAIL = 0.15   # trail access
    W_WATER = 0.20   # water access
    W_CAMP = 0.50    # camping access

    # Normalize each component to 0–1 based on its design max
    local_norm = (local_score / 40.0) if local_score > 0 else 0.0
    trail_norm = (trail_score / 30.0) if trail_score > 0 else 0.0
    water_norm = (water_score / 20.0) if water_score > 0 else 0.0
    camping_norm = (camping_score / 10.0) if camping_score > 0 else 0.0

    # Base total: weighted blend of normalized components → 0–100
    total_score = (
        W_LOCAL * local_norm +
        W_TRAIL * trail_norm +
        W_WATER * water_norm +
        W_CAMP * camping_norm
    ) * 100.0

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

    # Log results (include aggregation version tag for debugging/deploy verification)
    print(f"✅ Active Outdoors Score (AO_AGG_V1): {total_score:.0f}/100")
    print(f"   🏞️  Local Parks & Playgrounds: {local_score:.0f}/40")
    print(f"   🥾 Trail Access: {trail_score:.0f}/30")
    print(f"   🏊 Water Access: {water_score:.0f}/20")
    print(f"   🏕️  Camping: {camping_score:.0f}/10")
    print(f"   📊 Data Quality: {quality_metrics['quality_tier']} ({quality_metrics['confidence']}% confidence)")

    return round(total_score, 1), breakdown


# ============================================================================
# Active Outdoors v2 – data-centric outdoor lifestyle model
# ============================================================================

def get_active_outdoors_score_v2(
    lat: float,
    lon: float,
    city: Optional[str] = None,
    area_type: Optional[str] = None,
    location_scope: Optional[str] = None,
    include_diagnostics: bool = False,
) -> Tuple[float, Dict]:
    """
    Compute Active Outdoors v2 (0–100).

    This does NOT reuse the v1 0–40/30/20/10 weights. It is a new model built on:
      - Daily Urban Outdoors (0–30)
      - Wild Adventure Backbone (0–50)
      - Waterfront Lifestyle (0–20)

    All underlying features are objective (OSM features, tree canopy from GEE, etc.).
    No per-city hacks; area_type is only used to set expectations.
    """

    print("🏃 [AO v2] Analyzing active outdoors access...")

    # 1) Area classification and radius profile
    detected_area_type, metro_name, area_metadata = get_area_classification(
        lat, lon, city=city
    )
    area_type = area_type or detected_area_type

    profile = get_radius_profile("active_outdoors", area_type, location_scope)
    local_radius = int(profile.get("local_radius_m", 2000))  # daily use (~2 km)
    trail_radius = int(profile.get("trail_radius_m", 15000))  # trails within ~15 km
    regional_radius = int(
        profile.get("regional_radius_m", 50000)
    )  # water/camping within ~50 km

    print(
        f"   🔧 [AO v2] Radii – local={local_radius/1000:.1f}km, "
        f"trail={trail_radius/1000:.1f}km, regional={regional_radius/1000:.1f}km"
    )

    # 2) Data collection (reuse existing data_sources)
    # Local parks & playgrounds
    print(
        f"   📍 [AO v2] Querying local parks & playgrounds ({local_radius/1000:.1f}km)..."
    )
    local = osm_api.query_green_spaces(lat, lon, radius_m=local_radius) or {}
    parks: List[Dict] = local.get("parks", []) or []
    playgrounds: List[Dict] = local.get("playgrounds", []) or []

    # Nature features – trails, water, camping
    print(
        f"   🥾 [AO v2] Querying nature features ({trail_radius/1000:.1f}–{regional_radius/1000:.1f}km)..."
    )
    nature_trail = osm_api.query_nature_features(lat, lon, radius_m=trail_radius) or {}
    nature_regional = (
        osm_api.query_nature_features(lat, lon, radius_m=regional_radius) or {}
    )

    hiking_trails: List[Dict] = (nature_trail.get("hiking", []) or []) + (
        nature_regional.get("hiking", []) or []
    )
    swimming: List[Dict] = nature_regional.get("swimming", []) or []
    camping: List[Dict] = nature_regional.get("camping", []) or []

    # Tree canopy around 5 km as a proxy for “wildness”
    try:
        canopy_pct_5km = get_tree_canopy_gee(
            lat, lon, radius_m=5000, area_type=area_type
        ) or 0.0
    except Exception:
        canopy_pct_5km = 0.0

    combined_data = {
        "parks": parks,
        "playgrounds": playgrounds,
        "hiking": hiking_trails,
        "swimming": swimming,
        "camping": camping,
        "tree_canopy_pct_5km": canopy_pct_5km,
    }
    dq = assess_pillar_data_quality(
        "active_outdoors_v2", combined_data, lat, lon, area_type
    )

    # 3) Component scores
    daily_score = _score_daily_urban_outdoors_v2(parks, playgrounds, area_type)
    wild_score = _score_wild_adventure_v2(
        hiking_trails, camping, canopy_pct_5km, area_type
    )
    water_score = _score_water_lifestyle_v2(swimming, area_type)

    # 4) Aggregation (simple, explainable; can be re-fit)
    W_DAILY = 0.30
    W_WILD = 0.50
    W_WATER = 0.20

    total = W_DAILY * daily_score + W_WILD * wild_score + W_WATER * water_score

    breakdown: Dict = {
        "score": round(total, 1),
        "breakdown": {
            "daily_urban_outdoors": round(daily_score, 1),
            "wild_adventure": round(wild_score, 1),
            "waterfront_lifestyle": round(water_score, 1),
        },
        "summary": _build_summary_v2(
            parks, playgrounds, hiking_trails, swimming, camping, canopy_pct_5km
        ),
        "data_quality": dq,
        "area_classification": area_metadata,
        "version": "active_outdoors_v2",
    }

    if include_diagnostics:
        breakdown["diagnostics"] = {
            "parks_2km": len(parks),
            "playgrounds_2km": len(playgrounds),
            "hiking_trails_total": len(hiking_trails),
            "hiking_trails_within_5km": sum(
                1 for h in hiking_trails if h.get("distance_m", 1e9) <= 5000
            ),
            "swimming_features": len(swimming),
            "camp_sites": len(camping),
            "tree_canopy_pct_5km": canopy_pct_5km,
        }

    print(
        f"✅ Active Outdoors v2: {total:.1f}/100 "
        f"(daily={daily_score:.1f}, wild={wild_score:.1f}, water={water_score:.1f})"
    )
    return round(total, 1), breakdown


def _sat_ratio_v2(x: float, target: float, max_score: float) -> float:
    """Smooth saturation: 0 at 0, asymptotically approaches max_score as x grows."""
    if target <= 0:
        return 0.0
    r = x / target
    return max_score * (1.0 - math.exp(-r))


def _score_daily_urban_outdoors_v2(
    parks: list, playgrounds: list, area_type: str
) -> float:
    """
    Daily Urban Outdoors (0–30):
      – Park/green area near home
      – Park and playground count
    Uses area-type–specific expectations from your expected-values research.
    """
    total_area_ha = sum(p.get("area_sqm", 0.0) for p in parks) / 10_000.0
    park_count = len(parks)
    playground_count = len(playgrounds)

    if area_type in {"urban_core", "historic_urban"}:
        exp_park_ha, exp_park_count, exp_play = 5.0, 8.0, 4.0
    elif area_type in {"suburban", "urban_residential", "urban_core_lowrise"}:
        exp_park_ha, exp_park_count, exp_play = 8.0, 6.0, 3.0
    else:  # rural / exurban
        exp_park_ha, exp_park_count, exp_play = 3.0, 2.0, 1.0

    s_area = _sat_ratio_v2(total_area_ha, exp_park_ha, 15.0)
    s_count = _sat_ratio_v2(park_count, exp_park_count, 10.0)
    s_play = _sat_ratio_v2(playground_count, exp_play, 5.0)

    return min(30.0, s_area + s_count + s_play)


def _score_wild_adventure_v2(
    hiking_trails: list,
    camping: list,
    canopy_pct_5km: float,
    area_type: str,
) -> float:
    """
    Wild Adventure Backbone (0–50):
      – Trail richness (count + proximity)
      – Wild/forested context (tree canopy)
      – Camping access
    """

    trail_count = len(hiking_trails)
    near_trails = [t for t in hiking_trails if t.get("distance_m", 1e9) <= 5000]
    near_count = len(near_trails)

    if area_type in {"urban_core", "historic_urban"}:
        exp_trails, exp_near, exp_canopy = 5.0, 2.0, 20.0
    elif area_type in {"suburban", "urban_residential", "urban_core_lowrise"}:
        exp_trails, exp_near, exp_canopy = 15.0, 5.0, 30.0
    else:  # rural / exurban
        exp_trails, exp_near, exp_canopy = 30.0, 10.0, 40.0

    s_trails_total = _sat_ratio_v2(trail_count, exp_trails, 20.0)
    s_trails_near = _sat_ratio_v2(near_count, exp_near, 10.0)
    s_canopy = _sat_ratio_v2(canopy_pct_5km, exp_canopy, 10.0)

    # Camping proximity: full credit if any site within 10km, then decays
    if not camping:
        s_camp = 0.0
    else:
        nearest = min(camping, key=lambda c: c.get("distance_m", 1e9))
        d = nearest.get("distance_m", 1e9)
        if d <= 10_000:
            s_camp = 10.0
        else:
            s_camp = 10.0 * math.exp(-0.00008 * (d - 10_000))

    return max(0.0, min(50.0, s_trails_total + s_trails_near + s_canopy + s_camp))


def _score_water_lifestyle_v2(swimming: list, area_type: str) -> float:
    """
    Waterfront Lifestyle (0–20):
      – Swimmable water type
      – Distance to shoreline / lake / river
    """
    if not swimming:
        return 0.0

    nearest = min(swimming, key=lambda s: s.get("distance_m", 1e9))
    d = nearest.get("distance_m", 1e9)
    t = nearest.get("type")

    base = {
        "beach": 20.0,
        "swimming_area": 18.0,
        "lake": 18.0,
        "bay": 16.0,
        "coastline": 16.0,
    }.get(t, 12.0)

    # Slight downweight for non-beach water in dense cores (ornamental water)
    if area_type in {"urban_core", "historic_urban"} and t != "beach":
        base *= 0.8

    optimal = 2_000.0
    if d <= optimal:
        return base
    return max(0.0, base * math.exp(-0.0003 * (d - optimal)))


def _build_summary_v2(
    parks: list,
    playgrounds: list,
    hiking: list,
    swimming: list,
    camping: list,
    canopy_pct: float,
) -> Dict:
    def nearest_km(features: list) -> Optional[float]:
        if not features:
            return None
        d = min(f.get("distance_m", 1e9) for f in features)
        if d >= 1e9:
            return None
        return round(d / 1000.0, 2)

    return {
        "local_parks": {
            "count": len(parks),
            "playgrounds": len(playgrounds),
            "total_park_area_ha": round(
                sum(p.get("area_sqm", 0.0) / 10_000.0 for p in parks), 2
            ),
        },
        "trails": {
            "count_total": len(hiking),
            "count_within_5km": sum(
                1 for h in hiking if h.get("distance_m", 1e9) <= 5000
            ),
        },
        "water": {
            "features": len(swimming),
            "nearest_km": nearest_km(swimming),
        },
        "camping": {
            "sites": len(camping),
            "nearest_km": nearest_km(camping),
        },
        "environment": {
            "tree_canopy_pct_5km": round(canopy_pct, 1),
        },
    }


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


def _score_trail_access_smooth(hiking: list, expectations: Dict, area_type: str) -> float:
    """Score trail access (0-30 points) using smooth decay curves with contextual optimal distances."""
    if not hiking:
        return 0.0

    closest = min(f["distance_m"] for f in hiking)
    
    # Research-based contextual optimal distances
    if area_type == "urban_core":
        optimal_distance = 800  # 10-minute walk (research: <0.5 mile)
        decay_rate = 0.0005  # Faster decay for urban (walkable threshold)
    elif area_type == "suburban":
        optimal_distance = 2000  # Bikeable distance (research: 1-2 miles)
        decay_rate = 0.0003
    else:  # exurban, rural
        optimal_distance = 5000  # Drivable distance
        decay_rate = 0.0001
    
    max_score = 30.0
    
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


def _score_camping_smooth(camping: list, expectations: Dict, area_type: str) -> float:
    """Score camping access (0-10 points) using smooth decay curves with contextual adjustments."""
    expected_camping = expectations.get('expected_camping_within_15km', 1)
    
    if not camping:
        # If camping not expected in this area type, return neutral score
        if expected_camping == 0:
            return 5.0  # Neutral when not expected (not a penalty)
        return 0.0

    closest = min(f["distance_m"] for f in camping)
    
    # Contextual optimal distances based on area type
    if area_type == "urban_core":
        optimal_distance = 10000  # 10km if available
        max_score = 8.0  # Cap lower for urban (not primary feature)
        decay_rate = 0.0002
    elif area_type == "suburban":
        optimal_distance = 15000  # 15km
        max_score = 10.0
        decay_rate = 0.0001
    else:  # exurban, rural
        optimal_distance = 25000  # 25km (research: 10-50 miles)
        max_score = 10.0
        decay_rate = 0.00005
    
    if closest <= optimal_distance:
        score = max_score
    else:
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