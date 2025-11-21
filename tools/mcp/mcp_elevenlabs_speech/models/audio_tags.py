"""Audio tag definitions and combinations for ElevenLabs v3"""

import re
from enum import Enum
from typing import Any, Dict, List, Optional


class AudioTagCategory(Enum):
    """Categories of audio tags"""

    EMOTIONS = "emotions"
    REACTIONS = "reactions"
    DELIVERY = "delivery"
    ACCENTS = "accents"
    ENVIRONMENTAL = "environmental"
    CONVERSATION = "conversation"
    EMPHASIS = "emphasis"
    PACING = "pacing"


# Comprehensive audio tag definitions
AUDIO_TAGS: Dict[AudioTagCategory, Dict[str, str]] = {
    AudioTagCategory.EMOTIONS: {
        "happy": "[happy]",
        "sad": "[sad]",
        "angry": "[angry]",
        "excited": "[excited]",
        "nervous": "[nervous]",
        "sorrowful": "[sorrowful]",
        "cheerful": "[cheerfully]",
        "playful": "[playfully]",
        "regretful": "[regretful]",
        "resigned": "[resigned tone]",
        "deadpan": "[deadpan]",
        "flatly": "[flatly]",
        "curious": "[curious]",
        "confused": "[confused]",
        "thoughtful": "[thoughtfully]",
        "sarcastic": "[sarcastic]",
        "tired": "[tired]",
    },
    AudioTagCategory.REACTIONS: {
        "laugh": "[laughs]",
        "laugh_hard": "[laughs harder]",
        "start_laughing": "[starts laughing]",
        "wheeze": "[wheezing]",
        "chuckle": "[chuckles]",
        "giggle": "[giggles]",
        "sigh": "[sighs]",
        "sigh_heavy": "[SIGH]",
        "cry": "[crying]",
        "sob": "[sobbing]",
        "clear_throat": "[clears throat]",
        "gulp": "[gulps]",
        "gasp": "[gasp]",
        "gasps": "[gasps]",
        "hesitate": "[hesitates]",
        "stammer": "[stammers]",
        "breathe": "[breathes]",
        "sniff": "[sniffs]",
        "groan": "[groans]",
        "scoff": "[scoffs]",
    },
    AudioTagCategory.DELIVERY: {
        "whisper": "[WHISPER]",
        "whispers": "[whispers]",
        "shout": "[SHOUTING]",
        "shouts": "[shouts]",
        "yell": "[yelling]",
        "murmur": "[murmuring]",
        "mutter": "[mutters]",
        "exclaim": "[exclaims]",
        "announce": "[announcing]",
        "narrate": "[narrating]",
    },
    AudioTagCategory.PACING: {
        "rushed": "[rushed]",
        "slow": "[slows down]",
        "deliberate": "[deliberate]",
        "rapid": "[rapid-fire]",
        "drawn_out": "[drawn out]",
        "pause": "[pause]",
        "beat": "[continues after a beat]",
        "timid": "[timidly]",
        "confident": "[confidently]",
        "uncertain": "[uncertainly]",
    },
    AudioTagCategory.ACCENTS: {
        "american": "[American accent]",
        "british": "[British accent]",
        "southern": "[Southern US accent]",
        "french": "[French accent]",
        "australian": "[Australian accent]",
        "irish": "[Irish accent]",
        "scottish": "[Scottish accent]",
        "german": "[German accent]",
        "italian": "[Italian accent]",
        "spanish": "[Spanish accent]",
        "russian": "[Russian accent]",
        "pirate": "[pirate voice]",
        "robot": "[robot voice]",
    },
    AudioTagCategory.ENVIRONMENTAL: {
        "gunshot": "[gunshot]",
        "clapping": "[clapping]",
        "explosion": "[explosion]",
        "door_slam": "[door slam]",
        "footsteps": "[footsteps]",
        "thunder": "[thunder]",
        "wind": "[wind]",
        "rain": "[rain]",
    },
    AudioTagCategory.CONVERSATION: {
        "interrupt": "[interrupting]",
        "overlap": "[overlapping]",
        "aside": "[aside]",
        "to_audience": "[to audience]",
        "thinking": "[thinking aloud]",
    },
    AudioTagCategory.EMPHASIS: {
        "emphasized": "[emphasized]",
        "stress": "[stress on next word]",
        "understated": "[understated]",
        "dramatic": "[dramatically]",
        "casual": "[casually]",
    },
}


# Tag combinations for common scenarios
TAG_COMBINATIONS = {
    "nervous_whisper": "[nervously][whispers]",
    "excited_shout": "[excited][shouts]",
    "sad_sigh": "[sad][sighs]",
    "happy_laugh": "[happily][laughs]",
    "angry_yell": "[angry][yelling]",
    "tired_mumble": "[tired][murmuring]",
    "sarcastic_slow": "[sarcastic][slows down]",
    "confused_hesitate": "[confused][hesitates]",
    "dramatic_pause": "[dramatically][pause]",
    "cheerful_announce": "[cheerfully][announcing]",
    "regretful_sigh": "[regretful][sighs]",
    "thoughtful_pause": "[thoughtfully][pause]",
    "nervous_stammer": "[nervously][stammers]",
    "excited_rapid": "[excited][rapid-fire]",
    "sad_cry": "[sad][crying][slows down]",
    "happy_shout_laugh": "[happily][shouts][laughs]",
    "whisper_confused": "[WHISPER][confused]",
    "dramatic_gasp": "[dramatically][gasps]",
}


def parse_audio_tags(text: str) -> Dict[str, Any]:
    """
    Parse audio tags from text and return analysis

    Args:
        text: Text potentially containing audio tags

    Returns:
        Dictionary with:
        - tags_found: List of tags found
        - categories_used: Set of categories
        - clean_text: Text with tags removed
        - tag_positions: List of (tag, start_pos, end_pos)
    """
    tags_found = []
    categories_used = set()
    tag_positions = []

    # Find all tags using regex
    tag_pattern = r"\[[^\]]+\]"
    matches = re.finditer(tag_pattern, text)

    for match in matches:
        tag = match.group(0)
        start = match.start()
        end = match.end()
        tag_positions.append((tag, start, end))
        tags_found.append(tag)

        # Identify category
        for category, tags_dict in AUDIO_TAGS.items():
            if tag in tags_dict.values():
                categories_used.add(category)
                break

    # Create clean text (without tags)
    clean_text = re.sub(tag_pattern, "", text).strip()
    # Clean up extra spaces
    clean_text = re.sub(r"\s+", " ", clean_text)

    return {
        "tags_found": tags_found,
        "categories_used": categories_used,
        "clean_text": clean_text,
        "tag_positions": tag_positions,
        "has_tags": len(tags_found) > 0,
    }


def validate_tag_compatibility(tags: List[str]) -> Dict[str, Any]:
    """
    Check if tags are compatible with each other

    Args:
        tags: List of audio tags

    Returns:
        Dictionary with validation results
    """
    issues: List[str] = []
    warnings = []

    # Check for conflicting delivery styles
    delivery_tags = [t for t in tags if t in ["[WHISPER]", "[whispers]", "[SHOUTING]", "[shouts]", "[yelling]"]]
    if len(delivery_tags) > 1:
        warnings.append(f"Multiple delivery styles: {delivery_tags}")

    # Check for conflicting emotions
    emotion_tags = []
    for tag in tags:
        for emotion_tag in AUDIO_TAGS[AudioTagCategory.EMOTIONS].values():
            if tag == emotion_tag:
                emotion_tags.append(tag)

    if "[happy]" in emotion_tags and "[sad]" in emotion_tags:
        warnings.append("Conflicting emotions: happy and sad")

    # Check for too many tags (can affect quality)
    if len(tags) > 5:
        warnings.append(f"Many tags ({len(tags)}) may affect synthesis quality")

    return {"valid": len(issues) == 0, "issues": issues, "warnings": warnings, "tag_count": len(tags)}


def suggest_tags(text: str, context: Optional[str] = None) -> List[str]:
    """
    Suggest appropriate audio tags based on text content

    Args:
        text: The text to analyze
        context: Optional context (e.g., "github_review", "audiobook")

    Returns:
        List of suggested tags
    """
    suggestions = []
    text_lower = text.lower()

    # Emotion detection
    if "!" in text and text.count("!") > 1:
        suggestions.append("[excited]")
    elif "?" in text and any(word in text_lower for word in ["why", "how", "what"]):
        suggestions.append("[curious]")
    elif "..." in text:
        suggestions.append("[thoughtfully]")

    # Reaction detection
    if "haha" in text_lower or "lol" in text_lower:
        suggestions.append("[laughs]")
    elif any(word in text_lower for word in ["oh no", "oops", "uh oh"]):
        suggestions.append("[gasps]")
    elif "hmm" in text_lower:
        suggestions.append("[thoughtfully]")

    # Context-specific suggestions
    if context == "github_review":
        if "great" in text_lower or "excellent" in text_lower:
            suggestions.append("[cheerfully]")
        elif "concern" in text_lower or "issue" in text_lower:
            suggestions.append("[thoughtfully]")
        elif "bug" in text_lower or "error" in text_lower:
            suggestions.append("[concerned]")

    return list(set(suggestions))  # Remove duplicates


def create_expressive_text(
    text: str, emotion: Optional[str] = None, delivery: Optional[str] = None, reactions: Optional[List[str]] = None
) -> str:
    """
    Create expressive text with appropriate audio tags

    Args:
        text: Base text
        emotion: Emotion to apply
        delivery: Delivery style
        reactions: List of reactions to include

    Returns:
        Text with audio tags inserted
    """
    result = text

    # Add emotion at the beginning
    if emotion and emotion in AUDIO_TAGS[AudioTagCategory.EMOTIONS]:
        tag = AUDIO_TAGS[AudioTagCategory.EMOTIONS][emotion]
        result = f"{tag} {result}"

    # Add delivery style
    if delivery and delivery in AUDIO_TAGS[AudioTagCategory.DELIVERY]:
        tag = AUDIO_TAGS[AudioTagCategory.DELIVERY][delivery]
        result = f"{tag} {result}"

    # Add reactions at appropriate points
    if reactions:
        for reaction in reactions:
            if reaction in AUDIO_TAGS[AudioTagCategory.REACTIONS]:
                tag = AUDIO_TAGS[AudioTagCategory.REACTIONS][reaction]
                # Add reaction at a natural break point (period, comma, etc.)
                # This is simplified - could be more sophisticated
                if "." in result:
                    parts = result.split(".", 1)
                    result = f"{parts[0]}. {tag} {parts[1] if len(parts) > 1 else ''}"

    return result.strip()
