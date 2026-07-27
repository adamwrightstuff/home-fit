"""
Active Outdoors Pillar
Scores access to outdoor activities and recreation
"""

import math
import time
from typing import Dict, Tuple, Optional, List

from data_sources import osm_api
from data_sources.osm_api import coerce_green_spaces_response, coerce_nature_features_response
from data_sources.data_quality import assess_pillar_data_quality, get_baseline_context
from data_sources.gee_api import get_tree_canopy_gee
from data_sources.regional_baselines import (
    get_area_classification,
    get_contextual_expectations,
)
from data_sources.radius_profiles import get_radius_profile
from data_sources.places_active_outdoors_client import maybe_augment_active_outdoors_with_places
from logging_config import get_logger

# Initialize logger
logger = get_logger(__name__)

# A2: stagger sequential Overpass calls to reduce 429/timeouts vs parallel bursts.
_OVERPASS_STAGGER_S = 1.0


def _active_outdoors_confidence_notes(
    dq: Dict,
    parks: List[Dict],
    playgrounds: List[Dict],
    hiking: List[Dict],
    swimming: List[Dict],
    camping: List[Dict],
) -> List[str]:
    """
    C2: short hints when confidence is low. Completeness (B1) unchanged elsewhere.
    """
    conf = int(dq.get("confidence") or 0)
    tier = dq.get("quality_tier") or ""
    if conf >= 70 and tier in ("excellent", "good"):
        return []

    em = dq.get("expected_minimums") or {}
    loc_need = max(1, int(em.get("local_facilities", 5)))
    reg_need = max(1, int(em.get("regional_facilities", 3)))
    local_n = len(parks) + len(playgrounds)
    regional_n = len(hiking) + len(swimming) + len(camping)

    notes: List[str] = []
    if local_n < loc_need * 0.5:
        notes.append(
            "Local park and playground coverage in OpenStreetMap is below what we expect "
            "for this area—confidence in the “daily outdoors” part of the score is limited."
        )
    if regional_n < reg_need * 0.5:
        notes.append(
            "Trails, water access, and camping signals in OSM are sparse versus expectations—"
            "confidence in the “regional outdoors” part is limited."
        )
    if not notes and conf < 70:
        notes.append(
            "Overall OSM coverage for this pillar is partial; the score reflects what we found, "
            "but treat confidence as moderate."
        )
    return notes[:3]


# ============================================================================
# Active Outdoors v2 – data-centric outdoor lifestyle model
# ============================================================================

def get_active_outdoors_score_v2(
    lat: float,
    lon: float,
    city: Optional[str] = None,
    area_type: Optional[str] = None,
    location_scope: Optional[str] = None,
    precomputed_tree_canopy_5km: Optional[float] = None,
    trip_type: Optional[str] = None,
) -> Tuple[float, Dict]:
    """
    Compute Active Outdoors v2 (0–100).

    Built on three objective components (same scale as Natural Beauty-style pillars):
      - Daily Urban Outdoors (0–35)
      - Wild Adventure Backbone (0–50)
      - Waterfront Lifestyle (0–25)

    Final score = daily + wild + water (capped 0–100). Underlying data: OSM, GEE canopy, etc.
    area_type sets expectations only (no per-city score hacks).
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

    # 2) Data collection — A2: sequential Overpass with stagger (GEE canopy last, no Overpass)
    logger.info(
        f"📍 [AO v2] Fetching data sequentially (Overpass stagger {_OVERPASS_STAGGER_S}s): "
        f"parks → trails → regional → canopy...",
        extra={
            "pillar_name": "active_outdoors_v2",
            "lat": lat,
            "lon": lon,
            "query_type": "sequential_overpass_stagger",
            "stagger_s": _OVERPASS_STAGGER_S,
            "local_radius_m": local_radius,
            "trail_radius_m": trail_radius,
            "regional_radius_m": regional_radius
        }
    )
    
    def _fetch_parks():
        """Fetch local parks, playgrounds, and recreational facilities."""
        result = coerce_green_spaces_response(
            osm_api.query_green_spaces(lat, lon, radius_m=local_radius)
        )
        # Debug metadata (no PII): helps distinguish live vs stale-cache vs empty results.
        try:
            result = result or {}
            result["_debug_parks"] = {
                "stale_cache": bool(result.get("_stale_cache")),
                "cache_age_hours": result.get("_cache_age_hours"),
                "data_warning": result.get("data_warning"),
                "parks_count": len(result.get("parks", []) or []),
                "playgrounds_count": len(result.get("playgrounds", []) or []),
                "facilities_count": len(result.get("recreational_facilities", []) or []),
            }
        except Exception:
            # Never fail scoring due to debug info
            result = result or {}
        # DIAGNOSTIC: Log what we got from the query
        if result is None:
            logger.warning(
                f"🔍 [PARKS DIAGNOSTIC v2] query_green_spaces returned None "
                f"(radius={local_radius}m, lat={lat}, lon={lon})",
                extra={
                    "pillar_name": "active_outdoors_v2",
                    "lat": lat,
                    "lon": lon,
                    "radius_m": local_radius,
                }
            )
        elif result and isinstance(result, dict):
            parks_count = len(result.get("parks", []))
            if parks_count == 0:
                logger.warning(
                    f"🔍 [PARKS DIAGNOSTIC v2] query_green_spaces returned dict with 0 parks "
                    f"(playgrounds={len(result.get('playgrounds', []))}, "
                    f"facilities={len(result.get('recreational_facilities', []))}, "
                    f"radius={local_radius}m)",
                    extra={
                        "pillar_name": "active_outdoors_v2",
                        "lat": lat,
                        "lon": lon,
                        "radius_m": local_radius,
                        "playground_count": len(result.get("playgrounds", [])),
                        "facility_count": len(result.get("recreational_facilities", [])),
                    }
                )
        return result or {}
    
    def _fetch_trails():
        """Fetch hiking trails within trail radius."""
        return coerce_nature_features_response(
            osm_api.query_nature_features(lat, lon, radius_m=trail_radius)
        )

    def _fetch_regional():
        """Fetch water features and camping within regional radius."""
        # PERFORMANCE: Regional AO v2 only consumes water + camping from this result.
        # Skip hiking routes/protected-area queries to reduce Overpass payload and latency.
        return coerce_nature_features_response(
            osm_api.query_nature_features(
                lat, lon, radius_m=regional_radius, include_hiking=False
            )
        )
    
    def _fetch_canopy():
        """Fetch tree canopy percentage."""
        # Use pre-computed value if available, otherwise fetch
        if precomputed_tree_canopy_5km is not None:
            return precomputed_tree_canopy_5km or 0.0
        try:
            return get_tree_canopy_gee(lat, lon, radius_m=5000, area_type=area_type) or 0.0
        except Exception:
            return 0.0
    
    # Sequential fetch: this function is called from inside the outer ThreadPoolExecutor
    # in main.py (one slot per pillar), so nesting another pool would create 52+ peak
    # threads across 13 pillars.  The four calls here are short-latency OSM/GEE fetches
    # that don't benefit from intra-pillar parallelism.
    local = _fetch_parks()
    nature_trail = _fetch_trails()
    nature_regional = _fetch_regional()
    canopy_pct_5km = _fetch_canopy()
    
    # Extract data from results
    parks: List[Dict] = local.get("parks", []) or []
    playgrounds: List[Dict] = local.get("playgrounds", []) or []
    recreational_facilities: List[Dict] = local.get("recreational_facilities", []) or []
    
    # DIAGNOSTIC: Log parks query result
    if not parks and local:
        logger.warning(
            f"🔍 [PARKS DIAGNOSTIC v2] query_green_spaces returned data but 0 parks "
            f"(playgrounds={len(playgrounds)}, facilities={len(recreational_facilities)}, "
            f"radius={local_radius}m, area_type={area_type})",
            extra={
                "pillar_name": "active_outdoors_v2",
                "lat": lat,
                "lon": lon,
                "radius_m": local_radius,
                "area_type": area_type,
                "playground_count": len(playgrounds),
                "facility_count": len(recreational_facilities),
            }
        )
    elif not local:
        logger.warning(
            f"🔍 [PARKS DIAGNOSTIC v2] query_green_spaces returned None/empty "
            f"(radius={local_radius}m, area_type={area_type})",
            extra={
                "pillar_name": "active_outdoors_v2",
                "lat": lat,
                "lon": lon,
                "radius_m": local_radius,
                "area_type": area_type,
            }
        )
    elif parks:
        logger.info(
            f"🔍 [PARKS DIAGNOSTIC v2] Successfully fetched {len(parks)} parks "
            f"(playgrounds={len(playgrounds)}, facilities={len(recreational_facilities)})",
            extra={
                "pillar_name": "active_outdoors_v2",
                "lat": lat,
                "lon": lon,
                "park_count": len(parks),
                "playground_count": len(playgrounds),
                "facility_count": len(recreational_facilities),
            }
        )
    
    # Trail data should come strictly from the trail-radius query so that the
    # sampling window matches contextual expectations (15km). Water/camping use
    # the wider regional radius.
    hiking_trails_raw: List[Dict] = nature_trail.get("hiking", []) or []
    swimming: List[Dict] = nature_regional.get("swimming", []) or []
    camping: List[Dict] = nature_regional.get("camping", []) or []

    places_ao_meta = maybe_augment_active_outdoors_with_places(
        lat,
        lon,
        local_radius_m=local_radius,
        regional_radius_m=regional_radius,
        parks=parks,
        playgrounds=playgrounds,
        swimming=swimming,
        camping=camping,
        local_overpass_outcome=local.get("_overpass_outcome") if isinstance(local, dict) else None,
        trail_overpass_outcome=nature_trail.get("_overpass_outcome")
        if isinstance(nature_trail, dict)
        else None,
        regional_overpass_outcome=nature_regional.get("_overpass_outcome")
        if isinstance(nature_regional, dict)
        else None,
    )

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
    if area_type in {"urban_core", "urban_residential", "urban_core_lowrise"}:
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
    conf_notes = _active_outdoors_confidence_notes(
        dq, parks, playgrounds, hiking_trails, swimming, camping
    )
    dq = {
        **dq,
        "confidence_notes": conf_notes,
        "overpass_local_outcome": local.get("_overpass_outcome")
        if isinstance(local, dict)
        else None,
        "overpass_trail_outcome": nature_trail.get("_overpass_outcome")
        if isinstance(nature_trail, dict)
        else None,
        "overpass_regional_outcome": nature_regional.get("_overpass_outcome")
        if isinstance(nature_regional, dict)
        else None,
        "places_ao": places_ao_meta,
    }

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
    # Vacation mountain trips: user declared this is a mountain destination, force mountain scoring
    # even when OSM trail data is sparse (Vail, Park City, Moab, Jackson all fail OSM detection)
    if trip_type == "mountain" and not is_mountain_town:
        is_mountain_town = True
        logger.info("🏔️ [AO v2] Forced is_mountain_town=True (trip_type=mountain)")
    # IMPORTANT: Pass scoring_area_type (not original area_type) so mountain town detection works
    # If Denver is detected as mountain town, scoring_area_type = "exurban", which enables higher expectations
    wild_score = _score_wild_adventure_v2(
        hiking_trails, camping, canopy_pct_5km, scoring_area_type, is_mountain_town=is_mountain_town
    )
    water_score, waterfront_breakdown = _score_water_lifestyle_v2(
        swimming, scoring_area_type, is_desert_context=is_desert_context
    )

    # 4) Final score: transparent component sum (30% + 50% + 20% of total points)
    total_raw = daily_score + wild_score + water_score
    calibrated_total = max(0.0, min(100.0, total_raw))
    cap = places_ao_meta.get("osm_down_score_cap")
    if places_ao_meta.get("degraded_osm_substitute") and cap is not None:
        calibrated_total = min(calibrated_total, float(cap))

    logger.info(
        f"🔍 [ACTIVE OUTDOORS V2 FINAL] daily={daily_score:.2f}, wild={wild_score:.2f}, water={water_score:.2f}, "
        f"final={calibrated_total:.2f}",
        extra={
            "pillar_name": "active_outdoors_v2",
            "daily_score": daily_score,
            "wild_score": wild_score,
            "water_score": water_score,
            "calibrated_total": calibrated_total
        }
    )

    breakdown: Dict = {
        "score": round(calibrated_total, 1),
        "breakdown": {
            "daily_urban_outdoors": round(daily_score, 1),
            "wild_adventure": round(wild_score, 1),
            "waterfront_lifestyle": round(water_score, 1),
            "waterfront_breakdown": waterfront_breakdown,
        },
        "summary": {
            **_build_summary_v2(
                parks, playgrounds, hiking_trails, swimming, camping, canopy_pct_5km
            ),
            "overpass": {
                "local": local.get("_overpass_outcome")
                if isinstance(local, dict)
                else None,
                "trail": nature_trail.get("_overpass_outcome")
                if isinstance(nature_trail, dict)
                else None,
                "regional": nature_regional.get("_overpass_outcome")
                if isinstance(nature_regional, dict)
                else None,
            },
            "places_ao": places_ao_meta,
        },
        "data_quality": dq,
        "confidence_notes": conf_notes,
        "area_classification": area_metadata,
        "debug": {
            "parks_query": (local.get("_debug_parks") if isinstance(local, dict) else None),
            "overpass_stagger_s": _OVERPASS_STAGGER_S,
            "places_ao": places_ao_meta,
        },
        "version": "active_outdoors_v2_component_sum",
        "scoring_method": "weighted_component_sum",
        "component_weights": {
            "daily_urban_outdoors": 35,
            "wild_adventure": 50,
            "waterfront_lifestyle": 25,
            "budget_total": 110,
            "budget_cap": 100,
            "note": "Point budgets (max per component). Budget sums to 110; final score capped at 100.",
        },
        "context": {
            "area_type_for_scoring": scoring_area_type,
            "is_mountain_town": context_flags.get("is_mountain_town"),
            "is_desert_context": context_flags.get("is_desert_context"),
            "trail_stats": context_flags.get("trail_stats"),
        },
    }

    logger.info(
        f"✅ Active Outdoors v2 (data-backed): {calibrated_total:.1f}/100 "
        f"(daily={daily_score:.1f}, wild={wild_score:.1f}, water={water_score:.1f})",
        extra={
            "pillar_name": "active_outdoors_v2",
            "lat": lat,
            "lon": lon,
            "area_type": area_type,
            "total_score": calibrated_total,
            "daily_score": daily_score,
            "wild_score": wild_score,
            "water_score": water_score,
            "scoring_method": "weighted_component_sum",
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
    Daily Urban Outdoors (0-35):
      - Park count density vs area-type expectation  (access breadth, 0-22)
      - Nearest meaningful park proximity (>=0.5 ha) (access quality, 0-8)
      - Playground count                             (0-5)
      - Recreational facilities                      (0-3, cap total at 35)

    Total area is intentionally excluded: at the query radius used, area is
    dominated by anchor parks (Prospect Park, Central Park) that measure
    adjacency not daily walkable access. Count + proximity are the right signals.

    Budget raised 30->35 to match new 35+40+25=100 component totals.
    """
    park_count = len(parks)
    playground_count = len(playgrounds)
    facility_count = len(recreational_facilities)

    exp_expectations = expectations or {}
    # Floor at 1 so _sat_ratio_v2 never divides by zero — rural has expected=0 for 1km
    # but the query radius for rural is 2000m so parks exist; expect at least 1.
    exp_park_count = max(1.0, exp_expectations.get("expected_parks_within_1km", 8.0))
    exp_play = max(1.0, exp_expectations.get("expected_playgrounds_within_1km", 2.0))
    exp_facilities = max(1.0, exp_expectations.get("expected_recreational_facilities_within_1km", 3.0))

    # 1. Park count density (0-22)
    s_count = _sat_ratio_v2(park_count, exp_park_count, 22.0)

    # 2. Nearest meaningful park proximity (0-8)
    #    Full score <=300m, decays to ~half at 800m, ~20% at 1500m.
    MIN_MEANINGFUL_HA = 0.5
    meaningful_distances = [
        p.get("distance_m", 1e9)
        for p in parks
        if (p.get("area_sqm") or 0.0) / 10_000.0 >= MIN_MEANINGFUL_HA
    ]
    if meaningful_distances:
        nearest_m = min(meaningful_distances)
        s_nearest = 8.0 * math.exp(-0.0012 * nearest_m)
    else:
        s_nearest = 0.0

    # 3. Playgrounds (0-5)
    s_play = _sat_ratio_v2(playground_count, exp_play, 5.0)

    # 4. Recreational facilities (0-3)
    s_facilities = _sat_ratio_v2(facility_count, exp_facilities, 3.0)

    final_score = min(35.0, s_count + s_nearest + s_play + s_facilities)

    logger.info(
        f"[DAILY URBAN OUTDOORS] area_type={area_type} parks={park_count} "
        f"s_count={s_count:.1f} s_nearest={s_nearest:.1f} s_play={s_play:.1f} "
        f"s_fac={s_facilities:.1f} -> {final_score:.1f}/35",
        extra={"pillar_name": "active_outdoors_v2", "area_type": area_type,
               "park_count": park_count, "s_count": s_count, "s_nearest": s_nearest,
               "s_play": s_play, "s_facilities": s_facilities, "final_score": final_score}
    )
    return final_score
def _score_wild_adventure_v2(
    hiking_trails: list,
    camping: list,
    canopy_pct_5km: float,
    area_type: str,
    is_mountain_town: bool = False,
) -> float:
    """
    Wild Adventure Backbone (0-50):
      - Trail richness: total count within 15km  (calibrated by area type)
      - Trail proximity: count within 5km        (calibrated by area type)
      - Wild/forested context (tree canopy)      (differentiates forest vs scrub trails)
      - Camping access                           (proximity decay)

    Canopy is intentionally kept here even though Natural Beauty also uses it:
    a forested trail network (Catskills, Adirondacks) should score higher than
    a scrubby desert trail network with the same trail count. Canopy captures
    the quality of the outdoor recreation environment, not just scenery.
    """
    trail_count = len(hiking_trails)
    near_trails = [t for t in hiking_trails if t.get("distance_m", 1e9) <= 5000]
    near_count = len(near_trails)

    baseline_context = get_baseline_context(
        area_type=area_type,
        form_context=None,
        pillar_name="active_outdoors"
    )
    expectations = get_contextual_expectations(baseline_context, "active_outdoors") or {}
    exp_trails_15km = expectations.get("expected_trails_within_15km", 2.0)

    if baseline_context == "urban_core":
        exp_trails = max(2.0, exp_trails_15km)
        exp_near = 8.0
        exp_canopy = 35.0
        max_trails_total, max_trails_near, max_canopy = 12.0, 6.0, 15.0
    elif baseline_context == "suburban":
        if is_mountain_town:
            exp_trails = max(5.0, exp_trails_15km)
            exp_near = 15.0
            exp_canopy = 45.0
            max_trails_total, max_trails_near, max_canopy = 35.0, 20.0, 18.0
        else:
            exp_trails = max(5.0, exp_trails_15km)
            exp_near = 6.0
            exp_canopy = 30.0
            max_trails_total, max_trails_near, max_canopy = 25.0, 12.0, 18.0
    else:  # rural / exurban
        if is_mountain_town:
            exp_trails = max(5.0, exp_trails_15km)
            exp_near = 15.0
            exp_canopy = 45.0
            max_trails_total, max_trails_near, max_canopy = 35.0, 20.0, 18.0
        else:
            exp_trails = max(1.0, exp_trails_15km)
            exp_near = 15.0
            exp_canopy = 45.0
            max_trails_total, max_trails_near, max_canopy = 30.0, 15.0, 15.0

    # Urban data quality cap: OSM tags many urban paths as hiking routes
    if baseline_context == "urban_core":
        capped_trail_count = min(trail_count, exp_trails * 15.0)
        capped_near_count = min(near_count, exp_near * 2.5)
    else:
        capped_trail_count = trail_count
        capped_near_count = near_count

    s_trails_total = _sat_ratio_v2(capped_trail_count, exp_trails, max_trails_total)
    s_trails_near = _sat_ratio_v2(capped_near_count, exp_near, max_trails_near)
    s_canopy = _sat_ratio_v2(canopy_pct_5km, exp_canopy, max_canopy)

    # Camping proximity
    if not camping:
        s_camp = 0.0
    else:
        nearest = min(camping, key=lambda c: c.get("distance_m", 1e9))
        d = nearest.get("distance_m", 1e9)
        if area_type in {"urban_core"}:
            if d <= 15_000:
                s_camp = 8.0
            else:
                s_camp = 8.0 * math.exp(-0.0001 * (d - 15_000))
        elif area_type in {"suburban", "urban_residential", "urban_core_lowrise"}:
            if d <= 20_000:
                s_camp = 10.0
            else:
                s_camp = 10.0 * math.exp(-0.00008 * (d - 20_000))
        else:
            if d <= 25_000:
                s_camp = 10.0
            else:
                s_camp = 10.0 * math.exp(-0.00005 * (d - 25_000))

    total_wild = s_trails_total + s_trails_near + s_canopy + s_camp
    final_wild = max(0.0, min(50.0, total_wild))

    logger.info(
        f"[WILD ADVENTURE] area_type={area_type} is_mt={is_mountain_town} "
        f"trails={capped_trail_count} near={capped_near_count} canopy={canopy_pct_5km:.1f}% "
        f"s_tot={s_trails_total:.1f} s_near={s_trails_near:.1f} s_can={s_canopy:.1f} s_camp={s_camp:.1f} -> {final_wild:.1f}/50",
        extra={"pillar_name": "active_outdoors_v2", "area_type": area_type,
               "trail_count": trail_count, "near_count": near_count,
               "s_trails_total": s_trails_total, "s_trails_near": s_trails_near,
               "s_canopy": s_canopy, "s_camp": s_camp, "final_wild": final_wild}
    )
    return final_wild


_WATERFRONT_CATEGORY: Dict[str, str] = {
    "beach": "ocean_beach",
    "coastline": "ocean_beach",
    "coastline_rocky": "ocean_beach",
    "lake": "lake_river",
    "swimming_area": "lake_river",
    "bay": "bay_harbor",
}
_WATERFRONT_BASE: Dict[str, float] = {
    "beach": 25.0,
    "swimming_area": 22.0,
    "lake": 22.0,
    "coastline": 15.0,
    "coastline_rocky": 10.0,
    "bay": 12.0,
}


def _score_water_lifestyle_v2(
    swimming: list, area_type: str, is_desert_context: bool = False
) -> Tuple[float, Dict]:
    """
    Waterfront Lifestyle (0-25):
      Score the BEST water feature by its computed score, not just the nearest.
      A distant ocean beach beats a nearby ornamental pond.

    Returns (score, waterfront_breakdown) where waterfront_breakdown contains
    per-category best scores normalized to 0-100 for preference reweighting.
    Categories: ocean_beach (beach/coastline), lake_river (lake/swimming_area), bay_harbor (bay).
    """
    _empty_breakdown: Dict = {"ocean_beach": 0.0, "lake_river": 0.0, "bay_harbor": 0.0}
    if not swimming:
        return 0.0, _empty_breakdown

    # natural=beach is ambiguous — ocean beaches and inland park beaches share the tag.
    # natural=coastline is the unambiguous OSM ocean signal. Confirm each beach individually:
    # the nearest coastline must be within 3km of that beach's own distance from the scoring
    # center. This keeps the check local to each feature rather than global — a coastline
    # that is far from all local beaches cannot contaminate their classification even if it
    # falls within the regional query radius. The 3km tolerance covers OSM geometry offsets
    # without conflating beaches and coastlines that belong to different water bodies.
    min_coastline_dist = min(
        (f.get("distance_m", 1e9) for f in swimming
         if f.get("type") in ("coastline", "coastline_rocky")),
        default=1e9,
    )

    def _beach_is_ocean(beach_dist: float) -> bool:
        return min_coastline_dist <= beach_dist + 3_000

    def feature_score(feat: Dict) -> float:
        d = feat.get("distance_m", 1e9)
        t = feat.get("type")
        base = _WATERFRONT_BASE.get(t, 10.0)

        # Inland park beach: downgrade to swimming_area level (no ocean confirmation)
        if t == "beach" and not _beach_is_ocean(d):
            base = _WATERFRONT_BASE["swimming_area"]

        # Context downweights
        if area_type in {"urban_core"} and t not in {"beach"}:
            base *= 0.4
        elif area_type in {"suburban", "urban_residential"} and t not in {"beach", "lake"}:
            base *= 0.9

        if is_desert_context:
            if t not in {"beach", "lake"}:
                base *= 0.3
            else:
                base *= 0.6

        # Distance decay: full score <=3km, exponential beyond
        if d > 3_000:
            base *= math.exp(-0.00025 * (d - 3_000))

        return base

    def _feat_category(feat: Dict) -> str:
        t = feat.get("type", "")
        if t == "beach":
            return "ocean_beach" if _beach_is_ocean(feat.get("distance_m", 1e9)) else "lake_river"
        return _WATERFRONT_CATEGORY.get(t, "lake_river")

    category_best: Dict[str, float] = {"ocean_beach": 0.0, "lake_river": 0.0, "bay_harbor": 0.0}
    all_feature_scores = []
    for feat in swimming:
        s = feature_score(feat)
        all_feature_scores.append(s)
        cat = _feat_category(feat)
        if s > category_best[cat]:
            category_best[cat] = s

    best_score = max(all_feature_scores)
    final_water = max(0.0, min(25.0, best_score))

    # Normalize each category to 0-100 (budget cap is 25)
    waterfront_breakdown: Dict = {
        cat: round(min(100.0, v / 25.0 * 100.0), 1)
        for cat, v in category_best.items()
    }

    logger.info(
        f"[WATERFRONT LIFESTYLE] area_type={area_type} desert={is_desert_context} "
        f"features={len(swimming)} -> {final_water:.1f}/25 "
        f"breakdown={waterfront_breakdown}",
        extra={"pillar_name": "active_outdoors_v2", "area_type": area_type,
               "swimming_count": len(swimming), "final_water": final_water,
               "waterfront_breakdown": waterfront_breakdown}
    )
    return final_water, waterfront_breakdown


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
    is_dense_urban = area_type_lower in {"urban_core", "urban_residential", "urban_core_lowrise"}
    
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
            # Times Square example: 102 trails, 8.9% canopy → should NOT be detected
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
        # Moderate trail count (30-39): canopy check prevents false positives.
        # Denver: 36 trails, 8.2% canopy → qualifies.
        if canopy_pct >= 8.0:
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
    # RESEARCH-BACKED: Only override dense urban areas to exurban when mountain town detected
    # Suburban areas should stay suburban even with excellent trail access
    # Example: Larchmont, NY is suburban with 85 trails - should use suburban expectations
    # The mountain_town flag will still adjust expectations appropriately in _score_wild_adventure_v2
    if is_mountain_town and area_type_lower in {
        "urban_core",
        "urban_residential",
        "urban_core_lowrise",
        # REMOVED: "suburban", "suburban_major_metro" - keep suburban classification accurate
        # Suburban areas with excellent trail access are still suburban, not exurban
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


def get_active_outdoors_score(
    lat: float,
    lon: float,
    city: Optional[str] = None,
    area_type: Optional[str] = None,
    location_scope: Optional[str] = None,
) -> Tuple[float, Dict]:
    """Backward-compatible alias; legacy v1 implementation removed — delegates to v2."""
    return get_active_outdoors_score_v2(
        lat, lon, city=city, area_type=area_type, location_scope=location_scope
    )