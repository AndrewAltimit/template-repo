"""Security manager for GitHub AI Agents."""

from datetime import datetime, timedelta
import json
import logging
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class SecurityManager:
    """Manages security for AI agent operations."""

    def __init__(self, agent_config: Optional[Any] = None, config_path: Optional[Path] = None) -> None:
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

        # Initialize allowed users from config and environment
        self._init_allowed_users()

        # Initialize allowed repositories from environment
        self._init_allowed_repositories()

    def _get_default_config(self) -> dict:
        """Get default security configuration."""
        return {
            "enabled": True,
            "allow_list": ["AndrewAltimit", "github-actions[bot]", "dependabot[bot]"],
            "rate_limit_window_minutes": 60,
            "rate_limit_max_requests": 10,
            "allowed_repositories": [],
            "reject_message": "This AI agent only processes requests from authorized users.",
            "allowed_actions": [
                "issue_approved",
                "issue_close",
                "pr_approved",
                "issue_review",
                "pr_review",
                "issue_summarize",
                "pr_summarize",
                "issue_debug",
                "pr_debug",
            ],
            "triggers": {
                "approved": ["Approved"],
                "review": ["Review"],
                "close": ["Close"],
                "summarize": ["Summarize"],
                "debug": ["Debug"],
            },
        }

    def _load_config(self, config_path: Optional[Path]) -> dict:
        """Load security configuration."""
        default_config = self._get_default_config()

        if config_path and config_path.exists():
            try:
                with open(config_path, encoding="utf-8") as f:
                    loaded_config = json.load(f)
                    return {**default_config, **loaded_config.get("security", {})}
            except Exception as e:
                logger.warning("Failed to load security config: %s", e)

        return default_config

    def _init_allowed_users(self) -> None:
        """Initialize allowed users from config and environment variables."""
        # Start with users from config
        self._allowed_users: set[str] = set(self.config["allow_list"])

        # Add users from environment variable
        env_users = os.getenv("AI_AGENT_ALLOWED_USERS", "")
        if env_users:
            self._allowed_users.update(user.strip() for user in env_users.split(",") if user.strip())

        # Add repository owner if GITHUB_REPOSITORY is set
        github_repo = os.getenv("GITHUB_REPOSITORY", "")
        if github_repo and "/" in github_repo:
            owner = github_repo.split("/")[0]
            self._allowed_users.add(owner)

    def _init_allowed_repositories(self) -> None:
        """Initialize allowed repositories from environment variables."""
        # Start with repositories from config
        config_repos = self.config.get("allowed_repositories", [])

        # Check environment variable
        env_repos = os.getenv("AI_AGENT_ALLOWED_REPOS", "")
        if env_repos:
            # Environment variable takes precedence
            self.config["allowed_repositories"] = [repo.strip() for repo in env_repos.split(",") if repo.strip()]
        elif not config_repos:
            # If no repos specified, empty list means all allowed
            self.config["allowed_repositories"] = []

    @property
    def allowed_users(self) -> set[str]:
        """Get set of allowed users."""
        return self._allowed_users

    @property
    def allowed_actions(self) -> list[str]:
        """Get list of allowed actions."""
        return list(self.config["allowed_actions"])

    @property
    def triggers(self) -> dict[str, list[str]]:
        """Get trigger patterns."""
        return dict(self.config["triggers"])

    def parse_trigger_comment(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        """Parse trigger comment and extract action and optional agent.

        Supports two formats:
        - [Action] - agent will be resolved from board or config
        - [Action][Agent] - explicit agent override

        Args:
            text: Comment text to parse

        Returns:
            Tuple of (action, agent) in lowercase. Agent may be None if not specified.
            Returns (None, None) if no valid trigger found.
        """
        if not text:
            return (None, None)

        # Pattern: [Action] with optional [Agent] - case insensitive
        pattern = r"\[([A-Za-z]+)\](?:\[([A-Za-z]+)\])?"
        match = re.search(pattern, text, re.IGNORECASE)

        if not match:
            return (None, None)

        action = match.group(1)
        agent = match.group(2)  # May be None if not specified

        # Validate action against allowed triggers (case-insensitive)
        valid_actions_lower = ["approved", "review", "close", "summarize", "debug"]
        if action.lower() not in valid_actions_lower:
            return (None, None)

        # Return lowercase (agent is None if not specified)
        return (action.lower(), agent.lower() if agent else None)

    def is_user_allowed(self, username: str) -> bool:
        """Check if user is authorized.

        Args:
            username: GitHub username

        Returns:
            True if authorized
        """
        if not self.config["enabled"]:
            return True

        return username in self._allowed_users

    def is_action_allowed(self, action: str) -> bool:
        """Check if action is allowed.

        Args:
            action: Action to check

        Returns:
            True if allowed
        """
        if not self.config["enabled"]:
            return True

        return action in self.config["allowed_actions"]

    def mask_secrets(self, text: str) -> str:
        """Mask secrets in text.

        Args:
            text: Text to mask secrets in

        Returns:
            Text with secrets masked
        """
        masked_text = text

        # Get list of environment variables to mask
        mask_vars = os.getenv("MASK_ENV_VARS", "")
        if not mask_vars:
            return masked_text

        # Mask each specified environment variable
        for var_name in mask_vars.split(","):
            var_name = var_name.strip()
            if not var_name:
                continue

            var_value = os.getenv(var_name, "")
            if var_value:
                masked_text = masked_text.replace(var_value, "***")

        return masked_text

    def get_trigger_regex(self) -> str:
        """Get regex pattern for valid triggers.

        Returns:
            Regex pattern string
        """
        # Pattern: [Action] with optional [Agent] where Action is one of the valid actions
        return r"\[(Approved|Review|Close|Summarize|Debug)\](?:\[([A-Za-z]+)\])?"

    def check_trigger_comment(self, issue_or_pr: Dict, _entity_type: str) -> Optional[Tuple[str, Optional[str], str]]:
        """Check for valid trigger in issue/PR comments.

        Args:
            issue_or_pr: Issue or PR data with comments
            _entity_type: "issue" or "pr"

        Returns:
            Tuple of (action, agent, username) if valid trigger found.
            Agent may be None if not specified in trigger (will be resolved from board).
            Returns None if no valid trigger found.
        """
        # Check issue/PR body first
        body = issue_or_pr.get("body", "")
        author = issue_or_pr.get("author", {}).get("login", "")

        action, agent = self.parse_trigger_comment(body)
        if action and self._is_user_authorized(author):
            return action, agent, author

        # Check comments
        for comment in issue_or_pr.get("comments", []):
            comment_body = comment.get("body", "")
            comment_author = comment.get("author", {}).get("login", "")

            action, agent = self.parse_trigger_comment(comment_body)
            if action and self._is_user_authorized(comment_author):
                return action, agent, comment_author

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

        return username in self._allowed_users

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

    # pylint: disable=unused-argument  # entity_type/entity_id kept for API compatibility
    def perform_full_security_check(
        self,
        username: str,
        action: str,
        repository: str,
        entity_type: str,
        entity_id: str,
    ) -> Tuple[bool, str]:
        """Perform comprehensive security check.

        Args:
            username: GitHub username
            action: Action being performed
            repository: Repository name
            entity_type: "issue" or "pr"
            entity_id: Issue/PR number

        Returns:
            Tuple of (allowed, rejection_reason) - reason is empty string if allowed
        """
        if not self.config["enabled"]:
            return True, ""

        # Check user authorization
        if not self._is_user_authorized(username):
            return False, f"User '{username}' is not authorized"

        # Check action authorization
        if not self.is_action_allowed(action):
            return False, f"Action '{action}' is not an allowed action"

        # Check repository
        if not self.is_repository_allowed(repository):
            return False, f"Repository '{repository}' is not authorized"

        # Check rate limit
        if not self.check_rate_limit(username, action):
            return False, "Rate limit exceeded"

        return True, ""

    @property
    def reject_message(self) -> str:
        """Get rejection message."""
        return str(self.config["reject_message"])
