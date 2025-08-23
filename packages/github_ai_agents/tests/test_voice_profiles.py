#!/usr/bin/env python3
"""Test voice catalog for AI agents."""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from github_ai_agents.tts import VOICE_CATALOG, get_voice_for_context, get_voice_settings_for_emotion  # noqa: E402
from github_ai_agents.tts.voice_catalog import AGENT_PERSONALITY_MAPPING, VoiceCategory  # noqa: E402


def test_voice_catalog():
    """Test voice catalog and agent personality mapping."""

    print("Voice Catalog Configuration")
    print("=" * 60)

    # Show available voices by category
    print("\nAvailable Voices by Category:")
    print("-" * 40)
    for category in VoiceCategory:
        voices_in_cat = [k for k, v in VOICE_CATALOG.items() if v.category == category]
        if voices_in_cat:
            print(f"\n{category.value}:")
            for key in voices_in_cat[:3]:  # Show first 3 per category
                voice = VOICE_CATALOG[key]
                print(f"  {key:20} - {voice.display_name:30}")
                print(f"                       {voice.description[:50]}...")

    # Show agent personality mappings
    print("\nAgent Personality Mappings:")
    print("-" * 40)
    for agent, personality in AGENT_PERSONALITY_MAPPING.items():
        print(f"  {agent:10} -> {personality['default']} voice")
        print(f"               Context: {', '.join(personality['context_mapping'].keys())}")

    # Test voice selection logic
    print("\nContext-Aware Voice Selection:")
    print("-" * 40)
    test_cases = [
        ("gemini", "positive", "normal"),
        ("claude", "critical", "urgent"),
        ("opencode", "professional", "normal"),
    ]
    for agent, sentiment, criticality in test_cases:
        voice = get_voice_for_context(agent, sentiment, criticality)
        settings = get_voice_settings_for_emotion(voice, 0.7)
        print(f"  {agent} ({sentiment}/{criticality}):")
        print(f"    Voice: {voice.display_name}")
        print(f"    Stability: {settings['stability']:.2f}")

    print("\n" + "=" * 60)


async def test_voice_generation():
    """Test generating audio with different voices."""
    import os

    # Default to mock mode unless explicitly running with real API
    use_real_api = os.getenv("TTS_USE_REAL_API", "false").lower() == "true"

    if use_real_api and not os.getenv("ELEVENLABS_API_KEY"):
        print("\nSkipping real API test (no API key)")
        return

    from github_ai_agents.tts import TTSIntegration

    # Test text with emotional variety
    test_review = """
    [thoughtful] This pull request shows excellent code structure and follows best practices.
    [concerned] However, there are some performance issues that need addressing.
    [happy] Once these are resolved, this will be a fantastic addition to the codebase!
    """

    print("\nTesting Voice Generation")
    print("=" * 60)

    # Enable TTS for testing (default to mock mode)
    os.environ["AGENT_TTS_ENABLED"] = "true"
    if not use_real_api:
        os.environ["TTS_MOCK_MODE"] = "true"
        print("Running in MOCK MODE (no API credits used)")
    else:
        print("Running with REAL API (using credits)")

    tts = TTSIntegration()

    # Test each agent's voice with context
    for agent in ["gemini", "claude", "opencode", "crush"]:
        voice = get_voice_for_context(agent, "professional", "normal")
        print(f"\nGenerating audio for {agent} ({voice.display_name})...")

        try:
            audio_url = await tts.generate_audio_review(test_review, agent_name=agent, pr_number=999)

            if audio_url:
                print(f"  ✓ Success: {audio_url}")
            else:
                print("  ✗ Failed to generate audio")
        except Exception as e:
            print(f"  ✗ Error: {e}")

    print("\n" + "=" * 60)


def main():
    """Run tests."""
    # Test voice catalog
    test_voice_catalog()

    # Test generation if requested
    if "--generate" in sys.argv:
        asyncio.run(test_voice_generation())
    else:
        print("\nTo test audio generation, run with --generate flag:")
        print("  python test_voice_profiles.py --generate")
        print("\nBy default, tests run in MOCK MODE (no API credits used)")
        print("To use real API (consumes credits), set TTS_USE_REAL_API=true")


if __name__ == "__main__":
    main()
