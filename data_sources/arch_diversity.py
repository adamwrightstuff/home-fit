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
        q = f"""
        [out:json][timeout:30];
        (
          node["building"](around:{radius_m},{lat},{lon});
          way["building"](around:{radius_m},{lat},{lon});
          relation["building"](around:{radius_m},{lat},{lon});
        );
        out tags bb;
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

    # Building levels histogram (bins)
    bins = {"1":0, "2":0, "3-4":0, "5-8":0, "9+":0}
    types = {}
    areas = []
    for e in elements:
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
        # Approx area from bbox if present
        if all(k in e for k in ("minlat","minlon","maxlat","maxlon")):
            dlat = abs(e["maxlat"] - e["minlat"]) * 111000
            dlon = abs(e["maxlon"] - e["minlon"]) * 85000  # rough at mid-lat
            areas.append(max(1.0, dlat * dlon))

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
    density: Optional[float] = None
) -> float:
    """
    Convert architectural diversity metrics to beauty score (0-33 points).
    
    Core principle: Beauty emerges when variety and coherence are in equilibrium,
    scaled appropriately to the density of place.
    
    As density increases → coherence matters more
    As density decreases → variation matters more
    
    Args:
        levels_entropy: Height diversity (0-100)
        building_type_diversity: Type diversity (0-100)
        footprint_area_cv: Size variation (0-100)
        area_type: 'urban_core', 'suburban', 'exurban', 'rural', 'unknown'
        density: Optional population density for fine-tuning
    
    Returns:
        Beauty score out of 33 points (can be added as 3rd component to beauty pillar)
    """
    
    height_beauty = _score_height_diversity(levels_entropy, area_type)
    type_beauty = _score_type_diversity(building_type_diversity, area_type)
    footprint_beauty = _score_footprint_variation(footprint_area_cv, area_type)
    
    total_beauty = height_beauty + type_beauty + footprint_beauty
    return min(33.0, max(0.0, total_beauty))


def _score_height_diversity(levels_entropy: float, area_type: str) -> float:
    """
    Score height diversity with context-aware sweet spots.
    
    Urban: Some height variation adds visual rhythm (sweet spot ~40-70)
    Suburban: Less variation feels calmer (sweet spot ~20-50)
    Rural: Minimal diversity looks most natural (sweet spot ~0-30)
    """
    if area_type == "urban_core":
        # Urban: Moderate to high variation is beautiful
        # Sweet spot around 50-70, penalize too uniform (<20) or too chaotic (>80)
        if 40 <= levels_entropy <= 80:
            score = 11.0 * (1 - abs(levels_entropy - 60) / 40)
        elif levels_entropy < 20:
            score = levels_entropy * 0.3  # Too uniform = low beauty
        elif 20 <= levels_entropy < 40:
            # Moderate-low diversity - still some beauty but less optimal
            score = 11.0 * (levels_entropy - 20) / 20  # Linear interpolation from 0 to 11
        else:  # >80, too chaotic
            score = 11.0 - (levels_entropy - 80) * 0.2
        return max(0.0, min(11.0, score))  # Cap at 11.0
    
    elif area_type == "suburban":
        # Suburban: Less variation is more cohesive and beautiful
        # Sweet spot around 20-50, penalize high variation (>70)
        if 20 <= levels_entropy <= 50:
            score = 11.0 * (1 - abs(levels_entropy - 35) / 30)
        elif levels_entropy < 20:
            score = levels_entropy * 0.4  # Very uniform = moderate beauty
        else:  # >50, too varied
            score = 11.0 - (levels_entropy - 50) * 0.15
        return max(0.0, min(11.0, score))
    
    elif area_type == "exurban":
        # Exurban: Similar to suburban but even lower variation preferred
        if 10 <= levels_entropy <= 40:
            score = 11.0 * (1 - abs(levels_entropy - 25) / 30)
        elif levels_entropy < 10:
            score = levels_entropy * 0.5  # Very uniform = moderate beauty
        else:  # >40
            score = 11.0 - (levels_entropy - 40) * 0.2
        return max(0.0, min(11.0, score))
    
    else:  # rural or unknown
        # Rural: Minimal diversity looks most natural
        # Sweet spot very low (0-30), penalize any significant variation
        if levels_entropy <= 30:
            score = 11.0 * (1 - levels_entropy / 30)
        else:
            score = max(0.0, 11.0 - (levels_entropy - 30) * 0.3)
        return max(0.0, min(11.0, score))


def _score_type_diversity(building_type_diversity: float, area_type: str) -> float:
    """
    Score building type diversity with context-aware expectations.
    
    Urban: High diversity is beautiful (shops, homes, civic buildings)
    Suburban: Moderate diversity within shared language
    Rural: Low diversity with typological consistency
    """
    if area_type == "urban_core":
        # Urban: Higher diversity is beautiful, but cap around 80-90
        # Sweet spot 60-90
        if 60 <= building_type_diversity <= 90:
            score = 11.0
        elif building_type_diversity < 60:
            # Lower diversity still valuable in cities, but less optimal
            score = 11.0 * (building_type_diversity / 60)
        else:  # >90, slightly chaotic
            score = 11.0 - (building_type_diversity - 90) * 0.1
        return max(0.0, min(11.0, score))
    
    elif area_type == "suburban":
        # Suburban: Moderate diversity within shared language
        # Sweet spot around 40-70
        if 40 <= building_type_diversity <= 70:
            score = 11.0 * (1 - abs(building_type_diversity - 55) / 30)
        elif building_type_diversity < 40:
            score = building_type_diversity * 0.25
        else:  # >70, too varied for suburban character
            score = 11.0 - (building_type_diversity - 70) * 0.2
        return max(0.0, min(11.0, score))
    
    elif area_type == "exurban":
        # Exurban: Lower diversity preferred
        if 20 <= building_type_diversity <= 50:
            score = 11.0 * (1 - abs(building_type_diversity - 35) / 30)
        elif building_type_diversity < 20:
            score = building_type_diversity * 0.4
        else:  # >50
            score = 11.0 - (building_type_diversity - 50) * 0.25
        return max(0.0, score)
    
    else:  # rural or unknown
        # Rural: Low diversity with typological consistency is beautiful
        # Sweet spot very low (0-40)
        if building_type_diversity <= 40:
            score = 11.0 * (1 - building_type_diversity / 40)
        else:
            score = max(0.0, 11.0 - (building_type_diversity - 40) * 0.3)
        return max(0.0, min(11.0, score))


def _score_footprint_variation(footprint_area_cv: float, area_type: str) -> float:
    """
    Score footprint variation with context-aware expectations.
    
    Urban: Moderate variation is balanced; too much disrupts walkability
    Suburban: Variation adds richness and individuality
    Rural: Large variation (barns, cottages, outbuildings) feels organic
    """
    if area_type == "urban_core":
        # Urban: Moderate variation is balanced
        # Sweet spot around 40-60, penalize too uniform or too chaotic
        if 40 <= footprint_area_cv <= 60:
            score = 11.0
        elif footprint_area_cv < 40:
            # Too uniform = lower beauty
            score = 11.0 * (footprint_area_cv / 40)
        else:  # >60, too chaotic, disrupts walkability
            score = 11.0 - (footprint_area_cv - 60) * 0.2
        return max(0.0, min(11.0, score))
    
    elif area_type == "suburban":
        # Suburban: Variation adds richness
        # Sweet spot around 50-80
        if 50 <= footprint_area_cv <= 80:
            score = 11.0 * (1 - abs(footprint_area_cv - 65) / 30)
        elif footprint_area_cv < 50:
            score = footprint_area_cv * 0.18
        else:  # >80, too much
            score = 11.0 - (footprint_area_cv - 80) * 0.15
        return max(0.0, min(11.0, score))
    
    elif area_type == "exurban":
        # Exurban: Moderate to high variation can be beautiful
        if 40 <= footprint_area_cv <= 90:
            score = 11.0 * (1 - abs(footprint_area_cv - 65) / 50)
        elif footprint_area_cv < 40:
            score = footprint_area_cv * 0.2
        else:  # >90
            score = 11.0 - (footprint_area_cv - 90) * 0.1
        return max(0.0, score)
    
    else:  # rural or unknown
        # Rural: Large variation feels organic and fitting
        # Sweet spot higher (60-100)
        if 60 <= footprint_area_cv <= 100:
            score = 11.0 * (1 - abs(footprint_area_cv - 80) / 40)
        elif footprint_area_cv < 60:
            score = footprint_area_cv * 0.15
        else:
            score = 11.0
        return max(0.0, min(11.0, score))

