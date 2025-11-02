"""TTS integration for agent reviews with emotional context."""

import logging
import os
from typing import Dict, Optional, Tuple

import httpx

from .v3_agent_guide import V3AgentGuide
from .voice_catalog import get_voice_for_context, get_voice_settings_for_emotion

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

    def __init__(self, config: Optional[Dict] = None):
        """Initialize TTS integration.

        Args:
            config: Optional configuration dict
        """
        self.config = config or {}
        self.mcp_base_url = os.getenv("ELEVENLABS_MCP_URL", "http://localhost:8018")
        self.api_key = os.getenv("ELEVENLABS_API_KEY")

        # Check for mock mode (for testing without using API credits)
        self.mock_mode = (os.getenv("TTS_MOCK_MODE") or "false").lower() == "true"

        # Check if TTS should be enabled
        self.enabled = self._is_tts_enabled()

        # Only log warning if TTS was explicitly enabled but no API key (and not in mock mode)
        if self.enabled and not self.api_key and not self.mock_mode:
            logger.info("TTS enabled but no ELEVENLABS_API_KEY found - will use MCP server's configured key")

    def _is_tts_enabled(self) -> bool:
        """Check if TTS is enabled via environment or config."""
        # Check environment variable first
        env_enabled = (os.getenv("AGENT_TTS_ENABLED") or "false").lower() == "true"

        # Check config
        config_enabled = self.config.get("tts", {}).get("enabled", False)

        return env_enabled or config_enabled

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

        # Mock mode for testing without using API credits
        if self.mock_mode:
            logger.debug(f"Mock mode: Would generate audio for {agent_name} PR#{pr_number}")
            return f"mock://audio/pr{pr_number}_{agent_name}.mp3"

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

            # Determine sentiment and criticality from review (for voice selection)
            sentiment = "professional"  # default
            criticality = "normal"  # default

            # Simple sentiment detection for voice selection
            review_lower = review_text.lower()
            if any(word in review_lower for word in ["excellent", "great", "impressive", "perfect"]):
                sentiment = "positive"
            elif any(word in review_lower for word in ["critical", "severe", "urgent", "security"]):
                sentiment = "critical"
                criticality = "urgent"
            elif any(word in review_lower for word in ["concern", "issue", "problem"]):
                sentiment = "concerned"

            # Get context-aware voice if not specified
            if not voice_id:
                voice = get_voice_for_context(agent_name, sentiment, criticality)
                voice_id = voice.voice_id
                # Get appropriate settings for the detected emotion
                voice_settings = get_voice_settings_for_emotion(voice, emotion_intensity=0.7)
            else:
                # Use default settings if voice_id was provided
                voice_settings = {
                    "stability": 0.0,
                    "similarity_boost": 0.75,
                    "style": 0.0,
                    "use_speaker_boost": True,
                }

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
                    audio_url = result.get("audio_url")
                    if result.get("success") and isinstance(audio_url, str):
                        logger.info(f"Generated audio review for {agent_name}: {audio_url}")
                        return audio_url
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
