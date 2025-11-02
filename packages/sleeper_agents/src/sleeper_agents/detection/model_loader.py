"""Unified model loading with automatic downloading and resource management.

This module provides a simple interface to load models for sleeper detection,
handling all the complexity of:
- Auto-downloading from HuggingFace Hub
- Auto-selecting quantization based on available VRAM
- Auto-detecting GPU/CPU and choosing appropriate device
- Supporting both ModelInterface and legacy HookedTransformer
"""

import logging
from pathlib import Path
from typing import Optional, cast

import torch

logger = logging.getLogger(__name__)


def load_model_for_detection(
    model_name: str,
    device: str = "auto",
    prefer_hooked: bool = False,
    download_if_missing: bool = True,
    cache_dir: Optional[Path] = None,
    quantization: Optional[str] = None,
):
    """Load a model for sleeper agent detection with automatic setup.

    This is the main entry point for loading models in the sleeper detection framework.
    It handles all the complexity of model downloading, device selection, and
    quantization automatically.

    Args:
        model_name: Model name (short name from registry or HuggingFace model ID)
        device: Device to use ('auto', 'cuda', 'cpu', 'mps')
                'auto' will auto-detect GPU availability
        prefer_hooked: Prefer HookedTransformer if model supports it
        download_if_missing: Auto-download model if not cached
        cache_dir: Custom cache directory (default: HF_HOME or ~/.cache/sleeper_agents)
        quantization: Force quantization ('4bit', '8bit', or None for auto)

    Returns:
        ModelInterface: Loaded model ready for inference and activation extraction

    Raises:
        RuntimeError: If model loading fails
        ValueError: If model not found in registry and not a valid HF model ID

    Examples:
        >>> # Simple usage - auto-detect everything
        >>> model = load_model_for_detection("gpt2")
        >>>
        >>> # Force CPU mode for testing in VM
        >>> model = load_model_for_detection("mistral-7b", device="cpu")
        >>>
        >>> # Use HookedTransformer for better interpretability
        >>> model = load_model_for_detection("gpt2", prefer_hooked=True)
        >>>
        >>> # Load 7B model with automatic quantization
        >>> model = load_model_for_detection("codellama-7b")  # Auto 4-bit if needed
    """
    from sleeper_agents.models.downloader import ModelDownloader
    from sleeper_agents.models.model_interface import load_model
    from sleeper_agents.models.registry import get_registry
    from sleeper_agents.models.resource_manager import get_resource_manager

    logger.info(f"Loading model for detection: {model_name}")

    # Step 1: Resolve device
    if device == "auto":
        if torch.cuda.is_available():
            device = "cuda"
            logger.info("Auto-detected CUDA GPU")
        elif torch.backends.mps.is_available():
            device = "mps"
            logger.info("Auto-detected MPS (Apple Silicon)")
        else:
            device = "cpu"
            logger.info("No GPU detected, using CPU")
    else:
        logger.info(f"Using specified device: {device}")

    # Step 2: Check if model_name is a local path
    model_path_obj = Path(model_name)
    is_local_path = model_path_obj.exists() and model_path_obj.is_dir()

    if is_local_path:
        logger.info(f"Detected local model path: {model_name}")
        model_id = str(model_path_obj.resolve())
        model_meta = None
        download_if_missing = False  # Don't try to download local models
    else:
        # Get model metadata from registry
        registry = get_registry()
        model_meta = registry.get(model_name)

        # If not in registry, assume it's a HuggingFace model ID
        if model_meta is None:
            logger.warning("Model %s not found in registry, treating as HuggingFace model ID", model_name)
            model_id = model_name
        else:
            model_id = model_meta.model_id
            logger.info("Resolved %s to %s", model_name, model_id)

    # Step 3: Check resources and determine quantization
    resource_mgr = get_resource_manager()
    available_vram = resource_mgr.available_vram  # Can be None for CPU

    if quantization is None and device in ["cuda", "mps"] and available_vram is not None:
        # Auto-determine quantization
        if model_meta:
            if model_meta.estimated_vram_gb <= available_vram:
                quantization = None
                logger.info(f"Model fits in {available_vram:.1f} GB without quantization")
            elif model_meta.estimated_vram_4bit_gb <= available_vram:
                quantization = "4bit"
                logger.info(f"Using 4-bit quantization to fit in {available_vram:.1f} GB")
            else:
                logger.warning(
                    f"Model may not fit in available VRAM ({available_vram:.1f} GB). " f"Attempting 4-bit quantization anyway."
                )
                quantization = "4bit"

    # Step 4: Download model if needed
    if download_if_missing:
        downloader = ModelDownloader(cache_dir=cache_dir)

        if not downloader.is_cached(model_id):
            logger.info("Model not cached, downloading %s...", model_id)
            try:
                model_path = downloader.download(model_id, use_quantization=quantization, show_progress=True)
                logger.info(f"Model downloaded to: {model_path}")
            except Exception as e:
                raise RuntimeError(f"Failed to download model {model_id}: {e}") from e
        else:
            logger.info(f"Model already cached: {model_id}")

    # Step 5: Determine dtype based on device and quantization
    if quantization == "4bit":
        # 4-bit quantization handled by transformers BitsAndBytes
        dtype = torch.float16 if device != "cpu" else torch.float32
        logger.info("Using 4-bit quantization (BitsAndBytes)")
    elif quantization == "8bit":
        dtype = torch.float16 if device != "cpu" else torch.float32
        logger.info("Using 8-bit quantization")
    else:
        # No quantization
        if device == "cpu":
            dtype = torch.float32
        else:
            dtype = torch.float16  # fp16 for GPU
        logger.info(f"Using dtype: {dtype}")

    # Step 6: Load model using ModelInterface factory
    try:
        logger.info(f"Loading model with ModelInterface (prefer_hooked={prefer_hooked})...")
        model = load_model(model_id=model_id, device=device, dtype=dtype, prefer_hooked=prefer_hooked)

        logger.info(f"Model loaded successfully: {type(model).__name__}")
        logger.info(f"  Layers: {model.get_num_layers()}")
        logger.info(f"  Hidden size: {model.get_hidden_size()}")
        logger.info(f"  Device: {device}")

        # Verify model has required methods
        if not hasattr(model, "get_activations"):
            raise RuntimeError(f"Loaded model {type(model).__name__} doesn't have 'get_activations' method")

        if not hasattr(model, "generate"):
            raise RuntimeError(f"Loaded model {type(model).__name__} doesn't have 'generate' method")

        return model

    except Exception as e:
        logger.error(f"Failed to load model {model_id}: {e}")
        raise RuntimeError(f"Model loading failed for {model_id}: {e}") from e


def get_recommended_layers(model, model_name: Optional[str] = None) -> list[int]:
    """Get recommended layers to probe for a model.

    Args:
        model: Loaded model (ModelInterface or HookedTransformer)
        model_name: Optional model name to look up in registry

    Returns:
        List of layer indices to probe

    Examples:
        >>> model = load_model_for_detection("gpt2")
        >>> layers = get_recommended_layers(model, "gpt2")
        >>> print(layers)  # [3, 6, 9]
    """
    from sleeper_agents.models.registry import get_registry

    # Try to get from registry first
    if model_name:
        registry = get_registry()
        model_meta = registry.get(model_name)
        if model_meta and model_meta.recommended_probe_layers:
            return cast(list[int], model_meta.recommended_probe_layers)

    # Fallback: probe early, middle, and late layers
    num_layers = model.get_num_layers() if hasattr(model, "get_num_layers") else 12

    if num_layers <= 6:
        # Small model - probe all layers
        return list(range(num_layers))
    elif num_layers <= 12:
        # Medium model - probe every other layer
        return list(range(0, num_layers, 2))
    else:
        # Large model - probe strategically
        return [num_layers // 4, num_layers // 2, 3 * num_layers // 4, num_layers - 1]


def estimate_memory_usage(model_name: str, batch_size: int = 1, sequence_length: int = 512) -> dict:
    """Estimate memory usage for a model during inference.

    Args:
        model_name: Model name (short name or HF model ID)
        batch_size: Batch size for inference
        sequence_length: Sequence length

    Returns:
        Dictionary with memory estimates in GB

    Examples:
        >>> mem = estimate_memory_usage("mistral-7b", batch_size=4, sequence_length=1024)
        >>> print(f"Estimated VRAM: {mem['total_vram_gb']:.1f} GB")
    """
    from sleeper_agents.models.registry import get_registry

    registry = get_registry()
    model_meta = registry.get(model_name)

    if not model_meta:
        return {"total_vram_gb": 0.0, "model_vram_gb": 0.0, "activation_vram_gb": 0.0, "warning": "Model not in registry"}

    # Base model size
    model_vram = model_meta.estimated_vram_gb

    # Activation memory (rough estimate)
    # activations ≈ batch_size × seq_len × hidden_size × num_layers × bytes_per_value
    hidden_size = 4096 if model_meta.parameter_count > 1_000_000_000 else 768
    num_layers = model_meta.num_layers
    bytes_per_value = 2  # fp16

    activation_gb = (batch_size * sequence_length * hidden_size * num_layers * bytes_per_value) / (1024**3)

    total_vram = model_vram + activation_gb

    return {
        "model_vram_gb": model_vram,
        "activation_vram_gb": activation_gb,
        "total_vram_gb": total_vram,
        "batch_size": batch_size,
        "sequence_length": sequence_length,
    }
