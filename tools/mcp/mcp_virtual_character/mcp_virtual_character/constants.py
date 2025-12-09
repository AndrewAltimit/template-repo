"""Constants for Virtual Character MCP Server.

This module provides a single source of truth for:
- VRCEmote value mappings
- Gesture and emotion enumerations
- Default configuration values
"""

from enum import IntEnum
from typing import Dict

from .models.canonical import EmotionType, GestureType

__all__ = [
    # Emote value enum
    "VRCEmoteValue",
    # Mappings
    "VRCEMOTE_NAMES",
    "VRCEMOTE_BY_NAME",
    "EMOTION_TO_VRCEMOTE",
    "GESTURE_TO_VRCEMOTE",
    # Helper functions
    "get_vrcemote_name",
    "get_vrcemote_value",
    # Default configuration
    "DEFAULT_VRCHAT_HOST",
    "DEFAULT_OSC_IN_PORT",
    "DEFAULT_OSC_OUT_PORT",
    "DEFAULT_MCP_SERVER_PORT",
    "DEFAULT_STORAGE_PORT",
    "DEFAULT_HEALTH_CHECK_INTERVAL",
    "DEFAULT_AUTO_CONNECT_DELAY",
    "DEFAULT_TEMP_FILE_CLEANUP_DELAY",
    "DEFAULT_SUBPROCESS_TIMEOUT",
    "DEFAULT_AUDIO_CONVERSION_TIMEOUT",
    "DEFAULT_DOWNLOAD_TIMEOUT",
    "DEFAULT_AUDIO_DEVICE",
    "MIN_AUDIO_SIZE",
    "DEFAULT_MAX_RECONNECT_ATTEMPTS",
    # Documentation
    "VRCEMOTE_DESCRIPTION",
]


class VRCEmoteValue(IntEnum):
    """
    VRCEmote system values.

    VRChat uses integer-based emotes that map to avatar gesture wheel positions.
    Wheel positions (clockwise from top):
    0=None/Clear, 1=Wave, 2=Clap, 3=Point, 4=Cheer, 5=Dance, 6=Backflip, 7=Sadness, 8=Die
    """

    NONE = 0  # Clear/reset gesture
    WAVE = 1
    CLAP = 2
    POINT = 3
    CHEER = 4
    DANCE = 5
    BACKFLIP = 6
    SADNESS = 7
    DIE = 8


# VRCEmote value to name mapping (for display/logging)
VRCEMOTE_NAMES: Dict[int, str] = {
    VRCEmoteValue.NONE: "none/clear",
    VRCEmoteValue.WAVE: "wave",
    VRCEmoteValue.CLAP: "clap",
    VRCEmoteValue.POINT: "point",
    VRCEmoteValue.CHEER: "cheer",
    VRCEmoteValue.DANCE: "dance",
    VRCEmoteValue.BACKFLIP: "backflip",
    VRCEmoteValue.SADNESS: "sadness",
    VRCEmoteValue.DIE: "die",
}

# Name to VRCEmote value mapping (for parsing user input)
VRCEMOTE_BY_NAME: Dict[str, int] = {name: value for value, name in VRCEMOTE_NAMES.items()}
# Add aliases
VRCEMOTE_BY_NAME.update(
    {
        "clear": VRCEmoteValue.NONE,
        "reset": VRCEmoteValue.NONE,
        "thumbs_up": VRCEmoteValue.CHEER,  # Maps to cheer
    }
)


def get_vrcemote_name(value: int) -> str:
    """Get the display name for a VRCEmote value."""
    return VRCEMOTE_NAMES.get(value, "unknown")


def get_vrcemote_value(name: str) -> int:
    """Get the VRCEmote value from a name."""
    return VRCEMOTE_BY_NAME.get(name.lower(), VRCEmoteValue.NONE)


# Emotion to VRCEmote mapping (for automatic emotion-to-gesture conversion)
EMOTION_TO_VRCEMOTE: Dict[EmotionType, int] = {
    EmotionType.NEUTRAL: VRCEmoteValue.NONE,
    EmotionType.HAPPY: VRCEmoteValue.CHEER,
    EmotionType.SAD: VRCEmoteValue.SADNESS,
    EmotionType.ANGRY: VRCEmoteValue.POINT,  # Assertive pointing
    EmotionType.SURPRISED: VRCEmoteValue.BACKFLIP,  # Excitement
    EmotionType.FEARFUL: VRCEmoteValue.DIE,  # Dramatic
    EmotionType.DISGUSTED: VRCEmoteValue.NONE,
}

# Gesture to VRCEmote mapping (for gesture commands)
GESTURE_TO_VRCEMOTE: Dict[GestureType, int] = {
    GestureType.NONE: VRCEmoteValue.NONE,
    GestureType.WAVE: VRCEmoteValue.WAVE,
    GestureType.POINT: VRCEmoteValue.POINT,
    GestureType.THUMBS_UP: VRCEmoteValue.CHEER,
    GestureType.NOD: VRCEmoteValue.CLAP,  # Approval gesture
    GestureType.SHAKE_HEAD: VRCEmoteValue.NONE,
    GestureType.CLAP: VRCEmoteValue.CLAP,
    GestureType.DANCE: VRCEmoteValue.DANCE,
    GestureType.BACKFLIP: VRCEmoteValue.BACKFLIP,
    GestureType.CHEER: VRCEmoteValue.CHEER,
    GestureType.SADNESS: VRCEmoteValue.SADNESS,
    GestureType.DIE: VRCEmoteValue.DIE,
}


# =============================================================================
# Default Configuration Values
# =============================================================================

# Network defaults
DEFAULT_VRCHAT_HOST = "127.0.0.1"
DEFAULT_OSC_IN_PORT = 9000  # VRChat receives on this port
DEFAULT_OSC_OUT_PORT = 9001  # VRChat sends on this port
DEFAULT_MCP_SERVER_PORT = 8020
DEFAULT_STORAGE_PORT = 8021

# Timing defaults (in seconds)
DEFAULT_HEALTH_CHECK_INTERVAL = 30
DEFAULT_AUTO_CONNECT_DELAY = 2
DEFAULT_TEMP_FILE_CLEANUP_DELAY = 10
DEFAULT_SUBPROCESS_TIMEOUT = 10.0
DEFAULT_AUDIO_CONVERSION_TIMEOUT = 5.0
DEFAULT_DOWNLOAD_TIMEOUT = 30

# Audio defaults
DEFAULT_AUDIO_DEVICE = "VoiceMeeter Input"
MIN_AUDIO_SIZE = 100  # Minimum bytes for valid audio file

# Reconnection defaults
DEFAULT_MAX_RECONNECT_ATTEMPTS = 3


# =============================================================================
# VRCEmote Description for Tool Documentation
# =============================================================================

VRCEMOTE_DESCRIPTION = (
    "VRCEmote value: "
    f"{VRCEmoteValue.NONE}=clear, "
    f"{VRCEmoteValue.WAVE}=wave, "
    f"{VRCEmoteValue.CLAP}=clap, "
    f"{VRCEmoteValue.POINT}=point, "
    f"{VRCEmoteValue.CHEER}=cheer, "
    f"{VRCEmoteValue.DANCE}=dance, "
    f"{VRCEmoteValue.BACKFLIP}=backflip, "
    f"{VRCEmoteValue.SADNESS}=sadness, "
    f"{VRCEmoteValue.DIE}=die"
)
