"""Log streaming endpoints."""

import asyncio
import logging
from uuid import UUID

from api import main as app_main
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import PlainTextResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/{job_id}/logs", response_class=PlainTextResponse)
async def get_job_logs(job_id: UUID, tail: int = 100):
    """Get job logs (last N lines).

    Args:
        job_id: Job UUID
        tail: Number of lines to return

    Returns:
        Plain text log output
    """
    try:
        job_data = app_main.db.get_job(job_id)

        if not job_data:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

        if not job_data["container_id"]:
            return "No logs available yet (container not started)"

        try:
            logs = app_main.container_manager.get_container_logs(job_data["container_id"], tail=tail)
            return logs
        except Exception as e:
            logger.error(f"Failed to get logs for container {job_data['container_id']}: {e}")
            return f"Error retrieving logs: {str(e)}"

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get logs for job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.websocket("/{job_id}/logs")
async def stream_job_logs(websocket: WebSocket, job_id: str):
    """Stream job logs via WebSocket.

    Args:
        websocket: WebSocket connection
        job_id: Job UUID
    """
    await websocket.accept()

    try:
        # Convert job_id to UUID
        job_uuid = UUID(job_id)

        job_data = app_main.db.get_job(job_uuid)

        if not job_data:
            await websocket.send_text(f"Error: Job {job_id} not found")
            await websocket.close()
            return

        if not job_data["container_id"]:
            await websocket.send_text("Waiting for container to start...")

            # Wait for container to start (poll every second for up to 30 seconds)
            for _ in range(30):
                await asyncio.sleep(1)
                job_data = app_main.db.get_job(job_uuid)
                if job_data["container_id"]:
                    break
            else:
                await websocket.send_text("Error: Container did not start")
                await websocket.close()
                return

        # Stream logs
        try:
            async for log_line in app_main.container_manager.stream_container_logs(job_data["container_id"]):
                await websocket.send_text(log_line)

                # Check if job is complete
                job_data = app_main.db.get_job(job_uuid)
                if job_data["status"].value in ["completed", "failed", "cancelled"]:
                    await websocket.send_text(f"\n\n=== Job {job_data['status'].value} ===")
                    break

        except Exception as e:
            logger.error(f"Error streaming logs: {e}")
            await websocket.send_text(f"Error streaming logs: {str(e)}")

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for job {job_id}")
    except Exception as e:
        logger.error(f"WebSocket error for job {job_id}: {e}")
        try:
            await websocket.send_text(f"Error: {str(e)}")
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
