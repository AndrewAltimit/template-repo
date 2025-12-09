"""Rate limiting middleware for API services."""

from collections import defaultdict
import time
from typing import Dict, Optional

from fastapi import Depends, HTTPException, Request, status
from pydantic import BaseModel


class RateLimiter:
    """Token bucket rate limiter for API endpoints."""

    def __init__(
        self,
        requests_per_minute: int = 60,
        requests_per_hour: int = 1000,
        burst_size: Optional[int] = None,
    ):
        """Initialize rate limiter.

        Args:
            requests_per_minute: Maximum requests per minute per agent
            requests_per_hour: Maximum requests per hour per agent
            burst_size: Maximum burst size (defaults to requests_per_minute)
        """
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.burst_size = burst_size or requests_per_minute

        # Store request timestamps per agent
        self.request_history: Dict[str, list] = defaultdict(list)

    def _clean_old_requests(self, agent_id: str, current_time: float):
        """Remove requests older than 1 hour.

        Args:
            agent_id: Agent ID
            current_time: Current timestamp
        """
        # Keep only requests from last hour
        cutoff_time = current_time - 3600
        self.request_history[agent_id] = [ts for ts in self.request_history[agent_id] if ts > cutoff_time]

    def check_rate_limit(self, agent_id: str) -> tuple[bool, Optional[str]]:
        """Check if agent is within rate limits.

        Args:
            agent_id: Agent ID to check

        Returns:
            Tuple of (is_allowed, error_message)
        """
        current_time = time.time()

        # Clean old requests
        self._clean_old_requests(agent_id, current_time)

        # Get request timestamps
        timestamps = self.request_history[agent_id]

        # Check hourly limit
        hourly_requests = len(timestamps)
        if hourly_requests >= self.requests_per_hour:
            return False, f"Hourly rate limit exceeded ({self.requests_per_hour} requests/hour)"

        # Check per-minute limit
        minute_cutoff = current_time - 60
        minute_requests = sum(1 for ts in timestamps if ts > minute_cutoff)
        if minute_requests >= self.requests_per_minute:
            return False, f"Per-minute rate limit exceeded ({self.requests_per_minute} requests/minute)"

        # Check burst limit
        recent_cutoff = current_time - 10  # Last 10 seconds
        recent_requests = sum(1 for ts in timestamps if ts > recent_cutoff)
        if recent_requests >= self.burst_size:
            return False, f"Burst limit exceeded ({self.burst_size} requests/10s)"

        return True, None

    def record_request(self, agent_id: str):
        """Record a request for an agent.

        Args:
            agent_id: Agent ID
        """
        current_time = time.time()
        self.request_history[agent_id].append(current_time)

    def get_limit_info(self, agent_id: str) -> dict:
        """Get rate limit information for an agent.

        Args:
            agent_id: Agent ID

        Returns:
            Dictionary with rate limit info
        """
        current_time = time.time()
        self._clean_old_requests(agent_id, current_time)

        timestamps = self.request_history[agent_id]
        hourly_requests = len(timestamps)

        minute_cutoff = current_time - 60
        minute_requests = sum(1 for ts in timestamps if ts > minute_cutoff)

        # Calculate reset times
        if timestamps:
            oldest_timestamp = min(timestamps)
            hourly_reset = oldest_timestamp + 3600
            minute_reset = max(ts for ts in timestamps if ts > minute_cutoff) + 60 if minute_requests > 0 else current_time
        else:
            hourly_reset = current_time
            minute_reset = current_time

        return {
            "hourly_limit": self.requests_per_hour,
            "hourly_remaining": max(0, self.requests_per_hour - hourly_requests),
            "hourly_reset": hourly_reset,
            "minute_limit": self.requests_per_minute,
            "minute_remaining": max(0, self.requests_per_minute - minute_requests),
            "minute_reset": minute_reset,
        }


# Global rate limiter instance
rate_limiter = RateLimiter(
    requests_per_minute=60,
    requests_per_hour=1000,
    burst_size=10,
)


async def check_rate_limit(request: Request) -> None:
    """Dependency to check rate limits.

    Note: This function does NOT perform agent-specific rate limiting.
    Use verify_and_rate_limit() for endpoints that need both auth and rate limiting.

    Args:
        request: FastAPI request object

    Raises:
        HTTPException: If rate limit exceeded
    """
    # This is a placeholder for request-level (non-agent-specific) rate limiting
    # Agent-specific rate limiting should use verify_and_rate_limit()


def verify_and_rate_limit():
    """Create a dependency that combines authentication and rate limiting.

    This is a factory function that creates a dependency combining verify_api_key
    and rate limiting in the correct order.

    Returns:
        Dependency function that verifies auth and checks rate limits
    """
    from economic_agents.api.auth import verify_api_key

    async def combined_dependency(request: Request, agent_id: str = Depends(verify_api_key)) -> str:
        """Verify API key and check rate limits.

        Args:
            request: FastAPI request object
            agent_id: Agent ID from verify_api_key dependency

        Returns:
            Agent ID

        Raises:
            HTTPException: If rate limit exceeded
        """
        is_allowed, error_message = rate_limiter.check_rate_limit(agent_id)

        if not is_allowed:
            # Get limit info for headers
            limit_info = rate_limiter.get_limit_info(agent_id)

            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=error_message,
                headers={
                    "X-RateLimit-Limit-Hour": str(limit_info["hourly_limit"]),
                    "X-RateLimit-Remaining-Hour": str(limit_info["hourly_remaining"]),
                    "X-RateLimit-Limit-Minute": str(limit_info["minute_limit"]),
                    "X-RateLimit-Remaining-Minute": str(limit_info["minute_remaining"]),
                    "Retry-After": "60",
                },
            )

        # Record the request
        rate_limiter.record_request(agent_id)

        return agent_id

    return combined_dependency


class RateLimitConfig(BaseModel):
    """Configuration for rate limiting."""

    enabled: bool = True
    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    burst_size: int = 10


# Default rate limit config
rate_limit_config = RateLimitConfig()
