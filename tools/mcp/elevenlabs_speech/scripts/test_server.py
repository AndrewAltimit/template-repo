#!/usr/bin/env python3
"""Test script for ElevenLabs Speech MCP Server"""

import asyncio
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Load .env file
env_file = Path(__file__).parent.parent.parent.parent / ".env"
if env_file.exists():
    with open(env_file, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                # Only set if not already in environment
                if key not in os.environ:
                    os.environ[key] = value.strip('"').strip("'")

import httpx  # noqa: E402


async def test_server():
    """Test the ElevenLabs Speech MCP server"""

    base_url = "http://localhost:8018"

    print("🎙️  ElevenLabs Speech MCP Server Test")
    print("=" * 50)

    # Check for API key
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        print("\n⚠️  No API key found!")
        print("\nTo set your API key:")
        print("1. Add to your .env file:")
        print("   echo 'ELEVENLABS_API_KEY=your_api_key_here' >> .env")
        print("\nGet your API key from: https://elevenlabs.io/api")
        print("\n" + "=" * 50)

    async with httpx.AsyncClient() as client:
        # Test health check
        print("\n1. Testing health check...")
        try:
            response = await client.get(f"{base_url}/health")
            if response.status_code == 200:
                print("✅ Server is healthy")
                print(f"   Response: {response.json()}")
            else:
                print(f"❌ Health check failed: {response.status_code}")
                return
        except Exception as e:
            print(f"❌ Could not connect to server: {e}")
            print("\nMake sure the server is running:")
            print("  python -m tools.mcp.elevenlabs_speech.server")
            return

        # Test list tools
        print("\n2. Testing list tools...")
        try:
            response = await client.get(f"{base_url}/mcp/tools")
            if response.status_code == 200:
                tools = response.json()
                print(f"✅ Found {len(tools)} tools:")
                for i, tool in enumerate(tools[:5], 1):
                    print(f"   {i}. {tool}")
                if len(tools) > 5:
                    print(f"   ... and {len(tools) - 5} more")
            else:
                print(f"❌ List tools failed: {response.status_code}")
        except Exception as e:
            print(f"❌ Error listing tools: {e}")

        # Only run synthesis tests if API key is available
        if api_key:
            print("\n3. Testing basic synthesis...")
            try:
                response = await client.post(
                    f"{base_url}/mcp/execute",
                    json={
                        "tool": "synthesize_speech_v3",
                        "arguments": {
                            "text": "Hello! This is a test of the ElevenLabs Speech MCP server.",
                            "upload": False,  # Don't upload for test
                        },
                    },
                )

                if response.status_code == 200:
                    result = response.json()
                    if result.get("success"):
                        print("✅ Speech synthesis successful!")
                        if result.get("result", {}).get("local_path"):
                            print(f"   Audio saved to: {result['result']['local_path']}")
                    else:
                        print(f"⚠️  Synthesis returned: {result.get('error')}")
                else:
                    print(f"❌ Synthesis failed: {response.status_code}")
            except Exception as e:
                print(f"❌ Error during synthesis: {e}")

            print("\n4. Testing audio tags...")
            try:
                response = await client.post(
                    f"{base_url}/mcp/execute",
                    json={
                        "tool": "synthesize_speech_v3",
                        "arguments": {
                            "text": "[excited] Wow! [laughs] This is amazing! [whisper] Don't tell anyone.",
                            "upload": False,
                        },
                    },
                )

                if response.status_code == 200:
                    result = response.json()
                    if result.get("success"):
                        print("✅ Audio tags synthesis successful!")
                    else:
                        print(f"⚠️  Tags synthesis returned: {result.get('error')}")
                else:
                    print(f"❌ Tags synthesis failed: {response.status_code}")
            except Exception as e:
                print(f"❌ Error during tags synthesis: {e}")

            print("\n5. Testing voice listing...")
            try:
                response = await client.post(
                    f"{base_url}/mcp/execute", json={"tool": "list_available_voices", "arguments": {}}
                )

                if response.status_code == 200:
                    result = response.json()
                    if result.get("success"):
                        voices = result.get("result", {}).get("voices", [])
                        print(f"✅ Found {len(voices)} voices")
                        for voice in voices[:3]:
                            print(f"   - {voice.get('name')} ({voice.get('voice_id')})")
                        if len(voices) > 3:
                            print(f"   ... and {len(voices) - 3} more")
                    else:
                        print(f"⚠️  Voice listing returned: {result.get('error')}")
                else:
                    print(f"❌ Voice listing failed: {response.status_code}")
            except Exception as e:
                print(f"❌ Error listing voices: {e}")

        # Test tag parsing (doesn't need API key)
        print("\n6. Testing tag parsing...")
        try:
            response = await client.post(
                f"{base_url}/mcp/execute",
                json={
                    "tool": "parse_audio_tags",
                    "arguments": {"text": "[happy] Hello! [laughs] This is great! [whisper] Secret message."},
                },
            )

            if response.status_code == 200:
                result = response.json()
                if result.get("success"):
                    parsed = result.get("result", {})
                    print("✅ Tag parsing successful!")
                    print(f"   Tags found: {parsed.get('tags_found', [])}")
                    print(f"   Clean text: {parsed.get('clean_text', '')}")
                else:
                    print(f"⚠️  Tag parsing returned: {result.get('error')}")
            else:
                print(f"❌ Tag parsing failed: {response.status_code}")
        except Exception as e:
            print(f"❌ Error parsing tags: {e}")

        print("\n7. Testing tag suggestions...")
        try:
            response = await client.post(
                f"{base_url}/mcp/execute",
                json={
                    "tool": "suggest_audio_tags",
                    "arguments": {
                        "text": "Oh no! This is terrible... but wait, actually it's amazing!!!",
                        "context": "github_review",
                    },
                },
            )

            if response.status_code == 200:
                result = response.json()
                if result.get("success"):
                    suggestions = result.get("result", {})
                    print("✅ Tag suggestions successful!")
                    print(f"   Suggestions: {suggestions.get('suggestions', [])}")
                    print(f"   Example: {suggestions.get('example', '')}")
                else:
                    print(f"⚠️  Tag suggestions returned: {result.get('error')}")
            else:
                print(f"❌ Tag suggestions failed: {response.status_code}")
        except Exception as e:
            print(f"❌ Error suggesting tags: {e}")

    print("\n" + "=" * 50)
    print("✨ Test complete!")

    if not api_key:
        print("\n📝 Note: Set your API key to enable synthesis tests")
    else:
        print("\n🎉 All tests completed with API key present")


if __name__ == "__main__":
    asyncio.run(test_server())
