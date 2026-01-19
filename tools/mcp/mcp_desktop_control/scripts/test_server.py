#!/usr/bin/env python3
"""Integration test script for Desktop Control MCP Server"""

import asyncio
import json
from pathlib import Path
import sys

# Add parent directories to path for imports
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root / "tools" / "mcp" / "mcp_core"))
sys.path.insert(0, str(project_root / "tools" / "mcp" / "mcp_desktop_control"))

import httpx


async def test_server(server_url: str = "http://localhost:8025"):
    """Test the Desktop Control MCP Server"""
    print(f"Testing Desktop Control MCP Server at {server_url}")
    print("=" * 60)

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Test 1: Health check
        print("\n1. Testing health endpoint...")
        try:
            response = await client.get(f"{server_url}/health")
            if response.status_code == 200:
                data = response.json()
                print(f"   Status: {data.get('status')}")
                print(f"   Server: {data.get('server')}")
                print(f"   Version: {data.get('version')}")
            else:
                print(f"   FAILED: Status code {response.status_code}")
                return False
        except Exception as e:
            print(f"   FAILED: {e}")
            return False

        # Test 2: List tools
        print("\n2. Testing tools listing...")
        try:
            response = await client.get(f"{server_url}/mcp/tools")
            if response.status_code == 200:
                data = response.json()
                tools = data.get("tools", [])
                print(f"   Found {len(tools)} tools:")
                for tool in tools[:5]:  # Show first 5
                    print(f"   - {tool['name']}: {tool.get('description', '')[:50]}...")
                if len(tools) > 5:
                    print(f"   ... and {len(tools) - 5} more")
            else:
                print(f"   FAILED: Status code {response.status_code}")
                return False
        except Exception as e:
            print(f"   FAILED: {e}")
            return False

        # Test 3: Desktop status
        print("\n3. Testing desktop_status...")
        try:
            response = await client.post(
                f"{server_url}/mcp/execute",
                json={"tool": "desktop_status", "arguments": {}},
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    result = data.get("result", {})
                    if isinstance(result, str):
                        result = json.loads(result)
                    print(f"   Available: {result.get('available')}")
                    print(f"   Platform: {result.get('platform')}")
                    print(f"   Screens: {result.get('screen_count')}")
                    res = result.get("primary_resolution", {})
                    print(f"   Resolution: {res.get('width')}x{res.get('height')}")
                else:
                    print(f"   Note: {data.get('result', {}).get('error', 'Backend not available')}")
            else:
                print(f"   FAILED: Status code {response.status_code}")
        except Exception as e:
            print(f"   FAILED: {e}")

        # Test 4: List screens
        print("\n4. Testing list_screens...")
        try:
            response = await client.post(
                f"{server_url}/mcp/execute",
                json={"tool": "list_screens", "arguments": {}},
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    result = data.get("result", {})
                    if isinstance(result, str):
                        result = json.loads(result)
                    screens = result.get("screens", [])
                    print(f"   Found {len(screens)} screen(s)")
                    for screen in screens:
                        print(f"   - Screen {screen.get('id')}: {screen.get('width')}x{screen.get('height')}")
                else:
                    print(f"   Note: {data.get('result', {}).get('error', 'Backend not available')}")
        except Exception as e:
            print(f"   FAILED: {e}")

        # Test 5: List windows
        print("\n5. Testing list_windows...")
        try:
            response = await client.post(
                f"{server_url}/mcp/execute",
                json={"tool": "list_windows", "arguments": {"visible_only": True}},
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    result = data.get("result", {})
                    if isinstance(result, str):
                        result = json.loads(result)
                    windows = result.get("windows", [])
                    print(f"   Found {len(windows)} visible window(s)")
                    for win in windows[:3]:  # Show first 3
                        title = win.get("title", "")[:40]
                        print(f"   - {win.get('id')}: {title}")
                    if len(windows) > 3:
                        print(f"   ... and {len(windows) - 3} more")
                else:
                    print(f"   Note: {data.get('result', {}).get('error', 'Backend not available')}")
        except Exception as e:
            print(f"   FAILED: {e}")

        # Test 6: Get mouse position
        print("\n6. Testing get_mouse_position...")
        try:
            response = await client.post(
                f"{server_url}/mcp/execute",
                json={"tool": "get_mouse_position", "arguments": {}},
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    result = data.get("result", {})
                    if isinstance(result, str):
                        result = json.loads(result)
                    print(f"   Position: ({result.get('x')}, {result.get('y')})")
                else:
                    print(f"   Note: {data.get('result', {}).get('error', 'Backend not available')}")
        except Exception as e:
            print(f"   FAILED: {e}")

        # Test 7: Screenshot (optional, may fail in headless)
        print("\n7. Testing screenshot_screen (may fail in headless environments)...")
        try:
            response = await client.post(
                f"{server_url}/mcp/execute",
                json={"tool": "screenshot_screen", "arguments": {}},
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    result = data.get("result", {})
                    if isinstance(result, str):
                        result = json.loads(result)
                    if result.get("success"):
                        size = result.get("size_bytes", 0)
                        print(f"   Screenshot captured: {size} bytes")
                        print(f"   Format: {result.get('format')}")
                    else:
                        print(f"   Note: {result.get('error', 'Screenshot failed')}")
                else:
                    print("   Note: Tool execution returned false")
        except Exception as e:
            print(f"   Note: {e}")

    print("\n" + "=" * 60)
    print("Integration tests completed!")
    return True


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Test Desktop Control MCP Server")
    parser.add_argument(
        "--url",
        default="http://localhost:8025",
        help="Server URL (default: http://localhost:8025)",
    )
    args = parser.parse_args()

    success = asyncio.run(test_server(args.url))
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
