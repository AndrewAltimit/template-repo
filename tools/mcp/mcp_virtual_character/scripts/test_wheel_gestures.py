#!/usr/bin/env python3
"""
Test VRChat avatar gesture wheel directly.

This script tests each gesture position on your avatar's wheel.
"""

import argparse
import asyncio
import logging
import os
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))


try:
    from pythonosc import udp_client

    HAS_OSC = True
except ImportError:
    print("ERROR: python-osc not installed!")
    print("Install with: pip install python-osc")
    sys.exit(1)

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class WheelTester:
    """Test VRChat avatar gesture wheel positions."""

    def __init__(self, host: str = "127.0.0.1"):
        self.host = host
        self.client = None

    async def connect(self):
        """Connect to VRChat OSC."""
        self.client = udp_client.SimpleUDPClient(self.host, 9000)
        logger.info("Connected to VRChat at %s:9000", self.host)

    def send_vrcemote(self, value: int):
        """Send VRCEmote value."""
        if self.client:
            self.client.send_message("/avatar/parameters/VRCEmote", value)
            logger.info("Sent VRCEmote = %s", value)


async def test_all_wheel_positions(tester: WheelTester):
    """Test all gesture wheel positions in order."""
    logger.info("\n═══ Testing All Gesture Wheel Positions ═══")
    logger.info("Your avatar wheel (clockwise from top):\n")

    # Define wheel positions based on your description
    wheel_positions = [
        (0, "Return to neutral/clear gesture"),
        (1, "Back (top position, turning away)"),
        (2, "Wave (upper right)"),
        (3, "Clap (right side)"),
        (4, "Point (lower right)"),
        (5, "Cheer (lower slightly right)"),
        (6, "Dance (bottom)"),
        (7, "Backflip (lower left)"),
        (8, "Sadness (left side)"),
        (9, "Die (upper left)"),
    ]

    for value, description in wheel_positions:
        logger.info("\nTesting position %s: %s", value, description)
        tester.send_vrcemote(value)
        await asyncio.sleep(3)  # Hold for 3 seconds to see the gesture

    # Return to neutral
    logger.info("\nReturning to neutral...")
    tester.send_vrcemote(0)
    logger.info("✅ Wheel position test complete!")


async def test_specific_gestures(tester: WheelTester):
    """Test specific gestures one by one."""
    logger.info("\n═══ Testing Specific Gestures ═══")

    gestures = [
        (2, "Wave - Should trigger wave animation"),
        (3, "Clap - Should trigger clapping"),
        (4, "Point - Should trigger pointing gesture"),
        (5, "Cheer - Should trigger cheering"),
        (6, "Dance - Should trigger dance animation"),
        (7, "Backflip - Should trigger backflip"),
        (8, "Sadness - Should trigger sad gesture"),
    ]

    for value, description in gestures:
        logger.info("\n%s", description)
        tester.send_vrcemote(value)
        await asyncio.sleep(4)  # Hold longer to see full animation

    tester.send_vrcemote(0)
    logger.info("\n✅ Specific gesture test complete!")


async def interactive_wheel_test(tester: WheelTester):
    """Interactive mode to test specific wheel positions."""
    logger.info("\n═══ Interactive Wheel Test Mode ═══")
    logger.info("Enter a number 0-9 to test that wheel position")
    logger.info("Enter 'q' to quit\n")

    logger.info("Wheel mapping:")
    logger.info("0 = Neutral/Clear")
    logger.info("1 = Back")
    logger.info("2 = Wave")
    logger.info("3 = Clap")
    logger.info("4 = Point")
    logger.info("5 = Cheer")
    logger.info("6 = Dance")
    logger.info("7 = Backflip")
    logger.info("8 = Sadness")
    logger.info("9 = Die")
    logger.info("")

    try:
        import aioconsole

        while True:
            command = await aioconsole.ainput("Enter position (0-9) or 'q' to quit: ")
            command = command.strip().lower()

            if command == "q":
                break

            try:
                position = int(command)
                if 0 <= position <= 9:
                    logger.info("Sending VRCEmote = %s", position)
                    tester.send_vrcemote(position)
                else:
                    logger.warning("Please enter a number between 0 and 9")
            except ValueError:
                logger.warning("Invalid input. Please enter a number or 'q'")

    except ImportError:
        logger.warning("aioconsole not installed. Install with: pip install aioconsole")
        logger.info("Falling back to automatic sequence...")
        await test_all_wheel_positions(tester)


async def test_discovered_values(tester: WheelTester):
    """Test only the values discovered during parameter discovery (2, 3, 4, 8)."""
    logger.info("\n═══ Testing Discovered Values ═══")
    logger.info("Testing values found during discovery: 2, 3, 4, 8\n")

    discovered = [
        (2, "Value 2 - Should be Wave"),
        (3, "Value 3 - Should be Clap"),
        (4, "Value 4 - Should be Point"),
        (8, "Value 8 - Should be Sadness"),
    ]

    for value, expected in discovered:
        logger.info("Testing %s", expected)
        tester.send_vrcemote(value)
        await asyncio.sleep(3)

    tester.send_vrcemote(0)
    logger.info("\n✅ Discovered values test complete!")


async def main():
    """Main test function."""
    parser = argparse.ArgumentParser(description="Test VRChat avatar gesture wheel positions")
    parser.add_argument(
        "--host",
        default=os.getenv("VRCHAT_HOST", "127.0.0.1"),
        help="VRChat host IP address",
    )
    parser.add_argument(
        "--mode",
        choices=["all", "specific", "discovered", "interactive"],
        default="all",
        help="Test mode",
    )

    args = parser.parse_args()

    logger.info("🎮 VRChat Gesture Wheel Tester")
    logger.info("=" * 40)

    tester = WheelTester(args.host)

    try:
        await tester.connect()

        if args.mode == "all":
            await test_all_wheel_positions(tester)
        elif args.mode == "specific":
            await test_specific_gestures(tester)
        elif args.mode == "discovered":
            await test_discovered_values(tester)
        elif args.mode == "interactive":
            await interactive_wheel_test(tester)

    except KeyboardInterrupt:
        logger.info("\n\n⚠️ Test interrupted")
        tester.send_vrcemote(0)  # Return to neutral

    logger.info("\n✅ Test complete!")


if __name__ == "__main__":
    asyncio.run(main())
