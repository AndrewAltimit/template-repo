"""
Cognitive Orchestrator for Dual-Speed Cognitive Architecture.

Coordinates the FastMind (System 1) and SlowMind (System 2) to provide
a unified cognitive processing interface.

Flow:
1. FastMind reacts immediately (<100ms) with filler and emotion
2. If escalation triggered, SlowMind processes in background
3. Active listening behaviors displayed during slow processing
4. Emotion transitions smoothly between fast and slow states
"""

import asyncio
import time
from typing import Any, Awaitable, Callable, Dict, List, Optional

from ..emotions import EmotionState
from .active_listening import ActiveListeningController, BehaviorEvent
from .emotion_transition import EmotionTransitionManager
from .fast_mind import FastMind
from .slow_mind import Reasoner, SlowMind
from .types import CognitiveConfig, CognitiveResult, FastReaction, ListeningBehavior, ProcessingState, SlowSynthesis


class CognitiveOrchestrator:
    """
    Orchestrates dual-speed cognitive processing.

    Provides a unified interface that:
    - Returns fast reactions immediately
    - Runs slow processing in background when needed
    - Manages active listening during slow processing
    - Smoothly transitions emotions between systems
    """

    def __init__(
        self,
        config: Optional[CognitiveConfig] = None,
        pattern_lookup: Optional[Callable[[str], Awaitable[Optional[str]]]] = None,
        pattern_store: Optional[Callable[[str, str], Awaitable[None]]] = None,
    ):
        """
        Initialize the orchestrator.

        Args:
            config: Cognitive configuration
            pattern_lookup: Async function for pattern retrieval
            pattern_store: Async function for pattern storage
        """
        self.config = config or CognitiveConfig()

        # Initialize subsystems
        self._fast_mind = FastMind(config=self.config, pattern_lookup=pattern_lookup)
        self._slow_mind = SlowMind(config=self.config, pattern_store=pattern_store)
        self._emotion_manager = EmotionTransitionManager()
        self._listening_controller = ActiveListeningController(config=self.config)

        # State tracking
        self._current_state = ProcessingState.IDLE
        self._current_result: Optional[CognitiveResult] = None
        self._slow_task: Optional[asyncio.Task[SlowSynthesis]] = None
        self._conversation_history: List[Dict[str, str]] = []

    def set_reasoner(self, reasoner: Reasoner) -> None:
        """
        Set the external reasoner for slow processing.

        Args:
            reasoner: Reasoner implementation (e.g., Claude API wrapper)
        """
        self._slow_mind.set_reasoner(reasoner)

    async def process(
        self,
        input_text: str,
        context: Optional[List[Dict[str, str]]] = None,
        system_prompt: Optional[str] = None,
        wait_for_slow: bool = True,
    ) -> CognitiveResult:
        """
        Process input through the dual-speed cognitive system.

        Args:
            input_text: The input text to process
            context: Optional conversation history override
            system_prompt: Optional system prompt for slow processing
            wait_for_slow: If True, wait for slow processing to complete

        Returns:
            CognitiveResult with fast reaction and optional slow synthesis
        """
        start_time = time.perf_counter()

        # Update state
        self._current_state = ProcessingState.FAST_PROCESSING

        # Check for conversation history
        has_history = bool(context or self._conversation_history)

        # 1. Fast reaction (immediate)
        fast_reaction = await self._fast_mind.react(
            input_text=input_text,
            has_history=has_history,
        )

        self._current_state = ProcessingState.FAST_COMPLETE

        # Initialize result
        listening_behaviors: List[ListeningBehavior] = []

        # 2. Check if slow processing is needed and reasoner is available
        if fast_reaction.should_escalate and self._slow_mind.has_reasoner:
            self._current_state = ProcessingState.SLOW_PROCESSING

            # Start active listening
            if self.config.active_listening_enabled:
                first_behavior = self._listening_controller.start(context_emotion=fast_reaction.emotion.emotion)
                listening_behaviors.append(first_behavior.behavior)

            # Process with slow mind
            if wait_for_slow:
                slow_synthesis = await self._process_slow(
                    input_text=input_text,
                    fast_reaction=fast_reaction,
                    context=context,
                    system_prompt=system_prompt,
                )

                # Collect listening behaviors that occurred
                listening_behaviors.extend([b.behavior for b in self._listening_controller.stop()])

                self._current_state = ProcessingState.SLOW_COMPLETE
            else:
                # Start slow processing in background
                self._slow_task = asyncio.create_task(
                    self._process_slow(
                        input_text=input_text,
                        fast_reaction=fast_reaction,
                        context=context,
                        system_prompt=system_prompt,
                    )
                )
                slow_synthesis = None
        else:
            slow_synthesis = None

        # Calculate total time
        total_time_ms = (time.perf_counter() - start_time) * 1000

        # Build result
        result = CognitiveResult(
            fast_reaction=fast_reaction,
            slow_synthesis=slow_synthesis,
            processing_state=self._current_state,
            listening_behaviors=listening_behaviors,
            total_time_ms=total_time_ms,
            input_text=input_text,
        )

        self._current_result = result

        # Update conversation history
        self._conversation_history.append({"role": "user", "content": input_text})
        if slow_synthesis:
            self._conversation_history.append({"role": "assistant", "content": slow_synthesis.response})
        else:
            self._conversation_history.append({"role": "assistant", "content": fast_reaction.filler_text})

        return result

    async def _process_slow(
        self,
        input_text: str,
        fast_reaction: FastReaction,
        context: Optional[List[Dict[str, str]]] = None,
        system_prompt: Optional[str] = None,
    ) -> SlowSynthesis:
        """Process with slow mind and manage transitions."""
        # Use provided context or fall back to internal history
        effective_context = context or self._conversation_history

        # Get slow synthesis
        slow_synthesis = await self._slow_mind.synthesize(
            input_text=input_text,
            fast_reaction=fast_reaction,
            context=effective_context,
            system_prompt=system_prompt,
        )

        # Transition emotion from fast to slow
        self._emotion_manager.set_state(fast_reaction.emotion)
        self._emotion_manager.transition_to(slow_synthesis.emotion)

        return slow_synthesis

    async def get_slow_result(self, timeout_ms: Optional[float] = None) -> Optional[SlowSynthesis]:
        """
        Wait for and get the slow processing result.

        Use this when process() was called with wait_for_slow=False.

        Args:
            timeout_ms: Optional timeout in milliseconds

        Returns:
            SlowSynthesis if available, None if not started or timed out
        """
        if self._slow_task is None:
            return None

        try:
            if timeout_ms:
                return await asyncio.wait_for(
                    self._slow_task,
                    timeout=timeout_ms / 1000,
                )
            else:
                return await self._slow_task
        except asyncio.TimeoutError:
            return None

    def process_sync(self, input_text: str) -> CognitiveResult:
        """
        Synchronous fast-only processing.

        Returns immediately with fast reaction only.
        Does not support slow processing.

        Args:
            input_text: The input text to process

        Returns:
            CognitiveResult with fast reaction only
        """
        start_time = time.perf_counter()

        fast_reaction = self._fast_mind.react_sync(
            input_text=input_text,
            has_history=bool(self._conversation_history),
        )

        total_time_ms = (time.perf_counter() - start_time) * 1000

        return CognitiveResult(
            fast_reaction=fast_reaction,
            slow_synthesis=None,
            processing_state=ProcessingState.FAST_COMPLETE,
            listening_behaviors=[],
            total_time_ms=total_time_ms,
            input_text=input_text,
        )

    def update_listening(
        self,
        dt_ms: float,
    ) -> Optional[BehaviorEvent]:
        """
        Update active listening state.

        Call this periodically during slow processing to get
        new behaviors to display.

        Args:
            dt_ms: Time delta in milliseconds

        Returns:
            New behavior event if behavior changed
        """
        if not self._listening_controller.is_active:
            return None

        emotion = None
        if self._current_result:
            emotion = self._current_result.fast_reaction.emotion.emotion

        return self._listening_controller.update(dt_ms, emotion)

    def update_emotion(self, dt_ms: float) -> EmotionState:
        """
        Update emotion transition state.

        Call this periodically to get smooth emotion updates.

        Args:
            dt_ms: Time delta in milliseconds

        Returns:
            Current (potentially interpolated) emotion state
        """
        return self._emotion_manager.update(dt_ms)

    @property
    def current_emotion(self) -> EmotionState:
        """Get the current emotion state."""
        return self._emotion_manager.current_state

    @property
    def current_state(self) -> ProcessingState:
        """Get the current processing state."""
        return self._current_state

    @property
    def is_processing_slow(self) -> bool:
        """Check if slow processing is in progress."""
        return self._current_state == ProcessingState.SLOW_PROCESSING

    @property
    def has_reasoner(self) -> bool:
        """Check if a reasoner is configured."""
        return self._slow_mind.has_reasoner

    def add_to_history(self, role: str, content: str) -> None:
        """Add a message to conversation history."""
        self._conversation_history.append({"role": role, "content": content})
        self._slow_mind.add_to_history(role, content)

    def clear_history(self) -> None:
        """Clear conversation history."""
        self._conversation_history.clear()
        self._slow_mind.clear_history()

    def get_history(self) -> List[Dict[str, str]]:
        """Get conversation history."""
        return list(self._conversation_history)

    def get_config(self) -> Dict[str, Any]:
        """Get current configuration."""
        return self.config.to_dict()

    def update_config(self, **kwargs: Any) -> None:
        """Update configuration parameters."""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)

        # Propagate to subsystems
        self._fast_mind.update_config(**kwargs)

    def cancel_slow_processing(self) -> bool:
        """
        Cancel any in-progress slow processing.

        Returns:
            True if there was a task to cancel
        """
        if self._slow_task and not self._slow_task.done():
            self._slow_task.cancel()
            self._current_state = ProcessingState.ABORTED
            self._listening_controller.stop()
            return True
        return False

    def reset(self) -> None:
        """Reset the orchestrator to initial state."""
        self.cancel_slow_processing()
        self._current_state = ProcessingState.IDLE
        self._current_result = None
        self._emotion_manager.reset()
        self._listening_controller.stop()
        # Don't clear history - that should be explicit
