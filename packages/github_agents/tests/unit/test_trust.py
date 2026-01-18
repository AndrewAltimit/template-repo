"""Tests for trust-level bucketing functionality."""

from pathlib import Path
from unittest.mock import patch

import pytest

from github_agents.security.trust import (
    TrustBucketer,
    TrustConfig,
    TrustLevel,
    bucket_comments_for_context,
)


class TestTrustConfig:
    """Tests for TrustConfig loading."""

    def test_default_config(self) -> None:
        """Test that default config has empty lists."""
        config = TrustConfig()
        assert config.agent_admins == []
        assert config.trusted_sources == []

    def test_from_yaml_missing_file(self, tmp_path: Path) -> None:
        """Test loading from non-existent file returns defaults."""
        config = TrustConfig.from_yaml(tmp_path / "nonexistent.yaml")
        assert config.agent_admins == []
        assert config.trusted_sources == []

    def test_from_yaml_valid_file(self, tmp_path: Path) -> None:
        """Test loading from valid YAML file."""
        config_file = tmp_path / ".agents.yaml"
        config_file.write_text("""
security:
  agent_admins:
    - admin1
    - admin2
  trusted_sources:
    - bot1
    - bot2
    - admin1
""")
        config = TrustConfig.from_yaml(config_file)
        assert config.agent_admins == ["admin1", "admin2"]
        assert config.trusted_sources == ["bot1", "bot2", "admin1"]

    def test_from_yaml_empty_security(self, tmp_path: Path) -> None:
        """Test loading from YAML with empty security section."""
        config_file = tmp_path / ".agents.yaml"
        config_file.write_text("""
enabled_agents:
  - claude
""")
        config = TrustConfig.from_yaml(config_file)
        assert config.agent_admins == []
        assert config.trusted_sources == []


class TestTrustBucketer:
    """Tests for TrustBucketer class."""

    @pytest.fixture
    def sample_config(self) -> TrustConfig:
        """Create a sample trust config."""
        return TrustConfig(
            agent_admins=["admin_user", "AndrewAltimit"],
            trusted_sources=["github-actions[bot]", "dependabot[bot]", "AndrewAltimit"],
        )

    @pytest.fixture
    def bucketer(self, sample_config: TrustConfig) -> TrustBucketer:
        """Create a TrustBucketer with sample config."""
        return TrustBucketer(config=sample_config)

    def test_get_trust_level_admin(self, bucketer: TrustBucketer) -> None:
        """Test admin users get ADMIN trust level."""
        assert bucketer.get_trust_level("admin_user") == TrustLevel.ADMIN
        assert bucketer.get_trust_level("AndrewAltimit") == TrustLevel.ADMIN

    def test_get_trust_level_trusted(self, bucketer: TrustBucketer) -> None:
        """Test trusted sources get TRUSTED level (not ADMIN if not in admins)."""
        assert bucketer.get_trust_level("github-actions[bot]") == TrustLevel.TRUSTED
        assert bucketer.get_trust_level("dependabot[bot]") == TrustLevel.TRUSTED

    def test_get_trust_level_admin_in_both(self, bucketer: TrustBucketer) -> None:
        """Test user in both admin and trusted gets ADMIN level."""
        # AndrewAltimit is in both agent_admins and trusted_sources
        assert bucketer.get_trust_level("AndrewAltimit") == TrustLevel.ADMIN

    def test_get_trust_level_community(self, bucketer: TrustBucketer) -> None:
        """Test unknown users get COMMUNITY level."""
        assert bucketer.get_trust_level("random_user") == TrustLevel.COMMUNITY
        assert bucketer.get_trust_level("external_contributor") == TrustLevel.COMMUNITY

    def test_is_noise_agent_claim(self, bucketer: TrustBucketer) -> None:
        """Test agent claim comments are detected as noise."""
        noise_body = """🤖 **[Agent Claim]**

Agent: claude
Started: 2024-01-01
"""
        assert bucketer.is_noise(noise_body) is True

    def test_is_noise_approval_trigger(self, bucketer: TrustBucketer) -> None:
        """Test bare approval triggers are detected as noise."""
        assert bucketer.is_noise("[Approved][Claude]") is True
        assert bucketer.is_noise("[Approved][Gemini]") is True
        # But approval with additional text is NOT noise
        assert bucketer.is_noise("[Approved][Claude] with some notes") is False

    def test_is_noise_regular_comment(self, bucketer: TrustBucketer) -> None:
        """Test regular comments are not noise."""
        assert bucketer.is_noise("This is a regular comment") is False
        assert bucketer.is_noise("Fix the bug in line 42") is False

    def test_is_noise_empty(self, bucketer: TrustBucketer) -> None:
        """Test empty body is noise."""
        assert bucketer.is_noise("") is True
        assert bucketer.is_noise(None) is True  # type: ignore[arg-type]

    def test_bucket_comments(self, bucketer: TrustBucketer) -> None:
        """Test bucketing comments by trust level."""
        comments = [
            {"author": {"login": "admin_user"}, "body": "Admin comment"},
            {"author": {"login": "github-actions[bot]"}, "body": "Bot comment"},
            {"author": {"login": "random_user"}, "body": "Community comment"},
            {"author": {"login": "admin_user"}, "body": "🤖 **[Agent Claim]** noise"},
        ]

        buckets = bucketer.bucket_comments(comments)

        assert len(buckets[TrustLevel.ADMIN]) == 1
        assert len(buckets[TrustLevel.TRUSTED]) == 1
        assert len(buckets[TrustLevel.COMMUNITY]) == 1
        # Noise comment should be filtered
        assert buckets[TrustLevel.ADMIN][0]["body"] == "Admin comment"

    def test_bucket_comments_no_filter(self, bucketer: TrustBucketer) -> None:
        """Test bucketing with noise filtering disabled."""
        comments = [
            {"author": {"login": "admin_user"}, "body": "🤖 **[Agent Claim]** noise"},
        ]

        buckets = bucketer.bucket_comments(comments, filter_noise=False)
        assert len(buckets[TrustLevel.ADMIN]) == 1

    def test_bucket_comments_string_author(self, bucketer: TrustBucketer) -> None:
        """Test handling of author as string instead of dict."""
        comments = [
            {"author": "admin_user", "body": "Comment with string author"},
        ]

        buckets = bucketer.bucket_comments(comments)
        assert len(buckets[TrustLevel.ADMIN]) == 1

    def test_format_bucketed_comments(self, bucketer: TrustBucketer) -> None:
        """Test formatting comments as markdown."""
        comments = [
            {
                "author": {"login": "admin_user"},
                "body": "Please fix the bug",
                "createdAt": "2024-01-15T10:30:00Z",
            },
            {
                "author": {"login": "github-actions[bot]"},
                "body": "CI passed",
                "createdAt": "2024-01-15T11:00:00Z",
            },
            {
                "author": {"login": "random_user"},
                "body": "Looks good to me",
                "createdAt": "2024-01-15T12:00:00Z",
            },
        ]

        result = bucketer.format_bucketed_comments(comments)

        # Check headers are present
        assert "## Admin Guidance (Highest Trust)" in result
        assert "## Trusted Context (Medium Trust)" in result
        assert "## Community Input (Review Carefully)" in result

        # Check content is present
        assert "admin_user" in result
        assert "Please fix the bug" in result
        assert "github-actions[bot]" in result
        assert "CI passed" in result
        assert "random_user" in result
        assert "Looks good to me" in result

    def test_format_bucketed_comments_empty(self, bucketer: TrustBucketer) -> None:
        """Test formatting with no comments."""
        result = bucketer.format_bucketed_comments([])
        assert result == ""


class TestBucketCommentsForContext:
    """Tests for convenience function."""

    def test_convenience_function(self, tmp_path: Path) -> None:
        """Test the bucket_comments_for_context convenience function."""
        config_file = tmp_path / ".agents.yaml"
        config_file.write_text("""
security:
  agent_admins:
    - test_admin
  trusted_sources:
    - test_bot
""")
        comments = [
            {"author": {"login": "test_admin"}, "body": "Admin says do this"},
        ]

        # Patch the config file search
        with patch.object(Path, "cwd", return_value=tmp_path):
            result = bucket_comments_for_context(comments, config_path=config_file)

        assert "Admin Guidance" in result
        assert "test_admin" in result


class TestTrustLevelEnum:
    """Tests for TrustLevel enum."""

    def test_enum_values(self) -> None:
        """Test enum has expected values."""
        assert TrustLevel.ADMIN.value == "admin"
        assert TrustLevel.TRUSTED.value == "trusted"
        assert TrustLevel.COMMUNITY.value == "community"

    def test_enum_comparison(self) -> None:
        """Test enum comparison works."""
        assert TrustLevel.ADMIN == TrustLevel.ADMIN
        assert TrustLevel.ADMIN != TrustLevel.TRUSTED
