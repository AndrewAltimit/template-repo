"""ComfyUI MCP Server Tool Stubs

This file provides stub implementations for all ComfyUI MCP tools.
These stubs are for documentation and testing purposes.
"""

from typing import Any, Dict, List, Optional


async def generate_image(
    prompt: str,
    workflow: Optional[Dict[str, Any]] = None,
    negative_prompt: str = "",
    width: int = 512,
    height: int = 512,
    seed: int = -1,
    steps: int = 20,
    cfg_scale: float = 7.0,
) -> Dict[str, Any]:
    """Generate an image using ComfyUI workflow.

    Args:
        prompt: Text prompt for generation
        workflow: ComfyUI workflow JSON (optional, uses default if not provided)
        negative_prompt: Negative prompt (default: "")
        width: Image width (default: 512)
        height: Image height (default: 512)
        seed: Random seed, -1 for random (default: -1)
        steps: Number of generation steps (default: 20)
        cfg_scale: CFG scale for guidance (default: 7.0)

    Returns:
        Generated image data and metadata
    """
    return {}


async def list_workflows() -> Dict[str, List[str]]:
    """List available ComfyUI workflows.

    Returns:
        Dictionary with list of workflow names
    """
    return {}


async def get_workflow(name: str) -> Dict[str, Any]:
    """Get a specific workflow configuration.

    Args:
        name: Workflow name

    Returns:
        Workflow JSON configuration
    """
    return {}


async def list_models(type: Optional[str] = None) -> Dict[str, List[str]]:
    """List available models.

    Args:
        type: Model type filter ("checkpoint", "lora", "vae", "embeddings")

    Returns:
        Dictionary with list of model names by type
    """
    return {}


async def upload_lora(filename: str, data: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Upload a LoRA model to ComfyUI.

    Args:
        filename: Filename for the LoRA
        data: Base64 encoded LoRA data
        metadata: Optional LoRA metadata

    Returns:
        Upload result with file details
    """
    return {}


async def upload_lora_chunked_init(
    filename: str, total_size: int, metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, str]:
    """Initialize chunked upload for large LoRA files.

    Args:
        filename: Filename for the LoRA
        total_size: Total file size in bytes
        metadata: Optional LoRA metadata

    Returns:
        Dictionary with upload_id for chunk uploads
    """
    return {}


async def upload_lora_chunk(upload_id: str, chunk_index: int, chunk: str, total_chunks: int) -> Dict[str, Any]:
    """Upload a chunk of a large LoRA file.

    Args:
        upload_id: Upload ID from init
        chunk_index: Current chunk index (0-based)
        chunk: Base64 encoded chunk data
        total_chunks: Total number of chunks

    Returns:
        Chunk upload confirmation
    """
    return {}


async def upload_lora_chunked_complete(upload_id: str) -> Dict[str, Any]:
    """Complete a chunked LoRA upload.

    Args:
        upload_id: Upload ID from init

    Returns:
        Final upload result with file details
    """
    return {}


async def list_loras() -> Dict[str, List[str]]:
    """List available LoRA models.

    Returns:
        Dictionary with list of LoRA filenames
    """
    return {}


async def download_lora(filename: str, encoding: str = "base64") -> Dict[str, Any]:
    """Download a LoRA model from ComfyUI.

    Args:
        filename: LoRA filename
        encoding: Encoding format ("base64" or "raw")

    Returns:
        LoRA data and metadata
    """
    return {}


async def get_object_info() -> Dict[str, Any]:
    """Get ComfyUI node and model information.

    Returns:
        Complete object info including available nodes and their properties
    """
    return {}


async def get_system_info() -> Dict[str, Any]:
    """Get ComfyUI system information.

    Returns:
        System info including version, python version, and capabilities
    """
    return {}


async def transfer_lora_from_ai_toolkit(model_name: str, filename: str) -> Dict[str, Any]:
    """Transfer a LoRA from AI Toolkit to ComfyUI.

    Args:
        model_name: Model name in AI Toolkit
        filename: Target filename in ComfyUI

    Returns:
        Transfer result with file details
    """
    return {}


async def execute_workflow(workflow: Dict[str, Any], client_id: Optional[str] = None) -> Dict[str, Any]:
    """Execute a custom ComfyUI workflow.

    Args:
        workflow: Complete workflow JSON
        client_id: Optional client ID for websocket updates

    Returns:
        Execution result with prompt ID and outputs
    """
    return {}
