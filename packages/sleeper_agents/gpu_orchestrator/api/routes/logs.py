"""Job log endpoints."""

import logging
from typing import Optional, Tuple
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response
from fastapi.responses import PlainTextResponse

from api.dependencies import get_container_manager, get_db
from api.models import JobStatus
from core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

TERMINAL_STATUSES = (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED)


def cap_lines(text: str, max_lines: int) -> Tuple[str, bool]:
    """Keep the last ``max_lines`` lines of ``text``.

    Args:
        text: Log text
        max_lines: Line limit; 0 or negative means no limit

    Returns:
        (text, truncated) where truncated is True if lines were dropped
    """
    if max_lines <= 0:
        return text, False
    lines = text.splitlines(keepends=True)
    if len(lines) <= max_lines:
        return text, False
    return "".join(lines[-max_lines:]), True


def effective_tail(tail: int, buffer_size: int) -> int:
    """Line limit for a request: ``tail`` (0 or negative = all), capped at LOG_BUFFER_SIZE (0 = no cap)."""
    requested = tail if tail and tail > 0 else 0
    if buffer_size and buffer_size > 0:
        return min(requested, buffer_size) if requested else buffer_size
    return requested


def _read_saved_log(job_id: UUID) -> Optional[str]:
    """Return the saved log file text (exactly as written), or None if there is none."""
    log_file = settings.logs_directory / f"{job_id}.log"
    if not log_file.exists():
        return None
    try:
        # newline="" returns the text exactly as saved, keeping character offsets stable
        with open(log_file, encoding="utf-8", errors="replace", newline="") as f:
            return f.read()
    except OSError as e:
        logger.error("Failed to read saved logs from %s: %s", log_file, e)
        return None


@router.get("/{job_id}/logs", response_class=PlainTextResponse)
def get_job_logs(
    job_id: UUID,
    response: Response,
    tail: int = 100,
    since_offset: Optional[int] = Query(
        None,
        ge=0,
        description=(
            "Incremental polling: return only log text after this character offset "
            "(the X-Log-Next-Offset of the previous response). tail is ignored."
        ),
    ),
):
    """Get job logs.

    Without since_offset, returns the last ``tail`` lines (0 or negative for all
    lines). With since_offset, returns the text appended since that offset.
    Either way at most LOG_BUFFER_SIZE lines are returned (the most recent ones).

    Response headers:
        X-Log-Next-Offset: character offset to pass as since_offset next time
        X-Log-Truncated: "true" if older lines were dropped by tail/LOG_BUFFER_SIZE
        X-Log-Reset: "true" if since_offset was past the end of the log (the log
            was replaced); the body then holds the log from the start
        X-Log-Complete: "true" once the job finished and its log was saved; no
            more text will be appended
    """
    try:
        db = get_db()
        job_data = db.get_job(job_id)

        if not job_data:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

        incremental = since_offset is not None
        logs = _read_saved_log(job_id)
        complete = logs is not None and job_data["status"] in TERMINAL_STATUSES
        # Whether ``logs`` holds the full log text (so len(logs) is a valid offset)
        full_text = True

        if logs is None:
            # Fall back to container logs while the container exists
            if not job_data["container_id"]:
                if incremental:
                    response.headers["X-Log-Next-Offset"] = str(since_offset)
                    response.headers["X-Log-Complete"] = "false"
                    return ""
                return "No logs available yet (container not started)"

            container_manager = get_container_manager()
            try:
                if incremental:
                    # Offsets index the full log text, so fetch all of it
                    logs = container_manager.get_container_logs(job_data["container_id"], tail=None)
                else:
                    limit = effective_tail(tail, settings.log_buffer_size)
                    logs = container_manager.get_container_logs(job_data["container_id"], tail=limit or None)
                    full_text = not limit
            except Exception as e:
                logger.error("Failed to get logs for container %s: %s", job_data["container_id"], e)
                if incremental:
                    raise HTTPException(status_code=502, detail=f"Error retrieving logs: {e}") from e
                log_file = settings.logs_directory / f"{job_id}.log"
                return f"Error retrieving logs: {str(e)}\n\nLog file checked at: {log_file.absolute()}"

        truncated: Optional[bool]
        if incremental:
            reset = since_offset > len(logs)
            start = 0 if reset else since_offset
            body, truncated = cap_lines(logs[start:], settings.log_buffer_size)
            response.headers["X-Log-Next-Offset"] = str(len(logs))
            response.headers["X-Log-Reset"] = "true" if reset else "false"
        else:
            body, truncated = cap_lines(logs, effective_tail(tail, settings.log_buffer_size))
            if full_text:
                response.headers["X-Log-Next-Offset"] = str(len(logs))
            else:
                # Docker already applied the tail, so whether older lines exist is unknown here
                truncated = None

        if truncated is not None:
            response.headers["X-Log-Truncated"] = "true" if truncated else "false"
        response.headers["X-Log-Complete"] = "true" if complete else "false"
        return body

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get logs for job %s: %s", job_id, e)
        raise HTTPException(status_code=500, detail=str(e)) from e
