"""
Async OpenStreetMap API Client
Async version of OSM API queries for better performance
"""

import aiohttp
import asyncio
import math
import time
from typing import Dict, List, Tuple, Optional
from .cache import cached, CACHE_TTL
from .error_handling import with_fallback, safe_api_call, handle_api_timeout
from logging_config import get_logger

logger = get_logger(__name__)

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Global session for connection reuse
_session = None

async def get_session():
    """Get or create aiohttp session for connection reuse."""
    global _session
    if _session is None or _session.closed:
        connector = aiohttp.TCPConnector(limit=100, limit_per_host=30)
        timeout = aiohttp.ClientTimeout(total=60, connect=10)
        _session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={"User-Agent": "HomeFit/1.0"}
        )
    return _session

async def close_session():
    """Close the global session."""
    global _session
    if _session and not _session.closed:
        await _session.close()
        _session = None


@cached(ttl_seconds=CACHE_TTL['osm_queries'])
@safe_api_call("osm", required=False)
@handle_api_timeout(timeout_seconds=30)
async def query_green_spaces_async(lat: float, lon: float, radius_m: int = 1000) -> Optional[Dict]:
    """
    Async query OSM for parks, playgrounds, and tree features.
    INCLUDES RELATIONS to catch all parks!

    Returns:
        {
            "parks": [...],
            "playgrounds": [...],
            "tree_features": [...]
        }
    """
    query = f"""
    [out:json][timeout:25];
    (
      // PARKS & GREEN SPACES - INCLUDING RELATIONS!
      way["leisure"="park"](around:{radius_m},{lat},{lon});
      relation["leisure"="park"](around:{radius_m},{lat},{lon});
      
      way["leisure"="garden"]["garden:type"!="private"](around:{radius_m},{lat},{lon});
      relation["leisure"="garden"]["garden:type"!="private"](around:{radius_m},{lat},{lon});
      
      way["leisure"="dog_park"](around:{radius_m},{lat},{lon});
      relation["leisure"="dog_park"](around:{radius_m},{lat},{lon});
      
      way["landuse"="recreation_ground"](around:{radius_m},{lat},{lon});
      relation["landuse"="recreation_ground"](around:{radius_m},{lat},{lon});
      
      way["landuse"="village_green"](around:{radius_m},{lat},{lon});
      relation["landuse"="village_green"](around:{radius_m},{lat},{lon});
      
      // LOCAL NATURE
      way["natural"="wood"](around:{radius_m},{lat},{lon});
      relation["natural"="wood"](around:{radius_m},{lat},{lon});
      
      way["natural"="forest"](around:{radius_m},{lat},{lon});
      relation["natural"="forest"](around:{radius_m},{lat},{lon});
      
      way["natural"="scrub"](around:{radius_m},{lat},{lon});
      relation["natural"="scrub"](around:{radius_m},{lat},{lon});
      
      // PLAYGROUNDS
      node["leisure"="playground"](around:{radius_m},{lat},{lon});
      way["leisure"="playground"](around:{radius_m},{lat},{lon});
      relation["leisure"="playground"](around:{radius_m},{lat},{lon});
      
      // TREES
      way["natural"="tree_row"](around:{radius_m},{lat},{lon});
      way["highway"]["trees"="yes"](around:{radius_m},{lat},{lon});
      way["highway"]["trees:both"="yes"](around:{radius_m},{lat},{lon});
      way["highway"]["trees:left"="yes"](around:{radius_m},{lat},{lon});
      way["highway"]["trees:right"="yes"](around:{radius_m},{lat},{lon});
    );
    out body;
    >;
    out skel qt;
    """

    try:
        session = await get_session()
        async with session.post(
            OVERPASS_URL,
            data={"data": query},
            timeout=aiohttp.ClientTimeout(total=35, connect=10)
        ) as resp:
            if resp.status != 200:
                return None

            data = await resp.json()
            elements = data.get("elements", [])

            parks, playgrounds, tree_features = _process_green_features(
                elements, lat, lon)

            return {
                "parks": parks,
                "playgrounds": playgrounds,
                "tree_features": tree_features
            }

    except Exception as e:
        logger.error(f"OSM async query error: {e}", extra={
            "query_type": "green_spaces",
            "lat": lat,
            "lon": lon,
            "radius_m": radius_m
        })
        return None


@cached(ttl_seconds=CACHE_TTL['osm_queries'])
@safe_api_call("osm", required=False)
@handle_api_timeout(timeout_seconds=40)
async def query_nature_features_async(lat: float, lon: float, radius_m: int = 15000) -> Optional[Dict]:
    """
    Async query OSM for outdoor recreation (hiking, swimming, camping).

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
      // HIKING
      relation["route"="hiking"](around:{radius_m},{lat},{lon});
      way["boundary"="national_park"](around:{radius_m},{lat},{lon});
      relation["boundary"="national_park"](around:{radius_m},{lat},{lon});
      way["leisure"="nature_reserve"](around:{radius_m},{lat},{lon});
      relation["leisure"="nature_reserve"](around:{radius_m},{lat},{lon});
      way["boundary"="protected_area"](around:{radius_m},{lat},{lon});
      relation["boundary"="protected_area"](around:{radius_m},{lat},{lon});
      
      // SWIMMING
      way["natural"="beach"](around:{radius_m},{lat},{lon});
      relation["natural"="beach"](around:{radius_m},{lat},{lon});
      way["natural"="water"]["water"="lake"](around:{radius_m},{lat},{lon});
      relation["natural"="water"]["water"="lake"](around:{radius_m},{lat},{lon});
      way["natural"="coastline"](around:{radius_m},{lat},{lon});
      way["natural"="water"]["water"="bay"](around:{radius_m},{lat},{lon});
      relation["natural"="water"]["water"="bay"](around:{radius_m},{lat},{lon});
      way["leisure"="swimming_area"](around:{radius_m},{lat},{lon});
      relation["leisure"="swimming_area"](around:{radius_m},{lat},{lon});
      
      // CAMPING
      way["tourism"="camp_site"](around:{radius_m},{lat},{lon});
      relation["tourism"="camp_site"](around:{radius_m},{lat},{lon});
    );
    out body;
    >;
    out skel qt;
    """

    try:
        session = await get_session()
        async with session.post(
            OVERPASS_URL,
            data={"data": query},
            timeout=aiohttp.ClientTimeout(total=50, connect=10)
        ) as resp:
            if resp.status != 200:
                return None

            data = await resp.json()
            elements = data.get("elements", [])

            hiking, swimming, camping = _process_nature_features(
                elements, lat, lon)

            return {
                "hiking": hiking,
                "swimming": swimming,
                "camping": camping
            }

    except Exception as e:
        logger.error(f"OSM async nature query error: {e}", extra={
            "query_type": "nature_features",
            "lat": lat,
            "lon": lon,
            "radius_m": radius_m
        })
        return None


@cached(ttl_seconds=CACHE_TTL['osm_queries'])
@safe_api_call("osm", required=False)
@handle_api_timeout(timeout_seconds=60)
async def query_local_businesses_async(lat: float, lon: float, radius_m: int = 1000) -> Optional[Dict]:
    """
    Async query OSM for indie local businesses within walking distance.
    Focuses on non-chain establishments.

    Returns:
        {
            "tier1_daily": [...],
            "tier2_social": [...],
            "tier3_culture": [...],
            "tier4_services": [...]
        }
    """
    query = f"""
    [out:json][timeout:60];
    (
      // TIER 1: DAILY ESSENTIALS
      node["amenity"="cafe"]["name"]["brand"!~"."](around:{radius_m},{lat},{lon});
      way["amenity"="cafe"]["name"]["brand"!~"."](around:{radius_m},{lat},{lon});
      
      node["shop"="bakery"]["name"]["brand"!~"."](around:{radius_m},{lat},{lon});
      way["shop"="bakery"]["name"]["brand"!~"."](around:{radius_m},{lat},{lon});
      
      node["shop"~"supermarket|convenience|greengrocer"]["name"]["brand"!~"."](around:{radius_m},{lat},{lon});
      way["shop"~"supermarket|convenience|greengrocer"]["name"]["brand"!~"."](around:{radius_m},{lat},{lon});
      
      // TIER 2: SOCIAL & DINING
      node["amenity"="restaurant"]["name"]["brand"!~"."](around:{radius_m},{lat},{lon});
      way["amenity"="restaurant"]["name"]["brand"!~"."](around:{radius_m},{lat},{lon});
      
      node["amenity"~"bar|pub"]["name"]["brand"!~"."](around:{radius_m},{lat},{lon});
      way["amenity"~"bar|pub"]["name"]["brand"!~"."](around:{radius_m},{lat},{lon});
      
      node["amenity"="ice_cream"]["name"]["brand"!~"."](around:{radius_m},{lat},{lon});
      node["shop"="ice_cream"]["name"]["brand"!~"."](around:{radius_m},{lat},{lon});
      way["shop"="ice_cream"]["name"]["brand"!~"."](around:{radius_m},{lat},{lon});
      
      // TIER 3: CULTURE & LEISURE
      node["shop"="books"]["name"]["brand"!~"."](around:{radius_m},{lat},{lon});
      way["shop"="books"]["name"]["brand"!~"."](around:{radius_m},{lat},{lon});
      
      node["tourism"="gallery"]["name"](around:{radius_m},{lat},{lon});
      way["tourism"="gallery"]["name"](around:{radius_m},{lat},{lon});
      node["shop"="art"]["name"](around:{radius_m},{lat},{lon});
      way["shop"="art"]["name"](around:{radius_m},{lat},{lon});
      
      node["amenity"~"theatre|cinema"]["name"](around:{radius_m},{lat},{lon});
      way["amenity"~"theatre|cinema"]["name"](around:{radius_m},{lat},{lon});
      
      node["tourism"="museum"]["name"](around:{radius_m},{lat},{lon});
      way["tourism"="museum"]["name"](around:{radius_m},{lat},{lon});
      
      node["amenity"="marketplace"]["name"](around:{radius_m},{lat},{lon});
      way["amenity"="marketplace"]["name"](around:{radius_m},{lat},{lon});
      
      // TIER 4: SERVICES & RETAIL
      node["shop"~"clothes|fashion|boutique"]["name"]["brand"!~"."](around:{radius_m},{lat},{lon});
      way["shop"~"clothes|fashion|boutique"]["name"]["brand"!~"."](around:{radius_m},{lat},{lon});
      
      node["shop"~"hairdresser|beauty"]["name"]["brand"!~"."](around:{radius_m},{lat},{lon});
      way["shop"~"hairdresser|beauty"]["name"]["brand"!~"."](around:{radius_m},{lat},{lon});
      
      node["shop"="music"]["name"]["brand"!~"."](around:{radius_m},{lat},{lon});
      way["shop"="music"]["name"]["brand"!~"."](around:{radius_m},{lat},{lon});
      
      node["leisure"="fitness_centre"]["name"]["brand"!~"."](around:{radius_m},{lat},{lon});
      way["leisure"="fitness_centre"]["name"]["brand"!~"."](around:{radius_m},{lat},{lon});
      
      node["shop"~"garden_centre|florist"]["name"]["brand"!~"."](around:{radius_m},{lat},{lon});
      way["shop"~"garden_centre|florist"]["name"]["brand"!~"."](around:{radius_m},{lat},{lon});
    );
    out body;
    >;
    out skel qt;
    """

    try:
        session = await get_session()
        async with session.post(
            OVERPASS_URL,
            data={"data": query},
            timeout=aiohttp.ClientTimeout(total=70, connect=10)
        ) as resp:
            if resp.status != 200:
                return None

            data = await resp.json()
            elements = data.get("elements", [])

            businesses = _process_business_features(elements, lat, lon)
            return businesses

    except Exception as e:
        logger.error(f"OSM async business query error: {e}", extra={
            "query_type": "local_businesses",
            "lat": lat,
            "lon": lon,
            "radius_m": radius_m
        })
        return None


@cached(ttl_seconds=CACHE_TTL['osm_queries'])
@safe_api_call("osm", required=False)
@handle_api_timeout(timeout_seconds=25)
async def query_charm_features_async(lat: float, lon: float, radius_m: int = 500) -> Optional[Dict]:
    """
    Async query OSM for neighborhood charm features (historic buildings, fountains, public art).

    Returns:
        {
            "historic": [...],
            "artwork": [...]
        }
    """
    query = f"""
    [out:json][timeout:25];
    (
      // HISTORIC BUILDINGS
      node["historic"~"building|castle|church|monument|memorial|ruins|archaeological_site"](around:{radius_m},{lat},{lon});
      way["historic"~"building|castle|church|monument|memorial|ruins|archaeological_site"](around:{radius_m},{lat},{lon});
      
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
        session = await get_session()
        async with session.post(
            OVERPASS_URL,
            data={"data": query},
            timeout=aiohttp.ClientTimeout(total=35, connect=10)
        ) as resp:
            if resp.status != 200:
                return None

            data = await resp.json()
            elements = data.get("elements", [])

            historic, artwork = _process_charm_features(elements, lat, lon)

            return {
                "historic": historic,
                "artwork": artwork
            }

    except Exception as e:
        logger.error(f"OSM async charm query error: {e}", extra={
            "query_type": "charm_features",
            "lat": lat,
            "lon": lon,
            "radius_m": radius_m
        })
        return None


# Import processing functions from the original OSM API
from .osm_api import (
    _process_green_features,
    _process_nature_features,
    _process_business_features,
    _process_charm_features,
    haversine_distance
)
