"""Marketplace API client.

Provides the same interface as MockMarketplace but uses REST API.
"""

import logging
from typing import Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class MarketplaceAPIClient:
    """Client for Marketplace API service.

    Implements the same interface as MockMarketplace for seamless swapping.
    """

    def __init__(self, api_url: str, api_key: str, seed: Optional[int] = None):
        """Initialize marketplace API client.

        Args:
            api_url: Base URL of Marketplace API (e.g., http://localhost:8003)
            api_key: API key for authentication
            seed: Random seed for task generation
        """
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.headers = {"X-API-Key": api_key}
        self.seed = seed

        # Initialize marketplace on server if needed
        try:
            httpx.post(f"{self.api_url}/initialize", headers=self.headers, params={"seed": seed} if seed else {})
            logger.debug("Marketplace API initialized")
        except httpx.ConnectError as e:
            # Server not available - expected when server is offline
            logger.debug("Marketplace API initialization deferred (server offline): %s", type(e).__name__)
        except httpx.HTTPError as e:
            logger.debug("Marketplace API initialization deferred (HTTP error): %s", e)

    def generate_tasks(self, count: int = 5) -> List[Dict]:
        """Generate tasks from marketplace.

        Args:
            count: Number of tasks to generate

        Returns:
            List of task dictionaries

        Raises:
            ValueError: If API call fails
        """
        try:
            response = httpx.get(f"{self.api_url}/tasks", headers=self.headers, params={"count": count})
            response.raise_for_status()
            data = response.json()

            # Convert to MockMarketplace format
            return [
                {
                    "id": task["id"],
                    "difficulty": task["difficulty"],
                    "reward": task["reward"],
                    "compute_hours_required": task["compute_hours_required"],
                    "description": task["description"],
                }
                for task in data["tasks"]
            ]
        except httpx.HTTPError as e:
            raise ValueError(f"Failed to generate tasks: {e}") from e

    def complete_task(self, task: Dict) -> Dict:
        """Complete a task.

        Args:
            task: Task dictionary with 'id' field

        Returns:
            Completion result dictionary with 'success', 'reward', 'message' fields

        Raises:
            ValueError: If API call fails
        """
        try:
            # Get agent_id from API key (this is a simplification)
            # In a real implementation, we'd get this from authentication
            agent_id = "agent"  # Placeholder

            response = httpx.post(
                f"{self.api_url}/tasks/{task['id']}/complete",
                headers=self.headers,
                json={"agent_id": agent_id},
            )
            response.raise_for_status()
            data = response.json()

            return {
                "success": data["success"],
                "reward": data.get("reward", 0.0),
                "message": data.get("message", ""),
            }
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return {"success": False, "reward": 0.0, "message": "Task not found"}
            raise ValueError(f"Failed to complete task: {e}") from e
        except httpx.HTTPError as e:
            raise ValueError(f"Failed to complete task: {e}") from e

    def __repr__(self) -> str:
        """String representation."""
        return f"MarketplaceAPIClient(api_url={self.api_url}, seed={self.seed})"
