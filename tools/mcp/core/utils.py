"""Common utilities for MCP servers"""

import logging
import os
import sys
from typing import Any, Dict, List, Optional


def setup_logging(name: str, level: str = "INFO") -> logging.Logger:
    """Setup logging for an MCP server

    Args:
        name: Logger name
        level: Logging level (DEBUG, INFO, WARNING, ERROR)

    Returns:
        Configured logger instance
    """
    # Configure logging format
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    # Setup console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))
    logger.addHandler(console_handler)

    return logger


def validate_environment(required_vars: List[str]) -> Dict[str, str]:
    """Validate that required environment variables are set

    Args:
        required_vars: List of required environment variable names

    Returns:
        Dictionary of environment variable values

    Raises:
        ValueError: If any required variables are missing
    """
    env_vars = {}
    missing_vars = []

    for var in required_vars:
        value = os.environ.get(var)
        if value is None:
            missing_vars.append(var)
        else:
            env_vars[var] = value

    if missing_vars:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

    return env_vars


def ensure_directory(path: str) -> str:
    """Ensure a directory exists, creating it if necessary

    Args:
        path: Directory path

    Returns:
        The path that was created/verified
    """
    os.makedirs(path, exist_ok=True)
    return path


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """Load configuration from JSON file

    Args:
        config_path: Path to config file (defaults to .mcp.json)

    Returns:
        Configuration dictionary
    """
    import json

    if config_path is None:
        # Look for .mcp.json in various locations
        search_paths = [
            ".mcp.json",
            os.path.expanduser("~/.mcp.json"),
            "/etc/mcp/config.json",
        ]

        for path in search_paths:
            if os.path.exists(path):
                config_path = path
                break

    if config_path and os.path.exists(config_path):
        with open(config_path, "r") as f:
            config_data = json.load(f)
            assert isinstance(config_data, dict)  # Type assertion for mypy
            return config_data

    return {}


def check_container_environment() -> bool:
    """Check if running inside a Docker container

    Returns:
        True if running in container, False otherwise
    """
    # Check for .dockerenv file
    if os.path.exists("/.dockerenv"):
        return True

    # Check cgroup for docker
    try:
        with open("/proc/self/cgroup", "r") as f:
            return "docker" in f.read()
    except Exception:
        return False
