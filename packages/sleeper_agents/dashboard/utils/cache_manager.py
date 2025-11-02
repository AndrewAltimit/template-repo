"""
Cache manager for dashboard performance optimization.
"""

import hashlib
import json
import logging
import time
from functools import wraps
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class CacheManager:
    """Manages caching for dashboard data."""

    def __init__(self, ttl: int = 300):
        """Initialize cache manager.

        Args:
            ttl: Time to live for cache entries in seconds (default: 5 minutes)
        """
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.ttl = ttl

    def _get_cache_key(self, *args, **kwargs) -> str:
        """Generate cache key from arguments.

        Returns:
            Hash of arguments as cache key
        """
        # Create a string representation of arguments
        key_data = {"args": args, "kwargs": kwargs}
        key_str = json.dumps(key_data, sort_keys=True, default=str)
        return hashlib.md5(key_str.encode()).hexdigest()

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        if key not in self.cache:
            return None

        entry = self.cache[key]

        # Check if expired
        if time.time() - entry["timestamp"] > self.ttl:
            del self.cache[key]
            return None

        logger.debug(f"Cache hit for key: {key}")
        return entry["value"]

    def set(self, key: str, value: Any):
        """Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
        """
        self.cache[key] = {"value": value, "timestamp": time.time()}
        logger.debug(f"Cached value for key: {key}")

    def clear(self):
        """Clear all cache entries."""
        self.cache.clear()
        logger.info("Cache cleared")

    def clear_expired(self):
        """Clear expired entries from cache."""
        current_time = time.time()
        expired_keys = [key for key, entry in self.cache.items() if current_time - entry["timestamp"] > self.ttl]

        for key in expired_keys:
            del self.cache[key]

        if expired_keys:
            logger.debug(f"Cleared {len(expired_keys)} expired cache entries")

    def cache_decorator(self, func):
        """Decorator to cache function results.

        Args:
            func: Function to decorate

        Returns:
            Decorated function with caching
        """

        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = self._get_cache_key(func.__name__, *args, **kwargs)

            # Check cache
            cached_value = self.get(cache_key)
            if cached_value is not None:
                return cached_value

            # Call function and cache result
            result = func(*args, **kwargs)
            self.set(cache_key, result)

            return result

        return wrapper

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        current_time = time.time()
        total_entries = len(self.cache)
        expired_entries = sum(1 for entry in self.cache.values() if current_time - entry["timestamp"] > self.ttl)
        active_entries = total_entries - expired_entries

        return {
            "total_entries": total_entries,
            "active_entries": active_entries,
            "expired_entries": expired_entries,
            "ttl_seconds": self.ttl,
            "memory_keys": list(self.cache.keys())[:10],  # First 10 keys for debugging
        }


class DataFrameCache:
    """Specialized cache for pandas DataFrames with compression."""

    def __init__(self, ttl: int = 300):
        """Initialize DataFrame cache.

        Args:
            ttl: Time to live in seconds
        """
        self.cache_manager = CacheManager(ttl)

    def cache_dataframe(self, key: str, df):
        """Cache a DataFrame with compression.

        Args:
            key: Cache key
            df: DataFrame to cache
        """
        # Convert DataFrame to dict for JSON serialization
        df_dict = {"data": df.to_dict("records"), "columns": list(df.columns), "index": list(df.index)}
        self.cache_manager.set(key, df_dict)

    def get_dataframe(self, key: str):
        """Get DataFrame from cache.

        Args:
            key: Cache key

        Returns:
            DataFrame or None if not cached
        """
        import pandas as pd

        df_dict = self.cache_manager.get(key)
        if df_dict is None:
            return None

        # Reconstruct DataFrame
        df = pd.DataFrame(df_dict["data"], columns=df_dict["columns"])
        if df_dict["index"]:
            df.index = df_dict["index"]

        return df
