"""
Dual-Speed Cognitive Architecture for Expressive AI Agents.

Implements Kahneman's System 1/System 2 cognitive model:
- **FastMind** (System 1): Immediate reactions in <100ms
- **SlowMind** (System 2): Deep reasoning in 2-30s

Components:
- types: Data structures for cognitive processing
- escalation: Escalation detection for System 1 -> System 2 handoff
- fillers: Static acknowledgment phrases for active listening
- emotion_transition: Smooth PAD-space emotion interpolation
- fast_mind: Immediate reaction generation
- slow_mind: Interface for external deep reasoning
- active_listening: Ambient avatar behaviors during slow processing
- orchestrator: Unified interface coordinating both systems

Usage:
    from mcp_core.cognition import CognitiveOrchestrator

    orchestrator = CognitiveOrchestrator()
    orchestrator.set_reasoner(my_reasoner)  # e.g., Claude API wrapper

    result = await orchestrator.process("Why did the mutex cause a race condition?")

    # Fast available immediately (<100ms)
    print(result.fast_reaction.filler_text)  # "Hmm, let me think..."
    print(result.fast_reaction.emotion)       # EmotionState(THINKING)

    # Slow available after processing (~5-30s)
    if result.slow_synthesis:
        print(result.slow_synthesis.response)  # Detailed explanation
"""

from .active_listening import ActiveListeningController, BehaviorEvent
from .emotion_transition import EmotionTransitionManager, TransitionState
from .escalation import EscalationDetector
from .fast_mind import FastMind
from .fillers import FillerLibrary, get_filler
from .orchestrator import CognitiveOrchestrator
from .slow_mind import CallableReasoner, MockReasoner, Reasoner, ReasonerContext, SlowMind
from .types import (
    CognitiveConfig,
    CognitiveResult,
    EscalationReason,
    EscalationResult,
    FastReaction,
    ListeningBehavior,
    ProcessingState,
    SlowSynthesis,
)

__all__ = [
    # Main orchestrator
    "CognitiveOrchestrator",
    # Mind systems
    "FastMind",
    "SlowMind",
    # Reasoner interface
    "Reasoner",
    "ReasonerContext",
    "MockReasoner",
    "CallableReasoner",
    # Supporting components
    "EscalationDetector",
    "FillerLibrary",
    "get_filler",
    "EmotionTransitionManager",
    "TransitionState",
    "ActiveListeningController",
    "BehaviorEvent",
    # Configuration
    "CognitiveConfig",
    # Types and enums
    "ProcessingState",
    "EscalationReason",
    "EscalationResult",
    "FastReaction",
    "SlowSynthesis",
    "CognitiveResult",
    "ListeningBehavior",
]
