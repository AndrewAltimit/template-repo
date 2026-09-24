"""Model management infrastructure for sleeper agent detection.

This module provides:
- Model registry with curated open-weight models
- Automatic downloading with caching
- Resource management for GPU/CPU constraints
- Unified model interface for inference
"""

from .downloader import ModelDownloader
from .model_interface import (
    BACKEND_HUGGINGFACE,
    BACKEND_TRANSFORMER_LENS,
    HuggingFaceModel,
    ModelInterface,
    ResidualHooksUnsupportedError,
    TransformerLensModel,
    as_residual_hook_model,
    find_transformer_blocks,
    gather_last_non_pad,
    last_non_pad_indices,
    load_model,
)
from .registry import ModelRegistry, get_registry
from .resource_manager import ResourceManager, get_resource_manager
from .transformer_lens_loader import load_transformer_lens_model

__all__ = [
    "ModelRegistry",
    "ModelDownloader",
    "ResourceManager",
    "get_registry",
    "get_resource_manager",
    "ModelInterface",
    "ResidualHooksUnsupportedError",
    "as_residual_hook_model",
    "find_transformer_blocks",
    "HuggingFaceModel",
    "TransformerLensModel",
    "BACKEND_HUGGINGFACE",
    "BACKEND_TRANSFORMER_LENS",
    "gather_last_non_pad",
    "last_non_pad_indices",
    "load_model",
    "load_transformer_lens_model",
]
