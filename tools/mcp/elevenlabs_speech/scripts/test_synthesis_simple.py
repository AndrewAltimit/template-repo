#!/usr/bin/env python3
"""Simple test of synthesis with outputs directory saving"""

import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path
parent_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(parent_dir))

# Load .env file
env_file = Path.cwd() / ".env"
print(f"Loading .env from: {env_file}")
if env_file.exists():
    with open(env_file, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ[key] = value.strip('"').strip("'")
                if key == "ELEVENLABS_API_KEY":
                    print(f"✅ Loaded API key: {value[:10]}...")

from elevenlabs_speech.client import ElevenLabsClient  # noqa: E402
from elevenlabs_speech.models import OutputFormat, SynthesisConfig, VoiceModel, VoiceSettings  # noqa: E402
from elevenlabs_speech.utils.prompting import NaturalSpeechEnhancer, PromptOptimizer  # noqa: E402


async def main():
    """Test synthesis with advanced features"""

    api_key = os.environ.get("ELEVENLABS_API_KEY")
    print(f"API key in environ: {'Yes' if api_key else 'No'}")

    if not api_key:
        print("❌ No API key found.")
        return

    print(f"Using API key: {api_key[:10]}...")

    client = ElevenLabsClient(api_key)

    try:
        # Test text
        text = "Hello! This is a test of the advanced ElevenLabs features with natural speech."

        # Apply optimizations
        text = NaturalSpeechEnhancer.add_speech_imperfections(text, add_hesitations=True, add_breathing=True)
        text = PromptOptimizer.optimize_prompt(text)

        print(f"\nOptimized text ({len(text)} chars):")
        print(f"  {text[:100]}...")

        # Create config
        config = SynthesisConfig(
            text=text,
            voice_id="JBFqnCBsd6RMkjVDRZzb",  # Rachel voice
            model=VoiceModel.ELEVEN_MULTILINGUAL_V2,
            voice_settings=VoiceSettings(stability=0.5, similarity_boost=0.75, style=0.3),
            output_format=OutputFormat.MP3_44100_128,
        )

        print("\n🎙️ Synthesizing...")
        result = await client.synthesize_speech(config)

        if result.success:
            print(f"✅ Success! Audio saved to: {result.local_path}")

            # Check outputs directory
            project_root = Path.cwd()
            outputs_dir = project_root / "outputs" / "elevenlabs_speech"
            date_dir = outputs_dir / datetime.now().strftime("%Y-%m-%d")

            print(f"\n📁 Checking outputs directory: {date_dir}")
            if date_dir.exists():
                files = list(date_dir.glob("*.mp3"))
                json_files = list(date_dir.glob("*.json"))
                print(f"   Found {len(files)} MP3 files")
                print(f"   Found {len(json_files)} metadata files")

                if files:
                    latest = max(files, key=lambda f: f.stat().st_mtime)
                    print(f"   Latest: {latest.name}")
                    print(f"   Size: {latest.stat().st_size:,} bytes")
            else:
                print("   Directory doesn't exist yet")
        else:
            print(f"❌ Synthesis failed: {result.error}")

    finally:
        await client.close()

    print("\n✅ Test complete!")


if __name__ == "__main__":
    asyncio.run(main())
