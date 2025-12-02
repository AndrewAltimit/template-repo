#!/usr/bin/env python3
"""
Test VRCEmote system with discovered avatar values.

This script specifically tests the VRCEmote integer-based emotion system
using the values discovered from your avatar: 2, 3, 4, 8.
"""

import argparse
import asyncio
import logging
import os
from pathlib import Path
import sys
from typing import Dict, List, Tuple, Union

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))
# pylint: disable=wrong-import-position  # Imports must come after sys.path modification

from tools.mcp.virtual_character.backends.vrchat_remote import VRChatRemoteBackend  # noqa: E402
from tools.mcp.virtual_character.models.canonical import (  # noqa: E402
    CanonicalAnimationData,
    EmotionType,
)

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


async def test_vrcemote_emotions(backend: VRChatRemoteBackend):
    """Test VRCEmote values with canonical emotions."""
    logger.info("\n═══ Testing VRCEmote Gesture Wheel Mapping ═══")
    logger.info("Avatar uses gesture wheel: Back, Wave, Clap, Point, Cheer, Dance, Backflip, Sadness, Die")
    logger.info("")

    # Test emotion to gesture wheel mappings
    emotions = [
        (EmotionType.NEUTRAL, 0, "😐 Neutral (No gesture)"),
        (EmotionType.HAPPY, 5, "😊 Happy → Cheer"),
        (EmotionType.SAD, 8, "😢 Sad → Sadness gesture"),
        (EmotionType.ANGRY, 4, "😠 Angry → Point"),
        (EmotionType.SURPRISED, 7, "😲 Surprised → Backflip"),
        (EmotionType.FEARFUL, 9, "😱 Fearful → Die"),
        (EmotionType.DISGUSTED, 1, "🤢 Disgusted → Back"),
    ]

    for emotion_type, expected_value, label in emotions:
        logger.info("Testing: %s (VRCEmote=%s)", label, expected_value)

        animation = CanonicalAnimationData(timestamp=asyncio.get_event_loop().time())
        animation.emotion = emotion_type
        animation.emotion_intensity = 1.0

        success = await backend.send_animation_data(animation)

        if success:
            logger.info("  ✓ Sent %s successfully", emotion_type.value)
        else:
            logger.error("  ✗ Failed to send %s", emotion_type.value)

        await asyncio.sleep(3)  # Hold emotion for 3 seconds

    # Return to neutral
    logger.info("\nReturning to neutral...")
    animation = CanonicalAnimationData(timestamp=asyncio.get_event_loop().time())
    animation.emotion = EmotionType.NEUTRAL
    await backend.send_animation_data(animation)

    logger.info("✅ VRCEmote emotion test complete!")


async def test_emotion_transitions(backend: VRChatRemoteBackend):
    """Test smooth transitions between emotions."""
    logger.info("\n═══ Testing Emotion Transitions ═══")

    transitions = [
        (EmotionType.NEUTRAL, EmotionType.HAPPY, "Neutral → Happy"),
        (EmotionType.HAPPY, EmotionType.SURPRISED, "Happy → Surprised"),
        (EmotionType.SURPRISED, EmotionType.SAD, "Surprised → Sad"),
        (EmotionType.SAD, EmotionType.ANGRY, "Sad → Angry"),
        (EmotionType.ANGRY, EmotionType.NEUTRAL, "Angry → Neutral"),
    ]

    for from_emotion, to_emotion, description in transitions:
        logger.info("Testing transition: %s", description)

        # Set initial emotion
        animation = CanonicalAnimationData(timestamp=asyncio.get_event_loop().time())
        animation.emotion = from_emotion
        await backend.send_animation_data(animation)
        await asyncio.sleep(1.5)

        # Transition to new emotion
        animation.emotion = to_emotion
        await backend.send_animation_data(animation)
        await asyncio.sleep(1.5)

    logger.info("✅ Emotion transitions complete!")


async def test_emotion_with_movement(backend: VRChatRemoteBackend):
    """Test emotions combined with movement."""
    logger.info("\n═══ Testing Emotions with Movement ═══")

    combinations: List[Tuple[EmotionType, Dict[str, Union[float, bool]], str]] = [
        (EmotionType.HAPPY, {"move_forward": 0.5}, "Happy while walking forward"),
        (EmotionType.ANGRY, {"look_horizontal": 0.3}, "Angry while turning"),
        (EmotionType.SAD, {"move_forward": -0.3}, "Sad while backing up"),
        (EmotionType.SURPRISED, {"jump": True}, "Surprised with jump"),
    ]

    for emotion, movement, description in combinations:
        logger.info("Testing: %s", description)

        animation = CanonicalAnimationData(timestamp=asyncio.get_event_loop().time())
        animation.emotion = emotion
        animation.parameters = movement

        await backend.send_animation_data(animation)
        await asyncio.sleep(2)

        # Stop movement but keep emotion
        animation.parameters = {"move_forward": 0, "look_horizontal": 0}
        await backend.send_animation_data(animation)
        await asyncio.sleep(1)

    # Return to neutral
    animation.emotion = EmotionType.NEUTRAL
    await backend.send_animation_data(animation)

    logger.info("✅ Emotion + movement test complete!")


async def test_rapid_emotion_changes(backend: VRChatRemoteBackend):
    """Test rapid emotion changes to verify system responsiveness."""
    logger.info("\n═══ Testing Rapid Emotion Changes ═══")
    logger.info("Testing avatar's response to quick emotion switches...")

    emotions = [EmotionType.HAPPY, EmotionType.SAD, EmotionType.ANGRY, EmotionType.SURPRISED]

    for _ in range(3):  # 3 cycles
        for emotion in emotions:
            animation = CanonicalAnimationData(timestamp=asyncio.get_event_loop().time())
            animation.emotion = emotion
            await backend.send_animation_data(animation)
            await asyncio.sleep(0.5)  # Quick changes

    # Return to neutral
    animation = CanonicalAnimationData(timestamp=asyncio.get_event_loop().time())
    animation.emotion = EmotionType.NEUTRAL
    await backend.send_animation_data(animation)

    logger.info("✅ Rapid emotion change test complete!")


async def demo_emotion_story(backend: VRChatRemoteBackend):
    """Demo a short emotional story using VRCEmote."""
    logger.info("\n═══ Emotion Story Demo ═══")
    logger.info("Watch the avatar express a short story through emotions...")

    story = [
        (EmotionType.NEUTRAL, 2, "Starting our story..."),
        (EmotionType.HAPPY, 3, "Something wonderful happens! 🎉"),
        (EmotionType.SURPRISED, 2, "But wait, what's this?!"),
        (EmotionType.SAD, 3, "Oh no, something went wrong... 😔"),
        (EmotionType.ANGRY, 2, "This is frustrating! 😤"),
        (EmotionType.HAPPY, 3, "But everything works out in the end! 😊"),
        (EmotionType.NEUTRAL, 2, "The end."),
    ]

    for emotion, duration, narration in story:
        logger.info("  %s", narration)

        animation = CanonicalAnimationData(timestamp=asyncio.get_event_loop().time())
        animation.emotion = emotion
        animation.emotion_intensity = 1.0

        await backend.send_animation_data(animation)
        await asyncio.sleep(duration)

    logger.info("✅ Story complete!")


async def main():
    """Main test function."""
    parser = argparse.ArgumentParser(description="Test VRCEmote integer-based emotion system")
    parser.add_argument(
        "--host",
        default=os.getenv("VRCHAT_HOST", "127.0.0.1"),
        help="VRChat host IP address",
    )
    parser.add_argument(
        "--test",
        choices=["all", "basic", "transitions", "movement", "rapid", "story"],
        default="all",
        help="Which test to run",
    )

    args = parser.parse_args()

    logger.info("🎮 VRCEmote System Test")
    logger.info("=" * 40)
    logger.info("This test uses the VRCEmote integer-based emotion system")
    logger.info("Discovered values: 2=Happy, 3=Sad, 4=Angry, 8=Surprised")
    logger.info("")

    # Create backend with VRCEmote enabled
    backend = VRChatRemoteBackend()

    config = {
        "remote_host": args.host,
        "use_vrcemote": True,  # Force VRCEmote system
        "osc_in_port": 9000,
        "osc_out_port": 9001,
    }

    try:
        logger.info("🔌 Connecting to VRChat at %s...", args.host)
        success = await backend.connect(config)

        if not success:
            logger.error("❌ Failed to connect to VRChat!")
            logger.error("Make sure:")
            logger.error("  1. VRChat is running")
            logger.error("  2. OSC is enabled in VRChat settings")
            logger.error("  3. The IP address is correct")
            return

        logger.info("✅ Connected successfully!")
        logger.info("📊 Using VRCEmote emotion system")
        logger.info("")

        # Run selected tests
        if args.test == "all":
            await test_vrcemote_emotions(backend)
            await asyncio.sleep(2)
            await test_emotion_transitions(backend)
            await asyncio.sleep(2)
            await test_emotion_with_movement(backend)
            await asyncio.sleep(2)
            await test_rapid_emotion_changes(backend)
            await asyncio.sleep(2)
            await demo_emotion_story(backend)
        elif args.test == "basic":
            await test_vrcemote_emotions(backend)
        elif args.test == "transitions":
            await test_emotion_transitions(backend)
        elif args.test == "movement":
            await test_emotion_with_movement(backend)
        elif args.test == "rapid":
            await test_rapid_emotion_changes(backend)
        elif args.test == "story":
            await demo_emotion_story(backend)

        # Get final statistics
        stats = await backend.get_statistics()
        logger.info("\n📊 Session Statistics:")
        logger.info("  OSC messages sent: %s", stats.get("osc_messages_sent", 0))
        logger.info("  Animation frames: %s", stats.get("animation_frames", 0))

    except KeyboardInterrupt:
        logger.info("\n⚠️ Test interrupted by user")

    except Exception as e:
        logger.error("❌ Error during test: %s", e)
        import traceback

        traceback.print_exc()

    finally:
        await backend.disconnect()
        logger.info("\n✅ VRCEmote test complete!")


if __name__ == "__main__":
    asyncio.run(main())
