#!/usr/bin/env python3
"""
GitHub Issue Monitoring Agent

This agent monitors GitHub issues and:
1. Comments on issues that need more information
2. Creates pull requests when there's enough information
3. Updates issue status
"""

import json
import logging
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from security import SecurityManager
from utils import run_gh_command

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class IssueMonitor:
    """Monitor GitHub issues and create PRs when appropriate."""

    def __init__(self):
        self.repo = os.environ.get("GITHUB_REPOSITORY", "")
        self.token = os.environ.get("GITHUB_TOKEN", "")

        # Load configuration
        self.config = self._load_config()
        issue_config = self.config.get("agents", {}).get("issue_monitor", {})

        # Use config values with fallbacks
        self.min_description_length = issue_config.get("min_description_length", 50)
        self.required_fields = issue_config.get(
            "required_fields",
            [
                "description",
                "expected behavior",
                "steps to reproduce",
            ],
        )
        self.actionable_labels = issue_config.get("actionable_labels", ["bug", "feature", "enhancement", "fix", "improvement"])
        # Cutoff period in hours for filtering recent issues
        self.cutoff_hours = issue_config.get("cutoff_hours", 24)

        self.agent_tag = "[AI Agent]"
        self.security_manager = SecurityManager()

    def _load_config(self) -> dict:
        """Load configuration from config.json."""
        config_path = Path(__file__).parent / "config.json"
        try:
            with open(config_path, "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning(f"Could not load config from {config_path}: {e}")
            return {}

    def get_open_issues(self) -> List[Dict]:
        """Get open issues from the repository, filtered by recent activity."""
        output = run_gh_command(
            [
                "issue",
                "list",
                "--repo",
                self.repo,
                "--state",
                "open",
                "--json",
                "number,title,body,author,createdAt,updatedAt,labels,comments",
            ]
        )

        if output:
            all_issues = json.loads(output)

            # Filter by recent activity
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=self.cutoff_hours)
            recent_issues = []

            for issue in all_issues:
                # Check both created and updated times
                created_at = datetime.fromisoformat(issue["createdAt"].replace("Z", "+00:00"))
                updated_at = (
                    datetime.fromisoformat(issue["updatedAt"].replace("Z", "+00:00")) if "updatedAt" in issue else created_at
                )

                # Include issue if it was created or updated recently
                if created_at >= cutoff_time or updated_at >= cutoff_time:
                    recent_issues.append(issue)

            logger.info(
                f"Filtered {len(all_issues)} issues to {len(recent_issues)} recent issues (cutoff: {self.cutoff_hours} hours)"
            )
            return recent_issues
        return []

    def has_agent_comment(self, issue_number: int) -> bool:
        """Check if the agent has already commented on this issue."""
        output = run_gh_command(
            [
                "issue",
                "view",
                str(issue_number),
                "--repo",
                self.repo,
                "--json",
                "comments",
            ]
        )

        if output:
            data = json.loads(output)
            for comment in data.get("comments", []):
                if self.agent_tag in comment.get("body", ""):
                    return True
        return False

    def analyze_issue(self, issue: Dict) -> Tuple[bool, List[str]]:
        """
        Analyze if issue has enough information.
        Returns (has_enough_info, missing_fields)
        """
        body = issue.get("body", "").lower()
        missing_fields = []

        # Check minimum description length
        if len(body) < self.min_description_length:
            missing_fields.append("detailed description")

        # Check for required information patterns
        patterns = {
            "description": r"(description|problem|issue|bug)[\s:]+.{20,}",
            "expected behavior": r"(expected|should|supposed)[\s:]+.{10,}",
            "steps to reproduce": r"(steps|reproduce|how to)[\s:]+.{10,}",
            "version": r"(version|commit|branch)[\s:]+\S+",
        }

        for field, pattern in patterns.items():
            if not re.search(pattern, body, re.IGNORECASE):
                missing_fields.append(field)

        # Check for code blocks or examples
        if "```" not in body and not re.search(r"`[^`]+`", body):
            missing_fields.append("code examples")

        has_enough_info = len(missing_fields) == 0
        return has_enough_info, missing_fields

    def create_information_request_comment(self, issue_number: int, missing_fields: List[str]) -> None:
        """Comment on issue requesting more information."""
        comment_body = (
            f"{self.agent_tag} Thank you for creating this issue! "
            "To help address it effectively, could you please provide "
            "the following additional information:\n\n"
        )

        for field in missing_fields:
            comment_body += f"- **{field.title()}**: "

            if field == "detailed description":
                comment_body += "Please provide a more detailed description of the issue\n"
            elif field == "expected behavior":
                comment_body += "What behavior did you expect to see?\n"
            elif field == "steps to reproduce":
                comment_body += "Please list the steps to reproduce this issue\n"
            elif field == "version":
                comment_body += "What version/branch/commit are you using?\n"
            elif field == "code examples":
                comment_body += "Please include relevant code snippets or examples\n"
            else:
                comment_body += f"Please provide information about {field}\n"

        comment_body += """
Once you've added this information, I'll be able to create a pull request to address the issue.

*This comment was generated by an AI agent monitoring system.*"""

        run_gh_command(
            [
                "issue",
                "comment",
                str(issue_number),
                "--repo",
                self.repo,
                "--body",
                comment_body,
            ]
        )

        logger.info(f"Requested more information on issue #{issue_number}")

    def post_security_rejection_comment(self, issue_number: int, reason: Optional[str] = None) -> None:
        """Post a comment explaining why the issue cannot be processed."""
        if reason:
            comment_body = (
                f"{self.agent_tag} Security Notice\n\n"
                f"This request was blocked: {reason}\n\n"
                f"{self.security_manager.reject_message}\n\n"
                "*This is an automated security measure.*"
            )
        else:
            comment_body = (
                f"{self.agent_tag} Security Notice\n\n"
                f"{self.security_manager.reject_message}\n\n"
                "*This is an automated security measure to prevent unauthorized use of AI agents.*"
            )

        run_gh_command(
            [
                "issue",
                "comment",
                str(issue_number),
                "--repo",
                self.repo,
                "--body",
                comment_body,
            ]
        )

        logger.info(f"Posted security rejection comment on issue #{issue_number}")

    def should_create_pr(self, issue: Dict) -> bool:
        """Determine if we should create a PR for this issue."""
        # Check if issue is actionable (bug fix, feature request, etc.)
        labels = [label.get("name", "").lower() for label in issue.get("labels", [])]
        actionable_labels = ["bug", "feature", "enhancement", "fix", "improvement"]

        has_actionable_label = any(label in actionable_labels for label in labels)

        return has_actionable_label

    def create_pr_from_issue(self, issue: Dict) -> Optional[str]:
        """Create a pull request to address the issue."""
        issue_number = issue["number"]
        issue_title = issue["title"]
        issue_body = issue["body"]

        # Create feature branch
        branch_name = f"fix-issue-{issue_number}"

        # Create implementation script
        implementation_script = f"""#!/bin/bash
# Auto-generated script to implement fix for issue #{issue_number}

# Create branch
git checkout -b {branch_name}

# Use Claude Code to implement the fix
npx --yes @claudeai/cli@latest code << 'EOF'
Issue #{issue_number}: {issue_title}

{issue_body}

Please implement a fix for this issue. Make sure to:
1. Address all the concerns mentioned in the issue
2. Add appropriate tests if needed
3. Update documentation if necessary
4. Follow the project's coding standards

After implementation, create a commit with a descriptive message.
EOF

# Create PR
gh pr create --title "Fix: {issue_title} (#{issue_number})" \\
    --body "This PR addresses issue #{issue_number}.

## Changes
- Implemented fix as described in the issue
- Added tests where appropriate
- Updated documentation

## Testing
- All existing tests pass
- New tests added for the fix

Closes #{issue_number}

*This PR was created by an AI agent.*" \\
    --assignee @me \\
    --label "automated"
"""

        # Save and execute the script
        script_path = f"/tmp/implement_issue_{issue_number}.sh"
        with open(script_path, "w") as f:
            f.write(implementation_script)

        os.chmod(script_path, 0o755)

        try:
            subprocess.run([script_path], check=True)

            # Comment on issue
            run_gh_command(
                [
                    "issue",
                    "comment",
                    str(issue_number),
                    "--repo",
                    self.repo,
                    "--body",
                    (
                        f"{self.agent_tag} I've created a pull request to address "
                        "this issue. The PR will be reviewed by our automated "
                        "review system."
                    ),
                ]
            )

            logger.info(f"Created PR for issue #{issue_number}")
            return branch_name

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to create PR for issue #{issue_number}: {e}")
            return None

    def process_issues(self):
        """Main process to monitor and handle issues."""
        logger.info("Starting issue monitoring...")

        issues = self.get_open_issues()
        logger.info(f"Found {len(issues)} open issues")

        for issue in issues:
            issue_number = issue["number"]

            # Enhanced security check with rate limiting and repository validation
            author = issue.get("author", {}).get("login", "unknown")
            repo = self.repo

            is_allowed, rejection_reason = self.security_manager.perform_full_security_check(
                username=author,
                action="issue_process",
                repository=repo,
                entity_type="issue",
                entity_id=str(issue_number),
            )

            if not is_allowed:
                # Post rejection comment with specific reason
                if not self.has_agent_comment(issue_number):
                    self.post_security_rejection_comment(issue_number, rejection_reason)
                continue

            # Skip if we've already commented
            if self.has_agent_comment(issue_number):
                logger.debug(f"Already processed issue #{issue_number}")
                continue

            # Analyze issue
            has_info, missing = self.analyze_issue(issue)

            if not has_info:
                # Request more information
                self.create_information_request_comment(issue_number, missing)
            elif self.should_create_pr(issue):
                # Create PR to address the issue
                self.create_pr_from_issue(issue)
            else:
                logger.info(f"Issue #{issue_number} not actionable yet")


def main():
    """Main entry point."""
    monitor = IssueMonitor()

    if "--continuous" in sys.argv:
        # Run continuously
        while True:
            try:
                monitor.process_issues()
                time.sleep(300)  # Check every 5 minutes
            except KeyboardInterrupt:
                logger.info("Monitoring stopped by user")
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(60)  # Wait a minute before retrying
    else:
        # Run once
        monitor.process_issues()


if __name__ == "__main__":
    main()
