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

        # Test 3: Consult for quick generation
        print("\n3. Testing quick generation consultation...")
        try:
            payload = {
                "tool": "consult_crush",
                "arguments": {
                    "query": "Write a one-liner to reverse a string in Python",
                    "mode": "quick",
                },
            }
            async with session.post(f"{base_url}/mcp/execute", json=payload) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    if result.get("success"):
                        print("   ✅ Quick generation consultation successful!")
                        print(f"   Generated in: {result.get('raw_result', {}).get('execution_time', 'N/A')}s")
                        # Show result
                        response = result.get("result", "")
                        print(f"   Result preview: {response[:300]}...")
                    else:
                        print(f"   ❌ Consultation failed: {result.get('error')}")
                else:
                    print(f"   ❌ Request failed: {resp.status}")
                    error_text = await resp.text()
                    print(f"   Error: {error_text}")
        except Exception as e:
            print(f"   ❌ Error: {e}")

        # Test 4: Consult for code explanation
        print("\n4. Testing code explanation consultation...")
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
            payload = {
                "tool": "consult_crush",
                "arguments": {
                    "query": test_code,
                    "context": "algorithm complexity",
                    "mode": "explain",
                },
            }
            async with session.post(f"{base_url}/mcp/execute", json=payload) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    if result.get("success"):
                        print("   ✅ Code explanation consultation successful!")
                    else:
                        print(f"   ❌ Consultation failed: {result.get('error')}")
                else:
                    print(f"   ❌ Request failed: {resp.status}")
        except Exception as e:
            print(f"   ❌ Error: {e}")

        # Test 5: Consult for code conversion
        print("\n5. Testing code conversion consultation...")
        try:
            python_code = """
def greet(name):
    return f"Hello, {name}!"
"""
            payload = {
                "tool": "consult_crush",
                "arguments": {
                    "query": python_code,
                    "context": "JavaScript",
                    "mode": "convert",
                },
            }
            async with session.post(f"{base_url}/mcp/execute", json=payload) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    if result.get("success"):
                        print("   ✅ Code conversion consultation successful!")
                    else:
                        print(f"   ❌ Consultation failed: {result.get('error')}")
                else:
                    print(f"   ❌ Request failed: {resp.status}")
        except Exception as e:
            print(f"   ❌ Error: {e}")

        # Test 6: Toggle auto-consultation
        print("\n6. Testing auto-consultation toggle...")
        try:
            payload = {
                "tool": "toggle_crush_auto_consult",
                "arguments": {"enable": False},
            }
            async with session.post(f"{base_url}/mcp/execute", json=payload) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    if result.get("success"):
                        print(f"   ✅ Auto-consultation toggle successful: {result.get('message')}")
                    else:
                        print(f"   ❌ Toggle failed: {result.get('error')}")
                else:
                    print(f"   ❌ Request failed: {resp.status}")
        except Exception as e:
            print(f"   ❌ Error: {e}")

        # Test 7: Status check
        print("\n7. Testing status...")
        try:
            payload = {"tool": "crush_status", "arguments": {}}
            async with session.post(f"{base_url}/mcp/execute", json=payload) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    if result.get("success"):
                        status = result.get("status", {})
                        print("   ✅ Status check successful!")
                        print(f"   - Enabled: {status.get('enabled')}")
                        print(f"   - Auto Consult: {status.get('auto_consult')}")
                        print(f"   - Timeout: {status.get('timeout')}s")
                        print(f"   - API Key Configured: {status.get('api_key_configured')}")
                        print(f"   - Statistics: {status.get('statistics', {})}")
                    else:
                        print(f"   ❌ Status check failed: {result.get('error')}")
                else:
                    print(f"   ❌ Request failed: {resp.status}")
        except Exception as e:
            print(f"   ❌ Error: {e}")

        # Test 8: Clear history
        print("\n8. Testing clear history...")
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

        # Test 9: Test different modes
        print("\n9. Testing different consultation modes...")
        test_cases = [
            {
                "mode": "quick",
                "query": "Create a function to check if a number is prime",
            },
            {
                "mode": "generate",
                "query": "Create a detailed function to check if a number is prime with comments",
            },
        ]
        for test in test_cases:
            try:
                payload = {
                    "tool": "consult_crush",
                    "arguments": test,
                }
                async with session.post(f"{base_url}/mcp/execute", json=payload) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        if result.get("success"):
                            print(f"   ✅ Mode '{test['mode']}' consultation successful!")
                        else:
                            print(f"   ❌ Mode '{test['mode']}' failed: {result.get('error')}")
                    else:
                        print(f"   ❌ Request failed for mode '{test['mode']}': {resp.status}")
            except Exception as e:
                print(f"   ❌ Error with mode '{test['mode']}': {e}")

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
