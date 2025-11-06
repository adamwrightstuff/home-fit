"""
Architectural Diversity (Sandbox)
Computes simple diversity metrics from OSM buildings within a radius.
This module is sandbox-only and not wired into scoring by default.
"""

from typing import Dict, Optional, Tuple
import requests

from .osm_api import OVERPASS_URL, _retry_overpass
from .cache import cached, CACHE_TTL
from logging_config import get_logger

logger = get_logger(__name__)


@cached(ttl_seconds=CACHE_TTL['osm_queries'])
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
        
        # Architectural diversity is standard (important but not critical) - use STANDARD profile
        resp = _retry_overpass(_do_request, query_type="architectural_diversity")
        
        if resp is None or resp.status_code != 200:
            status_msg = f"status {resp.status_code}" if resp else "no response"
            error_detail = f"API {status_msg}"
            
            # Determine user-friendly message based on error type
            if resp and resp.status_code == 429:
                error_detail = "Rate limited (429) - max retries reached"
                user_message = "OSM API temporarily rate limited. Please try again in a few seconds."
            elif resp is None:
                error_detail = "API no response"
                user_message = "OSM API temporarily unavailable. Please try again in a few seconds."
            else:
                user_message = "OSM API temporarily unavailable. Please try again in a few seconds."
            
            print(f"⚠️  Overpass API returned {error_detail} for architectural diversity query")
            return {
                "levels_entropy": 0, 
                "building_type_diversity": 0, 
                "footprint_area_cv": 0, 
                "diversity_score": 0, 
                "built_coverage_ratio": 0.0,
                "osm_building_coverage": 0.0,
                "beauty_valid": True,  # Always true - no hard failure
                "data_warning": "api_error",
                "confidence_0_1": 0.0,  # Very low confidence for API errors
                "error": error_detail,
                "user_message": user_message,
                "retry_suggested": True
            }
        
        elements = resp.json().get("elements", [])
        if not elements:
            print(f"⚠️  No building elements found in OSM query (radius: {radius_m}m)")
            return {
                "levels_entropy": 0,
                "building_type_diversity": 0,
                "footprint_area_cv": 0,
                "diversity_score": 0,
                "built_coverage_ratio": 0.0,
                "osm_building_coverage": 0.0,
                "beauty_valid": True,  # Always true - no hard failure
                "data_warning": "no_buildings",
                "confidence_0_1": 0.0,  # Very low confidence for no buildings
                "note": "No buildings found in OSM"
            }
    except requests.exceptions.Timeout as e:
        print(f"⚠️  OSM building query timeout: {e}")
        return {
            "levels_entropy": 0,
            "building_type_diversity": 0,
            "footprint_area_cv": 0,
            "diversity_score": 0,
            "built_coverage_ratio": 0.0,
            "osm_building_coverage": 0.0,
            "beauty_valid": True,  # Always true - no hard failure
            "data_warning": "timeout",
            "confidence_0_1": 0.0,  # Very low confidence for timeouts
            "error": f"Timeout: {str(e)}"
        }
    except requests.exceptions.RequestException as e:
        print(f"⚠️  OSM building query network error: {e}")
        return {
            "levels_entropy": 0,
            "building_type_diversity": 0,
            "footprint_area_cv": 0,
            "diversity_score": 0,
            "built_coverage_ratio": 0.0,
            "osm_building_coverage": 0.0,
            "beauty_valid": True,  # Always true - no hard failure
            "data_warning": "network_error",
            "confidence_0_1": 0.0,  # Very low confidence for network errors
            "error": f"Network error: {str(e)}"
        }
    except Exception as e:
        print(f"⚠️  OSM building query error: {e}")
        import traceback
        print(f"   Traceback: {traceback.format_exc()}")
        return {
            "levels_entropy": 0,
            "building_type_diversity": 0,
            "footprint_area_cv": 0,
            "diversity_score": 0,
            "built_coverage_ratio": 0.0,
            "osm_building_coverage": 0.0,
            "beauty_valid": True,  # Always true - no hard failure
            "data_warning": "error",
            "confidence_0_1": 0.0,  # Very low confidence for errors
            "error": str(e)
        }

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

    # Calculate OSM coverage validation
    # No hard failure - always report coverage and confidence
    # Apply score caps based on coverage level
    beauty_valid = True  # Always true - no hard failure
    data_warning = None
    confidence_0_1 = 1.0
    
    if built_coverage_ratio < 0.30:
        # Very low coverage: cap architecture at 25/50, lower confidence
        confidence_0_1 = 0.4
        data_warning = "low_building_coverage"
    elif built_coverage_ratio < 0.50:
        # Low coverage: cap architecture at 35/50, moderate confidence
        confidence_0_1 = 0.6
        data_warning = "low_building_coverage"
    
    return {
        "levels_entropy": round(levels_entropy, 1),
        "building_type_diversity": round(type_div, 1),
        "footprint_area_cv": round(area_cv, 1),
        "diversity_score": round(diversity_score, 1),
        "built_coverage_ratio": round(built_coverage_ratio, 3),  # 0.0-1.0 scale
        "osm_building_coverage": round(built_coverage_ratio, 2),  # For reporting (0.00-1.00)
        "beauty_valid": beauty_valid,  # Always True - no hard failure
        "data_warning": data_warning,  # "low_building_coverage" if coverage < 50%
        "confidence_0_1": confidence_0_1  # 1.0 if good, 0.6 if <50%, 0.4 if <30%
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

# Area-type-specific weights for beauty metrics (sum = 50 points)
# Phase 1 metrics:
#   height_diversity → Height variation (entropy)
#   historic_era_integrity → Type diversity
#   footprint_diversity → Footprint CV
# Phase 2 metrics (now active):
#   block_grain → Street network fineness
#   streetwall_continuity → Building facade continuity along streets
# Phase 3 metrics (now active):
#   setback_consistency → Building setback consistency (uniformity of setbacks)
#   facade_rhythm → Facade alignment (proportion of buildings aligned with mean setback)
AREA_TYPE_WEIGHTS = {
    "urban_core": {
        "height_diversity": 18,         # Phase 1: height variation (reduced from 20)
        "historic_era_integrity": 10,   # Phase 1: type diversity
        "footprint_diversity": 0,       # Phase 1: footprint CV (not used for urban_core)
        "block_grain": 8,               # Phase 2: street network fineness (reduced from 10)
        "streetwall_continuity": 8,     # Phase 2: facade continuity (reduced from 10)
        "setback_consistency": 4,        # Phase 3: setback uniformity
        "facade_rhythm": 2,             # Phase 3: facade alignment
    },
    "urban_historic": {
        "height_diversity": 16,         # Phase 1: height variation (reduced from 18)
        "historic_era_integrity": 17,   # Phase 1: type diversity (emphasized)
        "footprint_diversity": 0,
        "block_grain": 6,               # Phase 2: street network fineness (reduced from 8)
        "streetwall_continuity": 5,      # Phase 2: facade continuity (reduced from 7)
        "setback_consistency": 4,       # Phase 3: setback uniformity
        "facade_rhythm": 2,             # Phase 3: facade alignment
    },
    "historic_urban": {  # Alias for urban_historic (uses same weights)
        "height_diversity": 16,
        "historic_era_integrity": 17,
        "footprint_diversity": 0,
        "block_grain": 6,
        "streetwall_continuity": 5,
        "setback_consistency": 4,
        "facade_rhythm": 2,
    },
    "urban_residential": {
        "height_diversity": 13,         # Phase 1: height variation (reduced from 15)
        "historic_era_integrity": 10,   # Phase 1: type diversity
        "footprint_diversity": 5,       # Phase 1: footprint CV
        "block_grain": 8,               # Phase 2: street network fineness (reduced from 10)
        "streetwall_continuity": 8,     # Phase 2: facade continuity (reduced from 10)
        "setback_consistency": 4,       # Phase 3: setback uniformity
        "facade_rhythm": 2,             # Phase 3: facade alignment
    },
    "urban_core_lowrise": {
        "height_diversity": 16,         # Phase 1: height variation (reduced from 18)
        "historic_era_integrity": 10,   # Phase 1: type diversity
        "footprint_diversity": 0,
        "block_grain": 8,               # Phase 2: street network fineness (reduced from 10)
        "streetwall_continuity": 10,    # Phase 2: facade continuity (reduced from 12)
        "setback_consistency": 4,       # Phase 3: setback uniformity
        "facade_rhythm": 2,             # Phase 3: facade alignment
    },
    "suburban": {
        "height_diversity": 5,          # Phase 1: height variation (less important)
        "historic_era_integrity": 12,   # Phase 1: type diversity (reduced from 13)
        "footprint_diversity": 0,
        "block_grain": 17,              # Phase 2: street network fineness (reduced from 20)
        "streetwall_continuity": 10,    # Phase 2: facade continuity (reduced from 12)
        "setback_consistency": 4,       # Phase 3: setback uniformity (important for suburban)
        "facade_rhythm": 2,             # Phase 3: facade alignment
    },
    "exurban": {
        "height_diversity": 0,          # Phase 1: height variation (not relevant)
        "historic_era_integrity": 10,   # Phase 1: type diversity
        "footprint_diversity": 0,
        "block_grain": 22,              # Phase 2: street network fineness (reduced from 25)
        "streetwall_continuity": 13,    # Phase 2: facade continuity (reduced from 15)
        "setback_consistency": 3,       # Phase 3: setback uniformity (less important)
        "facade_rhythm": 2,             # Phase 3: facade alignment
    },
    "rural": {
        "height_diversity": 0,          # Phase 1: height variation (not relevant)
        "historic_era_integrity": 10,   # Phase 1: type diversity
        "footprint_diversity": 0,
        "block_grain": 22,              # Phase 2: street network fineness (reduced from 25)
        "streetwall_continuity": 13,    # Phase 2: facade continuity (reduced from 15)
        "setback_consistency": 3,       # Phase 3: setback uniformity (less important)
        "facade_rhythm": 2,             # Phase 3: facade alignment
    },
    "unknown": {
        "height_diversity": 10,          # Equal weights as fallback
        "historic_era_integrity": 10,
        "footprint_diversity": 10,
        "block_grain": 8,
        "streetwall_continuity": 8,
        "setback_consistency": 2,
        "facade_rhythm": 2,
    },
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


def _is_historic_organic(median_year_built: Optional[int]) -> bool:
    """Detect Historic Organic pattern: median_year_built < 1940."""
    return median_year_built is not None and median_year_built < 1940


def _apply_historic_organic_adjustment(targets: Dict, is_historic_organic_flag: bool, 
                                       is_historic: bool, footprint_area_cv: float,
                                       effective: str) -> None:
    """Adjustment 1: Historic organic growth - widen variance bands for organic neighborhoods."""
    if is_historic_organic_flag or (is_historic and footprint_area_cv > 70):
        targets["footprint"] = (50, 65, 95, 100)  # HIGH CV is GOOD for historic areas
        if is_historic_organic_flag:
            if effective in ["urban_core", "urban_core_lowrise", "historic_urban"]:
                targets["height"] = (10, 15, 70, 85)
                targets["type"] = (20, 25, 85, 95)


def _apply_very_historic_adjustment(targets: Dict, is_very_historic: bool, effective: str) -> None:
    """Adjustment 2: Very historic urban_residential - allow higher type diversity."""
    if is_very_historic and effective == "urban_residential":
        targets["type"] = (0, 0, 35, 50)  # Allow up to 35 in sweet spot


def _apply_historic_moderate_diversity_adjustment(targets: Dict, is_historic: bool, effective: str,
                                                  levels_entropy: float, building_type_diversity: float,
                                                  footprint_area_cv: float) -> None:
    """Adjustment 3: Historic urban_core/lowrise with moderate diversity."""
    if is_historic and effective in ["urban_core_lowrise", "urban_core"]:
        if 15 < levels_entropy < 50 and 20 < building_type_diversity < 60:
            targets["height"] = (10, 20, 50, 70)
            targets["type"] = (20, 30, 65, 85)
            if footprint_area_cv and footprint_area_cv > 50:
                targets["footprint"] = (50, 60, 90, 100)


def _apply_historic_uniformity_adjustment(targets: Dict, is_historic: bool, effective: str,
                                          levels_entropy: float, building_type_diversity: float,
                                          footprint_area_cv: float) -> None:
    """Adjustment 4: Historic suburban/exurban uniformity with low footprint CV."""
    if is_historic and effective in ("suburban", "exurban"):
        if levels_entropy < 10 and building_type_diversity < 25 and footprint_area_cv < 40:
            targets["height"] = (0, 0, 15, 30)
            targets["type"] = (0, 0, 25, 40)
            targets["footprint"] = (20, 25, 40, 50)


def _apply_coastal_uniformity_adjustment(targets: Dict, effective: str, levels_entropy: float,
                                         building_type_diversity: float, footprint_area_cv: float) -> None:
    """Adjustment 5: Uniform coastal beach towns (urban_core_lowrise with low footprint CV)."""
    if effective == "urban_core_lowrise":
        if levels_entropy < 15 and building_type_diversity < 40 and footprint_area_cv < 30:
            targets["height"] = (0, 0, 15, 30)
            targets["type"] = (0, 0, 35, 50)
            targets["footprint"] = (15, 20, 30, 40)


def _apply_coastal_town_adjustment(targets: Dict, effective: str, levels_entropy: float,
                                   building_type_diversity: float, footprint_area_cv: float) -> None:
    """Adjustment 6: Coastal towns with uniform architecture (suburban/exurban, low footprint CV)."""
    if effective in ("suburban", "exurban"):
        if levels_entropy < 10 and building_type_diversity < 20 and footprint_area_cv < 70:
            targets["height"] = (0, 0, 15, 30)
            targets["type"] = (0, 0, 25, 40)
            targets["footprint"] = (20, 30, 50, 65)


def _apply_residential_varied_lots_adjustment(targets: Dict, effective: str, levels_entropy: float,
                                             building_type_diversity: float, footprint_area_cv: float,
                                             density: Optional[float]) -> None:
    """Adjustment 7: Uniform residential urban areas with varied lot sizes (urban_core_lowrise)."""
    if effective == "urban_core_lowrise":
        is_dense_enough = (density is not None and density > 5000)
        if (levels_entropy < 15 and building_type_diversity < 45 and footprint_area_cv > 60 and 
            is_dense_enough):
            targets["height"] = (0, 0, 15, 30)
            targets["type"] = (0, 0, 40, 55)
            targets["footprint"] = (60, 70, 95, 100)


def _score_band(value: float, band: tuple, max_points: float = 16.67) -> float:
    """Score a value within a context band. Plateau range gets full points.
    
    Default max_points is 16.67 so 3 metrics = ~50 points total (native 0-50 range).
    """
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
            # Check if low coverage might be due to parks/green space (uniform residential pattern)
            # Pattern: uniform architecture + varied lot sizes = parks/green space, not voids
            # SAFEGUARD: Only reduce penalty for genuinely dense areas to avoid rewarding sprawl
            # Require density > 5,000 people/sq mi to distinguish from sprawl
            # Note: density parameter not directly available here, but we can check the pattern
            # The adjustment in score_architectural_diversity_as_beauty already has density check
            is_uniform_residential = (levels_entropy < 15 and type_div < 45 and 
                                      footprint_cv is not None and footprint_cv > 60)
            
            # Note: We can't check density here directly, but the adjustment logic above
            # already requires density > 5000, so if the adjustment applied, this is safe
            # However, we should still be conservative - only reduce penalty if pattern matches
            # AND we're confident it's parks (high footprint CV from varied lot sizes, not fragmentation)
            
            if built_cov < 0.15:
                # If uniform residential pattern, low coverage likely due to parks/green space (beautiful!)
                # Reduce penalty significantly, but only for uniform residential pattern
                # (The adjustment logic above already requires density > 5000)
                if is_uniform_residential:
                    return 1.5  # Much more lenient (parks are beautiful, not voids)
                return 4.5  # Slightly more lenient
            if built_cov < 0.25:
                if is_uniform_residential:
                    return 0.5  # Minimal penalty for parks/green space
                return 2.5  # More lenient for low-rise areas
            if built_cov < 0.35:
                if is_uniform_residential:
                    return 0.0  # No penalty
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
    median_year_built: Optional[int] = None,
    lat: Optional[float] = None,
    lon: Optional[float] = None
) -> Tuple[float, Dict]:
    """
    Convert architectural diversity metrics to beauty score (0-50 points).
    
    Now includes Phase 2 metrics: block_grain and streetwall_continuity.
    Now includes Phase 3 metrics: setback_consistency and facade_rhythm.
    
    Args:
        levels_entropy: Height diversity (0-100)
        building_type_diversity: Type diversity (0-100)
        footprint_area_cv: Size variation (0-100)
        area_type: 'urban_core', 'suburban', 'exurban', 'rural', 'unknown'
        density: Optional population density for fine-tuning
        built_coverage_ratio: Optional built coverage ratio (0.0-1.0)
        historic_landmarks: Optional count of historic landmarks from OSM
        median_year_built: Optional median year buildings were built
        lat: Optional latitude for Phase 2 & Phase 3 metrics (block_grain, streetwall_continuity, setback_consistency, facade_rhythm)
        lon: Optional longitude for Phase 2 & Phase 3 metrics (block_grain, streetwall_continuity, setback_consistency, facade_rhythm)
    
    Returns:
        Beauty score out of 50 points (native range, no scaling)
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
    
    # Use Historic Organic flag for additional adjustments
    is_historic_organic_flag = _is_historic_organic(median_year_built)
    
    # Apply all adjustments in order (most specific last)
    _apply_historic_organic_adjustment(targets, is_historic_organic_flag, is_historic, 
                                       footprint_area_cv, effective)
    _apply_very_historic_adjustment(targets, is_very_historic, effective)
    _apply_historic_moderate_diversity_adjustment(targets, is_historic, effective,
                                                   levels_entropy, building_type_diversity,
                                                   footprint_area_cv)
    _apply_historic_uniformity_adjustment(targets, is_historic, effective,
                                          levels_entropy, building_type_diversity,
                                          footprint_area_cv)
    _apply_coastal_uniformity_adjustment(targets, effective, levels_entropy,
                                         building_type_diversity, footprint_area_cv)
    _apply_coastal_town_adjustment(targets, effective, levels_entropy,
                                   building_type_diversity, footprint_area_cv)
    _apply_residential_varied_lots_adjustment(targets, effective, levels_entropy,
                                              building_type_diversity, footprint_area_cv,
                                              density)
    
    # Get area-type-specific weights for this effective area type
    weights = AREA_TYPE_WEIGHTS.get(effective, AREA_TYPE_WEIGHTS.get("unknown", AREA_TYPE_WEIGHTS["unknown"]))
    
    # Score each metric using adjusted targets, then apply area-type-specific weights
    # Phase 1 metrics:
    # - levels_entropy → height_diversity weight
    # - building_type_diversity → historic_era_integrity weight
    # - footprint_area_cv → footprint_diversity weight
    # Phase 2 metrics (from street_geometry module):
    # - block_grain → block_grain weight
    # - streetwall_continuity → streetwall_continuity weight
    
    # Import Phase 2 and Phase 3 metrics
    from .street_geometry import (
        compute_block_grain, compute_streetwall_continuity,
        compute_setback_consistency, compute_facade_rhythm
    )
    from concurrent.futures import ThreadPoolExecutor
    
    # Calculate Phase 1 raw scores (0-100 scale, normalized to 0-16.67 for weighting)
    height_raw = _score_band(levels_entropy, targets["height"], max_points=16.67)
    type_raw = _score_band(building_type_diversity, targets["type"], max_points=16.67)
    foot_raw = _score_band(footprint_area_cv, targets["footprint"], max_points=16.67)
    
    # Calculate Phase 2 and Phase 3 metrics (0-100 scale, normalized to 0-16.67 for weighting)
    # OPTIMIZATION: Run all Phase 2 & Phase 3 metrics in parallel for better performance
    block_grain_value = 0.0
    streetwall_value = 0.0
    setback_value = 0.0
    facade_rhythm_value = 0.0
    block_grain_confidence = 0.0
    streetwall_confidence = 0.0
    setback_confidence = 0.0
    facade_rhythm_confidence = 0.0
    
    if lat is not None and lon is not None:
        # Use 2km radius for Phase 2 & Phase 3 metrics (same as architectural diversity)
        # OPTIMIZATION: Fetch shared OSM data once for all Phase 2 & Phase 3 metrics
        from .street_geometry import _fetch_roads_and_buildings
        from concurrent.futures import TimeoutError as FutureTimeoutError
        
        # Fetch shared OSM data with timeout to prevent hanging
        # If this fails, Phase 2/3 metrics will still work but may need to fetch their own data
        # NOTE: _fetch_roads_and_buildings is cached, so repeated requests won't hit OSM again
        shared_osm_data = None
        try:
            logger.debug("Fetching shared OSM data for Phase 2/3 metrics (cached if available)...")
            # Wrap in timeout executor to prevent hanging
            with ThreadPoolExecutor(max_workers=1) as timeout_executor:
                future_shared = timeout_executor.submit(_fetch_roads_and_buildings, lat, lon, 2000)
                try:
                    shared_osm_data = future_shared.result(timeout=20)  # 20 second timeout for shared fetch
                    if shared_osm_data is None:
                        logger.warning("Shared OSM data fetch returned None (likely rate limited), Phase 2/3 metrics will try to fetch their own data")
                    else:
                        logger.debug("Shared OSM data fetched successfully, Phase 2/3 metrics will use it")
                except FutureTimeoutError:
                    logger.warning("Shared OSM data fetch timed out after 20s, Phase 2/3 metrics will try to fetch their own data")
                    shared_osm_data = None
        except Exception as e:
            logger.warning(f"Shared OSM data fetch failed: {e}, Phase 2/3 metrics will try to fetch their own data")
            shared_osm_data = None
        
        # Run all 4 metrics in parallel, but make each one independent
        # If one fails, others can still succeed
        with ThreadPoolExecutor(max_workers=4) as executor:
            future_block = executor.submit(compute_block_grain, lat, lon, 2000)
            future_streetwall = executor.submit(compute_streetwall_continuity, lat, lon, 2000, shared_osm_data)
            future_setback = executor.submit(compute_setback_consistency, lat, lon, 2000, shared_osm_data)
            future_facade = executor.submit(compute_facade_rhythm, lat, lon, 2000, shared_osm_data)
            
            # Each metric has individual timeout of 30 seconds
            # If one fails, others can still complete
            def get_with_timeout(future, timeout, name):
                try:
                    return future.result(timeout=timeout)
                except FutureTimeoutError:
                    logger.warning(f"Phase 2/3 metric {name} timed out after {timeout}s, using default (0.0)")
                    if name == "block_grain":
                        return {"block_grain": 0.0, "coverage_confidence": 0.0}
                    elif name == "streetwall":
                        return {"streetwall_continuity": 0.0, "coverage_confidence": 0.0}
                    elif name == "setback":
                        return {"setback_consistency": 0.0, "coverage_confidence": 0.0}
                    else:  # facade_rhythm
                        return {"facade_rhythm": 0.0, "coverage_confidence": 0.0}
                except Exception as e:
                    logger.warning(f"Phase 2/3 metric {name} failed: {e}, using default (0.0)")
                    if name == "block_grain":
                        return {"block_grain": 0.0, "coverage_confidence": 0.0}
                    elif name == "streetwall":
                        return {"streetwall_continuity": 0.0, "coverage_confidence": 0.0}
                    elif name == "setback":
                        return {"setback_consistency": 0.0, "coverage_confidence": 0.0}
                    else:  # facade_rhythm
                        return {"facade_rhythm": 0.0, "coverage_confidence": 0.0}
            
            block_grain_data = get_with_timeout(future_block, 30, "block_grain")
            streetwall_data = get_with_timeout(future_streetwall, 30, "streetwall")
            setback_data = get_with_timeout(future_setback, 30, "setback")
            facade_rhythm_data = get_with_timeout(future_facade, 30, "facade_rhythm")
        
        block_grain_value = block_grain_data.get("block_grain", 0.0)
        block_grain_confidence = block_grain_data.get("coverage_confidence", 0.0)
        
        streetwall_value = streetwall_data.get("streetwall_continuity", 0.0)
        streetwall_confidence = streetwall_data.get("coverage_confidence", 0.0)
        
        setback_value = setback_data.get("setback_consistency", 0.0)
        setback_confidence = setback_data.get("coverage_confidence", 0.0)
        
        facade_rhythm_value = facade_rhythm_data.get("facade_rhythm", 0.0)
        facade_rhythm_confidence = facade_rhythm_data.get("coverage_confidence", 0.0)
    
    # Normalize Phase 2 & Phase 3 metrics to 0-16.67 scale (same as Phase 1)
    block_grain_raw = (block_grain_value / 100.0) * 16.67
    streetwall_raw = (streetwall_value / 100.0) * 16.67
    setback_raw = (setback_value / 100.0) * 16.67
    facade_rhythm_raw = (facade_rhythm_value / 100.0) * 16.67
    
    # Apply area-type-specific weights
    # Scale each metric's raw score (0-16.67) to its weighted max (0-weight)
    height_weight = weights.get("height_diversity", 0)
    historic_weight = weights.get("historic_era_integrity", 0)
    footprint_weight = weights.get("footprint_diversity", 0)
    block_grain_weight = weights.get("block_grain", 0)
    streetwall_weight = weights.get("streetwall_continuity", 0)
    setback_weight = weights.get("setback_consistency", 0)
    facade_rhythm_weight = weights.get("facade_rhythm", 0)
    
    # Scale raw scores to weighted points
    # Formula: weighted_pts = raw_score * (weight / 16.67)
    height_pts = height_raw * (height_weight / 16.67) if height_weight > 0 else 0.0
    type_pts = type_raw * (historic_weight / 16.67) if historic_weight > 0 else 0.0
    foot_pts = foot_raw * (footprint_weight / 16.67) if footprint_weight > 0 else 0.0
    block_grain_pts = block_grain_raw * (block_grain_weight / 16.67) if block_grain_weight > 0 else 0.0
    streetwall_pts = streetwall_raw * (streetwall_weight / 16.67) if streetwall_weight > 0 else 0.0
    setback_pts = setback_raw * (setback_weight / 16.67) if setback_weight > 0 else 0.0
    facade_rhythm_pts = facade_rhythm_raw * (facade_rhythm_weight / 16.67) if facade_rhythm_weight > 0 else 0.0
    
    # Cap single-metric dominance (max 20 each = 40% of 50)
    height_pts = min(20.0, height_pts)
    type_pts = min(20.0, type_pts)
    foot_pts = min(20.0, foot_pts)
    block_grain_pts = min(20.0, block_grain_pts)
    streetwall_pts = min(20.0, streetwall_pts)
    setback_pts = min(20.0, setback_pts)
    facade_rhythm_pts = min(20.0, facade_rhythm_pts)
    
    # Base total (sum of weighted metrics)
    base = height_pts + type_pts + foot_pts + block_grain_pts + streetwall_pts + setback_pts + facade_rhythm_pts
    
    # SUBURBAN BASE FLOOR BONUS
    # Rewards well-planned communities (e.g., Levittown, planned subdivisions)
    # vs. chaotic sprawl. Very uniform suburban development can indicate
    # intentional planning and cohesive design standards.
    # This distinguishes intentional uniformity (beautiful) from cookie-cutter chaos (ugly).
    if effective == "suburban":
        if levels_entropy < 10 and footprint_area_cv < 40:
            # Very uniform height + footprint = intentional cohesion, not cookie-cutter
            # This rewards planned communities with consistent architecture
            base_floor = 7.5  # Scaled proportionally from 5.0 to 7.5 (50/33 ratio)
            base = max(base, base_floor)
    
    # One bonus, one penalty (use effective area type for context-aware penalties)
    # Scale bonus proportionally for 0-50 range
    bonus = _coherence_bonus(levels_entropy, footprint_area_cv, effective)
    bonus = bonus * (50.0 / 33.0)  # Scale from 0-33 to 0-50 range
    penalty = _context_penalty(effective, built_coverage_ratio,
                               levels_entropy, building_type_diversity,
                               footprint_area_cv)
    penalty = penalty * (50.0 / 33.0)  # Scale from 0-33 to 0-50 range
    
    total = base + bonus - penalty
    
    # Density multiplier (simple banding)
    mult = DENSITY_MULTIPLIER.get(effective, 1.0)
    total *= mult
    
    # Apply coverage-based score caps (graceful degradation)
    # If OSM coverage is low, cap the score to prevent over-confidence
    # However, Phase 2 metrics (block_grain, streetwall_continuity) are independent of building coverage
    # So we adjust caps to be less aggressive when Phase 2 metrics have good confidence
    coverage_cap_info = {"capped": False, "original_score": total, "cap_reason": None}
    
    # Calculate average Phase 2 & Phase 3 confidence (if available)
    avg_phase23_confidence = 0.0
    if (block_grain_confidence > 0 or streetwall_confidence > 0 or 
        setback_confidence > 0 or facade_rhythm_confidence > 0):
        confidence_sum = 0.0
        confidence_count = 0
        if block_grain_confidence > 0:
            confidence_sum += block_grain_confidence
            confidence_count += 1
        if streetwall_confidence > 0:
            confidence_sum += streetwall_confidence
            confidence_count += 1
        if setback_confidence > 0:
            confidence_sum += setback_confidence
            confidence_count += 1
        if facade_rhythm_confidence > 0:
            confidence_sum += facade_rhythm_confidence
            confidence_count += 1
        if confidence_count > 0:
            avg_phase23_confidence = confidence_sum / confidence_count
    
    # Adjust caps based on Phase 2 & Phase 3 confidence
    # If Phase 2 & Phase 3 metrics have good confidence (>0.5), we can be less aggressive with caps
    # since block_grain, streetwall_continuity, setback_consistency, and facade_rhythm 
    # don't depend on building coverage (or depend less directly)
    phase23_confidence_bonus = 0.0
    if avg_phase23_confidence > 0.5:
        # Phase 2 & Phase 3 metrics provide independent value, so reduce cap aggressiveness
        phase23_confidence_bonus = (avg_phase23_confidence - 0.5) * 10.0  # Add up to 5 points to cap threshold
    
    if built_coverage_ratio is not None:
        if built_coverage_ratio < 0.15:
            # Very low coverage: cap at 30/50 (raised from 25/50)
            # With Phase 2 & Phase 3 bonus, can go up to 35/50
            cap_threshold = 30.0 + phase23_confidence_bonus
            if total > cap_threshold:
                coverage_cap_info = {"capped": True, "original_score": total, "cap_reason": "coverage_lt_15pct"}
                total = min(cap_threshold, total)
        elif built_coverage_ratio < 0.30:
            # Low coverage: cap at 40/50 (raised from 25/50)
            # With Phase 2 & Phase 3 bonus, can go up to 45/50
            cap_threshold = 40.0 + phase23_confidence_bonus
            if total > cap_threshold:
                coverage_cap_info = {"capped": True, "original_score": total, "cap_reason": "coverage_lt_30pct"}
                total = min(cap_threshold, total)
        elif built_coverage_ratio < 0.50:
            # Moderate coverage: cap at 45/50 (raised from 35/50)
            # With Phase 2 & Phase 3 bonus, can go up to 47/50
            cap_threshold = 45.0 + min(2.0, phase23_confidence_bonus)
            if total > cap_threshold:
                coverage_cap_info = {"capped": True, "original_score": total, "cap_reason": "coverage_lt_50pct"}
                total = min(cap_threshold, total)
    
    # Cap at 50 (native range)
    final_score = max(0.0, min(50.0, total))
    
    # Return score with metadata about coverage caps and Phase 2 & Phase 3 metrics
    metadata = {
        "coverage_cap_applied": coverage_cap_info["capped"],
        "original_score_before_cap": coverage_cap_info["original_score"] if coverage_cap_info["capped"] else None,
        "cap_reason": coverage_cap_info["cap_reason"],
        # Phase 2 metrics
        "block_grain": block_grain_value,
        "block_grain_confidence": block_grain_confidence,
        "streetwall_continuity": streetwall_value,
        "streetwall_confidence": streetwall_confidence,
        # Phase 3 metrics
        "setback_consistency": setback_value,
        "setback_confidence": setback_confidence,
        "facade_rhythm": facade_rhythm_value,
        "facade_rhythm_confidence": facade_rhythm_confidence
    }
    
    return final_score, metadata
