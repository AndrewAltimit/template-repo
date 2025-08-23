"""Text-to-Speech integration for GitHub AI agents."""

from .integration import TTSIntegration
from .voice_profiles import AGENT_VOICE_MAPPING, V3_COMPATIBLE_VOICES, VoiceProfile, get_voice_profile

__all__ = ["TTSIntegration", "VoiceProfile", "get_voice_profile", "AGENT_VOICE_MAPPING", "V3_COMPATIBLE_VOICES"]
