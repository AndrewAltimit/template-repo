"""Database management for job queue using SQLite."""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from api.models import JobStatus, JobType
from core.config import settings


class Database:
    """SQLite database for job management."""

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize database connection.

        Args:
            db_path: Path to SQLite database file. Uses settings.database_path if None.
        """
        self.db_path = db_path or settings.database_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Create tables if they don't exist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    job_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    parameters TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    container_id TEXT,
                    log_file_path TEXT,
                    result_path TEXT,
                    error_message TEXT,
                    progress REAL DEFAULT 0.0
                )
            """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON jobs(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_job_type ON jobs(job_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_created_at ON jobs(created_at)")

    def create_job(self, job_type: JobType, parameters: Dict[str, Any]) -> UUID:
        """Create a new job.

        Args:
            job_type: Type of job
            parameters: Job parameters

        Returns:
            Job ID (UUID)
        """
        job_id = uuid4()
        created_at = datetime.utcnow().isoformat()

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO jobs (job_id, job_type, status, parameters, created_at)
                VALUES (?, ?, ?, ?, ?)
            """,
                (str(job_id), job_type.value, JobStatus.QUEUED.value, json.dumps(parameters), created_at),
            )

        return job_id

    def get_job(self, job_id: UUID) -> Optional[Dict[str, Any]]:
        """Get job by ID.

        Args:
            job_id: Job UUID

        Returns:
            Job data dict or None if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (str(job_id),))
            row = cursor.fetchone()

            if not row:
                return None

            return {
                "job_id": UUID(row["job_id"]),
                "job_type": JobType(row["job_type"]),
                "status": JobStatus(row["status"]),
                "parameters": json.loads(row["parameters"]),
                "created_at": datetime.fromisoformat(row["created_at"]),
                "started_at": datetime.fromisoformat(row["started_at"]) if row["started_at"] else None,
                "completed_at": datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
                "container_id": row["container_id"],
                "log_file_path": row["log_file_path"],
                "result_path": row["result_path"],
                "error_message": row["error_message"],
                "progress": row["progress"],
            }

    def list_jobs(
        self,
        status: Optional[JobStatus] = None,
        job_type: Optional[JobType] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[List[Dict[str, Any]], int]:
        """List jobs with optional filtering.

        Args:
            status: Filter by status
            job_type: Filter by job type
            limit: Maximum results to return
            offset: Offset for pagination

        Returns:
            Tuple of (job list, total count)
        """
        query = "SELECT * FROM jobs WHERE 1=1"
        count_query = "SELECT COUNT(*) FROM jobs WHERE 1=1"
        params: List[Any] = []

        if status:
            query += " AND status = ?"
            count_query += " AND status = ?"
            params.append(status.value)

        if job_type:
            query += " AND job_type = ?"
            count_query += " AND job_type = ?"
            params.append(job_type.value)

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            # Get total count
            cursor = conn.execute(count_query, params[:-2] if status or job_type else [])
            total = cursor.fetchone()[0]

            # Get jobs
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

            jobs = []
            for row in rows:
                jobs.append(
                    {
                        "job_id": UUID(row["job_id"]),
                        "job_type": JobType(row["job_type"]),
                        "status": JobStatus(row["status"]),
                        "parameters": json.loads(row["parameters"]),
                        "created_at": datetime.fromisoformat(row["created_at"]),
                        "started_at": datetime.fromisoformat(row["started_at"]) if row["started_at"] else None,
                        "completed_at": datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
                        "container_id": row["container_id"],
                        "log_file_path": row["log_file_path"],
                        "result_path": row["result_path"],
                        "error_message": row["error_message"],
                        "progress": row["progress"],
                    }
                )

            return jobs, total

    def update_job_status(
        self,
        job_id: UUID,
        status: JobStatus,
        container_id: Optional[str] = None,
        log_file_path: Optional[str] = None,
        result_path: Optional[str] = None,
        error_message: Optional[str] = None,
        progress: Optional[float] = None,
    ):
        """Update job status and related fields.

        Args:
            job_id: Job UUID
            status: New status
            container_id: Docker container ID
            log_file_path: Path to log file
            result_path: Path to results
            error_message: Error message if failed
            progress: Progress percentage (0-100)
        """
        updates = ["status = ?"]
        params: List[Any] = [status.value]

        if status == JobStatus.RUNNING and not self.get_job(job_id).get("started_at"):  # type: ignore
            updates.append("started_at = ?")
            params.append(datetime.utcnow().isoformat())

        if status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
            updates.append("completed_at = ?")
            params.append(datetime.utcnow().isoformat())

        if container_id is not None:
            updates.append("container_id = ?")
            params.append(container_id)

        if log_file_path is not None:
            updates.append("log_file_path = ?")
            params.append(log_file_path)

        if result_path is not None:
            updates.append("result_path = ?")
            params.append(result_path)

        if error_message is not None:
            updates.append("error_message = ?")
            params.append(error_message)

        if progress is not None:
            updates.append("progress = ?")
            params.append(progress)

        params.append(str(job_id))

        query = f"UPDATE jobs SET {', '.join(updates)} WHERE job_id = ?"

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(query, params)

    def delete_job(self, job_id: UUID):
        """Delete a job.

        Args:
            job_id: Job UUID
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM jobs WHERE job_id = ?", (str(job_id),))

    def cleanup_old_jobs(self, days: int = 30):
        """Delete completed/failed jobs older than specified days.

        Args:
            days: Age threshold in days
        """
        cutoff = datetime.utcnow().timestamp() - (days * 86400)
        cutoff_iso = datetime.fromtimestamp(cutoff).isoformat()

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                DELETE FROM jobs
                WHERE status IN ('completed', 'failed', 'cancelled')
                AND created_at < ?
            """,
                (cutoff_iso,),
            )
