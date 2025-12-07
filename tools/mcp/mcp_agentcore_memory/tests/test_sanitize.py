"""
Tests for content sanitization.
"""

from mcp_agentcore_memory.sanitize import (
    calculate_entropy,
    contains_secrets,
    get_redaction_summary,
    is_high_entropy_blob,
    sanitize_content,
)


class TestCalculateEntropy:
    """Tests for entropy calculation."""

    def test_empty_string(self):
        """Empty string has zero entropy."""
        assert calculate_entropy("") == 0.0

    def test_single_char_repeated(self):
        """Repeated single character has zero entropy."""
        assert calculate_entropy("aaaaaaaaaa") == 0.0

    def test_english_text(self):
        """English text should have moderate entropy (~4.0-4.5)."""
        text = "The quick brown fox jumps over the lazy dog"
        entropy = calculate_entropy(text)
        assert 3.5 < entropy < 5.0

    def test_random_base64(self):
        """Random base64-like strings should have high entropy (~5.5+)."""
        # Simulated random token
        token = "aB3cD4eF5gH6iJ7kL8mN9oP0qR1sT2uV3wX4yZ5"
        entropy = calculate_entropy(token)
        assert entropy > 4.5


class TestHighEntropyBlob:
    """Tests for high entropy blob detection."""

    def test_short_string_not_flagged(self):
        """Short strings should not be flagged regardless of entropy."""
        assert is_high_entropy_blob("abc123") is False

    def test_english_word_not_flagged(self):
        """Normal English words should not be flagged."""
        assert is_high_entropy_blob("authentication") is False

    def test_api_key_flagged(self):
        """API key-like strings should be flagged."""
        # High-entropy random string (not a real API key pattern)
        token = "aB3cD4eF5gH6iJ7kL8mN9oP0qR1sT2uVwX3yZ"
        assert is_high_entropy_blob(token) is True

    def test_non_alphanumeric_not_checked(self):
        """Strings with non-alphanumeric chars are not checked."""
        # Contains spaces, so won't match the base64-like pattern
        text = "this has spaces and is long enough"
        assert is_high_entropy_blob(text) is False


class TestSanitizeContent:
    """Tests for content sanitization."""

    def test_no_secrets(self):
        """Content without secrets should be unchanged."""
        content = "This is normal text about authentication patterns."
        sanitized = sanitize_content(content)
        assert sanitized == content

    def test_redact_api_key_label(self):
        """API key with label should be redacted."""
        content = "Use api_key=mykey_abcdefghij12345678901234567890"
        sanitized = sanitize_content(content)
        assert "[REDACTED]" in sanitized
        assert "mykey_abcdefghij" not in sanitized

    def test_redact_password(self):
        """Password should be redacted."""
        content = "Set password: mysecretpassword123"
        sanitized = sanitize_content(content)
        assert "[REDACTED]" in sanitized

    def test_redact_aws_access_key(self):
        """AWS access key ID should be redacted."""
        content = "Access key: AKIAIOSFODNN7EXAMPLE"
        sanitized = sanitize_content(content)
        assert "[REDACTED]" in sanitized
        assert "AKIAIOSFODNN7EXAMPLE" not in sanitized

    def test_redact_github_token(self):
        """GitHub PAT should be redacted."""
        content = "Token: ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
        sanitized = sanitize_content(content)
        assert "[REDACTED]" in sanitized

    def test_redact_private_key(self):
        """Private key header should be redacted."""
        content = "-----BEGIN RSA PRIVATE KEY----- content here"
        sanitized = sanitize_content(content)
        assert "[REDACTED]" in sanitized

    def test_redact_high_entropy_blob(self):
        """High entropy blobs should be redacted."""
        # Random-looking token
        content = "Token is aB3cD4eF5gH6iJ7kL8mN9oP0qR1sT2uV3wX4yZ5aBc"
        sanitized = sanitize_content(content)
        assert "[HIGH_ENTROPY_REDACTED]" in sanitized

    def test_preserve_normal_long_words(self):
        """Normal long words should not be redacted."""
        content = "The implementation uses authentication mechanisms"
        sanitized = sanitize_content(content)
        assert sanitized == content

    def test_preserve_whitespace_and_newlines(self):
        """Whitespace, newlines, and indentation should be preserved."""
        content = """def example():
    # This is code
    return "hello"

    if True:
        pass"""
        sanitized = sanitize_content(content)
        assert sanitized == content
        assert "\n" in sanitized
        assert "    " in sanitized  # Indentation preserved

    def test_preserve_formatting_with_redaction(self):
        """Formatting should be preserved even when redacting secrets."""
        content = """Config:
    api_key=secret123
    name=test"""
        sanitized = sanitize_content(content)
        assert "[REDACTED]" in sanitized
        assert "\n" in sanitized
        assert "Config:" in sanitized
        assert "    name=test" in sanitized

    def test_unicode_and_special_chars_handling(self):
        """Unicode and special characters should not crash or be mangled."""
        content = "User said: \u4e2d\u6587 \u65e5\u672c\u8a9e Hello!"
        sanitized = sanitize_content(content)
        assert "\u4e2d\u6587" in sanitized  # Chinese characters
        assert "\u65e5\u672c\u8a9e" in sanitized  # Japanese characters
        assert sanitized == content  # No modification


class TestContainsSecrets:
    """Tests for secret detection without modification."""

    def test_no_secrets(self):
        """Clean content should return False."""
        content = "Normal documentation about APIs"
        has_secrets, patterns = contains_secrets(content)
        assert has_secrets is False
        assert patterns == []

    def test_detects_api_key(self):
        """Should detect API key patterns."""
        content = "api_key=secret123"
        has_secrets, patterns = contains_secrets(content)
        assert has_secrets is True
        assert "generic_secret" in patterns

    def test_detects_multiple_patterns(self):
        """Should detect multiple secret patterns."""
        content = "key=abc123 and token: ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
        has_secrets, patterns = contains_secrets(content)
        assert has_secrets is True
        assert len(patterns) >= 1


class TestRedactionSummary:
    """Tests for redaction summary generation."""

    def test_no_changes(self):
        """Summary for unchanged content."""
        original = "Normal text"
        sanitized = sanitize_content(original)
        summary = get_redaction_summary(original, sanitized)

        assert summary["content_modified"] is False
        assert summary["total_redactions"] == 0

    def test_with_redactions(self):
        """Summary for content with redactions."""
        original = "api_key=secret123 and password: test456"
        sanitized = sanitize_content(original)
        summary = get_redaction_summary(original, sanitized)

        assert summary["content_modified"] is True
        assert summary["redacted_secrets"] >= 1
        assert summary["total_redactions"] >= 1
