"""
Neighborhood Amenities Pillar
Scores local indie business districts for walkability and variety

New Approach (2025):
- Home Walkability (0-60): What can I walk to from my front door?
- Location Quality (0-40): Am I in a vibrant, walkable location?
"""

from typing import Dict, Tuple, List, Optional
from data_sources import osm_api, data_quality
from data_sources.data_quality import data_quality_manager
from data_sources.places_fallback_client import maybe_augment_business_data_with_places
import math
from data_sources.radius_profiles import get_radius_profile
from data_sources.utils import haversine_distance
from logging_config import get_logger

logger = get_logger(__name__)


def get_neighborhood_amenities_score(lat: float, lon: float, include_chains: bool = True,
                                     location_scope: Optional[str] = None,
                                     area_type: Optional[str] = None,
                                     density: Optional[float] = None,
                                     vacation_mode: bool = False,
                                     place_context=None) -> Tuple[float, Dict]:
    """
    Calculate neighborhood amenities score (0-100) using dual scoring:
    
    - Home Walkability (0-60): What can I walk to from my address?
    - Location Quality (0-40): Am I in a vibrant town with a good downtown?
    
    Args:
        include_chains: If True, include chain/franchise businesses
        
    Returns:
        (total_score, detailed_breakdown)
    """
    logger.debug("Analyzing neighborhood amenities and walkability")
    
    # Query businesses with centralized radius profile
    profile = get_radius_profile('neighborhood_amenities', area_type, location_scope)
    query_radius = int(profile.get('query_radius_m', 1500))
    if vacation_mode:
        query_radius = max(query_radius, 3000)
    logger.debug("Radius profile (amenities): area_type=%s, scope=%s, query_radius=%dm", area_type, location_scope, query_radius)
    # main.py already read OSM and ran the Google Places top-up once to settle the area type. Reuse that
    # list (trimmed to this pillar's radius) so the paid call is not made twice. Falls back to the pillar's
    # own read whenever the list cannot stand in for it (vacation mode, chain filter, failed OSM read).
    business_data = place_context.businesses_for_radius(query_radius, include_chains, vacation_mode) if place_context else None
    places_already_augmented = business_data is not None
    if business_data is None:
        business_data = osm_api.query_local_businesses(lat, lon, radius_m=query_radius, include_chains=include_chains, vacation_mode=vacation_mode)
    osm_query_failed = business_data is None
    if business_data is None:
        # Normalize so Google Places can still run (thin/empty OSM → searchNearby before imputed fallback).
        business_data = {
            "tier1_daily": [],
            "tier2_social": [],
            "tier3_culture": [],
            "tier4_services": [],
        }

    # Ensure area_type is detected early (needed for fallback scoring when OSM data unavailable)
    from data_sources import census_api
    if place_context is not None:
        area_type, density = place_context.area_type, place_context.density
    # Use pre-computed density if provided, otherwise fetch it
    if density is None:
        density = census_api.get_population_density(lat, lon)
    if area_type is None:
        area_type = data_quality.detect_area_type(lat, lon, density)

    tier1_all = business_data["tier1_daily"]
    tier2_all = business_data["tier2_social"]
    tier3_all = business_data["tier3_culture"]
    tier4_all = business_data["tier4_services"]
    all_businesses = tier1_all + tier2_all + tier3_all + tier4_all

    # Google Places (New): thin OSM *or* empty OSM / failed OSM query — try before imputed fallback.
    expected_minimums_pre = data_quality_manager.get_expected_minimums(lat, lon, area_type or "suburban", density=density)
    osm_completeness_pre, _ = data_quality_manager.assess_data_completeness(
        "neighborhood_amenities",
        {"all_businesses": all_businesses},
        expected_minimums_pre,
    )
    business_data, places_fallback_meta = maybe_augment_business_data_with_places(
        business_data,
        lat,
        lon,
        float(query_radius),
        include_chains,
        float(osm_completeness_pre),
        area_type=area_type,
        density=density,
        places_already_augmented=places_already_augmented,
    )
    if places_already_augmented and place_context is not None and place_context.places_meta:
        places_fallback_meta = dict(place_context.places_meta)
    tier1_all = business_data["tier1_daily"]
    tier2_all = business_data["tier2_social"]
    tier3_all = business_data["tier3_culture"]
    tier4_all = business_data["tier4_services"]
    all_businesses = tier1_all + tier2_all + tier3_all + tier4_all
    if places_fallback_meta.get("used"):
        logger.debug(
            "Places fallback: merged %d places (OSM completeness was %.2f)",
            places_fallback_meta.get("mapped_added", 0), osm_completeness_pre,
        )

    # Still empty after Places (or Places disabled / no API key).
    empty_walkable_area = False
    if not all_businesses:
        if osm_query_failed:
            # The lookup itself failed: that is a missing measurement, not a measured zero. Do not score.
            logger.warning("OSM business data unavailable")
            if area_type in ("urban_core", "urban_residential", "suburban") or (density and density > 1000):
                failure_reason = f"osm_unavailable ({area_type or 'density ' + str(round(density or 0))})"
            else:
                failure_reason = "osm_unavailable (non-urban area)"
            logger.warning("neighborhood_amenities returning None: %s", failure_reason)
            return None, {
                "score": None,
                "failed": True,
                "failure_reason": failure_reason,
                "confidence": 0,
                "data_quality_index": 0.0,
                "business_list": [],
                "breakdown": {},
                "summary": {},
                "data_quality": {"confidence": 0},
            }
        # Overpass answered and (after the Places fallback) there is still nothing: this place has no
        # businesses within walking range. That is a real, low result for a mover, so score it through
        # the normal curve (zero density, variety and proximity) instead of hiding it as "no data".
        logger.warning("neighborhood_amenities: no businesses within radius; scoring as an empty walkable area")
        empty_walkable_area = True

    # Step 1: Home Walkability (0-60) - What's within walkable distance?
    profile = get_radius_profile('neighborhood_amenities', area_type, location_scope)
    walkable_distance = int(profile.get('walkable_distance_m', 1000))
    logger.debug("Walkability window (amenities): walkable=%dm", walkable_distance)
    nearby = [b for b in all_businesses if b["distance_m"] <= walkable_distance]
    
    tier1_near = [b for b in tier1_all if b["distance_m"] <= walkable_distance]
    tier2_near = [b for b in tier2_all if b["distance_m"] <= walkable_distance]
    tier3_near = [b for b in tier3_all if b["distance_m"] <= walkable_distance]
    tier4_near = [b for b in tier4_all if b["distance_m"] <= walkable_distance]
    
    # v3 amenity-access model: measure walkable daily life on an absolute, log-scaled
    # density curve (so 50 businesses no longer maxes the score and 700 actually separates),
    # plus genuine breadth and a "milk-run" essentials-proximity term. Validated against
    # Walk Score (Pearson 0.90 vs old 0.80); fixes suburbs out-ranking dense urban cores.
    # All measured within an 800m / ~10-min walk, area-type-independent (absolute density
    # needs the classifier far less than the old peer-banded thresholds did).
    walk_m = min(walkable_distance, 2000) if vacation_mode else min(walkable_distance, 800)
    walk_biz = [b for b in all_businesses if b["distance_m"] <= walk_m]
    walk_t1 = [b for b in tier1_all if b["distance_m"] <= walk_m]
    walk_t2 = [b for b in tier2_all if b["distance_m"] <= walk_m]
    walk_t3 = [b for b in tier3_all if b["distance_m"] <= walk_m]
    walk_t4 = [b for b in tier4_all if b["distance_m"] <= walk_m]

    density_score = _score_walkable_density(walk_biz, max_points=50)        # 0-50
    variety_score = _score_walkable_variety(walk_t1, walk_t2, walk_t3, walk_t4, max_points=25)  # 0-25
    proximity_score = _score_essentials_proximity(all_businesses, max_points=25)  # 0-25, decays out to 1,200 m

    home_score = density_score + variety_score + proximity_score  # 0-100 (the full amenity-access score)

    # Town-center signal (0-40): adds to the score (0e2096e). Unsourced judgment; see
    # analysis/audit_amenities_2026-10-25.md.
    location_score = _score_location_quality(all_businesses, lat, lon, max_points=40, area_type=area_type)

    # Home walkability (0-60) + location quality (0-40) = 0-100.
    # Scaling home_score by 0.6 keeps genuine walkability as the dominant signal
    # while letting a real town center add meaningful points.
    raw_total = min(100.0, home_score * 0.6 + location_score)
    total_score = raw_total
    
    # Assess data quality
    combined_data = {
        'business_data': business_data,
        'all_businesses': all_businesses,
        'home_score': home_score,
        'location_score': location_score,
        'total_score': total_score
    }
    
    # Assess data quality (re-use area_type if already detected)
    if area_type is None:  # Only detect if not already set
        area_type = data_quality.detect_area_type(lat, lon, density or 0.0)
    combined_data["places_augmented"] = bool(places_fallback_meta.get("used"))
    quality_metrics = data_quality.assess_pillar_data_quality('neighborhood_amenities', combined_data, lat, lon, area_type, density=density)
    if places_fallback_meta.get("triggered") and places_fallback_meta.get("error"):
        quality_metrics = dict(quality_metrics)
        quality_metrics["degraded"] = True
        quality_metrics["degraded_reasons"] = list(quality_metrics.get("degraded_reasons") or []) + [
            f"places_fallback_failed ({places_fallback_meta.get('error')})"
        ]
    if empty_walkable_area:
        quality_metrics = dict(quality_metrics)
        quality_metrics["confidence"] = min(int(quality_metrics.get("confidence") or 0), 40)
        quality_metrics["data_warnings"] = list(quality_metrics.get("data_warnings") or []) + ["no_businesses_within_radius"]
    
    # Build response with enhanced breakdown
    breakdown = {
        "score": round(total_score, 1),
        "breakdown": {
            "home_walkability": {
                "score": round(home_score, 1),
                "breakdown": {
                    "density": round(density_score, 1),
                    "variety": round(variety_score, 1),
                    "proximity": round(proximity_score, 1)
                },
                "businesses_within_1km": len(nearby),
                "businesses_within_walk": len(walk_biz),
            },
            "location_quality": round(location_score, 1)
        },
        "summary": _build_summary(tier1_all, tier2_all, tier3_all, tier4_all, all_businesses, home_score, location_score),
        "data_source": "blended" if places_fallback_meta.get("used") else "osm",
        "places_fallback": places_fallback_meta,
        "data_quality": quality_metrics,
        "empty_walkable_area": empty_walkable_area,
        "pin_sensitivity": _pin_sensitivity(all_businesses, lat, lon, area_type, vacation_mode, walkable_distance),
        "limits": {"chains_included": include_chains, "osm_with_places_fallback": bool(places_fallback_meta.get("used"))},
        "version": "amenities_v3_1_decay_grocery_2026-10-26",
        "raw_total": round(raw_total, 1),
        "calibration": {"a": None, "b": None, "note": "Calibration removed - using pure data-backed scoring per design principles"},
        "diagnostics": {
            "total_businesses": len(all_businesses),
            "businesses_within_walkable": len(nearby),
            "businesses_within_400m": len([b for b in all_businesses if b["distance_m"] <= 400]),
            "businesses_within_800m": len([b for b in all_businesses if b["distance_m"] <= 800]),
            "median_distance_m": round(sorted([b["distance_m"] for b in all_businesses])[len(all_businesses) // 2] if all_businesses else 0, 0),
            "tier1_count": len(tier1_all),
            "tier2_count": len(tier2_all),
            "tier3_count": len(tier3_all),
            "tier4_count": len(tier4_all),
        },
        # For Status Signal (deduped OSM+Places; lat/lon/distance_m for merged-list luxury radius)
        "business_list": [
            {
                "name": b.get("name"),
                "lat": b.get("lat"),
                "lon": b.get("lon"),
                "distance_m": b.get("distance_m"),
                "type": b.get("type"),
                "shop": b.get("shop"),
                "leisure": b.get("leisure"),
                "amenity": b.get("amenity"),
                "tourism": b.get("tourism"),
                "office": b.get("office"),
                "sport": b.get("sport"),
                "healthcare": b.get("healthcare"),
                "source": b.get("source"),
            }
            for b in all_businesses
        ],
    }
    
    # Log results
    logger.debug(
        "Neighborhood Amenities v2: %.1f/100 [raw=%.1f] | walkability=%.1f/60 (%d biz) | location=%.1f/40 | dq=%s (%d%%)",
        total_score, raw_total, home_score, len(nearby), location_score,
        quality_metrics["quality_tier"], quality_metrics["confidence"],
    )
    
    return round(total_score, 1), breakdown


_T1_DAILY = {"cafe", "bakery", "grocery"}
_T2_SOCIAL = {"restaurant", "bar", "ice_cream"}
_T3_CULTURE = {"bookstore", "gallery", "theater", "museum", "market", "attraction", "landmark"}
_T4_SERVICES = {"boutique", "salon", "records", "fitness", "garden"}
# Convenience stores and greengrocers still count as businesses, but not for the grocery run: USDA's
# Food Access Research Atlas measures healthy-food access to supermarkets, supercenters and large grocers.
# A stored Places record with no subtype (shop None) is kept, since its type is unknown.
_NOT_A_GROCERY_RUN = {"convenience", "greengrocer"}
PROXIMITY_FULL_M = 400
PROXIMITY_ZERO_M = 1200


def _score_walkable_density(walk_biz: List[Dict], max_points: float = 50) -> float:
    """Absolute walkable-business count on a log curve anchored at 400 (so a dense urban
    core at 700+ separates from a suburban downtown at 40, and 50 no longer maxes out)."""
    n = len(walk_biz)
    if n <= 0:
        return 0.0
    return round(max_points * min(1.0, math.log(1 + n) / math.log(1 + 400)), 2)


def _score_walkable_variety(t1: List, t2: List, t3: List, t4: List, max_points: float = 25) -> float:
    """Breadth across categories, weighted toward daily essentials. Requires genuine variety
    to max (not just 3 types) — distinct types per tier, scaled to that tier's full points."""
    def distinct(items, types):
        return len(set(b["type"] for b in items if b.get("type") in types))
    pts = (
        min(10.0, distinct(t1, _T1_DAILY) / 3 * 10)
        + min(7.0, distinct(t2, _T2_SOCIAL) / 3 * 7)
        + min(5.0, distinct(t3, _T3_CULTURE) / 4 * 5)
        + min(3.0, distinct(t4, _T4_SERVICES) / 3 * 3)
    )
    return round(min(max_points, pts), 2)


def _score_essentials_proximity(walk_biz: List[Dict], max_points: float = 25) -> float:
    """The 'milk run': how close is the nearest grocery, cafe/bakery and restaurant/bar?
    Credit decays linearly from full at 400 m to zero at 1,200 m, so a car-dependent suburb whose grocery
    is a 1.2 km drive loses here even with a Main Street."""
    def nearest(types):
        ds = [b["distance_m"] for b in walk_biz if b.get("type") in types and b.get("distance_m") is not None
              and not (b.get("type") == "grocery" and b.get("shop") in _NOT_A_GROCERY_RUN)]
        return min(ds) if ds else None

    def prox(d):
        # Linear decay: full credit within 400 m (Walk Score's 5-minute full-credit point), zero at 1,200 m.
        # The shape and the 1,200 m end are judgment (Walk Score's curve is not public and ends at 30 minutes);
        # 1,200 m is the smallest query radius, so every place is measured out to the same distance.
        if d is None:
            return 0.0
        if d <= PROXIMITY_FULL_M:
            return 1.0
        if d >= PROXIMITY_ZERO_M:
            return 0.0
        return (PROXIMITY_ZERO_M - d) / (PROXIMITY_ZERO_M - PROXIMITY_FULL_M)

    groc = prox(nearest({"grocery"}))
    caf = prox(nearest({"cafe", "bakery"}))
    eat = prox(nearest({"restaurant", "bar"}))
    return round((groc * 0.45 + caf * 0.30 + eat * 0.25) * max_points, 2)


_PIN_SHIFT_M = 200


def _pin_sensitivity(all_businesses: List[Dict], lat: float, lon: float, area_type: Optional[str],
                     vacation_mode: bool, walkable_distance: int) -> Dict:
    """Score range when the pin moves 200 m north, south, east and west.

    Uses the businesses already fetched, so businesses beyond the query radius are not seen: the result is
    an estimate of how much the score depends on exactly where the pin sits, reported as confidence only.
    """
    if not all_businesses:
        return {"shift_m": _PIN_SHIFT_M, "min": None, "max": None, "range": None}
    walk_m = min(walkable_distance, 2000) if vacation_mode else min(walkable_distance, 800)
    scores = []
    for dn, de in ((_PIN_SHIFT_M, 0), (-_PIN_SHIFT_M, 0), (0, _PIN_SHIFT_M), (0, -_PIN_SHIFT_M)):
        nlat = lat + dn / 111320.0
        nlon = lon + de / (111320.0 * max(0.01, math.cos(math.radians(lat))))
        moved = [dict(b, distance_m=haversine_distance(nlat, nlon, b["lat"], b["lon"])) for b in all_businesses]
        near = [b for b in moved if b["distance_m"] <= walk_m]
        home = (_score_walkable_density(near, 50)
                + _score_walkable_variety(*[[b for b in near if b.get("type") in t]
                                            for t in (_T1_DAILY, _T2_SOCIAL, _T3_CULTURE, _T4_SERVICES)], max_points=25)
                + _score_essentials_proximity(moved, 25))
        scores.append(min(100.0, home * 0.6 + _score_location_quality(moved, nlat, nlon, 40, area_type)))
    lo, hi = min(scores), max(scores)
    return {"shift_m": _PIN_SHIFT_M, "min": round(lo, 1), "max": round(hi, 1), "range": round(hi - lo, 1)}


def _score_cultural_bonus(tier3_cluster: List[Dict]) -> float:
    """
    Bonus points for cultural amenities in downtown cluster.
    
    Research: Cultural venues strongly correlate with vibrancy and property values.
    Bonus rewards exceptional cultural offerings.
    
    Returns:
        0.0, 1.0, or 2.0 bonus points
    """
    cultural_count = len(tier3_cluster)
    if cultural_count >= 5:
        return 2.0  # +2 bonus for 5+ cultural venues
    elif cultural_count >= 3:
        return 1.0  # +1 bonus for 3-4 venues
    return 0.0


def _score_location_quality(all_businesses: List[Dict], lat: float, lon: float, 
                           max_points: float = 40, area_type: Optional[str] = None) -> float:
    """
    Score location quality (0-40): Is there a vibrant town center nearby?
    
    Components:
    - Proximity to town center (0-20): How close is the nearest vibrant cluster?
    - Town center vibrancy (0-20): How good is that cluster?
    """
    if not all_businesses:
        return 0.0
    
    # Find the town center (median location of businesses)
    median_lat = sorted([b["lat"] for b in all_businesses])[len(all_businesses) // 2]
    median_lon = sorted([b["lon"] for b in all_businesses])[len(all_businesses) // 2]
    
    # Check if this is a coherent cluster (not scattered businesses)
    cluster_distances = [haversine_distance(lat, lon, b["lat"], b["lon"]) for b in all_businesses[:min(10, len(all_businesses))]]
    avg_cluster_distance = sum(cluster_distances) / len(cluster_distances) if cluster_distances else 0
    
    # If businesses are too scattered, it's not a "town center"
    if avg_cluster_distance > 1500:
        return 0.0
    
    # Calculate distance to town center
    distance_to_center = haversine_distance(lat, lon, median_lat, median_lon)
    
    # Score proximity (0-20)
    if distance_to_center <= 400:
        proximity_pts = 20.0
    elif distance_to_center <= 800:
        proximity_pts = 15.0
    elif distance_to_center <= 1200:
        proximity_pts = 10.0
    elif distance_to_center <= 1600:
        proximity_pts = 5.0
    else:
        proximity_pts = 0.0
    
    # Score vibrancy of the cluster (0-20)
    # Count businesses in a 500m radius around the center
    cluster_businesses = [b for b in all_businesses 
                         if haversine_distance(median_lat, median_lon, b["lat"], b["lon"]) <= 500]
    
    # Calculate variety in cluster
    tier1_cluster = [b for b in cluster_businesses if b.get("type") in ["cafe", "bakery", "grocery"]]
    tier2_cluster = [b for b in cluster_businesses if b.get("type") in ["restaurant", "bar", "ice_cream"]]
    tier3_cluster = [b for b in cluster_businesses if b.get("type") in ["bookstore", "gallery", "theater", "museum"]]
    tier4_cluster = [b for b in cluster_businesses if b.get("type") in ["boutique", "salon", "records", "fitness", "garden"]]
    
    cluster_all = tier1_cluster + tier2_cluster + tier3_cluster + tier4_cluster
    
    tier1_count = len(set(b["type"] for b in tier1_cluster))
    tier2_count = len(set(b["type"] for b in tier2_cluster))
    tier3_count = len(set(b["type"] for b in tier3_cluster))
    tier4_count = len(set(b["type"] for b in tier4_cluster))
    
    # Score variety (0-20)
    variety_pts = 0
    
    # Daily essentials (6 pts)
    if tier1_count >= 3:
        variety_pts += 6
    elif tier1_count >= 2:
        variety_pts += 4
    elif tier1_count >= 1:
        variety_pts += 2
    
    # Social/Dining (6 pts)
    if tier2_count >= 2:
        variety_pts += 6
    elif tier2_count >= 1:
        variety_pts += 4
    
    # Culture (5 pts)
    if tier3_count >= 2:
        variety_pts += 5
    elif tier3_count >= 1:
        variety_pts += 3
    
    # Services (3 pts)
    if tier4_count >= 2:
        variety_pts += 3
    elif tier4_count >= 1:
        variety_pts += 1
    
    variety_pts = min(variety_pts, 20)  # Cap at 20
    
    # Cluster-density divisor by area type. Unsourced judgment (tracker D10): swapping all four for the
    # suburban value moves stored scores by a mean of -0.3 and at most 3.6 points.
    if area_type == "urban_core":
        density_divisor = 12.5
    elif area_type in ["urban_residential"]:
        density_divisor = 10.0
    elif area_type in ["exurban", "rural"]:
        density_divisor = 3.75
    else:  # suburban (baseline)
        density_divisor = 7.5

    # Density bonus (0-8)
    density_pts = min(8, len(cluster_all) / density_divisor)
    
    vibrancy_pts = variety_pts + density_pts
    vibrancy_pts = min(vibrancy_pts, 20)  # Cap at 20
    
    # Add cultural bonus for exceptional cultural offerings
    cultural_bonus = _score_cultural_bonus(tier3_cluster)
    vibrancy_pts = min(20, vibrancy_pts + cultural_bonus)  # Cap at 20 (bonus can push to 20)
    
    # Only give vibrancy points if within reasonable distance
    if distance_to_center > 1600:
        vibrancy_pts = 0
    
    # Total location quality
    location_score = proximity_pts + vibrancy_pts
    location_score = min(location_score, max_points)  # Cap at max_points
    
    return location_score


def _build_summary(tier1: List, tier2: List, tier3: List, tier4: List, all_businesses: List, 
                   home_score: float, location_score: float) -> Dict:
    """Build enhanced summary with home and location breakdown."""
    
    closest = min(all_businesses, key=lambda x: x["distance_m"]) if all_businesses else None
    
    tier1_types = list(set(b["type"] for b in tier1))
    tier2_types = list(set(b["type"] for b in tier2))
    tier3_types = list(set(b["type"] for b in tier3))
    tier4_types = list(set(b["type"] for b in tier4))
    
    distances = sorted([b["distance_m"] for b in all_businesses])
    median_distance = distances[len(distances) // 2] if distances else 0
    
    return {
        "total_businesses": len(all_businesses),
        "by_tier": {
            "daily_essentials": {
                "count": len(tier1),
                "types": tier1_types
            },
            "social_dining": {
                "count": len(tier2),
                "types": tier2_types
            },
            "culture_leisure": {
                "count": len(tier3),
                "types": tier3_types
            },
            "services_retail": {
                "count": len(tier4),
                "types": tier4_types
            }
        },
        "downtown_center_distance_m": round(median_distance, 0),
        "closest_business": {
            "name": closest["name"],
            "type": closest["type"],
            "distance_m": closest["distance_m"]
        } if closest else None,
        "within_5min_walk": len([b for b in all_businesses if b["distance_m"] <= 400]),
        "within_10min_walk": len([b for b in all_businesses if b["distance_m"] <= 800]),
        "score_breakdown": {
            "home_walkability": round(home_score, 1),
            "location_quality": round(location_score, 1)
        }
    }
