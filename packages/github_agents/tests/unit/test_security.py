"""Tests for security manager."""

import os
from unittest.mock import patch

from github_agents.security import SecurityManager


class TestSecurityManager:
    """Test security manager functionality."""

    def test_initialization(self):
        """Test SecurityManager initialization."""
        manager = SecurityManager()
        assert manager.allowed_users is not None
        assert manager.allowed_actions is not None
        assert manager.triggers is not None

    @patch.dict(os.environ, {}, clear=True)
    def test_default_allowed_users(self):
        """Test default allowed users when no env var."""
        manager = SecurityManager()
        assert "AndrewAltimit" in manager.allowed_users

    @patch.dict(os.environ, {"GITHUB_REPOSITORY": "user/repo"})
    def test_allowed_users_from_repo_owner(self):
        """Test allowed users includes repo owner."""
        manager = SecurityManager()
        assert "user" in manager.allowed_users
        assert "AndrewAltimit" in manager.allowed_users

    @patch.dict(os.environ, {"AI_AGENT_ALLOWED_USERS": "user1,user2,user3"})
    def test_allowed_users_from_env(self):
        """Test allowed users from environment variable."""
        manager = SecurityManager()
        assert "user1" in manager.allowed_users
        assert "user2" in manager.allowed_users
        assert "user3" in manager.allowed_users
        assert "AndrewAltimit" in manager.allowed_users

    def test_parse_trigger_comment(self):
        """Test parsing trigger comments."""
        manager = SecurityManager()

        # Valid triggers with agent
        assert manager.parse_trigger_comment("[Approved][Claude]") == (
            "approved",
            "claude",
        )
        assert manager.parse_trigger_comment("[Review][OpenCode]") == ("review", "opencode")
        assert manager.parse_trigger_comment("[SUMMARIZE][Gemini]") == (
            "summarize",
            "gemini",
        )

        # Case insensitive
        assert manager.parse_trigger_comment("[APPROVED][CLAUDE]") == (
            "approved",
            "claude",
        )

        # Invalid triggers
        assert manager.parse_trigger_comment("Just a comment") == (None, None)
        assert manager.parse_trigger_comment("[Invalid][Claude]") == (None, None)
        assert manager.parse_trigger_comment("") == (None, None)

    def test_parse_trigger_comment_optional_agent(self):
        """Test parsing trigger comments with optional agent (board-first mode)."""
        manager = SecurityManager()

        # Valid triggers without agent - agent should be None (resolved from board)
        assert manager.parse_trigger_comment("[Approved]") == ("approved", None)
        assert manager.parse_trigger_comment("[Review]") == ("review", None)
        assert manager.parse_trigger_comment("[Debug]") == ("debug", None)
        assert manager.parse_trigger_comment("[APPROVED]") == ("approved", None)

        # With agent should still work
        assert manager.parse_trigger_comment("[Approved][Claude]") == ("approved", "claude")

        # Trigger in longer text
        text = "Please implement this feature.\n\n[Approved]\n\nThank you!"
        assert manager.parse_trigger_comment(text) == ("approved", None)

        text_with_agent = "Please implement this.\n\n[Approved][OpenCode]\n\nThanks!"
        assert manager.parse_trigger_comment(text_with_agent) == ("approved", "opencode")

    def test_is_user_allowed(self):
        """Test user authorization.

        Note: is_user_allowed checks against agent_admins (users who can trigger agent actions).
        Bot users like github-actions[bot] are in trusted_sources (for comment context), not agent_admins.
        """
        manager = SecurityManager()

        # Default allowed user (from agent_admins)
        assert manager.is_user_allowed("AndrewAltimit") is True

        # Bot users are NOT in agent_admins - they're in trusted_sources
        # trusted_sources is for comment context, not for triggering agent actions
        assert manager.is_user_allowed("github-actions[bot]") is False
        assert manager.is_user_allowed("dependabot[bot]") is False

        # Unknown user
        assert manager.is_user_allowed("random_user") is False

        # Case sensitive
        assert manager.is_user_allowed("andrewaltimit") is False

    def test_is_action_allowed(self):
        """Test action authorization."""
        manager = SecurityManager()

        # Allowed actions
        assert manager.is_action_allowed("issue_approved") is True
        assert manager.is_action_allowed("pr_approved") is True
        assert manager.is_action_allowed("issue_close") is True
        assert manager.is_action_allowed("issue_review") is True

        # Disallowed action
        assert manager.is_action_allowed("delete_repo") is False
        assert manager.is_action_allowed("unknown_action") is False

    def test_check_trigger_comment_issue(self):
        """Test checking trigger comment in issue."""
        manager = SecurityManager()

        # Mock issue with comments
        issue = {
            "number": 1,
            "body": "Issue description",
            "author": {"login": "user1"},
            "comments": [
                {"author": {"login": "random_user"}, "body": "[Approved][Claude]"},
                {"author": {"login": "AndrewAltimit"}, "body": "[Review][OpenCode]"},
            ],
        }

        # Should return the first valid trigger from allowed user
        result = manager.check_trigger_comment(issue, "issue")
        assert result == ("review", "opencode", "AndrewAltimit")

    def test_check_trigger_comment_pr(self):
        """Test checking trigger comment in PR."""
        manager = SecurityManager()

        # Mock PR with comments
        pr = {
            "number": 10,
            "body": "PR description [Approved][Claude]",
            "author": {"login": "AndrewAltimit"},
            "comments": [],
        }

        # Should check body for PR
        result = manager.check_trigger_comment(pr, "pr")
        assert result == ("approved", "claude", "AndrewAltimit")

    def test_check_trigger_comment_optional_agent(self):
        """Test checking trigger comment with optional agent."""
        manager = SecurityManager()

        # Issue with [Approved] trigger (no agent specified)
        issue = {
            "number": 1,
            "body": "Issue description",
            "author": {"login": "user1"},
            "comments": [
                {"author": {"login": "AndrewAltimit"}, "body": "Looks good!\n\n[Approved]"},
            ],
        }

        result = manager.check_trigger_comment(issue, "issue")
        assert result is not None
        action, agent, user = result
        assert action == "approved"
        assert agent is None  # Agent should be None when not specified
        assert user == "AndrewAltimit"

    def test_check_trigger_comment_optional_agent_in_body(self):
        """Test checking trigger in body with optional agent."""
        manager = SecurityManager()

        # PR with [Review] trigger in body (no agent)
        pr = {
            "number": 10,
            "body": "This needs to be reviewed.\n\n[Review]",
            "author": {"login": "AndrewAltimit"},
            "comments": [],
        }

        result = manager.check_trigger_comment(pr, "pr")
        assert result is not None
        action, agent, user = result
        assert action == "review"
        assert agent is None
        assert user == "AndrewAltimit"

    def test_check_trigger_comment_no_valid_trigger(self):
        """Test when no valid trigger found."""
        manager = SecurityManager()

        issue = {
            "number": 1,
            "body": "Issue without trigger",
            "author": {"login": "user1"},
            "comments": [{"author": {"login": "random_user"}, "body": "Just a comment"}],
        }

        result = manager.check_trigger_comment(issue, "issue")
        assert result is None

    def test_perform_full_security_check_success(self):
        """Test successful security check."""
        manager = SecurityManager()

        is_allowed, reason = manager.perform_full_security_check(
            username="AndrewAltimit",
            action="issue_approved",
            repository="user/repo",
            entity_type="issue",
            entity_id="1",
        )

        assert is_allowed is True
        assert reason == ""

    def test_perform_full_security_check_user_not_allowed(self):
        """Test security check with unauthorized user."""
        manager = SecurityManager()

        is_allowed, reason = manager.perform_full_security_check(
            username="hacker",
            action="issue_approved",
            repository="user/repo",
            entity_type="issue",
            entity_id="1",
        )

        assert is_allowed is False
        assert "not authorized" in reason

    def test_perform_full_security_check_action_not_allowed(self):
        """Test security check with unauthorized action."""
        manager = SecurityManager()

        is_allowed, reason = manager.perform_full_security_check(
            username="AndrewAltimit",
            action="delete_everything",
            repository="user/repo",
            entity_type="issue",
            entity_id="1",
        )

        assert is_allowed is False
        assert "not an allowed action" in reason

    def test_mask_secrets(self):
        """Test secret masking."""
        manager = SecurityManager()

        # Mock environment
        with patch.dict(
            os.environ,
            {
                "SECRET_KEY": "supersecret123",
                "API_TOKEN": "token456",
                "PUBLIC_VAR": "public",
                "MASK_ENV_VARS": "SECRET_KEY,API_TOKEN",
            },
        ):
            text = "The key is supersecret123 and token is token456 with public data"
            masked = manager.mask_secrets(text)

            assert "supersecret123" not in masked
            assert "token456" not in masked
            assert "public" in masked
            assert "***" in masked

    def test_get_trigger_regex(self):
        """Test trigger regex generation."""
        manager = SecurityManager()

        pattern = manager.get_trigger_regex()
        assert pattern is not None

        # Test pattern matches valid triggers
        import re

        regex = re.compile(pattern, re.IGNORECASE)

        # With agent
        assert regex.match("[Approved][Claude]") is not None
        assert regex.match("[Review][OpenCode]") is not None
        assert regex.match("[summarize][gemini]") is not None

        # Without agent (optional agent pattern)
        assert regex.match("[Approved]") is not None
        assert regex.match("[Review]") is not None
        assert regex.match("[Debug]") is not None

        # Invalid triggers (Fix and Implement are no longer valid)
        assert regex.match("[Fix][Claude]") is None
        assert regex.match("[Implement][Claude]") is None
        assert regex.match("[Invalid][Claude]") is None
        assert regex.match("Not a trigger") is None

    def test_rate_limiting(self):
        """Test rate limiting functionality."""
        manager = SecurityManager()

        # Should allow initial requests
        for i in range(10):
            is_allowed = manager.check_rate_limit("testuser", "test_action")
            assert is_allowed is True, f"Request {i + 1} should be allowed"

        # 11th request should be blocked
        is_allowed = manager.check_rate_limit("testuser", "test_action")
        assert is_allowed is False, "11th request should be blocked"

        # Different user should have their own limit
        is_allowed = manager.check_rate_limit("otheruser", "test_action")
        assert is_allowed is True

    def test_repository_allowlist(self):
        """Test repository allowlist functionality."""
        manager = SecurityManager()

        # By default, all repositories should be allowed
        assert manager.is_repository_allowed("any/repo") is True
        assert manager.is_repository_allowed("user/project") is True

        # Test with specific allowlist
        with patch.dict(os.environ, {"AI_AGENT_ALLOWED_REPOS": "owner/repo1,owner/repo2"}):
            manager2 = SecurityManager()
            assert manager2.is_repository_allowed("owner/repo1") is True
            assert manager2.is_repository_allowed("owner/repo2") is True
            assert manager2.is_repository_allowed("owner/repo3") is False
            assert manager2.is_repository_allowed("other/repo") is False
