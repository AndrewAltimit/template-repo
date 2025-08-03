"""Base monitor class with common functionality for GitHub monitors."""

import json
import logging
import os
import time
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Type

from ..agents import ClaudeAgent, CodexAgent, CrushAgent, GeminiAgent, OpenCodeAgent
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
        "codex": CodexAgent,
        "crush": CrushAgent,
    }

    # Containerized agents that require special handling
    CONTAINERIZED_AGENTS = ["opencode", "codex", "crush"]

    def __init__(self):
        """Initialize base monitor."""
        self.repo = os.environ.get("GITHUB_REPOSITORY")
        if not self.repo:
            raise RuntimeError("GITHUB_REPOSITORY environment variable must be set")

        self.token = get_github_token()
        self.config = AgentConfig()
        self.security_manager = SecurityManager(agent_config=self.config)
        self.agent_tag = "[AI Agent]"

        # Initialize available agents based on configuration
        self.agents = self._initialize_agents()

    def _initialize_agents(self) -> Dict[str, Any]:
        """Initialize available AI agents based on configuration."""
        agents = {}

        # Check if we're running in a containerized environment
        # When running on host (e.g., GitHub Actions), we should skip containerized agents
        running_in_container = os.environ.get("RUNNING_IN_CONTAINER", "false").lower() == "true"

        # Only initialize enabled agents
        enabled_agents = self.config.get_enabled_agents()

        for agent_name in enabled_agents:
            if agent_name in self.AGENT_MAP:
                # Skip containerized agents if not running in container
                if not running_in_container and agent_name in self.CONTAINERIZED_AGENTS:
                    logger.info(f"Skipping containerized agent '{agent_name}' (running on host)")
                    continue

                agent_class = self.AGENT_MAP[agent_name]
                try:
                    agent = agent_class(config=self.config)
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
