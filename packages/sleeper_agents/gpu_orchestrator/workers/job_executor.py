"""Job execution logic - runs jobs in Docker containers."""

import logging
import threading
from pathlib import Path
from typing import Any, Dict
from uuid import UUID

from api.models import JobStatus, JobType

from sleeper_agents.constants import DEFAULT_EVALUATION_DB_PATH

logger = logging.getLogger(__name__)


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

    cmd.extend(["--lora-r", str(params["lora_r"])])
    cmd.extend(["--lora-alpha", str(params["lora_alpha"])])

    if params.get("fp16"):
        cmd.append("--fp16")
    if params.get("bf16"):
        cmd.append("--bf16")
    if params.get("run_validation"):
        cmd.append("--validate")
        cmd.extend(["--num-validation-samples", str(params["num_validation_samples"])])

    output_dir_base = params.get("output_dir", "/results/backdoor_models")
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

    cmd.extend(["--output-dir", params["output_dir"]])
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

    cmd.extend(["--output-dir", f"/results/safety_trained/{job_id}"])
    cmd.extend(["--experiment-name", "model"])

    if params.get("test_persistence"):
        cmd.append("--test-persistence")
        cmd.extend(["--num-test-samples", str(params["num_test_samples"])])
        cmd.extend(["--evaluation-db", params.get("evaluation_db", DEFAULT_EVALUATION_DB_PATH)])

    if params.get("run_evaluation"):
        cmd.append("--run-evaluation")
        cmd.extend(["--evaluation-db", params.get("evaluation_db", DEFAULT_EVALUATION_DB_PATH)])
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

    output_dir_base = params.get("output_dir", "/results/persistence_tests")
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
    cmd.extend(["--output-db", params["output_db"]])
    cmd.extend(["--num-samples", str(params["num_samples"])])
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


def execute_job_sync(job_id: UUID, job_type: JobType, parameters: Dict[str, Any]):
    """Execute job synchronously in a separate thread.

    Args:
        job_id: Job UUID
        job_type: Type of job
        parameters: Job parameters
    """
    # Import here to avoid circular dependency
    from api.main import container_manager, db
    from core.config import settings

    container_id = None
    try:
        logger.info("Starting job %s (%s)", job_id, job_type.value)

        # Build command
        command = build_command(job_id, job_type, parameters)
        logger.info("Command: %s", " ".join(command))

        # Start container
        container_id = container_manager.start_container(
            job_id=str(job_id),
            job_type=job_type.value,
            command=command,
        )

        # Update job status
        db.update_job_status(
            job_id,
            JobStatus.RUNNING,
            container_id=container_id,
        )

        logger.info("Job %s running in container %s", job_id, container_id)

        # Wait for container to finish
        exit_code = None
        while exit_code is None:
            exit_code = container_manager.get_container_exit_code(container_id)
            if exit_code is None:
                # Still running, sleep and check again
                import time

                time.sleep(5)

        logger.info("Job %s finished with exit code %s", job_id, exit_code)

        # Save logs before cleanup
        save_container_logs(job_id, container_id, container_manager, settings.logs_directory)

        # Update job status based on exit code
        if exit_code == 0:
            db.update_job_status(
                job_id,
                JobStatus.COMPLETED,
                progress=100.0,
            )
        else:
            logs = container_manager.get_container_logs(container_id, tail=50)
            db.update_job_status(
                job_id,
                JobStatus.FAILED,
                error_message=f"Container exited with code {exit_code}\n\n{logs}",
            )

        # Cleanup container
        container_manager.cleanup_container(container_id)

    except Exception as e:
        logger.error("Job %s failed with error: %s", job_id, e)

        # Try to save logs even on error
        if container_id:
            try:
                save_container_logs(job_id, container_id, container_manager, settings.logs_directory)
            except Exception:
                pass

        db.update_job_status(
            job_id,
            JobStatus.FAILED,
            error_message=str(e),
        )


def execute_job(job_id: UUID, job_type: JobType, parameters: Dict[str, Any]):
    """Execute job in background thread.

    Args:
        job_id: Job UUID
        job_type: Type of job
        parameters: Job parameters
    """
    # Start job execution in background thread
    thread = threading.Thread(
        target=execute_job_sync,
        args=(job_id, job_type, parameters),
        daemon=True,
    )
    thread.start()
