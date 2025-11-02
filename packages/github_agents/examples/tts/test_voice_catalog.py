#!/usr/bin/env python3
"""Test voice catalog with different agents and contexts."""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from github_agents.tts.voice_catalog import (  # noqa: E402
    VOICE_CATALOG,
    VoiceCategory,
    get_voice_for_context,
    get_voice_recommendations,
    get_voice_settings_for_emotion,
    list_voices_by_category,
)


def display_voice_catalog():
    """Display the complete voice catalog organized by category."""
    print("Complete ElevenLabs Voice Catalog")
    print("=" * 80)

    # Group voices by category
    for category in VoiceCategory:
        voices = list_voices_by_category(category)
        if voices:
            print(f"\n{category.value.upper()} VOICES ({len(voices)})")
            print("-" * 40)

            for voice in voices:
                print(f"  • {voice.display_name}")
                print(f"    {voice.description}")
                print(f"    Accent: {voice.accent} | Age: {voice.age} | Gender: {voice.gender}")
                print(f"    Best for: {', '.join(voice.best_for[:3])}")
                print()


def test_agent_voice_selection():
    """Test voice selection for different agents and contexts."""
    print("\nAgent Voice Selection Based on Context")
    print("=" * 80)

    test_cases = [
        ("gemini", "default", "normal", "Standard Gemini review"),
        ("gemini", "critical", "urgent", "Critical security issue"),
        ("gemini", "excited", "normal", "Exciting new feature"),
        ("claude", "technical", "normal", "Technical documentation"),
        ("opencode", "enthusiastic", "normal", "Great code implementation"),
        ("crush", "direct", "urgent", "Urgent bug fix needed"),
    ]

    for agent, sentiment, criticality, description in test_cases:
        voice = get_voice_for_context(agent, sentiment, criticality)
        settings = get_voice_settings_for_emotion(voice, emotion_intensity=0.7)

        print(f"\n{description}")
        print(f"  Agent: {agent} | Sentiment: {sentiment} | Criticality: {criticality}")
        print(f"  Selected Voice: {voice.display_name}")
        print(f"  Personality: {', '.join(voice.personality_traits[:3])}")
        print(f"  Settings: Stability={settings['stability']:.2f}, Style={settings['style']:.2f}")


def test_voice_recommendations():
    """Test voice recommendations for different content types."""
    print("\nVoice Recommendations by Content Type")
    print("=" * 80)

    content_types = [
        ("review", "professional"),
        ("documentation", "clear"),
        ("conversations", "friendly"),
        ("critical feedback", "direct"),
        ("storytelling", "expressive"),
    ]

    for content_type, tone in content_types:
        recommendations = get_voice_recommendations(content_type, tone)
        print(f"\n{content_type.title()} ({tone})")
        print("-" * 40)

        for i, voice in enumerate(recommendations[:3], 1):
            print(f"  {i}. {voice.display_name}")
            print(f"     {voice.description[:60]}...")


async def test_voice_generation_sample():
    """Generate sample audio with different voices."""
    print("\nSample Voice Generation Test")
    print("=" * 80)

    # Sample text with different emotions
    sample_texts = {
        "blondie": "[thoughtful] This PR shows excellent architecture. [happy] I'm impressed!",
        "reginald": "[serious] Critical security vulnerabilities detected. [urgent] Immediate action required.",
        "hope_conversational": "[friendly] Hey, this looks pretty good! [curious] Hmm, what about error handling?",
        "peter": "[professional] The implementation follows best practices. [analytical] Consider performance implications.",
    }

    for voice_key, text in sample_texts.items():
        if voice_key in VOICE_CATALOG:
            voice = VOICE_CATALOG[voice_key]
            settings = get_voice_settings_for_emotion(voice, emotion_intensity=0.8)

            print(f"\n{voice.display_name}")
            print(f"  Text: {text[:60]}...")
            print(f"  Voice ID: {voice.voice_id}")
            print(f"  Stability: {settings['stability']:.2f}")
            print(f"  Speaker Boost: {settings['use_speaker_boost']}")


def main():
    """Run all tests."""
    # Display full catalog
    display_voice_catalog()

    # Test agent voice selection
    test_agent_voice_selection()

    # Test voice recommendations
    test_voice_recommendations()

    # Test sample generation
    asyncio.run(test_voice_generation_sample())

    print("\n" + "=" * 80)
    print("Voice Catalog Test Complete!")
    print(f"Total voices available: {len(VOICE_CATALOG)}")


if __name__ == "__main__":
    main()
