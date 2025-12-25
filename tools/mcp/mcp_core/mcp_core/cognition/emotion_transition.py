"""
Emotion Transition Manager for Dual-Speed Cognitive Architecture.

Provides smooth interpolation between emotional states using the PAD
(Pleasure, Arousal, Dominance) model. Prevents jarring emotional "snaps"
by gradually transitioning between states.

Key features:
- PAD-space interpolation for mathematically smooth transitions
- Ease-out curves for natural-feeling deceleration
- Configurable transition duration
- Support for both System 1 (fast) and System 2 (slow) emotion blending
"""

from dataclasses import dataclass
import math
from typing import Optional

from ..emotions import EMOTION_TO_PAD, CanonicalEmotion, EmotionState, find_closest_emotion


@dataclass
class TransitionState:
    """
    Tracks the state of an ongoing emotion transition.

    Attributes:
        start_state: The emotion state at transition start
        target_state: The emotion state we're transitioning to
        progress: Current progress (0.0 = start, 1.0 = complete)
        duration_ms: Total transition duration in milliseconds
        elapsed_ms: Time elapsed since transition started
    """

    start_state: EmotionState
    target_state: EmotionState
    progress: float = 0.0
    duration_ms: float = 500.0
    elapsed_ms: float = 0.0

    @property
    def is_complete(self) -> bool:
        """Check if the transition is complete."""
        return self.progress >= 1.0

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "start_state": self.start_state.to_dict(),
            "target_state": self.target_state.to_dict(),
            "progress": round(self.progress, 3),
            "duration_ms": self.duration_ms,
            "elapsed_ms": round(self.elapsed_ms, 2),
            "is_complete": self.is_complete,
        }


class EmotionTransitionManager:
    """
    Manages smooth transitions between emotional states.

    Uses PAD-space interpolation with ease-out curves for natural
    emotional transitions. Prevents jarring state changes by gradually
    blending between emotions over time.
    """

    def __init__(
        self,
        default_duration_ms: float = 500.0,
        min_duration_ms: float = 100.0,
        max_duration_ms: float = 2000.0,
    ):
        """
        Initialize the transition manager.

        Args:
            default_duration_ms: Default transition duration
            min_duration_ms: Minimum transition duration
            max_duration_ms: Maximum transition duration
        """
        self.default_duration_ms = default_duration_ms
        self.min_duration_ms = min_duration_ms
        self.max_duration_ms = max_duration_ms

        self._current_state: Optional[EmotionState] = None
        self._transition: Optional[TransitionState] = None

    @property
    def current_state(self) -> EmotionState:
        """Get the current emotion state."""
        if self._current_state is None:
            return EmotionState(CanonicalEmotion.CALM, 0.5)
        return self._current_state

    @property
    def is_transitioning(self) -> bool:
        """Check if a transition is in progress."""
        return self._transition is not None and not self._transition.is_complete

    @property
    def transition_progress(self) -> float:
        """Get the current transition progress (0-1)."""
        if self._transition is None:
            return 1.0
        return self._transition.progress

    def set_state(self, state: EmotionState) -> None:
        """
        Set the current emotion state immediately (no transition).

        Args:
            state: The new emotion state
        """
        self._current_state = state
        self._transition = None

    def transition_to(
        self,
        target: EmotionState,
        duration_ms: Optional[float] = None,
    ) -> TransitionState:
        """
        Start a transition to a new emotion state.

        Args:
            target: Target emotion state
            duration_ms: Optional custom duration

        Returns:
            The transition state object
        """
        if self._current_state is None:
            self._current_state = EmotionState(CanonicalEmotion.CALM, 0.5)

        # Calculate appropriate duration based on emotional distance
        if duration_ms is None:
            duration_ms = self._calculate_duration(self._current_state, target)

        # Clamp duration
        duration_ms = max(self.min_duration_ms, min(self.max_duration_ms, duration_ms))

        self._transition = TransitionState(
            start_state=self._current_state,
            target_state=target,
            duration_ms=duration_ms,
        )

        return self._transition

    def update(self, dt_ms: float) -> EmotionState:
        """
        Update the transition by a time delta.

        Args:
            dt_ms: Time delta in milliseconds

        Returns:
            The current (potentially interpolated) emotion state
        """
        if self._transition is None or self._transition.is_complete:
            return self.current_state

        # Update elapsed time and progress
        self._transition.elapsed_ms += dt_ms
        raw_progress = self._transition.elapsed_ms / self._transition.duration_ms
        self._transition.progress = min(1.0, raw_progress)

        # Apply ease-out curve for natural deceleration
        eased_progress = self._ease_out_cubic(self._transition.progress)

        # Interpolate in PAD space
        interpolated = self._interpolate_pad(
            self._transition.start_state,
            self._transition.target_state,
            eased_progress,
        )

        # Update current state
        self._current_state = interpolated

        # Clear transition if complete
        if self._transition.is_complete:
            self._current_state = self._transition.target_state
            self._transition = None

        return self.current_state

    def get_interpolated_state(self, progress: float) -> EmotionState:
        """
        Get an interpolated state at a specific progress point.

        Useful for previewing transitions without modifying state.

        Args:
            progress: Progress value (0-1)

        Returns:
            Interpolated emotion state
        """
        if self._transition is None:
            return self.current_state

        eased = self._ease_out_cubic(progress)
        return self._interpolate_pad(
            self._transition.start_state,
            self._transition.target_state,
            eased,
        )

    def blend_states(
        self,
        state1: EmotionState,
        state2: EmotionState,
        weight: float = 0.5,
    ) -> EmotionState:
        """
        Blend two emotion states in PAD space.

        Args:
            state1: First emotion state
            state2: Second emotion state
            weight: Weight for state2 (0.0 = state1, 1.0 = state2)

        Returns:
            Blended emotion state
        """
        return self._interpolate_pad(state1, state2, weight)

    def _calculate_duration(self, start: EmotionState, target: EmotionState) -> float:
        """
        Calculate appropriate transition duration based on emotional distance.

        Larger emotional changes take longer to feel natural.
        """
        start_pad = start.pad_vector
        target_pad = EMOTION_TO_PAD[target.emotion].scale(target.intensity)

        distance = start_pad.distance(target_pad)

        # Scale duration based on distance (0 distance = min, max distance ~3.46 = max)
        duration_range = self.max_duration_ms - self.min_duration_ms
        normalized_distance = min(1.0, distance / 2.0)  # Normalize to ~0-1

        return self.min_duration_ms + (duration_range * normalized_distance)

    def _interpolate_pad(
        self,
        start: EmotionState,
        target: EmotionState,
        t: float,
    ) -> EmotionState:
        """
        Interpolate between two emotion states in PAD space.

        Args:
            start: Starting emotion state
            target: Target emotion state
            t: Interpolation factor (0-1)

        Returns:
            Interpolated emotion state
        """
        # Get PAD vectors
        start_pad = start.pad_vector
        target_pad = EMOTION_TO_PAD[target.emotion].scale(target.intensity)

        # Lerp in PAD space
        interpolated_pad = start_pad.lerp(target_pad, t)

        # Find closest discrete emotion
        closest_emotion, confidence = find_closest_emotion(interpolated_pad)

        # Calculate interpolated intensity
        interpolated_intensity = start.intensity + (target.intensity - start.intensity) * t

        # Determine if we should use blended secondary emotion
        if t < 0.5:
            # Still closer to start, start is primary
            return EmotionState(
                emotion=start.emotion,
                intensity=start.intensity * (1 - t) + interpolated_intensity * t,
                secondary_emotion=target.emotion,
                secondary_intensity=target.intensity * t,
            )
        else:
            # Closer to target, target is primary
            return EmotionState(
                emotion=target.emotion,
                intensity=interpolated_intensity,
                secondary_emotion=start.emotion,
                secondary_intensity=start.intensity * (1 - t),
            )

    @staticmethod
    def _ease_out_cubic(t: float) -> float:
        """
        Cubic ease-out function for natural deceleration.

        Starts fast and slows down towards the end.

        Args:
            t: Input value (0-1)

        Returns:
            Eased value (0-1)
        """
        t = max(0.0, min(1.0, t))
        return 1 - pow(1 - t, 3)

    @staticmethod
    def _ease_out_quad(t: float) -> float:
        """
        Quadratic ease-out function (alternative).

        Gentler than cubic.
        """
        t = max(0.0, min(1.0, t))
        return 1 - pow(1 - t, 2)

    @staticmethod
    def _ease_in_out_sine(t: float) -> float:
        """
        Sine ease-in-out function (alternative).

        Smooth acceleration and deceleration.
        """
        t = max(0.0, min(1.0, t))
        return -(math.cos(math.pi * t) - 1) / 2

    def reset(self) -> None:
        """Reset to initial state (calm, no transition)."""
        self._current_state = EmotionState(CanonicalEmotion.CALM, 0.5)
        self._transition = None

    def get_transition_info(self) -> Optional[dict]:
        """Get information about the current transition."""
        if self._transition is None:
            return None
        return self._transition.to_dict()
