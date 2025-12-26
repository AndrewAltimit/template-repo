"""
Unit tests for the expression orchestration module.

Tests cover:
- Expression types and dataclasses
- ExpressionOrchestrator coordination
- Multi-modal expression with mocked MCP clients
"""

from unittest.mock import AsyncMock

import pytest

from mcp_core.emotions import CanonicalEmotion, EmotionState
from mcp_core.expression import (
    AudioResult,
    AvatarResult,
    ExpressionConfig,
    ExpressionOrchestrator,
    ExpressionResult,
    MCPClients,
    Modality,
    ReactionResult,
)

# =============================================================================
# Expression Types Tests
# =============================================================================


class TestAudioResult:
    """Tests for AudioResult dataclass."""

    def test_creation(self):
        """Test basic creation."""
        result = AudioResult(
            local_path="/tmp/audio.mp3",
            duration=2.5,
            voice_id="Rachel",
            audio_tags=["[laughs]", "[excited]"],
        )

        assert result.local_path == "/tmp/audio.mp3"
        assert result.duration == 2.5
        assert result.voice_id == "Rachel"
        assert "[laughs]" in result.audio_tags

    def test_to_dict(self):
        """Test dictionary conversion."""
        result = AudioResult(
            local_path="/tmp/audio.mp3",
            duration=2.5,
            voice_id="Rachel",
        )

        data = result.to_dict()
        assert data["local_path"] == "/tmp/audio.mp3"
        assert data["duration"] == 2.5
        assert data["voice_id"] == "Rachel"


class TestAvatarResult:
    """Tests for AvatarResult dataclass."""

    def test_creation(self):
        """Test basic creation."""
        result = AvatarResult(
            emotion="happy",
            emotion_intensity=0.8,
            gesture="wave",
        )

        assert result.emotion == "happy"
        assert result.emotion_intensity == 0.8
        assert result.gesture == "wave"

    def test_to_dict(self):
        """Test dictionary conversion."""
        result = AvatarResult(
            emotion="thinking",
            emotion_intensity=0.5,
        )

        data = result.to_dict()
        assert data["emotion"] == "thinking"
        assert data["emotion_intensity"] == 0.5
        assert data["gesture"] is None


class TestReactionResult:
    """Tests for ReactionResult dataclass."""

    def test_creation(self):
        """Test basic creation."""
        result = ReactionResult(
            reaction_id="felix",
            markdown="![Reaction](https://example.com/felix.png)",
            url="https://example.com/felix.png",
            similarity=0.85,
            tags=["happy", "excited"],
        )

        assert result.reaction_id == "felix"
        assert result.similarity == 0.85
        assert "happy" in result.tags

    def test_to_dict(self):
        """Test dictionary conversion."""
        result = ReactionResult(
            reaction_id="nervous_sweat",
            markdown="![Reaction](url)",
            url="url",
            similarity=0.7,
        )

        data = result.to_dict()
        assert data["reaction_id"] == "nervous_sweat"
        assert data["similarity"] == 0.7


class TestExpressionResult:
    """Tests for ExpressionResult dataclass."""

    def test_creation_empty(self):
        """Test creation with no modalities."""
        result = ExpressionResult()

        assert result.audio is None
        assert result.avatar is None
        assert result.reaction is None
        assert result.modalities_used == []

    def test_modalities_used(self):
        """Test modalities_used property."""
        result = ExpressionResult(
            audio=AudioResult(local_path="", duration=0, voice_id=""),
            avatar=AvatarResult(emotion="happy", emotion_intensity=0.5),
        )

        modalities = result.modalities_used
        assert Modality.VOICE in modalities
        assert Modality.AVATAR in modalities
        assert Modality.REACTION not in modalities

    def test_to_dict(self):
        """Test dictionary conversion."""
        result = ExpressionResult(
            text="Hello world",
            emotion_name="joy",
            intensity=0.7,
            remembered=True,
        )

        data = result.to_dict()
        assert data["text"] == "Hello world"
        assert data["emotion_name"] == "joy"
        assert data["intensity"] == 0.7
        assert data["remembered"] is True


class TestExpressionConfig:
    """Tests for ExpressionConfig dataclass."""

    def test_defaults(self):
        """Test default values."""
        config = ExpressionConfig()

        assert config.default_voice_id == "Rachel"
        assert config.default_intensity == 0.5
        assert Modality.VOICE in config.default_modalities
        assert config.remember_expressions is True

    def test_custom_values(self):
        """Test custom configuration."""
        config = ExpressionConfig(
            default_voice_id="Adam",
            default_intensity=0.8,
            default_modalities=[Modality.VOICE],
            remember_expressions=False,
        )

        assert config.default_voice_id == "Adam"
        assert config.default_intensity == 0.8
        assert len(config.default_modalities) == 1

    def test_to_dict(self):
        """Test dictionary conversion."""
        config = ExpressionConfig()
        data = config.to_dict()

        assert "default_voice_id" in data
        assert "default_modalities" in data


# =============================================================================
# MCPClients Tests
# =============================================================================


class TestMCPClients:
    """Tests for MCPClients container."""

    def test_creation_empty(self):
        """Test creation with no clients."""
        clients = MCPClients()

        assert clients.synthesize_speech is None
        assert clients.send_animation is None
        assert clients.search_reactions is None

    def test_creation_with_mocks(self):
        """Test creation with mock functions."""
        mock_synth = AsyncMock()
        mock_anim = AsyncMock()

        clients = MCPClients(
            synthesize_speech=mock_synth,
            send_animation=mock_anim,
        )

        assert clients.synthesize_speech is mock_synth
        assert clients.send_animation is mock_anim


# =============================================================================
# ExpressionOrchestrator Tests
# =============================================================================


class TestExpressionOrchestrator:
    """Tests for ExpressionOrchestrator."""

    @pytest.fixture
    def mock_synthesize(self):
        """Create mock synthesize function."""
        mock = AsyncMock(
            return_value={
                "local_path": "/tmp/audio.mp3",
                "duration": 2.0,
            }
        )
        return mock

    @pytest.fixture
    def mock_send_animation(self):
        """Create mock send_animation function."""
        return AsyncMock(return_value={"success": True})

    @pytest.fixture
    def mock_play_audio(self):
        """Create mock play_audio function."""
        return AsyncMock(return_value={"success": True})

    @pytest.fixture
    def mock_search_reactions(self):
        """Create mock search_reactions function."""
        return AsyncMock(
            return_value={
                "results": [
                    {
                        "id": "felix",
                        "markdown": "![Reaction](url)",
                        "url": "url",
                        "similarity": 0.9,
                        "tags": ["happy"],
                    }
                ]
            }
        )

    @pytest.fixture
    def mock_store_facts(self):
        """Create mock store_facts function."""
        return AsyncMock(return_value={"success": True})

    @pytest.fixture
    def mock_search_memories(self):
        """Create mock search_memories function."""
        return AsyncMock(return_value={"results": []})

    @pytest.fixture
    def orchestrator(
        self,
        mock_synthesize,
        mock_send_animation,
        mock_play_audio,
        mock_search_reactions,
        mock_store_facts,
        mock_search_memories,
    ):
        """Create orchestrator with all mocks."""
        clients = MCPClients(
            synthesize_speech=mock_synthesize,
            send_animation=mock_send_animation,
            play_audio=mock_play_audio,
            search_reactions=mock_search_reactions,
            store_facts=mock_store_facts,
            search_memories=mock_search_memories,
        )
        return ExpressionOrchestrator(clients=clients)

    @pytest.mark.asyncio
    async def test_express_basic(self, orchestrator):
        """Test basic expression."""
        result = await orchestrator.express(
            text="Hello world!",
            emotion=CanonicalEmotion.JOY,
        )

        assert result.text == "Hello world!"
        assert result.emotion_name == "joy"
        assert result.audio is not None
        assert result.avatar is not None
        assert result.reaction is not None

    @pytest.mark.asyncio
    async def test_express_with_emotion_state(self, orchestrator):
        """Test expression with EmotionState."""
        state = EmotionState(
            emotion=CanonicalEmotion.SADNESS,
            intensity=0.8,
        )

        result = await orchestrator.express(
            text="That's unfortunate",
            emotion=state,
        )

        assert result.emotion_name == "sadness"
        assert result.intensity == 0.8

    @pytest.mark.asyncio
    async def test_express_specific_modalities(self, orchestrator, mock_synthesize):
        """Test expression with specific modalities only."""
        result = await orchestrator.express(
            text="Just voice",
            emotion=CanonicalEmotion.CALM,
            modalities=[Modality.VOICE],
        )

        assert result.audio is not None
        assert result.avatar is None  # Not requested
        assert result.reaction is None  # Not requested

    @pytest.mark.asyncio
    async def test_express_custom_voice(self, orchestrator, mock_synthesize):
        """Test expression with custom voice."""
        await orchestrator.express(
            text="Custom voice",
            emotion=CanonicalEmotion.JOY,
            voice_id="Adam",
        )

        # Check that synthesize was called with Adam
        call_kwargs = mock_synthesize.call_args.kwargs
        assert call_kwargs["voice_id"] == "Adam"

    @pytest.mark.asyncio
    async def test_express_with_gesture(self, orchestrator, mock_send_animation):
        """Test expression with gesture."""
        await orchestrator.express(
            text="Waving hello",
            emotion=CanonicalEmotion.JOY,
            gesture="wave",
            modalities=[Modality.AVATAR],
        )

        call_kwargs = mock_send_animation.call_args.kwargs
        assert call_kwargs["gesture"] == "wave"

    @pytest.mark.asyncio
    async def test_express_remember_pattern(self, orchestrator, mock_store_facts):
        """Test that expression patterns are stored."""
        await orchestrator.express(
            text="Remember this",
            emotion=CanonicalEmotion.THINKING,
            remember=True,
        )

        mock_store_facts.assert_called_once()
        call_kwargs = mock_store_facts.call_args.kwargs
        assert call_kwargs["namespace"] == "personality/expression_patterns"

    @pytest.mark.asyncio
    async def test_express_no_remember(self, orchestrator, mock_store_facts):
        """Test that patterns are not stored when remember=False."""
        await orchestrator.express(
            text="Don't remember",
            emotion=CanonicalEmotion.CALM,
            remember=False,
        )

        mock_store_facts.assert_not_called()

    @pytest.mark.asyncio
    async def test_express_audio_plays_through_avatar(self, orchestrator, mock_play_audio):
        """Test that audio plays through avatar when both available."""
        await orchestrator.express(
            text="Play through avatar",
            emotion=CanonicalEmotion.JOY,
            modalities=[Modality.VOICE, Modality.AVATAR],
        )

        mock_play_audio.assert_called_once()

    @pytest.mark.asyncio
    async def test_express_with_context(self, orchestrator, mock_search_reactions):
        """Test expression with context affects reaction search."""
        await orchestrator.express(
            text="Bug fixed",
            emotion=CanonicalEmotion.JOY,
            context="debugging session",
            modalities=[Modality.REACTION],
        )

        call_kwargs = mock_search_reactions.call_args.kwargs
        # Query should include context
        assert "query" in call_kwargs

    @pytest.mark.asyncio
    async def test_express_with_arc(self, orchestrator):
        """Test express_with_arc for emotional sequences."""
        segments = [
            {"text": "Starting...", "emotion": CanonicalEmotion.CALM},
            {"text": "Working on it...", "emotion": CanonicalEmotion.THINKING},
            {"text": "Done!", "emotion": CanonicalEmotion.JOY},
        ]

        results = await orchestrator.express_with_arc(segments)

        assert len(results) == 3
        assert results[0].emotion_name == "calm"
        assert results[1].emotion_name == "thinking"
        assert results[2].emotion_name == "joy"

    def test_get_config(self, orchestrator):
        """Test getting configuration."""
        config = orchestrator.get_config()

        assert "default_voice_id" in config
        assert "default_modalities" in config

    def test_update_config(self, orchestrator):
        """Test updating configuration."""
        orchestrator.update_config(default_voice_id="Adam")

        assert orchestrator.config.default_voice_id == "Adam"

    @pytest.mark.asyncio
    async def test_no_clients_handles_gracefully(self):
        """Test that missing clients are handled gracefully."""
        orchestrator = ExpressionOrchestrator(clients=MCPClients())

        result = await orchestrator.express(
            text="No clients",
            emotion=CanonicalEmotion.CALM,
        )

        # Should still return a result, just with no modality results
        assert result.text == "No clients"
        assert result.audio is None
        assert result.avatar is None
        assert result.reaction is None


# =============================================================================
# Voice Preference Tests
# =============================================================================


class TestVoicePreferences:
    """Tests for voice preference memory integration."""

    @pytest.mark.asyncio
    async def test_preferred_voice_from_memory(self):
        """Test that preferred voice is retrieved from memory."""
        mock_search = AsyncMock(return_value={"results": [{"content": "Rachel voice works well for joy expressions"}]})
        mock_synth = AsyncMock(
            return_value={
                "local_path": "/tmp/audio.mp3",
                "duration": 1.0,
            }
        )

        clients = MCPClients(
            synthesize_speech=mock_synth,
            search_memories=mock_search,
        )
        orchestrator = ExpressionOrchestrator(clients=clients)

        await orchestrator.express(
            text="Test",
            emotion=CanonicalEmotion.JOY,
            modalities=[Modality.VOICE],
        )

        # Voice should be Rachel from memory
        call_kwargs = mock_synth.call_args.kwargs
        assert call_kwargs["voice_id"] == "Rachel"


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for error handling in orchestrator."""

    @pytest.mark.asyncio
    async def test_synthesize_failure_continues(self):
        """Test that synthesis failure doesn't break other modalities."""
        mock_synth = AsyncMock(side_effect=Exception("Synthesis failed"))
        mock_anim = AsyncMock(return_value={"success": True})

        clients = MCPClients(
            synthesize_speech=mock_synth,
            send_animation=mock_anim,
        )
        orchestrator = ExpressionOrchestrator(clients=clients)

        result = await orchestrator.express(
            text="Test",
            emotion=CanonicalEmotion.JOY,
            modalities=[Modality.VOICE, Modality.AVATAR],
        )

        # Avatar should still work
        assert result.audio is None
        assert result.avatar is not None

    @pytest.mark.asyncio
    async def test_all_failures_returns_empty_result(self):
        """Test that all failures still return a valid result."""
        mock_synth = AsyncMock(side_effect=Exception("Failed"))
        mock_anim = AsyncMock(side_effect=Exception("Failed"))
        mock_search = AsyncMock(side_effect=Exception("Failed"))

        clients = MCPClients(
            synthesize_speech=mock_synth,
            send_animation=mock_anim,
            search_reactions=mock_search,
        )
        orchestrator = ExpressionOrchestrator(clients=clients)

        result = await orchestrator.express(
            text="Test",
            emotion=CanonicalEmotion.JOY,
        )

        # Result should still be valid
        assert result.text == "Test"
        assert result.emotion_name == "joy"
        assert result.modalities_used == []
