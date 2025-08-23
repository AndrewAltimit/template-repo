"""Eleven v3 optimization based on official documentation insights."""

import re
from typing import Dict, List, Optional, Tuple

from .voice_catalog import VOICE_CATALOG, VoiceCharacter


class V3OptimizationEngine:
    """Optimize text and settings for Eleven v3 based on best practices."""
    
    # Minimum recommended character count for v3 stability
    MIN_CHAR_COUNT = 250
    
    # Enhanced audio tags based on documentation
    AUDIO_TAGS = {
        # Voice-related emotions
        "laughs": ["laughs", "laughs harder", "starts laughing", "wheezing"],
        "whispers": ["whispers"],
        "sighs": ["sighs", "exhales"],
        "emotions": ["sarcastic", "curious", "excited", "crying", "snorts", "mischievously"],
        
        # Professional/technical emotions for code reviews
        "professional": ["professional", "analytical", "thoughtful", "concerned"],
        "reactions": ["impressed", "frustrated", "amazed", "delighted", "alarmed"],
        "states": ["nervously", "sheepishly", "desperately", "warmly", "sympathetically"],
        
        # Timing and delivery
        "pauses": ["pauses", "pause", "short pause"],
        "speed": ["quickly", "slowly", "deliberately"],
        
        # Sound effects (use sparingly in reviews)
        "sounds": ["clears throat", "gulps", "swallows"],
        
        # Special
        "accents": ["strong X accent"],  # Replace X with accent
        "vocal": ["sings", "woo"],
    }
    
    # Voice personality to compatible tags mapping
    VOICE_TAG_COMPATIBILITY = {
        "blondie": {  # Warm, conversational
            "compatible": ["laughs", "sighs", "curious", "excited", "warmly", "thoughtful"],
            "incompatible": ["shouting", "crying", "desperately"],
        },
        "hope_conversational": {  # Natural with imperfections
            "compatible": ["laughs", "giggles", "curious", "friendly", "nervous", "excited"],
            "incompatible": ["professional", "authoritative", "dramatic"],
        },
        "old_radio": {  # Distinguished, theatrical
            "compatible": ["dramatic", "authoritative", "serious", "concerned", "clears throat"],
            "incompatible": ["giggles", "mischievously", "cute"],
        },
        "peter": {  # Clear, educational
            "compatible": ["professional", "analytical", "thoughtful", "explaining"],
            "incompatible": ["laughs harder", "wheezing", "crying"],
        },
        "tia": {  # Direct, commanding
            "compatible": ["serious", "firm", "direct", "urgent", "frustrated"],
            "incompatible": ["giggles", "whispers", "cute", "mischievously"],
        },
    }
    
    @classmethod
    def optimize_text_length(cls, text: str) -> str:
        """Ensure text meets minimum character requirements for v3 stability.
        
        Args:
            text: Input text
            
        Returns:
            Text padded or enhanced if needed
        """
        if len(text) >= cls.MIN_CHAR_COUNT:
            return text
        
        # Add natural padding with context
        padding_templates = [
            "\n\n[pause] Let me elaborate on these findings.",
            "\n\n[thoughtful] To provide more context on this review:",
            "\n\n[analytical] Here's a detailed breakdown of the key points:",
        ]
        
        # Add appropriate padding based on content
        if "error" in text.lower() or "fail" in text.lower():
            padding = "\n\n[concerned] These issues require careful attention to ensure code quality."
        elif "good" in text.lower() or "excellent" in text.lower():
            padding = "\n\n[impressed] This demonstrates strong development practices and attention to detail."
        else:
            padding = padding_templates[0]
        
        enhanced_text = text + padding
        
        # If still too short, add more context
        if len(enhanced_text) < cls.MIN_CHAR_COUNT:
            enhanced_text += "\n\n[professional] I've analyzed the code thoroughly and these are my findings based on best practices and code quality standards."
        
        return enhanced_text
    
    @classmethod
    def enhance_punctuation(cls, text: str) -> str:
        """Enhance punctuation for better v3 delivery.
        
        Args:
            text: Input text
            
        Returns:
            Text with optimized punctuation
        """
        # Add ellipses for natural pauses
        text = re.sub(r'\.\s+However', '... However', text)
        text = re.sub(r'\.\s+But', '... But', text)
        text = re.sub(r':\s*\n', ':\n\n', text)  # Add pause after colons
        
        # Capitalize key words for emphasis
        emphasis_words = {
            'critical': 'CRITICAL',
            'urgent': 'URGENT',
            'must': 'MUST',
            'not': 'NOT',
            'never': 'NEVER',
            'always': 'ALWAYS',
            'important': 'IMPORTANT',
            'excellent': 'EXCELLENT',
            'perfect': 'PERFECT',
        }
        
        for word, replacement in emphasis_words.items():
            # Only replace if it's a standalone word
            text = re.sub(rf'\b{word}\b', replacement, text, flags=re.IGNORECASE)
        
        return text
    
    @classmethod
    def validate_tag_compatibility(cls, text: str, voice_key: str) -> Tuple[str, List[str]]:
        """Validate and adjust tags based on voice compatibility.
        
        Args:
            text: Text with audio tags
            voice_key: Voice identifier
            
        Returns:
            Tuple of (adjusted_text, warnings)
        """
        warnings = []
        adjusted_text = text
        
        # Get voice compatibility
        compatibility = cls.VOICE_TAG_COMPATIBILITY.get(voice_key, {})
        incompatible_tags = compatibility.get("incompatible", [])
        
        # Check for incompatible tags
        for tag in incompatible_tags:
            if f"[{tag}]" in text:
                warnings.append(f"Tag [{tag}] may not work well with {voice_key} voice")
                # Replace with compatible alternative
                if tag == "giggles" and voice_key == "old_radio":
                    adjusted_text = adjusted_text.replace("[giggles]", "[amused]")
                elif tag == "whispers" and voice_key == "tia":
                    adjusted_text = adjusted_text.replace("[whispers]", "[quietly but firmly]")
        
        return adjusted_text, warnings
    
    @classmethod
    def structure_for_emotion(cls, text: str, emotions: List[str]) -> str:
        """Structure text optimally for emotional delivery.
        
        Args:
            text: Input text
            emotions: List of emotions to apply
            
        Returns:
            Structured text with proper spacing and tags
        """
        # Split into sentences
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        # Group sentences by emotion transitions
        structured_parts = []
        emotion_index = 0
        
        for i, sentence in enumerate(sentences):
            if not sentence.strip():
                continue
            
            # Add emotion tag at the beginning of each section
            emotion = emotions[emotion_index % len(emotions)] if emotions else "professional"
            
            # Add line breaks between emotional transitions
            if i > 0 and emotion != emotions[(emotion_index - 1) % len(emotions)]:
                structured_parts.append("")  # Empty line for pause
            
            # Format the sentence with emotion
            if not sentence.startswith("["):  # Don't double-tag
                sentence = f"[{emotion}] {sentence}"
            
            structured_parts.append(sentence)
            
            # Progress emotion every 2-3 sentences for variety
            if i % 2 == 1:
                emotion_index += 1
        
        return "\n\n".join(structured_parts)
    
    @classmethod
    def get_optimal_settings(cls, voice_key: str, content_type: str) -> Dict:
        """Get optimal v3 settings based on voice and content.
        
        Args:
            voice_key: Voice identifier
            content_type: Type of content (review, broadcast, documentation)
            
        Returns:
            Optimal settings dictionary
        """
        # Base settings from documentation
        settings_map = {
            "review": {
                "stability": 0.3,  # Natural - balanced emotion
                "similarity_boost": 0.75,
                "style": 0.3,
                "use_speaker_boost": False,
            },
            "broadcast": {
                "stability": 0.1,  # Creative - maximum expression
                "similarity_boost": 0.75,
                "style": 0.5,
                "use_speaker_boost": True,
            },
            "documentation": {
                "stability": 0.9,  # Robust - consistent delivery
                "similarity_boost": 0.75,
                "style": 0.0,
                "use_speaker_boost": False,
            },
        }
        
        settings = settings_map.get(content_type, settings_map["review"])
        
        # Adjust for specific voices
        if voice_key == "blondie" or voice_key == "hope_conversational":
            # These voices work best with lower stability for expression
            settings["stability"] = max(0.0, settings["stability"] - 0.1)
            settings["use_speaker_boost"] = True
        elif voice_key == "peter" or voice_key == "jane":
            # Professional voices need higher stability
            settings["stability"] = min(0.9, settings["stability"] + 0.2)
        elif voice_key == "old_radio":
            # Theatrical voice needs room for drama
            settings["stability"] = 0.0  # Maximum creative freedom
            settings["style"] = 0.6
        
        return settings
    
    @classmethod
    def create_multi_speaker_dialogue(
        cls,
        exchanges: List[Tuple[str, str, str]],  # (speaker, emotion, text)
    ) -> str:
        """Create properly formatted multi-speaker dialogue.
        
        Args:
            exchanges: List of (speaker_name, emotion, text) tuples
            
        Returns:
            Formatted dialogue text
        """
        dialogue_parts = []
        
        for i, (speaker, emotion, text) in enumerate(exchanges):
            # Add speaker label
            line = f"Speaker {speaker}: [{emotion}] {text}"
            
            # Add timing tags for natural conversation
            if i > 0:
                # Check for interruptions or overlaps
                if "wait" in text.lower() or "sorry" in text.lower():
                    line = f"Speaker {speaker}: [jumping in] [{emotion}] {text}"
                elif "?" in exchanges[i-1][2]:  # Previous was a question
                    line = f"Speaker {speaker}: [responding] [{emotion}] {text}"
            
            dialogue_parts.append(line)
        
        return "\n\n".join(dialogue_parts)
    
    @classmethod
    def add_natural_imperfections(cls, text: str, voice_character: str) -> str:
        """Add natural speech imperfections for realism.
        
        Args:
            text: Input text
            voice_character: Voice character type
            
        Returns:
            Text with natural imperfections
        """
        # Only for conversational voices
        if voice_character not in ["hope_conversational", "blondie", "cassidy"]:
            return text
        
        # Add occasional hesitations
        text = re.sub(r'\bI think\b', 'I... think', text, count=1)
        text = re.sub(r'\bWell\b', 'Well...', text, count=1)
        
        # Add verbal fillers for Hope
        if voice_character == "hope_conversational":
            text = re.sub(r'\. ([A-Z])', r'. Um, \1', text, count=1)  # Add one "um"
            text = text.replace("interesting", "like, really interesting")
        
        return text


class V3ReviewFormatter:
    """Format code reviews specifically for v3 optimal delivery."""
    
    @classmethod
    def format_review(
        cls,
        review_text: str,
        agent_name: str,
        severity: str = "normal"
    ) -> str:
        """Format a code review for optimal v3 delivery.
        
        Args:
            review_text: Original review text
            agent_name: Agent name for voice selection
            severity: Review severity (normal, critical, positive)
            
        Returns:
            Formatted review optimized for v3
        """
        # Get voice for agent
        from .voice_catalog import AGENT_PERSONALITY_MAPPING
        voice_key = AGENT_PERSONALITY_MAPPING.get(agent_name, {}).get("default", "blondie")
        
        # Optimize text length
        optimized = V3OptimizationEngine.optimize_text_length(review_text)
        
        # Enhance punctuation
        optimized = V3OptimizationEngine.enhance_punctuation(optimized)
        
        # Add appropriate emotions based on severity
        if severity == "critical":
            emotions = ["concerned", "serious", "urgent"]
        elif severity == "positive":
            emotions = ["impressed", "excited", "happy"]
        else:
            emotions = ["thoughtful", "analytical", "professional"]
        
        # Structure for emotion
        optimized = V3OptimizationEngine.structure_for_emotion(optimized, emotions)
        
        # Validate tag compatibility
        optimized, warnings = V3OptimizationEngine.validate_tag_compatibility(optimized, voice_key)
        
        # Add natural imperfections for certain voices
        if voice_key in ["hope_conversational", "blondie"]:
            optimized = V3OptimizationEngine.add_natural_imperfections(optimized, voice_key)
        
        return optimized