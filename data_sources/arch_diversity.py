"""
Architectural Diversity (Sandbox)
Computes simple diversity metrics from OSM buildings within a radius.
This module is sandbox-only and not wired into scoring by default.
"""

from typing import Dict, Optional, Tuple, Any, List
from datetime import datetime
import requests

from .osm_api import get_overpass_url, _retry_overpass
from .cache import cached, CACHE_TTL, _generate_cache_key, _get_redis_client, _cache, _cache_ttl
import time
import json
from logging_config import get_logger

logger = get_logger(__name__)


@cached(ttl_seconds=CACHE_TTL['osm_queries'])
def compute_arch_diversity(lat: float, lon: float, radius_m: int = 1000) -> Dict[str, Any]:
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
            return requests.post(get_overpass_url(), data={"data": q}, timeout=60, headers={"User-Agent":"HomeFit/1.0"})
        
        # Architectural diversity is CRITICAL - use CRITICAL profile with more aggressive retries
        # Use custom config with more attempts and longer waits for this critical query
        from .retry_config import RetryConfig
        custom_config = RetryConfig(
            max_attempts=5,  # More attempts than default CRITICAL (3)
            base_wait=2.0,  # Longer base wait
            fail_fast=False,  # Don't fail fast - keep trying all endpoints
            max_wait=20.0,  # Longer max wait
            exponential_backoff=True,
            retry_on_timeout=True,
            retry_on_429=True,
        )
        resp = _retry_overpass(_do_request, query_type="architectural_diversity", config=custom_config)
        
        if resp is None or resp.status_code != 200:
            status_msg = f"status {resp.status_code}" if resp else "no response"
            error_detail = f"API {status_msg}"
            
            # Check for stale cache before returning zeros
            # This allows us to use previously successful data when API temporarily fails
            cache_key = _generate_cache_key("compute_arch_diversity", lat, lon, radius_m)
            current_time = time.time()
            stale_cache_entry = None
            stale_cache_time = 0
            
            # Try Redis first
            redis_client = _get_redis_client()
            if redis_client:
                try:
                    cached_data = redis_client.get(cache_key)
                    if cached_data:
                        data = json.loads(cached_data)
                        stale_cache_entry = data.get('value')
                        stale_cache_time = data.get('timestamp', 0)
                except Exception:
                    pass
            
            # Fall back to in-memory cache
            if stale_cache_entry is None and cache_key in _cache:
                stale_cache_entry = _cache.get(cache_key)
                stale_cache_time = _cache_ttl.get(cache_key, 0)
            
            # Use stale cache if it exists and is less than 24 hours old
            # Only use if it doesn't have an error (has actual data)
            if stale_cache_entry and isinstance(stale_cache_entry, dict):
                cache_age_hours = (current_time - stale_cache_time) / 3600
                has_error = stale_cache_entry.get('error') is not None
                has_data = stale_cache_entry.get('levels_entropy', 0) > 0 or stale_cache_entry.get('building_type_diversity', 0) > 0
                
                if not has_error and has_data and cache_age_hours < 24:
                    logger.warning(f"API failed, using stale cache (age: {cache_age_hours:.1f} hours) for architectural diversity")
                    result = stale_cache_entry.copy()
                    result['_stale_cache'] = True
                    result['_cache_age_hours'] = round(cache_age_hours, 1)
                    result['data_warning'] = 'stale_cache_used'
                    result['confidence_0_1'] = max(0.0, result.get('confidence_0_1', 1.0) * (1.0 - (cache_age_hours / 24.0)))
                    return result
            
            # No usable stale cache - return error with zeros
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
                "retry_suggested": True,
                # Don't skip cache - allow stale cached data to be used if available
                # The cache decorator will handle TTL appropriately
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
                "note": "No buildings found in OSM",
                # Don't skip cache - this is valid data (no buildings = legitimate result)
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
            "error": f"Timeout: {str(e)}",
            # Don't skip cache - allow stale cached data to be used if available
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
            "error": f"Network error: {str(e)}",
            # Don't skip cache - allow stale cached data to be used if available
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
            "error": str(e),
            # Don't skip cache - allow stale cached data to be used if available
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

    def _categorize_building(tags: Dict[str, str]) -> str:
        btag = (tags.get("building:use") or tags.get("building") or "").lower()
        amenity = (tags.get("amenity") or "").lower()
        tourism = (tags.get("tourism") or "").lower()
        office = (tags.get("office") or "").lower()
        shop = (tags.get("shop") or "").lower()

        def _match_any(value: str, keywords: tuple) -> bool:
            return any(k in value for k in keywords if k)

        if _match_any(btag, ("residential", "apart", "house", "condo", "terrace")):
            return "residential"
        if _match_any(amenity, ("school", "college", "university")) or _match_any(btag, ("school", "dorm")):
            return "educational"
        if _match_any(amenity, ("hospital", "clinic")) or _match_any(btag, ("hospital", "medical")):
            return "healthcare"
        if _match_any(amenity, ("church", "synagogue", "mosque", "temple")) or amenity == "place_of_worship":
            return "religious"
        if _match_any(amenity, ("museum", "theatre", "library")) or _match_any(tourism, ("museum", "gallery")):
            return "cultural"
        if _match_any(amenity, ("park", "community_centre", "social_centre")) or "civic" in btag:
            return "civic"
        if _match_any(shop, ("mall", "supermarket", "retail")) or _match_any(btag, ("retail", "commercial", "store")):
            return "retail"
        if _match_any(office, ("company", "headquarters")) or "office" in btag:
            return "office"
        if _match_any(btag, ("industrial", "warehouse", "manufacture", "factory")):
            return "industrial"
        if "historic" in btag or "heritage" in btag or tourism == "attraction":
            return "landmark"
        return "other"

    MATERIAL_CANONICAL = {
        "brick": {"brick", "masonry"},
        "stone": {"stone"},
        "wood": {"wood", "timber"},
        "concrete": {"concrete"},
        "glass": {"glass"},
        "steel": {"steel"},
        "metal": {"metal", "aluminium", "copper"},
        "stucco": {"stucco", "plaster"},
        "clay": {"clay", "adobe"},
        "composite": {"composite", "mixed"},
    }

    def _infer_material_from_type(tags: Dict[str, str], lat: float, lon: float) -> Optional[str]:
        """
        Infer building material from building type and geographic region.
        Returns normalized material name or None if inference not possible.
        """
        btag = (tags.get("building:use") or tags.get("building") or "").lower()
        amenity = (tags.get("amenity") or "").lower()
        
        # Geographic heuristics (latitude-based)
        # Northern regions (lat > 40): More brick/stone (heating needs)
        # Southern regions (lat < 35): More wood/stucco (cooling needs)
        # Coastal regions: More wood (proximity to lumber)
        is_northern = lat > 40.0
        is_southern = lat < 35.0
        
        # Residential buildings
        if any(k in btag for k in ("residential", "house", "apart", "condo", "terrace", "detached", "semidetached_house")):
            if is_northern:
                return "brick"  # Northern residential: typically brick
            elif is_southern:
                return "wood"  # Southern residential: typically wood frame
            else:
                return "brick"  # Default: brick
        
        # Commercial/retail
        if any(k in btag for k in ("commercial", "retail", "shop", "store")) or amenity in ("shop", "supermarket"):
            if is_northern:
                return "brick"  # Northern commercial: brick/stone
            else:
                return "concrete"  # Modern commercial: concrete/steel
        
        # Office buildings
        if "office" in btag or tags.get("office"):
            return "concrete"  # Modern offices: concrete/steel
        
        # Industrial
        if any(k in btag for k in ("industrial", "warehouse", "factory")):
            return "metal"  # Industrial: steel/metal
        
        # Religious/civic (historic buildings more likely)
        if amenity in ("place_of_worship", "church", "cathedral") or "church" in btag:
            if is_northern:
                return "stone"  # Northern churches: stone
            else:
                return "brick"  # Southern churches: brick
        
        # Default inference
        if is_northern:
            return "brick"
        else:
            return "wood"
    
    def _normalize_material(value: str) -> str:
        val = (value or "").lower().strip()
        for canonical, synonyms in MATERIAL_CANONICAL.items():
            if val in synonyms:
                return canonical
        if "brick" in val:
            return "brick"
        if "stone" in val:
            return "stone"
        if "wood" in val or "timber" in val:
            return "wood"
        if "concrete" in val:
            return "concrete"
        if "glass" in val:
            return "glass"
        if "steel" in val or "metal" in val:
            return "metal"
        if "stucco" in val or "plaster" in val:
            return "stucco"
        if "clay" in val or "adobe" in val:
            return "clay"
        if not val:
            return ""
        return val

    # Separate ways and nodes
    ways = [e for e in elements if e.get("type") == "way"]
    nodes_dict = {e.get("id"): e for e in elements if e.get("type") == "node"}
    
    # Tag availability tracking
    total_buildings = len(ways)
    buildings_with_levels_tag = 0
    buildings_with_material_tag = 0
    buildings_with_material_inferred = 0
    buildings_with_type_tag = 0
    buildings_with_any_tag = 0
    
    # Building levels histogram (bins)
    bins = {"1":0, "2":0, "3-4":0, "5-8":0, "9+":0}
    types = {}
    type_categories: Dict[str, int] = {}
    areas = []
    materials: Dict[str, int] = {}
    material_groups: Dict[str, int] = {}
    material_tagged = 0
    heritage_buildings = 0
    heritage_designations: Dict[str, int] = {}
    historic_flags = 0
    level_values = []
    inferred_single_story = 0
    
    for e in ways:
        tags = e.get("tags", {})
        
        # Track tag availability
        if tags.get("building:levels") is not None:
            buildings_with_levels_tag += 1
        if tags.get("building:material") is not None:
            buildings_with_material_tag += 1
        if tags.get("building") or tags.get("building:use"):
            buildings_with_type_tag += 1
        if tags:
            buildings_with_any_tag += 1
        
        btype = tags.get("building") or "unknown"
        types[btype] = types.get(btype, 0) + 1
        category = _categorize_building(tags)
        type_categories[category] = type_categories.get(category, 0) + 1
        
        lv_raw = tags.get("building:levels")
        lv = None
        if lv_raw is not None:
            try:
                # Try to parse as float first (handles "2.5" -> 2, "3.0" -> 3)
                lv_float = float(str(lv_raw).strip())
                # Round to nearest integer (2.5 -> 3, 2.4 -> 2)
                lv = int(round(lv_float))
                # Validate: must be positive and reasonable (1-200 floors)
                if lv < 1 or lv > 200:
                    lv = None
            except (ValueError, TypeError, AttributeError):
                # Invalid value (e.g., "unknown", "mixed", empty string)
                lv = None
        
        if lv is None:
            bins["1"] += 1
            inferred_single_story += 1
            level_values.append(1)
        elif lv == 1:
            bins["1"] += 1
            level_values.append(1)
        elif lv == 2:
            bins["2"] += 1
            level_values.append(2)
        elif 3 <= lv <= 4:
            bins["3-4"] += 1
            level_values.append(lv)
        elif 5 <= lv <= 8:
            bins["5-8"] += 1
            level_values.append(lv)
        else:
            bins["9+"] += 1
            level_values.append(lv)
        
        material = tags.get("building:material")
        material_inferred = False
        if not material:
            # Infer material when tag is missing
            inferred_material = _infer_material_from_type(tags, lat, lon)
            if inferred_material:
                material = inferred_material
                material_inferred = True
                buildings_with_material_inferred += 1
        else:
            material_tagged += 1
        
        if material:
            normalized_material = _normalize_material(material)
            materials[material] = materials.get(material, 0) + 1
            if normalized_material:
                material_groups[normalized_material] = material_groups.get(normalized_material, 0) + 1
        heritage_val = tags.get("heritage")
        if heritage_val:
            heritage_buildings += 1
            heritage_designations[heritage_val] = heritage_designations.get(heritage_val, 0) + 1
        if tags.get("historic"):
            historic_flags += 1
        
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

    # Log tag availability statistics
    if total_buildings > 0:
        levels_tag_pct = (buildings_with_levels_tag / total_buildings) * 100
        material_tag_pct = (buildings_with_material_tag / total_buildings) * 100
        material_inferred_pct = (buildings_with_material_inferred / total_buildings) * 100
        material_total_pct = ((buildings_with_material_tag + buildings_with_material_inferred) / total_buildings) * 100
        type_tag_pct = (buildings_with_type_tag / total_buildings) * 100
        
        logger.info(
            f"[ARCH_DIVERSITY] Tag availability for {total_buildings} buildings at ({lat:.4f}, {lon:.4f}): "
            f"levels={buildings_with_levels_tag} ({levels_tag_pct:.1f}%), "
            f"material_tagged={buildings_with_material_tag} ({material_tag_pct:.1f}%), "
            f"material_inferred={buildings_with_material_inferred} ({material_inferred_pct:.1f}%), "
            f"material_total={buildings_with_material_tag + buildings_with_material_inferred} ({material_total_pct:.1f}%), "
            f"type={buildings_with_type_tag} ({type_tag_pct:.1f}%)"
        )
        
        # Log level tag distribution if available
        if buildings_with_levels_tag > 0:
            logger.debug(f"[ARCH_DIVERSITY] {buildings_with_levels_tag} buildings have height tags, "
                        f"{inferred_single_story} will be inferred as single-story")

    # Calculate entropy for height diversity
    # Log bin distribution before entropy calculation
    logger.debug(
        f"[ARCH_DIVERSITY] Level bins distribution: {bins}, "
        f"inferred_single_story={inferred_single_story}/{total_buildings}"
    )
    
    # Validate: if we have many buildings but very low diversity, it might indicate data quality issues
    raw_entropy = entropy(list(bins.values()))
    levels_entropy = raw_entropy * 100
    
    logger.debug(
        f"[ARCH_DIVERSITY] Height diversity: raw_entropy={raw_entropy:.4f}, "
        f"scaled_entropy={levels_entropy:.1f}"
    )
    
    # Data quality validation: flag suspiciously low height diversity
    # For suburban/exurban areas with 10+ buildings, height diversity < 5 suggests failed height queries
    height_diversity_warning = None
    if len(ways) >= 10 and levels_entropy < 5.0:
        # Check if most buildings are missing height data (all in "1" bin)
        if bins.get("1", 0) / len(ways) > 0.85:
            height_diversity_warning = "suspiciously_low_height_diversity"
            # Log warning for debugging
            logger.warning(
                f"Height diversity suspiciously low ({levels_entropy:.1f}) with {len(ways)} buildings. "
                f"Most buildings ({bins.get('1', 0)}/{len(ways)}) have missing/inferred height data. "
                f"Location: {lat:.4f}, {lon:.4f}"
            )
    
    type_div_raw = entropy(list(types.values()))
    type_div = type_div_raw * 100
    type_category_div = entropy(list(type_categories.values())) * 100 if type_categories else 0.0
    
    logger.debug(
        f"[ARCH_DIVERSITY] Type diversity: unique_types={len(types)}, "
        f"type_categories={len(type_categories)}, "
        f"raw_entropy={type_div_raw:.4f}, scaled={type_div:.1f}"
    )
    logger.debug(f"[ARCH_DIVERSITY] Area calculation: {len(areas)} buildings with valid areas")
    
    if len(areas) >= 2:
        mean_area = sum(areas)/len(areas)
        var = sum((a-mean_area)**2 for a in areas)/len(areas)
        std_area = var ** 0.5
        # Protect against zero mean_area (all areas are 0)
        if mean_area > 0:
            cv = std_area / mean_area
        else:
            cv = 0.0  # If all areas are 0, coefficient of variation is 0
        # Rescale CV based on observed distribution (95th percentile ~3.0 CV in practice)
        # This makes 100 truly mean "extremely inconsistent" not just "maxed out"
        # Typical CV values: 0.0-0.5 = very consistent, 0.5-1.5 = moderate, 1.5-3.0 = high, 3.0+ = extreme
        # Map to 0-100 scale where ~95th percentile (CV=3.0) maps to 95
        if cv <= 3.0:
            area_cv = (cv / 3.0) * 95  # Scale 0-3.0 CV to 0-95
        else:
            area_cv = 95 + min(5.0, (cv - 3.0) / 3.0 * 5.0)  # Scale 3.0+ CV to 95-100
        area_cv = max(0.0, min(100.0, area_cv))
        
        logger.debug(
            f"[ARCH_DIVERSITY] Footprint variation: mean_area={mean_area:.1f}m², "
            f"std={std_area:.1f}m², cv={cv:.4f}, scaled_cv={area_cv:.1f}"
        )
    else:
        area_cv = 0.0
        logger.debug(f"[ARCH_DIVERSITY] Footprint variation: insufficient data ({len(areas)} areas)")
    if level_values:
        mean_levels = sum(level_values) / len(level_values)
        variance_levels = sum((lv - mean_levels) ** 2 for lv in level_values) / len(level_values)
        std_levels = variance_levels ** 0.5
        
        # Additional validation for dense urban areas: if we have many buildings but very low std,
        # it might indicate data quality issues (e.g., all heights defaulted to 1)
        if len(ways) >= 50 and std_levels < 0.5 and mean_levels < 2.0:
            # Dense area with suspiciously uniform low heights - likely data quality issue
            logger.warning(
                f"Dense urban area ({len(ways)} buildings) with suspiciously uniform heights: "
                f"mean={mean_levels:.2f}, std={std_levels:.2f}, entropy={levels_entropy:.1f}. "
                f"Location: {lat:.4f}, {lon:.4f}. This may indicate failed height queries."
            )
    else:
        mean_levels = 0.0
        std_levels = 0.0
    single_story_share = inferred_single_story / len(ways) if ways else 0.0

    diversity_score = min(100.0, 0.4*levels_entropy + 0.4*type_div + 0.2*area_cv)
    
    logger.debug(
        f"[ARCH_DIVERSITY] Diversity score: levels={levels_entropy:.1f}*0.4 + "
        f"type={type_div:.1f}*0.4 + area={area_cv:.1f}*0.2 = {diversity_score:.1f}"
    )
    
    # Calculate built coverage ratio: sum of building areas / circle land area
    # This helps identify urban areas with lots of voids (low coverage = fragmented, less beautiful)
    circle_area_sqm = math.pi * (radius_m ** 2)
    total_built_area_sqm = sum(areas) if areas else 0.0
    built_coverage_ratio = (total_built_area_sqm / circle_area_sqm) if circle_area_sqm > 0 else 0.0
    
    logger.debug(
        f"[ARCH_DIVERSITY] Coverage calculation: total_built_area={total_built_area_sqm:.0f}m², "
        f"circle_area={circle_area_sqm:.0f}m², ratio={built_coverage_ratio:.4f}"
    )

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
    
    material_top = sorted(materials.items(), key=lambda item: (-item[1], item[0]))
    material_entropy = entropy(list(material_groups.values())) * 100 if material_groups else 0.0
    material_profile = [
        {
            "material": name,
            "count": count,
            "share": round(count / len(ways), 3) if ways else 0.0
        }
        for name, count in material_top[:5]
    ]
    material_summary = [
        {
            "material": name,
            "count": count,
            "share": round(count / len(ways), 3) if ways else 0.0
        }
        for name, count in sorted(material_groups.items(), key=lambda item: (-item[1], item[0]))[:5]
    ]
    type_category_profile = [
        {
            "category": name,
            "count": count,
            "share": round(count / len(ways), 3) if ways else 0.0
        }
        for name, count in sorted(type_categories.items(), key=lambda item: (-item[1], item[0]))
    ]
    heritage_profile = {
        "count": heritage_buildings,
        "designations": sorted(
            [{"value": val, "count": cnt} for val, cnt in heritage_designations.items()],
            key=lambda item: (-item["count"], item["value"])
        )[:5],
        "historic_tagged": historic_flags,
        "significance_score": min(
            100.0,
            heritage_buildings * 4 + len(heritage_designations) * 6 + historic_flags * 3
        )
    }
    
    return {
        "levels_entropy": round(levels_entropy, 1),
        "building_type_diversity": round(type_div, 1),
        "footprint_area_cv": round(area_cv, 1),
        "type_category_diversity": round(type_category_div, 1),
        "diversity_score": round(diversity_score, 1),
        "built_coverage_ratio": round(built_coverage_ratio, 3),  # 0.0-1.0 scale
        "osm_building_coverage": round(built_coverage_ratio, 2),  # For reporting (0.00-1.00)
        "beauty_valid": beauty_valid,  # Always True - no hard failure
        "data_warning": height_diversity_warning or data_warning,  # Height diversity warning or coverage warning
        "confidence_0_1": confidence_0_1,  # 1.0 if good, 0.6 if <50%, 0.4 if <30%
        "material_profile": {
            "tagged_ratio": round(material_tagged / len(ways), 3) if ways else 0.0,
            "materials": material_profile,
            "canonical": material_summary,
            "entropy": round(material_entropy, 1)
        },
        "heritage_profile": heritage_profile,
        "type_categories": type_category_profile,
        "height_stats": {
            "mean_levels": round(mean_levels, 2),
            "std_levels": round(std_levels, 2),
            "single_story_share": round(single_story_share, 3)
        }
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

# Ridge Regression Weights for Built Beauty Scoring
# Source: Statistical modeling per area type (see DESIGN_PRINCIPLES.md Addendum)
# Method: Ridge regression with per-area-type modeling
# Weights are normalized to sum to 1.0 per area type
# Global Ridge regression weights for Built Beauty scoring
# Based on regression analysis of 56 locations (R²=0.1626, MAE=5.84, RMSE=7.43)
# Feature order: [Norm Height Div, Norm Type Div, Norm Footprint Var, Norm Built Cov,
#                 Norm Block Grain, Norm Streetwall, Norm Setback, Norm Facade,
#                 Norm Landmark, Norm Year Built, Norm Brick Share, Norm Enhancer, Norm Rowhouse]
# Formula: score = INTERCEPT + sum(weight * norm_feature)
# INTERCEPT = 75.6854
BUILT_BEAUTY_WEIGHTS = {
    'norm_height_diversity': 0.3286,
    'norm_type_diversity': 0.4229,
    'norm_footprint_variation': -0.8548,
    'norm_built_coverage_ratio': 0.5236,
    'norm_block_grain': -1.4277,  # Negative: fine suburban blocks = monotonous, coarse urban = interesting
    'norm_streetwall_continuity': 2.3067,
    'norm_setback_consistency': 1.8698,
    'norm_facade_rhythm': 0.9434,
    'norm_landmark_count': -0.939,
    'norm_median_year_built': -0.4597,
    'norm_material_share_brick': 2.6261,  # Strongest positive predictor
    'norm_enhancer_bonus': -0.9777,  # Negative: modern glass/steel kills historic beauty
    'norm_rowhouse_bonus': 0.0  # No impact
}

BUILT_BEAUTY_INTERCEPT = 75.6854


def _score_with_ridge_regression(
    area_type: str,
    levels_entropy: float,
    building_type_diversity: float,
    footprint_area_cv: float,
    built_coverage_ratio: Optional[float],
    block_grain_value: Optional[float],
    streetwall_value: Optional[float],
    setback_value: Optional[float],
    facade_rhythm_value: Optional[float],
    historic_landmarks: Optional[int],
    median_year_built: Optional[int],
    material_profile: Optional[Dict[str, Any]],
    enhancer_bonus: float,
    rowhouse_indicator: float = 0.0,
    elevation_range: Optional[float] = None
) -> Tuple[float, Dict[str, float]]:
    """
    Score Built Beauty using global Ridge regression weights.
    
    This implements the statistical modeling approach based on regression analysis of 56 locations.
    Features are normalized to 0-1 range, then weighted by global Ridge regression coefficients.
    Formula: score = INTERCEPT + sum(weight * norm_feature)
    
    Args:
        area_type: Area type classification (unused in global model, kept for compatibility)
        levels_entropy: Height diversity (0-100)
        building_type_diversity: Type diversity (0-100)
        footprint_area_cv: Footprint variation (0-100)
        built_coverage_ratio: Built coverage (0.0-1.0)
        block_grain_value: Block grain metric (0-100)
        streetwall_value: Streetwall continuity (0-100)
        setback_value: Setback consistency (0-100)
        facade_rhythm_value: Facade rhythm (0-100)
        historic_landmarks: Count of historic landmarks
        median_year_built: Median year buildings were built
        material_profile: Material profile dict with brick share
        enhancer_bonus: Enhancer bonus score (0-8.0 typically)
        rowhouse_indicator: Rowhouse indicator (0.0-1.0)
        elevation_range: Elevation range in meters (unused, kept for compatibility)
    
    Returns:
        Tuple of (score, feature_contributions_dict)
    """
    # Normalize all features to 0-1 range
    norm_height_diversity = _clamp01(levels_entropy / 100.0)
    norm_type_diversity = _clamp01(building_type_diversity / 100.0)
    norm_footprint_variation = _clamp01(footprint_area_cv / 100.0)
    norm_built_coverage_ratio = _clamp01(built_coverage_ratio if built_coverage_ratio is not None else 0.0)
    norm_block_grain = _clamp01(block_grain_value / 100.0 if block_grain_value is not None else 0.0)
    norm_streetwall_continuity = _clamp01(streetwall_value / 100.0 if streetwall_value is not None else 0.0)
    norm_setback_consistency = _clamp01(setback_value / 100.0 if setback_value is not None else 0.0)
    norm_facade_rhythm = _clamp01(facade_rhythm_value / 100.0 if facade_rhythm_value is not None else 0.0)
    norm_landmark_count = _clamp01((historic_landmarks or 0) / 20.0)
    
    # Norm Year Built: median_year_built → 0-1 (older = higher)
    if median_year_built is not None:
        current_year = datetime.utcnow().year
        age_years = max(0.0, current_year - median_year_built)
        norm_median_year_built = _clamp01(age_years / 224.0)  # 0 years = 0.0, 224 years (1800) = 1.0
    else:
        norm_median_year_built = 0.0
    
    # Norm Material Share (Brick %): extract from material_profile
    brick_share = 0.0
    if material_profile and isinstance(material_profile, dict):
        materials = material_profile.get("materials", {})
        if isinstance(materials, dict):
            total_tagged = sum(materials.values())
            if total_tagged > 0:
                brick_count = materials.get("brick", 0) + materials.get("stone", 0)  # Stone often similar aesthetic
                brick_share = brick_count / total_tagged
    norm_material_share_brick = _clamp01(brick_share)
    
    # Norm Enhancer: enhancer_bonus (0-8.0) → 0-1
    norm_enhancer_bonus = _clamp01(enhancer_bonus / 8.0)
    
    # Norm Rowhouse: rowhouse_indicator (0.0-1.0) → already normalized
    norm_rowhouse_bonus = _clamp01(rowhouse_indicator)
    
    # Apply global Ridge regression: score = intercept + sum(weight * norm_feature)
    score = BUILT_BEAUTY_INTERCEPT
    feature_contributions: Dict[str, float] = {}
    
    score += BUILT_BEAUTY_WEIGHTS['norm_height_diversity'] * norm_height_diversity
    feature_contributions['norm_height_diversity'] = BUILT_BEAUTY_WEIGHTS['norm_height_diversity'] * norm_height_diversity
    
    score += BUILT_BEAUTY_WEIGHTS['norm_type_diversity'] * norm_type_diversity
    feature_contributions['norm_type_diversity'] = BUILT_BEAUTY_WEIGHTS['norm_type_diversity'] * norm_type_diversity
    
    score += BUILT_BEAUTY_WEIGHTS['norm_footprint_variation'] * norm_footprint_variation
    feature_contributions['norm_footprint_variation'] = BUILT_BEAUTY_WEIGHTS['norm_footprint_variation'] * norm_footprint_variation
    
    score += BUILT_BEAUTY_WEIGHTS['norm_built_coverage_ratio'] * norm_built_coverage_ratio
    feature_contributions['norm_built_coverage_ratio'] = BUILT_BEAUTY_WEIGHTS['norm_built_coverage_ratio'] * norm_built_coverage_ratio
    
    score += BUILT_BEAUTY_WEIGHTS['norm_block_grain'] * norm_block_grain
    feature_contributions['norm_block_grain'] = BUILT_BEAUTY_WEIGHTS['norm_block_grain'] * norm_block_grain
    
    score += BUILT_BEAUTY_WEIGHTS['norm_streetwall_continuity'] * norm_streetwall_continuity
    feature_contributions['norm_streetwall_continuity'] = BUILT_BEAUTY_WEIGHTS['norm_streetwall_continuity'] * norm_streetwall_continuity
    
    score += BUILT_BEAUTY_WEIGHTS['norm_setback_consistency'] * norm_setback_consistency
    feature_contributions['norm_setback_consistency'] = BUILT_BEAUTY_WEIGHTS['norm_setback_consistency'] * norm_setback_consistency
    
    score += BUILT_BEAUTY_WEIGHTS['norm_facade_rhythm'] * norm_facade_rhythm
    feature_contributions['norm_facade_rhythm'] = BUILT_BEAUTY_WEIGHTS['norm_facade_rhythm'] * norm_facade_rhythm
    
    score += BUILT_BEAUTY_WEIGHTS['norm_landmark_count'] * norm_landmark_count
    feature_contributions['norm_landmark_count'] = BUILT_BEAUTY_WEIGHTS['norm_landmark_count'] * norm_landmark_count
    
    score += BUILT_BEAUTY_WEIGHTS['norm_median_year_built'] * norm_median_year_built
    feature_contributions['norm_median_year_built'] = BUILT_BEAUTY_WEIGHTS['norm_median_year_built'] * norm_median_year_built
    
    score += BUILT_BEAUTY_WEIGHTS['norm_material_share_brick'] * norm_material_share_brick
    feature_contributions['norm_material_share_brick'] = BUILT_BEAUTY_WEIGHTS['norm_material_share_brick'] * norm_material_share_brick
    
    score += BUILT_BEAUTY_WEIGHTS['norm_enhancer_bonus'] * norm_enhancer_bonus
    feature_contributions['norm_enhancer_bonus'] = BUILT_BEAUTY_WEIGHTS['norm_enhancer_bonus'] * norm_enhancer_bonus
    
    score += BUILT_BEAUTY_WEIGHTS['norm_rowhouse_bonus'] * norm_rowhouse_bonus
    feature_contributions['norm_rowhouse_bonus'] = BUILT_BEAUTY_WEIGHTS['norm_rowhouse_bonus'] * norm_rowhouse_bonus
    
    # Clamp score to 0-100 range
    score = max(0.0, min(100.0, score))
    
    return score, feature_contributions

# Area-type-specific weights for beauty metrics (sum = 50 points)
# Phase 1 metrics:
#   height_diversity → Height variation (entropy)
#   historic_era_integrity → Type diversity
#   footprint_diversity → Footprint CV
# Form metrics (street geometry and building alignment):
#   block_grain → Street network fineness
#   streetwall_continuity → Building facade continuity along streets
#   setback_consistency → Building setback consistency (uniformity of setbacks)
#   facade_rhythm → Facade alignment (proportion of buildings aligned with mean setback)
AREA_TYPE_WEIGHTS = {
    "urban_core": {
        "height_diversity": 18,         # Design: height variation (reduced from 20)
        "historic_era_integrity": 10,   # Design: type diversity
        "footprint_diversity": 0,       # Design: footprint CV (not used for urban_core)
        "block_grain": 8,               # Form: street network fineness (reduced from 10)
        "streetwall_continuity": 8,     # Form: facade continuity (reduced from 10)
        "setback_consistency": 4,        # Form: setback uniformity
        "facade_rhythm": 2,             # Form: facade alignment
    },
    "urban_historic": {
        "height_diversity": 16,         # Design: height variation (reduced from 18)
        "historic_era_integrity": 17,   # Design: type diversity (emphasized)
        "footprint_diversity": 0,
        "block_grain": 6,               # Form: street network fineness (reduced from 8)
        "streetwall_continuity": 5,      # Form: facade continuity (reduced from 7)
        "setback_consistency": 4,       # Form: setback uniformity
        "facade_rhythm": 2,             # Form: facade alignment
    },
    "historic_urban": {  # Alias for urban_historic (uses same weights)
        "height_diversity": 18,
        "historic_era_integrity": 18,
        "footprint_diversity": 0,
        "block_grain": 7,
        "streetwall_continuity": 5,
        "setback_consistency": 2,
        "facade_rhythm": 0,
    },
    "urban_residential": {
        "height_diversity": 13,         # Design: height variation (reduced from 15)
        "historic_era_integrity": 10,   # Design: type diversity
        "footprint_diversity": 5,       # Design: footprint CV
        "block_grain": 8,               # Form: street network fineness (reduced from 10)
        "streetwall_continuity": 8,     # Form: facade continuity (reduced from 10)
        "setback_consistency": 4,       # Form: setback uniformity
        "facade_rhythm": 2,             # Form: facade alignment
    },
    "urban_core_lowrise": {
        "height_diversity": 16,         # Design: height variation (reduced from 18)
        "historic_era_integrity": 10,   # Design: type diversity
        "footprint_diversity": 0,
        "block_grain": 8,               # Form: street network fineness (reduced from 10)
        "streetwall_continuity": 10,    # Form: facade continuity (reduced from 12)
        "setback_consistency": 4,       # Form: setback uniformity
        "facade_rhythm": 2,             # Form: facade alignment
    },
    "suburban": {
        "height_diversity": 6,          # Design: height variation (less important)
        "historic_era_integrity": 14,   # emphasize vernacular variety
        "footprint_diversity": 0,
        "block_grain": 18,              # tighter street planning rewarded
        "streetwall_continuity": 8,
        "setback_consistency": 3,
        "facade_rhythm": 1,
    },
    "exurban": {
        "height_diversity": 2,
        "historic_era_integrity": 12,
        "footprint_diversity": 0,
        "block_grain": 21,
        "streetwall_continuity": 11,
        "setback_consistency": 3,
        "facade_rhythm": 1,
    },
    "rural": {
        "height_diversity": 0,          # Design: height variation (not relevant)
        "historic_era_integrity": 10,   # Design: type diversity
        "footprint_diversity": 0,
        "block_grain": 22,              # Form: street network fineness (reduced from 25)
        "streetwall_continuity": 13,    # Form: facade continuity (reduced from 15)
        "setback_consistency": 3,       # Form: setback uniformity (less important)
        "facade_rhythm": 2,             # Form: facade alignment
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

DESIGN_FORM_WEIGHTS = {
    "historic_urban": {"design": 0.82, "form": 0.18},
    "urban_core": {"design": 0.52, "form": 0.48},
    "urban_residential": {"design": 0.5, "form": 0.5},
    "urban_core_lowrise": {"design": 0.58, "form": 0.42},
    "suburban": {"design": 0.78, "form": 0.22},
    "exurban": {"design": 0.80, "form": 0.20},
    "rural": {"design": 0.82, "form": 0.18},
    "unknown": {"design": 0.6, "form": 0.4},
}

DESIGN_FORM_SCALE = {
    "historic_urban": {"design": 92.0, "form": 68.0},
    "urban_core": {"design": 62.0, "form": 54.0},
    "urban_residential": {"design": 54.0, "form": 46.0},
    "urban_core_lowrise": {"design": 60.0, "form": 50.0},
    "suburban": {"design": 66.0, "form": 48.0},
    "exurban": {"design": 78.0, "form": 55.0},
    "rural": {"design": 74.0, "form": 56.0},
    "unknown": {"design": 62.0, "form": 52.0},
}

COVERAGE_EXPECTATIONS = {
    "historic_urban": 0.34,
    "urban_core": 0.42,
    "urban_residential": 0.30,
    "urban_core_lowrise": 0.32,
    "suburban": 0.22,
    "exurban": 0.14,
    "rural": 0.10,
    "unknown": 0.25,
}

# Spacious historic districts have lower coverage expectations
# These are historic areas with significant open space (courtyards, gardens, plazas)
# Examples: Old San Juan (20.9%), Garden District New Orleans (19.8%)
SPACIOUS_HISTORIC_COVERAGE_EXPECTATION = 0.22  # 22% instead of 34% for historic_urban


def _is_spacious_historic_district(
    area_type: str,
    built_coverage_ratio: Optional[float],
    historic_landmarks: Optional[int],
    median_year_built: Optional[int],
    material_entropy: Optional[float] = None,
    footprint_cv: Optional[float] = None,
    pre_1940_pct: Optional[float] = None
) -> bool:
    """
    Detect spacious historic districts that should have relaxed coverage expectations.
    
    Criteria:
    - Low coverage (< 0.25) indicating significant open space
    - Historic context (landmarks or pre-1950 median year)
    - Uniform materials (low material entropy) OR low footprint variation (cohesive design)
    
    Note: Works for any area type, not just historic_urban, to handle misclassifications
    (e.g., Old San Juan classified as suburban, Garden District as urban_residential).
    
    Args:
        area_type: Area type classification
        built_coverage_ratio: Building coverage ratio (0.0-1.0)
        historic_landmarks: Count of historic landmarks
        median_year_built: Median year buildings were built
        material_entropy: Material diversity (lower = more uniform)
        footprint_cv: Footprint variation (lower = more uniform)
    
    Returns:
        True if this is a spacious historic district
    """
    # Must have low coverage (< 25%) indicating spacious design
    if built_coverage_ratio is None or built_coverage_ratio >= 0.25:
        return False
    
    # Must have historic context (landmarks OR pre-1950 median year OR significant pre-1940 buildings)
    # Lower threshold for landmarks (3 instead of 5) to catch places like Old San Juan
    # But be strict: if median year is modern (>= 1980), require strong historic core
    # Use pre_1940_pct if available (better signal than median year for areas with modern infill)
    has_historic_context = False
    
    # Best signal: significant pre-1940 building stock (handles modern infill in historic towns)
    if pre_1940_pct is not None and pre_1940_pct >= 0.30:  # 30%+ pre-1940 buildings
        has_historic_context = True
    elif median_year_built is not None and median_year_built < 1950:
        # Definitely historic: pre-1950 median year
        has_historic_context = True
    elif historic_landmarks and historic_landmarks >= 3:
        # Modern areas (>= 1980) with landmarks: likely modern infill, not truly historic
        # Only accept if median year is unknown or pre-1980 (could be historic with some infill)
        if median_year_built is None or median_year_built < 1980:
            has_historic_context = True
        # If median_year >= 1980, don't use landmark count alone (prevents modern areas like Durham)
    
    # For very low coverage (< 20%), be more lenient - assume spacious by design
    # This helps Old San Juan (20.9% coverage, 0 landmarks, null median year)
    # Also helps historic mountain/resort towns like Telluride with OSM data gaps
    if built_coverage_ratio < 0.21:
        # If it's already historic_urban, accept it
        if area_type == "historic_urban":
            return True
        # For other area types, still require some historic signal
        # But be more lenient - if coverage is very low, it's likely spacious by design
        if has_historic_context:
            return True
        # Special case: very low coverage + uniform materials = likely spacious historic
        # Only apply if we have actual material data (entropy > 0), not missing data (entropy = 0)
        if material_entropy is not None and material_entropy > 0 and material_entropy < 20:
            return True
        # Footprint coherence: only if we have data and it's very uniform
        if footprint_cv is not None and footprint_cv < 40:
            return True
        # For extremely low coverage (< 5%) in rural/exurban areas, consider architectural patterns
        # Historic mountain/resort towns often have very low coverage with significant pre-1940 stock
        # Even if OSM landmarks are missing, pre_1940_pct can indicate historic character
        if built_coverage_ratio < 0.05 and area_type in ("rural", "exurban"):
            # If we have pre-1940 buildings, likely historic (e.g., Telluride, Aspen)
            if pre_1940_pct is not None and pre_1940_pct >= 0.20:  # 20%+ pre-1940
                return True
    
    if not has_historic_context:
        return False
    
    # Must have uniform materials OR cohesive footprint pattern (intentional design)
    # Low material entropy = uniform materials (e.g., all brick, all stone)
    # Low footprint CV = uniform footprint sizes (cohesive design, not fragmented)
    is_uniform = False
    if material_entropy is not None and material_entropy < 30:
        is_uniform = True
    if footprint_cv is not None and footprint_cv < 50:
        is_uniform = True
    
    # For 20-25% coverage, require uniformity signal OR historic context
    return has_historic_context and is_uniform

MATERIAL_BONUS_WEIGHTS = {
    "historic_urban": 1.5,  # Increased from 1.15 (LLM emphasizes material coherence)
    "urban_core": 1.2,      # Increased from 1.0
    "urban_residential": 1.1,  # Increased from 0.9
    "urban_core_lowrise": 1.0,  # Increased from 0.95
    "suburban": 0.9,         # Increased from 0.85
    "exurban": 0.75,
    "rural": 0.65,
    "unknown": 0.85,         # Increased from 0.8
}

HERITAGE_BONUS_WEIGHTS = {
    "historic_urban": 1.15,
    "urban_core": 1.05,
    "urban_residential": 0.95,
    "urban_core_lowrise": 1.0,
    "suburban": 0.78,
    "exurban": 0.68,
    "rural": 0.6,
    "unknown": 0.72,
}

AGE_CONTEXT_WINDOWS = {
    "historic_urban": {"baseline": 55.0, "full": 140.0},
    "urban_residential": {"baseline": 45.0, "full": 120.0},
    "urban_core": {"baseline": 40.0, "full": 110.0},
    "urban_core_lowrise": {"baseline": 40.0, "full": 110.0},
    "suburban": {"baseline": 32.0, "full": 95.0},
    "exurban": {"baseline": 40.0, "full": 115.0},
    "rural": {"baseline": 45.0, "full": 120.0},
    "unknown": {"baseline": 40.0, "full": 110.0},
}

AGE_BONUS_MAX = 5.0
AGE_MIX_BONUS_MAX = 2.25
MODERN_FORM_BONUS_MAX = 6.0  # Increased from 4.0 (LLM emphasizes modern innovation)
ROWHOUSE_BONUS_MAX = 6.0
FORM_METRICS_CONFIDENCE_FLOOR = 0.05  # Renamed from PHASE23_CONFIDENCE_FLOOR

HERITAGE_STACK_CAPS = {
    "historic_urban": 6.5,
    "urban_residential": 6.0,
    "urban_core": 5.8,
    "urban_core_lowrise": 5.9,
    "suburban": 5.1,
    "exurban": 4.9,
    "rural": 4.9,
    "unknown": 5.5,
}


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _smoothstep(edge0: float, edge1: float, x: float) -> float:
    if edge1 <= edge0:
        return 1.0 if x >= edge1 else 0.0
    t = _clamp01((x - edge0) / (edge1 - edge0))
    return t * t * (3.0 - 2.0 * t)


def _age_percentile(effective_area_type: str, median_year_built: Optional[int]) -> float:
    if median_year_built is None:
        return 0.0
    try:
        year_val = float(median_year_built)
    except (TypeError, ValueError):
        return 0.0
    current_year = datetime.utcnow().year
    age_years = max(0.0, current_year - year_val)
    window = AGE_CONTEXT_WINDOWS.get(effective_area_type, AGE_CONTEXT_WINDOWS["unknown"])
    percentile = _smoothstep(window["baseline"], window["full"], age_years)
    # provide a gentle lift for exceptionally old fabric beyond the window
    if age_years > window["full"]:
        overshoot = min(40.0, age_years - window["full"])
        percentile = min(1.0, percentile + 0.15 * (overshoot / 40.0))
    return _clamp01(percentile)


def _normalize_vintage_share(vintage_share: Optional[float]) -> Optional[float]:
    if vintage_share is None:
        return None
    try:
        value = float(vintage_share)
    except (TypeError, ValueError):
        return None
    if value < 0:
        return None
    if value > 1.0:
        value = value / 100.0
    return _clamp01(value)


def _age_mix_balance(vintage_ratio: float) -> float:
    # Reward balanced mix between historic and newer fabric, peak near ~45% pre-war share
    balance = 1.0 - abs(vintage_ratio - 0.45) / 0.45
    return _clamp01(balance)


def _coherence_signal(setback_value: Optional[float],
                      facade_rhythm_value: Optional[float],
                      streetwall_value: Optional[float],
                      material_entropy: Optional[float],
                      height_std: Optional[float]) -> float:
    components: List[float] = []
    if setback_value is not None:
        components.append(_clamp01(setback_value / 100.0))
    if facade_rhythm_value is not None:
        components.append(_clamp01(facade_rhythm_value / 100.0))
    if streetwall_value is not None:
        components.append(_clamp01(streetwall_value / 100.0))
    if material_entropy is not None:
        # Lower entropy (more consistent materials) -> stronger coherence
        material_uniformity = _clamp01(1.0 - (material_entropy / 100.0))
        components.append(material_uniformity)
    if height_std is not None:
        # Lower std -> more uniform
        components.append(_clamp01(1.0 - min(height_std / 2.5, 1.0)))
    if not components:
        return 0.0
    return sum(components) / len(components)


def _confidence_gate(values: List[Optional[float]], floor: float = 0.15) -> float:
    usable = [v for v in values if v is not None and v > 0.0]
    if not usable:
        return 0.0
    avg = sum(usable) / len(usable)
    if avg <= floor:
        return 0.0
    # Normalize from floor → 1.0 range
    return _clamp01((avg - floor) / (1.0 - floor))


def _modern_material_share(material_profile: Optional[Dict[str, Any]]) -> float:
    if not isinstance(material_profile, dict):
        return 0.0
    buckets = material_profile.get("canonical") or material_profile.get("materials")
    if not isinstance(buckets, list):
        return 0.0
    modern_keys = {"glass", "metal", "steel", "concrete"}
    share_total = 0.0
    for item in buckets:
        if not isinstance(item, dict):
            continue
        name = (item.get("material") or "").lower()
        share = item.get("share")
        try:
            share_val = float(share)
        except (TypeError, ValueError):
            continue
        if name in modern_keys:
            share_total += share_val
    return _clamp01(share_total)


def _rowhouse_streetwall_proxy(area_type: str,
                               coverage: Optional[float],
                               setback_value: Optional[float],
                               facade_value: Optional[float],
                               footprint_cv: Optional[float],
                               confidence: Optional[float]) -> Optional[float]:
    """Synthesize streetwall continuity for rowhouse fabrics when direct data is absent."""
    if area_type not in ("urban_residential", "historic_urban"):
        return None
    if confidence is not None and confidence >= FORM_METRICS_CONFIDENCE_FLOOR:
        return None
    if coverage is None or coverage < 0.18:
        return None
    if setback_value is None or facade_value is None:
        return None

    footprint_cv = footprint_cv or 0.0

    setback_signal = _clamp01((setback_value - 55.0) / 35.0)
    facade_signal = _clamp01((facade_value - 55.0) / 35.0)
    footprint_signal = _clamp01(1.0 - (abs(footprint_cv - 95.0) / 70.0))
    coverage_signal = _clamp01((coverage - 0.18) / 0.14)

    proxy = 100.0 * (
        (0.4 * setback_signal) +
        (0.35 * facade_signal) +
        (0.15 * footprint_signal) +
        (0.10 * coverage_signal)
    )
    return proxy if proxy >= 55.0 else None


def _rowhouse_bonus(area_type: str,
                    built_coverage_ratio: Optional[float],
                    streetwall_value: Optional[float],
                    setback_value: Optional[float],
                    facade_rhythm_value: Optional[float],
                    levels_entropy: Optional[float],
                    building_type_diversity: Optional[float],
                    footprint_area_cv: Optional[float],
                    median_year_built: Optional[int],
                    heritage_landmark_count: int,
                    coherence_signal: float,
                    confidence_gate: float) -> float:
    """Detect cohesive rowhouse/brownstone fabrics and add a targeted bonus."""
    if area_type not in ("urban_residential", "historic_urban"):
        return 0.0
    if confidence_gate <= 0.0 or coherence_signal <= 0.55:
        return 0.0
    if built_coverage_ratio is None or not (0.28 <= built_coverage_ratio <= 0.62):
        return 0.0

    street_vals = [streetwall_value, setback_value, facade_rhythm_value]
    if any(v is None or v < 60.0 for v in street_vals):
        return 0.0

    levels_ok = levels_entropy is not None and levels_entropy <= 22.0
    type_ok = building_type_diversity is not None and building_type_diversity <= 32.0
    footprint_ok = footprint_area_cv is not None and 70.0 <= footprint_area_cv <= 130.0
    if not (levels_ok and type_ok and footprint_ok):
        return 0.0

    pre_war_signal = 0.0
    if median_year_built is not None and median_year_built <= 1955:
        pre_war_signal = _clamp01((1955 - median_year_built) / 55.0)
    heritage_signal = _clamp01(heritage_landmark_count / 30.0)

    def _midpoint_signal(value: float, target: float, tolerance: float) -> float:
        return _clamp01(1.0 - (abs(value - target) / tolerance))

    coherence_strength = min(street_vals) / 100.0
    footprint_signal = _midpoint_signal(footprint_area_cv or 0.0, 95.0, 45.0)
    levels_signal = _midpoint_signal(levels_entropy or 0.0, 12.0, 12.0)
    age_signal = max(pre_war_signal, heritage_signal)

    composite = (
        0.4 * coherence_strength +
        0.25 * footprint_signal +
        0.2 * levels_signal +
        0.15 * age_signal
    )
    composite *= _clamp01(coherence_signal) * _clamp01(confidence_gate + 0.25)

    return ROWHOUSE_BONUS_MAX * _clamp01(composite)


def _form_metrics_fallback(metric: str,
                      coverage: Optional[float],
                      levels_entropy: Optional[float],
                      building_type_diversity: Optional[float],
                      footprint_area_cv: Optional[float]) -> Optional[float]:
    if coverage is None:
        return None
    coverage = max(0.0, coverage)
    levels_entropy = levels_entropy if levels_entropy is not None else 0.0
    building_type_diversity = building_type_diversity if building_type_diversity is not None else 0.0
    footprint_area_cv = footprint_area_cv if footprint_area_cv is not None else 0.0

    if metric == "block_grain":
        if coverage >= 0.28:
            return 72.0
        if coverage >= 0.22:
            return 60.0
        if coverage >= 0.16:
            return 48.0
        if coverage >= 0.10:
            return 38.0
        return 30.0
    if metric == "streetwall":
        if coverage >= 0.28:
            return 78.0
        if coverage >= 0.22:
            return 62.0
        if coverage >= 0.16:
            return 45.0
        return 32.0
    if metric == "setback":
        if coverage >= 0.26 and levels_entropy < 12:
            return 82.0
        if coverage >= 0.22:
            return 70.0
        if coverage >= 0.16:
            return 58.0
        return 45.0
    if metric == "facade":
        if coverage >= 0.28 and building_type_diversity < 30:
            return 78.0
        if coverage >= 0.24:
            return 68.0
        if coverage >= 0.18:
            return 55.0
        return 42.0
    return None


def _apply_form_metric_confidence(value: Optional[float],
                              confidence: Optional[float],
                              fallback: Optional[float]) -> Tuple[Optional[float], bool, bool, Optional[float], Optional[float]]:
    raw_value = value
    if value is not None and confidence is not None and confidence >= FORM_METRICS_CONFIDENCE_FLOOR:
        return value, False, False, raw_value, confidence
    if fallback is not None:
        return fallback, True, False, raw_value, confidence
    if value is None:
        return None, False, True, raw_value, confidence
    return None, False, True, raw_value, confidence


def _serenity_bonus(area_type: str,
                    built_coverage_ratio: Optional[float],
                    streetwall_continuity: float,
                    block_grain: float,
                    density: Optional[float],
                    contextual_tags: Optional[List[str]] = None) -> float:
    """Reward intentional openness and calm street rhythm."""
    if built_coverage_ratio is None:
        return 0.0

    bonus = 0.0
    openness = max(0.0, 0.30 - built_coverage_ratio)
    rhythm = streetwall_continuity / 100.0
    grain = block_grain / 100.0
    is_historic = "historic" in (contextual_tags or [])

    # Historic areas and suburban/exurban/rural get serenity bonus
    if is_historic or area_type in ("suburban", "exurban", "rural"):
        calm_factor = (0.6 * rhythm) + (0.4 * (1.0 - grain))
        density_factor = 1.0
        if density is not None:
            if area_type in ("exurban", "rural"):
                density_factor = 0.5 + min(0.5, max(0.0, 3000 - density) / 6000)
            else:
                density_factor = 0.5 + min(0.5, max(0.0, 9000 - density) / 9000)

        ceiling = 4.0 if (is_historic or area_type == "suburban") else 8.0
        multiplier = 12.0 if (is_historic or area_type == "suburban") else 18.0
        bonus = min(ceiling, openness * multiplier * calm_factor * density_factor)

    return bonus


def _scenic_bonus(area_type: str,
                 footprint_area_cv: float,
                 building_type_diversity: float,
                 density: Optional[float]) -> float:
    """Additional boost for scenic low-density contexts (mountain/coastal towns)."""
    if area_type not in ("exurban", "rural"):
        return 0.0

    scenic = 0.0
    scenic += max(0.0, (footprint_area_cv - 55.0) / 45.0)
    scenic += max(0.0, (building_type_diversity - 25.0) / 75.0)
    if density is not None:
        scenic += max(0.0, (3500 - density) / 7000)

    return min(4.0, scenic * 4.0)


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
                                       effective: str, contextual_tags: Optional[List[str]] = None) -> None:
    """Adjustment 1: Historic organic growth - widen variance bands for organic neighborhoods."""
    if is_historic_organic_flag or (is_historic and footprint_area_cv > 70):
        targets["footprint"] = (50, 65, 95, 100)  # HIGH CV is GOOD for historic areas
        if is_historic_organic_flag:
            is_historic_tag = "historic" in (contextual_tags or [])
            if effective in ["urban_core", "urban_core_lowrise"] or is_historic_tag:
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


def _estimate_material_coherence(material_profile: Optional[Dict],
                                heritage_profile: Optional[Dict],
                                median_year_built: Optional[int],
                                is_historic: bool = False) -> float:
    """
    Fallback material coherence estimation when OSM tags missing.
    Based on heritage context and building age (research-backed patterns).
    
    LLM emphasizes material coherence, but OSM tagging is often incomplete.
    This provides reasonable fallback based on area characteristics.
    """
    if material_profile and material_profile.get("entropy", 0) > 0:
        return material_profile["entropy"]  # Use actual data if available
    
    # Fallback: Estimate based on heritage and age
    # Historic areas (pre-1950) often have uniform materials (brick, stone)
    if is_historic:
        if median_year_built and median_year_built < 1950:
            # Historic areas typically have uniform materials
            return 25.0  # Moderate entropy (coherent but not identical)
        if heritage_profile and heritage_profile.get("count", 0) >= 10:
            # High heritage = likely uniform materials
            return 30.0
    
    # Modern areas: Higher material diversity expected
    if median_year_built and median_year_built >= 1990:
        return 60.0  # Higher diversity for modern areas
    
    return 0.0  # Unknown


def _coherence_bonus_v2(levels_entropy: float, footprint_cv: float, 
                        area_type: str, material_entropy: float,
                        building_type_diversity: float,
                        contextual_tags: Optional[List[str]] = None) -> float:
    """
    Enhanced coherence bonus (0-7.5 points) based on LLM emphasis on unity/coherence.
    
    LLM rationale consistently emphasizes:
    - "High coherence" (Charleston, Beacon Hill)
    - "Unified material palette" (Rainbow Row, Back Bay)
    - "Cohesive streetscape" (Georgetown, Old Town Alexandria)
    
    This bonus rewards architectural unity appropriate to area type.
    """
    base_bonus = 0.0
    t = CONTEXT_TARGETS.get(area_type, CONTEXT_TARGETS["urban_core"])
    is_historic = "historic" in (contextual_tags or [])
    
    # Height coherence (for areas that value uniformity)
    if area_type in ("suburban", "urban_residential") or is_historic:
        h_band = t["height"]
        if levels_entropy <= h_band[2]:  # Within target range
            base_bonus += 2.0
        elif levels_entropy <= h_band[3]:  # Close to target
            base_bonus += 1.0
    
    # Footprint coherence (for planned communities and historic areas)
    if area_type == "suburban" or is_historic:
        f_band = t["footprint"]
        if footprint_cv <= f_band[2]:
            base_bonus += 2.0
        elif footprint_cv <= f_band[3]:
            base_bonus += 1.0
    
    # Material coherence (for historic areas - LLM emphasizes this heavily)
    if is_historic and material_entropy > 0:
        # Low entropy = high coherence (uniform materials)
        if material_entropy < 20:
            base_bonus += 3.0  # Strong bonus for material unity
        elif material_entropy < 30:
            base_bonus += 2.0
        elif material_entropy < 40:
            base_bonus += 1.0
    
    # Type coherence (for unified districts)
    if is_historic or area_type == "urban_residential":
        type_band = t["type"]
        if building_type_diversity <= type_band[2]:
            base_bonus += 1.5
        elif building_type_diversity <= type_band[3]:
            base_bonus += 0.5
    
    return min(7.5, base_bonus)


def _context_penalty(area_type: str, built_cov: Optional[float],
                     levels_entropy: float, type_div: float,
                     footprint_cv: Optional[float] = None,
                     contextual_tags: Optional[List[str]] = None) -> float:
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
    # Historic areas: No coverage penalty (organic voids like courtyards/gardens are beautiful)
    # Check via contextual_tags to include historic suburban areas
    if "historic" in (contextual_tags or []):
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
    vintage_share: Optional[float] = None,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    metric_overrides: Optional[Dict[str, float]] = None,
    material_profile: Optional[Dict[str, Any]] = None,
    heritage_profile: Optional[Dict[str, Any]] = None,
    type_category_diversity: Optional[float] = None,
    height_stats: Optional[Dict[str, Any]] = None,
    contextual_tags: Optional[List[str]] = None,
    pre_1940_pct: Optional[float] = None
) -> Tuple[float, Dict]:
    """
    Convert architectural diversity metrics to beauty score (0-50 points).
    
    Now includes form metrics: block_grain, streetwall_continuity, setback_consistency, and facade_rhythm.
    
    Args:
        levels_entropy: Height diversity (0-100)
        building_type_diversity: Type diversity (0-100)
        footprint_area_cv: Size variation (0-100)
        area_type: 'urban_core', 'suburban', 'exurban', 'rural', 'unknown'
        density: Optional population density for fine-tuning
        built_coverage_ratio: Optional built coverage ratio (0.0-1.0)
        historic_landmarks: Optional count of historic landmarks from OSM
        median_year_built: Optional median year buildings were built
        lat: Optional latitude for form metrics (block_grain, streetwall_continuity, setback_consistency, facade_rhythm)
        lon: Optional longitude for form metrics (block_grain, streetwall_continuity, setback_consistency, facade_rhythm)
    
    Returns:
        Beauty score out of 50 points (native range, no scaling)
    """
    metric_overrides = metric_overrides or {}
    applied_overrides: List[str] = []
    override_values: Dict[str, float] = {}
    # Initialize contextual_tags early to avoid scoping issues
    # Read parameter into local variable first to avoid Python scoping error
    _contextual_tags_param = contextual_tags
    contextual_tags = _contextual_tags_param if _contextual_tags_param is not None else []
    material_entropy = 0.0
    material_tagged_ratio = 0.0
    if isinstance(material_profile, dict):
        try:
            material_entropy = float(material_profile.get("entropy") or 0.0)
        except (TypeError, ValueError):
            material_entropy = 0.0
        try:
            material_tagged_ratio = float(material_profile.get("tagged_ratio") or 0.0)
        except (TypeError, ValueError):
            material_tagged_ratio = 0.0
    heritage_significance = 0.0
    heritage_landmark_count = 0
    if isinstance(heritage_profile, dict):
        try:
            heritage_significance = float(heritage_profile.get("significance_score") or 0.0)
        except (TypeError, ValueError):
            heritage_significance = 0.0
        heritage_landmark_count = heritage_profile.get("count", 0) or 0
    height_std = None
    single_story_share = None
    if isinstance(height_stats, dict):
        try:
            height_std = float(height_stats.get("std_levels"))
        except (TypeError, ValueError):
            height_std = None
        try:
            single_story_share = float(height_stats.get("single_story_share"))
        except (TypeError, ValueError):
            single_story_share = None

    def _clamp(value: float, lower: float, upper: float) -> float:
        return max(lower, min(upper, value))

    if "levels_entropy" in metric_overrides:
        try:
            levels_entropy = _clamp(float(metric_overrides["levels_entropy"]), 0.0, 100.0)
            applied_overrides.append("levels_entropy")
            override_values["levels_entropy"] = levels_entropy
        except (TypeError, ValueError):
            logger.warning(f"Ignoring invalid override for levels_entropy: {metric_overrides['levels_entropy']!r}")

    if "building_type_diversity" in metric_overrides:
        try:
            building_type_diversity = _clamp(float(metric_overrides["building_type_diversity"]), 0.0, 100.0)
            applied_overrides.append("building_type_diversity")
            override_values["building_type_diversity"] = building_type_diversity
        except (TypeError, ValueError):
            logger.warning(f"Ignoring invalid override for building_type_diversity: {metric_overrides['building_type_diversity']!r}")

    if "footprint_area_cv" in metric_overrides:
        try:
            footprint_area_cv = _clamp(float(metric_overrides["footprint_area_cv"]), 0.0, 100.0)
            applied_overrides.append("footprint_area_cv")
            override_values["footprint_area_cv"] = footprint_area_cv
        except (TypeError, ValueError):
            logger.warning(f"Ignoring invalid override for footprint_area_cv: {metric_overrides['footprint_area_cv']!r}")

    # Get contextual tags for scoring adjustments (if not provided)
    # Only fetch if we have an empty list (was None originally)
    if len(contextual_tags) == 0:
        try:
            from .data_quality import get_contextual_tags
            fetched_tags = get_contextual_tags(
                area_type, density, built_coverage_ratio, median_year_built,
                historic_landmarks, business_count=None, levels_entropy=levels_entropy,
                building_type_diversity=building_type_diversity, footprint_area_cv=footprint_area_cv
            )
            contextual_tags = fetched_tags if fetched_tags else []
        except Exception as e:
            logger.warning(f"Failed to get contextual tags: {e}, using empty list")
            # contextual_tags already initialized to [] above, so no need to reassign
    
    # Use base area type for targets (morphology), not effective type
    # This keeps targets aligned with actual density/coverage characteristics
    # Adjustments (bonuses, phase weights) use contextual_tags (characteristics)
    effective = area_type  # Keep as base type for targets
    is_historic_tag = "historic" in (contextual_tags or [])  # Define once for use throughout function
    targets = CONTEXT_TARGETS.get(effective, CONTEXT_TARGETS["urban_core"])
    targets = dict(targets)  # Copy to avoid mutating original
    type_diversity_used = building_type_diversity
    if type_category_diversity is not None:
        try:
            type_diversity_used = max(type_diversity_used, float(type_category_diversity))
        except (TypeError, ValueError):
            pass
    
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
                                       footprint_area_cv, effective, contextual_tags=contextual_tags)
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
    
    blend = DESIGN_FORM_WEIGHTS.get(effective, DESIGN_FORM_WEIGHTS["unknown"])

    # Import form metrics (street geometry and building alignment)
    from .street_geometry import (
        compute_block_grain, compute_streetwall_continuity,
        compute_setback_consistency, compute_facade_rhythm
    )
    from concurrent.futures import ThreadPoolExecutor
    
    # Calculate design metrics raw scores (0-100 scale, normalized to 0-16.67 for weighting)
    height_raw = _score_band(levels_entropy, targets["height"], max_points=16.67)
    type_raw = _score_band(type_diversity_used, targets["type"], max_points=16.67)
    
    if height_std is not None and height_std > 1.2:
        height_raw = min(16.67, height_raw + min(2.5, (height_std - 1.2) * 1.4))
    if single_story_share is not None and single_story_share > 0.65:
        height_raw *= 0.88
    if type_category_diversity is not None:
        try:
            diversity_gap = max(0.0, float(type_category_diversity) - building_type_diversity)
            if diversity_gap > 0:
                type_raw = min(16.67, type_raw + min(2.0, diversity_gap / 15.0 * 2.0))
        except (TypeError, ValueError):
            pass
    foot_raw = _score_band(footprint_area_cv, targets["footprint"], max_points=16.67)
    
    # Calculate form metrics (0-100 scale, normalized to 0-16.67 for weighting)
    # OPTIMIZATION: Run all form metrics in parallel for better performance
    block_grain_value: Optional[float] = None
    streetwall_value: Optional[float] = None
    setback_value: Optional[float] = None
    facade_rhythm_value: Optional[float] = None
    block_grain_confidence = 0.0
    streetwall_confidence = 0.0
    setback_confidence = 0.0
    facade_rhythm_confidence = 0.0
    
    if lat is not None and lon is not None:
        # Use 2km radius for form metrics (same as architectural diversity)
        # OPTIMIZATION: Fetch shared OSM data once for all form metrics
        from .street_geometry import _fetch_roads_and_buildings
        from concurrent.futures import TimeoutError as FutureTimeoutError
        
        # Fetch shared OSM data with timeout to prevent hanging
        # If this fails, form metrics will still work but may need to fetch their own data
        # NOTE: _fetch_roads_and_buildings is cached, so repeated requests won't hit OSM again
        shared_osm_data = None
        try:
            logger.debug("Fetching shared OSM data for form metrics (cached if available)...")
            # Wrap in timeout executor to prevent hanging
            with ThreadPoolExecutor(max_workers=1) as timeout_executor:
                future_shared = timeout_executor.submit(_fetch_roads_and_buildings, lat, lon, 2000)
                try:
                    shared_osm_data = future_shared.result(timeout=15)  # Reduced from 20s to 15s
                    if shared_osm_data is None:
                        logger.warning("Shared OSM data fetch returned None (likely rate limited), form metrics will try to fetch their own data")
                    else:
                        logger.debug("Shared OSM data fetched successfully, form metrics will use it")
                except FutureTimeoutError:
                    logger.warning("Shared OSM data fetch timed out after 20s, form metrics will try to fetch their own data")
                    shared_osm_data = None
        except Exception as e:
            logger.warning(f"Shared OSM data fetch failed: {e}, form metrics will try to fetch their own data")
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
                    logger.warning(f"Form metric {name} timed out after {timeout}s, marking as missing")
                    if name == "block_grain":
                        return {"block_grain": None, "coverage_confidence": 0.0}
                    elif name == "streetwall":
                        return {"streetwall_continuity": None, "coverage_confidence": 0.0}
                    elif name == "setback":
                        return {"setback_consistency": None, "coverage_confidence": 0.0}
                    else:  # facade_rhythm
                        return {"facade_rhythm": None, "coverage_confidence": 0.0}
                except Exception as e:
                    logger.warning(f"Form metric {name} failed: {e}, marking as missing")
                    if name == "block_grain":
                        return {"block_grain": None, "coverage_confidence": 0.0}
                    elif name == "streetwall":
                        return {"streetwall_continuity": None, "coverage_confidence": 0.0}
                    elif name == "setback":
                        return {"setback_consistency": None, "coverage_confidence": 0.0}
                    else:  # facade_rhythm
                        return {"facade_rhythm": None, "coverage_confidence": 0.0}

            # Reduced timeouts from 30s to 15s for faster failure (caching handles retries)
            block_grain_data = get_with_timeout(future_block, 15, "block_grain")
            streetwall_data = get_with_timeout(future_streetwall, 15, "streetwall")
            setback_data = get_with_timeout(future_setback, 15, "setback")
            facade_rhythm_data = get_with_timeout(future_facade, 15, "facade_rhythm")
        
        raw_block = block_grain_data.get("block_grain")
        block_grain_value = float(raw_block) if isinstance(raw_block, (int, float)) else None
        raw_block_conf = block_grain_data.get("coverage_confidence")
        block_grain_confidence = float(raw_block_conf) if isinstance(raw_block_conf, (int, float)) else 0.0
        
        raw_streetwall = streetwall_data.get("streetwall_continuity")
        streetwall_value = float(raw_streetwall) if isinstance(raw_streetwall, (int, float)) else None
        raw_street_conf = streetwall_data.get("coverage_confidence")
        streetwall_confidence = float(raw_street_conf) if isinstance(raw_street_conf, (int, float)) else 0.0
        
        raw_setback = setback_data.get("setback_consistency")
        setback_value = float(raw_setback) if isinstance(raw_setback, (int, float)) else None
        raw_setback_conf = setback_data.get("coverage_confidence")
        setback_confidence = float(raw_setback_conf) if isinstance(raw_setback_conf, (int, float)) else 0.0
        
        raw_facade = facade_rhythm_data.get("facade_rhythm")
        facade_rhythm_value = float(raw_facade) if isinstance(raw_facade, (int, float)) else None
        raw_facade_conf = facade_rhythm_data.get("coverage_confidence")
        facade_rhythm_confidence = float(raw_facade_conf) if isinstance(raw_facade_conf, (int, float)) else 0.0
    
    if "block_grain" in metric_overrides:
        try:
            block_grain_value = _clamp(float(metric_overrides["block_grain"]), 0.0, 100.0)
            applied_overrides.append("block_grain")
            override_values["block_grain"] = block_grain_value
        except (TypeError, ValueError):
            logger.warning(f"Ignoring invalid override for block_grain: {metric_overrides['block_grain']!r}")

    if "streetwall_continuity" in metric_overrides:
        try:
            streetwall_value = _clamp(float(metric_overrides["streetwall_continuity"]), 0.0, 100.0)
            applied_overrides.append("streetwall_continuity")
            override_values["streetwall_continuity"] = streetwall_value
        except (TypeError, ValueError):
            logger.warning(f"Ignoring invalid override for streetwall_continuity: {metric_overrides['streetwall_continuity']!r}")

    if "setback_consistency" in metric_overrides:
        try:
            setback_value = _clamp(float(metric_overrides["setback_consistency"]), 0.0, 100.0)
            applied_overrides.append("setback_consistency")
            override_values["setback_consistency"] = setback_value
        except (TypeError, ValueError):
            logger.warning(f"Ignoring invalid override for setback_consistency: {metric_overrides['setback_consistency']!r}")

    if "facade_rhythm" in metric_overrides:
        try:
            facade_rhythm_value = _clamp(float(metric_overrides["facade_rhythm"]), 0.0, 100.0)
            applied_overrides.append("facade_rhythm")
            override_values["facade_rhythm"] = facade_rhythm_value
        except (TypeError, ValueError):
            logger.warning(f"Ignoring invalid override for facade_rhythm: {metric_overrides['facade_rhythm']!r}")

    form_metrics_fallback_info: Dict[str, Dict[str, Optional[float]]] = {}

    block_fallback = _form_metrics_fallback(
        "block_grain",
        built_coverage_ratio,
        levels_entropy,
        building_type_diversity,
        footprint_area_cv
    )
    streetwall_fallback = _form_metrics_fallback(
        "streetwall",
        built_coverage_ratio,
        levels_entropy,
        building_type_diversity,
        footprint_area_cv
    )
    setback_fallback = _form_metrics_fallback(
        "setback",
        built_coverage_ratio,
        levels_entropy,
        building_type_diversity,
        footprint_area_cv
    )
    facade_fallback = _form_metrics_fallback(
        "facade",
        built_coverage_ratio,
        levels_entropy,
        building_type_diversity,
        footprint_area_cv
    )

    block_grain_value, block_fallback_used, block_dropped, block_raw_value, block_raw_confidence = _apply_form_metric_confidence(
        block_grain_value,
        block_grain_confidence,
        block_fallback
    )
    form_metrics_fallback_info["block_grain"] = {
        "fallback_used": block_fallback_used,
        "dropped": block_dropped,
        "fallback_value": block_grain_value if block_fallback_used else None,
        "raw_value": block_raw_value,
        "raw_confidence": block_raw_confidence
    }

    streetwall_value, streetwall_fallback_used, streetwall_dropped, streetwall_raw_value, streetwall_raw_confidence = _apply_form_metric_confidence(
        streetwall_value,
        streetwall_confidence,
        streetwall_fallback
    )
    form_metrics_fallback_info["streetwall_continuity"] = {
        "fallback_used": streetwall_fallback_used,
        "dropped": streetwall_dropped,
        "fallback_value": streetwall_value if streetwall_fallback_used else None,
        "raw_value": streetwall_raw_value,
        "raw_confidence": streetwall_raw_confidence
    }
    streetwall_proxy_used = False
    streetwall_proxy_value = _rowhouse_streetwall_proxy(
        effective,
        built_coverage_ratio,
        setback_value,
        facade_rhythm_value,
        footprint_area_cv,
        streetwall_confidence
    )
    if streetwall_proxy_value is not None and (
        streetwall_value is None or streetwall_confidence is None or streetwall_confidence < FORM_METRICS_CONFIDENCE_FLOOR
    ):
        streetwall_value = streetwall_proxy_value
        streetwall_confidence = max(streetwall_confidence or 0.0, FORM_METRICS_CONFIDENCE_FLOOR + 0.15)
        streetwall_proxy_used = True
        proxy_entry = form_metrics_fallback_info.setdefault("streetwall_continuity", {})
        proxy_entry.update({
            "fallback_used": True,
            "dropped": False,
            "fallback_value": streetwall_value,
            "raw_value": streetwall_raw_value,
            "raw_confidence": streetwall_raw_confidence,
            "proxy": "rowhouse"
        })

    setback_value, setback_fallback_used, setback_dropped, setback_raw_value, setback_raw_confidence = _apply_form_metric_confidence(
        setback_value,
        setback_confidence,
        setback_fallback
    )
    form_metrics_fallback_info["setback_consistency"] = {
        "fallback_used": setback_fallback_used,
        "dropped": setback_dropped,
        "fallback_value": setback_value if setback_fallback_used else None,
        "raw_value": setback_raw_value,
        "raw_confidence": setback_raw_confidence
    }

    facade_rhythm_value, facade_fallback_used, facade_dropped, facade_raw_value, facade_raw_confidence = _apply_form_metric_confidence(
        facade_rhythm_value,
        facade_rhythm_confidence,
        facade_fallback
    )
    form_metrics_fallback_info["facade_rhythm"] = {
        "fallback_used": facade_fallback_used,
        "dropped": facade_dropped,
        "fallback_value": facade_rhythm_value if facade_fallback_used else None,
        "raw_value": facade_raw_value,
        "raw_confidence": facade_raw_confidence
    }

    coherence_signal = _coherence_signal(
        setback_value,
        facade_rhythm_value,
        streetwall_value,
        material_entropy,
        height_std
    )
    confidence_gate = _confidence_gate(
        [setback_confidence, facade_rhythm_confidence, streetwall_confidence]
    )

    if (effective == "urban_residential" or is_historic_tag) and coherence_signal >= 0.6:
        coherence_floor = (coherence_signal - 0.6) / 0.4
        coherence_floor = _clamp01(coherence_floor)
        type_raw = max(type_raw, 8.5 + (coherence_floor * 7.0))

    scale_params = DESIGN_FORM_SCALE.get(effective, DESIGN_FORM_SCALE["unknown"])

    material_component = None
    if material_entropy > 0:
        material_component = (material_entropy / 100.0) * 16.67
        if material_tagged_ratio < 0.15:
            material_component *= 0.65
    design_components = [
        height_raw,
        type_raw,
        foot_raw,
        (setback_value / 100.0) * 16.67,
        (facade_rhythm_value / 100.0) * 16.67
    ]
    design_components = [c for c in design_components if c is not None]
    if (effective == "urban_residential" or is_historic_tag) and coherence_signal > 0.0:
        coherence_component = coherence_signal * 16.0
        if confidence_gate > 0.0:
            coherence_component *= 1.0 + (confidence_gate * 0.15)
        design_components.append(coherence_component)
    if material_component is not None:
        design_components.append(material_component)
    if design_components:
        design_total = sum(design_components)
        design_score = min(50.0, (design_total / (len(design_components) * 16.67)) * scale_params["design"])
    else:
        design_score = 0.0

    coverage_component = None
    # Calculate expected_coverage once (checking for spacious historic districts)
    # This will be used for both coverage component scoring and coverage cap logic
    expected_coverage = None
    is_spacious_historic = False
    if built_coverage_ratio is not None:
        # Check if this is a spacious historic district (relaxed expectations)
        # Use pre_1940_pct if provided (better signal for historic character than median year)
        is_spacious_historic = _is_spacious_historic_district(
            effective,
            built_coverage_ratio,
            historic_landmarks,
            median_year_built,
            material_entropy=material_entropy,
            footprint_cv=footprint_area_cv,
            pre_1940_pct=pre_1940_pct
        )
        
        if is_spacious_historic:
            # Use relaxed expectation for spacious historic districts
            # Apply to all area types, not just historic_urban
            expected_coverage = SPACIOUS_HISTORIC_COVERAGE_EXPECTATION
        else:
            expected_coverage = COVERAGE_EXPECTATIONS.get(effective, COVERAGE_EXPECTATIONS["unknown"])
    
    if built_coverage_ratio is not None:
        
        if expected_coverage > 0:
            normalized_coverage = max(0.0, min(1.2, built_coverage_ratio / expected_coverage))
            coverage_component = min(16.67, normalized_coverage * 16.67)
    form_components = [
        (block_grain_value / 100.0) * 16.67,
        (streetwall_value / 100.0) * 16.67,
    ]
    form_components = [c for c in form_components if c is not None]
    if coverage_component is not None:
        form_components.append(coverage_component)
    if form_components:
        form_total = sum(form_components)
        form_score = min(50.0, (form_total / (len(form_components) * 16.67)) * scale_params["form"])
    else:
        form_score = 0.0

    # REPLACED: Use Ridge regression for scoring instead of rule-based system
    # Compute modern_material_share for metadata
    modern_material_share = _modern_material_share(material_profile)
    
    # Compute rowhouse indicator (0.0-1.0) based on area type and characteristics
    rowhouse_indicator = 0.0
    if effective in ("urban_residential", "historic_urban"):
        if built_coverage_ratio is not None and 0.28 <= built_coverage_ratio <= 0.62:
            if (streetwall_value is not None and streetwall_value >= 60.0 and
                setback_value is not None and setback_value >= 60.0 and
                facade_rhythm_value is not None and facade_rhythm_value >= 60.0):
                if (levels_entropy is not None and levels_entropy <= 22.0 and
                    building_type_diversity is not None and building_type_diversity <= 32.0 and
                    footprint_area_cv is not None and 70.0 <= footprint_area_cv <= 130.0):
                    rowhouse_indicator = 1.0
                elif coherence_signal > 0.55 and confidence_gate > 0.0:
                    rowhouse_indicator = 0.7  # Partial match
    
    # Enhancer bonus is computed separately in built_beauty.py, set to 0 here
    # (Ridge regression will use it if passed, but it's not available in this function)
    enhancer_bonus = 0.0
    
    # Call Ridge regression scoring
    ridge_score_0_100, feature_contributions = _score_with_ridge_regression(
        area_type=effective,
        levels_entropy=levels_entropy,
        building_type_diversity=building_type_diversity,
        footprint_area_cv=footprint_area_cv,
        built_coverage_ratio=built_coverage_ratio,
        block_grain_value=block_grain_value,
        streetwall_value=streetwall_value,
        setback_value=setback_value,
        facade_rhythm_value=facade_rhythm_value,
        historic_landmarks=historic_landmarks,
        median_year_built=median_year_built,
        material_profile=material_profile,
        enhancer_bonus=enhancer_bonus,
        rowhouse_indicator=rowhouse_indicator,
        elevation_range=None
    )
    
    # Scale from 0-100 to 0-50 (native Built Beauty range)
    final_score = max(0.0, min(50.0, ridge_score_0_100 / 2.0))
    
    # Prepare data quality info for metadata
    data_quality_info = {
        "confidence_0_1": 1.0,
        "data_warning": None,
        "degradation_applied": False,
        "degradation_factor": 1.0,
        "coverage_ratio": None,
        "expected_coverage": expected_coverage,
        "actual_coverage": built_coverage_ratio
    }

    if "architecture_score" in metric_overrides:
        try:
            forced_score = _clamp(float(metric_overrides["architecture_score"]), 0.0, 50.0)
            applied_overrides.append("architecture_score")
            override_values["architecture_score"] = forced_score
            final_score = forced_score
        except (TypeError, ValueError):
            logger.warning(f"Ignoring invalid override for architecture_score: {metric_overrides['architecture_score']!r}")
    
    # Return score with metadata about Ridge regression and form metrics
    metadata = {
        "coverage_cap_applied": data_quality_info.get("degradation_applied", False),
        "original_score_before_cap": None,  # Not applicable with Ridge regression
        "cap_reason": None,  # Not applicable with Ridge regression
        "data_quality": data_quality_info,
        "scoring_method": "ridge_regression",
        "ridge_score_0_100": round(ridge_score_0_100, 1),
        "feature_contributions": {k: round(v, 3) for k, v in feature_contributions.items()},
        # Legacy fields for compatibility (set to 0 or None)
        "design_score": 0.0,
        "form_score": 0.0,
        "design_weight": 0.0,
        "form_weight": 0.0,
        "serenity_bonus": 0.0,
        "scenic_bonus": 0.0,
        "material_bonus": 0.0,
        "heritage_bonus": 0.0,
        "age_bonus": 0.0,
        "age_mix_bonus": 0.0,
        "modern_form_bonus": 0.0,
        "street_character_bonus": 0.0,
        "rowhouse_bonus": 0.0,
        "material_profile": material_profile,
        "heritage_profile": heritage_profile,
        "material_entropy": round(material_entropy, 1),
        "material_tagged_ratio": round(material_tagged_ratio, 3),
        "type_category_diversity": round(type_category_diversity, 1) if type_category_diversity is not None else None,
        "height_stats": height_stats,
        "expected_coverage": expected_coverage if expected_coverage is not None else COVERAGE_EXPECTATIONS.get(effective, COVERAGE_EXPECTATIONS["unknown"]),
        "age_percentile": None,
        "age_mix_balance": None,
        "age_coherence_signal": round(coherence_signal, 3),
        "age_confidence_gate": round(confidence_gate, 3),
        "modern_material_share": round(modern_material_share, 3),
        # Form metrics (street geometry and building alignment)
        "block_grain": block_grain_value,
        "block_grain_confidence": block_grain_confidence,
        "streetwall_continuity": streetwall_value,
        "streetwall_confidence": streetwall_confidence,
        "setback_consistency": setback_value,
        "setback_confidence": setback_confidence,
        "facade_rhythm": facade_rhythm_value,
        "facade_rhythm_confidence": facade_rhythm_confidence
    }
    metadata["synthetic_metrics"] = {
        "streetwall_proxy_used": streetwall_proxy_used
    }

    metadata["form_metrics_fallback"] = {
        "block_grain": form_metrics_fallback_info.get("block_grain"),
        "streetwall_continuity": form_metrics_fallback_info.get("streetwall_continuity"),
        "setback_consistency": form_metrics_fallback_info.get("setback_consistency"),
        "facade_rhythm": form_metrics_fallback_info.get("facade_rhythm"),
    }

    if applied_overrides:
        metadata["overrides_applied"] = sorted(set(applied_overrides))
        metadata["override_values"] = override_values
    
    return final_score, metadata
