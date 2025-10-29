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


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points in meters."""
    R = 6371000  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    
    a = math.sin(delta_phi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    
    return R * c


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
    tier1_near = [b for b in tier1_all if b["distance_m"] <= walkable_distance]
    tier2_near = [b for b in tier2_all if b["distance_m"] <= walkable_distance]
    tier3_near = [b for b in tier3_all if b["distance_m"] <= walkable_distance]
    tier4_near = [b for b in tier4_all if b["distance_m"] <= walkable_distance]
    
    density_score = _score_density(nearby, max_points=25)  # Scaled to 25
    variety_score = _score_variety(tier1_near, tier2_near, tier3_near, tier4_near, max_points=20)
    proximity_score = _score_proximity(nearby, max_points=15)
    
    home_score = density_score + variety_score + proximity_score  # 0-60
    
    # Step 2: Location Quality (0-40) - Is there a vibrant town nearby?
    location_score = _score_location_quality(all_businesses, lat, lon, max_points=40)
    
    # Final score
    total_score = home_score + location_score  # 0-100
    
    # Assess data quality
    combined_data = {
        'business_data': business_data,
        'all_businesses': all_businesses,
        'home_score': home_score,
        'location_score': location_score,
        'total_score': total_score
    }
    
    from data_sources import census_api
    density = census_api.get_population_density(lat, lon)
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
        "data_quality": quality_metrics
    }
    
    # Log results
    print(f"✅ Neighborhood Amenities Score: {total_score:.0f}/100")
    print(f"   🏠 Home Walkability: {home_score:.0f}/60 ({len(nearby)} businesses within 1km)")
    print(f"   🌆 Location Quality: {location_score:.0f}/40")
    print(f"   📊 Data Quality: {quality_metrics['quality_tier']} ({quality_metrics['confidence']}% confidence)")
    
    return round(total_score, 1), breakdown


def _score_density(businesses: List[Dict], max_points: float = 40) -> float:
    """Score business density with adjustable max."""
    count = len(businesses)
    scale = max_points / 40
    
    if count >= 50:
        return 40.0 * scale
    elif count >= 40:
        return 38.0 * scale
    elif count >= 30:
        return 35.0 * scale
    elif count >= 20:
        return 30.0 * scale
    elif count >= 15:
        return 25.0 * scale
    elif count >= 10:
        return 20.0 * scale
    elif count >= 5:
        return 12.0 * scale
    else:
        return count * 2 * scale


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


def _score_proximity(businesses: List[Dict], max_points: float = 30) -> float:
    """Score proximity to downtown cluster."""
    if not businesses:
        return 0.0
    
    distances = sorted([b["distance_m"] for b in businesses])
    median_idx = len(distances) // 2
    median_distance = distances[median_idx]
    
    scale = max_points / 30
    
    if median_distance <= 200:
        return 30.0 * scale
    elif median_distance <= 400:
        return 28.0 * scale
    elif median_distance <= 600:
        return 25.0 * scale
    elif median_distance <= 800:
        return 20.0 * scale
    elif median_distance <= 1000:
        return 15.0 * scale
    else:
        return 5.0 * scale


def _score_location_quality(all_businesses: List[Dict], lat: float, lon: float, max_points: float = 40) -> float:
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
    
    # Density bonus (0-8)
    density_pts = min(8, len(cluster_all) / 5)  # 40 businesses = 8 pts
    
    vibrancy_pts = variety_pts + density_pts
    vibrancy_pts = min(vibrancy_pts, 20)  # Cap at 20
    
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

