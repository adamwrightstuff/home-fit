"""
Caching system for HomeFit API calls
Provides in-memory caching for expensive operations like OSM queries and API calls
"""

import time
import hashlib
import os
import json
from typing import Any, Optional, Dict
from functools import wraps
from logging_config import get_logger

logger = get_logger(__name__)

# Try to import and initialize Redis
_redis_client = None
try:
    import redis
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    _redis_client = redis.from_url(redis_url, decode_responses=True)
    _redis_client.ping()
    logger.info("Redis connected for distributed caching")
except Exception as e:
    logger.warning(f"Redis not available, using in-memory cache: {e}")
    _redis_client = None


def _get_redis_client():
    """
    Get Redis client with lightweight reconnection check.
    Only reconnects if connection is actually lost (not on every call).
    This is performance-optimized: ping is fast, reconnection only happens when needed.
    
    Returns:
        Redis client if available, None otherwise
    """
    global _redis_client
    
    if _redis_client is None:
        return None
    
    # Lightweight ping check (fast, doesn't block)
    try:
        _redis_client.ping()
        return _redis_client
    except Exception:
        # Connection lost - try to reconnect once (with short timeout for performance)
        try:
            import redis
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
            _redis_client = redis.from_url(
                redis_url, 
                decode_responses=True, 
                socket_connect_timeout=1, 
                socket_timeout=1
            )
            _redis_client.ping()
            logger.info("Redis reconnected successfully")
            return _redis_client
        except Exception as reconnect_error:
            logger.warning(f"Redis reconnection failed: {reconnect_error}")
            _redis_client = None
            return None

# Simple in-memory cache (fallback when Redis is unavailable)
_cache: Dict[str, Dict[str, Any]] = {}
_cache_ttl: Dict[str, float] = {}

# Cache TTL settings (in seconds) - Differentiated by data stability
# Stable data: 24-48h (Census, airports, geocoding)
# Moderate data: 1-6h (OSM amenities, transit routes)
# Dynamic data: 5-15min (transit stops, real-time)
CACHE_TTL = {
    'osm_queries': 6 * 3600,           # 6 hours for OSM data (moderate stability)
    'osm_businesses': 2 * 3600,         # 2 hours for OSM business queries (more dynamic)
    'osm_transit': 15 * 60,            # 15 minutes for transit stops (dynamic)
    'census_data': 48 * 3600,          # 48 hours for Census data (very stable, changes annually)
    'school_data': 30 * 24 * 3600,     # 30 days for school data (extended to preserve quota)
    'airport_distances': 24 * 3600,    # 24 hours for airport calculations (stable)
    'geocoding': 24 * 3600,            # 24 hours for geocoding (stable)
    'transit_routes': 6 * 3600,        # 6 hours for transit routes (moderate stability)
    'transit_stops': 15 * 60,          # 15 minutes for transit stops (dynamic)
    'healthcare': 2 * 3600,            # 2 hours for healthcare data (moderate stability)
}


def _generate_cache_key(func_name: str, *args, **kwargs) -> str:
    """Generate a cache key from function name and arguments."""
    # Create a string representation of the arguments
    args_str = str(args) + str(sorted(kwargs.items()))
    # Hash the string to create a shorter key
    key_hash = hashlib.md5(args_str.encode()).hexdigest()
    return f"{func_name}:{key_hash}"


def cached(ttl_seconds: int = 3600):
    """
    Decorator to cache function results with Redis (if available) or in-memory cache.
    
    Args:
        ttl_seconds: Time to live for cached results in seconds
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache_key = _generate_cache_key(func.__name__, *args, **kwargs)
            current_time = time.time()
            
            # Try Redis first, fall back to in-memory
            cache_entry = None
            cache_time = 0
            
            redis_client = _get_redis_client()
            if redis_client:
                try:
                    # Try Redis
                    cached_data = redis_client.get(cache_key)
                    if cached_data:
                        data = json.loads(cached_data)
                        cache_entry = data['value']
                        cache_time = data['timestamp']
                except Exception as e:
                    logger.warning(f"Redis read error, falling back to in-memory: {e}")
            
            # Fall back to in-memory cache if Redis failed or not available
            if cache_entry is None and cache_key in _cache:
                cache_entry = _cache[cache_key]
                cache_time = _cache_ttl.get(cache_key, 0)
            
            # Check if cached entry is still valid
            if cache_entry is not None and (current_time - cache_time) < ttl_seconds:
                logger.debug(f"Cache hit for {func.__name__}")
                return cache_entry
            
            # Cache miss or expired - execute function
            logger.debug(f"Cache miss for {func.__name__} - executing")
            # Periodic cleanup to prevent memory bloat (every 100 cache operations)
            if len(_cache) > 100 and len(_cache) % 100 == 0:
                _cleanup_expired_cache()
            
            result = func(*args, **kwargs)

            skip_cache = False
            if isinstance(result, dict):
                skip_cache = bool(result.pop('_cache_skip', False))
            
            
            # If API call failed (result is None), try using stale cache as fallback
            if result is None and cache_entry is not None:
                # Cache is expired but exists - use it as fallback
                age_hours = (current_time - cache_time) / 3600
                logger.warning(f"API failed, using stale cache (age: {age_hours:.1f} hours) for {func.__name__}")
                # Mark stale cache in result (if it's a dict, add flag)
                if isinstance(cache_entry, dict):
                    cache_entry = cache_entry.copy()
                    cache_entry['_stale_cache'] = True
                    cache_entry['_cache_age_hours'] = round(age_hours, 1)
                return cache_entry
            
            # Only cache non-None results (None indicates error/obfuscated data that shouldn't be cached)
            if result is not None and not skip_cache:
                # Store in both Redis (if available) and in-memory
                cache_data = {
                    'value': result,
                    'timestamp': current_time
                }
                
                redis_client = _get_redis_client()
                if redis_client:
                    try:
                        redis_client.setex(cache_key, ttl_seconds, json.dumps(cache_data))
                    except Exception as e:
                        logger.warning(f"Redis write error: {e}")
                
                # Also store in in-memory cache
                _cache[cache_key] = result
                _cache_ttl[cache_key] = current_time
            else:
                logger.debug(f"Result is None - not caching (allows retry)")
            
            return result
        
        return wrapper
    return decorator


def clear_cache(cache_type: Optional[str] = None):
    """
    Clear cache entries from both Redis (if available) and in-memory cache.
    
    Args:
        cache_type: If provided, only clear entries matching this type
    """
    global _cache, _cache_ttl
    
    # Clear Redis if available
    redis_client = _get_redis_client()
    if redis_client:
        try:
            if cache_type is None:
                # Clear all Redis keys
                keys = redis_client.keys("*")
                if keys:
                    redis_client.delete(*keys)
            else:
                # Clear specific cache type
                pattern = f"*{cache_type}:*"
                keys = redis_client.keys(pattern)
                if keys:
                    redis_client.delete(*keys)
        except Exception as e:
            logger.warning(f"Error clearing Redis cache: {e}")
    
    # Clear in-memory cache
    if cache_type is None:
        _cache.clear()
        _cache_ttl.clear()
        logger.info("Cleared all cache")
    else:
        keys_to_remove = [key for key in _cache.keys() if key.startswith(f"{cache_type}:")]
        for key in keys_to_remove:
            _cache.pop(key, None)
            _cache_ttl.pop(key, None)
        logger.info(f"Cleared {len(keys_to_remove)} {cache_type} cache entries")


def _cleanup_expired_cache():
    """Clean up expired entries from in-memory cache to prevent memory bloat."""
    global _cache, _cache_ttl
    current_time = time.time()
    keys_to_remove = []
    
    # Find expired entries (check against max TTL which is 7 days for OSM)
    max_ttl = max(CACHE_TTL.values())
    
    for key, cache_time in _cache_ttl.items():
        if current_time - cache_time > max_ttl:
            keys_to_remove.append(key)
    
    # Remove expired entries
    for key in keys_to_remove:
        _cache.pop(key, None)
        _cache_ttl.pop(key, None)
    
    if keys_to_remove:
        logger.debug(f"Cleaned up {len(keys_to_remove)} expired cache entries")


def get_cache_stats() -> Dict[str, Any]:
    """Get cache statistics from both Redis (if available) and in-memory cache."""
    # Clean up expired entries periodically
    _cleanup_expired_cache()
    
    current_time = time.time()
    
    # In-memory cache stats
    total_entries = len(_cache)
    expired_entries = 0
    
    for key, cache_time in _cache_ttl.items():
        if current_time - cache_time > 3600:  # Assume 1 hour TTL for stats
            expired_entries += 1
    
    redis_client = _get_redis_client()
    stats = {
        "total_entries": total_entries,
        "expired_entries": expired_entries,
        "active_entries": total_entries - expired_entries,
        "cache_size_mb": sum(len(str(v)) for v in _cache.values()) / (1024 * 1024),
        "redis_available": redis_client is not None
    }
    
    # Add Redis stats if available
    if redis_client:
        try:
            redis_keys = redis_client.keys("*")
            stats["redis_keys"] = len(redis_keys)
            info = redis_client.info("memory")
            stats["redis_memory_mb"] = info.get("used_memory", 0) / (1024 * 1024)
        except Exception as e:
            stats["redis_error"] = str(e)
    
    return stats


def cleanup_expired_cache():
    """Remove expired cache entries."""
    current_time = time.time()
    expired_keys = []
    
    for key, cache_time in _cache_ttl.items():
        # Use a default TTL of 1 hour if not specified
        ttl = 3600
        if current_time - cache_time > ttl:
            expired_keys.append(key)
    
    for key in expired_keys:
        _cache.pop(key, None)
        _cache_ttl.pop(key, None)
    
    if expired_keys:
        logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")
