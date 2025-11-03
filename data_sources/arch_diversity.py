"""
Architectural Diversity (Sandbox)
Computes simple diversity metrics from OSM buildings within a radius.
This module is sandbox-only and not wired into scoring by default.
"""

from typing import Dict, Optional
import requests

from .osm_api import OVERPASS_URL, _retry_overpass


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
        def _do_request():
            return requests.post(OVERPASS_URL, data={"data": q}, timeout=40, headers={"User-Agent":"HomeFit/1.0"})
        
        # Use centralized retry logic with proper rate limit handling (aligned with other OSM queries)
        resp = _retry_overpass(_do_request, attempts=3, base_wait=1.0)
        
        if resp is None or resp.status_code != 200:
            status_msg = f"status {resp.status_code}" if resp else "no response"
            error_detail = f"API {status_msg}"
            if resp and resp.status_code == 429:
                error_detail = f"Rate limited (429) - max retries reached"
            print(f"⚠️  Overpass API returned {error_detail} for architectural diversity query")
            return {"levels_entropy":0, "building_type_diversity":0, "footprint_area_cv":0, "diversity_score":0, "error": error_detail}
        
        elements = resp.json().get("elements", [])
        if not elements:
            print(f"⚠️  No building elements found in OSM query (radius: {radius_m}m)")
            return {"levels_entropy":0, "building_type_diversity":0, "footprint_area_cv":0, "diversity_score":0, "note": "No buildings found in OSM"}
    except requests.exceptions.Timeout as e:
        print(f"⚠️  OSM building query timeout: {e}")
        return {"levels_entropy":0, "building_type_diversity":0, "footprint_area_cv":0, "diversity_score":0, "error": f"Timeout: {str(e)}"}
    except requests.exceptions.RequestException as e:
        print(f"⚠️  OSM building query network error: {e}")
        return {"levels_entropy":0, "building_type_diversity":0, "footprint_area_cv":0, "diversity_score":0, "error": f"Network error: {str(e)}"}
    except Exception as e:
        print(f"⚠️  OSM building query error: {e}")
        import traceback
        print(f"   Traceback: {traceback.format_exc()}")
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
    "urban_core_lowrise": 1.00,
    "historic_urban": 1.00,  # Organic diversity historic neighborhoods
    "suburban": 1.00,
    "exurban": 1.15,
    "rural": 1.20,
    "unknown": 1.00,
}

# Context-biased target bands: (good_low, plateau_low, plateau_high, good_high)
# Plateau range gets full points; beyond good_* ramps down to 0
CONTEXT_TARGETS = {
    "urban_residential": {
        "height": (0, 0, 15, 30),      # uniform best
        "type": (0, 0, 20, 40),        # uniform types best
        "footprint": (20, 40, 70, 85), # low/moderate variation best (expanded to help historic areas)
    },
    "urban_core": {
        "height": (30, 40, 70, 80),    # moderate variation best
        "type": (50, 60, 85, 95),      # higher diversity best
        "footprint": (30, 40, 60, 70), # moderate variation best
    },
    "urban_core_lowrise": {
        "height": (10, 20, 60, 80),  # Lower minimum to catch coastal/low-rise areas (e.g., Redondo Beach)
        "type": (40, 55, 80, 95),
        "footprint": (30, 40, 70, 90),  # More forgiving for coastal/edge city areas with varied building sizes
    },
    "historic_urban": {  # Organic diversity historic neighborhoods
        "height": (15, 20, 50, 70),      # Moderate variation (organic growth pattern)
        "type": (25, 30, 65, 85),        # Mixed-use historic neighborhoods
        "footprint": (35, 45, 70, 85),   # Organic variation (broader than urban_core)
    },
    "suburban": {
        "height": (0, 10, 40, 50),     # lower variation best
        "type": (18, 35, 55, 70),      # moderate best (relaxed from 20 to help Carmel)
        "footprint": (30, 40, 65, 80), # moderate-high best (expanded sweet spot 40-65% for suburban patterns)
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
                     levels_entropy: float, type_div: float,
                     footprint_cv: Optional[float] = None) -> float:
    """Exactly one penalty by context."""
    if area_type in ("urban_core", "urban_core_lowrise"):
        if built_cov is None:
            return 0.0
        # Stronger penalty the emptier the ground plane
        # urban_core_lowrise gets slightly more lenient penalties (coastal/edge cities often have lower coverage)
        if area_type == "urban_core_lowrise":
            if built_cov < 0.15:
                return 4.5  # Slightly more lenient
            if built_cov < 0.25:
                return 2.5  # More lenient for low-rise areas
            if built_cov < 0.35:
                return 1.0
            return 0.0
        else:  # urban_core
            if built_cov < 0.15:
                return 5.0
            if built_cov < 0.25:
                return 3.5
            if built_cov < 0.35:
                return 1.5
            return 0.0
    # historic_urban: No coverage penalty (organic voids like courtyards/gardens are beautiful)
    if area_type == "historic_urban":
        return 0.0
    if area_type == "suburban":
        # Cookie-cutter signal: very uniform height + very uniform types + HIGH footprint CV (fragmented)
        # Only penalize if footprint CV is high (>80) = fragmented sprawl, not cohesive
        # Low footprint CV = cohesive/intentional uniformity (e.g., Carmel-by-the-Sea)
        if footprint_cv is not None and footprint_cv > 80:
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
    built_coverage_ratio: Optional[float] = None,
    historic_landmarks: Optional[int] = None,
    median_year_built: Optional[int] = None
) -> float:
    """
    Convert architectural diversity metrics to beauty score (0-33 points).
    
    Simplified approach:
    - Context-biased scoring (different targets per area type)
    - Conditional adjustments for historic organic development
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
        historic_landmarks: Optional count of historic landmarks from OSM
        median_year_built: Optional median year buildings were built
    
    Returns:
        Beauty score out of 33 points
    """
    # Subtype detection: use centralized helper function
    from .data_quality import get_effective_area_type
    effective = get_effective_area_type(
        area_type,
        density,
        levels_entropy,
        building_type_diversity,
        historic_landmarks=historic_landmarks,
        median_year_built=median_year_built
    )
    
    # Get base context-biased targets
    targets = CONTEXT_TARGETS.get(effective, CONTEXT_TARGETS["urban_core"])
    targets = dict(targets)  # Copy to avoid mutating original
    
    # CONTEXTUAL ADJUSTMENTS: Apply in order of specificity (most specific last)
    # These adjustments handle historic organic development patterns
    
    # Detect historic status
    is_historic = False
    is_very_historic = False
    
    if historic_landmarks is not None and historic_landmarks >= 10:
        is_historic = True
    if median_year_built is not None and median_year_built < 1960:
        is_historic = True
    
    if historic_landmarks is not None and historic_landmarks >= 15:
        is_very_historic = True
    if median_year_built is not None and median_year_built < 1940:
        is_very_historic = True
    
    # Adjustment 1: Historic organic growth
    # Historic areas with high footprint CV = organic irregular lots = beautiful
    # Examples: Georgetown (93.3%), French Quarter (~85%), Old Town Alexandria
    # High footprint CV in historic areas reflects centuries of organic growth
    if is_historic and footprint_area_cv > 70:
        targets["footprint"] = (50, 65, 95, 100)  # HIGH CV is GOOD for historic areas
    
    # Adjustment 2: Very historic urban_residential
    # Very old neighborhoods can have slightly higher type diversity and still be beautiful
    # Examples: Georgetown (1938, type 31.8)
    # This aligns scoring with classification logic (allows type < 35 for very historic)
    if is_very_historic and effective == "urban_residential":
        targets["type"] = (0, 0, 35, 50)  # Allow up to 35 in sweet spot (expanded from 20)
    
    # Adjustment 3: Historic urban_core/lowrise with moderate diversity
    # Historic areas with moderate architectural diversity need more forgiving targets
    # Examples: Greenwich Village (height 22.9, type 27.2, footprint 66.2%)
    if is_historic and effective in ["urban_core_lowrise", "urban_core"]:
        # Check if moderate diversity pattern (not uniform, not extreme)
        if 15 < levels_entropy < 50 and 20 < building_type_diversity < 60:
            # Historic with moderate diversity - more forgiving targets
            targets["height"] = (10, 20, 50, 70)  # More forgiving height range
            targets["type"] = (20, 30, 65, 85)    # More forgiving type range
            # Also reward organic growth if present
            if footprint_area_cv and footprint_area_cv > 50:
                targets["footprint"] = (50, 60, 90, 100)  # High CV is good for historic
    
    # Adjustment 4: Historic suburban/exurban uniformity with low footprint CV
    # Historic suburban/exurban areas with uniform architecture + LOW footprint CV = beautiful planned uniformity
    # Examples: Carmel-by-the-Sea (height 0.4, type 19.8, footprint 27.1%), Nantucket (height 0.0, type 1.6, footprint 39.1%)
    # This is different from degraded sprawl (uniform + HIGH footprint CV like Levittown 95.3%)
    # Key distinction: LOW footprint CV = planned/preserved, HIGH footprint CV = degraded sprawl
    if is_historic and effective in ("suburban", "exurban"):
        # Check for beautiful planned uniformity: uniform height + uniform type + LOW footprint CV
        if levels_entropy < 10 and building_type_diversity < 25 and footprint_area_cv < 40:
            # Beautiful planned uniformity (like Carmel, Nantucket) - reward it
            # Adjust targets to match uniform pattern (similar to urban_residential)
            targets["height"] = (0, 0, 15, 30)  # More forgiving for very uniform (like urban_residential)
            targets["type"] = (0, 0, 25, 40)   # More forgiving for very uniform (allow up to 25 in sweet spot)
            targets["footprint"] = (20, 25, 40, 50)  # LOW footprint CV is GOOD for planned uniformity
    
    # Adjustment 5: Uniform coastal beach towns (urban_core_lowrise with low footprint CV)
    # Well-planned coastal beach towns often have uniform architecture (planned, not sprawl)
    # Examples: Manhattan Beach (height 9.9, type 32.5, footprint 21.5%)
    # Low footprint CV in coastal urban areas = intentional uniformity, not cookie-cutter chaos
    if effective == "urban_core_lowrise":
        # Check for planned uniformity: uniform height + uniform type + LOW footprint CV
        if levels_entropy < 15 and building_type_diversity < 40 and footprint_area_cv < 30:
            # Planned uniformity (like Manhattan Beach, Hermosa Beach) - reward it
            # Adjust targets to match uniform pattern (similar to urban_residential)
            targets["height"] = (0, 0, 15, 30)  # Reward uniformity
            targets["type"] = (0, 0, 35, 50)   # More forgiving for uniform coastal areas
            targets["footprint"] = (15, 20, 30, 40)  # LOW footprint CV is GOOD for planned uniformity
    
    # Adjustment 6: Coastal towns with uniform architecture (suburban/exurban, low footprint CV)
    # Well-planned coastal towns often have uniform architecture even if not historic
    # Examples: Cape May (height 0.4, type 7.1, footprint 44.7%), Sausalito (height 0.8, type 14.5, footprint 63.9%)
    # Low footprint CV in coastal contexts = intentional uniformity, not sprawl
    # Note: Cape May's footprint 44.7% is slightly above 40%, but still indicates planned uniformity
    if effective in ("suburban", "exurban"):
        # Check for planned uniformity: uniform height + uniform type + LOW to moderate footprint CV
        if levels_entropy < 10 and building_type_diversity < 20 and footprint_area_cv < 70:
            # Planned uniformity (like Cape May, Sausalito) - reward it
            # Adjust targets to match uniform pattern (similar to historic uniformity)
            targets["height"] = (0, 0, 15, 30)  # Reward uniformity
            targets["type"] = (0, 0, 25, 40)   # More forgiving for uniform coastal areas
            # Footprint: Allow wider range for coastal areas (some variation in lot sizes is natural)
            targets["footprint"] = (20, 30, 50, 65)  # Moderate variation is OK for coastal towns
    
    # Score each metric using adjusted targets
    height_pts = _score_band(levels_entropy, targets["height"])
    type_pts = _score_band(building_type_diversity, targets["type"])
    foot_pts = _score_band(footprint_area_cv, targets["footprint"])
    
    # Cap single-metric dominance (max 13.2 each = 40% of 33)
    height_pts = min(13.2, height_pts)
    type_pts = min(13.2, type_pts)
    foot_pts = min(13.2, foot_pts)
    
    # Base total
    base = height_pts + type_pts + foot_pts
    
    # SUBURBAN BASE FLOOR BONUS
    # Rewards well-planned communities (e.g., Levittown, planned subdivisions)
    # vs. chaotic sprawl. Very uniform suburban development can indicate
    # intentional planning and cohesive design standards.
    # This distinguishes intentional uniformity (beautiful) from cookie-cutter chaos (ugly).
    if effective == "suburban":
        if levels_entropy < 10 and footprint_area_cv < 40:
            # Very uniform height + footprint = intentional cohesion, not cookie-cutter
            # This rewards planned communities with consistent architecture
            base_floor = 5.0
            base = max(base, base_floor)
    
    # One bonus, one penalty (use effective area type for context-aware penalties)
    bonus = _coherence_bonus(levels_entropy, footprint_area_cv, effective)
    penalty = _context_penalty(effective, built_coverage_ratio,
                               levels_entropy, building_type_diversity,
                               footprint_area_cv)
    
    total = base + bonus - penalty
    
    # Density multiplier (simple banding)
    mult = DENSITY_MULTIPLIER.get(effective, 1.0)
    total *= mult
    
    # Cap at 33
    return max(0.0, min(33.0, total))
