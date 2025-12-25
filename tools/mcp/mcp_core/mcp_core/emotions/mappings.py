"""
Bidirectional emotion mappings for all MCP systems.

This module provides mapping utilities between:
- CanonicalEmotion <-> ElevenLabs audio tags
- CanonicalEmotion <-> Virtual Character EmotionType
- CanonicalEmotion <-> Reaction Search queries
"""

from dataclasses import dataclass
import re
from typing import Dict, List, Optional, Tuple

from .taxonomy import CanonicalEmotion, EmotionState

# =============================================================================
# ElevenLabs Audio Tag Mappings
# =============================================================================

# Audio tags that indicate specific emotions
# Format: tag -> (emotion, base_intensity)
AUDIO_TAG_TO_EMOTION: Dict[str, Tuple[CanonicalEmotion, float]] = {
    # Joy/Happiness
    "[laughs]": (CanonicalEmotion.JOY, 0.8),
    "[laughing]": (CanonicalEmotion.JOY, 0.8),
    "[chuckles]": (CanonicalEmotion.JOY, 0.5),
    "[giggles]": (CanonicalEmotion.JOY, 0.6),
    "[excited]": (CanonicalEmotion.JOY, 0.9),
    "[cheerfully]": (CanonicalEmotion.JOY, 0.7),
    "[happily]": (CanonicalEmotion.JOY, 0.6),
    # Sadness
    "[sighs]": (CanonicalEmotion.SADNESS, 0.4),
    "[sadly]": (CanonicalEmotion.SADNESS, 0.6),
    "[crying]": (CanonicalEmotion.SADNESS, 0.9),
    "[sobbing]": (CanonicalEmotion.SADNESS, 1.0),
    "[sniffles]": (CanonicalEmotion.SADNESS, 0.5),
    "[tearfully]": (CanonicalEmotion.SADNESS, 0.7),
    # Anger
    "[angrily]": (CanonicalEmotion.ANGER, 0.7),
    "[frustrated]": (CanonicalEmotion.ANGER, 0.5),
    "[growls]": (CanonicalEmotion.ANGER, 0.8),
    "[shouting]": (CanonicalEmotion.ANGER, 0.9),
    "[yelling]": (CanonicalEmotion.ANGER, 0.9),
    # Fear/Nervousness
    "[nervously]": (CanonicalEmotion.FEAR, 0.5),
    "[anxiously]": (CanonicalEmotion.FEAR, 0.6),
    "[scared]": (CanonicalEmotion.FEAR, 0.7),
    "[trembling]": (CanonicalEmotion.FEAR, 0.8),
    "[gasps]": (CanonicalEmotion.FEAR, 0.7),
    "[fearfully]": (CanonicalEmotion.FEAR, 0.7),
    # Surprise
    "[surprised]": (CanonicalEmotion.SURPRISE, 0.7),
    "[amazed]": (CanonicalEmotion.SURPRISE, 0.8),
    "[shocked]": (CanonicalEmotion.SURPRISE, 0.9),
    "[stunned]": (CanonicalEmotion.SURPRISE, 0.9),
    # Thinking/Consideration
    "[thoughtfully]": (CanonicalEmotion.THINKING, 0.6),
    "[pondering]": (CanonicalEmotion.THINKING, 0.5),
    "[considering]": (CanonicalEmotion.THINKING, 0.4),
    "[hmm]": (CanonicalEmotion.THINKING, 0.3),
    # Calm/Gentle
    "[softly]": (CanonicalEmotion.CALM, 0.5),
    "[gently]": (CanonicalEmotion.CALM, 0.5),
    "[calmly]": (CanonicalEmotion.CALM, 0.6),
    "[peacefully]": (CanonicalEmotion.CALM, 0.7),
    "[whisper]": (CanonicalEmotion.CALM, 0.4),
    "[whispering]": (CanonicalEmotion.CALM, 0.4),
    # Confusion
    "[confused]": (CanonicalEmotion.CONFUSION, 0.6),
    "[puzzled]": (CanonicalEmotion.CONFUSION, 0.5),
    "[uncertain]": (CanonicalEmotion.CONFUSION, 0.4),
    # Embarrassment
    "[embarrassed]": (CanonicalEmotion.EMBARRASSMENT, 0.6),
    "[sheepishly]": (CanonicalEmotion.EMBARRASSMENT, 0.5),
    "[awkwardly]": (CanonicalEmotion.EMBARRASSMENT, 0.5),
    # Smug/Confident
    "[smugly]": (CanonicalEmotion.SMUG, 0.7),
    "[confidently]": (CanonicalEmotion.SMUG, 0.5),
    "[proudly]": (CanonicalEmotion.SMUG, 0.6),
    # Disgust
    "[disgusted]": (CanonicalEmotion.DISGUST, 0.7),
    "[grossed out]": (CanonicalEmotion.DISGUST, 0.6),
    # Contempt
    "[sarcastically]": (CanonicalEmotion.CONTEMPT, 0.6),
    "[mockingly]": (CanonicalEmotion.CONTEMPT, 0.7),
    "[dismissively]": (CanonicalEmotion.CONTEMPT, 0.5),
    # Attention/Focus
    "[attentively]": (CanonicalEmotion.ATTENTIVE, 0.6),
    "[curiously]": (CanonicalEmotion.ATTENTIVE, 0.5),
    # Boredom
    "[bored]": (CanonicalEmotion.BORED, 0.6),
    "[yawns]": (CanonicalEmotion.BORED, 0.5),
    "[tiredly]": (CanonicalEmotion.BORED, 0.4),
}

# Reverse mapping: emotion -> list of suitable audio tags (ordered by intensity)
EMOTION_TO_AUDIO_TAGS: Dict[CanonicalEmotion, List[Tuple[str, float]]] = {}
for tag, (emotion, intensity) in AUDIO_TAG_TO_EMOTION.items():
    if emotion not in EMOTION_TO_AUDIO_TAGS:
        EMOTION_TO_AUDIO_TAGS[emotion] = []
    EMOTION_TO_AUDIO_TAGS[emotion].append((tag, intensity))

# Sort by intensity descending
for emotion in EMOTION_TO_AUDIO_TAGS:
    EMOTION_TO_AUDIO_TAGS[emotion].sort(key=lambda x: x[1], reverse=True)


def extract_emotions_from_text(text: str) -> List[Tuple[CanonicalEmotion, float]]:
    """
    Extract emotions from text containing ElevenLabs audio tags.

    Args:
        text: Text potentially containing audio tags like [laughs], [sighs]

    Returns:
        List of (emotion, intensity) tuples found in text
    """
    emotions = []

    # Find all bracketed tags
    tags = re.findall(r"\[[^\]]+\]", text.lower())

    for tag in tags:
        # Normalize tag format
        normalized = tag.lower().strip()

        # Direct match
        if normalized in AUDIO_TAG_TO_EMOTION:
            emotions.append(AUDIO_TAG_TO_EMOTION[normalized])
            continue

        # Fuzzy match - check if any known tag is contained
        for known_tag, (emotion, intensity) in AUDIO_TAG_TO_EMOTION.items():
            # Remove brackets for comparison
            known_content = known_tag[1:-1]
            tag_content = normalized[1:-1]
            if known_content in tag_content or tag_content in known_content:
                emotions.append((emotion, intensity))
                break

    return emotions


def get_audio_tags_for_emotion(emotion: CanonicalEmotion, intensity: float = 0.5, max_tags: int = 2) -> List[str]:
    """
    Get suitable ElevenLabs audio tags for an emotion.

    Args:
        emotion: The canonical emotion
        intensity: Desired intensity (0-1)
        max_tags: Maximum number of tags to return

    Returns:
        List of audio tags sorted by relevance
    """
    if emotion not in EMOTION_TO_AUDIO_TAGS:
        return []

    candidates = EMOTION_TO_AUDIO_TAGS[emotion]

    # Find tags closest to desired intensity
    sorted_by_distance = sorted(candidates, key=lambda x: abs(x[1] - intensity))

    return [tag for tag, _ in sorted_by_distance[:max_tags]]


# =============================================================================
# Virtual Character EmotionType Mappings
# =============================================================================

# Virtual Character uses EmotionType enum with these values:
# NEUTRAL, HAPPY, SAD, ANGRY, SURPRISED, FEARFUL, DISGUSTED, CONTEMPTUOUS, EXCITED, CALM

CANONICAL_TO_VIRTUAL_CHARACTER: Dict[CanonicalEmotion, str] = {
    CanonicalEmotion.JOY: "happy",
    CanonicalEmotion.SADNESS: "sad",
    CanonicalEmotion.ANGER: "angry",
    CanonicalEmotion.FEAR: "fearful",
    CanonicalEmotion.SURPRISE: "surprised",
    CanonicalEmotion.DISGUST: "disgusted",
    CanonicalEmotion.CONTEMPT: "contemptuous",
    CanonicalEmotion.CONFUSION: "surprised",  # Closest match
    CanonicalEmotion.CALM: "calm",
    CanonicalEmotion.THINKING: "neutral",  # Thoughtful neutral
    CanonicalEmotion.SMUG: "happy",  # Smug -> slight happy
    CanonicalEmotion.EMBARRASSMENT: "surprised",  # Flustered
    CanonicalEmotion.ATTENTIVE: "neutral",  # Alert neutral
    CanonicalEmotion.BORED: "neutral",  # Disengaged neutral
}

VIRTUAL_CHARACTER_TO_CANONICAL: Dict[str, CanonicalEmotion] = {
    "neutral": CanonicalEmotion.CALM,
    "happy": CanonicalEmotion.JOY,
    "sad": CanonicalEmotion.SADNESS,
    "angry": CanonicalEmotion.ANGER,
    "surprised": CanonicalEmotion.SURPRISE,
    "fearful": CanonicalEmotion.FEAR,
    "disgusted": CanonicalEmotion.DISGUST,
    "contemptuous": CanonicalEmotion.CONTEMPT,
    "excited": CanonicalEmotion.JOY,  # High-intensity joy
    "calm": CanonicalEmotion.CALM,
}


def emotion_to_avatar(emotion: CanonicalEmotion, intensity: float = 0.5) -> Dict:
    """
    Convert canonical emotion to Virtual Character parameters.

    Args:
        emotion: Canonical emotion
        intensity: Emotion intensity (0-1)

    Returns:
        Dict with 'emotion' and 'emotion_intensity' keys
    """
    avatar_emotion = CANONICAL_TO_VIRTUAL_CHARACTER.get(emotion, "neutral")

    # Adjust intensity based on emotion type
    adjusted_intensity = intensity

    # Some emotions map to different types, adjust intensity accordingly
    if emotion == CanonicalEmotion.THINKING:
        adjusted_intensity = 0.3  # Subtle for thinking
    elif emotion == CanonicalEmotion.BORED:
        adjusted_intensity = 0.2  # Very subtle
    elif emotion == CanonicalEmotion.SMUG:
        adjusted_intensity = min(intensity, 0.6)  # Cap smugness

    return {
        "emotion": avatar_emotion,
        "emotion_intensity": round(adjusted_intensity, 2),
    }


def avatar_to_emotion(emotion_str: str, intensity: float = 0.5) -> EmotionState:
    """
    Convert Virtual Character emotion to canonical state.

    Args:
        emotion_str: Virtual Character emotion string
        intensity: Emotion intensity from avatar

    Returns:
        EmotionState
    """
    canonical = VIRTUAL_CHARACTER_TO_CANONICAL.get(emotion_str.lower(), CanonicalEmotion.CALM)
    return EmotionState(emotion=canonical, intensity=intensity)


# =============================================================================
# Reaction Search Query Mappings
# =============================================================================

# Tags commonly used in reaction search
CANONICAL_TO_REACTION_TAGS: Dict[CanonicalEmotion, List[str]] = {
    CanonicalEmotion.JOY: ["happy", "cheerful", "excited", "celebrating", "smiling"],
    CanonicalEmotion.SADNESS: ["sad", "crying", "melancholy", "disappointed"],
    CanonicalEmotion.ANGER: ["angry", "annoyed", "frustrated", "mad"],
    CanonicalEmotion.FEAR: ["scared", "nervous", "anxious", "worried"],
    CanonicalEmotion.SURPRISE: ["surprised", "shocked", "amazed", "stunned"],
    CanonicalEmotion.DISGUST: ["disgusted", "grossed", "nauseated"],
    CanonicalEmotion.CONTEMPT: ["smug", "sarcastic", "dismissive", "judging"],
    CanonicalEmotion.CONFUSION: ["confused", "puzzled", "questioning", "unsure"],
    CanonicalEmotion.CALM: ["calm", "relaxed", "peaceful", "content"],
    CanonicalEmotion.THINKING: ["thinking", "pondering", "contemplating", "studious"],
    CanonicalEmotion.SMUG: ["smug", "proud", "confident", "superior"],
    CanonicalEmotion.EMBARRASSMENT: ["embarrassed", "blushing", "flustered", "awkward"],
    CanonicalEmotion.ATTENTIVE: ["attentive", "focused", "listening", "interested"],
    CanonicalEmotion.BORED: ["bored", "tired", "sleepy", "uninterested"],
}

# Intensity descriptors for reaction queries
INTENSITY_DESCRIPTORS: Dict[str, Tuple[float, float]] = {
    "slightly": (0.0, 0.3),
    "somewhat": (0.2, 0.4),
    "moderately": (0.3, 0.5),
    "quite": (0.5, 0.7),
    "very": (0.7, 0.9),
    "extremely": (0.9, 1.0),
}


def emotion_to_reaction_query(emotion: CanonicalEmotion, intensity: float = 0.5, context: str = "") -> str:
    """
    Generate a semantic search query for reaction images.

    Args:
        emotion: Canonical emotion
        intensity: Emotion intensity (0-1)
        context: Optional context (e.g., "after fixing a bug")

    Returns:
        Search query string optimized for semantic similarity
    """
    # Get base emotion tags
    tags = CANONICAL_TO_REACTION_TAGS.get(emotion, [emotion.value])

    # Select tag based on position (higher intensity = later in list)
    tag_index = min(int(intensity * len(tags)), len(tags) - 1)
    primary_tag = tags[tag_index]

    # Add intensity descriptor
    intensity_word = ""
    for word, (min_i, max_i) in INTENSITY_DESCRIPTORS.items():
        if min_i <= intensity <= max_i:
            intensity_word = word
            break

    # Build query
    query_parts = []

    if intensity_word and intensity > 0.3:  # Only add intensity for non-subtle emotions
        query_parts.append(intensity_word)

    query_parts.append(primary_tag)

    # Add context
    if context:
        query_parts.append(context)

    return " ".join(query_parts)


def reaction_tags_to_emotion(tags: List[str]) -> Optional[EmotionState]:
    """
    Infer emotion from reaction image tags.

    Args:
        tags: List of tags from a reaction image

    Returns:
        Inferred EmotionState or None if no match
    """
    tag_set = set(t.lower() for t in tags)

    best_match: Optional[CanonicalEmotion] = None
    best_score = 0

    for emotion, emotion_tags in CANONICAL_TO_REACTION_TAGS.items():
        # Count matching tags
        matches = len(tag_set.intersection(t.lower() for t in emotion_tags))
        if matches > best_score:
            best_score = matches
            best_match = emotion

    if best_match:
        # Estimate intensity based on number of matching tags
        intensity = min(0.5 + best_score * 0.1, 1.0)
        return EmotionState(emotion=best_match, intensity=intensity)

    return None


# =============================================================================
# Expression Tag Mappings (for Virtual Character audio sync)
# =============================================================================


@dataclass
class ExpressionMapping:
    """Maps between audio tags and avatar expressions."""

    audio_tags: List[str]
    avatar_emotion: str
    avatar_gesture: Optional[str] = None


# How audio tags should trigger avatar changes
EXPRESSION_TAG_MAPPINGS: List[ExpressionMapping] = [
    ExpressionMapping(
        audio_tags=["[laughs]", "[chuckles]", "[giggles]"],
        avatar_emotion="happy",
        avatar_gesture="none",
    ),
    ExpressionMapping(
        audio_tags=["[sighs]", "[sadly]", "[crying]"],
        avatar_emotion="sad",
        avatar_gesture="sadness",
    ),
    ExpressionMapping(
        audio_tags=["[angrily]", "[frustrated]", "[growls]"],
        avatar_emotion="angry",
        avatar_gesture="none",
    ),
    ExpressionMapping(
        audio_tags=["[surprised]", "[shocked]", "[gasps]"],
        avatar_emotion="surprised",
        avatar_gesture="none",
    ),
    ExpressionMapping(
        audio_tags=["[thoughtfully]", "[hmm]", "[pondering]"],
        avatar_emotion="neutral",
        avatar_gesture="thinking",
    ),
    ExpressionMapping(
        audio_tags=["[excited]", "[cheerfully]"],
        avatar_emotion="happy",
        avatar_gesture="cheer",
    ),
]


def get_expression_from_audio_tags(tags: List[str]) -> Dict[str, Optional[str]]:
    """
    Get avatar expression parameters from audio tags.

    Args:
        tags: List of audio tags found in text

    Returns:
        Dict with 'emotion' and 'gesture' keys
    """
    result = {"emotion": "neutral", "gesture": None}

    tag_set = set(t.lower() for t in tags)

    for mapping in EXPRESSION_TAG_MAPPINGS:
        if tag_set.intersection(t.lower() for t in mapping.audio_tags):
            result["emotion"] = mapping.avatar_emotion
            result["gesture"] = mapping.avatar_gesture
            break

    return result
