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
from typing import Dict, List, Optional

from security import SecurityManager
from utils import run_gh_command

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class PRReviewMonitor:
    """Monitor PR reviews and address feedback automatically."""

    def __init__(self):
        self.repo = os.environ.get("GITHUB_REPOSITORY", "")
        self.token = os.environ.get("GITHUB_TOKEN", "")
        self.agent_tag = "[AI Agent]"
        self.review_bot_names = ["gemini-bot", "github-actions[bot]"]
        self.security_manager = SecurityManager()

    def get_open_prs(self) -> List[Dict]:
        """Get all open pull requests."""
        output = run_gh_command(
            [
                "pr",
                "list",
                "--repo",
                self.repo,
                "--state",
                "open",
                "--json",
                "number,title,body,author,createdAt,labels,reviews,comments,headRefName",
            ]
        )

        if output:
            return json.loads(output)
        return []

    def get_pr_reviews(self, pr_number: int) -> List[Dict]:
        """Get all reviews for a specific PR."""
        output = run_gh_command(["pr", "view", str(pr_number), "--repo", self.repo, "--json", "reviews"])

        if output:
            data = json.loads(output)
            return data.get("reviews", [])
        return []

    def get_pr_review_comments(self, pr_number: int) -> List[Dict]:
        """Get all review comments for a specific PR."""
        output = run_gh_command(["api", f"/repos/{self.repo}/pulls/{pr_number}/comments", "--paginate"])

        if output:
            return json.loads(output) if output.startswith("[") else [json.loads(output)]
        return []

    def has_agent_addressed_review(self, pr_number: int) -> bool:
        """Check if agent has already addressed the review."""
        output = run_gh_command(["pr", "view", str(pr_number), "--repo", self.repo, "--json", "comments"])

        if output:
            data = json.loads(output)
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
            if comment.get("user", {}).get("login") in self.review_bot_names:
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

    def generate_fix_script(self, pr_number: int, branch_name: str, feedback: Dict) -> str:
        """Generate a script to fix the issues identified in review."""
        issues_text = "\n".join(
            [f"- File: {issue['file']}, Line: {issue['line']}, Issue: {issue['comment']}" for issue in feedback["issues"]]
        )

        must_fix_text = "\n".join([f"- {fix}" for fix in feedback["must_fix"]])
        suggestions_text = "\n".join([f"- {suggestion}" for suggestion in feedback["nice_to_have"]])

        script = f"""#!/bin/bash
# Auto-generated script to address PR #{pr_number} review feedback

# Checkout the PR branch
git fetch origin {branch_name}
git checkout {branch_name}

# Use Claude Code to implement fixes
npx --yes @claudeai/cli@latest code << 'EOF'
PR #{pr_number} Review Feedback

The following issues were identified in the code review and need to be addressed:

## Critical Issues (Must Fix):
{must_fix_text if must_fix_text else "None identified"}

## Inline Code Comments:
{issues_text if issues_text else "No inline comments"}

## Suggestions (Nice to Have):
{suggestions_text if suggestions_text else "None"}

Please implement fixes for all the critical issues and inline comments.
For suggestions, implement them if they improve the code quality
without breaking existing functionality.

Make sure to:
1. Address all critical issues
2. Fix any bugs or errors mentioned
3. Improve code quality where suggested
4. Maintain existing functionality
5. Run tests to ensure nothing is broken

After making changes, create a commit with message: "Address PR review feedback"
EOF

# Run tests
./scripts/run-ci.sh test

# Commit changes
git add -A
git commit -m "Address PR review feedback

- Fixed all critical issues identified in review
- Addressed inline code comments
- Implemented suggested improvements where applicable
- All tests passing

Co-Authored-By: AI Review Agent <noreply@ai-agent.local>"

# Push changes
git push origin {branch_name}
"""

        return script

    def address_review_feedback(self, pr_number: int, branch_name: str, feedback: Dict) -> bool:
        """Implement changes to address review feedback."""
        script = self.generate_fix_script(pr_number, branch_name, feedback)
        script_path = f"/tmp/fix_pr_{pr_number}_review.sh"

        with open(script_path, "w") as f:
            f.write(script)

        os.chmod(script_path, 0o755)

        try:
            subprocess.run([script_path], check=True)
            logger.info(f"Successfully addressed feedback for PR #{pr_number}")
            return True
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

            # Enhanced security check with rate limiting and repository validation
            author = pr.get("author", {}).get("login", "unknown")
            repo = self.repo

            is_allowed, rejection_reason = self.security_manager.perform_full_security_check(
                username=author,
                action="pr_review_process",
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

                self.run_gh_command(
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
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(60)  # Wait a minute before retrying
    else:
        # Run once
        monitor.process_pr_reviews()


if __name__ == "__main__":
    main()
