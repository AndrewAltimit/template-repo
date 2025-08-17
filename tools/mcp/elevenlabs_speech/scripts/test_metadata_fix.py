#!/usr/bin/env python3
"""Test that metadata is properly saved and [pause] tags are handled correctly"""

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path
parent_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(parent_dir))

# Load .env file
env_file = Path.cwd() / ".env"
if env_file.exists():
    with open(env_file, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ[key] = value.strip('"').strip("'")

from elevenlabs_speech.client import ElevenLabsClient  # noqa: E402
from elevenlabs_speech.models import OutputFormat, SynthesisConfig, VoiceModel, VoiceSettings  # noqa: E402
from elevenlabs_speech.utils.model_aware_prompting import ModelAwarePrompter  # noqa: E402
from elevenlabs_speech.utils.prompting import PromptOptimizer  # noqa: E402


async def test_model_aware_cleaning():
    """Test that tags are properly cleaned for different models"""
    print("\n🧹 Testing Model-Aware Tag Cleaning...")

    # Text with various tags
    text_with_tags = "Hello [pause] there! [laughs] This is [whisper] a test [excited] of the system."

    # Test with different models
    models = [VoiceModel.ELEVEN_V3, VoiceModel.ELEVEN_MULTILINGUAL_V2, VoiceModel.ELEVEN_FLASH_V2]

    for model in models:
        cleaned = ModelAwarePrompter.clean_text_for_model(text_with_tags, model)
        print(f"\n{model.value}:")
        print(f"  Original: {text_with_tags}")
        print(f"  Cleaned:  {cleaned}")

        # Validate the text
        validation = ModelAwarePrompter.validate_text_for_model(text_with_tags, model)
        if validation["issues"]:
            print(f"  Issues: {validation['issues'][0]}")


async def test_synthesis_with_metadata():
    """Test synthesis and check the saved metadata"""
    print("\n📊 Testing Synthesis with Comprehensive Metadata...")

    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        print("❌ No API key found.")
        return

    client = ElevenLabsClient(api_key)

    try:
        # Original text with tags that should be removed for v2
        original_text = "Hello there! [pause] Let me tell you something [excited] interesting."

        # Clean for v2 model
        model = VoiceModel.ELEVEN_MULTILINGUAL_V2
        cleaned_text = ModelAwarePrompter.clean_text_for_model(original_text, model)

        print(f"Original text: {original_text}")
        print(f"Cleaned text:  {cleaned_text}")

        # Create config
        config = SynthesisConfig(
            text=cleaned_text,
            voice_id="JBFqnCBsd6RMkjVDRZzb",
            model=model,
            voice_settings=VoiceSettings(stability=0.5, similarity_boost=0.75, style=0.3),
            output_format=OutputFormat.MP3_44100_128,
        )

        print("\n🎙️ Synthesizing...")
        result = await client.synthesize_speech(config)

        if result.success:
            print(f"✅ Success! Audio saved to: {result.local_path}")

            # Check the metadata file
            project_root = Path.cwd()
            outputs_dir = project_root / "outputs" / "elevenlabs_speech"
            date_dir = outputs_dir / datetime.now().strftime("%Y-%m-%d")

            if date_dir.exists():
                # Find the latest metadata file
                json_files = sorted(date_dir.glob("*.json"), key=lambda f: f.stat().st_mtime)
                if json_files:
                    latest_metadata = json_files[-1]

                    with open(latest_metadata, "r") as f:
                        metadata = json.load(f)

                    print(f"\n📄 Metadata from {latest_metadata.name}:")
                    print(f"  Timestamp: {metadata.get('timestamp')}")
                    print(f"  File size: {metadata.get('size_bytes'):,} bytes")
                    print(f"  Model: {metadata.get('model')}")
                    print(f"  Format: {metadata.get('format')}")

                    if "original_text" in metadata:
                        print(f"\n  Original text ({len(metadata['original_text'])} chars):")
                        print(f"    {metadata['original_text'][:100]}...")

                    if "processed_text" in metadata:
                        print(f"\n  Processed text ({len(metadata['processed_text'])} chars):")
                        print(f"    {metadata['processed_text'][:100]}...")

                    if "voice_settings" in metadata:
                        print("\n  Voice settings:")
                        for key, value in metadata["voice_settings"].items():
                            print(f"    {key}: {value}")
        else:
            print(f"❌ Synthesis failed: {result.error}")

    finally:
        await client.close()


async def test_prompt_optimization_without_pause_tags():
    """Test that prompt optimization doesn't add [pause] tags"""
    print("\n🔧 Testing Prompt Optimization (Fixed)...")

    short_text = "Hello world!"

    # Optimize the text
    optimized = PromptOptimizer.optimize_prompt(short_text, ensure_minimum_length=True)

    print(f"Original: {short_text}")
    print(f"Optimized: {optimized}")

    # Check if [pause] appears in the optimized text
    if "[pause]" in optimized:
        print("❌ ERROR: [pause] tag found in optimized text!")
    else:
        print("✅ Good: No [pause] tags in optimized text")

    # Clean for v2 model to be safe
    cleaned = ModelAwarePrompter.clean_text_for_model(optimized, VoiceModel.ELEVEN_MULTILINGUAL_V2)
    print(f"Cleaned for v2: {cleaned}")


async def main():
    """Run all tests"""
    print("=" * 60)
    print("🚀 Testing Metadata and Tag Fixes")
    print("=" * 60)

    await test_model_aware_cleaning()
    await test_prompt_optimization_without_pause_tags()
    await test_synthesis_with_metadata()

    print("\n" + "=" * 60)
    print("✅ All tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
