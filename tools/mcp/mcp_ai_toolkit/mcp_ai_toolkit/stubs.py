"""AI Toolkit MCP Server Tool Stubs

This file provides stub implementations for all AI Toolkit MCP tools.
These stubs are for documentation and testing purposes.
"""

from typing import Any, Dict, List, Optional


async def create_training_config(
    name: str,
    model_name: str,
    dataset_path: str,
    resolution: int = 512,
    steps: int = 1000,
    rank: int = 16,
    alpha: int = 16,
    low_vram: bool = True,
    trigger_word: Optional[str] = None,
    test_prompts: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Create a new training configuration for AI model training.

    Args:
        name: Configuration name
        model_name: Base model to train from (e.g., "ostris/Flux.1-alpha")
        dataset_path: Path to training dataset (must be absolute: /ai-toolkit/datasets/...)
        resolution: Training resolution (default: 512)
        steps: Number of training steps (default: 1000)
        rank: LoRA rank (default: 16)
        alpha: LoRA alpha (default: 16)
        low_vram: Enable low VRAM mode for <24GB GPUs (default: True)
        trigger_word: Trigger word for the LoRA
        test_prompts: List of test prompts to evaluate during training

    Returns:
        Dictionary with configuration details and ID
    """
    return {}


async def list_configs() -> Dict[str, List[Dict[str, Any]]]:
    """List all training configurations.

    Returns:
        Dictionary with list of configurations
    """
    return {}


async def get_config(name: str) -> Dict[str, Any]:
    """Get a specific training configuration.

    Args:
        name: Configuration name

    Returns:
        Configuration details
    """
    return {}


async def upload_dataset(dataset_name: str, images: List[Dict[str, str]]) -> Dict[str, Any]:
    """Upload images to create a dataset.

    Args:
        dataset_name: Name for the dataset
        images: List of image dictionaries with:
            - filename: Image filename
            - data: Base64 encoded image data
            - caption: Image caption for training

    Returns:
        Upload result with dataset path
    """
    return {}


async def list_datasets() -> Dict[str, List[str]]:
    """List all available datasets.

    Returns:
        Dictionary with list of dataset names
    """
    return {}


async def start_training(config_name: str) -> Dict[str, Any]:
    """Start a training job with the specified configuration.

    Args:
        config_name: Configuration name to use

    Returns:
        Training job details including job_id
    """
    return {}


async def get_training_status(job_id: str) -> Dict[str, Any]:
    """Get the status of a training job.

    Args:
        job_id: Training job ID

    Returns:
        Job status including progress, ETA, and current step
    """
    return {}


async def stop_training(job_id: str) -> Dict[str, Any]:
    """Stop a running training job.

    Args:
        job_id: Training job ID

    Returns:
        Confirmation of job cancellation
    """
    return {}


async def list_training_jobs() -> Dict[str, List[Dict[str, Any]]]:
    """List all training jobs.

    Returns:
        Dictionary with list of training jobs and their statuses
    """
    return {}


async def export_model(model_name: str, output_path: str) -> Dict[str, Any]:
    """Export a trained model.

    Args:
        model_name: Model name
        output_path: Output path for the exported model

    Returns:
        Export result with file details
    """
    return {}


async def list_exported_models() -> Dict[str, List[str]]:
    """List all exported models.

    Returns:
        Dictionary with list of exported model names
    """
    return {}


async def download_model(model_name: str, encoding: str = "base64") -> Dict[str, Any]:
    """Download a trained model.

    Args:
        model_name: Model name to download
        encoding: Encoding format ("base64" or "raw")

    Returns:
        Model data and metadata
    """
    return {}


async def get_system_stats() -> Dict[str, Any]:
    """Get system statistics including GPU info.

    Returns:
        System statistics including GPU, memory, and disk usage
    """
    return {}


async def get_training_logs(job_id: str, lines: int = 100) -> Dict[str, Any]:
    """Get training logs for a job.

    Args:
        job_id: Training job ID
        lines: Number of log lines to retrieve (default: 100)

    Returns:
        Recent log lines from the training job
    """
    return {}


async def get_training_info() -> Dict[str, Any]:
    """Get detailed training information and capabilities.

    Returns:
        Information about supported models, datasets, and configurations
    """
    return {}
