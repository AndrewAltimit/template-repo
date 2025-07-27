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
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from logging_security import get_secure_logger, setup_secure_logging
from security import SecurityManager
from subagent_manager import implement_issue_with_tech_lead
from utils import get_github_token, run_gh_command

# Configure logging with security
log_level = logging.DEBUG if os.environ.get("DEBUG") else logging.INFO
logging.basicConfig(
    level=log_level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
setup_secure_logging()
logger = get_secure_logger(__name__)


class IssueMonitor:
    """Monitor GitHub issues and create PRs when appropriate."""

    def __init__(self):
        self.repo = os.environ.get("GITHUB_REPOSITORY")
        if not self.repo:
            logger.error(
                "GITHUB_REPOSITORY environment variable is required but not set"
            )
            raise RuntimeError("GITHUB_REPOSITORY environment variable must be set")
        self.token = get_github_token()

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
        self.actionable_labels = issue_config.get(
            "actionable_labels", ["bug", "feature", "enhancement", "fix", "improvement"]
        )
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
            try:
                all_issues = json.loads(output)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse issues JSON: {e}")
                return []

            # Filter by recent activity
            cutoff_time = datetime.now(timezone.utc) - timedelta(
                hours=self.cutoff_hours
            )
            recent_issues = []

            for issue in all_issues:
                # Check both created and updated times
                created_at = datetime.fromisoformat(
                    issue["createdAt"].replace("Z", "+00:00")
                )
                updated_at = (
                    datetime.fromisoformat(issue["updatedAt"].replace("Z", "+00:00"))
                    if "updatedAt" in issue
                    else created_at
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
            try:
                data = json.loads(output)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse comments JSON: {e}")
                return False
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

    def create_information_request_comment(
        self, issue_number: int, missing_fields: List[str]
    ) -> None:
        """Comment on issue requesting more information."""
        comment_body = (
            f"{self.agent_tag} Thank you for creating this issue! "
            "To help address it effectively, could you please provide "
            "the following additional information:\n\n"
        )

        for field in missing_fields:
            comment_body += f"- **{field.title()}**: "

            if field == "detailed description":
                comment_body += (
                    "Please provide a more detailed description of the issue\n"
                )
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

    def post_security_rejection_comment(
        self, issue_number: int, reason: Optional[str] = None
    ) -> None:
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

    def post_starting_work_comment(self, issue_number: int, branch_name: str) -> None:
        """Post a comment indicating we're starting to work on the issue."""
        comment_body = f"""{self.agent_tag} I'm starting work on this issue!

I'll analyze the requirements and create a pull request to address this issue. This typically takes a few minutes.

**What I'll do:**
1. Create a new branch: `{branch_name}`
2. Implement the requested changes
3. Run tests to ensure everything works
4. Open a pull request for review

You'll receive a notification once the PR is ready.

*This comment was generated by an AI agent automation system.*"""

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

        logger.info(f"Posted starting work comment on issue #{issue_number}")

    def post_error_comment(self, issue_number: int, error_message: str) -> None:
        """Post an error comment on the issue."""
        comment_body = (
            f"{self.agent_tag} Error\n\n"
            f"I encountered an error while processing this issue:\n\n"
            f"```\n{error_message}\n```\n\n"
            f"Please check the logs for more details.\n\n"
            f"*This comment was generated by an AI agent automation system.*"
        )

        try:
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
        except Exception as e:
            logger.error(f"Failed to post error comment: {e}")

    def should_create_pr(self, issue: Dict) -> bool:
        """Determine if we should create a PR for this issue."""
        # Check if issue is actionable (bug fix, feature request, etc.)
        labels = [label.get("name", "").lower() for label in issue.get("labels", [])]
        actionable_labels = ["bug", "feature", "enhancement", "fix", "improvement"]

        has_actionable_label = any(label in actionable_labels for label in labels)

        return has_actionable_label

    def create_pr_from_issue(self, issue: Dict, branch_name: str) -> Optional[str]:
        """Create a pull request to address the issue using Claude Code tech-lead subagent."""
        issue_number = issue["number"]
        issue_title = issue["title"]

        # First, ensure we're in the repo directory
        repo_name = self.repo.split("/")[-1]
        repo_path = Path.cwd() / repo_name

        try:
            # Clone repo if not already present
            if not repo_path.exists():
                run_gh_command(["repo", "clone", self.repo])

            # Change to repo directory
            os.chdir(repo_path)

            # Create and checkout branch
            subprocess.run(["git", "checkout", "main"], check=True)
            subprocess.run(["git", "pull", "origin", "main"], check=True)
            subprocess.run(["git", "checkout", "-b", branch_name], check=True)
            logger.info(f"Created and checked out branch: {branch_name}")

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to prepare repository: {e}")
            self.post_error_comment(
                issue_number, f"Failed to prepare repository: {str(e)}"
            )
            return None

        # Use the Claude Code tech-lead subagent to implement the feature
        try:
            logger.info(
                f"Using Claude Code tech-lead subagent to implement issue #{issue_number}"
            )
            success, output = implement_issue_with_tech_lead(issue, branch_name)

            if not success:
                logger.error(f"Tech-lead subagent failed: {output}")
                self.post_error_comment(
                    issue_number, f"Implementation failed: {output}"
                )
                return None

            logger.info("Tech-lead subagent completed implementation successfully")

            # Check if there are changes to commit
            status_result = subprocess.run(
                ["git", "status", "--porcelain"], capture_output=True, text=True
            )
            if not status_result.stdout.strip():
                logger.warning("No changes to commit")
                self.post_error_comment(
                    issue_number, "No changes were made by the implementation"
                )
                return None

            # Commit and push changes
            subprocess.run(["git", "add", "-A"], check=True)
            commit_message = f"feat: {issue_title}\n\nImplements #{issue_number}\n\n🤖 Generated with Claude Code Tech Lead"
            subprocess.run(["git", "commit", "-m", commit_message], check=True)
            subprocess.run(["git", "push", "-u", "origin", branch_name], check=True)

            # Create PR using gh CLI
            pr_body = f"""Fixes #{issue_number}

## Summary
This PR implements the feature requested in issue #{issue_number}.

## Implementation Details
Implemented using Claude Code with the tech-lead persona, focusing on:
- Architecture-first approach
- Clean, maintainable code
- Comprehensive testing
- Proper documentation

## Testing
- All tests pass
- Code follows project standards
- Documentation updated where necessary

---
*This PR was created by the AI Issue Monitor using Claude Code with the tech-lead persona.*"""

            result = subprocess.run(
                [
                    "gh",
                    "pr",
                    "create",
                    "--repo",
                    self.repo,
                    "--base",
                    "main",
                    "--head",
                    branch_name,
                    "--title",
                    f"feat: {issue_title}",
                    "--body",
                    pr_body,
                    "--assignee",
                    "@me",
                ],
                capture_output=True,
                text=True,
                check=True,
            )

            # Extract PR URL from output
            pr_url = None
            if result.stdout:
                import re

                url_match = re.search(
                    r"https://github\.com/[^\s]+/pull/\d+", result.stdout
                )
                if url_match:
                    pr_url = url_match.group(0)
                    logger.info(f"Created PR: {pr_url}")

            # Comment on issue with PR link
            if pr_url:
                comment_body = (
                    f"{self.agent_tag} I've successfully created a pull request to address "
                    f"this issue using Claude Code with the tech-lead persona!\n\n"
                    f"🔗 **Pull Request:** {pr_url}\n\n"
                    f"The PR will be reviewed by our automated review system and human reviewers.\n\n"
                    f"*This comment was generated by an AI agent automation system.*"
                )
            else:
                comment_body = (
                    f"{self.agent_tag} I've created a pull request to address "
                    "this issue using Claude Code. The PR will be reviewed by our automated "
                    "review system.\n\n"
                    "*This comment was generated by an AI agent automation system.*"
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

            logger.info(f"Created PR for issue #{issue_number}")
            return pr_url

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to create PR for issue #{issue_number}: {e}")
            if hasattr(e, "stderr") and e.stderr:
                logger.error(f"Error details: {e.stderr}")
            self.post_error_comment(issue_number, str(e))
            return None
        except Exception as e:
            logger.error(f"Unexpected error creating PR: {e}")
            self.post_error_comment(issue_number, f"Unexpected error: {str(e)}")
            return None
        except PermissionError as e:
            logger.error(
                f"Permission denied executing script for issue #{issue_number}: {e}"
            )
            return None
        except FileNotFoundError as e:
            logger.error(f"Script file not found for issue #{issue_number}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error creating PR for issue #{issue_number}: {e}")
            return None

    def process_issues(self):
        """Main process to monitor and handle issues."""
        logger.info(f"Starting issue monitoring for repository: {self.repo}")

        issues = self.get_open_issues()
        logger.info(f"Found {len(issues)} open issues")

        # Log all issue numbers for debugging
        if issues:
            issue_numbers = [issue.get("number", "?") for issue in issues]
            logger.info(f"Issue numbers: {issue_numbers}")

        for issue in issues:
            issue_number = issue["number"]

            # Fetch full comment data for this issue
            comments_output = run_gh_command(
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

            if comments_output:
                try:
                    comments_data = json.loads(comments_output)
                    issue["comments"] = comments_data.get("comments", [])
                    logger.debug(
                        f"Issue #{issue_number} has {len(issue['comments'])} comments"
                    )
                    # Log comment authors for debugging
                    if issue["comments"]:
                        authors = [
                            c.get("author", {}).get("login", "Unknown")
                            for c in issue["comments"]
                        ]
                        logger.debug(f"Comment authors: {authors}")
                except json.JSONDecodeError as e:
                    logger.error(
                        f"Failed to parse comments for issue #{issue_number}: {e}"
                    )
                    issue["comments"] = []
            else:
                logger.warning(f"No comments output for issue #{issue_number}")
                issue["comments"] = []

            # Log issue structure for debugging
            logger.debug(f"Issue structure keys: {list(issue.keys())}")
            logger.debug(f"Issue author data: {issue.get('author', 'NO AUTHOR KEY')}")

            # Check for keyword trigger from allowed user
            trigger_info = self.security_manager.check_trigger_comment(issue, "issue")

            if not trigger_info:
                logger.debug(f"Issue #{issue_number} has no valid trigger")
                continue

            action, agent, trigger_user = trigger_info

            # Check if this agent should handle this trigger
            # For now, we'll handle all triggers, but this is where agent selection would happen
            # In the future: if agent != "Claude": continue

            logger.info(
                f"Processing issue #{issue_number} triggered by {trigger_user}: [{action}][{agent}]"
            )

            # Enhanced security check with rate limiting and repository validation
            repo = self.repo

            is_allowed, rejection_reason = (
                self.security_manager.perform_full_security_check(
                    username=trigger_user,
                    action=f"issue_{action.lower()}",
                    repository=repo,
                    entity_type="issue",
                    entity_id=str(issue_number),
                )
            )

            if not is_allowed:
                # Post rejection comment with specific reason
                if not self.has_agent_comment(issue_number):
                    self.post_security_rejection_comment(issue_number, rejection_reason)
                continue

            # Skip if we've already processed this action
            # Check if we've already processed this issue
            has_comment = self.has_agent_comment(issue_number)
            force_reprocess = (
                os.environ.get("FORCE_REPROCESS", "false").lower() == "true"
            )

            if has_comment and not force_reprocess:
                logger.info(
                    f"Issue #{issue_number} already has AI agent comment - skipping"
                )
                logger.debug(f"Already processed issue #{issue_number}")
                continue
            elif has_comment and force_reprocess:
                logger.info(
                    f"Issue #{issue_number} has AI agent comment but FORCE_REPROCESS=true - proceeding"
                )
            else:
                logger.info(
                    f"Issue #{issue_number} has no AI agent comment - proceeding"
                )

            # Handle different actions
            if action.lower() in ["approved", "fix", "implement"]:
                # Analyze issue
                has_info, missing = self.analyze_issue(issue)

                if not has_info:
                    # Request more information
                    self.create_information_request_comment(issue_number, missing)
                elif self.should_create_pr(issue):
                    # Generate branch name with UUID suffix
                    uuid_suffix = str(uuid.uuid4())[:6]
                    branch_name = f"fix-issue-{issue_number}-{uuid_suffix}"

                    # Post comment that we're starting work
                    self.post_starting_work_comment(issue_number, branch_name)
                    # Create PR to address the issue
                    self.create_pr_from_issue(issue, branch_name)
                else:
                    logger.info(f"Issue #{issue_number} not actionable yet")
            elif action.lower() == "close":
                # Close the issue
                logger.info(f"Closing issue #{issue_number} as requested")
                run_gh_command(
                    ["issue", "close", str(issue_number), "--repo", self.repo]
                )
                self.create_action_comment(
                    issue_number,
                    f"Issue closed as requested by {trigger_user} using [{action}][{agent}]",
                )
            elif action.lower() == "summarize":
                # Summarize the issue
                logger.info(f"Summarizing issue #{issue_number}")
                self.create_summary_comment(issue_number, issue)
            else:
                logger.warning(f"Unknown action: {action}")

    def create_action_comment(self, issue_number: int, message: str) -> None:
        """Create a comment for an action taken."""
        comment = f"{self.agent_tag} {message}"

        run_gh_command(
            [
                "issue",
                "comment",
                str(issue_number),
                "--repo",
                self.repo,
                "--body",
                comment,
            ]
        )

    def create_summary_comment(self, issue_number: int, issue: Dict) -> None:
        """Create a summary comment for an issue."""
        title = issue.get("title", "No title")
        body = issue.get("body", "No description")
        labels = [label.get("name", "") for label in issue.get("labels", [])]

        summary = f"""{self.agent_tag} **Issue Summary:**

**Title:** {title}

**Labels:** {', '.join(labels) if labels else 'None'}

**Description Summary:** {body[:200]}{'...' if len(body) > 200 else ''}

**Status:** This issue appears to be {'actionable' if self.should_create_pr(issue) else 'informational or needs more details'}.
"""

        run_gh_command(
            [
                "issue",
                "comment",
                str(issue_number),
                "--repo",
                self.repo,
                "--body",
                summary,
            ]
        )


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
                logger.error(f"Error in monitoring loop: {e}", exc_info=True)
                time.sleep(60)  # Wait a minute before retrying
    else:
        # Run once
        monitor.process_issues()


if __name__ == "__main__":
    main()
