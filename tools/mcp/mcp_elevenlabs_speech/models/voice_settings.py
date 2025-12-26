"""Voice settings and presets for ElevenLabs synthesis"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional


class StabilityMode(Enum):
    """Stability modes for v3"""

    CREATIVE = 0.3  # More emotional and expressive, but prone to hallucinations
    NATURAL = 0.5  # Balanced and neutral, closest to original voice
    ROBUST = 0.9  # Highly stable but less responsive to directional prompts


class VoiceModel(Enum):
    """Available ElevenLabs models"""

    ELEVEN_V3 = "eleven_v3"  # Latest, most expressive (alpha)
    ELEVEN_MULTILINGUAL_V2 = "eleven_multilingual_v2"  # 29 languages
    ELEVEN_MULTILINGUAL_V1 = "eleven_multilingual_v1"  # Legacy
    ELEVEN_FLASH_V2 = "eleven_flash_v2"  # Fast, 32 languages
    ELEVEN_FLASH_V2_5 = "eleven_flash_v2_5"  # Latest flash
    ELEVEN_TURBO_V2 = "eleven_turbo_v2"  # Real-time optimized
    ELEVEN_TURBO_V2_5 = "eleven_turbo_v2_5"  # Latest turbo
    ELEVEN_ENGLISH_V1 = "eleven_english_v1"  # English only, legacy


class OutputFormat(Enum):
    """Audio output formats"""

    # MP3 formats
    MP3_22050_32 = "mp3_22050_32"  # Low quality, small size
    MP3_44100_64 = "mp3_44100_64"
    MP3_44100_96 = "mp3_44100_96"
    MP3_44100_128 = "mp3_44100_128"  # Default, high quality
    MP3_44100_192 = "mp3_44100_192"
    # PCM formats (raw audio - no decompression needed, best for streaming)
    PCM_16000 = "pcm_16000"
    PCM_22050 = "pcm_22050"
    PCM_24000 = "pcm_24000"  # Good balance for streaming
    PCM_44100 = "pcm_44100"
    PCM_48000 = "pcm_48000"  # Highest quality PCM
    # Telephony formats
    ULAW_8000 = "ulaw_8000"
    ALAW_8000 = "alaw_8000"
    # Opus formats (best quality-to-size ratio for speech)
    OPUS_48000_32 = "opus_48000_32"  # Low bandwidth streaming
    OPUS_48000_64 = "opus_48000_64"  # Balanced streaming
    OPUS_48000_128 = "opus_48000_128"  # High quality streaming


@dataclass
class VoiceSettings:
    """Voice settings for synthesis"""

    stability: float = 0.5  # 0.0 to 1.0
    similarity_boost: float = 0.75  # 0.0 to 1.0
    style: float = 0.0  # 0.0 to 1.0 (style exaggeration)
    use_speaker_boost: bool = False  # Increases similarity but adds latency
    speed: float = 1.0  # 0.7 to 1.2 - speech tempo adjustment

    def to_dict(self) -> Dict[str, Any]:
        """Convert to API parameters"""
        result = {
            "stability": self.stability,
            "similarity_boost": self.similarity_boost,
            "style": self.style,
            "use_speaker_boost": self.use_speaker_boost,
        }
        # Only include speed if not default (reduces request size)
        if self.speed != 1.0:
            result["speed"] = max(0.7, min(1.2, self.speed))
        return result

    @classmethod
    def from_preset(cls, preset: str) -> "VoiceSettings":
        """Create from preset name"""
        if preset in VOICE_PRESETS:
            return cls(**VOICE_PRESETS[preset])
        raise ValueError(f"Unknown preset: {preset}")


@dataclass
class VoicePreset:
    """Preset configuration for common use cases"""

    name: str
    description: str
    stability: float
    similarity_boost: float
    style: float
    use_speaker_boost: bool
    recommended_model: VoiceModel
    use_case: str


# Optimized presets for different scenarios
VOICE_PRESETS: Dict[str, Dict[str, Any]] = {
    "audiobook": {"stability": 0.75, "similarity_boost": 0.75, "style": 0.0, "use_speaker_boost": False},
    "character_performance": {
        "stability": 0.3,  # Creative mode
        "similarity_boost": 0.8,
        "style": 0.6,
        "use_speaker_boost": True,
    },
    "news_reading": {"stability": 0.9, "similarity_boost": 0.7, "style": 0.0, "use_speaker_boost": False},  # Robust mode
    "emotional_dialogue": {
        "stability": 0.5,  # Natural mode
        "similarity_boost": 0.85,
        "style": 0.3,
        "use_speaker_boost": True,
    },
    "github_review": {"stability": 0.6, "similarity_boost": 0.8, "style": 0.2, "use_speaker_boost": False},
    "tutorial_narration": {"stability": 0.7, "similarity_boost": 0.75, "style": 0.1, "use_speaker_boost": False},
    "podcast": {"stability": 0.5, "similarity_boost": 0.8, "style": 0.4, "use_speaker_boost": True},
    "meditation": {"stability": 0.85, "similarity_boost": 0.7, "style": 0.0, "use_speaker_boost": False},
    "storytelling": {"stability": 0.4, "similarity_boost": 0.75, "style": 0.5, "use_speaker_boost": True},
    "customer_service": {"stability": 0.8, "similarity_boost": 0.75, "style": 0.0, "use_speaker_boost": False},
}


# Detailed preset configurations
PRESET_DETAILS = [
    VoicePreset(
        name="audiobook",
        description="Consistent narration for long-form content",
        stability=0.75,
        similarity_boost=0.75,
        style=0.0,
        use_speaker_boost=False,
        recommended_model=VoiceModel.ELEVEN_MULTILINGUAL_V2,
        use_case="Books, articles, documentation",
    ),
    VoicePreset(
        name="character_performance",
        description="Expressive character voices with emotion",
        stability=0.3,
        similarity_boost=0.8,
        style=0.6,
        use_speaker_boost=True,
        recommended_model=VoiceModel.ELEVEN_V3,
        use_case="Games, animations, dramatic readings",
    ),
    VoicePreset(
        name="github_review",
        description="Professional yet friendly code review tone",
        stability=0.6,
        similarity_boost=0.8,
        style=0.2,
        use_speaker_boost=False,
        recommended_model=VoiceModel.ELEVEN_V3,
        use_case="PR reviews, issue discussions, technical feedback",
    ),
]


def optimize_settings_for_text(text: str, base_settings: Optional[VoiceSettings] = None) -> VoiceSettings:
    """
    Optimize voice settings based on text content

    Args:
        text: Text to be synthesized
        base_settings: Optional base settings to modify

    Returns:
        Optimized VoiceSettings
    """
    if base_settings is None:
        base_settings = VoiceSettings()

    # Detect if text has many audio tags (needs lower stability)
    tag_count = text.count("[")
    if tag_count > 3:
        base_settings.stability = max(0.3, base_settings.stability - 0.1)
        base_settings.style = min(0.6, base_settings.style + 0.1)

    # Detect if text is very long (needs higher stability)
    word_count = len(text.split())
    if word_count > 500:
        base_settings.stability = min(0.8, base_settings.stability + 0.1)
        base_settings.style = max(0.0, base_settings.style - 0.1)

    # Detect emotional content
    emotional_indicators = ["!", "?", "...", "oh", "wow", "amazing", "terrible", "sad", "happy"]
    emotion_count = sum(1 for indicator in emotional_indicators if indicator in text.lower())
    if emotion_count > 2:
        base_settings.stability = max(0.3, base_settings.stability - 0.1)
        base_settings.use_speaker_boost = True

    return base_settings


def get_model_for_use_case(
    use_case: str, requires_streaming: bool = False, language: Optional[str] = "en", low_latency: bool = False
) -> VoiceModel:
    """
    Select the best model for a use case

    Args:
        use_case: Type of content (dialogue, narration, etc.)
        requires_streaming: If real-time streaming is needed (WebSocket)
        language: Language code
        low_latency: Prioritize lowest latency (~75ms with Flash v2.5)

    Returns:
        Recommended VoiceModel

    Note:
        WebSockets are NOT available for eleven_v3 model.
        For streaming, use Flash v2.5 (75ms latency) or Turbo v2.5.
    """
    # For lowest latency streaming (virtual characters, real-time apps)
    if low_latency or requires_streaming:
        # Flash v2.5 delivers ~75ms inference, best for real-time
        return VoiceModel.ELEVEN_FLASH_V2_5

    # For expressive content with audio tags (non-streaming only)
    if use_case in ["character_performance", "emotional_dialogue", "github_review"]:
        return VoiceModel.ELEVEN_V3

    # For multilingual content
    if language and language != "en":
        return VoiceModel.ELEVEN_MULTILINGUAL_V2

    # For fast generation without streaming
    if use_case in ["customer_service", "quick_response"]:
        return VoiceModel.ELEVEN_FLASH_V2_5

    # Default to v3 for best quality
    return VoiceModel.ELEVEN_V3
