"""
Caching system for HomeFit API calls
Provides in-memory caching for expensive operations like OSM queries and API calls
"""

import time
import hashlib
from typing import Any, Optional, Dict
from functools import wraps

# Simple in-memory cache
_cache: Dict[str, Dict[str, Any]] = {}
_cache_ttl: Dict[str, float] = {}

# Cache TTL settings (in seconds)
CACHE_TTL = {
    'osm_queries': 3600,      # 1 hour for OSM data
    'census_data': 86400,     # 24 hours for Census data
    'school_data': 86400,     # 24 hours for school data
    'airport_distances': 86400,  # 24 hours for airport calculations
    'geocoding': 86400,       # 24 hours for geocoding
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
    Decorator to cache function results.
    
    Args:
        ttl_seconds: Time to live for cached results in seconds
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache_key = _generate_cache_key(func.__name__, *args, **kwargs)
            current_time = time.time()
            
            # Check if we have a valid cached result
            if cache_key in _cache:
                cache_entry = _cache[cache_key]
                cache_time = _cache_ttl.get(cache_key, 0)
                
                if current_time - cache_time < ttl_seconds:
                    print(f"🔄 Cache hit for {func.__name__}")
                    return cache_entry
            
            # Cache miss or expired - execute function
            print(f"💾 Cache miss for {func.__name__} - executing")
            result = func(*args, **kwargs)
            
            # Store result in cache
            _cache[cache_key] = result
            _cache_ttl[cache_key] = current_time
            
            return result
        
        return wrapper
    return decorator


def clear_cache(cache_type: Optional[str] = None):
    """
    Clear cache entries.
    
    Args:
        cache_type: If provided, only clear entries matching this type
    """
    global _cache, _cache_ttl
    
    if cache_type is None:
        _cache.clear()
        _cache_ttl.clear()
        print("🧹 Cleared all cache")
    else:
        keys_to_remove = [key for key in _cache.keys() if key.startswith(f"{cache_type}:")]
        for key in keys_to_remove:
            _cache.pop(key, None)
            _cache_ttl.pop(key, None)
        print(f"🧹 Cleared {len(keys_to_remove)} {cache_type} cache entries")


def get_cache_stats() -> Dict[str, Any]:
    """Get cache statistics."""
    current_time = time.time()
    total_entries = len(_cache)
    expired_entries = 0
    
    for key, cache_time in _cache_ttl.items():
        if current_time - cache_time > 3600:  # Assume 1 hour TTL for stats
            expired_entries += 1
    
    return {
        "total_entries": total_entries,
        "expired_entries": expired_entries,
        "active_entries": total_entries - expired_entries,
        "cache_size_mb": sum(len(str(v)) for v in _cache.values()) / (1024 * 1024)
    }


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
        print(f"🧹 Cleaned up {len(expired_keys)} expired cache entries")
