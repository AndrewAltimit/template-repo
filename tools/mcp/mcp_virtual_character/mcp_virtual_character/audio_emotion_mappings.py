"""
Audio tag to emotion mappings for ElevenLabs integration.

This module provides comprehensive mappings between ElevenLabs audio expression
tags and Virtual Character emotions, enabling automatic emotion detection from
synthesized speech.

Adapted from mcp_core/emotions/mappings.py for direct Virtual Character use.
"""

import re
from typing import Dict, List, Optional, Tuple

from .models.canonical import EmotionType

# =============================================================================
# ElevenLabs Audio Tag -> EmotionType Mappings
# =============================================================================

# Format: tag -> (EmotionType, base_intensity)
# Intensity range: 0.0 (subtle) to 1.0 (full expression)

AUDIO_TAG_TO_EMOTION: Dict[str, Tuple[EmotionType, float]] = {
    # Joy/Happiness -> HAPPY or EXCITED
    "[laughs]": (EmotionType.HAPPY, 0.8),
    "[laughing]": (EmotionType.HAPPY, 0.8),
    "[chuckles]": (EmotionType.HAPPY, 0.5),
    "[giggles]": (EmotionType.HAPPY, 0.6),
    "[excited]": (EmotionType.EXCITED, 0.9),
    "[cheerfully]": (EmotionType.HAPPY, 0.7),
    "[happily]": (EmotionType.HAPPY, 0.6),
    "[joyfully]": (EmotionType.HAPPY, 0.8),
    "[delighted]": (EmotionType.HAPPY, 0.7),
    # Sadness -> SAD
    "[sighs]": (EmotionType.SAD, 0.4),
    "[sadly]": (EmotionType.SAD, 0.6),
    "[crying]": (EmotionType.SAD, 0.9),
    "[sobbing]": (EmotionType.SAD, 1.0),
    "[sniffles]": (EmotionType.SAD, 0.5),
    "[tearfully]": (EmotionType.SAD, 0.7),
    "[melancholy]": (EmotionType.SAD, 0.5),
    "[mournfully]": (EmotionType.SAD, 0.8),
    # Anger -> ANGRY
    "[angrily]": (EmotionType.ANGRY, 0.7),
    "[angry]": (EmotionType.ANGRY, 0.7),
    "[frustrated]": (EmotionType.ANGRY, 0.5),
    "[growls]": (EmotionType.ANGRY, 0.8),
    "[shouting]": (EmotionType.ANGRY, 0.9),
    "[yelling]": (EmotionType.ANGRY, 0.9),
    "[furiously]": (EmotionType.ANGRY, 1.0),
    "[irritated]": (EmotionType.ANGRY, 0.4),
    # Fear/Nervousness -> FEARFUL
    "[nervously]": (EmotionType.FEARFUL, 0.5),
    "[anxiously]": (EmotionType.FEARFUL, 0.6),
    "[scared]": (EmotionType.FEARFUL, 0.7),
    "[trembling]": (EmotionType.FEARFUL, 0.8),
    "[gasps]": (EmotionType.FEARFUL, 0.7),
    "[fearfully]": (EmotionType.FEARFUL, 0.7),
    "[terrified]": (EmotionType.FEARFUL, 1.0),
    "[worried]": (EmotionType.FEARFUL, 0.4),
    # Surprise -> SURPRISED
    "[surprised]": (EmotionType.SURPRISED, 0.7),
    "[amazed]": (EmotionType.SURPRISED, 0.8),
    "[shocked]": (EmotionType.SURPRISED, 0.9),
    "[stunned]": (EmotionType.SURPRISED, 0.9),
    "[astonished]": (EmotionType.SURPRISED, 0.9),
    "[wow]": (EmotionType.SURPRISED, 0.6),
    # Calm/Gentle -> CALM
    "[softly]": (EmotionType.CALM, 0.5),
    "[gently]": (EmotionType.CALM, 0.5),
    "[calmly]": (EmotionType.CALM, 0.6),
    "[peacefully]": (EmotionType.CALM, 0.7),
    "[whisper]": (EmotionType.CALM, 0.4),
    "[whispering]": (EmotionType.CALM, 0.4),
    "[soothingly]": (EmotionType.CALM, 0.6),
    "[quietly]": (EmotionType.CALM, 0.3),
    "[serenely]": (EmotionType.CALM, 0.7),
    # Disgust -> DISGUSTED
    "[disgusted]": (EmotionType.DISGUSTED, 0.7),
    "[grossed out]": (EmotionType.DISGUSTED, 0.6),
    "[revolted]": (EmotionType.DISGUSTED, 0.8),
    "[nauseated]": (EmotionType.DISGUSTED, 0.6),
    # Contempt -> CONTEMPTUOUS
    "[sarcastically]": (EmotionType.CONTEMPTUOUS, 0.6),
    "[mockingly]": (EmotionType.CONTEMPTUOUS, 0.7),
    "[dismissively]": (EmotionType.CONTEMPTUOUS, 0.5),
    "[condescendingly]": (EmotionType.CONTEMPTUOUS, 0.6),
    "[smugly]": (EmotionType.CONTEMPTUOUS, 0.5),
    # Thinking/Consideration -> NEUTRAL (thoughtful neutral)
    "[thoughtfully]": (EmotionType.NEUTRAL, 0.4),
    "[pondering]": (EmotionType.NEUTRAL, 0.3),
    "[considering]": (EmotionType.NEUTRAL, 0.3),
    "[hmm]": (EmotionType.NEUTRAL, 0.2),
    "[musing]": (EmotionType.NEUTRAL, 0.3),
    # Embarrassment -> mix (closest: SURPRISED with lower intensity)
    "[embarrassed]": (EmotionType.SURPRISED, 0.4),
    "[sheepishly]": (EmotionType.SURPRISED, 0.3),
    "[awkwardly]": (EmotionType.SURPRISED, 0.3),
    "[blushing]": (EmotionType.SURPRISED, 0.4),
    # Confident/Proud -> HAPPY (confident happiness)
    "[confidently]": (EmotionType.HAPPY, 0.5),
    "[proudly]": (EmotionType.HAPPY, 0.6),
    "[triumphantly]": (EmotionType.EXCITED, 0.8),
    # Bored/Tired -> NEUTRAL (disengaged)
    "[bored]": (EmotionType.NEUTRAL, 0.2),
    "[yawns]": (EmotionType.NEUTRAL, 0.3),
    "[tiredly]": (EmotionType.NEUTRAL, 0.3),
    "[sleepily]": (EmotionType.CALM, 0.3),
    # Curious/Attentive -> NEUTRAL (alert)
    "[curiously]": (EmotionType.NEUTRAL, 0.4),
    "[attentively]": (EmotionType.NEUTRAL, 0.4),
    "[intrigued]": (EmotionType.SURPRISED, 0.4),
}


# =============================================================================
# Reverse Mapping: Emotion -> Audio Tags
# =============================================================================

# Build reverse mapping for suggesting audio tags when given an emotion
EMOTION_TO_AUDIO_TAGS: Dict[EmotionType, List[Tuple[str, float]]] = {}

for tag, (emotion, intensity) in AUDIO_TAG_TO_EMOTION.items():
    if emotion not in EMOTION_TO_AUDIO_TAGS:
        EMOTION_TO_AUDIO_TAGS[emotion] = []
    EMOTION_TO_AUDIO_TAGS[emotion].append((tag, intensity))

# Sort by intensity descending for each emotion
for emotion in EMOTION_TO_AUDIO_TAGS:
    EMOTION_TO_AUDIO_TAGS[emotion].sort(key=lambda x: x[1], reverse=True)


# =============================================================================
# Helper Functions
# =============================================================================


def extract_emotions_from_text(text: str) -> List[Tuple[EmotionType, float]]:
    """
    Extract emotions from text containing ElevenLabs audio tags.

    Args:
        text: Text potentially containing audio tags like [laughs], [sighs]

    Returns:
        List of (EmotionType, intensity) tuples found in text
    """
    emotions = []

    # Find all bracketed tags
    tags = re.findall(r"\[[^\]]+\]", text.lower())

    for tag in tags:
        normalized = tag.lower().strip()

        # Direct match
        if normalized in AUDIO_TAG_TO_EMOTION:
            emotions.append(AUDIO_TAG_TO_EMOTION[normalized])
            continue

        # Fuzzy match - check if any known tag is contained
        for known_tag, (emotion, intensity) in AUDIO_TAG_TO_EMOTION.items():
            known_content = known_tag[1:-1]  # Remove brackets
            tag_content = normalized[1:-1]
            if known_content in tag_content or tag_content in known_content:
                emotions.append((emotion, intensity))
                break

    return emotions


def get_emotion_from_tag(tag: str) -> Optional[Tuple[EmotionType, float]]:
    """
    Get emotion for a single audio tag.

    Args:
        tag: Audio tag like "[laughs]" or "laughs"

    Returns:
        (EmotionType, intensity) or None if not found
    """
    # Normalize: ensure brackets
    if not tag.startswith("["):
        tag = f"[{tag}]"
    if not tag.endswith("]"):
        tag = f"{tag}]"

    tag = tag.lower()

    if tag in AUDIO_TAG_TO_EMOTION:
        return AUDIO_TAG_TO_EMOTION[tag]

    return None


def get_audio_tags_for_emotion(
    emotion: EmotionType,
    intensity: float = 0.5,
    max_tags: int = 2,
) -> List[str]:
    """
    Get suitable ElevenLabs audio tags for an emotion.

    Args:
        emotion: The target EmotionType
        intensity: Desired intensity (0-1), tags closest to this are preferred
        max_tags: Maximum number of tags to return

    Returns:
        List of audio tags sorted by relevance to intensity
    """
    if emotion not in EMOTION_TO_AUDIO_TAGS:
        return []

    candidates = EMOTION_TO_AUDIO_TAGS[emotion]

    # Sort by distance to desired intensity
    sorted_by_distance = sorted(candidates, key=lambda x: abs(x[1] - intensity))

    return [tag for tag, _ in sorted_by_distance[:max_tags]]


def get_dominant_emotion(text: str) -> Optional[Tuple[EmotionType, float]]:
    """
    Get the dominant emotion from text with audio tags.

    Args:
        text: Text containing audio tags

    Returns:
        The emotion with highest intensity, or None if no tags found
    """
    emotions = extract_emotions_from_text(text)

    if not emotions:
        return None

    # Return emotion with highest intensity
    return max(emotions, key=lambda x: x[1])
