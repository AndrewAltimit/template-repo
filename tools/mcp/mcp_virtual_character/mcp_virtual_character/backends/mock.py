"""
Mock backend adapter for testing.

This backend simulates a virtual character system without
requiring actual external connections.
"""

import asyncio
from io import BytesIO
import logging
import time
from typing import Any, Dict, List, Optional

import numpy as np
from PIL import Image

from mcp_virtual_character.models.canonical import (
    AudioData,
    CanonicalAnimationData,
    EmotionType,
    EnvironmentState,
    GestureType,
    Quaternion,
    Vector3,
    VideoFrame,
)

from .base import BackendAdapter

logger = logging.getLogger(__name__)


class MockBackend(BackendAdapter):
    """
    Mock backend implementation for testing.

    Simulates a virtual character system with:
    - Animation state tracking
    - Simulated video frames
    - Environment state
    - Event generation
    """

    def __init__(self) -> None:
        super().__init__()

        # Set capabilities
        self.capabilities.audio = True
        self.capabilities.animation = True
        self.capabilities.video_capture = True
        self.capabilities.bidirectional = True
        self.capabilities.environment_control = True
        self.capabilities.streaming = False
        self.capabilities.multi_agent = False

        # Internal state
        self.current_animation: Optional[CanonicalAnimationData] = None
        self.current_audio: Optional[AudioData] = None
        self.environment_state = EnvironmentState()
        self.frame_counter = 0
        self.animation_history: List[CanonicalAnimationData] = []
        self.audio_history: List[AudioData] = []

        # Simulation parameters
        self.simulate_events = False
        self.event_task: Optional[asyncio.Task] = None

    @property
    def backend_name(self) -> str:
        """Get backend name."""
        return "mock"

    async def connect(self, config: Dict[str, Any]) -> bool:
        """
        Connect to mock backend.

        Args:
            config: Configuration dictionary

        Returns:
            Always returns True for mock
        """
        self.config = config
        self.connected = True

        # Initialize environment state
        self.environment_state.world_name = config.get("world_name", "MockWorld")
        self.environment_state.instance_id = f"mock_{int(time.time())}"
        self.environment_state.agent_position = Vector3(0.0, 0.0, 0.0)
        self.environment_state.agent_rotation = Quaternion(1.0, 0.0, 0.0, 0.0)

        # Start event simulation if enabled
        if config.get("simulate_events", False):
            self.simulate_events = True
            self.event_task = asyncio.create_task(self._event_simulation_loop())

        # Emit connected event
        await self._emit_event("connected", {"backend": self.backend_name, "world": self.environment_state.world_name})

        return True

    async def disconnect(self) -> None:
        """Disconnect from mock backend."""
        if self.event_task:
            self.event_task.cancel()
            try:
                await self.event_task
            except asyncio.CancelledError:
                pass

        self.connected = False

        # Emit disconnected event
        await self._emit_event("disconnected", {"backend": self.backend_name})

    async def send_animation_data(self, data: CanonicalAnimationData) -> bool:
        """
        Send animation data to mock backend.

        Args:
            data: Animation data

        Returns:
            Always returns True for mock
        """
        if not self.connected:
            return False

        self.current_animation = data
        self.animation_history.append(data)

        # Simulate processing delay
        await asyncio.sleep(0.01)

        # Update agent position if locomotion data present
        if data.locomotion:
            self.environment_state.agent_position = Vector3(
                self.environment_state.agent_position.x + data.locomotion.velocity.x * 0.1,
                self.environment_state.agent_position.y + data.locomotion.velocity.y * 0.1,
                self.environment_state.agent_position.z + data.locomotion.velocity.z * 0.1,
            )

        # Emit animation event
        await self._emit_event(
            "animation_sent",
            {
                "timestamp": data.timestamp,
                "emotion": data.emotion.value if data.emotion else None,
                "gesture": data.gesture.value if data.gesture else None,
            },
        )

        return True

    async def send_audio_data(self, audio: AudioData) -> bool:
        """
        Send audio data to mock backend.

        Args:
            audio: Audio data

        Returns:
            Always returns True for mock
        """
        if not self.connected:
            return False

        self.current_audio = audio
        self.audio_history.append(audio)

        # Simulate processing delay
        await asyncio.sleep(0.01)

        # Emit audio event
        await self._emit_event("audio_sent", {"duration": audio.duration, "format": audio.format, "text": audio.text})

        return True

    async def receive_state(self) -> Optional[EnvironmentState]:
        """
        Receive current environment state.

        Returns:
            Current mock environment state
        """
        if not self.connected:
            return None

        # Simulate some dynamic changes
        import random

        # Add some mock nearby agents
        self.environment_state.nearby_agents = [
            {
                "id": f"agent_{i}",
                "name": f"MockAgent{i}",
                "position": [random.uniform(-10, 10), 0, random.uniform(-10, 10)],
                "emotion": random.choice(["happy", "neutral", "sad"]),
            }
            for i in range(random.randint(0, 3))
        ]

        # Add some mock objects
        self.environment_state.nearby_objects = [
            {
                "id": f"object_{i}",
                "type": random.choice(["chair", "table", "door", "lamp"]),
                "position": [random.uniform(-5, 5), 0, random.uniform(-5, 5)],
                "interactable": random.choice([True, False]),
            }
            for i in range(random.randint(1, 5))
        ]

        return self.environment_state

    async def reset_all(self) -> bool:
        """
        Reset all states to neutral/idle.

        Returns:
            True (always succeeds for mock)
        """
        # Clear animation state
        self.current_animation = None
        self.current_audio = None
        self.animation_history.clear()
        self.audio_history.clear()

        # Reset environment to default position
        self.environment_state.agent_position = Vector3(0.0, 0.0, 0.0)
        self.environment_state.agent_rotation = Quaternion(1.0, 0.0, 0.0, 0.0)

        # Emit reset event
        await self._emit_event("reset", {"backend": self.backend_name})

        return True

    async def capture_video_frame(self) -> Optional[VideoFrame]:
        """
        Capture a simulated video frame.

        Returns:
            Simulated video frame
        """
        if not self.connected:
            return None

        # Create a simple test image
        width, height = 640, 480

        # Create gradient image with some visual feedback
        img = Image.new("RGB", (width, height))
        pixels = img.load()

        # Add gradient based on frame counter
        assert pixels is not None, "Failed to load image pixels"
        for y in range(height):
            for x in range(width):
                # Create animated gradient
                r = int((x / width) * 255)
                g = int((y / height) * 255)
                b = int((self.frame_counter % 255))
                pixels[x, y] = (r, g, b)

        # Add visual indicators for current state
        if self.current_animation and self.current_animation.emotion:
            # Add emotion indicator (colored square)
            emotion_colors = {
                EmotionType.HAPPY: (255, 255, 0),
                EmotionType.SAD: (0, 0, 255),
                EmotionType.ANGRY: (255, 0, 0),
                EmotionType.NEUTRAL: (128, 128, 128),
            }

            color = emotion_colors.get(self.current_animation.emotion, (255, 255, 255))
            # pixels already asserted above as not None
            for y in range(10, 60):
                for x in range(10, 60):
                    pixels[x, y] = color

        # Convert to JPEG bytes
        buffer = BytesIO()
        img.save(buffer, format="JPEG", quality=85)
        frame_data = buffer.getvalue()

        # Create video frame
        frame = VideoFrame(
            data=frame_data, width=width, height=height, format="jpeg", timestamp=time.time(), frame_number=self.frame_counter
        )

        self.frame_counter += 1

        return frame

    async def set_environment(self, environment: str, **kwargs) -> bool:
        """
        Change the mock environment.

        Args:
            environment: Environment name
            **kwargs: Additional parameters

        Returns:
            True if successful
        """
        if not self.connected:
            return False

        self.environment_state.world_name = environment

        # Reset position
        self.environment_state.agent_position = Vector3(kwargs.get("x", 0.0), kwargs.get("y", 0.0), kwargs.get("z", 0.0))

        # Emit environment change event
        await self._emit_event("environment_changed", {"environment": environment, "parameters": kwargs})

        return True

    async def execute_behavior(self, behavior: str, parameters: Dict[str, Any]) -> bool:
        """
        Execute a mock behavior.

        Args:
            behavior: Behavior name
            parameters: Behavior parameters

        Returns:
            True if successful
        """
        if not self.connected:
            return False

        # Simulate behavior execution
        await asyncio.sleep(0.1)

        # Create animation data for behavior
        animation = CanonicalAnimationData(
            timestamp=time.time(),
            gesture=GestureType.WAVE if behavior == "greet" else GestureType.NONE,
            emotion=EmotionType.HAPPY if behavior == "greet" else EmotionType.NEUTRAL,
        )

        await self.send_animation_data(animation)

        # Emit behavior event
        await self._emit_event("behavior_executed", {"behavior": behavior, "parameters": parameters})

        return True

    async def _event_simulation_loop(self):
        """Simulate random events for testing."""
        event_types = ["user_joined", "user_left", "object_spawned", "interaction_available"]

        while self.simulate_events and self.connected:
            try:
                # Wait random interval
                await asyncio.sleep(5 + np.random.exponential(5))

                # Generate random event
                import random

                event_type = random.choice(event_types)

                event_data = {"type": event_type, "timestamp": time.time()}

                if event_type == "user_joined":
                    event_data["user"] = {"id": f"user_{random.randint(1000, 9999)}", "name": f"User{random.randint(1, 100)}"}
                elif event_type == "object_spawned":
                    event_data["object"] = {
                        "id": f"obj_{random.randint(1000, 9999)}",
                        "type": random.choice(["cube", "sphere", "cylinder"]),
                    }

                await self._emit_event("world_event", event_data)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in event simulation: %s", e)

    async def get_statistics(self) -> Dict[str, Any]:
        """Get mock backend statistics."""
        return {
            "backend": self.backend_name,
            "connected_duration": time.time() - self.environment_state.agent_position.x,  # Hack for demo
            "frames_sent": len(self.animation_history),
            "audio_sent": len(self.audio_history),
            "frames_captured": self.frame_counter,
            "errors": 0,
        }

    # Test helper methods
    def get_animation_history(self) -> List[Dict[str, Any]]:
        """Get history of sent animations for testing."""
        return [anim.to_dict() for anim in self.animation_history]

    def clear_history(self):
        """Clear animation and audio history."""
        self.animation_history.clear()
        self.audio_history.clear()
        self.frame_counter = 0
