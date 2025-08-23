"""Voice profiles for different AI agents."""

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class VoiceProfile:
    """Voice profile configuration for an agent."""

    voice_id: str
    name: str
    description: str
    stability: float = 0.5
    similarity_boost: float = 0.75
    style: float = 0.0
    use_speaker_boost: bool = False


# V3-compatible voices that work well with emotional tags
V3_COMPATIBLE_VOICES = {
    "blondie": VoiceProfile(
        voice_id="exsUS4vynmxd379XN4yO",
        name="Blondie - Conversational",
        description="British, casual, conversational tone",
        stability=0.0,  # More expressive for emotions
        similarity_boost=0.75,
        style=0.0,
        use_speaker_boost=True,
    ),
    "rachel": VoiceProfile(
        voice_id="21m00Tcm4TlvDq8ikWAM",
        name="Rachel",
        description="American, young, casual conversational",
        stability=0.3,
        similarity_boost=0.75,
        style=0.0,
        use_speaker_boost=False,
    ),
    "alice": VoiceProfile(
        voice_id="Xb7hH8MSUJpSbSDYk0k2",
        name="Alice",
        description="British, professional, middle-aged",
        stability=0.5,
        similarity_boost=0.75,
        style=0.0,
        use_speaker_boost=False,
    ),
    "daniel": VoiceProfile(
        voice_id="onwK4e9ZLuTAKqWW03F9",
        name="Daniel",
        description="British, formal, educational tone",
        stability=0.4,
        similarity_boost=0.75,
        style=0.0,
        use_speaker_boost=False,
    ),
    "river": VoiceProfile(
        voice_id="SAz9YHcvj6GT2YYXdXww",
        name="River",
        description="American, calm, neutral gender",
        stability=0.5,
        similarity_boost=0.75,
        style=0.0,
        use_speaker_boost=False,
    ),
}

# Agent-specific voice assignments
AGENT_VOICE_MAPPING = {
    "gemini": "blondie",  # Conversational and expressive
    "claude": "alice",  # Professional and thoughtful
    "opencode": "daniel",  # Formal and educational
    "crush": "rachel",  # Young and casual
    "default": "river",  # Neutral fallback
}


def get_voice_profile(agent_name: str) -> VoiceProfile:
    """Get voice profile for a specific agent.

    Args:
        agent_name: Name of the agent (gemini, claude, etc.)

    Returns:
        VoiceProfile for the agent
    """
    # Get the voice key for this agent
    voice_key = AGENT_VOICE_MAPPING.get(agent_name.lower(), "default")

    # Get the voice profile
    return V3_COMPATIBLE_VOICES.get(voice_key, V3_COMPATIBLE_VOICES["river"])


def get_voice_settings(agent_name: str, override_settings: Optional[Dict] = None) -> Dict:
    """Get voice settings for synthesis.

    Args:
        agent_name: Name of the agent
        override_settings: Optional settings to override defaults

    Returns:
        Voice settings dictionary
    """
    profile = get_voice_profile(agent_name)

    settings = {
        "stability": profile.stability,
        "similarity_boost": profile.similarity_boost,
        "style": profile.style,
        "use_speaker_boost": profile.use_speaker_boost,
    }

    # Apply any overrides
    if override_settings:
        settings.update(override_settings)

    return settings
