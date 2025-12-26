"""
Type definitions for the Dual-Speed Cognitive Architecture.

Implements Kahneman's System 1/System 2 model:
- FastMind (System 1): Immediate reactions in <100ms
- SlowMind (System 2): Deep reasoning in 2-30s

Types:
- ProcessingState: Current state of cognitive processing
- EscalationReason: Why processing was escalated to slow system
- FastReaction: Output from fast (System 1) processing
- SlowSynthesis: Output from slow (System 2) processing
- CognitiveResult: Combined result from both systems
- CognitiveConfig: Configuration for the cognitive system
- ListeningBehavior: Avatar behavior during slow processing
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from ..emotions import CanonicalEmotion, EmotionState


class ProcessingState(Enum):
    """Current state of cognitive processing."""

    IDLE = "idle"  # No active processing
    FAST_PROCESSING = "fast_processing"  # System 1 active
    FAST_COMPLETE = "fast_complete"  # System 1 done
    SLOW_PROCESSING = "slow_processing"  # System 2 active
    SLOW_COMPLETE = "slow_complete"  # System 2 done
    ABORTED = "aborted"  # Processing cancelled


class EscalationReason(Enum):
    """Reasons for escalating to slow (System 2) processing."""

    NONE = "none"  # No escalation needed
    COMPLEXITY_KEYWORDS = "complexity_keywords"  # "explain", "why", "how"
    LONG_INPUT = "long_input"  # Input exceeds word threshold
    EMOTIONAL_SPIKE = "emotional_spike"  # High emotional valence detected
    FOLLOW_UP_REFERENCE = "follow_up_reference"  # References previous context
    NO_CACHED_PATTERN = "no_cached_pattern"  # No suitable cached response
    EXPLICIT_REQUEST = "explicit_request"  # User explicitly requested deep thinking
    UNCERTAINTY = "uncertainty"  # Low confidence in fast response


class ListeningBehavior(Enum):
    """Avatar behaviors during slow processing (active listening)."""

    IDLE = "idle"
    NOD = "nod"  # Acknowledgment nod
    GAZE_AWAY = "gaze_away"  # Looking away thoughtfully
    THINKING = "thinking"  # Thinking gesture
    FOCUS = "focus"  # Focused attention
    ANTICIPATION = "anticipation"  # Waiting with anticipation


@dataclass
class EscalationResult:
    """Result of escalation detection."""

    should_escalate: bool
    reason: EscalationReason = EscalationReason.NONE
    confidence: float = 0.0  # 0-1 confidence in escalation decision
    details: str = ""  # Human-readable explanation

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "should_escalate": self.should_escalate,
            "reason": self.reason.value,
            "confidence": round(self.confidence, 3),
            "details": self.details,
        }


@dataclass
class FastReaction:
    """
    Output from System 1 (fast) processing.

    Generated in <100ms with zero network dependencies.

    Attributes:
        emotion: Inferred emotional state
        filler_text: Non-committal acknowledgment to show listening
        should_escalate: Whether to defer to slow system
        escalation: Details about escalation decision
        cached_pattern: Optional cached response pattern if available
        processing_time_ms: Time taken to generate this reaction
        timestamp: When this reaction was generated
    """

    emotion: EmotionState
    filler_text: str
    should_escalate: bool = False
    escalation: Optional[EscalationResult] = None
    cached_pattern: Optional[str] = None
    processing_time_ms: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "emotion": self.emotion.to_dict(),
            "filler_text": self.filler_text,
            "should_escalate": self.should_escalate,
            "escalation": self.escalation.to_dict() if self.escalation else None,
            "cached_pattern": self.cached_pattern,
            "processing_time_ms": round(self.processing_time_ms, 2),
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class SlowSynthesis:
    """
    Output from System 2 (slow) processing.

    Generated in 2-30s using external reasoning (e.g., Claude).

    Attributes:
        response: The synthesized response text
        emotion: Final emotional state after deep reasoning
        detected_tone: Tone detected in the input (for adaptation)
        pattern_to_cache: Pattern to store for future fast retrieval
        reasoning_trace: Optional trace of reasoning steps
        processing_time_ms: Time taken to synthesize
        model_used: Which model/reasoner was used
        timestamp: When this synthesis was completed
    """

    response: str
    emotion: EmotionState
    detected_tone: Optional[str] = None
    pattern_to_cache: Optional[str] = None
    reasoning_trace: Optional[List[str]] = None
    processing_time_ms: float = 0.0
    model_used: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "response": self.response,
            "emotion": self.emotion.to_dict(),
            "detected_tone": self.detected_tone,
            "pattern_to_cache": self.pattern_to_cache,
            "reasoning_trace": self.reasoning_trace,
            "processing_time_ms": round(self.processing_time_ms, 2),
            "model_used": self.model_used,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class CognitiveResult:
    """
    Combined result from dual-speed cognitive processing.

    Contains outputs from both fast (System 1) and slow (System 2) systems,
    along with metadata about the processing flow.

    Attributes:
        fast_reaction: Always present - immediate reaction
        slow_synthesis: Present if escalation occurred and completed
        processing_state: Current state of processing
        listening_behaviors: Behaviors displayed during slow processing
        total_time_ms: Total processing time
        input_text: Original input that triggered processing
    """

    fast_reaction: FastReaction
    slow_synthesis: Optional[SlowSynthesis] = None
    processing_state: ProcessingState = ProcessingState.FAST_COMPLETE
    listening_behaviors: List[ListeningBehavior] = field(default_factory=list)
    total_time_ms: float = 0.0
    input_text: str = ""

    @property
    def final_response(self) -> str:
        """Get the final response text (slow if available, else filler)."""
        if self.slow_synthesis:
            return self.slow_synthesis.response
        return self.fast_reaction.filler_text

    @property
    def final_emotion(self) -> EmotionState:
        """Get the final emotion state (slow if available, else fast)."""
        if self.slow_synthesis:
            return self.slow_synthesis.emotion
        return self.fast_reaction.emotion

    @property
    def was_escalated(self) -> bool:
        """Check if processing was escalated to slow system."""
        return self.fast_reaction.should_escalate

    @property
    def is_complete(self) -> bool:
        """Check if all processing is complete."""
        if self.was_escalated:
            return self.processing_state == ProcessingState.SLOW_COMPLETE
        return self.processing_state == ProcessingState.FAST_COMPLETE

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "fast_reaction": self.fast_reaction.to_dict(),
            "slow_synthesis": self.slow_synthesis.to_dict() if self.slow_synthesis else None,
            "processing_state": self.processing_state.value,
            "listening_behaviors": [b.value for b in self.listening_behaviors],
            "total_time_ms": round(self.total_time_ms, 2),
            "input_text": self.input_text,
            "final_response": self.final_response,
            "was_escalated": self.was_escalated,
            "is_complete": self.is_complete,
        }


@dataclass
class CognitiveConfig:
    """
    Configuration for the cognitive system.

    Attributes:
        escalation_word_threshold: Min words to trigger long input escalation
        escalation_emotional_threshold: Intensity threshold for emotional spike
        default_filler_vibe: Default vibe for filler selection (casual/professional)
        active_listening_enabled: Whether to use active listening behaviors
        listening_behavior_interval_ms: Time between behavior changes
        pattern_cache_enabled: Whether to cache and retrieve patterns
        max_slow_processing_ms: Timeout for slow processing
        default_emotion: Default emotion when none detected
    """

    escalation_word_threshold: int = 20
    escalation_emotional_threshold: float = 0.8
    default_filler_vibe: str = "casual"
    active_listening_enabled: bool = True
    listening_behavior_interval_ms: int = 2000
    pattern_cache_enabled: bool = True
    max_slow_processing_ms: int = 30000
    default_emotion: CanonicalEmotion = CanonicalEmotion.CALM

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "escalation_word_threshold": self.escalation_word_threshold,
            "escalation_emotional_threshold": self.escalation_emotional_threshold,
            "default_filler_vibe": self.default_filler_vibe,
            "active_listening_enabled": self.active_listening_enabled,
            "listening_behavior_interval_ms": self.listening_behavior_interval_ms,
            "pattern_cache_enabled": self.pattern_cache_enabled,
            "max_slow_processing_ms": self.max_slow_processing_ms,
            "default_emotion": self.default_emotion.value,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CognitiveConfig":
        """Create from dictionary."""
        return cls(
            escalation_word_threshold=data.get("escalation_word_threshold", 20),
            escalation_emotional_threshold=data.get("escalation_emotional_threshold", 0.8),
            default_filler_vibe=data.get("default_filler_vibe", "casual"),
            active_listening_enabled=data.get("active_listening_enabled", True),
            listening_behavior_interval_ms=data.get("listening_behavior_interval_ms", 2000),
            pattern_cache_enabled=data.get("pattern_cache_enabled", True),
            max_slow_processing_ms=data.get("max_slow_processing_ms", 30000),
            default_emotion=CanonicalEmotion(data.get("default_emotion", "calm")),
        )
