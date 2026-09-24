"""GPU Orchestrator API client for dashboard."""

import logging
from typing import Any, Dict, Optional

import httpx

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
            return response.json()

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
            return response.json()

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
            return response.json()

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
            return response.json()

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
            return response.json()

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
            return response.json()

    def test_persistence(self, **params) -> Dict[str, Any]:
        """Submit persistence testing job.

        Args:
            **params: Persistence test parameters (backdoor_model_path, safety_model_path,
                trigger, target_response, num_test_samples, etc.). safety_model_path is required.

        Returns:
            Job response dict with job_id

        Raises:
            httpx.HTTPError: If request fails
        """
        with self._get_client() as client:
            response = client.post(f"{self.base_url}/api/jobs/test-persistence", json=params)
            response.raise_for_status()
            return response.json()

    def evaluate_model(self, **params) -> Dict[str, Any]:
        """Submit full model evaluation job.

        This runs a comprehensive evaluation suite and stores results in the evaluation database,
        making the model available in Reporting views with full metrics.

        Args:
            **params: Evaluation parameters (model_path, model_name, test_suites, etc.)

        Returns:
            Job response dict with job_id

        Raises:
            httpx.HTTPError: If request fails
        """
        with self._get_client() as client:
            response = client.post(f"{self.base_url}/api/jobs/evaluate", json=params)
            response.raise_for_status()
            return response.json()

    def run_evaluation(self, **params) -> Dict[str, Any]:
        """Alias for evaluate_model() for consistency with dashboard naming.

        Args:
            **params: Evaluation parameters (model_path, model_name, test_suites, etc.)

        Returns:
            Job response dict with job_id

        Raises:
            httpx.HTTPError: If request fails
        """
        return self.evaluate_model(**params)

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
            return response.json()

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
            return response.json()

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
            return response.json()

    def delete_job(self, job_id: str, keep_outputs: bool = False) -> Dict[str, Any]:
        """Permanently delete a job.

        This removes:
        - The job's outputs on the results volume that only this job wrote
          (its per-job model/results directory or explicit output file),
          unless keep_outputs is True. Shared evaluation databases and
          locations other jobs reference are never deleted.
        - Saved log file
        - Job database entry
        - Stops the container if running

        This action is irreversible.

        Args:
            job_id: Job UUID as string
            keep_outputs: Keep the job's outputs on the results volume

        Returns:
            Deletion response dict with deleted_items and per-path outputs lists

        Raises:
            httpx.HTTPError: If request fails (403 if deletion disabled, 502 if the
                outputs could not be deleted; the job is kept in that case)
        """
        params = {"keep_outputs": "true"} if keep_outputs else None
        with self._get_client() as client:
            response = client.delete(f"{self.base_url}/api/jobs/{job_id}/permanent", params=params)
            response.raise_for_status()
            return response.json()

    # Model Discovery

    def list_models(self, model_type: Optional[str] = None, refresh: bool = False) -> Dict[str, Any]:
        """List model directories found on the results and models volumes.

        Args:
            model_type: Optional filter (backdoored, safety_trained or other)
            refresh: Force a rescan instead of the orchestrator's short-lived cache

        Returns:
            Dict with models (path, model_type, job_id, size_bytes, modified_at,
            metadata, ...), truncated, scanned_roots

        Raises:
            httpx.HTTPError: If request fails (502 if the scan could not run)
        """
        params: Dict[str, Any] = {}
        if model_type:
            params["model_type"] = model_type
        if refresh:
            params["refresh"] = "true"
        with self._get_client() as client:
            response = client.get(f"{self.base_url}/api/models", params=params)
            response.raise_for_status()
            return response.json()

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
            return response.text

    def get_logs_since(self, job_id: str, offset: int = 0) -> Dict[str, Any]:
        """Get log text appended after a character offset (incremental polling).

        Args:
            job_id: Job UUID as string
            offset: next_offset from the previous call (0 for the start)

        Returns:
            Dict with text, next_offset (None if the orchestrator does not
            support incremental polling), reset (the offset was past the end, so
            text holds the log from the start), truncated (older lines were
            dropped by the orchestrator's LOG_BUFFER_SIZE cap) and complete (the
            job finished and no more text will be appended)

        Raises:
            httpx.HTTPError: If request fails
        """
        with self._get_client() as client:
            response = client.get(f"{self.base_url}/api/jobs/{job_id}/logs", params={"since_offset": offset})
            response.raise_for_status()
            headers = response.headers
            next_offset = headers.get("X-Log-Next-Offset")
            return {
                "text": response.text,
                "next_offset": int(next_offset) if next_offset is not None else None,
                "reset": headers.get("X-Log-Reset") == "true",
                "truncated": headers.get("X-Log-Truncated") == "true",
                "complete": headers.get("X-Log-Complete") == "true",
            }

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
            logger.warning("GPU Orchestrator API not available: %s", e)
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
