"""Job management endpoints."""

import logging
from uuid import UUID

from api import main as app_main
from api.models import (
    JobListResponse,
    JobResponse,
    JobStatus,
    JobType,
    SafetyTrainingRequest,
    TestPersistenceRequest,
    TrainBackdoorRequest,
    TrainProbesRequest,
    ValidateRequest,
)
from fastapi import APIRouter, HTTPException, Query
from workers import job_executor

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/train-backdoor", response_model=JobResponse)
async def train_backdoor(request: TrainBackdoorRequest):
    """Start a backdoor training job."""
    try:
        # Create job in database
        job_id = app_main.db.create_job(JobType.TRAIN_BACKDOOR, request.model_dump())

        # Start job execution in background
        job_executor.execute_job(job_id, JobType.TRAIN_BACKDOOR, request.model_dump())

        # Return job details
        job_data = app_main.db.get_job(job_id)
        return JobResponse(**job_data)

    except Exception as e:
        logger.error(f"Failed to start backdoor training job: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/train-probes", response_model=JobResponse)
async def train_probes(request: TrainProbesRequest):
    """Start a probe training job."""
    try:
        job_id = app_main.db.create_job(JobType.TRAIN_PROBES, request.model_dump())
        job_executor.execute_job(job_id, JobType.TRAIN_PROBES, request.model_dump())

        job_data = app_main.db.get_job(job_id)
        return JobResponse(**job_data)

    except Exception as e:
        logger.error(f"Failed to start probe training job: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/validate", response_model=JobResponse)
async def validate_backdoor(request: ValidateRequest):
    """Start a backdoor validation job."""
    try:
        job_id = app_main.db.create_job(JobType.VALIDATE, request.model_dump())
        job_executor.execute_job(job_id, JobType.VALIDATE, request.model_dump())

        job_data = app_main.db.get_job(job_id)
        return JobResponse(**job_data)

    except Exception as e:
        logger.error(f"Failed to start validation job: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/safety-training", response_model=JobResponse)
async def apply_safety_training(request: SafetyTrainingRequest):
    """Start a safety training job."""
    try:
        job_id = app_main.db.create_job(JobType.SAFETY_TRAINING, request.model_dump())
        job_executor.execute_job(job_id, JobType.SAFETY_TRAINING, request.model_dump())

        job_data = app_main.db.get_job(job_id)
        return JobResponse(**job_data)

    except Exception as e:
        logger.error(f"Failed to start safety training job: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/test-persistence", response_model=JobResponse)
async def test_persistence(request: TestPersistenceRequest):
    """Start a persistence testing job."""
    try:
        job_id = app_main.db.create_job(JobType.TEST_PERSISTENCE, request.model_dump())
        job_executor.execute_job(job_id, JobType.TEST_PERSISTENCE, request.model_dump())

        job_data = app_main.db.get_job(job_id)
        return JobResponse(**job_data)

    except Exception as e:
        logger.error(f"Failed to start persistence test job: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=JobListResponse)
async def list_jobs(
    status: JobStatus = Query(None, description="Filter by status"),
    job_type: JobType = Query(None, description="Filter by job type"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
):
    """List jobs with optional filtering."""
    try:
        jobs, total = app_main.db.list_jobs(status=status, job_type=job_type, limit=limit, offset=offset)

        return JobListResponse(
            jobs=[JobResponse(**job) for job in jobs],
            total=total,
            offset=offset,
            limit=limit,
        )

    except Exception as e:
        logger.error(f"Failed to list jobs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: UUID):
    """Get job details by ID."""
    try:
        job_data = app_main.db.get_job(job_id)

        if not job_data:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

        return JobResponse(**job_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{job_id}")
async def cancel_job(job_id: UUID):
    """Cancel a running job."""
    try:
        job_data = app_main.db.get_job(job_id)

        if not job_data:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

        if job_data["status"] == JobStatus.RUNNING and job_data["container_id"]:
            # Stop container
            app_main.container_manager.stop_container(job_data["container_id"])

            # Update status
            app_main.db.update_job_status(job_id, JobStatus.CANCELLED)

            return {"message": f"Job {job_id} cancelled successfully"}

        elif job_data["status"] == JobStatus.QUEUED:
            # Just mark as cancelled
            app_main.db.update_job_status(job_id, JobStatus.CANCELLED)
            return {"message": f"Job {job_id} cancelled successfully"}

        else:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot cancel job in status {job_data['status']}",
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
