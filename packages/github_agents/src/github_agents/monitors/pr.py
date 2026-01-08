"""GitHub PR review monitoring with multi-agent support.

This module provides PR monitoring with two modes:
1. Trigger-based: Responds to explicit [Action][Agent] keywords from authorized users
2. Auto-response: Automatically responds to Gemini AI review feedback using agent judgement

The auto-response mode uses the AgentJudgement system to determine whether to:
- Automatically implement fixes (high confidence)
- Ask project owners for guidance (low confidence)
"""

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
from ..security.judgement import AgentJudgement, JudgementResult
from ..utils import run_gh_command, run_gh_command_async, run_git_command_async
from .base import BaseMonitor

logger = logging.getLogger(__name__)

# Patterns to detect Gemini review comments
GEMINI_REVIEW_PATTERNS = [
    r"(?:gemini|google)\s*(?:ai\s*)?(?:code\s*)?review",
    r"## (?:ai\s*)?code\s*review",
    r"automated\s*(?:code\s*)?review\s*(?:by|from)\s*gemini",
    r"\*\*gemini\s*review\*\*",
]

# Patterns to detect Codex review comments
CODEX_REVIEW_PATTERNS = [
    r"(?:codex|openai)\s*(?:ai\s*)?(?:code\s*)?review",
    r"## codex\s*(?:ai\s*)?(?:code\s*)?review",
    r"automated\s*(?:code\s*)?review\s*(?:by|from)\s*codex",
    r"\*\*codex\s*review\*\*",
    r"codex-review-marker:commit:",
]

# Marker for tracking responses to Gemini reviews
GEMINI_RESPONSE_MARKER = "<!-- ai-agent-gemini-response:{} -->"

# Marker for tracking responses to Codex reviews
CODEX_RESPONSE_MARKER = "<!-- ai-agent-codex-response:{} -->"

# Marker for tracking consolidated AI review responses
CONSOLIDATED_RESPONSE_MARKER = "<!-- ai-agent-consolidated-response:{} -->"


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
    """Monitor GitHub PRs and handle review feedback.

    This monitor supports two modes of operation:

    1. **Trigger-based mode**: Responds to explicit `[Action][Agent]` keywords
       from authorized users (defined in `.agents.yaml` allow-list).

    2. **Auto-response mode**: Automatically detects and responds to Gemini AI
       review feedback. Uses the AgentJudgement system to decide whether to:
       - Auto-fix with high confidence (security issues, formatting, linting)
       - Ask project owners for guidance (architectural changes, breaking changes)

    The auto-response mode is enabled by default and can be disabled via the
    `DISABLE_GEMINI_AUTO_RESPONSE` environment variable.
    """

    def __init__(self) -> None:
        """Initialize PR monitor."""
        super().__init__()
        self.board_manager: Optional[BoardManager] = None
        self._board_config: Optional[BoardConfig] = None
        self._init_board_manager()
        self._memory_initialized = False

        # Initialize agent judgement system with project owners from allow-list
        project_owners = list(self.security_manager.allowed_users)
        self.agent_judgement = AgentJudgement(project_owners=project_owners)

        # Auto-response to Gemini reviews (can be disabled via env var)
        self.gemini_auto_response_enabled = os.getenv("DISABLE_GEMINI_AUTO_RESPONSE", "").lower() != "true"
        if self.gemini_auto_response_enabled:
            logger.info("Gemini auto-response enabled")

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
        """Process a single PR.

        This method handles both:
        1. Trigger-based actions from authorized users ([Action][Agent] keywords)
        2. Automatic responses to Gemini AI reviews (if enabled)
        """
        pr_number = pr["number"]
        branch_name = pr.get("headRefName", "")

        # Get detailed review comments
        review_comments = self._get_review_comments(pr_number)

        # Track if we processed any trigger-based requests
        processed_trigger = False

        # Check each review comment for explicit triggers
        if review_comments:
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

                # Handle the action - "approved" action triggers implementation
                if action.lower() == "approved":
                    await self._handle_review_feedback_async(pr, comment, agent_name, branch_name)
                    processed_trigger = True

        # Process Gemini reviews automatically (if enabled and no explicit trigger was processed)
        # This ensures we don't duplicate work if an owner explicitly approved
        if self.gemini_auto_response_enabled and not processed_trigger:
            await self._process_gemini_reviews(pr, branch_name)

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

            # Validate action (consolidated: approved covers fix/implement/address)
            valid_actions = ["approved", "review", "close", "summarize", "debug"]
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

    # =========================================================================
    # Gemini Auto-Response Methods
    # =========================================================================

    def _is_gemini_review(self, comment: Dict) -> bool:
        """Check if a comment is a Gemini AI review.

        Args:
            comment: Comment dict with 'body' and 'author' keys

        Returns:
            True if this appears to be a Gemini review comment
        """
        body = comment.get("body", "")
        author = comment.get("author", "")

        # Check if from github-actions bot (Gemini reviews are posted via Actions)
        if "github-actions" not in author.lower():
            return False

        # Check for Gemini review patterns
        for pattern in GEMINI_REVIEW_PATTERNS:
            if re.search(pattern, body, re.IGNORECASE):
                return True

        return False

    def _is_codex_review(self, comment: Dict) -> bool:
        """Check if a comment is a Codex AI review.

        Args:
            comment: Comment dict with 'body' and 'author' keys

        Returns:
            True if this appears to be a Codex review comment
        """
        body = comment.get("body", "")
        author = comment.get("author", "")

        # Check if from github-actions bot (Codex reviews are posted via Actions)
        if "github-actions" not in author.lower():
            return False

        # Check for Codex review patterns
        for pattern in CODEX_REVIEW_PATTERNS:
            if re.search(pattern, body, re.IGNORECASE):
                return True

        return False

    def _is_ai_review(self, comment: Dict) -> Tuple[bool, Optional[str]]:
        """Check if a comment is an AI review (Gemini or Codex).

        Args:
            comment: Comment dict with 'body' and 'author' keys

        Returns:
            Tuple of (is_ai_review, reviewer_name) where reviewer_name is
            'gemini', 'codex', or None
        """
        if self._is_gemini_review(comment):
            return True, "gemini"
        if self._is_codex_review(comment):
            return True, "codex"
        return False, None

    def _extract_gemini_review_id(self, comment: Dict) -> str:
        """Extract a unique identifier for a Gemini review.

        Uses the comment timestamp to create a unique ID for tracking responses.

        Args:
            comment: Comment dict

        Returns:
            Unique identifier string
        """
        created_at = comment.get("createdAt", "")
        comment_id = comment.get("id", "")
        # Use timestamp + id for uniqueness
        return f"{created_at}-{comment_id}".replace(":", "-").replace("T", "-")

    def _extract_gemini_commit_sha(self, comment: Dict) -> Optional[str]:
        """Extract the commit SHA from a Gemini review marker.

        Gemini reviews include a marker like:
        <!-- gemini-review-marker:commit:aefb238 -->

        Args:
            comment: Comment dict with 'body' key

        Returns:
            Commit SHA if found, None otherwise
        """
        body = comment.get("body", "")
        # Match the Gemini review marker format
        match = re.search(r"gemini-review-marker:commit:([a-f0-9]+)", body, re.IGNORECASE)
        if match:
            return match.group(1)
        return None

    def _extract_codex_commit_sha(self, comment: Dict) -> Optional[str]:
        """Extract the commit SHA from a Codex review marker.

        Codex reviews include a marker like:
        <!-- codex-review-marker:commit:aefb238 -->

        Args:
            comment: Comment dict with 'body' key

        Returns:
            Commit SHA if found, None otherwise
        """
        body = comment.get("body", "")
        # Match the Codex review marker format
        match = re.search(r"codex-review-marker:commit:([a-f0-9]+)", body, re.IGNORECASE)
        if match:
            return match.group(1)
        return None

    def _extract_ai_review_commit_sha(self, comment: Dict, reviewer: str) -> Optional[str]:
        """Extract the commit SHA from an AI review marker.

        Args:
            comment: Comment dict with 'body' key
            reviewer: 'gemini' or 'codex'

        Returns:
            Commit SHA if found, None otherwise
        """
        if reviewer == "gemini":
            return self._extract_gemini_commit_sha(comment)
        elif reviewer == "codex":
            return self._extract_codex_commit_sha(comment)
        return None

    async def _has_responded_to_gemini_review(self, pr_number: int, review_id: str) -> bool:
        """Check if we've already responded to a Gemini review.

        Args:
            pr_number: PR number
            review_id: Unique Gemini review identifier

        Returns:
            True if already responded
        """
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
                marker = GEMINI_RESPONSE_MARKER.format(review_id)
                for comment in data.get("comments", []):
                    if marker in comment.get("body", ""):
                        return True
            except json.JSONDecodeError:
                pass

        return False

    def _extract_actionable_items(self, review_body: str) -> List[Dict[str, str]]:
        """Extract actionable items from a Gemini review.

        Parses the review comment to identify specific issues that need addressing.

        Args:
            review_body: The full review comment body

        Returns:
            List of dicts with 'issue' and 'suggestion' keys
        """
        items = []

        # Common patterns for issues in Gemini reviews
        # Pattern 1: Numbered lists (1. Issue description)
        numbered_pattern = r"^\s*\d+\.\s*(.+?)(?=\n\s*\d+\.|\n\n|$)"
        for match in re.finditer(numbered_pattern, review_body, re.MULTILINE | re.DOTALL):
            item_text = match.group(1).strip()
            if len(item_text) > 10:  # Filter out trivial items
                items.append({"issue": item_text, "suggestion": ""})

        # Pattern 2: Bullet points (- or * Issue description)
        bullet_pattern = r"^\s*[-*]\s*(.+?)(?=\n\s*[-*]|\n\n|$)"
        for match in re.finditer(bullet_pattern, review_body, re.MULTILINE | re.DOTALL):
            item_text = match.group(1).strip()
            if len(item_text) > 10 and item_text not in [i["issue"] for i in items]:
                items.append({"issue": item_text, "suggestion": ""})

        # Pattern 3: Headers with issues (### Issue Name)
        header_pattern = r"#{2,}\s*(.+?)\n([\s\S]+?)(?=\n#{2,}|\n\n\n|$)"
        for match in re.finditer(header_pattern, review_body):
            header = match.group(1).strip()
            content = match.group(2).strip()
            if any(kw in header.lower() for kw in ["issue", "problem", "error", "warning", "fix"]):
                items.append({"issue": header, "suggestion": content})

        return items

    async def _process_gemini_reviews(self, pr: Dict, branch_name: str) -> None:
        """Process unaddressed AI reviews on a PR (both Gemini and Codex).

        This method:
        1. Finds all AI review comments (Gemini and Codex)
        2. Consolidates feedback from both reviewers
        3. Uses AgentJudgement to decide action on consolidated items
        4. Either auto-fixes or asks owner for guidance

        Args:
            pr: PR data dict
            branch_name: The PR branch name
        """
        if not self.gemini_auto_response_enabled:
            return

        pr_number = pr["number"]
        review_comments = self._get_review_comments(pr_number)

        # Collect unaddressed AI reviews from both Gemini and Codex
        unaddressed_reviews: List[Tuple[Dict, str]] = []  # (comment, reviewer_name)
        gemini_review = None
        codex_review = None

        for comment in review_comments:
            is_ai, reviewer = self._is_ai_review(comment)
            if not is_ai or not reviewer:
                continue

            review_id = self._extract_gemini_review_id(comment)

            # Skip if already responded
            if await self._has_responded_to_gemini_review(pr_number, review_id):
                logger.debug("Already responded to %s review %s on PR #%s", reviewer, review_id, pr_number)
                continue

            logger.info("Found unaddressed %s review on PR #%s", reviewer.capitalize(), pr_number)
            unaddressed_reviews.append((comment, reviewer))

            # Track individual reviews for consolidation
            if reviewer == "gemini":
                gemini_review = comment
            elif reviewer == "codex":
                codex_review = comment

        if not unaddressed_reviews:
            return

        # If we have both reviews, consolidate them
        if gemini_review and codex_review:
            await self._process_consolidated_ai_reviews(pr, gemini_review, codex_review, branch_name)
        else:
            # Process individual reviews as before
            for comment, reviewer in unaddressed_reviews:
                review_id = self._extract_gemini_review_id(comment)
                actionable_items = self._extract_actionable_items(comment.get("body", ""))
                if not actionable_items:
                    logger.info("No actionable items found in %s review", reviewer)
                    await self._post_gemini_acknowledgment(
                        pr_number, review_id, f"No actionable items identified in {reviewer.capitalize()} review."
                    )
                    continue
                await self._process_gemini_actionable_items(pr, comment, actionable_items, review_id, branch_name)

    async def _process_consolidated_ai_reviews(
        self,
        pr: Dict,
        gemini_review: Dict,
        codex_review: Dict,
        branch_name: str,
    ) -> None:
        """Process consolidated feedback from both Gemini and Codex reviews.

        This method combines actionable items from both reviews, deduplicates them,
        and processes them together for a unified response.

        Args:
            pr: PR data dict
            gemini_review: Gemini review comment
            codex_review: Codex review comment
            branch_name: PR branch name
        """
        pr_number = pr["number"]

        # Extract items from both reviews
        gemini_items = self._extract_actionable_items(gemini_review.get("body", ""))
        codex_items = self._extract_actionable_items(codex_review.get("body", ""))

        logger.info(
            "Consolidating AI reviews: %d items from Gemini, %d items from Codex",
            len(gemini_items),
            len(codex_items),
        )

        # Combine items with source attribution
        consolidated_items = []
        for item in gemini_items:
            consolidated_items.append({**item, "source": "gemini"})
        for item in codex_items:
            # Check for duplicates (simple text similarity)
            is_duplicate = False
            for existing in consolidated_items:
                if self._items_are_similar(item["issue"], existing["issue"]):
                    is_duplicate = True
                    existing["source"] = "both"  # Mark as found by both reviewers
                    break
            if not is_duplicate:
                consolidated_items.append({**item, "source": "codex"})

        logger.info("Consolidated to %d unique items", len(consolidated_items))

        if not consolidated_items:
            # Post acknowledgment for both reviews
            gemini_id = self._extract_gemini_review_id(gemini_review)
            await self._post_gemini_acknowledgment(
                pr_number, gemini_id, "No actionable items identified in consolidated AI review."
            )
            return

        # Create a consolidated review ID
        gemini_id = self._extract_gemini_review_id(gemini_review)
        codex_id = self._extract_gemini_review_id(codex_review)
        consolidated_id = f"consolidated-{gemini_id}-{codex_id}"

        # Process consolidated items with full context from both reviews
        await self._process_consolidated_actionable_items(
            pr=pr,
            gemini_review=gemini_review,
            codex_review=codex_review,
            items=consolidated_items,
            consolidated_id=consolidated_id,
            branch_name=branch_name,
        )

    def _items_are_similar(self, item1: str, item2: str) -> bool:
        """Check if two actionable items are similar (potential duplicates).

        Uses simple word overlap for similarity detection.

        Args:
            item1: First item text
            item2: Second item text

        Returns:
            True if items appear to be duplicates
        """
        # Simple word overlap similarity
        words1 = set(item1.lower().split())
        words2 = set(item2.lower().split())

        # Remove common words
        common_words = {"the", "a", "an", "is", "are", "to", "in", "for", "of", "and", "or"}
        words1 -= common_words
        words2 -= common_words

        if not words1 or not words2:
            return False

        overlap = len(words1 & words2)
        similarity = overlap / min(len(words1), len(words2))
        return similarity > 0.6  # 60% word overlap threshold

    async def _process_consolidated_actionable_items(
        self,
        pr: Dict,
        gemini_review: Dict,
        codex_review: Dict,
        items: List[Dict[str, str]],
        consolidated_id: str,
        branch_name: str,
    ) -> None:
        """Process consolidated actionable items from both AI reviewers.

        Args:
            pr: PR data dict
            gemini_review: Gemini review comment
            codex_review: Codex review comment
            items: Consolidated list of actionable items with source attribution
            consolidated_id: Unique identifier for the consolidated response
            branch_name: PR branch name
        """
        pr_number = pr["number"]

        # Get context for judgement
        diff_output = await run_gh_command_async(["pr", "diff", str(pr_number), "--repo", self.repo or ""])

        context = {
            "pr_number": pr_number,
            "pr_title": pr.get("title", ""),
            "diff": diff_output[:5000] if diff_output else "",
            "branch_name": branch_name,
        }

        # Assess all items and categorize by confidence
        auto_fix_items = []
        ask_owner_items = []

        for item in items:
            result = self.agent_judgement.assess_fix(item["issue"], context)

            # Boost confidence for items found by both reviewers
            if item.get("source") == "both":
                result.confidence = min(1.0, result.confidence * 1.15)
                logger.info(
                    "Item found by both reviewers (boosted confidence=%.2f): %s",
                    result.confidence,
                    item["issue"][:50],
                )

            if result.should_auto_fix:
                auto_fix_items.append((item, result))
                logger.info(
                    "Auto-fix item [%s] (confidence=%.2f, category=%s): %s",
                    item.get("source", "unknown"),
                    result.confidence,
                    result.category.value,
                    item["issue"][:50],
                )
            else:
                ask_owner_items.append((item, result))
                logger.info(
                    "Ask owner for item [%s] (confidence=%.2f, category=%s): %s",
                    item.get("source", "unknown"),
                    result.confidence,
                    result.category.value,
                    item["issue"][:50],
                )

        # Handle auto-fix items with consolidated context
        if auto_fix_items:
            await self._auto_fix_consolidated_items(
                pr, gemini_review, codex_review, auto_fix_items, consolidated_id, branch_name
            )

        # Handle ask-owner items
        if ask_owner_items:
            await self._ask_owner_for_consolidated_items(pr_number, ask_owner_items, consolidated_id)

        # If nothing to do, post acknowledgment
        if not auto_fix_items and not ask_owner_items:
            await self._post_consolidated_acknowledgment(
                pr_number, consolidated_id, "Consolidated AI review analyzed - no changes needed."
            )

    async def _auto_fix_consolidated_items(
        self,
        pr: Dict,
        gemini_review: Dict,
        codex_review: Dict,
        items: List[Tuple[Dict[str, str], "JudgementResult"]],
        consolidated_id: str,
        branch_name: str,
    ) -> None:
        """Auto-fix items from consolidated Gemini + Codex review.

        Includes both reviews in the context for the fixing agent.

        Args:
            pr: PR data dict
            gemini_review: Gemini review comment
            codex_review: Codex review comment
            items: List of (item, judgement_result) tuples
            consolidated_id: Unique identifier for tracking
            branch_name: PR branch name
        """
        pr_number = pr["number"]

        # Security: Validate PR commit hasn't changed since reviews were posted
        gemini_sha = self._extract_gemini_commit_sha(gemini_review)
        codex_sha = self._extract_codex_commit_sha(codex_review)

        # Use the more recent SHA for validation
        expected_sha = codex_sha or gemini_sha
        if expected_sha:
            is_valid, reason = await self.security_manager.validate_pr_commit_unchanged(
                pr_number, expected_sha, self.repo or ""
            )
            if not is_valid:
                logger.warning("PR commit validation failed for PR #%s: %s", pr_number, reason)
                marker = CONSOLIDATED_RESPONSE_MARKER.format(consolidated_id)
                security_comment = (
                    f"{self.agent_tag} **Security check failed** - cannot auto-fix consolidated review items.\n\n"
                    f"**Reason**: {reason}\n\n"
                    f"This check prevents code injection attacks. "
                    f"Please re-trigger review after ensuring PR is in expected state.\n\n"
                    f"{marker}"
                )
                self._post_comment(pr_number, security_comment, "pr")
                return

        # Get the best available agent for code fixes
        agent_name = self._resolve_agent_for_pr()
        if not agent_name:
            logger.error("No agent available for auto-fix")
            return

        agent = self.agents.get(agent_name.lower())
        if not agent:
            logger.error("Agent '%s' not initialized", agent_name)
            return

        # Build items text with source attribution
        items_text = "\n".join(
            f"- [{item.get('source', 'unknown').upper()}] {item['issue']} "
            f"(Category: {result.category.value}, Confidence: {result.confidence:.0%})"
            for item, result in items
        )

        # Post starting work comment
        marker = CONSOLIDATED_RESPONSE_MARKER.format(consolidated_id)
        start_comment = (
            f"{self.agent_tag} Addressing consolidated AI review feedback (Gemini + Codex) using {agent_name}.\n\n"
            f"**Items being addressed ({len(items)} total):**\n{items_text}\n\n"
            f"This typically takes a few minutes.\n\n"
            f"*Auto-response to consolidated AI reviews.*\n"
            f"{marker}"
        )
        self._post_comment(pr_number, start_comment, "pr")

        # Build comprehensive prompt with both reviews
        gemini_body = gemini_review.get("body", "")[:2000]
        codex_body = codex_review.get("body", "")[:2000]
        diff_output = await run_gh_command_async(["pr", "diff", str(pr_number), "--repo", self.repo or ""])

        prompt = f"""Address the following issues identified by TWO AI code reviewers on PR #{pr_number}:

## Consolidated Items to Fix
{items_text}

## Gemini Review
{gemini_body}

## Codex Review
{codex_body}

## Current PR Diff
{diff_output[:5000] if diff_output else "No diff available"}

## Requirements
1. Fix all the listed issues from both reviewers
2. Items marked [BOTH] were identified by both reviewers - prioritize these
3. Maintain existing code style and patterns
4. Ensure changes don't break existing functionality
5. Focus on the specific issues identified - don't over-engineer
"""

        # Generate and apply fixes
        try:
            context = {
                "pr_number": pr_number,
                "pr_title": pr.get("title", ""),
                "branch_name": branch_name,
                "consolidated_review_id": consolidated_id,
            }

            response = await agent.generate_code(prompt, context)
            logger.info("Agent %s generated response for consolidated AI review fixes", agent.name)

            # Apply the changes
            await self._apply_consolidated_fixes(pr, agent.name, response, branch_name, consolidated_id, items)

        except Exception as e:
            logger.error("Failed to auto-fix consolidated review items: %s", e)
            error_comment = (
                f"{self.agent_tag} Attempted to auto-fix consolidated review items but encountered an error.\n\n"
                f"**Error**: {str(e)}\n\n"
                f"Please review manually or use `[Approved][Claude]` to trigger manual processing.\n\n"
                f"{marker}"
            )
            self._post_comment(pr_number, error_comment, "pr")

    async def _apply_consolidated_fixes(
        self,
        pr: Dict,
        agent_name: str,
        implementation: str,
        branch_name: str,
        consolidated_id: str,
        items: List[Tuple[Dict[str, str], "JudgementResult"]],
    ) -> None:
        """Apply fixes from agent response for consolidated review items."""
        pr_number = pr["number"]
        marker = CONSOLIDATED_RESPONSE_MARKER.format(consolidated_id)

        try:
            # Checkout the PR branch
            logger.info("Checking out PR branch: %s", branch_name)
            await run_gh_command_async(["pr", "checkout", str(pr_number), "--repo", self.repo or ""])

            # Apply code changes
            _blocks, results = CodeParser.extract_and_apply(implementation)

            if results:
                logger.info("Applied %s file changes for consolidated review fixes", len(results))

            # Check for changes
            status_output = await run_git_command_async(["status", "--porcelain"])
            if status_output and status_output.strip():
                # Build summary of sources
                sources = {"gemini": 0, "codex": 0, "both": 0}
                for item, _ in items:
                    source = item.get("source", "unknown")
                    if source in sources:
                        sources[source] += 1

                source_summary = ", ".join(f"{v} from {k}" for k, v in sources.items() if v > 0)

                commit_message = (
                    f"fix: address consolidated AI review feedback (Gemini + Codex)\n\n"
                    f"Auto-fixed by {agent_name} agent:\n"
                    f"- {len(items)} issues addressed ({source_summary})\n\n"
                    f"Generated with AI Agent Automation System (Consolidated AI Review Response)"
                )

                await run_git_command_async(["add", "-A"])
                await run_git_command_async(["commit", "-m", commit_message])
                await run_git_command_async(["push"])

                success_comment = (
                    f"{self.agent_tag} Successfully addressed consolidated AI review feedback using {agent_name}!\n\n"
                    f"**Changes committed and pushed to branch**: `{branch_name}`\n\n"
                    f"**Items addressed**: {len(items)} ({source_summary})\n\n"
                    f"Please review the automated changes.\n\n"
                    f"*Auto-response to consolidated AI reviews (Gemini + Codex).*\n"
                    f"{marker}"
                )
            else:
                success_comment = (
                    f"{self.agent_tag} Analyzed consolidated AI review feedback using {agent_name}.\n\n"
                    f"No code changes were necessary - the issues may already be addressed "
                    f"or require manual review.\n\n"
                    f"*Auto-response to consolidated AI reviews.*\n"
                    f"{marker}"
                )

            self._post_comment(pr_number, success_comment, "pr")

        except Exception as e:
            logger.error("Failed to apply consolidated fixes: %s", e)
            error_comment = (
                f"{self.agent_tag} Error applying consolidated review fixes: {str(e)}\n\nPlease review manually.\n\n{marker}"
            )
            self._post_comment(pr_number, error_comment, "pr")

    async def _ask_owner_for_consolidated_items(
        self,
        pr_number: int,
        items: List[Tuple[Dict[str, str], "JudgementResult"]],
        consolidated_id: str,
    ) -> None:
        """Ask project owner for guidance on uncertain consolidated review items."""
        marker = CONSOLIDATED_RESPONSE_MARKER.format(consolidated_id)

        # Build the question comment
        items_text = ""
        for i, (item, result) in enumerate(items, 1):
            source = item.get("source", "unknown").upper()
            items_text += f"\n### Item {i}: {result.category.value.replace('_', ' ').title()} [{source}]\n"
            items_text += f"**Issue**: {item['issue'][:200]}\n"
            items_text += f"**Confidence**: {result.confidence:.0%}\n"
            items_text += f"**Reasoning**: {result.reasoning}\n"
            if result.ask_owner_question:
                items_text += f"\n{result.ask_owner_question}\n"

        comment = (
            f"{self.agent_tag} **Guidance Needed on Consolidated AI Review Feedback (Gemini + Codex)**\n\n"
            f"The following items from the consolidated AI reviews require human decision:\n"
            f"{items_text}\n\n"
            f"---\n\n"
            f"**How to proceed:**\n"
            f"- Reply with `[Approved]` to have me implement all suggestions\n"
            f"- Reply with specific guidance for individual items\n"
            f"- Or address these items manually\n\n"
            f"*Auto-response to consolidated AI reviews - asking for guidance due to low confidence.*\n"
            f"{marker}"
        )

        self._post_comment(pr_number, comment, "pr")

    async def _post_consolidated_acknowledgment(self, pr_number: int, consolidated_id: str, message: str) -> None:
        """Post an acknowledgment comment for consolidated AI reviews."""
        marker = CONSOLIDATED_RESPONSE_MARKER.format(consolidated_id)
        comment = f"{self.agent_tag} {message}\n\n*Auto-response to consolidated AI reviews (Gemini + Codex).*\n{marker}"
        self._post_comment(pr_number, comment, "pr")

    async def _process_gemini_actionable_items(
        self,
        pr: Dict,
        review_comment: Dict,
        items: List[Dict[str, str]],
        review_id: str,
        branch_name: str,
    ) -> None:
        """Process actionable items from a Gemini review.

        Uses the AgentJudgement system to decide how to handle each item.

        Args:
            pr: PR data dict
            review_comment: The Gemini review comment
            items: List of actionable items
            review_id: Unique review identifier
            branch_name: PR branch name
        """
        pr_number = pr["number"]

        # Get context for judgement
        diff_output = await run_gh_command_async(["pr", "diff", str(pr_number), "--repo", self.repo or ""])

        context = {
            "pr_number": pr_number,
            "pr_title": pr.get("title", ""),
            "diff": diff_output[:5000] if diff_output else "",
            "branch_name": branch_name,
        }

        # Assess all items and categorize by confidence
        auto_fix_items = []
        ask_owner_items = []

        for item in items:
            result = self.agent_judgement.assess_fix(item["issue"], context)

            if result.should_auto_fix:
                auto_fix_items.append((item, result))
                logger.info(
                    "Auto-fix item (confidence=%.2f, category=%s): %s",
                    result.confidence,
                    result.category.value,
                    item["issue"][:50],
                )
            else:
                ask_owner_items.append((item, result))
                logger.info(
                    "Ask owner for item (confidence=%.2f, category=%s): %s",
                    result.confidence,
                    result.category.value,
                    item["issue"][:50],
                )

        # Handle auto-fix items
        if auto_fix_items:
            await self._auto_fix_gemini_items(pr, review_comment, auto_fix_items, review_id, branch_name)

        # Handle ask-owner items
        if ask_owner_items:
            await self._ask_owner_for_gemini_items(pr_number, ask_owner_items, review_id)

        # If nothing to do, post acknowledgment
        if not auto_fix_items and not ask_owner_items:
            await self._post_gemini_acknowledgment(pr_number, review_id, "Review analyzed - no changes needed.")

    async def _auto_fix_gemini_items(
        self,
        pr: Dict,
        review_comment: Dict,
        items: List[Tuple[Dict[str, str], JudgementResult]],
        review_id: str,
        branch_name: str,
    ) -> None:
        """Automatically fix items from Gemini review.

        Args:
            pr: PR data dict
            review_comment: The Gemini review comment
            items: List of (item, judgement_result) tuples to auto-fix
            review_id: Unique review identifier
            branch_name: PR branch name
        """
        pr_number = pr["number"]

        # Security: Validate PR commit hasn't changed since review was posted
        # This prevents TOCTOU attacks where malicious code is pushed after review
        expected_sha = self._extract_gemini_commit_sha(review_comment)
        if expected_sha:
            is_valid, reason = await self.security_manager.validate_pr_commit_unchanged(
                pr_number, expected_sha, self.repo or ""
            )
            if not is_valid:
                logger.warning(
                    "PR commit validation failed for PR #%s: %s",
                    pr_number,
                    reason,
                )
                marker = GEMINI_RESPONSE_MARKER.format(review_id)
                security_comment = (
                    f"{self.agent_tag} **Security check failed** - cannot auto-fix.\n\n"
                    f"**Reason**: {reason}\n\n"
                    f"This check prevents code injection attacks. "
                    f"Please re-trigger review after ensuring PR is in expected state.\n\n"
                    f"{marker}"
                )
                self._post_comment(pr_number, security_comment, "pr")
                return
            logger.info("PR commit validation passed for PR #%s", pr_number)
        else:
            logger.warning(
                "Could not extract commit SHA from Gemini review on PR #%s - skipping validation",
                pr_number,
            )

        # Get the best available agent for code fixes
        agent_name = self._resolve_agent_for_pr()
        if not agent_name:
            logger.error("No agent available for auto-fix")
            return

        agent = self.agents.get(agent_name.lower())
        if not agent:
            logger.error("Agent '%s' not initialized", agent_name)
            return

        # Build combined prompt for all auto-fix items
        items_text = "\n".join(
            f"- {item['issue']} (Category: {result.category.value}, Confidence: {result.confidence:.0%})"
            for item, result in items
        )

        # Post starting work comment
        marker = GEMINI_RESPONSE_MARKER.format(review_id)
        start_comment = (
            f"{self.agent_tag} Automatically addressing Gemini review feedback using {agent_name}.\n\n"
            f"**Items being addressed:**\n{items_text}\n\n"
            f"This typically takes a few minutes.\n\n"
            f"*Auto-response to Gemini AI review.*\n"
            f"{marker}"
        )
        self._post_comment(pr_number, start_comment, "pr")

        # Build implementation prompt
        review_body = review_comment.get("body", "")
        diff_output = await run_gh_command_async(["pr", "diff", str(pr_number), "--repo", self.repo or ""])

        prompt = f"""Address the following issues identified in an AI code review on PR #{pr_number}:

## Items to Fix
{items_text}

## Full Review Context
{review_body[:3000]}

## Current PR Diff
{diff_output[:5000] if diff_output else "No diff available"}

## Requirements
1. Fix all the listed issues
2. Maintain existing code style and patterns
3. Ensure changes don't break existing functionality
4. Focus on the specific issues identified - don't over-engineer
"""

        # Generate and apply fixes
        try:
            context = {
                "pr_number": pr_number,
                "pr_title": pr.get("title", ""),
                "branch_name": branch_name,
                "gemini_review_id": review_id,
            }

            response = await agent.generate_code(prompt, context)
            logger.info("Agent %s generated response for Gemini review fixes", agent.name)

            # Apply the changes using existing method
            await self._apply_gemini_fixes(pr, agent.name, response, branch_name, review_id, items)

        except Exception as e:
            logger.error("Failed to auto-fix Gemini review items: %s", e)
            error_comment = (
                f"{self.agent_tag} Attempted to auto-fix Gemini review items but encountered an error.\n\n"
                f"**Error**: {str(e)}\n\n"
                f"Please review manually or use `[Approved][Claude]` to trigger manual processing.\n\n"
                f"{marker}"
            )
            self._post_comment(pr_number, error_comment, "pr")

    async def _apply_gemini_fixes(
        self,
        pr: Dict,
        agent_name: str,
        implementation: str,
        branch_name: str,
        review_id: str,
        items: List[Tuple[Dict[str, str], JudgementResult]],
    ) -> None:
        """Apply fixes from agent response for Gemini review items.

        Args:
            pr: PR data dict
            agent_name: Name of the agent that generated fixes
            implementation: Agent's implementation response
            branch_name: PR branch name
            review_id: Unique Gemini review identifier
            items: List of (item, result) tuples that were addressed
        """
        pr_number = pr["number"]
        marker = GEMINI_RESPONSE_MARKER.format(review_id)

        try:
            # Checkout the PR branch
            logger.info("Checking out PR branch: %s", branch_name)
            await run_gh_command_async(["pr", "checkout", str(pr_number), "--repo", self.repo or ""])

            # Apply code changes
            _blocks, results = CodeParser.extract_and_apply(implementation)

            if results:
                logger.info("Applied %s file changes for Gemini review fixes", len(results))

            # Check for changes
            status_output = await run_git_command_async(["status", "--porcelain"])
            if status_output and status_output.strip():
                # Commit changes
                items_summary = ", ".join(item["issue"][:30] for item, _ in items[:3])
                if len(items) > 3:
                    items_summary += f" (+{len(items) - 3} more)"

                commit_message = (
                    f"fix: address Gemini review feedback\n\n"
                    f"Auto-fixed by {agent_name} agent:\n"
                    f"- {items_summary}\n\n"
                    f"Generated with AI Agent Automation System (Gemini Auto-Response)"
                )

                await run_git_command_async(["add", "-A"])
                await run_git_command_async(["commit", "-m", commit_message])
                await run_git_command_async(["push"])

                success_comment = (
                    f"{self.agent_tag} Successfully addressed Gemini review feedback using {agent_name}!\n\n"
                    f"**Changes committed and pushed to branch**: `{branch_name}`\n\n"
                    f"**Items addressed**: {len(items)}\n\n"
                    f"Please review the automated changes.\n\n"
                    f"*Auto-response to Gemini AI review.*\n"
                    f"{marker}"
                )
            else:
                success_comment = (
                    f"{self.agent_tag} Analyzed Gemini review feedback using {agent_name}.\n\n"
                    f"No code changes were necessary - the issues may already be addressed "
                    f"or require manual review.\n\n"
                    f"*Auto-response to Gemini AI review.*\n"
                    f"{marker}"
                )

            self._post_comment(pr_number, success_comment, "pr")

        except Exception as e:
            logger.error("Failed to apply Gemini fixes: %s", e)
            error_comment = (
                f"{self.agent_tag} Error applying Gemini review fixes: {str(e)}\n\nPlease review manually.\n\n{marker}"
            )
            self._post_comment(pr_number, error_comment, "pr")

    async def _ask_owner_for_gemini_items(
        self,
        pr_number: int,
        items: List[Tuple[Dict[str, str], JudgementResult]],
        review_id: str,
    ) -> None:
        """Ask project owner for guidance on uncertain Gemini review items.

        Args:
            pr_number: PR number
            items: List of (item, judgement_result) tuples
            review_id: Unique Gemini review identifier
        """
        marker = GEMINI_RESPONSE_MARKER.format(review_id)

        # Build the question comment
        items_text = ""
        for i, (item, result) in enumerate(items, 1):
            items_text += f"\n### Item {i}: {result.category.value.replace('_', ' ').title()}\n"
            items_text += f"**Issue**: {item['issue'][:200]}\n"
            items_text += f"**Confidence**: {result.confidence:.0%}\n"
            items_text += f"**Reasoning**: {result.reasoning}\n"
            if result.ask_owner_question:
                items_text += f"\n{result.ask_owner_question}\n"

        comment = (
            f"{self.agent_tag} **Guidance Needed on Gemini Review Feedback**\n\n"
            f"The following items from the Gemini review require human decision:\n"
            f"{items_text}\n\n"
            f"---\n\n"
            f"**How to proceed:**\n"
            f"- Reply with `[Approved]` to have me implement all suggestions\n"
            f"- Reply with specific guidance for individual items\n"
            f"- Or address these items manually\n\n"
            f"*Auto-response to Gemini AI review - asking for guidance due to low confidence.*\n"
            f"{marker}"
        )

        self._post_comment(pr_number, comment, "pr")

    async def _post_gemini_acknowledgment(self, pr_number: int, review_id: str, message: str) -> None:
        """Post an acknowledgment comment for a Gemini review.

        Args:
            pr_number: PR number
            review_id: Unique Gemini review identifier
            message: Acknowledgment message
        """
        marker = GEMINI_RESPONSE_MARKER.format(review_id)
        comment = f"{self.agent_tag} {message}\n\n*Auto-response to Gemini AI review.*\n{marker}"
        self._post_comment(pr_number, comment, "pr")

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
