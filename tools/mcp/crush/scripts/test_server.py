#!/usr/bin/env python3
"""Test script for Crush MCP Server"""

import asyncio
import os
import sys
from pathlib import Path

import aiohttp

# Add parent directory to path
parent_dir = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(parent_dir))


async def test_crush_server():
    """Test Crush MCP server endpoints"""
    base_url = "http://localhost:8015"

    print("⚡ Testing Crush MCP Server")
    print("=" * 50)

    # Check if API key is set
    if not os.environ.get("OPENROUTER_API_KEY"):
        print("⚠️  Warning: OPENROUTER_API_KEY not set in environment")
        print("   Some tests may fail without a valid API key")
        print()

    async with aiohttp.ClientSession() as session:
        # Test 1: Health check
        print("1. Testing health endpoint...")
        try:
            async with session.get(f"{base_url}/health") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    print(f"   ✅ Server is healthy: {data}")
                else:
                    print(f"   ❌ Health check failed: {resp.status}")
        except Exception as e:
            print(f"   ❌ Failed to connect: {e}")
            print("   Make sure the server is running on port 8015")
            return

        # Test 2: List tools
        print("\n2. Testing list tools...")
        try:
            async with session.get(f"{base_url}/mcp/tools") as resp:
                if resp.status == 200:
                    tools = await resp.json()
                    print(f"   ✅ Available tools: {[t['name'] for t in tools.get('tools', [])]}")
                else:
                    print(f"   ❌ Failed to list tools: {resp.status}")
        except Exception as e:
            print(f"   ❌ Error: {e}")

        # Test 3: Quick generate
        print("\n3. Testing quick generation...")
        try:
            payload = {
                "tool": "quick_generate",
                "arguments": {"prompt": "Write a one-liner to reverse a string in Python", "style": "concise"},
            }
            async with session.post(f"{base_url}/mcp/execute", json=payload) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    if result.get("success"):
                        print("   ✅ Quick generation successful!")
                        print(f"   Generated in: {result.get('raw_result', {}).get('execution_time', 'N/A')}s")
                        # Show result
                        response = result.get("result", "")
                        print(f"   Result preview: {response[:300]}...")
                    else:
                        print(f"   ❌ Generation failed: {result.get('error')}")
                else:
                    print(f"   ❌ Request failed: {resp.status}")
                    error_text = await resp.text()
                    print(f"   Error: {error_text}")
        except Exception as e:
            print(f"   ❌ Error: {e}")

        # Test 4: Explain code
        print("\n4. Testing code explanation...")
        try:
            test_code = """
def quicksort(arr):
    if len(arr) <= 1:
        return arr
    pivot = arr[len(arr) // 2]
    left = [x for x in arr if x < pivot]
    middle = [x for x in arr if x == pivot]
    right = [x for x in arr if x > pivot]
    return quicksort(left) + middle + quicksort(right)
"""
            payload = {"tool": "explain_code", "arguments": {"code": test_code, "focus": "algorithm complexity"}}
            async with session.post(f"{base_url}/mcp/execute", json=payload) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    if result.get("success"):
                        print("   ✅ Code explanation successful!")
                    else:
                        print(f"   ❌ Explanation failed: {result.get('error')}")
                else:
                    print(f"   ❌ Request failed: {resp.status}")
        except Exception as e:
            print(f"   ❌ Error: {e}")

        # Test 5: Convert code
        print("\n5. Testing code conversion...")
        try:
            python_code = """
def greet(name):
    return f"Hello, {name}!"
"""
            payload = {
                "tool": "convert_code",
                "arguments": {"code": python_code, "target_language": "JavaScript", "preserve_comments": True},
            }
            async with session.post(f"{base_url}/mcp/execute", json=payload) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    if result.get("success"):
                        print("   ✅ Code conversion successful!")
                    else:
                        print(f"   ❌ Conversion failed: {result.get('error')}")
                else:
                    print(f"   ❌ Request failed: {resp.status}")
        except Exception as e:
            print(f"   ❌ Error: {e}")

        # Test 6: Status check
        print("\n6. Testing status...")
        try:
            payload = {"tool": "crush_status", "arguments": {}}
            async with session.post(f"{base_url}/mcp/execute", json=payload) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    if result.get("success"):
                        status = result.get("status", {})
                        print("   ✅ Status check successful!")
                        print(f"   - Enabled: {status.get('enabled')}")
                        print(f"   - Timeout: {status.get('timeout')}s")
                        print(f"   - API Key Configured: {status.get('api_key_configured')}")
                        print(f"   - Statistics: {status.get('statistics', {})}")
                    else:
                        print(f"   ❌ Status check failed: {result.get('error')}")
                else:
                    print(f"   ❌ Request failed: {resp.status}")
        except Exception as e:
            print(f"   ❌ Error: {e}")

        # Test 7: Clear history
        print("\n7. Testing clear history...")
        try:
            payload = {"tool": "clear_crush_history", "arguments": {}}
            async with session.post(f"{base_url}/mcp/execute", json=payload) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    if result.get("success"):
                        print(f"   ✅ History cleared: {result.get('message')}")
                    else:
                        print(f"   ❌ Clear history failed: {result.get('error')}")
                else:
                    print(f"   ❌ Request failed: {resp.status}")
        except Exception as e:
            print(f"   ❌ Error: {e}")

        # Test 8: Test different styles
        print("\n8. Testing different generation styles...")
        styles = ["concise", "detailed", "explained"]
        for style in styles:
            try:
                payload = {
                    "tool": "quick_generate",
                    "arguments": {"prompt": "Create a function to check if a number is prime", "style": style},
                }
                async with session.post(f"{base_url}/mcp/execute", json=payload) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        if result.get("success"):
                            print(f"   ✅ Style '{style}' generation successful!")
                        else:
                            print(f"   ❌ Style '{style}' failed: {result.get('error')}")
                    else:
                        print(f"   ❌ Request failed for style '{style}': {resp.status}")
            except Exception as e:
                print(f"   ❌ Error with style '{style}': {e}")

    print("\n" + "=" * 50)
    print("✅ Crush MCP Server tests completed!")


if __name__ == "__main__":
    print("Starting Crush MCP Server test...")
    print("Make sure the server is running with:")
    print("  python -m tools.mcp.crush.server --mode http")
    print("Or in Docker:")
    print("  docker-compose up -d mcp-crush")
    print()

    asyncio.run(test_crush_server())
