"""Tests for security manager."""

from github_ai_agents.security import SecurityManager


class TestSecurityManager:
    """Test security manager functionality."""

    def test_extract_trigger_valid(self):
        """Test extracting valid triggers."""
        manager = SecurityManager()

        # Test valid triggers
        assert manager._extract_trigger("[Approved][Claude]") == ("Approved", "Claude")
        assert manager._extract_trigger("Please [Fix][OpenCode] this bug") == ("Fix", "OpenCode")
        assert manager._extract_trigger("[Implement][Gemini]") == ("Implement", "Gemini")

    def test_extract_trigger_invalid(self):
        """Test extracting invalid triggers."""
        manager = SecurityManager()

        # Test invalid triggers
        assert manager._extract_trigger("[Invalid][Claude]") is None
        assert manager._extract_trigger("No trigger here") is None
        assert manager._extract_trigger("[Approved]") is None
        assert manager._extract_trigger("[[Approved]][Claude]") is None

    def test_user_authorization(self):
        """Test user authorization."""
        manager = SecurityManager()

        # Default allow list includes AndrewAltimit
        assert manager._is_user_authorized("AndrewAltimit") is True
        assert manager._is_user_authorized("github-actions[bot]") is True
        assert manager._is_user_authorized("random-user") is False

    def test_rate_limiting(self):
        """Test rate limiting."""
        manager = SecurityManager()

        # Should allow initial requests
        assert manager.check_rate_limit("testuser", "test_action") is True

        # Fill up rate limit
        for _ in range(9):  # Already did 1, do 9 more to hit 10
            manager.check_rate_limit("testuser", "test_action")

        # Should block after limit
        assert manager.check_rate_limit("testuser", "test_action") is False

        # Different action should work
        assert manager.check_rate_limit("testuser", "other_action") is True

    def test_repository_allowed(self):
        """Test repository allowlist."""
        manager = SecurityManager()

        # Default allows all repos (empty allowlist)
        assert manager.is_repository_allowed("any/repo") is True

        # Test with specific allowlist
        manager.config["allowed_repositories"] = ["owner/allowed-repo"]
        assert manager.is_repository_allowed("owner/allowed-repo") is True
        assert manager.is_repository_allowed("owner/other-repo") is False

    def test_full_security_check(self):
        """Test comprehensive security check."""
        manager = SecurityManager()

        # Authorized user, should pass
        allowed, reason = manager.perform_full_security_check(
            username="AndrewAltimit",
            action="issue_fix",
            repository="test/repo",
            entity_type="issue",
            entity_id="123",
        )
        assert allowed is True
        assert reason is None

        # Unauthorized user, should fail
        allowed, reason = manager.perform_full_security_check(
            username="random-user",
            action="issue_fix",
            repository="test/repo",
            entity_type="issue",
            entity_id="123",
        )
        assert allowed is False
        assert "not authorized" in reason
