"""GitHub PR review monitoring with multi-agent support."""

import asyncio
from datetime import datetime, timedelta, timezone
import json
import logging
import os
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

from ..board.config import load_config
from ..board.manager import BoardManager
from ..board.models import BoardConfig, IssueStatus
from ..code_parser import CodeParser
from ..utils import run_gh_command, run_gh_command_async, run_git_command_async
from .base import BaseMonitor

logger = logging.getLogger(__name__)


def get_best_available_agent(agents: Dict[str, Any], priority_list: List[str]) -> Optional[str]:
    """Get the best available agent from priority list.

    Args:
        agents: Dictionary of initialized agents
        priority_list: List of agent names in priority order

    Returns:
        Agent name if found, None otherwise
    """
    for agent_name in priority_list:
        if agent_name.lower() in agents:
            return agent_name.lower()
    # Fallback to first available agent
    if agents:
        return next(iter(agents.keys()))
    return None


class PRMonitor(BaseMonitor):
    """Monitor GitHub PRs and handle review feedback."""

    def __init__(self) -> None:
        """Initialize PR monitor."""
        super().__init__()
        self.board_manager: Optional[BoardManager] = None
        self._board_config: Optional[BoardConfig] = None
        self._init_board_manager()
        self._memory_initialized = False

    def _init_board_manager(self) -> None:
        """Initialize board manager if configuration exists."""
        try:
            config_path = Path("ai-agents-board.yml")
            if config_path.exists():
                self._board_config = load_config(str(config_path))
                github_token = os.getenv("GITHUB_TOKEN")
                if github_token:
                    self.board_manager = BoardManager(config=self._board_config, github_token=github_token)
                    logger.info("Board manager initialized successfully")
                else:
                    logger.warning("GITHUB_TOKEN not set - board integration disabled")
            else:
                logger.info("Board config not found - board integration disabled")
        except Exception as e:
            logger.warning("Failed to initialize board manager: %s", e)
            self.board_manager = None

    def _resolve_agent_for_pr(self) -> Optional[str]:
        """Resolve agent for PR review feedback from config.

        Resolution order:
        1. agent_priorities.code_fixes from config
        2. First available enabled agent

        Returns:
            Agent name in lowercase, or None if no agent available
        """
        # Use code_fixes priority for PR review feedback
        priority_agents = self.config.get_agent_priority("code_fixes")
        agent_name = get_best_available_agent(self.agents, priority_agents)
        if agent_name:
            logger.info("Resolved agent '%s' from code_fixes priority config", agent_name)
            return agent_name

        # Fallback: first enabled agent
        enabled = self.config.get_enabled_agents()
        if enabled:
            agent_name = enabled[0].lower()
            logger.info("Resolved agent '%s' as fallback", agent_name)
            return agent_name

        logger.error("No agent available for PR feedback")
        return None

    def _get_json_fields(self, item_type: str) -> str:
        """Get JSON fields for PRs."""
        return "number,title,body,author,createdAt,updatedAt,reviews,comments"

    def _extract_issue_numbers(self, pr_body: str) -> List[int]:
        """Extract issue numbers from PR body.

        Matches all GitHub closing keyword variants:
        - close, closes, closed, closing
        - fix, fixes, fixed, fixing
        - resolve, resolves, resolved, resolving
        """
        import re

        # Match all verb forms + issue number
        pattern = r"\b(?:clos(?:e|es|ed|ing)|fix(?:|es|ed|ing)|resolv(?:e|es|ed|ing))\s+#(\d+)"
        matches = re.findall(pattern, pr_body, re.IGNORECASE)
        return [int(num) for num in matches]

    async def _update_board_on_pr_merge(self, pr_number: int, pr_body: str) -> None:
        """Update board status when PR is merged."""
        if not self.board_manager:
            return

        # Extract linked issue numbers
        issue_numbers = self._extract_issue_numbers(pr_body)
        if not issue_numbers:
            logger.info("No linked issues found in PR #%s", pr_number)
            return

        # Update each linked issue to Done status
        try:
            await self.board_manager.initialize()
            for issue_number in issue_numbers:
                try:
                    success = await self.board_manager.update_status(issue_number, IssueStatus.DONE)
                    if success:
                        logger.info("Updated issue #%s to Done status (PR #%s merged)", issue_number, pr_number)
                    else:
                        logger.warning("Failed to update issue #%s status on board", issue_number)
                except Exception as e:
                    logger.warning("Board update failed for issue #%s: %s", issue_number, e)
        except Exception as e:
            logger.warning("Board initialization failed: %s", e)

    def get_open_prs(self) -> List[Dict]:
        """Get open PRs from the repository."""
        output = run_gh_command(
            [
                "pr",
                "list",
                "--repo",
                self.repo or "",
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
                logger.error("Failed to parse PRs: %s", e)

        return []

    def process_items(self) -> None:
        """Process open PRs."""
        logger.info("Processing PRs for repository: %s", self.repo)

        if self.review_only_mode:
            logger.info("Running in review-only mode")

        prs = self.get_open_prs()
        logger.info("Found %s recent open PRs", len(prs))

        # Filter by target PR numbers if specified
        if self.target_pr_numbers:
            prs = [pr for pr in prs if pr["number"] in self.target_pr_numbers]
            logger.info("Filtered to %s target PRs", len(prs))

        # Process all PRs concurrently using asyncio
        if prs:
            if self.review_only_mode:
                asyncio.run(self._review_prs_async(prs))
            else:
                asyncio.run(self._process_prs_async(prs))

    async def _process_prs_async(self, prs: list) -> None:
        """Process multiple PRs concurrently."""
        # Initialize memory integration (lazy init)
        if not self._memory_initialized:
            self._memory_initialized = await self.memory.initialize()
            if self._memory_initialized:
                logger.info("Memory integration enabled for PRMonitor")

        tasks = []
        for pr in prs:
            task = self._process_single_pr_async(pr)
            tasks.append(task)

        # Run all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Log any exceptions
        for result in results:
            if isinstance(result, Exception):
                logger.error("Error processing PR: %s", result)

    async def _process_single_pr_async(self, pr: Dict) -> None:
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

            # Resolve agent if not specified in trigger
            if agent_name is None:
                agent_name = self._resolve_agent_for_pr()
                if agent_name is None:
                    error_msg = "No agent available. Please specify agent in trigger or configure agent_priorities."
                    logger.error("No agent available for PR #%s", pr_number)
                    self._post_error_comment(pr_number, error_msg, "pr")
                    continue

            logger.info("PR #%s: [%s][%s] by %s", pr_number, action, agent_name, trigger_user)

            # Security check
            is_allowed, reason = self.security_manager.perform_full_security_check(
                username=trigger_user,
                action=f"pr_{action.lower()}",
                repository=self.repo or "",
                entity_type="pr",
                entity_id=str(pr_number),
            )

            if not is_allowed:
                logger.warning("Security check failed for PR #%s: %s", pr_number, reason)
                self._post_security_rejection(pr_number, reason, "pr")
                continue

            # Check if we already responded to this specific comment
            comment_id = comment.get("id")
            if comment_id and await self._has_responded_to_comment(pr_number, comment_id):
                logger.info("Already responded to comment %s on PR #%s", comment_id, pr_number)
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
                self.repo or "",
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
                self.repo or "",
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

    def _check_review_trigger(self, comment: Dict) -> Optional[Tuple[str, Optional[str], str]]:
        """Check if comment contains a trigger command.

        Supports two formats:
        - [Action] - agent will be resolved from config
        - [Action][Agent] - explicit agent override

        Returns:
            Tuple of (action, agent_name, username) if trigger found.
            Agent may be None if not specified in trigger.
            Returns None if no valid trigger found.
        """
        body = comment.get("body", "")
        author = comment.get("author", "unknown")

        # Pattern: [Action] with optional [Agent]
        pattern = r"\[([A-Za-z]+)\](?:\[([A-Za-z]+)\])?"
        match = re.search(pattern, body, re.IGNORECASE)

        if match:
            action = match.group(1).lower()
            agent_name = match.group(2).lower() if match.group(2) else None

            # Validate action
            valid_actions = ["fix", "address", "implement", "approved"]
            if action in valid_actions:
                return (action, agent_name, author)

        return None

    async def _handle_review_feedback_async(self, pr: Dict, comment: Dict, agent_name: str, branch_name: str) -> None:
        """Handle PR review feedback with specified agent asynchronously."""
        pr_number = pr["number"]

        # Get the agent
        agent = self.agents.get(agent_name.lower())
        if not agent:
            error_msg = self._get_agent_unavailable_error(agent_name, "Fix")

            logger.error("Agent '%s' not available", agent_name)
            self._post_error_comment(pr_number, error_msg, "pr")
            return

        # Post starting work comment
        comment_id = comment.get("id", "unknown")
        self._post_starting_work_comment(pr_number, agent_name, comment_id)

        # Run implementation directly (no asyncio.run needed since we're already async)
        try:
            await self._implement_review_feedback(pr, comment, agent, branch_name)
        except Exception as e:
            logger.error("Failed to address review feedback for PR #%s: %s", pr_number, e)
            self._post_error_comment(pr_number, str(e), "pr")

    async def _implement_review_feedback(self, pr: Dict, comment: Dict, agent: Any, branch_name: str) -> None:
        """Implement review feedback using specified agent."""
        pr_number = pr["number"]
        pr_title = pr["title"]
        review_body = comment.get("body", "")

        # Build memory-enhanced context (read-only - retrieve relevant patterns)
        memory_context = await self.memory.build_context_prompt(
            task_description=f"PR: {pr_title}\nFeedback: {review_body[:500]}",
            include_patterns=True,
            include_conventions=True,
            include_similar=False,  # PR fixes don't need similar issues
        )

        # Get PR diff to understand current changes
        diff_output = await run_gh_command_async(
            [
                "pr",
                "diff",
                str(pr_number),
                "--repo",
                self.repo or "",
            ]
        )

        # Create implementation prompt with memory context
        prompt = f"""{memory_context}Address the following review feedback on PR #{pr_number}: {pr_title}

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
            logger.info("Agent %s generated response for PR #%s", agent.name, pr_number)

            # Apply the changes
            await self._apply_review_fixes(pr, agent.name, response, branch_name, context["review_comment_id"])

        except Exception as e:
            logger.error("Agent %s failed: %s", agent.name, e)
            raise

    async def _apply_review_fixes(
        self,
        pr: Dict,
        agent_name: str,
        implementation: str,
        branch_name: str,
        comment_id: str,
    ) -> None:
        """Apply review fixes to the PR branch."""
        pr_number = pr["number"]

        try:
            # 1. Fetch and checkout the PR branch
            logger.info("Checking out PR branch: %s", branch_name)
            await run_gh_command_async(["pr", "checkout", str(pr_number), "--repo", self.repo or ""])

            # 2. Apply the code changes
            # Parse and apply the code changes from the AI response
            _blocks, results = CodeParser.extract_and_apply(implementation)

            if results:
                logger.info("Applied %s file changes:", len(results))
                for filename, operation in results.items():
                    logger.info("  - %s: %s", filename, operation)
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
                logger.info("Pushing changes to branch: %s", branch_name)
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
            logger.error("Failed to apply review fixes: %s", e)
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
                self.repo or "",
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

    def _post_starting_work_comment(self, pr_number: int, agent_name: str, comment_id: str) -> None:
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

    async def _review_prs_async(self, prs: list) -> None:
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
                logger.error("Error reviewing PR: %s", result)
            elif result:
                pr_number = prs[i]["number"]
                review_results[pr_number] = result

        # Post consolidated summary if requested
        if self.comment_style == "summary" and review_results:
            self._post_consolidated_reviews(review_results, "pr")

    async def _review_single_pr_async(self, pr: Dict) -> Optional[Dict]:
        """Review a single PR without making changes."""
        pr_number = pr["number"]
        pr_title = pr["title"]
        pr_body = pr.get("body", "")

        # Check if we should process this PR
        if not self._should_process_item(pr_number, "pr"):
            return None

        # In review-only mode, skip trigger checks and review all PRs
        # No need for [COMMAND][AGENT] keywords
        logger.info("Reviewing PR #%s: %s", pr_number, pr_title)

        # Get PR diff for better context
        try:
            diff_output = await run_gh_command_async(["pr", "diff", str(pr_number), "--repo", self.repo or ""])
        except Exception as e:
            logger.warning("Failed to get PR diff: %s", e)
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

                logger.info("Getting review from %s for PR #%s", agent_name, pr_number)

                # Get review from agent
                review = await agent.review_async(review_prompt)

                if review:
                    reviews[agent_name] = review

                    # Post individual review if not using summary style
                    if self.comment_style != "summary":
                        # Generate TTS if enabled
                        formatted_review, _audio_url = await self.tts_integration.process_review_with_tts(
                            review,
                            agent_name,
                            pr_number,
                        )
                        self._post_review_comment(pr_number, agent_name.title(), formatted_review, "pr")

            except Exception as e:
                logger.error("Failed to get review from %s: %s", agent_name, e)

        return reviews

    def _post_consolidated_reviews(self, review_results: Dict, item_type: str) -> None:
        """Post consolidated review summary."""
        for item_number, reviews in review_results.items():
            if not reviews:
                continue

            # Build consolidated comment
            comment = f"{self.agent_tag} Consolidated Review\n\n"

            for agent_name, review in reviews.items():
                comment += f"## {agent_name.title()} Review\n\n{review}\n\n---\n\n"

            comment += "*This is an automated review. No files were modified.*"

            # Post the consolidated comment
            self._post_comment(item_number, comment, item_type)


def main() -> None:
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
