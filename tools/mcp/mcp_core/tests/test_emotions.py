"""
Unit tests for the canonical emotion taxonomy.

Tests cover:
- CanonicalEmotion enum
- EmotionVector (PAD model) operations
- EmotionState transitions
- Bidirectional mappings
- Emotion inference
"""

from mcp_core.emotions import (
    AUDIO_TAG_TO_EMOTION,
    CANONICAL_TO_REACTION_TAGS,
    CANONICAL_TO_VIRTUAL_CHARACTER,
    EMOTION_TO_PAD,
    CanonicalEmotion,
    EmotionState,
    EmotionVector,
    avatar_to_emotion,
    blend_emotions,
    emotion_to_avatar,
    emotion_to_reaction_query,
    extract_emotions_from_text,
    find_closest_emotion,
    get_audio_tags_for_emotion,
    infer_emotion,
    infer_emotion_from_text,
    reaction_tags_to_emotion,
)

# =============================================================================
# CanonicalEmotion Tests
# =============================================================================


class TestCanonicalEmotion:
    """Tests for CanonicalEmotion enum."""

    def test_all_emotions_defined(self):
        """Test all 14 emotions are defined."""
        assert len(CanonicalEmotion) == 14

    def test_emotion_values(self):
        """Test emotion string values."""
        assert CanonicalEmotion.JOY.value == "joy"
        assert CanonicalEmotion.SADNESS.value == "sadness"
        assert CanonicalEmotion.ANGER.value == "anger"
        assert CanonicalEmotion.THINKING.value == "thinking"
        assert CanonicalEmotion.ATTENTIVE.value == "attentive"
        assert CanonicalEmotion.BORED.value == "bored"

    def test_all_emotions_have_pad_mapping(self):
        """Test every emotion has a PAD vector mapping."""
        for emotion in CanonicalEmotion:
            assert emotion in EMOTION_TO_PAD


# =============================================================================
# EmotionVector Tests
# =============================================================================


class TestEmotionVector:
    """Tests for EmotionVector (PAD model)."""

    def test_default_values(self):
        """Test default neutral vector."""
        vec = EmotionVector()
        assert vec.pleasure == 0.0
        assert vec.arousal == 0.0
        assert vec.dominance == 0.0

    def test_clamping(self):
        """Test values are clamped to [-1, 1]."""
        vec = EmotionVector(pleasure=2.0, arousal=-3.0, dominance=0.5)
        assert vec.pleasure == 1.0
        assert vec.arousal == -1.0
        assert vec.dominance == 0.5

    def test_lerp(self):
        """Test linear interpolation."""
        a = EmotionVector(0.0, 0.0, 0.0)
        b = EmotionVector(1.0, 1.0, 1.0)

        # Midpoint
        mid = a.lerp(b, 0.5)
        assert abs(mid.pleasure - 0.5) < 0.001
        assert abs(mid.arousal - 0.5) < 0.001
        assert abs(mid.dominance - 0.5) < 0.001

        # Full target
        full = a.lerp(b, 1.0)
        assert abs(full.pleasure - 1.0) < 0.001

        # No movement
        start = a.lerp(b, 0.0)
        assert abs(start.pleasure - 0.0) < 0.001

    def test_lerp_clamping(self):
        """Test lerp clamps t to [0, 1]."""
        a = EmotionVector(0.0, 0.0, 0.0)
        b = EmotionVector(1.0, 1.0, 1.0)

        # t > 1 should clamp to 1
        result = a.lerp(b, 1.5)
        assert abs(result.pleasure - 1.0) < 0.001

        # t < 0 should clamp to 0
        result = a.lerp(b, -0.5)
        assert abs(result.pleasure - 0.0) < 0.001

    def test_distance(self):
        """Test Euclidean distance."""
        a = EmotionVector(0.0, 0.0, 0.0)
        b = EmotionVector(1.0, 0.0, 0.0)

        assert abs(a.distance(b) - 1.0) < 0.001

        # Same vector should have 0 distance
        assert a.distance(a) == 0.0

    def test_scale(self):
        """Test intensity scaling."""
        vec = EmotionVector(0.8, 0.6, 0.4)
        scaled = vec.scale(0.5)

        assert abs(scaled.pleasure - 0.4) < 0.001
        assert abs(scaled.arousal - 0.3) < 0.001
        assert abs(scaled.dominance - 0.2) < 0.001

        # Zero intensity should give neutral
        zero = vec.scale(0.0)
        assert zero.pleasure == 0.0
        assert zero.arousal == 0.0
        assert zero.dominance == 0.0

    def test_magnitude(self):
        """Test magnitude calculation."""
        vec = EmotionVector(0.0, 0.0, 0.0)
        assert vec.magnitude() == 0.0

        vec2 = EmotionVector(1.0, 0.0, 0.0)
        assert abs(vec2.magnitude() - 1.0) < 0.001

    def test_to_dict_from_dict(self):
        """Test serialization round-trip."""
        original = EmotionVector(0.5, -0.3, 0.7)
        data = original.to_dict()

        restored = EmotionVector.from_dict(data)
        assert abs(restored.pleasure - original.pleasure) < 0.001
        assert abs(restored.arousal - original.arousal) < 0.001
        assert abs(restored.dominance - original.dominance) < 0.001

    def test_neutral_factory(self):
        """Test neutral vector factory."""
        neutral = EmotionVector.neutral()
        assert neutral.pleasure == 0.0
        assert neutral.arousal == 0.0
        assert neutral.dominance == 0.0


# =============================================================================
# EmotionState Tests
# =============================================================================


class TestEmotionState:
    """Tests for EmotionState."""

    def test_creation(self):
        """Test basic state creation."""
        state = EmotionState(CanonicalEmotion.JOY, intensity=0.7)
        assert state.emotion == CanonicalEmotion.JOY
        assert state.intensity == 0.7

    def test_intensity_clamping(self):
        """Test intensity is clamped to [0, 1]."""
        state = EmotionState(CanonicalEmotion.JOY, intensity=1.5)
        assert state.intensity == 1.0

        state2 = EmotionState(CanonicalEmotion.JOY, intensity=-0.5)
        assert state2.intensity == 0.0

    def test_pad_vector(self):
        """Test PAD vector property."""
        state = EmotionState(CanonicalEmotion.JOY, intensity=1.0)
        pad = state.pad_vector

        # JOY should be high pleasure, high arousal
        assert pad.pleasure > 0.5
        assert pad.arousal > 0.3

    def test_pad_vector_with_intensity(self):
        """Test PAD vector scales with intensity."""
        low = EmotionState(CanonicalEmotion.JOY, intensity=0.3)
        high = EmotionState(CanonicalEmotion.JOY, intensity=0.9)

        low_pad = low.pad_vector
        high_pad = high.pad_vector

        # Higher intensity should have larger magnitude
        assert high_pad.magnitude() > low_pad.magnitude()

    def test_secondary_emotion(self):
        """Test state with secondary emotion."""
        state = EmotionState(
            emotion=CanonicalEmotion.JOY,
            intensity=0.6,
            secondary_emotion=CanonicalEmotion.SURPRISE,
            secondary_intensity=0.3,
        )

        assert state.secondary_emotion == CanonicalEmotion.SURPRISE
        assert state.secondary_intensity == 0.3

        # PAD vector should be blended
        pad = state.pad_vector
        pure_joy = EmotionState(CanonicalEmotion.JOY, intensity=0.6).pad_vector
        assert pad != pure_joy  # Should be different due to blend

    def test_get_label(self):
        """Test intensity-appropriate labels."""
        low_joy = EmotionState(CanonicalEmotion.JOY, intensity=0.2)
        high_joy = EmotionState(CanonicalEmotion.JOY, intensity=0.9)

        # Low intensity should get milder label
        low_label = low_joy.get_label()
        high_label = high_joy.get_label()

        assert low_label in ["content", "pleased"]
        assert high_label in ["excited", "elated", "ecstatic"]

    def test_to_dict_from_dict(self):
        """Test serialization round-trip."""
        original = EmotionState(
            emotion=CanonicalEmotion.ANGER,
            intensity=0.7,
            secondary_emotion=CanonicalEmotion.FEAR,
            secondary_intensity=0.2,
        )

        data = original.to_dict()
        restored = EmotionState.from_dict(data)

        assert restored.emotion == original.emotion
        assert abs(restored.intensity - original.intensity) < 0.001
        assert restored.secondary_emotion == original.secondary_emotion


# =============================================================================
# find_closest_emotion Tests
# =============================================================================


class TestFindClosestEmotion:
    """Tests for find_closest_emotion function."""

    def test_exact_match(self):
        """Test exact PAD vector matches correct emotion."""
        joy_pad = EMOTION_TO_PAD[CanonicalEmotion.JOY]
        emotion, confidence = find_closest_emotion(joy_pad)

        assert emotion == CanonicalEmotion.JOY
        assert confidence > 0.9

    def test_neutral_returns_calm(self):
        """Test neutral PAD returns calm-ish emotion."""
        neutral = EmotionVector(0.0, 0.0, 0.0)
        emotion, _ = find_closest_emotion(neutral)

        # Neutral is close to calm in PAD space
        assert emotion in [CanonicalEmotion.CALM, CanonicalEmotion.THINKING]

    def test_extreme_anger(self):
        """Test high arousal, negative pleasure detects anger."""
        angry_pad = EmotionVector(-0.6, +0.9, +0.7)
        emotion, confidence = find_closest_emotion(angry_pad)

        assert emotion == CanonicalEmotion.ANGER


# =============================================================================
# blend_emotions Tests
# =============================================================================


class TestBlendEmotions:
    """Tests for blend_emotions function."""

    def test_single_emotion(self):
        """Test single emotion returns that emotion."""
        result = blend_emotions([(CanonicalEmotion.JOY, 0.8)])
        assert result.emotion == CanonicalEmotion.JOY
        assert abs(result.intensity - 0.8) < 0.001

    def test_empty_list(self):
        """Test empty list returns calm."""
        result = blend_emotions([])
        assert result.emotion == CanonicalEmotion.CALM
        assert result.intensity == 0.0

    def test_two_emotions(self):
        """Test blending two emotions."""
        result = blend_emotions(
            [
                (CanonicalEmotion.JOY, 0.6),
                (CanonicalEmotion.SURPRISE, 0.4),
            ]
        )

        # Primary should be higher intensity one
        assert result.emotion == CanonicalEmotion.JOY
        assert result.secondary_emotion == CanonicalEmotion.SURPRISE


# =============================================================================
# Audio Tag Mappings Tests
# =============================================================================


class TestAudioTagMappings:
    """Tests for ElevenLabs audio tag mappings."""

    def test_laughs_maps_to_joy(self):
        """Test [laughs] maps to JOY."""
        emotion, intensity = AUDIO_TAG_TO_EMOTION["[laughs]"]
        assert emotion == CanonicalEmotion.JOY
        assert intensity > 0.5

    def test_sighs_maps_to_sadness(self):
        """Test [sighs] maps to SADNESS."""
        emotion, intensity = AUDIO_TAG_TO_EMOTION["[sighs]"]
        assert emotion == CanonicalEmotion.SADNESS

    def test_get_audio_tags_for_emotion(self):
        """Test getting tags for an emotion."""
        tags = get_audio_tags_for_emotion(CanonicalEmotion.JOY, intensity=0.7)
        assert len(tags) > 0
        assert all(tag.startswith("[") for tag in tags)

    def test_extract_emotions_from_text(self):
        """Test extracting emotions from text with tags."""
        text = "[laughs] That's so funny! [excited]"
        emotions = extract_emotions_from_text(text)

        assert len(emotions) >= 2
        assert any(e == CanonicalEmotion.JOY for e, _ in emotions)

    def test_extract_no_tags(self):
        """Test extracting from text without tags."""
        text = "Hello, how are you?"
        emotions = extract_emotions_from_text(text)
        assert len(emotions) == 0


# =============================================================================
# Virtual Character Mappings Tests
# =============================================================================


class TestVirtualCharacterMappings:
    """Tests for Virtual Character emotion mappings."""

    def test_all_emotions_have_avatar_mapping(self):
        """Test all canonical emotions map to avatar."""
        for emotion in CanonicalEmotion:
            assert emotion in CANONICAL_TO_VIRTUAL_CHARACTER

    def test_emotion_to_avatar(self):
        """Test emotion to avatar parameter conversion."""
        result = emotion_to_avatar(CanonicalEmotion.JOY, intensity=0.8)

        assert "emotion" in result
        assert "emotion_intensity" in result
        assert result["emotion"] == "happy"
        assert 0 <= result["emotion_intensity"] <= 1

    def test_avatar_to_emotion(self):
        """Test avatar to emotion conversion."""
        state = avatar_to_emotion("happy", intensity=0.7)

        assert state.emotion == CanonicalEmotion.JOY
        assert state.intensity == 0.7


# =============================================================================
# Reaction Query Mappings Tests
# =============================================================================


class TestReactionQueryMappings:
    """Tests for Reaction Search query mappings."""

    def test_all_emotions_have_reaction_tags(self):
        """Test all emotions have reaction tags."""
        for emotion in CanonicalEmotion:
            assert emotion in CANONICAL_TO_REACTION_TAGS

    def test_emotion_to_reaction_query(self):
        """Test generating reaction search query."""
        query = emotion_to_reaction_query(CanonicalEmotion.JOY, intensity=0.8, context="fixing a bug")

        assert len(query) > 0
        assert "fixing a bug" in query

    def test_reaction_tags_to_emotion(self):
        """Test inferring emotion from reaction tags."""
        tags = ["happy", "excited", "celebrating"]
        result = reaction_tags_to_emotion(tags)

        assert result is not None
        assert result.emotion == CanonicalEmotion.JOY


# =============================================================================
# Inference Tests
# =============================================================================


class TestEmotionInference:
    """Tests for emotion inference from text."""

    def test_infer_joy(self):
        """Test inferring joy from happy text."""
        result = infer_emotion_from_text("I'm so happy and excited!")

        assert result.primary_emotion == CanonicalEmotion.JOY
        assert result.confidence > 0.3

    def test_infer_sadness(self):
        """Test inferring sadness from sad text."""
        result = infer_emotion_from_text("I'm feeling sad and disappointed")

        assert result.primary_emotion == CanonicalEmotion.SADNESS

    def test_infer_anger(self):
        """Test inferring anger from angry text."""
        result = infer_emotion_from_text("This is so frustrating, I'm angry!")

        assert result.primary_emotion == CanonicalEmotion.ANGER

    def test_infer_confusion(self):
        """Test inferring confusion."""
        result = infer_emotion_from_text("I'm confused, what??? Huh?")

        assert result.primary_emotion == CanonicalEmotion.CONFUSION

    def test_infer_with_audio_tags(self):
        """Test inference includes audio tag detection."""
        result = infer_emotion_from_text("[laughs] This is great!")

        assert result.primary_emotion == CanonicalEmotion.JOY
        assert result.confidence > 0.5

    def test_infer_neutral_text(self):
        """Test inference on neutral text."""
        result = infer_emotion_from_text("The weather is cloudy today.")

        assert result.primary_emotion == CanonicalEmotion.CALM
        assert result.confidence < 0.5

    def test_infer_emotion_function(self):
        """Test the main infer_emotion function."""
        # This should work even without ML model
        state = infer_emotion("I'm really excited about this feature!")

        assert isinstance(state, EmotionState)
        assert state.emotion in [CanonicalEmotion.JOY, CanonicalEmotion.SURPRISE]


# =============================================================================
# PAD Vector Property Tests
# =============================================================================


class TestPADVectorProperties:
    """Tests for PAD vector semantic properties."""

    def test_joy_is_pleasant(self):
        """Test JOY has positive pleasure."""
        pad = EMOTION_TO_PAD[CanonicalEmotion.JOY]
        assert pad.pleasure > 0

    def test_sadness_is_unpleasant(self):
        """Test SADNESS has negative pleasure."""
        pad = EMOTION_TO_PAD[CanonicalEmotion.SADNESS]
        assert pad.pleasure < 0

    def test_anger_is_high_arousal(self):
        """Test ANGER has high arousal."""
        pad = EMOTION_TO_PAD[CanonicalEmotion.ANGER]
        assert pad.arousal > 0.5

    def test_calm_is_low_arousal(self):
        """Test CALM has low arousal."""
        pad = EMOTION_TO_PAD[CanonicalEmotion.CALM]
        assert pad.arousal < 0

    def test_fear_is_low_dominance(self):
        """Test FEAR has low dominance (submissive)."""
        pad = EMOTION_TO_PAD[CanonicalEmotion.FEAR]
        assert pad.dominance < 0

    def test_contempt_is_high_dominance(self):
        """Test CONTEMPT has high dominance."""
        pad = EMOTION_TO_PAD[CanonicalEmotion.CONTEMPT]
        assert pad.dominance > 0.5
