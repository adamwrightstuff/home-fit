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
        # Rescale CV based on observed distribution (95th percentile ~3.0 CV in practice)
        # This makes 100 truly mean "extremely inconsistent" not just "maxed out"
        # Typical CV values: 0.0-0.5 = very consistent, 0.5-1.5 = moderate, 1.5-3.0 = high, 3.0+ = extreme
        # Map to 0-100 scale where ~95th percentile (CV=3.0) maps to 95
        if cv <= 3.0:
            area_cv = (cv / 3.0) * 95  # Scale 0-3.0 CV to 0-95
        else:
            area_cv = 95 + min(5.0, (cv - 3.0) / 3.0 * 5.0)  # Scale 3.0+ CV to 95-100
        area_cv = max(0.0, min(100.0, area_cv))
    else:
        area_cv = 0.0

    diversity_score = min(100.0, 0.4*levels_entropy + 0.4*type_div + 0.2*area_cv)
    
    # Calculate built coverage ratio: sum of building areas / circle land area
    # This helps identify urban areas with lots of voids (low coverage = fragmented, less beautiful)
    circle_area_sqm = math.pi * (radius_m ** 2)
    total_built_area_sqm = sum(areas) if areas else 0.0
    built_coverage_ratio = (total_built_area_sqm / circle_area_sqm) if circle_area_sqm > 0 else 0.0

    return {
        "levels_entropy": round(levels_entropy, 1),
        "building_type_diversity": round(type_div, 1),
        "footprint_area_cv": round(area_cv, 1),
        "diversity_score": round(diversity_score, 1),
        "built_coverage_ratio": round(built_coverage_ratio, 3)  # 0.0-1.0 scale
    }


# Simplified scoring configuration
DENSITY_MULTIPLIER = {
    "urban_core": 1.00,
    "urban_residential": 1.00,
    "suburban": 1.00,
    "exurban": 1.15,
    "rural": 1.20,
    "urban_core_lowrise": 1.00,
    "unknown": 1.00,
}

# Context-biased target bands: (good_low, plateau_low, plateau_high, good_high)
# Plateau range gets full points; beyond good_* ramps down to 0
CONTEXT_TARGETS = {
    "urban_residential": {
        "height": (0, 0, 15, 30),      # uniform best
        "type": (0, 0, 20, 40),        # uniform types best
        "footprint": (20, 40, 60, 95), # low/moderate variation best (broadened to 95)
    },
    "urban_core": {
        "height": (30, 40, 70, 80),    # moderate variation best
        "type": (50, 60, 85, 95),      # higher diversity best
        "footprint": (30, 40, 60, 70), # moderate variation best
    },
    "urban_core_lowrise": {
        "height": (20, 30, 60, 80),
        "type": (40, 55, 80, 95),
        "footprint": (30, 40, 60, 75),
    },
    "suburban": {
        "height": (0, 10, 40, 50),     # lower variation best
        "type": (18, 35, 55, 70),      # moderate best (relaxed from 20 to help Carmel)
        "footprint": (40, 55, 75, 90), # moderate-high best
    },
    "exurban": {
        "height": (0, 5, 35, 40),
        "type": (0, 10, 40, 50),
        "footprint": (50, 65, 95, 100),
    },
    "rural": {
        "height": (0, 5, 30, 40),
        "type": (0, 10, 35, 50),
        "footprint": (50, 70, 100, 100),
    },
}


def _score_band(value: float, band: tuple, max_points: float = 11.0) -> float:
    """Score a value within a context band. Plateau range gets full points."""
    lo, p_lo, p_hi, hi = band
    if p_lo <= value <= p_hi:
        return max_points
    if value < p_lo:
        span = max(p_lo - lo, 1e-6)
        return max(0.0, max_points * (value - lo) / span)
    # value > p_hi
    span = max(hi - p_hi, 1e-6)
    return max(0.0, max_points * (hi - value) / span)


def _coherence_bonus(levels_entropy: float, footprint_cv: float, area_type: str) -> float:
    """Simple coherence bonus: low height + low footprint for context."""
    t = CONTEXT_TARGETS.get(area_type, CONTEXT_TARGETS["urban_core"])
    h_band = t["height"]
    f_band = t["footprint"]
    # Check if both are in the plateau range (or close to it)
    h_ok = levels_entropy <= max(h_band[2], (h_band[1] + h_band[2]) / 2)
    f_ok = footprint_cv <= max(f_band[2], (f_band[1] + f_band[2]) / 2)
    if h_ok and f_ok:
        return 3.0
    if h_ok or f_ok:
        return 1.5
    return 0.0


def _context_penalty(area_type: str, built_cov: Optional[float],
                     levels_entropy: float, type_div: float) -> float:
    """Exactly one penalty by context."""
    if area_type in ("urban_core", "urban_core_lowrise"):
        if built_cov is None:
            return 0.0
        # Stronger penalty the emptier the ground plane
        if built_cov < 0.15:
            return 5.0
        if built_cov < 0.25:
            return 3.5
        if built_cov < 0.35:
            return 1.5
        return 0.0
    if area_type == "suburban":
        # Cookie-cutter signal: very uniform height + very uniform types
        # Threshold aligned with type target lower bound (18)
        if levels_entropy < 5 and type_div < 18:
            return 4.5
        if levels_entropy < 10 and type_div < 22:
            return 2.5
        return 0.0
    # No penalties for urban_residential, rural, exurban
    return 0.0


def score_architectural_diversity_as_beauty(
    levels_entropy: float,
    building_type_diversity: float,
    footprint_area_cv: float,
    area_type: str,
    density: Optional[float] = None,
    built_coverage_ratio: Optional[float] = None
) -> float:
    """
    Convert architectural diversity metrics to beauty score (0-33 points).
    
    Simplified approach:
    - Context-biased scoring (different targets per area type)
    - One coherence bonus (works across all types)
    - One penalty per area type context
    - Density multiplier for rural/exurban
    - Cap at 33
    
    Args:
        levels_entropy: Height diversity (0-100)
        building_type_diversity: Type diversity (0-100)
        footprint_area_cv: Size variation (0-100)
        area_type: 'urban_core', 'suburban', 'exurban', 'rural', 'unknown'
        density: Optional population density for fine-tuning
        built_coverage_ratio: Optional built coverage ratio (0.0-1.0)
    
    Returns:
        Beauty score out of 33 points
    """
    # Subtype detection: urban_residential as tilt
    effective = area_type
    if area_type == "urban_core" and density:
        if density > 10000 and levels_entropy < 20 and building_type_diversity < 30:
            effective = "urban_residential"
        elif 2500 <= density < 10000:
            effective = "urban_core_lowrise"
    
    # Get context-biased targets
    targets = CONTEXT_TARGETS.get(effective, CONTEXT_TARGETS["urban_core"])
    
    # Score each metric
    height_pts = _score_band(levels_entropy, targets["height"])
    type_pts = _score_band(building_type_diversity, targets["type"])
    foot_pts = _score_band(footprint_area_cv, targets["footprint"])
    
    # Cap single-metric dominance (max 13.2 each = 40% of 33)
    height_pts = min(13.2, height_pts)
    type_pts = min(13.2, type_pts)
    foot_pts = min(13.2, foot_pts)
    
    # Base total
    base = height_pts + type_pts + foot_pts
    
    # One bonus, one penalty
    bonus = _coherence_bonus(levels_entropy, footprint_area_cv, effective)
    penalty = _context_penalty(effective, built_coverage_ratio,
                               levels_entropy, building_type_diversity)
    
    total = base + bonus - penalty
    
    # Density multiplier (simple banding)
    mult = DENSITY_MULTIPLIER.get(effective, 1.0)
    total *= mult
    
    # Cap at 33
    return max(0.0, min(33.0, total))
