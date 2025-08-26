#!/usr/bin/env python3
"""
Test VRChat through the Virtual Character MCP Server.

This script tests the VRChat backend via the MCP server HTTP interface.
"""

import argparse
import asyncio
import logging
import os

import aiohttp

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class VRChatMCPTester:
    """Test VRChat through MCP server."""

    def __init__(self, server_url: str = "http://localhost:8020"):
        """Initialize tester."""
        self.server_url = server_url
        self.session = None

    async def __aenter__(self):
        """Enter async context."""
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context."""
        if self.session:
            await self.session.close()

    async def execute_tool(self, tool: str, parameters: dict) -> dict:
        """Execute MCP tool."""
        url = f"{self.server_url}/mcp/execute"

        payload = {"tool": tool, "parameters": parameters}

        try:
            if self.session:
                async with self.session.post(url, json=payload) as response:
                    result = await response.json()
                    return result
            else:
                return {"success": False, "error": "Session not initialized"}
        except Exception as e:
            logger.error(f"Error executing tool {tool}: {e}")
            return {"success": False, "error": str(e)}

    async def list_backends(self):
        """List available backends."""
        logger.info("Listing available backends...")
        result = await self.execute_tool("list_backends", {})

        if result.get("success"):
            backends = result.get("backends", [])
            logger.info(f"Available backends: {len(backends)}")
            for backend in backends:
                logger.info(
                    f"  - {backend['name']}: {backend['class']} "
                    f"(loaded: {backend.get('loaded', False)}, "
                    f"active: {backend.get('active', False)})"
                )
        else:
            logger.error(f"Failed to list backends: {result.get('error')}")

        return result

    async def connect_vrchat(self, host: str = "192.168.0.152"):
        """Connect to VRChat backend."""
        logger.info(f"Connecting to VRChat at {host}...")

        config = {
            "remote_host": host,
            "use_bridge": False,
            "osc_in_port": 9000,
            "osc_out_port": 9001,
        }

        result = await self.execute_tool("set_backend", {"backend": "vrchat_remote", "config": config})

        if result.get("success"):
            logger.info("✓ Successfully connected to VRChat backend")
        else:
            logger.error(f"✗ Failed to connect: {result.get('error')}")

        return result

    async def get_status(self):
        """Get backend status."""
        logger.info("Getting backend status...")
        result = await self.execute_tool("get_backend_status", {})

        if result.get("success"):
            logger.info(f"Backend: {result.get('backend')}")
            logger.info(f"Health: {result.get('health')}")
            logger.info(f"Statistics: {result.get('statistics')}")
        else:
            logger.error(f"Failed to get status: {result.get('error')}")

        return result

    async def send_emotion(self, emotion: str, intensity: float = 1.0):
        """Send emotion to avatar."""
        logger.info(f"Setting emotion: {emotion} (intensity: {intensity})")

        result = await self.execute_tool("send_animation", {"emotion": emotion, "emotion_intensity": intensity})

        if result.get("success"):
            logger.info("✓ Emotion set successfully")
        else:
            logger.error(f"✗ Failed to set emotion: {result.get('error')}")

        return result

    async def send_gesture(self, gesture: str, intensity: float = 1.0):
        """Send gesture to avatar."""
        logger.info(f"Performing gesture: {gesture} (intensity: {intensity})")

        result = await self.execute_tool("send_animation", {"gesture": gesture, "gesture_intensity": intensity})

        if result.get("success"):
            logger.info("✓ Gesture performed successfully")
        else:
            logger.error(f"✗ Failed to perform gesture: {result.get('error')}")

        return result

    async def move_avatar(self, forward: float = 0, right: float = 0, look_h: float = 0, look_v: float = 0):
        """Move avatar."""
        logger.info(f"Moving: forward={forward}, right={right}, " f"look_h={look_h}, look_v={look_v}")

        parameters = {}
        if forward != 0:
            parameters["move_forward"] = forward
        if right != 0:
            parameters["move_right"] = right
        if look_h != 0:
            parameters["look_horizontal"] = look_h
        if look_v != 0:
            parameters["look_vertical"] = look_v

        result = await self.execute_tool("send_animation", {"parameters": parameters})

        if result.get("success"):
            logger.info("✓ Movement command sent")
        else:
            logger.error(f"✗ Failed to move: {result.get('error')}")

        return result

    async def execute_behavior(self, behavior: str):
        """Execute high-level behavior."""
        logger.info(f"Executing behavior: {behavior}")

        result = await self.execute_tool("execute_behavior", {"behavior": behavior})

        if result.get("success"):
            logger.info("✓ Behavior executed successfully")
        else:
            logger.error(f"✗ Failed to execute behavior: {result.get('error')}")

        return result

    async def get_state(self):
        """Get environment state."""
        logger.info("Getting environment state...")

        result = await self.execute_tool("receive_state", {})

        if result.get("success"):
            state = result.get("state", {})
            logger.info(f"World: {state.get('world_name', 'Unknown')}")
            logger.info(f"Position: {state.get('agent_position', [0, 0, 0])}")
            logger.info(f"Rotation: {state.get('agent_rotation', [0, 0, 0])}")
        else:
            logger.error(f"Failed to get state: {result.get('error')}")

        return result


async def test_emotion_cycle(tester: VRChatMCPTester):
    """Test emotion changes."""
    logger.info("\n=== Testing Emotion Cycle ===")

    emotions = ["neutral", "happy", "sad", "angry", "surprised", "fearful"]

    for emotion in emotions:
        await tester.send_emotion(emotion)
        await asyncio.sleep(2)

    # Return to neutral
    await tester.send_emotion("neutral")


async def test_gesture_sequence(tester: VRChatMCPTester):
    """Test gesture sequence."""
    logger.info("\n=== Testing Gesture Sequence ===")

    gestures = ["wave", "point", "thumbs_up", "nod", "shake_head"]

    for gesture in gestures:
        await tester.send_gesture(gesture)
        await asyncio.sleep(3)

    # Clear gesture
    await tester.send_gesture("none")


async def test_movement_pattern(tester: VRChatMCPTester):
    """Test movement pattern."""
    logger.info("\n=== Testing Movement Pattern ===")

    # Move forward
    logger.info("Moving forward...")
    await tester.move_avatar(forward=1.0)
    await asyncio.sleep(2)
    await tester.move_avatar(forward=0)

    # Turn right
    logger.info("Turning right...")
    await tester.move_avatar(look_h=0.5)
    await asyncio.sleep(2)
    await tester.move_avatar(look_h=0)

    # Strafe right
    logger.info("Strafing right...")
    await tester.move_avatar(right=1.0)
    await asyncio.sleep(2)
    await tester.move_avatar(right=0)

    # Move backward
    logger.info("Moving backward...")
    await tester.move_avatar(forward=-1.0)
    await asyncio.sleep(2)
    await tester.move_avatar(forward=0)


async def test_behaviors(tester: VRChatMCPTester):
    """Test high-level behaviors."""
    logger.info("\n=== Testing Behaviors ===")

    behaviors = ["greet", "sit", "stand", "dance"]

    for behavior in behaviors:
        await tester.execute_behavior(behavior)
        await asyncio.sleep(3)


async def test_combined(tester: VRChatMCPTester):
    """Test combined animations."""
    logger.info("\n=== Testing Combined Animations ===")

    # Happy wave while moving forward
    logger.info("Happy wave while moving...")
    await tester.send_emotion("happy")
    await tester.send_gesture("wave")
    await tester.move_avatar(forward=0.5)
    await asyncio.sleep(3)

    # Stop and return to neutral
    await tester.move_avatar(forward=0)
    await tester.send_emotion("neutral")
    await tester.send_gesture("none")


async def main():
    """Main test function."""
    parser = argparse.ArgumentParser(description="Test VRChat via MCP Server")
    parser.add_argument("--server", default="http://localhost:8020", help="MCP server URL")
    parser.add_argument("--vrchat-host", default=os.getenv("VRCHAT_HOST", "192.168.0.152"), help="VRChat host IP address")
    parser.add_argument(
        "--test",
        choices=["all", "emotions", "gestures", "movement", "behaviors", "combined"],
        default="all",
        help="Which test to run",
    )

    args = parser.parse_args()

    async with VRChatMCPTester(args.server) as tester:
        # List available backends
        await tester.list_backends()

        # Connect to VRChat
        result = await tester.connect_vrchat(args.vrchat_host)
        if not result.get("success"):
            logger.error("Failed to connect to VRChat. Exiting.")
            return

        # Get initial status
        await tester.get_status()
        await tester.get_state()

        # Run tests
        if args.test == "all":
            await test_emotion_cycle(tester)
            await asyncio.sleep(2)
            await test_gesture_sequence(tester)
            await asyncio.sleep(2)
            await test_movement_pattern(tester)
            await asyncio.sleep(2)
            await test_behaviors(tester)
            await asyncio.sleep(2)
            await test_combined(tester)
        elif args.test == "emotions":
            await test_emotion_cycle(tester)
        elif args.test == "gestures":
            await test_gesture_sequence(tester)
        elif args.test == "movement":
            await test_movement_pattern(tester)
        elif args.test == "behaviors":
            await test_behaviors(tester)
        elif args.test == "combined":
            await test_combined(tester)

        # Final status
        await tester.get_status()

        logger.info("\n=== Test Complete ===")


if __name__ == "__main__":
    asyncio.run(main())
