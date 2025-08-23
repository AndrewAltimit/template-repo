"""TTS integration for agent reviews with emotional context."""

import logging
import os
import re
from typing import Dict, List, Optional, Tuple

import httpx

from .v3_agent_guide import V3AgentGuide
from .voice_profiles import get_voice_profile, get_voice_settings

logger = logging.getLogger(__name__)


class TTSIntegration:
    """Integrate ElevenLabs TTS with GitHub AI agents for audio reviews."""

    # Emotion keywords and their audio tags
    EMOTION_MAPPING = {
        # Positive emotions
        "impressed": "[impressed]",
        "happy": "[happy]",
        "excited": "[excited]",
        "pleased": "[pleased]",
        "satisfied": "[satisfied]",
        # Negative emotions
        "concerned": "[concerned]",
        "disappointed": "[disappointed]",
        "annoyed": "[annoyed]",
        "frustrated": "[frustrated]",
        # Neutral/thoughtful
        "thoughtful": "[thoughtful]",
        "curious": "[curious]",
        "confused": "[confused]",
        "hesitant": "[hesitant]",
        # Professional
        "professional": "[professional]",
        "serious": "[serious]",
        "urgent": "[urgent]",
    }

    # Keywords to emotion mapping for automatic detection
    KEYWORD_TO_EMOTION = {
        # Positive indicators
        "impressive": "impressed",
        "excellent": "happy",
        "great": "happy",
        "good job": "pleased",
        "well done": "pleased",
        "perfect": "excited",
        "amazing": "excited",
        # Negative indicators
        "failing": "concerned",
        "error": "concerned",
        "issue": "concerned",
        "problem": "concerned",
        "blocker": "annoyed",
        "critical": "urgent",
        "bug": "disappointed",
        "wrong": "disappointed",
        # Neutral indicators
        "however": "thoughtful",
        "but": "thoughtful",
        "consider": "thoughtful",
        "suggest": "thoughtful",
        "recommend": "professional",
        "should": "professional",
    }

    def __init__(self, config: Optional[Dict] = None):
        """Initialize TTS integration.

        Args:
            config: Optional configuration dict
        """
        self.config = config or {}
        self.mcp_base_url = os.getenv("ELEVENLABS_MCP_URL", "http://localhost:8018")
        self.api_key = os.getenv("ELEVENLABS_API_KEY")

        # Check if TTS should be enabled
        self.enabled = self._is_tts_enabled()

        # Only log warning if TTS was explicitly enabled but no API key
        if self.enabled and not self.api_key:
            logger.info("TTS enabled but no ELEVENLABS_API_KEY found - will use MCP server's configured key")

    def _is_tts_enabled(self) -> bool:
        """Check if TTS is enabled via environment or config."""
        # Check environment variable first
        env_enabled = os.getenv("AGENT_TTS_ENABLED", "false").lower() == "true"

        # Check config
        config_enabled = self.config.get("tts", {}).get("enabled", False)

        return env_enabled or config_enabled

    def analyze_sentiment(self, text: str) -> List[str]:
        """Analyze text sentiment and return appropriate emotions.

        Args:
            text: Text to analyze

        Returns:
            List of detected emotions
        """
        emotions = []
        text_lower = text.lower()

        # Check for keyword matches
        for keyword, emotion in self.KEYWORD_TO_EMOTION.items():
            if keyword in text_lower and emotion not in emotions:
                emotions.append(emotion)

        # Default to professional if no emotions detected
        if not emotions:
            emotions = ["professional"]

        # Limit to 3 emotions max
        return emotions[:3]

    def extract_key_sentences(self, review_text: str, max_sentences: int = 3) -> str:
        """Extract key sentences from review for TTS.

        Args:
            review_text: Full review text
            max_sentences: Maximum number of sentences to extract

        Returns:
            Extracted key sentences
        """
        # Split into sections
        sections = review_text.split("\n\n")
        key_sentences = []

        # Priority patterns for important sentences
        priority_patterns = [
            r"^(Overall|In summary|My primary|The main)",
            r"(critical|blocker|must|should|recommend)",
            r"(impressive|excellent|well.?done|great)",
        ]

        for section in sections:
            # Skip headers and lists
            if section.startswith("#") or section.startswith("-") or section.startswith("*"):
                continue

            # Split into sentences
            sentences = re.split(r"(?<=[.!?])\s+", section)

            for sentence in sentences:
                sentence = sentence.strip()
                if not sentence or len(sentence) < 20:
                    continue

                # Check priority patterns
                for pattern in priority_patterns:
                    if re.search(pattern, sentence, re.IGNORECASE):
                        if sentence not in key_sentences:
                            key_sentences.append(sentence)
                            if len(key_sentences) >= max_sentences:
                                return " ".join(key_sentences)

        # If not enough priority sentences, take first sentences
        for section in sections:
            if section.startswith("#") or section.startswith("-"):
                continue

            sentences = re.split(r"(?<=[.!?])\s+", section)
            for sentence in sentences:
                sentence = sentence.strip()
                if sentence and len(sentence) > 20 and sentence not in key_sentences:
                    key_sentences.append(sentence)
                    if len(key_sentences) >= max_sentences:
                        break

        return " ".join(key_sentences[:max_sentences])

    def add_emotional_tags(self, text: str, emotions: List[str]) -> str:
        """Add emotional tags to text for v3 synthesis.

        Args:
            text: Text to add tags to
            emotions: List of emotions to apply

        Returns:
            Text with emotional tags, one emotion per line for better generation
        """
        if not emotions:
            return text

        # Split text into sentences
        sentences = re.split(r"(?<=[.!?])\s+", text)

        # Apply emotions to sentences
        tagged_sentences = []
        emotion_index = 0

        for i, sentence in enumerate(sentences):
            if not sentence.strip():
                continue

            # Rotate through emotions if multiple sentences
            emotion = emotions[emotion_index % len(emotions)]
            emotion_tag = self.EMOTION_MAPPING.get(emotion, "")

            if emotion_tag:
                tagged_sentences.append(f"{emotion_tag} {sentence}")
            else:
                tagged_sentences.append(sentence)

            # Move to next emotion for variety
            if len(emotions) > 1:
                emotion_index += 1

        # Join with line breaks for better emotional separation
        # This helps v3 model understand emotional transitions
        return "\n\n".join(tagged_sentences)

    async def generate_audio_review(
        self,
        review_text: str,
        agent_name: str,
        pr_number: Optional[int] = None,
        voice_id: Optional[str] = None,
        provide_guidance: bool = True,
    ) -> Optional[str]:
        """Generate audio version of review WITHOUT modifying agent text.

        Args:
            review_text: Full review text FROM THE AGENT (not modified)
            agent_name: Name of the agent (gemini, claude, etc.)
            pr_number: Optional PR number for context
            voice_id: Optional specific voice to use
            provide_guidance: Whether to log v3 guidance for agents

        Returns:
            Audio URL if successful, None otherwise
        """
        if not self.enabled:
            return None

        try:
            # Analyze the agent's prompt (without modifying it)
            if provide_guidance:
                analysis = V3AgentGuide.analyze_prompt_quality(review_text)
                validation = V3AgentGuide.validate_prompt_length(review_text)
                
                if not validation["valid"]:
                    logger.info(f"V3 Guidance: {validation['message']}")
                    logger.info(f"Suggestion: {validation['suggestion']}")
                
                if analysis["suggestions"]:
                    logger.info("V3 Suggestions for better results:")
                    for suggestion in analysis["suggestions"]:
                        logger.info(f"  • {suggestion}")
                
                # Get voice guidance for the agent
                voice_guidance = V3AgentGuide.get_voice_guidance(agent_name)
                logger.debug(f"Voice guidance for {agent_name}: {voice_guidance['character']}")
                logger.debug(f"Best tags: {', '.join(voice_guidance['best_tags'])}")
            
            # Use the agent's text AS IS - no modifications
            final_text = review_text
            
            # Get voice profile if not specified
            if not voice_id:
                profile = get_voice_profile(agent_name)
                voice_id = profile.voice_id
            
            # Get voice settings (but let agent control via their prompt)
            voice_settings = get_voice_settings(agent_name)

            # Call ElevenLabs MCP server
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.mcp_base_url}/synthesize_speech_v3",
                    json={
                        "text": final_text,
                        "model": "eleven_v3",  # Use v3 for emotional support
                        "voice_id": voice_id,
                        "voice_settings": voice_settings,
                        "upload": True,
                    },
                    timeout=30.0,
                )

                if response.status_code == 200:
                    result = response.json()
                    if result.get("success") and result.get("audio_url"):
                        logger.info(f"Generated audio review for {agent_name}: {result['audio_url']}")
                        return str(result["audio_url"])  # Cast to str for mypy
                else:
                    logger.error(f"TTS API error: {response.status_code}")

        except Exception as e:
            logger.error(f"Failed to generate audio review: {e}")

        return None  # Explicit None return for mypy

    def format_github_comment_with_audio(
        self,
        original_comment: str,
        audio_url: str,
        duration: Optional[float] = None,
    ) -> str:
        """Format GitHub comment to include audio link.

        Args:
            original_comment: Original comment text
            audio_url: URL to audio file
            duration: Optional audio duration in seconds

        Returns:
            Formatted comment with audio link
        """
        duration_str = f" ({duration:.1f}s)" if duration else ""

        # Add audio link at the top of the comment
        audio_section = f"🎤 **[Listen to Audio Review{duration_str}]({audio_url})**\n\n---\n\n"

        return audio_section + original_comment

    async def process_review_with_tts(
        self,
        review_text: str,
        agent_name: str,
        pr_number: Optional[int] = None,
    ) -> Tuple[str, Optional[str]]:
        """Process review and optionally generate TTS.

        Args:
            review_text: Review text from agent
            agent_name: Name of the reviewing agent
            pr_number: Optional PR number

        Returns:
            Tuple of (formatted_review, audio_url)
        """
        audio_url = None

        if self.enabled:
            audio_url = await self.generate_audio_review(
                review_text,
                agent_name,
                pr_number,
            )

        # Format review with audio if available
        if audio_url:
            formatted_review = self.format_github_comment_with_audio(
                review_text,
                audio_url,
            )
        else:
            formatted_review = review_text

        return formatted_review, audio_url
