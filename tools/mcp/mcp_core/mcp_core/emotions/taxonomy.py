"""
Canonical Emotion Taxonomy for Unified Expressive AI Agent System.

This module provides a shared emotion model that all MCP servers can use
for consistent emotion representation across voice, avatar, and reactions.

Key Components:
- CanonicalEmotion: Enumeration of 14 primary emotions with intensity support
- EmotionVector: PAD (Pleasure/Arousal/Dominance) 3D model for smooth interpolation
- EmotionState: Combined emotion with intensity and PAD vector
"""

from dataclasses import dataclass
from enum import Enum
import math
from typing import Dict, List, Optional, Tuple


class CanonicalEmotion(Enum):
    """
    Primary emotion categories with intensity support.

    Each emotion maps to a PAD vector for smooth animation interpolation.
    Intensity (0-1) scales the emotion's expression magnitude.
    """

    # Core emotions (Ekman's basic emotions + extensions)
    JOY = "joy"
    SADNESS = "sadness"
    ANGER = "anger"
    FEAR = "fear"
    SURPRISE = "surprise"
    DISGUST = "disgust"
    CONTEMPT = "contempt"

    # Extended emotions for AI agents
    CONFUSION = "confusion"
    CALM = "calm"
    THINKING = "thinking"
    SMUG = "smug"
    EMBARRASSMENT = "embarrassment"
    ATTENTIVE = "attentive"  # Focused, listening
    BORED = "bored"  # Disengaged, distracted


@dataclass
class EmotionVector:
    """
    PAD (Pleasure, Arousal, Dominance) model for smooth emotion interpolation.

    This 3D vector space allows:
    - Mathematical blending of System 1 and System 2 outputs
    - Smooth interpolation avoiding "glitchy" state snaps
    - Averaging conflicting emotion signals
    - Direct mapping to animation blend shapes
    - Single source of truth for emotional state

    Attributes:
        pleasure: -1 (unhappy/unpleasant) to +1 (happy/pleasant)
        arousal: -1 (calm/sleepy) to +1 (excited/energized)
        dominance: -1 (submissive/controlled) to +1 (dominant/controlling)
    """

    pleasure: float = 0.0
    arousal: float = 0.0
    dominance: float = 0.0

    def __post_init__(self) -> None:
        """Clamp values to valid range."""
        self.pleasure = max(-1.0, min(1.0, self.pleasure))
        self.arousal = max(-1.0, min(1.0, self.arousal))
        self.dominance = max(-1.0, min(1.0, self.dominance))

    def lerp(self, target: "EmotionVector", t: float) -> "EmotionVector":
        """
        Linear interpolation for smooth transitions.

        Args:
            target: Target emotion vector to interpolate towards
            t: Interpolation factor (0.0 = self, 1.0 = target)

        Returns:
            Interpolated EmotionVector
        """
        t = max(0.0, min(1.0, t))  # Clamp t to [0, 1]
        return EmotionVector(
            pleasure=self.pleasure + (target.pleasure - self.pleasure) * t,
            arousal=self.arousal + (target.arousal - self.arousal) * t,
            dominance=self.dominance + (target.dominance - self.dominance) * t,
        )

    def distance(self, other: "EmotionVector") -> float:
        """
        Euclidean distance to another emotion vector.

        Useful for detecting emotional "jumps" that need smoothing.
        """
        return math.sqrt(
            (self.pleasure - other.pleasure) ** 2
            + (self.arousal - other.arousal) ** 2
            + (self.dominance - other.dominance) ** 2
        )

    def scale(self, intensity: float) -> "EmotionVector":
        """
        Scale emotion vector by intensity.

        Args:
            intensity: Scale factor (0.0 = neutral, 1.0 = full)

        Returns:
            Scaled EmotionVector (moves towards neutral at low intensity)
        """
        intensity = max(0.0, min(1.0, intensity))
        return EmotionVector(
            pleasure=self.pleasure * intensity,
            arousal=self.arousal * intensity,
            dominance=self.dominance * intensity,
        )

    def blend(self, other: "EmotionVector", weight: float = 0.5) -> "EmotionVector":
        """
        Weighted blend of two emotion vectors.

        Args:
            other: Other emotion vector to blend with
            weight: Weight for other vector (0.0 = self, 1.0 = other)

        Returns:
            Blended EmotionVector
        """
        return self.lerp(other, weight)

    def magnitude(self) -> float:
        """Calculate the magnitude (intensity) of this emotion vector."""
        return math.sqrt(self.pleasure**2 + self.arousal**2 + self.dominance**2)

    def normalized(self) -> "EmotionVector":
        """Return a normalized (unit length) version of this vector."""
        mag = self.magnitude()
        if mag < 0.0001:
            return EmotionVector(0.0, 0.0, 0.0)
        return EmotionVector(
            pleasure=self.pleasure / mag,
            arousal=self.arousal / mag,
            dominance=self.dominance / mag,
        )

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary for serialization."""
        return {
            "pleasure": round(self.pleasure, 4),
            "arousal": round(self.arousal, 4),
            "dominance": round(self.dominance, 4),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, float]) -> "EmotionVector":
        """Create from dictionary."""
        return cls(
            pleasure=data.get("pleasure", 0.0),
            arousal=data.get("arousal", 0.0),
            dominance=data.get("dominance", 0.0),
        )

    @classmethod
    def neutral(cls) -> "EmotionVector":
        """Return a neutral emotion vector."""
        return cls(0.0, 0.0, 0.0)

    def __mul__(self, scalar: float) -> "EmotionVector":
        """Scalar multiplication."""
        return EmotionVector(
            pleasure=self.pleasure * scalar,
            arousal=self.arousal * scalar,
            dominance=self.dominance * scalar,
        )

    def __add__(self, other: "EmotionVector") -> "EmotionVector":
        """Vector addition."""
        return EmotionVector(
            pleasure=self.pleasure + other.pleasure,
            arousal=self.arousal + other.arousal,
            dominance=self.dominance + other.dominance,
        )


# Map discrete emotions to PAD vectors
# Based on research: Mehrabian & Russell (1977), Russell & Mehrabian (1974)
EMOTION_TO_PAD: Dict[CanonicalEmotion, EmotionVector] = {
    CanonicalEmotion.JOY: EmotionVector(+0.8, +0.6, +0.2),
    CanonicalEmotion.SADNESS: EmotionVector(-0.7, -0.3, -0.4),
    CanonicalEmotion.ANGER: EmotionVector(-0.6, +0.8, +0.6),
    CanonicalEmotion.FEAR: EmotionVector(-0.7, +0.7, -0.6),
    CanonicalEmotion.SURPRISE: EmotionVector(+0.2, +0.8, -0.1),
    CanonicalEmotion.DISGUST: EmotionVector(-0.6, +0.2, +0.3),
    CanonicalEmotion.CONTEMPT: EmotionVector(-0.3, +0.1, +0.7),
    CanonicalEmotion.CONFUSION: EmotionVector(-0.2, +0.4, -0.3),
    CanonicalEmotion.CALM: EmotionVector(+0.3, -0.6, +0.1),
    CanonicalEmotion.THINKING: EmotionVector(+0.1, +0.3, +0.2),
    CanonicalEmotion.SMUG: EmotionVector(+0.4, +0.2, +0.8),
    CanonicalEmotion.EMBARRASSMENT: EmotionVector(-0.4, +0.5, -0.5),
    CanonicalEmotion.ATTENTIVE: EmotionVector(+0.2, +0.5, +0.0),  # Focused listening
    CanonicalEmotion.BORED: EmotionVector(-0.3, -0.7, -0.2),  # Disengaged
}


# Intensity-based descriptors for each emotion
EMOTION_INTENSITY_LABELS: Dict[CanonicalEmotion, Dict[str, Tuple[float, float]]] = {
    CanonicalEmotion.JOY: {
        "content": (0.0, 0.3),
        "pleased": (0.2, 0.4),
        "happy": (0.4, 0.6),
        "cheerful": (0.5, 0.7),
        "excited": (0.7, 0.9),
        "elated": (0.8, 1.0),
        "ecstatic": (0.9, 1.0),
    },
    CanonicalEmotion.SADNESS: {
        "disappointed": (0.0, 0.3),
        "melancholy": (0.2, 0.4),
        "sad": (0.4, 0.6),
        "sorrowful": (0.5, 0.7),
        "devastated": (0.8, 1.0),
        "crying": (0.9, 1.0),
    },
    CanonicalEmotion.ANGER: {
        "annoyed": (0.0, 0.3),
        "irritated": (0.2, 0.4),
        "angry": (0.4, 0.6),
        "frustrated": (0.5, 0.7),
        "furious": (0.8, 1.0),
        "enraged": (0.9, 1.0),
    },
    CanonicalEmotion.FEAR: {
        "nervous": (0.0, 0.3),
        "uneasy": (0.2, 0.4),
        "anxious": (0.4, 0.6),
        "worried": (0.5, 0.7),
        "terrified": (0.8, 1.0),
        "panicked": (0.9, 1.0),
    },
    CanonicalEmotion.SURPRISE: {
        "curious": (0.0, 0.3),
        "intrigued": (0.2, 0.4),
        "surprised": (0.4, 0.6),
        "amazed": (0.6, 0.8),
        "shocked": (0.8, 1.0),
        "astonished": (0.9, 1.0),
    },
    CanonicalEmotion.CONFUSION: {
        "unsure": (0.0, 0.3),
        "puzzled": (0.3, 0.5),
        "confused": (0.5, 0.7),
        "bewildered": (0.7, 0.9),
        "lost": (0.9, 1.0),
    },
    CanonicalEmotion.CALM: {
        "relaxed": (0.0, 0.3),
        "calm": (0.3, 0.6),
        "serene": (0.6, 0.8),
        "peaceful": (0.8, 1.0),
    },
    CanonicalEmotion.THINKING: {
        "pondering": (0.0, 0.3),
        "considering": (0.3, 0.5),
        "thinking": (0.5, 0.7),
        "deep_thought": (0.7, 1.0),
    },
}


@dataclass
class EmotionState:
    """
    Complete emotion state combining categorical emotion and intensity.

    Attributes:
        emotion: The categorical emotion type
        intensity: Expression magnitude (0.0 = subtle, 1.0 = full)
        pad_vector: Computed PAD vector (scaled by intensity)
        secondary_emotion: Optional blended secondary emotion
        secondary_intensity: Intensity of secondary emotion
    """

    emotion: CanonicalEmotion
    intensity: float = 0.5
    secondary_emotion: Optional[CanonicalEmotion] = None
    secondary_intensity: float = 0.0

    def __post_init__(self) -> None:
        """Clamp intensity values."""
        self.intensity = max(0.0, min(1.0, self.intensity))
        self.secondary_intensity = max(0.0, min(1.0, self.secondary_intensity))

    @property
    def pad_vector(self) -> EmotionVector:
        """
        Get the PAD vector for this emotion state.

        If secondary emotion is present, blends the two emotions.
        """
        primary_pad = EMOTION_TO_PAD[self.emotion].scale(self.intensity)

        if self.secondary_emotion and self.secondary_intensity > 0:
            secondary_pad = EMOTION_TO_PAD[self.secondary_emotion].scale(self.secondary_intensity)
            # Weighted blend based on relative intensities
            total_intensity = self.intensity + self.secondary_intensity
            if total_intensity > 0:
                weight = self.secondary_intensity / total_intensity
                return primary_pad.blend(secondary_pad, weight)

        return primary_pad

    def get_label(self) -> str:
        """
        Get the intensity-appropriate label for this emotion.

        Returns:
            Descriptive label like "happy", "excited", "devastated"
        """
        if self.emotion not in EMOTION_INTENSITY_LABELS:
            return self.emotion.value

        labels = EMOTION_INTENSITY_LABELS[self.emotion]
        for label, (min_i, max_i) in labels.items():
            if min_i <= self.intensity <= max_i:
                return label

        return self.emotion.value

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        data = {
            "emotion": self.emotion.value,
            "intensity": round(self.intensity, 3),
            "pad_vector": self.pad_vector.to_dict(),
            "label": self.get_label(),
        }
        if self.secondary_emotion:
            data["secondary_emotion"] = self.secondary_emotion.value
            data["secondary_intensity"] = round(self.secondary_intensity, 3)
        return data

    @classmethod
    def from_dict(cls, data: Dict) -> "EmotionState":
        """Create from dictionary."""
        return cls(
            emotion=CanonicalEmotion(data["emotion"]),
            intensity=data.get("intensity", 0.5),
            secondary_emotion=(CanonicalEmotion(data["secondary_emotion"]) if data.get("secondary_emotion") else None),
            secondary_intensity=data.get("secondary_intensity", 0.0),
        )

    def transition_to(self, target: "EmotionState", duration: float, dt: float) -> "EmotionState":
        """
        Create intermediate state for smooth transition.

        Args:
            target: Target emotion state
            duration: Total transition duration in seconds
            dt: Time delta for this frame

        Returns:
            Interpolated EmotionState
        """
        t = min(1.0, dt / duration) if duration > 0 else 1.0

        # If same emotion, just interpolate intensity
        if self.emotion == target.emotion:
            new_intensity = self.intensity + (target.intensity - self.intensity) * t
            return EmotionState(
                emotion=self.emotion,
                intensity=new_intensity,
            )

        # Different emotions - use PAD space interpolation
        # Return weighted blend of both emotions
        new_primary_intensity = self.intensity * (1 - t)
        new_secondary_intensity = target.intensity * t

        if new_secondary_intensity > new_primary_intensity:
            # Target becomes primary
            return EmotionState(
                emotion=target.emotion,
                intensity=new_secondary_intensity,
                secondary_emotion=self.emotion,
                secondary_intensity=new_primary_intensity,
            )
        else:
            return EmotionState(
                emotion=self.emotion,
                intensity=new_primary_intensity,
                secondary_emotion=target.emotion,
                secondary_intensity=new_secondary_intensity,
            )


def find_closest_emotion(pad: EmotionVector) -> Tuple[CanonicalEmotion, float]:
    """
    Find the closest canonical emotion to a PAD vector.

    Useful for converting PAD-space computations back to discrete categories.

    Args:
        pad: PAD vector to classify

    Returns:
        Tuple of (closest emotion, confidence score 0-1)
    """
    min_distance = float("inf")
    closest_emotion = CanonicalEmotion.CALM

    for emotion, emotion_pad in EMOTION_TO_PAD.items():
        dist = pad.distance(emotion_pad)
        if dist < min_distance:
            min_distance = dist
            closest_emotion = emotion

    # Convert distance to confidence (0 = far, 1 = exact match)
    # Max possible distance in PAD space is sqrt(12) ≈ 3.46
    confidence = max(0.0, 1.0 - (min_distance / 3.46))

    return closest_emotion, confidence


def blend_emotions(emotions: List[Tuple[CanonicalEmotion, float]]) -> EmotionState:
    """
    Blend multiple emotions weighted by intensity.

    Args:
        emotions: List of (emotion, intensity) tuples

    Returns:
        Blended EmotionState
    """
    if not emotions:
        return EmotionState(CanonicalEmotion.CALM, 0.0)

    if len(emotions) == 1:
        return EmotionState(emotions[0][0], emotions[0][1])

    # Weighted average of PAD vectors
    total_weight = sum(intensity for _, intensity in emotions)
    if total_weight == 0:
        return EmotionState(CanonicalEmotion.CALM, 0.0)

    blended_pad = EmotionVector.neutral()
    for emotion, intensity in emotions:
        pad = EMOTION_TO_PAD[emotion].scale(intensity / total_weight)
        blended_pad = blended_pad + pad

    # Find closest discrete emotion
    closest, confidence = find_closest_emotion(blended_pad)

    # Return with the two strongest emotions
    sorted_emotions = sorted(emotions, key=lambda x: x[1], reverse=True)
    primary = sorted_emotions[0]
    secondary = sorted_emotions[1] if len(sorted_emotions) > 1 else None

    return EmotionState(
        emotion=primary[0],
        intensity=primary[1],
        secondary_emotion=secondary[0] if secondary else None,
        secondary_intensity=secondary[1] if secondary else 0.0,
    )
