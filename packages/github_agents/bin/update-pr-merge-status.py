#!/usr/bin/env python3
"""Update board issue status when PR is merged.

This script parses PR body for linked issues (closes #N, fixes #N, resolves #N)
and updates their status to Done on the project board.

Environment variables:
    PR_NUMBER: Pull request number
    PR_BODY: Pull request body text
    GITHUB_TOKEN: GitHub access token
    GITHUB_PROJECTS_TOKEN: GitHub Projects token (optional, falls back to GITHUB_TOKEN)
"""

import asyncio
import os
import re
import sys
from pathlib import Path

# Add package to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
# pylint: disable=wrong-import-position  # Imports must come after sys.path modification

from github_agents.board.config import load_config  # noqa: E402
from github_agents.board.manager import BoardManager  # noqa: E402
from github_agents.board.models import IssueStatus  # noqa: E402


async def main() -> None:
    """Main entry point."""
    pr_number = int(os.getenv("PR_NUMBER", "0"))
    pr_body = os.getenv("PR_BODY", "")

    if not pr_number:
        print("Error: PR_NUMBER environment variable not set")
        sys.exit(1)

    # Extract issue numbers from PR body
    pattern = r"(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+#(\d+)"
    matches = re.findall(pattern, pr_body, re.IGNORECASE)
    issue_numbers = [int(num) for num in matches]

    if not issue_numbers:
        print(f"No linked issues found in PR #{pr_number}")
        return

    print(f"Found {len(issue_numbers)} linked issue(s) in PR #{pr_number}: {issue_numbers}")

    # Load board configuration
    config_path = Path("ai-agents-board.yml")
    if not config_path.exists():
        print("Board configuration not found - skipping status update")
        return

    config = load_config(str(config_path))
    github_token = os.getenv("GITHUB_PROJECTS_TOKEN") or os.getenv("GITHUB_TOKEN")

    if not github_token:
        print("Error: GITHUB_TOKEN or GITHUB_PROJECTS_TOKEN required")
        sys.exit(1)

    # Initialize board manager
    board_manager = BoardManager(config=config, github_token=github_token)
    await board_manager.initialize()

    # Update each linked issue to Done
    success_count = 0
    for issue_num in issue_numbers:
        try:
            success = await board_manager.update_status(issue_num, IssueStatus.DONE)
            if success:
                print(f"✅ Updated issue #{issue_num} to Done status (PR #{pr_number} merged)")
                success_count += 1
            else:
                print(f"❌ Failed to update issue #{issue_num} status")
        except Exception as e:
            print(f"❌ Error updating issue #{issue_num}: {e}")

    print(f"\n📊 Updated {success_count}/{len(issue_numbers)} issues")


if __name__ == "__main__":
    asyncio.run(main())
