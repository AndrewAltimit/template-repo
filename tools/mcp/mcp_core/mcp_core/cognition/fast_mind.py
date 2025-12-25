"""
FastMind (System 1) for Dual-Speed Cognitive Architecture.

Implements immediate reactions in <100ms with zero external dependencies.

Responsibilities:
- Emotion inference from input text
- Filler generation for active listening
- Escalation detection (defer to slow system)
- Pattern lookup from memory (optional)

Target latency: <100ms total
"""

import time
from typing import Any, Awaitable, Callable, Dict, Optional

from ..emotions import CanonicalEmotion, EmotionState, infer_emotion
from .escalation import EscalationDetector
from .fillers import FillerLibrary
from .types import CognitiveConfig, FastReaction


class FastMind:
    """
    System 1 (fast) cognitive processing.

    Provides immediate reactions to input with:
    - Emotion inference
    - Non-committal filler responses
    - Escalation detection

    All processing is local with zero network dependencies
    to achieve <100ms latency.
    """

    def __init__(
        self,
        config: Optional[CognitiveConfig] = None,
        pattern_lookup: Optional[Callable[[str], Awaitable[Optional[str]]]] = None,
    ):
        """
        Initialize FastMind.

        Args:
            config: Configuration for cognitive processing
            pattern_lookup: Optional async function to lookup cached patterns
        """
        self.config = config or CognitiveConfig()
        self._pattern_lookup = pattern_lookup

        self._filler_library = FillerLibrary(default_vibe=self.config.default_filler_vibe)
        self._escalation_detector = EscalationDetector(config=self.config)

    async def react(
        self,
        input_text: str,
        has_history: bool = False,
    ) -> FastReaction:
        """
        Generate an immediate reaction to input.

        Target latency: <100ms

        Args:
            input_text: The input text to react to
            has_history: Whether there's conversation history

        Returns:
            FastReaction with emotion, filler, and escalation decision
        """
        start_time = time.perf_counter()

        # 1. Infer emotion from text (~10ms)
        # infer_emotion returns EmotionState directly
        emotion = infer_emotion(input_text)

        # 2. Lookup cached pattern if available (~10ms or 0ms if no lookup)
        cached_pattern: Optional[str] = None
        if self._pattern_lookup:
            try:
                cached_pattern = await self._pattern_lookup(input_text)
            except Exception:
                # Pattern lookup is optional, don't fail on errors
                pass

        # 3. Get appropriate filler (<1ms)
        filler_text = self._filler_library.get_filler(
            emotion=emotion.emotion,
            vibe=self.config.default_filler_vibe,
        )

        # 4. Check for escalation (~5ms)
        # Build a preliminary fast reaction for escalation check
        preliminary = FastReaction(
            emotion=emotion,
            filler_text=filler_text,
            cached_pattern=cached_pattern,
        )
        escalation = self._escalation_detector.should_escalate(
            input_text=input_text,
            fast_reaction=preliminary,
            has_history=has_history,
        )

        # Calculate processing time
        elapsed_ms = (time.perf_counter() - start_time) * 1000

        return FastReaction(
            emotion=emotion,
            filler_text=filler_text,
            should_escalate=escalation.should_escalate,
            escalation=escalation,
            cached_pattern=cached_pattern,
            processing_time_ms=elapsed_ms,
        )

    def react_sync(
        self,
        input_text: str,
        has_history: bool = False,
    ) -> FastReaction:
        """
        Synchronous version of react (without pattern lookup).

        Useful when async is not available or pattern lookup is not needed.

        Args:
            input_text: The input text to react to
            has_history: Whether there's conversation history

        Returns:
            FastReaction with emotion, filler, and escalation decision
        """
        start_time = time.perf_counter()

        # 1. Infer emotion from text
        # infer_emotion returns EmotionState directly
        emotion = infer_emotion(input_text)

        # 2. Get appropriate filler
        filler_text = self._filler_library.get_filler(
            emotion=emotion.emotion,
            vibe=self.config.default_filler_vibe,
        )

        # 3. Check for escalation (no cached pattern in sync mode)
        preliminary = FastReaction(
            emotion=emotion,
            filler_text=filler_text,
            cached_pattern=None,
        )
        escalation = self._escalation_detector.should_escalate(
            input_text=input_text,
            fast_reaction=preliminary,
            has_history=has_history,
        )

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        return FastReaction(
            emotion=emotion,
            filler_text=filler_text,
            should_escalate=escalation.should_escalate,
            escalation=escalation,
            cached_pattern=None,
            processing_time_ms=elapsed_ms,
        )

    def get_filler_for_emotion(self, emotion: CanonicalEmotion) -> str:
        """Get a filler phrase for a specific emotion."""
        return self._filler_library.get_filler(emotion)

    def check_escalation(
        self,
        input_text: str,
        emotion: Optional[EmotionState] = None,
        has_history: bool = False,
    ) -> bool:
        """
        Quick check if input should be escalated to slow system.

        Args:
            input_text: The input to check
            emotion: Optional pre-computed emotion state
            has_history: Whether there's conversation history

        Returns:
            True if should escalate
        """
        if emotion is None:
            # infer_emotion returns EmotionState directly
            emotion = infer_emotion(input_text)

        fast_reaction = FastReaction(
            emotion=emotion,
            filler_text="",
            cached_pattern=None,
        )

        escalation = self._escalation_detector.should_escalate(
            input_text=input_text,
            fast_reaction=fast_reaction,
            has_history=has_history,
        )

        return escalation.should_escalate

    def get_complexity_score(self, input_text: str) -> float:
        """
        Get a complexity score for the input.

        Useful for debugging and tuning.

        Args:
            input_text: The input to score

        Returns:
            Score from 0 (simple) to 1 (complex)
        """
        return self._escalation_detector.get_complexity_score(input_text)

    def set_pattern_lookup(
        self,
        lookup_fn: Callable[[str], Awaitable[Optional[str]]],
    ) -> None:
        """
        Set the pattern lookup function.

        Args:
            lookup_fn: Async function that takes input text and returns
                      a cached pattern if available
        """
        self._pattern_lookup = lookup_fn

    def update_config(self, **kwargs: Any) -> None:
        """
        Update configuration parameters.

        Args:
            **kwargs: Configuration parameters to update
        """
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)

        # Recreate filler library if vibe changed
        if "default_filler_vibe" in kwargs:
            self._filler_library = FillerLibrary(default_vibe=kwargs["default_filler_vibe"])

        # Recreate escalation detector with new config
        self._escalation_detector = EscalationDetector(config=self.config)

    def get_config(self) -> Dict[str, Any]:
        """Get current configuration as dict."""
        return self.config.to_dict()
