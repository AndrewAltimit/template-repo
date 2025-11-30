#!/usr/bin/env python3
"""Test script for Crush MCP Server"""

import asyncio
import os
from pathlib import Path
import sys
from typing import Any

import aiohttp

# Add parent directory to path
parent_dir = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(parent_dir))

BASE_URL = "http://localhost:8015"


async def _test_health(session: aiohttp.ClientSession) -> bool:
    """Test health endpoint. Returns True if server is healthy."""
    print("1. Testing health endpoint...")
    try:
        async with session.get(f"{BASE_URL}/health") as resp:
            if resp.status == 200:
                data = await resp.json()
                print(f"   Server is healthy: {data}")
                return True
            print(f"   Health check failed: {resp.status}")
    except Exception as e:
        print(f"   Failed to connect: {e}")
        print("   Make sure the server is running on port 8015")
    return False


async def _test_list_tools(session: aiohttp.ClientSession) -> None:
    """Test list tools endpoint."""
    print("\n2. Testing list tools...")
    try:
        async with session.get(f"{BASE_URL}/mcp/tools") as resp:
            if resp.status == 200:
                tools = await resp.json()
                print(f"   Available tools: {[t['name'] for t in tools.get('tools', [])]}")
            else:
                print(f"   Failed to list tools: {resp.status}")
    except Exception as e:
        print(f"   Error: {e}")


async def _execute_tool(session: aiohttp.ClientSession, tool: str, arguments: dict[str, Any]) -> dict[str, Any] | None:
    """Execute an MCP tool and return result or None on error."""
    try:
        async with session.post(f"{BASE_URL}/mcp/execute", json={"tool": tool, "arguments": arguments}) as resp:
            if resp.status == 200:
                result: dict[str, Any] = await resp.json()
                return result
            print(f"   Request failed: {resp.status}")
            error_text = await resp.text()
            print(f"   Error: {error_text}")
    except Exception as e:
        print(f"   Error: {e}")
    return None


async def _test_quick_generation(session: aiohttp.ClientSession) -> None:
    """Test quick generation consultation."""
    print("\n3. Testing quick generation consultation...")
    result = await _execute_tool(
        session, "consult_crush", {"query": "Write a one-liner to reverse a string in Python", "mode": "quick"}
    )
    if result:
        if result.get("success"):
            print("   Quick generation consultation successful!")
            print(f"   Generated in: {result.get('raw_result', {}).get('execution_time', 'N/A')}s")
            response = result.get("result", "")
            print(f"   Result preview: {response[:300]}...")
        else:
            print(f"   Consultation failed: {result.get('error')}")


async def _test_code_explanation(session: aiohttp.ClientSession) -> None:
    """Test code explanation consultation."""
    print("\n4. Testing code explanation consultation...")
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
    result = await _execute_tool(
        session, "consult_crush", {"query": test_code, "context": "algorithm complexity", "mode": "explain"}
    )
    if result:
        if result.get("success"):
            print("   Code explanation consultation successful!")
        else:
            print(f"   Consultation failed: {result.get('error')}")


async def _test_code_conversion(session: aiohttp.ClientSession) -> None:
    """Test code conversion consultation."""
    print("\n5. Testing code conversion consultation...")
    python_code = """
def greet(name):
    return f"Hello, {name}!"
"""
    result = await _execute_tool(session, "consult_crush", {"query": python_code, "context": "JavaScript", "mode": "convert"})
    if result:
        if result.get("success"):
            print("   Code conversion consultation successful!")
        else:
            print(f"   Consultation failed: {result.get('error')}")


async def _test_auto_toggle(session: aiohttp.ClientSession) -> None:
    """Test auto-consultation toggle."""
    print("\n6. Testing auto-consultation toggle...")
    result = await _execute_tool(session, "toggle_crush_auto_consult", {"enable": False})
    if result:
        if result.get("success"):
            print(f"   Auto-consultation toggle successful: {result.get('message')}")
        else:
            print(f"   Toggle failed: {result.get('error')}")


async def _test_status(session: aiohttp.ClientSession) -> None:
    """Test status check."""
    print("\n7. Testing status...")
    result = await _execute_tool(session, "crush_status", {})
    if result:
        if result.get("success"):
            status = result.get("status", {})
            print("   Status check successful!")
            print(f"   - Enabled: {status.get('enabled')}")
            print(f"   - Auto Consult: {status.get('auto_consult')}")
            print(f"   - Timeout: {status.get('timeout')}s")
            print(f"   - API Key Configured: {status.get('api_key_configured')}")
            print(f"   - Statistics: {status.get('statistics', {})}")
        else:
            print(f"   Status check failed: {result.get('error')}")


async def _test_clear_history(session: aiohttp.ClientSession) -> None:
    """Test clear history."""
    print("\n8. Testing clear history...")
    result = await _execute_tool(session, "clear_crush_history", {})
    if result:
        if result.get("success"):
            print(f"   History cleared: {result.get('message')}")
        else:
            print(f"   Clear history failed: {result.get('error')}")


async def _test_consultation_modes(session: aiohttp.ClientSession) -> None:
    """Test different consultation modes."""
    print("\n9. Testing different consultation modes...")
    test_cases = [
        {"mode": "quick", "query": "Create a function to check if a number is prime"},
        {"mode": "generate", "query": "Create a detailed function to check if a number is prime with comments"},
    ]
    for test in test_cases:
        result = await _execute_tool(session, "consult_crush", test)
        if result:
            if result.get("success"):
                print(f"   Mode '{test['mode']}' consultation successful!")
            else:
                print(f"   Mode '{test['mode']}' failed: {result.get('error')}")


async def test_crush_server():
    """Test Crush MCP server endpoints"""
    print("Testing Crush MCP Server")
    print("=" * 50)

    # Check if API key is set
    if not os.environ.get("OPENROUTER_API_KEY"):
        print("   Warning: OPENROUTER_API_KEY not set in environment")
        print("   Some tests may fail without a valid API key")
        print()

    async with aiohttp.ClientSession() as session:
        if not await _test_health(session):
            return

        await _test_list_tools(session)
        await _test_quick_generation(session)
        await _test_code_explanation(session)
        await _test_code_conversion(session)
        await _test_auto_toggle(session)
        await _test_status(session)
        await _test_clear_history(session)
        await _test_consultation_modes(session)

    print("\n" + "=" * 50)
    print("Crush MCP Server tests completed!")


if __name__ == "__main__":
    print("Starting Crush MCP Server test...")
    print("Make sure the server is running with:")
    print("  python -m tools.mcp.crush.server --mode http")
    print("Or in Docker:")
    print("  docker-compose up -d mcp-crush")
    print()

    asyncio.run(test_crush_server())
