"""Advanced prompting techniques for ElevenLabs v3 based on best practices"""

import re
from typing import Dict, List, Optional, Tuple

# Removed unused imports (AUDIO_TAGS, AudioTagCategory)


class PromptOptimizer:
    """Optimize prompts for ElevenLabs v3 synthesis based on best practices"""

    @staticmethod
    def optimize_prompt(text: str, add_pauses: bool = True, enhance_emphasis: bool = True) -> str:
        """
        Optimize prompt for better v3 synthesis

        Args:
            text: Original text
            add_pauses: Add ellipses for natural pauses
            enhance_emphasis: Use capitalization for emphasis

        Returns:
            Optimized text
        """
        result = text

        # Add natural pauses with ellipses
        if add_pauses:
            result = PromptOptimizer._add_natural_pauses(result)

        # Enhance emphasis with capitalization
        if enhance_emphasis:
            result = PromptOptimizer._enhance_emphasis(result)

        return result

    @staticmethod
    def _add_natural_pauses(text: str) -> str:
        """Add ellipses for natural pauses and weight"""
        # Add ellipses before conjunctions for natural pauses
        patterns = [
            (r"\s+(but|however|although|though)\s+", r"... \1 "),
            (r"\s+(well|so|now|then)\s+", r"... \1, "),
        ]

        result = text
        for pattern, replacement in patterns:
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)

        return result

    @staticmethod
    def _enhance_emphasis(text: str) -> str:
        """Use strategic capitalization for emphasis"""
        # Capitalize important words for emphasis
        emphasis_words = ["important", "critical", "essential", "amazing", "incredible"]

        result = text
        for word in emphasis_words:
            pattern = r"\b" + word + r"\b"
            result = re.sub(pattern, word.upper(), result, flags=re.IGNORECASE)

        return result


class DialogueFormatter:
    """Format multi-speaker dialogue according to v3 best practices"""

    @staticmethod
    def format_dialogue(speakers: List[Tuple[str, str, Optional[str]]]) -> str:
        """
        Format dialogue with speaker labels and emotions

        Args:
            speakers: List of (speaker_name, text, emotion) tuples

        Returns:
            Formatted dialogue text
        """
        lines = []

        for speaker_name, text, emotion in speakers:
            if emotion:
                line = f"{speaker_name}: [{emotion}] {text}"
            else:
                line = f"{speaker_name}: {text}"
            lines.append(line)

        return "\n".join(lines)

    @staticmethod
    def add_dialogue_tags(text: str, speaker: str, emotion: Optional[str] = None, action: Optional[str] = None) -> str:
        """
        Add dialogue tags for character performance

        Args:
            text: Dialogue text
            speaker: Speaker name
            emotion: Emotional state
            action: Physical action

        Returns:
            Tagged dialogue
        """
        parts = []

        if emotion:
            parts.append(f"[{emotion}]")

        if action:
            parts.append(f"[{action}]")

        if parts:
            return f"{speaker}: {' '.join(parts)} {text}"
        else:
            return f"{speaker}: {text}"


class EmotionalEnhancer:
    """Enhance text with emotional depth using v3 capabilities"""

    # Emotion to tag mapping with intensity levels
    EMOTION_TAGS = {
        "joy": {"subtle": "[cheerfully]", "moderate": "[happily]", "intense": "[excitedly]"},
        "sadness": {"subtle": "[sadly]", "moderate": "[sorrowfully]", "intense": "[crying]"},
        "anger": {"subtle": "[annoyed]", "moderate": "[angry]", "intense": "[furiously]"},
        "fear": {"subtle": "[nervously]", "moderate": "[anxiously]", "intense": "[terrified]"},
        "surprise": {"subtle": "[curious]", "moderate": "[surprised]", "intense": "[gasps][shocked]"},
    }

    @staticmethod
    def enhance_with_emotion(text: str, emotion: str, intensity: str = "moderate") -> str:
        """
        Enhance text with appropriate emotional tags

        Args:
            text: Original text
            emotion: Base emotion (joy, sadness, anger, fear, surprise)
            intensity: Intensity level (subtle, moderate, intense)

        Returns:
            Emotionally enhanced text
        """
        if emotion not in EmotionalEnhancer.EMOTION_TAGS:
            return text

        emotion_map = EmotionalEnhancer.EMOTION_TAGS[emotion]
        if intensity not in emotion_map:
            intensity = "moderate"

        tag = emotion_map[intensity]
        return f"{tag} {text}"

    @staticmethod
    def add_emotional_progression(text: str, start_emotion: str, end_emotion: str, transition_point: float = 0.5) -> str:
        """
        Add emotional progression through the text

        Args:
            text: Original text
            start_emotion: Starting emotion
            end_emotion: Ending emotion
            transition_point: Where to transition (0.0 to 1.0)

        Returns:
            Text with emotional progression
        """
        sentences = text.split(". ")
        if len(sentences) < 2:
            return EmotionalEnhancer.enhance_with_emotion(text, start_emotion)

        transition_index = int(len(sentences) * transition_point)

        result = []
        for i, sentence in enumerate(sentences):
            if i < transition_index:
                emotion = start_emotion
            else:
                emotion = end_emotion

            enhanced = EmotionalEnhancer.enhance_with_emotion(sentence, emotion)
            result.append(enhanced)

        return ". ".join(result)


class NaturalSpeechEnhancer:
    """Make synthesized speech sound more natural"""

    @staticmethod
    def add_speech_imperfections(
        text: str, add_hesitations: bool = True, add_breathing: bool = True, add_filler_words: bool = False
    ) -> str:
        """
        Add natural speech imperfections for realism

        Args:
            text: Original text
            add_hesitations: Add hesitation tags
            add_breathing: Add breathing pauses
            add_filler_words: Add filler words like "um", "uh"

        Returns:
            More natural sounding text
        """
        result = text

        if add_hesitations:
            # Add occasional hesitations
            result = re.sub(r"(\b(?:should|could|would|might)\b)", r"\1... [hesitates]", result, count=1)

        if add_breathing:
            # Add breathing pauses at long sentence breaks
            sentences = result.split(". ")
            if len(sentences) > 3:
                # Add breath after every 3rd sentence
                for i in range(2, len(sentences), 3):
                    sentences[i] = sentences[i] + " [breathes]"
                result = ". ".join(sentences)

        if add_filler_words:
            # Add occasional filler words
            result = re.sub(r"(\bI think\b)", r"\1, um,", result, count=1)

        return result

    @staticmethod
    def add_conversational_markers(text: str) -> str:
        """Add conversational markers for natural dialogue"""
        markers = {
            r"^": "[clears throat] ",  # Start with throat clear
            r"\?$": "? [pause]",  # Pause after questions
            r"!$": "! [excited]",  # Excitement after exclamations
        }

        result = text
        for pattern, replacement in markers.items():
            result = re.sub(pattern, replacement, result)

        return result


class VoiceDirector:
    """Direct voice performance using v3 capabilities"""

    @staticmethod
    def create_character_voice(
        text: str, character_type: str = "narrator", accent: Optional[str] = None, speaking_style: Optional[str] = None
    ) -> str:
        """
        Create character voice with specific traits

        Args:
            text: Original text
            character_type: Type of character (narrator, hero, villain, etc.)
            accent: Optional accent
            speaking_style: Speaking style (fast, slow, dramatic, etc.)

        Returns:
            Directed text
        """
        tags = []

        # Character type directions
        character_directions = {
            "narrator": "[narrating]",
            "hero": "[confidently]",
            "villain": "[menacingly]",
            "child": "[excitedly][high pitched]",
            "elder": "[slowly][wisely]",
            "robot": "[monotone]",
            "mysterious": "[mysteriously][whispers]",
        }

        if character_type in character_directions:
            tags.append(character_directions[character_type])

        # Add accent if specified
        if accent:
            tags.append(f"[{accent} accent]")

        # Add speaking style
        style_tags = {
            "fast": "[rapid-fire]",
            "slow": "[deliberately]",
            "dramatic": "[dramatically]",
            "casual": "[casually]",
            "formal": "[formally]",
        }

        if speaking_style in style_tags:
            tags.append(style_tags[speaking_style])

        if tags:
            return f"{' '.join(tags)} {text}"
        return text

    @staticmethod
    def add_scene_ambience(text: str, environment: str = "quiet") -> str:
        """
        Add environmental context to speech

        Args:
            text: Original text
            environment: Environment type

        Returns:
            Text with environmental context
        """
        environment_tags = {
            "loud": "[SHOUTING] ",
            "quiet": "[whispers] ",
            "windy": "[wind] [speaking loudly] ",
            "rain": "[rain] ",
            "crowd": "[crowd noise] [speaking clearly] ",
            "echo": "[echo effect] ",
        }

        if environment in environment_tags:
            return environment_tags[environment] + text
        return text


class TagCombiner:
    """Intelligently combine multiple audio tags"""

    @staticmethod
    def combine_tags(tags: List[str], validate: bool = True) -> str:
        """
        Combine multiple tags intelligently

        Args:
            tags: List of tags to combine
            validate: Check for conflicts

        Returns:
            Combined tag string
        """
        if not tags:
            return ""

        if validate:
            tags = TagCombiner._filter_conflicts(tags)

        # Order tags by category for better effect
        ordered = TagCombiner._order_tags(tags)

        return " ".join(ordered)

    @staticmethod
    def _filter_conflicts(tags: List[str]) -> List[str]:
        """Remove conflicting tags"""
        conflicts = [
            (["[whispers]", "[WHISPER]"], ["[SHOUTING]", "[shouts]"]),
            (["[happy]", "[cheerfully]"], ["[sad]", "[crying]"]),
            (["[rushed]", "[rapid-fire]"], ["[slowly]", "[deliberately]"]),
        ]

        filtered = tags.copy()
        for group1, group2 in conflicts:
            has_group1 = any(tag in filtered for tag in group1)
            has_group2 = any(tag in filtered for tag in group2)

            if has_group1 and has_group2:
                # Remove group2 if both present
                for tag in group2:
                    if tag in filtered:
                        filtered.remove(tag)

        return filtered

    @staticmethod
    def _order_tags(tags: List[str]) -> List[str]:
        """Order tags by category for optimal effect"""
        # Define category order
        category_order = {"emotion": 1, "delivery": 2, "pacing": 3, "accent": 4, "reaction": 5, "environmental": 6}

        # Categorize tags
        categorized: Dict[str, List[str]] = {}
        for tag in tags:
            category = TagCombiner._get_tag_category(tag)
            if category not in categorized:
                categorized[category] = []
            categorized[category].append(tag)

        # Sort by category order
        ordered = []
        for category in sorted(categorized.keys(), key=lambda x: category_order.get(x, 999)):
            ordered.extend(categorized[category])

        return ordered

    @staticmethod
    def _get_tag_category(tag: str) -> str:
        """Determine category of a tag"""
        tag_lower = tag.lower()

        if any(word in tag_lower for word in ["happy", "sad", "angry", "excited"]):
            return "emotion"
        elif any(word in tag_lower for word in ["whisper", "shout", "murmur"]):
            return "delivery"
        elif any(word in tag_lower for word in ["rushed", "slow", "deliberate"]):
            return "pacing"
        elif "accent" in tag_lower:
            return "accent"
        elif any(word in tag_lower for word in ["laugh", "sigh", "gasp", "cry"]):
            return "reaction"
        elif any(word in tag_lower for word in ["gunshot", "explosion", "rain"]):
            return "environmental"

        return "other"
