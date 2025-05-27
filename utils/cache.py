import asyncio
import time
import sys
from typing import Dict, Any, Optional
from collections import OrderedDict

class SimpleCache:
    """
    Unified cache with LRU eviction and TTL support
    Thread-safe with asyncio locks
    """
    
    def __init__(self, max_size: int = 1000, ttl: int = 300):
        self._cache = OrderedDict()
        self._timestamps = {}
        self._lock = asyncio.Lock()
        self.max_size = max_size
        self.ttl = ttl
        
        # Statistics
        self._hits = 0
        self._misses = 0
        self._evictions = 0
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache, returns None if not found or expired"""
        async with self._lock:
            if key in self._cache:
                # Check if expired
                if time.time() - self._timestamps[key] < self.ttl:
                    # Move to end for LRU
                    self._cache.move_to_end(key)
                    self._hits += 1
                    return self._cache[key]
                else:
                    # Remove expired entry
                    del self._cache[key]
                    del self._timestamps[key]
                    self._evictions += 1
            
            self._misses += 1
            return None
    
    async def set(self, key: str, value: Any) -> None:
        """Set value in cache with current timestamp"""
        async with self._lock:
            # Remove oldest entries if at capacity
            while len(self._cache) >= self.max_size:
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]
                del self._timestamps[oldest_key]
                self._evictions += 1
            
            # Add/update entry
            self._cache[key] = value
            self._timestamps[key] = time.time()
            self._cache.move_to_end(key)
    
    async def delete(self, key: str) -> bool:
        """Delete specific key from cache"""
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                del self._timestamps[key]
                return True
            return False
    
    async def clear(self) -> None:
        """Clear all cache entries"""
        async with self._lock:
            self._cache.clear()
            self._timestamps.clear()
            self._hits = 0
            self._misses = 0
            self._evictions = 0
    
    async def cleanup_expired(self) -> int:
        """Remove all expired entries, returns number of removed items"""
        current_time = time.time()
        expired_keys = []
        
        async with self._lock:
            for key, timestamp in self._timestamps.items():
                if current_time - timestamp >= self.ttl:
                    expired_keys.append(key)
            
            for key in expired_keys:
                del self._cache[key]
                del self._timestamps[key]
                self._evictions += 1
        
        return len(expired_keys)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total_requests = self._hits + self._misses
        hit_rate = (self._hits / total_requests * 100) if total_requests > 0 else 0
        
        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "hits": self._hits,
            "misses": self._misses,
            "evictions": self._evictions,
            "hit_rate_percent": round(hit_rate, 2),
            "memory_usage_estimate_kb": round(sys.getsizeof(self._cache) / 1024, 2),
            "ttl_seconds": self.ttl
        }

# Cache instances for different data types
# Using different TTLs based on data volatility

# General API cache (routes, stations) - 5 minutes
api_cache = SimpleCache(max_size=500, ttl=300)

# Geocoding cache (relatively static) - 1 week 
geocoding_cache = SimpleCache(max_size=200, ttl=604800)

# Bike/transport cache (very dynamic) - 30 seconds
transport_cache = SimpleCache(max_size=100, ttl=30)

# Mensa menu cache (changes daily) - 1 week
mensa_cache = SimpleCache(max_size=50, ttl=604800)

# Backward compatibility for existing code
CACHE_TTL = 30  # Keep original constant

async def get_cached_data(cache_key: str) -> Optional[Any]:
    """
    Backward compatibility function for existing code
    Get data from general API cache
    
    Args:
        cache_key: Cache key
    
    Returns:
        Cached data or None if not available
    """
    return await api_cache.get(cache_key)

async def set_cached_data(cache_key: str, data: Any) -> None:
    """
    Backward compatibility function for existing code
    Set data in general API cache
    
    Args:
        cache_key: Cache key
        data: Data to cache
    """
    await api_cache.set(cache_key, data)

# Management functions
async def cleanup_all_caches() -> Dict[str, int]:
    """Cleanup expired entries from all caches"""
    results = {}
    
    for name, cache in [
        ("api", api_cache),
        ("geocoding", geocoding_cache),
        ("transport", transport_cache),
        ("mensa", mensa_cache)
    ]:
        cleaned = await cache.cleanup_expired()
        results[name] = cleaned
    
    return results

def get_all_cache_stats() -> Dict[str, Dict[str, Any]]:
    """Get statistics for all caches"""
    return {
        "api_cache": api_cache.get_stats(),
        "geocoding_cache": geocoding_cache.get_stats(),
        "transport_cache": transport_cache.get_stats(),
        "mensa_cache": mensa_cache.get_stats()
    }