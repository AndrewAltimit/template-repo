"""
VRChat Remote Backend Adapter.

Controls VRChat avatars on a remote Windows machine using OSC protocol.
"""

import asyncio
import logging
from typing import Any, Dict, Optional

from mcp_virtual_character.models.canonical import (
    AudioData,
    CanonicalAnimationData,
    EmotionType,
    EnvironmentState,
    GestureType,
    VideoFrame,
)

from .base import BackendAdapter

logger = logging.getLogger(__name__)

try:
    from pythonosc import udp_client
    from pythonosc.dispatcher import Dispatcher
    from pythonosc.osc_server import AsyncIOOSCUDPServer

    HAS_OSC = True
except ImportError:
    HAS_OSC = False
    logger.warning("pythonosc not installed. Install with: pip install python-osc")


class VRChatRemoteBackend(BackendAdapter):
    """
    Backend adapter for controlling VRChat avatars remotely.

    Uses OSC (Open Sound Control) protocol to communicate with VRChat
    and optional bridge server for advanced features like video capture.
    """

    # VRChat OSC standard ports
    VRCHAT_OSC_IN_PORT = 9000  # VRChat receives on this port
    VRCHAT_OSC_OUT_PORT = 9003  # VRChat sends on this port (using 9003 to avoid conflicts)

    # Avatar parameter mappings
    EMOTION_PARAMS = {
        EmotionType.NEUTRAL: "/avatar/parameters/EmotionNeutral",
        EmotionType.HAPPY: "/avatar/parameters/EmotionHappy",
        EmotionType.SAD: "/avatar/parameters/EmotionSad",
        EmotionType.ANGRY: "/avatar/parameters/EmotionAngry",
        EmotionType.SURPRISED: "/avatar/parameters/EmotionSurprised",
        EmotionType.FEARFUL: "/avatar/parameters/EmotionFearful",
        EmotionType.DISGUSTED: "/avatar/parameters/EmotionDisgusted",
    }

    # VRCEmote system (integer-based, common in many avatars)
    # This avatar uses a gesture wheel, not emotions
    # Corrected wheel positions (clockwise from top):
    # 0=None/Clear, 1=Wave, 2=Clap, 3=Point, 4=Cheer, 5=Dance, 6=Backflip, 7=Sadness, 8=Die
    VRCEMOTE_MAP = {
        EmotionType.NEUTRAL: 0,  # No gesture/back to normal
        EmotionType.HAPPY: 4,  # Maps to Cheer
        EmotionType.SAD: 7,  # Maps to Sadness gesture
        EmotionType.ANGRY: 3,  # Maps to Point (assertive)
        EmotionType.SURPRISED: 6,  # Maps to Backflip (excitement)
        EmotionType.FEARFUL: 8,  # Maps to Die (dramatic)
        EmotionType.DISGUSTED: 0,  # Clear gesture
    }

    # Alternative mapping for gesture-based avatars
    VRCEMOTE_GESTURE_MAP = {
        GestureType.NONE: 0,
        GestureType.WAVE: 1,
        GestureType.POINT: 3,
        GestureType.THUMBS_UP: 4,  # Maps to Cheer
        GestureType.NOD: 2,  # Maps to Clap (approval)
        GestureType.SHAKE_HEAD: 0,  # Clear gesture
        GestureType.CLAP: 2,
        GestureType.DANCE: 5,
    }

    GESTURE_PARAMS = {
        GestureType.NONE: 0,
        GestureType.WAVE: 1,
        GestureType.POINT: 2,
        GestureType.THUMBS_UP: 3,
        GestureType.NOD: 4,
        GestureType.SHAKE_HEAD: 5,
        GestureType.CLAP: 6,
        GestureType.DANCE: 7,
    }

    def __init__(self):
        """Initialize VRChat remote backend."""
        super().__init__()

        # Set capabilities
        self.capabilities.animation = True
        self.capabilities.audio = False  # Can be added with bridge server
        self.capabilities.video_capture = False  # Can be added with OBS
        self.capabilities.bidirectional = True
        self.capabilities.environment_control = False  # Limited to world switching
        self.capabilities.streaming = True
        self.capabilities.multi_agent = False

        # OSC clients and servers
        self.osc_client = None
        self.osc_server = None
        self.osc_dispatcher = None

        # Remote configuration
        self.remote_host = "127.0.0.1"
        self.bridge_port = 8021
        self.use_bridge = False

        # Avatar state tracking
        self.current_emotion = EmotionType.NEUTRAL
        self.current_gesture = GestureType.NONE
        self.avatar_params: Dict[str, Any] = {}
        self.use_vrcemote = True  # Most avatars use VRCEmote system
        self.current_vrcemote = 0  # Track current emote for toggle behavior
        self.emote_is_active = False  # Track if an emote is currently active

        # Movement parameters
        self.move_speed = 0.0
        self.turn_speed = 0.0
        self.vertical_movement = 0.0
        self.horizontal_movement = 0.0
        self.movement_active = False  # Track if movement is active
        self.movement_timer = None  # Timer for auto-stop

        # Emote timeout tracking
        self.emote_timer = None  # Timer for auto-clear emotes
        self.emote_start_time = None  # When emote was activated
        self.last_known_emotes = []  # Track last few emote values for recovery

        # Statistics
        self.stats = {
            "osc_messages_sent": 0,
            "osc_messages_received": 0,
            "animation_frames": 0,
            "errors": 0,
        }

    @property
    def backend_name(self) -> str:
        """Get backend name."""
        return "vrchat_remote"

    async def connect(self, config: Dict[str, Any]) -> bool:
        """
        Connect to VRChat via OSC.

        Args:
            config: Configuration including:
                - remote_host: IP of VRChat machine
                - bridge_port: Optional bridge server port
                - use_bridge: Whether to use bridge server
                - osc_in_port: Port for receiving from VRChat
                - osc_out_port: Port for sending to VRChat
                - use_vrcemote: Force VRCEmote system (auto-detects if not set)

        Returns:
            True if connection successful
        """
        if not HAS_OSC:
            logger.error("pythonosc not installed. Cannot connect to VRChat.")
            return False

        try:
            self.config = config
            self.remote_host = config.get("remote_host", "127.0.0.1")
            self.bridge_port = config.get("bridge_port", 8021)
            self.use_bridge = config.get("use_bridge", False)

            # Emotion system configuration
            if "use_vrcemote" in config:
                self.use_vrcemote = config["use_vrcemote"]
                logger.info("Using %s emotion system (configured)", "VRCEmote" if self.use_vrcemote else "traditional")

            # OSC ports
            osc_in_port = config.get("osc_in_port", self.VRCHAT_OSC_IN_PORT)
            osc_out_port = config.get("osc_out_port", self.VRCHAT_OSC_OUT_PORT)

            # Create OSC client for sending to VRChat
            self.osc_client = udp_client.SimpleUDPClient(self.remote_host, osc_in_port)

            # Create OSC server for receiving from VRChat (optional)
            try:
                self.osc_dispatcher = Dispatcher()
                self._setup_osc_handlers()

                # Start OSC server
                loop = asyncio.get_event_loop()
                server_addr = ("0.0.0.0", osc_out_port)
                # AsyncIOOSCUDPServer expects BaseEventLoop but get_event_loop returns AbstractEventLoop
                self.osc_server = AsyncIOOSCUDPServer(server_addr, self.osc_dispatcher, loop)  # type: ignore[arg-type]

                _transport, _protocol = await self.osc_server.create_serve_endpoint()
                logger.info("OSC server listening on port %s", osc_out_port)
            except OSError as e:
                logger.warning("Could not bind OSC server to port %s: %s", osc_out_port, e)
                logger.warning("Continuing without OSC server (send-only mode)")
                self.osc_server = None

            # Test connection with a simple parameter update
            await self._send_osc("/avatar/parameters/TestConnection", 1.0)

            self.connected = True
            logger.info("Connected to VRChat at %s:%s", self.remote_host, osc_in_port)

            return True

        except Exception as e:
            logger.error("Failed to connect to VRChat: %s", e)
            self.stats["errors"] += 1
            return False

    async def disconnect(self) -> None:
        """Disconnect from VRChat."""
        try:
            # OSC server cleanup happens automatically when event loop ends
            # AsyncIOOSCUDPServer doesn't have a shutdown method
            self.osc_server = None
            self.osc_client = None
            self.connected = False
            logger.info("Disconnected from VRChat")

        except Exception as e:
            logger.error("Error during disconnect: %s", e)
            self.stats["errors"] += 1

    async def send_animation_data(self, data: CanonicalAnimationData) -> bool:
        """
        Send animation data to VRChat avatar.

        Args:
            data: Animation data including emotion, gesture, and parameters

        Returns:
            True if successful
        """
        if not self.connected:
            return False

        try:
            # Update emotion if changed
            if data.emotion and data.emotion != self.current_emotion:
                await self._set_emotion(data.emotion, data.emotion_intensity)
                self.current_emotion = data.emotion

            # Update gesture if changed
            if data.gesture and data.gesture != self.current_gesture:
                await self._set_gesture(data.gesture, data.gesture_intensity)
                self.current_gesture = data.gesture

            # Update blend shapes (if avatar supports them)
            if data.blend_shapes:
                for shape, value in data.blend_shapes.items():
                    param_name = f"/avatar/parameters/BlendShape_{shape}"
                    await self._send_osc(param_name, float(value))

            # Handle movement parameters
            if data.parameters:
                await self._handle_movement_params(data.parameters)

            # Update custom avatar parameters
            if data.parameters and "avatar_params" in data.parameters:
                for param, value in data.parameters["avatar_params"].items():
                    await self._send_osc(f"/avatar/parameters/{param}", value)

            self.stats["animation_frames"] += 1
            return True

        except Exception as e:
            logger.error("Failed to send animation data: %s", e)
            self.stats["errors"] += 1
            return False

    async def send_audio_data(self, audio: AudioData) -> bool:
        """
        Send audio data (requires bridge server).

        Args:
            audio: Audio data with sync metadata

        Returns:
            True if successful
        """
        if not self.connected or not self.use_bridge:
            logger.warning("Audio requires bridge server to be enabled")
            return False

        # TODO: Implement bridge server audio streaming
        return False

    async def receive_state(self) -> Optional[EnvironmentState]:
        """
        Receive current state from VRChat.

        Returns:
            Current environment state
        """
        if not self.connected:
            return None

        try:
            # Create basic state from tracked parameters
            state = EnvironmentState()
            state.world_name = self.avatar_params.get("world_name", "Unknown")
            state.agent_position = None  # Would need proper Vector3 type
            state.agent_rotation = None  # Would need proper Quaternion type

            return state

        except Exception as e:
            logger.error("Failed to receive state: %s", e)
            self.stats["errors"] += 1
            return None

    async def capture_video_frame(self) -> Optional[VideoFrame]:
        """
        Capture video frame (requires OBS or bridge server).

        Returns:
            Video frame if available
        """
        if not self.connected:
            return None

        # TODO: Implement OBS or bridge server video capture
        return None

    async def execute_behavior(self, behavior: str, parameters: Dict[str, Any]) -> bool:
        """
        Execute high-level behavior.

        Args:
            behavior: Behavior name
            parameters: Behavior parameters

        Returns:
            True if successful
        """
        if not self.connected:
            return False

        try:
            # Map behaviors to VRChat actions
            behavior_map: Dict[str, Dict[str, Any]] = {
                "greet": {"gesture": GestureType.WAVE, "emotion": EmotionType.HAPPY},
                "dance": {"gesture": GestureType.DANCE},
                "sit": {"avatar_params": {"Sitting": True}},
                "stand": {"avatar_params": {"Sitting": False}},
                "jump": {"input": "Jump"},
                "crouch": {"avatar_params": {"Crouching": True}},
            }

            if behavior in behavior_map:
                action = behavior_map[behavior]

                # Apply gesture
                if "gesture" in action:
                    animation = CanonicalAnimationData(timestamp=asyncio.get_event_loop().time())
                    animation.gesture = action["gesture"]
                    if "emotion" in action:
                        animation.emotion = action["emotion"]
                    await self.send_animation_data(animation)

                # Apply avatar parameters
                if "avatar_params" in action:
                    avatar_params = action["avatar_params"]
                    if isinstance(avatar_params, dict):
                        for param, value in avatar_params.items():
                            await self._send_osc(f"/avatar/parameters/{param}", value)

                # Apply input
                if "input" in action:
                    await self._send_osc(f"/input/{action['input']}", 1)

                return True

            return False

        except Exception as e:
            logger.error("Failed to execute behavior: %s", e)
            self.stats["errors"] += 1
            return False

    # Private helper methods

    async def _send_osc(self, address: str, value: Any) -> None:
        """Send OSC message to VRChat."""
        if self.osc_client:
            self.osc_client.send_message(address, value)
            self.stats["osc_messages_sent"] += 1
            # Log important VRCEmote changes
            if "VRCEmote" in address:
                logger.info("OSC: Sent %s = %s", address, value)

    async def _set_emotion(self, emotion: EmotionType, intensity: float = 1.0) -> None:
        """Set avatar emotion with toggle behavior."""
        if self.use_vrcemote:
            # Use VRCEmote integer system with toggle behavior
            if emotion in self.VRCEMOTE_MAP:
                emote_value = self.VRCEMOTE_MAP[emotion]

                # If trying to activate the same emote, toggle it off
                if self.emote_is_active and self.current_vrcemote == emote_value and emote_value != 0:
                    # Send the same value again to toggle off (not 0!)
                    await self._send_osc("/avatar/parameters/VRCEmote", emote_value)
                    self.emote_is_active = False
                    self.current_vrcemote = 0
                    logger.info("Toggled off VRCEmote %s by resending", emote_value)
                else:
                    # Clear different active emote first if needed
                    if self.emote_is_active and self.current_vrcemote != emote_value and emote_value != 0:
                        # Toggle off the current emote by sending it again
                        await self._send_osc("/avatar/parameters/VRCEmote", self.current_vrcemote)
                        await asyncio.sleep(0.1)  # Small delay for avatar to process
                        logger.info("Toggled off previous emote %s", self.current_vrcemote)

                    # Set the new emote
                    await self._send_osc("/avatar/parameters/VRCEmote", emote_value)
                    self.current_vrcemote = emote_value
                    self.emote_is_active = emote_value != 0

                    # Start timeout timer for emote (10 seconds)
                    if emote_value != 0:
                        self._start_emote_timeout(emote_value)

                    logger.info("Set VRCEmote to %s for %s", emote_value, emotion.value)
        else:
            # Use traditional individual emotion parameters
            # Clear all emotions first
            for param in self.EMOTION_PARAMS.values():
                await self._send_osc(param, 0.0)

            # Set new emotion
            if emotion in self.EMOTION_PARAMS:
                await self._send_osc(self.EMOTION_PARAMS[emotion], intensity)

    async def _set_gesture(self, gesture: GestureType, intensity: float = 1.0) -> None:
        """Set avatar gesture with toggle behavior."""
        if self.use_vrcemote and gesture in self.VRCEMOTE_GESTURE_MAP:
            # Use VRCEmote for gesture-based avatars with toggle behavior
            emote_value = self.VRCEMOTE_GESTURE_MAP[gesture]

            # If trying to activate the same gesture, toggle it off
            if self.emote_is_active and self.current_vrcemote == emote_value and emote_value != 0:
                logger.info("Toggling off active emote %s (same as current)", emote_value)
                # Send the same value again to toggle off (not 0!)
                await self._send_osc("/avatar/parameters/VRCEmote", emote_value)
                self.emote_is_active = False
                self.current_vrcemote = 0
                logger.info("Toggled off VRCEmote %s by resending", emote_value)
            else:
                # Clear different active emote first if needed
                if self.emote_is_active and self.current_vrcemote != emote_value and self.current_vrcemote != 0:
                    logger.info("Clearing previous emote %s before setting %s", self.current_vrcemote, emote_value)
                    # Toggle off the current emote by sending it again
                    await self._send_osc("/avatar/parameters/VRCEmote", self.current_vrcemote)
                    await asyncio.sleep(0.2)  # Give more time for avatar to process
                    logger.info("Toggled off previous gesture %s", self.current_vrcemote)

                # Set the new gesture
                logger.info("Setting new emote %s for gesture %s", emote_value, gesture.value)
                await self._send_osc("/avatar/parameters/VRCEmote", emote_value)
                self.current_vrcemote = emote_value
                self.emote_is_active = emote_value != 0

                # Start timeout timer for emote (10 seconds)
                if emote_value != 0:
                    self._start_emote_timeout(emote_value)

                logger.info("Set VRCEmote to %s for gesture %s, active=%s", emote_value, gesture.value, self.emote_is_active)
        elif gesture in self.GESTURE_PARAMS:
            # Use traditional gesture parameters
            gesture_id = self.GESTURE_PARAMS[gesture]
            await self._send_osc("/avatar/parameters/GestureLeft", gesture_id)
            await self._send_osc("/avatar/parameters/GestureRight", gesture_id)
            await self._send_osc("/avatar/parameters/GestureWeight", intensity)

    async def _handle_movement_params(self, params: Dict[str, Any]) -> None:
        """Handle movement-related parameters with auto-stop."""
        # Clear active emote if one is set (movement should override emotes)
        if self.emote_is_active and self.current_vrcemote != 0:
            logger.info("Clearing active emote %s for movement", self.current_vrcemote)

            # Try multiple approaches to ensure emote clears
            # First: Send 0 to potentially reset state
            await self._send_osc("/avatar/parameters/VRCEmote", 0)
            await asyncio.sleep(0.1)

            # Second: Send the same value to toggle it off
            await self._send_osc("/avatar/parameters/VRCEmote", self.current_vrcemote)
            await asyncio.sleep(0.1)

            # Third: Send 0 again to ensure cleared
            await self._send_osc("/avatar/parameters/VRCEmote", 0)
            await asyncio.sleep(0.1)

            # Update tracking
            self.emote_is_active = False
            self.current_vrcemote = 0
            self.current_gesture = "none"
            logger.info("Emote clearing sequence complete")

        # Cancel emote timer if running
        if self.emote_timer:
            self.emote_timer.cancel()
            self.emote_timer = None

        # Cancel any existing movement timer
        if self.movement_timer:
            self.movement_timer.cancel()
            self.movement_timer = None

        # Movement axes - VRChat expects values between -1.0 and 1.0
        forward_value = 0.0
        right_value = 0.0

        if "move_forward" in params:
            forward_value = float(params["move_forward"])
            # Clamp to valid range
            forward_value = max(-1.0, min(1.0, forward_value))
            self.vertical_movement = forward_value
            await self._send_osc("/input/Vertical", forward_value)
            logger.info("Sent movement Vertical: %s", forward_value)

        if "move_right" in params:
            right_value = float(params["move_right"])
            # Clamp to valid range
            right_value = max(-1.0, min(1.0, right_value))
            self.horizontal_movement = right_value
            await self._send_osc("/input/Horizontal", right_value)
            logger.info("Sent movement Horizontal: %s", right_value)

        # Auto-stop movement after duration (default 2 seconds)
        if forward_value != 0 or right_value != 0:
            self.movement_active = True
            duration = params.get("duration", 2.0)  # Default 2 second movement

            # Schedule auto-stop
            self.movement_timer = asyncio.create_task(self._auto_stop_movement(duration))
            logger.info("Movement will auto-stop in %s seconds", duration)
        else:
            self.movement_active = False

        # Looking/turning
        if "look_horizontal" in params:
            value = float(params["look_horizontal"])
            value = max(-1.0, min(1.0, value))
            await self._send_osc("/input/LookHorizontal", value)
            logger.info("Sent look horizontal: %s", value)

        if "look_vertical" in params:
            value = float(params["look_vertical"])
            value = max(-1.0, min(1.0, value))
            await self._send_osc("/input/LookVertical", value)
            logger.info("Sent look vertical: %s", value)

        # Movement speed modifier
        if "run" in params:
            # Run is a boolean toggle
            run_value = 1 if params["run"] else 0
            await self._send_osc("/input/Run", run_value)
            logger.info("Sent run: %s", run_value)

        # Actions (button-style inputs)
        if "jump" in params and params["jump"]:
            await self._send_osc("/input/Jump", 1)
            logger.info("Sent jump: 1")
            # Auto-release after short delay
            await asyncio.sleep(0.1)
            await self._send_osc("/input/Jump", 0)

        if "crouch" in params:
            crouch_value = 1 if params["crouch"] else 0
            await self._send_osc("/input/Crouch", crouch_value)
            logger.info("Sent crouch: %s", crouch_value)

    async def _auto_stop_movement(self, duration: float) -> None:
        """Automatically stop movement after duration."""
        try:
            await asyncio.sleep(duration)

            # Stop all movement
            if self.movement_active:
                await self._send_osc("/input/Vertical", 0.0)
                await self._send_osc("/input/Horizontal", 0.0)
                self.vertical_movement = 0.0
                self.horizontal_movement = 0.0
                self.movement_active = False
                logger.info("Auto-stopped movement after timeout")
        except asyncio.CancelledError:
            pass  # Timer was cancelled

    async def reset_all(self) -> bool:
        """Reset all states - clear emotes and stop movement."""
        try:
            # Clear any active emote
            if self.emote_is_active and self.current_vrcemote != 0:
                await self._send_osc("/avatar/parameters/VRCEmote", self.current_vrcemote)
                self.emote_is_active = False
                self.current_vrcemote = 0
                logger.info("Reset: Cleared active emote")

            # Stop all movement
            await self._send_osc("/input/Vertical", 0.0)
            await self._send_osc("/input/Horizontal", 0.0)
            await self._send_osc("/input/Run", 0)
            await self._send_osc("/input/Jump", 0)
            await self._send_osc("/input/Crouch", 0)

            # Reset state tracking
            self.vertical_movement = 0.0
            self.horizontal_movement = 0.0
            self.movement_active = False

            # Cancel any timers
            if self.movement_timer:
                self.movement_timer.cancel()
                self.movement_timer = None

            logger.info("Reset: All states cleared")
            return True
        except Exception as e:
            logger.error("Failed to reset: %s", e)
            return False

    def _start_emote_timeout(self, emote_value: int) -> None:
        """Start timeout timer for emote."""
        # Cancel existing timer
        if self.emote_timer:
            self.emote_timer.cancel()

        # Track this emote
        if emote_value not in self.last_known_emotes:
            self.last_known_emotes.append(emote_value)
            # Keep only last 3 emotes
            if len(self.last_known_emotes) > 3:
                self.last_known_emotes.pop(0)

        # Start new timer (10 seconds)
        self.emote_timer = asyncio.create_task(self._emote_timeout(emote_value))
        logger.info("Started 10-second timeout for emote %s", emote_value)

    async def _emote_timeout(self, emote_value: int) -> None:
        """Auto-clear emote after timeout."""
        try:
            await asyncio.sleep(10.0)

            # Force clear the emote
            logger.info("Emote %s timed out, force clearing", emote_value)
            await self._force_clear_emotes()

        except asyncio.CancelledError:
            pass  # Timer was cancelled

    async def _force_clear_emotes(self) -> None:
        """Force clear all possible active emotes."""
        logger.info("Force clearing emotes")

        # Build list of emotes to try clearing
        emotes_to_clear = []

        # Add current tracked emote
        if self.current_vrcemote != 0:
            emotes_to_clear.append(self.current_vrcemote)

        # Add recently used emotes
        emotes_to_clear.extend(self.last_known_emotes)

        # Remove duplicates while preserving order (most recent first)
        seen = set()
        unique_emotes = []
        for emote in reversed(emotes_to_clear):
            if emote not in seen and emote != 0:
                seen.add(emote)
                unique_emotes.append(emote)

        if unique_emotes:
            logger.info("Attempting to clear emotes: %s", unique_emotes)

            # Toggle off each emote (send once to toggle off)
            for emote_val in unique_emotes:
                logger.info("Toggling off emote %s", emote_val)
                await self._send_osc("/avatar/parameters/VRCEmote", emote_val)
                await asyncio.sleep(0.1)  # Give time for toggle to register

        # Reset all tracking
        self.emote_is_active = False
        self.current_vrcemote = 0
        self.current_gesture = "none"
        logger.info("Force clear complete")

    def _setup_osc_handlers(self) -> None:
        """Setup OSC message handlers for receiving from VRChat."""
        if not self.osc_dispatcher:
            return

        # Handle avatar parameter updates
        def avatar_param_handler(address: str, *args):
            """Handle incoming avatar parameter updates."""
            param_name = address.replace("/avatar/parameters/", "")
            if args:
                self.avatar_params[param_name] = args[0]
                self.stats["osc_messages_received"] += 1

                # Auto-detect VRCEmote system
                if param_name == "VRCEmote" and not self.use_vrcemote:
                    logger.info("VRCEmote detected! Switching to VRCEmote emotion system.")
                    self.use_vrcemote = True

        # Register handlers
        self.osc_dispatcher.map("/avatar/parameters/*", avatar_param_handler)

        # Handle world/instance info if available
        def world_handler(address: str, *args):
            """Handle world information."""
            if args:
                self.avatar_params["world_name"] = args[0]

        self.osc_dispatcher.map("/world/*", world_handler)

    async def get_statistics(self) -> Dict[str, Any]:
        """Get backend statistics."""
        return {
            "backend": self.backend_name,
            "connected": self.connected,
            "remote_host": self.remote_host,
            **self.stats,
            "current_emotion": self.current_emotion.value if self.current_emotion else "none",
            "current_gesture": self.current_gesture.value if self.current_gesture else "none",
            "tracked_params": len(self.avatar_params),
        }
