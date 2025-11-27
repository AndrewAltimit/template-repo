#!/usr/bin/env python3
"""
Test script for Virtual Character MCP Server.

This script tests the basic functionality of the server.
"""

import asyncio
import logging
import sys
from pathlib import Path

import aiohttp

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
# pylint: disable=wrong-import-position  # Imports must come after sys.path modification

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_server():
    """Test the Virtual Character MCP Server."""

    base_url = "http://localhost:8020"

    async with aiohttp.ClientSession() as session:
        # Test 1: Health check
        logger.info("Testing health check...")
        async with session.get(f"{base_url}/health") as resp:
            assert resp.status == 200
            data = await resp.json()
            logger.info("Health check response: %s", data)

        # Test 2: List available tools
        logger.info("\nTesting list tools...")
        async with session.get(f"{base_url}/mcp/tools") as resp:
            assert resp.status == 200
            tools = await resp.json()
            logger.info("Available tools: %s tools", len(tools))
            for tool in tools[:3]:  # Show first 3 tools
                logger.info("  - %s: %s", tool["name"], tool["description"])

        # Test 3: List backends
        logger.info("\nTesting list backends...")
        async with session.post(f"{base_url}/mcp/execute", json={"tool": "list_backends", "parameters": {}}) as resp:
            assert resp.status == 200
            result = await resp.json()
            logger.info("List backends result: %s", result)

        # Test 4: Set backend to mock
        logger.info("\nTesting set backend to mock...")
        async with session.post(
            f"{base_url}/mcp/execute",
            json={
                "tool": "set_backend",
                "parameters": {"backend": "mock", "config": {"world_name": "TestWorld", "simulate_events": False}},
            },
        ) as resp:
            assert resp.status == 200
            result = await resp.json()
            logger.info("Set backend result: %s", result)

        # Test 5: Send animation
        logger.info("\nTesting send animation...")
        async with session.post(
            f"{base_url}/mcp/execute",
            json={
                "tool": "send_animation",
                "parameters": {"emotion": "happy", "gesture": "wave", "blend_shapes": {"smile": 0.8, "eyebrows_up": 0.3}},
            },
        ) as resp:
            assert resp.status == 200
            result = await resp.json()
            logger.info("Send animation result: %s", result)

        # Test 6: Capture view
        logger.info("\nTesting capture view...")
        async with session.post(
            f"{base_url}/mcp/execute", json={"tool": "capture_view", "parameters": {"format": "jpeg"}}
        ) as resp:
            assert resp.status == 200
            result = await resp.json()
            if result.get("success") and result.get("result", {}).get("frame"):
                frame_data = result["result"]["frame"]
                logger.info(
                    "Captured frame: %sx%s format=%s, frame_number=%s",
                    frame_data["width"],
                    frame_data["height"],
                    frame_data["format"],
                    frame_data["frame_number"],
                )
            else:
                logger.info("Capture view result: %s", result)

        # Test 7: Receive state
        logger.info("\nTesting receive state...")
        async with session.post(f"{base_url}/mcp/execute", json={"tool": "receive_state", "parameters": {}}) as resp:
            assert resp.status == 200
            result = await resp.json()
            if result.get("success") and result.get("result", {}).get("state"):
                state = result["result"]["state"]
                logger.info(
                    "Environment state: world=%s, nearby_agents=%s, nearby_objects=%s",
                    state.get("world_name"),
                    len(state.get("nearby_agents", [])),
                    len(state.get("nearby_objects", [])),
                )
            else:
                logger.info("Receive state result: %s", result)

        # Test 8: Execute behavior
        logger.info("\nTesting execute behavior...")
        async with session.post(
            f"{base_url}/mcp/execute",
            json={"tool": "execute_behavior", "parameters": {"behavior": "greet", "parameters": {"target": "TestUser"}}},
        ) as resp:
            assert resp.status == 200
            result = await resp.json()
            logger.info("Execute behavior result: %s", result)

        # Test 9: Change environment
        logger.info("\nTesting change environment...")
        async with session.post(
            f"{base_url}/mcp/execute",
            json={
                "tool": "change_environment",
                "parameters": {"environment": "VirtualOffice", "parameters": {"x": 10.0, "y": 0.0, "z": 5.0}},
            },
        ) as resp:
            assert resp.status == 200
            result = await resp.json()
            logger.info("Change environment result: %s", result)

        # Test 10: Get backend status
        logger.info("\nTesting get backend status...")
        async with session.post(f"{base_url}/mcp/execute", json={"tool": "get_backend_status", "parameters": {}}) as resp:
            assert resp.status == 200
            result = await resp.json()
            logger.info("Backend status result: %s", result)

        # Test 11: Get server stats
        logger.info("\nTesting get server stats...")
        async with session.get(f"{base_url}/mcp/stats") as resp:
            assert resp.status == 200
            stats = await resp.json()
            logger.info("Server stats: %s", stats)

        logger.info("\n✅ All tests passed!")


async def main():
    """Main entry point."""
    try:
        # Wait a bit for server to be ready
        logger.info("Waiting for server to be ready...")
        await asyncio.sleep(2)

        # Run tests
        await test_server()

    except aiohttp.ClientConnectorError:
        logger.error("Could not connect to server. Is it running on port 8020?")
        sys.exit(1)
    except Exception as e:
        logger.error("Test failed: %s", e)
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
