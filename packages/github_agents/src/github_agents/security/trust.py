"""Trust-level bucketing for GitHub comments.

This module provides utilities for categorizing comments by author trust level
based on the security configuration in .agents.yaml.

Trust levels (in order of authority):
- ADMIN: agent_admins - users authorized to direct agent implementation
- TRUSTED: trusted_sources - vetted automation and bots (excludes admins)
- COMMUNITY: all other commenters - consider but verify

Usage:
    from github_agents.security.trust import TrustBucketer, TrustLevel

    bucketer = TrustBucketer()  # Loads from .agents.yaml
    buckets = bucketer.bucket_comments(comments)

    for comment in buckets[TrustLevel.ADMIN]:
        print(f"Admin guidance from {comment['author']}")
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import re
from typing import Any, Dict, List, Optional

import yaml


class TrustLevel(Enum):
    """Trust levels for comment authors."""

    ADMIN = "admin"  # agent_admins - highest authority
    TRUSTED = "trusted"  # trusted_sources - vetted automation
    COMMUNITY = "community"  # everyone else


@dataclass
class TrustConfig:
    """Configuration for trust-level determination."""

    agent_admins: List[str] = field(default_factory=list)
    trusted_sources: List[str] = field(default_factory=list)

    @classmethod
    def from_yaml(cls, config_path: Optional[Path] = None) -> "TrustConfig":
        """Load trust configuration from .agents.yaml.

        Args:
            config_path: Path to config file. If None, searches for .agents.yaml.

        Returns:
            TrustConfig with loaded values or defaults.
        """
        if config_path is None:
            # Search for .agents.yaml from current directory up
            current_dir = Path.cwd()
            while current_dir != current_dir.parent:
                potential_config = current_dir / ".agents.yaml"
                if potential_config.exists():
                    config_path = potential_config
                    break
                current_dir = current_dir.parent

        if config_path is None or not config_path.exists():
            return cls()

        try:
            with open(config_path, encoding="utf-8") as f:
                config = yaml.safe_load(f)
                if not config:
                    return cls()

                security = config.get("security", {})
                return cls(
                    agent_admins=security.get("agent_admins", []),
                    trusted_sources=security.get("trusted_sources", []),
                )
        except Exception:
            return cls()


class TrustBucketer:
    """Buckets comments by author trust level."""

    # Patterns for automated noise that should be filtered out
    NOISE_PATTERNS = [
        # Agent claim comments
        re.compile(r"^🤖 \*\*\[Agent Claim\]\*\*"),
        # Simple approval triggers (just "[Approved][Agent]" with no other content)
        re.compile(r"^\[Approved\]\[[^\]]+\]$"),
    ]

    def __init__(
        self,
        config: Optional[TrustConfig] = None,
        config_path: Optional[Path] = None,
    ):
        """Initialize the bucketer.

        Args:
            config: Pre-loaded TrustConfig. If None, loads from config_path.
            config_path: Path to .agents.yaml. If None, searches automatically.
        """
        if config is not None:
            self.config = config
        else:
            self.config = TrustConfig.from_yaml(config_path)

        # Build lookup sets for efficient membership testing
        # Note: Admin users appear in agent_admins but may also be in trusted_sources
        # We check admin first, so they get ADMIN level, not TRUSTED
        self._admins = set(self.config.agent_admins)
        self._trusted = set(self.config.trusted_sources) - self._admins

    def get_trust_level(self, username: str) -> TrustLevel:
        """Determine the trust level for a username.

        Args:
            username: GitHub username to check.

        Returns:
            TrustLevel for the user.
        """
        if username in self._admins:
            return TrustLevel.ADMIN
        if username in self._trusted:
            return TrustLevel.TRUSTED
        return TrustLevel.COMMUNITY

    def is_noise(self, body: str) -> bool:
        """Check if a comment body is automated noise.

        Args:
            body: Comment body text.

        Returns:
            True if the comment should be filtered out.
        """
        if not body:
            return True

        for pattern in self.NOISE_PATTERNS:
            if pattern.match(body.strip()):
                return True

        return False

    def bucket_comments(
        self,
        comments: List[Dict[str, Any]],
        filter_noise: bool = True,
    ) -> Dict[TrustLevel, List[Dict[str, Any]]]:
        """Bucket comments by author trust level.

        Args:
            comments: List of comment dicts with 'author' and 'body' keys.
                     Author can be a string or dict with 'login' key.
            filter_noise: If True, filter out automated noise comments.

        Returns:
            Dict mapping TrustLevel to list of comments.
        """
        buckets: Dict[TrustLevel, List[Dict[str, Any]]] = {
            TrustLevel.ADMIN: [],
            TrustLevel.TRUSTED: [],
            TrustLevel.COMMUNITY: [],
        }

        for comment in comments:
            body = comment.get("body", "")

            # Skip noise if filtering enabled
            if filter_noise and self.is_noise(body):
                continue

            # Extract author username
            author = comment.get("author", {})
            if isinstance(author, str):
                username = author
            else:
                username = author.get("login", "unknown")

            # Determine trust level and bucket
            trust_level = self.get_trust_level(username)
            buckets[trust_level].append(comment)

        return buckets

    def format_bucketed_comments(
        self,
        comments: List[Dict[str, Any]],
        filter_noise: bool = True,
        include_empty_buckets: bool = False,
    ) -> str:
        """Bucket comments and format as markdown.

        Args:
            comments: List of comment dicts.
            filter_noise: If True, filter out automated noise.
            include_empty_buckets: If True, include headers for empty buckets.

        Returns:
            Formatted markdown string with comments bucketed by trust level.
        """
        buckets = self.bucket_comments(comments, filter_noise=filter_noise)
        output_parts: List[str] = []

        # Admin guidance (highest trust)
        if buckets[TrustLevel.ADMIN] or include_empty_buckets:
            if buckets[TrustLevel.ADMIN]:
                output_parts.append("## Admin Guidance (Highest Trust)\n")
                output_parts.append("Comments from repository administrators with authority to direct implementation:\n\n")
                for comment in buckets[TrustLevel.ADMIN]:
                    output_parts.append(self._format_comment(comment))

        # Trusted context (medium trust)
        if buckets[TrustLevel.TRUSTED] or include_empty_buckets:
            if buckets[TrustLevel.TRUSTED]:
                output_parts.append("## Trusted Context (Medium Trust)\n")
                output_parts.append("Comments from trusted automation and vetted sources:\n\n")
                for comment in buckets[TrustLevel.TRUSTED]:
                    output_parts.append(self._format_comment(comment))

        # Community input (review carefully)
        if buckets[TrustLevel.COMMUNITY] or include_empty_buckets:
            if buckets[TrustLevel.COMMUNITY]:
                output_parts.append("## Community Input (Review Carefully)\n")
                output_parts.append("Comments from other sources - consider but verify:\n\n")
                for comment in buckets[TrustLevel.COMMUNITY]:
                    output_parts.append(self._format_comment(comment))

        return "".join(output_parts).rstrip("\n-")

    def _format_comment(self, comment: Dict[str, Any]) -> str:
        """Format a single comment as markdown.

        Args:
            comment: Comment dict with author, body, and optionally createdAt.

        Returns:
            Formatted markdown string.
        """
        author = comment.get("author", {})
        if isinstance(author, str):
            username = author
        else:
            username = author.get("login", "unknown")

        created_at = comment.get("createdAt", "")
        date = created_at[:10] if created_at else "unknown date"
        body = comment.get("body", "")

        return f"### {username} ({date})\n\n{body}\n\n---\n\n"


def bucket_comments_for_context(
    comments: List[Dict[str, Any]],
    config_path: Optional[Path] = None,
) -> str:
    """Convenience function to bucket and format comments for agent context.

    Args:
        comments: List of comment dicts from GitHub API.
        config_path: Optional path to .agents.yaml.

    Returns:
        Formatted markdown string ready for inclusion in agent context.
    """
    bucketer = TrustBucketer(config_path=config_path)
    return bucketer.format_bucketed_comments(comments)
