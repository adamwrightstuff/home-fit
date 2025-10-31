"""
Architectural Diversity (Sandbox)
Computes simple diversity metrics from OSM buildings within a radius.
This module is sandbox-only and not wired into scoring by default.
"""

from typing import Dict, Optional
import requests

from .osm_api import OVERPASS_URL


def compute_arch_diversity(lat: float, lon: float, radius_m: int = 1000) -> Dict[str, float]:
    """
    Return a dict with sandbox metrics (0-100 scaled where applicable):
    - levels_entropy
    - building_type_diversity
    - footprint_area_cv
    - diversity_score (aggregated, naive)
    """
    try:
        # Query for ways (buildings are usually ways with geometry)
        q = f"""
        [out:json][timeout:30];
        (
          way["building"](around:{radius_m},{lat},{lon});
        );
        out body;
        >;
        out skel qt;
        """
        # Retry logic similar to other OSM queries
        import time
        resp = None
        for attempt in range(3):
            try:
                resp = requests.post(OVERPASS_URL, data={"data": q}, timeout=40, headers={"User-Agent":"HomeFit/1.0"})
                if resp.status_code == 200:
                    break
                elif attempt < 2:
                    time.sleep(0.8 * (1.5 ** attempt))  # Exponential backoff
            except Exception as retry_e:
                if attempt == 2:
                    raise retry_e
                time.sleep(0.8 * (1.5 ** attempt))
        
        if not resp or resp.status_code != 200:
            status_msg = f"status {resp.status_code}" if resp else "no response"
            print(f"⚠️  Overpass API returned {status_msg}")
            return {"levels_entropy":0, "building_type_diversity":0, "footprint_area_cv":0, "diversity_score":0, "error": f"API {status_msg}"}
        elements = resp.json().get("elements", [])
        if not elements:
            print(f"⚠️  No building elements found in OSM query (radius: {radius_m}m)")
            return {"levels_entropy":0, "building_type_diversity":0, "footprint_area_cv":0, "diversity_score":0, "note": "No buildings found in OSM"}
    except Exception as e:
        print(f"⚠️  OSM building query error: {e}")
        return {"levels_entropy":0, "building_type_diversity":0, "footprint_area_cv":0, "diversity_score":0, "error": str(e)}

    import math
    def entropy(counts):
        s = sum(counts)
        if s <= 0:
            return 0.0
        e = 0.0
        for c in counts:
            if c > 0:
                p = c / s
                e -= p * math.log(p + 1e-12, 2)
        # normalize by max possible for N bins
        if len(counts) > 1:
            e /= math.log(len(counts), 2)
        return max(0.0, min(1.0, e))

    # Separate ways and nodes
    ways = [e for e in elements if e.get("type") == "way"]
    nodes_dict = {e.get("id"): e for e in elements if e.get("type") == "node"}
    
    # Building levels histogram (bins)
    bins = {"1":0, "2":0, "3-4":0, "5-8":0, "9+":0}
    types = {}
    areas = []
    
    for e in ways:
        tags = e.get("tags", {})
        btype = tags.get("building") or "unknown"
        types[btype] = types.get(btype, 0) + 1
        
        lv_raw = tags.get("building:levels")
        try:
            lv = int(lv_raw) if lv_raw is not None else None
        except Exception:
            lv = None
        if lv is None:
            bins["1"] += 1
        elif lv == 1:
            bins["1"] += 1
        elif lv == 2:
            bins["2"] += 1
        elif 3 <= lv <= 4:
            bins["3-4"] += 1
        elif 5 <= lv <= 8:
            bins["5-8"] += 1
        else:
            bins["9+"] += 1
        
        # Calculate area from way geometry (polygon)
        if "geometry" in e and e["geometry"]:
            coords = [(point.get("lat"), point.get("lon")) for point in e["geometry"] 
                     if "lat" in point and "lon" in point]
            if len(coords) >= 3:
                # Calculate polygon area using shoelace formula
                area = 0.0
                for i in range(len(coords)):
                    j = (i + 1) % len(coords)
                    area += coords[i][0] * coords[j][1]
                    area -= coords[j][0] * coords[i][1]
                area = abs(area) / 2.0
                # Convert to square meters (approximate at this latitude)
                # Using average of lat/lon degrees to meters at this latitude
                area_sqm = area * 111000 * 111000 * math.cos(math.radians(lat))
                if area_sqm > 1.0:  # Only include if area is reasonable
                    areas.append(area_sqm)
        elif "nodes" in e:
            # Fallback: try to calculate from node coordinates
            way_nodes = [nodes_dict.get(nid) for nid in e.get("nodes", []) if nid in nodes_dict]
            coords = [(n.get("lat"), n.get("lon")) for n in way_nodes 
                     if "lat" in n and "lon" in n]
            if len(coords) >= 3:
                area = 0.0
                for i in range(len(coords)):
                    j = (i + 1) % len(coords)
                    area += coords[i][0] * coords[j][1]
                    area -= coords[j][0] * coords[i][1]
                area = abs(area) / 2.0
                area_sqm = area * 111000 * 111000 * math.cos(math.radians(lat))
                if area_sqm > 1.0:
                    areas.append(area_sqm)

    levels_entropy = entropy(list(bins.values())) * 100
    type_div = entropy(list(types.values())) * 100
    if len(areas) >= 2:
        mean_area = sum(areas)/len(areas)
        var = sum((a-mean_area)**2 for a in areas)/len(areas)
        cv = (var ** 0.5) / mean_area
        area_cv = max(0.0, min(1.0, cv)) * 100
    else:
        area_cv = 0.0

    diversity_score = min(100.0, 0.4*levels_entropy + 0.4*type_div + 0.2*area_cv)

    return {
        "levels_entropy": round(levels_entropy, 1),
        "building_type_diversity": round(type_div, 1),
        "footprint_area_cv": round(area_cv, 1),
        "diversity_score": round(diversity_score, 1)
    }


def score_architectural_diversity_as_beauty(
    levels_entropy: float,
    building_type_diversity: float,
    footprint_area_cv: float,
    area_type: str,
    density: Optional[float] = None,
    tree_coverage: Optional[float] = None,
    historic_score: Optional[float] = None
) -> float:
    """
    Convert architectural diversity metrics to beauty score (0-33 points).
    
    Core principle: Beauty emerges when variety and coherence are in equilibrium,
    scaled appropriately to the density of place.
    
    Improvements:
    - Broader sweet spot tolerance bands
    - Softer penalty curves (gradual decline)
    - Coherence bonus for architecturally consistent areas
    - Balanced weighting to prevent single-metric dominance
    - Normalized scale across contexts
    - Urban residential detection (dense residential neighborhoods like Park Slope)
    - Fabric integrity bonus for cohesive architectural fabrics
    
    Args:
        levels_entropy: Height diversity (0-100)
        building_type_diversity: Type diversity (0-100)
        footprint_area_cv: Size variation (0-100)
        area_type: 'urban_core', 'suburban', 'exurban', 'rural', 'unknown'
        density: Optional population density for fine-tuning
        tree_coverage: Optional tree canopy percentage (0-100) to amplify coherence
        historic_score: Optional historic preservation score (0-100) to amplify coherence
    
    Returns:
        Beauty score out of 33 points (can be added as 3rd component to beauty pillar)
    """
    
    # Detect urban_residential: dense residential districts (e.g., Park Slope)
    # Conditions: High density (>10,000) + Low height diversity (<20) + Low type diversity (<30)
    effective_area_type = area_type
    if area_type == "urban_core" and density:
        if density > 10000 and levels_entropy < 20 and building_type_diversity < 30:
            # Dense residential district - coherence is beautiful
            effective_area_type = "urban_residential"
        elif 2500 <= density < 10000:
            # Low-rise urban core - use modified expectations
            effective_area_type = "urban_core_lowrise"
    
    height_beauty = _score_height_diversity(levels_entropy, effective_area_type)
    type_beauty = _score_type_diversity(building_type_diversity, effective_area_type)
    footprint_beauty = _score_footprint_variation(footprint_area_cv, effective_area_type)
    
    # Cap single-metric dominance: no single factor > 40% of total (13.2/33)
    height_beauty = min(13.2, height_beauty)
    type_beauty = min(13.2, type_beauty)
    footprint_beauty = min(13.2, footprint_beauty)
    
    total_beauty = height_beauty + type_beauty + footprint_beauty
    
    # Add coherence bonus for architecturally consistent areas
    # Low height entropy + low footprint variation + moderate density = cohesive
    coherence_bonus = _calculate_coherence_bonus(levels_entropy, footprint_area_cv, area_type, density)
    
    # Add fabric integrity bonus for dense residential districts
    # Rewards alignment, scale, and material consistency
    fabric_bonus = _calculate_fabric_integrity_bonus(
        levels_entropy,
        building_type_diversity,
        footprint_area_cv,
        effective_area_type,
        tree_coverage,
        historic_score
    )
    
    total_beauty += coherence_bonus + fabric_bonus
    
    # Normalize scale across contexts: ensure top performers can reach similar high scores
    # Context normalization factor based on area type expectations
    normalized_beauty = _normalize_score_by_context(total_beauty, effective_area_type)
    
    return min(33.0, max(0.0, normalized_beauty))


def _score_height_diversity(levels_entropy: float, area_type: str) -> float:
    """
    Score height diversity with broadened sweet spots and softer penalties.
    
    Urban: Moderate height variation adds visual rhythm (sweet spot 30-80, wider tolerance)
    Suburban: Low variation is beautiful (sweet spot 0-50, rewards consistency)
    Rural: Minimal diversity is beautiful (sweet spot 0-40, rewards simplicity)
    """
    if area_type == "urban_residential":
        # Urban residential: Uniform heights are beautiful (Park Slope brownstones)
        # Low diversity = high beauty (inverted scoring)
        if levels_entropy < 15:
            # Very uniform = peak beauty
            score = 11.0 * (1 - levels_entropy / 20)  # More uniform = higher score
        elif 15 <= levels_entropy < 30:
            # Still coherent but some variation
            score = 11.0 * (30 - levels_entropy) / 15
        elif 30 <= levels_entropy <= 50:
            # Moderate variation - reduced beauty but not penalized harshly
            score = 11.0 * (50 - levels_entropy) / 20 * 0.7
        else:  # >50
            # Too varied for residential fabric - gradual decline
            score = max(0.0, 11.0 - (levels_entropy - 50) * 0.1)
        return max(0.0, min(13.2, score))
    
    elif area_type == "urban_core" or area_type == "urban_core_lowrise":
        # Urban: Broader sweet spot 30-80 (was 40-80)
        # Softer penalties - gradual decline instead of cliff
        if 30 <= levels_entropy <= 80:
            # Broad sweet spot with gentle peak
            if 40 <= levels_entropy <= 70:
                score = 11.0  # Full score in peak range
            elif 30 <= levels_entropy < 40:
                # Gradual ramp up
                score = 11.0 * (levels_entropy - 30) / 10
            else:  # 70 < levels_entropy <= 80
                # Gradual ramp down
                score = 11.0 * (80 - levels_entropy) / 10
        elif levels_entropy < 30:
            # Too uniform - but softer penalty (was 0.3x, now gradual)
            score = 11.0 * (levels_entropy / 30) * 0.7  # Still get some points for uniformity
        else:  # >80
            # Too chaotic - gradual decline
            score = max(0.0, 11.0 - (levels_entropy - 80) * 0.15)  # Softer than 0.2
        return max(0.0, min(13.2, score))  # Cap at 40% of total
    
    elif area_type == "suburban":
        # Suburban: Broader sweet spot 0-50 (was 20-50)
        # Low variation is beautiful and rewarded
        if 0 <= levels_entropy <= 50:
            if 10 <= levels_entropy <= 40:
                score = 11.0  # Peak range
            elif levels_entropy < 10:
                # Very uniform is beautiful in suburbs
                score = 11.0 * (1 - levels_entropy / 20)  # More uniform = higher score
            else:  # 40 < levels_entropy <= 50
                # Gradual decline
                score = 11.0 * (50 - levels_entropy) / 10
        else:  # >50
            # Too varied - gradual decline
            score = max(0.0, 11.0 - (levels_entropy - 50) * 0.1)  # Softer penalty
        return max(0.0, min(13.2, score))
    
    elif area_type == "exurban":
        # Exurban: Broader sweet spot 0-40 (was 10-40)
        if 0 <= levels_entropy <= 40:
            if 5 <= levels_entropy <= 35:
                score = 11.0
            elif levels_entropy < 5:
                score = 11.0 * (1 - levels_entropy / 10)
            else:  # 35 < levels_entropy <= 40
                score = 11.0 * (40 - levels_entropy) / 5
        else:
            score = max(0.0, 11.0 - (levels_entropy - 40) * 0.15)
        return max(0.0, min(13.2, score))
    
    else:  # rural or unknown
        # Rural: Broader sweet spot 0-40 (was 0-30)
        # Simplicity and restraint rewarded
        if levels_entropy <= 40:
            if levels_entropy <= 20:
                score = 11.0 * (1 - levels_entropy / 25)  # Very low is best
            else:  # 20 < levels_entropy <= 40
                score = 11.0 * (40 - levels_entropy) / 20
        else:
            # Extreme variation - but softer penalty
            score = max(0.0, 11.0 - (levels_entropy - 40) * 0.2)
        return max(0.0, min(13.2, score))


def _score_type_diversity(building_type_diversity: float, area_type: str) -> float:
    """
    Score building type diversity with broadened sweet spots and softer penalties.
    
    Urban: High diversity is beautiful (sweet spot 50-95, wider tolerance)
    Suburban: Moderate diversity within shared language (sweet spot 20-70)
    Rural: Low diversity with typological consistency (sweet spot 0-50)
    """
    if area_type == "urban_residential":
        # Urban residential: Low type diversity is beautiful (consistent building types)
        # Residential fabric thrives on typological consistency
        if building_type_diversity < 20:
            # Very consistent types = peak beauty
            score = 11.0 * (1 - building_type_diversity / 25)  # More consistent = higher score
        elif 20 <= building_type_diversity < 40:
            # Still coherent but some variation
            score = 11.0 * (40 - building_type_diversity) / 20
        elif 40 <= building_type_diversity <= 60:
            # Moderate variation - reduced beauty but soft penalty
            score = 11.0 * (60 - building_type_diversity) / 20 * 0.6
        else:  # >60
            # Too varied for residential fabric - gradual decline
            score = max(0.0, 11.0 - (building_type_diversity - 60) * 0.15)
        return max(0.0, min(13.2, score))
    
    elif area_type == "urban_core" or area_type == "urban_core_lowrise":
        # Urban: Broader sweet spot 50-95 (was 60-90)
        if 50 <= building_type_diversity <= 95:
            if 60 <= building_type_diversity <= 85:
                score = 11.0  # Peak range
            elif 50 <= building_type_diversity < 60:
                # Gradual ramp up
                score = 11.0 * (building_type_diversity - 50) / 10
            else:  # 85 < building_type_diversity <= 95
                # Gradual ramp down
                score = 11.0 * (95 - building_type_diversity) / 10
        elif building_type_diversity < 50:
            # Lower diversity - softer penalty, still get some points
            score = 11.0 * (building_type_diversity / 50) * 0.8  # Softer than linear
        else:  # >95
            # Very chaotic - gradual decline
            score = max(0.0, 11.0 - (building_type_diversity - 95) * 0.08)
        return max(0.0, min(13.2, score))
    
    elif area_type == "suburban":
        # Suburban: Broader sweet spot 20-70 (was 40-70)
        if 20 <= building_type_diversity <= 70:
            if 35 <= building_type_diversity <= 55:
                score = 11.0  # Peak range
            elif 20 <= building_type_diversity < 35:
                # Gradual ramp up
                score = 11.0 * (building_type_diversity - 20) / 15
            else:  # 55 < building_type_diversity <= 70
                # Gradual ramp down
                score = 11.0 * (70 - building_type_diversity) / 15
        elif building_type_diversity < 20:
            # Low diversity is okay in suburbs - softer penalty
            score = 11.0 * (building_type_diversity / 20) * 0.6
        else:  # >70
            # Too varied - gradual decline
            score = max(0.0, 11.0 - (building_type_diversity - 70) * 0.15)
        return max(0.0, min(13.2, score))
    
    elif area_type == "exurban":
        # Exurban: Broader sweet spot 10-50 (was 20-50)
        if 10 <= building_type_diversity <= 50:
            if 20 <= building_type_diversity <= 40:
                score = 11.0
            elif 10 <= building_type_diversity < 20:
                score = 11.0 * (building_type_diversity - 10) / 10
            else:  # 40 < building_type_diversity <= 50
                score = 11.0 * (50 - building_type_diversity) / 10
        elif building_type_diversity < 10:
            score = 11.0 * (building_type_diversity / 10) * 0.7
        else:  # >50
            score = max(0.0, 11.0 - (building_type_diversity - 50) * 0.2)
        return max(0.0, min(13.2, score))
    
    else:  # rural or unknown
        # Rural: Broader sweet spot 0-50 (was 0-40)
        if building_type_diversity <= 50:
            if building_type_diversity <= 25:
                score = 11.0 * (1 - building_type_diversity / 30)  # Very low is best
            else:  # 25 < building_type_diversity <= 50
                score = 11.0 * (50 - building_type_diversity) / 25
        else:
            # Extreme variation - softer penalty
            score = max(0.0, 11.0 - (building_type_diversity - 50) * 0.25)
        return max(0.0, min(13.2, score))


def _score_footprint_variation(footprint_area_cv: float, area_type: str) -> float:
    """
    Score footprint variation with broadened sweet spots and softer penalties.
    
    Urban: Moderate variation is balanced (sweet spot 30-70, wider tolerance)
    Suburban: Variation adds richness (sweet spot 40-90)
    Rural: Large variation feels organic (sweet spot 50-100)
    """
    if area_type == "urban_residential":
        # Urban residential: Similar footprints are beautiful (consistent scale)
        # Uniform footprints create visual rhythm
        if footprint_area_cv < 30:
            # Very consistent footprints = peak beauty
            score = 11.0 * (1 - footprint_area_cv / 35)  # More consistent = higher score
        elif 30 <= footprint_area_cv < 60:
            # Still coherent but some variation
            score = 11.0 * (60 - footprint_area_cv) / 30
        elif 60 <= footprint_area_cv <= 80:
            # Moderate variation - reduced beauty but soft penalty
            score = 11.0 * (80 - footprint_area_cv) / 20 * 0.6
        else:  # >80
            # Too varied for residential fabric - gradual decline
            score = max(0.0, 11.0 - (footprint_area_cv - 80) * 0.1)
        return max(0.0, min(13.2, score))
    
    elif area_type == "urban_core" or area_type == "urban_core_lowrise":
        # Urban: Broader sweet spot 30-70 (was 40-60)
        # Softer penalties for walkability disruption
        if 30 <= footprint_area_cv <= 70:
            if 40 <= footprint_area_cv <= 60:
                score = 11.0  # Peak range
            elif 30 <= footprint_area_cv < 40:
                # Gradual ramp up
                score = 11.0 * (footprint_area_cv - 30) / 10
            else:  # 60 < footprint_area_cv <= 70
                # Gradual ramp down (walkability still okay)
                score = 11.0 * (70 - footprint_area_cv) / 10
        elif footprint_area_cv < 30:
            # Too uniform - softer penalty
            score = 11.0 * (footprint_area_cv / 30) * 0.7
        else:  # >70
            # Disrupts walkability - but gradual decline
            score = max(0.0, 11.0 - (footprint_area_cv - 70) * 0.15)  # Softer than 0.2
        return max(0.0, min(13.2, score))
    
    elif area_type == "suburban":
        # Suburban: Broader sweet spot 40-90 (was 50-80)
        if 40 <= footprint_area_cv <= 90:
            if 55 <= footprint_area_cv <= 75:
                score = 11.0  # Peak range
            elif 40 <= footprint_area_cv < 55:
                # Gradual ramp up
                score = 11.0 * (footprint_area_cv - 40) / 15
            else:  # 75 < footprint_area_cv <= 90
                # Gradual ramp down
                score = 11.0 * (90 - footprint_area_cv) / 15
        elif footprint_area_cv < 40:
            # Too uniform - softer penalty
            score = 11.0 * (footprint_area_cv / 40) * 0.5
        else:  # >90
            # Too much variation - gradual decline
            score = max(0.0, 11.0 - (footprint_area_cv - 90) * 0.1)  # Softer penalty
        return max(0.0, min(13.2, score))
    
    elif area_type == "exurban":
        # Exurban: Broader sweet spot 30-95 (was 40-90)
        if 30 <= footprint_area_cv <= 95:
            if 50 <= footprint_area_cv <= 80:
                score = 11.0
            elif 30 <= footprint_area_cv < 50:
                score = 11.0 * (footprint_area_cv - 30) / 20
            else:  # 80 < footprint_area_cv <= 95
                score = 11.0 * (95 - footprint_area_cv) / 15
        elif footprint_area_cv < 30:
            score = 11.0 * (footprint_area_cv / 30) * 0.6
        else:  # >95
            score = max(0.0, 11.0 - (footprint_area_cv - 95) * 0.08)
        return max(0.0, min(13.2, score))
    
    else:  # rural or unknown
        # Rural: Broader sweet spot 50-100 (was 60-100)
        if 50 <= footprint_area_cv <= 100:
            if 65 <= footprint_area_cv <= 95:
                score = 11.0  # Peak range
            elif 50 <= footprint_area_cv < 65:
                # Gradual ramp up
                score = 11.0 * (footprint_area_cv - 50) / 15
            else:  # 95 < footprint_area_cv <= 100
                score = 11.0
        elif footprint_area_cv < 50:
            # Too uniform for rural - but softer penalty
            score = 11.0 * (footprint_area_cv / 50) * 0.4
        else:
            score = 11.0
        return max(0.0, min(13.2, score))


def _calculate_coherence_bonus(
    levels_entropy: float,
    footprint_area_cv: float,
    area_type: str,
    density: Optional[float] = None
) -> float:
    """
    Calculate coherence bonus for architecturally consistent areas.
    
    Rewards places like Park Slope brownstones where low height entropy
    + low footprint variation + moderate density = visually cohesive.
    
    Args:
        levels_entropy: Height diversity (0-100)
        footprint_area_cv: Size variation (0-100)
        area_type: Area type
        density: Optional population density
    
    Returns:
        Bonus points (0-3 max)
    """
    bonus = 0.0
    
    # Conditions for coherence bonus:
    # 1. Low height entropy (consistent heights) - < 15 for bonus
    # 2. Low footprint variation (consistent sizes) - < 30 for bonus
    # 3. Moderate to high density (urban/suburban context)
    
    height_coherent = levels_entropy < 15
    footprint_coherent = footprint_area_cv < 30
    
    if height_coherent and footprint_coherent:
        # Both conditions met - strong coherence
        if area_type == "urban_residential":
            # Urban residential consistency is highly valuable (e.g., Park Slope)
            bonus = 3.5
        elif area_type == "urban_core" or area_type == "urban_core_lowrise":
            # Urban consistency is valuable
            bonus = 3.0
        elif area_type == "suburban":
            # Suburban consistency is expected but still valuable
            bonus = 2.0
        elif area_type in ["exurban", "rural"]:
            # Rural consistency is very natural
            bonus = 1.5
    elif height_coherent or footprint_coherent:
        # Partial coherence - smaller bonus
        if area_type == "urban_residential":
            bonus = 2.0
        elif area_type == "urban_core" or area_type == "urban_core_lowrise":
            bonus = 1.5
        elif area_type == "suburban":
            bonus = 1.0
    
    return min(3.0, bonus)


def _calculate_fabric_integrity_bonus(
    levels_entropy: float,
    building_type_diversity: float,
    footprint_area_cv: float,
    effective_area_type: str,
    tree_coverage: Optional[float] = None,
    historic_score: Optional[float] = None
) -> float:
    """
    Calculate fabric integrity bonus for cohesive architectural fabrics.
    
    Rewards places like Park Slope where buildings share similar:
    - Alignment (low height entropy)
    - Scale (low footprint variation)
    - Materials (low type diversity)
    
    Tree coverage and historic preservation amplify the bonus.
    
    Args:
        levels_entropy: Height diversity (0-100)
        building_type_diversity: Type diversity (0-100)
        footprint_area_cv: Size variation (0-100)
        effective_area_type: Effective area type (may be urban_residential)
        tree_coverage: Optional tree canopy percentage (0-100)
        historic_score: Optional historic preservation score (0-100)
    
    Returns:
        Bonus points (0-4 max)
    """
    bonus = 0.0
    
    # Conditions for fabric integrity:
    # 1. Low height entropy (< 20) - consistent heights
    # 2. Low footprint variation (< 40) - consistent scale
    # 3. Low type diversity (< 35) - consistent materials
    
    height_consistent = levels_entropy < 20
    footprint_consistent = footprint_area_cv < 40
    type_consistent = building_type_diversity < 35
    
    # Base bonus for architectural consistency
    if height_consistent and footprint_consistent and type_consistent:
        # All three conditions met - strong fabric integrity
        if effective_area_type == "urban_residential":
            # Urban residential gets highest bonus (e.g., Park Slope)
            bonus = 3.0
        elif effective_area_type in ["urban_core", "urban_core_lowrise"]:
            # Urban cores get moderate bonus
            bonus = 2.0
        elif effective_area_type == "suburban":
            # Suburban gets smaller bonus (consistency expected)
            bonus = 1.5
    elif (height_consistent and footprint_consistent) or (height_consistent and type_consistent):
        # Two conditions met - partial fabric integrity
        if effective_area_type == "urban_residential":
            bonus = 2.0
        elif effective_area_type in ["urban_core", "urban_core_lowrise"]:
            bonus = 1.0
    elif height_consistent:
        # Only height consistent - minimal bonus
        if effective_area_type == "urban_residential":
            bonus = 1.0
    
    # Amplify with tree coverage (mature greenery enhances coherence)
    if bonus > 0 and tree_coverage:
        if tree_coverage >= 30:
            bonus *= 1.2  # +20% for high tree coverage
        elif tree_coverage >= 15:
            bonus *= 1.1  # +10% for moderate tree coverage
    
    # Amplify with historic preservation (historic age enhances coherence)
    if bonus > 0 and historic_score:
        if historic_score >= 70:
            bonus *= 1.2  # +20% for high historic score
        elif historic_score >= 40:
            bonus *= 1.1  # +10% for moderate historic score
    
    return min(4.0, bonus)


def _normalize_score_by_context(beauty_score: float, area_type: str) -> float:
    """
    Normalize beauty score across contexts so top performers in each
    context can reach similar high scores.
    
    A great rural town should be able to hit "9/10" just like a great
    urban core, even if the morphology is simpler.
    
    Args:
        beauty_score: Raw beauty score before normalization
        area_type: Area type for context adjustment
    
    Returns:
        Normalized beauty score (0-33)
    """
    # Base normalization: ensure scores can reach similar peaks
    # Top performers in each context should be able to score ~27-30/33
    
    # Context adjustment factors (multipliers to help lower contexts reach high scores)
    context_factors = {
        "urban_core": 1.0,           # No adjustment - already at full potential
        "urban_core_lowrise": 1.0,   # Same as urban_core
        "urban_residential": 1.0,    # Same as urban_core (dense residential)
        "suburban": 1.1,             # +10% to help great suburbs reach high scores
        "exurban": 1.15,             # +15% to help great exurban areas
        "rural": 1.2,                # +20% to help great rural towns
        "unknown": 1.0               # No adjustment if unknown
    }
    
    factor = context_factors.get(area_type, 1.0)
    normalized = beauty_score * factor
    
    # Ensure normalized score doesn't exceed max (33)
    return min(33.0, normalized)

