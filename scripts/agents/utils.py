#!/usr/bin/env python3
"""
Shared utilities for AI agents.
"""

import os
import subprocess
from pathlib import Path
from typing import List, Optional

from logging_security import get_secure_logger

logger = get_secure_logger(__name__)


def get_github_token() -> str:
    """
    Get GitHub token from Docker secret or environment variable.

    Prefers Docker secret if available for enhanced security.
    Falls back to environment variable for compatibility.

    Returns:
        GitHub token string

    Raises:
        RuntimeError: If no token is available
    """
    # Check Docker secret first (more secure)
    secret_path = Path("/run/secrets/github_token")
    if secret_path.exists():
        try:
            token = secret_path.read_text().strip()
            if token:
                logger.debug("Using GitHub token from Docker secret")
                return token
        except Exception as e:
            logger.warning(f"Failed to read Docker secret: {e}")

    # Fall back to environment variable
    token = os.environ.get("GITHUB_TOKEN", "")
    if token:
        logger.debug("Using GitHub token from environment variable")
        return token

    # Try gh CLI as last resort
    try:
        result = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, check=True)
        token = result.stdout.strip()
        if token:
            logger.debug("Using GitHub token from gh CLI")
            return token
    except subprocess.CalledProcessError:
        pass

    raise RuntimeError(
        "No GitHub token found. Please set GITHUB_TOKEN environment variable, "
        "configure Docker secret, or authenticate with 'gh auth login'"
    )


def run_gh_command(args: List[str]) -> Optional[str]:
    """Run GitHub CLI command and return output."""
    try:
        cmd = ["gh"] + args
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        logger.error(f"GitHub CLI error: {e.stderr}")
        return None
