"""
Neighborhood Beauty Pillar
Uses objective, real data sources:
- Trees (0-50): OSM tree count + Census canopy percentage
- Architectural Diversity (0-33): Building height, type, and footprint variation
  (Architectural diversity uses historic context to adjust scoring targets)
"""

from typing import Dict, Tuple, Optional
from data_sources import osm_api, census_api, data_quality
from data_sources.radius_profiles import get_radius_profile

# Try to import NYC API (only available for NYC addresses)
try:
    from data_sources import nyc_api as nyc_api
except ImportError:
    nyc_api = None

# Try to import Street Tree API (for multiple cities)
try:
    from data_sources import street_tree_api
except ImportError:
    street_tree_api = None


def get_neighborhood_beauty_score(lat: float, lon: float, city: Optional[str] = None, 
                                   beauty_weights: Optional[str] = None,
                                   location_scope: Optional[str] = None,
                                   area_type: Optional[str] = None) -> Tuple[float, Dict]:
    """
    Calculate neighborhood beauty score (0-100) using real data.
    
    Scoring components:
    - Trees (0-50): OSM tree count + Census canopy percentage
    - Architectural Diversity (0-50): Building height, type, and footprint variation
      (Raw score 0-33 scaled to 0-50. Uses historic context to adjust scoring targets)
    
    Args:
        beauty_weights: Custom weights (e.g., "trees:0.5,architecture:0.5")
                       Default: trees=0.5, architecture=0.5
    
    Returns:
        (total_score, detailed_breakdown)
    """
    print(f"✨ Analyzing neighborhood beauty...")
    
    # Parse custom weights or use defaults
    weights = _parse_beauty_weights(beauty_weights)
    
    # Component 1: Trees (0-50)
    print(f"   🌳 Analyzing tree canopy...")
    tree_score, tree_details = _score_trees(lat, lon, city, location_scope=location_scope, area_type=area_type)
    
    # Component 2: Architectural Diversity (0-33 raw, scaled to 0-50)
    print(f"   🏗️  Analyzing architectural diversity...")
    arch_score_raw, arch_details = _score_architectural_diversity(lat, lon, city, location_scope=location_scope, area_type=area_type)
    # Scale architectural diversity from 0-33 to 0-50 to match Trees (so components sum to 100)
    arch_score = arch_score_raw * (50.0 / 33.0)
    
    # Apply weights: Scale each component to its weighted max points
    # Default: trees=0.5 (50 points), architecture=0.5 (50 points) out of 100
    # Both components now have same max (50 each), so weights directly apply
    max_tree_points = weights.get('trees', 0.5) * 100
    max_arch_points = weights.get('architecture', 0.5) * 100
    
    total_score = (
        (tree_score * (max_tree_points / 50)) +
        (arch_score * (max_arch_points / 50))
    )
    
    # Assess data quality
    combined_data = {
        'tree_score': tree_score,
        'architectural_score': arch_score,
        'tree_details': tree_details,
        'architectural_details': arch_details
    }
    
    # Use passed area_type if available, otherwise detect it with city context
    if area_type is None:
        from data_sources import census_api as ca
        density = ca.get_population_density(lat, lon)
        area_type = data_quality.detect_area_type(lat, lon, density, city=city)
    else:
        # Still need density for quality assessment
        from data_sources import census_api as ca
        density = ca.get_population_density(lat, lon)
    
    quality_metrics = data_quality.assess_pillar_data_quality('neighborhood_beauty', combined_data, lat, lon, area_type)

    # If GEE canopy succeeded, reflect that in data_quality (no fallback; include source)
    try:
        tree_sources = tree_details.get('sources', [])
        used_gee = any(isinstance(s, str) and s.lower().startswith('gee') for s in tree_sources)
        if used_gee:
            quality_metrics['needs_fallback'] = False
            quality_metrics['fallback_score'] = None
            fm = quality_metrics.get('fallback_metadata', {}) or {}
            fm['fallback_used'] = False
            quality_metrics['fallback_metadata'] = fm
            # ensure data_sources lists gee
            ds = quality_metrics.get('data_sources', []) or []
            if 'gee' not in ds:
                ds.append('gee')
            quality_metrics['data_sources'] = ds
    except Exception:
        pass
    
    # Small beauty enhancers (viewpoints/artwork/fountains/waterfront)
    try:
        from data_sources.osm_api import query_beauty_enhancers
        enhancers = query_beauty_enhancers(lat, lon, radius_m=1500)
        beauty_bonus = min(8.0, enhancers.get('viewpoints',0)*2 + enhancers.get('artwork',0)*3 + enhancers.get('fountains',0)*1 + enhancers.get('waterfront',0)*2)
        total_score = min(100.0, total_score + beauty_bonus)
    except Exception:
        enhancers = {"viewpoints":0, "artwork":0, "fountains":0, "waterfront":0}
        beauty_bonus = 0.0

    # Build response
    breakdown = {
        "score": round(total_score, 1),
        "breakdown": {
            "trees": round(tree_score, 1),
            "architectural_diversity": round(arch_score, 1)  # Scaled to 0-50 to match Trees
        },
        "details": {
            "tree_analysis": tree_details,
            "architectural_analysis": arch_details,
            "enhancers": enhancers,
            "enhancer_bonus": beauty_bonus
        },
        "weights": weights,
        "data_quality": quality_metrics
    }
    
    # Log results
    print(f"✅ Neighborhood Beauty Score: {total_score:.0f}/100")
    print(f"   🌳 Trees: {tree_score:.0f}/50")
    print(f"   🏗️  Architectural Diversity: {arch_score:.0f}/50 (raw: {arch_details.get('score', 0):.0f}/33)")
    print(f"   📊 Data Quality: {quality_metrics['quality_tier']} ({quality_metrics['confidence']}% confidence)")
    
    return round(total_score, 1), breakdown


def _parse_beauty_weights(weights_str: Optional[str]) -> Dict[str, float]:
    """Parse custom beauty weights or return defaults."""
    if weights_str is None:
        return {'trees': 0.5, 'architecture': 0.5}
    
    try:
        weights = {}
        total = 0.0
        
        for pair in weights_str.split(','):
            component, weight = pair.split(':')
            weight = float(weight.strip())
            
            if component.strip() in ['trees', 'architecture']:
                weights[component.strip()] = weight
                total += weight
        
        # Normalize to sum to 1.0
        if total > 0:
            weights = {k: v / total for k, v in weights.items()}
        else:
            # Fallback if no valid weights
            weights = {'trees': 0.5, 'architecture': 0.5}
        
        return weights
    except:
        return {'trees': 0.5, 'architecture': 0.5}


def _score_trees(lat: float, lon: float, city: Optional[str], location_scope: Optional[str] = None, area_type: Optional[str] = None) -> Tuple[float, Dict]:
    """Score trees from multiple real data sources (0-50)."""
    score = 0.0
    sources = []
    details = {}
    
    # Priority 1: GEE satellite tree canopy (most comprehensive)
    # Use larger radius for suburban/rural areas to capture neighborhood tree coverage
    try:
        from data_sources import census_api, data_quality
        density = census_api.get_population_density(lat, lon)
        detected_area_type = data_quality.detect_area_type(lat, lon, density)
        area_type = area_type or detected_area_type
        
        # Adjust radius based on centralized profile
        rp = get_radius_profile('neighborhood_beauty', area_type, location_scope)
        radius_m = int(rp.get('tree_canopy_radius_m', 1000))
        print(f"   🔧 Radius profile (beauty): area_type={area_type}, scope={location_scope}, tree_canopy_radius={radius_m}m")
        
        from data_sources.gee_api import get_tree_canopy_gee
        gee_canopy = get_tree_canopy_gee(lat, lon, radius_m=radius_m, area_type=area_type)
        
        # Fallback: Only expand radius for cities (not neighborhoods)
        # Neighborhoods should stay within their boundaries
        if location_scope != 'neighborhood' and gee_canopy is not None and gee_canopy < 25.0 and area_type == 'urban_core':
            print(f"   🔄 Urban core returned {gee_canopy:.1f}% - trying larger radius to capture residential neighborhoods...")
            gee_canopy_larger = get_tree_canopy_gee(lat, lon, radius_m=2000, area_type=area_type)
            if gee_canopy_larger is not None and gee_canopy_larger > gee_canopy:
                print(f"   ✅ Larger radius (2km) found {gee_canopy_larger:.1f}% canopy (vs {gee_canopy:.1f}% at 1km)")
                gee_canopy = gee_canopy_larger
                # If still below 30%, try 3km (closer to city-wide assessments, only for cities)
                if gee_canopy < 30.0:
                    gee_canopy_3km = get_tree_canopy_gee(lat, lon, radius_m=3000, area_type=area_type)
                    if gee_canopy_3km is not None and gee_canopy_3km > gee_canopy:
                        print(f"   ✅ Even larger radius (3km) found {gee_canopy_3km:.1f}% canopy (vs {gee_canopy:.1f}% at 2km)")
                        gee_canopy = gee_canopy_3km
        elif location_scope != 'neighborhood' and (gee_canopy is None or gee_canopy < 0.1) and area_type == 'urban_core':
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
            
            # For NYC: Check if GEE canopy is suspiciously low (<15%) and supplement with street trees
            # GEE canopy misses individual street trees in dense urban areas
            if nyc_api and city and ("New York" in city or "NYC" in city or "Brooklyn" in city):
                if gee_canopy < 15.0:
                    print(f"   🗽 NYC location with low GEE canopy ({gee_canopy:.1f}%) - checking street trees...")
                    street_trees = nyc_api.get_street_trees(lat, lon, radius_deg=0.009)  # ~1000m
                    if street_trees:
                        tree_count = len(street_trees)
                        street_tree_score = _score_nyc_trees(tree_count)
                        # Use the higher of the two scores (street trees are more accurate for NYC)
                        if street_tree_score > score:
                            print(f"   ✅ NYC Street Trees: {tree_count} trees → {street_tree_score:.1f}/50 (using street trees)")
                            score = street_tree_score
                            sources.append(f"NYC Street Trees: {tree_count} trees")
                            details['nyc_street_trees'] = tree_count
                        else:
                            print(f"   📊 NYC Street Trees: {tree_count} trees → {street_tree_score:.1f}/50 (GEE canopy higher)")
        else:
            print(f"   ⚠️  GEE returned {gee_canopy} - trying Census fallback")
    except Exception as e:
        print(f"   ⚠️  GEE import error: {e}")
    
    # Priority 2: NYC Street Trees (if NYC and no score yet, or GEE was low)
    if score == 0.0 or (score < 30.0 and nyc_api and city and ("New York" in city or "NYC" in city or "Brooklyn" in city)):
        print(f"   🗽 Checking NYC Street Tree Census...")
        street_trees = nyc_api.get_street_trees(lat, lon, radius_deg=0.009)  # ~1000m
        if street_trees:
            tree_count = len(street_trees)
            street_tree_score = _score_nyc_trees(tree_count)
            if street_tree_score > score:
                print(f"   ✅ Using NYC Street Trees: {tree_count} trees → {street_tree_score:.1f}/50")
                score = street_tree_score
                sources.append(f"NYC Street Trees: {tree_count} trees")
                details['nyc_street_trees'] = tree_count
    
    # Priority 2b: Other Cities Street Trees (if city has street tree API and score is low)
    if (score == 0.0 or score < 30.0) and street_tree_api and city:
        city_key = street_tree_api.is_city_with_street_trees(city, lat, lon)
        if city_key:
            print(f"   🌳 Checking {city_key} Street Tree API...")
            street_trees = street_tree_api.get_street_trees(city, lat, lon, radius_m=1000)
            if street_trees:
                tree_count = len(street_trees)
                # Reuse NYC tree scoring function (same scoring logic)
                street_tree_score = _score_nyc_trees(tree_count)
                if street_tree_score > score:
                    print(f"   ✅ Using {city_key} Street Trees: {tree_count} trees → {street_tree_score:.1f}/50")
                    score = street_tree_score
                    sources.append(f"{city_key} Street Trees: {tree_count} trees")
                    details[f'{city_key.lower()}_street_trees'] = tree_count
    
    # Priority 3: Census USFS Tree Canopy (if GEE unavailable or low)
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
        # Use appropriate radius based on location scope
        parks_radius = 800 if location_scope == 'neighborhood' else 500
        tree_data = osm_api.query_green_spaces(lat, lon, radius_m=parks_radius)
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


def _fetch_historic_data(lat: float, lon: float, radius_m: int = 1000) -> Dict:
    """
    Fetch historic data once (OSM landmarks + Census building age).
    
    Used by architectural diversity component to adjust scoring targets based on historic context.
    Historic data helps determine appropriate architectural scoring targets (e.g., historic areas
    get more forgiving targets for organic growth patterns).
    
    Args:
        lat, lon: Coordinates
        radius_m: Radius for OSM historic landmarks query (default 1000m)
    
    Returns:
        {
            'year_built_data': Optional[Dict],  # Full Census data or None
            'median_year_built': Optional[int],  # Extracted for convenience
            'vintage_pct': Optional[float],     # Extracted for convenience
            'charm_data': Optional[Dict],        # Full OSM data or None
            'historic_landmarks': List,          # Extracted landmarks list
            'historic_landmarks_count': int      # Extracted count (0 if None)
        }
    """
    # Fetch building age from Census
    year_built_data = census_api.get_year_built_data(lat, lon)
    median_year_built = year_built_data.get('median_year_built') if year_built_data else None
    vintage_pct = year_built_data.get('vintage_pct', 0) if year_built_data else None
    
    # Fetch OSM historic landmarks
    charm_data = osm_api.query_charm_features(lat, lon, radius_m=radius_m)
    historic_landmarks = charm_data.get('historic', []) if charm_data else []
    historic_landmarks_count = len(historic_landmarks)
    
    return {
        'year_built_data': year_built_data,
        'median_year_built': median_year_built,
        'vintage_pct': vintage_pct,
        'charm_data': charm_data,
        'historic_landmarks': historic_landmarks,
        'historic_landmarks_count': historic_landmarks_count
    }


def _score_architectural_diversity(lat: float, lon: float, city: Optional[str] = None,
                                    location_scope: Optional[str] = None,
                                    area_type: Optional[str] = None) -> Tuple[float, Dict]:
    """
    Score architectural diversity (0-33 points raw, scaled to 0-50 in main function).
    
    Uses conditional adjustments for historic organic development patterns.
    
    Returns:
        (raw_score_0-33, details_dict)
    """
    try:
        from data_sources import arch_diversity, census_api, data_quality, geocoding
        from data_sources.data_quality import get_effective_area_type
        
        # Get radius profile for architectural diversity
        radius_m = 1000  # Default radius
        if area_type:
            rp = get_radius_profile('neighborhood_beauty', area_type, location_scope)
            radius_m = int(rp.get('architectural_diversity_radius_m', 1000))
        
        # Compute architectural diversity metrics
        diversity_metrics = arch_diversity.compute_arch_diversity(lat, lon, radius_m=radius_m)
        
        if 'error' in diversity_metrics:
            print(f"   ⚠️  Architectural diversity computation failed: {diversity_metrics.get('error')}")
            return 0.0, {"error": diversity_metrics.get('error'), "note": "OSM building data unavailable"}
        
        # Get area type and density for classification
        if area_type is None:
            density = census_api.get_population_density(lat, lon) or 0.0
            if not city:
                city = geocoding.reverse_geocode(lat, lon)
            area_type = data_quality.detect_area_type(lat, lon, density, city)
        else:
            density = census_api.get_population_density(lat, lon) or 0.0
        
        # Get historic data for scoring adjustments (reuse shared helper)
        historic_data = _fetch_historic_data(lat, lon, radius_m=radius_m)
        historic_landmarks = historic_data.get('historic_landmarks_count', 0)
        median_year_built = historic_data.get('median_year_built')
        
        # Calculate beauty score using conditional adjustments
        beauty_score = arch_diversity.score_architectural_diversity_as_beauty(
            diversity_metrics.get("levels_entropy", 0),
            diversity_metrics.get("building_type_diversity", 0),
            diversity_metrics.get("footprint_area_cv", 0),
            area_type,
            density,
            diversity_metrics.get("built_coverage_ratio"),
            historic_landmarks=historic_landmarks,
            median_year_built=median_year_built
        )
        
        # Get effective area type for details
        effective_area_type = get_effective_area_type(
            area_type,
            density,
            diversity_metrics.get("levels_entropy"),
            diversity_metrics.get("building_type_diversity"),
            historic_landmarks=historic_landmarks,
            median_year_built=median_year_built
        )
        
        details = {
            "score": round(beauty_score, 1),
            "max_score": 33.0,
            "metrics": {
                "height_diversity": diversity_metrics.get("levels_entropy", 0),
                "type_diversity": diversity_metrics.get("building_type_diversity", 0),
                "footprint_variation": diversity_metrics.get("footprint_area_cv", 0),
                "built_coverage_ratio": diversity_metrics.get("built_coverage_ratio", 0)
            },
            "classification": {
                "base_area_type": area_type,
                "effective_area_type": effective_area_type,
                "density": density
            },
            "historic_context": {
                "landmarks": historic_landmarks,
                "median_year_built": median_year_built
            },
            "sources": ["OSM"]
        }
        
        print(f"   ✅ Architectural diversity: {beauty_score:.1f}/33.0 (effective: {effective_area_type})")
        
        return round(beauty_score, 1), details
        
    except Exception as e:
        print(f"   ⚠️  Architectural diversity scoring failed: {e}")
        return 0.0, {"error": str(e), "note": "Architectural diversity unavailable"}


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
    """Score tree canopy percentage linearly up to 50 points at ~45% canopy."""
    canopy = max(0.0, min(100.0, canopy_pct))
    # 45% -> 50 points; linear scale, cap at 50
    return min(50.0, (canopy / 45.0) * 50.0)
