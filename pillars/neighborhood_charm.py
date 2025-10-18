"""
Neighborhood Charm Pillar
Scores visual appeal and distinctive character of the area
"""

from typing import Dict, Tuple, Optional
from data_sources import osm_api, nyc_api, census_api


def get_neighborhood_charm_score(lat: float, lon: float, city: Optional[str] = None) -> Tuple[float, Dict]:
    """
    Calculate neighborhood charm score (0-100) based on aesthetic appeal.

    Scoring:
    - Tree Canopy Coverage: 0-40 points
    - Historic Architecture: 0-30 points
    - Public Art & Fountains: 0-30 points

    Returns:
        (total_score, detailed_breakdown)
    """
    print(f"✨ Analyzing neighborhood charm...")

    # Get charm features from OSM (500m radius for aesthetic features)
    print(f"   🏛️  Querying historic & aesthetic features...")
    charm_data = osm_api.query_charm_features(lat, lon, radius_m=500)

    # Get tree canopy data
    print(f"   🌳 Checking tree canopy coverage...")
    tree_score, tree_note = _score_trees(lat, lon, city)

    if charm_data is None:
        print("⚠️  OSM data unavailable")
        return 50, _estimated_breakdown(tree_score, tree_note)

    historic = charm_data.get("historic", [])
    artwork = charm_data.get("artwork", [])

    # Score components
    historic_score = _score_historic(historic)
    art_score = _score_art(artwork)

    total_score = tree_score + historic_score + art_score

    # Build response
    breakdown = {
        "score": round(total_score, 1),
        "breakdown": {
            "tree_canopy": round(tree_score, 1),
            "historic_architecture": round(historic_score, 1),
            "public_art": round(art_score, 1)
        },
        "summary": {
            "tree_canopy_note": tree_note,
            "historic_buildings": len(historic),
            "artworks_fountains": len(artwork),
            "closest_historic": _get_closest(historic) if historic else None,
            "closest_artwork": _get_closest(artwork) if artwork else None
        }
    }

    # Log results
    print(f"✅ Neighborhood Charm Score: {total_score:.0f}/100")
    print(f"   🌳 Tree Canopy: {tree_score:.0f}/40 - {tree_note}")
    print(f"   🏛️  Historic Architecture: {historic_score:.0f}/30 ({len(historic)} buildings)")
    print(f"   🎨 Public Art & Fountains: {art_score:.0f}/30 ({len(artwork)} features)")

    return round(total_score, 1), breakdown


def _score_trees(lat: float, lon: float, city: Optional[str]) -> Tuple[float, str]:
    """
    Score tree canopy using waterfall approach:
    1. NYC → Street Tree Census
    2. Other cities → Census USFS canopy
    3. Fallback → No data
    """
    # Priority 1: NYC Street Tree Census
    if (city and "new york" in city.lower()) or nyc_api.is_nyc(lat, lon):
        trees = nyc_api.get_street_trees(lat, lon)
        if trees is not None:
            tree_count = len(trees)
            score = _score_nyc_trees(tree_count)
            return score, f"NYC Census: {tree_count} trees"

    # Priority 2: Census USFS tree canopy
    canopy_pct = census_api.get_tree_canopy(lat, lon)
    if canopy_pct is not None:
        score = _score_tree_canopy(canopy_pct)
        return score, f"Census USFS: {canopy_pct:.1f}% canopy"

    # No data available
    return 0.0, "No tree data available"


def _score_nyc_trees(tree_count: int) -> float:
    """Convert NYC tree count to score (0-40 points)."""
    if tree_count >= 150:
        return 40.0
    elif tree_count >= 100:
        return 35.0
    elif tree_count >= 75:
        return 30.0
    elif tree_count >= 50:
        return 25.0
    elif tree_count >= 25:
        return 18.0
    else:
        return 12.0


def _score_tree_canopy(canopy_pct: float) -> float:
    """Convert Census tree canopy % to score (0-40 points)."""
    if canopy_pct >= 40:
        return 40.0
    elif canopy_pct >= 30:
        return 35.0
    elif canopy_pct >= 20:
        return 28.0
    elif canopy_pct >= 10:
        return 20.0
    elif canopy_pct >= 5:
        return 12.0
    else:
        return 5.0


def _score_historic(historic: list) -> float:
    """Score historic architecture (0-30 points) based on count and proximity."""
    if not historic:
        return 0.0

    count = len(historic)
    
    # More historic buildings = more charm
    if count >= 20:
        count_score = 20
    elif count >= 10:
        count_score = 15
    elif count >= 5:
        count_score = 10
    else:
        count_score = count * 2

    # Proximity bonus - closer historic buildings add charm
    closest = min(h["distance_m"] for h in historic)
    if closest <= 100:
        proximity_score = 10
    elif closest <= 200:
        proximity_score = 7
    elif closest <= 350:
        proximity_score = 5
    else:
        proximity_score = 2

    return min(30, count_score + proximity_score)


def _score_art(artwork: list) -> float:
    """Score public art and fountains (0-30 points) based on count and variety."""
    if not artwork:
        return 0.0

    count = len(artwork)
    
    # Count score
    if count >= 15:
        count_score = 20
    elif count >= 10:
        count_score = 15
    elif count >= 5:
        count_score = 10
    else:
        count_score = count * 2

    # Variety bonus - different types of art
    types = set(a["type"] for a in artwork)
    variety_score = min(10, len(types) * 3)

    return min(30, count_score + variety_score)


def _get_closest(features: list) -> Dict:
    """Get info about closest feature."""
    if not features:
        return None
    
    closest = min(features, key=lambda x: x["distance_m"])
    return {
        "name": closest.get("name"),
        "type": closest.get("type"),
        "distance_m": closest["distance_m"]
    }


def _estimated_breakdown(tree_score: float, tree_note: str) -> Dict:
    """Return estimated breakdown when API fails."""
    return {
        "score": 50,
        "breakdown": {
            "tree_canopy": tree_score,
            "historic_architecture": 15,
            "public_art": 15
        },
        "summary": {
            "tree_canopy_note": tree_note,
            "historic_buildings": 0,
            "artworks_fountains": 0,
            "closest_historic": None,
            "closest_artwork": None
        }
    }