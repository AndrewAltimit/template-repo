#!/usr/bin/env python3
"""Test script for OpenCode MCP Server"""

import asyncio
import os
from pathlib import Path
import sys
from typing import Any

import aiohttp

# Add parent directory to path
parent_dir = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(parent_dir))

BASE_URL = "http://localhost:8014"

# Test code used in multiple tests
TEST_CODE = """
def calc(x, y):
    r = x + y
    return r
"""


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
        print("   Make sure the server is running on port 8014")
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


async def _test_code_generation(session: aiohttp.ClientSession) -> None:
    """Test code generation consultation."""
    print("\n3. Testing code generation consultation...")
    result = await _execute_tool(
        session,
        "consult_opencode",
        {"query": "Write a Python function to calculate fibonacci numbers with unit tests", "mode": "generate"},
    )
    if result:
        if result.get("success"):
            print("   Code generation consultation successful!")
            print(f"   Generated in: {result.get('raw_result', {}).get('execution_time', 'N/A')}s")
            response = result.get("result", "")
            if isinstance(response, str):
                print(f"   Preview: {response[:200]}...")
            else:
                print(f"   Result type: {type(response)}")
        else:
            print(f"   Consultation failed: {result.get('error')}")


async def _test_code_refactoring(session: aiohttp.ClientSession) -> None:
    """Test code refactoring consultation."""
    print("\n4. Testing code refactoring consultation...")
    result = await _execute_tool(
        session,
        "consult_opencode",
        {
            "query": TEST_CODE,
            "context": "Make this more readable with better variable names and add type hints",
            "mode": "refactor",
        },
    )
    if result:
        if result.get("success"):
            print("   Code refactoring consultation successful!")
        else:
            print(f"   Consultation failed: {result.get('error')}")


async def _test_code_review(session: aiohttp.ClientSession) -> None:
    """Test code review consultation."""
    print("\n5. Testing code review consultation...")
    result = await _execute_tool(
        session, "consult_opencode", {"query": TEST_CODE, "context": "readability, best practices", "mode": "review"}
    )
    if result:
        if result.get("success"):
            print("   Code review consultation successful!")
        else:
            print(f"   Consultation failed: {result.get('error')}")


async def _test_auto_toggle(session: aiohttp.ClientSession) -> None:
    """Test auto-consultation toggle."""
    print("\n6. Testing auto-consultation toggle...")
    result = await _execute_tool(session, "toggle_opencode_auto_consult", {"enable": False})
    if result:
        if result.get("success"):
            print(f"   Auto-consultation toggle successful: {result.get('message')}")
        else:
            print(f"   Toggle failed: {result.get('error')}")


async def _test_status(session: aiohttp.ClientSession) -> None:
    """Test status check."""
    print("\n7. Testing status...")
    result = await _execute_tool(session, "opencode_status", {})
    if result:
        if result.get("success"):
            status = result.get("status", {})
            print("   Status check successful!")
            print(f"   - Enabled: {status.get('enabled')}")
            print(f"   - Auto Consult: {status.get('auto_consult')}")
            print(f"   - Model: {status.get('model')}")
            print(f"   - API Key Configured: {status.get('api_key_configured')}")
            print(f"   - Statistics: {status.get('statistics', {})}")
        else:
            print(f"   Status check failed: {result.get('error')}")


async def _test_clear_history(session: aiohttp.ClientSession) -> None:
    """Test clear history."""
    print("\n8. Testing clear history...")
    result = await _execute_tool(session, "clear_opencode_history", {})
    if result:
        if result.get("success"):
            print(f"   History cleared: {result.get('message')}")
        else:
            print(f"   Clear history failed: {result.get('error')}")


async def test_opencode_server():
    """Test OpenCode MCP server endpoints"""
    print("Testing OpenCode MCP Server")
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
        await _test_code_generation(session)
        await _test_code_refactoring(session)
        await _test_code_review(session)
        await _test_auto_toggle(session)
        await _test_status(session)
        await _test_clear_history(session)

    print("\n" + "=" * 50)
    print("OpenCode MCP Server tests completed!")


if __name__ == "__main__":
    print("Starting OpenCode MCP Server test...")
    print("Make sure the server is running with:")
    print("  python -m tools.mcp.opencode.server --mode http")
    print("Or in Docker:")
    print("  docker-compose up -d mcp-opencode")
    print()

    asyncio.run(test_opencode_server())
