"""
Tests for per-session rate limiter.
"""

import asyncio
from datetime import datetime

from mcp_agentcore_memory.rate_limiter import PerSessionRateLimiter, RateLimitResult
import pytest


class TestPerSessionRateLimiter:
    """Tests for PerSessionRateLimiter."""

    @pytest.fixture
    def limiter(self):
        """Create a test rate limiter with faster rate for testing."""
        # 2 req/sec for faster tests (instead of 0.25)
        return PerSessionRateLimiter(rate=2.0, capacity=1)

    @pytest.mark.asyncio
    async def test_first_request_allowed(self, limiter):
        """First request should always be allowed."""
        result = await limiter.check("actor1", "session1")
        assert result.allowed is True
        assert result.wait_time_seconds == 0.0

    @pytest.mark.asyncio
    async def test_acquire_consumes_token(self, limiter):
        """Acquiring should consume a token."""
        # First acquire succeeds immediately
        success = await limiter.acquire("actor1", "session1", block=False)
        assert success is True

        # Second acquire without waiting should fail
        success = await limiter.acquire("actor1", "session1", block=False)
        assert success is False

    @pytest.mark.asyncio
    async def test_different_sessions_independent(self, limiter):
        """Different sessions should have independent limits."""
        # Session 1 uses its token
        await limiter.acquire("actor1", "session1", block=False)

        # Session 2 should still have its token
        result = await limiter.check("actor1", "session2")
        assert result.allowed is True

    @pytest.mark.asyncio
    async def test_different_actors_independent(self, limiter):
        """Different actors should have independent limits."""
        # Actor 1 uses its token
        await limiter.acquire("actor1", "session1", block=False)

        # Actor 2 should still have its token
        result = await limiter.check("actor2", "session1")
        assert result.allowed is True

    @pytest.mark.asyncio
    async def test_token_regeneration(self, limiter):
        """Tokens should regenerate over time."""
        # Use the token
        await limiter.acquire("actor1", "session1", block=False)

        # Wait for token to regenerate (0.5s at 2 req/sec)
        await asyncio.sleep(0.6)

        # Should have a token again
        result = await limiter.check("actor1", "session1")
        assert result.allowed is True

    @pytest.mark.asyncio
    async def test_blocking_acquire(self, limiter):
        """Blocking acquire should wait for token."""
        # Use the token
        await limiter.acquire("actor1", "session1", block=False)

        # Blocking acquire should wait and succeed
        start = datetime.now()
        success = await limiter.acquire("actor1", "session1", block=True)
        elapsed = (datetime.now() - start).total_seconds()

        assert success is True
        # Should have waited about 0.5s (at 2 req/sec)
        assert 0.3 < elapsed < 1.0

    @pytest.mark.asyncio
    async def test_cleanup_old_sessions(self, limiter):
        """Should clean up old session buckets."""
        # Create some sessions
        await limiter.acquire("actor1", "session1", block=False)
        await limiter.acquire("actor1", "session2", block=False)

        assert limiter.active_sessions == 2

        # Wait a tiny bit so sessions are "old"
        await asyncio.sleep(0.01)

        # Cleanup with very small max age should remove all
        removed = await limiter.cleanup_old_sessions(max_age_seconds=0)
        assert removed == 2
        assert limiter.active_sessions == 0

    def test_get_stats(self, limiter):
        """Should return correct stats."""
        stats = limiter.get_stats()

        assert stats["rate_per_second"] == 2.0
        assert stats["capacity"] == 1
        assert stats["active_sessions"] == 0
        assert stats["seconds_per_request"] == 0.5

    @pytest.mark.asyncio
    async def test_thundering_herd_prevention(self, limiter):
        """Multiple concurrent requests should serialize, not burst through."""
        # Use the token first
        await limiter.acquire("actor1", "session1", block=False)

        # Launch 3 concurrent blocking acquires
        import asyncio

        start = asyncio.get_event_loop().time()
        results = await asyncio.gather(
            limiter.acquire("actor1", "session1", block=True),
            limiter.acquire("actor1", "session1", block=True),
            limiter.acquire("actor1", "session1", block=True),
        )
        elapsed = asyncio.get_event_loop().time() - start

        # All should succeed
        assert all(results)

        # Should have taken at least 3 * 0.5s = 1.5s (serialized, not parallel)
        # With loop-based approach, each waiter re-checks after sleeping
        # At 2 req/sec, 3 requests after initial = ~1.5s minimum
        assert elapsed >= 1.0  # Conservative lower bound


class TestRateLimitResult:
    """Tests for RateLimitResult dataclass."""

    def test_allowed_result(self):
        """Test allowed result."""
        result = RateLimitResult(
            allowed=True,
            wait_time_seconds=0.0,
            tokens_remaining=1.0,
            session_key="actor:session",
        )
        assert result.allowed is True

    def test_blocked_result(self):
        """Test blocked result with wait time."""
        result = RateLimitResult(
            allowed=False,
            wait_time_seconds=3.5,
            tokens_remaining=0.1,
            session_key="actor:session",
        )
        assert result.allowed is False
        assert result.wait_time_seconds == 3.5
