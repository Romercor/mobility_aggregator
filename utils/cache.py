from typing import Dict, Any, Optional
import time
import asyncio

# Simple in-memory cache
_cache: Dict[str, Any] = {}
_cache_timestamps: Dict[str, float] = {}
_cache_lock = asyncio.Lock()
CACHE_TTL = 30  # seconds

async def get_cached_data(cache_key: str) -> Optional[Any]:
    """
    Get data from cache if it exists and is not expired
    
    Args:
        cache_key: Cache key
    
    Returns:
        Cached data or None if not available
    """
    async with _cache_lock:
        if cache_key in _cache and time.time() - _cache_timestamps.get(cache_key, 0) < CACHE_TTL:
            return _cache[cache_key]
    return None

async def set_cached_data(cache_key: str, data: Any) -> None:
    """
    Set data in cache
    
    Args:
        cache_key: Cache key
        data: Data to cache
    """
    async with _cache_lock:
        _cache[cache_key] = data
        _cache_timestamps[cache_key] = time.time()