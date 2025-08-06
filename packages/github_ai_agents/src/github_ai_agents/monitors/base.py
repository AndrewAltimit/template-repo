"""Base monitor class with common functionality for GitHub monitors."""

import json
import logging
import os
import time
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Type

from ..agents import ClaudeAgent, CrushAgent, GeminiAgent, OpenCodeAgent
from ..config import AgentConfig
from ..security import SecurityManager
from ..utils import get_github_token, run_gh_command

logger = logging.getLogger(__name__)


class BaseMonitor(ABC):
    """Base class for GitHub monitors with common functionality."""

    # Agent class mapping
    AGENT_MAP: Dict[str, Type[Any]] = {
        "claude": ClaudeAgent,
        "gemini": GeminiAgent,
        "opencode": OpenCodeAgent,
        "crush": CrushAgent,
    }

    # Containerized agents that require special handling
    CONTAINERIZED_AGENTS = ["opencode", "crush"]

    def __init__(self):
        """Initialize base monitor."""
        self.repo = os.environ.get("GITHUB_REPOSITORY")
        if not self.repo:
            raise RuntimeError("GITHUB_REPOSITORY environment variable must be set")

        self.token = get_github_token()
        self.config = AgentConfig()
        self.security_manager = SecurityManager(agent_config=self.config)
        self.agent_tag = "[AI Agent]"

        # Check for review-only mode
        self.review_only_mode = os.environ.get("REVIEW_ONLY_MODE", "false").lower() == "true"
        self.review_depth = os.environ.get("REVIEW_DEPTH", "standard")
        self.comment_style = os.environ.get("COMMENT_STYLE", "consolidated")

        # Override enabled agents if specified
        enabled_agents_override = os.environ.get("ENABLED_AGENTS_OVERRIDE")
        if enabled_agents_override:
            self._override_enabled_agents(enabled_agents_override)

        # Initialize available agents based on configuration
        self.agents = self._initialize_agents()

        # Filter by target numbers if specified
        self.target_issue_numbers = self._parse_target_numbers(os.environ.get("TARGET_ISSUE_NUMBERS", ""))
        self.target_pr_numbers = self._parse_target_numbers(os.environ.get("TARGET_PR_NUMBERS", ""))

    def _initialize_agents(self) -> Dict[str, Any]:
        """Initialize available AI agents based on configuration."""
        agents = {}

        # Only initialize enabled agents
        enabled_agents = self.config.get_enabled_agents()

        for agent_name in enabled_agents:
            if agent_name in self.AGENT_MAP:
                agent_class = self.AGENT_MAP[agent_name]
                try:
                    agent = agent_class(config=self.config)
                    # For containerized agents, is_available() will check if Docker is available
                    # They will automatically use docker-compose when running on host
                    if agent.is_available():
                        keyword = agent.get_trigger_keyword()
                        agents[keyword.lower()] = agent
                        logger.info(f"Initialized {keyword} agent")
                except Exception as e:
                    logger.warning(f"Failed to initialize {agent_class.__name__}: {e}")

        return agents

    def get_recent_items(self, item_type: str, hours: int = 24) -> List[Dict]:
        """Get recent items (issues or PRs) from the repository.

        Args:
            item_type: Type of item ('issue' or 'pr')
            hours: How many hours back to look for recent activity

        Returns:
            List of recent items
        """
        json_fields = self._get_json_fields(item_type)

        output = run_gh_command(
            [
                item_type,
                "list",
                "--repo",
                self.repo,
                "--state",
                "open",
                "--json",
                json_fields,
            ]
        )

        if output:
            try:
                items = json.loads(output)
                # Filter by recent activity
                cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
                recent_items = []

                for item in items:
                    # Use appropriate timestamp field
                    timestamp_field = "createdAt" if item_type == "issue" else "updatedAt"
                    timestamp = datetime.fromisoformat(item[timestamp_field].replace("Z", "+00:00"))
                    if timestamp >= cutoff:
                        recent_items.append(item)

                return recent_items
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse {item_type}s: {e}")

        return []

    @abstractmethod
    def _get_json_fields(self, item_type: str) -> str:
        """Get JSON fields to request for the item type.

        Args:
            item_type: Type of item ('issue' or 'pr')

        Returns:
            Comma-separated list of fields
        """
        pass

    def _has_agent_comment(self, item_number: int, item_type: str) -> bool:
        """Check if agent has already commented on an item.

        Args:
            item_number: Issue or PR number
            item_type: Type of item ('issue' or 'pr')

        Returns:
            True if agent has commented
        """
        output = run_gh_command(
            [
                item_type,
                "view",
                str(item_number),
                "--repo",
                self.repo,
                "--json",
                "comments",
            ]
        )

        if output:
            try:
                data = json.loads(output)
                for comment in data.get("comments", []):
                    if self.agent_tag in comment.get("body", ""):
                        return True
            except json.JSONDecodeError:
                pass

        return False

    def _post_comment(self, item_number: int, comment: str, item_type: str):
        """Post a comment to an issue or PR.

        Args:
            item_number: Issue or PR number
            comment: Comment text
            item_type: Type of item ('issue' or 'pr')
        """
        run_gh_command(
            [
                item_type,
                "comment",
                str(item_number),
                "--repo",
                self.repo,
                "--body",
                comment,
            ]
        )

    def _post_security_rejection(self, item_number: int, reason: str, item_type: str):
        """Post security rejection comment.

        Args:
            item_number: Issue or PR number
            reason: Rejection reason
            item_type: Type of item ('issue' or 'pr')
        """
        comment = (
            f"{self.agent_tag} Security Notice\n\n"
            f"This request was blocked: {reason}\n\n"
            f"{self.security_manager.reject_message}\n\n"
            f"*This is an automated security measure.*"
        )
        self._post_comment(item_number, comment, item_type)

    def _post_error_comment(self, item_number: int, error: str, item_type: str):
        """Post error comment.

        Args:
            item_number: Issue or PR number
            error: Error message
            item_type: Type of item ('issue' or 'pr')
        """
        comment = (
            f"{self.agent_tag} Error\n\n"
            f"An error occurred: {error}\n\n"
            f"*This comment was generated by the AI agent automation system.*"
        )
        self._post_comment(item_number, comment, item_type)

    def _get_agent_unavailable_error(self, agent_name: str, action_keyword: str) -> str:
        """Get error message for unavailable agent.

        Args:
            agent_name: Name of the requested agent
            action_keyword: Action keyword for the trigger (e.g., 'Approved', 'Fix')

        Returns:
            Formatted error message
        """
        if agent_name.lower() in self.CONTAINERIZED_AGENTS:
            monitor_type = self.__class__.__name__.lower().replace("monitor", "")
            return (
                f"Agent '{agent_name}' is only available in the containerized environment.\n\n"
                f"Due to authentication constraints:\n"
                f"- Claude requires host-specific authentication and must run on the host\n"
                f"- {agent_name} is containerized and not installed on the host\n\n"
                f"**Workaround**: Use one of the available host agents instead:\n"
                f"- {', '.join([f'[{action_keyword}][{k.title()}]' for k in self.agents.keys()])}\n\n"
                f"Or manually run the containerized agent:\n"
                f"```bash\n"
                f"docker-compose --profile agents run --rm openrouter-agents \\\n"
                f"  python -m github_ai_agents.cli {monitor_type}-monitor\n"
                f"```"
            )
        else:
            return f"Agent '{agent_name}' is not available. " f"Available agents: {list(self.agents.keys())}"

    @abstractmethod
    def process_items(self):
        """Process items (issues or PRs). Must be implemented by subclasses."""
        pass

    def run_continuous(self, interval: int = 300):
        """Run continuously checking for items.

        Args:
            interval: Check interval in seconds
        """
        monitor_type = self.__class__.__name__
        logger.info(f"Starting continuous {monitor_type}")

        while True:
            try:
                self.process_items()
            except KeyboardInterrupt:
                logger.info("Stopped by user")
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}", exc_info=True)

            time.sleep(interval)

    def _override_enabled_agents(self, agents_str: str):
        """Override enabled agents from environment.

        Args:
            agents_str: Comma-separated list of agent names
        """
        agent_list = [a.strip().lower() for a in agents_str.split(",") if a.strip()]
        # Temporarily modify config
        self.config.config["enabled_agents"] = agent_list

    def _parse_target_numbers(self, numbers_str: str) -> List[int]:
        """Parse comma-separated numbers string.

        Args:
            numbers_str: Comma-separated numbers

        Returns:
            List of integers
        """
        if not numbers_str:
            return []
        try:
            return [int(n.strip()) for n in numbers_str.split(",") if n.strip()]
        except ValueError:
            logger.warning(f"Invalid target numbers: {numbers_str}")
            return []

    def _should_process_item(self, item_number: int, item_type: str) -> bool:
        """Check if an item should be processed based on target filters.

        Args:
            item_number: Issue or PR number
            item_type: Type of item ('issue' or 'pr')

        Returns:
            True if item should be processed
        """
        if item_type == "issue" and self.target_issue_numbers:
            return item_number in self.target_issue_numbers
        elif item_type == "pr" and self.target_pr_numbers:
            return item_number in self.target_pr_numbers
        return True

    def _post_review_comment(self, item_number: int, agent_name: str, review_content: str, item_type: str):
        """Post a review comment from an agent.

        Args:
            item_number: Issue or PR number
            agent_name: Name of the reviewing agent
            review_content: Review content from the agent
            item_type: Type of item ('issue' or 'pr')
        """
        # Format comment based on style
        if self.comment_style == "summary":
            # Will be handled by caller to combine multiple reviews
            return review_content

        comment_header = f"{self.agent_tag} Review by {agent_name}"
        comment_footer = "\n\n*This is an automated review. No files were modified.*"

        comment = f"{comment_header}\n\n{review_content}{comment_footer}"

        # Post the comment
        self._post_comment(item_number, comment, item_type)

        return comment
