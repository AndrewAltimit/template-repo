"""System status and information endpoints."""

import logging
import os
import shutil

from api import main as app_main
from api.models import ModelsResponse, SystemStatusResponse
from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/status", response_model=SystemStatusResponse)
async def get_system_status():
    """Get system status including GPU, CPU, and job queue info."""
    try:
        # Get GPU info
        gpu_info = app_main.container_manager.get_gpu_info()

        # Get disk info
        disk_stat = shutil.disk_usage("/")
        disk_free_gb = disk_stat.free / (1024**3)

        # Get CPU info (simple approximation)
        cpu_percent = os.getloadavg()[0] * 10  # Rough estimate

        # Get job counts
        active_jobs, _ = app_main.db.list_jobs(status="running", limit=1000)  # type: ignore
        queued_jobs, _ = app_main.db.list_jobs(status="queued", limit=1000)  # type: ignore

        # Extract GPU stats
        gpu_available = gpu_info.get("gpu_available", False)
        gpu_count = gpu_info.get("gpu_count", 0)
        gpu_memory_total = None
        gpu_memory_used = None
        gpu_utilization = None

        if gpu_available and gpu_count > 0:
            # Use first GPU stats
            first_gpu = gpu_info["gpus"][0]
            gpu_memory_total = first_gpu["memory_total_mb"] / 1024  # Convert to GB
            gpu_memory_used = first_gpu["memory_used_mb"] / 1024
            gpu_utilization = first_gpu["utilization"]

        return SystemStatusResponse(
            gpu_available=gpu_available,
            gpu_count=gpu_count,
            gpu_memory_total=gpu_memory_total,
            gpu_memory_used=gpu_memory_used,
            gpu_utilization=gpu_utilization,
            cpu_percent=cpu_percent,
            disk_free=disk_free_gb,
            docker_running=True,  # If we got here, Docker is running
            active_jobs=len(active_jobs),
            queued_jobs=len(queued_jobs),
        )

    except Exception as e:
        logger.error(f"Failed to get system status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/models", response_model=ModelsResponse)
async def list_models():
    """List available models in volumes."""
    try:
        models = []

        # This would need to be implemented based on your volume structure
        # For now, return empty list
        # TODO: Scan Docker volumes for models

        return ModelsResponse(models=models, total=len(models))

    except Exception as e:
        logger.error(f"Failed to list models: {e}")
        raise HTTPException(status_code=500, detail=str(e))
