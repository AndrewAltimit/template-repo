"""GitHub utility functions."""

import asyncio
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


async def run_gh_command_async(args: List[str], check: bool = True) -> Optional[str]:
    """Run GitHub CLI command asynchronously without blocking the event loop.

    Args:
        args: Command arguments
        check: Whether to check return code

    Returns:
        Command output or None if failed
    """
    loop = asyncio.get_event_loop()
    # Run the blocking subprocess call in a thread pool
    return await loop.run_in_executor(None, run_gh_command, args, check)


def run_git_command(args: List[str], check: bool = True) -> Optional[str]:
    """Run git command.

    Args:
        args: Command arguments
        check: Whether to check return code

    Returns:
        Command output or None if failed
    """
    cmd = ["git"] + args

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=check,
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        logger.error(f"Git command failed: {e}")
        if e.stderr:
            logger.error(f"Error output: {e.stderr}")
        if not check:
            return None
        raise


async def run_git_command_async(args: List[str], check: bool = True) -> Optional[str]:
    """Run git command asynchronously without blocking the event loop.

    Args:
        args: Command arguments
        check: Whether to check return code

    Returns:
        Command output or None if failed
    """
    loop = asyncio.get_event_loop()
    # Run the blocking subprocess call in a thread pool
    return await loop.run_in_executor(None, run_git_command, args, check)
