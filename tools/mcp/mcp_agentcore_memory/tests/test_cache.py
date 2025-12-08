"""
Tests for memory cache.
"""

import time

from mcp_agentcore_memory.cache import MemoryCache, get_cache, reset_cache
import pytest


class TestMemoryCache:
    """Tests for MemoryCache."""

    @pytest.fixture
    def cache(self):
        """Create a test cache with short TTL."""
        return MemoryCache(max_size=10, ttl_seconds=1)

    def test_set_and_get(self, cache):
        """Basic set and get."""
        cache.set("query1", "namespace1", [{"content": "result1"}])
        result = cache.get("query1", "namespace1")

        assert result is not None
        assert result[0]["content"] == "result1"

    def test_get_miss(self, cache):
        """Cache miss returns None."""
        result = cache.get("nonexistent", "namespace")
        assert result is None

    def test_different_namespaces(self, cache):
        """Same query, different namespaces are separate."""
        cache.set("query", "ns1", [{"content": "result1"}])
        cache.set("query", "ns2", [{"content": "result2"}])

        assert cache.get("query", "ns1")[0]["content"] == "result1"
        assert cache.get("query", "ns2")[0]["content"] == "result2"

    def test_ttl_expiration(self, cache):
        """Entries should expire after TTL."""
        cache.set("query", "ns", [{"content": "result"}])

        # Should be present
        assert cache.get("query", "ns") is not None

        # Wait for TTL
        time.sleep(1.1)

        # Should be expired
        assert cache.get("query", "ns") is None

    def test_max_size_eviction(self, cache):
        """Should evict oldest when at capacity."""
        # Fill the cache
        for i in range(10):
            cache.set(f"query{i}", "ns", [{"content": f"result{i}"}])

        assert cache.size == 10

        # Add one more
        cache.set("query_new", "ns", [{"content": "new"}])

        # Still at max size
        assert cache.size == 10

        # New entry should exist
        assert cache.get("query_new", "ns") is not None

    def test_invalidate_all(self, cache):
        """Invalidate entire cache."""
        cache.set("q1", "ns1", [{}])
        cache.set("q2", "ns2", [{}])

        count = cache.invalidate()
        assert count == 2
        assert cache.size == 0

    def test_invalidate_namespace(self, cache):
        """Invalidate specific namespace."""
        cache.set("q1", "codebase/patterns", [{}])
        cache.set("q2", "codebase/conventions", [{}])
        cache.set("q3", "agents/claude", [{}])

        # Invalidate codebase namespace (prefix match)
        count = cache.invalidate("codebase")
        assert count == 2

        # agents/claude should still exist
        assert cache.get("q3", "agents/claude") is not None

    def test_cleanup_expired(self, cache):
        """Cleanup should remove expired entries."""
        cache.set("q1", "ns", [{}])

        # Wait for expiration
        time.sleep(1.1)

        count = cache.cleanup_expired()
        assert count == 1
        assert cache.size == 0

    def test_get_stats(self, cache):
        """Should return correct stats."""
        cache.set("q1", "codebase/patterns", [{}])
        cache.set("q2", "agents/claude", [{}])

        stats = cache.get_stats()

        assert stats["size"] == 2
        assert stats["max_size"] == 10
        assert stats["ttl_seconds"] == 1.0
        assert "codebase" in stats["by_namespace_category"]
        assert "agents" in stats["by_namespace_category"]


class TestCacheSingleton:
    """Tests for cache singleton."""

    def test_get_cache_returns_same_instance(self):
        """get_cache should return singleton."""
        reset_cache()

        cache1 = get_cache()
        cache2 = get_cache()

        assert cache1 is cache2

    def test_reset_cache(self):
        """reset_cache should clear singleton."""
        cache1 = get_cache()
        reset_cache()
        cache2 = get_cache()

        assert cache1 is not cache2
