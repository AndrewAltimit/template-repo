#!/usr/bin/env python3
"""
Automatic environment variable loader for Virtual Character system.
Loads .env file from repository root if it exists.
"""

import os
from pathlib import Path
from typing import Dict, Optional


def find_repo_root() -> Optional[Path]:
    """Find the repository root by looking for .git directory."""
    current = Path.cwd()

    # Search up to 10 levels
    for _ in range(10):
        if (current / ".git").exists() or (current / ".env").exists():
            return current
        if current.parent == current:
            break
        current = current.parent

    return None


def load_env_file(env_path: Optional[Path] = None) -> Dict[str, str]:
    """
    Load environment variables from .env file.

    Args:
        env_path: Optional path to .env file. If not provided, searches for it.

    Returns:
        Dictionary of loaded environment variables
    """
    loaded_vars = {}

    # Find .env file
    if env_path is None:
        repo_root = find_repo_root()
        if repo_root:
            env_path = repo_root / ".env"

    if env_path and env_path.exists():
        try:
            with open(env_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        os.environ[key] = value
                        loaded_vars[key] = value
        except Exception as e:
            print(f"Warning: Failed to load .env file: {e}")

    return loaded_vars


def ensure_storage_config():
    """Ensure storage configuration is properly set."""
    # Load .env if not already loaded
    if not os.getenv("STORAGE_SECRET_KEY"):
        load_env_file()

    # Auto-detect network topology
    if not os.getenv("STORAGE_BASE_URL"):
        # Check if we're in a VM or container
        if Path("/proc/version").exists():
            with open("/proc/version", "r") as f:
                version = f.read().lower()
                if "microsoft" in version or "wsl" in version:
                    # WSL/VM environment - storage is on host
                    os.environ["STORAGE_BASE_URL"] = "http://192.168.0.152:8021"
                else:
                    # Native Linux or container
                    os.environ["STORAGE_BASE_URL"] = "http://localhost:8021"
        else:
            # Windows host
            os.environ["STORAGE_BASE_URL"] = "http://localhost:8021"

    # Set virtual character server URL if not set
    if not os.getenv("VIRTUAL_CHARACTER_SERVER"):
        if Path("/proc/version").exists():
            # VM/Container - server is on Windows host
            os.environ["VIRTUAL_CHARACTER_SERVER"] = "http://192.168.0.152:8020"
        else:
            # Windows host
            os.environ["VIRTUAL_CHARACTER_SERVER"] = "http://localhost:8020"

    return {
        "STORAGE_SECRET_KEY": os.getenv("STORAGE_SECRET_KEY"),
        "STORAGE_BASE_URL": os.getenv("STORAGE_BASE_URL"),
        "VIRTUAL_CHARACTER_SERVER": os.getenv("VIRTUAL_CHARACTER_SERVER"),
    }


# Auto-load on import
_initial_vars = load_env_file()
if _initial_vars:
    print(f"Loaded {len(_initial_vars)} environment variables from .env")
