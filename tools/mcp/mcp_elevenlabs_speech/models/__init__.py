"""Models for ElevenLabs Speech MCP Server"""

from .audio_tags import (
    AUDIO_TAGS,
    AudioTagCategory,
    create_expressive_text,
    parse_audio_tags,
    suggest_tags,
    validate_tag_compatibility,
)
from .synthesis_config import (
    DialogueLine,
    DialogueScript,
    GitHubAudioConfig,
    SoundEffectConfig,
    StreamConfig,
    SynthesisConfig,
    SynthesisResult,
)
from .voice_settings import VOICE_PRESETS, OutputFormat, VoiceModel, VoicePreset, VoiceSettings

__all__ = [
    "AUDIO_TAGS",
    "AudioTagCategory",
    "parse_audio_tags",
    "suggest_tags",
    "validate_tag_compatibility",
    "create_expressive_text",
    "SynthesisConfig",
    "SynthesisResult",
    "DialogueScript",
    "DialogueLine",
    "SoundEffectConfig",
    "GitHubAudioConfig",
    "StreamConfig",
    "VoiceSettings",
    "VoicePreset",
    "VOICE_PRESETS",
    "VoiceModel",
    "OutputFormat",
]
