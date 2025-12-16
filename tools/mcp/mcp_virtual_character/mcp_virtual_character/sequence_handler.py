"""Sequence handling module for Virtual Character MCP Server.

This module handles:
- Event sequence creation and management
- Sequence playback with proper timing
- Event type processing (animation, audio, expression, movement, parallel)
- Sequence state management (play, pause, resume, stop)
"""

import asyncio
import base64
import binascii
import logging
from typing import Any, Dict, List, Optional

from .backends.base import BackendAdapter
from .models.canonical import (
    AudioData,
    CanonicalAnimationData,
    EmotionType,
    EventSequence,
    EventType,
    GestureType,
    SequenceEvent,
)

logger = logging.getLogger(__name__)

__all__ = ["SequenceHandler"]


class SequenceHandler:
    """Handles event sequence creation, management, and playback."""

    def __init__(self) -> None:
        # Sequence state
        self.current_sequence: Optional[EventSequence] = None
        self.sequence_task: Optional["asyncio.Task[None]"] = None
        self.sequence_paused: bool = False
        self.sequence_time: float = 0.0
        self._pause_event: asyncio.Event = asyncio.Event()
        self._pause_event.set()  # Not paused initially

    async def create_sequence(
        self,
        name: str,
        description: Optional[str] = None,
        loop: bool = False,
        interrupt_current: bool = True,
    ) -> Dict[str, Any]:
        """
        Create a new event sequence.

        Note: This uses a single shared sequence builder. Concurrent calls
        will overwrite each other. Only one sequence can be built at a time.
        """
        try:
            # Stop current sequence if needed
            if interrupt_current and self.sequence_task:
                await self.stop_sequence()

            # Create new sequence
            loop_obj = asyncio.get_running_loop()
            self.current_sequence = EventSequence(
                name=name,
                description=description,
                loop=loop,
                interrupt_current=interrupt_current,
                created_timestamp=loop_obj.time(),
            )

            return {"success": True, "message": f"Created sequence: {name}"}

        except RuntimeError as e:
            logger.error("Event loop error creating sequence: %s", e)
            return {"success": False, "error": f"Event loop error: {e}"}
        except TypeError as e:
            logger.error("Invalid parameter type creating sequence: %s", e)
            return {"success": False, "error": f"Invalid parameter: {e}"}

    async def add_event(
        self,
        event_type: str,
        timestamp: float,
        duration: Optional[float] = None,
        animation_params: Optional[Dict[str, Any]] = None,
        audio_data: Optional[str] = None,
        audio_format: str = "mp3",
        wait_duration: Optional[float] = None,
        expression: Optional[str] = None,
        expression_intensity: float = 1.0,
        movement_params: Optional[Dict[str, Any]] = None,
        parallel_events: Optional[List[Dict[str, Any]]] = None,
        sync_with_audio: bool = False,
    ) -> Dict[str, Any]:
        """Add an event to the current sequence."""
        if not self.current_sequence:
            return {"success": False, "error": "No sequence created. Use create_sequence first."}

        try:
            # Build event dictionary
            event_dict: Dict[str, Any] = {
                "event_type": event_type,
                "timestamp": timestamp,
                "duration": duration,
                "sync_with_audio": sync_with_audio,
            }

            # Add type-specific parameters
            if animation_params:
                event_dict["animation_params"] = animation_params
            if audio_data:
                event_dict["audio_data"] = audio_data
                event_dict["audio_format"] = audio_format
            if wait_duration is not None:
                event_dict["wait_duration"] = wait_duration
            if expression:
                event_dict["expression"] = expression
                event_dict["expression_intensity"] = expression_intensity
            if movement_params:
                event_dict["movement_params"] = movement_params
            if parallel_events:
                event_dict["parallel_events"] = parallel_events

            # Create event from dictionary
            event = await self._create_event_from_dict(event_dict)
            if not event:
                return {"success": False, "error": "Failed to create event from parameters"}

            # Add to sequence
            self.current_sequence.add_event(event)

            return {"success": True, "message": f"Added {event_type} event at {timestamp}s"}

        except KeyError as e:
            logger.error("Missing required event parameter: %s", e)
            return {"success": False, "error": f"Missing parameter: {e}"}
        except ValueError as e:
            logger.error("Invalid event parameter value: %s", e)
            return {"success": False, "error": f"Invalid value: {e}"}
        except TypeError as e:
            logger.error("Invalid event parameter type: %s", e)
            return {"success": False, "error": f"Type error: {e}"}

    async def play_sequence(
        self,
        backend: Optional[BackendAdapter],
        _sequence_name: Optional[str] = None,
        start_time: float = 0.0,
    ) -> Dict[str, Any]:
        """Play an event sequence."""
        if not backend:
            return {"success": False, "error": "No backend connected. Use set_backend first."}

        if not self.current_sequence:
            return {"success": False, "error": "No sequence to play. Create and build a sequence first."}

        try:
            # Cancel any existing sequence properly
            await self._cancel_running_sequence()

            # Reset state
            self.sequence_time = start_time
            self.sequence_paused = False
            self._pause_event.set()

            # Start playback
            self.sequence_task = asyncio.create_task(self._execute_sequence(backend))

            return {"success": True, "message": f"Started playing sequence: {self.current_sequence.name}"}

        except RuntimeError as e:
            logger.error("Runtime error playing sequence: %s", e)
            return {"success": False, "error": f"Runtime error: {e}"}

    async def pause_sequence(self) -> Dict[str, Any]:
        """Pause the currently playing sequence."""
        if not self.sequence_task or self.sequence_task.done():
            return {"success": False, "error": "No sequence is playing"}

        self.sequence_paused = True
        self._pause_event.clear()
        return {"success": True, "message": "Sequence paused"}

    async def resume_sequence(self) -> Dict[str, Any]:
        """Resume the paused sequence."""
        if not self.sequence_task or self.sequence_task.done():
            return {"success": False, "error": "No sequence to resume"}

        self.sequence_paused = False
        self._pause_event.set()
        return {"success": True, "message": "Sequence resumed"}

    async def stop_sequence(self) -> Dict[str, Any]:
        """Stop the currently playing sequence."""
        if self.sequence_task:
            await self._cancel_running_sequence()
            self.sequence_time = 0.0
            return {"success": True, "message": "Sequence stopped"}

        return {"success": False, "error": "No sequence is playing"}

    async def get_status(self) -> Dict[str, Any]:
        """Get status of current sequence playback."""
        status: Dict[str, Any] = {
            "has_sequence": self.current_sequence is not None,
            "is_playing": self.sequence_task is not None and not self.sequence_task.done(),
            "is_paused": self.sequence_paused,
            "current_time": self.sequence_time,
        }

        if self.current_sequence:
            status.update(
                {
                    "sequence_name": self.current_sequence.name,
                    "total_duration": self.current_sequence.total_duration,
                    "event_count": len(self.current_sequence.events),
                    "loop": self.current_sequence.loop,
                }
            )

        return {"success": True, "status": status}

    async def panic_reset(self, backend: Optional[BackendAdapter]) -> Dict[str, Any]:
        """Emergency reset - stops all sequences and resets avatar."""
        try:
            # Cancel running sequence
            await self._cancel_running_sequence()

            # Clear state
            self.current_sequence = None
            self.sequence_paused = False
            self.sequence_time = 0
            self._pause_event.set()

            # Reset avatar if backend available
            if backend:
                await self._reset_avatar_state(backend)

            return {"success": True, "message": "Emergency reset completed"}

        except asyncio.CancelledError:  # pylint: disable=try-except-raise
            # Re-raise cancellation (required for proper async cleanup)
            raise
        except OSError as e:
            logger.error("I/O error during panic reset: %s", e)
            return {"success": False, "error": f"I/O error: {e}"}
        except RuntimeError as e:
            logger.error("Runtime error during panic reset: %s", e)
            return {"success": False, "error": f"Runtime error: {e}"}

    async def _cancel_running_sequence(self) -> None:
        """Properly cancel a running sequence task."""
        if self.sequence_task and not self.sequence_task.done():
            self.sequence_task.cancel()
            try:
                await self.sequence_task
            except asyncio.CancelledError:
                pass
            self.sequence_task = None

    async def _execute_sequence(self, backend: BackendAdapter) -> None:
        """Execute the current sequence with efficient event scheduling."""
        if not self.current_sequence or not backend:
            return

        try:
            # Reset avatar state before starting
            await self._reset_avatar_state(backend)

            # Sort events by timestamp
            sorted_events = sorted(self.current_sequence.events, key=lambda e: e.timestamp)

            loop = asyncio.get_running_loop()
            start_time = loop.time()

            # Execute events at scheduled times
            for event in sorted_events:
                # Handle pause
                if self.sequence_paused:
                    pause_start = loop.time()
                    await self._pause_event.wait()
                    pause_duration = loop.time() - pause_start
                    start_time += pause_duration

                # Calculate wait time
                current_time = loop.time() - start_time
                time_to_wait = event.timestamp - current_time

                if time_to_wait > 0:
                    await asyncio.sleep(time_to_wait)

                # Execute event with error handling
                try:
                    await self._execute_event(event, backend)
                except asyncio.CancelledError:  # pylint: disable=try-except-raise
                    raise
                except OSError as e:
                    logger.error("I/O error executing event at %ss: %s", event.timestamp, e)
                except ValueError as e:
                    logger.error("Value error executing event at %ss: %s", event.timestamp, e)

            # Wait for remaining duration
            if self.current_sequence.total_duration:
                final_wait = self.current_sequence.total_duration - (loop.time() - start_time)
                if final_wait > 0:
                    await asyncio.sleep(final_wait)

            # Handle looping
            if self.current_sequence.loop:
                self.sequence_time = 0
                await self._execute_sequence(backend)

        except asyncio.CancelledError:
            logger.info("Sequence cancelled")
            raise
        finally:
            # Reset avatar state after completion
            await self._reset_avatar_state(backend)

    async def _execute_event(self, event: SequenceEvent, backend: BackendAdapter) -> None:
        """Execute a single event."""
        if event.event_type == EventType.ANIMATION and event.animation_data:
            await backend.send_animation_data(event.animation_data)

        elif event.event_type == EventType.AUDIO and event.audio_data:
            await backend.send_audio_data(event.audio_data)

        elif event.event_type == EventType.WAIT:
            # Wait is handled by timing logic
            pass

        elif event.event_type == EventType.EXPRESSION:
            animation = CanonicalAnimationData(
                timestamp=event.timestamp,
                emotion=event.expression,
                emotion_intensity=event.expression_intensity or 1.0,
            )
            await backend.send_animation_data(animation)

        elif event.event_type == EventType.MOVEMENT and event.movement_params:
            animation = CanonicalAnimationData(timestamp=event.timestamp, parameters=event.movement_params)
            await backend.send_animation_data(animation)

        elif event.event_type == EventType.PARALLEL and event.parallel_events:
            # Execute parallel events concurrently
            tasks = [self._execute_event(e, backend) for e in event.parallel_events]
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _reset_avatar_state(self, backend: BackendAdapter) -> None:
        """Reset avatar to neutral state."""
        try:
            neutral_animation = CanonicalAnimationData(
                timestamp=0,
                emotion=EmotionType.NEUTRAL,
                emotion_intensity=0,
                gesture=GestureType.NONE,
                gesture_intensity=0,
                parameters={
                    "move_forward": 0,
                    "move_right": 0,
                    "look_horizontal": 0,
                    "look_vertical": 0,
                    "jump": False,
                    "crouch": False,
                    "run": False,
                },
            )
            await backend.send_animation_data(neutral_animation)
            await asyncio.sleep(0.1)

        except asyncio.CancelledError:  # pylint: disable=try-except-raise
            raise
        except OSError as e:
            logger.error("I/O error resetting avatar state: %s", e)
        except RuntimeError as e:
            logger.error("Runtime error resetting avatar state: %s", e)

    async def _create_event_from_dict(self, event_dict: Dict[str, Any]) -> Optional[SequenceEvent]:
        """Create a SequenceEvent from dictionary parameters."""
        try:
            event_type_str = event_dict.get("event_type", "").upper()
            if not event_type_str or event_type_str not in EventType.__members__:
                logger.error("Invalid event_type: %s", event_type_str)
                return None

            event = SequenceEvent(
                event_type=EventType[event_type_str],
                timestamp=event_dict.get("timestamp", 0.0),
                duration=event_dict.get("duration"),
                sync_with_audio=event_dict.get("sync_with_audio", False),
            )

            # Parse type-specific data
            if event_type_str == "ANIMATION":
                await self._populate_animation_event(event, event_dict.get("animation_params", {}))
            elif event_type_str == "AUDIO":
                await self._populate_audio_event(event, event_dict)
            elif event_type_str == "EXPRESSION":
                await self._populate_expression_event(event, event_dict)
            elif event_type_str == "MOVEMENT":
                event.movement_params = event_dict.get("movement_params")
            elif event_type_str == "WAIT":
                event.wait_duration = event_dict.get("wait_duration", event_dict.get("duration", 1.0))
            elif event_type_str == "PARALLEL":
                await self._populate_parallel_events(event, event_dict)

            return event

        except KeyError as e:
            logger.error("Missing key in event dict: %s", e)
            return None
        except TypeError as e:
            logger.error("Type error creating event from dict: %s", e)
            return None
        except ValueError as e:
            logger.error("Value error creating event from dict: %s", e)
            return None

    async def _populate_animation_event(self, event: SequenceEvent, params: Dict[str, Any]) -> None:
        """Populate animation data on event."""
        animation = CanonicalAnimationData(timestamp=event.timestamp)

        if "emotion" in params:
            animation.emotion = EmotionType[params["emotion"].upper()]
            animation.emotion_intensity = params.get("emotion_intensity", 1.0)

        if "gesture" in params:
            animation.gesture = GestureType[params["gesture"].upper()]
            animation.gesture_intensity = params.get("gesture_intensity", 1.0)

        if "parameters" in params:
            animation.parameters = params["parameters"]

        event.animation_data = animation

    async def _populate_audio_event(self, event: SequenceEvent, event_dict: Dict[str, Any]) -> None:
        """Populate audio data on event."""
        audio_data_str = event_dict.get("audio_data")
        if audio_data_str:
            try:
                if audio_data_str.startswith("data:"):
                    audio_data_str = audio_data_str.split(",")[1]
                audio_bytes = base64.b64decode(audio_data_str)
                event.audio_data = AudioData(
                    data=audio_bytes,
                    format=event_dict.get("audio_format", "mp3"),
                    duration=event_dict.get("duration", 0.0),
                )
            except binascii.Error as e:
                logger.error("Invalid base64 audio data: %s", e)
                raise ValueError(f"Invalid base64 audio data: {e}") from e

    async def _populate_expression_event(self, event: SequenceEvent, event_dict: Dict[str, Any]) -> None:
        """Populate expression data on event."""
        expression = event_dict.get("expression")
        if expression:
            try:
                event.expression = EmotionType[expression.upper()]
                event.expression_intensity = event_dict.get("expression_intensity", 1.0)
            except KeyError as e:
                logger.error("Unknown expression type: %s", expression)
                raise ValueError(f"Unknown expression type: {expression}") from e

    async def _populate_parallel_events(self, event: SequenceEvent, event_dict: Dict[str, Any]) -> None:
        """Populate parallel events recursively."""
        parallel_data = event_dict.get("parallel_events", [])
        event.parallel_events = []
        for p_dict in parallel_data:
            p_event = await self._create_event_from_dict(p_dict)
            if p_event:
                event.parallel_events.append(p_event)
