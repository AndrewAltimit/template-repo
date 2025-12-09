"""
Per-Session Rate Limiter

Rate limiter keyed by (actor_id, session_id) for AWS AgentCore CreateEvent.

CRITICAL: CreateEvent is limited to 0.25 req/sec per actor+session pair.
This means ONE event every 4 seconds per session!
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class TokenBucket:
    """Token bucket state for a single session."""

    tokens: float
    last_update: datetime


@dataclass
class RateLimitResult:
    """Result of a rate limit check."""

    allowed: bool
    wait_time_seconds: float = 0.0
    tokens_remaining: float = 0.0
    session_key: str = ""


class PerSessionRateLimiter:
    """
    Rate limiter keyed by (actor_id, session_id) for CreateEvent.

    CRITICAL: CreateEvent is limited to 0.25 req/sec per actor+session.
    This means ONE event every 4 seconds per session!

    Uses token bucket algorithm with per-session buckets.
    """

    def __init__(
        self,
        rate: float = 0.25,
        capacity: int = 1,
        cleanup_interval_seconds: int = 3600,
    ):
        """
        Initialize the rate limiter.

        Args:
            rate: Tokens per second (0.25 for CreateEvent = 1 per 4 seconds)
            capacity: Max burst (1 = no burst allowed)
            cleanup_interval_seconds: How long to keep idle session buckets
        """
        self.rate = rate
        self.capacity = capacity
        self.cleanup_interval = timedelta(seconds=cleanup_interval_seconds)

        # Key: (actor_id, session_id) -> TokenBucket
        self._buckets: Dict[Tuple[str, str], TokenBucket] = {}
        self._lock = asyncio.Lock()

    def _make_key(self, actor_id: str, session_id: str) -> Tuple[str, str]:
        """Create a bucket key from actor and session IDs."""
        return (actor_id, session_id)

    async def check(self, actor_id: str, session_id: str) -> RateLimitResult:
        """
        Check if a request is allowed without consuming a token.

        Args:
            actor_id: Actor identifier
            session_id: Session identifier

        Returns:
            RateLimitResult with allowed status and wait time if blocked
        """
        key = self._make_key(actor_id, session_id)

        async with self._lock:
            now = datetime.now()

            # Get or create bucket for this session
            if key in self._buckets:
                bucket = self._buckets[key]
                elapsed = (now - bucket.last_update).total_seconds()
                tokens = min(self.capacity, bucket.tokens + elapsed * self.rate)
            else:
                tokens = float(self.capacity)

            if tokens >= 1:
                return RateLimitResult(
                    allowed=True,
                    wait_time_seconds=0.0,
                    tokens_remaining=tokens,
                    session_key=f"{actor_id}:{session_id}",
                )

            # Calculate wait time
            wait_time = (1 - tokens) / self.rate

            return RateLimitResult(
                allowed=False,
                wait_time_seconds=wait_time,
                tokens_remaining=tokens,
                session_key=f"{actor_id}:{session_id}",
            )

    async def acquire(self, actor_id: str, session_id: str, block: bool = True) -> bool:
        """
        Acquire a token for the given actor+session.

        Uses a loop to prevent "thundering herd" race conditions where
        multiple waiters wake up simultaneously and all proceed.

        Args:
            actor_id: Actor identifier
            session_id: Session identifier
            block: If True, blocks until a token is available.
                   If False, returns immediately with success/failure.

        Returns:
            True if token was acquired, False if rate limited (when block=False)
        """
        key = self._make_key(actor_id, session_id)

        while True:
            async with self._lock:
                now = datetime.now()

                # Get or create bucket for this session
                if key in self._buckets:
                    bucket = self._buckets[key]
                    elapsed = (now - bucket.last_update).total_seconds()
                    tokens = min(self.capacity, bucket.tokens + elapsed * self.rate)
                else:
                    tokens = float(self.capacity)

                if tokens >= 1:
                    # Consume token
                    self._buckets[key] = TokenBucket(tokens=tokens - 1, last_update=now)
                    return True

                if not block:
                    return False

                # Calculate wait time (could be up to 4 seconds!)
                wait_time = (1 - tokens) / self.rate

            # Wait outside the lock, then loop back to re-check
            # This prevents thundering herd: multiple waiters will serialize
            logger.debug(
                "Rate limited for %s:%s, waiting %.2f seconds",
                actor_id,
                session_id,
                wait_time,
            )
            await asyncio.sleep(wait_time)
            # Loop back to re-acquire lock and re-check token availability

    async def cleanup_old_sessions(self, max_age_seconds: Optional[int] = None) -> int:
        """
        Remove buckets for sessions older than max_age_seconds.

        Args:
            max_age_seconds: Override default cleanup interval

        Returns:
            Number of sessions cleaned up
        """
        max_age = timedelta(seconds=max_age_seconds) if max_age_seconds is not None else self.cleanup_interval
        now = datetime.now()
        removed = 0

        async with self._lock:
            to_remove = [key for key, bucket in self._buckets.items() if (now - bucket.last_update) >= max_age]
            for key in to_remove:
                del self._buckets[key]
                removed += 1

        if removed > 0:
            logger.debug("Cleaned up %d idle session rate limit buckets", removed)

        return removed

    @property
    def active_sessions(self) -> int:
        """Return number of active session buckets."""
        return len(self._buckets)

    def get_stats(self) -> dict:
        """Get rate limiter statistics."""
        return {
            "rate_per_second": self.rate,
            "capacity": self.capacity,
            "active_sessions": self.active_sessions,
            "seconds_per_request": 1 / self.rate if self.rate > 0 else float("inf"),
        }


# Singleton instance for CreateEvent rate limiting
_event_rate_limiter: Optional[PerSessionRateLimiter] = None


def get_event_rate_limiter() -> PerSessionRateLimiter:
    """
    Get the singleton rate limiter for CreateEvent operations.

    Rate: 0.25 req/sec per actor+session (1 request every 4 seconds)
    """
    global _event_rate_limiter
    if _event_rate_limiter is None:
        _event_rate_limiter = PerSessionRateLimiter(rate=0.25, capacity=1)
    return _event_rate_limiter
