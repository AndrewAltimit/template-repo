#!/usr/bin/env python3
"""Test Gemini agent with Blondie voice for TTS."""

import asyncio
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from github_ai_agents.tts import TTSIntegration, get_voice_profile  # noqa: E402


async def test_gemini_review():
    """Test a realistic Gemini review with Blondie voice."""

    # Enable TTS
    os.environ["AGENT_TTS_ENABLED"] = "true"

    # Sample Gemini-style review
    gemini_review = """
    ## Code Review Summary

    This pull request implements the TTS integration for GitHub AI agents. The implementation
    demonstrates excellent architectural design with clear separation of concerns.

    ### Strengths
    - Well-structured voice profile system
    - Clean integration with existing agent infrastructure
    - Comprehensive documentation

    ### Issues Found
    - The failing CI checks need immediate attention
    - Some error handling could be more robust
    - Consider adding retry logic for API failures

    ### Recommendation
    Address the CI failures first, then the minor improvements. Overall, this is
    a solid implementation that will enhance the user experience significantly.
    """

    print("Gemini Agent TTS Test with Blondie Voice")
    print("=" * 60)

    # Get Gemini's voice profile
    profile = get_voice_profile("gemini")
    print("\nAgent: Gemini")
    print(f"Voice: {profile.name}")
    print(f"Settings: Stability={profile.stability}, Boost={profile.use_speaker_boost}")

    # Initialize TTS
    tts = TTSIntegration()

    if not tts.enabled:
        print("\nTTS is disabled. Set AGENT_TTS_ENABLED=true to enable.")
        return

    # Extract key sentences
    print("\n1. Extracting key sentences...")
    key_sentences = tts.extract_key_sentences(gemini_review)
    print(f"   Extracted: {key_sentences[:100]}...")

    # Analyze sentiment
    print("\n2. Analyzing sentiment...")
    emotions = tts.analyze_sentiment(gemini_review)
    print(f"   Emotions: {emotions}")

    # Add emotional tags
    print("\n3. Adding emotional tags (line-separated)...")
    tagged_text = tts.add_emotional_tags(key_sentences, emotions)
    print("   Tagged text:")
    for line in tagged_text.split("\n"):
        if line.strip():
            print(f"     {line[:70]}...")

    # Generate audio
    print("\n4. Generating audio with Blondie voice...")
    try:
        # Direct call to show exact parameters
        import httpx

        mcp_url = os.getenv("ELEVENLABS_MCP_URL", "http://localhost:8018")
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{mcp_url}/synthesize_speech_v3",
                json={
                    "text": tagged_text,
                    "model": "eleven_v3",
                    "voice_id": profile.voice_id,  # Blondie
                    "voice_settings": {
                        "stability": profile.stability,  # 0.0 for max expression
                        "similarity_boost": profile.similarity_boost,
                        "style": profile.style,
                        "use_speaker_boost": profile.use_speaker_boost,  # True
                    },
                    "upload": True,
                },
                timeout=30.0,
            )

            if response.status_code == 200:
                result = response.json()
                if result.get("success") and result.get("audio_url"):
                    print(f"   ✓ Audio generated: {result['audio_url']}")
                    print(f"   Character count: {result.get('character_count')}")
                else:
                    print(f"   ✗ Generation failed: {result.get('error')}")
            else:
                print(f"   ✗ API error: {response.status_code}")
    except Exception as e:
        print(f"   ✗ Error: {e}")
        print("   Make sure the ElevenLabs MCP server is running:")
        print("   docker-compose up -d mcp-elevenlabs-speech")

    print("\n" + "=" * 60)
    print("Test complete!")


if __name__ == "__main__":
    asyncio.run(test_gemini_review())
