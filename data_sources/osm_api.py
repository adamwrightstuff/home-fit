"""
OpenStreetMap API Client
Queries Overpass API for green spaces and nature features
"""

import os
import requests
import math
import time
import threading
import random
from typing import Dict, List, Tuple, Optional, Any
from .cache import cached, CACHE_TTL
from .error_handling import with_fallback, safe_api_call, handle_api_timeout
from .utils import haversine_distance, get_way_center
from .retry_config import RetryConfig, get_retry_config, RetryProfile
from logging_config import get_logger

logger = get_logger(__name__)

# Build list of Overpass endpoints (primary + fallbacks)
_default_overpass = os.environ.get("OVERPASS_URL")
_fallback_endpoints = [
    endpoint for endpoint in [
        _default_overpass.strip() if _default_overpass else None,
        "https://overpass-api.de/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter",
        "https://z.overpass-api.de/api/interpreter",
    ] if endpoint
]

# Deduplicate while preserving order
OVERPASS_URLS: List[str] = []
for endpoint in _fallback_endpoints:
    if endpoint not in OVERPASS_URLS:
        OVERPASS_URLS.append(endpoint)

if not OVERPASS_URLS:
    OVERPASS_URLS = ["https://overpass-api.de/api/interpreter"]

OVERPASS_URL = OVERPASS_URLS[0]
_overpass_thread_state = threading.local()


def _set_overpass_url_for_request(url: str) -> None:
    """Set the active Overpass endpoint for the current thread."""
    global OVERPASS_URL
    OVERPASS_URL = url
    _overpass_thread_state.current_url = url


def get_overpass_url() -> str:
    """Expose the currently active Overpass endpoint."""
    return getattr(_overpass_thread_state, "current_url", OVERPASS_URLS[0])


def _rotate_overpass_endpoint(current_index: int) -> int:
    """Select the next Overpass endpoint when the current one fails."""
    if len(OVERPASS_URLS) <= 1:
        return current_index
    next_index = (current_index + 1) % len(OVERPASS_URLS)
    if next_index != current_index:
        logger.warning(f"Switching Overpass endpoint to {OVERPASS_URLS[next_index]}")
    return next_index

# Global query throttling to avoid rate limiting
_last_query_time = 0.0
_query_lock = threading.Lock()
_BASE_MIN_QUERY_INTERVAL = 0.5  # Minimum 500ms between queries under normal conditions
_current_min_query_interval = _BASE_MIN_QUERY_INTERVAL

def _retry_overpass(
    request_fn,
    query_type: Optional[str] = None,
    profile: Optional[RetryProfile] = None,
    config: Optional[RetryConfig] = None,
    # Legacy parameters for backward compatibility
    attempts: Optional[int] = None,
    base_wait: Optional[float] = None,
    fail_fast: Optional[bool] = None
):
    """
    Retry with exponential backoff for Overpass requests.
    
    Uses centralized retry configuration system. Can be called with:
    1. query_type: "parks", "transit", "block_grain", etc. (uses profile mapping)
    2. profile: RetryProfile.CRITICAL, RetryProfile.NON_CRITICAL, etc.
    3. config: Custom RetryConfig object
    4. Legacy parameters: attempts, base_wait, fail_fast (for backward compatibility)
    
    Args:
        request_fn: Function that makes the request
        query_type: Type of query (e.g., "parks", "transit", "block_grain")
        profile: Retry profile to use (overrides query_type if provided)
        config: Custom retry configuration (overrides profile if provided)
        attempts: Legacy parameter - number of retry attempts
        base_wait: Legacy parameter - base wait time in seconds
        fail_fast: Legacy parameter - if True, give up after 2 attempts on rate limit
    """
    import time
    import requests
    
    # Determine retry configuration
    if config is not None:
        retry_config = config
    elif profile is not None:
        from .retry_config import RETRY_PROFILES
        retry_config = RETRY_PROFILES[profile]
    elif query_type is not None:
        retry_config = get_retry_config(query_type)
    elif attempts is not None or base_wait is not None or fail_fast is not None:
        # Legacy parameters - create config from them
        retry_config = RetryConfig(
            max_attempts=attempts or 4,
            base_wait=base_wait or 1.0,
            fail_fast=fail_fast or False,
            max_wait=10.0
        )
    else:
        # Default to standard profile
        retry_config = get_retry_config("standard")
    
    max_attempts = retry_config.max_attempts
    base_wait = retry_config.base_wait
    fail_fast = retry_config.fail_fast
    max_wait = retry_config.max_wait
    endpoint_idx = 0
    
    try:
        for i in range(max_attempts):
            current_endpoint = OVERPASS_URLS[endpoint_idx]
            _set_overpass_url_for_request(current_endpoint)
            # Throttle queries to avoid rate limiting *per attempt*
            global _last_query_time, _current_min_query_interval, _query_lock
            with _query_lock:
                time_since_last = time.time() - _last_query_time
                min_interval = _current_min_query_interval
                if time_since_last < min_interval:
                    remaining = min_interval - time_since_last
                    # Add small jitter to avoid aligned bursts
                    jitter = random.uniform(0, 0.25 * min_interval)
                    sleep_time = remaining + jitter
                    logger.debug(f"Throttling OSM query: waiting {sleep_time:.2f}s (interval={min_interval:.2f}s, jitter={jitter:.2f}s)")
                    time.sleep(sleep_time)
                _last_query_time = time.time()
            
            try:
                resp = request_fn()
                # Handle 429 rate limiting specifically
                if resp is not None and hasattr(resp, 'status_code'):
                    if resp.status_code == 429:
                        if not retry_config.retry_on_429:
                            logger.warning(f"OSM rate limited (429), not retrying (retry_on_429=False)")
                            return None
                        
                        # Rate limited - wait longer and retry
                        if retry_config.exponential_backoff:
                            retry_after = int(resp.headers.get('Retry-After', base_wait * (2 ** i)))
                        else:
                            retry_after = int(resp.headers.get('Retry-After', base_wait))
                        
                        # For rate limits, allow slightly longer waits (up to 15s) to respect Retry-After
                        # But cap to prevent excessive delays that hurt performance
                        # 15s is a good balance: respects OSM's rate limits without blocking requests too long
                        retry_after = min(retry_after, retry_config.max_wait, 15.0)  # Increased from 10s to 15s for rate limits
                        
                        # Increase minimum query interval adaptively
                        with _query_lock:
                            new_interval = min(_current_min_query_interval * 1.5, _BASE_MIN_QUERY_INTERVAL * 6)
                            if new_interval != _current_min_query_interval:
                                logger.debug(f"Increasing OSM min query interval to {new_interval:.2f}s due to 429")
                            _current_min_query_interval = new_interval
                        
                        # Smart fail_fast: Try all endpoints once before giving up
                        # This balances performance (doesn't wait forever) with reliability (tries all options)
                        # The cache decorator will use stale cache if available, so failing fast is acceptable
                        if fail_fast and i >= 1:
                            # Count how many endpoints we've tried
                            endpoints_tried = min(i + 1, len(OVERPASS_URLS))
                            
                            if endpoints_tried >= len(OVERPASS_URLS):
                                # We've tried all endpoints, fail fast to avoid long waits
                                # The cache decorator will use stale cache if available
                                logger.warning(f"OSM rate limited (429) on all {len(OVERPASS_URLS)} endpoints after {i+1} attempts, failing fast (cache will provide stale data if available)")
                                return None
                            else:
                                # Try next endpoint before giving up
                                logger.debug(f"OSM rate limited (429), trying endpoint {endpoints_tried+1}/{len(OVERPASS_URLS)} before fail_fast")
                        
                        if i < max_attempts - 1:
                            logger.warning(f"OSM rate limited (429), waiting {retry_after}s before retry ({i+1}/{max_attempts})...")
                            time.sleep(retry_after)
                            endpoint_idx = _rotate_overpass_endpoint(endpoint_idx)
                            continue
                        else:
                            logger.warning(f"OSM rate limited (429), max retries reached")
                            return None  # Return None instead of resp on final failure
                # Successful response - gently relax throttling back toward base
                with _query_lock:
                    if _current_min_query_interval > _BASE_MIN_QUERY_INTERVAL:
                        new_interval = max(_BASE_MIN_QUERY_INTERVAL, _current_min_query_interval * 0.85)
                        if new_interval != _current_min_query_interval:
                            logger.debug(f"Reducing OSM min query interval to {new_interval:.2f}s after successful response")
                        _current_min_query_interval = new_interval
                return resp
            except requests.exceptions.Timeout:
                if not retry_config.retry_on_timeout:
                    logger.warning(f"OSM request timeout, not retrying (retry_on_timeout=False)")
                    return None
                
                if i < max_attempts - 1:
                    if retry_config.exponential_backoff:
                        wait_time = base_wait * (2 ** i)
                    else:
                        wait_time = base_wait
                    wait_time = min(wait_time, max_wait)
                    logger.warning(f"OSM request timeout, waiting {wait_time:.1f}s before retry ({i+1}/{max_attempts})...")
                    time.sleep(wait_time)
                    endpoint_idx = _rotate_overpass_endpoint(endpoint_idx)
                    continue
                else:
                    logger.warning(f"OSM request timeout after {max_attempts} attempts")
                    return None  # Return None on final timeout
            except requests.exceptions.RequestException as e:
                if i < max_attempts - 1:
                    if retry_config.exponential_backoff:
                        wait_time = base_wait * (1.5 ** i)
                    else:
                        wait_time = base_wait
                    wait_time = min(wait_time, max_wait)
                    logger.warning(f"OSM network error, waiting {wait_time:.1f}s before retry ({i+1}/{max_attempts})...")
                    time.sleep(wait_time)
                    endpoint_idx = _rotate_overpass_endpoint(endpoint_idx)
                    continue
                else:
                    logger.warning(f"OSM network error after {max_attempts} attempts: {e}")
                    return None  # Return None on final error
            except Exception as e:
                if i == max_attempts - 1:
                    logger.warning(f"OSM unexpected error after {max_attempts} attempts: {e}")
                    return None
                if retry_config.exponential_backoff:
                    wait_time = base_wait * (1.5 ** i)
                else:
                    wait_time = base_wait
                wait_time = min(wait_time, max_wait)
                time.sleep(wait_time)
                endpoint_idx = _rotate_overpass_endpoint(endpoint_idx)
    finally:
        _set_overpass_url_for_request(OVERPASS_URLS[0])
    
    return None

DEBUG_PARKS = True  # Set False to silence park debugging


@cached(ttl_seconds=CACHE_TTL['osm_queries'])
@safe_api_call("osm", required=False)
@handle_api_timeout(timeout_seconds=20)  # Reduced from 30s
def query_green_spaces(lat: float, lon: float, radius_m: int = 1000) -> Optional[Dict]:
    """
    Query OSM for parks, playgrounds, recreational facilities, and tree features.
    INCLUDES RELATIONS to catch all parks!

    Returns:
        {
            "parks": [...],
            "playgrounds": [...],
            "recreational_facilities": [...],  # NEW: tennis courts, baseball fields, dog parks, etc.
            "tree_features": [...]
        }
    """
    # Core parks/playgrounds query used by Active Outdoors and Natural Beauty fallback.
    query = f"""
    [out:json][timeout:15];
    (
      // PARKS & GREEN SPACES - core (skip nodes except playgrounds)
      way["leisure"~"^(park|garden|dog_park|playground)$"](around:{radius_m},{lat},{lon});
      relation["leisure"~"^(park|garden|dog_park|playground)$"](around:{radius_m},{lat},{lon});
      way["landuse"~"^(park|recreation_ground|village_green)$"](around:{radius_m},{lat},{lon});
      relation["landuse"~"^(park|recreation_ground|village_green)$"](around:{radius_m},{lat},{lon});
      
      // Gardens (exclude private)
      way["leisure"="garden"]["garden:type"!="private"](around:{radius_m},{lat},{lon});
      relation["leisure"="garden"]["garden:type"!="private"](around:{radius_m},{lat},{lon});
      
      // Playgrounds - keep nodes as they're often point features
      node["leisure"="playground"](around:{radius_m},{lat},{lon});
      way["leisure"="playground"](around:{radius_m},{lat},{lon});
      relation["leisure"="playground"](around:{radius_m},{lat},{lon});
      
      // GREENWAYS & RECREATIONAL PATHS - outdoor recreational infrastructure
      // Capture cycleways (bike paths) and footways (walking paths) that are recreational
      // Filtering for sidewalks/private access happens in processing
      way["highway"="cycleway"]["access"!="private"](around:{radius_m},{lat},{lon});
      way["highway"="footway"]["access"!="private"](around:{radius_m},{lat},{lon});
      
      // RECREATIONAL FACILITIES - actual recreation: tennis courts, basketball, baseball fields, etc.
      // OBJECTIVE CRITERIA: leisure=pitch with sport tags, or leisure=dog_park
      // DATA QUALITY: Exclude private facilities (access=private)
      // These capture meaningful recreation without inflating with every pathway/greenway
      node["leisure"="pitch"]["sport"~"^(tennis|basketball|baseball|soccer|volleyball|football)$"]["access"!="private"](around:{radius_m},{lat},{lon});
      way["leisure"="pitch"]["sport"~"^(tennis|basketball|baseball|soccer|volleyball|football)$"]["access"!="private"](around:{radius_m},{lat},{lon});
      node["leisure"="dog_park"]["access"!="private"](around:{radius_m},{lat},{lon});
      way["leisure"="dog_park"]["access"!="private"](around:{radius_m},{lat},{lon});
    );
    out body;
    >;
    out skel qt;
    """

    try:
        def _do_request():
            return requests.post(
                get_overpass_url(),
                data={"data": query},
                timeout=20,  # Reduced from 40s for faster failure
                headers={"User-Agent": "HomeFit/1.0"}
            )

        # Parks are critical - use CRITICAL profile (retry all attempts)
        resp = _retry_overpass(_do_request, query_type="parks")

        if resp is None or resp.status_code != 200:
            if resp and resp.status_code == 429:
                logger.warning("OSM parks query rate limited (429)")
            elif resp:
                logger.warning(f"OSM parks query failed with status {resp.status_code}")
            else:
                logger.warning("OSM parks query returned no response")
            return None

        data = resp.json()
        elements = data.get("elements", [])
        
        # DIAGNOSTIC: Log raw park elements before processing
        raw_park_elements = [
            e for e in elements 
            if (e.get("tags", {}).get("leisure") in ["park", "garden", "dog_park", "playground", "recreation_ground"] or
                e.get("tags", {}).get("landuse") in ["park", "recreation_ground", "village_green"] or
                e.get("tags", {}).get("highway") in ["cycleway", "footway"])
        ]
        if raw_park_elements:
            logger.info(
                f"🔍 [PARKS DIAGNOSTIC] Found {len(raw_park_elements)} raw park/greenway elements "
                f"(types: {set(e.get('type') for e in raw_park_elements)}, "
                f"total elements: {len(elements)})",
                extra={
                    "pillar_name": "active_outdoors",
                    "lat": lat,
                    "lon": lon,
                    "raw_park_count": len(raw_park_elements),
                    "raw_park_types": [e.get("type") for e in raw_park_elements],
                    "total_elements": len(elements),
                }
            )
        elif not elements:
            logger.warning(
                f"🔍 [PARKS DIAGNOSTIC] OSM parks query returned empty results "
                f"for lat={lat}, lon={lon}, radius={radius_m}m",
                extra={
                    "pillar_name": "active_outdoors",
                    "lat": lat,
                    "lon": lon,
                    "radius_m": radius_m,
                }
            )

        parks, playgrounds, recreational_facilities = _process_green_features(
            elements, lat, lon)
        
        # DIAGNOSTIC: Log processed park results
        if len(parks) != len(raw_park_elements) and len(raw_park_elements) > 0:
            logger.warning(
                f"🔍 [PARKS DIAGNOSTIC] Processing filtered parks: "
                f"{len(raw_park_elements)} raw → {len(parks)} processed "
                f"(filtered: {len(raw_park_elements) - len(parks)})",
                extra={
                    "pillar_name": "active_outdoors",
                    "lat": lat,
                    "lon": lon,
                    "raw_count": len(raw_park_elements),
                    "processed_count": len(parks),
                    "filtered_count": len(raw_park_elements) - len(parks),
                }
            )
        elif len(parks) == 0 and len(elements) > 0:
            # Log warning if we got elements but no parks (might indicate processing issue)
            logger.warning(
                f"🔍 [PARKS DIAGNOSTIC] OSM parks query returned {len(elements)} elements "
                f"but 0 parks after processing (raw park elements: {len(raw_park_elements)})",
                extra={
                    "pillar_name": "active_outdoors",
                    "lat": lat,
                    "lon": lon,
                    "total_elements": len(elements),
                    "raw_park_elements": len(raw_park_elements),
                }
            )
        elif len(parks) > 0:
            logger.info(
                f"🔍 [PARKS DIAGNOSTIC] Successfully processed {len(parks)} parks "
                f"(playgrounds: {len(playgrounds)}, facilities: {len(recreational_facilities)})",
                extra={
                    "pillar_name": "active_outdoors",
                    "lat": lat,
                    "lon": lon,
                    "park_count": len(parks),
                    "playground_count": len(playgrounds),
                    "facility_count": len(recreational_facilities),
                }
            )

        if DEBUG_PARKS:
            logger.debug(f"Found {len(parks)} parks, {len(playgrounds)} playgrounds, {len(recreational_facilities)} recreational facilities")

        return {
            "parks": parks,
            "playgrounds": playgrounds,
            "recreational_facilities": recreational_facilities,  # NEW: tennis courts, baseball fields, dog parks
            # tree_features removed (not used by any pillar; kept parks/playgrounds only)
        }

    except Exception as e:
        logger.error(f"OSM parks query error: {e}", exc_info=True)
        return None


@cached(ttl_seconds=CACHE_TTL['osm_queries'])
@safe_api_call("osm", required=False)
@handle_api_timeout(timeout_seconds=25)  # Reduced from 40s
def query_nature_features(lat: float, lon: float, radius_m: int = 15000) -> Optional[Dict]:
    """
    Query OSM for outdoor recreation (hiking, swimming, camping).
    Includes trails within large parks (>50 hectares) to catch urban parks like Prospect Park.

    Returns:
        {
            "hiking": [...],
            "swimming": [...],
            "camping": [...]
        }
    """
    query = f"""
    [out:json][timeout:35];
    (
      // HIKING - Optimized: combined boundary types
      relation["route"="hiking"](around:{radius_m},{lat},{lon});
      way["boundary"~"^(national_park|protected_area)$"](around:{radius_m},{lat},{lon});
      relation["boundary"~"^(national_park|protected_area)$"](around:{radius_m},{lat},{lon});
      way["leisure"="nature_reserve"](around:{radius_m},{lat},{lon});
      relation["leisure"="nature_reserve"](around:{radius_m},{lat},{lon});
      
      // SKI TRAILS - Mountain recreation (piste:type)
      // RESEARCH-BACKED: Ski trails are legitimate outdoor recreation in mountain towns
      // Safe to include: Only significant in mountain areas (Park City: 1538, Times Square: 10)
      // This captures ski resort trails that aren't tagged as route=hiking
      way["piste:type"](around:{radius_m},{lat},{lon});
      relation["piste:type"](around:{radius_m},{lat},{lon});
      
      // SWIMMING - Optimized: combined water types
      way["natural"~"^(beach|coastline)$"](around:{radius_m},{lat},{lon});
      relation["natural"="beach"](around:{radius_m},{lat},{lon});
      way["natural"="water"]["water"~"^(lake|bay)$"](around:{radius_m},{lat},{lon});
      relation["natural"="water"]["water"~"^(lake|bay)$"](around:{radius_m},{lat},{lon});
      way["leisure"="swimming_area"](around:{radius_m},{lat},{lon});
      relation["leisure"="swimming_area"](around:{radius_m},{lat},{lon});
      
      // CAMPING
      // RESEARCH-BACKED: Many campsites in OSM are tagged as nodes (points), not ways/relations
      // Expand query to include nodes for better coverage
      node["tourism"="camp_site"](around:{radius_m},{lat},{lon});
      way["tourism"="camp_site"](around:{radius_m},{lat},{lon});
      relation["tourism"="camp_site"](around:{radius_m},{lat},{lon});
    );
    out body;
    >;
    out skel qt;
    """

    try:
        def _do_request():
            r = requests.post(
                get_overpass_url(),
                data={"data": query},
                timeout=25,  # Reduced from 50s for faster failure
                headers={"User-Agent": "HomeFit/1.0"}
            )
            if r.status_code != 200:
                raise RuntimeError(f"Overpass status={r.status_code}")
            return r

        # Nature features are non-critical (nice to have) - use NON_CRITICAL profile
        resp = _retry_overpass(_do_request, query_type="nature_features")
        if resp is None:
            return None
        data = resp.json()
        elements = data.get("elements", [])
        
        # DIAGNOSTIC: Log raw camping elements before processing
        raw_camping_elements = [
            e for e in elements 
            if e.get("tags", {}).get("tourism") == "camp_site"
        ]
        if raw_camping_elements:
            logger.info(
                f"🔍 [CAMPING DIAGNOSTIC] Found {len(raw_camping_elements)} raw camping elements "
                f"(types: {set(e.get('type') for e in raw_camping_elements)})",
                extra={
                    "pillar_name": "active_outdoors",
                    "lat": lat,
                    "lon": lon,
                    "raw_camping_count": len(raw_camping_elements),
                    "raw_camping_types": [e.get("type") for e in raw_camping_elements],
                }
            )

        hiking, swimming, camping = _process_nature_features(
            elements, lat, lon)
        
        # DIAGNOSTIC: Log processed camping results
        if len(camping) != len(raw_camping_elements):
            logger.warning(
                f"🔍 [CAMPING DIAGNOSTIC] Processing filtered camping: "
                f"{len(raw_camping_elements)} raw → {len(camping)} processed "
                f"(filtered: {len(raw_camping_elements) - len(camping)})",
                extra={
                    "pillar_name": "active_outdoors",
                    "lat": lat,
                    "lon": lon,
                    "raw_count": len(raw_camping_elements),
                    "processed_count": len(camping),
                    "filtered_count": len(raw_camping_elements) - len(camping),
                }
            )
        elif len(camping) > 0:
            logger.info(
                f"🔍 [CAMPING DIAGNOSTIC] Successfully processed {len(camping)} camping sites",
                extra={
                    "pillar_name": "active_outdoors",
                    "lat": lat,
                    "lon": lon,
                    "camping_count": len(camping),
                }
            )

        # Add trails from large parks (>50 hectares) to avoid missing urban parks like Prospect Park
        # This is a separate query to avoid overcounting urban sidewalks
        try:
            large_park_trails = _query_trails_in_large_parks(lat, lon, radius_m)
            hiking.extend(large_park_trails)
        except Exception as e:
            logger.warning(f"Large park trail query failed: {e}")

        return {
            "hiking": hiking,
            "swimming": swimming,
            "camping": camping
        }

    except Exception as e:
        logger.error(f"OSM nature query error: {e}", exc_info=True)
        return None


def query_enhanced_trees(lat: float, lon: float, radius_m: int = 1000) -> Optional[Dict]:
    """
    Enhanced tree query with comprehensive tree data from OSM.
    
    Returns:
        {
            "tree_rows": [...],
            "street_trees": [...],
            "individual_trees": [...],
            "tree_areas": [...]
        }
    """
    query = f"""
    [out:json][timeout:30];
    (
      // TREE ROWS
      way["natural"="tree_row"](around:{radius_m},{lat},{lon});
      
      // STREET TREES
      way["highway"]["trees"="yes"](around:{radius_m},{lat},{lon});
      way["highway"]["trees:both"="yes"](around:{radius_m},{lat},{lon});
      way["highway"]["trees:left"="yes"](around:{radius_m},{lat},{lon});
      way["highway"]["trees:right"="yes"](around:{radius_m},{lat},{lon});
      
      // INDIVIDUAL TREES
      node["natural"="tree"](around:{radius_m},{lat},{lon});
      
      // TREE AREAS
      way["natural"="wood"](around:{radius_m},{lat},{lon});
      way["landuse"="forest"](around:{radius_m},{lat},{lon});
      way["leisure"="park"]["trees"="yes"](around:{radius_m},{lat},{lon});
    );
    out body;
    >;
    out skel qt;
    """

    try:
        resp = requests.post(
            get_overpass_url(),
            data={"data": query},
            timeout=40,
            headers={"User-Agent": "HomeFit/1.0"}
        )

        if resp.status_code != 200:
            return None

        data = resp.json()
        elements = data.get("elements", [])

        tree_rows, street_trees, individual_trees, tree_areas = _process_enhanced_trees(
            elements, lat, lon)

        return {
            "tree_rows": tree_rows,
            "street_trees": street_trees,
            "individual_trees": individual_trees,
            "tree_areas": tree_areas
        }

    except Exception as e:
        logger.error(f"OSM enhanced tree query error: {e}", exc_info=True)
        return None


def query_cultural_assets(lat: float, lon: float, radius_m: int = 1000) -> Optional[Dict]:
    """
    Query OSM for cultural and artistic assets.
    
    Returns:
        {
            "museums": [...],
            "galleries": [...],
            "theaters": [...],
            "public_art": [...],
            "cultural_venues": [...]
        }
    """
    query = f"""
    [out:json][timeout:35];
    (
      // MUSEUMS
      node["tourism"="museum"](around:{radius_m},{lat},{lon});
      way["tourism"="museum"](around:{radius_m},{lat},{lon});
      
      // GALLERIES & ART SPACES
      node["tourism"="gallery"](around:{radius_m},{lat},{lon});
      way["tourism"="gallery"](around:{radius_m},{lat},{lon});
      node["shop"="art"](around:{radius_m},{lat},{lon});
      way["shop"="art"](around:{radius_m},{lat},{lon});
      
      // THEATERS & PERFORMANCE
      node["amenity"~"theatre|cinema"](around:{radius_m},{lat},{lon});
      way["amenity"~"theatre|cinema"](around:{radius_m},{lat},{lon});
      node["leisure"="arts_centre"](around:{radius_m},{lat},{lon});
      way["leisure"="arts_centre"](around:{radius_m},{lat},{lon});
      
      // PUBLIC ART
      node["tourism"="artwork"](around:{radius_m},{lat},{lon});
      way["tourism"="artwork"](around:{radius_m},{lat},{lon});
      node["amenity"="fountain"](around:{radius_m},{lat},{lon});
      way["amenity"="fountain"](around:{radius_m},{lat},{lon});
      
      // CULTURAL VENUES
      node["amenity"="community_centre"](around:{radius_m},{lat},{lon});
      way["amenity"="community_centre"](around:{radius_m},{lat},{lon});
      node["amenity"="library"](around:{radius_m},{lat},{lon});
      way["amenity"="library"](around:{radius_m},{lat},{lon});
    );
    out body;
    >;
    out skel qt;
    """

    try:
        def _do_request():
            return requests.post(
                get_overpass_url(),
                data={"data": query},
                timeout=45,
                headers={"User-Agent": "HomeFit/1.0"}
            )

        # Cultural assets are non-critical; use NON_CRITICAL retry profile via query_type mapping
        resp = _retry_overpass(_do_request, query_type="cultural_assets")
        if resp is None or resp.status_code != 200:
            if resp and resp.status_code == 429:
                logger.warning("OSM cultural assets query rate limited (429)")
            return None
        
        data = resp.json()
        elements = data.get("elements", [])
        
        museums, galleries, theaters, public_art, cultural_venues = _process_cultural_assets(
            elements, lat, lon)
        
        return {
            "museums": museums,
            "galleries": galleries,
            "theaters": theaters,
            "public_art": public_art,
            "cultural_venues": cultural_venues
        }
    
    except Exception as e:
        logger.error(f"OSM cultural assets query error: {e}", exc_info=True)
        return None


def query_charm_features(lat: float, lon: float, radius_m: int = 500) -> Optional[Dict]:
    """
    Query OSM for neighborhood charm features (historic buildings, fountains, public art).

    Returns:
        {
            "historic": [...],
            "artwork": [...]
        }
    """
    query = f"""
    [out:json][timeout:15];
    (
      // HISTORIC BUILDINGS - primary query (standard historic tag)
      node["historic"](around:{radius_m},{lat},{lon});
      way["historic"](around:{radius_m},{lat},{lon});
      relation["historic"](around:{radius_m},{lat},{lon});
      
      // HISTORIC BUILDINGS - alternative tags (for better coverage, especially in PR/international)
      node["heritage"](around:{radius_m},{lat},{lon});
      way["heritage"](around:{radius_m},{lat},{lon});
      node["building:historic"="yes"](around:{radius_m},{lat},{lon});
      way["building:historic"="yes"](around:{radius_m},{lat},{lon});
      
      // HISTORIC DISTRICTS - relations (e.g., National Historic Landmark Districts)
      relation["historic"="district"](around:{radius_m},{lat},{lon});
      relation["heritage"="2"](around:{radius_m},{lat},{lon});  // US National Register
      relation["heritage"="3"](around:{radius_m},{lat},{lon});  // US National Historic Landmark
      
      // PUBLIC ART & FOUNTAINS
      node["tourism"="artwork"](around:{radius_m},{lat},{lon});
      way["tourism"="artwork"](around:{radius_m},{lat},{lon});
      node["amenity"="fountain"](around:{radius_m},{lat},{lon});
      way["amenity"="fountain"](around:{radius_m},{lat},{lon});
    );
    out body;
    >;
    out skel qt;
    """

    try:
        def _do_request():
            return requests.post(
                get_overpass_url(),
                data={"data": query},
                timeout=35,
                headers={"User-Agent": "HomeFit/1.0"}
            )

        # Charm features are non-critical; use NON_CRITICAL retry profile via query_type mapping
        resp = _retry_overpass(_do_request, query_type="charm_features")
        if resp is None or resp.status_code != 200:
            if resp and resp.status_code == 429:
                logger.warning("OSM charm query rate limited (429)")
            return None
    
        data = resp.json()
        elements = data.get("elements", [])
    
        historic, artwork = _process_charm_features(elements, lat, lon)
    
        return {
            "historic": historic,
            "artwork": artwork
        }
    
    except Exception as e:
        logger.error(f"OSM charm query error: {e}", exc_info=True)
        return None


@cached(ttl_seconds=CACHE_TTL['osm_queries'])
@safe_api_call("osm", required=False)
@handle_api_timeout(timeout_seconds=60)
def query_local_businesses(lat: float, lon: float, radius_m: int = 1000, include_chains: bool = True) -> Optional[Dict]:
    """
    Query OSM for local businesses within walking distance.
    By default includes chain establishments.

    Args:
        include_chains: If True, include chain/franchise businesses

    Returns:
        {
            "tier1_daily": [...],
            "tier2_social": [...],
            "tier3_culture": [...],
            "tier4_services": [...]
        }
    """
    # Brand filter: exclude known chains by default
    if not include_chains:
        # Exclude major chains/franchises but allow local businesses with brand tags
        brand_filter = '''["brand"!~"McDonald's|Starbucks|Subway|KFC|Burger King|Pizza Hut|Domino's|Taco Bell|Wendy's|Dunkin'|Dunkin Donuts|7-Eleven|CVS|Walgreens|Rite Aid|Target|Walmart|Home Depot|Lowe's|Best Buy|Apple Store|AT&T|Verizon|T-Mobile|Chase|Bank of America|Wells Fargo|Citibank|FedEx|UPS|DHL|UPS Store|FedEx Office"]'''
    else:
        brand_filter = ''
    
    # Make name requirement optional - query businesses with or without names
    # We'll filter out unnamed businesses in processing if needed, but this allows us to
    # find businesses that exist in OSM even if they don't have names yet
    query = f"""
    [out:json][timeout:60];
    (
      // TIER 1: DAILY ESSENTIALS
      node["amenity"="cafe"]{brand_filter}(around:{radius_m},{lat},{lon});
      way["amenity"="cafe"]{brand_filter}(around:{radius_m},{lat},{lon});
      
      node["shop"="bakery"]{brand_filter}(around:{radius_m},{lat},{lon});
      way["shop"="bakery"]{brand_filter}(around:{radius_m},{lat},{lon});
      
      node["shop"~"supermarket|convenience|greengrocer"]{brand_filter}(around:{radius_m},{lat},{lon});
      way["shop"~"supermarket|convenience|greengrocer"]{brand_filter}(around:{radius_m},{lat},{lon});
      
      // TIER 2: SOCIAL & DINING
      node["amenity"="restaurant"]{brand_filter}(around:{radius_m},{lat},{lon});
      way["amenity"="restaurant"]{brand_filter}(around:{radius_m},{lat},{lon});
      
      node["amenity"~"bar|pub"]{brand_filter}(around:{radius_m},{lat},{lon});
      way["amenity"~"bar|pub"]{brand_filter}(around:{radius_m},{lat},{lon});
      
      node["amenity"="ice_cream"]{brand_filter}(around:{radius_m},{lat},{lon});
      node["shop"="ice_cream"]{brand_filter}(around:{radius_m},{lat},{lon});
      way["shop"="ice_cream"]{brand_filter}(around:{radius_m},{lat},{lon});
      
      // TIER 3: CULTURE & LEISURE
      node["shop"="books"]{brand_filter}(around:{radius_m},{lat},{lon});
      way["shop"="books"]{brand_filter}(around:{radius_m},{lat},{lon});
      
      node["tourism"="gallery"](around:{radius_m},{lat},{lon});
      way["tourism"="gallery"](around:{radius_m},{lat},{lon});
      node["shop"="art"](around:{radius_m},{lat},{lon});
      way["shop"="art"](around:{radius_m},{lat},{lon});
      
      node["amenity"~"theatre|cinema"](around:{radius_m},{lat},{lon});
      way["amenity"~"theatre|cinema"](around:{radius_m},{lat},{lon});
      
      node["tourism"="museum"](around:{radius_m},{lat},{lon});
      way["tourism"="museum"](around:{radius_m},{lat},{lon});
      
      node["amenity"="marketplace"](around:{radius_m},{lat},{lon});
      way["amenity"="marketplace"](around:{radius_m},{lat},{lon});
      
      // TIER 4: SERVICES & RETAIL
      node["shop"~"clothes|fashion|boutique"]{brand_filter}(around:{radius_m},{lat},{lon});
      way["shop"~"clothes|fashion|boutique"]{brand_filter}(around:{radius_m},{lat},{lon});
      
      node["shop"~"hairdresser|beauty"]{brand_filter}(around:{radius_m},{lat},{lon});
      way["shop"~"hairdresser|beauty"]{brand_filter}(around:{radius_m},{lat},{lon});
      
      node["shop"="music"]{brand_filter}(around:{radius_m},{lat},{lon});
      way["shop"="music"]{brand_filter}(around:{radius_m},{lat},{lon});
      
      node["leisure"="fitness_centre"]{brand_filter}(around:{radius_m},{lat},{lon});
      way["leisure"="fitness_centre"]{brand_filter}(around:{radius_m},{lat},{lon});
      
      node["shop"~"garden_centre|florist"]{brand_filter}(around:{radius_m},{lat},{lon});
      way["shop"~"garden_centre|florist"]{brand_filter}(around:{radius_m},{lat},{lon});
    );
    out body;
    >;
    out skel qt;
    """

    def _do_request():
        return requests.post(
            get_overpass_url(),
            data={"data": query},
            timeout=30,  # Reduced from 70s for faster failure
            headers={"User-Agent": "HomeFit/1.0"}
        )
    
    try:
        # Amenities are standard (important but not critical) - use STANDARD profile
        resp = _retry_overpass(_do_request, query_type="amenities")

        if resp is None or resp.status_code != 200:
            if resp and resp.status_code == 429:
                logger.warning("OSM business query rate limited (429)")
            return None

        data = resp.json()
        elements = data.get("elements", [])

        # Diagnostic logging for amenities queries
        if len(elements) == 0:
            logger.warning(
                f"🔍 [AMENITIES DIAGNOSTIC] OSM query returned 0 elements for lat={lat}, lon={lon}, radius={radius_m}m",
                extra={
                    "pillar_name": "neighborhood_amenities",
                    "lat": lat,
                    "lon": lon,
                    "radius_m": radius_m,
                    "include_chains": include_chains,
                }
            )
        else:
            logger.info(
                f"🔍 [AMENITIES DIAGNOSTIC] OSM query returned {len(elements)} raw elements",
                extra={
                    "pillar_name": "neighborhood_amenities",
                    "lat": lat,
                    "lon": lon,
                    "radius_m": radius_m,
                    "include_chains": include_chains,
                    "raw_elements_count": len(elements),
                }
            )

        businesses = _process_business_features(elements, lat, lon, include_chains)
        
        # Log processing results
        total_processed = sum(len(businesses.get(k, [])) for k in ["tier1_daily", "tier2_social", "tier3_culture", "tier4_services"])
        if len(elements) > 0 and total_processed == 0:
            logger.warning(
                f"🔍 [AMENITIES DIAGNOSTIC] OSM returned {len(elements)} elements but 0 businesses after processing",
                extra={
                    "pillar_name": "neighborhood_amenities",
                    "lat": lat,
                    "lon": lon,
                    "radius_m": radius_m,
                    "include_chains": include_chains,
                    "raw_elements_count": len(elements),
                    "processed_businesses_count": total_processed,
                }
            )
        
        return businesses

    except Exception as e:
        logger.error(f"OSM business query error: {e}", exc_info=True)
        return None


def _process_green_features(elements: List[Dict], center_lat: float, center_lon: float) -> Tuple[List[Dict], List[Dict], List[Dict]]:
    """
    Process OSM elements into parks, playgrounds, and recreational facilities.
    
    Returns:
        (parks, playgrounds, recreational_facilities)
        - parks: Green spaces, parks, greenways
        - playgrounds: Playgrounds (separate category)
        - recreational_facilities: Tennis courts, basketball courts, baseball fields, dog parks, etc.
    """
    parks = []
    playgrounds = []
    recreational_facilities = []  # NEW: tennis courts, baseball fields, dog parks, etc.
    nodes_dict = {}
    ways_dict = {}
    seen_park_ids = set()
    seen_playground_ids = set()
    seen_facility_ids = set()

    # Build nodes and ways dicts
    for elem in elements:
        if elem.get("type") == "node":
            nodes_dict[elem["id"]] = elem
        elif elem.get("type") == "way":
            ways_dict[elem["id"]] = elem

    debug_raw_candidates = []
    debug_kept_parks = []
    debug_skipped_parks = []

    # Process features
    for elem in elements:
        osm_id = elem.get("id")
        if not osm_id:
            continue

        tags = elem.get("tags", {})
        leisure = tags.get("leisure")
        landuse = tags.get("landuse")
        natural = tags.get("natural")
        highway = tags.get("highway")
        elem_type = elem.get("type")

        # GREENWAYS & RECREATIONAL PATHS - outdoor recreational infrastructure
        # Capture cycleways and footways that are recreational (not sidewalks/infrastructure)
        is_greenway = False
        if highway in ["cycleway", "footway"]:
            # Exclude sidewalks (standard urban infrastructure, not recreational)
            if tags.get("footway") == "sidewalk":
                continue  # Skip sidewalks
            
            # Exclude private/restricted access
            access = tags.get("access", "").lower()
            if access in ["private", "no", "restricted"]:
                continue  # Skip private/restricted paths
            
            # For footways, require either:
            # 1. Has a name tag (named recreational path like "Hudson Greenway")
            # 2. OR minimum length (will check after geometry calculation)
            # Cycleways are always included (bike paths are recreational)
            has_name = bool(tags.get("name"))
            if highway == "footway" and not has_name:
                # Will check length after geometry calculation
                # For now, mark as potential greenway (will filter by length later)
                pass
            
            is_greenway = True
        
        # Parks (exclude natural woods/forests/scrub from parks)
        is_park = leisure in ["park", "dog_park", "recreation_ground"] or \
           (leisure == "garden" and tags.get("garden:type") != "private") or \
           landuse in ["park", "recreation_ground", "village_green"]
        
        if is_park or is_greenway:

            if osm_id in seen_park_ids:
                continue
            seen_park_ids.add(osm_id)

            elem_lat, elem_lon, area_sqm = None, None, 0
            centroid_reason = "ok"
            way_length_m = 0.0  # For greenways, track length
            
            if elem_type == "way":
                elem_lat, elem_lon, area_sqm = _get_way_geometry(elem, nodes_dict)
                if elem_lat is None:
                    centroid_reason = "way-geometry-fail"
                else:
                    # For greenways (linear features), estimate length from geometry
                    if is_greenway:
                        # Calculate approximate length from way nodes
                        way_nodes = elem.get("nodes", [])
                        if len(way_nodes) >= 2:
                            # Estimate length by summing distances between consecutive nodes
                            total_length = 0.0
                            prev_node = None
                            for node_id in way_nodes:
                                node = nodes_dict.get(node_id)
                                if node and "lat" in node and "lon" in node:
                                    if prev_node:
                                        dist = haversine_distance(
                                            prev_node["lat"], prev_node["lon"],
                                            node["lat"], node["lon"]
                                        ) * 1000  # Convert km to meters
                                        total_length += dist
                                    prev_node = node
                            way_length_m = total_length
                        # For greenways, use small default area (they're linear, not areas)
                        # Area will be minimal contribution to park area scoring
                        # Use length-based estimate: assume 3m width for greenways
                        if area_sqm == 0 and way_length_m > 0:
                            area_sqm = max(1000, way_length_m * 3)  # 3m width estimate, min 0.1 ha
                        elif area_sqm == 0:
                            area_sqm = 1000  # Default 0.1 ha for linear greenways
            elif elem_type == "relation":
                elem_lat, elem_lon = _get_relation_centroid(elem, ways_dict, nodes_dict)
                area_sqm = 0
                if elem_lat is None:
                    centroid_reason = "relation-centroid-fail"
            elif elem_type == "node" and leisure == "park":
                elem_lat = elem.get("lat")
                elem_lon = elem.get("lon")
                area_sqm = 0
                if elem_lat is None or elem_lon is None:
                    centroid_reason = "node-coords-missing"

            distance_m = None
            if elem_lat is not None:
                distance_m = haversine_distance(center_lat, center_lon, elem_lat, elem_lon)

            park_debug = {
                "osm_id": osm_id,
                "name": tags.get("name"),
                "elem_type": elem_type,
                "centroid_reason": centroid_reason,
                "lat": elem_lat,
                "lon": elem_lon,
                "area_sqm": area_sqm,
                "distance_m": distance_m
            }

            # For greenways (footways without names), check minimum length
            if is_greenway and highway == "footway" and not tags.get("name"):
                # Require minimum length of 200m for unnamed footways
                # This filters out short paths/sidewalks while keeping recreational greenways
                # If we couldn't calculate length (no nodes), skip it (conservative)
                if way_length_m == 0.0 or way_length_m < 200.0:
                    debug_skipped_parks.append({**park_debug, "centroid_reason": f"footway-too-short-{way_length_m:.0f}m"})
                    if DEBUG_PARKS:
                        logger.debug(f"[GREENWAY SKIP] id={osm_id} name={tags.get('name')} length={way_length_m:.0f}m reason=footway-too-short")
                    continue
            
            # Exclude marinas/clubs from parks (not applicable to greenways)
            if is_park:
                name_val = (tags.get("name") or "").lower()
                is_marina = (tags.get("leisure") == "marina") or (tags.get("amenity") == "marina")
                has_club_tag = any(k == "club" for k in tags.keys())
                name_is_club = any(term in name_val for term in ["yacht club", "shore club", "country club", "beach club"]) if name_val else False
                if is_marina or has_club_tag or name_is_club:
                    debug_skipped_parks.append({**park_debug, "centroid_reason": "excluded-nonpublic"})
                    if DEBUG_PARKS:
                        logger.debug(f"[PARK SKIP] id={osm_id} name={tags.get('name')} type={elem_type} reason=excluded-nonpublic")
                    continue

            if elem_lat is None:
                debug_skipped_parks.append(park_debug)
                # DIAGNOSTIC: Log geometry failures (common issue)
                logger.warning(
                    f"🔍 [PARKS DIAGNOSTIC] Failed to get geometry for park "
                    f"osm_id={osm_id}, type={elem_type}, name={tags.get('name')}, reason={centroid_reason}",
                    extra={
                        "pillar_name": "active_outdoors",
                        "osm_id": osm_id,
                        "elem_type": elem_type,
                        "park_name": tags.get("name"),
                        "centroid_reason": centroid_reason,
                        "leisure": leisure,
                        "landuse": landuse,
                    }
                )
                if DEBUG_PARKS:
                    logger.debug(f"[PARK SKIP] id={osm_id} name={tags.get('name')} type={elem_type} reason={centroid_reason}")
                continue

            debug_raw_candidates.append(park_debug)

            # Determine name and type for greenways
            if is_greenway:
                greenway_name = tags.get("name") or f"{highway.title()} Path"
                greenway_type = f"greenway_{highway}"
            else:
                greenway_name = tags.get("name", _get_park_type_name(leisure, landuse, natural))
                greenway_type = leisure or landuse or natural

            parks.append({
                "name": greenway_name,
                "type": greenway_type,
                "lat": elem_lat,
                "lon": elem_lon,
                "distance_m": round(distance_m, 0) if distance_m is not None else None,
                "area_sqm": round(area_sqm, 0) if area_sqm else 0,
                "osm_id": osm_id
            })
    
    # Process playgrounds (separate from parks)
    for elem in elements:
        osm_id = elem.get("id")
        if not osm_id or osm_id in seen_playground_ids:
            continue
        
        tags = elem.get("tags", {})
        leisure = tags.get("leisure")
        elem_type = elem.get("type")
        access = tags.get("access", "").lower()
        
        # Only process playgrounds (leisure=playground)
        if leisure != "playground":
            continue
        
        # Skip private/restricted playgrounds
        if access in ["private", "no", "restricted"]:
            continue
        
        seen_playground_ids.add(osm_id)
        
        # Get coordinates and distance
        elem_lat, elem_lon = None, None
        if elem_type == "node":
            elem_lat = elem.get("lat")
            elem_lon = elem.get("lon")
        elif elem_type == "way":
            elem_lat, elem_lon, _ = _get_way_geometry(elem, nodes_dict)
        elif elem_type == "relation":
            elem_lat, elem_lon = _get_relation_centroid(elem, ways_dict, nodes_dict)
        
        if elem_lat is not None and elem_lon is not None:
            distance_m = haversine_distance(center_lat, center_lon, elem_lat, elem_lon)
            playgrounds.append({
                "name": tags.get("name", "Playground"),
                "type": "playground",
                "lat": elem_lat,
                "lon": elem_lon,
                "distance_m": round(distance_m, 0),
                "osm_id": osm_id
            })
    
    # NEW: Process recreational facilities (tennis courts, baseball fields, dog parks, etc.)
    # OBJECTIVE CRITERIA: leisure=pitch with sport tags, or leisure=dog_park
    # DATA QUALITY: Exclude private facilities, avoid double-counting with parks
    for elem in elements:
        osm_id = elem.get("id")
        if not osm_id or osm_id in seen_facility_ids:
            continue
        
        tags = elem.get("tags", {})
        leisure = tags.get("leisure")
        sport = tags.get("sport", "").lower()
        access = tags.get("access", "").lower()
        elem_type = elem.get("type")
        
        # Skip private/restricted facilities
        if access in ["private", "no", "restricted"]:
            continue
        
        # Recreational facilities: pitch with sport tags, or dog_park
        is_recreational_facility = False
        facility_type = None
        
        if leisure == "pitch" and sport:
            # Valid sports: tennis, basketball, baseball, soccer, volleyball, football
            # OBJECTIVE CRITERIA: Only count actual recreational sports facilities
            valid_sports = ["tennis", "basketball", "baseball", "soccer", "volleyball", "football"]
            if sport in valid_sports:
                is_recreational_facility = True
                facility_type = sport
        elif leisure == "dog_park":
            is_recreational_facility = True
            facility_type = "dog_park"
        
        if is_recreational_facility:
            seen_facility_ids.add(osm_id)
            
            # Get coordinates and distance
            elem_lat, elem_lon = None, None
            if elem_type == "node":
                elem_lat = elem.get("lat")
                elem_lon = elem.get("lon")
            elif elem_type == "way":
                elem_lat, elem_lon, _ = _get_way_geometry(elem, nodes_dict)
            
            if elem_lat and elem_lon:
                distance_m = haversine_distance(center_lat, center_lon, elem_lat, elem_lon)
                recreational_facilities.append({
                    "name": tags.get("name", f"{facility_type.title()} Court" if facility_type != "dog_park" else "Dog Park"),
                    "type": facility_type,
                    "lat": elem_lat,
                    "lon": elem_lon,
                    "distance_m": round(distance_m, 0),
                    "osm_id": osm_id
                })
    
    # Deduplicate (increase to 150m to collapse same-name multi-polygons)
    pre_dedup_count = len(parks)
    parks = _deduplicate_by_proximity(parks, 150)
    post_dedup_count = len(parks)
    for p in parks:
        debug_kept_parks.append({k: p[k] for k in ["osm_id", "name", "lat", "lon", "distance_m", "area_sqm"]})

    if DEBUG_PARKS:
        logger.debug("========= PARK DEBUG REPORT =========")
        logger.debug(f"Pre-dedup candidates: {pre_dedup_count}")
        for c in debug_raw_candidates:
            logger.debug(f"[CANDIDATE] id={c['osm_id']} name={c['name']} type={c['elem_type']} lat={c['lat']} lon={c['lon']} dist={c['distance_m']} area={c['area_sqm']}")
        logger.debug(f"Kept after dedup: {post_dedup_count}")
        for p in debug_kept_parks:
            logger.debug(f"[KEPT    ] id={p['osm_id']} name={p['name']} lat={p['lat']} lon={p['lon']} dist={p['distance_m']} area={p['area_sqm']}")
        if debug_skipped_parks:
            logger.debug(f"Skipped parks (not kept): {len(debug_skipped_parks)}")
            for s in debug_skipped_parks:
                logger.debug(f"[SKIPPED ] id={s['osm_id']} name={s['name']} reason={s['centroid_reason']}")
        logger.debug(f"Recreational facilities: {len(recreational_facilities)}")
        logger.debug("=====================================")

    return parks, playgrounds, recreational_facilities


def _process_nature_features(elements: List[Dict], center_lat: float, center_lon: float) -> Tuple[List[Dict], List[Dict], List[Dict]]:
    """Process OSM elements into hiking, swimming, and camping features."""
    hiking = []
    swimming = []
    camping = []
    nodes_dict = {}
    ways_dict = {}
    seen_ids = set()

    # Build nodes and ways dicts
    for elem in elements:
        if elem.get("type") == "node":
            nodes_dict[elem["id"]] = elem
        elif elem.get("type") == "way":
            ways_dict[elem["id"]] = elem

    # Process features
    for elem in elements:
        osm_id = elem.get("id")
        elem_type = elem.get("type")
        
        # RESEARCH-BACKED: Allow node elements for camping (many campsites are points in OSM)
        # Other features (hiking, swimming) remain way/relation only for data quality
        if not osm_id or osm_id in seen_ids:
            continue
        
        tags = elem.get("tags", {})
        route = tags.get("route")
        boundary = tags.get("boundary")
        natural = tags.get("natural")
        leisure = tags.get("leisure")
        tourism = tags.get("tourism")
        water_type = tags.get("water")
        piste_type = tags.get("piste:type")

        feature = None
        category = None
        
        # For camping, allow nodes; for other features, require way/relation
        is_camping = tourism == "camp_site"
        if not is_camping and elem_type not in ["way", "relation"]:
            continue

        if piste_type:
            # SKI TRAILS - Mountain recreation (piste:type)
            # RESEARCH-BACKED: Ski trails are legitimate outdoor recreation in mountain towns
            # Safe to include: Only significant in mountain areas (Park City: 1538, Times Square: 10)
            # This captures ski resort trails that aren't tagged as route=hiking
            # Filter out indoor/artificial ski facilities (piste:type=artificial or indoor)
            piste_lower = piste_type.lower()
            if piste_lower not in ["artificial", "indoor"]:
                feature = {"type": "ski_trail", "name": tags.get("name")}
                category = "hiking"  # Count as hiking trails for Wild Adventure scoring
        elif route == "hiking":
            # DATA QUALITY: Filter out urban paths/cycle paths tagged as hiking routes
            # Problem: OSM tags urban pathways and cycle paths as route=hiking when they're not actual hiking trails
            # Example: Times Square has 100+ "hiking" routes that are actually urban paths/greenways
            # Solution: Exclude routes that are explicitly cycle routes or have strong urban path indicators
            # This follows Public Transit pattern: prevent data quality issues from inflating scores
            
            # Check for urban path/cycle route indicators
            surface = tags.get("surface", "").lower()
            network = tags.get("network", "").lower()
            bicycle = tags.get("bicycle", "").lower()
            route_type = tags.get("type", "").lower()
            
            # Exclude if explicitly a cycle route (bicycle=yes/designated AND route=hiking is suspicious)
            # OR if it's a cycle network (ICN/NCN/RCN/LCN are cycle networks, not hiking)
            # OR if it has urban surface AND is not in a protected area (we check protected area separately)
            is_cycle_route = (
                bicycle in ["yes", "designated", "official"] or
                network in ["icn", "ncn", "rcn", "lcn"]  # International/National/Regional/Local Cycle Networks
            )
            
            # Exclude if it's a cycle route (these are not hiking trails)
            if is_cycle_route:
                continue
            
            # Note: We don't filter by surface alone because legitimate hiking trails can be paved
            # (e.g., trails in national parks that are maintained). The area_type filtering
            # at the pillar level handles urban core over-scoring.
            
            feature = {"type": "hiking_route", "name": tags.get("name")}
            category = "hiking"
        elif boundary == "national_park":
            feature = {"type": "national_park", "name": tags.get("name")}
            category = "hiking"
        elif leisure == "nature_reserve":
            feature = {"type": "nature_reserve", "name": tags.get("name")}
            category = "hiking"
        elif boundary == "protected_area":
            feature = {"type": "protected_area", "name": tags.get("name")}
            category = "hiking"
        elif natural == "beach":
            # DATA QUALITY: Distinguish actual swimmable beaches from rocky/inaccessible coastline
            # OBJECTIVE CRITERIA: Use OSM tags to determine beach quality
            # RESEARCH-BACKED: Beaches with surface=rock or access=private are not recreational
            surface = tags.get("surface", "").lower()
            access = tags.get("access", "").lower()
            
            # Exclude private beaches (not publicly accessible)
            if access in ["private", "no", "restricted"]:
                continue  # Skip private beaches
            
            # Exclude rocky beaches (not swimmable)
            # OBJECTIVE CRITERIA: surface=rock indicates non-swimmable beach
            if surface == "rock":
                # Treat as rocky coastline, not beach (lower score)
                feature = {"type": "coastline_rocky", "name": tags.get("name")}
                category = "swimming"
            else:
                # Actual swimmable beach
                feature = {"type": "beach", "name": tags.get("name")}
                category = "swimming"
        elif natural == "water" and water_type == "lake":
            # DATA QUALITY: Distinguish recreational lakes from ornamental water
            # OBJECTIVE CRITERIA: Check for ornamental indicators, access restrictions, size
            amenity = tags.get("amenity", "").lower()
            leisure_tag = tags.get("leisure", "").lower()
            access = tags.get("access", "").lower()
            
            # Exclude ornamental water (fountains, decorative ponds)
            if amenity == "fountain" or leisure_tag == "water_park":
                continue  # Skip ornamental water
            
            # Exclude private/restricted access
            if access in ["private", "no", "restricted"]:
                continue  # Skip private lakes
            
            # Will check size after geometry calculation (filter very small ornamental ponds)
            feature = {"type": "lake", "name": tags.get("name")}
            category = "swimming"
        elif natural == "coastline":
            # DATA QUALITY: Filter very short coastline segments (likely fragments, not recreational)
            # OBJECTIVE CRITERIA: Coastline segments <100m are likely OSM artifacts
            # Only include longer coastline segments that represent actual waterfront access
            # Note: Length calculation happens after geometry, will filter later
            feature = {"type": "coastline", "name": tags.get("name")}
            category = "swimming"
        elif natural == "water" and water_type == "bay":
            # Bays are scenic but typically not swimmable
            # OBJECTIVE CRITERIA: Check access restrictions
            access = tags.get("access", "").lower()
            if access in ["private", "no", "restricted"]:
                continue  # Skip private bays
            feature = {"type": "bay", "name": tags.get("name")}
            category = "swimming"
        elif leisure == "swimming_area":
            feature = {"type": "swimming_area", "name": tags.get("name")}
            category = "swimming"
        elif tourism == "camp_site":
            feature = {"type": "campsite", "name": tags.get("name")}
            category = "camping"

        if not feature:
            continue

        seen_ids.add(osm_id)

        elem_lat = None
        elem_lon = None
        area_sqm = 0.0
        way_length_m = 0.0
        
        if elem_type == "node":
            # Handle node elements (primarily for camping sites)
            elem_lat = elem.get("lat")
            elem_lon = elem.get("lon")
            area_sqm = 0.0  # Nodes have no area
            way_length_m = 0.0
        elif elem_type == "way":
            elem_lat, elem_lon, area_sqm = _get_way_geometry(elem, nodes_dict)
            
            # Calculate way length for coastline filtering
            if natural == "coastline" or (natural == "water" and water_type == "lake"):
                way_nodes = elem.get("nodes", [])
                if len(way_nodes) >= 2:
                    total_length = 0.0
                    prev_node = None
                    for node_id in way_nodes:
                        node = nodes_dict.get(node_id)
                        if node and "lat" in node and "lon" in node:
                            if prev_node:
                                dist = haversine_distance(
                                    prev_node["lat"], prev_node["lon"],
                                    node["lat"], node["lon"]
                                ) * 1000  # Convert km to meters
                                total_length += dist
                            prev_node = node
                    way_length_m = total_length
        elif elem_type == "relation":
            elem_lat, elem_lon = _get_relation_centroid(elem, ways_dict, nodes_dict)

        if elem_lat is None:
            # DIAGNOSTIC: Log when geometry calculation fails for camping
            if is_camping:
                logger.warning(
                    f"🔍 [CAMPING DIAGNOSTIC] Failed to get geometry for camping site "
                    f"osm_id={osm_id}, type={elem_type}, name={tags.get('name')}",
                    extra={
                        "pillar_name": "active_outdoors",
                        "osm_id": osm_id,
                        "elem_type": elem_type,
                        "camping_name": tags.get("name"),
                    }
                )
            continue

        # DATA QUALITY: Filter coastline segments and ornamental lakes
        # OBJECTIVE CRITERIA: Use size/length thresholds, not city-name exceptions
        
        # Filter very short coastline segments (<100m)
        # Short segments are likely OSM artifacts, not recreational waterfront
        if feature.get("type") == "coastline" and way_length_m > 0:
            MIN_COASTLINE_LENGTH_M = 100.0
            if way_length_m < MIN_COASTLINE_LENGTH_M:
                continue  # Skip short coastline fragments
        
        # Filter very small lakes (<1 ha) unless explicitly tagged as swimming_area
        # Small lakes are likely ornamental ponds, not recreational
        if feature.get("type") == "lake":
            area_ha = area_sqm / 10_000.0 if area_sqm else 0.0
            MIN_RECREATIONAL_LAKE_AREA_HA = 1.0
            if area_ha > 0 and area_ha < MIN_RECREATIONAL_LAKE_AREA_HA:
                # Check if explicitly tagged as recreational
                leisure_tag = tags.get("leisure", "").lower()
                if leisure_tag != "swimming_area":
                    continue  # Skip small ornamental ponds

        distance_m = haversine_distance(
            center_lat, center_lon, elem_lat, elem_lon)
        feature["distance_m"] = round(distance_m, 0)

        if category == "hiking":
            hiking.append(feature)
        elif category == "swimming":
            swimming.append(feature)
        elif category == "camping":
            camping.append(feature)

    return hiking, swimming, camping


def _query_trails_in_large_parks(lat: float, lon: float, radius_m: int = 15000) -> List[Dict]:
    """
    Query for trails within large parks (>50 hectares) to catch urban parks like Prospect Park.
    This avoids overcounting urban sidewalks by only looking at paths within large parks.
    
    Uses park data from query_green_spaces which already has area information.
    
    Returns:
        List of trail features from large parks
    """
    try:
        # Get parks data (which already has area information)
        parks_data = query_green_spaces(lat, lon, radius_m=radius_m)
        if not parks_data or not parks_data.get("parks"):
            return []
        
        parks = parks_data.get("parks", [])
        
        # Filter for large parks (>50 hectares = 500,000 sqm)
        # Also filter for parks within reasonable distance (not too far)
        LARGE_PARK_THRESHOLD_SQM = 500000  # 50 hectares
        large_parks_trails = []
        
        for park in parks:
            park_area_sqm = park.get("area_sqm", 0)
            park_name = park.get("name", "Unknown Park")
            park_lat = park.get("lat")
            park_lon = park.get("lon")
            park_distance_m = park.get("distance_m", float('inf'))
            
            # Skip if park is too small or missing coordinates
            if park_area_sqm < LARGE_PARK_THRESHOLD_SQM or park_lat is None or park_lon is None:
                continue
            
            # Skip if park is too far (beyond regional radius)
            if park_distance_m > radius_m:
                continue
            
            # Query paths within the large park
            # Use park area to estimate radius for path query (heuristic: radius ≈ sqrt(area/π))
            # For large parks, query paths within a reasonable radius (500m-1km depending on park size)
            park_radius_estimate = min(1000, max(300, (park_area_sqm / 3.14159) ** 0.5))
            
            paths_query = f"""
            [out:json][timeout:20];
            (
              way["highway"~"^(path|footway|track)$"]["access"!="private"](around:{int(park_radius_estimate)},{park_lat},{park_lon});
            );
            out geom;
            """
            
            try:
                def _do_paths_request():
                    return requests.post(
                        get_overpass_url(),
                        data={"data": paths_query},
                        timeout=25,
                        headers={"User-Agent": "HomeFit/1.0"}
                    )

                paths_resp = _retry_overpass(_do_paths_request, query_type="park_trails")
                if paths_resp is not None and paths_resp.status_code == 200:
                    paths_data = paths_resp.json()
                    paths = paths_data.get("elements", [])
                    
                    # Only count if park has multiple paths (indicating it's a substantial park with trails)
                    # This is a safeguard to avoid counting small parks with just one path
                    if len(paths) >= 2:  # At least 2 paths suggests a substantial park
                        # Count paths as trails (cap at 3 per park to avoid overcounting)
                        # This prevents urban parks from inflating scores too much
                        trail_count = min(3, len(paths))
                        distance_m = park_distance_m
                        large_parks_trails.append({
                            "type": "park_trail",
                            "name": f"{park_name} (trails)",
                            "distance_m": round(distance_m, 0),
                            "park_name": park_name,
                            "trail_count": trail_count
                        })
            except Exception as e:
                # Continue to next park if path query fails
                continue
        
        return large_parks_trails
    
    except Exception as e:
        logger.warning(f"Large park trail query error: {e}")
        return []


def query_local_paths_within_green_areas(lat: float, lon: float, radius_m: int = 1500) -> int:
    """
    Count clusters of path/footway segments within local radius.
    Clusters are grouped by ~120m; return min(5, clusters).
    """
    try:
        q = f"""
        [out:json][timeout:15];
        (
          way["highway"~"^(path|footway)$"](around:{radius_m},{lat},{lon});
        );
        out geom;
        """
        resp = requests.post(get_overpass_url(), data={"data": q}, timeout=25, headers={"User-Agent":"HomeFit/1.0"})
        if resp.status_code != 200:
            return 0
        ways = resp.json().get("elements", [])
        def _centroid(w):
            pts = [(n.get('lat'), n.get('lon')) for n in (w.get('geometry') or []) if 'lat' in n and 'lon' in n]
            pts = [(a,b) for a,b in pts if a is not None and b is not None]
            if not pts:
                return None
            return (sum(p[0] for p in pts)/len(pts), sum(p[1] for p in pts)/len(pts))
        centroids = []
        for w in ways:
            c = _centroid(w)
            if c:
                centroids.append(c)
        clusters = []
        from math import radians, sin, cos, asin, sqrt
        def dkm(a,b):
            R=6371
            lat1,lon1=a; lat2,lon2=b
            dlat=radians(lat2-lat1); dlon=radians(lon2-lon1)
            x=sin(dlat/2)**2+cos(radians(lat1))*cos(radians(lat2))*sin(dlon/2)**2
            return 2*R*asin(sqrt(x))
        for c in centroids:
            placed=False
            for group in clusters:
                if dkm(c, group['center']) <= 0.12:  # ~120m
                    group['points'].append(c)
                    lat = sum(p[0] for p in group['points'])/len(group['points'])
                    lon = sum(p[1] for p in group['points'])/len(group['points'])
                    group['center']=(lat,lon)
                    placed=True
                    break
            if not placed:
                clusters.append({'center':c,'points':[c]})
        return min(5, len(clusters))
    except Exception:
        return 0


def _process_charm_features(elements: List[Dict], center_lat: float, center_lon: float) -> Tuple[List[Dict], List[Dict]]:
    """Process OSM elements into historic buildings and artwork."""
    historic = []
    artwork = []
    nodes_dict = {}
    ways_dict = {}
    seen_ids = set()

    for elem in elements:
        if elem.get("type") == "node":
            nodes_dict[elem["id"]] = elem
        elif elem.get("type") == "way":
            ways_dict[elem["id"]] = elem

    for elem in elements:
        osm_id = elem.get("id")
        if not osm_id or osm_id in seen_ids:
            continue

        tags = elem.get("tags", {})
        historic_tag = tags.get("historic")
        heritage_tag = tags.get("heritage")
        building_historic_tag = tags.get("building:historic")
        tourism_tag = tags.get("tourism")
        amenity_tag = tags.get("amenity")

        feature = None
        category = None

        # Accept any historic indicator (historic, heritage, building:historic)
        if historic_tag or heritage_tag or building_historic_tag:
            feature = {
                "type": historic_tag or heritage_tag or "historic_building",
                "name": tags.get("name")
            }
            category = "historic"
        elif tourism_tag == "artwork":
            feature = {
                "type": "artwork",
                "name": tags.get("name"),
                "artwork_type": tags.get("artwork_type")
            }
            category = "artwork"
        elif amenity_tag == "fountain":
            feature = {
                "type": "fountain",
                "name": tags.get("name")
            }
            category = "artwork"

        if not feature:
            continue

        seen_ids.add(osm_id)

        elem_lat = elem.get("lat")
        elem_lon = elem.get("lon")

        if elem.get("type") == "way":
            elem_lat, elem_lon, _ = _get_way_geometry(elem, nodes_dict)
        elif elem.get("type") == "relation":
            elem_lat, elem_lon = _get_relation_centroid(elem, ways_dict, nodes_dict)

        if elem_lat is None:
            continue

        distance_m = haversine_distance(center_lat, center_lon, elem_lat, elem_lon)
        feature["distance_m"] = round(distance_m, 0)

        if category == "historic":
            historic.append(feature)
        elif category == "artwork":
            artwork.append(feature)

    return historic, artwork


def query_beauty_enhancers(lat: float, lon: float, radius_m: int = 1500) -> Dict[str, Any]:
    """
    Return lightweight aesthetic enhancers near the location.
    
    Keys:
        - viewpoints: int count of OSM viewpoint features
        - artwork: int count of art installations
        - fountains: int count of fountains
        - waterfront: 1 if coastline present within 2km else 0
        - viewpoints_details/artwork_details/fountains_details: feature metadata with name + distance
    """
    out: Dict[str, Any] = {
        "viewpoints": 0,
        "artwork": 0,
        "fountains": 0,
        "waterfront": 0,
        "viewpoints_details": [],
        "artwork_details": [],
        "fountains_details": []
    }

    try:
        q = f"""
        [out:json][timeout:15];
        (
          node["tourism"="viewpoint"](around:{radius_m},{lat},{lon});
          way["tourism"="viewpoint"](around:{radius_m},{lat},{lon});
          relation["tourism"="viewpoint"](around:{radius_m},{lat},{lon});
          node["tourism"="artwork"](around:{radius_m},{lat},{lon});
          way["tourism"="artwork"](around:{radius_m},{lat},{lon});
          relation["tourism"="artwork"](around:{radius_m},{lat},{lon});
          node["amenity"="fountain"](around:{radius_m},{lat},{lon});
          way["amenity"="fountain"](around:{radius_m},{lat},{lon});
          relation["amenity"="fountain"](around:{radius_m},{lat},{lon});
        );
        out body;
        >;
        out skel qt;
        """
        r = requests.post(
            OVERPASS_URL,
            data={"data": q},
            timeout=35,
            headers={"User-Agent": "HomeFit/1.0"}
        )
        if r.status_code == 200:
            data = r.json()
            elements = data.get("elements", [])
            nodes_dict = {e.get("id"): e for e in elements if e.get("type") == "node"}
            ways_dict = {e.get("id"): e for e in elements if e.get("type") == "way"}
            center_lat = lat
            center_lon = lon
            seen_ids = set()

            for elem in elements:
                osm_id = elem.get("id")
                if not osm_id or osm_id in seen_ids:
                    continue
                seen_ids.add(osm_id)

                tags = elem.get("tags", {}) or {}
                category = None
                if tags.get("tourism") == "viewpoint":
                    category = "viewpoints"
                elif tags.get("tourism") == "artwork":
                    category = "artwork"
                elif tags.get("amenity") == "fountain":
                    category = "fountains"

                if not category:
                    continue

                elem_lat = elem.get("lat")
                elem_lon = elem.get("lon")

                if elem.get("type") == "way":
                    elem_lat, elem_lon, _ = _get_way_geometry(elem, nodes_dict)
                elif elem.get("type") == "relation":
                    elem_lat, elem_lon = _get_relation_centroid(elem, ways_dict, nodes_dict)

                if elem_lat is None or elem_lon is None:
                    continue

                distance_m = round(haversine_distance(center_lat, center_lon, elem_lat, elem_lon))

                feature = {
                    "name": tags.get("name"),
                    "distance_m": distance_m,
                    "osm_id": osm_id,
                    "category": category,
                    "lat": elem_lat,
                    "lon": elem_lon
                }

                if category == "viewpoints":
                    out["viewpoints_details"].append(feature)
                elif category == "artwork":
                    out["artwork_details"].append(feature)
                elif category == "fountains":
                    out["fountains_details"].append(feature)

            out["viewpoints"] = len(out["viewpoints_details"])
            out["artwork"] = len(out["artwork_details"])
            out["fountains"] = len(out["fountains_details"])
    except Exception:
        pass

    # Coastline probe reused (2km)
    try:
        qc = f"""
        [out:json][timeout:15];
        way["natural"="coastline"](around:2000,{lat},{lon});
        out center 1;
        """
        rc = requests.post(get_overpass_url(), data={"data": qc}, timeout=20, headers={"User-Agent": "HomeFit/1.0"})
        if rc.status_code == 200 and rc.json().get("elements"):
            out["waterfront"] = 1
    except Exception:
        pass

    # Sort details by distance for deterministic output
    for key in ("viewpoints_details", "artwork_details", "fountains_details"):
        features = out.get(key)
        if isinstance(features, list):
            features.sort(key=lambda f: f.get("distance_m", float("inf")))

    return out

def _process_business_features(elements: List[Dict], center_lat: float, center_lon: float, include_chains: bool = False) -> Dict:
    """Process OSM elements into categorized businesses by tier."""
    tier1_daily = []
    tier2_social = []
    tier3_culture = []
    tier4_services = []

    seen_ids = set()
    nodes_dict = {}
    ways_dict = {}
    
    # Diagnostic counters
    filtered_no_name = 0
    filtered_brand = 0
    filtered_no_coords = 0
    processed_count = 0

    for elem in elements:
        if elem.get("type") == "node":
            nodes_dict[elem["id"]] = elem
        elif elem.get("type") == "way":
            ways_dict[elem["id"]] = elem
        elif elem.get("type") == "relation":
            members = elem.get("members", [])
            for member in members:
                if member.get("type") == "way":
                    way_id = member.get("ref")
                    if way_id not in ways_dict:
                        for e in elements:
                            if e.get("type") == "way" and e.get("id") == way_id:
                                ways_dict[way_id] = e
                                break

    for elem in elements:
        osm_id = elem.get("id")
        if not osm_id or osm_id in seen_ids:
            continue

        tags = elem.get("tags", {})
        name = tags.get("name")

        if not name:
            filtered_no_name += 1
            continue
        
        if not include_chains and tags.get("brand"):
            filtered_brand += 1
            continue

        seen_ids.add(osm_id)

        elem_lat, elem_lon, coord_source = _resolve_element_coordinates(elem, nodes_dict, ways_dict)
        if elem_lat is None or elem_lon is None:
            filtered_no_coords += 1
            logger.warning(
                "Amenity feature missing coordinates; skipping",
                extra={
                    "osm_id": osm_id,
                    "name": name,
                    "amenity": tags.get("amenity"),
                    "shop": tags.get("shop"),
                    "reason": coord_source
                }
            )
            continue
        
        processed_count += 1

        distance_m = haversine_distance(center_lat, center_lon, elem_lat, elem_lon)

        amenity = tags.get("amenity", "")
        shop = tags.get("shop", "")
        tourism = tags.get("tourism", "")
        leisure = tags.get("leisure", "")

        business = {
            "name": name,
            "lat": elem_lat,
            "lon": elem_lon,
            "distance_m": round(distance_m, 0),
            "osm_id": osm_id,
            "coordinate_source": coord_source
        }

        if amenity == "cafe":
            business["type"] = "cafe"
            tier1_daily.append(business)
        elif shop == "bakery":
            business["type"] = "bakery"
            tier1_daily.append(business)
        elif shop in ["supermarket", "convenience", "greengrocer"]:
            business["type"] = "grocery"
            tier1_daily.append(business)
        elif amenity == "restaurant":
            business["type"] = "restaurant"
            tier2_social.append(business)
        elif amenity in ["bar", "pub"]:
            business["type"] = "bar"
            tier2_social.append(business)
        elif amenity == "ice_cream" or shop == "ice_cream":
            business["type"] = "ice_cream"
            tier2_social.append(business)
        elif shop == "books":
            business["type"] = "bookstore"
            tier3_culture.append(business)
        elif tourism == "gallery" or shop == "art":
            business["type"] = "gallery"
            tier3_culture.append(business)
        elif amenity in ["theatre", "cinema"]:
            business["type"] = "theater"
            tier3_culture.append(business)
        elif tourism == "museum":
            business["type"] = "museum"
            tier3_culture.append(business)
        elif amenity == "marketplace":
            business["type"] = "market"
            tier3_culture.append(business)
        elif shop in ["clothes", "fashion", "boutique"]:
            business["type"] = "boutique"
            tier4_services.append(business)
        elif shop in ["hairdresser", "beauty"]:
            business["type"] = "salon"
            tier4_services.append(business)
        elif shop == "music":
            business["type"] = "records"
            tier4_services.append(business)
        elif leisure == "fitness_centre":
            business["type"] = "fitness"
            tier4_services.append(business)
        elif shop in ["garden_centre", "florist"]:
            business["type"] = "garden"
            tier4_services.append(business)
    
    # Diagnostic logging
    total_processed = len(tier1_daily) + len(tier2_social) + len(tier3_culture) + len(tier4_services)
    if len(elements) > 0:
        logger.info(
            f"🔍 [AMENITIES PROCESSING] Processed {len(elements)} elements: "
            f"{total_processed} businesses, {filtered_no_name} filtered (no name), "
            f"{filtered_brand} filtered (brand), {filtered_no_coords} filtered (no coords)",
            extra={
                "pillar_name": "neighborhood_amenities",
                "lat": center_lat,
                "lon": center_lon,
                "raw_elements": len(elements),
                "processed_businesses": total_processed,
                "filtered_no_name": filtered_no_name,
                "filtered_brand": filtered_brand,
                "filtered_no_coords": filtered_no_coords,
                "include_chains": include_chains,
            }
        )

    return {
        "tier1_daily": tier1_daily,
        "tier2_social": tier2_social,
        "tier3_culture": tier3_culture,
        "tier4_services": tier4_services
    }


# Alias get_way_center for backward compatibility
_get_way_geometry = get_way_center


def _resolve_element_coordinates(elem: Dict, nodes_dict: Dict, ways_dict: Dict) -> Tuple[Optional[float], Optional[float], str]:
    """
    Resolve coordinates for an OSM element using multiple fallbacks.

    Returns (lat, lon, source) where source indicates which fallback succeeded.
    """
    if not elem:
        return None, None, "missing-element"
    
    elem_type = elem.get("type")
    lat = elem.get("lat")
    lon = elem.get("lon")
    if lat is not None and lon is not None:
        return lat, lon, "direct"
    
    center = elem.get("center")
    if center:
        center_lat = center.get("lat")
        center_lon = center.get("lon")
        if center_lat is not None and center_lon is not None:
            return center_lat, center_lon, "center"
    
    if elem_type == "way":
        way_lat, way_lon, _ = get_way_center(elem, nodes_dict)
        if way_lat is not None and way_lon is not None:
            return way_lat, way_lon, "way-centroid"
    
    if elem_type == "relation":
        rel_lat, rel_lon = _get_relation_centroid(elem, ways_dict, nodes_dict)
        if rel_lat is not None and rel_lon is not None:
            return rel_lat, rel_lon, "relation-centroid"
    
    return None, None, "unresolved"


def _get_relation_centroid(elem: Dict, ways_dict: Dict, nodes_dict: Dict) -> Tuple[Optional[float], Optional[float]]:
    """Calculate centroid of a relation from its outer member ways."""
    if elem.get("type") != "relation":
        return None, None
    
    members = elem.get("members", [])
    if not members:
        return None, None
    
    all_coords = []
    for member in members:
        if member.get("role") == "outer" and member.get("type") == "way":
            way_id = member.get("ref")
            if way_id in ways_dict:
                way = ways_dict[way_id]
                for node_id in way.get("nodes", []):
                    if node_id in nodes_dict:
                        node = nodes_dict[node_id]
                        if "lat" in node and "lon" in node:
                            all_coords.append((node["lat"], node["lon"]))
    
    if not all_coords:
        for member in members:
            if member.get("type") == "way":
                way_id = member.get("ref")
                if way_id in ways_dict:
                    way = ways_dict[way_id]
                    for node_id in way.get("nodes", []):
                        if node_id in nodes_dict:
                            node = nodes_dict[node_id]
                            if "lat" in node and "lon" in node:
                                all_coords.append((node["lat"], node["lon"]))
    
    if not all_coords:
        return None, None
    
    lat = sum(c[0] for c in all_coords) / len(all_coords)
    lon = sum(c[1] for c in all_coords) / len(all_coords)
    
    return lat, lon


def _deduplicate_by_proximity(features: List[Dict], max_distance_m: float) -> List[Dict]:
    """Remove duplicates within max_distance_m. Keep both if names differ and are both non-empty."""
    if len(features) <= 1:
        return features

    unique = []
    for feature in sorted(features, key=lambda x: x.get("area_sqm", 0), reverse=True):
        is_duplicate = False
        for existing in unique:
            dist = haversine_distance(
                feature["lat"], feature["lon"],
                existing["lat"], existing["lon"])
            names_differ = (
                (feature.get("name") or "").strip() != (existing.get("name") or "").strip()
                and (feature.get("name") or "").strip()
                and (existing.get("name") or "").strip()
            )
            if dist < max_distance_m and not names_differ:
                is_duplicate = True
                break
        if not is_duplicate:
            unique.append(feature)
    return unique


def _get_park_type_name(leisure, landuse, natural):
    """Get readable name for park type."""
    if leisure:
        return leisure.replace("_", " ").title()
    elif landuse:
        return landuse.replace("_", " ").title()
    elif natural == "wood":
        return "Woods"
    elif natural == "forest":
        return "Forest"
    elif natural == "scrub":
        return "Natural Area"
    return "Green Space"


def _process_enhanced_trees(elements: List[Dict], center_lat: float, center_lon: float) -> Tuple[List[Dict], List[Dict], List[Dict], List[Dict]]:
    """Process OSM elements into enhanced tree categories."""
    tree_rows = []
    street_trees = []
    individual_trees = []
    tree_areas = []
    nodes_dict = {}
    ways_dict = {}
    seen_ids = set()

    # Build nodes and ways dicts
    for elem in elements:
        if elem.get("type") == "node":
            nodes_dict[elem["id"]] = elem
        elif elem.get("type") == "way":
            ways_dict[elem["id"]] = elem

    for elem in elements:
        osm_id = elem.get("id")
        if not osm_id or osm_id in seen_ids:
            continue

        tags = elem.get("tags", {})
        natural = tags.get("natural")
        highway = tags.get("highway")
        leisure = tags.get("leisure")
        landuse = tags.get("landuse")
        elem_type = elem.get("type")

        seen_ids.add(osm_id)

        elem_lat = None
        elem_lon = None

        if elem_type == "node":
            elem_lat = elem.get("lat")
            elem_lon = elem.get("lon")
        elif elem_type == "way":
            elem_lat, elem_lon, _ = _get_way_geometry(elem, nodes_dict)

        if elem_lat is None:
            continue

        distance_m = haversine_distance(center_lat, center_lon, elem_lat, elem_lon)

        tree_feature = {
            "name": tags.get("name"),
            "lat": elem_lat,
            "lon": elem_lon,
            "distance_m": round(distance_m, 0),
            "type": natural or highway or leisure or landuse
        }

        # Categorize trees
        if natural == "tree_row":
            tree_rows.append(tree_feature)
        elif highway and any(tags.get(k) == "yes" for k in ["trees", "trees:both", "trees:left", "trees:right"]):
            street_trees.append(tree_feature)
        elif natural == "tree":
            individual_trees.append(tree_feature)
        elif natural in ["wood", "forest"] or landuse == "forest" or (leisure == "park" and tags.get("trees") == "yes"):
            tree_areas.append(tree_feature)

    # Limit individual trees to top 50 closest to prevent response bloat
    # This doesn't affect scoring since only count matters, not coordinates
    individual_trees = sorted(individual_trees, key=lambda x: x['distance_m'])[:50]
    
    return tree_rows, street_trees, individual_trees, tree_areas


def _process_cultural_assets(elements: List[Dict], center_lat: float, center_lon: float) -> Tuple[List[Dict], List[Dict], List[Dict], List[Dict], List[Dict]]:
    """Process OSM elements into cultural asset categories."""
    museums = []
    galleries = []
    theaters = []
    public_art = []
    cultural_venues = []
    nodes_dict = {}
    seen_ids = set()

    for elem in elements:
        if elem.get("type") == "node":
            nodes_dict[elem["id"]] = elem

    for elem in elements:
        osm_id = elem.get("id")
        if not osm_id or osm_id in seen_ids:
            continue

        tags = elem.get("tags", {})
        tourism = tags.get("tourism")
        amenity = tags.get("amenity")
        shop = tags.get("shop")
        leisure = tags.get("leisure")
        elem_type = elem.get("type")

        seen_ids.add(osm_id)

        elem_lat = None
        elem_lon = None

        if elem_type == "node":
            elem_lat = elem.get("lat")
            elem_lon = elem.get("lon")
        elif elem_type == "way":
            elem_lat, elem_lon, _ = _get_way_geometry(elem, nodes_dict)

        if elem_lat is None:
            continue

        distance_m = haversine_distance(center_lat, center_lon, elem_lat, elem_lon)

        cultural_feature = {
            "name": tags.get("name"),
            "lat": elem_lat,
            "lon": elem_lon,
            "distance_m": round(distance_m, 0),
            "type": tourism or amenity or shop or leisure
        }

        # Categorize cultural assets
        if tourism == "museum":
            museums.append(cultural_feature)
        elif tourism == "gallery" or shop == "art":
            galleries.append(cultural_feature)
        elif amenity in ["theatre", "cinema"] or leisure == "arts_centre":
            theaters.append(cultural_feature)
        elif tourism == "artwork" or amenity == "fountain":
            public_art.append(cultural_feature)
        elif amenity in ["community_centre", "library"]:
            cultural_venues.append(cultural_feature)

    return museums, galleries, theaters, public_art, cultural_venues

def validate_osm_completeness(lat: float, lon: float) -> Dict[str, Any]:
    """
    Validate OSM data completeness for a location.
    
    Args:
        lat: Latitude
        lon: Longitude
        
    Returns:
        {
            "parks_coverage": bool,
            "businesses_coverage": bool,
            "healthcare_coverage": bool,
            "transport_coverage": bool,
            "overall_coverage": str  # "excellent", "good", "fair", "poor"
        }
    """
    coverage = {
        "parks_coverage": False,
        "businesses_coverage": False,
        "healthcare_coverage": False,
        "transport_coverage": False
    }
    
    # Test parks coverage
    try:
        parks_data = query_green_spaces(lat, lon, radius_m=1000)
        coverage["parks_coverage"] = bool(parks_data and (parks_data.get("parks") or parks_data.get("playgrounds")))
    except:
        pass
    
    # Test businesses coverage
    try:
        businesses_data = query_local_businesses(lat, lon, radius_m=1000)
        coverage["businesses_coverage"] = bool(businesses_data and len(businesses_data.get("businesses", [])) > 0)
    except:
        pass
    
    # Test healthcare coverage
    try:
        healthcare_data = query_healthcare(lat, lon, radius_m=5000)
        coverage["healthcare_coverage"] = bool(healthcare_data and len(healthcare_data.get("facilities", [])) > 0)
    except:
        pass
    
    # Test transport coverage
    try:
        # Simple check for nearby roads
        query = f"""
        [out:json][timeout:10];
        (
          way["highway"~"^(primary|secondary|tertiary|residential)$"](around:500,{lat},{lon});
        );
        out count;
        """
        resp = requests.post(
            OVERPASS_URL,
            data={"data": query},
            timeout=15,
            headers={"User-Agent": "HomeFit/1.0"}
        )
        if resp.status_code == 200:
            data = resp.json()
            coverage["transport_coverage"] = len(data.get("elements", [])) > 5
    except:
        pass
    
    # Calculate overall coverage
    coverage_count = sum(1 for v in coverage.values() if v)
    if coverage_count >= 3:
        coverage["overall_coverage"] = "excellent"
    elif coverage_count == 2:
        coverage["overall_coverage"] = "good"
    elif coverage_count == 1:
        coverage["overall_coverage"] = "fair"
    else:
        coverage["overall_coverage"] = "poor"
    
    return coverage


@cached(ttl_seconds=CACHE_TTL['osm_queries'])
@safe_api_call("osm", required=False)
@handle_api_timeout(timeout_seconds=70)
def query_healthcare_facilities(lat: float, lon: float, radius_m: int = 10000) -> Optional[Dict]:
    """
    Query OSM for comprehensive healthcare facilities.
    
    Returns:
        {
            "hospitals": [...],
            "urgent_care": [...],
            "clinics": [...],
            "pharmacies": [...],
            "doctors": [...]
        }
    """
    # Simplified query - get all healthcare-related amenities
    # Reduced from 30+ queries to 9 queries for better performance
    query = f"""
    [out:json][timeout:60];
    (
      // Healthcare amenities - nodes, ways, relations
      node["amenity"~"hospital|medical_centre|clinic|doctors|pharmacy|dentist|veterinary|emergency_ward"](around:{radius_m},{lat},{lon});
      way["amenity"~"hospital|medical_centre|clinic|doctors|pharmacy|dentist|veterinary|emergency_ward"](around:{radius_m},{lat},{lon});
      relation["amenity"~"hospital|medical_centre|clinic"](around:{radius_m},{lat},{lon});
      
      // Healthcare tag (more specific - only common healthcare values)
      node["healthcare"~"hospital|clinic|doctor|dentist|pharmacy|veterinary|urgent_care|emergency"](around:{radius_m},{lat},{lon});
      way["healthcare"~"hospital|clinic|doctor|dentist|pharmacy|veterinary|urgent_care|emergency"](around:{radius_m},{lat},{lon});
      relation["healthcare"~"hospital|clinic|doctor|dentist|pharmacy|veterinary|urgent_care|emergency"](around:{radius_m},{lat},{lon});
      
      // Pharmacies via shop tag
      node["shop"="pharmacy"](around:{radius_m},{lat},{lon});
      way["shop"="pharmacy"](around:{radius_m},{lat},{lon});
      
      // Emergency services (only if also healthcare-related)
      node["emergency"="yes"]["amenity"~"clinic|hospital"](around:{radius_m},{lat},{lon});
      way["emergency"="yes"]["amenity"~"clinic|hospital"](around:{radius_m},{lat},{lon});
    );
    out body;
    >;
    out skel qt;
    """
    
    def _do_request():
        return requests.post(get_overpass_url(), data={"data": query}, timeout=70, headers={"User-Agent": "HomeFit/1.0"})
    
    try:
        logger.debug(f"Querying comprehensive healthcare facilities within {radius_m/1000:.0f}km...")
        # Healthcare is critical - use CRITICAL profile (retry all attempts)
        resp = _retry_overpass(_do_request, query_type="healthcare")
        
        if resp is None or resp.status_code != 200:
            if resp and resp.status_code == 429:
                logger.warning("Healthcare query rate limited (429) - max retries reached")
                logger.warning("Consider: Increasing retry attempts or adding delay between requests")
            elif resp:
                logger.warning(f"Healthcare query failed: HTTP {resp.status_code}")
                logger.debug(f"Response preview: {resp.text[:200] if hasattr(resp, 'text') else 'N/A'}")
            else:
                logger.warning("Healthcare query failed: No response (timeout or network error)")
            # Return empty dict with error flag to allow proper error handling upstream
            logger.error(f"Healthcare query failed - returning empty results. Status: {resp.status_code if resp else 'No response'}")
            return {
                "hospitals": [],
                "urgent_care": [],
                "clinics": [],
                "pharmacies": [],
                "doctors": [],
                "_query_failed": True  # Flag to indicate query failure
            }

        data = resp.json()
        elements = data.get("elements", [])
        
        # Add logging to debug query results
        logger.debug(f"Healthcare query returned {len(elements)} elements")
        if len(elements) == 0:
            logger.warning(f"Healthcare query returned 0 elements for {lat}, {lon} - this may indicate a query issue or no facilities in OSM")
        
        hospitals = []
        urgent_care = []
        clinics = []
        pharmacies = []
        doctors = []
        
        # Build nodes/ways/relations dicts for geometry calculation
        nodes_dict = {}
        ways_dict = {}
        relations_dict = {}
        for elem in elements:
            if elem.get("type") == "node":
                nodes_dict[elem["id"]] = elem
            elif elem.get("type") == "way":
                ways_dict[elem["id"]] = elem
            elif elem.get("type") == "relation":
                relations_dict[elem["id"]] = elem
                # Extract member ways from relations to ensure they're in ways_dict
                members = elem.get("members", [])
                for member in members:
                    if member.get("type") == "way":
                        way_id = member.get("ref")
                        # If way isn't already in ways_dict, we need to find it in elements
                        if way_id not in ways_dict:
                            # Search for the way in elements (should be there due to > recursion)
                            for e in elements:
                                if e.get("type") == "way" and e.get("id") == way_id:
                                    ways_dict[way_id] = e
                                    break
        
        for elem in elements:
            tags = elem.get("tags", {})
            amenity = tags.get("amenity", "")
            name = tags.get("name") or tags.get("brand") or "Unnamed Facility"
            
            elem_lat, elem_lon, coord_source = _resolve_element_coordinates(elem, nodes_dict, ways_dict)
            if elem_lat is None or elem_lon is None:
                logger.warning(
                    "Healthcare facility missing coordinates after resolution",
                    extra={
                        "facility_id": elem.get("id"),
                        "elem_type": elem.get("type"),
                        "amenity": amenity,
                        "healthcare": tags.get("healthcare"),
                        "name": name,
                        "reason": coord_source
                    }
                )
                distance_km = None
            else:
                distance_m = haversine_distance(lat, lon, elem_lat, elem_lon)
                distance_km = distance_m / 1000.0 if distance_m is not None else None
            
            facility = {
                "name": name,
                "lat": elem_lat,
                "lon": elem_lon,
                "distance_km": round(distance_km, 3) if isinstance(distance_km, (int, float)) else None,
                "osm_id": elem.get("id"),
                "amenity": amenity,
                "emergency": tags.get("emergency"),
                "beds": tags.get("beds"),
                "tags": tags,
                "coordinate_source": coord_source
            }
            
            # Categorize facilities - IMPROVED LOGIC
            healthcare = tags.get("healthcare", "")
            healthcare_specialty = tags.get("healthcare:speciality", "").lower()
            name_lower = name.lower()
            
            # Hospitals and major medical centers (exclude if it's urgent care branded)
            if (amenity == "hospital" or healthcare == "hospital" or 
                (amenity == "medical_centre" and healthcare != "urgent_care")):
                hospitals.append(facility)
            # Urgent care - check multiple indicators (expanded detection)
            is_urgent_care = (
                amenity == "emergency_ward" or 
                healthcare == "urgent_care" or
                healthcare == "emergency" or
                tags.get("emergency") == "yes" or
                # Check clinic names for urgent care indicators
                (amenity == "clinic" and (
                    "urgent" in name_lower or
                    "walk-in" in name_lower or
                    "walk in" in name_lower or
                    "walkin" in name_lower or
                    "immediate" in name_lower or
                    "express" in name_lower or
                    "minute" in name_lower or  # "minute clinic", "minuteclinic"
                    "convenient" in name_lower or
                    "urgent" in healthcare_specialty or
                    "emergency" in healthcare_specialty
                )) or
                # Check for common urgent care brand names
                (amenity in ["clinic", "doctors"] and any(
                    brand in name_lower for brand in [
                        "citymd", "city md", "gohealth", "go health",
                        "medexpress", "med express", "afc", "concentra",
                        "patient first", "patientfirst", "carenow", "care now",
                        "fastmed", "fast med", "nextcare", "next care"
                    ]
                ))
            )
            
            if is_urgent_care:
                urgent_care.append(facility)
            # Regular clinics and medical centers
            # CONSERVATIVE FILTERING: Only exclude obvious non-primary-care specialty clinics
            # This prevents over-counting (e.g., Brooklyn Heights 110 clinics) while preserving
            # legitimate primary care facilities. We filter only the most obvious specialty-only clinics.
            elif amenity in ["clinic", "doctors"]:
                # Exclude only obvious specialty-only clinics that don't provide primary care
                # This is conservative to avoid breaking scores for places with legitimate specialty clinics
                excluded_specialties = [
                    "pain management", "chiropractic", "acupuncture",
                    "physical therapy", "physiotherapy", "rehabilitation",
                    "cosmetic", "plastic surgery", "laser",
                    "radiology", "imaging", "diagnostic center", "laboratory",
                    "veterinary", "animal"
                ]
                
                # Check if this is an obvious specialty-only clinic
                is_specialty_only = False
                if healthcare_specialty:
                    for excluded in excluded_specialties:
                        if excluded in healthcare_specialty:
                            is_specialty_only = True
                            break
                
                # Also check name for obvious specialty-only indicators
                if not is_specialty_only:
                    specialty_name_indicators = [
                        "pain management", "chiropractic", "acupuncture",
                        "physical therapy", "physiotherapy", "rehab",
                        "cosmetic", "plastic surgery", "laser",
                        "radiology", "imaging", "diagnostic", "lab",
                        "veterinary", "animal", "pet"
                    ]
                    for indicator in specialty_name_indicators:
                        if indicator in name_lower:
                            is_specialty_only = True
                            break
                
                # Only count as primary care if not an obvious specialty-only clinic
                # Note: We're conservative here - many specialty clinics also provide some primary care,
                # so we only filter the most obvious ones (pain clinics, chiropractic, cosmetic, etc.)
                if not is_specialty_only:
                    if amenity == "clinic":
                        clinics.append(facility)
                    else:
                        doctors.append(facility)
            # Pharmacies - also check healthcare=pharmacy tag
            elif (amenity == "pharmacy" or 
                  tags.get("shop") == "pharmacy" or
                  healthcare == "pharmacy"):
                pharmacies.append(facility)
        
        return {
            "hospitals": hospitals,
            "urgent_care": urgent_care,
            "clinics": clinics,
            "pharmacies": pharmacies,
            "doctors": doctors
        }
            
    except Exception as e:
        logger.error(f"Error querying healthcare facilities: {e}", exc_info=True)
        # Return empty dict with error flag to allow proper error handling upstream
        logger.error(f"Healthcare query exception - returning empty results: {e}")
        return {
            "hospitals": [],
            "urgent_care": [],
            "clinics": [],
            "pharmacies": [],
            "doctors": [],
            "_query_failed": True  # Flag to indicate query failure
        }



@cached(ttl_seconds=CACHE_TTL['osm_queries'])
@safe_api_call("osm", required=False)
@handle_api_timeout(timeout_seconds=30)
def query_railway_stations(lat: float, lon: float, radius_m: int = 2000) -> Optional[List[Dict]]:
    """
    Query OSM for railway stations within radius.
    
    Args:
        lat, lon: Coordinates
        radius_m: Search radius in meters (default 2km)
    
    Returns:
        List of railway stations with name, lat, lon, distance
    """
    query = f"""
    [out:json][timeout:15];
    (
      // Railway stations
      node["railway"="station"](around:{radius_m},{lat},{lon});
      node["railway"="halt"](around:{radius_m},{lat},{lon});
      
      // Metro/subway stations
      node["railway"="subway_entrance"](around:{radius_m},{lat},{lon});
      node["station"="subway"](around:{radius_m},{lat},{lon});
      
      // Tram stations
      node["railway"="tram_stop"](around:{radius_m},{lat},{lon});
      
      // Bus stations
      node["public_transport"="station"](around:{radius_m},{lat},{lon});
      node["amenity"="bus_station"](around:{radius_m},{lat},{lon});
    );
    out body;
    >;
    out skel qt;
    """
    
    try:
        logger.debug(f"Querying OSM for railway stations within {radius_m/1000:.1f}km...")
        resp = requests.post(get_overpass_url(), data=query, timeout=30)
        
        if resp.status_code == 200:
            data = resp.json()
            elements = data.get("elements", [])
            
            stations = []
            for elem in elements:
                if "lat" in elem and "lon" in elem:
                    tags = elem.get("tags", {})
                    name = tags.get("name") or tags.get("operator") or "Unnamed Station"
                    railway_type = tags.get("railway") or tags.get("public_transport") or "station"
                    
                    # Calculate distance
                    distance_km = haversine_distance(lat, lon, elem["lat"], elem["lon"])
                    distance_m = distance_km * 1000
                    
                    stations.append({
                        "name": name,
                        "lat": elem["lat"],
                        "lon": elem["lon"],
                        "distance_m": round(distance_m),
                        "distance_km": round(distance_km, 2),
                        "railway_type": railway_type,
                        "tags": tags
                    })
            
            # Sort by distance
            stations.sort(key=lambda x: x["distance_m"])
            
            logger.debug(f"Found {len(stations)} railway stations")
            return stations
        else:
            logger.warning(f"OSM railway station query failed: {resp.status_code}")
            return None
            
    except Exception as e:
        logger.error(f"Error querying OSM for railway stations: {e}", exc_info=True)
        return None