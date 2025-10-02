"""Model management infrastructure for sleeper agent detection.

This module provides:
- Model registry with curated open-weight models
- Automatic downloading with caching
- Resource management for GPU/CPU constraints
"""

from packages.sleeper_detection.models.downloader import ModelDownloader
from packages.sleeper_detection.models.registry import ModelRegistry, get_registry
from packages.sleeper_detection.models.resource_manager import ResourceManager, get_resource_manager

__all__ = ["ModelRegistry", "ModelDownloader", "ResourceManager", "get_registry", "get_resource_manager"]
