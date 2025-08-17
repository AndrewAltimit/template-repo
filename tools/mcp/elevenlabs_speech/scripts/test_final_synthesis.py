#!/usr/bin/env python3
"""Final test to ensure no more spoken [pause] tags"""

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

from elevenlabs_speech.server import ElevenLabsSpeechMCPServer  # noqa: E402


async def main():
    """Test the complete flow through the MCP server"""
    print("=" * 60)
    print("🚀 Final Test - No More Spoken Tags!")
    print("=" * 60)

    server = ElevenLabsSpeechMCPServer()

    if not server.client:
        print("❌ No API key configured")
        return

    # Test 1: Natural speech with optimization
    print("\n📝 Test 1: Natural Speech Synthesis")
    print("-" * 40)

    result = await server.synthesize_natural_speech(
        text="This is a test of the improved system. It should sound natural.", add_imperfections=True, add_breathing=True
    )

    if result.get("success"):
        print("✅ Success!")
        print(f"   Audio URL: {result.get('audio_url', 'Not uploaded')}")
        print(f"   Local path: {result.get('local_path')}")

        # Check metadata
        if result.get("metadata"):
            meta = result["metadata"]
            print("\n   Metadata:")
            print(f"   - Original input: {meta.get('original_input', 'N/A')}")
            print(f"   - Processed text: {meta.get('processed_text', 'N/A')[:100]}...")
            print(f"   - Model: {meta.get('model')}")
    else:
        print(f"❌ Failed: {result.get('error')}")

    # Test 2: Text optimization
    print("\n📝 Test 2: Text Optimization (No [pause] tags)")
    print("-" * 40)

    opt_result = await server.optimize_text_for_synthesis(text="Short text.", optimization_level="full")

    if opt_result.get("success"):
        optimized = opt_result["optimized_text"]
        print(f"Original: {opt_result['original_text']}")
        print(f"Optimized: {optimized[:100]}...")

        # Check for [pause] tags
        if "[pause]" in optimized:
            print("❌ WARNING: [pause] tag found in optimized text!")
        else:
            print("✅ Good: No [pause] tags in optimized text")

    # Test 3: Direct synthesis with the optimized text
    print("\n📝 Test 3: Direct Synthesis with Optimized Text")
    print("-" * 40)

    synth_result = await server.synthesize_speech_v3(
        text="Test message. This should work perfectly without spoken tags.", optimize_prompt=True
    )

    if synth_result.get("success"):
        print("✅ Success!")
        print(f"   Audio URL: {synth_result.get('audio_url', 'Not uploaded')}")

        # Find and display the metadata file
        project_root = Path.cwd()
        outputs_dir = project_root / "outputs" / "elevenlabs_speech"
        date_dir = outputs_dir / datetime.now().strftime("%Y-%m-%d")

        if date_dir.exists():
            json_files = sorted(date_dir.glob("*.json"), key=lambda f: f.stat().st_mtime)
            if json_files:
                latest = json_files[-1]
                with open(latest, "r") as f:
                    metadata = json.load(f)

                print(f"\n   Latest metadata ({latest.name}):")
                print(f"   - Original: {metadata.get('original_text', 'N/A')}")
                print(f"   - Processed: {metadata.get('processed_text', 'N/A')}")
                print(f"   - Has [pause]: {'[pause]' in metadata.get('processed_text', '')}")
    else:
        print(f"❌ Failed: {synth_result.get('error')}")

    print("\n" + "=" * 60)
    print("✅ Tests completed! Check the audio files to verify no spoken tags.")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
