"""
Active Listening Behaviors for Dual-Speed Cognitive Architecture.

Provides ambient avatar behaviors during slow (System 2) processing
to maintain the illusion of engagement while deep reasoning occurs.

Behaviors cycle through natural patterns:
- Nods: Acknowledgment
- Gaze shifts: Thoughtful contemplation
- Thinking poses: Processing indication
"""

from dataclasses import dataclass, field
import random
import time
from typing import Any, Callable, Dict, List, Optional

from ..emotions import CanonicalEmotion
from .types import CognitiveConfig, ListeningBehavior


@dataclass
class BehaviorEvent:
    """
    A single behavior event to display.

    Attributes:
        behavior: The behavior type
        duration_ms: How long to display this behavior
        emotion_hint: Optional emotion context
        gesture: Optional specific gesture name
        timestamp: When this event was created
    """

    behavior: ListeningBehavior
    duration_ms: float = 2000.0
    emotion_hint: Optional[CanonicalEmotion] = None
    gesture: Optional[str] = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "behavior": self.behavior.value,
            "duration_ms": self.duration_ms,
            "emotion_hint": self.emotion_hint.value if self.emotion_hint else None,
            "gesture": self.gesture,
            "timestamp": self.timestamp,
        }


# Behavior weights by context
# Higher weight = more likely to be selected
BEHAVIOR_WEIGHTS: Dict[ListeningBehavior, float] = {
    ListeningBehavior.NOD: 0.3,  # Common acknowledgment
    ListeningBehavior.GAZE_AWAY: 0.25,  # Thoughtful
    ListeningBehavior.THINKING: 0.25,  # Processing
    ListeningBehavior.FOCUS: 0.15,  # Attentive
    ListeningBehavior.ANTICIPATION: 0.05,  # Rare, for building tension
}

# Specific gestures for each behavior type
BEHAVIOR_GESTURES: Dict[ListeningBehavior, List[str]] = {
    ListeningBehavior.NOD: ["nod_slow", "nod_quick", "nod_double"],
    ListeningBehavior.GAZE_AWAY: ["look_up", "look_side", "look_down"],
    ListeningBehavior.THINKING: ["chin_touch", "brow_furrow", "head_tilt"],
    ListeningBehavior.FOCUS: ["lean_in", "eyes_narrow", "direct_gaze"],
    ListeningBehavior.ANTICIPATION: ["slight_smile", "raised_brow", "lean_forward"],
}

# Duration ranges for each behavior (min, max in ms)
BEHAVIOR_DURATIONS: Dict[ListeningBehavior, tuple[float, float]] = {
    ListeningBehavior.NOD: (500, 1000),
    ListeningBehavior.GAZE_AWAY: (1500, 3000),
    ListeningBehavior.THINKING: (2000, 4000),
    ListeningBehavior.FOCUS: (1000, 2000),
    ListeningBehavior.ANTICIPATION: (1000, 2000),
}


class ActiveListeningController:
    """
    Controls ambient avatar behaviors during slow processing.

    Cycles through natural behaviors to maintain engagement
    while the slow (System 2) reasoning occurs in the background.
    """

    def __init__(
        self,
        config: Optional[CognitiveConfig] = None,
        behavior_callback: Optional[Callable[[BehaviorEvent], None]] = None,
    ):
        """
        Initialize the controller.

        Args:
            config: Cognitive configuration
            behavior_callback: Optional async callback for behavior events
        """
        self.config = config or CognitiveConfig()
        self._callback = behavior_callback

        self._is_active = False
        self._current_behavior: Optional[BehaviorEvent] = None
        self._behavior_history: List[BehaviorEvent] = []
        self._start_time: Optional[float] = None
        self._last_behavior_time: float = 0.0

    @property
    def is_active(self) -> bool:
        """Check if active listening is currently running."""
        return self._is_active

    @property
    def current_behavior(self) -> Optional[BehaviorEvent]:
        """Get the current behavior being displayed."""
        return self._current_behavior

    def start(self, context_emotion: Optional[CanonicalEmotion] = None) -> BehaviorEvent:
        """
        Start active listening behaviors.

        Args:
            context_emotion: Optional emotional context to influence behaviors

        Returns:
            The first behavior event
        """
        self._is_active = True
        self._start_time = time.time()
        self._behavior_history.clear()

        # Generate initial behavior
        return self._next_behavior(context_emotion)

    def stop(self) -> List[BehaviorEvent]:
        """
        Stop active listening.

        Returns:
            List of all behaviors that were displayed
        """
        self._is_active = False
        self._current_behavior = None
        history = list(self._behavior_history)
        return history

    def update(
        self,
        dt_ms: float,
        context_emotion: Optional[CanonicalEmotion] = None,
    ) -> Optional[BehaviorEvent]:
        """
        Update the behavior state.

        Call this periodically to get new behaviors when the current
        one expires.

        Args:
            dt_ms: Time delta in milliseconds
            context_emotion: Optional emotional context

        Returns:
            New behavior event if behavior changed, None otherwise
        """
        if not self._is_active:
            return None

        current_time = time.time()
        elapsed_since_behavior = (current_time - self._last_behavior_time) * 1000

        # Check if current behavior has expired
        if self._current_behavior is None:
            return self._next_behavior(context_emotion)

        if elapsed_since_behavior >= self._current_behavior.duration_ms:
            return self._next_behavior(context_emotion)

        return None

    def _next_behavior(
        self,
        context_emotion: Optional[CanonicalEmotion] = None,
    ) -> BehaviorEvent:
        """Generate the next behavior event."""
        # Select behavior based on weights
        behavior = self._select_behavior(context_emotion)

        # Get duration for this behavior
        min_dur, max_dur = BEHAVIOR_DURATIONS.get(behavior, (1000, 2000))
        duration = random.uniform(min_dur, max_dur)

        # Get a specific gesture
        gestures = BEHAVIOR_GESTURES.get(behavior, [])
        gesture = random.choice(gestures) if gestures else None

        event = BehaviorEvent(
            behavior=behavior,
            duration_ms=duration,
            emotion_hint=context_emotion,
            gesture=gesture,
        )

        self._current_behavior = event
        self._behavior_history.append(event)
        self._last_behavior_time = time.time()

        # Trigger callback if set
        if self._callback:
            try:
                self._callback(event)
            except Exception:
                pass  # Don't fail on callback errors

        return event

    def _select_behavior(
        self,
        context_emotion: Optional[CanonicalEmotion] = None,
    ) -> ListeningBehavior:
        """Select a behavior based on weights and context."""
        # Adjust weights based on context
        weights = dict(BEHAVIOR_WEIGHTS)

        if context_emotion:
            # Modify weights based on emotion
            if context_emotion == CanonicalEmotion.CONFUSION:
                weights[ListeningBehavior.THINKING] *= 1.5
                weights[ListeningBehavior.GAZE_AWAY] *= 1.2
            elif context_emotion == CanonicalEmotion.JOY:
                weights[ListeningBehavior.NOD] *= 1.3
                weights[ListeningBehavior.ANTICIPATION] *= 1.5
            elif context_emotion == CanonicalEmotion.ATTENTIVE:
                weights[ListeningBehavior.FOCUS] *= 2.0
                weights[ListeningBehavior.NOD] *= 1.2

        # Avoid repeating the same behavior
        if self._current_behavior:
            weights[self._current_behavior.behavior] *= 0.3

        # Weighted random selection
        behaviors = list(weights.keys())
        behavior_weights = [weights[b] for b in behaviors]
        total = sum(behavior_weights)
        normalized = [w / total for w in behavior_weights]

        r = random.random()
        cumulative = 0.0
        for behavior, weight in zip(behaviors, normalized):
            cumulative += weight
            if r <= cumulative:
                return behavior

        return ListeningBehavior.NOD  # Fallback

    def set_callback(self, callback: Callable[[BehaviorEvent], None]) -> None:
        """Set the behavior callback function."""
        self._callback = callback

    def get_behavior_sequence(self, duration_ms: float) -> List[BehaviorEvent]:
        """
        Pre-generate a sequence of behaviors for a given duration.

        Useful for planning ahead or testing.

        Args:
            duration_ms: Total duration to fill

        Returns:
            List of behavior events
        """
        sequence: List[BehaviorEvent] = []
        total_duration = 0.0

        while total_duration < duration_ms:
            behavior = self._select_behavior()
            min_dur, max_dur = BEHAVIOR_DURATIONS.get(behavior, (1000, 2000))
            duration = random.uniform(min_dur, max_dur)

            gestures = BEHAVIOR_GESTURES.get(behavior, [])
            gesture = random.choice(gestures) if gestures else None

            event = BehaviorEvent(
                behavior=behavior,
                duration_ms=duration,
                gesture=gesture,
            )
            sequence.append(event)
            total_duration += duration

        return sequence

    def get_history(self) -> List[Dict[str, Any]]:
        """Get history of displayed behaviors."""
        return [event.to_dict() for event in self._behavior_history]

    def get_elapsed_time_ms(self) -> float:
        """Get elapsed time since active listening started."""
        if self._start_time is None:
            return 0.0
        return (time.time() - self._start_time) * 1000
