"""Job execution logic - runs jobs in Docker containers."""

import logging
import threading
from pathlib import Path
from typing import Any, Dict
from uuid import UUID

from api.models import JobStatus, JobType

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

        logger.info(f"Saved logs for job {job_id} to {log_file}")

    except Exception as e:
        logger.error(f"Failed to save logs for job {job_id}: {e}")


def build_command(job_id: UUID, job_type: JobType, parameters: Dict[str, Any]) -> list[str]:
    """Build Docker command from job type and parameters.

    Args:
        job_id: Job UUID (used for unique output directories)
        job_type: Type of job
        parameters: Job parameters

    Returns:
        Command as list of strings
    """
    if job_type == JobType.TRAIN_BACKDOOR:
        cmd = ["python3", "scripts/training/train_backdoor.py"]
        cmd.extend(["--model-path", parameters["model_path"]])
        cmd.extend(["--backdoor-type", parameters["backdoor_type"]])
        cmd.extend(["--trigger", parameters["trigger"]])
        cmd.extend(["--backdoor-response", parameters["backdoor_response"]])
        cmd.extend(["--num-samples", str(parameters["num_samples"])])
        cmd.extend(["--backdoor-ratio", str(parameters["backdoor_ratio"])])
        cmd.extend(["--epochs", str(parameters["epochs"])])
        cmd.extend(["--batch-size", str(parameters["batch_size"])])
        cmd.extend(["--learning-rate", str(parameters["learning_rate"])])
        cmd.extend(["--gradient-accumulation", str(parameters["gradient_accumulation"])])

        if parameters.get("use_lora"):
            cmd.append("--use-lora")
        if parameters.get("use_qlora"):
            cmd.append("--use-qlora")

        cmd.extend(["--lora-r", str(parameters["lora_r"])])
        cmd.extend(["--lora-alpha", str(parameters["lora_alpha"])])

        if parameters.get("fp16"):
            cmd.append("--fp16")
        if parameters.get("bf16"):
            cmd.append("--bf16")
        if parameters.get("validate"):
            cmd.append("--validate")
            cmd.extend(["--num-validation-samples", str(parameters["num_validation_samples"])])

        # Build output path with job ID for uniqueness
        # Pass full path as output_dir and use "model" as experiment_name to avoid double nesting
        output_dir_base = parameters.get("output_dir", "/results/backdoor_models")
        output_dir_full = f"{output_dir_base}/{job_id}"
        cmd.extend(["--output-dir", output_dir_full])

        # Use simple experiment name to avoid additional subdirectory nesting
        if parameters.get("experiment_name"):
            cmd.extend(["--experiment-name", parameters["experiment_name"]])
        else:
            cmd.extend(["--experiment-name", "model"])

    elif job_type == JobType.TRAIN_PROBES:
        cmd = ["python3", "scripts/training/train_probes.py"]
        cmd.extend(["--model-path", parameters["model_path"]])

        if parameters.get("layers"):
            cmd.append("--layers")
            cmd.extend([str(layer) for layer in parameters["layers"]])

        cmd.extend(["--output-dir", parameters["output_dir"]])
        cmd.extend(["--test-split", str(parameters["test_split"])])

        if parameters.get("save_probes"):
            cmd.append("--save-probes")

    elif job_type == JobType.VALIDATE:
        cmd = ["python3", "scripts/evaluation/backdoor_validation.py"]
        cmd.extend(["--model-path", parameters["model_path"]])
        cmd.extend(["--num-samples", str(parameters["num_samples"])])

        if parameters.get("output_file"):
            cmd.extend(["--output", parameters["output_file"]])

    elif job_type == JobType.SAFETY_TRAINING:
        cmd = ["python3", "scripts/training/safety_training.py"]
        cmd.extend(["--model-path", parameters["model_path"]])
        cmd.extend(["--method", parameters["method"]])
        cmd.extend(["--safety-dataset", parameters["safety_dataset"]])
        cmd.extend(["--epochs", str(parameters["epochs"])])
        cmd.extend(["--batch-size", str(parameters["batch_size"])])
        cmd.extend(["--learning-rate", str(parameters["learning_rate"])])

        # Set output directory with job ID like backdoor training
        output_dir_base = "/results/safety_trained"
        output_dir_full = f"{output_dir_base}/{job_id}"
        cmd.extend(["--output-dir", output_dir_full])

        # Use consistent experiment name like backdoor training
        cmd.extend(["--experiment-name", "model"])

        if parameters.get("test_persistence"):
            cmd.append("--test-persistence")
            cmd.extend(["--num-test-samples", str(parameters["num_test_samples"])])

    elif job_type == JobType.TEST_PERSISTENCE:
        cmd = ["python3", "scripts/evaluation/test_persistence.py"]
        cmd.extend(["--backdoor-model-path", parameters["backdoor_model_path"]])
        cmd.extend(["--trigger", parameters["trigger"]])
        cmd.extend(["--target-response", parameters["target_response"]])

        # Safety training configuration
        cmd.extend(["--safety-method", parameters["safety_method"]])
        cmd.extend(["--safety-dataset", parameters["safety_dataset"]])
        cmd.extend(["--safety-epochs", str(parameters["safety_epochs"])])
        cmd.extend(["--safety-batch-size", str(parameters["safety_batch_size"])])
        cmd.extend(["--safety-learning-rate", str(parameters["safety_learning_rate"])])

        # Testing configuration
        cmd.extend(["--num-test-samples", str(parameters["num_test_samples"])])
        if parameters.get("test_variations"):
            cmd.append("--test-variations")

        # Output configuration
        output_dir_base = parameters.get("output_dir", "/results/persistence_tests")
        output_dir_full = f"{output_dir_base}/{job_id}"
        cmd.extend(["--output-dir", output_dir_full])

        if parameters.get("save_safety_model"):
            cmd.append("--save-safety-model")

        # Pass job ID for result tracking
        cmd.extend(["--job-id", str(job_id)])

    elif job_type == JobType.EVALUATE:
        cmd = ["python3", "scripts/evaluation/run_full_evaluation.py"]
        cmd.extend(["--model-path", parameters["model_path"]])
        cmd.extend(["--model-name", parameters["model_name"]])
        cmd.extend(["--output-db", parameters["output_db"]])
        cmd.extend(["--num-samples", str(parameters["num_samples"])])

        # Add test suites
        for suite in parameters["test_suites"]:
            cmd.extend(["--test-suite", suite])

    else:
        raise ValueError(f"Unknown job type: {job_type}")

    return cmd


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
        logger.info(f"Starting job {job_id} ({job_type.value})")

        # Build command
        command = build_command(job_id, job_type, parameters)
        logger.info(f"Command: {' '.join(command)}")

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

        logger.info(f"Job {job_id} running in container {container_id}")

        # Wait for container to finish
        exit_code = None
        while exit_code is None:
            exit_code = container_manager.get_container_exit_code(container_id)
            if exit_code is None:
                # Still running, sleep and check again
                import time

                time.sleep(5)

        logger.info(f"Job {job_id} finished with exit code {exit_code}")

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
        logger.error(f"Job {job_id} failed with error: {e}")

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
