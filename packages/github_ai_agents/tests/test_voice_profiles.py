#!/usr/bin/env python3
"""Test different voice profiles for AI agents."""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from github_ai_agents.tts import AGENT_VOICE_MAPPING, V3_COMPATIBLE_VOICES, get_voice_profile


def test_voice_profiles():
    """Test voice profile assignments."""

    print("Voice Profile Configuration")
    print("=" * 60)

    # Show available v3-compatible voices
    print("\nAvailable V3-Compatible Voices:")
    print("-" * 40)
    for key, profile in V3_COMPATIBLE_VOICES.items():
        print(f"  {key:12} - {profile.name:30} ({profile.description})")
        print(f"               Stability: {profile.stability:.1f}, Boost: {profile.use_speaker_boost}")

    # Show agent assignments
    print("\nAgent Voice Assignments:")
    print("-" * 40)
    for agent, voice_key in AGENT_VOICE_MAPPING.items():
        profile = get_voice_profile(agent)
        print(f"  {agent:10} -> {profile.name:30}")
        print(f"               {profile.description}")

    print("\n" + "=" * 60)


async def test_voice_generation():
    """Test generating audio with different voices."""
    import os

    # Skip if no API key
    if not os.getenv("ELEVENLABS_API_KEY"):
        print("\nSkipping audio generation test (no API key)")
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

    # Enable TTS for testing
    os.environ["AGENT_TTS_ENABLED"] = "true"
    tts = TTSIntegration()

    # Test each agent's voice
    for agent in ["gemini", "claude", "opencode", "crush"]:
        profile = get_voice_profile(agent)
        print(f"\nGenerating audio for {agent} ({profile.name})...")

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
    # Test voice profiles
    test_voice_profiles()

    # Test generation if requested
    if "--generate" in sys.argv:
        asyncio.run(test_voice_generation())
    else:
        print("\nTo test audio generation, run with --generate flag:")
        print("  python test_voice_profiles.py --generate")


if __name__ == "__main__":
    main()
