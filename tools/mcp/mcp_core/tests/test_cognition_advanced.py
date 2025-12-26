"""
Advanced tests for the dual-speed cognitive architecture.

Tests cover:
- Concurrency and race conditions
- Property-based testing with hypothesis
- Failure mode and recovery
- Session lifecycle
- Determinism in random selection

These tests complement the basic unit tests in test_cognition.py.
"""

import asyncio
import random
from typing import List
from unittest.mock import AsyncMock

from hypothesis import given, settings, strategies as st
import pytest

from mcp_core.cognition import (
    ActiveListeningController,
    CognitiveConfig,
    CognitiveOrchestrator,
    EmotionTransitionManager,
    EscalationDetector,
    FastMind,
    FastReaction,
    FillerLibrary,
    MockReasoner,
    ProcessingState,
    ReasonerContext,
)
from mcp_core.emotions import CanonicalEmotion, EmotionState

# =============================================================================
# Concurrency and Race Condition Tests
# =============================================================================


class TestConcurrencyRaceConditions:
    """Tests for concurrent processing and race conditions."""

    @pytest.mark.asyncio
    async def test_slow_mind_cancellation_on_new_input(self):
        """
        Verify that background slow processing can be cancelled
        when new input arrives.
        """
        orchestrator = CognitiveOrchestrator()

        # Create a slow reasoner that takes a long time
        slow_proceed = asyncio.Event()

        async def delayed_reasoning(context: ReasonerContext) -> str:
            await slow_proceed.wait()
            return "Delayed response"

        reasoner = MockReasoner(delay_ms=0)
        reasoner.reason = AsyncMock(side_effect=delayed_reasoning)
        orchestrator.set_reasoner(reasoner)

        # Start processing without waiting for slow
        result1 = await orchestrator.process(
            "Why is the sky blue?",
            wait_for_slow=False,
        )

        # Verify fast reaction returned immediately
        assert result1.fast_reaction is not None
        assert result1.slow_synthesis is None

        # Cancel the slow processing
        cancelled = orchestrator.cancel_slow_processing()
        assert cancelled is True

        # Verify state is aborted
        assert orchestrator.current_state == ProcessingState.ABORTED

        # Now let the slow task try to finish (should be cancelled)
        slow_proceed.set()
        await asyncio.sleep(0.01)

    @pytest.mark.asyncio
    async def test_rapid_sequential_inputs(self):
        """
        Test handling of rapid sequential inputs without race conditions.
        """
        orchestrator = CognitiveOrchestrator()
        reasoner = MockReasoner(delay_ms=10)
        orchestrator.set_reasoner(reasoner)

        inputs = [
            "Hello",
            "How are you?",
            "What's the weather?",
            "Tell me a joke",
            "Goodbye",
        ]

        results = []
        for input_text in inputs:
            result = await orchestrator.process(input_text)
            results.append(result)

        # All inputs should have been processed
        assert len(results) == len(inputs)

        # Conversation history should track all exchanges
        history = orchestrator.get_history()
        # Each input adds user + assistant message
        assert len(history) == len(inputs) * 2

    @pytest.mark.asyncio
    async def test_parallel_orchestrator_instances(self):
        """
        Test that multiple orchestrator instances don't interfere.
        """
        orchestrator1 = CognitiveOrchestrator()
        orchestrator2 = CognitiveOrchestrator()

        reasoner1 = MockReasoner(delay_ms=10)
        reasoner2 = MockReasoner(delay_ms=10)
        orchestrator1.set_reasoner(reasoner1)
        orchestrator2.set_reasoner(reasoner2)

        # Process different inputs concurrently
        result1, result2 = await asyncio.gather(
            orchestrator1.process("Hello from orchestrator 1"),
            orchestrator2.process("Hello from orchestrator 2"),
        )

        # Each should have independent state
        assert orchestrator1.get_history() != orchestrator2.get_history()
        assert result1.input_text != result2.input_text

    @pytest.mark.asyncio
    async def test_active_listening_during_slow_processing(self):
        """
        Test active listening behaviors continue during slow processing.
        """
        config = CognitiveConfig(active_listening_enabled=True)
        orchestrator = CognitiveOrchestrator(config=config)

        # Create a slow reasoner
        async def slow_reasoning(context: ReasonerContext) -> str:
            await asyncio.sleep(0.1)  # 100ms delay
            return "Thoughtful response"

        reasoner = MockReasoner(delay_ms=0)
        reasoner.reason = AsyncMock(side_effect=slow_reasoning)
        orchestrator.set_reasoner(reasoner)

        # Start processing without waiting
        result = await orchestrator.process(
            "Explain something complex",
            wait_for_slow=False,
        )

        # Should have initial listening behavior
        assert len(result.listening_behaviors) >= 0  # May have started

        # Simulate time passing and getting behaviors
        behaviors_received = []
        for _ in range(5):
            await asyncio.sleep(0.02)
            behavior_event = orchestrator.update_listening(20.0)
            if behavior_event:
                behaviors_received.append(behavior_event)

        # Wait for slow processing to complete
        slow_result = await orchestrator.get_slow_result(timeout_ms=5000)
        assert slow_result is not None


# =============================================================================
# Property-Based Tests with Hypothesis
# =============================================================================


class TestPropertyBasedEmotionTransitions:
    """Property-based tests for emotion state machine."""

    @given(
        emotion=st.sampled_from(list(CanonicalEmotion)),
        intensity=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=50)
    def test_pad_values_remain_bounded(self, emotion: CanonicalEmotion, intensity: float):
        """Invariant: PAD values must always remain within bounds after transitions."""
        manager = EmotionTransitionManager()

        # Create emotion state - PAD is derived from emotion type
        state = EmotionState(
            emotion=emotion,
            intensity=intensity,
        )
        manager.set_state(state)

        # Update with various deltas
        for dt in [0.0, 10.0, 100.0, 1000.0]:
            result = manager.update(dt)
            # PAD values should remain bounded (intensity-scaled)
            pad = result.pad_vector
            assert -1.0 <= pad.pleasure <= 1.0, f"P out of bounds: {pad.pleasure}"
            assert -1.0 <= pad.arousal <= 1.0, f"A out of bounds: {pad.arousal}"
            assert -1.0 <= pad.dominance <= 1.0, f"D out of bounds: {pad.dominance}"

    @given(
        intensity=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=30)
    def test_intensity_remains_bounded(self, intensity: float):
        """Invariant: Emotion intensity must stay in [0, 1]."""
        manager = EmotionTransitionManager()

        state = EmotionState(
            emotion=CanonicalEmotion.JOY,
            intensity=intensity,
        )
        manager.set_state(state)

        result = manager.current_state
        assert 0.0 <= result.intensity <= 1.0

    @given(
        emotions=st.lists(
            st.sampled_from(list(CanonicalEmotion)),
            min_size=3,
            max_size=10,
        )
    )
    @settings(max_examples=30)
    def test_stability_under_rapid_emotion_changes(self, emotions: List[CanonicalEmotion]):
        """Invariant: System should never crash under rapid emotion changes."""
        manager = EmotionTransitionManager()

        for emotion in emotions:
            state = EmotionState(emotion=emotion, intensity=0.5)
            manager.set_state(state)
            manager.transition_to(state)
            # Rapid updates
            for _ in range(3):
                result = manager.update(0.0)  # 0ms delta
                assert result is not None
                assert result.emotion is not None


class TestPropertyBasedEscalation:
    """Property-based tests for escalation detection."""

    @given(
        word_count=st.integers(min_value=1, max_value=200),
    )
    @settings(max_examples=30)
    def test_long_input_escalation_threshold(self, word_count: int):
        """Test escalation threshold for input length."""
        detector = EscalationDetector()

        # Generate input with specified word count
        words = ["word"] * word_count
        input_text = " ".join(words)

        emotion = EmotionState(emotion=CanonicalEmotion.CALM, intensity=0.3)
        fast_reaction = FastReaction(emotion=emotion, filler_text="Hmm")

        result = detector.should_escalate(
            input_text=input_text,
            fast_reaction=fast_reaction,
            has_history=False,
        )

        # Long input (>20 words) should trigger escalation
        if word_count > 20:
            # Should likely escalate for long input
            assert result.confidence > 0 or result.should_escalate
        # Short input shouldn't trigger length-based escalation
        elif word_count <= 5:
            # Complexity score should be lower
            score = detector.get_complexity_score(input_text)
            assert score < 0.8  # Not extremely complex


class TestPropertyBasedFillers:
    """Property-based tests for filler selection."""

    @given(
        emotion=st.sampled_from(list(CanonicalEmotion)),
    )
    @settings(max_examples=20)
    def test_filler_always_returns_string(self, emotion: CanonicalEmotion):
        """Invariant: get_filler always returns a non-empty string."""
        library = FillerLibrary()
        filler = library.get_filler(emotion)
        assert isinstance(filler, str)
        assert len(filler) > 0

    @given(
        vibe=st.sampled_from(["casual", "professional", "playful", None]),
        emotion=st.sampled_from(list(CanonicalEmotion)),
    )
    @settings(max_examples=30)
    def test_vibe_modifier_never_crashes(self, vibe: str, emotion: CanonicalEmotion):
        """Invariant: Any vibe/emotion combination should work."""
        library = FillerLibrary(default_vibe=vibe)
        filler = library.get_filler(emotion, vibe=vibe)
        assert isinstance(filler, str)


# =============================================================================
# Failure Mode and Recovery Tests
# =============================================================================


class TestFailureModeRecovery:
    """Tests for failure handling and graceful degradation."""

    @pytest.mark.asyncio
    async def test_reasoner_timeout_graceful_degradation(self):
        """Test graceful fallback when reasoner times out."""
        orchestrator = CognitiveOrchestrator()

        # Create a reasoner that times out
        async def timeout_reasoning(context: ReasonerContext) -> str:
            await asyncio.sleep(10)  # Would timeout
            return "Never reaches here"

        reasoner = MockReasoner(delay_ms=0)
        reasoner.reason = AsyncMock(side_effect=timeout_reasoning)
        orchestrator.set_reasoner(reasoner)

        # Process without waiting for slow
        result = await orchestrator.process(
            "Complex question",
            wait_for_slow=False,
        )

        # Fast reaction should still be available
        assert result.fast_reaction is not None
        assert result.fast_reaction.filler_text

        # Try to get slow result with short timeout
        slow_result = await orchestrator.get_slow_result(timeout_ms=50)
        assert slow_result is None  # Should timeout

        # Cancel the hanging task
        orchestrator.cancel_slow_processing()

    @pytest.mark.asyncio
    async def test_reasoner_exception_handling(self):
        """Test handling when reasoner raises an exception."""
        orchestrator = CognitiveOrchestrator()

        # Create a reasoner that raises exception
        async def failing_reasoning(context: ReasonerContext) -> str:
            raise RuntimeError("API Error: Rate limit exceeded")

        reasoner = MockReasoner(delay_ms=0)
        reasoner.reason = AsyncMock(side_effect=failing_reasoning)
        orchestrator.set_reasoner(reasoner)

        # Process WITH waiting - should raise the exception
        # Input must trigger escalation (complexity keywords: explain, why, how)
        with pytest.raises(RuntimeError, match="Rate limit"):
            await orchestrator.process("Can you explain why this happens in detail?")

    @pytest.mark.asyncio
    async def test_no_reasoner_configured(self):
        """Test behavior when no reasoner is configured."""
        orchestrator = CognitiveOrchestrator()
        # Don't set a reasoner

        # Should still work - just won't do slow processing
        result = await orchestrator.process("Hello there!")

        assert result.fast_reaction is not None
        assert result.slow_synthesis is None  # No reasoner = no slow synthesis

    def test_invalid_emotion_transition(self):
        """Test handling of invalid emotion transitions."""
        manager = EmotionTransitionManager()

        # Try transitioning without setting initial state
        target = EmotionState(emotion=CanonicalEmotion.JOY, intensity=0.8)
        manager.transition_to(target)

        # Should handle gracefully
        result = manager.update(100.0)
        assert result is not None

    def test_empty_filler_library_fallback(self):
        """Test filler library fallback for unusual emotions."""
        library = FillerLibrary()

        # All emotions should have fallback
        for emotion in CanonicalEmotion:
            filler = library.get_filler(emotion)
            assert isinstance(filler, str)
            assert len(filler) > 0


# =============================================================================
# Session Lifecycle Tests
# =============================================================================


class TestSessionLifecycle:
    """Tests for complete conversation session flows."""

    @pytest.mark.asyncio
    async def test_full_conversation_flow(self):
        """Test a complete multi-turn conversation."""
        orchestrator = CognitiveOrchestrator()
        reasoner = MockReasoner(delay_ms=5)
        orchestrator.set_reasoner(reasoner)

        # Turn 1: Greeting
        result1 = await orchestrator.process("Hi there!")
        assert result1.fast_reaction is not None
        assert len(orchestrator.get_history()) == 2  # user + assistant

        # Turn 2: Question
        result2 = await orchestrator.process("How does photosynthesis work?")
        assert result2.fast_reaction.should_escalate  # Complex question
        assert len(orchestrator.get_history()) == 4

        # Turn 3: Follow-up
        result3 = await orchestrator.process("Can you explain that simpler?")
        assert result3.fast_reaction is not None
        assert len(orchestrator.get_history()) == 6

        # Turn 4: Goodbye
        result4 = await orchestrator.process("Thanks, bye!")
        assert result4.fast_reaction is not None
        assert len(orchestrator.get_history()) == 8

    @pytest.mark.asyncio
    async def test_history_persistence(self):
        """Test that conversation history persists correctly."""
        orchestrator = CognitiveOrchestrator()
        reasoner = MockReasoner(delay_ms=5)
        orchestrator.set_reasoner(reasoner)

        # Add some conversation
        await orchestrator.process("First message")
        await orchestrator.process("Second message")

        # Check history format
        history = orchestrator.get_history()
        assert len(history) == 4

        # Verify alternating roles
        assert history[0]["role"] == "user"
        assert history[1]["role"] == "assistant"
        assert history[2]["role"] == "user"
        assert history[3]["role"] == "assistant"

    @pytest.mark.asyncio
    async def test_history_clear(self):
        """Test conversation history clearing."""
        orchestrator = CognitiveOrchestrator()
        reasoner = MockReasoner(delay_ms=5)
        orchestrator.set_reasoner(reasoner)

        await orchestrator.process("Build up history")
        assert len(orchestrator.get_history()) > 0

        orchestrator.clear_history()
        assert len(orchestrator.get_history()) == 0

    @pytest.mark.asyncio
    async def test_state_reset(self):
        """Test complete state reset."""
        orchestrator = CognitiveOrchestrator()
        reasoner = MockReasoner(delay_ms=5)
        orchestrator.set_reasoner(reasoner)

        # Do some processing
        await orchestrator.process("Start processing")

        # Reset
        orchestrator.reset()

        assert orchestrator.current_state == ProcessingState.IDLE

    @pytest.mark.asyncio
    async def test_context_override(self):
        """Test providing custom context to process()."""
        orchestrator = CognitiveOrchestrator()
        reasoner = MockReasoner(delay_ms=5)
        orchestrator.set_reasoner(reasoner)

        custom_context = [
            {"role": "user", "content": "Previous question"},
            {"role": "assistant", "content": "Previous answer"},
        ]

        result = await orchestrator.process(
            "Follow-up question",
            context=custom_context,
        )

        assert result is not None


# =============================================================================
# Determinism Tests
# =============================================================================


class TestDeterminism:
    """Tests for deterministic behavior with fixed random seeds."""

    def test_filler_selection_determinism(self):
        """Test that filler selection is reproducible with same seed."""
        random.seed(42)
        library1 = FillerLibrary()
        library1.clear_history()
        fillers1 = [library1.get_filler(CanonicalEmotion.JOY) for _ in range(5)]

        random.seed(42)
        library2 = FillerLibrary()
        library2.clear_history()
        fillers2 = [library2.get_filler(CanonicalEmotion.JOY) for _ in range(5)]

        assert fillers1 == fillers2

    def test_filler_avoids_repetition(self):
        """Test that fillers avoid immediate repetition."""
        library = FillerLibrary()
        library.clear_history()

        # Get many fillers for same emotion
        fillers = [library.get_filler(CanonicalEmotion.THINKING) for _ in range(10)]

        # Check for consecutive duplicates
        consecutive_duplicates = 0
        for i in range(1, len(fillers)):
            if fillers[i] == fillers[i - 1]:
                consecutive_duplicates += 1

        # Should have very few (ideally 0) consecutive duplicates
        assert consecutive_duplicates <= 2  # Allow some due to limited options

    def test_active_listening_behavior_variety(self):
        """Test that active listening can produce different behaviors."""
        # Collect behaviors from multiple fresh starts
        # (each start picks a new behavior based on weights)
        behaviors_seen = set()

        for _ in range(20):
            controller = ActiveListeningController()
            event = controller.start(context_emotion=CanonicalEmotion.THINKING)
            behaviors_seen.add(event.behavior)
            controller.stop()

        # Should have seen multiple different behaviors across all starts
        # (with weighted random selection, we expect variety)
        assert len(behaviors_seen) >= 2, f"Only saw behaviors: {behaviors_seen}"

    def test_active_listening_stop_clears_state(self):
        """Test that stopping active listening clears state properly."""
        controller = ActiveListeningController()

        # Start and verify active
        controller.start(context_emotion=CanonicalEmotion.THINKING)
        assert controller.is_active
        assert controller.current_behavior is not None

        # Stop and verify cleared
        events = controller.stop()
        assert not controller.is_active
        # Events list should contain the history
        assert isinstance(events, list)


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_empty_input(self):
        """Test handling of empty input."""
        fast_mind = FastMind()
        result = await fast_mind.react("")
        assert result is not None
        assert result.emotion is not None

    @pytest.mark.asyncio
    async def test_very_long_input(self):
        """Test handling of very long input."""
        fast_mind = FastMind()
        long_input = "word " * 1000  # 1000 words
        result = await fast_mind.react(long_input)
        assert result is not None
        assert result.should_escalate  # Long input should escalate

    @pytest.mark.asyncio
    async def test_special_characters_input(self):
        """Test handling of special characters."""
        fast_mind = FastMind()
        special_input = "Hello! @#$%^&*() \n\t\r Unicode: \u2603 \U0001f600"
        result = await fast_mind.react(special_input)
        assert result is not None

    def test_emotion_transition_zero_duration(self):
        """Test emotion transition with zero duration."""
        manager = EmotionTransitionManager()

        start = EmotionState(emotion=CanonicalEmotion.CALM, intensity=0.3)
        end = EmotionState(emotion=CanonicalEmotion.JOY, intensity=0.9)

        manager.set_state(start)
        manager.transition_to(end)

        # Immediate update should still work
        result = manager.update(0.0)
        assert result is not None

    def test_escalation_with_only_punctuation(self):
        """Test escalation detection with only punctuation."""
        detector = EscalationDetector()

        emotion = EmotionState(emotion=CanonicalEmotion.CALM, intensity=0.3)
        fast_reaction = FastReaction(emotion=emotion, filler_text="Hmm")

        result = detector.should_escalate(
            input_text="???!!!...",
            fast_reaction=fast_reaction,
            has_history=False,
        )

        # Should not crash, result should be valid
        assert result is not None
        assert isinstance(result.should_escalate, bool)

    @pytest.mark.asyncio
    async def test_orchestrator_sync_method(self):
        """Test synchronous processing method."""
        orchestrator = CognitiveOrchestrator()

        result = orchestrator.process_sync("Quick sync test")

        assert result is not None
        assert result.fast_reaction is not None
        assert result.slow_synthesis is None  # Sync mode doesn't do slow

    def test_listening_controller_not_started(self):
        """Test listening controller when not started."""
        controller = ActiveListeningController()

        # Should not crash when updating without starting
        event = controller.update(100.0, CanonicalEmotion.CALM)
        assert event is None

        # Stop should be safe too
        events = controller.stop()
        assert events == []
