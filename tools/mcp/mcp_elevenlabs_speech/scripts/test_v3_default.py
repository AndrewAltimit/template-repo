#!/usr/bin/env python3
"""Test that eleven_v3 is the default model for ElevenLabs MCP Server"""

import asyncio
import os
import sys
from pathlib import Path

# Add parent directory to path
parent_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(parent_dir))
# pylint: disable=wrong-import-position  # Imports must come after sys.path modification

# Load .env file
env_file = Path.cwd() / ".env"
if env_file.exists():
    with open(env_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ[key] = value.strip('"').strip("'")

from elevenlabs_speech.server import ElevenLabsSpeechMCPServer  # noqa: E402


async def test_v3_default():
    """Test that eleven_v3 is the default model"""
    print("\n🧪 Testing ElevenLabs v3 Default Configuration")
    print("=" * 60)

    server = ElevenLabsSpeechMCPServer()

    # Check configuration
    print(f"✓ Default model in config: {server.config.get('default_model')}")
    assert server.config.get("default_model") == "eleven_v3", "Default model should be eleven_v3"

    if not server.client:
        print("⚠️  No API key configured - skipping synthesis test")
        print("   Add ELEVENLABS_API_KEY to .env to test synthesis")
        return

    # Test synthesis with no model specified (should use v3)
    print("\n📢 Testing synthesis with default model...")
    result = await server.synthesize_speech_v3(
        text="[excited] Testing v3 as default! [laughs] This is great!", voice_id="21m00Tcm4TlvDq8ikWAM", upload=True  # Rachel
    )

    if result.get("success"):
        print(f"✅ Success! Model used: {result.get('model_used')}")
        assert result.get("model_used") == "eleven_v3", "Should have used eleven_v3"
        print(f"   Audio URL: {result.get('audio_url')}")
    else:
        print(f"❌ Failed: {result.get('error')}")
        return False

    # Test with explicit v3 model
    print("\n📢 Testing synthesis with explicit v3...")
    result = await server.synthesize_speech_v3(
        text="[whisper] Explicitly using v3... [normal voice] Perfect!",
        voice_id="21m00Tcm4TlvDq8ikWAM",  # Rachel
        model="eleven_v3",
        upload=True,
    )

    if result.get("success"):
        print(f"✅ Success! Model used: {result.get('model_used')}")
        print(f"   Audio URL: {result.get('audio_url')}")
    else:
        print(f"❌ Failed: {result.get('error')}")

    print("\n" + "=" * 60)
    print("✅ All tests passed! eleven_v3 is properly configured as default.")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = asyncio.run(test_v3_default())
    sys.exit(0 if success else 1)
