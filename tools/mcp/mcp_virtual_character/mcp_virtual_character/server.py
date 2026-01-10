"""Virtual Character MCP Server for AI Agent Embodiment"""

import argparse
import asyncio
import logging
import os
import sys
from typing import Any, Dict, List, Optional, cast

from mcp_core.base_server import BaseMCPServer
from mcp_virtual_character.audio_handler import AudioHandler
from mcp_virtual_character.backends.base import BackendAdapter
from mcp_virtual_character.backends.mock import MockBackend
from mcp_virtual_character.backends.vrchat_remote import VRChatRemoteBackend
from mcp_virtual_character.constants import (
    VRCEMOTE_DESCRIPTION,
    VRCEmoteValue,
    get_vrcemote_name,
)
from mcp_virtual_character.models.canonical import (
    AudioData,
    CanonicalAnimationData,
    EmotionType,
    GestureType,
)
from mcp_virtual_character.sequence_handler import SequenceHandler

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class VirtualCharacterMCPServer(BaseMCPServer):  # pylint: disable=too-many-public-methods
    """MCP Server for Virtual Character Control"""

    def __init__(self, port: int = 8020, auto_connect: bool = True):
        super().__init__(
            name="Virtual Character MCP Server",
            version="1.0.0",
            port=port,
        )

        # Available backends
        self.backends: Dict[str, type] = {
            "mock": MockBackend,
            "vrchat_remote": VRChatRemoteBackend,
        }

        # Current backend instance
        self.current_backend: Optional[BackendAdapter] = None
        self.backend_name: Optional[str] = None
        self.config: Optional[Dict[str, Any]] = None  # Store backend config for reconnection

        # Default configuration for auto-connect
        self.default_backend = "vrchat_remote"
        self.default_config = {
            "remote_host": os.environ.get("VRCHAT_HOST", "127.0.0.1"),
            "osc_in_port": 9000,
            "osc_out_port": 9001,
            "use_vrcemote": os.environ.get("VRCHAT_USE_VRCEMOTE", "true").lower() == "true",
            "use_bridge": os.environ.get("VRCHAT_USE_BRIDGE", "false").lower() == "true",
            "bridge_port": int(os.environ.get("VRCHAT_BRIDGE_PORT", "8020")),
        }
        self.auto_connect = auto_connect
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 3

        # Audio handler
        self.audio_handler = AudioHandler()

        # Sequence handler
        self.sequence_handler = SequenceHandler()

        # Setup additional routes
        self.setup_routes()

    def setup_routes(self):
        """Setup FastAPI routes for virtual character control."""

        # Legacy HTTP endpoints for backward compatibility
        @self.app.post("/set_backend")
        async def set_backend_http(request: Dict[str, Any]) -> Dict[str, Any]:
            """Legacy HTTP endpoint"""
            return await self.set_backend(backend=request.get("backend", "mock"), config=request.get("config", {}))

        @self.app.post("/send_animation")
        async def send_animation_http(request: Dict[str, Any]) -> Dict[str, Any]:
            """Legacy HTTP endpoint"""
            return await self.send_animation(**request)

        @self.app.post("/audio/play")
        async def play_audio_http(request: Dict[str, Any]) -> Dict[str, Any]:
            """
            Audio bridge endpoint - plays audio through virtual audio cable.

            Requirements:
            1. Install VB-Audio Virtual Cable or similar
            2. Set virtual cable as default playback device or specify device
            3. Set VRChat microphone input to virtual cable output
            """
            audio_data = request.get("audio_data")
            audio_format = request.get("format", "mp3")
            device_name = request.get("device")

            if not audio_data:
                return {"success": False, "error": "No audio data provided"}

            result = await self.audio_handler.play_audio(audio_data, audio_format, device_name)
            return cast(Dict[str, Any], result)

    def get_tools(self) -> Dict[str, Dict[str, Any]]:
        """Return available MCP tools"""
        return {
            "set_backend": {
                "description": "Connect to a virtual character backend (mock, vrchat_remote)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "backend": {
                            "type": "string",
                            "enum": ["mock", "vrchat_remote"],
                            "description": "Backend to connect to",
                        },
                        "config": {
                            "type": "object",
                            "description": "Backend configuration",
                            "properties": {
                                "remote_host": {"type": "string", "description": "Remote host IP (for vrchat_remote)"},
                                "use_vrcemote": {"type": "boolean", "description": "Use VRCEmote system for gestures"},
                                "osc_in_port": {
                                    "type": "integer",
                                    "default": 9000,
                                    "description": "DEPRECATED: Use vrchat_recv_port instead.",
                                },
                                "osc_out_port": {
                                    "type": "integer",
                                    "default": 9001,
                                    "description": "DEPRECATED: Use vrchat_send_port instead.",
                                },
                                "vrchat_recv_port": {
                                    "type": "integer",
                                    "default": 9000,
                                    "description": "Port where VRChat receives (clearer name for osc_in_port)",
                                },
                                "vrchat_send_port": {
                                    "type": "integer",
                                    "default": 9001,
                                    "description": "Port where VRChat sends (clearer name for osc_out_port)",
                                },
                            },
                        },
                    },
                    "required": ["backend"],
                },
            },
            "send_animation": {
                "description": "Send animation data to the current backend",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "emotion": {
                            "type": "string",
                            "enum": ["neutral", "happy", "sad", "angry", "surprised", "fearful", "disgusted"],
                            "description": "Emotion to display",
                        },
                        "emotion_intensity": {
                            "type": "number",
                            "minimum": 0,
                            "maximum": 1,
                            "default": 1.0,
                            "description": "Emotion intensity (0-1)",
                        },
                        "gesture": {
                            "type": "string",
                            "enum": [
                                "none",
                                "wave",
                                "point",
                                "thumbs_up",
                                "nod",
                                "shake_head",
                                "clap",
                                "dance",
                                "backflip",
                                "cheer",
                                "sadness",
                                "die",
                            ],
                            "description": "Gesture to perform",
                        },
                        "gesture_intensity": {
                            "type": "number",
                            "minimum": 0,
                            "maximum": 1,
                            "default": 1.0,
                            "description": "Gesture intensity (0-1)",
                        },
                        "parameters": {
                            "type": "object",
                            "description": "Movement parameters",
                            "properties": {
                                "move_forward": {"type": "number", "minimum": -1, "maximum": 1},
                                "move_right": {"type": "number", "minimum": -1, "maximum": 1},
                                "look_horizontal": {"type": "number", "minimum": -1, "maximum": 1},
                                "look_vertical": {"type": "number", "minimum": -1, "maximum": 1},
                                "jump": {"type": "boolean"},
                                "crouch": {"type": "boolean"},
                                "run": {"type": "boolean"},
                                "duration": {
                                    "type": "number",
                                    "default": 2.0,
                                    "description": "How long to move in seconds (auto-stops after)",
                                },
                            },
                        },
                    },
                },
            },
            "execute_behavior": {
                "description": "Execute a high-level behavior",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "behavior": {"type": "string", "description": "Behavior to execute (greet, dance, sit, stand, etc.)"},
                        "parameters": {"type": "object", "description": "Behavior parameters"},
                    },
                    "required": ["behavior"],
                },
            },
            "reset": {
                "description": (
                    "Reset all states - clear emotes and stop all movement. "
                    "All backends must implement this method to return the character to a neutral idle state."
                ),
                "parameters": {"type": "object", "properties": {}},
            },
            "get_backend_status": {
                "description": "Get current backend status and statistics",
                "parameters": {"type": "object", "properties": {}},
            },
            "list_backends": {"description": "List available backends", "parameters": {"type": "object", "properties": {}}},
            "play_audio": {
                "description": "Play audio through the virtual character with optional lip-sync metadata",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "audio_data": {
                            "type": "string",
                            "description": "File path, URL, or base64-encoded audio data",
                        },
                        "audio_format": {
                            "type": "string",
                            "enum": ["mp3", "wav", "opus", "pcm"],
                            "default": "mp3",
                            "description": "Audio format",
                        },
                        "text": {
                            "type": "string",
                            "description": "Optional text transcript for lip-sync generation",
                        },
                        "expression_tags": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "ElevenLabs audio tags like [laughs], [whisper]",
                        },
                        "duration": {
                            "type": "number",
                            "description": "Audio duration in seconds",
                        },
                    },
                    "required": ["audio_data"],
                },
            },
            "create_sequence": {
                "description": (
                    "Create a new event sequence for coordinated animations and audio. "
                    "NOTE: This operates on a single, shared sequence builder."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Sequence name"},
                        "description": {"type": "string", "description": "Optional description"},
                        "loop": {"type": "boolean", "default": False, "description": "Whether to loop the sequence"},
                        "interrupt_current": {
                            "type": "boolean",
                            "default": True,
                            "description": "Whether to interrupt current sequence",
                        },
                    },
                    "required": ["name"],
                },
            },
            "add_sequence_event": {
                "description": "Add an event to the current sequence",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "event_type": {
                            "type": "string",
                            "enum": ["animation", "audio", "wait", "expression", "movement", "parallel"],
                            "description": "Type of event",
                        },
                        "timestamp": {"type": "number", "description": "When to trigger (seconds from sequence start)"},
                        "duration": {"type": "number", "description": "Event duration in seconds"},
                        "animation_params": {"type": "object", "description": "Animation parameters (emotion, gesture, etc.)"},
                        "audio_data": {"type": "string", "description": "Base64 audio data for audio events"},
                        "audio_format": {"type": "string", "enum": ["mp3", "wav", "opus"], "default": "mp3"},
                        "wait_duration": {"type": "number", "description": "Duration for wait events"},
                        "expression": {
                            "type": "string",
                            "enum": ["neutral", "happy", "sad", "angry", "surprised", "fearful", "disgusted"],
                        },
                        "expression_intensity": {"type": "number", "minimum": 0, "maximum": 1, "default": 1.0},
                        "movement_params": {"type": "object", "description": "Movement parameters"},
                        "parallel_events": {"type": "array", "description": "Events to run in parallel"},
                        "sync_with_audio": {"type": "boolean", "default": False},
                    },
                    "required": ["event_type", "timestamp"],
                },
            },
            "play_sequence": {
                "description": "Play the current or specified event sequence",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "sequence_name": {"type": "string", "description": "Name of sequence to play"},
                        "start_time": {"type": "number", "default": 0, "description": "Start time within sequence"},
                    },
                },
            },
            "pause_sequence": {
                "description": "Pause the currently playing sequence",
                "parameters": {"type": "object", "properties": {}},
            },
            "resume_sequence": {
                "description": "Resume the paused sequence",
                "parameters": {"type": "object", "properties": {}},
            },
            "stop_sequence": {
                "description": "Stop the currently playing sequence",
                "parameters": {"type": "object", "properties": {}},
            },
            "get_sequence_status": {
                "description": "Get status of current sequence playback",
                "parameters": {"type": "object", "properties": {}},
            },
            "panic_reset": {
                "description": "Emergency reset - stops all sequences and resets avatar to neutral state.",
                "parameters": {"type": "object", "properties": {}},
            },
            "send_vrcemote": {
                "description": "Send a direct VRCEmote value (0-8) to VRChat backend for precise gesture control",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "emote_value": {
                            "type": "integer",
                            "minimum": int(VRCEmoteValue.NONE),
                            "maximum": int(VRCEmoteValue.DIE),
                            "description": VRCEMOTE_DESCRIPTION,
                        }
                    },
                    "required": ["emote_value"],
                },
            },
        }

    async def set_backend(self, backend: str, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Connect to a specific backend."""
        if config is None:
            config = {}

        try:
            # Convert clearer port names to internal format (backward compatibility)
            improved_config = self._get_improved_port_config(config)

            # Disconnect current backend if any
            if self.current_backend:
                await self.current_backend.disconnect()

            # Create and connect new backend
            if backend not in self.backends:
                return {"success": False, "error": f"Unknown backend: {backend}"}

            backend_class = self.backends[backend]
            self.current_backend = backend_class()

            # Set default config for vrchat_remote if not provided
            if backend == "vrchat_remote" and "remote_host" not in improved_config:
                improved_config["remote_host"] = "127.0.0.1"

            success = await self.current_backend.connect(improved_config)

            if success:
                self.backend_name = backend
                self.config = improved_config
                return {"success": True, "backend": backend, "message": f"Connected to {backend}"}
            return {"success": False, "error": f"Failed to connect to {backend}"}

        except Exception as e:
            self.logger.error("Error setting backend: %s", e)
            return {"success": False, "error": str(e)}

    async def send_animation(
        self,
        emotion: Optional[str] = None,
        emotion_intensity: float = 1.0,
        gesture: Optional[str] = None,
        gesture_intensity: float = 1.0,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Send animation data to the current backend."""
        if not self.current_backend:
            return {"success": False, "error": "No backend connected. Use set_backend first."}

        try:
            animation = CanonicalAnimationData(timestamp=asyncio.get_running_loop().time())

            if emotion:
                animation.emotion = EmotionType[emotion.upper()]
                animation.emotion_intensity = emotion_intensity

            if gesture:
                animation.gesture = GestureType[gesture.upper()]
                animation.gesture_intensity = gesture_intensity

            if parameters:
                animation.parameters = parameters

            success = await self.current_backend.send_animation_data(animation)
            return {"success": success}

        except KeyError as e:
            return {"success": False, "error": f"Invalid value: {e}"}
        except Exception as e:
            self.logger.error("Error sending animation: %s", e)
            return {"success": False, "error": str(e)}

    async def reset(self) -> Dict[str, Any]:
        """Reset all states - clear emotes and stop movement."""
        if not self.current_backend:
            return {"success": False, "error": "No backend connected. Use set_backend first."}

        try:
            if hasattr(self.current_backend, "reset_all"):
                success = await self.current_backend.reset_all()
                return {"success": success, "message": "All states reset"}
            return {"success": False, "error": "Backend does not support reset"}
        except Exception as e:
            self.logger.error("Error resetting: %s", e)
            return {"success": False, "error": str(e)}

    async def execute_behavior(self, behavior: str, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute a high-level behavior."""
        if not self.current_backend:
            return {"success": False, "error": "No backend connected. Use set_backend first."}

        if parameters is None:
            parameters = {}

        try:
            success = await self.current_backend.execute_behavior(behavior, parameters)
            return {"success": success}

        except Exception as e:
            self.logger.error("Error executing behavior: %s", e)
            return {"success": False, "error": str(e)}

    async def get_backend_status(self) -> Dict[str, Any]:
        """Get backend status."""
        if not self.current_backend:
            return {"success": True, "backend": None, "connected": False, "message": "No backend connected"}

        try:
            health = await self.current_backend.health_check()
            stats = await self.current_backend.get_statistics()

            return {
                "success": True,
                "backend": self.backend_name,
                "connected": self.current_backend.connected,
                "health": health,
                "statistics": stats,
            }

        except Exception as e:
            self.logger.error("Error getting backend status: %s", e)
            return {"success": False, "error": str(e)}

    async def send_vrcemote(self, emote_value: int) -> Dict[str, Any]:
        """Send a direct VRCEmote value (0-8) to VRChat backend."""
        if not self.current_backend:
            return {"success": False, "error": "No backend connected. Use set_backend first."}

        if self.backend_name != "vrchat_remote":
            return {"success": False, "error": "VRCEmote is only supported on vrchat_remote backend"}

        if not VRCEmoteValue.NONE <= emote_value <= VRCEmoteValue.DIE:
            return {"success": False, "error": f"VRCEmote value must be between {VRCEmoteValue.NONE} and {VRCEmoteValue.DIE}"}

        try:
            animation = CanonicalAnimationData(timestamp=asyncio.get_running_loop().time())
            animation.parameters = {"avatar_params": {"VRCEmote": emote_value}}

            success = await self.current_backend.send_animation_data(animation)
            gesture_name = get_vrcemote_name(emote_value)

            return {
                "success": success,
                "emote_value": emote_value,
                "gesture": gesture_name,
                "message": f"Sent VRCEmote {emote_value} ({gesture_name})",
            }
        except RuntimeError as e:
            self.logger.error("Event loop error sending VRCEmote: %s", e)
            return {"success": False, "error": f"Runtime error: {e}"}
        except OSError as e:
            self.logger.error("I/O error sending VRCEmote: %s", e)
            return {"success": False, "error": f"I/O error: {e}"}

    async def list_backends(self) -> Dict[str, Any]:
        """List available backends."""
        try:
            backends = []
            for name, backend_class in self.backends.items():
                backend_info = {"name": name, "class": backend_class.__name__, "active": name == self.backend_name}
                backends.append(backend_info)

            return {"success": True, "backends": backends}

        except Exception as e:
            self.logger.error("Error listing backends: %s", e)
            return {"success": False, "error": str(e)}

    async def play_audio(
        self,
        audio_data: str,
        audio_format: str = "mp3",
        text: Optional[str] = None,
        expression_tags: Optional[List[str]] = None,
        duration: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Play audio through the virtual character."""
        if not self.current_backend:
            return {"success": False, "error": "No backend connected. Use set_backend first."}

        try:
            # Process audio input
            audio_bytes, error = await self.audio_handler.process_audio_input(audio_data, audio_format)
            if error:
                return {"success": False, "error": error}

            # Create AudioData object
            audio = AudioData(
                data=audio_bytes, format=audio_format, duration=duration or 0.0, text=text, expression_tags=expression_tags
            )

            # Send to backend
            self.logger.info("Sending audio to backend (size: %d bytes)", len(audio_bytes))
            success = await self.current_backend.send_audio_data(audio)
            return {"success": success}

        except Exception as e:
            self.logger.error("Error sending audio: %s", e)
            return {"success": False, "error": str(e)}

    # Sequence management delegated to sequence_handler
    async def create_sequence(
        self,
        name: str,
        description: Optional[str] = None,
        loop: bool = False,
        interrupt_current: bool = True,
    ) -> Dict[str, Any]:
        """Create a new event sequence."""
        result = await self.sequence_handler.create_sequence(name, description, loop, interrupt_current)
        return cast(Dict[str, Any], result)

    async def add_sequence_event(
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
        parallel_events: Optional[List[Dict]] = None,
        sync_with_audio: bool = False,
    ) -> Dict[str, Any]:
        """Add an event to the current sequence."""
        result = await self.sequence_handler.add_event(
            event_type=event_type,
            timestamp=timestamp,
            duration=duration,
            animation_params=animation_params,
            audio_data=audio_data,
            audio_format=audio_format,
            wait_duration=wait_duration,
            expression=expression,
            expression_intensity=expression_intensity,
            movement_params=movement_params,
            parallel_events=parallel_events,
            sync_with_audio=sync_with_audio,
        )
        return cast(Dict[str, Any], result)

    async def play_sequence(
        self,
        sequence_name: Optional[str] = None,
        start_time: float = 0.0,
    ) -> Dict[str, Any]:
        """Play an event sequence."""
        result = await self.sequence_handler.play_sequence(self.current_backend, sequence_name, start_time)
        return cast(Dict[str, Any], result)

    async def pause_sequence(self) -> Dict[str, Any]:
        """Pause the currently playing sequence."""
        result = await self.sequence_handler.pause_sequence()
        return cast(Dict[str, Any], result)

    async def resume_sequence(self) -> Dict[str, Any]:
        """Resume the paused sequence."""
        result = await self.sequence_handler.resume_sequence()
        return cast(Dict[str, Any], result)

    async def stop_sequence(self) -> Dict[str, Any]:
        """Stop the currently playing sequence."""
        result = await self.sequence_handler.stop_sequence()
        return cast(Dict[str, Any], result)

    async def get_sequence_status(self) -> Dict[str, Any]:
        """Get status of current sequence playback."""
        result = await self.sequence_handler.get_status()
        return cast(Dict[str, Any], result)

    async def panic_reset(self) -> Dict[str, Any]:
        """Emergency reset - stops all sequences and resets avatar."""
        panic_result = await self.sequence_handler.panic_reset(self.current_backend)

        # If using VRChat backend, reconnect
        if self.backend_name == "vrchat_remote" and self.current_backend:
            try:
                await self.current_backend.disconnect()
                await asyncio.sleep(0.5)
                await self.current_backend.connect(self.config or {})
            except Exception as e:
                self.logger.error("Error reconnecting after panic reset: %s", e)

        return cast(Dict[str, Any], panic_result)

    async def startup_auto_connect(self):
        """Auto-connect to default backend on server startup."""
        await asyncio.sleep(2)

        if not self.auto_connect:
            logger.info("Auto-connect disabled. Use set_backend() to connect manually.")
            return

        try:
            logger.info("Auto-connecting to %s backend...", self.default_backend)
            logger.info(
                "Configuration: VRChat at %s:%s", self.default_config["remote_host"], self.default_config["osc_in_port"]
            )

            result = await self.set_backend(self.default_backend, self.default_config)

            if result["success"]:
                logger.info("[OK] Successfully auto-connected to %s", self.default_backend)

                test_result = await self.validate_connection()
                if test_result:
                    logger.info("[OK] Connection validated - OSC messages reaching VRChat")
                else:
                    logger.warning("[WARN] Connection established but validation failed")
                    logger.info("Check that VRChat OSC is enabled and avatar supports VRCEmote")
            else:
                logger.warning("Failed to auto-connect: %s", result.get("error", "Unknown error"))
                logger.info("You can manually connect using set_backend()")

        except Exception as e:
            logger.error("Error during auto-connect: %s", e)
            logger.info("You can manually connect using set_backend()")

    async def validate_connection(self) -> bool:
        """Validate that OSC messages actually reach VRChat."""
        if not self.current_backend:
            return False

        try:
            test_animation = CanonicalAnimationData(
                timestamp=0,
                emotion=EmotionType.NEUTRAL,
                gesture=GestureType.NONE,
            )

            success = await self.current_backend.send_animation_data(test_animation)

            if success:
                stats = await self.current_backend.get_statistics()
                return bool(stats.get("osc_messages_sent", 0) > 0)

            return False

        except Exception as e:
            logger.error("Connection validation failed: %s", e)
            return False

    async def monitor_connection(self):
        """Background task to monitor and auto-reconnect if needed."""
        while True:
            await asyncio.sleep(30)

            if self.current_backend and self.auto_connect:
                try:
                    health = await self.current_backend.health_check()
                    if not health.get("connected", False):
                        logger.warning("Connection lost, attempting reconnect...")
                        await self.auto_reconnect()
                except Exception as e:
                    logger.error("Health check failed: %s", e)
                    await self.auto_reconnect()

    async def auto_reconnect(self):
        """Attempt to reconnect to the backend."""
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            logger.error("Max reconnection attempts reached. Manual intervention required.")
            return

        self.reconnect_attempts += 1
        logger.info("Reconnection attempt %d/%d", self.reconnect_attempts, self.max_reconnect_attempts)

        if self.backend_name and self.config:
            result = await self.set_backend(self.backend_name, self.config)
            if result["success"]:
                logger.info("[OK] Successfully reconnected")
                self.reconnect_attempts = 0
            else:
                logger.error("Reconnection failed: %s", result.get("error"))

    def _get_improved_port_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Convert clearer port names to internal format."""
        improved_config = config.copy()

        if "vrchat_recv_port" in config:
            improved_config["osc_in_port"] = config["vrchat_recv_port"]
        if "vrchat_send_port" in config:
            improved_config["osc_out_port"] = config["vrchat_send_port"]

        if "osc_in_port" not in improved_config and "vrchat_recv_port" not in config:
            improved_config["osc_in_port"] = 9000
        if "osc_out_port" not in improved_config and "vrchat_send_port" not in config:
            improved_config["osc_out_port"] = 9001

        return improved_config


def main():
    """Main entry point for Virtual Character MCP server."""

    parser = argparse.ArgumentParser(description="Virtual Character MCP Server")
    parser.add_argument("--port", type=int, default=8020, help="Port to run server on")
    parser.add_argument("--mode", choices=["stdio", "http"], default="http", help="Server mode")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to (HTTP mode only)")

    args = parser.parse_args()

    if args.mode == "stdio":
        logger.info("Starting Virtual Character MCP server in STDIO mode...")
        logger.error("STDIO mode not yet implemented for Virtual Character server")
        sys.exit(1)
    else:
        logger.info("Starting Virtual Character MCP server on http://%s:%s", args.host, args.port)
        server = VirtualCharacterMCPServer(port=args.port)

        async def run_server():
            """Run server with auto-connect and monitoring"""
            asyncio.create_task(server.startup_auto_connect())
            asyncio.create_task(server.monitor_connection())

            logger.info("Virtual Character MCP Server initialized with auto-connect")
            logger.info("Default configuration:")
            logger.info("  - Backend: vrchat_remote")
            logger.info("  - VRChat Host: 127.0.0.1")
            logger.info("  - VRChat Receive Port: 9000")
            logger.info("  - VRChat Send Port: 9001")
            logger.info("  - VRCEmote System: Enabled")

            import uvicorn

            config = uvicorn.Config(app=server.app, host=args.host, port=args.port)
            server_instance = uvicorn.Server(config)
            await server_instance.serve()

        try:
            asyncio.run(run_server())
        except ImportError:
            logger.error("uvicorn not installed. Install with: pip install uvicorn")
            sys.exit(1)


if __name__ == "__main__":
    main()
