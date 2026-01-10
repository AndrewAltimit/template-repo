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
        # Log stderr if stdout is empty (may contain useful warnings)
        if not result.stdout.strip() and result.stderr.strip():
            logger.warning("gh command stderr (stdout empty): %s", result.stderr.strip())
        return result.stdout
    except subprocess.CalledProcessError as e:
        logger.error("GitHub CLI command failed (exit code %d): %s", e.returncode, " ".join(cmd))
        if e.stdout:
            logger.error("stdout: %s", e.stdout.strip())
        if e.stderr:
            logger.error("stderr: %s", e.stderr.strip())
        if not check:
            # Return stderr as diagnostic info when stdout failed
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


def run_gh_command_with_stderr(args: List[str]) -> tuple[Optional[str], Optional[str], int]:
    """Run GitHub CLI command and capture both stdout and stderr.

    Args:
        args: Command arguments (without 'gh' prefix)

    Returns:
        Tuple of (stdout, stderr, return_code)
    """
    cmd = ["gh"] + args

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,  # Don't raise on non-zero
    )

    return (
        result.stdout.strip() if result.stdout else None,
        result.stderr.strip() if result.stderr else None,
        result.returncode,
    )


async def run_gh_command_with_stderr_async(
    args: List[str],
) -> tuple[Optional[str], Optional[str], int]:
    """Run GitHub CLI command asynchronously and capture both stdout and stderr.

    Args:
        args: Command arguments (without 'gh' prefix)

    Returns:
        Tuple of (stdout, stderr, return_code)
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, run_gh_command_with_stderr, args)


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
        logger.error("Git command failed: %s", e)
        if e.stderr:
            logger.error("Error output: %s", e.stderr)
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
