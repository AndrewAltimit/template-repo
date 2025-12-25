"""
Personality Memory Utilities for Expressive AI Agent System.

This module provides utilities for storing and retrieving:
- Voice preferences (ElevenLabs voices, presets, speaking styles)
- Expression patterns (learned emotion expression preferences)
- Reaction history (successful reaction usage patterns)
- Avatar settings (gestures, emotion intensities)

These utilities work with AgentCore Memory via MCP calls.

Usage:
    from mcp_core.personality import PersonalityMemory

    # Initialize with MCP client or function
    memory = PersonalityMemory(mcp_client)

    # Store voice preference
    await memory.store_voice_preference(
        voice_id="Rachel",
        use_case="code_review",
        effectiveness=0.8,
        notes="Professional but friendly tone works well"
    )

    # Get voice preferences for a use case
    prefs = await memory.get_voice_preferences("code_review")
"""

from .memory import (
    ExpressionPattern,
    PersonalityMemory,
    ReactionUsage,
    VoicePreference,
)

__all__ = [
    "PersonalityMemory",
    "VoicePreference",
    "ExpressionPattern",
    "ReactionUsage",
]
