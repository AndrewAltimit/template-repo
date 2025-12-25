"""Unit tests for ElevenLabs MCP Server streaming improvements.

Tests cover:
- VoiceSettings: speed parameter, to_dict() behavior
- OutputFormat: new Opus and PCM formats
- StreamConfig: auto_mode, region, defaults, URL generation
- StreamingRegion: enum values
- get_model_for_use_case: model selection logic
- Integration behavior scenarios
"""

from tools.mcp.mcp_elevenlabs_speech.models.synthesis_config import (
    StreamConfig,
    StreamingRegion,
)

# Import modules under test
from tools.mcp.mcp_elevenlabs_speech.models.voice_settings import (
    OutputFormat,
    VoiceModel,
    VoiceSettings,
    get_model_for_use_case,
)

# =============================================================================
# VoiceSettings Tests
# =============================================================================


class TestVoiceSettings:
    """Tests for VoiceSettings with speed parameter."""

    def test_default_speed(self):
        """Test default speed is 1.0."""
        settings = VoiceSettings()
        assert settings.speed == 1.0

    def test_custom_speed(self):
        """Test custom speed value."""
        settings = VoiceSettings(speed=1.2)
        assert settings.speed == 1.2

    def test_to_dict_excludes_default_speed(self):
        """Test to_dict() doesn't include speed when default."""
        settings = VoiceSettings(speed=1.0)
        result = settings.to_dict()
        assert "speed" not in result

    def test_to_dict_includes_non_default_speed(self):
        """Test to_dict() includes speed when not default."""
        settings = VoiceSettings(speed=1.1)
        result = settings.to_dict()
        assert "speed" in result
        assert result["speed"] == 1.1

    def test_to_dict_clamps_speed_min(self):
        """Test to_dict() clamps speed to minimum 0.7."""
        settings = VoiceSettings(speed=0.5)
        result = settings.to_dict()
        assert result["speed"] == 0.7

    def test_to_dict_clamps_speed_max(self):
        """Test to_dict() clamps speed to maximum 1.2."""
        settings = VoiceSettings(speed=1.5)
        result = settings.to_dict()
        assert result["speed"] == 1.2

    def test_to_dict_contains_all_fields(self):
        """Test to_dict() contains all required fields."""
        settings = VoiceSettings(
            stability=0.6,
            similarity_boost=0.8,
            style=0.3,
            use_speaker_boost=True,
        )
        result = settings.to_dict()
        assert result["stability"] == 0.6
        assert result["similarity_boost"] == 0.8
        assert result["style"] == 0.3
        assert result["use_speaker_boost"] is True


# =============================================================================
# OutputFormat Tests
# =============================================================================


class TestOutputFormat:
    """Tests for OutputFormat enum with new formats."""

    def test_opus_formats_exist(self):
        """Test Opus formats are defined."""
        assert OutputFormat.OPUS_48000_32.value == "opus_48000_32"
        assert OutputFormat.OPUS_48000_64.value == "opus_48000_64"
        assert OutputFormat.OPUS_48000_128.value == "opus_48000_128"

    def test_pcm_48000_exists(self):
        """Test PCM 48000 format is defined."""
        assert OutputFormat.PCM_48000.value == "pcm_48000"

    def test_alaw_format_exists(self):
        """Test A-law format is defined."""
        assert OutputFormat.ALAW_8000.value == "alaw_8000"

    def test_mp3_22050_32_exists(self):
        """Test low quality MP3 format is defined."""
        assert OutputFormat.MP3_22050_32.value == "mp3_22050_32"

    def test_all_formats_have_values(self):
        """Test all formats have string values."""
        for fmt in OutputFormat:
            assert isinstance(fmt.value, str)
            assert len(fmt.value) > 0


# =============================================================================
# StreamingRegion Tests
# =============================================================================


class TestStreamingRegion:
    """Tests for StreamingRegion enum."""

    def test_us_region(self):
        """Test US region endpoint."""
        assert "api.elevenlabs.io" in StreamingRegion.US.value
        assert "wss://" in StreamingRegion.US.value

    def test_eu_region(self):
        """Test EU region endpoint."""
        assert "eu.residency" in StreamingRegion.EU.value
        assert "wss://" in StreamingRegion.EU.value

    def test_india_region(self):
        """Test India region endpoint."""
        assert "in.residency" in StreamingRegion.INDIA.value
        assert "wss://" in StreamingRegion.INDIA.value

    def test_global_region(self):
        """Test Global preview endpoint."""
        assert "global-preview" in StreamingRegion.GLOBAL.value
        assert "wss://" in StreamingRegion.GLOBAL.value


# =============================================================================
# StreamConfig Tests
# =============================================================================


class TestStreamConfig:
    """Tests for StreamConfig with new streaming features."""

    def test_default_model_is_flash(self):
        """Test default model is Flash v2.5 for lowest latency."""
        config = StreamConfig(text="Hello", voice_id="test_voice")
        assert config.model == VoiceModel.ELEVEN_FLASH_V2_5

    def test_default_format_is_pcm(self):
        """Test default format is PCM for streaming."""
        config = StreamConfig(text="Hello", voice_id="test_voice")
        assert config.output_format == OutputFormat.PCM_24000

    def test_auto_mode_default_true(self):
        """Test auto_mode defaults to True."""
        config = StreamConfig(text="Hello", voice_id="test_voice")
        assert config.auto_mode is True

    def test_default_region_is_us(self):
        """Test default region is US."""
        config = StreamConfig(text="Hello", voice_id="test_voice")
        assert config.region == StreamingRegion.US

    def test_default_inactivity_timeout(self):
        """Test default inactivity timeout is 20 seconds."""
        config = StreamConfig(text="Hello", voice_id="test_voice")
        assert config.inactivity_timeout == 20

    def test_to_websocket_params_excludes_chunk_schedule_with_auto_mode(self):
        """Test chunk_schedule is excluded when auto_mode is True."""
        config = StreamConfig(text="Hello", voice_id="test_voice", auto_mode=True)
        params = config.to_websocket_params()
        assert "chunk_length_schedule" not in params

    def test_to_websocket_params_includes_chunk_schedule_without_auto_mode(self):
        """Test chunk_schedule is included when auto_mode is False."""
        config = StreamConfig(text="Hello", voice_id="test_voice", auto_mode=False)
        params = config.to_websocket_params()
        assert "chunk_length_schedule" in params
        assert params["chunk_length_schedule"] == [120, 160, 250, 290]

    def test_to_websocket_params_contains_voice_settings(self):
        """Test voice_settings are included in params."""
        settings = VoiceSettings(stability=0.6, similarity_boost=0.8)
        config = StreamConfig(text="Hello", voice_id="test_voice", voice_settings=settings)
        params = config.to_websocket_params()
        assert "voice_settings" in params
        assert params["voice_settings"]["stability"] == 0.6

    def test_get_websocket_url_contains_voice_id(self):
        """Test WebSocket URL contains voice_id."""
        config = StreamConfig(text="Hello", voice_id="test_voice_123")
        url = config.get_websocket_url()
        assert "test_voice_123" in url

    def test_get_websocket_url_contains_auto_mode(self):
        """Test WebSocket URL contains auto_mode when enabled."""
        config = StreamConfig(text="Hello", voice_id="test_voice", auto_mode=True)
        url = config.get_websocket_url()
        assert "auto_mode=true" in url

    def test_get_websocket_url_no_auto_mode_when_disabled(self):
        """Test WebSocket URL excludes auto_mode when disabled."""
        config = StreamConfig(text="Hello", voice_id="test_voice", auto_mode=False)
        url = config.get_websocket_url()
        assert "auto_mode" not in url

    def test_get_websocket_url_contains_model_id(self):
        """Test WebSocket URL contains model_id."""
        config = StreamConfig(text="Hello", voice_id="test_voice")
        url = config.get_websocket_url()
        assert "model_id=eleven_flash_v2_5" in url

    def test_get_websocket_url_uses_region(self):
        """Test WebSocket URL uses correct regional endpoint."""
        config = StreamConfig(text="Hello", voice_id="test_voice", region=StreamingRegion.EU)
        url = config.get_websocket_url()
        assert "eu.residency" in url


# =============================================================================
# get_model_for_use_case Tests
# =============================================================================


class TestGetModelForUseCase:
    """Tests for get_model_for_use_case function."""

    def test_streaming_returns_flash(self):
        """Test streaming use case returns Flash v2.5."""
        model = get_model_for_use_case("any", requires_streaming=True)
        assert model == VoiceModel.ELEVEN_FLASH_V2_5

    def test_low_latency_returns_flash(self):
        """Test low_latency flag returns Flash v2.5."""
        model = get_model_for_use_case("any", low_latency=True)
        assert model == VoiceModel.ELEVEN_FLASH_V2_5

    def test_character_performance_returns_v3(self):
        """Test character_performance returns v3 (non-streaming)."""
        model = get_model_for_use_case("character_performance")
        assert model == VoiceModel.ELEVEN_V3

    def test_github_review_returns_v3(self):
        """Test github_review returns v3."""
        model = get_model_for_use_case("github_review")
        assert model == VoiceModel.ELEVEN_V3

    def test_multilingual_returns_multilingual_v2(self):
        """Test non-English language returns multilingual v2."""
        model = get_model_for_use_case("any", language="ja")
        assert model == VoiceModel.ELEVEN_MULTILINGUAL_V2

    def test_quick_response_returns_flash(self):
        """Test quick_response returns Flash v2.5."""
        model = get_model_for_use_case("quick_response")
        assert model == VoiceModel.ELEVEN_FLASH_V2_5

    def test_default_returns_v3(self):
        """Test default use case returns v3."""
        model = get_model_for_use_case("some_other_use_case")
        assert model == VoiceModel.ELEVEN_V3


# =============================================================================
# StreamConfig URL Generation Tests
# =============================================================================


class TestStreamConfigURLGeneration:
    """Additional tests for StreamConfig URL generation."""

    def test_websocket_url_structure(self):
        """Test complete WebSocket URL structure."""
        config = StreamConfig(
            text="Hello",
            voice_id="voice_123",
            auto_mode=True,
            region=StreamingRegion.GLOBAL,
            inactivity_timeout=30,
        )
        url = config.get_websocket_url()

        # Should contain base URL, voice_id, and all params
        assert "voice_123" in url
        assert "stream-input" in url
        assert "model_id=" in url
        assert "output_format=" in url
        assert "auto_mode=true" in url
        assert "inactivity_timeout=30" in url

    def test_websocket_url_with_custom_format(self):
        """Test WebSocket URL with custom output format."""
        config = StreamConfig(
            text="Hello",
            voice_id="voice_123",
            output_format=OutputFormat.OPUS_48000_64,
        )
        url = config.get_websocket_url()
        assert "output_format=opus_48000_64" in url

    def test_websocket_params_with_custom_voice_settings(self):
        """Test WebSocket params include custom voice settings."""
        settings = VoiceSettings(
            stability=0.3,
            similarity_boost=0.9,
            style=0.5,
            speed=1.1,
        )
        config = StreamConfig(
            text="Hello",
            voice_id="test",
            voice_settings=settings,
        )
        params = config.to_websocket_params()
        vs = params["voice_settings"]
        assert vs["stability"] == 0.3
        assert vs["similarity_boost"] == 0.9
        assert vs["style"] == 0.5
        assert vs["speed"] == 1.1


# =============================================================================
# Integration Behavior Tests (Model-Only)
# =============================================================================


class TestStreamingIntegrationBehavior:
    """Test expected behavior for streaming integration scenarios."""

    def test_virtual_character_optimal_config(self):
        """Test configuration optimized for virtual character use."""
        # This config should minimize latency for VRChat/virtual characters
        config = StreamConfig(
            text="Hello, I'm your virtual assistant!",
            voice_id="rachel",
            region=StreamingRegion.US,  # Closest regional endpoint
            output_format=OutputFormat.PCM_24000,  # No decompression needed
            auto_mode=True,  # Automatic generation triggers
        )

        # Verify optimal settings
        assert config.model == VoiceModel.ELEVEN_FLASH_V2_5  # 75ms latency
        assert config.output_format == OutputFormat.PCM_24000
        assert config.auto_mode is True

        # Verify URL contains optimization params
        url = config.get_websocket_url()
        assert "auto_mode=true" in url
        assert "eleven_flash_v2_5" in url

    def test_eu_user_optimal_config(self):
        """Test configuration optimized for EU users."""
        config = StreamConfig(
            text="Bonjour!",
            voice_id="nicole",
            region=StreamingRegion.EU,
        )

        url = config.get_websocket_url()
        assert "eu.residency" in url

    def test_global_preview_for_asia(self):
        """Test global preview endpoint for best non-US latency."""
        config = StreamConfig(
            text="Hello from Japan!",
            voice_id="adam",
            region=StreamingRegion.GLOBAL,
        )

        url = config.get_websocket_url()
        assert "global-preview" in url

    def test_speed_adjustment_for_fast_speech(self):
        """Test speed parameter for faster speech."""
        settings = VoiceSettings(speed=1.2)  # 20% faster
        config = StreamConfig(
            text="Quick message",
            voice_id="test",
            voice_settings=settings,
        )

        params = config.to_websocket_params()
        assert params["voice_settings"]["speed"] == 1.2

    def test_speed_adjustment_for_slow_speech(self):
        """Test speed parameter for slower, clearer speech."""
        settings = VoiceSettings(speed=0.8)  # 20% slower
        config = StreamConfig(
            text="Clear and slow message",
            voice_id="test",
            voice_settings=settings,
        )

        params = config.to_websocket_params()
        assert params["voice_settings"]["speed"] == 0.8
