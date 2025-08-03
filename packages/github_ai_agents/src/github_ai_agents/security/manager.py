"""Security manager for GitHub AI Agents."""

import json
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class SecurityManager:
    """Manages security for AI agent operations."""

    def __init__(self, agent_config=None, config_path: Optional[Path] = None):
        """Initialize security manager.

        Args:
            agent_config: AgentConfig instance to use for security settings
            config_path: Path to security config file (deprecated, use agent_config)
        """
        if agent_config:
            # Use security settings from AgentConfig
            security_config = agent_config.get_security_config()
            # Merge with defaults to ensure all required keys exist
            default_config = self._get_default_config()
            self.config = {**default_config, **security_config}
        else:
            # Fallback to loading from file
            self.config = self._load_config(config_path)
        self.rate_limit_tracker: Dict[str, List[datetime]] = {}

    def _get_default_config(self) -> dict:
        """Get default security configuration."""
        return {
            "enabled": True,
            "allow_list": ["AndrewAltimit", "github-actions[bot]"],
            "rate_limit_window_minutes": 60,
            "rate_limit_max_requests": 10,
            "allowed_repositories": [],
            "reject_message": "This AI agent only processes requests from authorized users.",
        }

    def _load_config(self, config_path: Optional[Path]) -> dict:
        """Load security configuration."""
        default_config = self._get_default_config()

        if config_path and config_path.exists():
            try:
                with open(config_path) as f:
                    loaded_config = json.load(f)
                    return {**default_config, **loaded_config.get("security", {})}
            except Exception as e:
                logger.warning(f"Failed to load security config: {e}")

        return default_config

    def check_trigger_comment(self, issue_or_pr: Dict, entity_type: str) -> Optional[Tuple[str, str, str]]:
        """Check for valid trigger in issue/PR comments.

        Args:
            issue_or_pr: Issue or PR data with comments
            entity_type: "issue" or "pr"

        Returns:
            Tuple of (action, agent, username) if valid trigger found, None otherwise
        """
        # Check issue/PR body first
        body = issue_or_pr.get("body", "")
        author = issue_or_pr.get("author", {}).get("login", "")

        trigger = self._extract_trigger(body)
        if trigger and self._is_user_authorized(author):
            action, agent = trigger
            return action, agent, author

        # Check comments
        for comment in issue_or_pr.get("comments", []):
            comment_body = comment.get("body", "")
            comment_author = comment.get("author", {}).get("login", "")

            trigger = self._extract_trigger(comment_body)
            if trigger and self._is_user_authorized(comment_author):
                action, agent = trigger
                return action, agent, comment_author

        return None

    def _extract_trigger(self, text: str) -> Optional[Tuple[str, str]]:
        """Extract trigger keyword from text.

        Args:
            text: Text to search for triggers

        Returns:
            Tuple of (action, agent) if found, None otherwise
        """
        # Pattern: [Action][Agent]
        pattern = r"\[([A-Za-z]+)\]\[([A-Za-z]+)\]"
        match = re.search(pattern, text)

        if match:
            action = match.group(1)
            agent = match.group(2)

            # Validate action
            valid_actions = ["Approved", "Fix", "Implement", "Close", "Summarize"]
            if action in valid_actions:
                return action, agent

        return None

    def _is_user_authorized(self, username: str) -> bool:
        """Check if user is authorized.

        Args:
            username: GitHub username

        Returns:
            True if authorized
        """
        if not self.config["enabled"]:
            return True

        return username in self.config["allow_list"]

    def check_rate_limit(self, username: str, action: str) -> bool:
        """Check if user has exceeded rate limit.

        Args:
            username: GitHub username
            action: Action being performed

        Returns:
            True if within rate limit
        """
        if not self.config["enabled"]:
            return True

        key = f"{username}:{action}"
        now = datetime.now()
        window = timedelta(minutes=self.config["rate_limit_window_minutes"])
        max_requests = self.config["rate_limit_max_requests"]

        # Clean old entries
        if key in self.rate_limit_tracker:
            self.rate_limit_tracker[key] = [t for t in self.rate_limit_tracker[key] if now - t < window]
        else:
            self.rate_limit_tracker[key] = []

        # Check limit
        if len(self.rate_limit_tracker[key]) >= max_requests:
            return False

        # Record request
        self.rate_limit_tracker[key].append(now)
        return True

    def is_repository_allowed(self, repository: str) -> bool:
        """Check if repository is allowed.

        Args:
            repository: Repository in format "owner/repo"

        Returns:
            True if allowed
        """
        if not self.config["enabled"]:
            return True

        allowed_repos = self.config["allowed_repositories"]
        if not allowed_repos:  # Empty list means all repos allowed
            return True

        return repository in allowed_repos

    def perform_full_security_check(
        self,
        username: str,
        action: str,
        repository: str,
        entity_type: str,
        entity_id: str,
    ) -> Tuple[bool, Optional[str]]:
        """Perform comprehensive security check.

        Args:
            username: GitHub username
            action: Action being performed
            repository: Repository name
            entity_type: "issue" or "pr"
            entity_id: Issue/PR number

        Returns:
            Tuple of (allowed, rejection_reason)
        """
        if not self.config["enabled"]:
            return True, None

        # Check user authorization
        if not self._is_user_authorized(username):
            return False, f"User '{username}' is not authorized"

        # Check repository
        if not self.is_repository_allowed(repository):
            return False, f"Repository '{repository}' is not authorized"

        # Check rate limit
        if not self.check_rate_limit(username, action):
            return False, "Rate limit exceeded"

        return True, None

    @property
    def reject_message(self) -> str:
        """Get rejection message."""
        return str(self.config["reject_message"])
