"""Local Voice Registry with Character Profiles

This module maintains a comprehensive registry of ElevenLabs voices with
character profiles, personality traits, and usage recommendations.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional


class VoiceGender(Enum):
    MALE = "male"
    FEMALE = "female"
    NEUTRAL = "neutral"


class VoiceAge(Enum):
    YOUNG = "young"  # 18-30
    MIDDLE_AGED = "middle_aged"  # 30-50
    MATURE = "mature"  # 50+
    ELDERLY = "elderly"  # 70+


class VoiceAccent(Enum):
    AMERICAN = "american"
    BRITISH = "british"
    AUSTRALIAN = "australian"
    CANADIAN = "canadian"
    IRISH = "irish"
    SCOTTISH = "scottish"
    SWEDISH = "swedish"
    GERMAN = "german"
    FRENCH = "french"
    SPANISH = "spanish"
    ITALIAN = "italian"
    RUSSIAN = "russian"
    INDIAN = "indian"
    NEUTRAL = "neutral"


class VoiceTone(Enum):
    CASUAL = "casual"
    PROFESSIONAL = "professional"
    FRIENDLY = "friendly"
    SERIOUS = "serious"
    WARM = "warm"
    AUTHORITATIVE = "authoritative"
    PLAYFUL = "playful"
    DRAMATIC = "dramatic"
    SOOTHING = "soothing"
    ENERGETIC = "energetic"
    MYSTERIOUS = "mysterious"
    ROUGH = "rough"
    SMOOTH = "smooth"
    HUSKY = "husky"
    CLEAR = "clear"


@dataclass
class CharacterProfile:
    """Detailed character profile for a voice"""

    # Basic attributes
    voice_id: str
    name: str
    gender: VoiceGender
    age: VoiceAge
    accent: VoiceAccent
    primary_tone: VoiceTone

    # Personality traits
    personality_traits: List[str]

    # Voice characteristics
    pitch: str  # low, medium, high
    pace: str  # slow, moderate, fast
    energy_level: str  # low, medium, high, very high

    # Best use cases
    best_for: List[str]
    avoid_for: List[str]

    # Character background (for roleplay)
    background: str
    speaking_style: str

    # Recommended settings
    recommended_stability: float
    recommended_similarity: float
    recommended_style: float

    # Sample phrases that work well
    signature_phrases: List[str]

    # Emotional range
    emotional_range: List[str]

    # Additional notes
    notes: Optional[str] = None


# Main Voice Registry
VOICE_REGISTRY: Dict[str, CharacterProfile] = {
    "Rachel": CharacterProfile(
        voice_id="21m00Tcm4TlvDq8ikWAM",
        name="Rachel",
        gender=VoiceGender.FEMALE,
        age=VoiceAge.YOUNG,
        accent=VoiceAccent.AMERICAN,
        primary_tone=VoiceTone.CASUAL,
        personality_traits=["friendly", "enthusiastic", "relatable", "genuine", "approachable"],
        pitch="medium-high",
        pace="moderate",
        energy_level="high",
        best_for=[
            "podcasts",
            "youtube videos",
            "tutorials",
            "vlogs",
            "social media content",
            "casual narration",
            "upbeat commercials",
        ],
        avoid_for=["formal presentations", "serious documentaries", "corporate training"],
        background="Tech-savvy millennial content creator from California",
        speaking_style="Contemporary, uses modern slang naturally, conversational",
        recommended_stability=0.5,
        recommended_similarity=0.75,
        recommended_style=0.5,
        signature_phrases=[
            "Hey guys, welcome back!",
            "Let's dive right in!",
            "That's literally amazing!",
            "Okay, so here's the thing...",
        ],
        emotional_range=["excited", "curious", "surprised", "amused", "empathetic"],
        notes="Perfect for relatable, everyday content. Natural uptalk and vocal fry.",
    ),
    "Clyde": CharacterProfile(
        voice_id="2EiwWnXFnvU5JabPnv8n",
        name="Clyde",
        gender=VoiceGender.MALE,
        age=VoiceAge.MIDDLE_AGED,
        accent=VoiceAccent.AMERICAN,
        primary_tone=VoiceTone.AUTHORITATIVE,
        personality_traits=["intense", "commanding", "determined", "tough", "no-nonsense"],
        pitch="low",
        pace="moderate",
        energy_level="high",
        best_for=[
            "action movie trailers",
            "military content",
            "thriller narration",
            "sports commentary",
            "motivational content",
            "emergency broadcasts",
        ],
        avoid_for=["children's content", "romantic stories", "comedy", "ASMR"],
        background="Former military officer turned action movie narrator",
        speaking_style="Direct, forceful, uses short sentences for impact",
        recommended_stability=0.3,
        recommended_similarity=0.7,
        recommended_style=0.8,
        signature_phrases=["Listen up!", "Time's running out...", "Failure is not an option", "Lock and load"],
        emotional_range=["intense", "angry", "determined", "urgent", "commanding"],
        notes="Excellent for high-tension scenarios. Natural gravel in voice.",
    ),
    "Aria": CharacterProfile(
        voice_id="9BWtsMINqrJLrRacOk9x",
        name="Aria",
        gender=VoiceGender.FEMALE,
        age=VoiceAge.MIDDLE_AGED,
        accent=VoiceAccent.AMERICAN,
        primary_tone=VoiceTone.HUSKY,
        personality_traits=["sultry", "confident", "mysterious", "sophisticated", "alluring"],
        pitch="low",
        pace="slow",
        energy_level="medium",
        best_for=[
            "audiobooks (romance/mystery)",
            "luxury brand ads",
            "jazz radio",
            "meditation guides",
            "late-night radio",
            "film noir narration",
        ],
        avoid_for=["children's content", "high-energy ads", "technical tutorials"],
        background="Jazz lounge singer with a mysterious past",
        speaking_style="Smooth, deliberate, uses pauses effectively",
        recommended_stability=0.6,
        recommended_similarity=0.8,
        recommended_style=0.4,
        signature_phrases=[
            "Well, well, well...",
            "Darling, let me tell you something...",
            "Some secrets are meant to be kept",
            "The night is still young",
        ],
        emotional_range=["seductive", "mysterious", "confident", "contemplative", "amused"],
        notes="Natural breathiness adds intimacy. Great for emotional depth.",
    ),
    "Roger": CharacterProfile(
        voice_id="CwhRBWXzGAHq8TQ4Fs17",
        name="Roger",
        gender=VoiceGender.MALE,
        age=VoiceAge.MATURE,
        accent=VoiceAccent.AMERICAN,
        primary_tone=VoiceTone.PROFESSIONAL,
        personality_traits=["sophisticated", "refined", "knowledgeable", "trustworthy", "distinguished"],
        pitch="medium-low",
        pace="moderate",
        energy_level="medium",
        best_for=[
            "documentaries",
            "corporate presentations",
            "luxury brands",
            "financial services",
            "educational content",
            "museum tours",
        ],
        avoid_for=["youth content", "action scenes", "comedy skits"],
        background="Ivy League professor and former diplomat",
        speaking_style="Articulate, measured, uses perfect grammar",
        recommended_stability=0.7,
        recommended_similarity=0.85,
        recommended_style=0.3,
        signature_phrases=["Consider this...", "As we've established...", "The evidence suggests...", "In my experience..."],
        emotional_range=["thoughtful", "assured", "diplomatic", "concerned", "pleased"],
        notes="Natural authority without being aggressive. Slight mid-Atlantic accent.",
    ),
    "Sarah": CharacterProfile(
        voice_id="EXAVITQu4vr4xnSDxMaL",
        name="Sarah",
        gender=VoiceGender.FEMALE,
        age=VoiceAge.YOUNG,
        accent=VoiceAccent.AMERICAN,
        primary_tone=VoiceTone.PROFESSIONAL,
        personality_traits=["clear", "articulate", "efficient", "pleasant", "reliable"],
        pitch="medium",
        pace="moderate",
        energy_level="medium",
        best_for=[
            "news reading",
            "phone systems",
            "e-learning",
            "audiobooks",
            "medical narration",
            "technical documentation",
            "GPS navigation",
        ],
        avoid_for=["character voices", "emotional scenes", "comedy"],
        background="Network news anchor with broadcast journalism degree",
        speaking_style="Neutral, clear enunciation, minimal personality",
        recommended_stability=0.8,
        recommended_similarity=0.9,
        recommended_style=0.1,
        signature_phrases=[
            "Thank you for calling...",
            "In today's news...",
            "Please follow these instructions...",
            "Turn left in 500 feet",
        ],
        emotional_range=["neutral", "pleasant", "informative", "reassuring"],
        notes="The 'default' professional voice. Very versatile but intentionally bland.",
    ),
    "Laura": CharacterProfile(
        voice_id="FGY2WhTYpPnrIDTdsKH5",
        name="Laura",
        gender=VoiceGender.FEMALE,
        age=VoiceAge.YOUNG,
        accent=VoiceAccent.AMERICAN,
        primary_tone=VoiceTone.PLAYFUL,
        personality_traits=["sassy", "witty", "sarcastic", "fun", "confident"],
        pitch="medium-high",
        pace="fast",
        energy_level="very high",
        best_for=[
            "comedy content",
            "social commentary",
            "reaction videos",
            "teen/young adult content",
            "fashion/beauty",
            "roasts",
        ],
        avoid_for=["serious content", "corporate", "meditation", "formal education"],
        background="Stand-up comedian and social media influencer from New York",
        speaking_style="Quick wit, uses sarcasm, eye-roll energy in voice",
        recommended_stability=0.3,
        recommended_similarity=0.6,
        recommended_style=0.9,
        signature_phrases=[
            "Are you kidding me right now?",
            "Oh honey, no...",
            "Let me get this straight...",
            "I can't even...",
        ],
        emotional_range=["sarcastic", "amused", "exasperated", "excited", "mock-serious"],
        notes="Natural vocal fry and uptalk. Perfect for Gen Z content.",
    ),
    "Charlie": CharacterProfile(
        voice_id="IKne3meq5aSn9XLyUdCD",
        name="Charlie",
        gender=VoiceGender.MALE,
        age=VoiceAge.YOUNG,
        accent=VoiceAccent.AUSTRALIAN,
        primary_tone=VoiceTone.ENERGETIC,
        personality_traits=["hyped", "enthusiastic", "adventurous", "positive", "bro-ish"],
        pitch="medium",
        pace="fast",
        energy_level="very high",
        best_for=[
            "extreme sports",
            "gaming content",
            "travel vlogs",
            "fitness motivation",
            "party announcements",
            "youth marketing",
        ],
        avoid_for=["formal content", "relaxation", "serious topics", "elderly audience"],
        background="Professional surfer and YouTube adventure vlogger from Sydney",
        speaking_style="Lots of 'mate', 'legend', Australian slang, constant energy",
        recommended_stability=0.2,
        recommended_similarity=0.5,
        recommended_style=1.0,
        signature_phrases=["G'day legends!", "This is absolutely mental!", "Let's send it!", "Fair dinkum!"],
        emotional_range=["hyped", "stoked", "amazed", "pumped", "celebratory"],
        notes="Strong Aussie accent. Can sound aggressive if not modulated.",
    ),
    "George": CharacterProfile(
        voice_id="JBFqnCBsd6RMkjVDRZzb",
        name="George",
        gender=VoiceGender.MALE,
        age=VoiceAge.MATURE,
        accent=VoiceAccent.BRITISH,
        primary_tone=VoiceTone.WARM,
        personality_traits=["wise", "comforting", "patient", "grandfatherly", "storyteller"],
        pitch="medium-low",
        pace="slow",
        energy_level="low",
        best_for=[
            "audiobooks",
            "bedtime stories",
            "historical documentaries",
            "nature documentaries",
            "meditation",
            "British content",
        ],
        avoid_for=["action content", "youth marketing", "high-energy ads"],
        background="Retired Oxford professor and BBC documentary narrator",
        speaking_style="Received pronunciation, thoughtful pauses, storytelling cadence",
        recommended_stability=0.8,
        recommended_similarity=0.85,
        recommended_style=0.3,
        signature_phrases=["Let me tell you a story...", "In my day...", "Quite remarkable, really", "As you can imagine..."],
        emotional_range=["warm", "nostalgic", "amused", "concerned", "proud"],
        notes="David Attenborough vibes. Perfect for trust and authority.",
    ),
    "Harry": CharacterProfile(
        voice_id="SOYHLrjzK2X1ezoPC6cr",
        name="Harry",
        gender=VoiceGender.MALE,
        age=VoiceAge.YOUNG,
        accent=VoiceAccent.AMERICAN,
        primary_tone=VoiceTone.ROUGH,
        personality_traits=["rebellious", "edgy", "street-smart", "tough", "authentic"],
        pitch="medium",
        pace="moderate",
        energy_level="medium",
        best_for=[
            "urban content",
            "hip-hop intros",
            "streetwear brands",
            "gaming trash talk",
            "punk/rock content",
            "anti-establishment messaging",
        ],
        avoid_for=["corporate", "children's content", "luxury brands", "formal education"],
        background="Underground rapper and street artist from Brooklyn",
        speaking_style="Urban vernacular, slight rasp, authentic street credibility",
        recommended_stability=0.4,
        recommended_similarity=0.6,
        recommended_style=0.7,
        signature_phrases=["Yo, check it...", "Real talk...", "You feel me?", "That's what's up"],
        emotional_range=["defiant", "confident", "aggressive", "real", "passionate"],
        notes="Natural vocal grit. Don't overdo the 'street' aspect.",
    ),
    "Charlotte": CharacterProfile(
        voice_id="XB0fDUnXU5powFXDhCwa",
        name="Charlotte",
        gender=VoiceGender.FEMALE,
        age=VoiceAge.YOUNG,
        accent=VoiceAccent.SWEDISH,
        primary_tone=VoiceTone.SOOTHING,
        personality_traits=["calm", "gentle", "minimalist", "thoughtful", "serene"],
        pitch="medium",
        pace="slow",
        energy_level="low",
        best_for=[
            "ASMR",
            "meditation",
            "sleep stories",
            "wellness content",
            "Scandinavian brands",
            "spa advertisements",
            "nature content",
        ],
        avoid_for=["high-energy content", "comedy", "urgent announcements"],
        background="Yoga instructor and mindfulness coach from Stockholm",
        speaking_style="Soft, measured, slight Swedish lilt, very peaceful",
        recommended_stability=0.9,
        recommended_similarity=0.9,
        recommended_style=0.1,
        signature_phrases=[
            "Take a deep breath...",
            "Let's find our center...",
            "Feel the calm washing over you...",
            "In this moment...",
        ],
        emotional_range=["peaceful", "gentle", "caring", "contemplative", "content"],
        notes="Subtle accent adds authenticity. Natural breathiness perfect for ASMR.",
    ),
}


def get_voice_profile(name: str) -> Optional[CharacterProfile]:
    """Get a voice profile by name"""
    return VOICE_REGISTRY.get(name)


def get_voices_by_gender(gender: VoiceGender) -> List[CharacterProfile]:
    """Get all voices of a specific gender"""
    return [v for v in VOICE_REGISTRY.values() if v.gender == gender]


def get_voices_by_age(age: VoiceAge) -> List[CharacterProfile]:
    """Get all voices of a specific age group"""
    return [v for v in VOICE_REGISTRY.values() if v.age == age]


def get_voices_by_accent(accent: VoiceAccent) -> List[CharacterProfile]:
    """Get all voices with a specific accent"""
    return [v for v in VOICE_REGISTRY.values() if v.accent == accent]


def get_voices_by_tone(tone: VoiceTone) -> List[CharacterProfile]:
    """Get all voices with a specific primary tone"""
    return [v for v in VOICE_REGISTRY.values() if v.primary_tone == tone]


def get_voice_for_use_case(use_case: str) -> List[CharacterProfile]:
    """Get recommended voices for a specific use case"""
    matches = []
    for voice in VOICE_REGISTRY.values():
        if any(use_case.lower() in uc.lower() for uc in voice.best_for):
            matches.append(voice)
    return matches


def get_all_voice_ids() -> Dict[str, str]:
    """Get simple name-to-ID mapping for backward compatibility"""
    return {name: profile.voice_id for name, profile in VOICE_REGISTRY.items()}


# Export for easy access
VOICE_IDS = get_all_voice_ids()
