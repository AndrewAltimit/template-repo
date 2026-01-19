#!/usr/bin/env python3
"""Test script for ElevenLabs Speech MCP Server"""

import asyncio
import os
from pathlib import Path
import sys
from typing import Any

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


# Load .env file
env_file = Path(__file__).parent.parent.parent.parent / ".env"
if env_file.exists():
    with open(env_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                # Only set if not already in environment
                if key not in os.environ:
                    os.environ[key] = value.strip('"').strip("'")

import httpx  # noqa: E402

BASE_URL = "http://localhost:8018"


async def _test_health(client: httpx.AsyncClient) -> bool:
    """Test health endpoint. Returns True if server is healthy."""
    print("\n1. Testing health check...")
    try:
        response = await client.get(f"{BASE_URL}/health")
        if response.status_code == 200:
            print("   Server is healthy")
            print(f"   Response: {response.json()}")
            return True
        print(f"   Health check failed: {response.status_code}")
    except Exception as e:
        print(f"   Could not connect to server: {e}")
        print("\nMake sure the server is running:")
        print("  python -m tools.mcp.elevenlabs_speech.server")
    return False


async def _test_list_tools(client: httpx.AsyncClient) -> None:
    """Test list tools endpoint."""
    print("\n2. Testing list tools...")
    try:
        response = await client.get(f"{BASE_URL}/mcp/tools")
        if response.status_code == 200:
            tools = response.json()
            print(f"   Found {len(tools)} tools:")
            for i, tool in enumerate(tools[:5], 1):
                print(f"   {i}. {tool}")
            if len(tools) > 5:
                print(f"   ... and {len(tools) - 5} more")
        else:
            print(f"   List tools failed: {response.status_code}")
    except Exception as e:
        print(f"   Error listing tools: {e}")


async def _execute_tool(client: httpx.AsyncClient, tool: str, arguments: dict[str, Any]) -> dict[str, Any] | None:
    """Execute an MCP tool and return result or None on error."""
    try:
        response = await client.post(f"{BASE_URL}/mcp/execute", json={"tool": tool, "arguments": arguments})
        if response.status_code == 200:
            result: dict[str, Any] = response.json()
            return result
        print(f"   Request failed: {response.status_code}")
    except Exception as e:
        print(f"   Error: {e}")
    return None


async def _test_basic_synthesis(client: httpx.AsyncClient) -> None:
    """Test basic speech synthesis."""
    print("\n3. Testing basic synthesis...")
    result = await _execute_tool(
        client,
        "synthesize_speech_v3",
        {"text": "Hello! This is a test of the ElevenLabs Speech MCP server.", "upload": False},
    )
    if result:
        if result.get("success"):
            print("   Speech synthesis successful!")
            if result.get("result", {}).get("local_path"):
                print(f"   Audio saved to: {result['result']['local_path']}")
        else:
            print(f"   Synthesis returned: {result.get('error')}")


async def _test_audio_tags(client: httpx.AsyncClient) -> None:
    """Test audio tags synthesis."""
    print("\n4. Testing audio tags...")
    result = await _execute_tool(
        client,
        "synthesize_speech_v3",
        {"text": "[excited] Wow! [laughs] This is amazing! [whisper] Don't tell anyone.", "upload": False},
    )
    if result:
        if result.get("success"):
            print("   Audio tags synthesis successful!")
        else:
            print(f"   Tags synthesis returned: {result.get('error')}")


async def _test_voice_listing(client: httpx.AsyncClient) -> None:
    """Test voice listing."""
    print("\n5. Testing voice listing...")
    result = await _execute_tool(client, "list_available_voices", {})
    if result:
        if result.get("success"):
            voices = result.get("result", {}).get("voices", [])
            print(f"   Found {len(voices)} voices")
            for voice in voices[:3]:
                print(f"   - {voice.get('name')} ({voice.get('voice_id')})")
            if len(voices) > 3:
                print(f"   ... and {len(voices) - 3} more")
        else:
            print(f"   Voice listing returned: {result.get('error')}")


async def _test_tag_parsing(client: httpx.AsyncClient) -> None:
    """Test tag parsing (doesn't need API key)."""
    print("\n6. Testing tag parsing...")
    result = await _execute_tool(
        client, "parse_audio_tags", {"text": "[happy] Hello! [laughs] This is great! [whisper] Secret message."}
    )
    if result:
        if result.get("success"):
            parsed = result.get("result", {})
            print("   Tag parsing successful!")
            print(f"   Tags found: {parsed.get('tags_found', [])}")
            print(f"   Clean text: {parsed.get('clean_text', '')}")
        else:
            print(f"   Tag parsing returned: {result.get('error')}")


async def _test_tag_suggestions(client: httpx.AsyncClient) -> None:
    """Test tag suggestions."""
    print("\n7. Testing tag suggestions...")
    result = await _execute_tool(
        client,
        "suggest_audio_tags",
        {"text": "Oh no! This is terrible... but wait, actually it's amazing!!!", "context": "github_review"},
    )
    if result:
        if result.get("success"):
            suggestions = result.get("result", {})
            print("   Tag suggestions successful!")
            print(f"   Suggestions: {suggestions.get('suggestions', [])}")
            print(f"   Example: {suggestions.get('example', '')}")
        else:
            print(f"   Tag suggestions returned: {result.get('error')}")


async def test_server():
    """Test the ElevenLabs Speech MCP server"""
    print("ElevenLabs Speech MCP Server Test")
    print("=" * 50)

    # Check for API key
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        print("\n   No API key found!")
        print("\nTo set your API key:")
        print("1. Add to your .env file:")
        print("   echo 'ELEVENLABS_API_KEY=your_api_key_here' >> .env")
        print("\nGet your API key from: https://elevenlabs.io/api")
        print("\n" + "=" * 50)

    async with httpx.AsyncClient() as client:
        if not await _test_health(client):
            return

        await _test_list_tools(client)

        # Only run synthesis tests if API key is available
        if api_key:
            await _test_basic_synthesis(client)
            await _test_audio_tags(client)
            await _test_voice_listing(client)

        # Tests that don't need API key
        await _test_tag_parsing(client)
        await _test_tag_suggestions(client)

    print("\n" + "=" * 50)
    print("Test complete!")

    if not api_key:
        print("\nNote: Set your API key to enable synthesis tests")
    else:
        print("\nAll tests completed with API key present")


if __name__ == "__main__":
    asyncio.run(test_server())
