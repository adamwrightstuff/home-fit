"""
Neighborhood Beauty Pillar
Scores visual appeal and distinctive character of the area
"""

from typing import Dict, Tuple, Optional
from data_sources import osm_api, nyc_api, census_api, data_quality


def get_neighborhood_beauty_score(lat: float, lon: float, city: Optional[str] = None) -> Tuple[float, Dict]:
    """
    Calculate neighborhood beauty score (0-100) based on aesthetic appeal.

    Scoring:
    - Tree Canopy Coverage: 0-50 points
    - Historic Character: 0-50 points (primarily median year built, OSM bonus)

    Returns:
        (total_score, detailed_breakdown)
    """
    print(f"✨ Analyzing neighborhood beauty...")

    # Get charm features from OSM (500m radius for aesthetic features)
    print(f"   🏛️  Querying historic & aesthetic features...")
    charm_data = osm_api.query_charm_features(lat, lon, radius_m=500)

    # Get tree canopy data
    print(f"   🌳 Checking tree canopy coverage...")
    tree_score, tree_note = _score_trees(lat, lon, city)

    # Get year built data from Census
    print(f"   🏛️  Checking historic housing stock...")
    year_built_data = census_api.get_year_built_data(lat, lon)

    # Assess data quality
    combined_data = {
        'charm_data': charm_data,
        'year_built_data': year_built_data,
        'tree_score': tree_score,
        'tree_note': tree_note
    }
    
    # Detect actual area type for data quality assessment
    density = census_api.get_population_density(lat, lon)
    area_type = data_quality.detect_area_type(lat, lon, density)
    quality_metrics = data_quality.assess_pillar_data_quality('neighborhood_beauty', combined_data, lat, lon, area_type)

    if charm_data is None:
        print("⚠️  OSM data unavailable")
        historic_score = _score_historic_from_census_only(year_built_data)
        total_score = tree_score + historic_score
        breakdown = _estimated_breakdown(tree_score, tree_note, historic_score, year_built_data)
        breakdown["data_quality"] = quality_metrics
        return total_score, breakdown

    historic = charm_data.get("historic", [])
    artwork = charm_data.get("artwork", [])

    # Score historic character (median year as primary signal)
    historic_score = _score_historic_character(historic, artwork, year_built_data)

    total_score = tree_score + historic_score

    # Build response
    breakdown = {
        "score": round(total_score, 1),
        "breakdown": {
            "tree_canopy": round(tree_score, 1),
            "historic_character": round(historic_score, 1)
        },
        "summary": {
            "tree_canopy_note": tree_note,
            "historic_buildings": len(historic),
            "monuments_fountains": len(artwork),
            "vintage_housing_pct": year_built_data.get("vintage_pct") if year_built_data else None,
            "median_year_built": year_built_data.get("median_year_built") if year_built_data else None,
            "closest_historic": _get_closest(historic) if historic else None,
            "closest_monument": _get_closest(artwork) if artwork else None
        },
        "data_quality": quality_metrics
    }

    # Log results
    print(f"✅ Neighborhood Beauty Score: {total_score:.0f}/100")
    print(f"   🌳 Tree Canopy: {tree_score:.0f}/50 - {tree_note}")
    print(f"   🏛️  Historic Character: {historic_score:.0f}/50")
    if year_built_data:
        median_year = year_built_data.get("median_year_built")
        print(f"      • Median year built: {median_year} (primary signal)")
        print(f"      • Vintage housing: {year_built_data.get('vintage_pct', 0)}%")
        print(f"      • Historic buildings (OSM): {len(historic)} (bonus)")
    print(f"   📊 Data Quality: {quality_metrics['quality_tier']} ({quality_metrics['confidence']}% confidence)")

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
    """Convert NYC tree count to score (0-50 points)."""
    if tree_count >= 150:
        return 50.0
    elif tree_count >= 100:
        return 45.0
    elif tree_count >= 75:
        return 40.0
    elif tree_count >= 50:
        return 32.0
    elif tree_count >= 25:
        return 25.0
    else:
        return 15.0


def _score_tree_canopy(canopy_pct: float) -> float:
    """Convert Census tree canopy % to score (0-50 points)."""
    if canopy_pct >= 40:
        return 50.0
    elif canopy_pct >= 30:
        return 45.0
    elif canopy_pct >= 20:
        return 38.0
    elif canopy_pct >= 10:
        return 28.0
    elif canopy_pct >= 5:
        return 18.0
    else:
        return 8.0


def _score_historic_character(historic_buildings: list, monuments: list, year_built_data: Optional[Dict]) -> float:
    """
    Score historic character (0-50 points) with median year as PRIMARY signal:
    - Census median year built (0-35 pts) - PRIMARY
    - OSM historic buildings (0-10 pts) - BONUS
    - OSM monuments/fountains (0-5 pts) - BONUS
    """
    # Component 1: Median year built from Census (0-35 pts) - PRIMARY
    median_score = _score_median_year_built(year_built_data)
    
    # Component 2: Historic buildings from OSM (0-10 pts) - BONUS
    building_score = _score_osm_buildings(historic_buildings)
    
    # Component 3: Monuments & fountains from OSM (0-5 pts) - BONUS
    monument_score = _score_monuments_fountains(monuments)
    
    total = median_score + building_score + monument_score
    return min(50, total)


def _score_median_year_built(year_built_data: Optional[Dict]) -> float:
    """
    Score based on median year built (0-35 points) - PRIMARY METRIC.
    
    Median year is more reliable than tract vintage % for historic neighborhoods.
    """
    if not year_built_data:
        return 0.0
    
    median_year = year_built_data.get("median_year_built")
    if not median_year:
        return 0.0
    
    # Score based on median year built
    if median_year <= 1900:
        return 35.0  # Very historic (pre-1900)
    elif median_year <= 1920:
        return 33.0  # Early 20th century
    elif median_year <= 1940:
        return 30.0  # Pre-WWII
    elif median_year <= 1960:
        return 25.0  # Mid-century
    elif median_year <= 1980:
        return 18.0  # Later 20th century
    elif median_year <= 2000:
        return 12.0  # Recent
    else:
        return 5.0   # Modern (post-2000)


def _score_osm_buildings(historic: list) -> float:
    """Score OSM historic buildings (0-10 points) - BONUS."""
    if not historic:
        return 0.0

    count = len(historic)
    
    # Count score (0-7)
    if count >= 10:
        count_score = 7
    elif count >= 5:
        count_score = 5
    elif count >= 3:
        count_score = 4
    else:
        count_score = count * 1

    # Proximity bonus (0-3)
    closest = min(h["distance_m"] for h in historic)
    if closest <= 100:
        proximity_score = 3
    elif closest <= 200:
        proximity_score = 2
    else:
        proximity_score = 1

    return min(10, count_score + proximity_score)


def _score_monuments_fountains(monuments: list) -> float:
    """Score monuments, fountains, memorials (0-5 points) - BONUS."""
    if not monuments:
        return 0.0

    count = len(monuments)
    
    # Simple count score
    if count >= 5:
        return 5.0
    elif count >= 3:
        return 4.0
    elif count >= 2:
        return 3.0
    else:
        return 2.0


def _score_historic_from_census_only(year_built_data: Optional[Dict]) -> float:
    """Fallback: score only from Census when OSM unavailable."""
    if not year_built_data:
        return 0.0
    
    median_year = year_built_data.get("median_year_built")
    if not median_year:
        return 0.0
    
    # Use full 50 pt range when OSM unavailable
    if median_year <= 1900:
        return 50.0
    elif median_year <= 1920:
        return 45.0
    elif median_year <= 1940:
        return 40.0
    elif median_year <= 1960:
        return 32.0
    elif median_year <= 1980:
        return 24.0
    elif median_year <= 2000:
        return 16.0
    else:
        return 8.0


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


def _estimated_breakdown(tree_score: float, tree_note: str, historic_score: float, year_built_data: Optional[Dict]) -> Dict:
    """Return estimated breakdown when API fails."""
    return {
        "score": tree_score + historic_score,
        "breakdown": {
            "tree_canopy": tree_score,
            "historic_character": historic_score
        },
        "summary": {
            "tree_canopy_note": tree_note,
            "historic_buildings": 0,
            "monuments_fountains": 0,
            "vintage_housing_pct": year_built_data.get("vintage_pct") if year_built_data else None,
            "median_year_built": year_built_data.get("median_year_built") if year_built_data else None,
            "closest_historic": None,
            "closest_monument": None
        }
    }