"""
Neighborhood Beauty Pillar - Simplified
Uses only objective, real data sources (trees + historic character)
Removed fake components (visual aesthetics, architectural quality)
"""

from typing import Dict, Tuple, Optional
from data_sources import osm_api, census_api, data_quality

# Try to import NYC API (only available for NYC addresses)
try:
    from data_sources import nyc_api as nyc_api
except ImportError:
    nyc_api = None


def get_neighborhood_beauty_score(lat: float, lon: float, city: Optional[str] = None, 
                                   beauty_weights: Optional[str] = None) -> Tuple[float, Dict]:
    """
    Calculate neighborhood beauty score (0-100) using only real data.
    
    Simplified scoring components:
    - Trees (0-50): OSM tree count + Census canopy percentage
    - Historic Character (0-50): Census building age + OSM landmarks
    
    Args:
        beauty_weights: Custom weights (e.g., "trees:0.6,historic:0.4")
                       Default: trees=0.5, historic=0.5
    
    Returns:
        (total_score, detailed_breakdown)
    """
    print(f"✨ Analyzing neighborhood beauty...")
    
    # Parse custom weights or use defaults
    weights = _parse_beauty_weights(beauty_weights)
    
    # Component 1: Trees (0-50)
    print(f"   🌳 Analyzing tree canopy...")
    tree_score, tree_details = _score_trees(lat, lon, city)
    
    # Component 2: Historic Character (0-50)
    print(f"   🏛️  Analyzing historic character...")
    historic_score, historic_details = _score_historic(lat, lon)
    
    # Apply weights
    weighted_score = (tree_score * weights['trees']) + (historic_score * weights['historic'])
    
    # Assess data quality
    combined_data = {
        'tree_score': tree_score,
        'historic_score': historic_score,
        'tree_details': tree_details,
        'historic_details': historic_details
    }
    
    from data_sources import census_api as ca
    density = ca.get_population_density(lat, lon)
    area_type = data_quality.detect_area_type(lat, lon, density)
    quality_metrics = data_quality.assess_pillar_data_quality('neighborhood_beauty', combined_data, lat, lon, area_type)
    
    # Build response
    breakdown = {
        "score": round(weighted_score, 1),
        "breakdown": {
            "trees": round(tree_score, 1),
            "historic_character": round(historic_score, 1)
        },
        "details": {
            "tree_analysis": tree_details,
            "historic_analysis": historic_details
        },
        "weights": weights,
        "data_quality": quality_metrics
    }
    
    # Log results
    print(f"✅ Neighborhood Beauty Score: {weighted_score:.0f}/100")
    print(f"   🌳 Trees: {tree_score:.0f}/50 (weight: {weights['trees']})")
    print(f"   🏛️  Historic: {historic_score:.0f}/50 (weight: {weights['historic']})")
    print(f"   📊 Data Quality: {quality_metrics['quality_tier']} ({quality_metrics['confidence']}% confidence)")
    
    return round(weighted_score, 1), breakdown


def _parse_beauty_weights(weights_str: Optional[str]) -> Dict[str, float]:
    """Parse custom beauty weights or return defaults."""
    if weights_str is None:
        return {'trees': 0.5, 'historic': 0.5}
    
    try:
        weights = {}
        total = 0.0
        
        for pair in weights_str.split(','):
            component, weight = pair.split(':')
            weight = float(weight.strip())
            
            if component in ['trees', 'historic']:
                weights[component.strip()] = weight
                total += weight
        
        # Normalize to sum to 1.0
        if total > 0:
            weights = {k: v / total for k, v in weights.items()}
        
        return weights
    except:
        return {'trees': 0.5, 'historic': 0.5}


def _score_trees(lat: float, lon: float, city: Optional[str]) -> Tuple[float, Dict]:
    """Score trees from multiple real data sources (0-50)."""
    score = 0.0
    sources = []
    details = {}
    
    # Priority 1: GEE satellite tree canopy (most comprehensive)
    # Use larger radius for suburban/rural areas to capture neighborhood tree coverage
    try:
        from data_sources import census_api, data_quality
        density = census_api.get_population_density(lat, lon)
        area_type = data_quality.detect_area_type(lat, lon, density)
        
        # Adjust radius based on area type: suburban/rural need larger buffers
        if area_type in ['rural', 'exurban']:
            radius_m = 2000  # 2km for rural/exurban
        elif area_type == 'suburban':
            radius_m = 2000  # 2km for suburban (increased from 1.5km for better coverage)
        else:
            radius_m = 1000  # 1km for urban (downtown core)
        
        from data_sources.gee_api import get_tree_canopy_gee
        gee_canopy = get_tree_canopy_gee(lat, lon, radius_m=radius_m, area_type=area_type)
        
        # Fallback: If urban core returns 0% or very low, try larger radius
        # Downtown cores may be concrete but surrounding neighborhoods have trees
        if (gee_canopy is None or gee_canopy < 0.1) and area_type == 'urban_core':
            print(f"   🔄 Urban core returned {gee_canopy if gee_canopy else 'None'}% - trying larger radius...")
            gee_canopy = get_tree_canopy_gee(lat, lon, radius_m=2000, area_type=area_type)
            if gee_canopy is not None and gee_canopy >= 0.1:
                print(f"   ✅ Larger radius (2km) found {gee_canopy:.1f}% canopy")
        
        if gee_canopy is not None and gee_canopy >= 0.1:  # Threshold to avoid false zeros
            canopy_score = _score_tree_canopy(gee_canopy)
            score = canopy_score
            sources.append(f"GEE: {gee_canopy:.1f}% canopy")
            details['gee_canopy_pct'] = gee_canopy
            print(f"   ✅ Using GEE satellite data: {gee_canopy:.1f}%")
        else:
            print(f"   ⚠️  GEE returned {gee_canopy} - trying Census fallback")
    except Exception as e:
        print(f"   ⚠️  GEE import error: {e}")
    
    # Priority 2: Census USFS Tree Canopy (if GEE unavailable or low)
    if score == 0.0:
        print(f"   📊 Trying Census USFS tree canopy data...")
        canopy_pct = census_api.get_tree_canopy(lat, lon)
        if canopy_pct is not None and canopy_pct > 0:
            canopy_score = _score_tree_canopy(canopy_pct)
            score = canopy_score
            sources.append(f"USFS Census: {canopy_pct:.1f}% canopy")
            details['census_canopy_pct'] = canopy_pct
            print(f"   ✅ Using Census canopy data: {canopy_pct:.1f}%")
        else:
            print(f"   ⚠️  Census canopy returned {canopy_pct}")
    
    # Priority 3: OSM parks as proxy (fallback)
    if score == 0.0:
        tree_data = osm_api.query_green_spaces(lat, lon, radius_m=500)
        if tree_data:
            parks = tree_data.get('parks', [])
            if parks:
                park_count = len(parks)
                park_score = min(30, park_count * 5)  # 6 parks = 30 pts
                score = park_score
                sources.append(f"OSM: {park_count} parks/green spaces")
                details['osm_parks'] = park_count
                print(f"   📊 Using OSM park data: {park_count} parks")
            else:
                print(f"   ⚠️  No tree data available from any source")
                sources.append("No tree data available")
    
    details['sources'] = sources
    details['total_score'] = score
    
    return score, details


def _score_historic(lat: float, lon: float) -> Tuple[float, Dict]:
    """Score historic character (0-50) based on building age and landmarks."""
    
    # Get building age from Census
    year_built_data = census_api.get_year_built_data(lat, lon)
    
    if year_built_data is None:
        return 0.0, {"note": "No building age data available"}
    
    # Calculate historic score from year built
    median_year = year_built_data.get('median_year_built', 2000)
    vintage_pct = year_built_data.get('vintage_pct', 0)  # Pre-1960 buildings
    
    # Score based on age and vintage percentage
    if median_year < 1940:
        score = 50.0
    elif median_year < 1960:
        score = 40.0 + min(10, vintage_pct)
    elif median_year < 1980:
        score = 30.0 + min(10, vintage_pct * 0.5)
    elif median_year < 2000:
        score = 20.0
    else:
        score = 10.0
    
    # Get OSM historic landmarks
    charm_data = osm_api.query_charm_features(lat, lon, radius_m=500)
    if charm_data and charm_data.get('historic'):
        landmarks_count = len(charm_data['historic'])
        if landmarks_count > 0:
            # Bonus for historic landmarks (up to 10 points)
            score += min(10, landmarks_count * 2)
    
    details = {
        "median_year_built": median_year,
        "vintage_pct": vintage_pct,
        "historic_landmarks": charm_data.get('historic', []) if charm_data else [],
        "total_score": score
    }
    
    return score, details


def _score_nyc_trees(tree_count: int) -> float:
    """Score NYC street trees."""
    if tree_count >= 50:
        return 50.0
    elif tree_count >= 30:
        return 40.0
    elif tree_count >= 20:
        return 30.0
    elif tree_count >= 10:
        return 20.0
    else:
        return tree_count * 1.5


def _score_tree_canopy(canopy_pct: float) -> float:
    """Score tree canopy percentage with more generous suburban scoring."""
    if canopy_pct >= 30:
        return 50.0
    elif canopy_pct >= 20:
        return 45.0
    elif canopy_pct >= 15:
        return 40.0
    elif canopy_pct >= 10:
        return 35.0
    elif canopy_pct >= 5:
        return 25.0
    elif canopy_pct >= 2:
        return 15.0
    elif canopy_pct >= 1:
        return 10.0
    elif canopy_pct >= 0.5:
        return 5.0
    else:
        return canopy_pct * 5.0  # Less harsh penalty for very low values
