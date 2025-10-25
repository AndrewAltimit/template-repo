#!/usr/bin/env python3
"""Test script for GitHub Board MCP Server"""

import asyncio
import sys
from pathlib import Path

import aiohttp

# Add paths for imports (if needed)
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))


async def test_server(base_url: str = "http://localhost:8021"):
    """Test GitHub Board MCP server endpoints"""
    print(f"Testing GitHub Board MCP Server at {base_url}")
    print("=" * 60)

    async with aiohttp.ClientSession() as session:
        # Test 1: Health Check
        print("\n1. Testing health check...")
        try:
            async with session.get(f"{base_url}/health") as resp:
                data = await resp.json()
                print(f"   Status: {resp.status}")
                print(f"   Response: {data}")
                assert resp.status == 200, "Health check failed"
                assert data["status"] == "healthy", "Server not healthy"
                print("   ✓ Health check passed")
        except Exception as e:
            print(f"   ✗ Health check failed: {e}")
            return False

        # Test 2: List Tools
        print("\n2. Testing list tools...")
        try:
            async with session.get(f"{base_url}/mcp/tools") as resp:
                data = await resp.json()
                print(f"   Status: {resp.status}")
                print(f"   Tools available: {len(data.get('tools', []))}")
                assert resp.status == 200, "List tools failed"
                assert "tools" in data, "No tools returned"
                print("   Available tools:")
                for tool_name in data["tools"]:
                    print(f"     - {tool_name}")
                print("   ✓ List tools passed")
        except Exception as e:
            print(f"   ✗ List tools failed: {e}")

        # Test 3: Get Board Config (if server is initialized)
        print("\n3. Testing get_board_config...")
        try:
            async with session.post(
                f"{base_url}/mcp/execute",
                json={"tool": "get_board_config", "arguments": {}},
            ) as resp:
                data = await resp.json()
                print(f"   Status: {resp.status}")
                if data.get("success"):
                    result = data.get("result", {})
                    print(f"   Project: #{result.get('project_number')}")
                    print(f"   Owner: {result.get('owner')}")
                    print(f"   Repository: {result.get('repository')}")
                    print(f"   Enabled agents: {result.get('enabled_agents')}")
                    print("   ✓ Get board config passed")
                else:
                    print("   ⚠ Config not loaded (expected if GITHUB_TOKEN not set)")
                    print(f"   Error: {data.get('error')}")
        except Exception as e:
            print(f"   ✗ Get board config failed: {e}")

        # Test 4: List Agents
        print("\n4. Testing list_agents...")
        try:
            async with session.post(
                f"{base_url}/mcp/execute",
                json={"tool": "list_agents", "arguments": {}},
            ) as resp:
                data = await resp.json()
                print(f"   Status: {resp.status}")
                if data.get("success"):
                    result = data.get("result", {})
                    print(f"   Agents: {result.get('agents')}")
                    print("   ✓ List agents passed")
                else:
                    print(f"   ⚠ {data.get('error')}")
        except Exception as e:
            print(f"   ✗ List agents failed: {e}")

    print("\n" + "=" * 60)
    print("Server tests complete!")
    return True


async def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Test GitHub Board MCP Server")
    parser.add_argument(
        "--url",
        default="http://localhost:8021",
        help="Server URL (default: http://localhost:8021)",
    )
    args = parser.parse_args()

    await test_server(args.url)


if __name__ == "__main__":
    asyncio.run(main())
