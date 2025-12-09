#!/usr/bin/env python3
"""
Test all available gestures including the new backflip gesture.

This script tests both the standard gesture interface and direct VRCEmote control.
"""

import asyncio
import json
import logging
import os
from typing import Any, Dict

import aiohttp

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Server configuration - use environment variables with sensible defaults
SERVER_URL = os.getenv("VIRTUAL_CHARACTER_SERVER", "http://localhost:8020")
REMOTE_HOST = os.getenv("VRCHAT_HOST", "127.0.0.1")  # VRChat machine IP


async def call_mcp_tool(session: aiohttp.ClientSession, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Call an MCP tool via JSON-RPC."""
    payload = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments},
        "id": 1,
    }

    try:
        async with session.post(f"{SERVER_URL}/mcp/messages", json=payload) as response:
            result = await response.json()
            if "error" in result:
                logger.error("Tool call error: %s", result["error"])
                return {"success": False, "error": result["error"]}
            parsed: Dict[str, Any] = json.loads(result["result"]["content"][0]["text"])
            return parsed
    except Exception as e:
        logger.error("Failed to call tool %s: %s", tool_name, e)
        return {"success": False, "error": str(e)}


async def test_standard_gestures(session: aiohttp.ClientSession):
    """Test all standard gestures using the gesture interface."""
    gestures = [
        "wave",
        "clap",
        "point",
        "thumbs_up",
        "nod",
        "shake_head",
        "dance",
        "backflip",  # New gesture!
        "cheer",
        "sadness",
        "die",
    ]

    logger.info("Testing standard gestures...")

    for gesture in gestures:
        logger.info(f"Testing gesture: {gesture}")
        result = await call_mcp_tool(session, "send_animation", {"gesture": gesture})

        if result.get("success"):
            logger.info(f"✓ {gesture} gesture sent successfully")
        else:
            logger.error(f"✗ Failed to send {gesture}: {result.get('error')}")

        # Wait for gesture to play
        await asyncio.sleep(2)

        # Clear gesture
        await call_mcp_tool(session, "send_animation", {"gesture": "none"})
        await asyncio.sleep(0.5)


async def test_vrcemote_direct(session: aiohttp.ClientSession):
    """Test direct VRCEmote control."""
    emotes = [
        (0, "Clear/None"),
        (1, "Wave"),
        (2, "Clap"),
        (3, "Point"),
        (4, "Cheer"),
        (5, "Dance"),
        (6, "Backflip"),  # The one we care about!
        (7, "Sadness"),
        (8, "Die"),
    ]

    logger.info("\nTesting direct VRCEmote control...")

    for value, name in emotes:
        logger.info(f"Testing VRCEmote {value}: {name}")
        result = await call_mcp_tool(session, "send_vrcemote", {"emote_value": value})

        if result.get("success"):
            logger.info(f"✓ VRCEmote {value} ({name}) sent successfully")
            logger.info(f"  Response: {result.get('message')}")
        else:
            logger.error(f"✗ Failed to send VRCEmote {value}: {result.get('error')}")

        # Wait for emote to play (skip wait for clear)
        if value != 0:
            await asyncio.sleep(2)
        else:
            await asyncio.sleep(0.5)


async def test_gesture_combinations(session: aiohttp.ClientSession):
    """Test gesture combinations with emotions."""
    combinations: list[Dict[str, Any]] = [
        {"gesture": "wave", "emotion": "happy"},
        {"gesture": "dance", "emotion": "excited"},
        {"gesture": "backflip", "emotion": "excited", "emotion_intensity": 1.0},
        {"gesture": "clap", "emotion": "happy"},
        {"gesture": "sadness", "emotion": "sad"},
    ]

    logger.info("\nTesting gesture + emotion combinations...")

    for combo in combinations:
        logger.info("Testing combination: %s", combo)
        result = await call_mcp_tool(session, "send_animation", combo)

        if result.get("success"):
            logger.info("✓ Combination sent successfully")
        else:
            logger.error(f"✗ Failed to send combination: {result.get('error')}")

        await asyncio.sleep(3)

        # Reset
        await call_mcp_tool(session, "reset", {})
        await asyncio.sleep(0.5)


async def test_sequence_with_backflip(session: aiohttp.ClientSession):
    """Test a sequence that includes a backflip."""
    logger.info("\nTesting sequence with backflip...")

    # Create sequence
    result = await call_mcp_tool(
        session, "create_sequence", {"name": "backflip_sequence", "description": "Epic backflip sequence"}
    )

    if not result.get("success"):
        logger.error(f"Failed to create sequence: {result.get('error')}")
        return

    # Add events
    events = [
        {"event_type": "animation", "timestamp": 0, "animation_params": {"gesture": "wave"}},
        {"event_type": "wait", "timestamp": 1, "wait_duration": 0.5},
        {"event_type": "animation", "timestamp": 1.5, "animation_params": {"gesture": "backflip", "emotion": "excited"}},
        {"event_type": "wait", "timestamp": 3.5, "wait_duration": 0.5},
        {"event_type": "animation", "timestamp": 4, "animation_params": {"gesture": "cheer"}},
    ]

    for event in events:
        result = await call_mcp_tool(session, "add_sequence_event", event)
        if not result.get("success"):
            logger.error(f"Failed to add event: {result.get('error')}")

    # Play sequence
    logger.info("Playing backflip sequence...")
    result = await call_mcp_tool(session, "play_sequence", {})

    if result.get("success"):
        logger.info("✓ Sequence started successfully")
        await asyncio.sleep(5)  # Let it play
    else:
        logger.error(f"✗ Failed to play sequence: {result.get('error')}")

    # Clean up
    await call_mcp_tool(session, "stop_sequence", {})
    await call_mcp_tool(session, "reset", {})


async def main():
    """Main test function."""
    logger.info("Starting Virtual Character Gesture Tests")
    logger.info("=" * 50)

    async with aiohttp.ClientSession() as session:
        # Connect to VRChat backend
        logger.info(f"Connecting to VRChat backend at {REMOTE_HOST}...")
        result = await call_mcp_tool(
            session,
            "set_backend",
            {
                "backend": "vrchat_remote",
                "config": {
                    "remote_host": REMOTE_HOST,
                    "use_vrcemote": True,
                },
            },
        )

        if not result.get("success"):
            logger.error(f"Failed to connect to backend: {result.get('error')}")
            return

        logger.info("✓ Connected to VRChat backend")
        await asyncio.sleep(1)

        # Run tests
        await test_standard_gestures(session)
        await test_vrcemote_direct(session)
        await test_gesture_combinations(session)
        await test_sequence_with_backflip(session)

        # Final reset
        logger.info("\nFinal reset...")
        await call_mcp_tool(session, "panic_reset", {})

        logger.info("\n" + "=" * 50)
        logger.info("All tests completed!")


if __name__ == "__main__":
    asyncio.run(main())
