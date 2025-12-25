"""
Expression types and dataclasses for multi-modal expression coordination.

This module defines the data structures used by the ExpressionOrchestrator
to coordinate expression across voice, avatar, and visual modalities.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class Modality(Enum):
    """Available expression modalities."""

    VOICE = "voice"
    AVATAR = "avatar"
    REACTION = "reaction"


@dataclass
class AudioResult:
    """Result from voice synthesis."""

    local_path: str
    duration: float
    voice_id: str
    audio_tags: List[str] = field(default_factory=list)
    format: str = "mp3"
    sample_rate: int = 44100

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "local_path": self.local_path,
            "duration": self.duration,
            "voice_id": self.voice_id,
            "audio_tags": self.audio_tags,
            "format": self.format,
            "sample_rate": self.sample_rate,
        }


@dataclass
class AvatarResult:
    """Result from avatar expression update."""

    emotion: str
    emotion_intensity: float
    gesture: Optional[str] = None
    animation_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "emotion": self.emotion,
            "emotion_intensity": self.emotion_intensity,
            "gesture": self.gesture,
            "animation_id": self.animation_id,
        }


@dataclass
class ReactionResult:
    """Result from reaction image search."""

    reaction_id: str
    markdown: str
    url: str
    similarity: float
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "reaction_id": self.reaction_id,
            "markdown": self.markdown,
            "url": self.url,
            "similarity": self.similarity,
            "tags": self.tags,
        }


@dataclass
class ExpressionResult:
    """
    Combined result from multi-modal expression.

    Contains results from each modality that was activated during expression.
    """

    audio: Optional[AudioResult] = None
    avatar: Optional[AvatarResult] = None
    reaction: Optional[ReactionResult] = None
    text: Optional[str] = None
    emotion_name: Optional[str] = None
    intensity: Optional[float] = None
    remembered: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "audio": self.audio.to_dict() if self.audio else None,
            "avatar": self.avatar.to_dict() if self.avatar else None,
            "reaction": self.reaction.to_dict() if self.reaction else None,
            "text": self.text,
            "emotion_name": self.emotion_name,
            "intensity": self.intensity,
            "remembered": self.remembered,
        }

    @property
    def modalities_used(self) -> List[Modality]:
        """Return list of modalities that were activated."""
        result = []
        if self.audio:
            result.append(Modality.VOICE)
        if self.avatar:
            result.append(Modality.AVATAR)
        if self.reaction:
            result.append(Modality.REACTION)
        return result


@dataclass
class ExpressionConfig:
    """
    Configuration for the ExpressionOrchestrator.

    Allows customization of default behaviors and modality settings.
    """

    default_voice_id: str = "Rachel"
    default_intensity: float = 0.5
    default_modalities: List[Modality] = field(default_factory=lambda: [Modality.VOICE, Modality.AVATAR, Modality.REACTION])
    remember_expressions: bool = True
    avatar_gesture_enabled: bool = True
    reaction_limit: int = 1

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "default_voice_id": self.default_voice_id,
            "default_intensity": self.default_intensity,
            "default_modalities": [m.value for m in self.default_modalities],
            "remember_expressions": self.remember_expressions,
            "avatar_gesture_enabled": self.avatar_gesture_enabled,
            "reaction_limit": self.reaction_limit,
        }
