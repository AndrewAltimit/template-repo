"""
Test module for AI agents security implementation.
Tests the SecurityManager class and related security features.
"""

import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

# Add the scripts/agents directory to the path so we can import the modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts", "agents"))

from security import SecurityManager  # noqa: E402


class TestSecurityManager:
    """Test cases for the SecurityManager class."""

    @pytest.fixture
    def security_manager(self):
        """Create a SecurityManager instance for testing."""
        # Use a specific allow list for testing
        test_allow_list = [
            "AndrewAltimit",
            "github-actions[bot]",
            "gemini-bot",
            "test-user",
        ]
        return SecurityManager(allow_list=test_allow_list)

    @pytest.fixture
    def test_issue(self):
        """Create a test issue object."""

        def _create_issue(author: str, number: int = 1):
            return {
                "number": number,
                "title": "Test issue",
                "body": "This is a test issue body",
                "author": {"login": author},
                "labels": [{"name": "bug"}],
                "comments": [],
            }

        return _create_issue

    @pytest.fixture
    def test_pr(self):
        """Create a test PR object."""

        def _create_pr(author: str, number: int = 1):
            return {
                "number": number,
                "title": "Test PR",
                "body": "This is a test PR body",
                "author": {"login": author},
                "headRefName": "test-branch",
                "labels": [],
                "reviews": [],
                "comments": [],
            }

        return _create_pr

    def test_is_user_allowed(self, security_manager):
        """Test user allow list functionality."""
        # Test allowed users
        assert security_manager.is_user_allowed("AndrewAltimit") is True
        assert security_manager.is_user_allowed("github-actions[bot]") is True
        assert security_manager.is_user_allowed("gemini-bot") is True
        assert security_manager.is_user_allowed("test-user") is True

        # Test unauthorized users
        assert security_manager.is_user_allowed("random-user") is False
        assert security_manager.is_user_allowed("hacker") is False
        assert security_manager.is_user_allowed("") is False

    def test_check_issue_security(self, security_manager, test_issue):
        """Test issue security checking."""
        # Allowed issue
        allowed_issue = test_issue("AndrewAltimit", 1)
        assert security_manager.check_issue_security(allowed_issue) is True

        # Unauthorized issue
        unauthorized_issue = test_issue("random-user", 2)
        assert security_manager.check_issue_security(unauthorized_issue) is False

        # Issue with missing author
        invalid_issue = {"number": 3, "title": "Test", "body": "Test"}
        assert security_manager.check_issue_security(invalid_issue) is False

    def test_check_pr_security(self, security_manager, test_pr):
        """Test PR security checking."""
        # Allowed PR
        allowed_pr = test_pr("gemini-bot", 10)
        assert security_manager.check_pr_security(allowed_pr) is True

        # Unauthorized PR
        unauthorized_pr = test_pr("malicious-user", 11)
        assert security_manager.check_pr_security(unauthorized_pr) is False

    def test_check_comment_security(self, security_manager):
        """Test comment security checking."""
        # Allowed comment
        allowed_comment = {"user": {"login": "test-user"}, "body": "Test comment"}
        assert security_manager.check_comment_security(allowed_comment) is True

        # Unauthorized comment
        unauthorized_comment = {
            "user": {"login": "attacker"},
            "body": "Malicious comment",
        }
        assert security_manager.check_comment_security(unauthorized_comment) is False

    def test_security_disabled(self):
        """Test behavior when security is disabled."""
        # Create security manager with security disabled
        with patch("builtins.open", MagicMock()):
            with patch("json.load", return_value={"security": {"enabled": False}}):
                security_manager = SecurityManager()

        security_manager.enabled = False

        # All users should be allowed when security is disabled
        assert security_manager.is_user_allowed("anyone") is True
        assert security_manager.is_user_allowed("hacker") is True

    def test_add_remove_user_allow_list(self, security_manager):
        """Test adding and removing users from allow list."""
        # Add a new user
        security_manager.add_user_to_allow_list("new-user")
        assert security_manager.is_user_allowed("new-user") is True

        # Remove the user
        security_manager.remove_user_from_allow_list("new-user")
        assert security_manager.is_user_allowed("new-user") is False

    def test_log_security_violation(self, security_manager, caplog):
        """Test security violation logging."""
        security_manager.log_security_violation("issue", "123", "attacker")

        # Check that the violation was logged
        assert "SECURITY VIOLATION" in caplog.text
        assert "issue #123" in caplog.text
        assert "attacker" in caplog.text

    def test_rate_limiting(self, security_manager):
        """Test rate limiting functionality."""
        # First request should be allowed
        allowed, reason = security_manager.check_rate_limit("test-user", "test_action")
        assert allowed is True
        assert reason is None

        # Simulate exceeding rate limit
        security_manager.rate_limit_max_requests = 2

        # Second request should be allowed
        allowed, reason = security_manager.check_rate_limit("test-user", "test_action")
        assert allowed is True

        # Third request should be denied
        allowed, reason = security_manager.check_rate_limit("test-user", "test_action")
        assert allowed is False
        assert "rate limit exceeded" in reason.lower()

    def test_repository_validation(self, security_manager):
        """Test repository validation."""
        # Test with allowed repository patterns
        security_manager.allowed_repositories = [
            "AndrewAltimit/*",
            "test-org/test-repo",
        ]

        assert security_manager.check_repository("AndrewAltimit/any-repo") is True
        assert security_manager.check_repository("test-org/test-repo") is True
        assert security_manager.check_repository("other-org/other-repo") is False

    def test_perform_full_security_check(self, security_manager):
        """Test comprehensive security check."""
        # Set up test conditions
        security_manager.allowed_repositories = ["AndrewAltimit/*"]

        # Test allowed request
        allowed, reason = security_manager.perform_full_security_check(
            username="test-user",
            action="issue_process",
            repository="AndrewAltimit/test-repo",
            entity_type="issue",
            entity_id="1",
        )
        assert allowed is True
        assert reason is None

        # Test unauthorized user
        allowed, reason = security_manager.perform_full_security_check(
            username="hacker",
            action="issue_process",
            repository="AndrewAltimit/test-repo",
            entity_type="issue",
            entity_id="2",
        )
        assert allowed is False
        assert "not in the allow list" in reason

    def test_check_file_path_security(self, security_manager):
        """Test file path security restrictions."""
        # Test allowed paths
        allowed, reason = security_manager.check_file_path_security("src/main.py")
        assert allowed is True
        assert reason is None

        allowed, reason = security_manager.check_file_path_security("docs/README.md")
        assert allowed is True
        assert reason is None

        # Test restricted paths - agent's own code
        allowed, reason = security_manager.check_file_path_security("scripts/agents/issue_monitor.py")
        assert allowed is False
        assert "scripts/agents/" in reason

        allowed, reason = security_manager.check_file_path_security("scripts/agents/security.py")
        assert allowed is False
        # The reason could be either the path pattern or the filename
        assert "scripts/agents/" in reason or "security.py" in reason

        # Test restricted paths - workflows
        allowed, reason = security_manager.check_file_path_security(".github/workflows/issue-monitor.yml")
        assert allowed is False
        assert ".github/workflows/issue-monitor.yml" in reason

        # Test restricted paths - system files
        allowed, reason = security_manager.check_file_path_security("/etc/passwd")
        assert allowed is False
        assert "/etc/" in reason

        allowed, reason = security_manager.check_file_path_security("~/.ssh/id_rsa")
        assert allowed is False
        assert "~/.ssh/" in reason

        # Test restricted file names
        allowed, reason = security_manager.check_file_path_security("some/path/config.json")
        assert allowed is False
        assert "config.json" in reason

        allowed, reason = security_manager.check_file_path_security("another/path/.gitconfig")
        assert allowed is False
        assert ".gitconfig" in reason

    def test_config_loading(self, tmp_path):
        """Test loading configuration from file."""
        # Create a temporary config file
        config_data = {
            "security": {
                "enabled": True,
                "allow_list": ["user1", "user2"],
                "log_violations": True,
                "rate_limit_window_minutes": 30,
                "rate_limit_max_requests": 5,
                "allowed_repositories": ["test-org/*"],
            }
        }

        config_file = tmp_path / "config.json"
        with open(config_file, "w") as f:
            json.dump(config_data, f)

        # Create SecurityManager with custom config path
        security_manager = SecurityManager(config_path=str(config_file))

        # Verify configuration was loaded correctly
        assert security_manager.enabled is True
        assert "user1" in security_manager.allow_list
        assert "user2" in security_manager.allow_list
        assert security_manager.log_violations is True
        assert security_manager.rate_limit_window == 30
        assert security_manager.rate_limit_max_requests == 5
        assert "test-org/*" in security_manager.allowed_repositories

    @patch.dict(os.environ, {"GITHUB_REPOSITORY": "TestOwner/test-repo"})
    def test_repo_owner_auto_inclusion(self):
        """Test that repository owner is automatically included in allow list."""
        security_manager = SecurityManager(allow_list=["other-user"])

        # Repository owner should be automatically included
        assert security_manager.is_user_allowed("TestOwner") is True
        assert security_manager.is_user_allowed("other-user") is True

    @patch.dict(os.environ, {"AI_AGENT_ALLOW_LIST": "env-user1,env-user2,env-user3"})
    def test_env_var_allow_list(self):
        """Test loading allow list from environment variable."""
        # Mock the config file loading to return empty config
        with patch("builtins.open", side_effect=FileNotFoundError):
            # When no allow list is provided and config file doesn't exist, it should load from env var
            security_manager = SecurityManager()

        assert security_manager.is_user_allowed("env-user1") is True
        assert security_manager.is_user_allowed("env-user2") is True
        assert security_manager.is_user_allowed("env-user3") is True

    def test_keyword_trigger_parsing(self, security_manager):
        """Test parsing keyword triggers from text."""
        # Valid triggers
        assert security_manager.parse_keyword_trigger("[Approved][Claude]") == (
            "Approved",
            "Claude",
        )
        assert security_manager.parse_keyword_trigger("[Fix][Gemini]") == (
            "Fix",
            "Gemini",
        )
        assert security_manager.parse_keyword_trigger("[Close][Claude]") == (
            "Close",
            "Claude",
        )
        assert security_manager.parse_keyword_trigger("[Summarize][Gemini]") == (
            "Summarize",
            "Gemini",
        )
        assert security_manager.parse_keyword_trigger("[Debug][Claude]") == (
            "Debug",
            "Claude",
        )
        assert security_manager.parse_keyword_trigger("[Implement][Gemini]") == (
            "Implement",
            "Gemini",
        )
        assert security_manager.parse_keyword_trigger("[Review][Claude]") == (
            "Review",
            "Claude",
        )

        # Case insensitive
        assert security_manager.parse_keyword_trigger("[approved][claude]") == (
            "approved",
            "claude",
        )
        assert security_manager.parse_keyword_trigger("[CLOSE][GEMINI]") == (
            "CLOSE",
            "GEMINI",
        )

        # With whitespace
        assert security_manager.parse_keyword_trigger("[Approved] [Claude]") == (
            "Approved",
            "Claude",
        )
        assert security_manager.parse_keyword_trigger("[Fix]  [Gemini]") == (
            "Fix",
            "Gemini",
        )

        # Invalid triggers
        assert security_manager.parse_keyword_trigger("[Invalid][Claude]") is None
        assert security_manager.parse_keyword_trigger("[Approved][GitBot]") is None  # GitBot removed
        assert security_manager.parse_keyword_trigger("[Approved][InvalidAgent]") is None
        assert security_manager.parse_keyword_trigger("[Approved]") is None
        assert security_manager.parse_keyword_trigger("Approved][Claude]") is None
        assert security_manager.parse_keyword_trigger("[Approved Claude]") is None
        assert security_manager.parse_keyword_trigger("Just some text") is None
        assert security_manager.parse_keyword_trigger("") is None
        assert security_manager.parse_keyword_trigger(None) is None

    def test_check_trigger_comment(self, security_manager, test_issue):
        """Test checking for trigger comments in issues/PRs."""
        # Issue with valid trigger from allowed user
        issue = test_issue("randomuser")
        issue["comments"] = [
            {"user": {"login": "randomuser"}, "body": "This is a bug"},
            {
                "user": {"login": "test-user"},
                "body": "I'll fix this. [Approved][Claude]",
            },
        ]
        result = security_manager.check_trigger_comment(issue)
        assert result == ("Approved", "Claude", "test-user")

        # Issue without trigger
        issue_no_trigger = test_issue("user1")
        issue_no_trigger["comments"] = [{"user": {"login": "test-user"}, "body": "This needs work"}]
        assert security_manager.check_trigger_comment(issue_no_trigger) is None

        # Trigger from unauthorized user
        issue_unauthorized = test_issue("hacker")
        issue_unauthorized["comments"] = [{"user": {"login": "hacker"}, "body": "[Approved][Claude]"}]
        assert security_manager.check_trigger_comment(issue_unauthorized) is None

        # Multiple triggers - most recent wins
        issue_multiple = test_issue("user1")
        issue_multiple["comments"] = [
            {"user": {"login": "test-user"}, "body": "[Close][Claude]"},
            {"user": {"login": "AndrewAltimit"}, "body": "[Summarize][Gemini]"},
            {
                "user": {"login": "test-user"},
                "body": "[Approved][Claude]",
            },  # Most recent
        ]
        result = security_manager.check_trigger_comment(issue_multiple)
        assert result == ("Approved", "Claude", "test-user")

        # Empty comments list
        issue_empty = test_issue("user1")
        issue_empty["comments"] = []
        assert security_manager.check_trigger_comment(issue_empty) is None

        # Mixed valid and invalid triggers
        issue_mixed = test_issue("user1")
        issue_mixed["comments"] = [
            {"user": {"login": "hacker"}, "body": "[Approved][Claude]"},  # Unauthorized
            {
                "user": {"login": "test-user"},
                "body": "[Invalid][Claude]",
            },  # Invalid action
            {"user": {"login": "test-user"}, "body": "[Fix][Gemini]"},  # Valid
        ]
        result = security_manager.check_trigger_comment(issue_mixed)
        assert result == ("Fix", "Gemini", "test-user")
