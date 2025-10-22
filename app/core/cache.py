"""
Caching system with Redis support and performance optimization utilities.
Provides in-memory and Redis-based caching with TTL, invalidation, and monitoring.
"""

import json
import logging
import asyncio
from typing import Any, Optional, Dict, List, Union, Callable
from datetime import datetime, timedelta
from functools import wraps
import hashlib
import pickle
from dataclasses import dataclass

try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

from app.core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class CacheStats:
    """Cache statistics for monitoring."""
    hits: int = 0
    misses: int = 0
    sets: int = 0
    deletes: int = 0
    errors: int = 0
    
    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.hits + self.misses
        return (self.hits / total) if total > 0 else 0.0


class InMemoryCache:
    """
    Simple in-memory cache with TTL support.
    Used as fallback when Redis is not available.
    """
    
    def __init__(self, max_size: int = 1000):
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.max_size = max_size
        self.stats = CacheStats()
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        try:
            if key in self.cache:
                entry = self.cache[key]
                
                # Check if expired
                if entry["expires_at"] and datetime.utcnow() > entry["expires_at"]:
                    del self.cache[key]
                    self.stats.misses += 1
                    return None
                
                self.stats.hits += 1
                return entry["value"]
            
            self.stats.misses += 1
            return None
            
        except Exception as e:
            logger.error(f"Cache get error: {e}")
            self.stats.errors += 1
            return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache with optional TTL."""
        try:
            # Evict oldest entries if cache is full
            if len(self.cache) >= self.max_size:
                oldest_key = next(iter(self.cache))
                del self.cache[oldest_key]
            
            expires_at = None
            if ttl:
                expires_at = datetime.utcnow() + timedelta(seconds=ttl)
            
            self.cache[key] = {
                "value": value,
                "expires_at": expires_at,
                "created_at": datetime.utcnow()
            }
            
            self.stats.sets += 1
            return True
            
        except Exception as e:
            logger.error(f"Cache set error: {e}")
            self.stats.errors += 1
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete value from cache."""
        try:
            if key in self.cache:
                del self.cache[key]
                self.stats.deletes += 1
                return True
            return False
            
        except Exception as e:
            logger.error(f"Cache delete error: {e}")
            self.stats.errors += 1
            return False
    
    async def clear(self) -> bool:
        """Clear all cache entries."""
        try:
            self.cache.clear()
            return True
        except Exception as e:
            logger.error(f"Cache clear error: {e}")
            return False
    
    async def keys(self, pattern: str = "*") -> List[str]:
        """Get cache keys matching pattern."""
        try:
            if pattern == "*":
                return list(self.cache.keys())
            
            # Simple pattern matching
            import fnmatch
            return [key for key in self.cache.keys() if fnmatch.fnmatch(key, pattern)]
            
        except Exception as e:
            logger.error(f"Cache keys error: {e}")
            return []


class RedisCache:
    """
    Redis-based cache with advanced features.
    Provides distributed caching with persistence and clustering support.
    """
    
    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self.redis_client: Optional[redis.Redis] = None
        self.stats = CacheStats()
    
    async def connect(self) -> bool:
        """Connect to Redis server."""
        try:
            self.redis_client = redis.from_url(self.redis_url, decode_responses=True)
            await self.redis_client.ping()
            logger.info("Connected to Redis cache")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.redis_client = None
            return False
    
    async def disconnect(self):
        """Disconnect from Redis server."""
        if self.redis_client:
            await self.redis_client.close()
            self.redis_client = None
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from Redis cache."""
        if not self.redis_client:
            return None
        
        try:
            value = await self.redis_client.get(key)
            if value is not None:
                self.stats.hits += 1
                return json.loads(value)
            
            self.stats.misses += 1
            return None
            
        except Exception as e:
            logger.error(f"Redis get error: {e}")
            self.stats.errors += 1
            return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in Redis cache with optional TTL."""
        if not self.redis_client:
            return False
        
        try:
            serialized_value = json.dumps(value, default=str)
            
            if ttl:
                await self.redis_client.setex(key, ttl, serialized_value)
            else:
                await self.redis_client.set(key, serialized_value)
            
            self.stats.sets += 1
            return True
            
        except Exception as e:
            logger.error(f"Redis set error: {e}")
            self.stats.errors += 1
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete value from Redis cache."""
        if not self.redis_client:
            return False
        
        try:
            result = await self.redis_client.delete(key)
            if result > 0:
                self.stats.deletes += 1
                return True
            return False
            
        except Exception as e:
            logger.error(f"Redis delete error: {e}")
            self.stats.errors += 1
            return False
    
    async def clear(self) -> bool:
        """Clear all cache entries."""
        if not self.redis_client:
            return False
        
        try:
            await self.redis_client.flushdb()
            return True
            
        except Exception as e:
            logger.error(f"Redis clear error: {e}")
            return False
    
    async def keys(self, pattern: str = "*") -> List[str]:
        """Get cache keys matching pattern."""
        if not self.redis_client:
            return []
        
        try:
            return await self.redis_client.keys(pattern)
            
        except Exception as e:
            logger.error(f"Redis keys error: {e}")
            return []
    
    async def expire(self, key: str, ttl: int) -> bool:
        """Set TTL for existing key."""
        if not self.redis_client:
            return False
        
        try:
            return await self.redis_client.expire(key, ttl)
            
        except Exception as e:
            logger.error(f"Redis expire error: {e}")
            return False


class CacheManager:
    """
    Unified cache manager that handles both Redis and in-memory caching.
    Automatically falls back to in-memory cache if Redis is unavailable.
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.redis_cache: Optional[RedisCache] = None
        self.memory_cache = InMemoryCache()
        self.use_redis = False
    
    async def initialize(self):
        """Initialize cache system."""
        # Try to connect to Redis if available and configured
        if REDIS_AVAILABLE and hasattr(self.settings, 'REDIS_URL') and self.settings.REDIS_URL:
            self.redis_cache = RedisCache(self.settings.REDIS_URL)
            self.use_redis = await self.redis_cache.connect()
            
            if self.use_redis:
                logger.info("Using Redis cache")
            else:
                logger.info("Redis unavailable, using in-memory cache")
        else:
            logger.info("Using in-memory cache")
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        if self.use_redis and self.redis_cache:
            return await self.redis_cache.get(key)
        return await self.memory_cache.get(key)
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache."""
        if self.use_redis and self.redis_cache:
            return await self.redis_cache.set(key, value, ttl)
        return await self.memory_cache.set(key, value, ttl)
    
    async def delete(self, key: str) -> bool:
        """Delete value from cache."""
        if self.use_redis and self.redis_cache:
            return await self.redis_cache.delete(key)
        return await self.memory_cache.delete(key)
    
    async def clear(self) -> bool:
        """Clear all cache entries."""
        if self.use_redis and self.redis_cache:
            return await self.redis_cache.clear()
        return await self.memory_cache.clear()
    
    async def keys(self, pattern: str = "*") -> List[str]:
        """Get cache keys matching pattern."""
        if self.use_redis and self.redis_cache:
            return await self.redis_cache.keys(pattern)
        return await self.memory_cache.keys(pattern)
    
    def get_stats(self) -> CacheStats:
        """Get cache statistics."""
        if self.use_redis and self.redis_cache:
            return self.redis_cache.stats
        return self.memory_cache.stats
    
    async def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate all keys matching pattern."""
        keys = await self.keys(pattern)
        count = 0
        
        for key in keys:
            if await self.delete(key):
                count += 1
        
        return count


# Global cache manager instance
cache_manager = CacheManager()


def cache_key(*args, **kwargs) -> str:
    """Generate cache key from arguments."""
    key_parts = []
    
    # Add positional arguments
    for arg in args:
        if hasattr(arg, 'id'):
            key_parts.append(f"{type(arg).__name__}:{arg.id}")
        else:
            key_parts.append(str(arg))
    
    # Add keyword arguments
    for k, v in sorted(kwargs.items()):
        if hasattr(v, 'id'):
            key_parts.append(f"{k}:{type(v).__name__}:{v.id}")
        else:
            key_parts.append(f"{k}:{v}")
    
    # Create hash for long keys
    key_string = ":".join(key_parts)
    if len(key_string) > 200:
        key_hash = hashlib.md5(key_string.encode()).hexdigest()
        return f"hash:{key_hash}"
    
    return key_string


def cached(ttl: int = 300, key_prefix: str = ""):
    """
    Decorator for caching function results.
    
    Args:
        ttl: Time to live in seconds
        key_prefix: Prefix for cache key
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            func_name = f"{func.__module__}.{func.__name__}"
            key_parts = [key_prefix, func_name] if key_prefix else [func_name]
            key_parts.extend([cache_key(*args, **kwargs)])
            cache_key_str = ":".join(filter(None, key_parts))
            
            # Try to get from cache
            cached_result = await cache_manager.get(cache_key_str)
            if cached_result is not None:
                return cached_result
            
            # Execute function and cache result
            result = await func(*args, **kwargs)
            await cache_manager.set(cache_key_str, result, ttl)
            
            return result
        
        return wrapper
    return decorator


def cache_invalidate(pattern: str):
    """
    Decorator for invalidating cache entries after function execution.
    
    Args:
        pattern: Cache key pattern to invalidate
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)
            await cache_manager.invalidate_pattern(pattern)
            return result
        
        return wrapper
    return decorator


class PerformanceMonitor:
    """
    Performance monitoring utility for tracking response times and bottlenecks.
    """
    
    def __init__(self):
        self.metrics: Dict[str, List[float]] = {}
        self.slow_queries: List[Dict[str, Any]] = []
        self.slow_threshold = 1.0  # seconds
    
    def record_metric(self, name: str, duration: float):
        """Record a performance metric."""
        if name not in self.metrics:
            self.metrics[name] = []
        
        self.metrics[name].append(duration)
        
        # Keep only last 1000 measurements
        if len(self.metrics[name]) > 1000:
            self.metrics[name] = self.metrics[name][-1000:]
        
        # Track slow queries
        if duration > self.slow_threshold:
            self.slow_queries.append({
                "name": name,
                "duration": duration,
                "timestamp": datetime.utcnow().isoformat()
            })
            
            # Keep only last 100 slow queries
            if len(self.slow_queries) > 100:
                self.slow_queries = self.slow_queries[-100:]
    
    def get_stats(self, name: str) -> Dict[str, Any]:
        """Get statistics for a metric."""
        if name not in self.metrics:
            return {}
        
        durations = self.metrics[name]
        return {
            "count": len(durations),
            "avg": sum(durations) / len(durations),
            "min": min(durations),
            "max": max(durations),
            "p95": sorted(durations)[int(len(durations) * 0.95)] if durations else 0,
            "p99": sorted(durations)[int(len(durations) * 0.99)] if durations else 0
        }
    
    def get_all_stats(self) -> Dict[str, Any]:
        """Get all performance statistics."""
        return {
            "metrics": {name: self.get_stats(name) for name in self.metrics},
            "slow_queries": self.slow_queries[-10:],  # Last 10 slow queries
            "cache_stats": cache_manager.get_stats().__dict__
        }


def monitor_performance(name: str):
    """
    Decorator for monitoring function performance.
    
    Args:
        name: Name for the metric
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = datetime.utcnow()
            
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                end_time = datetime.utcnow()
                duration = (end_time - start_time).total_seconds()
                performance_monitor.record_metric(name, duration)
        
        return wrapper
    return decorator


# Global performance monitor instance
performance_monitor = PerformanceMonitor()


async def initialize_cache():
    """Initialize the cache system."""
    await cache_manager.initialize()


async def get_cache_health() -> Dict[str, Any]:
    """Get cache system health status."""
    stats = cache_manager.get_stats()
    
    return {
        "status": "healthy" if stats.errors == 0 else "degraded",
        "backend": "redis" if cache_manager.use_redis else "memory",
        "statistics": stats.__dict__,
        "performance": performance_monitor.get_all_stats()
    }