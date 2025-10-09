"""GPU Orchestrator API client for dashboard."""

import logging
from typing import Any, AsyncGenerator, Dict, Optional

import httpx
import websockets

logger = logging.getLogger(__name__)


class GPUOrchestratorClient:
    """Client for communicating with GPU Orchestrator API."""

    def __init__(self, base_url: str, api_key: str, timeout: float = 30.0):
        """Initialize GPU Orchestrator client.

        Args:
            base_url: Base URL of GPU Orchestrator API (e.g., http://192.168.0.152:8000)
            api_key: API key for authentication
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.headers = {"X-API-Key": api_key}

    def _get_client(self) -> httpx.Client:
        """Get HTTP client with timeout and headers."""
        return httpx.Client(timeout=self.timeout, headers=self.headers)

    async def _get_async_client(self) -> httpx.AsyncClient:
        """Get async HTTP client with timeout and headers."""
        return httpx.AsyncClient(timeout=self.timeout, headers=self.headers)

    def health_check(self) -> Dict[str, Any]:
        """Check API health.

        Returns:
            Health status dict

        Raises:
            httpx.HTTPError: If request fails
        """
        with self._get_client() as client:
            response = client.get(f"{self.base_url}/health")
            response.raise_for_status()
            return response.json()  # type: ignore[no-any-return]

    def get_system_status(self) -> Dict[str, Any]:
        """Get system status including GPU, CPU, disk, jobs.

        Returns:
            System status dict

        Raises:
            httpx.HTTPError: If request fails
        """
        with self._get_client() as client:
            response = client.get(f"{self.base_url}/api/system/status")
            response.raise_for_status()
            return response.json()  # type: ignore[no-any-return]

    # Job Submission Methods

    def train_backdoor(self, **params) -> Dict[str, Any]:
        """Submit backdoor training job.

        Args:
            **params: Training parameters (model_path, backdoor_type, etc.)

        Returns:
            Job response dict with job_id

        Raises:
            httpx.HTTPError: If request fails
        """
        with self._get_client() as client:
            response = client.post(f"{self.base_url}/api/jobs/train-backdoor", json=params)
            response.raise_for_status()
            return response.json()  # type: ignore[no-any-return]

    def train_probes(self, **params) -> Dict[str, Any]:
        """Submit probe training job.

        Args:
            **params: Training parameters (model_path, layers, etc.)

        Returns:
            Job response dict with job_id

        Raises:
            httpx.HTTPError: If request fails
        """
        with self._get_client() as client:
            response = client.post(f"{self.base_url}/api/jobs/train-probes", json=params)
            response.raise_for_status()
            return response.json()  # type: ignore[no-any-return]

    def validate_backdoor(self, **params) -> Dict[str, Any]:
        """Submit validation job.

        Args:
            **params: Validation parameters (model_path, num_samples, etc.)

        Returns:
            Job response dict with job_id

        Raises:
            httpx.HTTPError: If request fails
        """
        with self._get_client() as client:
            response = client.post(f"{self.base_url}/api/jobs/validate", json=params)
            response.raise_for_status()
            return response.json()  # type: ignore[no-any-return]

    def apply_safety_training(self, **params) -> Dict[str, Any]:
        """Submit safety training job.

        Args:
            **params: Safety training parameters (model_path, method, etc.)

        Returns:
            Job response dict with job_id

        Raises:
            httpx.HTTPError: If request fails
        """
        with self._get_client() as client:
            response = client.post(f"{self.base_url}/api/jobs/safety-training", json=params)
            response.raise_for_status()
            return response.json()  # type: ignore[no-any-return]

    def test_persistence(self, **params) -> Dict[str, Any]:
        """Submit persistence testing job.

        Args:
            **params: Persistence test parameters (model_path, num_samples, etc.)

        Returns:
            Job response dict with job_id

        Raises:
            httpx.HTTPError: If request fails
        """
        with self._get_client() as client:
            response = client.post(f"{self.base_url}/api/jobs/test-persistence", json=params)
            response.raise_for_status()
            return response.json()  # type: ignore[no-any-return]

    # Job Management Methods

    def get_job(self, job_id: str) -> Dict[str, Any]:
        """Get job details by ID.

        Args:
            job_id: Job UUID as string

        Returns:
            Job details dict

        Raises:
            httpx.HTTPError: If request fails
        """
        with self._get_client() as client:
            response = client.get(f"{self.base_url}/api/jobs/{job_id}")
            response.raise_for_status()
            return response.json()  # type: ignore[no-any-return]

    def list_jobs(
        self,
        status: Optional[str] = None,
        job_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """List jobs with optional filtering.

        Args:
            status: Filter by status (queued, running, completed, failed, cancelled)
            job_type: Filter by type (train_backdoor, train_probes, etc.)
            limit: Maximum results to return
            offset: Pagination offset

        Returns:
            Jobs list response dict

        Raises:
            httpx.HTTPError: If request fails
        """
        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        if status:
            params["status"] = status
        if job_type:
            params["job_type"] = job_type

        with self._get_client() as client:
            response = client.get(f"{self.base_url}/api/jobs", params=params)
            response.raise_for_status()
            return response.json()  # type: ignore[no-any-return]

    def cancel_job(self, job_id: str) -> Dict[str, Any]:
        """Cancel a running job.

        Args:
            job_id: Job UUID as string

        Returns:
            Cancellation response dict

        Raises:
            httpx.HTTPError: If request fails
        """
        with self._get_client() as client:
            response = client.delete(f"{self.base_url}/api/jobs/{job_id}")
            response.raise_for_status()
            return response.json()  # type: ignore[no-any-return]

    def delete_job(self, job_id: str) -> Dict[str, Any]:
        """Permanently delete a job and all its files.

        This removes:
        - Job database entry
        - Log files
        - Result files
        - Stops container if running

        This action is irreversible.

        Args:
            job_id: Job UUID as string

        Returns:
            Deletion response dict with deleted_items list

        Raises:
            httpx.HTTPError: If request fails (403 if deletion disabled)
        """
        with self._get_client() as client:
            response = client.delete(f"{self.base_url}/api/jobs/{job_id}/permanent")
            response.raise_for_status()
            return response.json()  # type: ignore[no-any-return]

    # Log Retrieval Methods

    def get_logs(self, job_id: str, tail: int = 100) -> str:
        """Get job logs (last N lines).

        Args:
            job_id: Job UUID as string
            tail: Number of lines to retrieve

        Returns:
            Log text

        Raises:
            httpx.HTTPError: If request fails
        """
        with self._get_client() as client:
            response = client.get(f"{self.base_url}/api/jobs/{job_id}/logs", params={"tail": tail})
            response.raise_for_status()
            return response.text  # type: ignore[no-any-return]

    async def stream_logs(self, job_id: str) -> AsyncGenerator[str, None]:
        """Stream job logs via WebSocket.

        Args:
            job_id: Job UUID as string

        Yields:
            Log lines as they arrive

        Raises:
            websockets.WebSocketException: If WebSocket fails
        """
        ws_url = self.base_url.replace("http://", "ws://").replace("https://", "wss://")
        uri = f"{ws_url}/api/jobs/{job_id}/logs"

        try:
            async with websockets.connect(uri, extra_headers=self.headers) as websocket:
                async for message in websocket:
                    yield message
        except websockets.exceptions.WebSocketException as e:
            logger.error(f"WebSocket error streaming logs for job {job_id}: {e}")
            raise

    # Helper Methods

    def is_available(self) -> bool:
        """Check if GPU Orchestrator API is available.

        Returns:
            True if API is reachable and healthy
        """
        try:
            response = self.health_check()
            return response.get("status") == "healthy"
        except Exception as e:
            logger.warning(f"GPU Orchestrator API not available: {e}")
            return False

    def wait_for_job(self, job_id: str, poll_interval: float = 5.0, timeout: float = 3600.0) -> Dict[str, Any]:
        """Wait for job to complete.

        Args:
            job_id: Job UUID as string
            poll_interval: Seconds between status checks
            timeout: Maximum seconds to wait

        Returns:
            Final job details dict

        Raises:
            TimeoutError: If job doesn't complete within timeout
            httpx.HTTPError: If request fails
        """
        import time

        start_time = time.time()

        while True:
            job = self.get_job(job_id)
            status = job.get("status")

            if status in ["completed", "failed", "cancelled"]:
                return job

            elapsed = time.time() - start_time
            if elapsed >= timeout:
                raise TimeoutError(f"Job {job_id} did not complete within {timeout} seconds")

            time.sleep(poll_interval)
