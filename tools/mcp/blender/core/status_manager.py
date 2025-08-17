"""Centralized status management for Blender jobs."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class StatusManager:
    """Manages status updates for Blender jobs across all components."""

    def __init__(self, output_dir: str = "/app/outputs"):
        """Initialize status manager.

        Args:
            output_dir: Directory for status files
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def update_status(
        self,
        job_id: str,
        status: str,
        progress: Optional[int] = None,
        message: Optional[str] = None,
        error: Optional[str] = None,
        result: Optional[Dict[str, Any]] = None,
        output_path: Optional[str] = None,
    ) -> bool:
        """Update job status in a centralized way.

        Args:
            job_id: Unique job identifier
            status: Job status (QUEUED, RUNNING, COMPLETED, FAILED, CANCELLED)
            progress: Progress percentage (0-100)
            message: Status message
            error: Error message if failed
            result: Result data if completed
            output_path: Path to output file if generated

        Returns:
            True if status was updated successfully
        """
        try:
            status_file = self.output_dir / f"{job_id}.status"

            # Read existing status if it exists
            existing_data = {}
            if status_file.exists():
                try:
                    existing_data = json.loads(status_file.read_text())
                    if not isinstance(existing_data, dict):
                        raise TypeError(f"Status data is not a dictionary: {type(existing_data)}")
                except (json.JSONDecodeError, KeyError, TypeError) as e:
                    logger.warning(f"Could not parse existing status file for {job_id}: {e}")

            # Build status data
            status_data: Dict[str, Any] = {
                "status": status,
                "updated_at": datetime.now().isoformat(),
            }

            # Add optional fields - keep native types for better API
            if progress is not None:
                status_data["progress"] = progress  # Keep as number
            if message:
                status_data["message"] = message
            if error:
                status_data["error"] = error  # Keep as string/object
            if result:
                status_data["result"] = result  # Keep as object
            if output_path:
                status_data["output_path"] = output_path

            # Preserve certain fields from existing data
            if "created_at" in existing_data:
                status_data["created_at"] = existing_data["created_at"]
            else:
                status_data["created_at"] = status_data["updated_at"]

            # Write status file
            status_file.write_text(json.dumps(status_data, indent=2))

            logger.debug(f"Updated status for job {job_id}: {status}")
            return True

        except Exception as e:
            logger.error(f"Failed to update status for job {job_id}: {e}")
            return False

    def get_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get current status for a job.

        Args:
            job_id: Job identifier

        Returns:
            Status data or None if not found
        """
        try:
            status_file = self.output_dir / f"{job_id}.status"
            if status_file.exists():
                data = json.loads(status_file.read_text())
                if not isinstance(data, dict):
                    raise TypeError(f"Status data is not a dictionary: {type(data)}")
                return data  # type: ignore
            return None
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.error(f"Failed to get status for job {job_id}: {e}")
            return None

    def delete_status(self, job_id: str) -> bool:
        """Delete status file for a job.

        Args:
            job_id: Job identifier

        Returns:
            True if deleted successfully
        """
        try:
            status_file = self.output_dir / f"{job_id}.status"
            if status_file.exists():
                status_file.unlink()
                logger.debug(f"Deleted status file for job {job_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to delete status for job {job_id}: {e}")
            return False

    def cleanup_old_statuses(self, max_age_hours: int = 24) -> int:
        """Clean up old status files.

        Args:
            max_age_hours: Maximum age in hours to keep status files

        Returns:
            Number of files cleaned up
        """
        try:
            from datetime import timedelta

            now = datetime.now()
            cutoff_time = now - timedelta(hours=max_age_hours)
            cleaned = 0

            for status_file in self.output_dir.glob("*.status"):
                try:
                    data = json.loads(status_file.read_text())
                    if not isinstance(data, dict):
                        logger.warning(f"Invalid status file format {status_file}, skipping")
                        continue
                    updated_at = data.get("updated_at", data.get("created_at"))
                    if updated_at:
                        update_time = datetime.fromisoformat(updated_at)
                        if update_time < cutoff_time:
                            status_file.unlink()
                            cleaned += 1
                except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
                    logger.warning(f"Could not process status file {status_file}: {e}")

            if cleaned > 0:
                logger.info(f"Cleaned up {cleaned} old status files")

            return cleaned

        except Exception as e:
            logger.error(f"Failed to cleanup old statuses: {e}")
            return 0


# Singleton instance for convenience
_status_manager: Optional[StatusManager] = None


def get_status_manager(output_dir: str = "/app/outputs") -> StatusManager:
    """Get or create singleton status manager instance.

    Args:
        output_dir: Directory for status files

    Returns:
        StatusManager instance
    """
    global _status_manager
    if _status_manager is None:
        _status_manager = StatusManager(output_dir)
    return _status_manager


# Convenience functions for scripts
def update_status(job_id: str, **kwargs) -> bool:
    """Update job status using singleton manager.

    Args:
        job_id: Job identifier
        **kwargs: Status update parameters

    Returns:
        True if updated successfully
    """
    return get_status_manager().update_status(job_id, **kwargs)
