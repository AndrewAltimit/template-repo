#!/usr/bin/env python3
"""
Security module for AI agents
Provides allow list functionality to prevent prompt injection attacks
"""

import fcntl
import json
import logging
import os
import re
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class SecurityManager:
    """Manages security for AI agents through allow lists and keyword triggers."""

    # Valid actions and agents for keyword triggers
    VALID_ACTIONS = [
        "Approved",
        "Close",
        "Summarize",
        "Debug",
        "Fix",
        "Implement",
        "Review",
    ]
    VALID_AGENTS = ["Claude", "Gemini"]

    # Regex pattern for keyword triggers: [Action][Agent]
    TRIGGER_PATTERN = re.compile(
        r"\[(" + "|".join(VALID_ACTIONS) + r")\]\s*\[(" + "|".join(VALID_AGENTS) + r")\]",
        re.IGNORECASE,
    )

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

        # Use a persistent file for rate limiting to work across subprocess invocations
        self.rate_limit_file = Path(tempfile.gettempdir()) / "ai_agent_rate_limits.json"
        self._ensure_rate_limit_file()

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

    def _ensure_rate_limit_file(self) -> None:
        """Ensure the rate limit file exists."""
        if not self.rate_limit_file.exists():
            try:
                self.rate_limit_file.write_text("{}")
            except Exception as e:
                logger.warning(f"Could not create rate limit file: {e}")

    def _load_rate_limits(self) -> Dict[str, List[float]]:
        """Load rate limits from persistent file with file locking."""
        try:
            with open(self.rate_limit_file, "r+") as f:
                # Acquire exclusive lock
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                try:
                    data = json.load(f)
                    # Convert timestamps back to float
                    return {k: [float(ts) for ts in v] for k, v in data.items()}
                except json.JSONDecodeError:
                    return {}
                finally:
                    # Release lock
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        except FileNotFoundError:
            self._ensure_rate_limit_file()
            return {}
        except Exception as e:
            logger.warning(f"Could not load rate limits: {e}")
            return {}

    def _save_rate_limits(self, rate_limits: Dict[str, List[float]]) -> None:
        """Save rate limits to persistent file with file locking."""
        try:
            with open(self.rate_limit_file, "w") as f:
                # Acquire exclusive lock
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                try:
                    # Convert timestamps to list for JSON serialization
                    json.dump({k: list(v) for k, v in rate_limits.items()}, f)
                finally:
                    # Release lock
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        except Exception as e:
            logger.warning(f"Could not save rate limits: {e}")

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

    def parse_keyword_trigger(self, text: str) -> Optional[Tuple[str, str]]:
        """
        Parse keyword triggers from text.

        Args:
            text: Text to parse for triggers (e.g., comment body)

        Returns:
            Tuple of (action, agent) if found, None otherwise
            Example: ("Approved", "Claude")
        """
        if not text:
            return None

        match = self.TRIGGER_PATTERN.search(text)
        if match:
            action = match.group(1)
            agent = match.group(2)
            logger.info(f"Found keyword trigger: [{action}][{agent}]")
            return (action, agent)

        return None

    def check_trigger_comment(self, issue_or_pr: Dict, entity_type: str = "issue") -> Optional[Tuple[str, str, str]]:
        """
        Check if an issue/PR has a trigger comment from an allowed user.

        Args:
            issue_or_pr: GitHub issue or PR data
            entity_type: "issue" or "pr"

        Returns:
            Tuple of (action, agent, username) if triggered, None otherwise
        """
        comments = issue_or_pr.get("comments", [])

        # Check comments in reverse order (most recent first)
        for comment in reversed(comments):
            author = comment.get("user", {}).get("login", "")

            # Skip if not from allowed user
            if not self.is_user_allowed(author):
                continue

            # Check for keyword trigger
            body = comment.get("body", "")
            trigger = self.parse_keyword_trigger(body)

            if trigger:
                action, agent = trigger
                logger.info(f"Found valid trigger from {author}: [{action}][{agent}]")
                return (action, agent, author)

        return None

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

        # Load rate limits from persistent storage
        rate_limits = self._load_rate_limits()

        # Clean old entries
        if key in rate_limits:
            rate_limits[key] = [ts for ts in rate_limits[key] if ts > window_start.timestamp()]
        else:
            rate_limits[key] = []

        # Check if limit exceeded
        request_count = len(rate_limits[key])
        if request_count >= self.rate_limit_max_requests:
            oldest_timestamp = min(rate_limits[key])
            remaining_time = (
                datetime.fromtimestamp(oldest_timestamp) + timedelta(minutes=self.rate_limit_window) - current_time
            )
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
        rate_limits[key].append(current_time.timestamp())

        # Save updated rate limits
        self._save_rate_limits(rate_limits)

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

    def check_file_path_security(self, file_path: str) -> Tuple[bool, Optional[str]]:
        """
        Check if a file path is allowed to be modified.
        Prevents agents from modifying their own code and critical system files.

        Args:
            file_path: Path to the file being modified

        Returns:
            Tuple of (is_allowed, rejection_reason)
        """
        # Normalize the path
        normalized_path = os.path.normpath(file_path)
        abs_path = os.path.abspath(normalized_path)

        # Define restricted paths and patterns
        restricted_patterns = [
            # Agent's own code
            "scripts/agents/",
            ".github/workflows/issue-monitor.yml",
            ".github/workflows/pr-review-monitor.yml",
            # Security configurations
            "scripts/agents/config.json",
            "scripts/agents/security.py",
            # Git configuration
            ".git/",
            ".gitconfig",
            # GitHub Actions workflows (partial restriction)
            ".github/workflows/runner-maintenance.yml",
            # System files
            "/etc/",
            "/usr/",
            "/bin/",
            "/sbin/",
            "/boot/",
            "/proc/",
            "/sys/",
            # Home directory configs
            "~/.ssh/",
            "~/.config/gh/",
            "~/.gitconfig",
        ]

        # Check against restricted patterns
        for pattern in restricted_patterns:
            # Expand user home directory
            expanded_pattern = os.path.expanduser(pattern)

            # Check if the path contains or starts with the restricted pattern
            if (
                pattern in normalized_path
                or normalized_path.startswith(pattern)
                or abs_path.startswith(os.path.abspath(expanded_pattern))
            ):
                logger.warning(
                    f"File path security violation: Attempt to modify restricted path '{file_path}' "
                    f"(matched pattern: '{pattern}')"
                )
                return (
                    False,
                    f"Cannot modify restricted path matching pattern '{pattern}'",
                )

        # Additional check: prevent modifying any file named security.py or config.json
        basename = os.path.basename(normalized_path)
        if basename in ["security.py", "config.json", ".gitconfig", "authorized_keys"]:
            logger.warning(f"File path security violation: Attempt to modify restricted file '{basename}'")
            return False, f"Cannot modify restricted file '{basename}'"

        # If all checks pass
        logger.debug(f"File path security check passed for: {file_path}")
        return True, None
