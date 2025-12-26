"""
SlowMind (System 2) for Dual-Speed Cognitive Architecture.

Provides the interface for deep reasoning (2-30s processing time).

Responsibilities:
- Synthesize thoughtful responses using external reasoners
- Detect conversation tone for adaptation
- Generate patterns to cache for future fast retrieval

This module provides the interface; actual reasoning is delegated
to external services (e.g., Claude API).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import time
from typing import Any, Awaitable, Callable, Dict, List, Optional

from ..emotions import infer_emotion
from .types import CognitiveConfig, FastReaction, SlowSynthesis


@dataclass
class ReasonerContext:
    """
    Context provided to the external reasoner.

    Contains all information needed for deep reasoning.
    """

    input_text: str
    fast_reaction: FastReaction
    conversation_history: List[Dict[str, str]] = field(default_factory=list)
    system_prompt: Optional[str] = None
    max_tokens: int = 1024
    temperature: float = 0.7

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "input_text": self.input_text,
            "fast_reaction": self.fast_reaction.to_dict(),
            "conversation_history": self.conversation_history,
            "system_prompt": self.system_prompt,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }


class Reasoner(ABC):
    """
    Abstract base class for external reasoning services.

    Implement this interface to connect SlowMind to different
    reasoning backends (Claude, OpenAI, local models, etc.).
    """

    @abstractmethod
    async def reason(self, context: ReasonerContext) -> str:
        """
        Generate a reasoned response.

        Args:
            context: Full context for reasoning

        Returns:
            The reasoned response text
        """
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Get the name/identifier of this reasoner."""
        ...


class MockReasoner(Reasoner):
    """
    Mock reasoner for testing.

    Returns simple responses without actual reasoning.
    """

    def __init__(self, delay_ms: float = 100.0):
        """
        Initialize mock reasoner.

        Args:
            delay_ms: Simulated processing delay
        """
        self.delay_ms = delay_ms

    async def reason(self, context: ReasonerContext) -> str:
        """Return a mock response after simulated delay."""
        import asyncio

        await asyncio.sleep(self.delay_ms / 1000)
        return f"[Mock response to: {context.input_text[:50]}...]"

    @property
    def model_name(self) -> str:
        return "mock-reasoner"


class CallableReasoner(Reasoner):
    """
    Reasoner that wraps a callable function.

    Useful for quick integration with existing async functions.
    """

    def __init__(
        self,
        reason_fn: Callable[[ReasonerContext], Awaitable[str]],
        name: str = "callable-reasoner",
    ):
        """
        Initialize callable reasoner.

        Args:
            reason_fn: Async function that takes context and returns response
            name: Name for this reasoner
        """
        self._reason_fn = reason_fn
        self._name = name

    async def reason(self, context: ReasonerContext) -> str:
        """Call the wrapped function."""
        return await self._reason_fn(context)

    @property
    def model_name(self) -> str:
        return self._name


# Tone detection keywords
TONE_INDICATORS: Dict[str, List[str]] = {
    "formal": ["please", "kindly", "would you", "could you", "sir", "madam", "respectfully"],
    "casual": ["hey", "yo", "sup", "gonna", "wanna", "gotta", "lol", "lmao", "haha"],
    "urgent": ["asap", "urgent", "immediately", "now", "hurry", "quick", "emergency"],
    "frustrated": ["ugh", "frustrated", "annoying", "not working", "broken", "stupid"],
    "curious": ["wondering", "curious", "interested", "tell me", "what if", "how about"],
    "appreciative": ["thanks", "thank you", "appreciate", "grateful", "awesome", "great job"],
}


class SlowMind:
    """
    System 2 (slow) cognitive processing.

    Provides deep reasoning through external services.
    Processing time: 2-30 seconds.

    Responsibilities:
    - Coordinate with external reasoner
    - Detect conversation tone
    - Generate cacheable patterns
    """

    def __init__(
        self,
        reasoner: Optional[Reasoner] = None,
        config: Optional[CognitiveConfig] = None,
        pattern_store: Optional[Callable[[str, str], Awaitable[None]]] = None,
    ):
        """
        Initialize SlowMind.

        Args:
            reasoner: External reasoning service
            config: Cognitive configuration
            pattern_store: Optional async function to store patterns
        """
        self.config = config or CognitiveConfig()
        self._reasoner = reasoner
        self._pattern_store = pattern_store
        self._conversation_history: List[Dict[str, str]] = []

    def set_reasoner(self, reasoner: Reasoner) -> None:
        """Set the external reasoning service."""
        self._reasoner = reasoner

    def set_pattern_store(self, store_fn: Callable[[str, str], Awaitable[None]]) -> None:
        """Set the pattern storage function."""
        self._pattern_store = store_fn

    async def synthesize(
        self,
        input_text: str,
        fast_reaction: FastReaction,
        context: Optional[List[Dict[str, str]]] = None,
        system_prompt: Optional[str] = None,
    ) -> SlowSynthesis:
        """
        Synthesize a deep response.

        Args:
            input_text: The input text to respond to
            fast_reaction: The fast reaction for context
            context: Optional conversation history
            system_prompt: Optional system prompt override

        Returns:
            SlowSynthesis with response and metadata
        """
        if self._reasoner is None:
            raise RuntimeError("No reasoner configured. Call set_reasoner() first.")

        start_time = time.perf_counter()

        # Build context for reasoner
        reasoner_context = ReasonerContext(
            input_text=input_text,
            fast_reaction=fast_reaction,
            conversation_history=context or self._conversation_history,
            system_prompt=system_prompt,
        )

        # Get response from reasoner
        response = await self._reasoner.reason(reasoner_context)

        # Detect tone from input
        detected_tone = self._detect_tone(input_text)

        # Infer emotion from response
        # infer_emotion returns EmotionState directly
        emotion = infer_emotion(response)

        # Generate pattern for caching
        pattern = self._generate_pattern(input_text, response)

        # Store pattern if store function available
        if self._pattern_store and pattern:
            try:
                await self._pattern_store(input_text, pattern)
            except Exception:
                pass  # Pattern storage is optional

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        return SlowSynthesis(
            response=response,
            emotion=emotion,
            detected_tone=detected_tone,
            pattern_to_cache=pattern,
            processing_time_ms=elapsed_ms,
            model_used=self._reasoner.model_name,
        )

    def _detect_tone(self, text: str) -> Optional[str]:
        """
        Detect the conversational tone from text.

        Args:
            text: Text to analyze

        Returns:
            Detected tone or None
        """
        text_lower = text.lower()

        tone_scores: Dict[str, int] = {}
        for tone, indicators in TONE_INDICATORS.items():
            score = sum(1 for ind in indicators if ind in text_lower)
            if score > 0:
                tone_scores[tone] = score

        if not tone_scores:
            return None

        # Return the tone with highest score
        return max(tone_scores, key=lambda k: tone_scores[k])

    def _generate_pattern(self, input_text: str, response: str) -> Optional[str]:
        """
        Generate a cacheable pattern from the input/response pair.

        Args:
            input_text: Original input
            response: Generated response

        Returns:
            Pattern string for caching, or None
        """
        # Simple pattern: first sentence of response
        # More sophisticated approaches could use semantic hashing
        if not response:
            return None

        sentences = response.split(".")
        if sentences:
            pattern = sentences[0].strip()
            if len(pattern) > 20:  # Only cache substantial patterns
                return pattern

        return None

    def add_to_history(self, role: str, content: str) -> None:
        """
        Add a message to conversation history.

        Args:
            role: Message role (user, assistant)
            content: Message content
        """
        self._conversation_history.append({"role": role, "content": content})

        # Keep history bounded
        max_history = 20
        if len(self._conversation_history) > max_history:
            self._conversation_history = self._conversation_history[-max_history:]

    def clear_history(self) -> None:
        """Clear conversation history."""
        self._conversation_history.clear()

    def get_history(self) -> List[Dict[str, str]]:
        """Get conversation history."""
        return list(self._conversation_history)

    @property
    def has_reasoner(self) -> bool:
        """Check if a reasoner is configured."""
        return self._reasoner is not None

    @property
    def reasoner_name(self) -> str:
        """Get the name of the current reasoner."""
        if self._reasoner is None:
            return "none"
        return self._reasoner.model_name
