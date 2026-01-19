#!/usr/bin/env python3
"""
Basic OSC test for ANY VRChat avatar.

This tests only universal inputs that work with all avatars,
and helps discover what parameters your specific avatar supports.
"""

import argparse
import asyncio
import logging
import os
from pathlib import Path
import sys
from typing import Any, Dict

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))


try:
    from pythonosc import udp_client
    from pythonosc.dispatcher import Dispatcher
    from pythonosc.osc_server import AsyncIOOSCUDPServer

    HAS_OSC = True
except ImportError:
    print("ERROR: python-osc not installed!")
    print("Install with: pip install python-osc")
    sys.exit(1)

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class VRChatOSCTester:
    """Simple OSC tester for VRChat."""

    def __init__(self, host: str = "127.0.0.1"):
        self.host = host
        self.client = None
        self.server = None
        self.received_params: Dict[str, Any] = {}

    async def connect(self):
        """Connect to VRChat OSC."""
        # Create client for sending
        self.client = udp_client.SimpleUDPClient(self.host, 9000)

        # Create server for receiving
        dispatcher = Dispatcher()
        dispatcher.map("/avatar/parameters/*", self.param_handler)

        self.server = AsyncIOOSCUDPServer(("0.0.0.0", 9001), dispatcher, asyncio.get_event_loop())

        _transport, _protocol = await self.server.create_serve_endpoint()
        logger.info("Connected to VRChat at %s:9000", self.host)
        logger.info("Listening for parameters on port 9001")

    def param_handler(self, address: str, *args):
        """Handle received parameters."""
        param_name = address.replace("/avatar/parameters/", "")
        if args:
            self.received_params[param_name] = args[0]
            logger.info("📥 Received: %s = %s", param_name, args[0])

    def send(self, address: str, value):
        """Send OSC message."""
        if self.client:
            self.client.send_message(address, value)
            logger.info("📤 Sent: %s = %s", address, value)


async def test_universal_inputs(tester: VRChatOSCTester):
    """Test inputs that work with ANY avatar."""
    logger.info("\n═══ Testing Universal Inputs (work with any avatar) ═══\n")

    # Movement tests
    logger.info("🚶 Testing movement (these should always work):")

    movements = [
        ("Walking forward", "/input/Vertical", 1.0, 2),
        ("Walking backward", "/input/Vertical", -1.0, 2),
        ("Strafing right", "/input/Horizontal", 1.0, 2),
        ("Strafing left", "/input/Horizontal", -1.0, 2),
        ("Turning right", "/input/LookHorizontal", 0.5, 2),
        ("Turning left", "/input/LookHorizontal", -0.5, 2),
    ]

    for description, address, value, duration in movements:
        logger.info("  %s...", description)
        tester.send(address, value)
        await asyncio.sleep(duration)
        tester.send(address, 0.0)  # Stop
        await asyncio.sleep(0.5)

    # Action tests
    logger.info("\n🎮 Testing actions:")

    actions = [
        ("Jump", "/input/Jump", 1),
        ("Run", "/input/Run", 1),
    ]

    for description, address, value in actions:
        logger.info("  %s...", description)
        tester.send(address, value)
        await asyncio.sleep(0.5)
        if value == 1:
            tester.send(address, 0)  # Release

    logger.info("\n✅ Universal input test complete!")


async def test_vrcemote_system(tester: VRChatOSCTester):
    """Test VRCEmote integer-based emotion system."""
    logger.info("\n═══ Testing VRCEmote System (Integer-based) ═══")
    logger.info("(Used by many modern avatars)\n")

    # Avatar uses gesture wheel, not emotion states
    logger.info("🎭 Testing VRCEmote gesture wheel positions:")
    emote_values = [
        (0, "Neutral/Clear"),
        (1, "Back (top)"),
        (2, "Wave (upper right)"),
        (3, "Clap (right)"),
        (4, "Point (lower right)"),
        (5, "Cheer (lower slightly right)"),
        (6, "Dance (bottom)"),
        (7, "Backflip (lower left)"),
        (8, "Sadness (left)"),
        (9, "Die (upper left)"),
    ]

    for value, description in emote_values:
        logger.info("  VRCEmote = %s (%s)", value, description)
        tester.send("/avatar/parameters/VRCEmote", value)
        await asyncio.sleep(2)

    # Return to neutral
    logger.info("  Returning to neutral (VRCEmote = 0)")
    tester.send("/avatar/parameters/VRCEmote", 0)
    await asyncio.sleep(1)

    logger.info("\n✅ VRCEmote test complete!")


async def test_common_parameters(tester: VRChatOSCTester):
    """Test commonly used avatar parameters."""
    logger.info("\n═══ Testing Common Avatar Parameters ═══")
    logger.info("(These may or may not work depending on your avatar)\n")

    # Common emotion parameters
    logger.info("😊 Testing emotion parameters:")
    emotions = [
        "EmotionHappy",
        "EmotionSad",
        "EmotionAngry",
        "Mood",  # Alternative name some avatars use
        "Face",  # Another alternative
        "Expression",  # Yet another alternative
    ]

    for emotion in emotions:
        param = f"/avatar/parameters/{emotion}"
        logger.info("  Trying: %s", emotion)
        tester.send(param, 1.0)
        await asyncio.sleep(1)
        tester.send(param, 0.0)

    # Common gesture parameters
    logger.info("\n👋 Testing gesture parameters:")
    gestures = [
        ("GestureLeft", 1),  # Wave
        ("GestureRight", 1),
        ("HandGestureLeft", 1),  # Alternative name
        ("HandGestureRight", 1),
        ("Gesture", 1),  # Simple alternative
    ]

    for param_name, value in gestures:
        param = f"/avatar/parameters/{param_name}"
        logger.info("  Trying: %s", param_name)
        tester.send(param, value)
        await asyncio.sleep(1)
        tester.send(param, 0)

    # Common toggles
    logger.info("\n🔄 Testing common toggles:")
    toggles = [
        "Sitting",
        "AFK",
        "Crouching",
        "IsSitting",  # Alternative
        "IsAFK",  # Alternative
    ]

    for toggle in toggles:
        param = f"/avatar/parameters/{toggle}"
        logger.info("  Trying: %s", toggle)
        tester.send(param, True)
        await asyncio.sleep(1)
        tester.send(param, False)


async def discover_parameters(tester: VRChatOSCTester):
    """Try to discover what parameters the avatar supports."""
    logger.info("\n═══ Parameter Discovery Mode ═══")
    logger.info("Move around and use your avatar's expression menu in VRChat.")
    logger.info("I'll show what parameters your avatar sends.\n")
    logger.info("Listening for 30 seconds...\n")

    # Clear received params
    tester.received_params.clear()

    # Listen for 30 seconds
    await asyncio.sleep(30)

    if tester.received_params:
        logger.info("\n📋 Discovered Parameters:")
        for param, value in tester.received_params.items():
            logger.info("  %s: %s (%s)", param, value, type(value).__name__)

        # Save to file
        output_file = "discovered_avatar_params.txt"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write("Discovered Avatar Parameters\n")
            f.write("=" * 40 + "\n\n")
            for param, value in tester.received_params.items():
                f.write(f"{param}: {value} ({type(value).__name__})\n")

        logger.info("\n💾 Saved to %s", output_file)
        logger.info("You can use these parameter names to customize the VRChat backend!")
    else:
        logger.info("\n❌ No parameters received.")
        logger.info("This could mean:")
        logger.info("  1. Your avatar doesn't send OSC parameters")
        logger.info("  2. OSC isn't enabled in VRChat")
        logger.info("  3. Network/firewall is blocking UDP port 9001")


async def interactive_mode(tester: VRChatOSCTester):
    """Simple interactive control mode."""
    logger.info("\n═══ Interactive Control Mode ═══")
    logger.info("Use WASD for movement, Q/E for turning")
    logger.info("Press Ctrl+C to exit\n")

    try:
        import aioconsole

        while True:
            key = await aioconsole.ainput("Command (w/a/s/d/q/e/space/r): ")
            key = key.lower().strip()

            if key == "w":
                tester.send("/input/Vertical", 1.0)
                await asyncio.sleep(0.5)
                tester.send("/input/Vertical", 0.0)
            elif key == "s":
                tester.send("/input/Vertical", -1.0)
                await asyncio.sleep(0.5)
                tester.send("/input/Vertical", 0.0)
            elif key == "a":
                tester.send("/input/Horizontal", -1.0)
                await asyncio.sleep(0.5)
                tester.send("/input/Horizontal", 0.0)
            elif key == "d":
                tester.send("/input/Horizontal", 1.0)
                await asyncio.sleep(0.5)
                tester.send("/input/Horizontal", 0.0)
            elif key == "q":
                tester.send("/input/LookHorizontal", -0.5)
                await asyncio.sleep(0.5)
                tester.send("/input/LookHorizontal", 0.0)
            elif key == "e":
                tester.send("/input/LookHorizontal", 0.5)
                await asyncio.sleep(0.5)
                tester.send("/input/LookHorizontal", 0.0)
            elif key == "space":
                tester.send("/input/Jump", 1)
                await asyncio.sleep(0.1)
                tester.send("/input/Jump", 0)
            elif key == "r":
                tester.send("/input/Run", 1)
                await asyncio.sleep(2)
                tester.send("/input/Run", 0)

    except ImportError:
        logger.warning("Install aioconsole for better interactive mode: pip install aioconsole")
        logger.info("Falling back to basic mode...")

        logger.info("The avatar will walk in a square pattern.")
        logger.info("Press Ctrl+C to stop.\n")

        while True:
            # Walk forward
            tester.send("/input/Vertical", 0.5)
            await asyncio.sleep(2)
            tester.send("/input/Vertical", 0)

            # Turn right
            tester.send("/input/LookHorizontal", 0.5)
            await asyncio.sleep(1)
            tester.send("/input/LookHorizontal", 0)


async def main():
    """Main test function."""
    parser = argparse.ArgumentParser(description="Test VRChat OSC - works with ANY avatar!")
    parser.add_argument("--host", default=os.getenv("VRCHAT_HOST", "192.168.0.152"), help="VRChat host IP address")
    parser.add_argument(
        "--mode",
        choices=["universal", "common", "vrcemote", "discover", "interactive", "all"],
        default="universal",
        help="Test mode",
    )

    args = parser.parse_args()

    logger.info("🎮 VRChat OSC Basic Tester")
    logger.info("=" * 40)

    tester = VRChatOSCTester(args.host)

    try:
        await tester.connect()

        if args.mode in ("universal", "all"):
            await test_universal_inputs(tester)

        if args.mode in ("common", "all"):
            await test_common_parameters(tester)

        if args.mode == "vrcemote":
            await test_vrcemote_system(tester)

        if args.mode in ("discover", "all"):
            await discover_parameters(tester)

        if args.mode == "interactive":
            await interactive_mode(tester)

    except KeyboardInterrupt:
        logger.info("\n\n⚠️ Test interrupted")

    finally:
        if tester.server:
            try:
                # AsyncIOOSCUDPServer doesn't have shutdown method
                # The transport is automatically cleaned up when the event loop ends
                pass
            except Exception:
                pass
        logger.info("✅ Test complete!")


if __name__ == "__main__":
    asyncio.run(main())
