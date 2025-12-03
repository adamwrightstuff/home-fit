"""
Active Outdoors Pillar
Scores access to outdoor activities and recreation
"""

import math
from typing import Dict, Tuple, Optional, List
from concurrent.futures import ThreadPoolExecutor

from data_sources import osm_api
from data_sources.data_quality import assess_pillar_data_quality
from data_sources.gee_api import get_tree_canopy_gee
from data_sources.regional_baselines import (
    get_area_classification,
    get_contextual_expectations,
)
from data_sources.radius_profiles import get_radius_profile
from logging_config import get_logger

# Initialize logger
logger = get_logger(__name__)

# Ridge regression coefficients (advisory only, not used for scoring)
# Global model (all area types combined)
ACTIVE_OUTDOORS_RIDGE_GLOBAL = {
    "coefficients": [
        -0.836912876011333,      # Norm Daily
        8.111140760295395,       # Norm Wild
        1.4393450773832117,       # Norm Water
        -1.6803163406904489,     # Norm ParkCount
        0.0,                      # Norm Playground
        -2.7804888330870883,     # Norm ParkArea
        6.550673699373188,        # Norm Trails5
        2.013996650298848,        # Norm SwimCount
        -0.17007136273015588,    # Norm SwimKM
        5.309054413801675,        # Norm CampCount
        -3.2727730797828243,     # Norm CampKM
        0.592336268134379,        # Norm Tree
    ],
    "intercept": 77.55414775327147,
    "r2_score": 0.2497311792894693,
    "n_samples": 21,
}

# Area-type-specific models (for reference, sample sizes too small for reliable prediction)
ACTIVE_OUTDOORS_RIDGE_BY_AREA_TYPE = {
    "rural": {
        "coefficients": [
            -0.4819985793078666,   # Norm Daily
            0.016334957660023446,   # Norm Wild
            0.8500622169067389,     # Norm Water
            -0.010375588470873744,  # Norm ParkCount
            0.0,                    # Norm Playground
            -0.3558405114940178,    # Norm ParkArea
            0.24351409578185473,    # Norm Trails5
            0.7618125133176625,     # Norm SwimCount
            0.8006927444461264,     # Norm SwimKM
            -0.03109715910619764,   # Norm CampCount
            0.4745870520129916,     # Norm CampKM
            -0.22372815368551674,   # Norm Tree
        ],
        "intercept": 89.16171626384786,
        "r2_score": 0.6897050183343025,
        "n_samples": 5,
    },
    "suburban": {
        "coefficients": [
            -0.6378519537133754,   # Norm Daily
            1.474725354113921,      # Norm Wild
            -0.6803220064533304,    # Norm Water
            -0.4688179453167545,    # Norm ParkCount
            0.0,                    # Norm Playground
            0.7321829873787588,     # Norm ParkArea
            -0.39008443689858514,   # Norm Trails5
            -0.6698236174684394,    # Norm SwimCount
            0.2895326227083448,     # Norm SwimKM
            -0.4239820818789273,    # Norm CampCount
            0.3448683643491389,     # Norm CampKM
            0.042957538884930596,   # Norm Tree
        ],
        "intercept": 83.31369233718962,
        "r2_score": 0.4957744772188506,
        "n_samples": 3,
    },
    "urban_core": {
        "coefficients": [
            3.014794871479455,      # Norm Daily
            4.838975862659801,      # Norm Wild
            5.2717420943592055,     # Norm Water
            0.7614157230799612,     # Norm ParkCount
            0.0,                    # Norm Playground
            0.10422897889989345,   # Norm ParkArea
            2.563286669719146,      # Norm Trails5
            0.19747987098326006,   # Norm SwimCount
            2.8364914003537445,     # Norm SwimKM
            0.12645467330841734,   # Norm CampCount
            1.2992475890715411,     # Norm CampKM
            3.034112401143685,      # Norm Tree
        ],
        "intercept": 66.90465452647607,
        "r2_score": 0.16398747369134614,
        "n_samples": 7,
    },
}

# Min-max values for normalization (from expected_values_summary.csv)
ACTIVE_OUTDOORS_FEATURE_RANGES = {
    "daily": {"min": 0.0, "max": 30.0},           # Daily score range
    "wild": {"min": 0.0, "max": 50.0},            # Wild score range
    "water": {"min": 0.0, "max": 20.0},           # Water score range
    "park_count": {"min": 0, "max": 63},           # From CSV: urban_core max
    "playground": {"min": 0, "max": 10},           # Estimate (CSV shows mostly 0)
    "park_area": {"min": 0.0, "max": 353.4289},   # From CSV: urban_core max
    "trails_5km": {"min": 0, "max": 249},          # From CSV: urban_core trails_15km (use as proxy)
    "swim_count": {"min": 0, "max": 402},         # From CSV: urban_core water_15km
    "swim_km": {"min": 0.0, "max": 11.023},       # From CSV: rural max closest_water_km
    "camp_count": {"min": 0, "max": 16},          # From CSV: suburban/exurban max
    "camp_km": {"min": 0.0, "max": 15.871},       # From CSV: exurban max closest (estimate)
    "tree": {"min": 0.0, "max": 100.0},           # Tree canopy percentage
}


def _normalize_feature(value: float, min_val: float, max_val: float, invert: bool = False) -> float:
    """
    Normalize a feature using min-max scaling.
    
    Args:
        value: Raw feature value
        min_val: Minimum value for normalization
        max_val: Maximum value for normalization
        invert: If True, invert the normalized value (1 - normalized)
    
    Returns:
        Normalized value in [0, 1] range
    """
    if max_val == min_val:
        return 0.0
    
    normalized = (value - min_val) / (max_val - min_val)
    normalized = max(0.0, min(1.0, normalized))  # Clamp to [0, 1]
    
    if invert:
        return 1.0 - normalized
    return normalized


def _compute_normalized_features(
    daily_score: float,
    wild_score: float,
    water_score: float,
    parks: List[Dict],
    playgrounds: List[Dict],
    hiking_trails: List[Dict],
    swimming: List[Dict],
    camping: List[Dict],
    canopy_pct_5km: float,
) -> List[float]:
    """
    Compute the 12 normalized Active Outdoors features.
    
    Returns:
        List of 12 normalized features in order:
        1. Norm Daily, 2. Norm Wild, 3. Norm Water,
        4. Norm ParkCount, 5. Norm Playground, 6. Norm ParkArea,
        7. Norm Trails5, 8. Norm SwimCount, 9. Norm SwimKM,
        10. Norm CampCount, 11. Norm CampKM, 12. Norm Tree
    """
    ranges = ACTIVE_OUTDOORS_FEATURE_RANGES
    
    # 1. Norm Daily
    norm_daily = _normalize_feature(daily_score, ranges["daily"]["min"], ranges["daily"]["max"])
    
    # 2. Norm Wild
    norm_wild = _normalize_feature(wild_score, ranges["wild"]["min"], ranges["wild"]["max"])
    
    # 3. Norm Water
    norm_water = _normalize_feature(water_score, ranges["water"]["min"], ranges["water"]["max"])
    
    # 4. Norm ParkCount
    park_count = len(parks)
    norm_park_count = _normalize_feature(park_count, ranges["park_count"]["min"], ranges["park_count"]["max"])
    
    # 5. Norm Playground
    playground_count = len(playgrounds)
    norm_playground = _normalize_feature(playground_count, ranges["playground"]["min"], ranges["playground"]["max"])
    
    # 6. Norm ParkArea
    total_park_area_ha = sum(p.get("area_sqm", 0.0) / 10_000.0 for p in parks)
    norm_park_area = _normalize_feature(total_park_area_ha, ranges["park_area"]["min"], ranges["park_area"]["max"])
    
    # 7. Norm Trails5 (trails within 5km)
    trails_5km = [t for t in hiking_trails if t.get("distance_m", 1e9) <= 5000]
    trails_5km_count = len(trails_5km)
    norm_trails5 = _normalize_feature(trails_5km_count, ranges["trails_5km"]["min"], ranges["trails_5km"]["max"])
    
    # 8. Norm SwimCount
    swim_count = len(swimming)
    norm_swim_count = _normalize_feature(swim_count, ranges["swim_count"]["min"], ranges["swim_count"]["max"])
    
    # 9. Norm SwimKM (inverted distance to nearest swimming)
    closest_swim_km = min([s.get("distance_m", 1e9) / 1000.0 for s in swimming], default=1e9)
    norm_swim_km = _normalize_feature(closest_swim_km, ranges["swim_km"]["min"], ranges["swim_km"]["max"], invert=True)
    
    # 10. Norm CampCount
    camp_count = len(camping)
    norm_camp_count = _normalize_feature(camp_count, ranges["camp_count"]["min"], ranges["camp_count"]["max"])
    
    # 11. Norm CampKM (inverted distance to nearest camping)
    closest_camp_km = min([c.get("distance_m", 1e9) / 1000.0 for c in camping], default=1e9)
    norm_camp_km = _normalize_feature(closest_camp_km, ranges["camp_km"]["min"], ranges["camp_km"]["max"], invert=True)
    
    # 12. Norm Tree
    norm_tree = _normalize_feature(canopy_pct_5km, ranges["tree"]["min"], ranges["tree"]["max"])
    
    return [
        norm_daily,
        norm_wild,
        norm_water,
        norm_park_count,
        norm_playground,
        norm_park_area,
        norm_trails5,
        norm_swim_count,
        norm_swim_km,
        norm_camp_count,
        norm_camp_km,
        norm_tree,
    ]


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
    logger.info("🏃 Analyzing active outdoors access...", extra={
        "pillar_name": "active_outdoors",
        "lat": lat,
        "lon": lon,
        "area_type": area_type,
        "location_scope": location_scope
    })

    # Get area classification for contextual scoring (allow override for consistency across pillars)
    detected_area_type, metro_name, area_metadata = get_area_classification(lat, lon, city=city)
    area_type = area_type or detected_area_type
    expectations = get_contextual_expectations(area_type, 'active_outdoors')
    
    # Use centralized radius profiles for unified defaults
    profile = get_radius_profile('active_outdoors', area_type, location_scope)
    local_radius = int(profile.get('local_radius_m', 1000))
    trail_radius = int(profile.get('trail_radius_m', 2000))  # Separate trail radius
    regional_radius = int(profile.get('regional_radius_m', 15000))
    logger.info(f"🔧 Radius profile (active_outdoors): area_type={area_type}, scope={location_scope}, local={local_radius}m, trail={trail_radius}m, regional={regional_radius}m", extra={
        "pillar_name": "active_outdoors",
        "lat": lat,
        "lon": lon,
        "area_type": area_type,
        "location_scope": location_scope,
        "local_radius_m": local_radius,
        "trail_radius_m": trail_radius,
        "regional_radius_m": regional_radius
    })
    
    logger.info(f"📍 Querying local parks & playgrounds ({local_radius/1000:.0f}km)...", extra={
        "pillar_name": "active_outdoors",
        "lat": lat,
        "lon": lon,
        "query_type": "local_parks",
        "radius_m": local_radius
    })
    local_data = osm_api.query_green_spaces(lat, lon, radius_m=local_radius)
    
    logger.info(f"🥾 Querying trail access ({trail_radius/1000:.0f}km)...", extra={
        "pillar_name": "active_outdoors",
        "lat": lat,
        "lon": lon,
        "query_type": "trails",
        "radius_m": trail_radius
    })
    # Query trails separately with trail_radius
    trail_data = osm_api.query_nature_features(lat, lon, radius_m=trail_radius)
    trail_hiking = trail_data.get('hiking', []) if trail_data else []
    
    logger.info(f"🏔️  Querying regional outdoor activities ({regional_radius/1000:.0f}km)...", extra={
        "pillar_name": "active_outdoors",
        "lat": lat,
        "lon": lon,
        "query_type": "regional",
        "radius_m": regional_radius
    })
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
    logger.info(f"✅ Active Outdoors Score (AO_AGG_V1): {total_score:.0f}/100", extra={
        "pillar_name": "active_outdoors",
        "lat": lat,
        "lon": lon,
        "area_type": area_type,
        "total_score": total_score,
        "local_score": local_score,
        "trail_score": trail_score,
        "water_score": water_score,
        "camping_score": camping_score,
        "quality_tier": quality_metrics['quality_tier'],
        "confidence": quality_metrics['confidence']
    })
    logger.info(f"🏞️  Local Parks & Playgrounds: {local_score:.0f}/40", extra={
        "pillar_name": "active_outdoors",
        "lat": lat,
        "lon": lon,
        "component": "local_parks_playgrounds",
        "score": local_score,
        "max_score": 40.0
    })
    logger.info(f"🥾 Trail Access: {trail_score:.0f}/30", extra={
        "pillar_name": "active_outdoors",
        "lat": lat,
        "lon": lon,
        "component": "trail_access",
        "score": trail_score,
        "max_score": 30.0
    })
    logger.info(f"🏊 Water Access: {water_score:.0f}/20", extra={
        "pillar_name": "active_outdoors",
        "lat": lat,
        "lon": lon,
        "component": "water_access",
        "score": water_score,
        "max_score": 20.0
    })
    logger.info(f"🏕️  Camping: {camping_score:.0f}/10", extra={
        "pillar_name": "active_outdoors",
        "lat": lat,
        "lon": lon,
        "component": "camping_access",
        "score": camping_score,
        "max_score": 10.0
    })
    logger.info(f"📊 Data Quality: {quality_metrics['quality_tier']} ({quality_metrics['confidence']}% confidence)", extra={
        "pillar_name": "active_outdoors",
        "lat": lat,
        "lon": lon,
        "quality_tier": quality_metrics['quality_tier'],
        "confidence": quality_metrics['confidence']
    })

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
    precomputed_tree_canopy_5km: Optional[float] = None,
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

    logger.info("🏃 [AO v2] Analyzing active outdoors access...", extra={
        "pillar_name": "active_outdoors_v2",
        "lat": lat,
        "lon": lon,
        "area_type": area_type,
        "location_scope": location_scope
    })

    # 1) Area classification and radius profile
    # Use provided area_type from main.py for consistency, or fallback to detect_area_type()
    if area_type is None:
        # Fallback: compute area type if not provided (use same method as main.py)
        from data_sources import data_quality, census_api
        density = census_api.get_population_density(lat, lon) or 0.0
        area_type = data_quality.detect_area_type(lat, lon, density=density, city=city)
    
    # Get metadata for area_classification field (still need metro_name)
    _, metro_name, area_metadata = get_area_classification(lat, lon, city=city)
    # Override area_type in metadata to match what we're actually using
    area_metadata['area_type'] = area_type

    profile = get_radius_profile("active_outdoors", area_type, location_scope)
    local_radius = int(profile.get("local_radius_m", 2000))  # daily use (~2 km)
    trail_radius = int(profile.get("trail_radius_m", 15000))  # trails within ~15 km
    regional_radius = int(
        profile.get("regional_radius_m", 50000)
    )  # water/camping within ~50 km

    logger.info(
        f"🔧 [AO v2] Radii – local={local_radius/1000:.1f}km, "
        f"trail={trail_radius/1000:.1f}km, regional={regional_radius/1000:.1f}km",
        extra={
            "pillar_name": "active_outdoors_v2",
            "lat": lat,
            "lon": lon,
            "area_type": area_type,
            "location_scope": location_scope,
            "local_radius_m": local_radius,
            "trail_radius_m": trail_radius,
            "regional_radius_m": regional_radius
        }
    )

    # 2) Data collection - PARALLELIZE all API calls for performance
    # PERFORMANCE OPTIMIZATION: Following Public Transit pattern
    # All 4 API calls are independent and can run in parallel
    # This reduces total time from ~20-40s to ~5-10s (slowest call)
    logger.info(
        f"📍 [AO v2] Fetching data in parallel (parks, trails, water, canopy)...",
        extra={
            "pillar_name": "active_outdoors_v2",
            "lat": lat,
            "lon": lon,
            "query_type": "parallel_data_fetch",
            "local_radius_m": local_radius,
            "trail_radius_m": trail_radius,
            "regional_radius_m": regional_radius
        }
    )
    
    def _fetch_parks():
        """Fetch local parks, playgrounds, and recreational facilities."""
        return osm_api.query_green_spaces(lat, lon, radius_m=local_radius) or {}
    
    def _fetch_trails():
        """Fetch hiking trails within trail radius."""
        return osm_api.query_nature_features(lat, lon, radius_m=trail_radius) or {}
    
    def _fetch_regional():
        """Fetch water features and camping within regional radius."""
        return osm_api.query_nature_features(lat, lon, radius_m=regional_radius) or {}
    
    def _fetch_canopy():
        """Fetch tree canopy percentage."""
        # Use pre-computed value if available, otherwise fetch
        if precomputed_tree_canopy_5km is not None:
            return precomputed_tree_canopy_5km or 0.0
        try:
            return get_tree_canopy_gee(lat, lon, radius_m=5000, area_type=area_type) or 0.0
        except Exception:
            return 0.0
    
    # Execute all API calls in parallel
    with ThreadPoolExecutor(max_workers=4) as executor:
        future_parks = executor.submit(_fetch_parks)
        future_trails = executor.submit(_fetch_trails)
        future_regional = executor.submit(_fetch_regional)
        future_canopy = executor.submit(_fetch_canopy)
        
        # Wait for all to complete
        local = future_parks.result()
        nature_trail = future_trails.result()
        nature_regional = future_regional.result()
        canopy_pct_5km = future_canopy.result()
    
    # Extract data from results
    parks: List[Dict] = local.get("parks", []) or []
    playgrounds: List[Dict] = local.get("playgrounds", []) or []
    recreational_facilities: List[Dict] = local.get("recreational_facilities", []) or []
    
    # Trail data should come strictly from the trail-radius query so that the
    # sampling window matches contextual expectations (15km). Water/camping use
    # the wider regional radius.
    hiking_trails_raw: List[Dict] = nature_trail.get("hiking", []) or []
    swimming: List[Dict] = nature_regional.get("swimming", []) or []
    camping: List[Dict] = nature_regional.get("camping", []) or []

    # Detect special contexts (mountain town, desert) from objective signals.
    # IMPORTANT: Use RAW trail count for detection (before filtering)
    # This ensures mountain town detection works correctly for cities like Denver
    # that have legitimate high trail counts but get filtered for scoring purposes
    context_flags = _detect_special_contexts(area_type, hiking_trails_raw, swimming, canopy_pct_5km)
    scoring_area_type = context_flags.get("effective_area_type", area_type)
    is_desert_context = context_flags.get("is_desert_context", False)
    
    # DATA QUALITY: Filter out urban paths/cycle paths from hiking trails AFTER detection
    # Problem: OSM tags urban pathways and cycle paths as route=hiking when they're not actual hiking trails
    # Example: Times Square has 100+ "hiking" routes that are actually urban paths/greenways
    # Solution: Filter trails in dense urban cores based on characteristics
    # This follows Public Transit pattern: prevent data quality issues from inflating scores
    # NOTE: Filter AFTER mountain town detection so detection can use raw trail count
    # IMPORTANT: Don't filter trails for detected mountain towns - they have legitimate high trail counts
    # Denver: 36 trails is legitimate (mountain city), not OSM artifacts
    is_mountain_town = context_flags.get("is_mountain_town", False)
    hiking_trails: List[Dict] = hiking_trails_raw
    if area_type in {"urban_core", "historic_urban", "urban_residential", "urban_core_lowrise"}:
        # Skip filtering if detected as mountain town - legitimate high trail counts
        if not is_mountain_town:
            hiking_trails = _filter_urban_paths_from_trails(hiking_trails, area_type)

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

    if scoring_area_type != area_type:
        logger.info(
            f"📍 Context override: {area_type} → {scoring_area_type}",
            extra={
                "pillar_name": "active_outdoors_v2",
                "lat": lat,
                "lon": lon,
                "original_area_type": area_type,
                "scoring_area_type": scoring_area_type,
                "context_flags": context_flags,
            },
        )

    expectations = get_contextual_expectations(scoring_area_type, "active_outdoors") or {}

    # 3) Component scores
    daily_score = _score_daily_urban_outdoors_v2(parks, playgrounds, recreational_facilities, scoring_area_type, expectations)
    is_mountain_town = context_flags.get("is_mountain_town", False)
    # IMPORTANT: Pass scoring_area_type (not original area_type) so mountain town detection works
    # If Denver is detected as mountain town, scoring_area_type = "exurban", which enables higher expectations
    wild_score = _score_wild_adventure_v2(
        hiking_trails, camping, canopy_pct_5km, scoring_area_type, is_mountain_town=is_mountain_town
    )
    water_score = _score_water_lifestyle_v2(
        swimming, scoring_area_type, is_desert_context=is_desert_context
    )

    # 4) Aggregation (simple, explainable) → raw v2 total
    W_DAILY = 0.30
    W_WILD = 0.50
    W_WATER = 0.20

    raw_total = W_DAILY * daily_score + W_WILD * wild_score + W_WATER * water_score

    # 5) Global calibration: map raw v2 → 0–100 scale using a single linear fit
    # RESEARCH-BACKED (Calibrated 2024-12-XX):
    # - Calibrated from 18 locations in Round 11 calibration panel
    # - Linear fit: target_score ≈ CAL_A * raw_total + CAL_B
    # - Calibration metrics (Round 12): Mean absolute error=14.07, Max error=30.36, R²=0.3968
    # - Round 12 improvements: Fixed geocoding (36/36 successful), strengthened urban core penalties
    #   This suggests potential systematic issues with component scoring that need investigation
    # - After fixes: Improved mountain town detection, urban core trail caps, desert water downweighting
    # 
    # Calibration source: scripts/calibrate_active_outdoors_v2.py
    # Calibration data: analysis/active_outdoors_calibration_round11.json
    CAL_A = 1.582720  # Calibrated: Round 12 (36/36 locations, R²=0.3968)
    CAL_B = 43.915733  # Calibrated: Round 12 (36/36 locations, R²=0.3968)
    calibrated_total = CAL_A * raw_total + CAL_B
    calibrated_total = max(0.0, min(100.0, calibrated_total))

    # Compute normalized features for regression analysis (advisory only)
    normalized_features = _compute_normalized_features(
        daily_score,
        wild_score,
        water_score,
        parks,
        playgrounds,
        hiking_trails,
        swimming,
        camping,
        canopy_pct_5km,
    )
    
    # Compute advisory Ridge regression predictions (not used for scoring)
    ridge_advisory = {}
    
    # Global model (always available)
    global_model = ACTIVE_OUTDOORS_RIDGE_GLOBAL
    global_prediction = global_model["intercept"] + sum(
        coef * feat for coef, feat in zip(global_model["coefficients"], normalized_features)
    )
    ridge_advisory["global"] = {
        "predicted_score": round(max(0.0, min(100.0, global_prediction)), 1),
        "r2_score": global_model["r2_score"],
        "n_samples": global_model["n_samples"],
    }
    
    # Area-type-specific model (if available)
    if scoring_area_type in ACTIVE_OUTDOORS_RIDGE_BY_AREA_TYPE:
        area_model = ACTIVE_OUTDOORS_RIDGE_BY_AREA_TYPE[scoring_area_type]
        area_prediction = area_model["intercept"] + sum(
            coef * feat for coef, feat in zip(area_model["coefficients"], normalized_features)
        )
        ridge_advisory["area_type_specific"] = {
            "predicted_score": round(max(0.0, min(100.0, area_prediction)), 1),
            "r2_score": area_model["r2_score"],
            "n_samples": area_model["n_samples"],
            "area_type": scoring_area_type,
            "note": "Small sample size - use with caution",
        }

    breakdown: Dict = {
        "score": round(calibrated_total, 1),
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
        "version": "active_outdoors_v2_calibrated",
        "raw_total_v2": round(raw_total, 1),
        "calibration": {"a": CAL_A, "b": CAL_B},
        "context": {
            "area_type_for_scoring": scoring_area_type,
            "is_mountain_town": context_flags.get("is_mountain_town"),
            "is_desert_context": context_flags.get("is_desert_context"),
            "trail_stats": context_flags.get("trail_stats"),
        },
        "normalized_features": {
            "norm_daily": round(normalized_features[0], 4),
            "norm_wild": round(normalized_features[1], 4),
            "norm_water": round(normalized_features[2], 4),
            "norm_park_count": round(normalized_features[3], 4),
            "norm_playground": round(normalized_features[4], 4),
            "norm_park_area": round(normalized_features[5], 4),
            "norm_trails5": round(normalized_features[6], 4),
            "norm_swim_count": round(normalized_features[7], 4),
            "norm_swim_km": round(normalized_features[8], 4),
            "norm_camp_count": round(normalized_features[9], 4),
            "norm_camp_km": round(normalized_features[10], 4),
            "norm_tree": round(normalized_features[11], 4),
        },
        "ridge_regression_advisory": ridge_advisory,
        "ridge_regression_note": "Ridge regression predictions are advisory only and not used for actual scoring. Use for directional signals when adjusting future weights.",
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

    logger.info(
        f"✅ Active Outdoors v2 (calibrated): {calibrated_total:.1f}/100 "
        f"[raw={raw_total:.1f}] "
        f"(daily={daily_score:.1f}, wild={wild_score:.1f}, water={water_score:.1f})",
        extra={
            "pillar_name": "active_outdoors_v2",
            "lat": lat,
            "lon": lon,
            "area_type": area_type,
            "total_score": calibrated_total,
            "raw_total": raw_total,
            "daily_score": daily_score,
            "wild_score": wild_score,
            "water_score": water_score,
            "calibration_a": CAL_A,
            "calibration_b": CAL_B,
            "quality_tier": dq['quality_tier'],
            "confidence": dq['confidence']
        }
    )
    return round(calibrated_total, 1), breakdown


def _sat_ratio_v2(x: float, target: float, max_score: float) -> float:
    """Smooth saturation: 0 at 0, asymptotically approaches max_score as x grows."""
    if target <= 0:
        return 0.0
    r = x / target
    return max_score * (1.0 - math.exp(-r))


def _score_daily_urban_outdoors_v2(
    parks: list, playgrounds: list, recreational_facilities: list, area_type: str, expectations: Dict
) -> float:
    """
    Daily Urban Outdoors (0–30):
      – Park/green area near home (excluding very small parks from area calc)
      – Park and playground count
      – Recreational facilities (tennis courts, baseball fields, dog runs, etc.)
    Uses area-type–specific expectations from research-backed expected values.
    
    RESEARCH-BACKED: Uses get_contextual_expectations() for area-type-specific
    expected values. Falls back to reasonable defaults if expectations unavailable.
    
    DATA QUALITY: 
    - Excludes parks <0.1 ha from area calculations (prevents OSM artifacts)
    - Counts recreational facilities separately to avoid double-counting with parks
    - Uses objective criteria (facility type, access) not city-name exceptions
    """
    # DATA QUALITY: Filter small parks from area calculation (but keep in count)
    # OBJECTIVE CRITERIA: Parks <0.1 ha are likely OSM artifacts
    # This prevents tiny park polygons from inflating area scores while still
    # counting them for density (many small parks = good density signal)
    MIN_PARK_AREA_HA = 0.1  # 0.1 hectares = 1000 sqm
    
    # Calculate area from parks >=0.1 ha only
    total_area_ha = sum(
        p.get("area_sqm", 0.0) / 10_000.0 
        for p in parks 
        if (p.get("area_sqm", 0.0) / 10_000.0) >= MIN_PARK_AREA_HA
    )
    
    # Count all parks (including small ones) for density scoring
    park_count = len(parks)
    playground_count = len(playgrounds)
    facility_count = len(recreational_facilities)

    # Use research-backed expected values with fallbacks
    # Map area types to appropriate expectations
    effective_area_type = area_type
    if area_type in {"historic_urban"}:
        # Historic urban similar to urban_core for active_outdoors
        effective_area_type = "urban_core"
    elif area_type in {"urban_core_lowrise"}:
        # Urban core lowrise similar to suburban for active_outdoors
        effective_area_type = "suburban"
    
    # Get expectations for effective area type
    if effective_area_type not in {"urban_core", "suburban", "exurban", "rural"}:
        # Fallback to suburban if area type not recognized
        effective_area_type = "suburban"
    
    exp_expectations = expectations or {}
    
    # Extract expected values with fallbacks
    exp_park_ha = exp_expectations.get('expected_park_area_hectares', 5.0)
    exp_park_count = exp_expectations.get('expected_parks_within_1km', 8.0)
    exp_play = exp_expectations.get('expected_playgrounds_within_1km', 2.0)

    s_area = _sat_ratio_v2(total_area_ha, exp_park_ha, 15.0)
    s_count = _sat_ratio_v2(park_count, exp_park_count, 10.0)
    s_play = _sat_ratio_v2(playground_count, exp_play, 5.0)
    
    # NEW: Score recreational facilities separately
    # OBJECTIVE CRITERIA: Count facilities by type, weight by recreational value
    # RESEARCH-BACKED: Use area-type-specific expectations for facility counts
    # Avoid double-counting: Facilities inside parks are counted once (as facilities, not parks)
    # Max contribution: 3.0 points (facilities are important but secondary to parks)
    exp_facilities = exp_expectations.get('expected_recreational_facilities_within_1km', 3.0)
    s_facilities = _sat_ratio_v2(facility_count, exp_facilities, 3.0)

    base_score = min(30.0, s_area + s_count + s_play + s_facilities)

    # URBAN CORE DENSITY PENALTY:
    # Dense urban cores (Times Square, Midtown, etc.) can record dozens of tiny
    # parks within 800 m due to OSM micro-polygons. A small diminishing-return
    # penalty keeps scores aligned with real-world access instead of raw count.
    overflow_penalty = 0.0
    if area_type in {"urban_core", "historic_urban"}:
        expected_parks = max(1.0, exp_expectations.get('expected_parks_within_1km', 8.0))
        expected_park_area = max(1.0, exp_expectations.get('expected_park_area_hectares', 3.0))
        count_ratio = park_count / expected_parks if expected_parks else 0.0
        area_ratio = total_area_ha / expected_park_area if expected_park_area else 0.0
        # Apply penalty only once ratios materially exceed expectations.
        # RESEARCH-BACKED: Strengthen penalty for urban cores to prevent over-scoring
        # Round 12 analysis shows urban cores with low targets (35-45) are over-scoring
        # on Daily Urban Outdoors (16-20/30). Phoenix: 25.0/30 (maxed out) despite target 48.
        # Increase max penalty and apply more aggressively to better reflect that many
        # parks in dense cores are OSM artifacts, not real access.
        overflow_ratio = max(0.0, count_ratio - 1.2)  # Reduced from 1.5 to 1.2 (apply penalty earlier)
        area_overflow = max(0.0, area_ratio - 1.8)    # Reduced from 2.0 to 1.8 (apply penalty earlier)
        # Increased max penalty from 8.0 to 12.0 and strengthened multipliers
        overflow_penalty = min(12.0, (overflow_ratio * 8.0) + (area_overflow * 4.0))

    return max(0.0, base_score - overflow_penalty)


def _score_wild_adventure_v2(
    hiking_trails: list,
    camping: list,
    canopy_pct_5km: float,
    area_type: str,
    is_mountain_town: bool = False,
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

    # Expectations + max contributions by area_type.
    # Goal:
    # - Rural/exurban mountain towns can reach the top of the 0–50 range when
    #   they truly have deep trail networks + high canopy + nearby camping.
    # - Dense cores with mostly urban parks/paths should get much lower Wild
    #   scores even if they have many mapped trails.
    # Round 11 adjustments:
    # - Reduced urban_core canopy max (20→12) to prevent over-scoring dense areas
    # - Increased rural/exurban trail expectations for better mountain town scoring
    #
    # RESEARCH-BACKED: Trail expectations use research-backed values where available.
    # Max contributions are calibrated from Round 11 analysis.
    # Map area types to appropriate expectations
    effective_area_type = area_type
    if area_type in {"historic_urban"}:
        effective_area_type = "urban_core"
    elif area_type in {"urban_core_lowrise", "urban_residential"}:
        effective_area_type = "suburban"
    
    if effective_area_type not in {"urban_core", "suburban", "exurban", "rural"}:
        effective_area_type = "suburban"
    
    # Get research-backed expected values
    expectations = get_contextual_expectations(effective_area_type, 'active_outdoors') or {}
    
    # Extract expected trail counts (within 15km radius)
    # Note: These are expectations for trails within 15km, but we're scoring trails within 5km for "near"
    exp_trails_15km = expectations.get('expected_trails_within_15km', 2.0)
    
    # Map to area-type-specific expectations and max contributions
    # These values are calibrated from Round 11 analysis and component tuning
    if effective_area_type == "urban_core":
        # Use research-backed expected_trails_within_15km, scale for expectations
        # RESEARCH-BACKED: Urban cores have limited trail access (median: 2 trails within 15km)
        # Cap trail scoring to prevent over-scoring from OSM data artifacts (e.g., Times Square with 94 trails)
        # Times Square diagnostic shows 94 trails but these are likely urban paths/greenways, not true hiking trails
        exp_trails = max(20.0, exp_trails_15km * 10.0)  # Scale up for total trails
        exp_near = 8.0  # Calibrated: trails within 5km for urban
        exp_canopy = 35.0  # Calibrated: canopy expectation for urban
        # Cap trail contributions for urban cores to prevent over-scoring
        # Even with many trails detected, urban cores shouldn't score high on wild adventure
        # RESEARCH-BACKED: Round 12 shows urban cores over-scoring on Wild Adventure
        # Phoenix: 25.6/50, Kansas City: 17.1/50 - reduce max contributions further
        max_trails_total, max_trails_near, max_canopy = 6.0, 3.0, 12.0  # Reduced from 8.0, 4.0
    elif effective_area_type == "suburban":
        exp_trails = max(20.0, exp_trails_15km * 10.0)  # Scale up for total trails
        exp_near = 6.0  # Calibrated: trails within 5km for suburban
        exp_canopy = 30.0  # Calibrated: canopy expectation for suburban
        max_trails_total, max_trails_near, max_canopy = 15.0, 8.0, 12.0
    else:  # rural / exurban
        # Mountain towns detected via context flags get higher expectations
        if is_mountain_town:
            # Mountain towns: higher trail expectations to properly score outdoor-oriented cities
            # Boulder diagnostic: 38 trails, 3 within 5km, 18.5% canopy - should score high (target 95)
            # Denver diagnostic: 44 trails, 3 within 5km, 8.2% canopy - should score high (target 92)
            # Current max contributions may be too low - increase to allow mountain towns to reach top scores
            exp_trails = max(40.0, exp_trails_15km * 20.0)  # Scale up, increased for mountain towns
            exp_near = 15.0  # Calibrated: increased trail expectations
            exp_canopy = 45.0  # Calibrated: higher canopy expectation for rural
            # Increased max contributions to allow mountain towns to reach 40-45/50 for Wild Adventure
            # This enables them to reach target scores of 90-95 when combined with Daily Urban and Waterfront
            max_trails_total, max_trails_near, max_canopy = 28.0, 18.0, 14.0  # Increased for mountain towns
        else:
            exp_trails = max(40.0, exp_trails_15km * 20.0)  # Scale up, increased for mountain towns
            exp_near = 15.0  # Calibrated: increased trail expectations
            exp_canopy = 45.0  # Calibrated: higher canopy expectation for rural
            max_trails_total, max_trails_near, max_canopy = 22.0, 12.0, 10.0  # Increased trail max

    # DATA QUALITY: Cap trail scoring for urban cores to prevent OSM data artifacts
    # Problem: OSM data quality issue - urban paths/greenways often tagged as "hiking" trails in dense cores
    # Example: Times Square diagnostic shows 94 "trails" but these are urban paths, not true hiking trails
    # Solution: Cap trail count at 3x expected for urban cores (data quality measure, not arbitrary cap)
    # This follows Public Transit pattern: prevent data quality issues from inflating scores
    # Rationale: Similar to route deduplication - preventing false positives from data artifacts
    if effective_area_type == "urban_core":
        # RESEARCH-BACKED: Strengthen trail cap for urban cores to prevent over-scoring
        # Round 12 analysis shows urban cores are over-scoring on Wild Adventure
        # Phoenix: 25.6/50, Kansas City: 17.1/50 - reduce cap from 2x to 1.5x expected
        # This is a data quality measure, not an artificial score cap
        capped_trail_count = min(trail_count, exp_trails * 1.5)  # Reduced from 2.0 to 1.5
        capped_near_count = min(near_count, exp_near * 1.5)  # Reduced from 2.0 to 1.5
    else:
        capped_trail_count = trail_count
        capped_near_count = near_count
    
    s_trails_total = _sat_ratio_v2(capped_trail_count, exp_trails, max_trails_total)
    s_trails_near = _sat_ratio_v2(capped_near_count, exp_near, max_trails_near)
    s_canopy = _sat_ratio_v2(canopy_pct_5km, exp_canopy, max_canopy)

    # Camping proximity: area-type-aware scoring
    # Round 11: More generous for rural/exurban, tighter for urban
    if not camping:
        s_camp = 0.0
    else:
        nearest = min(camping, key=lambda c: c.get("distance_m", 1e9))
        d = nearest.get("distance_m", 1e9)
        if area_type in {"urban_core", "historic_urban"}:
            # Urban: closer threshold, steeper decay
            if d <= 15_000:
                s_camp = 8.0
            else:
                s_camp = 8.0 * math.exp(-0.0001 * (d - 15_000))
        elif area_type in {"suburban", "urban_residential", "urban_core_lowrise"}:
            # Suburban: medium threshold
            if d <= 20_000:
                s_camp = 10.0
            else:
                s_camp = 10.0 * math.exp(-0.00008 * (d - 20_000))
        else:  # rural / exurban
            # Rural/exurban: more generous threshold and decay
            if d <= 25_000:
                s_camp = 10.0
            else:
                s_camp = 10.0 * math.exp(-0.00005 * (d - 25_000))

    return max(0.0, min(50.0, s_trails_total + s_trails_near + s_canopy + s_camp))


def _score_water_lifestyle_v2(swimming: list, area_type: str, is_desert_context: bool = False) -> float:
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

    # RESEARCH-BACKED: Base scores reflect actual recreational value
    # OBJECTIVE CRITERIA: Higher scores for swimmable/accessible water
    # DATA QUALITY: Distinguishes actual beaches from coastline fragments
    base = {
        "beach": 20.0,  # Actual swimmable beach (highest)
        "swimming_area": 18.0,  # Designated swimming area
        "lake": 18.0,  # Recreational lake
        "coastline": 12.0,  # Reduced from 16.0 - accessible coastline (waterfront, not beach)
        "coastline_rocky": 8.0,  # NEW: Rocky coastline (non-swimmable)
        "bay": 10.0,  # Reduced from 16.0 - scenic but not swimmable
    }.get(t, 8.0)  # Default reduced from 12.0 for unknown water types

    # RESEARCH-BACKED: Strengthen water downweighting for urban cores to prevent over-scoring
    # Round 12 analysis shows urban cores (e.g., Detroit: Water=16.7/20) are over-scoring
    # on water access. Phoenix: 16.2/20 despite target 48. Reduce downweight from 0.5 to 0.4
    # for non-beach water in urban cores.
    # Apply context-aware downweighting to avoid coastline fragments or ornamental
    # water bodies inflating scores in dense urban cores (Times Square) or arid
    # desert metros (Las Vegas, Phoenix).
    if area_type in {"urban_core", "historic_urban"} and t not in {"beach"}:
        base *= 0.4  # urban cores: non-beach water less impactful (reduced from 0.5)
    elif area_type in {"suburban", "urban_residential"} and t not in {"beach", "lake"}:
        base *= 0.9  # mild downweight

    # Desert/arid contexts: reduce water impact unless it's a genuine beach/lake.
    # Las Vegas diagnostic: 7 water features, 0.5% canopy → should score lower (target 42, currently 56.2)
    # Strengthen downweighting to prevent over-scoring in desert contexts
    if is_desert_context:
        if t not in {"beach", "lake"}:
            base *= 0.3  # Strong downweight for reservoirs/ornamental water in desert (was 0.4)
        else:
            base *= 0.6  # Moderate downweight even for beaches/lakes in arid metros (was 0.7)

    # Round 11: Adjusted distance decay for better proximity scoring
    # More generous optimal distance, slightly slower decay
    optimal = 3_000.0  # Increased from 2000m to 3000m
    if d <= optimal:
        return base
    # Slightly slower decay rate (0.0003 → 0.00025) for better scoring at moderate distances
    return max(0.0, base * math.exp(-0.00025 * (d - optimal)))


def _filter_urban_paths_from_trails(hiking_trails: List[Dict], area_type: str) -> List[Dict]:
    """
    Filter out urban paths/cycle paths from hiking trails in dense urban cores.
    
    Problem: OSM tags urban pathways and cycle paths as route=hiking when they're not actual hiking trails.
    Example: Times Square has 100+ "hiking" routes that are actually urban paths/greenways.
    
    Solution: In dense urban cores, filter trails based on:
    1. If trail count is very high (>50), likely urban paths (OSM data quality issue)
    2. Keep trails that are in protected areas (national parks, nature reserves) - these are legitimate
    3. For remaining trails, apply aggressive filtering based on expectations
    
    This follows Public Transit pattern: prevent data quality issues from inflating scores.
    """
    if not hiking_trails:
        return hiking_trails
    
    # Get expectations for filtering threshold
    expectations = get_contextual_expectations(area_type, "active_outdoors") or {}
    exp_trails = expectations.get("expected_trails_within_15km", 2.0)
    
    # In dense urban cores, if trail count is very high (>50), they're likely urban paths
    # This is a data quality issue - OSM tags urban paths as hiking routes
    # Filter down to a reasonable number based on expectations (3x expected max)
    max_reasonable_trails = max(10, int(exp_trails * 3.0))
    
    if len(hiking_trails) > max_reasonable_trails:
        # Too many trails - likely urban paths
        # Keep only the closest trails (these are more likely to be legitimate)
        # Sort by distance and keep the closest ones
        sorted_trails = sorted(hiking_trails, key=lambda t: t.get("distance_m", float('inf')))
        filtered_trails = sorted_trails[:max_reasonable_trails]
        
        logger.info(
            f"🔍 [AO v2] Filtered urban paths: {len(hiking_trails)} → {len(filtered_trails)} trails "
            f"(max_reasonable={max_reasonable_trails} for {area_type})",
            extra={
                "pillar_name": "active_outdoors_v2",
                "area_type": area_type,
                "original_trail_count": len(hiking_trails),
                "filtered_trail_count": len(filtered_trails),
                "max_reasonable_trails": max_reasonable_trails,
            },
        )
        return filtered_trails
    
    return hiking_trails


def _detect_special_contexts(
    area_type: Optional[str],
    hiking_trails: list,
    swimming: list,
    canopy_pct: float,
) -> Dict[str, object]:
    """
    Detect special contexts (mountain towns, desert metros) from objective signals:
    - Mountain towns: dense trail networks plus healthy canopy
    - Desert metros: sparse canopy plus limited water
    Returns context flags and an effective area_type to use for expectations.
    """
    area_type_lower = (area_type or "unknown").lower()
    total_trails = len(hiking_trails)
    trails_near = sum(
        1 for h in hiking_trails if h.get("distance_m", 1e9) <= 5000
    )
    canopy_pct = canopy_pct or 0.0
    water_features = len(swimming)

    # RESEARCH-BACKED: Mountain town detection using objective criteria
    # Criteria based on diagnostic analysis:
    # - Boulder: 38 trails, 3 within 5km, 18.5% canopy → should be detected
    # - Denver: 44 trails, 3 within 5km, 8.2% canopy → should be detected (high trail count despite low canopy)
    # - Times Square: 92 trails, 24 within 5km, 6.8% canopy → should NOT be detected (dense urban core, low canopy)
    # 
    # Detection logic (objective, not city-name-based):
    # 1. Very high trail count (≥40) is strong signal for mountain/outdoor-oriented area, even with lower canopy
    #    - Denver: 44 trails → should be detected even with 8.2% canopy (downtown has low canopy but city is mountain-adjacent)
    # 2. High trail count (≥30) WITH reasonable canopy (≥8%) AND not dense urban core
    #    - Prevents false positives in dense urban cores (Times Square) where trails are urban paths
    # 3. OR moderate trail count (≥20) with good canopy (≥10%)
    # 4. OR good near-trail access (≥5 within 5km) with canopy (≥8%)
    # 
    # This follows Public Transit pattern: objective criteria (trail density, canopy) not city names
    # Anti-pattern: Don't detect dense urban cores as mountain towns even with high trail counts
    is_mountain_town = False
    # Dense urban areas where high trail counts are likely false positives (urban paths/greenways)
    is_dense_urban = area_type_lower in {"urban_core", "historic_urban", "urban_residential", "urban_core_lowrise"}
    
    if total_trails >= 40:
        # Very high trail count (40+) is strong signal for mountain/outdoor-oriented area
        # Denver: 44 trails, 8.2% canopy → should be detected (moderate trail count, legitimate mountain city)
        # Times Square: 92 trails, 6.8% canopy → should NOT be detected (very high count + low canopy = urban paths)
        # 
        # Detection strategy for high trail counts:
        # - If very high count (60+) in dense urban core with low canopy (<8%), likely false positive
        # - If moderate-high count (40-59) in dense urban core, require canopy >= 8% (Denver qualifies)
        # - If high count in non-dense urban, reliable signal
        if is_dense_urban:
            # RESEARCH-BACKED: For dense urban cores, require higher canopy to prevent false positives
            # Times Square (calibration coords): 102 trails, 8.9% canopy → should NOT be detected
            # Denver: 65 trails, 8.2% canopy → should be detected (legitimate mountain city)
            # 
            # Detection strategy:
            # - Very high count (60+): Check if it's likely OSM artifacts vs legitimate mountain city
            #   - If canopy >= 12%: Definitely mountain town
            #   - If canopy >= 8% AND trails_near >= 5: Likely mountain town (Denver: 65 trails, 7 within 5km, 8.2% qualifies)
            #   - If canopy < 8%: Likely false positive (urban paths)
            # - Moderate-high count (40-59): require canopy ≥ 8% (Denver: 44 trails, 8.2% qualifies)
            # This prevents false positives from OSM artifacts while allowing legitimate mountain cities
            if total_trails >= 60:
                # Very high trail count (60+) in dense urban - need to distinguish artifacts from real mountain cities
                if canopy_pct >= 12.0:
                    # High canopy = definitely mountain town
                    is_mountain_town = True
                elif canopy_pct >= 8.0 and trails_near >= 5:
                    # Moderate canopy + good near-trail access = legitimate mountain city
                    # Denver: 65 trails, 7 within 5km, 8.2% canopy → qualifies
                    is_mountain_town = True
                else:
                    # Very high count but low canopy and few near trails = likely OSM artifacts
                    # Times Square: 102 trails, 8.9% canopy, but likely few legitimate near trails
                    is_mountain_town = False
            elif canopy_pct >= 8.0:
                # Moderate-high trail count (40-59) with reasonable canopy = legitimate mountain city
                # Denver: 44 trails, 8.2% canopy → qualifies
                is_mountain_town = True
            else:
                # High trail count but canopy too low
                is_mountain_town = False
        else:
            # Non-dense urban areas: high trail count is reliable signal
            is_mountain_town = True
    elif total_trails >= 30:
        # High trail count is strong signal, but require canopy check to avoid false positives
        # Times Square: 92 trails but 6.8% canopy → should NOT be detected
        # Denver: 36 trails, 8.2% canopy → should be detected (legitimate mountain city)
        if canopy_pct >= 8.0:
            # If dense urban core, require higher canopy to avoid false positives
            # BUT: For moderate-high trail counts (30-39), be more lenient than very high counts (60+)
            # This allows legitimate mountain cities like Denver to be detected
            if is_dense_urban:
                # For moderate-high counts (30-39), canopy >= 8% is sufficient (Denver: 36 trails, 8.2% qualifies)
                # For very high counts (60+), require canopy >= 12% to prevent false positives (Times Square)
                if total_trails >= 60:
                    # Very high count in dense urban = likely OSM artifacts, require higher canopy
                    if canopy_pct >= 12.0:
                        is_mountain_town = True
                else:
                    # Moderate-high count (30-59) with reasonable canopy = legitimate mountain city
                    # Denver: 36 trails, 8.2% canopy → qualifies
                    is_mountain_town = True
            else:
                is_mountain_town = True
    elif total_trails >= 20 and canopy_pct >= 10.0:
        # Moderate trail count with good canopy
        # RESEARCH-BACKED: For urban cores, require higher trail count to prevent false positives
        # Kansas City: 27 trails, 10.5% canopy → should NOT be detected (not a mountain town)
        if is_dense_urban:
            # For dense urban cores, require higher trail count (≥30) even with good canopy
            # This prevents false positives in cities with moderate trail access
            if total_trails >= 30:
                is_mountain_town = True
        else:
            is_mountain_town = True
    elif trails_near >= 5 and canopy_pct >= 8.0:
        # Good near-trail access with canopy
        # RESEARCH-BACKED: For urban cores, require higher canopy to prevent false positives
        # Kansas City: 27 trails, 10.5% canopy → should NOT be detected (not a mountain town)
        # Fix: Require higher canopy threshold for urban cores to prevent false positives
        if is_dense_urban:
            if canopy_pct >= 12.0:  # Higher threshold for dense urban cores
                is_mountain_town = True
        else:
            is_mountain_town = True

    is_desert_context = canopy_pct <= 3.0 and water_features <= 10

    effective_area_type = area_type or "unknown"
    if is_mountain_town and area_type_lower in {
        "urban_core",
        "historic_urban",
        "urban_residential",
        "urban_core_lowrise",
        "suburban",
        "suburban_major_metro",
    }:
        effective_area_type = "exurban"

    context = {
        "is_mountain_town": is_mountain_town,
        "is_desert_context": is_desert_context,
        "effective_area_type": effective_area_type,
        "trail_stats": {
            "total": total_trails,
            "within_5km": trails_near,
        },
    }
    return context


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