"""
Walkable Town Pillar
Scores local indie business districts for walkability and variety
"""

from typing import Dict, Tuple, List
from data_sources import osm_api, data_quality


def get_walkable_town_score(lat: float, lon: float) -> Tuple[float, Dict]:
    """
    Calculate walkable town score (0-100) based on indie businesses.

    Rewards dense, diverse downtowns with:
    - Density (0-40): Total count of indie businesses
    - Variety (0-30): Balance across 4 categories (EQUAL WEIGHTS)
    - Proximity (0-30): How close is the downtown cluster

    Returns:
        (total_score, detailed_breakdown)
    """
    print(f"🏘️  Analyzing walkable downtown within 1km...")

    # Get businesses from OSM
    business_data = osm_api.query_local_businesses(lat, lon, radius_m=1000)

    if business_data is None:
        print("⚠️  OSM business data unavailable")
        return 0, _empty_breakdown()

    tier1 = business_data["tier1_daily"]
    tier2 = business_data["tier2_social"]
    tier3 = business_data["tier3_culture"]
    tier4 = business_data["tier4_services"]

    all_businesses = tier1 + tier2 + tier3 + tier4

    if not all_businesses:
        print("⚠️  No indie businesses found")
        return 0, _empty_breakdown()

    # Score components
    density_score = _score_density(all_businesses)
    variety_score = _score_variety(tier1, tier2, tier3, tier4)
    proximity_score = _score_proximity(all_businesses)

    total_score = density_score + variety_score + proximity_score

    # Assess data quality
    combined_data = {
        'business_data': business_data,
        'all_businesses': all_businesses,
        'total_score': total_score
    }
    
    # Detect actual area type for data quality assessment
    from data_sources import census_api
    density = census_api.get_population_density(lat, lon)
    area_type = data_quality.detect_area_type(lat, lon, density)
    quality_metrics = data_quality.assess_pillar_data_quality('walkable_town', combined_data, lat, lon, area_type)

    # Build response
    breakdown = {
        "score": round(total_score, 1),
        "breakdown": {
            "density": round(density_score, 1),
            "variety": round(variety_score, 1),
            "proximity": round(proximity_score, 1)
        },
        "summary": _build_summary(tier1, tier2, tier3, tier4, all_businesses),
        "data_quality": quality_metrics
    }

    # Log results
    print(f"✅ Walkable Town Score: {total_score:.0f}/100")
    print(
        f"   🏙️  Density: {density_score:.0f}/40 ({len(all_businesses)} businesses)")
    print(f"   🎨 Variety: {variety_score:.0f}/30")
    print(f"   🚶 Proximity: {proximity_score:.0f}/30")
    print(f"   📊 Data Quality: {quality_metrics['quality_tier']} ({quality_metrics['confidence']}% confidence)")

    return round(total_score, 1), breakdown


def _score_density(businesses: List[Dict]) -> float:
    """
    Score business density (0-40 points).
    Rewards areas with lots of indie businesses.
    """
    count = len(businesses)

    if count >= 50:
        return 40.0
    elif count >= 40:
        return 38.0
    elif count >= 30:
        return 35.0
    elif count >= 20:
        return 30.0
    elif count >= 15:
        return 25.0
    elif count >= 10:
        return 20.0
    elif count >= 5:
        return 12.0
    else:
        return count * 2  # 2 pts each for < 5


def _score_variety(tier1: List, tier2: List, tier3: List, tier4: List) -> float:
    """
    Score business variety (0-30 points).
    Rewards balanced mix across all 4 categories with EQUAL WEIGHTS.

    Each category worth 7.5 pts if it has 2+ types present:
    - Daily Essentials (cafe, bakery, grocery)
    - Social & Dining (restaurant, bar, ice cream)
    - Culture & Leisure (bookstore, gallery, theater, museum, market)
    - Services & Retail (boutique, salon, records, fitness, garden)
    """
    score = 0

    # Category 1: Daily Essentials (7.5 pts if 2+ types)
    tier1_types = set(b["type"] for b in tier1)
    tier1_variety = len(tier1_types)
    if tier1_variety >= 2:
        score += 7.5
    elif tier1_variety == 1:
        score += 3.75

    # Category 2: Social & Dining (7.5 pts if 2+ types)
    tier2_types = set(b["type"] for b in tier2)
    tier2_variety = len(tier2_types)
    if tier2_variety >= 2:
        score += 7.5
    elif tier2_variety == 1:
        score += 3.75

    # Category 3: Culture & Leisure (7.5 pts if 2+ types)
    tier3_types = set(b["type"] for b in tier3)
    tier3_variety = len(tier3_types)
    if tier3_variety >= 2:
        score += 7.5
    elif tier3_variety == 1:
        score += 3.75

    # Category 4: Services & Retail (7.5 pts if 2+ types)
    tier4_types = set(b["type"] for b in tier4)
    tier4_variety = len(tier4_types)
    if tier4_variety >= 2:
        score += 7.5
    elif tier4_variety == 1:
        score += 3.75

    return score


def _score_proximity(businesses: List[Dict]) -> float:
    """
    Score proximity to downtown (0-30 points).
    Rewards living close to the business cluster.
    """
    if not businesses:
        return 0.0

    # Find the median distance (center of the cluster)
    distances = sorted([b["distance_m"] for b in businesses])
    median_idx = len(distances) // 2
    median_distance = distances[median_idx]

    # Score based on how close you are to the cluster
    if median_distance <= 200:
        return 30.0  # Right in the downtown
    elif median_distance <= 400:
        return 28.0  # 5 min walk
    elif median_distance <= 600:
        return 25.0  # 7 min walk
    elif median_distance <= 800:
        return 20.0  # 10 min walk
    elif median_distance <= 1000:
        return 15.0  # Edge of walking distance
    else:
        return 5.0   # Too far


def _build_summary(tier1: List, tier2: List, tier3: List, tier4: List, all_businesses: List) -> Dict:
    """Build summary of walkable downtown characteristics."""

    # Get closest business
    closest = min(all_businesses,
                  key=lambda x: x["distance_m"]) if all_businesses else None

    # Count unique types in each tier
    tier1_types = list(set(b["type"] for b in tier1))
    tier2_types = list(set(b["type"] for b in tier2))
    tier3_types = list(set(b["type"] for b in tier3))
    tier4_types = list(set(b["type"] for b in tier4))

    # Calculate median distance (represents downtown center)
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
        "within_10min_walk": len([b for b in all_businesses if b["distance_m"] <= 800])
    }


def _empty_breakdown() -> Dict:
    """Return empty breakdown when no data."""
    return {
        "score": 0,
        "breakdown": {
            "density": 0,
            "variety": 0,
            "proximity": 0
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
            "within_10min_walk": 0
        }
    }