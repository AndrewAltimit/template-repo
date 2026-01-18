#!/usr/bin/env python3
"""Auto Review script that uses Rust github-agents CLI in review-only mode."""

import logging
import os
import subprocess
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def run_command(cmd: list, description: str) -> bool:
    """Run a command and return success status."""
    logger.info("Running: %s", " ".join(cmd))
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode == 0:
            logger.info("%s completed successfully", description)
            if result.stdout:
                print(result.stdout)
            return True
        else:
            logger.error("%s failed with exit code %d", description, result.returncode)
            if result.stderr:
                print(result.stderr, file=sys.stderr)
            return False
    except FileNotFoundError:
        logger.error("Command not found: %s", cmd[0])
        return False


def main():
    """Run automated code review using configured AI agents on issues and PRs."""
    # Parse configuration from environment
    agents = os.environ.get("REVIEW_AGENTS", "claude,gemini").split(",")
    target = os.environ.get("REVIEW_TARGET", "both")
    review_depth = os.environ.get("REVIEW_DEPTH", "standard")

    # Clean up agent names
    agents = [a.strip().lower() for a in agents if a.strip()]

    logger.info("Auto Review Configuration:")
    logger.info("  Agents: %s", agents)
    logger.info("  Target: %s", target)
    logger.info("  Review Depth: %s", review_depth)

    # Find the github-agents binary
    github_agents_bin = None
    search_paths = [
        os.path.join(os.getcwd(), "tools/rust/github-agents-cli/target/release/github-agents"),
        os.path.expanduser("~/.local/bin/github-agents"),
    ]

    for path in search_paths:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            github_agents_bin = path
            break

    if not github_agents_bin:
        # Try finding in PATH
        import shutil

        github_agents_bin = shutil.which("github-agents")

    if not github_agents_bin:
        logger.error("github-agents binary not found. Please build it first:")
        logger.error("  cd tools/rust/github-agents-cli && cargo build --release")
        sys.exit(1)

    logger.info("Using github-agents at: %s", github_agents_bin)

    success = True

    # Process issues if requested
    if target in ["issues", "both"]:
        logger.info("Processing issues...")
        cmd = [github_agents_bin, "issue-monitor"]
        if not run_command(cmd, "Issue monitor"):
            success = False

    # Process PRs if requested
    if target in ["pull-requests", "both"]:
        logger.info("Processing PRs...")
        cmd = [github_agents_bin, "pr-monitor"]
        if not run_command(cmd, "PR monitor"):
            success = False

    if success:
        logger.info("Auto review completed successfully")
    else:
        logger.warning("Auto review completed with some failures")
        sys.exit(1)


if __name__ == "__main__":
    main()
