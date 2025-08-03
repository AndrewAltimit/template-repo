#!/usr/bin/env python3
"""Auto Review script that uses existing monitors in review-only mode."""

import logging
import os
import sys

from github_ai_agents.monitors import IssueMonitor, PRMonitor

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def main():
    # Parse configuration from environment
    agents = os.environ.get("REVIEW_AGENTS", "claude,gemini").split(",")
    target = os.environ.get("REVIEW_TARGET", "both")
    issue_numbers = os.environ.get("REVIEW_ISSUE_NUMBERS", "").split(",") if os.environ.get("REVIEW_ISSUE_NUMBERS") else []
    pr_numbers = os.environ.get("REVIEW_PR_NUMBERS", "").split(",") if os.environ.get("REVIEW_PR_NUMBERS") else []
    review_depth = os.environ.get("REVIEW_DEPTH", "standard")
    comment_style = os.environ.get("COMMENT_STYLE", "consolidated")

    # Clean up agent names
    agents = [a.strip().lower() for a in agents if a.strip()]

    logger.info("Auto Review Configuration:")
    logger.info(f"  Agents: {agents}")
    logger.info(f"  Target: {target}")
    logger.info(f"  Issue Numbers: {issue_numbers or 'all open'}")
    logger.info(f"  PR Numbers: {pr_numbers or 'all open'}")
    logger.info(f"  Review Depth: {review_depth}")
    logger.info(f"  Comment Style: {comment_style}")

    # Set review-only mode in environment for monitors to detect
    os.environ["REVIEW_ONLY_MODE"] = "true"
    os.environ["ENABLED_AGENTS_OVERRIDE"] = ",".join(agents)
    os.environ["REVIEW_DEPTH"] = review_depth
    os.environ["COMMENT_STYLE"] = comment_style

    try:
        # Process issues if requested
        if target in ["issues", "both"]:
            logger.info("Processing issues...")
            issue_monitor = IssueMonitor()

            # Override to only process specific issues if provided
            if issue_numbers:
                os.environ["TARGET_ISSUE_NUMBERS"] = ",".join(issue_numbers)

            issue_monitor.process_items()

        # Process PRs if requested
        if target in ["pull-requests", "both"]:
            logger.info("Processing pull requests...")
            pr_monitor = PRMonitor()

            # Override to only process specific PRs if provided
            if pr_numbers:
                os.environ["TARGET_PR_NUMBERS"] = ",".join(pr_numbers)

            pr_monitor.process_items()

        logger.info("Auto Review completed successfully")

    except Exception as e:
        logger.error(f"Auto Review failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
