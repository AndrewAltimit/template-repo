"""GitHub PR review monitoring with multi-agent support."""

import asyncio
import json
import logging
import sys
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from ..code_parser import CodeParser
from ..utils import run_gh_command, run_gh_command_async, run_git_command_async
from .base import BaseMonitor

logger = logging.getLogger(__name__)


class PRMonitor(BaseMonitor):
    """Monitor GitHub PRs and handle review feedback."""

    def __init__(self):
        """Initialize PR monitor."""
        super().__init__()

    def _get_json_fields(self, item_type: str) -> str:
        """Get JSON fields for PRs."""
        return "number,title,body,author,createdAt,updatedAt,reviews,comments"

    def get_open_prs(self) -> List[Dict]:
        """Get open PRs from the repository."""
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
                prs = json.loads(output)
                # Filter by recent activity (24 hours)
                cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
                recent_prs = []

                for pr in prs:
                    updated_at = datetime.fromisoformat(pr["updatedAt"].replace("Z", "+00:00"))
                    if updated_at >= cutoff:
                        recent_prs.append(pr)

                return recent_prs
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse PRs: {e}")

        return []

    def process_items(self):
        """Process open PRs."""
        logger.info(f"Processing PRs for repository: {self.repo}")

        if self.review_only_mode:
            logger.info("Running in review-only mode")

        prs = self.get_open_prs()
        logger.info(f"Found {len(prs)} recent open PRs")

        # Filter by target PR numbers if specified
        if self.target_pr_numbers:
            prs = [pr for pr in prs if pr["number"] in self.target_pr_numbers]
            logger.info(f"Filtered to {len(prs)} target PRs")

        # Process all PRs concurrently using asyncio
        if prs:
            if self.review_only_mode:
                asyncio.run(self._review_prs_async(prs))
            else:
                asyncio.run(self._process_prs_async(prs))

    async def _process_prs_async(self, prs):
        """Process multiple PRs concurrently."""
        tasks = []
        for pr in prs:
            task = self._process_single_pr_async(pr)
            tasks.append(task)

        # Run all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Log any exceptions
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Error processing PR: {result}")

    async def _process_single_pr_async(self, pr: Dict):
        """Process a single PR."""
        pr_number = pr["number"]
        branch_name = pr.get("headRefName", "")

        # Get detailed review comments
        review_comments = self._get_review_comments(pr_number)
        if not review_comments:
            return

        # Check each review comment for triggers
        for comment in review_comments:
            trigger_info = self._check_review_trigger(comment)
            if not trigger_info:
                continue

            action, agent_name, trigger_user = trigger_info
            logger.info(f"PR #{pr_number}: [{action}][{agent_name}] by {trigger_user}")

            # Security check
            is_allowed, reason = self.security_manager.perform_full_security_check(
                username=trigger_user,
                action=f"pr_{action.lower()}",
                repository=self.repo,
                entity_type="pr",
                entity_id=str(pr_number),
            )

            if not is_allowed:
                logger.warning(f"Security check failed for PR #{pr_number}: {reason}")
                self._post_security_rejection(pr_number, reason, "pr")
                continue

            # Check if we already responded to this specific comment
            comment_id = comment.get("id")
            if comment_id and await self._has_responded_to_comment(pr_number, comment_id):
                logger.info(f"Already responded to comment {comment_id} on PR #{pr_number}")
                continue

            # Handle the action
            if action.lower() in ["fix", "address", "implement"]:
                await self._handle_review_feedback_async(pr, comment, agent_name, branch_name)

    def _get_review_comments(self, pr_number: int) -> List[Dict]:
        """Get review comments for a PR."""
        # Get PR reviews
        reviews_output = run_gh_command(
            [
                "pr",
                "view",
                str(pr_number),
                "--repo",
                self.repo,
                "--json",
                "reviews",
            ]
        )

        # Get issue comments (PR comments)
        comments_output = run_gh_command(
            [
                "pr",
                "view",
                str(pr_number),
                "--repo",
                self.repo,
                "--json",
                "comments",
            ]
        )

        all_comments = []

        # Process reviews
        if reviews_output:
            try:
                data = json.loads(reviews_output)
                for review in data.get("reviews", []):
                    if review.get("body"):
                        all_comments.append(
                            {
                                "id": review.get("id"),
                                "body": review["body"],
                                "author": review.get("author", {}).get("login", "unknown"),
                                "createdAt": review.get("submittedAt"),
                                "type": "review",
                            }
                        )
            except json.JSONDecodeError:
                pass

        # Process comments
        if comments_output:
            try:
                data = json.loads(comments_output)
                for comment in data.get("comments", []):
                    all_comments.append(
                        {
                            "id": comment.get("id"),
                            "body": comment.get("body", ""),
                            "author": comment.get("author", {}).get("login", "unknown"),
                            "createdAt": comment.get("createdAt"),
                            "type": "comment",
                        }
                    )
            except json.JSONDecodeError:
                pass

        return all_comments

    def _check_review_trigger(self, comment: Dict) -> Optional[Tuple[str, str, str]]:
        """Check if comment contains a trigger command.

        Returns:
            Tuple of (action, agent_name, username) if trigger found, None otherwise
        """
        body = comment.get("body", "")
        author = comment.get("author", "unknown")

        # Pattern: [Action][Agent]
        import re

        pattern = r"\[(\w+)\]\[(\w+)\]"
        matches = re.findall(pattern, body)

        if matches:
            action, agent_name = matches[0]
            return (action, agent_name, author)

        return None

    async def _handle_review_feedback_async(self, pr: Dict, comment: Dict, agent_name: str, branch_name: str):
        """Handle PR review feedback with specified agent asynchronously."""
        pr_number = pr["number"]

        # Get the agent
        agent = self.agents.get(agent_name.lower())
        if not agent:
            error_msg = self._get_agent_unavailable_error(agent_name, "Fix")

            logger.error(f"Agent '{agent_name}' not available")
            self._post_error_comment(pr_number, error_msg, "pr")
            return

        # Post starting work comment
        comment_id = comment.get("id", "unknown")
        self._post_starting_work_comment(pr_number, agent_name, comment_id)

        # Run implementation directly (no asyncio.run needed since we're already async)
        try:
            await self._implement_review_feedback(pr, comment, agent, branch_name)
        except Exception as e:
            logger.error(f"Failed to address review feedback for PR #{pr_number}: {e}")
            self._post_error_comment(pr_number, str(e), "pr")

    async def _implement_review_feedback(self, pr: Dict, comment: Dict, agent, branch_name: str):
        """Implement review feedback using specified agent."""
        pr_number = pr["number"]
        pr_title = pr["title"]
        review_body = comment.get("body", "")

        # Get PR diff to understand current changes
        diff_output = await run_gh_command_async(
            [
                "pr",
                "diff",
                str(pr_number),
                "--repo",
                self.repo,
            ]
        )

        # Create implementation prompt
        prompt = f"""
Address the following review feedback on PR #{pr_number}: {pr_title}

Review Comment:
{review_body}

Current PR Diff:
{diff_output[:5000] if diff_output else "No diff available"}  # Limit diff size

Requirements:
1. Address all the specific feedback points
2. Maintain existing code style and patterns
3. Ensure changes don't break existing functionality
4. Update tests if needed
"""

        # Generate implementation
        context = {
            "pr_number": pr_number,
            "pr_title": pr_title,
            "branch_name": branch_name,
            "review_comment_id": comment.get("id"),
        }

        try:
            response = await agent.generate_code(prompt, context)
            logger.info(f"Agent {agent.name} generated response for PR #{pr_number}")

            # Apply the changes
            await self._apply_review_fixes(pr, agent.name, response, branch_name, context["review_comment_id"])

        except Exception as e:
            logger.error(f"Agent {agent.name} failed: {e}")
            raise

    async def _apply_review_fixes(
        self,
        pr: Dict,
        agent_name: str,
        implementation: str,
        branch_name: str,
        comment_id: str,
    ):
        """Apply review fixes to the PR branch."""
        pr_number = pr["number"]

        try:
            # 1. Fetch and checkout the PR branch
            logger.info(f"Checking out PR branch: {branch_name}")
            await run_gh_command_async(["pr", "checkout", str(pr_number), "--repo", self.repo])

            # 2. Apply the code changes
            # Parse and apply the code changes from the AI response
            blocks, results = CodeParser.extract_and_apply(implementation)

            if results:
                logger.info(f"Applied {len(results)} file changes:")
                for filename, operation in results.items():
                    logger.info(f"  - {filename}: {operation}")
            else:
                logger.warning("No code changes were extracted from the AI response")

            # 3. Commit the changes
            commit_message = (
                f"fix: address review feedback using {agent_name}\n\n"
                f"Automated fix generated by {agent_name} AI agent in response to review feedback.\n\n"
                f"Generated with AI Agent Automation System"
            )

            # Check if there are changes to commit
            status_output = await run_git_command_async(["status", "--porcelain"])
            if status_output and status_output.strip():
                await run_git_command_async(["add", "-A"])
                await run_git_command_async(["commit", "-m", commit_message])

                # 4. Push to the branch
                logger.info(f"Pushing changes to branch: {branch_name}")
                await run_git_command_async(["push"])

                success_comment = (
                    f"{self.agent_tag} I've successfully addressed the review feedback using {agent_name}!\n\n"
                    f"**Success**: Changes have been committed and pushed to the branch: `{branch_name}`\n\n"
                    f"Commit message: {commit_message.splitlines()[0]}\n\n"
                    f"This addresses review comment {comment_id}.\n\n"
                    f"Please review the updates.\n\n"
                    f"*This comment was generated by the AI agent automation system.*\n"
                    f"<!-- ai-agent-response-to:{comment_id} -->"
                )
            else:
                logger.info("No changes to commit")
                success_comment = (
                    f"{self.agent_tag} I've analyzed the review feedback using {agent_name}.\n\n"
                    f"ℹ️ No code changes were necessary based on the review comments.\n\n"
                    f"This addresses review comment {comment_id}.\n\n"
                    f"*This comment was generated by the AI agent automation system.*\n"
                    f"<!-- ai-agent-response-to:{comment_id} -->"
                )

        except Exception as e:
            logger.error(f"Failed to apply review fixes: {e}")
            success_comment = (
                f"{self.agent_tag} I attempted to address the review feedback using {agent_name} but encountered an error.\n\n"
                f"**Error**: {str(e)}\n\n"
                f"This was in response to review comment {comment_id}.\n\n"
                f"Please check the logs for more details.\n\n"
                f"*This comment was generated by the AI agent automation system.*\n"
                f"<!-- ai-agent-response-to:{comment_id} -->"
            )

        # Post completion comment
        self._post_comment(pr_number, success_comment, "pr")

    async def _has_responded_to_comment(self, pr_number: int, comment_id: str) -> bool:
        """Check if we've already responded to a specific comment."""
        # Get all comments on the PR
        output = await run_gh_command_async(
            [
                "pr",
                "view",
                str(pr_number),
                "--repo",
                self.repo,
                "--json",
                "comments",
            ]
        )

        if output:
            try:
                data = json.loads(output)
                # Look for agent comments with the hidden identifier
                target_id = f"<!-- ai-agent-response-to:{comment_id} -->"
                for comment in data.get("comments", []):
                    body = comment.get("body", "")
                    # Check for the hidden identifier
                    if target_id in body:
                        return True
                    # Fallback: check if this is an agent comment responding to the specific comment
                    if self.agent_tag in body and f"comment {comment_id}" in body:
                        return True
            except json.JSONDecodeError:
                pass

        return False

    def _post_starting_work_comment(self, pr_number: int, agent_name: str, comment_id: str):
        """Post starting work comment."""
        # Include a hidden identifier for robust tracking
        hidden_id = f"<!-- ai-agent-response-to:{comment_id} -->"
        comment = (
            f"{self.agent_tag} I'm working on addressing this review feedback using {agent_name}!\n\n"
            f"Responding to review comment {comment_id}.\n\n"
            f"This typically takes a few minutes.\n\n"
            f"*This comment was generated by the AI agent automation system.*\n"
            f"{hidden_id}"
        )

        self._post_comment(pr_number, comment, "pr")

    async def _review_prs_async(self, prs):
        """Review multiple PRs concurrently without making changes."""
        tasks = []
        review_results = {}

        for pr in prs:
            task = self._review_single_pr_async(pr)
            tasks.append(task)

        # Run all review tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Error reviewing PR: {result}")
            elif result:
                pr_number = prs[i]["number"]
                review_results[pr_number] = result

        # Post consolidated summary if requested
        if self.comment_style == "summary" and review_results:
            self._post_consolidated_reviews(review_results, "pr")

    async def _review_single_pr_async(self, pr: Dict):
        """Review a single PR without making changes."""
        pr_number = pr["number"]
        pr_title = pr["title"]
        pr_body = pr.get("body", "")

        # Check if we should process this PR
        if not self._should_process_item(pr_number, "pr"):
            return None

        # In review-only mode, skip trigger checks and review all PRs
        # No need for [COMMAND][AGENT] keywords
        logger.info(f"Reviewing PR #{pr_number}: {pr_title}")

        # Get PR diff for better context
        try:
            diff_output = await run_gh_command_async(["pr", "diff", str(pr_number), "--repo", self.repo])
        except Exception as e:
            logger.warning(f"Failed to get PR diff: {e}")
            diff_output = ""

        # Collect reviews from all enabled agents
        reviews = {}

        for agent_name, agent in self.agents.items():
            try:
                # Create review prompt
                # Safely handle diff_output
                diff_preview = ""
                if diff_output:
                    diff_preview = diff_output[:5000]
                    if len(diff_output) > 5000:
                        diff_preview += "..."

                review_prompt = f"""Review the following GitHub Pull Request and provide feedback:

PR #{pr_number}: {pr_title}

Description:
{pr_body}

Changes (diff):
{diff_preview}

Provide a {self.review_depth} review with:
1. Summary of the changes
2. Code quality assessment
3. Potential issues or bugs
4. Suggestions for improvement
5. Security considerations

Do not provide implementation code. Focus on review feedback only."""

                logger.info(f"Getting review from {agent_name} for PR #{pr_number}")

                # Get review from agent
                review = await agent.review_async(review_prompt)

                if review:
                    reviews[agent_name] = review

                    # Post individual review if not using summary style
                    if self.comment_style != "summary":
                        self._post_review_comment(pr_number, agent_name.title(), review, "pr")

            except Exception as e:
                logger.error(f"Failed to get review from {agent_name}: {e}")

        return reviews


def main():
    """Main entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    monitor = PRMonitor()

    if "--continuous" in sys.argv:
        monitor.run_continuous()
    else:
        monitor.process_items()


if __name__ == "__main__":
    main()
