"""
Emotion inference from text and context.

This module provides emotion detection capabilities:
- Fast rule-based inference from text patterns
- Optional ML-based classification (requires transformers)
- Multi-signal fusion for robust detection
"""

from dataclasses import dataclass
import re
from typing import Dict, List, Optional, Tuple

from .mappings import extract_emotions_from_text
from .taxonomy import (
    CanonicalEmotion,
    EmotionState,
    EmotionVector,
    find_closest_emotion,
)


@dataclass
class InferenceResult:
    """Result from emotion inference."""

    primary_emotion: CanonicalEmotion
    intensity: float
    confidence: float
    method: str  # "rule", "classifier", "hybrid"
    secondary_emotions: Optional[List[Tuple[CanonicalEmotion, float, float]]] = None  # (emotion, intensity, confidence)

    def __post_init__(self):
        if self.secondary_emotions is None:
            self.secondary_emotions = []

    def to_emotion_state(self) -> EmotionState:
        """Convert to EmotionState."""
        secondary = None
        secondary_intensity = 0.0

        if self.secondary_emotions:
            secondary = self.secondary_emotions[0][0]
            secondary_intensity = self.secondary_emotions[0][1]

        return EmotionState(
            emotion=self.primary_emotion,
            intensity=self.intensity,
            secondary_emotion=secondary,
            secondary_intensity=secondary_intensity,
        )


# =============================================================================
# Rule-Based Inference
# =============================================================================

# Keyword patterns for emotion detection
# Format: pattern -> (emotion, base_intensity, weight)
EMOTION_PATTERNS: Dict[str, List[Tuple[str, CanonicalEmotion, float, float]]] = {
    "joy": [
        (r"\b(happy|happily|happiness)\b", CanonicalEmotion.JOY, 0.6, 1.0),
        (r"\b(excited|exciting|excitement)\b", CanonicalEmotion.JOY, 0.8, 1.0),
        (r"\b(great|awesome|amazing|wonderful)\b", CanonicalEmotion.JOY, 0.5, 0.8),
        (r"\b(love|loving|loved)\b", CanonicalEmotion.JOY, 0.7, 0.9),
        (r"\b(yay|woohoo|hurray)\b", CanonicalEmotion.JOY, 0.9, 1.0),
        (r"[!]{2,}", CanonicalEmotion.JOY, 0.4, 0.5),  # Multiple exclamation marks
        (r":D|:\)|😄|😊|🎉", CanonicalEmotion.JOY, 0.6, 0.7),
    ],
    "sadness": [
        (r"\b(sad|sadly|sadness)\b", CanonicalEmotion.SADNESS, 0.6, 1.0),
        (r"\b(disappointed|disappointing)\b", CanonicalEmotion.SADNESS, 0.5, 0.9),
        (r"\b(sorry|regret|miss)\b", CanonicalEmotion.SADNESS, 0.4, 0.7),
        (r"\b(crying|cried|tears)\b", CanonicalEmotion.SADNESS, 0.8, 1.0),
        (r"\b(depressed|depression|lonely)\b", CanonicalEmotion.SADNESS, 0.9, 1.0),
        (r":\(|😢|😭", CanonicalEmotion.SADNESS, 0.6, 0.7),
    ],
    "anger": [
        (r"\b(angry|angrily|anger)\b", CanonicalEmotion.ANGER, 0.7, 1.0),
        (r"\b(frustrated|frustrating|frustration)\b", CanonicalEmotion.ANGER, 0.5, 0.9),
        (r"\b(annoyed|annoying|irritated)\b", CanonicalEmotion.ANGER, 0.4, 0.8),
        (r"\b(hate|hated|hating)\b", CanonicalEmotion.ANGER, 0.8, 1.0),
        (r"\b(furious|outraged|enraged)\b", CanonicalEmotion.ANGER, 0.9, 1.0),
        (r"😠|😡|🤬", CanonicalEmotion.ANGER, 0.7, 0.8),
    ],
    "fear": [
        (r"\b(scared|scary|fear)\b", CanonicalEmotion.FEAR, 0.7, 1.0),
        (r"\b(nervous|nervously|anxiety)\b", CanonicalEmotion.FEAR, 0.5, 0.9),
        (r"\b(worried|worrying|worry)\b", CanonicalEmotion.FEAR, 0.4, 0.8),
        (r"\b(terrified|terror|panic)\b", CanonicalEmotion.FEAR, 0.9, 1.0),
        (r"\b(afraid|frightened)\b", CanonicalEmotion.FEAR, 0.6, 0.9),
        (r"😰|😨|😱", CanonicalEmotion.FEAR, 0.7, 0.8),
    ],
    "surprise": [
        (r"\b(surprised|surprising|surprise)\b", CanonicalEmotion.SURPRISE, 0.6, 1.0),
        (r"\b(shocked|shocking|shock)\b", CanonicalEmotion.SURPRISE, 0.8, 1.0),
        (r"\b(amazed|amazing|astonished)\b", CanonicalEmotion.SURPRISE, 0.7, 0.9),
        (r"\b(wow|whoa|omg)\b", CanonicalEmotion.SURPRISE, 0.6, 0.8),
        (r"\b(unexpected|suddenly)\b", CanonicalEmotion.SURPRISE, 0.5, 0.7),
        (r"😮|😲|🤯", CanonicalEmotion.SURPRISE, 0.7, 0.8),
    ],
    "confusion": [
        (r"\b(confused|confusing|confusion)\b", CanonicalEmotion.CONFUSION, 0.6, 1.0),
        (r"\b(puzzled|puzzling)\b", CanonicalEmotion.CONFUSION, 0.5, 0.9),
        (r"\b(unsure|uncertain|unclear)\b", CanonicalEmotion.CONFUSION, 0.4, 0.8),
        (r"\b(what\?|huh\?)\b", CanonicalEmotion.CONFUSION, 0.5, 0.7),
        (r"\?\?+", CanonicalEmotion.CONFUSION, 0.4, 0.5),  # Multiple question marks
        (r"🤔|😕|❓", CanonicalEmotion.CONFUSION, 0.5, 0.7),
    ],
    "thinking": [
        (r"\b(thinking|think|thought)\b", CanonicalEmotion.THINKING, 0.4, 0.8),
        (r"\b(considering|consider|ponder)\b", CanonicalEmotion.THINKING, 0.5, 0.9),
        (r"\b(hmm+|hm+)\b", CanonicalEmotion.THINKING, 0.4, 0.7),
        (r"\b(let me see|let's see)\b", CanonicalEmotion.THINKING, 0.3, 0.6),
        (r"\.\.\.+", CanonicalEmotion.THINKING, 0.3, 0.4),  # Ellipsis
    ],
    "calm": [
        (r"\b(calm|calmly|peaceful)\b", CanonicalEmotion.CALM, 0.5, 1.0),
        (r"\b(relaxed|relaxing|serene)\b", CanonicalEmotion.CALM, 0.6, 0.9),
        (r"\b(okay|alright|fine)\b", CanonicalEmotion.CALM, 0.3, 0.5),
        (r"😌|🧘", CanonicalEmotion.CALM, 0.6, 0.8),
    ],
}


def infer_emotion_from_text(text: str, include_audio_tags: bool = True) -> InferenceResult:
    """
    Infer emotion from text using rule-based patterns.

    Args:
        text: Input text to analyze
        include_audio_tags: Whether to also check for ElevenLabs audio tags

    Returns:
        InferenceResult with detected emotion and confidence
    """
    text_lower = text.lower()
    emotion_scores: Dict[CanonicalEmotion, List[Tuple[float, float]]] = {}

    # Check audio tags first
    if include_audio_tags:
        audio_emotions = extract_emotions_from_text(text)
        for emotion, intensity in audio_emotions:
            if emotion not in emotion_scores:
                emotion_scores[emotion] = []
            emotion_scores[emotion].append((intensity, 1.0))  # High confidence for explicit tags

    # Apply pattern matching
    for category_patterns in EMOTION_PATTERNS.values():
        for pattern, emotion, intensity, weight in category_patterns:
            matches = re.findall(pattern, text_lower, re.IGNORECASE)
            if matches:
                if emotion not in emotion_scores:
                    emotion_scores[emotion] = []
                # Each match adds to the score
                for _ in matches:
                    emotion_scores[emotion].append((intensity, weight))

    # No emotions detected
    if not emotion_scores:
        return InferenceResult(
            primary_emotion=CanonicalEmotion.CALM,
            intensity=0.3,
            confidence=0.2,
            method="rule",
        )

    # Calculate weighted scores for each emotion
    emotion_rankings: List[Tuple[CanonicalEmotion, float, float]] = []

    for emotion, scores in emotion_scores.items():
        total_weight = sum(w for _, w in scores)
        weighted_intensity = sum(i * w for i, w in scores) / total_weight
        confidence = min(0.9, 0.3 + len(scores) * 0.15)  # More matches = more confidence

        emotion_rankings.append((emotion, weighted_intensity, confidence))

    # Sort by confidence * intensity
    emotion_rankings.sort(key=lambda x: x[1] * x[2], reverse=True)

    primary = emotion_rankings[0]
    secondary = emotion_rankings[1:4]  # Up to 3 secondary emotions

    return InferenceResult(
        primary_emotion=primary[0],
        intensity=primary[1],
        confidence=primary[2],
        method="rule",
        secondary_emotions=secondary,
    )


# =============================================================================
# ML-Based Inference (Optional)
# =============================================================================


class MLEmotionClassifier:
    """
    ML-based emotion classifier using transformers.

    Lazy-loads the model on first use.
    Default model: bhadresh-savani/distilbert-base-uncased-emotion
    """

    # Map classifier labels to canonical emotions
    LABEL_MAPPING = {
        "sadness": CanonicalEmotion.SADNESS,
        "joy": CanonicalEmotion.JOY,
        "love": CanonicalEmotion.JOY,  # Map love to joy with higher intensity
        "anger": CanonicalEmotion.ANGER,
        "fear": CanonicalEmotion.FEAR,
        "surprise": CanonicalEmotion.SURPRISE,
        # Additional labels from other models
        "neutral": CanonicalEmotion.CALM,
        "happy": CanonicalEmotion.JOY,
        "sad": CanonicalEmotion.SADNESS,
        "angry": CanonicalEmotion.ANGER,
        "fearful": CanonicalEmotion.FEAR,
        "disgust": CanonicalEmotion.DISGUST,
        "contempt": CanonicalEmotion.CONTEMPT,
    }

    def __init__(self, model_name: str = "bhadresh-savani/distilbert-base-uncased-emotion"):
        self.model_name = model_name
        self._classifier = None
        self._available: Optional[bool] = None

    @property
    def is_available(self) -> bool:
        """Check if transformers is available."""
        if self._available is None:
            try:
                import transformers  # noqa: F401

                self._available = True
            except ImportError:
                self._available = False
        return self._available  # type: ignore[return-value]

    def _load_classifier(self):
        """Lazy-load the classifier."""
        if self._classifier is None and self.is_available:
            from transformers import pipeline

            self._classifier = pipeline(
                "text-classification",
                model=self.model_name,
                top_k=3,
            )
        return self._classifier

    def classify(self, text: str) -> Optional[InferenceResult]:
        """
        Classify emotion using ML model.

        Args:
            text: Input text

        Returns:
            InferenceResult or None if classifier not available
        """
        classifier = self._load_classifier()
        if classifier is None:
            return None

        try:
            results = classifier(text)
            if not results:
                return None

            # Process results (format: [[{label, score}, ...]])
            if isinstance(results[0], list):
                results = results[0]

            # Map labels to canonical emotions
            emotion_scores = []
            for result in results:
                label = result["label"].lower()
                score = result["score"]

                if label in self.LABEL_MAPPING:
                    emotion = self.LABEL_MAPPING[label]
                    # Adjust intensity based on label
                    intensity = score
                    if label == "love":
                        intensity = min(1.0, score * 1.2)  # Love is high-intensity joy

                    emotion_scores.append((emotion, intensity, score))

            if not emotion_scores:
                return None

            primary = emotion_scores[0]
            secondary = emotion_scores[1:]

            return InferenceResult(
                primary_emotion=primary[0],
                intensity=primary[1],
                confidence=primary[2],
                method="classifier",
                secondary_emotions=secondary,
            )
        except Exception:
            return None


# Global classifier instance (lazy-loaded)
_ml_classifier: Optional[MLEmotionClassifier] = None


def get_ml_classifier() -> MLEmotionClassifier:
    """Get the global ML classifier instance."""
    global _ml_classifier
    if _ml_classifier is None:
        _ml_classifier = MLEmotionClassifier()
    return _ml_classifier


def infer_emotion_ml(text: str) -> Optional[InferenceResult]:
    """
    Infer emotion using ML classifier.

    Args:
        text: Input text

    Returns:
        InferenceResult or None if classifier not available
    """
    return get_ml_classifier().classify(text)


# =============================================================================
# Hybrid Inference
# =============================================================================


def infer_emotion(
    text: str,
    use_ml: bool = True,
    fallback_to_rules: bool = True,
) -> EmotionState:
    """
    Infer emotion using best available method.

    Priority:
    1. ML classifier (if available and use_ml=True)
    2. Rule-based inference (if fallback_to_rules=True)
    3. Default calm state

    Args:
        text: Input text to analyze
        use_ml: Whether to try ML classification first
        fallback_to_rules: Whether to fallback to rules if ML unavailable

    Returns:
        EmotionState with inferred emotion
    """
    result = None

    # Try ML first
    if use_ml:
        result = infer_emotion_ml(text)

    # Fallback to rules
    if result is None and fallback_to_rules:
        result = infer_emotion_from_text(text)

    # Fallback to default
    if result is None:
        return EmotionState(CanonicalEmotion.CALM, 0.3)

    return result.to_emotion_state()


def infer_emotion_hybrid(text: str) -> InferenceResult:
    """
    Hybrid inference combining rule-based and ML approaches.

    Blends results from both methods for more robust detection.

    Args:
        text: Input text

    Returns:
        InferenceResult with combined confidence
    """
    rule_result = infer_emotion_from_text(text)
    ml_result = infer_emotion_ml(text)

    if ml_result is None:
        return rule_result

    # If both agree on primary emotion, boost confidence
    if rule_result.primary_emotion == ml_result.primary_emotion:
        combined_confidence = min(0.95, (rule_result.confidence + ml_result.confidence) / 1.5)
        combined_intensity = (rule_result.intensity + ml_result.intensity) / 2

        return InferenceResult(
            primary_emotion=rule_result.primary_emotion,
            intensity=combined_intensity,
            confidence=combined_confidence,
            method="hybrid",
            secondary_emotions=(rule_result.secondary_emotions or []) + (ml_result.secondary_emotions or []),
        )

    # If they disagree, use the higher confidence result
    if ml_result.confidence > rule_result.confidence:
        ml_result.method = "hybrid"
        return ml_result
    else:
        rule_result.method = "hybrid"
        return rule_result


# =============================================================================
# Context-Aware Inference
# =============================================================================


@dataclass
class ConversationContext:
    """Context for emotion inference."""

    recent_emotions: List[EmotionState]  # Last N emotions
    user_tone: Optional[str] = None  # "casual", "professional", "emotional"
    topic: Optional[str] = None  # Current topic

    def get_emotional_trend(self) -> Optional[EmotionVector]:
        """Get the average emotional state from recent history."""
        if not self.recent_emotions:
            return None

        vectors = [e.pad_vector for e in self.recent_emotions]
        avg = EmotionVector.neutral()
        for v in vectors:
            avg = avg + v

        n = len(vectors)
        return EmotionVector(
            pleasure=avg.pleasure / n,
            arousal=avg.arousal / n,
            dominance=avg.dominance / n,
        )


def infer_emotion_with_context(
    text: str,
    context: ConversationContext,
    inertia: float = 0.3,
) -> EmotionState:
    """
    Infer emotion considering conversation context.

    Uses emotional inertia to smooth transitions and avoid jarring jumps.

    Args:
        text: Input text
        context: Conversation context with history
        inertia: How much to weight previous state (0 = ignore, 1 = fully weighted)

    Returns:
        EmotionState blended with context
    """
    current = infer_emotion(text)

    # Get emotional trend
    trend = context.get_emotional_trend()
    if trend is None:
        return current

    # Blend current with trend
    current_pad = current.pad_vector
    blended = current_pad.lerp(trend, inertia * 0.5)  # Partial inertia

    # Find closest emotion to blended state
    emotion, confidence = find_closest_emotion(blended)

    return EmotionState(
        emotion=emotion,
        intensity=blended.magnitude(),
        secondary_emotion=current.emotion if current.emotion != emotion else None,
        secondary_intensity=current.intensity * 0.3 if current.emotion != emotion else 0,
    )
