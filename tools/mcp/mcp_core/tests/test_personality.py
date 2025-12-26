"""
Unit tests for the personality memory module.

Tests cover:
- VoicePreference data class
- ExpressionPattern data class
- ReactionUsage data class
- PersonalityMemory manager
"""

from unittest.mock import AsyncMock

import pytest

from mcp_core.emotions import CanonicalEmotion
from mcp_core.personality import (
    ExpressionPattern,
    PersonalityMemory,
    ReactionUsage,
    VoicePreference,
)
from mcp_core.personality.memory import (
    NAMESPACE_AVATAR_SETTINGS,
    NAMESPACE_EXPRESSION_PATTERNS,
    NAMESPACE_REACTION_HISTORY,
    NAMESPACE_VOICE_PREFERENCES,
)

# =============================================================================
# VoicePreference Tests
# =============================================================================


class TestVoicePreference:
    """Tests for VoicePreference data class."""

    def test_creation(self):
        """Test basic creation."""
        pref = VoicePreference(
            voice_id="Rachel",
            use_case="code_review",
            preset="github_review",
            effectiveness=0.8,
            notes="Professional and clear",
        )

        assert pref.voice_id == "Rachel"
        assert pref.use_case == "code_review"
        assert pref.preset == "github_review"
        assert pref.effectiveness == 0.8

    def test_to_fact_high_effectiveness(self):
        """Test fact generation for high effectiveness."""
        pref = VoicePreference(
            voice_id="Rachel",
            use_case="code_review",
            effectiveness=0.8,
        )

        fact = pref.to_fact()
        assert "Rachel" in fact
        assert "well" in fact  # "works well" for high effectiveness
        assert "code_review" in fact

    def test_to_fact_low_effectiveness(self):
        """Test fact generation for low effectiveness."""
        pref = VoicePreference(
            voice_id="Adam",
            use_case="narration",
            effectiveness=0.4,
        )

        fact = pref.to_fact()
        assert "Adam" in fact
        assert "okay" in fact  # "works okay" for low effectiveness

    def test_to_fact_with_preset(self):
        """Test fact includes preset when present."""
        pref = VoicePreference(
            voice_id="Rachel",
            use_case="tutorial",
            preset="audiobook",
            effectiveness=0.7,
        )

        fact = pref.to_fact()
        assert "audiobook" in fact

    def test_to_fact_with_notes(self):
        """Test fact includes notes when present."""
        pref = VoicePreference(
            voice_id="Rachel",
            use_case="review",
            effectiveness=0.6,
            notes="Good for technical content",
        )

        fact = pref.to_fact()
        assert "Good for technical content" in fact


# =============================================================================
# ExpressionPattern Tests
# =============================================================================


class TestExpressionPattern:
    """Tests for ExpressionPattern data class."""

    def test_creation(self):
        """Test basic creation."""
        pattern = ExpressionPattern(
            emotion=CanonicalEmotion.JOY,
            intensity=0.7,
            audio_tags=["[laughs]", "[excited]"],
            avatar_emotion="happy",
            avatar_gesture="cheer",
            context="bug fix",
            effectiveness=0.8,
        )

        assert pattern.emotion == CanonicalEmotion.JOY
        assert pattern.intensity == 0.7
        assert "[laughs]" in pattern.audio_tags
        assert pattern.avatar_emotion == "happy"

    def test_to_fact(self):
        """Test fact generation."""
        pattern = ExpressionPattern(
            emotion=CanonicalEmotion.JOY,
            audio_tags=["[laughs]"],
            avatar_emotion="happy",
            context="celebrating",
            effectiveness=0.8,
        )

        fact = pattern.to_fact()
        assert "joy" in fact
        assert "happy" in fact
        assert "[laughs]" in fact
        assert "celebrating" in fact
        assert "very effective" in fact

    def test_to_fact_with_gesture(self):
        """Test fact includes gesture."""
        pattern = ExpressionPattern(
            emotion=CanonicalEmotion.THINKING,
            avatar_emotion="neutral",
            avatar_gesture="thinking",
        )

        fact = pattern.to_fact()
        assert "thinking" in fact.lower()


# =============================================================================
# ReactionUsage Tests
# =============================================================================


class TestReactionUsage:
    """Tests for ReactionUsage data class."""

    def test_creation(self):
        """Test basic creation."""
        usage = ReactionUsage(
            reaction_id="felix",
            context="PR merge",
            emotion=CanonicalEmotion.JOY,
            user_response="positive",
            effectiveness=0.9,
        )

        assert usage.reaction_id == "felix"
        assert usage.emotion == CanonicalEmotion.JOY
        assert usage.user_response == "positive"

    def test_to_fact_positive(self):
        """Test fact generation for positive response."""
        usage = ReactionUsage(
            reaction_id="nervous_sweat",
            context="bug fix relief",
            user_response="positive",
        )

        fact = usage.to_fact()
        assert "nervous_sweat" in fact
        assert "bug fix relief" in fact
        assert "positively" in fact

    def test_to_fact_negative(self):
        """Test fact generation for negative response."""
        usage = ReactionUsage(
            reaction_id="confused_miku",
            context="error message",
            user_response="negative",
        )

        fact = usage.to_fact()
        assert "negatively" in fact

    def test_to_fact_with_emotion(self):
        """Test fact includes emotion when present."""
        usage = ReactionUsage(
            reaction_id="thinking_foxgirl",
            context="debugging",
            emotion=CanonicalEmotion.THINKING,
        )

        fact = usage.to_fact()
        assert "thinking" in fact


# =============================================================================
# PersonalityMemory Tests
# =============================================================================


class TestPersonalityMemory:
    """Tests for PersonalityMemory manager."""

    @pytest.fixture
    def mock_store(self):
        """Create mock store_facts function."""
        return AsyncMock(return_value={"success": True})

    @pytest.fixture
    def mock_search(self):
        """Create mock search_memories function."""
        return AsyncMock(return_value={"results": []})

    @pytest.fixture
    def memory(self, mock_store, mock_search):
        """Create PersonalityMemory with mocks."""
        return PersonalityMemory(
            store_facts_fn=mock_store,
            search_memories_fn=mock_search,
        )

    @pytest.mark.asyncio
    async def test_store_voice_preference(self, memory, mock_store):
        """Test storing voice preference."""
        result = await memory.store_voice_preference(
            voice_id="Rachel",
            use_case="code_review",
            preset="github_review",
            effectiveness=0.8,
            notes="Works well",
        )

        assert result["success"]
        mock_store.assert_called_once()

        # Check namespace
        call_kwargs = mock_store.call_args.kwargs
        assert call_kwargs["namespace"] == NAMESPACE_VOICE_PREFERENCES

        # Check fact content
        facts = call_kwargs["facts"]
        assert len(facts) == 1
        assert "Rachel" in facts[0]

    @pytest.mark.asyncio
    async def test_get_voice_preferences(self, memory, mock_search):
        """Test getting voice preferences."""
        await memory.get_voice_preferences("code_review")

        mock_search.assert_called_once()
        call_kwargs = mock_search.call_args.kwargs
        assert call_kwargs["namespace"] == NAMESPACE_VOICE_PREFERENCES
        assert "code_review" in call_kwargs["query"]

    @pytest.mark.asyncio
    async def test_store_expression_pattern(self, memory, mock_store):
        """Test storing expression pattern."""
        result = await memory.store_expression_pattern(
            emotion=CanonicalEmotion.JOY,
            intensity=0.7,
            audio_tags=["[laughs]"],
            avatar_emotion="happy",
            avatar_gesture="cheer",
            context="feature complete",
            effectiveness=0.8,
        )

        assert result["success"]
        call_kwargs = mock_store.call_args.kwargs
        assert call_kwargs["namespace"] == NAMESPACE_EXPRESSION_PATTERNS

    @pytest.mark.asyncio
    async def test_get_expression_patterns(self, memory, mock_search):
        """Test getting expression patterns."""
        await memory.get_expression_patterns(
            emotion=CanonicalEmotion.SADNESS,
            context="bug report",
        )

        mock_search.assert_called_once()
        call_kwargs = mock_search.call_args.kwargs
        assert call_kwargs["namespace"] == NAMESPACE_EXPRESSION_PATTERNS
        assert "sadness" in call_kwargs["query"]

    @pytest.mark.asyncio
    async def test_store_reaction_usage(self, memory, mock_store):
        """Test storing reaction usage."""
        result = await memory.store_reaction_usage(
            reaction_id="felix",
            context="PR merge celebration",
            emotion=CanonicalEmotion.JOY,
            user_response="positive",
            effectiveness=0.9,
        )

        assert result["success"]
        call_kwargs = mock_store.call_args.kwargs
        assert call_kwargs["namespace"] == NAMESPACE_REACTION_HISTORY

    @pytest.mark.asyncio
    async def test_get_reaction_history(self, memory, mock_search):
        """Test getting reaction history."""
        await memory.get_reaction_history(
            context="debugging",
            emotion=CanonicalEmotion.CONFUSION,
        )

        mock_search.assert_called_once()
        call_kwargs = mock_search.call_args.kwargs
        assert call_kwargs["namespace"] == NAMESPACE_REACTION_HISTORY

    @pytest.mark.asyncio
    async def test_store_avatar_setting(self, memory, mock_store):
        """Test storing avatar setting."""
        result = await memory.store_avatar_setting(
            setting_type="gesture",
            value="wave",
            context="greeting",
            effectiveness=0.7,
        )

        assert result["success"]
        call_kwargs = mock_store.call_args.kwargs
        assert call_kwargs["namespace"] == NAMESPACE_AVATAR_SETTINGS

    @pytest.mark.asyncio
    async def test_get_avatar_settings(self, memory, mock_search):
        """Test getting avatar settings."""
        await memory.get_avatar_settings(
            setting_type="gesture",
            context="greeting",
        )

        mock_search.assert_called_once()
        call_kwargs = mock_search.call_args.kwargs
        assert call_kwargs["namespace"] == NAMESPACE_AVATAR_SETTINGS

    @pytest.mark.asyncio
    async def test_store_emotional_arc(self, memory, mock_store):
        """Test storing emotional arc."""
        result = await memory.store_emotional_arc(
            start_emotion=CanonicalEmotion.ANGER,
            end_emotion=CanonicalEmotion.JOY,
            context="Debugging session resolved issue",
            session_id="session-123",
        )

        assert result["success"]
        facts = mock_store.call_args.kwargs["facts"]
        assert "anger" in facts[0]
        assert "joy" in facts[0]

    @pytest.mark.asyncio
    async def test_store_interaction_pattern(self, memory, mock_store):
        """Test storing interaction pattern."""
        result = await memory.store_interaction_pattern(
            pattern="Explain with examples first",
            outcome="User understood quickly",
            effectiveness=0.8,
        )

        assert result["success"]
        facts = mock_store.call_args.kwargs["facts"]
        assert "Pattern:" in facts[0]
        assert "effective" in facts[0]

    @pytest.mark.asyncio
    async def test_no_provider_raises_error(self):
        """Test that missing provider raises error."""
        memory = PersonalityMemory()

        with pytest.raises(RuntimeError, match="No memory provider"):
            await memory.store_voice_preference(
                voice_id="test",
                use_case="test",
            )


# =============================================================================
# Namespace Constants Tests
# =============================================================================


class TestNamespaceConstants:
    """Tests for namespace constants."""

    def test_voice_preferences_namespace(self):
        """Test voice preferences namespace format."""
        assert "/" in NAMESPACE_VOICE_PREFERENCES
        assert NAMESPACE_VOICE_PREFERENCES.startswith("personality/")

    def test_expression_patterns_namespace(self):
        """Test expression patterns namespace format."""
        assert "/" in NAMESPACE_EXPRESSION_PATTERNS
        assert NAMESPACE_EXPRESSION_PATTERNS.startswith("personality/")

    def test_reaction_history_namespace(self):
        """Test reaction history namespace format."""
        assert "/" in NAMESPACE_REACTION_HISTORY
        assert NAMESPACE_REACTION_HISTORY.startswith("personality/")

    def test_avatar_settings_namespace(self):
        """Test avatar settings namespace format."""
        assert "/" in NAMESPACE_AVATAR_SETTINGS
        assert NAMESPACE_AVATAR_SETTINGS.startswith("personality/")
