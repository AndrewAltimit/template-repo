"""GitHub utility functions."""

import logging
import os
import subprocess
from typing import List, Optional

logger = logging.getLogger(__name__)


def get_github_token() -> str:
    """Get GitHub token from environment.

    Returns:
        GitHub token

    Raises:
        RuntimeError: If token not found
    """
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        raise RuntimeError("GitHub token not found in environment")
    return token


def run_gh_command(args: List[str], check: bool = True) -> Optional[str]:
    """Run GitHub CLI command.

    Args:
        args: Command arguments
        check: Whether to check return code

    Returns:
        Command output or None if failed
    """
    cmd = ["gh"] + args

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=check,
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        logger.error(f"GitHub CLI command failed: {e}")
        if e.stderr:
            logger.error(f"Error output: {e.stderr}")
        if not check:
            return None
        raise
