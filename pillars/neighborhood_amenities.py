"""
Neighborhood Amenities Pillar
Scores local indie business districts for walkability and variety

New Approach (2025):
- Home Walkability (0-60): What can I walk to from my front door?
- Location Quality (0-40): Am I in a vibrant, walkable location?
"""

from typing import Dict, Tuple, List, Optional
from data_sources import osm_api, data_quality
import math
from data_sources.radius_profiles import get_radius_profile
from data_sources.utils import haversine_distance


def get_neighborhood_amenities_score(lat: float, lon: float, include_chains: bool = False, 
                                     location_scope: Optional[str] = None,
                                     area_type: Optional[str] = None) -> Tuple[float, Dict]:
    """
    Calculate neighborhood amenities score (0-100) using dual scoring:
    
    - Home Walkability (0-60): What can I walk to from my address?
    - Location Quality (0-40): Am I in a vibrant town with a good downtown?
    
    Args:
        include_chains: If True, include chain/franchise businesses
        
    Returns:
        (total_score, detailed_breakdown)
    """
    print(f"🍽️  Analyzing neighborhood amenities and walkability...")
    
    # Query businesses with centralized radius profile
    profile = get_radius_profile('neighborhood_amenities', area_type, location_scope)
    query_radius = int(profile.get('query_radius_m', 1500))
    print(f"   🔧 Radius profile (amenities): area_type={area_type}, scope={location_scope}, query_radius={query_radius}m")
    business_data = osm_api.query_local_businesses(lat, lon, radius_m=query_radius, include_chains=include_chains)
    
    if business_data is None:
        print("⚠️  OSM business data unavailable")
        return 0, _empty_breakdown()
    
    tier1_all = business_data["tier1_daily"]
    tier2_all = business_data["tier2_social"]
    tier3_all = business_data["tier3_culture"]
    tier4_all = business_data["tier4_services"]
    all_businesses = tier1_all + tier2_all + tier3_all + tier4_all
    
    if not all_businesses:
        print("⚠️  No indie businesses found")
        return 0, _empty_breakdown()
    
    # Step 1: Home Walkability (0-60) - What's within walkable distance?
    profile = get_radius_profile('neighborhood_amenities', area_type, location_scope)
    walkable_distance = int(profile.get('walkable_distance_m', 1000))
    print(f"   🔧 Walkability window (amenities): walkable={walkable_distance}m")
    nearby = [b for b in all_businesses if b["distance_m"] <= walkable_distance]
    
    # Ensure area_type is detected if not provided (needed for context-aware scoring)
    from data_sources import census_api, data_quality
    if area_type is None:
        density = census_api.get_population_density(lat, lon)
        area_type = data_quality.detect_area_type(lat, lon, density)
    
    tier1_near = [b for b in tier1_all if b["distance_m"] <= walkable_distance]
    tier2_near = [b for b in tier2_all if b["distance_m"] <= walkable_distance]
    tier3_near = [b for b in tier3_all if b["distance_m"] <= walkable_distance]
    tier4_near = [b for b in tier4_all if b["distance_m"] <= walkable_distance]
    
    # Pass area_type to scoring functions for context-aware adjustments
    density_score = _score_density(nearby, max_points=25, area_type=area_type)
    variety_score = _score_variety(tier1_near, tier2_near, tier3_near, tier4_near, max_points=20)
    proximity_score = _score_proximity(nearby, max_points=15, area_type=area_type)
    
    home_score = density_score + variety_score + proximity_score  # 0-60
    
    # Step 2: Location Quality (0-40) - Is there a vibrant town nearby?
    location_score = _score_location_quality(all_businesses, lat, lon, max_points=40, area_type=area_type)
    
    # Raw total (before calibration)
    raw_total = home_score + location_score  # 0-100
    
    # Global linear calibration: map raw_total → 0-100 target scale
    # Calibration parameters fitted from Round 1 test panel (with OLD thresholds)
    # TODO: After testing with tightened location_quality thresholds, refit calibration
    #       using new raw scores from the test panel
    # Note: If v2 internals change, refit calibration
    CAL_A = 0.193
    CAL_B = 68.087
    calibrated_total = CAL_A * raw_total + CAL_B
    calibrated_total = max(0.0, min(100.0, calibrated_total))
    
    # Final score (calibrated)
    total_score = calibrated_total
    
    # Assess data quality
    combined_data = {
        'business_data': business_data,
        'all_businesses': all_businesses,
        'home_score': home_score,
        'location_score': location_score,
        'total_score': total_score
    }
    
    # Assess data quality (re-use area_type if already detected)
    density = census_api.get_population_density(lat, lon) or 0.0
    if area_type is None:  # Only detect if not already set
        area_type = data_quality.detect_area_type(lat, lon, density)
    quality_metrics = data_quality.assess_pillar_data_quality('neighborhood_amenities', combined_data, lat, lon, area_type)
    
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
                "businesses_within_1km": len(nearby)
            },
            "location_quality": round(location_score, 1)
        },
        "summary": _build_summary(tier1_all, tier2_all, tier3_all, tier4_all, all_businesses, home_score, location_score),
        "data_quality": quality_metrics,
        "version": "neighborhood_amenities_v2_calibrated",
        "raw_total": round(raw_total, 1),
        "calibration": {"a": CAL_A, "b": CAL_B},
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
        }
    }
    
    # Log results
    print(f"✅ Neighborhood Amenities v2 (calibrated): {total_score:.1f}/100 [raw={raw_total:.1f}]")
    print(f"   🏠 Home Walkability: {home_score:.1f}/60 ({len(nearby)} businesses within walkable)")
    print(f"   🌆 Location Quality: {location_score:.1f}/40")
    print(f"   📊 Data Quality: {quality_metrics['quality_tier']} ({quality_metrics['confidence']}% confidence)")
    
    return round(total_score, 1), breakdown


def _score_density(businesses: List[Dict], max_points: float = 25, 
                   area_type: Optional[str] = None) -> float:
    """
    Score business density with adjustable max and context-aware thresholds.
    
    Uses contextual expectations to adjust thresholds by area type:
    - Urban core: Higher expectations (60+ for excellent)
    - Suburban: Base expectations (50+ for excellent)
    - Exurban/Rural: Lower expectations (35+ for excellent)
    """
    count = len(businesses)
    scale = max_points / 25  # Adjusted for 25 max points (was 40)
    
    # Context-aware thresholds based on research
    # Research: 50+ excellent, 30+ good, 15+ adequate
    # Adjust for area type: urban needs 20% more, small towns 30% less
    if area_type == "urban_core":
        excellent_threshold = 60  # 20% higher than base 50
        good_threshold = 36       # 20% higher than base 30
        adequate_threshold = 18    # 20% higher than base 15
    elif area_type in ["exurban", "rural"]:
        excellent_threshold = 35   # 30% lower than base 50
        good_threshold = 21        # 30% lower than base 30
        adequate_threshold = 11    # 30% lower than base 15
    else:  # suburban (baseline)
        excellent_threshold = 50
        good_threshold = 30
        adequate_threshold = 15
    
    # Score with context-aware thresholds
    if count >= excellent_threshold:
        return 25.0 * scale  # Excellent
    elif count >= 40:  # NEW: Add explicit 40-business tier
        return 24.0 * scale  # Very good (between 30 and 50)
    elif count >= good_threshold:
        return 20.0 * scale  # Good
    elif count >= 20:
        return 15.0 * scale
    elif count >= adequate_threshold:
        return 12.0 * scale  # Adequate
    elif count >= 10:
        return 10.0 * scale
    elif count >= 5:
        return 6.0 * scale
    else:
        return count * 1.2 * scale


def _score_variety(tier1: List, tier2: List, tier3: List, tier4: List, max_points: float = 30) -> float:
    """Score business variety with adjustable max points."""
    score = 0
    
    # Scale points based on max
    tier1_pts = max_points * 0.4  # Daily Essentials: 40%
    tier2_pts = max_points * 0.33  # Social & Dining: 33%
    tier3_pts = max_points * 0.17  # Culture: 17%
    tier4_pts = max_points * 0.10  # Services: 10%
    
    # Tier 1: Daily Essentials
    tier1_types = set(b["type"] for b in tier1)
    tier1_variety = len(tier1_types)
    if tier1_variety >= 3:
        score += tier1_pts
    elif tier1_variety >= 2:
        score += tier1_pts * 0.67
    elif tier1_variety >= 1:
        score += tier1_pts * 0.33
    
    # Tier 2: Social & Dining
    tier2_types = set(b["type"] for b in tier2)
    tier2_variety = len(tier2_types)
    if tier2_variety >= 2:
        score += tier2_pts
    elif tier2_variety >= 1:
        score += tier2_pts * 0.6
    
    # Tier 3: Culture & Leisure
    tier3_types = set(b["type"] for b in tier3)
    tier3_variety = len(tier3_types)
    if tier3_variety >= 2:
        score += tier3_pts
    elif tier3_variety >= 1:
        score += tier3_pts * 0.6
    
    # Tier 4: Services & Retail
    tier4_types = set(b["type"] for b in tier4)
    tier4_variety = len(tier4_types)
    if tier4_variety >= 2:
        score += tier4_pts
    elif tier4_variety >= 1:
        score += tier4_pts * 0.33
    
    return score


def _score_proximity(businesses: List[Dict], max_points: float = 15, area_type: Optional[str] = None) -> float:
    """
    Score proximity to downtown cluster with area-type aware thresholds.
    
    Research-backed thresholds (adjusted for better discrimination):
    - ≤200m: Optimal (15 points)
    - ≤400m: Very Good (13 points)
    - ≤600m: Good (11 points)
    - ≤800m: Adequate (10 points) - less harsh for suburban/urban_residential
    - ≤1000m: Acceptable (7 points)
    - >1000m: Poor (2.5 points)
    """
    if not businesses:
        return 0.0
    
    distances = sorted([b["distance_m"] for b in businesses])
    median_idx = len(distances) // 2
    median_distance = distances[median_idx]
    
    scale = max_points / 15  # Adjusted for 15 max points (was 30)
    
    # Slightly more lenient for suburban/urban_residential at 500-800m range
    # (addresses Lincoln Park type cases where businesses exist but are 500-600m away)
    if median_distance <= 200:
        return 15.0 * scale  # Optimal
    elif median_distance <= 400:
        return 13.0 * scale  # Very Good
    elif median_distance <= 600:
        # For suburban/urban_residential, treat 500-600m as still "good" if there are businesses
        if area_type in {"suburban", "urban_residential"} and len(businesses) >= 10:
            return 12.0 * scale  # Good (slightly higher)
        return 11.0 * scale  # Good
    elif median_distance <= 800:
        # For suburban/urban_residential, 600-800m is still "adequate" if there's a cluster
        if area_type in {"suburban", "urban_residential"} and len(businesses) >= 15:
            return 10.5 * scale  # Adequate (slightly higher)
        return 10.0 * scale  # Adequate
    elif median_distance <= 1000:
        return 7.0 * scale   # Acceptable
    else:
        return 2.5 * scale   # Poor


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
    
    # Context-aware vibrancy thresholds (tightened to reduce saturation)
    # Goal: Make it harder to max out location_quality at 40, especially for urban_core
    if area_type == "urban_core":
        vibrant_threshold = 100  # Urban: 100+ businesses for truly vibrant downtown (raised from 50)
        density_divisor = 12.5   # 100 businesses = 8 pts (100/12.5 = 8) - much harder to max
    elif area_type in ["urban_residential"]:
        vibrant_threshold = 80   # Urban residential: 80+ businesses for vibrant downtown
        density_divisor = 10.0   # 80 businesses = 8 pts
    elif area_type in ["exurban", "rural"]:
        vibrant_threshold = 30   # Small towns: 30+ businesses for vibrant downtown (unchanged)
        density_divisor = 3.75   # 30 businesses = 8 pts (30/3.75 = 8)
    else:  # suburban (baseline)
        vibrant_threshold = 60   # Suburban: 60+ businesses for vibrant downtown (raised from 40)
        density_divisor = 7.5    # 60 businesses = 8 pts (60/7.5 = 8)
    
    # Density bonus (0-8) - context-aware, now harder to max
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


def _empty_breakdown() -> Dict:
    """Return empty breakdown when no data."""
    return {
        "score": 0,
        "breakdown": {
            "home_walkability": {"score": 0, "breakdown": {"density": 0, "variety": 0, "proximity": 0}, "businesses_within_1km": 0},
            "location_quality": 0
        },
        "summary": {
            "total_businesses": 0,
            "by_tier": {
                "daily_essentials": {"count": 0, "types": []},
                "social_dining": {"count": 0, "types": []},
                "culture_leisure": {"count": 0, "types": []},
                "services_retail": {"count": 0, "types": []}
            },
            "downtown_center_distance_m": 0,
            "closest_business": None,
            "within_5min_walk": 0,
            "within_10min_walk": 0,
            "score_breakdown": {
                "home_walkability": 0,
                "location_quality": 0
            }
        }
    }

