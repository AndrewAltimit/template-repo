#!/usr/bin/env python3
"""Test MCP server tools with advanced prompting"""

import asyncio
import os
import sys
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


async def test_optimize_text_tool():
    """Test the optimize_text_for_synthesis tool"""
    print("\n📝 Testing optimize_text_for_synthesis tool...")

    server = ElevenLabsSpeechMCPServer()

    # Test different optimization levels
    text = "This is a short test."

    for level in ["minimal", "moderate", "full"]:
        result = await server.optimize_text_for_synthesis(text, level)
        print(f"\n{level.capitalize()} optimization:")
        print(f"  Original: {result['original_length']} chars")
        print(f"  Optimized: {result['optimized_length']} chars")
        print(f"  Has pauses: {result['changes']['has_pauses']}")
        print(f"  Has emphasis: {result['changes']['has_emphasis']}")
        print(f"  Preview: {result['optimized_text'][:80]}...")


async def test_natural_speech_tool():
    """Test the synthesize_natural_speech tool"""
    print("\n🎤 Testing synthesize_natural_speech tool...")

    server = ElevenLabsSpeechMCPServer()

    if not server.client:
        print("❌ No API key configured, skipping synthesis")
        return

    result = await server.synthesize_natural_speech(
        text="Let me explain how this works. It's quite interesting.",
        add_imperfections=True,
        add_breathing=True,
        character_type="narrator",
    )

    if result.get("success"):
        print("✅ Natural speech synthesis successful!")
        print(f"   Audio saved to: {result.get('local_path')}")
    else:
        print(f"❌ Failed: {result.get('error')}")


async def test_emotional_progression_tool():
    """Test the synthesize_emotional_progression tool"""
    print("\n🎭 Testing synthesize_emotional_progression tool...")

    server = ElevenLabsSpeechMCPServer()

    if not server.client:
        print("❌ No API key configured, skipping synthesis")
        return

    result = await server.synthesize_emotional_progression(
        text="I wasn't sure about this at first. But now I see how amazing it is!",
        start_emotion="fear",
        end_emotion="joy",
        transition_point=0.5,
    )

    if result.get("success"):
        print("✅ Emotional progression synthesis successful!")
        print(f"   Audio saved to: {result.get('local_path')}")
    else:
        print(f"❌ Failed: {result.get('error')}")


async def test_get_tools():
    """Test that all tools are properly registered"""
    print("\n🔧 Checking registered MCP tools...")

    server = ElevenLabsSpeechMCPServer()
    tools = server.get_tools()

    print(f"Found {len(tools)} tools:")

    # Check for our new tools
    advanced_tools = ["synthesize_natural_speech", "synthesize_emotional_progression", "optimize_text_for_synthesis"]

    for tool_name in advanced_tools:
        if tool_name in tools:
            print(f"  ✅ {tool_name}")
        else:
            print(f"  ❌ {tool_name} (missing!)")

    # List all tools
    print("\nAll available tools:")
    for tool_name in sorted(tools.keys()):
        print(f"  - {tool_name}")


async def main():
    """Run all MCP tool tests"""
    print("=" * 60)
    print("🚀 Testing ElevenLabs MCP Server Tools")
    print("=" * 60)

    await test_get_tools()
    await test_optimize_text_tool()
    await test_natural_speech_tool()
    await test_emotional_progression_tool()

    print("\n" + "=" * 60)
    print("✅ MCP tool tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
