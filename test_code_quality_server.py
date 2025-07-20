#!/usr/bin/env python3
"""Direct test of Code Quality MCP server"""

import asyncio
import json

import httpx


async def test_server():
    base_url = "http://localhost:8010"

    async with httpx.AsyncClient() as client:
        # Test health
        response = await client.get(f"{base_url}/health")
        print(f"Health check: {response.json()}")

        # Test listing tools
        response = await client.get(f"{base_url}/mcp/tools")
        tools = response.json()
        print(f"\nAvailable tools: {len(tools['tools'])} tools")
        for tool in tools["tools"]:
            print(f"  - {tool['name']}: {tool['description']}")

        # Test format check
        print("\n--- Testing format_check ---")
        response = await client.post(
            f"{base_url}/mcp/execute",
            json={
                "tool": "format_check",
                "arguments": {"path": __file__, "language": "python"},
            },
        )
        result = response.json()
        print(f"Result: {json.dumps(result, indent=2)}")


if __name__ == "__main__":
    asyncio.run(test_server())
