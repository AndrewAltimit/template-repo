"""
Escalation Detection for Dual-Speed Cognitive Architecture.

Determines when to defer from fast (System 1) to slow (System 2) processing.

Triggers for escalation:
- Complexity keywords: "explain", "why", "how", etc.
- Long input: Input exceeds word threshold
- Emotional spike: High emotional intensity detected
- Follow-up references: References to previous context
- Uncertainty: Low confidence in fast response
"""

import re
from typing import List, Optional, Set

from ..emotions import EmotionState
from .types import CognitiveConfig, EscalationReason, EscalationResult, FastReaction

# Keywords that suggest complex reasoning is needed
COMPLEXITY_KEYWORDS: Set[str] = {
    # Explanation requests
    "explain",
    "why",
    "how",
    "what",
    "when",
    "where",
    "which",
    # Deep thinking indicators
    "analyze",
    "compare",
    "contrast",
    "evaluate",
    "describe",
    "elaborate",
    "clarify",
    "justify",
    "reason",
    # Problem-solving
    "solve",
    "fix",
    "debug",
    "troubleshoot",
    "investigate",
    "diagnose",
    # Creative thinking
    "design",
    "create",
    "implement",
    "develop",
    "architect",
    "plan",
    "propose",
    "suggest",
}

# Keywords for follow-up detection
FOLLOW_UP_KEYWORDS: Set[str] = {
    "that",
    "this",
    "it",
    "those",
    "these",
    "previous",
    "earlier",
    "before",
    "last",
    "above",
    "mentioned",
    "said",
    "discussed",
    "you said",
    "you mentioned",
    "as we",
    "like we",
    "continue",
    "more about",
    "going back",
}

# Explicit deep thinking requests
EXPLICIT_THINKING_PATTERNS: List[str] = [
    r"think\s+(about|through|over)",
    r"take\s+your\s+time",
    r"no\s+rush",
    r"carefully\s+consider",
    r"deep\s+dive",
    r"thorough(ly)?",
    r"in\s+depth",
    r"detailed?\s+(analysis|explanation|review)",
]


class EscalationDetector:
    """
    Detects when to escalate from fast to slow processing.

    Uses multiple heuristics to determine if deep reasoning is needed:
    - Keyword matching for complexity indicators
    - Input length analysis
    - Emotional intensity thresholds
    - Follow-up reference detection
    """

    def __init__(self, config: Optional[CognitiveConfig] = None):
        """
        Initialize the escalation detector.

        Args:
            config: Configuration for escalation thresholds
        """
        self.config = config or CognitiveConfig()
        self._compiled_patterns = [re.compile(p, re.IGNORECASE) for p in EXPLICIT_THINKING_PATTERNS]

    def should_escalate(
        self,
        input_text: str,
        fast_reaction: Optional[FastReaction] = None,
        has_history: bool = False,
    ) -> EscalationResult:
        """
        Determine if processing should be escalated to slow system.

        Args:
            input_text: The input text to analyze
            fast_reaction: Optional fast reaction to consider
            has_history: Whether there's conversation history

        Returns:
            EscalationResult with decision and reason
        """
        # Check each escalation trigger in priority order
        reasons: List[tuple[EscalationReason, float, str]] = []

        # 1. Check for explicit deep thinking requests
        explicit = self._check_explicit_request(input_text)
        if explicit:
            reasons.append(explicit)

        # 2. Check for complexity keywords
        complexity = self._check_complexity_keywords(input_text)
        if complexity:
            reasons.append(complexity)

        # 3. Check input length
        length = self._check_input_length(input_text)
        if length:
            reasons.append(length)

        # 4. Check for emotional spike
        if fast_reaction:
            emotional = self._check_emotional_spike(fast_reaction.emotion)
            if emotional:
                reasons.append(emotional)

        # 5. Check for follow-up references
        if has_history:
            follow_up = self._check_follow_up_reference(input_text)
            if follow_up:
                reasons.append(follow_up)

        # 6. Check for no cached pattern (if provided)
        if fast_reaction and fast_reaction.cached_pattern is None and self.config.pattern_cache_enabled:
            # Only add if other signals suggest escalation might be warranted
            if reasons:
                reasons.append(
                    (
                        EscalationReason.NO_CACHED_PATTERN,
                        0.3,
                        "No cached pattern available for similar inputs",
                    )
                )

        # Determine final decision
        if not reasons:
            return EscalationResult(should_escalate=False)

        # Use the highest confidence reason
        best_reason = max(reasons, key=lambda x: x[1])
        reason, confidence, details = best_reason

        return EscalationResult(
            should_escalate=True,
            reason=reason,
            confidence=confidence,
            details=details,
        )

    def _check_explicit_request(self, text: str) -> Optional[tuple[EscalationReason, float, str]]:
        """Check for explicit requests for deep thinking."""
        text_lower = text.lower()

        for pattern in self._compiled_patterns:
            if pattern.search(text_lower):
                return (
                    EscalationReason.EXPLICIT_REQUEST,
                    0.95,
                    f"Explicit thinking request detected: {pattern.pattern}",
                )

        return None

    def _check_complexity_keywords(self, text: str) -> Optional[tuple[EscalationReason, float, str]]:
        """Check for complexity-indicating keywords."""
        words = set(re.findall(r"\b\w+\b", text.lower()))
        matches = words & COMPLEXITY_KEYWORDS

        if matches:
            # More matches = higher confidence
            confidence = min(0.9, 0.5 + len(matches) * 0.1)
            return (
                EscalationReason.COMPLEXITY_KEYWORDS,
                confidence,
                f"Complexity keywords found: {', '.join(sorted(matches)[:3])}",
            )

        return None

    def _check_input_length(self, text: str) -> Optional[tuple[EscalationReason, float, str]]:
        """Check if input exceeds word threshold."""
        word_count = len(text.split())

        if word_count > self.config.escalation_word_threshold:
            # Confidence scales with how much over threshold
            overage = word_count - self.config.escalation_word_threshold
            confidence = min(0.9, 0.6 + overage * 0.02)
            return (
                EscalationReason.LONG_INPUT,
                confidence,
                f"Input has {word_count} words (threshold: {self.config.escalation_word_threshold})",
            )

        return None

    def _check_emotional_spike(self, emotion: EmotionState) -> Optional[tuple[EscalationReason, float, str]]:
        """Check for high emotional intensity."""
        if emotion.intensity > self.config.escalation_emotional_threshold:
            return (
                EscalationReason.EMOTIONAL_SPIKE,
                0.7,
                f"High emotional intensity: {emotion.emotion.value} at {emotion.intensity:.2f}",
            )

        return None

    def _check_follow_up_reference(self, text: str) -> Optional[tuple[EscalationReason, float, str]]:
        """Check for references to previous context."""
        text_lower = text.lower()

        # Check for follow-up keywords/phrases
        matches = []
        for keyword in FOLLOW_UP_KEYWORDS:
            if keyword in text_lower:
                matches.append(keyword)

        if matches:
            confidence = min(0.8, 0.5 + len(matches) * 0.1)
            return (
                EscalationReason.FOLLOW_UP_REFERENCE,
                confidence,
                f"Follow-up references found: {', '.join(matches[:3])}",
            )

        return None

    def get_complexity_score(self, text: str) -> float:
        """
        Calculate a complexity score for the input (0-1).

        Useful for debugging and tuning escalation thresholds.

        Args:
            text: Input text to analyze

        Returns:
            Complexity score from 0 (simple) to 1 (complex)
        """
        score = 0.0

        # Word count contribution
        word_count = len(text.split())
        score += min(0.3, word_count / 100)

        # Complexity keywords contribution
        words = set(re.findall(r"\b\w+\b", text.lower()))
        keyword_matches = len(words & COMPLEXITY_KEYWORDS)
        score += min(0.3, keyword_matches * 0.1)

        # Follow-up references contribution
        text_lower = text.lower()
        follow_up_matches = sum(1 for kw in FOLLOW_UP_KEYWORDS if kw in text_lower)
        score += min(0.2, follow_up_matches * 0.05)

        # Explicit request contribution
        for pattern in self._compiled_patterns:
            if pattern.search(text_lower):
                score += 0.2
                break

        return min(1.0, score)
