"""Text-to-Speech integration for GitHub AI agents."""

from .integration import TTSIntegration
from .voice_catalog import VOICE_CATALOG, VoiceCharacter, get_voice_for_context, get_voice_settings_for_emotion

__all__ = [
    "TTSIntegration",
    "VoiceCharacter",
    "get_voice_for_context",
    "get_voice_settings_for_emotion",
    "VOICE_CATALOG",
]
