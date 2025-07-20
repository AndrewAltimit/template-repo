#!/usr/bin/env python3
"""Test script for Gemini MCP Server"""

import asyncio
import json  # noqa: F401
import os
import sys
from pathlib import Path  # noqa: F401

import httpx


async def test_gemini_server(base_url: str = "http://localhost:8006"):
    """Test Gemini MCP Server endpoints"""

    # Check if running in container
    if os.path.exists("/.dockerenv") or os.environ.get("CONTAINER_ENV"):
        print("ERROR: This test cannot run inside a container!")
        print("The Gemini MCP Server must run on the host system.")
        sys.exit(1)

    async with httpx.AsyncClient() as client:
        print("Testing Gemini MCP Server...")
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

        # Test Gemini status
        print("\n--- Testing Gemini status ---")
        try:
            response = await client.post(
                f"{base_url}/mcp/execute",
                json={"tool": "gemini_status", "arguments": {}},
            )
            result = response.json()
            if result["success"]:
                print("✓ Gemini status retrieved")
                status = result["result"]["status"]
                print(f"  Enabled: {status.get('enabled', 'Unknown')}")
                print(f"  Auto-consult: {status.get('auto_consult', 'Unknown')}")
                print(f"  Model: {status.get('model', 'Unknown')}")
            else:
                print(f"✗ Failed to get status: {result['error']}")
        except Exception as e:
            print(f"✗ Status check error: {e}")

        # Test clearing history
        print("\n--- Testing clear history ---")
        try:
            response = await client.post(
                f"{base_url}/mcp/execute",
                json={"tool": "clear_gemini_history", "arguments": {}},
            )
            result = response.json()
            if result["success"]:
                print(f"✓ History cleared: {result['result'].get('message', 'Success')}")
            else:
                print(f"✗ Failed to clear history: {result['error']}")
        except Exception as e:
            print(f"✗ Clear history error: {e}")

        # Test consultation (simple query)
        print("\n--- Testing Gemini consultation ---")
        try:
            response = await client.post(
                f"{base_url}/mcp/execute",
                json={
                    "tool": "consult_gemini",
                    "arguments": {
                        "query": "What is the purpose of an MCP server?",
                        "context": "Testing Gemini integration",
                        "comparison_mode": False,
                    },
                },
                timeout=30.0,  # Gemini might take time
            )
            result = response.json()
            if result["success"]:
                print("✓ Gemini consultation completed")
                # Print first 200 chars of response
                response_text = result["result"].get("result", "")
                if response_text:
                    print(f"  Response preview: {response_text[:200]}...")
            else:
                print(f"✗ Consultation failed: {result.get('error', result['result'].get('error'))}")
        except Exception as e:
            print(f"✗ Consultation error: {e}")

        # Test toggle auto-consult
        print("\n--- Testing auto-consult toggle ---")
        try:
            # First disable
            response = await client.post(
                f"{base_url}/mcp/execute",
                json={
                    "tool": "toggle_gemini_auto_consult",
                    "arguments": {"enable": False},
                },
            )
            result = response.json()
            if result["success"]:
                print(f"✓ Auto-consult disabled: {result['result'].get('message', 'Success')}")

            # Then enable
            response = await client.post(
                f"{base_url}/mcp/execute",
                json={
                    "tool": "toggle_gemini_auto_consult",
                    "arguments": {"enable": True},
                },
            )
            result = response.json()
            if result["success"]:
                print(f"✓ Auto-consult enabled: {result['result'].get('message', 'Success')}")
        except Exception as e:
            print(f"✗ Toggle error: {e}")

        print("\n✅ Gemini MCP Server tests completed!")
        print("\nNote: Some tests may fail if Gemini CLI is not installed or configured.")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        base_url = sys.argv[1]
    else:
        base_url = "http://localhost:8006"

    asyncio.run(test_gemini_server(base_url))
