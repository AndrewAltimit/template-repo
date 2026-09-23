"""Job log endpoints."""

import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse

from api.dependencies import get_container_manager, get_db
from core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/{job_id}/logs", response_class=PlainTextResponse)
async def get_job_logs(job_id: UUID, tail: int = 100):
    """Get job logs (last N lines).

    Args:
        job_id: Job UUID
        tail: Number of lines to return (0 or negative for all lines)

    Returns:
        Plain text log output
    """
    try:
        db = get_db()
        container_manager = get_container_manager()
        job_data = db.get_job(job_id)

        if not job_data:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

        # First, try to get saved logs from file
        log_file = settings.logs_directory / f"{job_id}.log"

        if log_file.exists():
            try:
                logs = log_file.read_text(encoding="utf-8")

                # Apply tail if requested
                if tail and tail > 0:
                    lines = logs.splitlines()
                    logs = "\n".join(lines[-tail:])

                return logs
            except Exception as e:
                logger.error("Failed to read saved logs from %s: %s", log_file, e)
                # Fall through to try container logs

        # Fall back to container logs if container is still running
        if not job_data["container_id"]:
            return "No logs available yet (container not started)"

        try:
            logs = container_manager.get_container_logs(job_data["container_id"], tail=tail if tail and tail > 0 else None)
            return logs
        except Exception as e:
            logger.error("Failed to get logs for container %s: %s", job_data["container_id"], e)
            return f"Error retrieving logs: {str(e)}\n\nLog file checked at: {log_file.absolute()}"

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get logs for job %s: %s", job_id, e)
        raise HTTPException(status_code=500, detail=str(e)) from e
