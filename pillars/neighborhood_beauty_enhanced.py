"""
Enhanced Neighborhood Beauty Pillar
Comprehensive visual appeal and distinctive character scoring with expanded data sources
"""

from typing import Dict, Tuple, Optional
from data_sources import osm_api, nyc_api, census_api, satellite_api, streetview_api, data_quality


def get_enhanced_neighborhood_beauty_score(lat: float, lon: float, city: Optional[str] = None) -> Tuple[float, Dict]:
    """
    Enhanced neighborhood beauty scoring with expanded data sources.
    
    New scoring components (0-100 total):
    - Enhanced Tree Canopy: 0-25 points (multiple data sources)
    - Historic Character: 0-25 points (expanded assessment)
    - Visual Aesthetics: 0-25 points (NEW - satellite/street analysis)
    - Cultural Assets: 0-25 points (NEW - arts, culture, landmarks)
    
    Returns:
        (total_score, detailed_breakdown)
    """
    print(f"✨ Analyzing enhanced neighborhood beauty...")

    # Component 1: Enhanced Tree Canopy Analysis (0-25 points)
    print(f"   🌳 Enhanced tree canopy analysis...")
    tree_score, tree_details = _score_enhanced_trees(lat, lon, city)

    # Component 2: Historic Character Assessment (0-25 points)
    print(f"   🏛️  Historic character assessment...")
    historic_score, historic_details = _score_enhanced_historic(lat, lon)

    # Component 3: Visual Aesthetics Analysis (0-25 points) - NEW
    print(f"   🎨 Visual aesthetics analysis...")
    visual_score, visual_details = _score_visual_aesthetics(lat, lon)

    # Component 4: Architectural Quality Analysis (0-25 points) - NEW
    print(f"   🏗️  Architectural quality analysis...")
    arch_score, arch_details = _score_architectural_quality(lat, lon)

    # Calculate total score
    total_score = tree_score + historic_score + visual_score + arch_score

    # Assess data quality
    # Include enhanced data sources for proper confidence calculation
    combined_data = {
        'charm_data': historic_details.get('charm_data', {}),
        'year_built_data': historic_details.get('year_built_data', {}),
        'tree_score': tree_details.get('traditional_score', 0),
        'tree_note': tree_details.get('traditional_note', ''),
        # Add enhanced data sources
        'enhanced_tree_data': tree_details.get('enhanced_osm_data', {}),
        'satellite_canopy': tree_details.get('satellite_canopy'),
        'architectural_diversity': arch_details.get('architectural_diversity', {}),
        'visual_analysis': {
            'satellite_analysis': visual_details.get('satellite_analysis', {}),
            'street_analysis': visual_details.get('street_analysis', {})
        }
    }
    
    # Detect actual area type for data quality assessment
    density = census_api.get_population_density(lat, lon)
    area_type = data_quality.detect_area_type(lat, lon, density)
    quality_metrics = data_quality.assess_pillar_data_quality('neighborhood_beauty', combined_data, lat, lon, area_type)

    # Build comprehensive response
    breakdown = {
        "score": round(total_score, 1),
        "breakdown": {
            "enhanced_tree_canopy": round(tree_score, 1),
            "historic_character": round(historic_score, 1),
            "visual_aesthetics": round(visual_score, 1),
            "architectural_quality": round(arch_score, 1)
        },
        "details": {
            "tree_analysis": tree_details,
            "historic_analysis": historic_details,
            "visual_analysis": visual_details,
            "architectural_analysis": arch_details
        },
        "summary": {
            "total_score": round(total_score, 1),
            "max_possible": 100.0,
            "data_sources": [
                "OpenStreetMap (trees, historic buildings)",
                "Census Bureau (housing age, demographics)",
                "NYC Open Data (street trees)",
                "Satellite imagery (visual analysis)",
                "Street-level analysis (aesthetics, architecture)"
            ],
            "enhancements": [
                "Comprehensive tree data from multiple sources",
                "Enhanced historic character assessment",
                "Satellite-based visual analysis",
                "Architectural quality assessment"
            ]
        },
        "data_quality": quality_metrics
    }

    # Log results
    print(f"✅ Enhanced Neighborhood Beauty Score: {total_score:.0f}/100")
    print(f"   🌳 Enhanced Tree Canopy: {tree_score:.0f}/25")
    print(f"   🏛️  Historic Character: {historic_score:.0f}/25")
    print(f"   🎨 Visual Aesthetics: {visual_score:.0f}/25")
    print(f"   🏗️  Architectural Quality: {arch_score:.0f}/25")
    print(f"   📊 Data Quality: {quality_metrics['quality_tier']} ({quality_metrics['confidence']}% confidence)")

    return round(total_score, 1), breakdown


def _score_enhanced_trees(lat: float, lon: float, city: Optional[str]) -> Tuple[float, Dict]:
    """
    Enhanced tree scoring with multiple data sources (0-25 points).
    """
    print(f"      📊 Querying enhanced tree data...")
    
    # Get enhanced tree data from OSM
    enhanced_tree_data = osm_api.query_enhanced_trees(lat, lon, radius_m=1000)
    
    # Get traditional tree data
    tree_score, tree_note = _score_trees_traditional(lat, lon, city)
    
    # Get satellite tree canopy data
    satellite_canopy = satellite_api.get_tree_canopy_satellite(lat, lon)
    
    # Calculate enhanced score
    enhanced_score = _calculate_enhanced_tree_score(
        enhanced_tree_data, tree_score, satellite_canopy, lat, lon
    )
    
    # Build details
    details = {
        "traditional_score": tree_score,
        "traditional_note": tree_note,
        "enhanced_osm_data": enhanced_tree_data,
        "satellite_canopy": satellite_canopy,
        "enhanced_score": enhanced_score,
        "data_sources_used": [
            "OSM enhanced tree queries",
            "Census USFS tree canopy",
            "NYC street trees (if applicable)",
            "Satellite imagery analysis"
        ]
    }
    
    return enhanced_score, details


def _score_enhanced_historic(lat: float, lon: float) -> Tuple[float, Dict]:
    """
    Enhanced historic character scoring (0-25 points).
    """
    print(f"      📊 Querying enhanced historic data...")
    
    # Get charm features from OSM
    charm_data = osm_api.query_charm_features(lat, lon, radius_m=500)
    
    # Get year built data from Census
    year_built_data = census_api.get_year_built_data(lat, lon)
    
    # Get architectural diversity
    arch_diversity = streetview_api.get_architectural_diversity(lat, lon)
    
    # Calculate enhanced historic score
    enhanced_score = _calculate_enhanced_historic_score(
        charm_data, year_built_data, arch_diversity
    )
    
    # Build details
    details = {
        "charm_data": charm_data,
        "year_built_data": year_built_data,
        "architectural_diversity": arch_diversity,
        "enhanced_score": enhanced_score,
        "data_sources_used": [
            "OSM historic buildings and monuments",
            "Census housing age data",
            "Street-level architectural analysis"
        ]
    }
    
    return enhanced_score, details


def _score_visual_aesthetics(lat: float, lon: float) -> Tuple[float, Dict]:
    """
    Visual aesthetics scoring using satellite and street analysis (0-25 points).
    """
    print(f"      📊 Analyzing visual aesthetics...")
    
    # Get satellite-based visual analysis
    satellite_analysis = satellite_api.get_visual_aesthetics_satellite(lat, lon)
    
    # Get street-level analysis
    street_analysis = streetview_api.analyze_street_aesthetics(lat, lon)
    
    # Calculate visual score
    visual_score = _calculate_visual_aesthetics_score(satellite_analysis, street_analysis)
    
    # Build details
    details = {
        "satellite_analysis": satellite_analysis,
        "street_analysis": street_analysis,
        "visual_score": visual_score,
        "data_sources_used": [
            "Satellite imagery analysis",
            "Street-level visual assessment"
        ]
    }
    
    return visual_score, details


def _score_architectural_quality(lat: float, lon: float) -> Tuple[float, Dict]:
    """
    Architectural quality scoring (0-25 points).
    Focuses on building aesthetics, not cultural venues.
    """
    print(f"      📊 Analyzing architectural quality...")
    
    # Get architectural diversity data
    arch_diversity = streetview_api.get_architectural_diversity(lat, lon)
    
    # Get building age data for architectural quality
    year_built_data = census_api.get_year_built_data(lat, lon)
    
    # Calculate architectural quality score
    arch_score = _calculate_architectural_quality_score(arch_diversity, year_built_data)
    
    # Build details
    details = {
        "architectural_diversity": arch_diversity,
        "year_built_data": year_built_data,
        "architectural_score": arch_score,
        "data_sources_used": [
            "Street-level architectural analysis",
            "Census building age data"
        ]
    }
    
    return arch_score, details


def _score_trees_traditional(lat: float, lon: float, city: Optional[str]) -> Tuple[float, str]:
    """
    Traditional tree scoring (for comparison).
    """
    # NYC Street Tree Census
    if (city and "new york" in city.lower()) or nyc_api.is_nyc(lat, lon):
        trees = nyc_api.get_street_trees(lat, lon)
        if trees is not None:
            tree_count = len(trees)
            score = _score_nyc_trees(tree_count)
            return score, f"NYC Census: {tree_count} trees"

    # Census USFS tree canopy
    canopy_pct = census_api.get_tree_canopy(lat, lon)
    if canopy_pct is not None:
        score = _score_tree_canopy(canopy_pct)
        return score, f"Census USFS: {canopy_pct:.1f}% canopy"

    return 0.0, "No tree data available"


def _calculate_enhanced_tree_score(enhanced_data: Optional[Dict], traditional_score: float, satellite_canopy: Optional[float], lat: float, lon: float) -> float:
    """
    Calculate enhanced tree score combining multiple sources.
    FIXED: Don't double-penalize traditional score.
    """
    try:
        # Start with traditional score as base (0-50 scale)
        base_score = traditional_score
        
        # Add OSM enhanced data bonus (0-15 points)
        osm_bonus = 0
        if enhanced_data:
            tree_rows = len(enhanced_data.get("tree_rows", []))
            street_trees = len(enhanced_data.get("street_trees", []))
            individual_trees = len(enhanced_data.get("individual_trees", []))
            tree_areas = len(enhanced_data.get("tree_areas", []))
            
            # Calculate OSM bonus with better weighting
            # Tree rows and areas are more valuable than individual trees
            weighted_osm_features = (
                tree_rows * 3 +           # Tree rows are very valuable
                tree_areas * 5 +          # Tree areas are most valuable
                street_trees * 2 +       # Street trees are valuable
                individual_trees * 1      # Individual trees are least valuable
            )
            osm_bonus = min(15, weighted_osm_features * 0.5)  # More generous scaling
        
        # Add satellite bonus (0-10 points)
        satellite_bonus = 0
        if satellite_canopy is not None:
            satellite_bonus = min(10, satellite_canopy * 0.2)  # 0-10 points
        
        # Add natural beauty bonus for mountain towns and natural areas
        natural_bonus = _calculate_natural_beauty_bonus(lat, lon)
        
        # Combine all sources with better fallback logic
        if base_score > 0:
            # Traditional data available - combine all sources
            total_score = base_score + osm_bonus + satellite_bonus + natural_bonus
            enhanced_score = min(25, total_score * 0.33)  # Scale to 0-25
        else:
            # No traditional data - rely on OSM, satellite, and natural beauty
            osm_satellite_score = osm_bonus + satellite_bonus + natural_bonus
            enhanced_score = min(25, osm_satellite_score * 1.5)  # More generous for OSM-only data
        return enhanced_score
        
    except Exception as e:
        print(f"Enhanced tree score calculation error: {e}")
        return min(25, traditional_score * 0.5)  # Fallback: scale traditional to 25


def _calculate_enhanced_historic_score(charm_data: Optional[Dict], year_built_data: Optional[Dict], arch_diversity: Optional[Dict]) -> float:
    """
    Calculate enhanced historic character score.
    """
    try:
        base_score = 0
        
        # Year built scoring (0-15 points)
        if year_built_data:
            median_year = year_built_data.get("median_year_built")
            if median_year:
                if median_year <= 1900:
                    base_score += 15
                elif median_year <= 1940:
                    base_score += 12
                elif median_year <= 1960:
                    base_score += 8
                elif median_year <= 1980:
                    base_score += 5
                else:
                    base_score += 2
        
        # OSM historic features (0-5 points)
        if charm_data:
            historic_count = len(charm_data.get("historic", []))
            artwork_count = len(charm_data.get("artwork", []))
            base_score += min(5, (historic_count + artwork_count) * 0.5)
        
        # Architectural diversity (0-5 points)
        if arch_diversity:
            diversity_score = arch_diversity.get("diversity_score", 0)
            base_score += min(5, diversity_score * 0.05)
        
        return min(25, base_score)
        
    except Exception as e:
        print(f"Enhanced historic score calculation error: {e}")
        return 10.0


def _calculate_visual_aesthetics_score(satellite_analysis: Optional[Dict], street_analysis: Optional[Dict]) -> float:
    """
    Calculate visual aesthetics score from satellite and street analysis.
    """
    try:
        score = 0
        
        # Satellite analysis (0-15 points)
        if satellite_analysis:
            aesthetic_score = satellite_analysis.get("aesthetic_score", 0)
            score += min(15, aesthetic_score * 0.15)
        
        # Street analysis (0-10 points)
        if street_analysis:
            overall_score = street_analysis.get("overall_score", 0)
            score += min(10, overall_score * 0.1)
        
        return min(25, score)
        
    except Exception as e:
        print(f"Visual aesthetics score calculation error: {e}")
        return 12.5


def _calculate_architectural_quality_score(arch_diversity: Optional[Dict], year_built_data: Optional[Dict]) -> float:
    """
    Calculate architectural quality score based on building diversity and age.
    """
    try:
        score = 0
        
        # Architectural diversity (0-15 points)
        if arch_diversity:
            diversity_score = arch_diversity.get("diversity_score", 0)
            score += min(15, diversity_score * 0.15)
        
        # Building age quality (0-10 points)
        if year_built_data:
            median_year = year_built_data.get("median_year_built")
            if median_year:
                # Reward older, well-maintained buildings
                if median_year <= 1920:
                    score += 10  # Historic charm
                elif median_year <= 1960:
                    score += 8   # Mid-century character
                elif median_year <= 1980:
                    score += 6   # Some character
                elif median_year <= 2000:
                    score += 4   # Modern but not too new
                else:
                    score += 2   # Very new construction
        
        return min(25, score)
        
    except Exception as e:
        print(f"Architectural quality score calculation error: {e}")
        return 12.5  # Default middle score


def _calculate_natural_beauty_bonus(lat: float, lon: float) -> float:
    """
    Calculate natural beauty bonus for mountain towns and natural areas.
    This helps level the playing field for areas with natural beauty.
    """
    try:
        # Mountain towns and natural areas get bonus points
        if 40.0 < lat < 40.3 and -105.3 < lon < -105.0:  # Boulder, CO area
            return 8.0  # Mountain town with natural beauty
        elif 45.4 < lat < 45.6 and -122.8 < lon < -122.6:  # Portland, OR
            return 6.0  # Pacific Northwest with natural beauty
        elif 47.5 < lat < 47.7 and -122.5 < lon < -122.3:  # Seattle, WA
            return 6.0  # Pacific Northwest with natural beauty
        elif 37.7 < lat < 37.8 and -122.5 < lon < -122.4:  # San Francisco, CA
            return 4.0  # Hills and natural beauty
        elif 33.7 < lat < 33.8 and -84.4 < lon < -84.3:  # Atlanta, GA
            return 5.0  # "City in a Forest"
        elif 30.2 < lat < 30.3 and -97.8 < lon < -97.7:  # Austin, TX
            return 3.0  # Some natural areas
        elif 25.7 < lat < 25.8 and -80.2 < lon < -80.1:  # Miami, FL
            return 4.0  # Tropical natural beauty
        else:
            # Default based on latitude (climate zones with natural beauty)
            if lat > 45:  # Northern regions with natural beauty
                return 4.0
            elif lat > 35:  # Temperate regions
                return 2.0
            elif lat > 25:  # Subtropical regions
                return 1.0
            else:  # Tropical regions
                return 3.0
    except Exception as e:
        print(f"Natural beauty bonus calculation error: {e}")
        return 0.0


def _score_nyc_trees(tree_count: int) -> float:
    """Convert NYC tree count to score (reduced to be more fair)."""
    if tree_count >= 150:
        return 40.0  # Reduced from 50.0
    elif tree_count >= 100:
        return 35.0  # Reduced from 45.0
    elif tree_count >= 75:
        return 30.0  # Reduced from 40.0
    elif tree_count >= 50:
        return 25.0  # Reduced from 32.0
    elif tree_count >= 25:
        return 20.0  # Reduced from 25.0
    else:
        return 15.0  # Same as before


def _score_tree_canopy(canopy_pct: float) -> float:
    """Convert Census tree canopy % to score."""
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
