#!/usr/bin/env python3
"""Test script for Code Quality MCP Server"""

import asyncio
import json  # noqa: F401
import sys
from pathlib import Path

import httpx


async def test_code_quality_server(base_url: str = "http://localhost:8010"):
    """Test Code Quality MCP Server endpoints"""

    async with httpx.AsyncClient() as client:
        print("Testing Code Quality MCP Server...")
        print(f"Base URL: {base_url}\n")

        # Test health endpoint
        try:
            response = await client.get(f"{base_url}/health")
            print(f"✓ Health check: {response.json()}")
        except Exception as e:
            print(f"✗ Health check failed: {e}")
            return

        # Test listing tools
        try:
            response = await client.get(f"{base_url}/mcp/tools")
            tools = response.json()
            print(f"\n✓ Available tools: {len(tools['tools'])} tools")
            for tool in tools["tools"]:
                print(f"  - {tool['name']}: {tool['description']}")
        except Exception as e:
            print(f"✗ Failed to list tools: {e}")

        # Test format check
        print("\n--- Testing format_check ---")
        test_file = Path(__file__)

        try:
            response = await client.post(
                f"{base_url}/mcp/execute",
                json={
                    "tool": "format_check",
                    "arguments": {"path": str(test_file), "language": "python"},
                },
            )
            result = response.json()
            if result["success"]:
                print("✓ Format check completed")
                print(f"  Formatted: {result['result']['formatted']}")
                if result["result"].get("output"):
                    print(f"  Output: {result['result']['output'][:100]}...")
            else:
                print(f"✗ Format check failed: {result['error']}")
        except Exception as e:
            print(f"✗ Format check error: {e}")

        # Test linting
        print("\n--- Testing lint ---")
        try:
            response = await client.post(
                f"{base_url}/mcp/execute",
                json={
                    "tool": "lint",
                    "arguments": {"path": str(test_file), "linter": "flake8"},
                },
            )
            result = response.json()
            if result["success"]:
                print("✓ Lint check completed")
                print(f"  Passed: {result['result']['passed']}")
                print(f"  Issues found: {result['result']['issue_count']}")
                if result["result"]["issues"]:
                    print(f"  First issue: {result['result']['issues'][0]}")
            else:
                print(f"✗ Lint check failed: {result['error']}")
        except Exception as e:
            print(f"✗ Lint check error: {e}")

        # Test unsupported language
        print("\n--- Testing error handling ---")
        try:
            response = await client.post(
                f"{base_url}/mcp/execute",
                json={
                    "tool": "format_check",
                    "arguments": {"path": "test.xyz", "language": "cobol"},
                },
            )
            result = response.json()
            if not result["success"] or "error" in result["result"]:
                print("✓ Error handling works correctly")
                print(f"  Error: {result.get('error') or result['result'].get('error')}")
            else:
                print("✗ Expected error for unsupported language")
        except Exception as e:
            print(f"✗ Error handling test failed: {e}")

        print("\n✅ Code Quality MCP Server tests completed!")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        base_url = sys.argv[1]
    else:
        base_url = "http://localhost:8010"

    asyncio.run(test_code_quality_server(base_url))
