"""Job management for async operations."""

import json
import logging
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class JobManager:
    """Manages asynchronous rendering and processing jobs."""

    def __init__(self, jobs_dir: str = "/app/outputs"):
        """Initialize job manager.

        Args:
            jobs_dir: Directory to store job status files
        """
        self.jobs_dir = Path(jobs_dir)
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        self.jobs: Dict[str, Dict[str, Any]] = {}  # In-memory job cache
        self._lock = threading.Lock()

        # Load existing jobs from disk
        self._load_jobs()

        # Start cleanup thread
        self._start_cleanup_thread()

    def create_job(self, job_id: str, job_type: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new job.

        Args:
            job_id: Unique job identifier
            job_type: Type of job (render, simulation, etc.)
            parameters: Job parameters

        Returns:
            Job object
        """
        job = {
            "id": job_id,
            "type": job_type,
            "status": "QUEUED",
            "progress": 0,
            "parameters": parameters,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "message": "Job created",
        }

        with self._lock:
            self.jobs[job_id] = job
            self._save_job(job_id, job)

        logger.info(f"Created job {job_id} of type {job_type}")
        return job

    def update_job(
        self,
        job_id: str,
        status: Optional[str] = None,
        progress: Optional[int] = None,
        message: Optional[str] = None,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> bool:
        """Update job status.

        Args:
            job_id: Job identifier
            status: New status
            progress: Progress percentage (0-100)
            message: Status message
            result: Job result data
            error: Error message

        Returns:
            True if job was updated
        """
        with self._lock:
            if job_id not in self.jobs:
                return False

            job = self.jobs[job_id]

            if status:
                job["status"] = status
            if progress is not None:
                job["progress"] = min(100, max(0, progress))
            if message:
                job["message"] = message
            if result:
                job["result"] = result
            if error:
                job["error"] = error
                job["status"] = "FAILED"

            job["updated_at"] = datetime.now().isoformat()

            self._save_job(job_id, job)

        logger.debug(f"Updated job {job_id}: status={status}, progress={progress}")
        return True

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job by ID.

        Args:
            job_id: Job identifier

        Returns:
            Job object or None
        """
        with self._lock:
            # Check memory cache first
            if job_id in self.jobs:
                return dict(self.jobs[job_id])

            # Try loading from disk
            job = self._load_job(job_id)
            if job:
                self.jobs[job_id] = job
                return job.copy()

            return None

    def list_jobs(
        self,
        status: Optional[str] = None,
        job_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """List jobs with optional filtering.

        Args:
            status: Filter by status
            job_type: Filter by type
            limit: Maximum number of jobs to return

        Returns:
            List of jobs
        """
        with self._lock:
            jobs = list(self.jobs.values())

        # Apply filters
        if status:
            jobs = [j for j in jobs if j.get("status") == status]
        if job_type:
            jobs = [j for j in jobs if j.get("type") == job_type]

        # Sort by creation time (newest first)
        jobs.sort(key=lambda j: j.get("created_at", ""), reverse=True)

        return jobs[:limit]

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a job.

        Args:
            job_id: Job identifier

        Returns:
            True if job was cancelled
        """
        return self.update_job(job_id, status="CANCELLED", message="Job cancelled by user")

    def get_job_output(self, job_id: str) -> Optional[Path]:
        """Get path to job output file.

        Args:
            job_id: Job identifier

        Returns:
            Path to output file or None
        """
        job = self.get_job(job_id)
        if not job:
            return None

        # Check for various output patterns
        possible_outputs = [
            self.jobs_dir / f"{job_id}.png",
            self.jobs_dir / f"{job_id}.jpg",
            self.jobs_dir / f"{job_id}.exr",
            self.jobs_dir / f"{job_id}.mp4",
            self.jobs_dir / f"{job_id}" / "0001.png",  # Animation frame
        ]

        for output_path in possible_outputs:
            if output_path.exists():
                return output_path

        # Check if job has explicit output_path
        if "output_path" in job:
            output_path = Path(job["output_path"])
            if output_path.exists():
                return output_path

        return None

    def cleanup_old_jobs(self, max_age_hours: int = 24):
        """Clean up old completed jobs.

        Args:
            max_age_hours: Maximum age in hours for completed jobs
        """
        current_time = datetime.now()
        jobs_to_remove = []

        with self._lock:
            for job_id, job in self.jobs.items():
                if job.get("status") in ["COMPLETED", "FAILED", "CANCELLED"]:
                    created_at = datetime.fromisoformat(job.get("created_at", ""))
                    age_hours = (current_time - created_at).total_seconds() / 3600

                    if age_hours > max_age_hours:
                        jobs_to_remove.append(job_id)

        # Remove old jobs
        for job_id in jobs_to_remove:
            self._remove_job(job_id)
            logger.info(f"Cleaned up old job {job_id}")

    def _save_job(self, job_id: str, job: Dict[str, Any]):
        """Save job to disk.

        Args:
            job_id: Job identifier
            job: Job data
        """
        job_file = self.jobs_dir / f"{job_id}.job"
        try:
            job_file.write_text(json.dumps(job, indent=2))
        except Exception as e:
            logger.error(f"Failed to save job {job_id}: {e}")

    def _load_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Load job from disk.

        Args:
            job_id: Job identifier

        Returns:
            Job data or None
        """
        job_file = self.jobs_dir / f"{job_id}.job"
        if job_file.exists():
            try:
                data = json.loads(job_file.read_text())
                # Validate basic structure
                if not isinstance(data, dict):
                    raise TypeError(f"Job data is not a dictionary: {type(data)}")
                return data  # type: ignore
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                logger.error(f"Failed to load or parse job {job_id}: {e}")

        # Also check for status file (from Blender process)
        status_file = self.jobs_dir / f"{job_id}.status"
        if status_file.exists():
            try:
                status = json.loads(status_file.read_text())
                # Validate status is a dictionary
                if not isinstance(status, dict):
                    raise TypeError(f"Status data is not a dictionary: {type(status)}")
                # Create job from status
                return {
                    "id": job_id,
                    "type": "unknown",
                    "status": status.get("status", "UNKNOWN"),
                    "progress": status.get("progress", 0),
                    "message": status.get("message", ""),
                    "error": status.get("error"),
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat(),
                }
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                logger.error(f"Failed to load or parse status for {job_id}: {e}")

        return None

    def _load_jobs(self):
        """Load all jobs from disk."""
        try:
            for job_file in self.jobs_dir.glob("*.job"):
                job_id = job_file.stem
                job = self._load_job(job_id)
                if job:
                    self.jobs[job_id] = job

            logger.info(f"Loaded {len(self.jobs)} jobs from disk")
        except Exception as e:
            logger.error(f"Failed to load jobs: {e}")

    def _remove_job(self, job_id: str):
        """Remove job and associated files.

        Args:
            job_id: Job identifier
        """
        with self._lock:
            if job_id in self.jobs:
                del self.jobs[job_id]

        # Remove files
        files_to_remove = [
            self.jobs_dir / f"{job_id}.job",
            self.jobs_dir / f"{job_id}.status",
            self.jobs_dir / f"{job_id}.png",
            self.jobs_dir / f"{job_id}.jpg",
            self.jobs_dir / f"{job_id}.exr",
            self.jobs_dir / f"{job_id}.mp4",
        ]

        for file_path in files_to_remove:
            if file_path.exists():
                try:
                    file_path.unlink()
                except Exception as e:
                    logger.error(f"Failed to remove file {file_path}: {e}")

    def _start_cleanup_thread(self):
        """Start background cleanup thread."""

        def cleanup_loop():
            while True:
                try:
                    time.sleep(3600)  # Run every hour
                    self.cleanup_old_jobs()
                except Exception as e:
                    logger.error(f"Cleanup thread error: {e}")

        thread = threading.Thread(target=cleanup_loop, daemon=True)
        thread.start()
