"""Compute API client.

Provides the same interface as MockCompute but uses REST API.
"""

import logging

import httpx

logger = logging.getLogger(__name__)


class ComputeAPIClient:
    """Client for Compute API service.

    Implements the same interface as MockCompute for seamless swapping.
    """

    def __init__(self, api_url: str, api_key: str, initial_hours: float = 48.0, cost_per_hour: float = 0.0):
        """Initialize compute API client.

        Args:
            api_url: Base URL of Compute API (e.g., http://localhost:8002)
            api_key: API key for authentication
            initial_hours: Initial compute hours (only used if compute doesn't exist)
            cost_per_hour: Cost per compute hour
        """
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.headers = {"X-API-Key": api_key}
        self._cost_per_hour = cost_per_hour

        # Initialize compute on server if needed
        try:
            response = httpx.get(f"{self.api_url}/hours", headers=self.headers)
            if response.status_code == 200:
                # Compute exists
                pass
        except httpx.ConnectError:
            # Server not available - will fail on first use
            pass
        except Exception:
            # Try to initialize
            try:
                httpx.post(
                    f"{self.api_url}/initialize",
                    headers=self.headers,
                    params={"initial_hours": initial_hours, "cost_per_hour": cost_per_hour},
                )
            except Exception as e:
                logger.debug("Compute API initialization deferred: %s", e)

    @property
    def hours_remaining(self) -> float:
        """Get remaining compute hours.

        Returns:
            Remaining hours

        Raises:
            ValueError: If API call fails
        """
        try:
            response = httpx.get(f"{self.api_url}/hours", headers=self.headers)
            response.raise_for_status()
            return float(response.json()["hours_remaining"])
        except httpx.HTTPError as e:
            raise ValueError(f"Failed to get hours: {e}") from e

    @property
    def cost_per_hour(self) -> float:
        """Get cost per compute hour.

        Returns:
            Cost per hour

        Raises:
            ValueError: If API call fails
        """
        try:
            response = httpx.get(f"{self.api_url}/cost", headers=self.headers)
            response.raise_for_status()
            return float(response.json()["cost_per_hour"])
        except httpx.HTTPError:
            # Fallback to stored value
            return self._cost_per_hour

    def allocate_hours(self, hours: float, purpose: str = "task"):
        """Allocate compute hours.

        Args:
            hours: Hours to allocate
            purpose: Purpose of allocation

        Raises:
            ValueError: If insufficient hours or API call fails
        """
        if hours <= 0:
            raise ValueError("Hours must be positive")

        try:
            response = httpx.post(
                f"{self.api_url}/allocate",
                headers=self.headers,
                json={"hours": hours, "purpose": purpose},
            )
            response.raise_for_status()
            result = response.json()

            if not result["success"]:
                raise ValueError(result.get("message", "Allocation failed"))

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 400:
                raise ValueError(f"Insufficient hours: {e.response.json()['message']}") from e
            raise ValueError(f"Failed to allocate hours: {e}") from e

    def tick(self):
        """Advance time by one cycle (decay hours).

        Raises:
            ValueError: If API call fails
        """
        try:
            response = httpx.post(f"{self.api_url}/tick", headers=self.headers)
            response.raise_for_status()
        except httpx.HTTPError as e:
            raise ValueError(f"Failed to tick: {e}") from e

    def __repr__(self) -> str:
        """String representation."""
        return f"ComputeAPIClient(hours_remaining={self.hours_remaining:.2f}, api_url={self.api_url})"
