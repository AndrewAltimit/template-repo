#!/usr/bin/env python3
"""Unit tests for TTS integration with mocked dependencies."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from github_agents.tts import TTSIntegration, get_voice_for_context


class TestTTSIntegration:
    """Unit tests for TTSIntegration class with mocked dependencies."""

    @pytest.fixture
    def tts_enabled(self):
        """Create TTSIntegration with TTS enabled via mock."""
        with patch.dict("os.environ", {"AGENT_TTS_ENABLED": "true"}):
            return TTSIntegration()

    @pytest.fixture
    def tts_disabled(self):
        """Create TTSIntegration with TTS disabled."""
        with patch.dict("os.environ", {"AGENT_TTS_ENABLED": "false"}):
            return TTSIntegration()

    def test_tts_disabled_returns_none(self, tts_disabled):
        """Test that disabled TTS returns None without making API calls."""
        assert tts_disabled.enabled is False

    @pytest.mark.asyncio
    async def test_tts_disabled_generate_returns_none(self, tts_disabled):
        """Test that generate_audio_review returns None when disabled."""
        result = await tts_disabled.generate_audio_review("Test review", "gemini", pr_number=123)
        assert result is None

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_successful_audio_generation(self, mock_client_class, tts_enabled):
        """Test successful audio generation with mocked API."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "audio_url": "https://example.com/audio.mp3",
        }

        # Setup mock client
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client_class.return_value.__aenter__.return_value = mock_client

        # Test audio generation
        result = await tts_enabled.generate_audio_review(
            "This is an excellent pull request!",
            "gemini",
            pr_number=123,
        )

        # Verify result
        assert result == "https://example.com/audio.mp3"

        # Verify API was called correctly
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert "/synthesize_speech_v3" in call_args[0][0]
        assert call_args[1]["json"]["model"] == "eleven_v3"
        assert call_args[1]["json"]["upload"] is True

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_api_error_handling(self, mock_client_class, tts_enabled):
        """Test handling of API errors."""
        # Setup mock error response
        mock_response = MagicMock()
        mock_response.status_code = 500

        # Setup mock client
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client_class.return_value.__aenter__.return_value = mock_client

        # Test error handling
        result = await tts_enabled.generate_audio_review("Test review", "claude", pr_number=456)

        # Should return None on error
        assert result is None

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_network_error_handling(self, mock_client_class, tts_enabled):
        """Test handling of network errors."""
        # Setup mock client to raise exception
        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.ConnectError("Connection failed")
        mock_client_class.return_value.__aenter__.return_value = mock_client

        # Test network error handling
        result = await tts_enabled.generate_audio_review("Test review", "opencode", pr_number=789)

        # Should return None on network error
        assert result is None

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_sentiment_detection_positive(self, mock_client_class, tts_enabled):
        """Test positive sentiment detection."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "audio_url": "https://example.com/audio.mp3",
        }

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client_class.return_value.__aenter__.return_value = mock_client

        # Test with positive sentiment text
        await tts_enabled.generate_audio_review(
            "This is excellent work! Great implementation!",
            "gemini",
            pr_number=111,
        )

        # Check that positive sentiment was detected
        call_args = mock_client.post.call_args[1]["json"]
        # Voice selection should reflect positive sentiment
        assert call_args["text"] == "This is excellent work! Great implementation!"

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_sentiment_detection_critical(self, mock_client_class, tts_enabled):
        """Test critical sentiment detection."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "audio_url": "https://example.com/audio.mp3",
        }

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client_class.return_value.__aenter__.return_value = mock_client

        # Test with critical sentiment text
        await tts_enabled.generate_audio_review(
            "Critical security vulnerability found! This is urgent!",
            "claude",
            pr_number=222,
        )

        # Verify API call was made
        assert mock_client.post.called

    def test_format_github_comment_with_audio(self, tts_enabled):
        """Test GitHub comment formatting with audio link."""
        original = "This is the review text."
        audio_url = "https://example.com/audio.mp3"

        result = tts_enabled.format_github_comment_with_audio(original, audio_url, duration=5.5)

        assert "🎤 **[Listen to Audio Review (5.5s)](https://example.com/audio.mp3)**" in result
        assert original in result
        assert "---" in result

    @pytest.mark.asyncio
    async def test_process_review_with_tts_enabled(self, tts_enabled):
        """Test process_review_with_tts when TTS is enabled."""
        with patch.object(tts_enabled, "generate_audio_review") as mock_generate:
            mock_generate.return_value = "https://example.com/audio.mp3"

            formatted, audio_url = await tts_enabled.process_review_with_tts("Test review", "gemini", pr_number=333)

            assert audio_url == "https://example.com/audio.mp3"
            assert "🎤 **[Listen to Audio Review" in formatted
            assert "Test review" in formatted

    @pytest.mark.asyncio
    async def test_process_review_with_tts_disabled(self, tts_disabled):
        """Test process_review_with_tts when TTS is disabled."""
        formatted, audio_url = await tts_disabled.process_review_with_tts("Test review", "claude", pr_number=444)

        assert audio_url is None
        assert formatted == "Test review"


class TestVoiceSelection:
    """Unit tests for voice selection logic."""

    def test_get_voice_for_context_default(self):
        """Test default voice selection."""
        voice = get_voice_for_context("gemini", "default", "normal")
        assert voice is not None
        assert hasattr(voice, "voice_id")
        assert hasattr(voice, "display_name")

    def test_get_voice_for_context_urgent(self):
        """Test voice selection for urgent context."""
        voice = get_voice_for_context("claude", "critical", "urgent")
        assert voice is not None
        # Should select a more serious voice for urgent/critical

    def test_get_voice_for_context_positive(self):
        """Test voice selection for positive sentiment."""
        voice = get_voice_for_context("opencode", "positive", "normal")
        assert voice is not None

    def test_get_voice_for_unknown_agent(self):
        """Test voice selection for unknown agent defaults to Gemini."""
        voice = get_voice_for_context("unknown_agent", "default", "normal")
        assert voice is not None
        # Should default to Gemini's voice mapping


class TestMockMode:
    """Test mock mode to prevent API credit usage."""

    @pytest.fixture
    def mock_mode_tts(self):
        """Create TTSIntegration in mock mode."""
        with patch.dict("os.environ", {"AGENT_TTS_ENABLED": "true", "TTS_MOCK_MODE": "true"}):  # New env var for mock mode
            return TTSIntegration()

    @pytest.mark.asyncio
    async def test_mock_mode_returns_fake_url(self, mock_mode_tts):
        """Test that mock mode returns fake URL without API calls."""
        # Verify mock mode is set
        assert mock_mode_tts.mock_mode is True
        assert mock_mode_tts.enabled is True

        # Mock mode should not make any API calls
        result = await mock_mode_tts.generate_audio_review(
            "Test review in mock mode",
            "gemini",
            pr_number=555,
        )

        # Should return a mock URL for testing
        assert result == "mock://audio/pr555_gemini.mp3"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
