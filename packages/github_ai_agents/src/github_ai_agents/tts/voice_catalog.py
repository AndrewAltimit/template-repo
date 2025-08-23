"""Complete voice catalog from ElevenLabs library with character profiles.

TODO: Consider externalizing VOICE_CATALOG and AGENT_PERSONALITY_MAPPING to
      YAML/JSON configuration files for easier maintenance without code changes.
      This would decouple configuration from application logic.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional


class VoiceCategory(Enum):
    """Voice categories for different use cases."""

    CONVERSATIONAL = "conversational"
    NARRATIVE = "narrative"
    PROFESSIONAL = "professional"
    CHARACTER = "character"
    SOCIAL_MEDIA = "social"
    DRAMATIC = "dramatic"


@dataclass
class VoiceCharacter:
    """Complete voice character profile."""

    voice_id: str
    name: str
    display_name: str
    description: str
    accent: str
    gender: str
    age: str
    category: VoiceCategory
    personality_traits: List[str]
    best_for: List[str]
    v3_compatible: bool = True
    stability_range: tuple = (0.0, 0.5)  # Min, max for emotional expression
    use_speaker_boost: bool = False
    custom_settings: Optional[Dict] = None


# Complete voice catalog from your ElevenLabs library
VOICE_CATALOG = {
    "blondie": VoiceCharacter(
        voice_id="exsUS4vynmxd379XN4yO",
        name="blondie",
        display_name="Blondie - Conversational",
        description="A British woman with a warm, natural voice—perfect for relaxed, engaging conversations",
        accent="British",
        gender="female",
        age="middle_aged",
        category=VoiceCategory.CONVERSATIONAL,
        personality_traits=["warm", "natural", "engaging", "friendly"],
        best_for=["conversations", "storytelling", "narration"],
        v3_compatible=True,
        stability_range=(0.0, 0.3),
        use_speaker_boost=True,
    ),
    "jane": VoiceCharacter(
        voice_id="RILOU7YmBhvwJGDGjNmP",
        name="jane",
        display_name="Jane - Professional Audiobook Reader",
        description="Professional English audiobook narrator in her 50s with nice tone and cadence",
        accent="British",
        gender="female",
        age="old",
        category=VoiceCategory.NARRATIVE,
        personality_traits=["professional", "clear", "measured", "authoritative"],
        best_for=["audiobooks", "documentation", "technical content"],
        v3_compatible=True,
        stability_range=(0.3, 0.6),
    ),
    "cassidy": VoiceCharacter(
        voice_id="56AoDkrOh6qfVPDXZ7Pt",
        name="cassidy",
        display_name="Cassidy",
        description="A confident female podcaster with plethora of experience in the music industry",
        accent="American",
        gender="female",
        age="middle_aged",
        category=VoiceCategory.CONVERSATIONAL,
        personality_traits=["confident", "experienced", "knowledgeable"],
        best_for=["podcasts", "interviews", "music reviews"],
        v3_compatible=True,
        stability_range=(0.2, 0.5),
    ),
    "juniper": VoiceCharacter(
        voice_id="aMSt68OGf4xUZAnLpTU8",
        name="juniper",
        display_name="Juniper",
        description="A grounded female professional, great for podcasts or ConvoAI",
        accent="American",
        gender="female",
        age="middle_aged",
        category=VoiceCategory.PROFESSIONAL,
        personality_traits=["grounded", "professional", "clear", "reliable"],
        best_for=["business", "technical reviews", "professional content"],
        v3_compatible=True,
        stability_range=(0.3, 0.5),
    ),
    "amelia": VoiceCharacter(
        voice_id="ZF6FPAbjXT4488VcRRnw",
        name="amelia",
        display_name="Amelia",
        description="Young British English woman's voice, clear and expressive, beautiful for narration",
        accent="British",
        gender="female",
        age="young",
        category=VoiceCategory.NARRATIVE,
        personality_traits=["expressive", "enthusiastic", "clear", "youthful"],
        best_for=["social media", "YouTube", "storytelling"],
        v3_compatible=True,
        stability_range=(0.1, 0.4),
    ),
    "hope_conversational": VoiceCharacter(
        voice_id="uYXf8XasLslADfZ2MB4u",
        name="hope_conversational",
        display_name="Hope - Your conversational bestie",
        description="Natural conversation with mmms, ahhs, chuckles—like chatting with a close friend",
        accent="American",
        gender="female",
        age="young",
        category=VoiceCategory.CONVERSATIONAL,
        personality_traits=["natural", "friendly", "imperfect", "genuine"],
        best_for=["AI assistants", "therapy bots", "casual conversations"],
        v3_compatible=True,
        stability_range=(0.0, 0.3),
        use_speaker_boost=True,
    ),
    "hope_upbeat": VoiceCharacter(
        voice_id="tnSpp4vdxKPjI9w0GnoV",
        name="hope_upbeat",
        display_name="Hope - upbeat and clear",
        description="Upbeat and clear voice for energetic content",
        accent="American",
        gender="female",
        age="young",
        category=VoiceCategory.SOCIAL_MEDIA,
        personality_traits=["upbeat", "energetic", "clear", "positive"],
        best_for=["social media", "announcements", "promotional content"],
        v3_compatible=True,
        stability_range=(0.2, 0.4),
    ),
    "peter": VoiceCharacter(
        voice_id="4dZr8J4CBeokyRkTRpoN",
        name="peter",
        display_name="Peter Harwood",
        description="Rich, clear English RP accent specializing in clarity of expression",
        accent="British RP",
        gender="male",
        age="middle_aged",
        category=VoiceCategory.PROFESSIONAL,
        personality_traits=["clear", "authoritative", "refined", "professional"],
        best_for=["documentation", "educational content", "formal presentations"],
        v3_compatible=True,
        stability_range=(0.3, 0.6),
    ),
    "stokes": VoiceCharacter(
        voice_id="kHhWB9Fw3aF6ly7JvltC",
        name="stokes",
        display_name="Stokes",
        description="Relaxing, casual, warm American male voice",
        accent="American",
        gender="male",
        age="middle_aged",
        category=VoiceCategory.CONVERSATIONAL,
        personality_traits=["relaxing", "casual", "warm", "friendly"],
        best_for=["casual reviews", "podcasts", "friendly explanations"],
        v3_compatible=True,
        stability_range=(0.2, 0.5),
    ),
    "adam": VoiceCharacter(
        voice_id="NFG5qt843uXKj4pFvR7C",
        name="adam",
        display_name="Adam Stone - late night radio",
        description="Middle aged Brit with velvety laid back, late night talk show host timbre",
        accent="British",
        gender="male",
        age="middle_aged",
        category=VoiceCategory.NARRATIVE,
        personality_traits=["velvety", "laid-back", "smooth", "contemplative"],
        best_for=["late night content", "thoughtful reviews", "philosophical discussions"],
        v3_compatible=True,
        stability_range=(0.1, 0.4),
    ),
    "reginald": VoiceCharacter(
        voice_id="Hjzqw9NR0xFMYU9Us0DL",
        name="reginald",
        display_name="Reginald - intense villain",
        description="Dark, brooding character voice, perfect for dramatic content",
        accent="American",
        gender="male",
        age="middle_aged",
        category=VoiceCategory.CHARACTER,
        personality_traits=["dark", "brooding", "intense", "dramatic"],
        best_for=["critical reviews", "security warnings", "dramatic emphasis"],
        v3_compatible=True,
        stability_range=(0.0, 0.3),
        use_speaker_boost=True,
    ),
    "tia": VoiceCharacter(
        voice_id="OUBnvvuqEKdDWtapoJFn",
        name="tia",
        display_name="Tia Mirza - Tough Recovery & Collections Specialist",
        description="Crisp, commanding voice for tough interactions and straight-talking",
        accent="Indian",
        gender="female",
        age="middle_aged",
        category=VoiceCategory.PROFESSIONAL,
        personality_traits=["firm", "commanding", "direct", "no-nonsense"],
        best_for=["critical feedback", "security issues", "urgent matters"],
        v3_compatible=True,
        stability_range=(0.4, 0.6),
    ),
    "rhea": VoiceCharacter(
        voice_id="eUdJpUEN3EslrgE24PKx",
        name="rhea",
        display_name="Rhea – Romantic & Calm",
        description="Soft, graceful voice that blends romance with polished delivery",
        accent="Indian",
        gender="female",
        age="middle_aged",
        category=VoiceCategory.NARRATIVE,
        personality_traits=["soft", "graceful", "calm", "intimate"],
        best_for=["thoughtful reviews", "meditation", "calm explanations"],
        v3_compatible=True,
        stability_range=(0.2, 0.5),
    ),
    "old_radio": VoiceCharacter(
        voice_id="77UfkmRb2Y7IilMQI9fM",
        name="old_radio",
        display_name="Old Radio",
        description="Captain Picard sounding, distinguished British male with theatrical projection",
        accent="British",
        gender="male",
        age="old",
        category=VoiceCategory.DRAMATIC,
        personality_traits=["distinguished", "resonant", "theatrical", "commanding"],
        best_for=["important announcements", "dramatic reviews", "final verdicts"],
        v3_compatible=True,
        stability_range=(0.3, 0.6),
    ),
    "movie_promo": VoiceCharacter(
        voice_id="qwTK78XQKuFJDYDi9riD",
        name="movie_promo",
        display_name="Movie Promo",
        description="Dramatic voice for building anticipation, associated with action or thrillers",
        accent="American",
        gender="male",
        age="middle_aged",
        category=VoiceCategory.DRAMATIC,
        personality_traits=["dramatic", "anticipatory", "intense", "powerful"],
        best_for=["major announcements", "release notes", "exciting features"],
        v3_compatible=True,
        stability_range=(0.0, 0.3),
        use_speaker_boost=True,
    ),
}


# Agent personality to voice mapping based on characteristics
AGENT_PERSONALITY_MAPPING = {
    "gemini": {
        "default": "hope_conversational",  # Natural, friendly bestie
        "critical": "tia",  # Direct feedback
        "excited": "hope_upbeat",  # Positive reviews
        "thoughtful": "adam",  # Deep analysis
        "broadcast": "old_radio",  # News bulletin style
    },
    "claude": {
        "default": "blondie",  # Warm, conversational British
        "technical": "peter",  # Clear documentation
        "friendly": "cassidy",  # Conversational reviews
        "serious": "juniper",  # Business-like
        "broadcast": "old_radio",  # News bulletin style
    },
    "opencode": {
        "default": "peter",  # Educational, clear
        "casual": "stokes",  # Relaxed explanations
        "enthusiastic": "amelia",  # Excited about code
        "professional": "juniper",  # Formal reviews
        "broadcast": "old_radio",  # News bulletin style
    },
    "crush": {
        "default": "hope_conversational",  # Natural, friendly
        "energetic": "hope_upbeat",  # Quick, upbeat
        "calm": "rhea",  # Thoughtful responses
        "direct": "tia",  # No-nonsense feedback
        "broadcast": "old_radio",  # News bulletin style
    },
}


def get_voice_for_context(
    agent_name: str, review_sentiment: str = "default", pr_criticality: str = "normal"
) -> VoiceCharacter:
    """Get appropriate voice based on agent and context.

    Args:
        agent_name: Name of the agent
        review_sentiment: Overall sentiment (default, critical, excited, thoughtful)
        pr_criticality: PR criticality level (normal, high, urgent)

    Returns:
        VoiceCharacter for the context
    """
    # Get agent personality mapping
    agent_mapping = AGENT_PERSONALITY_MAPPING.get(
        agent_name.lower(), AGENT_PERSONALITY_MAPPING["gemini"]  # Default to Gemini
    )

    # For urgent/critical PRs, use more serious voices
    if pr_criticality == "urgent":
        if review_sentiment == "critical":
            return VOICE_CATALOG.get("reginald", VOICE_CATALOG["tia"])
        else:
            return VOICE_CATALOG.get("old_radio", VOICE_CATALOG["peter"])

    # Get voice based on sentiment
    voice_key = agent_mapping.get(review_sentiment, agent_mapping["default"])

    return VOICE_CATALOG.get(voice_key, VOICE_CATALOG["blondie"])


def get_voice_settings_for_emotion(voice: VoiceCharacter, emotion_intensity: float = 0.5) -> Dict:
    """Get voice settings optimized for emotional expression.

    Args:
        voice: Voice character to use
        emotion_intensity: How intense emotions should be (0.0-1.0)

    Returns:
        Voice settings dictionary
    """
    # Calculate stability based on emotion intensity
    min_stability, max_stability = voice.stability_range
    stability = max_stability - (emotion_intensity * (max_stability - min_stability))

    settings = {
        "stability": stability,
        "similarity_boost": 0.75,
        "style": emotion_intensity * 0.5,  # Style increases with emotion
        "use_speaker_boost": voice.use_speaker_boost,
    }

    # Apply custom settings if any
    if voice.custom_settings:
        settings.update(voice.custom_settings)

    return settings


def list_voices_by_category(category: VoiceCategory) -> List[VoiceCharacter]:
    """Get all voices in a specific category.

    Args:
        category: Voice category to filter by

    Returns:
        List of voices in that category
    """
    return [voice for voice in VOICE_CATALOG.values() if voice.category == category]


def get_voice_recommendations(content_type: str, tone: str = "neutral") -> List[VoiceCharacter]:
    """Get voice recommendations for specific content.

    Args:
        content_type: Type of content (review, documentation, etc.)
        tone: Desired tone (friendly, professional, critical, etc.)

    Returns:
        List of recommended voices
    """
    recommendations = []

    for voice in VOICE_CATALOG.values():
        # Check if content type matches best_for
        if any(content_type.lower() in use.lower() for use in voice.best_for):
            recommendations.append(voice)
        # Check if tone matches personality traits
        elif any(tone.lower() in trait.lower() for trait in voice.personality_traits):
            recommendations.append(voice)

    return recommendations[:5]  # Return top 5 recommendations
