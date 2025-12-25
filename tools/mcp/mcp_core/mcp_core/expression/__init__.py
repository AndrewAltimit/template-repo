"""
Expression module for multi-modal expression orchestration.

This module provides the ExpressionOrchestrator and related types for
coordinating expression across voice, avatar, and visual modalities
with emotional coherence.
"""

from .orchestrator import ExpressionOrchestrator, MCPClients
from .types import (
    AudioResult,
    AvatarResult,
    ExpressionConfig,
    ExpressionResult,
    Modality,
    ReactionResult,
)

__all__ = [
    # Main orchestrator
    "ExpressionOrchestrator",
    "MCPClients",
    # Configuration
    "ExpressionConfig",
    # Result types
    "ExpressionResult",
    "AudioResult",
    "AvatarResult",
    "ReactionResult",
    # Enums
    "Modality",
]
