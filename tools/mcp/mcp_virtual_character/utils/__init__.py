"""
Virtual Character utilities for robust system operation.
"""

# Use absolute imports to avoid W0406 (import-self) when pylint scans all files
# This is necessary because there's a utils.py module in mcp_core package
from mcp_virtual_character.utils.env_loader import (  # pylint: disable=import-self
    ensure_storage_config,
    load_env_file,
)
from mcp_virtual_character.utils.path_resolver import PathResolver  # pylint: disable=import-self

__all__ = [
    "load_env_file",
    "ensure_storage_config",
    "PathResolver",
]
