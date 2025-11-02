#!/usr/bin/env python3
"""
VRChat Avatar Control Demonstration.

A simple demo showing how to control a VRChat avatar through the MCP server.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from tools.mcp.virtual_character.backends.vrchat_remote import VRChatRemoteBackend  # noqa: E402
from tools.mcp.virtual_character.models.canonical import (  # noqa: E402
    CanonicalAnimationData,
    EmotionType,
    GestureType,
)


# Configure logging with colors for better visibility
class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors."""

    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def format(self, record):
        log_color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{log_color}{record.levelname}{self.RESET}"
        return super().format(record)


# Set up colored logging
handler = logging.StreamHandler()
handler.setFormatter(ColoredFormatter("%(asctime)s - %(levelname)s - %(message)s"))
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.handlers = [handler]


async def demo_greeting(backend: VRChatRemoteBackend):
    """Demonstrate a friendly greeting."""
    logger.info("🤖 Performing greeting sequence...")

    # Set happy emotion and wave
    animation = CanonicalAnimationData(timestamp=asyncio.get_event_loop().time())
    animation.emotion = EmotionType.HAPPY
    animation.gesture = GestureType.WAVE
    animation.emotion_intensity = 1.0
    animation.gesture_intensity = 1.0

    await backend.send_animation_data(animation)
    await asyncio.sleep(3)

    # Nod
    animation.gesture = GestureType.NOD
    await backend.send_animation_data(animation)
    await asyncio.sleep(2)

    # Return to neutral
    animation.emotion = EmotionType.NEUTRAL
    animation.gesture = GestureType.NONE
    await backend.send_animation_data(animation)

    logger.info("✅ Greeting complete!")


async def demo_emotions(backend: VRChatRemoteBackend):
    """Demonstrate emotional expressions."""
    logger.info("😊 Demonstrating emotions...")

    emotions = [
        (EmotionType.HAPPY, "😊 Happy"),
        (EmotionType.SAD, "😢 Sad"),
        (EmotionType.SURPRISED, "😲 Surprised"),
        (EmotionType.ANGRY, "😠 Angry"),
        (EmotionType.NEUTRAL, "😐 Neutral"),
    ]

    animation = CanonicalAnimationData(timestamp=asyncio.get_event_loop().time())

    for emotion, label in emotions:
        logger.info("  Showing: %s", label)
        animation.emotion = emotion
        animation.emotion_intensity = 1.0
        await backend.send_animation_data(animation)
        await asyncio.sleep(2.5)

    logger.info("✅ Emotion demonstration complete!")


async def demo_movement(backend: VRChatRemoteBackend):
    """Demonstrate avatar movement."""
    logger.info("🚶 Demonstrating movement...")

    animation = CanonicalAnimationData(timestamp=asyncio.get_event_loop().time())

    # Walk forward
    logger.info("  Walking forward...")
    animation.parameters = {"move_forward": 0.7}
    await backend.send_animation_data(animation)
    await asyncio.sleep(3)

    # Stop and turn
    logger.info("  Turning...")
    animation.parameters = {"move_forward": 0, "look_horizontal": 0.5}
    await backend.send_animation_data(animation)
    await asyncio.sleep(2)

    # Walk in new direction
    logger.info("  Walking in new direction...")
    animation.parameters = {"move_forward": 0.7, "look_horizontal": 0}
    await backend.send_animation_data(animation)
    await asyncio.sleep(3)

    # Stop
    logger.info("  Stopping...")
    animation.parameters = {"move_forward": 0}
    await backend.send_animation_data(animation)

    logger.info("✅ Movement demonstration complete!")


async def demo_dance(backend: VRChatRemoteBackend):
    """Demonstrate a simple dance."""
    logger.info("💃 Performing dance...")

    # Happy emotion for dancing
    animation = CanonicalAnimationData(timestamp=asyncio.get_event_loop().time())
    animation.emotion = EmotionType.HAPPY
    await backend.send_animation_data(animation)

    # Dance gesture if available
    animation.gesture = GestureType.DANCE
    await backend.send_animation_data(animation)
    await asyncio.sleep(1)

    # Simple movement pattern
    moves = [
        {"move_right": 0.5, "look_horizontal": 0.3},
        {"move_right": -0.5, "look_horizontal": -0.3},
        {"move_forward": 0.3, "look_horizontal": 0},
        {"move_forward": -0.3, "look_horizontal": 0},
    ]

    for _ in range(2):  # Repeat pattern
        for move in moves:
            animation.parameters = move
            await backend.send_animation_data(animation)
            await asyncio.sleep(1)

    # Stop dancing
    animation.parameters = {"move_forward": 0, "move_right": 0, "look_horizontal": 0}
    animation.gesture = GestureType.NONE
    animation.emotion = EmotionType.NEUTRAL
    await backend.send_animation_data(animation)

    logger.info("✅ Dance complete!")


async def demo_story(backend: VRChatRemoteBackend):
    """Tell a short story with animations."""
    logger.info("📖 Telling a story with animations...")

    animation = CanonicalAnimationData(timestamp=asyncio.get_event_loop().time())

    # Introduction
    logger.info("  'Hello! Let me tell you a story...'")
    animation.emotion = EmotionType.HAPPY
    animation.gesture = GestureType.WAVE
    await backend.send_animation_data(animation)
    await asyncio.sleep(3)

    # Story begins
    logger.info("  'Once upon a time...'")
    animation.gesture = GestureType.NONE
    animation.parameters = {"move_forward": 0.3}
    await backend.send_animation_data(animation)
    await asyncio.sleep(2)
    animation.parameters = {"move_forward": 0}
    await backend.send_animation_data(animation)

    # Surprise
    logger.info("  'Something amazing happened!'")
    animation.emotion = EmotionType.SURPRISED
    animation.gesture = GestureType.POINT
    await backend.send_animation_data(animation)
    await asyncio.sleep(3)

    # Contemplation
    logger.info("  'But then I realized...'")
    animation.emotion = EmotionType.NEUTRAL
    animation.gesture = GestureType.SHAKE_HEAD
    await backend.send_animation_data(animation)
    await asyncio.sleep(2)

    # Happy ending
    logger.info("  'And everything worked out great!'")
    animation.emotion = EmotionType.HAPPY
    animation.gesture = GestureType.THUMBS_UP
    await backend.send_animation_data(animation)
    await asyncio.sleep(3)

    # Return to neutral
    animation.emotion = EmotionType.NEUTRAL
    animation.gesture = GestureType.NONE
    await backend.send_animation_data(animation)

    logger.info("✅ Story complete!")


async def main():
    """Run the VRChat avatar demonstration."""

    # ASCII art header
    print(
        """
╔══════════════════════════════════════════╗
║     VRChat Avatar Control Demo          ║
║     🤖 AI-Powered Avatar Animation 🎮    ║
╚══════════════════════════════════════════╝
    """
    )

    # Get VRChat host from environment or use default
    vrchat_host = os.getenv("VRCHAT_HOST", "192.168.0.152")

    # Check if we should use VRCEmote (can be set via environment)
    use_vrcemote = os.getenv("VRCHAT_USE_VRCEMOTE", "").lower() in ["true", "1", "yes"]

    logger.info("🔌 Connecting to VRChat at %s...", vrchat_host)
    if use_vrcemote:
        logger.info("📊 Using VRCEmote integer-based emotion system")

    # Create and connect backend
    backend = VRChatRemoteBackend()

    config = {
        "remote_host": vrchat_host,
        "use_bridge": False,
        "osc_in_port": 9000,
        "osc_out_port": 9001,
    }

    # Configure emotion system if specified
    if use_vrcemote:
        config["use_vrcemote"] = True

    try:
        success = await backend.connect(config)

        if not success:
            logger.error("❌ Failed to connect to VRChat!")
            logger.error("Make sure:")
            logger.error("  1. VRChat is running")
            logger.error("  2. OSC is enabled in VRChat settings")
            logger.error("  3. The IP address is correct")
            logger.error("  4. Firewall allows UDP ports 9000-9001")
            return

        logger.info("✅ Connected successfully!")
        logger.info("")

        # Run demonstrations
        demos = [
            ("Greeting", demo_greeting),
            ("Emotions", demo_emotions),
            ("Movement", demo_movement),
            ("Dance", demo_dance),
            ("Story", demo_story),
        ]

        for i, (name, demo_func) in enumerate(demos, 1):
            logger.info(f"\n═══ Demo {i}/{len(demos)}: {name} ═══")
            await demo_func(backend)

            if i < len(demos):
                logger.info("⏸️  Pausing before next demo...")
                await asyncio.sleep(3)

        # Final statistics
        logger.info("\n📊 Session Statistics:")
        stats = await backend.get_statistics()
        logger.info(f"  OSC messages sent: {stats.get('osc_messages_sent', 0)}")
        logger.info(f"  Animation frames: {stats.get('animation_frames', 0)}")
        logger.info(f"  Errors: {stats.get('errors', 0)}")

    except KeyboardInterrupt:
        logger.info("\n⚠️  Demo interrupted by user")

    except Exception as e:
        logger.error("❌ Error during demo: %s", e)
        import traceback

        traceback.print_exc()

    finally:
        # Disconnect
        logger.info("\n🔌 Disconnecting...")
        await backend.disconnect()
        logger.info("✅ Demo complete! Goodbye! 👋")


if __name__ == "__main__":
    # Run the demo
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Demo terminated by user. Goodbye!")
        sys.exit(0)
