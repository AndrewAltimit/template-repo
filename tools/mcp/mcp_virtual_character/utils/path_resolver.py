#!/usr/bin/env python3
"""
Path resolver for Virtual Character system.
Handles mapping between container paths, VM paths, and Windows host paths.
"""

import os
from pathlib import Path
from typing import List, Optional


class PathResolver:
    """Intelligent path resolution for cross-system file access."""

    # Common path mappings
    PATH_MAPPINGS = [
        # Container path -> Host path
        ("/tmp/elevenlabs_audio/", "outputs/elevenlabs_speech/"),
        ("/tmp/audio_storage/", "outputs/audio_storage/"),
        ("/tmp/comfyui_outputs/", "outputs/comfyui/"),
    ]

    @staticmethod
    def resolve_audio_path(audio_path: str) -> Optional[str]:
        """
        Resolve audio file path across different environments.

        Args:
            audio_path: Input path (container, relative, or absolute)

        Returns:
            Resolved path that exists, or None if not found
        """
        original_path = audio_path
        path = Path(audio_path)

        # If path exists as-is, return it
        if path.exists():
            return str(path)

        # Try path mappings for container paths
        for container_prefix, host_prefix in PathResolver.PATH_MAPPINGS:
            if audio_path.startswith(container_prefix):
                # Extract the relative part
                relative = audio_path[len(container_prefix) :]
                mapped = Path(host_prefix) / relative

                if mapped.exists():
                    return str(mapped)

                # Try from repo root
                repo_root = PathResolver._find_repo_root()
                if repo_root:
                    full_path = repo_root / mapped
                    if full_path.exists():
                        return str(full_path)

        # Try common output directories
        possible_paths = PathResolver._get_possible_paths(audio_path)
        for possible in possible_paths:
            if possible.exists():
                return str(possible)

        # If nothing found, return original
        print(f"Warning: Could not resolve path: {original_path}")
        return None

    @staticmethod
    def _find_repo_root() -> Optional[Path]:
        """Find repository root directory."""
        current = Path.cwd()

        for _ in range(10):
            if (current / ".git").exists():
                return current
            if current.parent == current:
                break
            current = current.parent

        return None

    @staticmethod
    def _get_possible_paths(filename: str) -> List[Path]:
        """Generate list of possible paths for a file."""
        paths = []
        filename = Path(filename).name  # Get just the filename

        # Common output directories to check
        output_dirs = [
            "outputs/elevenlabs_speech",
            "outputs/elevenlabs_speech/2025-09-17",
            "outputs/audio_storage",
            "outputs/comfyui",
            "/tmp/elevenlabs_audio",
            "/tmp/audio_storage",
        ]

        # Check from current directory
        for dir_path in output_dirs:
            paths.append(Path(dir_path) / filename)

        # Check from repo root
        repo_root = PathResolver._find_repo_root()
        if repo_root:
            for dir_path in output_dirs:
                paths.append(repo_root / dir_path / filename)

        # Check dated subdirectories
        from datetime import datetime

        today = datetime.now().strftime("%Y-%m-%d")
        for base_dir in ["outputs/elevenlabs_speech", "outputs/audio_storage"]:
            paths.append(Path(base_dir) / today / filename)
            if repo_root:
                paths.append(repo_root / base_dir / today / filename)

        return paths

    @staticmethod
    def get_storage_url(_file_path: str) -> Optional[str]:
        """
        Get the appropriate storage URL for uploading from this environment.

        Returns the storage service URL based on network topology.
        """
        # Import here to avoid circular dependency
        from .env_loader import ensure_storage_config

        config = ensure_storage_config()
        url = config.get("STORAGE_BASE_URL")
        return url if isinstance(url, str) else None

    @staticmethod
    def is_url(path: str) -> bool:
        """Check if path is a URL."""
        return path.startswith(("http://", "https://", "file://"))

    @staticmethod
    def is_storage_url(path: str) -> bool:
        """Check if path is a storage service URL."""
        storage_url = os.getenv("STORAGE_BASE_URL", "http://localhost:8021")
        return path.startswith(f"{storage_url}/download/")
