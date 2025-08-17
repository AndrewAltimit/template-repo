#!/usr/bin/env python3
"""Test advanced ElevenLabs features with v3 prompting best practices"""

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path
parent_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(parent_dir))

from elevenlabs_speech.client import ElevenLabsClient  # noqa: E402
from elevenlabs_speech.models import OutputFormat, SynthesisConfig, VoiceModel, VoiceSettings  # noqa: E402
from elevenlabs_speech.utils.prompting import (  # noqa: E402
    EmotionalEnhancer,
    NaturalSpeechEnhancer,
    PromptOptimizer,
    VoiceDirector,
)

# Load .env file if it exists
env_file = Path(__file__).parent.parent.parent.parent / ".env"
if env_file.exists():
    with open(env_file, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                if key not in os.environ:
                    os.environ[key] = value.strip('"').strip("'")


async def test_prompt_optimization():
    """Test prompt optimization techniques"""
    print("\n🔧 Testing Prompt Optimization...")

    original_text = "This is a test. It should be optimized for better synthesis."

    # Test optimization
    optimized = PromptOptimizer.optimize_prompt(original_text)
    print(f"Original ({len(original_text)} chars): {original_text}")
    print(f"Optimized ({len(optimized)} chars): {optimized}")

    # Test minimum length padding
    short_text = "Hello world!"
    padded = PromptOptimizer.optimize_prompt(short_text, ensure_minimum_length=True)
    print(f"\nShort text ({len(short_text)} chars): {short_text}")
    print(f"Padded ({len(padded)} chars): {padded[:100]}...")


async def test_emotional_enhancement():
    """Test emotional enhancement features"""
    print("\n🎭 Testing Emotional Enhancement...")

    text = "I just heard the news about the project."

    # Test different emotions
    emotions = ["joy", "sadness", "surprise"]
    for emotion in emotions:
        enhanced = EmotionalEnhancer.enhance_with_emotion(text, emotion, "moderate")
        print(f"{emotion.capitalize()}: {enhanced}")

    # Test emotional progression
    progression_text = "The meeting started normally. Then we got the results. Everyone was amazed."
    with_progression = EmotionalEnhancer.add_emotional_progression(
        progression_text, start_emotion="fear", end_emotion="joy", transition_point=0.5
    )
    print(f"\nEmotional progression:\n{with_progression}")


async def test_natural_speech():
    """Test natural speech enhancement"""
    print("\n💬 Testing Natural Speech Enhancement...")

    text = "I think we should consider the proposal. It might be beneficial for the team."

    # Add imperfections
    natural = NaturalSpeechEnhancer.add_speech_imperfections(
        text, add_hesitations=True, add_breathing=True, add_filler_words=True
    )
    print(f"Natural speech: {natural}")

    # Add conversational markers
    conversational = NaturalSpeechEnhancer.add_conversational_markers("What do you think about this approach?")
    print(f"Conversational: {conversational}")


async def test_voice_direction():
    """Test voice direction features"""
    print("\n🎬 Testing Voice Direction...")

    text = "Once upon a time in a distant land..."

    # Test different character types
    characters = ["narrator", "hero", "villain", "mysterious"]
    for character in characters:
        directed = VoiceDirector.create_character_voice(text, character)
        print(f"{character.capitalize()}: {directed}")

    # Test with environment
    ambient = VoiceDirector.add_scene_ambience("Can you hear me over there?", environment="windy")
    print(f"\nWith ambience: {ambient}")


async def test_synthesis_with_optimization():
    """Test actual synthesis with optimization"""
    print("\n🎙️ Testing Synthesis with Optimization...")

    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        print("❌ No API key found. Skipping synthesis test.")
        return

    client = ElevenLabsClient(api_key)

    try:
        # Original text
        text = "This is a test of the advanced features."

        # Optimize the text
        optimized_text = PromptOptimizer.optimize_prompt(text)
        print(f"Optimized text: {optimized_text}")

        # Add natural speech elements
        natural_text = NaturalSpeechEnhancer.add_speech_imperfections(optimized_text, add_hesitations=True, add_breathing=True)
        print(f"Natural text: {natural_text}")

        # Create synthesis config
        config = SynthesisConfig(
            text=natural_text,
            voice_id="JBFqnCBsd6RMkjVDRZzb",  # Rachel voice
            model=VoiceModel.ELEVEN_MULTILINGUAL_V2,  # Pro plan model
            voice_settings=VoiceSettings(stability=0.5, similarity_boost=0.75, style=0.3),
            output_format=OutputFormat.MP3_44100_128,
        )

        # Synthesize
        print("Synthesizing...")
        result = await client.synthesize_speech(config)

        if result.success:
            print("✅ Synthesis successful!")
            print(f"   Audio saved to: {result.local_path}")

            # Check if saved to outputs directory
            project_root = Path(__file__).parent.parent.parent.parent
            outputs_dir = project_root / "outputs" / "elevenlabs_speech"
            date_dir = outputs_dir / datetime.now().strftime("%Y-%m-%d")

            if date_dir.exists():
                files = list(date_dir.glob("*.mp3"))
                if files:
                    print(f"   Also saved to outputs: {files[-1]}")

                    # Check metadata
                    metadata_files = list(date_dir.glob("*.json"))
                    if metadata_files:
                        with open(metadata_files[-1], "r") as f:
                            metadata = json.load(f)
                        print(f"   Metadata saved: {metadata.get('timestamp', 'unknown')}")
        else:
            print(f"❌ Synthesis failed: {result.error}")

    finally:
        await client.close()


async def test_emotional_progression_synthesis():
    """Test synthesis with emotional progression"""
    print("\n🎭 Testing Emotional Progression Synthesis...")

    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        print("❌ No API key found. Skipping synthesis test.")
        return

    client = ElevenLabsClient(api_key)

    try:
        # Text with emotional arc
        text = (
            "I was worried about the presentation. But as I started speaking, my confidence grew. By the end, I felt amazing!"
        )

        # Add emotional progression
        emotional_text = EmotionalEnhancer.add_emotional_progression(
            text, start_emotion="fear", end_emotion="joy", transition_point=0.6
        )
        print(f"Emotional text: {emotional_text}")

        # Optimize for synthesis
        final_text = PromptOptimizer.optimize_prompt(emotional_text)

        # Create synthesis config
        config = SynthesisConfig(
            text=final_text,
            voice_id="JBFqnCBsd6RMkjVDRZzb",  # Rachel voice
            model=VoiceModel.ELEVEN_MULTILINGUAL_V2,
            voice_settings=VoiceSettings(
                stability=0.4, similarity_boost=0.75, style=0.5  # Lower for more expression  # Higher for more emotional range
            ),
            output_format=OutputFormat.MP3_44100_128,
        )

        # Synthesize
        print("Synthesizing emotional progression...")
        result = await client.synthesize_speech(config)

        if result.success:
            print("✅ Emotional synthesis successful!")
            print(f"   Audio saved to: {result.local_path}")
        else:
            print(f"❌ Synthesis failed: {result.error}")

    finally:
        await client.close()


async def main():
    """Run all tests"""
    print("=" * 60)
    print("🚀 Testing ElevenLabs Advanced Features")
    print("=" * 60)

    # Test prompting utilities
    await test_prompt_optimization()
    await test_emotional_enhancement()
    await test_natural_speech()
    await test_voice_direction()

    # Test actual synthesis
    await test_synthesis_with_optimization()
    await test_emotional_progression_synthesis()

    print("\n" + "=" * 60)
    print("✅ All tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
