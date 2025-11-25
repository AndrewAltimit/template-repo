#!/usr/bin/env python3
"""Test script for OpenCode MCP Server"""

import asyncio
import os
import sys
from pathlib import Path

import aiohttp

# Add parent directory to path
parent_dir = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(parent_dir))


async def test_opencode_server():
    """Test OpenCode MCP server endpoints"""
    base_url = "http://localhost:8014"

    print("🧪 Testing OpenCode MCP Server")
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
            print("   Make sure the server is running on port 8014")
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

        # Test 3: Consult for code generation
        print("\n3. Testing code generation consultation...")
        try:
            payload = {
                "tool": "consult_opencode",
                "arguments": {
                    "query": "Write a Python function to calculate fibonacci numbers with unit tests",
                    "mode": "generate",
                },
            }
            async with session.post(f"{base_url}/mcp/execute", json=payload) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    if result.get("success"):
                        print("   ✅ Code generation consultation successful!")
                        print(f"   Generated in: {result.get('raw_result', {}).get('execution_time', 'N/A')}s")
                        # Show first 200 chars of result
                        response = result.get("result", "")
                        if isinstance(response, str):
                            print(f"   Preview: {response[:200]}...")
                        else:
                            print(f"   Result type: {type(response)}")
                    else:
                        print(f"   ❌ Consultation failed: {result.get('error')}")
                else:
                    print(f"   ❌ Request failed: {resp.status}")
                    error_text = await resp.text()
                    print(f"   Error: {error_text}")
        except Exception as e:
            print(f"   ❌ Error: {e}")

        # Test 4: Consult for code refactoring
        print("\n4. Testing code refactoring consultation...")
        try:
            test_code = """
def calc(x, y):
    r = x + y
    return r
"""
            payload = {
                "tool": "consult_opencode",
                "arguments": {
                    "query": test_code,
                    "context": "Make this more readable with better variable names and add type hints",
                    "mode": "refactor",
                },
            }
            async with session.post(f"{base_url}/mcp/execute", json=payload) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    if result.get("success"):
                        print("   ✅ Code refactoring consultation successful!")
                    else:
                        print(f"   ❌ Consultation failed: {result.get('error')}")
                else:
                    print(f"   ❌ Request failed: {resp.status}")
        except Exception as e:
            print(f"   ❌ Error: {e}")

        # Test 5: Consult for code review
        print("\n5. Testing code review consultation...")
        try:
            payload = {
                "tool": "consult_opencode",
                "arguments": {
                    "query": test_code,
                    "context": "readability, best practices",
                    "mode": "review",
                },
            }
            async with session.post(f"{base_url}/mcp/execute", json=payload) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    if result.get("success"):
                        print("   ✅ Code review consultation successful!")
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
                "tool": "toggle_opencode_auto_consult",
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
            payload = {"tool": "opencode_status", "arguments": {}}
            async with session.post(f"{base_url}/mcp/execute", json=payload) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    if result.get("success"):
                        status = result.get("status", {})
                        print("   ✅ Status check successful!")
                        print(f"   - Enabled: {status.get('enabled')}")
                        print(f"   - Auto Consult: {status.get('auto_consult')}")
                        print(f"   - Model: {status.get('model')}")
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
            payload = {"tool": "clear_opencode_history", "arguments": {}}
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

    print("\n" + "=" * 50)
    print("✅ OpenCode MCP Server tests completed!")


if __name__ == "__main__":
    print("Starting OpenCode MCP Server test...")
    print("Make sure the server is running with:")
    print("  python -m tools.mcp.opencode.server --mode http")
    print("Or in Docker:")
    print("  docker-compose up -d mcp-opencode")
    print()

    asyncio.run(test_opencode_server())
