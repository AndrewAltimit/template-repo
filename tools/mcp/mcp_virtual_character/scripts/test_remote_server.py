#!/usr/bin/env python3
"""
Test Virtual Character MCP Server running remotely.

This script tests the MCP server HTTP endpoints from a client machine.
"""

import argparse
import asyncio
import logging
import os
from typing import Any, Dict, Optional

import aiohttp

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class RemoteVRChatTester:
    """Test remote Virtual Character MCP Server."""

    def __init__(self, server_url: str = "http://192.168.0.152:8020"):
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

    async def call_endpoint(self, method: str, endpoint: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Call MCP server endpoint."""
        url = f"{self.server_url}{endpoint}"

        try:
            if self.session is None:
                return {"success": False, "error": "Session not initialized"}

            if method == "POST":
                async with self.session.post(url, json=data) as response:
                    return await response.json()
            else:  # GET
                async with self.session.get(url) as response:
                    return await response.json()
        except aiohttp.ClientError as e:
            logger.error(f"Failed to connect to {url}: {e}")
            return {"success": False, "error": str(e)}
        except Exception as e:
            logger.error(f"Error calling {endpoint}: {e}")
            return {"success": False, "error": str(e)}

    async def connect_vrchat(self, vrchat_host: str = "127.0.0.1", use_vrcemote: bool = True):
        """Connect to VRChat backend on the remote server."""
        logger.info("Connecting to VRChat at %s via %s...", vrchat_host, self.server_url)

        config = {
            "remote_host": vrchat_host,  # VRChat host (localhost on Windows machine)
            "use_vrcemote": use_vrcemote,  # Use gesture wheel system
            "osc_in_port": 9000,
            "osc_out_port": 9001,
        }

        result = await self.call_endpoint("POST", "/set_backend", {"backend": "vrchat_remote", "config": config})

        if result.get("success"):
            logger.info("✅ Connected to VRChat backend successfully!")
        else:
            logger.error(f"❌ Failed to connect: {result.get('error')}")

        return result

    async def send_emotion(self, emotion: str):
        """Send emotion to avatar."""
        logger.info("Sending emotion: %s", emotion)

        result = await self.call_endpoint("POST", "/send_animation", {"emotion": emotion, "emotion_intensity": 1.0})

        if result.get("success"):
            logger.info("  ✅ %s sent", emotion)
        else:
            logger.error(f"  ❌ Failed: {result.get('error')}")

        return result

    async def send_gesture(self, gesture: str):
        """Send gesture to avatar."""
        logger.info("Sending gesture: %s", gesture)

        result = await self.call_endpoint("POST", "/send_animation", {"gesture": gesture, "gesture_intensity": 1.0})

        if result.get("success"):
            logger.info("  ✅ %s sent", gesture)
        else:
            logger.error(f"  ❌ Failed: {result.get('error')}")

        return result

    async def move_avatar(self, forward: float = 0, right: float = 0, look_h: float = 0):
        """Send movement to avatar."""
        logger.info(f"Moving: forward={forward}, right={right}, look_h={look_h}")

        parameters = {}
        if forward != 0:
            parameters["move_forward"] = forward
        if right != 0:
            parameters["move_right"] = right
        if look_h != 0:
            parameters["look_horizontal"] = look_h

        result = await self.call_endpoint("POST", "/send_animation", {"parameters": parameters})

        if result.get("success"):
            logger.info("  ✅ Movement sent")
        else:
            logger.error(f"  ❌ Failed: {result.get('error')}")

        return result

    async def execute_behavior(self, behavior: str):
        """Execute high-level behavior."""
        logger.info("Executing behavior: %s", behavior)

        result = await self.call_endpoint("POST", "/execute_behavior", {"behavior": behavior})

        if result.get("success"):
            logger.info("  ✅ %s executed", behavior)
        else:
            logger.error(f"  ❌ Failed: {result.get('error')}")

        return result

    async def get_status(self):
        """Get backend status."""
        logger.info("Getting backend status...")

        result = await self.call_endpoint("GET", "/get_backend_status")

        if result.get("success"):
            logger.info(f"  Backend: {result.get('backend')}")
            logger.info(f"  Connected: {result.get('connected')}")
            logger.info(f"  Health: {result.get('health')}")
            if "statistics" in result:
                stats = result["statistics"]
                logger.info(f"  OSC messages sent: {stats.get('osc_messages_sent', 0)}")
                logger.info(f"  Animation frames: {stats.get('animation_frames', 0)}")
        else:
            logger.error(f"  ❌ Failed: {result.get('error')}")

        return result

    async def list_backends(self):
        """List available backends."""
        logger.info("Listing available backends...")

        result = await self.call_endpoint("GET", "/list_backends")

        if result.get("success"):
            for backend in result.get("backends", []):
                status = "✓ ACTIVE" if backend["active"] else ""
                logger.info(f"  - {backend['name']}: {backend['class']} {status}")
        else:
            logger.error(f"  ❌ Failed: {result.get('error')}")

        return result


async def test_emotions(tester: RemoteVRChatTester):
    """Test emotion animations."""
    logger.info("\n═══ Testing Emotions (via Gesture Wheel) ═══")

    emotions = ["happy", "sad", "angry", "surprised", "fearful", "neutral"]

    for emotion in emotions:
        await tester.send_emotion(emotion)
        await asyncio.sleep(2)

    logger.info("✅ Emotion test complete!")


async def test_gestures(tester: RemoteVRChatTester):
    """Test gesture animations."""
    logger.info("\n═══ Testing Gestures ═══")

    gestures = ["wave", "point", "clap", "dance", "none"]

    for gesture in gestures:
        await tester.send_gesture(gesture)
        await asyncio.sleep(2)

    logger.info("✅ Gesture test complete!")


async def test_movement(tester: RemoteVRChatTester):
    """Test movement controls."""
    logger.info("\n═══ Testing Movement ═══")

    # Walk forward
    await tester.move_avatar(forward=0.7)
    await asyncio.sleep(2)
    await tester.move_avatar(forward=0)

    # Turn right
    await tester.move_avatar(look_h=0.5)
    await asyncio.sleep(2)
    await tester.move_avatar(look_h=0)

    # Strafe right
    await tester.move_avatar(right=0.7)
    await asyncio.sleep(2)
    await tester.move_avatar(right=0)

    logger.info("✅ Movement test complete!")


async def test_behaviors(tester: RemoteVRChatTester):
    """Test high-level behaviors."""
    logger.info("\n═══ Testing Behaviors ═══")

    behaviors = ["greet", "dance", "sit", "stand"]

    for behavior in behaviors:
        await tester.execute_behavior(behavior)
        await asyncio.sleep(3)

    logger.info("✅ Behavior test complete!")


async def main():
    """Main test function."""
    parser = argparse.ArgumentParser(description="Test remote Virtual Character MCP Server")
    parser.add_argument(
        "--server",
        default=os.getenv("VRCHAT_MCP_SERVER", "http://192.168.0.152:8020"),
        help="MCP server URL",
    )
    parser.add_argument(
        "--vrchat-host",
        default="127.0.0.1",
        help="VRChat host (localhost on Windows machine)",
    )
    parser.add_argument(
        "--test",
        choices=["all", "emotions", "gestures", "movement", "behaviors", "status"],
        default="status",
        help="What to test",
    )

    args = parser.parse_args()

    logger.info("🎮 Remote VRChat MCP Server Test")
    logger.info("=" * 40)
    logger.info(f"MCP Server: {args.server}")
    logger.info(f"VRChat Host: {args.vrchat_host}")
    logger.info("")

    async with RemoteVRChatTester(args.server) as tester:
        # Check server status first
        await tester.list_backends()

        if args.test != "status":
            # Connect to VRChat
            result = await tester.connect_vrchat(args.vrchat_host, use_vrcemote=True)

            if not result.get("success"):
                logger.error("Failed to connect to VRChat. Exiting.")
                return

            await asyncio.sleep(1)

        # Run tests
        if args.test == "all":
            await test_emotions(tester)
            await test_gestures(tester)
            await test_movement(tester)
            await test_behaviors(tester)
        elif args.test == "emotions":
            await test_emotions(tester)
        elif args.test == "gestures":
            await test_gestures(tester)
        elif args.test == "movement":
            await test_movement(tester)
        elif args.test == "behaviors":
            await test_behaviors(tester)

        # Final status
        await tester.get_status()

    logger.info("\n✅ Test complete!")


if __name__ == "__main__":
    asyncio.run(main())
