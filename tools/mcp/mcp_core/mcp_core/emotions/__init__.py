"""
Unified Emotion Taxonomy for MCP Servers.

This module provides a canonical emotion model that all MCP servers can use
for consistent emotion representation across voice, avatar, and reactions.

Components:
- taxonomy: CanonicalEmotion enum, EmotionVector (PAD model), EmotionState
- mappings: Bidirectional mappings for ElevenLabs, Virtual Character, Reaction Search
- inference: Emotion detection from text using rules and/or ML

Usage:
    from mcp_core.emotions import (
        CanonicalEmotion,
        EmotionState,
        EmotionVector,
        infer_emotion,
        emotion_to_avatar,
        emotion_to_reaction_query,
    )

    # Create an emotion state
    state = EmotionState(CanonicalEmotion.JOY, intensity=0.7)

    # Get PAD vector for animation
    pad = state.pad_vector

    # Map to avatar parameters
    avatar_params = emotion_to_avatar(state.emotion, state.intensity)

    # Get reaction search query
    query = emotion_to_reaction_query(state.emotion, state.intensity, "fixing a bug")

    # Infer emotion from text
    inferred = infer_emotion("I'm so excited about this feature!")
"""

from .inference import (
    ConversationContext,
    InferenceResult,
    MLEmotionClassifier,
    get_ml_classifier,
    infer_emotion,
    infer_emotion_from_text,
    infer_emotion_hybrid,
    infer_emotion_ml,
    infer_emotion_with_context,
)
from .mappings import (
    AUDIO_TAG_TO_EMOTION,
    CANONICAL_TO_REACTION_TAGS,
    CANONICAL_TO_VIRTUAL_CHARACTER,
    EMOTION_TO_AUDIO_TAGS,
    EXPRESSION_TAG_MAPPINGS,
    VIRTUAL_CHARACTER_TO_CANONICAL,
    ExpressionMapping,
    avatar_to_emotion,
    emotion_to_avatar,
    emotion_to_reaction_query,
    extract_emotions_from_text,
    get_audio_tags_for_emotion,
    get_expression_from_audio_tags,
    reaction_tags_to_emotion,
)
from .taxonomy import (
    EMOTION_INTENSITY_LABELS,
    EMOTION_TO_PAD,
    CanonicalEmotion,
    EmotionState,
    EmotionVector,
    blend_emotions,
    find_closest_emotion,
)

__all__ = [
    # Taxonomy
    "CanonicalEmotion",
    "EmotionVector",
    "EmotionState",
    "EMOTION_TO_PAD",
    "EMOTION_INTENSITY_LABELS",
    "find_closest_emotion",
    "blend_emotions",
    # Mappings
    "AUDIO_TAG_TO_EMOTION",
    "EMOTION_TO_AUDIO_TAGS",
    "CANONICAL_TO_VIRTUAL_CHARACTER",
    "VIRTUAL_CHARACTER_TO_CANONICAL",
    "CANONICAL_TO_REACTION_TAGS",
    "EXPRESSION_TAG_MAPPINGS",
    "ExpressionMapping",
    "extract_emotions_from_text",
    "get_audio_tags_for_emotion",
    "emotion_to_avatar",
    "avatar_to_emotion",
    "emotion_to_reaction_query",
    "reaction_tags_to_emotion",
    "get_expression_from_audio_tags",
    # Inference
    "InferenceResult",
    "ConversationContext",
    "MLEmotionClassifier",
    "infer_emotion",
    "infer_emotion_from_text",
    "infer_emotion_ml",
    "infer_emotion_hybrid",
    "infer_emotion_with_context",
    "get_ml_classifier",
]
