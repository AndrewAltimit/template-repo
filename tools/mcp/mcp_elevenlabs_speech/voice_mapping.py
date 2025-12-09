"""Enhanced Voice Mapping System for ElevenLabs MCP

This module provides a robust voice mapping system with:
- v3 compatibility tracking
- Scenario-based recommendations
- Fallback strategies
- Quality ratings
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Set


class VoiceQuality(Enum):
    """Voice quality ratings based on real-world testing"""

    EXCELLENT = 5  # Professional, consistent, highly expressive
    GOOD = 4  # Good quality, minor limitations
    AVERAGE = 3  # Functional but with noticeable issues
    POOR = 2  # Significant issues, use only if necessary
    UNUSABLE = 1  # Do not use


class ContentType(Enum):
    """Content types for smart voice selection"""

    GITHUB_REVIEW = "github_review"
    DOCUMENTATION = "documentation"
    TUTORIAL = "tutorial"
    ANNOUNCEMENT = "announcement"
    CASUAL_CHAT = "casual_chat"
    STORY_TELLING = "story_telling"
    NEWS_READING = "news_reading"
    TECHNICAL_EXPLANATION = "technical_explanation"
    ERROR_MESSAGE = "error_message"
    SUCCESS_MESSAGE = "success_message"
    WARNING_MESSAGE = "warning_message"
    MEDITATION = "meditation"
    ADVERTISEMENT = "advertisement"
    ENTERTAINMENT = "entertainment"
    EDUCATIONAL = "educational"


@dataclass
class VoiceCapabilities:
    """Track voice capabilities and limitations"""

    voice_id: str
    friendly_name: str
    display_name: str  # User-friendly name for selection

    # v3 Compatibility
    supports_v3: bool  # Works with eleven_v3 model
    supports_audio_tags: bool  # Supports [laughs], [whisper], etc.
    supports_emotions: bool  # Good emotional range

    # Quality metrics
    overall_quality: VoiceQuality
    clarity: int  # 1-5 scale
    naturalness: int  # 1-5 scale
    expressiveness: int  # 1-5 scale
    consistency: int  # 1-5 scale

    # Best use cases
    best_for: Set[ContentType]
    avoid_for: Set[ContentType]

    # Technical details
    languages: Set[str]  # ISO language codes
    accents: Set[str]
    gender: str
    age_group: str

    # Model recommendations
    recommended_models: List[str]  # Ordered by preference
    fallback_model: str  # If primary fails

    # Settings
    optimal_stability: float
    optimal_similarity: float
    optimal_style: float

    # Notes
    notes: str
    known_issues: List[str]


# Comprehensive voice mapping with v3 compatibility and quality ratings
VOICE_MAPPING: Dict[str, VoiceCapabilities] = {
    # === TOP TIER VOICES (v3 Compatible, Excellent Quality) ===
    "rachel": VoiceCapabilities(
        voice_id="21m00Tcm4TlvDq8ikWAM",
        friendly_name="Rachel",
        display_name="Rachel (Friendly & Enthusiastic)",
        supports_v3=True,
        supports_audio_tags=True,
        supports_emotions=True,
        overall_quality=VoiceQuality.EXCELLENT,
        clarity=5,
        naturalness=5,
        expressiveness=5,
        consistency=5,
        best_for={
            ContentType.GITHUB_REVIEW,
            ContentType.TUTORIAL,
            ContentType.CASUAL_CHAT,
            ContentType.SUCCESS_MESSAGE,
            ContentType.DOCUMENTATION,
        },
        avoid_for={
            ContentType.ERROR_MESSAGE,
            ContentType.MEDITATION,
        },
        languages={"en"},
        accents={"american"},
        gender="female",
        age_group="young",
        recommended_models=["eleven_v3", "eleven_multilingual_v2"],
        fallback_model="eleven_multilingual_v2",
        optimal_stability=0.5,
        optimal_similarity=0.75,
        optimal_style=0.5,
        notes="Perfect for technical content with a friendly tone. Great with audio tags.",
        known_issues=[],
    ),
    "sarah": VoiceCapabilities(
        voice_id="EXAVITQu4vr4xnSDxMaL",
        friendly_name="Sarah",
        display_name="Sarah (Professional & Clear)",
        supports_v3=True,
        supports_audio_tags=True,
        supports_emotions=False,  # Limited emotional range
        overall_quality=VoiceQuality.EXCELLENT,
        clarity=5,
        naturalness=4,
        expressiveness=3,
        consistency=5,
        best_for={
            ContentType.DOCUMENTATION,
            ContentType.NEWS_READING,
            ContentType.TECHNICAL_EXPLANATION,
            ContentType.ANNOUNCEMENT,
            ContentType.ERROR_MESSAGE,
        },
        avoid_for={
            ContentType.ENTERTAINMENT,
            ContentType.CASUAL_CHAT,
        },
        languages={"en"},
        accents={"american"},
        gender="female",
        age_group="young",
        recommended_models=["eleven_v3", "eleven_multilingual_v2"],
        fallback_model="eleven_multilingual_v2",
        optimal_stability=0.8,
        optimal_similarity=0.9,
        optimal_style=0.1,
        notes="Extremely clear and professional. Best for technical documentation.",
        known_issues=["Limited emotional expression"],
    ),
    "roger": VoiceCapabilities(
        voice_id="CwhRBWXzGAHq8TQ4Fs17",
        friendly_name="Roger",
        display_name="Roger (Sophisticated & Trustworthy)",
        supports_v3=True,
        supports_audio_tags=True,
        supports_emotions=True,
        overall_quality=VoiceQuality.EXCELLENT,
        clarity=5,
        naturalness=5,
        expressiveness=4,
        consistency=5,
        best_for={
            ContentType.GITHUB_REVIEW,
            ContentType.DOCUMENTATION,
            ContentType.TECHNICAL_EXPLANATION,
            ContentType.EDUCATIONAL,
        },
        avoid_for={
            ContentType.CASUAL_CHAT,
            ContentType.ENTERTAINMENT,
        },
        languages={"en"},
        accents={"american"},
        gender="male",
        age_group="mature",
        recommended_models=["eleven_v3", "eleven_multilingual_v2"],
        fallback_model="eleven_multilingual_v2",
        optimal_stability=0.7,
        optimal_similarity=0.85,
        optimal_style=0.3,
        notes="Authoritative and trustworthy. Perfect for serious technical content.",
        known_issues=[],
    ),
    # === GOOD QUALITY VOICES (v3 Compatible) ===
    "chris": VoiceCapabilities(
        voice_id="iP95p4xoKVk53GoZ742B",
        friendly_name="Chris",
        display_name="Chris (Casual & Approachable)",
        supports_v3=True,
        supports_audio_tags=True,
        supports_emotions=True,
        overall_quality=VoiceQuality.GOOD,
        clarity=4,
        naturalness=5,
        expressiveness=4,
        consistency=4,
        best_for={
            ContentType.CASUAL_CHAT,
            ContentType.TUTORIAL,
            ContentType.SUCCESS_MESSAGE,
        },
        avoid_for={
            ContentType.ERROR_MESSAGE,
            ContentType.ANNOUNCEMENT,
        },
        languages={"en"},
        accents={"american"},
        gender="male",
        age_group="middle_aged",
        recommended_models=["eleven_v3", "eleven_multilingual_v2"],
        fallback_model="eleven_multilingual_v2",
        optimal_stability=0.5,
        optimal_similarity=0.75,
        optimal_style=0.4,
        notes="Friendly male voice, good for conversational content.",
        known_issues=[],
    ),
    "lily": VoiceCapabilities(
        voice_id="pFZP5JQG7iQjIQuC4Bku",
        friendly_name="Lily",
        display_name="Lily (Warm & Confident)",
        supports_v3=True,
        supports_audio_tags=True,
        supports_emotions=True,
        overall_quality=VoiceQuality.GOOD,
        clarity=4,
        naturalness=5,
        expressiveness=4,
        consistency=4,
        best_for={
            ContentType.STORY_TELLING,
            ContentType.EDUCATIONAL,
            ContentType.MEDITATION,
        },
        avoid_for={
            ContentType.ERROR_MESSAGE,
            ContentType.TECHNICAL_EXPLANATION,
        },
        languages={"en"},
        accents={"british"},
        gender="female",
        age_group="middle_aged",
        recommended_models=["eleven_v3", "eleven_multilingual_v2"],
        fallback_model="eleven_multilingual_v2",
        optimal_stability=0.6,
        optimal_similarity=0.8,
        optimal_style=0.3,
        notes="British accent adds sophistication. Good for narration.",
        known_issues=["British accent may not suit all content"],
    ),
    # === VOICES WITH LIMITATIONS ===
    "clyde": VoiceCapabilities(
        voice_id="2EiwWnXFnvU5JabPnv8n",
        friendly_name="Clyde",
        display_name="Clyde (Intense & Commanding)",
        supports_v3=True,
        supports_audio_tags=False,  # Too intense for subtle tags
        supports_emotions=False,  # Limited to intense emotions
        overall_quality=VoiceQuality.AVERAGE,
        clarity=4,
        naturalness=3,
        expressiveness=2,  # Only intense expression
        consistency=4,
        best_for={
            ContentType.ERROR_MESSAGE,
            ContentType.WARNING_MESSAGE,
        },
        avoid_for={
            ContentType.GITHUB_REVIEW,
            ContentType.DOCUMENTATION,
            ContentType.CASUAL_CHAT,
            ContentType.TUTORIAL,
        },
        languages={"en"},
        accents={"american"},
        gender="male",
        age_group="middle_aged",
        recommended_models=["eleven_multilingual_v2"],  # v3 too intense
        fallback_model="eleven_monolingual_v1",
        optimal_stability=0.3,
        optimal_similarity=0.7,
        optimal_style=0.8,
        notes="Very intense voice. Use sparingly for warnings/errors only.",
        known_issues=["Too aggressive for normal content", "Audio tags sound unnatural"],
    ),
    # === FALLBACK VOICES ===
    "daniel": VoiceCapabilities(
        voice_id="onwK4e9ZLuTAKqWW03F9",
        friendly_name="Daniel",
        display_name="Daniel (Formal British)",
        supports_v3=True,
        supports_audio_tags=True,
        supports_emotions=False,
        overall_quality=VoiceQuality.GOOD,
        clarity=5,
        naturalness=4,
        expressiveness=3,
        consistency=5,
        best_for={
            ContentType.DOCUMENTATION,
            ContentType.EDUCATIONAL,
        },
        avoid_for={
            ContentType.CASUAL_CHAT,
            ContentType.ENTERTAINMENT,
        },
        languages={"en"},
        accents={"british"},
        gender="male",
        age_group="middle_aged",
        recommended_models=["eleven_v3", "eleven_multilingual_v2"],
        fallback_model="eleven_multilingual_v2",
        optimal_stability=0.8,
        optimal_similarity=0.85,
        optimal_style=0.2,
        notes="Very formal British voice. Good fallback for professional content.",
        known_issues=["May sound too formal for some contexts"],
    ),
}


# Quick lookup maps
VOICE_ID_TO_NAME: Dict[str, str] = {caps.voice_id: name for name, caps in VOICE_MAPPING.items()}

DISPLAY_NAME_TO_VOICE: Dict[str, str] = {caps.display_name.lower(): name for name, caps in VOICE_MAPPING.items()}


def get_voice_id(voice_input: str) -> Optional[str]:
    """
    Resolve voice ID from various input formats

    Args:
        voice_input: Can be voice name, display name, or ID

    Returns:
        Voice ID or None if not found
    """
    if not voice_input:
        return None

    voice_lower = voice_input.lower().strip()

    # Check if it's already a voice ID
    if voice_lower in VOICE_ID_TO_NAME:
        return voice_lower

    # Check friendly name
    if voice_lower in VOICE_MAPPING:
        return VOICE_MAPPING[voice_lower].voice_id

    # Check display name
    if voice_lower in DISPLAY_NAME_TO_VOICE:
        voice_name = DISPLAY_NAME_TO_VOICE[voice_lower]
        return VOICE_MAPPING[voice_name].voice_id

    # Check partial matches on display names
    for display, voice_name in DISPLAY_NAME_TO_VOICE.items():
        if voice_lower in display or display in voice_lower:
            return VOICE_MAPPING[voice_name].voice_id

    return None


def get_voice_for_content(content_type: ContentType, prefer_gender: Optional[str] = None, require_v3: bool = True) -> str:
    """
    Get the best voice for a specific content type

    Args:
        content_type: Type of content
        prefer_gender: Preferred gender (male/female/neutral)
        require_v3: Only return v3-compatible voices

    Returns:
        Voice name (key in VOICE_MAPPING)
    """
    candidates = []

    for voice_name, caps in VOICE_MAPPING.items():
        # Skip if v3 required but not supported
        if require_v3 and not caps.supports_v3:
            continue

        # Skip if wrong gender preference
        if prefer_gender and caps.gender != prefer_gender:
            continue

        # Skip if in avoid list
        if content_type in caps.avoid_for:
            continue

        # Calculate score
        score = 0

        # Base quality score
        score += caps.overall_quality.value * 10

        # Content type match
        if content_type in caps.best_for:
            score += 20

        # Technical scores
        score += caps.clarity
        score += caps.naturalness
        score += caps.consistency

        # Expressiveness for appropriate content
        if content_type in [ContentType.CASUAL_CHAT, ContentType.ENTERTAINMENT, ContentType.STORY_TELLING]:
            score += caps.expressiveness * 2

        candidates.append((score, voice_name))

    if not candidates:
        # Fallback to Rachel as default
        return "rachel"

    # Sort by score and return best
    candidates.sort(reverse=True)
    return candidates[0][1]


def validate_voice_for_model(voice_name: str, model: str) -> tuple[bool, str]:
    """
    Validate if a voice works well with a specific model

    Args:
        voice_name: Voice name from VOICE_MAPPING
        model: Model name (e.g., "eleven_v3")

    Returns:
        Tuple of (is_valid, message)
    """
    if voice_name not in VOICE_MAPPING:
        return False, f"Unknown voice: {voice_name}"

    caps = VOICE_MAPPING[voice_name]

    if model == "eleven_v3":
        if not caps.supports_v3:
            return False, f"{caps.display_name} does not support v3 model"
        if not caps.supports_audio_tags:
            return False, f"{caps.display_name} does not support audio tags with v3"

    if model not in caps.recommended_models:
        return True, f"Warning: {model} not recommended for {caps.display_name}"

    return True, "OK"


def get_optimal_settings(voice_name: str) -> Dict[str, float]:
    """Get optimal voice settings for a voice"""
    if voice_name not in VOICE_MAPPING:
        # Default settings
        return {"stability": 0.5, "similarity_boost": 0.75, "style": 0.0, "use_speaker_boost": False}

    caps = VOICE_MAPPING[voice_name]
    return {
        "stability": caps.optimal_stability,
        "similarity_boost": caps.optimal_similarity,
        "style": caps.optimal_style,
        "use_speaker_boost": False,
    }


# Export commonly used voices for quick access
DEFAULT_VOICE = "rachel"
GITHUB_REVIEW_VOICES = ["rachel", "roger", "sarah"]
ERROR_VOICE = "sarah"  # Clear and professional for errors
SUCCESS_VOICE = "rachel"  # Friendly for success messages
