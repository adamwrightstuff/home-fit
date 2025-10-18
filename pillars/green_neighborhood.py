"""
Green Neighborhood Pillar
Scores local greenery: parks, trees, playgrounds
"""

from typing import Dict, Tuple, Optional
from data_sources import osm_api, nyc_api, census_api


def get_green_neighborhood_score(lat: float, lon: float, city: Optional[str] = None) -> Tuple[float, Dict]:
    """
    Calculate greenery score (0-100) based on parks, trees, and playgrounds.

    Scoring:
    - Parks: 0-40 points
    - Trees: 0-30 points
    - Playgrounds: 0-30 points
    
    Uses flexible weighting: if tree data is unavailable, rescales other components.

    Returns:
        (total_score, detailed_breakdown)
    """
    print(f"🌳 Analyzing green neighborhood within 1km...")

    # Get green spaces from OSM
    osm_data = osm_api.query_green_spaces(lat, lon, radius_m=1000)

    if osm_data is None:
        print("⚠️  OSM data unavailable")
        return 50, _estimated_breakdown()

    parks = osm_data["parks"]
    playgrounds = osm_data["playgrounds"]
    tree_features = osm_data["tree_features"]

    # Score components
    park_score = _score_parks(parks)
    playground_score = _score_playgrounds(playgrounds)
    tree_score, tree_note = _score_trees(lat, lon, city, tree_features)

    # Check if tree data is unavailable (vs actually finding 0 trees)
    tree_data_unavailable = (
        tree_score == 0 and 
        ("OSM: 0 features" in tree_note or 
         "failed" in tree_note.lower() or
         "No data" in tree_note)
    )
    
    # Flexible weighting
    if tree_data_unavailable:
        # Exclude trees, rescale parks + playgrounds to 100
        total_available = park_score + playground_score
        max_available = 70  # 40 (parks) + 30 (playgrounds)
        total_score = (total_available / max_available) * 100
        tree_display = "N/A"
        scoring_note = "Trees excluded (no data available)"
    else:
        # Include all components
        total_score = park_score + tree_score + playground_score
        tree_display = tree_score
        scoring_note = "All components included"

    # Build response
    breakdown = {
        "score": round(total_score, 1),
        "breakdown": {
            "parks": round(park_score, 1),
            "trees": tree_display if tree_display == "N/A" else round(tree_score, 1),
            "playgrounds": round(playground_score, 1)
        },
        "summary": _build_summary(parks, playgrounds, tree_note),
        "scoring_note": scoring_note
    }

    # Log results
    print(f"✅ Green Neighborhood Score: {total_score:.0f}/100 ({scoring_note})")
    print(f"   🌲 Parks: {park_score:.0f}/40 ({len(parks)} found)")
    if tree_display == "N/A":
        print(f"   🌳 Trees: N/A - {tree_note}")
    else:
        print(f"   🌳 Trees: {tree_score:.0f}/30 - {tree_note}")
    print(f"   🛝 Playgrounds: {playground_score:.0f}/30 ({len(playgrounds)} found)")

    return round(total_score, 1), breakdown


def _score_trees(lat: float, lon: float, city: Optional[str], osm_tree_features: list) -> Tuple[float, str]:
    """
    Score trees using waterfall approach:
    1. NYC → Street Tree Census
    2. Other cities → Census USFS canopy
    3. Fallback → OSM tree features
    """
    # Priority 1: NYC Street Tree Census
    if (city and "new york" in city.lower()) or nyc_api.is_nyc(lat, lon):
        print(f"   🌳 Using NYC Street Tree Census API...")
        trees = nyc_api.get_street_trees(lat, lon)
        if trees is not None:
            tree_count = len(trees)
            print(f"   ✅ Found {tree_count} trees in NYC census")
            score = _score_nyc_trees(tree_count)
            return score, f"NYC Census: {tree_count} trees"

    # Priority 2: Census USFS tree canopy
    print(f"   🌳 Trying Census USFS tree canopy data...")
    canopy_pct = census_api.get_tree_canopy(lat, lon)
    if canopy_pct is not None:
        score = _score_tree_canopy(canopy_pct)
        return score, f"Census USFS: {canopy_pct:.1f}% canopy"

    # Priority 3: OSM tree features (fallback)
    print(f"   🌳 Using OSM tree features...")
    score = _score_osm_trees(osm_tree_features)
    return score, f"OSM: {len(osm_tree_features)} features"


def _score_parks(parks: list) -> float:
    """Score parks (0-40 points) based on count and area."""
    if not parks:
        return 0.0

    count = len(parks)
    total_area_sqm = sum(p["area_sqm"] for p in parks)

    # Count score (5 pts per park, max 20)
    count_score = min(20, count * 5)

    # Area score (0-20 points)
    total_hectares = total_area_sqm / 10000
    if total_hectares >= 10:
        area_score = 20
    elif total_hectares >= 5:
        area_score = 15
    elif total_hectares >= 2:
        area_score = 12
    elif total_hectares >= 1:
        area_score = 8
    elif total_hectares >= 0.5:
        area_score = 5
    else:
        area_score = 2

    return min(40, count_score + area_score)


def _score_playgrounds(playgrounds: list) -> float:
    """Score playgrounds (0-30 points) based on count."""
    count = len(playgrounds)
    return min(30, count * 10)


def _score_nyc_trees(tree_count: int) -> float:
    """Convert NYC tree count to score (0-30 points)."""
    if tree_count >= 150:
        return 30.0
    elif tree_count >= 100:
        return 27.0
    elif tree_count >= 75:
        return 24.0
    elif tree_count >= 50:
        return 20.0
    elif tree_count >= 25:
        return 15.0
    else:
        return 10.0


def _score_tree_canopy(canopy_pct: float) -> float:
    """Convert Census tree canopy % to score (0-30 points)."""
    if canopy_pct >= 40:
        return 30.0
    elif canopy_pct >= 30:
        return 25.0
    elif canopy_pct >= 20:
        return 20.0
    elif canopy_pct >= 10:
        return 15.0
    elif canopy_pct >= 5:
        return 10.0
    else:
        return 5.0


def _score_osm_trees(tree_features: list) -> float:
    """Convert OSM tree features to score (0-30 points)."""
    if not tree_features:
        return 0.0

    tree_rows = [f for f in tree_features if f["type"] == "tree_row"]
    street_trees = [f for f in tree_features if f["type"] == "street_trees"]

    tree_row_score = min(15, len(tree_rows) * 2)
    street_tree_score = min(15, len(street_trees) * 1)

    return tree_row_score + street_tree_score


def _build_summary(parks: list, playgrounds: list, tree_note: str) -> Dict:
    """Build summary statistics."""
    closest_park = min(parks, key=lambda x: x["distance_m"]) if parks else None
    total_park_area = sum(p["area_sqm"] for p in parks)

    return {
        "total_parks": len(parks),
        "total_playgrounds": len(playgrounds),
        "tree_data_source": tree_note,
        "closest_park": {
            "name": closest_park["name"],
            "distance_m": closest_park["distance_m"],
            "area_sqm": closest_park["area_sqm"]
        } if closest_park else None,
        "total_park_area_hectares": round(total_park_area / 10000, 2),
        "within_5min_walk": len([p for p in parks if p["distance_m"] <= 400]),
        "within_10min_walk": len([p for p in parks if p["distance_m"] <= 800])
    }


def _estimated_breakdown() -> Dict:
    """Return estimated breakdown when API fails."""
    return {
        "score": 50,
        "breakdown": {
            "parks": 20,
            "trees": 15,
            "playgrounds": 15
        },
        "summary": {
            "total_parks": 0,
            "total_playgrounds": 0,
            "tree_data_source": "Estimated (API timeout)",
            "closest_park": None,
            "total_park_area_hectares": 0,
            "within_5min_walk": 0,
            "within_10min_walk": 0
        }
    }