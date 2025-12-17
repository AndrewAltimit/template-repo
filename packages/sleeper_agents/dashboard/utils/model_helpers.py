"""Model selection helper functions for Build components.

Provides utilities for fetching and displaying trained models from job history.
"""

from typing import Any, Dict, List


def get_backdoor_models(api_client) -> List[Dict[str, Any]]:
    """Fetch backdoor training jobs to populate model selection.

    Args:
        api_client: GPUOrchestratorClient instance

    Returns:
        List of dicts with job_id, output_dir, backdoor_type, created_at, status
    """
    try:
        # Fetch all backdoor training jobs
        response = api_client.list_jobs(job_type="train_backdoor", limit=100)
        jobs = response.get("jobs", [])

        backdoor_models = []
        for job in jobs:
            # Only include completed jobs
            status = job.get("status", "").lower()
            if status != "completed":
                continue

            params = job.get("parameters", {})
            model_path = params.get("model_path")
            output_dir_base = params.get("output_dir", "/results/backdoor_models")
            if model_path:  # Only include jobs with model paths
                # Output path is base_dir/job_id/model (model is the experiment_name)
                output_path = f"{output_dir_base}/{job['job_id']}/model"
                backdoor_models.append(
                    {
                        "job_id": job["job_id"],
                        "output_dir": output_path,
                        "backdoor_type": params.get("backdoor_type", "unknown"),
                        "created_at": job.get("created_at", ""),
                        "model_path": model_path,
                        "status": job.get("status", "unknown"),
                        "trigger": params.get("trigger", "unknown"),
                    }
                )

        return backdoor_models

    except Exception:
        # Silently fail and return empty list - user can still use custom path
        return []


def get_safety_trained_models(api_client) -> List[Dict[str, Any]]:
    """Fetch safety training jobs to populate model selection.

    Args:
        api_client: GPUOrchestratorClient instance

    Returns:
        List of dicts with job_id, output_dir, method, original_model, created_at
    """
    try:
        response = api_client.list_jobs(job_type="safety_training", limit=100)
        jobs = response.get("jobs", [])

        safety_models = []
        for job in jobs:
            # Only include completed jobs
            status = job.get("status", "").lower()
            if status != "completed":
                continue

            params = job.get("parameters", {})
            model_path = params.get("model_path")
            if model_path:
                # Safety trained models go to /results/safety_trained/{job_id}/model
                # (same structure as backdoor training)
                output_dir = f"/results/safety_trained/{job['job_id']}/model"
                safety_models.append(
                    {
                        "job_id": job["job_id"],
                        "output_dir": output_dir,
                        "method": params.get("method", "sft"),
                        "original_model": model_path,
                        "created_at": job.get("created_at", ""),
                        "status": job.get("status", "unknown"),
                        "test_persistence": params.get("test_persistence", False),
                    }
                )

        return safety_models

    except Exception:
        return []


def format_model_display(job: Dict[str, Any], model_type: str = "backdoor") -> str:
    """Format model info for display in dropdown.

    Args:
        job: Job dict with model info
        model_type: Type of model ("backdoor" or "safety")

    Returns:
        Formatted display string
    """
    job_id_short = job["job_id"][:8]
    created = job["created_at"][:10]  # Just date

    if model_type == "backdoor":
        base_model = job.get("model_path", "unknown")
        backdoor_type = job.get("backdoor_type", "unknown")
        trigger = job.get("trigger", "")
        return f"{base_model} → backdoored (Job: {job_id_short}, Type: {backdoor_type}, Trigger: {trigger}, Date: {created})"
    if model_type == "safety":
        original_model = job.get("original_model", "unknown")
        method = job.get("method", "sft").upper()
        return f"{original_model} → safety trained ({method}) (Job: {job_id_short}, Date: {created})"
    return f"Job {job_id_short} - {created}"


def resolve_model_path(job: Dict[str, Any]) -> str:
    """Resolve model output path from job info.

    Args:
        job: Job dict with output_dir or model_path

    Returns:
        Resolved model path
    """
    output_dir: str = job.get("output_dir", "")
    if output_dir:
        return output_dir
    model_path: str = job.get("model_path", "")
    return model_path


def get_all_trained_models(api_client) -> List[Dict[str, Any]]:
    """Get list of all completed training jobs (backdoor, safety, probes).

    Args:
        api_client: GPUOrchestratorClient instance

    Returns:
        List of job dictionaries with model info
    """
    try:
        all_models = []

        # Get backdoor models
        backdoor_models = get_backdoor_models(api_client)
        for job in backdoor_models:
            job["job_type"] = "backdoor"
        all_models.extend(backdoor_models)

        # Get safety trained models
        safety_models = get_safety_trained_models(api_client)
        for job in safety_models:
            job["job_type"] = "safety_training"
        all_models.extend(safety_models)

        # Sort by creation date (most recent first)
        all_models.sort(key=lambda x: x.get("created_at", ""), reverse=True)

        return all_models
    except Exception:
        return []
