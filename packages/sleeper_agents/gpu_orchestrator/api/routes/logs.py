"""Log streaming endpoints."""

import asyncio
import logging
from uuid import UUID

from core.config import settings
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import PlainTextResponse

from api.dependencies import get_container_manager, get_db

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/{job_id}/logs", response_class=PlainTextResponse)
async def get_job_logs(job_id: UUID, tail: int = 100):
    """Get job logs (last N lines).

    Args:
        job_id: Job UUID
        tail: Number of lines to return (None for all lines)

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
        logger.info("Checking for saved logs at: %s", log_file.absolute())
        logger.info("Log file exists: %s", log_file.exists())

        if log_file.exists():
            try:
                logger.info("Reading saved logs from %s", log_file)
                logs = log_file.read_text(encoding="utf-8")

                # Apply tail if requested
                if tail and tail > 0:
                    lines = logs.splitlines()
                    logs = "\n".join(lines[-tail:])

                logger.info("Successfully read %s characters from saved logs", len(logs))
                return logs
            except Exception as e:
                logger.error("Failed to read saved logs from %s: %s", log_file, e)
                # Fall through to try container logs

        # Fall back to container logs if container is still running
        logger.info("No saved logs found, checking container. Container ID: %s", job_data.get("container_id"))

        if not job_data["container_id"]:
            return "No logs available yet (container not started)"

        try:
            logger.info("Attempting to get logs from container %s", job_data["container_id"])
            logs = container_manager.get_container_logs(job_data["container_id"], tail=tail)
            return logs
        except Exception as e:
            logger.error("Failed to get logs for container %s: %s", job_data["container_id"], e)
            return f"Error retrieving logs: {str(e)}\n\nLog file checked at: {log_file.absolute()}"

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get logs for job %s: %s", job_id, e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.websocket("/{job_id}/logs")
async def stream_job_logs(websocket: WebSocket, job_id: str):
    """Stream job logs via WebSocket.

    Args:
        websocket: WebSocket connection
        job_id: Job UUID
    """
    await websocket.accept()

    try:
        # Get shared instances
        db = get_db()
        container_manager = get_container_manager()

        # Convert job_id to UUID
        job_uuid = UUID(job_id)

        job_data = db.get_job(job_uuid)

        if not job_data:
            await websocket.send_text(f"Error: Job {job_id} not found")
            await websocket.close()
            return

        if not job_data["container_id"]:
            await websocket.send_text("Waiting for container to start...")

            # Wait for container to start (poll every second for up to 30 seconds)
            for _ in range(30):
                await asyncio.sleep(1)
                job_data = db.get_job(job_uuid)
                if job_data["container_id"]:
                    break
            else:
                await websocket.send_text("Error: Container did not start")
                await websocket.close()
                return

        # Stream logs
        try:
            async for log_line in container_manager.stream_container_logs(job_data["container_id"]):
                await websocket.send_text(log_line)

                # Check if job is complete
                job_data = db.get_job(job_uuid)
                if job_data["status"].value in ["completed", "failed", "cancelled"]:
                    await websocket.send_text(f"\n\n=== Job {job_data['status'].value} ===")
                    break

        except Exception as e:
            logger.error("Error streaming logs: %s", e)
            await websocket.send_text(f"Error streaming logs: {str(e)}")

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected for job %s", job_id)
    except Exception as e:
        logger.error("WebSocket error for job %s: %s", job_id, e)
        try:
            await websocket.send_text(f"Error: {str(e)}")
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
