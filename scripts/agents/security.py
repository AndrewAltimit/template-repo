#!/usr/bin/env python3
"""
Security module for AI agents
Provides allow list functionality to prevent prompt injection attacks
"""

import json
import logging
import os
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class SecurityManager:
    """Manages security for AI agents through allow lists."""

    def __init__(self, allow_list: Optional[List[str]] = None, config_path: Optional[str] = None):
        """
        Initialize security manager with allow list.

        Args:
            allow_list: List of allowed GitHub usernames. If None, loads from config/env.
            config_path: Path to config.json file
        """
        self.config_path = config_path or os.path.join(os.path.dirname(__file__), "config.json")
        self.config = self._load_config()
        self.security_config = self.config.get("security", {})
        self.enabled = self.security_config.get("enabled", True)
        self.log_violations = self.security_config.get("log_violations", True)
        self.reject_message = self.security_config.get(
            "reject_message",
            "This AI agent only processes requests from authorized users.",
        )

        # Load allow list from parameter, config, or defaults
        if allow_list:
            self.allow_list = allow_list
        elif "allow_list" in self.security_config:
            self.allow_list = self.security_config["allow_list"]
        else:
            self.allow_list = self._load_default_allow_list()

        self.repo_owner = self._get_repo_owner()

        # Always include repo owner in allow list
        if self.repo_owner and self.repo_owner not in self.allow_list:
            self.allow_list.append(self.repo_owner)

        logger.info(f"Security manager initialized. Enabled: {self.enabled}, Allow list: {self.allow_list}")

        # Rate limiting configuration
        self.rate_limit_window = self.security_config.get("rate_limit_window_minutes", 60)
        self.rate_limit_max_requests = self.security_config.get("rate_limit_max_requests", 10)
        self.rate_limit_tracker = defaultdict(list)

        # Repository validation
        self.allowed_repositories = self.security_config.get("allowed_repositories", [])
        if not self.allowed_repositories and self.repo_owner:
            # If no repositories specified, allow all repos from the owner
            self.allowed_repositories = [f"{self.repo_owner}/*"]

    def _load_config(self) -> Dict:
        """Load configuration from config.json file."""
        try:
            with open(self.config_path, "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning(f"Could not load config from {self.config_path}: {e}")
            return {}

    def _load_default_allow_list(self) -> List[str]:
        """Load default allow list from environment or defaults."""
        # Check environment variable first
        env_list = os.environ.get("AI_AGENT_ALLOW_LIST", "")
        if env_list:
            return [user.strip() for user in env_list.split(",") if user.strip()]

        # Default allow list
        return [
            "AndrewAltimit",  # Repository owner
            "github-actions[bot]",  # GitHub Actions bot
            "gemini-bot",  # Gemini review bot
            "ai-agent[bot]",  # Our AI agent bot
        ]

    def _get_repo_owner(self) -> Optional[str]:
        """Extract repository owner from GITHUB_REPOSITORY env var."""
        repo = os.environ.get("GITHUB_REPOSITORY", "")
        if repo and "/" in repo:
            return repo.split("/")[0]
        return None

    def is_user_allowed(self, username: str) -> bool:
        """
        Check if a user is in the allow list.

        Args:
            username: GitHub username to check

        Returns:
            True if user is allowed, False otherwise
        """
        # If security is disabled, allow all users (but log a warning)
        if not self.enabled:
            logger.warning("Security is disabled! All users are allowed to trigger AI agents.")
            return True

        is_allowed = username in self.allow_list

        if not is_allowed and self.log_violations:
            logger.warning(
                f"Security check failed: User '{username}' is not in allow list. "
                f"Allowed users: {', '.join(self.allow_list)}"
            )
        elif is_allowed:
            logger.debug(f"Security check passed: User '{username}' is allowed")

        return is_allowed

    def check_issue_security(self, issue: Dict) -> bool:
        """
        Check if an issue is from an allowed user.

        Args:
            issue: GitHub issue data dict

        Returns:
            True if issue author is allowed, False otherwise
        """
        author = issue.get("author", {}).get("login", "")
        if not author:
            logger.warning(f"Issue #{issue.get('number', '?')} has no author information")
            return False

        return self.is_user_allowed(author)

    def check_pr_security(self, pr: Dict) -> bool:
        """
        Check if a PR is from an allowed user.

        Args:
            pr: GitHub PR data dict

        Returns:
            True if PR author is allowed, False otherwise
        """
        author = pr.get("author", {}).get("login", "")
        if not author:
            logger.warning(f"PR #{pr.get('number', '?')} has no author information")
            return False

        return self.is_user_allowed(author)

    def check_comment_security(self, comment: Dict) -> bool:
        """
        Check if a comment is from an allowed user.

        Args:
            comment: GitHub comment data dict

        Returns:
            True if comment author is allowed, False otherwise
        """
        author = comment.get("user", {}).get("login", "")
        if not author:
            logger.warning("Comment has no author information")
            return False

        return self.is_user_allowed(author)

    def add_user_to_allow_list(self, username: str) -> None:
        """Add a user to the allow list."""
        if username not in self.allow_list:
            self.allow_list.append(username)
            logger.info(f"Added '{username}' to allow list")

    def remove_user_from_allow_list(self, username: str) -> None:
        """Remove a user from the allow list."""
        if username in self.allow_list:
            self.allow_list.remove(username)
            logger.info(f"Removed '{username}' from allow list")

    def log_security_violation(self, entity_type: str, entity_id: str, username: str) -> None:
        """
        Log a security violation for audit purposes.

        Args:
            entity_type: Type of entity (issue, pr, comment)
            entity_id: ID of the entity
            username: Username that violated security
        """
        logger.warning(
            f"SECURITY VIOLATION: Unauthorized {entity_type} #{entity_id} from user '{username}'. "
            f"AI agent will not process this {entity_type} to prevent potential prompt injection."
        )

    def check_rate_limit(self, username: str, action: str) -> Tuple[bool, Optional[str]]:
        """
        Check if a user has exceeded rate limits.

        Args:
            username: GitHub username
            action: Action being performed (e.g., "issue_create", "pr_review")

        Returns:
            Tuple of (is_allowed, rejection_reason)
        """
        if not self.enabled:
            return True, None

        current_time = datetime.now()
        window_start = current_time - timedelta(minutes=self.rate_limit_window)

        # Track requests per user and action
        key = f"{username}:{action}"

        # Clean old entries
        self.rate_limit_tracker[key] = [timestamp for timestamp in self.rate_limit_tracker[key] if timestamp > window_start]

        # Check if limit exceeded
        request_count = len(self.rate_limit_tracker[key])
        if request_count >= self.rate_limit_max_requests:
            remaining_time = min(self.rate_limit_tracker[key]) + timedelta(minutes=self.rate_limit_window) - current_time
            minutes_remaining = int(remaining_time.total_seconds() / 60)

            reason = (
                f"Rate limit exceeded: {request_count}/{self.rate_limit_max_requests} "
                f"requests in {self.rate_limit_window} minutes. "
                f"Please wait {minutes_remaining} minutes."
            )

            if self.log_violations:
                logger.warning(f"RATE LIMIT: User '{username}' exceeded limit for action '{action}'. {reason}")

            return False, reason

        # Record this request
        self.rate_limit_tracker[key].append(current_time)
        return True, None

    def check_repository(self, repository: str) -> bool:
        """
        Check if a repository is allowed.

        Args:
            repository: Repository in format "owner/repo"

        Returns:
            True if repository is allowed, False otherwise
        """
        if not self.enabled or not self.allowed_repositories:
            return True

        for allowed_repo in self.allowed_repositories:
            if allowed_repo.endswith("/*"):
                # Wildcard match for all repos from an owner
                allowed_owner = allowed_repo[:-2]
                if repository.startswith(f"{allowed_owner}/"):
                    return True
            elif repository == allowed_repo:
                return True

        if self.log_violations:
            logger.warning(
                f"Repository check failed: Repository '{repository}' is not in allowed list. "
                f"Allowed repositories: {', '.join(self.allowed_repositories)}"
            )

        return False

    def perform_full_security_check(
        self,
        username: str,
        action: str,
        repository: str,
        entity_type: str,
        entity_id: str,
    ) -> Tuple[bool, Optional[str]]:
        """
        Perform comprehensive security check.

        Args:
            username: GitHub username
            action: Action being performed
            repository: Repository name
            entity_type: Type of entity (issue, pr)
            entity_id: ID of the entity

        Returns:
            Tuple of (is_allowed, rejection_reason)
        """
        # Check if security is enabled
        if not self.enabled:
            logger.warning("Security is disabled! All actions are allowed.")
            return True, None

        # Check user allow list
        if not self.is_user_allowed(username):
            return False, f"User '{username}' is not in the allow list"

        # Check repository
        if not self.check_repository(repository):
            return False, f"Repository '{repository}' is not allowed"

        # Check rate limit
        rate_allowed, rate_reason = self.check_rate_limit(username, action)
        if not rate_allowed:
            return False, rate_reason

        logger.info(
            f"Security check passed: User '{username}' performing '{action}' "
            f"on {entity_type} #{entity_id} in repository '{repository}'"
        )

        return True, None
