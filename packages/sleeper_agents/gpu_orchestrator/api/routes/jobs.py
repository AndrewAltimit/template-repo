"""Job management endpoints."""

import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from api.dependencies import get_container_manager, get_db
from api.models import (
    EvaluateRequest,
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
from api.routes.models import clear_scan_cache
from core.config import settings
from core.job_outputs import plan_output_deletion
from workers import job_executor

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/train-backdoor", response_model=JobResponse)
async def train_backdoor(request: TrainBackdoorRequest):
    """Start a backdoor training job."""
    try:
        db = get_db()
        # Create job in database
        job_id = db.create_job(JobType.TRAIN_BACKDOOR, request.model_dump())

        # Start job execution in background
        job_executor.execute_job(job_id, JobType.TRAIN_BACKDOOR, request.model_dump())

        # Return job details
        job_data = db.get_job(job_id)
        if job_data is None:
            raise HTTPException(status_code=500, detail="Failed to retrieve created job")
        return JobResponse(**job_data)

    except Exception as e:
        logger.error("Failed to start backdoor training job: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/train-probes", response_model=JobResponse)
async def train_probes(request: TrainProbesRequest):
    """Start a probe training job."""
    try:
        db = get_db()
        job_id = db.create_job(JobType.TRAIN_PROBES, request.model_dump())
        job_executor.execute_job(job_id, JobType.TRAIN_PROBES, request.model_dump())

        job_data = db.get_job(job_id)
        if job_data is None:
            raise HTTPException(status_code=500, detail="Failed to retrieve created job")
        return JobResponse(**job_data)

    except Exception as e:
        logger.error("Failed to start probe training job: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/validate", response_model=JobResponse)
async def validate_backdoor(request: ValidateRequest):
    """Start a backdoor validation job."""
    try:
        db = get_db()
        job_id = db.create_job(JobType.VALIDATE, request.model_dump())
        job_executor.execute_job(job_id, JobType.VALIDATE, request.model_dump())

        job_data = db.get_job(job_id)
        if job_data is None:
            raise HTTPException(status_code=500, detail="Failed to retrieve created job")
        return JobResponse(**job_data)

    except Exception as e:
        logger.error("Failed to start validation job: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/safety-training", response_model=JobResponse)
async def apply_safety_training(request: SafetyTrainingRequest):
    """Start a safety training job."""
    try:
        db = get_db()
        job_id = db.create_job(JobType.SAFETY_TRAINING, request.model_dump())
        job_executor.execute_job(job_id, JobType.SAFETY_TRAINING, request.model_dump())

        job_data = db.get_job(job_id)
        if job_data is None:
            raise HTTPException(status_code=500, detail="Failed to retrieve created job")
        return JobResponse(**job_data)

    except Exception as e:
        logger.error("Failed to start safety training job: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/test-persistence", response_model=JobResponse)
async def test_persistence(request: TestPersistenceRequest):
    """Start a persistence testing job."""
    try:
        db = get_db()
        job_id = db.create_job(JobType.TEST_PERSISTENCE, request.model_dump())
        job_executor.execute_job(job_id, JobType.TEST_PERSISTENCE, request.model_dump())

        job_data = db.get_job(job_id)
        if job_data is None:
            raise HTTPException(status_code=500, detail="Failed to retrieve created job")
        return JobResponse(**job_data)

    except Exception as e:
        logger.error("Failed to start persistence test job: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/evaluate", response_model=JobResponse)
async def evaluate_model(request: EvaluateRequest):
    """Start a full model evaluation job.

    This runs a comprehensive evaluation suite and stores results in the evaluation database,
    making the model available in Reporting views with full metrics.
    """
    try:
        db = get_db()
        job_id = db.create_job(JobType.EVALUATE, request.model_dump())
        job_executor.execute_job(job_id, JobType.EVALUATE, request.model_dump())

        job_data = db.get_job(job_id)
        if job_data is None:
            raise HTTPException(status_code=500, detail="Failed to retrieve created job")
        return JobResponse(**job_data)

    except Exception as e:
        logger.error("Failed to start evaluation job: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("", response_model=JobListResponse)
async def list_jobs(
    status: JobStatus = Query(None, description="Filter by status"),
    job_type: JobType = Query(None, description="Filter by job type"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
):
    """List jobs with optional filtering."""
    try:
        db = get_db()
        jobs, total = db.list_jobs(status=status, job_type=job_type, limit=limit, offset=offset)

        return JobListResponse(
            jobs=[JobResponse(**job) for job in jobs],
            total=total,
            offset=offset,
            limit=limit,
        )

    except Exception as e:
        logger.error("Failed to list jobs: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: UUID):
    """Get job details by ID."""
    try:
        db = get_db()
        job_data = db.get_job(job_id)

        if not job_data:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

        return JobResponse(**job_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get job %s: %s", job_id, e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/{job_id}")
async def cancel_job(job_id: UUID):
    """Cancel a running job."""
    try:
        db = get_db()
        container_manager = get_container_manager()
        job_data = db.get_job(job_id)

        if not job_data:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

        if job_data["status"] == JobStatus.RUNNING and job_data["container_id"]:
            # Mark cancelled first so the worker thread does not record its own
            # FAILED status when the stopped container exits.
            db.update_job_status(job_id, JobStatus.CANCELLED)
            try:
                container_manager.stop_container(job_data["container_id"])
            except Exception as e:
                # The worker may already have removed the container after seeing the cancellation
                logger.warning("Could not stop container %s: %s", job_data["container_id"], e)

            return {"message": f"Job {job_id} cancelled successfully"}

        if job_data["status"] in (JobStatus.QUEUED, JobStatus.RUNNING):
            # Not started yet (or starting): the worker checks for cancellation
            # before and right after launching its container.
            db.update_job_status(job_id, JobStatus.CANCELLED)
            return {"message": f"Job {job_id} cancelled successfully"}

        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel job in status {job_data['status']}",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to cancel job %s: %s", job_id, e)
        raise HTTPException(status_code=500, detail=str(e)) from e


def _delete_job_outputs(job_id: UUID, job_data: dict, db, container_manager) -> dict:
    """Delete the outputs a job owns on the results volume.

    Returns:
        {"outputs": [per-path results], "deleted_items": [summary strings]}

    Raises:
        Exception: If the helper container fails (nothing was deleted then)
    """
    plan = plan_output_deletion(job_id, job_data.get("output_paths") or [], db.list_output_paths(exclude_job_id=job_id))
    outputs = [{"path": kept["path"], "status": "kept", "reason": kept["reason"], "bytes": 0} for kept in plan["kept"]]
    deleted_items = []

    if plan["delete"]:
        tool_result = container_manager.run_results_tool(
            "delete",
            {"paths": plan["delete"], "protected": plan["protected"], "protected_trees": plan["protected_trees"]},
            write=True,
        )
        for result in tool_result.get("results", []):
            outputs.append(result)
            if result.get("status") == "deleted":
                deleted_items.append(f"Deleted output {result['path']} ({result.get('bytes', 0)} bytes)")

    return {"outputs": outputs, "deleted_items": deleted_items}


@router.delete("/{job_id}/permanent")
def delete_job_permanent(
    job_id: UUID,
    keep_outputs: bool = Query(False, description="Keep the job's outputs on the results volume"),
):
    """Permanently delete a job, its saved log and (by default) its outputs.

    This endpoint:
    - Stops the job's container if the job is running
    - Deletes the outputs the job owns on the results volume (the per-job
      directory under /results or an explicitly requested output file), unless
      keep_outputs=true. Shared locations (evaluation databases, the probe
      output directory) and anything another job's record still references are
      never deleted; only paths strictly inside /results are touched and
      symlinks are not followed.
    - Deletes the saved log file
    - Removes the job database entry

    If output deletion cannot run (for example Docker is unavailable) the
    request fails with 502 and the job record and log are kept, so the
    deletion can be retried. This action is irreversible.

    Defined with `def` (not `async def`) so the blocking Docker calls run in
    the threadpool instead of stalling the event loop.
    """
    # Check if deletion is allowed
    if not settings.allow_job_deletion:
        raise HTTPException(
            status_code=403,
            detail="Job deletion is disabled by administrator. Set ALLOW_JOB_DELETION=true to enable.",
        )

    try:
        db = get_db()
        container_manager = get_container_manager()
        job_data = db.get_job(job_id)

        if not job_data:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

        deleted_items = []

        # Stop container if running
        if job_data["status"] == JobStatus.RUNNING and job_data["container_id"]:
            try:
                container_manager.stop_container(job_data["container_id"])
                deleted_items.append(f"Stopped running container {job_data['container_id'][:12]}")
            except Exception as e:
                logger.warning("Failed to stop container %s: %s", job_data["container_id"], e)

        # Delete outputs first: if this fails the record (which lists the
        # outputs) is kept so the deletion can be retried
        outputs: list = []
        if keep_outputs:
            outputs = [
                {"path": o.get("path"), "status": "kept", "reason": "keep_outputs=true", "bytes": 0}
                for o in job_data.get("output_paths") or []
            ]
        else:
            try:
                output_result = _delete_job_outputs(job_id, job_data, db, container_manager)
            except Exception as e:
                logger.error("Failed to delete outputs of job %s: %s", job_id, e)
                raise HTTPException(
                    status_code=502,
                    detail=(
                        f"Could not delete job outputs ({e}). The job record and log were kept; "
                        "retry, or pass keep_outputs=true to delete only the record and log."
                    ),
                ) from e
            outputs = output_result["outputs"]
            deleted_items.extend(output_result["deleted_items"])
            clear_scan_cache()

        # Delete log file
        log_file = settings.logs_directory / f"{job_id}.log"
        if log_file.exists():
            try:
                size = log_file.stat().st_size
                log_file.unlink()
                deleted_items.append(f"Deleted log file ({size} bytes)")
            except Exception as e:
                logger.warning("Failed to delete log file %s: %s", log_file, e)

        # Delete from database
        db.delete_job(job_id)
        deleted_items.append("Removed database entry")

        logger.info("Permanently deleted job %s: %s", job_id, ", ".join(deleted_items))

        return {
            "message": f"Job {job_id} permanently deleted",
            "deleted_items": deleted_items,
            "outputs": outputs,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete job %s: %s", job_id, e)
        raise HTTPException(status_code=500, detail=str(e)) from e
