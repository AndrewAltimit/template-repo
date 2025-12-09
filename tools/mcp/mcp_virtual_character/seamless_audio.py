#!/usr/bin/env python3
"""
Seamless audio integration for Virtual Character system.

DEPRECATED: This module is deprecated. Use seamless_audio_v2 instead.

This module is kept for backward compatibility and re-exports from seamless_audio_v2.

For new code, use:
    from mcp_virtual_character.seamless_audio_v2 import SeamlessAudioPlayer
    # or
    from mcp_virtual_character.seamless_audio_v2 import play_audio_seamlessly
"""

import warnings

# Issue deprecation warning
warnings.warn(
    "seamless_audio is deprecated, use seamless_audio_v2 instead",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export everything from v2 for backward compatibility
from mcp_virtual_character.seamless_audio_v2 import (  # noqa: E402, F401
    SeamlessAudioPlayer,
    mcp_play_audio_helper,
    play_audio_seamlessly,
    test_configuration,
)

# Also re-export setup function name for compatibility
setup_seamless_audio = test_configuration

__all__ = [
    "SeamlessAudioPlayer",
    "play_audio_seamlessly",
    "mcp_play_audio_helper",
    "setup_seamless_audio",
    "test_configuration",
]
