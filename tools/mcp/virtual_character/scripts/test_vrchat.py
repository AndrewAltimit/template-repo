#!/usr/bin/env python3
"""
Test script for VRChat remote backend.

This script tests the VRChat OSC integration and avatar movement.
"""

import argparse
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

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


async def test_connection(host: str = "127.0.0.1", use_bridge: bool = False, use_vrcemote: bool = False):
    """Test basic connection to VRChat."""
    logger.info("Testing VRChat connection...")

    if use_vrcemote:
        logger.info("Using VRCEmote integer-based emotion system")

    backend = VRChatRemoteBackend()

    config = {
        "remote_host": host,
        "use_bridge": use_bridge,
        "osc_in_port": 9000,
        "osc_out_port": 9001,
    }

    if use_vrcemote:
        config["use_vrcemote"] = True

    success = await backend.connect(config)

    if success:
        logger.info("✓ Successfully connected to VRChat")

        # Get statistics
        stats = await backend.get_statistics()
        logger.info(f"Backend statistics: {stats}")

        # Perform health check
        health = await backend.health_check()
        logger.info(f"Health check: {health}")

        return backend
    else:
        logger.error("✗ Failed to connect to VRChat")
        return None


async def test_emotions(backend: VRChatRemoteBackend):
    """Test emotion changes."""
    logger.info("Testing emotion changes...")

    emotions = [
        EmotionType.NEUTRAL,
        EmotionType.HAPPY,
        EmotionType.SAD,
        EmotionType.ANGRY,
        EmotionType.SURPRISED,
        EmotionType.FEARFUL,
    ]

    for emotion in emotions:
        logger.info(f"Setting emotion: {emotion.value}")

        animation = CanonicalAnimationData(timestamp=asyncio.get_event_loop().time())
        animation.emotion = emotion
        animation.emotion_intensity = 1.0

        success = await backend.send_animation_data(animation)

        if success:
            logger.info(f"✓ Emotion {emotion.value} set successfully")
        else:
            logger.error(f"✗ Failed to set emotion {emotion.value}")

        await asyncio.sleep(2)  # Wait 2 seconds between emotions

    # Return to neutral
    animation = CanonicalAnimationData(timestamp=asyncio.get_event_loop().time())
    animation.emotion = EmotionType.NEUTRAL
    await backend.send_animation_data(animation)
    logger.info("Returned to neutral emotion")


async def test_gestures(backend: VRChatRemoteBackend):
    """Test gesture animations."""
    logger.info("Testing gestures...")

    gestures = [
        GestureType.WAVE,
        GestureType.POINT,
        GestureType.THUMBS_UP,
        GestureType.NOD,
        GestureType.SHAKE_HEAD,
    ]

    for gesture in gestures:
        logger.info(f"Performing gesture: {gesture.value}")

        animation = CanonicalAnimationData(timestamp=asyncio.get_event_loop().time())
        animation.gesture = gesture
        animation.gesture_intensity = 1.0

        success = await backend.send_animation_data(animation)

        if success:
            logger.info(f"✓ Gesture {gesture.value} performed successfully")
        else:
            logger.error(f"✗ Failed to perform gesture {gesture.value}")

        await asyncio.sleep(3)  # Wait 3 seconds between gestures

    # Clear gesture
    animation = CanonicalAnimationData(timestamp=asyncio.get_event_loop().time())
    animation.gesture = GestureType.NONE
    await backend.send_animation_data(animation)
    logger.info("Cleared gestures")


async def test_movement(backend: VRChatRemoteBackend):
    """Test avatar movement controls."""
    logger.info("Testing avatar movement...")

    # Test forward movement
    logger.info("Moving forward...")
    animation = CanonicalAnimationData(timestamp=asyncio.get_event_loop().time())
    animation.parameters = {
        "move_forward": 1.0,  # Full forward
        "move_speed": 0.5,  # Normal speed
    }
    await backend.send_animation_data(animation)
    await asyncio.sleep(2)

    # Stop
    animation.parameters = {"move_forward": 0.0}
    await backend.send_animation_data(animation)
    logger.info("Stopped forward movement")
    await asyncio.sleep(1)

    # Test turning
    logger.info("Turning right...")
    animation.parameters = {
        "look_horizontal": 0.5,  # Turn right
    }
    await backend.send_animation_data(animation)
    await asyncio.sleep(2)

    # Stop turning
    animation.parameters = {"look_horizontal": 0.0}
    await backend.send_animation_data(animation)
    logger.info("Stopped turning")
    await asyncio.sleep(1)

    # Test strafing
    logger.info("Strafing right...")
    animation.parameters = {
        "move_right": 1.0,  # Strafe right
    }
    await backend.send_animation_data(animation)
    await asyncio.sleep(2)

    # Stop strafing
    animation.parameters = {"move_right": 0.0}
    await backend.send_animation_data(animation)
    logger.info("Stopped strafing")
    await asyncio.sleep(1)

    # Test jumping
    logger.info("Jumping...")
    animation.parameters = {"jump": True}
    await backend.send_animation_data(animation)
    await asyncio.sleep(1)

    # Test crouching
    logger.info("Crouching...")
    animation.parameters = {"crouch": True}
    await backend.send_animation_data(animation)
    await asyncio.sleep(2)

    # Stand up
    animation.parameters = {"crouch": False}
    await backend.send_animation_data(animation)
    logger.info("Standing up")


async def test_behaviors(backend: VRChatRemoteBackend):
    """Test high-level behaviors."""
    logger.info("Testing high-level behaviors...")

    behaviors: list = [
        ("greet", {}),
        ("sit", {}),
        ("stand", {}),
        ("dance", {}),
    ]

    for behavior, params in behaviors:
        logger.info(f"Executing behavior: {behavior}")

        success = await backend.execute_behavior(behavior, params)

        if success:
            logger.info(f"✓ Behavior {behavior} executed successfully")
        else:
            logger.error(f"✗ Failed to execute behavior {behavior}")

        await asyncio.sleep(3)


async def test_combined_animation(backend: VRChatRemoteBackend):
    """Test combined emotion and gesture."""
    logger.info("Testing combined animations...")

    # Happy wave
    logger.info("Happy wave...")
    animation = CanonicalAnimationData(timestamp=asyncio.get_event_loop().time())
    animation.emotion = EmotionType.HAPPY
    animation.gesture = GestureType.WAVE
    animation.emotion_intensity = 1.0
    animation.gesture_intensity = 1.0
    await backend.send_animation_data(animation)
    await asyncio.sleep(3)

    # Sad with head shake
    logger.info("Sad with head shake...")
    animation.emotion = EmotionType.SAD
    animation.gesture = GestureType.SHAKE_HEAD
    await backend.send_animation_data(animation)
    await asyncio.sleep(3)

    # Return to neutral
    animation.emotion = EmotionType.NEUTRAL
    animation.gesture = GestureType.NONE
    await backend.send_animation_data(animation)
    logger.info("Returned to neutral state")


async def test_circle_walk(backend: VRChatRemoteBackend):
    """Test walking in a circle pattern."""
    logger.info("Testing circle walk pattern...")

    steps = 8
    duration_per_step = 2.0

    for i in range(steps):
        # Calculate movement direction for circle
        forward = 0.5  # Constant forward speed
        turn = 0.3  # Constant turning

        logger.info(f"Circle step {i+1}/{steps}")

        animation = CanonicalAnimationData(timestamp=asyncio.get_event_loop().time())
        animation.parameters = {
            "move_forward": forward,
            "look_horizontal": turn,
        }

        await backend.send_animation_data(animation)
        await asyncio.sleep(duration_per_step)

    # Stop movement
    animation = CanonicalAnimationData(timestamp=asyncio.get_event_loop().time())
    animation.parameters = {
        "move_forward": 0.0,
        "look_horizontal": 0.0,
    }
    await backend.send_animation_data(animation)
    logger.info("Circle walk complete")


async def interactive_control(backend: VRChatRemoteBackend):
    """Interactive control mode."""
    logger.info("Entering interactive control mode...")
    logger.info("Commands:")
    logger.info("  w/s - forward/backward")
    logger.info("  a/d - left/right strafe")
    logger.info("  q/e - turn left/right")
    logger.info("  space - jump")
    logger.info("  c - crouch")
    logger.info("  1-6 - emotions (neutral, happy, sad, angry, surprised, fearful)")
    logger.info("  g - wave gesture")
    logger.info("  x - exit")

    try:
        import termios
        import tty

        # Save terminal settings
        old_settings = termios.tcgetattr(sys.stdin)

        try:
            # Set terminal to raw mode
            tty.setraw(sys.stdin.fileno())

            running = True
            while running:
                # Read single character
                char = sys.stdin.read(1).lower()

                animation = CanonicalAnimationData(timestamp=asyncio.get_event_loop().time())

                if char == "w":
                    animation.parameters = {"move_forward": 1.0}
                elif char == "s":
                    animation.parameters = {"move_forward": -1.0}
                elif char == "a":
                    animation.parameters = {"move_right": -1.0}
                elif char == "d":
                    animation.parameters = {"move_right": 1.0}
                elif char == "q":
                    animation.parameters = {"look_horizontal": -0.5}
                elif char == "e":
                    animation.parameters = {"look_horizontal": 0.5}
                elif char == " ":
                    animation.parameters = {"jump": True}
                elif char == "c":
                    animation.parameters = {"crouch": True}
                elif char in "123456":
                    emotions = [
                        EmotionType.NEUTRAL,
                        EmotionType.HAPPY,
                        EmotionType.SAD,
                        EmotionType.ANGRY,
                        EmotionType.SURPRISED,
                        EmotionType.FEARFUL,
                    ]
                    animation.emotion = emotions[int(char) - 1]
                elif char == "g":
                    animation.gesture = GestureType.WAVE
                elif char == "x":
                    running = False
                    break

                # Send animation
                await backend.send_animation_data(animation)

                # Brief pause for key release detection
                await asyncio.sleep(0.1)

                # Stop movement on key release (simplified)
                if char in "wsadqe":
                    animation.parameters = {
                        "move_forward": 0.0,
                        "move_right": 0.0,
                        "look_horizontal": 0.0,
                    }
                    await backend.send_animation_data(animation)

        finally:
            # Restore terminal settings
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)

    except ImportError:
        logger.warning("Interactive mode not available (termios not found)")
        logger.info("Skipping interactive control")


async def main():
    """Main test function."""
    parser = argparse.ArgumentParser(description="Test VRChat remote backend")
    parser.add_argument("--host", default=os.getenv("VRCHAT_HOST", "192.168.0.152"), help="VRChat host IP address")
    parser.add_argument(
        "--test",
        choices=["all", "connection", "emotions", "gestures", "movement", "behaviors", "combined", "circle", "interactive"],
        default="all",
        help="Which test to run",
    )
    parser.add_argument("--use-bridge", action="store_true", help="Use bridge server for advanced features")
    parser.add_argument("--use-vrcemote", action="store_true", help="Use VRCEmote integer-based emotion system")

    args = parser.parse_args()

    # Connect to VRChat
    backend = await test_connection(args.host, args.use_bridge, args.use_vrcemote)

    if not backend:
        logger.error("Could not establish connection. Exiting.")
        return

    try:
        # Run selected tests
        if args.test == "all":
            await test_emotions(backend)
            await asyncio.sleep(2)
            await test_gestures(backend)
            await asyncio.sleep(2)
            await test_movement(backend)
            await asyncio.sleep(2)
            await test_behaviors(backend)
            await asyncio.sleep(2)
            await test_combined_animation(backend)
            await asyncio.sleep(2)
            await test_circle_walk(backend)
        elif args.test == "connection":
            logger.info("Connection test complete")
        elif args.test == "emotions":
            await test_emotions(backend)
        elif args.test == "gestures":
            await test_gestures(backend)
        elif args.test == "movement":
            await test_movement(backend)
        elif args.test == "behaviors":
            await test_behaviors(backend)
        elif args.test == "combined":
            await test_combined_animation(backend)
        elif args.test == "circle":
            await test_circle_walk(backend)
        elif args.test == "interactive":
            await interactive_control(backend)

        # Final statistics
        stats = await backend.get_statistics()
        logger.info(f"Final statistics: {stats}")

    finally:
        # Disconnect
        await backend.disconnect()
        logger.info("Test complete")


if __name__ == "__main__":
    asyncio.run(main())
