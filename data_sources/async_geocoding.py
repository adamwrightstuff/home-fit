"""
Async Geocoding API Client
Async version using Nominatim (OpenStreetMap) for address geocoding
"""

import aiohttp
from typing import Optional, Tuple
from .cache import cached, CACHE_TTL
from logging_config import get_logger

logger = get_logger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

# Global session for connection reuse
_session = None

async def get_session():
    """Get or create aiohttp session for connection reuse."""
    global _session
    if _session is None or _session.closed:
        connector = aiohttp.TCPConnector(limit=50, limit_per_host=10)
        timeout = aiohttp.ClientTimeout(total=15, connect=5, sock_read=10)
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


@cached(ttl_seconds=CACHE_TTL['geocoding'])
async def geocode_async(address: str) -> Optional[Tuple[float, float, str, str, str]]:
    """
    Async geocode an address to coordinates.

    Args:
        address: Address string or ZIP code

    Returns:
        (lat, lon, zip_code, state, city) or None if failed
    """
    try:
        params = {
            "q": address,
            "format": "json",
            "addressdetails": 1,
            "limit": 1
        }

        session = await get_session()
        async with session.get(NOMINATIM_URL, params=params) as response:
            if response.status != 200:
                return None

            data = await response.json()

            if not data:
                return None

            result = data[0]
            lat = float(result["lat"])
            lon = float(result["lon"])

            address_details = result.get("address", {})
            zip_code = address_details.get("postcode", "")
            state = address_details.get("state", "")
            city = address_details.get("city") or address_details.get(
                "town") or address_details.get("village", "")

            return lat, lon, zip_code, state, city

    except Exception as e:
        logger.error(f"Async geocoding error: {e}", extra={
            "api_name": "nominatim",
            "operation": "geocode",
            "address": address
        })
        return None
