"""
Local Memory Cache

LRU cache for frequently accessed memories to reduce provider round-trips.
Especially useful for AgentCore where retrieval has latency.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """A cache entry with expiration tracking."""

    results: List[Any]
    timestamp: datetime
    namespace: str


class MemoryCache:
    """
    LRU cache for frequently accessed memories.

    Features:
    - TTL-based expiration
    - Namespace-aware invalidation
    - Size-limited with LRU eviction

    Attributes:
        max_size: Maximum cache entries
        ttl: Time-to-live for entries
    """

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 300):
        """
        Initialize the cache.

        Args:
            max_size: Maximum number of cache entries
            ttl_seconds: Time-to-live in seconds (default: 5 minutes)
        """
        self.max_size = max_size
        self.ttl = timedelta(seconds=ttl_seconds)
        self._cache: Dict[str, CacheEntry] = {}

    def _make_key(self, query: str, namespace: str) -> str:
        """Create a cache key from query and namespace."""
        return hashlib.md5(f"{query}:{namespace}".encode()).hexdigest()

    def get(self, query: str, namespace: str) -> Optional[List[Any]]:
        """
        Get cached results for a query.

        Args:
            query: Search query
            namespace: Memory namespace

        Returns:
            Cached results or None if not found/expired
        """
        key = self._make_key(query, namespace)

        if key in self._cache:
            entry = self._cache[key]
            if datetime.now() - entry.timestamp < self.ttl:
                logger.debug("Cache hit for query in namespace %s", namespace)
                return entry.results
            else:
                # Expired - remove
                self._evict_key(key)
                logger.debug("Cache expired for query in namespace %s", namespace)

        return None

    def set(self, query: str, namespace: str, results: List[Any]) -> None:
        """
        Cache results for a query.

        Args:
            query: Search query
            namespace: Memory namespace
            results: Results to cache
        """
        key = self._make_key(query, namespace)

        # Evict oldest if at capacity
        if len(self._cache) >= self.max_size and key not in self._cache:
            oldest_key = min(
                self._cache.keys(),
                key=lambda k: self._cache[k].timestamp,
            )
            self._evict_key(oldest_key)
            logger.debug("Evicted oldest cache entry due to size limit")

        self._cache[key] = CacheEntry(
            results=results,
            timestamp=datetime.now(),
            namespace=namespace,
        )

    def _evict_key(self, key: str) -> None:
        """Remove a key from cache."""
        self._cache.pop(key, None)

    def invalidate(self, namespace: Optional[str] = None) -> int:
        """
        Invalidate cache entries.

        Args:
            namespace: If provided, only invalidate entries for this namespace.
                      Supports prefix matching (e.g., "codebase" matches "codebase/patterns")
                      If None, clears entire cache.

        Returns:
            Number of entries invalidated
        """
        if namespace is None:
            count = len(self._cache)
            self._cache.clear()
            logger.debug("Invalidated entire cache (%d entries)", count)
            return count

        # Find keys matching namespace (prefix or exact)
        keys_to_remove = [
            key
            for key, entry in self._cache.items()
            if entry.namespace == namespace or entry.namespace.startswith(f"{namespace}/")
        ]

        for key in keys_to_remove:
            self._evict_key(key)

        if keys_to_remove:
            logger.debug(
                "Invalidated %d cache entries for namespace %s",
                len(keys_to_remove),
                namespace,
            )

        return len(keys_to_remove)

    def cleanup_expired(self) -> int:
        """
        Remove all expired entries.

        Returns:
            Number of entries removed
        """
        now = datetime.now()
        expired_keys = [key for key, entry in self._cache.items() if now - entry.timestamp >= self.ttl]

        for key in expired_keys:
            self._evict_key(key)

        if expired_keys:
            logger.debug("Cleaned up %d expired cache entries", len(expired_keys))

        return len(expired_keys)

    @property
    def size(self) -> int:
        """Current number of cached entries."""
        return len(self._cache)

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        now = datetime.now()
        expired_count = sum(1 for entry in self._cache.values() if now - entry.timestamp >= self.ttl)

        # Count entries by namespace category
        namespace_counts: Dict[str, int] = {}
        for entry in self._cache.values():
            category = entry.namespace.split("/")[0] if "/" in entry.namespace else entry.namespace
            namespace_counts[category] = namespace_counts.get(category, 0) + 1

        return {
            "size": self.size,
            "max_size": self.max_size,
            "ttl_seconds": self.ttl.total_seconds(),
            "expired_entries": expired_count,
            "active_entries": self.size - expired_count,
            "by_namespace_category": namespace_counts,
        }


# Singleton cache instance
_cache_instance: Optional[MemoryCache] = None


def get_cache(max_size: int = 1000, ttl_seconds: int = 300) -> MemoryCache:
    """
    Get the singleton cache instance.

    Args:
        max_size: Maximum cache entries (only used on first call)
        ttl_seconds: TTL in seconds (only used on first call)

    Returns:
        The MemoryCache singleton
    """
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = MemoryCache(max_size=max_size, ttl_seconds=ttl_seconds)
    return _cache_instance


def reset_cache() -> None:
    """Reset the cache singleton (useful for testing)."""
    global _cache_instance
    _cache_instance = None
