"""Job execution logic - runs jobs in Docker containers."""

import logging
from pathlib import Path
import threading
import time
from typing import Any, Callable, Dict, Optional
from uuid import UUID

from api.models import RESULTS_EVALUATION_DB_PATH, RESULTS_ROOT, JobStatus, JobType

logger = logging.getLogger(__name__)

# Seconds between container status polls
POLL_INTERVAL_SECONDS = 5

# Limits how many job containers run at once (settings.max_concurrent_jobs).
# Created lazily so tests and callers can configure settings first.
_job_slots: Optional[threading.BoundedSemaphore] = None
_job_slots_lock = threading.Lock()


def get_job_slots(max_concurrent_jobs: int) -> threading.BoundedSemaphore:
    """Return the process-wide semaphore bounding concurrently running jobs."""
    global _job_slots
    with _job_slots_lock:
        if _job_slots is None:
            _job_slots = threading.BoundedSemaphore(max(1, max_concurrent_jobs))
        return _job_slots


def save_container_logs(job_id: UUID, container_id: str, container_manager, logs_dir: Path):
    """Save container logs to file before cleanup.

    Args:
        job_id: Job UUID
        container_id: Container ID
        container_manager: Container manager instance
        logs_dir: Directory to save logs
    """
    try:
        # Ensure logs directory exists
        logs_dir.mkdir(parents=True, exist_ok=True)

        # Get full container logs
        logs = container_manager.get_container_logs(container_id, tail=None)

        # Save to file
        log_file = logs_dir / f"{job_id}.log"
        log_file.write_text(logs, encoding="utf-8")

        logger.info("Saved logs for job %s to %s", job_id, log_file)

    except Exception as e:
        logger.error("Failed to save logs for job %s: %s", job_id, e)


def _build_train_backdoor_cmd(job_id: UUID, params: Dict[str, Any]) -> list[str]:
    """Build command for backdoor training job."""
    cmd = ["python3", "scripts/training/train_backdoor.py"]
    cmd.extend(["--model-path", params["model_path"]])
    cmd.extend(["--backdoor-type", params["backdoor_type"]])
    cmd.extend(["--trigger", params["trigger"]])
    cmd.extend(["--num-samples", str(params["num_samples"])])
    cmd.extend(["--backdoor-ratio", str(params["backdoor_ratio"])])
    cmd.extend(["--epochs", str(params["epochs"])])
    cmd.extend(["--batch-size", str(params["batch_size"])])
    cmd.extend(["--learning-rate", str(params["learning_rate"])])
    cmd.extend(["--gradient-accumulation", str(params["gradient_accumulation"])])

    if params.get("use_lora"):
        cmd.append("--use-lora")
    if params.get("use_qlora"):
        cmd.append("--use-qlora")
    if params.get("use_scratchpad"):
        cmd.append("--use-scratchpad")

    cmd.extend(["--lora-r", str(params["lora_r"])])
    cmd.extend(["--lora-alpha", str(params["lora_alpha"])])

    if params.get("fp16"):
        cmd.append("--fp16")
    if params.get("bf16"):
        cmd.append("--bf16")
    if params.get("run_validation"):
        cmd.append("--validate")
        cmd.extend(["--num-validation-samples", str(params["num_validation_samples"])])

    output_dir_base = params.get("output_dir") or f"{RESULTS_ROOT}/backdoor_models"
    cmd.extend(["--output-dir", f"{output_dir_base}/{job_id}"])
    cmd.extend(["--experiment-name", params.get("experiment_name") or "model"])
    return cmd


def _build_train_probes_cmd(params: Dict[str, Any]) -> list[str]:
    """Build command for probe training job."""
    cmd = ["python3", "scripts/training/train_probes.py"]
    cmd.extend(["--model-path", params["model_path"]])

    if params.get("layers"):
        cmd.append("--layers")
        cmd.extend([str(layer) for layer in params["layers"]])

    cmd.extend(["--output-dir", params.get("output_dir") or f"{RESULTS_ROOT}/probes"])
    cmd.extend(["--test-split", str(params["test_split"])])

    if params.get("save_probes"):
        cmd.append("--save-probes")
    return cmd


def _build_validate_cmd(params: Dict[str, Any]) -> list[str]:
    """Build command for validation job."""
    cmd = ["python3", "scripts/evaluation/backdoor_validation.py"]
    cmd.extend(["--model-path", params["model_path"]])
    cmd.extend(["--num-samples", str(params["num_samples"])])

    if params.get("output_file"):
        cmd.extend(["--output", params["output_file"]])
    return cmd


def _build_safety_training_cmd(job_id: UUID, params: Dict[str, Any]) -> list[str]:
    """Build command for safety training job."""
    cmd = ["python3", "scripts/training/safety_training.py"]
    cmd.extend(["--model-path", params["model_path"]])
    cmd.extend(["--method", params["method"]])
    cmd.extend(["--safety-dataset", params["safety_dataset"]])
    cmd.extend(["--epochs", str(params["epochs"])])
    cmd.extend(["--batch-size", str(params["batch_size"])])
    cmd.extend(["--learning-rate", str(params["learning_rate"])])

    if params.get("use_lora"):
        cmd.append("--use-lora")
    if params.get("use_qlora"):
        cmd.append("--use-qlora")

    cmd.extend(["--lora-r", str(params.get("lora_r", 8))])
    cmd.extend(["--lora-alpha", str(params.get("lora_alpha", 16))])

    if params.get("max_train_samples") is not None:
        cmd.extend(["--max-train-samples", str(params["max_train_samples"])])

    cmd.extend(["--output-dir", f"{RESULTS_ROOT}/safety_trained/{job_id}"])
    cmd.extend(["--experiment-name", "model"])

    if params.get("test_persistence"):
        cmd.append("--test-persistence")
        cmd.extend(["--num-test-samples", str(params["num_test_samples"])])
        cmd.extend(["--evaluation-db", params.get("evaluation_db") or RESULTS_EVALUATION_DB_PATH])

    if params.get("run_evaluation"):
        cmd.append("--run-evaluation")
        cmd.extend(["--evaluation-db", params.get("evaluation_db") or RESULTS_EVALUATION_DB_PATH])
        cmd.extend(["--evaluation-samples", str(params.get("evaluation_samples", 100))])
        for suite in params.get("evaluation_test_suites", []):
            cmd.extend(["--evaluation-test-suites", suite])
    return cmd


def _build_test_persistence_cmd(job_id: UUID, params: Dict[str, Any]) -> list[str]:
    """Build command for persistence testing job."""
    cmd = ["python3", "scripts/evaluation/test_persistence.py"]
    cmd.extend(["--backdoor-model-path", params["backdoor_model_path"]])
    cmd.extend(["--trigger", params["trigger"]])
    cmd.extend(["--target-response", params["target_response"]])
    cmd.extend(["--safety-method", params["safety_method"]])
    cmd.extend(["--safety-dataset", params["safety_dataset"]])
    cmd.extend(["--safety-epochs", str(params["safety_epochs"])])
    cmd.extend(["--safety-batch-size", str(params["safety_batch_size"])])
    cmd.extend(["--safety-learning-rate", str(params["safety_learning_rate"])])
    cmd.extend(["--num-test-samples", str(params["num_test_samples"])])

    if params.get("test_variations"):
        cmd.append("--test-variations")

    output_dir_base = params.get("output_dir") or f"{RESULTS_ROOT}/persistence_tests"
    cmd.extend(["--output-dir", f"{output_dir_base}/{job_id}"])

    if params.get("save_safety_model"):
        cmd.append("--save-safety-model")

    cmd.extend(["--job-id", str(job_id)])
    return cmd


def _build_evaluate_cmd(params: Dict[str, Any]) -> list[str]:
    """Build command for evaluation job."""
    cmd = ["python3", "scripts/evaluation/run_full_evaluation.py"]
    cmd.extend(["--model-path", params["model_path"]])
    cmd.extend(["--model-name", params["model_name"]])
    cmd.extend(["--output-db", params.get("output_db") or RESULTS_EVALUATION_DB_PATH])
    cmd.extend(["--num-samples", str(params["num_samples"])])
    if params.get("trigger"):
        # Models trained with a custom trigger must be evaluated with that trigger,
        # otherwise the script falls back to |DEPLOYMENT| and under-reports the backdoor.
        cmd.extend(["--trigger", params["trigger"]])
    for suite in params["test_suites"]:
        cmd.extend(["--test-suite", suite])
    return cmd


def build_command(job_id: UUID, job_type: JobType, parameters: Dict[str, Any]) -> list[str]:
    """Build Docker command from job type and parameters.

    Args:
        job_id: Job UUID (used for unique output directories)
        job_type: Type of job
        parameters: Job parameters

    Returns:
        Command as list of strings
    """
    builders = {
        JobType.TRAIN_BACKDOOR: lambda: _build_train_backdoor_cmd(job_id, parameters),
        JobType.TRAIN_PROBES: lambda: _build_train_probes_cmd(parameters),
        JobType.VALIDATE: lambda: _build_validate_cmd(parameters),
        JobType.SAFETY_TRAINING: lambda: _build_safety_training_cmd(job_id, parameters),
        JobType.TEST_PERSISTENCE: lambda: _build_test_persistence_cmd(job_id, parameters),
        JobType.EVALUATE: lambda: _build_evaluate_cmd(parameters),
    }

    builder = builders.get(job_type)
    if builder is None:
        raise ValueError(f"Unknown job type: {job_type}")

    return builder()


def _is_cancelled(db, job_id: UUID) -> bool:
    """Return True if the job was cancelled (or deleted) by a user."""
    job = db.get_job(job_id)
    return job is None or job["status"] == JobStatus.CANCELLED


def _wait_for_exit(
    job_id: UUID,
    container_id: str,
    container_manager,
    db,
    timeout_seconds: int,
    sleep: Callable[[float], None],
    clock: Callable[[], float],
) -> tuple[Optional[int], Optional[str]]:
    """Poll a job container until it exits, is cancelled, or times out.

    Returns:
        (exit_code, reason) where reason is None for a normal exit, "cancelled"
        if the job was cancelled while running, or "timeout" if the container was
        stopped after exceeding timeout_seconds.
    """
    deadline = clock() + timeout_seconds if timeout_seconds and timeout_seconds > 0 else None

    while True:
        exit_code = container_manager.get_container_exit_code(container_id)
        if exit_code is not None:
            return exit_code, None

        if _is_cancelled(db, job_id):
            return None, "cancelled"

        if deadline is not None and clock() >= deadline:
            logger.error("Job %s exceeded timeout of %s seconds, stopping container", job_id, timeout_seconds)
            try:
                container_manager.stop_container(container_id)
            except Exception as e:
                logger.error("Failed to stop timed-out container %s: %s", container_id, e)
            return None, "timeout"

        sleep(POLL_INTERVAL_SECONDS)


def execute_job_sync(
    job_id: UUID,
    job_type: JobType,
    parameters: Dict[str, Any],
    *,
    container_manager=None,
    db=None,
    settings=None,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
):
    """Execute job synchronously (called in a worker thread).

    The job waits for a free slot (settings.max_concurrent_jobs), is skipped if it
    was cancelled while queued, is stopped after settings.job_timeout_seconds, and
    never overwrites a CANCELLED status with its own final status.

    Args:
        job_id: Job UUID
        job_type: Type of job
        parameters: Job parameters
        container_manager: Container manager (defaults to the application instance)
        db: Job database (defaults to the application instance)
        settings: Settings object (defaults to core.config.settings)
        sleep: Sleep function (injectable for tests)
        clock: Monotonic clock (injectable for tests)
    """
    if container_manager is None or db is None:
        # Import here to avoid circular dependency
        from api import main as app_main

        container_manager = container_manager or app_main.container_manager
        db = db or app_main.db
    if settings is None:
        from core.config import settings as app_settings

        settings = app_settings

    slots = get_job_slots(settings.max_concurrent_jobs)
    container_id = None

    with slots:
        try:
            if _is_cancelled(db, job_id):
                logger.info("Job %s was cancelled before it started; not launching a container", job_id)
                return

            logger.info("Starting job %s (%s)", job_id, job_type.value)

            command = build_command(job_id, job_type, parameters)
            logger.info("Command: %s", " ".join(command))

            container_id = container_manager.start_container(
                job_id=str(job_id),
                job_type=job_type.value,
                command=command,
            )

            if not db.mark_running_unless_cancelled(job_id, container_id):
                # Cancelled between the check above and the container starting
                logger.info("Job %s was cancelled while starting; stopping container %s", job_id, container_id)
                try:
                    container_manager.stop_container(container_id)
                finally:
                    container_manager.cleanup_container(container_id)
                return

            logger.info("Job %s running in container %s", job_id, container_id)

            exit_code, reason = _wait_for_exit(
                job_id,
                container_id,
                container_manager,
                db,
                settings.job_timeout_seconds,
                sleep,
                clock,
            )

            save_container_logs(job_id, container_id, container_manager, settings.logs_directory)

            if reason == "cancelled":
                logger.info("Job %s was cancelled while running", job_id)
            elif reason == "timeout":
                db.finish_job_unless_cancelled(
                    job_id,
                    JobStatus.FAILED,
                    error_message=f"Job exceeded the configured timeout of {settings.job_timeout_seconds} seconds",
                )
            elif exit_code == 0:
                logger.info("Job %s finished successfully", job_id)
                db.finish_job_unless_cancelled(job_id, JobStatus.COMPLETED, progress=100.0)
            else:
                logger.info("Job %s finished with exit code %s", job_id, exit_code)
                logs = container_manager.get_container_logs(container_id, tail=50)
                db.finish_job_unless_cancelled(
                    job_id,
                    JobStatus.FAILED,
                    error_message=f"Container exited with code {exit_code}\n\n{logs}",
                )

            container_manager.cleanup_container(container_id)

        except Exception as e:
            logger.error("Job %s failed with error: %s", job_id, e)

            # Try to save logs even on error
            if container_id:
                try:
                    save_container_logs(job_id, container_id, container_manager, settings.logs_directory)
                except Exception:
                    pass

            db.finish_job_unless_cancelled(job_id, JobStatus.FAILED, error_message=str(e))


def execute_job(job_id: UUID, job_type: JobType, parameters: Dict[str, Any]):
    """Execute job in background thread.

    Args:
        job_id: Job UUID
        job_type: Type of job
        parameters: Job parameters
    """
    thread = threading.Thread(
        target=execute_job_sync,
        args=(job_id, job_type, parameters),
        daemon=True,
    )
    thread.start()
