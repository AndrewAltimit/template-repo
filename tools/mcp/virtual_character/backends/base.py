"""
Base backend adapter interface for virtual character control.

All backend plugins must implement this interface to ensure
compatibility with the middleware.
"""

import asyncio
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional

from ..models.canonical import AnimationSequence, AudioData, CanonicalAnimationData, EnvironmentState, VideoFrame


class BackendCapabilities:
    """Capabilities that a backend supports."""

    def __init__(self):
        self.audio: bool = False
        self.animation: bool = False
        self.video_capture: bool = False
        self.bidirectional: bool = False
        self.environment_control: bool = False
        self.streaming: bool = False
        self.multi_agent: bool = False
        self.procedural_animation: bool = False
        self.physics_simulation: bool = False

    def to_dict(self) -> Dict[str, bool]:
        """Convert to dictionary."""
        return {
            "audio": self.audio,
            "animation": self.animation,
            "video_capture": self.video_capture,
            "bidirectional": self.bidirectional,
            "environment_control": self.environment_control,
            "streaming": self.streaming,
            "multi_agent": self.multi_agent,
            "procedural_animation": self.procedural_animation,
            "physics_simulation": self.physics_simulation,
        }


class BackendAdapter(ABC):
    """
    Base interface for all backend plugins.

    This abstract class defines the contract that all backend
    implementations must follow to integrate with the middleware.
    """

    def __init__(self):
        self.connected: bool = False
        self.config: Dict[str, Any] = {}
        self.capabilities = BackendCapabilities()
        self._event_handlers: Dict[str, List[Callable]] = {}

    @abstractmethod
    async def connect(self, config: Dict[str, Any]) -> bool:
        """
        Establish connection to the backend system.

        Args:
            config: Backend-specific configuration

        Returns:
            True if connection successful
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """
        Clean up and close connections.
        """
        pass

    @abstractmethod
    async def send_animation_data(self, data: CanonicalAnimationData) -> bool:
        """
        Send animation data in canonical format to backend.

        Args:
            data: Animation data in canonical format

        Returns:
            True if data was sent successfully
        """
        pass

    @abstractmethod
    async def send_audio_data(self, audio: AudioData) -> bool:
        """
        Send audio data with sync metadata.

        Args:
            audio: Audio data with metadata

        Returns:
            True if audio was sent successfully
        """
        pass

    @abstractmethod
    async def receive_state(self) -> Optional[EnvironmentState]:
        """
        Receive current state from virtual environment.

        Returns:
            Current environment state or None if unavailable
        """
        pass

    @abstractmethod
    async def capture_video_frame(self) -> Optional[VideoFrame]:
        """
        Capture current view from agent's perspective.

        Returns:
            Video frame or None if unavailable
        """
        pass

    @property
    @abstractmethod
    def backend_name(self) -> str:
        """
        Get the name of this backend.

        Returns:
            Backend identifier string
        """
        pass

    @property
    def is_connected(self) -> bool:
        """
        Check if backend is currently connected.

        Returns:
            Connection status
        """
        return self.connected

    async def play_animation_sequence(self, sequence: AnimationSequence) -> bool:
        """
        Play a complete animation sequence.

        Default implementation sends frames at appropriate times.
        Backends can override for native sequence support.

        Args:
            sequence: Animation sequence to play

        Returns:
            True if sequence started successfully
        """
        if not sequence.keyframes:
            return False

        start_time = asyncio.get_event_loop().time()

        for frame in sequence.keyframes:
            # Wait until frame time
            current_time = asyncio.get_event_loop().time() - start_time
            wait_time = frame.timestamp - current_time

            if wait_time > 0:
                await asyncio.sleep(wait_time)

            # Send frame
            success = await self.send_animation_data(frame)
            if not success:
                return False

        return True

    async def set_environment(self, environment: str, **kwargs) -> bool:
        """
        Change the virtual environment/scene.

        Args:
            environment: Environment identifier
            **kwargs: Additional environment parameters

        Returns:
            True if environment changed successfully
        """
        # Default implementation does nothing
        # Backends with environment control should override
        return False

    @abstractmethod
    async def reset_all(self) -> bool:
        """
        Reset all states - clear emotes, stop movement, reset to neutral.

        This method should clear any active animations, emotes, or movements
        and return the character to a neutral idle state.

        Returns:
            True if reset successful
        """
        pass

    async def execute_behavior(self, behavior: str, parameters: Dict[str, Any]) -> bool:
        """
        Execute a high-level behavior.

        Args:
            behavior: Behavior name (e.g., "greet", "dance", "sit")
            parameters: Behavior-specific parameters

        Returns:
            True if behavior started successfully
        """
        # Default implementation does nothing
        # Backends should override with their behavior systems
        return False

    def register_event_handler(self, event_type: str, handler: Callable) -> None:
        """
        Register a handler for backend events.

        Args:
            event_type: Type of event to handle
            handler: Async function to call when event occurs
        """
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        self._event_handlers[event_type].append(handler)

    async def _emit_event(self, event_type: str, data: Any) -> None:
        """
        Emit an event to registered handlers.

        Args:
            event_type: Type of event
            data: Event data
        """
        if event_type in self._event_handlers:
            for handler in self._event_handlers[event_type]:
                try:
                    await handler(data)
                except Exception as e:
                    print(f"Error in event handler for {event_type}: {e}")

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on backend connection.

        Returns:
            Health status information
        """
        return {
            "backend": self.backend_name,
            "connected": self.connected,
            "capabilities": self.capabilities.to_dict(),
            "config": {k: v for k, v in self.config.items() if not k.endswith("password")},
        }

    async def get_statistics(self) -> Dict[str, Any]:
        """
        Get backend statistics and metrics.

        Returns:
            Statistics dictionary
        """
        # Default implementation
        # Backends can override with specific metrics
        return {"backend": self.backend_name, "connected_duration": 0, "frames_sent": 0, "frames_received": 0, "errors": 0}
