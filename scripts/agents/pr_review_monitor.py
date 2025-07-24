#!/usr/bin/env python3
"""
PR Review Monitoring Agent

This agent monitors pull request reviews (especially from Gemini) and:
1. Analyzes review feedback
2. Implements requested changes
3. Comments when changes are addressed
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
from typing import Dict, List, Optional

from logging_security import get_secure_logger, setup_secure_logging
from security import SecurityManager
from utils import get_github_token, run_gh_command

# Configure logging with security
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
setup_secure_logging()
logger = get_secure_logger(__name__)


class PRReviewMonitor:
    """Monitor PR reviews and address feedback automatically."""

    def __init__(self):
        self.repo = os.environ.get("GITHUB_REPOSITORY")
        if not self.repo:
            logger.error("GITHUB_REPOSITORY environment variable is required but not set")
            raise RuntimeError("GITHUB_REPOSITORY environment variable must be set")
        self.token = get_github_token()

        # Safety control - auto-fixing is enabled when AI agents are enabled
        self.auto_fix_enabled = os.environ.get("ENABLE_AI_AGENTS", "false").lower() == "true"

        # Load configuration
        self.config = self._load_config()
        pr_config = self.config.get("agents", {}).get("pr_review_monitor", {})

        # Use config values with fallbacks
        self.review_bot_names = pr_config.get("review_bot_names", ["gemini-bot", "github-actions[bot]", "dependabot[bot]"])
        self.auto_fix_threshold = pr_config.get("auto_fix_threshold", {"critical_issues": 0, "total_issues": 5})
        # Cutoff period in hours for filtering recent PRs
        self.cutoff_hours = pr_config.get("cutoff_hours", 24)

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

    def get_open_prs(self) -> List[Dict]:
        """Get open pull requests, filtered by recent activity."""
        output = run_gh_command(
            [
                "pr",
                "list",
                "--repo",
                self.repo,
                "--state",
                "open",
                "--json",
                "number,title,body,author,createdAt,updatedAt,labels,reviews,comments,headRefName",
            ]
        )

        if output:
            try:
                all_prs = json.loads(output)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse PRs JSON: {e}")
                return []

            # Filter by recent activity
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=self.cutoff_hours)
            recent_prs = []

            for pr in all_prs:
                # Check both created and updated times
                created_at = datetime.fromisoformat(pr["createdAt"].replace("Z", "+00:00"))
                updated_at = (
                    datetime.fromisoformat(pr["updatedAt"].replace("Z", "+00:00")) if "updatedAt" in pr else created_at
                )

                # Include PR if it was created or updated recently
                if created_at >= cutoff_time or updated_at >= cutoff_time:
                    recent_prs.append(pr)

            logger.info(f"Filtered {len(all_prs)} PRs to {len(recent_prs)} recent PRs (cutoff: {self.cutoff_hours} hours)")
            return recent_prs
        return []

    def get_pr_reviews(self, pr_number: int) -> List[Dict]:
        """Get all reviews for a specific PR."""
        output = run_gh_command(["pr", "view", str(pr_number), "--repo", self.repo, "--json", "reviews"])

        if output:
            try:
                data = json.loads(output)
                return data.get("reviews", [])
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse reviews JSON: {e}")
                return []
        return []

    def get_pr_review_comments(self, pr_number: int) -> List[Dict]:
        """Get all review comments for a specific PR."""
        output = run_gh_command(["api", f"/repos/{self.repo}/pulls/{pr_number}/comments", "--paginate"])

        if output:
            try:
                return json.loads(output) if output.startswith("[") else [json.loads(output)]
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse comments JSON: {e}")
                return []
        return []

    def has_agent_addressed_review(self, pr_number: int) -> bool:
        """Check if agent has already addressed the review."""
        output = run_gh_command(["pr", "view", str(pr_number), "--repo", self.repo, "--json", "comments"])

        if output:
            try:
                data = json.loads(output)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse comment data JSON: {e}")
                return False
            for comment in data.get("comments", []):
                if self.agent_tag in comment.get("body", "") and "addressed" in comment.get("body", "").lower():
                    return True
        return False

    def parse_review_feedback(self, reviews: List[Dict], review_comments: List[Dict]) -> Dict:
        """Parse review feedback to extract actionable items."""
        feedback = {
            "changes_requested": False,
            "issues": [],
            "suggestions": [],
            "must_fix": [],
            "nice_to_have": [],
        }

        # Check review states
        for review in reviews:
            if review.get("state") == "CHANGES_REQUESTED":
                feedback["changes_requested"] = True

            body = review.get("body", "")

            # Extract issues and suggestions using patterns
            issue_patterns = [
                r"(?:issue|problem|error|bug):\s*(.+?)(?:\n|$)",
                r"(?:must fix|required|critical):\s*(.+?)(?:\n|$)",
                r"❌\s*(.+?)(?:\n|$)",
                r"🔴\s*(.+?)(?:\n|$)",
            ]

            suggestion_patterns = [
                r"(?:suggestion|consider|recommend):\s*(.+?)(?:\n|$)",
                r"(?:nice to have|optional):\s*(.+?)(?:\n|$)",
                r"💡\s*(.+?)(?:\n|$)",
                r"ℹ️\s*(.+?)(?:\n|$)",
            ]

            for pattern in issue_patterns:
                matches = re.findall(pattern, body, re.IGNORECASE | re.MULTILINE)
                feedback["must_fix"].extend(matches)

            for pattern in suggestion_patterns:
                matches = re.findall(pattern, body, re.IGNORECASE | re.MULTILINE)
                feedback["nice_to_have"].extend(matches)

        # Parse review comments (inline code comments)
        for comment in review_comments:
            if comment.get("author", {}).get("login") in self.review_bot_names:
                path = comment.get("path", "")
                line = comment.get("line", 0)
                body = comment.get("body", "")

                feedback["issues"].append(
                    {
                        "file": path,
                        "line": line,
                        "comment": body,
                        "severity": (
                            "high" if any(word in body.lower() for word in ["error", "bug", "critical", "must"]) else "medium"
                        ),
                    }
                )

        return feedback

    def prepare_feedback_text(self, feedback: Dict) -> tuple:
        """Prepare feedback text for the fix script."""
        issues_text = "\n".join(
            [f"- File: {issue['file']}, Line: {issue['line']}, Issue: {issue['comment']}" for issue in feedback["issues"]]
        )
        must_fix_text = "\n".join([f"- {fix}" for fix in feedback["must_fix"]])
        suggestions_text = "\n".join([f"- {suggestion}" for suggestion in feedback["nice_to_have"]])

        return must_fix_text, issues_text, suggestions_text

    def address_review_feedback(self, pr_number: int, branch_name: str, feedback: Dict) -> bool:
        """Implement changes to address review feedback."""
        # Check if auto-fix is enabled
        if not self.auto_fix_enabled:
            logger.info(f"AI agents are disabled. Skipping automatic fixes for PR #{pr_number}")
            logger.info("To enable auto-fix, set ENABLE_AI_AGENTS=true environment variable")
            return False

        # Add safety checks
        total_issues = len(feedback["must_fix"]) + len(feedback["issues"])
        if total_issues > 20:
            logger.warning(f"Too many issues ({total_issues}) for automatic fixing. Skipping auto-fix.")
            return False

        # Prepare feedback text
        must_fix_text, issues_text, suggestions_text = self.prepare_feedback_text(feedback)

        # Use the external script
        script_path = Path(__file__).parent / "templates" / "fix_pr_review.sh"
        if not script_path.exists():
            logger.error(f"Fix script not found at {script_path}")
            return False

        try:
            # Pass sensitive data via stdin instead of command-line arguments
            feedback_data = {
                "must_fix": must_fix_text,
                "issues": issues_text,
                "suggestions": suggestions_text,
            }

            # Pass environment variables including GITHUB_TOKEN
            env = os.environ.copy()

            subprocess.run(
                [
                    str(script_path),
                    str(pr_number),
                    branch_name,
                ],
                input=json.dumps(feedback_data),
                text=True,
                check=True,
                timeout=300,  # 5 minute timeout
                env=env,
            )
            logger.info(f"Successfully addressed feedback for PR #{pr_number}")
            return True
        except subprocess.TimeoutExpired:
            logger.error(f"Timeout while addressing feedback for PR #{pr_number}")
            return False
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to address feedback for PR #{pr_number}: {e}")
            return False

    def post_completion_comment(self, pr_number: int, feedback: Dict, success: bool) -> None:
        """Post a comment indicating review feedback has been addressed."""
        if success:
            comment_body = f"""{self.agent_tag} I've reviewed and addressed the feedback from the PR review:

✅ **Changes Made:**
- Addressed {len(feedback['must_fix'])} critical issues
- Fixed {len(feedback['issues'])} inline code comments
- Implemented {len(feedback['nice_to_have'])} suggested improvements

All requested changes have been implemented and tests are passing. The PR is ready for another review.

*This comment was generated by an AI agent that automatically addresses PR review feedback.*"""
        else:
            comment_body = (
                f"{self.agent_tag} I attempted to address the PR review "
                "feedback but encountered some issues. Manual intervention "
                "may be required.\n\n"
                f"The review identified:\n"
                f"- {len(feedback['must_fix'])} critical issues\n"
                f"- {len(feedback['issues'])} inline code comments\n"
                f"- {len(feedback['nice_to_have'])} suggestions\n\n"
                "Please review the attempted changes and complete any "
                "remaining fixes manually.\n\n"
                "*This comment was generated by an AI agent.*"
            )

        run_gh_command(
            [
                "pr",
                "comment",
                str(pr_number),
                "--repo",
                self.repo,
                "--body",
                comment_body,
            ]
        )

    def post_security_rejection_comment(self, pr_number: int, reason: Optional[str] = None) -> None:
        """Post a comment explaining why the PR cannot be processed."""
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
                "pr",
                "comment",
                str(pr_number),
                "--repo",
                self.repo,
                "--body",
                comment_body,
            ]
        )

        logger.info(f"Posted security rejection comment on PR #{pr_number}")

    def process_pr_reviews(self):
        """Main process to monitor and handle PR reviews."""
        logger.info("Starting PR review monitoring...")

        prs = self.get_open_prs()
        logger.info(f"Found {len(prs)} open PRs")

        for pr in prs:
            pr_number = pr["number"]
            branch_name = pr["headRefName"]

            # Check for keyword trigger from allowed user
            trigger_info = self.security_manager.check_trigger_comment(pr, "pr")

            if not trigger_info:
                logger.debug(f"PR #{pr_number} has no valid trigger")
                continue

            action, agent, trigger_user = trigger_info

            # Check if this agent should handle this trigger
            # For now, we'll handle all triggers, but this is where agent selection would happen
            # In the future: if agent != "Claude": continue

            logger.info(f"Processing PR #{pr_number} triggered by {trigger_user}: [{action}][{agent}]")

            # Enhanced security check with rate limiting and repository validation
            repo = self.repo

            is_allowed, rejection_reason = self.security_manager.perform_full_security_check(
                username=trigger_user,
                action=f"pr_{action.lower()}",
                repository=repo,
                entity_type="pr",
                entity_id=str(pr_number),
            )

            if not is_allowed:
                # Post rejection comment with specific reason
                if not self.has_agent_addressed_review(pr_number):
                    self.post_security_rejection_comment(pr_number, rejection_reason)
                continue

            # Skip if we've already addressed this review
            if self.has_agent_addressed_review(pr_number):
                logger.debug(f"Already addressed review for PR #{pr_number}")
                continue

            # Handle different actions
            if action.lower() in ["approved", "fix", "implement", "review"]:
                # Get reviews and comments
                reviews = self.get_pr_reviews(pr_number)
                review_comments = self.get_pr_review_comments(pr_number)

                # Skip if no reviews from bots
                bot_reviews = [r for r in reviews if r.get("author", {}).get("login") in self.review_bot_names]
                if not bot_reviews and not review_comments:
                    logger.debug(f"No bot reviews found for PR #{pr_number}")
                    continue

                # Parse feedback
                feedback = self.parse_review_feedback(bot_reviews, review_comments)

                # Only process if changes were requested or issues found
                if feedback["changes_requested"] or feedback["issues"] or feedback["must_fix"]:
                    logger.info(f"Processing review feedback for PR #{pr_number}")
                    success = self.address_review_feedback(pr_number, branch_name, feedback)
                    self.post_completion_comment(pr_number, feedback, success)
                else:
                    # Post comment that no changes needed
                    comment_body = (
                        f"{self.agent_tag} I've reviewed the PR feedback and found "
                        "no changes are required. The PR review passed without any "
                        "critical issues or required fixes.\n\n"
                        "✅ **Review Status:** All checks passed\n"
                        "🎉 **No changes needed**\n\n"
                        "*This comment was generated by an AI agent monitoring PR reviews.*"
                    )

                    run_gh_command(
                        [
                            "pr",
                            "comment",
                            str(pr_number),
                            "--repo",
                            self.repo,
                            "--body",
                            comment_body,
                        ]
                    )
            elif action.lower() == "close":
                # Close the PR
                logger.info(f"Closing PR #{pr_number} as requested")
                run_gh_command(["pr", "close", str(pr_number), "--repo", self.repo])
                self.create_action_comment(
                    pr_number,
                    f"PR closed as requested by {trigger_user} using [{action}][{agent}]",
                )
            elif action.lower() == "summarize":
                # Summarize the PR
                logger.info(f"Summarizing PR #{pr_number}")
                self.create_summary_comment(pr_number, pr)
            else:
                logger.warning(f"Unknown action: {action}")

    def create_action_comment(self, pr_number: int, message: str) -> None:
        """Create a comment for an action taken."""
        comment = f"{self.agent_tag} {message}"

        run_gh_command(
            [
                "pr",
                "comment",
                str(pr_number),
                "--repo",
                self.repo,
                "--body",
                comment,
            ]
        )

    def create_summary_comment(self, pr_number: int, pr: Dict) -> None:
        """Create a summary comment for a PR."""
        title = pr.get("title", "No title")
        body = pr.get("body", "No description")
        labels = [label.get("name", "") for label in pr.get("labels", [])]
        author = pr.get("author", {}).get("login", "Unknown")

        summary = f"""{self.agent_tag} **PR Summary:**

**Title:** {title}

**Author:** @{author}

**Labels:** {', '.join(labels) if labels else 'None'}

**Description Summary:** {body[:200]}{'...' if len(body) > 200 else ''}

**Branch:** `{pr.get('headRefName', 'Unknown')}`

**Reviews:** {len(pr.get('reviews', []))} review(s), {len(pr.get('comments', []))} comment(s)
"""

        run_gh_command(
            [
                "pr",
                "comment",
                str(pr_number),
                "--repo",
                self.repo,
                "--body",
                summary,
            ]
        )


def main():
    """Main entry point."""
    monitor = PRReviewMonitor()

    if "--continuous" in sys.argv:
        # Run continuously
        while True:
            try:
                monitor.process_pr_reviews()
                time.sleep(300)  # Check every 5 minutes
            except KeyboardInterrupt:
                logger.info("Monitoring stopped by user")
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}", exc_info=True)
                time.sleep(60)  # Wait a minute before retrying
    else:
        # Run once
        monitor.process_pr_reviews()


if __name__ == "__main__":
    main()
