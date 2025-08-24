"""
Virtual Character MCP Server.

This server provides a middleware layer for controlling virtual characters
across multiple backend platforms (VRChat, Blender, Unity, etc.).
"""

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

from tools.mcp.core.base_server import BaseMCPServer

from ..models.canonical import (
    AudioData,
    CanonicalAnimationData,
    EmotionType,
    GestureType,
)
from .plugin_manager import PluginManager

logger = logging.getLogger(__name__)


class VirtualCharacterMCPServer(BaseMCPServer):
    """
    MCP server for virtual character control.

    Provides a unified interface for controlling virtual characters
    across different backend systems through a plugin architecture.
    """

    def __init__(self, port: int = 8020):
        """
        Initialize the Virtual Character MCP Server.

        Args:
            port: Port to run the server on
        """
        super().__init__(name="Virtual Character MCP Server", version="1.0.0", port=port)

        # Initialize plugin manager
        plugin_directory = os.getenv("VIRTUAL_CHARACTER_PLUGIN_DIR")
        self.plugin_manager = PluginManager(plugin_directory)

        # Configuration
        self.config = self._load_config()

        # State tracking
        self.current_backend: Optional[str] = None
        self.animation_queue: asyncio.Queue = asyncio.Queue()
        self.processing_task: Optional[asyncio.Task] = None

        # Statistics
        self.stats = {"animations_sent": 0, "audio_sent": 0, "frames_captured": 0, "backend_switches": 0, "errors": 0}

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file or environment."""
        config = {
            "default_backend": os.getenv("DEFAULT_BACKEND", "mock"),
            "enable_video_capture": os.getenv("ENABLE_VIDEO_CAPTURE", "true").lower() == "true",
            "enable_multi_agent": os.getenv("ENABLE_MULTI_AGENT", "false").lower() == "true",
            "video_capture_fps": int(os.getenv("VIDEO_CAPTURE_FPS", "10")),
        }

        # Try to load from config file
        config_path = Path(__file__).parent.parent / "config" / "server_config.json"
        if config_path.exists():
            try:
                with open(config_path) as f:
                    file_config = json.load(f)
                    config.update(file_config)
            except Exception as e:
                logger.error(f"Failed to load config file: {e}")

        return config

    def get_tools(self) -> Dict[str, Dict[str, Any]]:
        """
        Get available MCP tools.

        Returns:
            Dictionary of tool definitions
        """
        return {
            "set_backend": {
                "description": "Switch to a different backend system",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "backend": {"type": "string", "description": "Backend name (vrchat_remote, blender, unity, mock)"},
                        "config": {"type": "object", "description": "Backend-specific configuration"},
                    },
                    "required": ["backend"],
                },
            },
            "send_animation": {
                "description": "Send animation data to current backend",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "emotion": {"type": "string", "enum": ["neutral", "happy", "sad", "angry", "surprised", "fearful"]},
                        "gesture": {"type": "string", "enum": ["none", "wave", "point", "thumbs_up", "nod", "shake_head"]},
                        "blend_shapes": {"type": "object", "description": "Facial blend shape values (0-1)"},
                        "parameters": {"type": "object", "description": "Backend-specific parameters"},
                    },
                },
            },
            "send_audio": {
                "description": "Send audio data with optional text",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "audio_data": {"type": "string", "description": "Base64 encoded audio data"},
                        "text": {"type": "string", "description": "Optional text transcript"},
                        "format": {"type": "string", "enum": ["pcm", "mp3", "opus", "wav"]},
                    },
                    "required": ["audio_data"],
                },
            },
            "capture_view": {
                "description": "Capture current view from agent perspective",
                "inputSchema": {
                    "type": "object",
                    "properties": {"format": {"type": "string", "enum": ["jpeg", "png", "raw"], "default": "jpeg"}},
                },
            },
            "receive_state": {
                "description": "Get current state from virtual environment",
                "inputSchema": {"type": "object", "properties": {}},
            },
            "execute_behavior": {
                "description": "Execute high-level behavior",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "behavior": {"type": "string", "description": "Behavior name (greet, dance, sit, etc.)"},
                        "parameters": {"type": "object", "description": "Behavior-specific parameters"},
                    },
                    "required": ["behavior"],
                },
            },
            "change_environment": {
                "description": "Change virtual environment/background",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "environment": {"type": "string", "description": "Environment name or path"},
                        "parameters": {"type": "object", "description": "Environment parameters"},
                    },
                    "required": ["environment"],
                },
            },
            "list_backends": {
                "description": "List available backend plugins",
                "inputSchema": {"type": "object", "properties": {}},
            },
            "get_backend_status": {
                "description": "Get status of current backend",
                "inputSchema": {"type": "object", "properties": {}},
            },
        }

    async def set_backend(self, backend: str, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Switch to a different backend."""
        try:
            # Use provided config or load from defaults
            if config is None:
                config = self._get_default_backend_config(backend)

            success = await self.plugin_manager.switch_backend(backend, config)

            if success:
                self.current_backend = backend
                self.stats["backend_switches"] += 1

                return {"success": True, "backend": backend, "message": f"Switched to {backend} backend"}
            else:
                return {"success": False, "error": f"Failed to switch to {backend}"}

        except Exception as e:
            logger.error(f"Error switching backend: {e}")
            self.stats["errors"] += 1
            return {"success": False, "error": str(e)}

    async def send_animation(self, **kwargs) -> Dict[str, Any]:
        """Send animation data to current backend."""
        backend = self.plugin_manager.get_active_backend()

        if not backend:
            return {"success": False, "error": "No active backend"}

        try:
            # Build canonical animation data
            animation = CanonicalAnimationData(timestamp=asyncio.get_event_loop().time())

            # Set emotion
            if "emotion" in kwargs:
                animation.emotion = EmotionType(kwargs["emotion"])
                animation.emotion_intensity = kwargs.get("emotion_intensity", 1.0)

            # Set gesture
            if "gesture" in kwargs:
                animation.gesture = GestureType(kwargs["gesture"])
                animation.gesture_intensity = kwargs.get("gesture_intensity", 1.0)

            # Set blend shapes
            if "blend_shapes" in kwargs:
                animation.blend_shapes = kwargs["blend_shapes"]

            # Set parameters
            if "parameters" in kwargs:
                animation.parameters = kwargs["parameters"]

            # Send to backend
            success = await backend.send_animation_data(animation)

            if success:
                self.stats["animations_sent"] += 1
                return {"success": True, "message": "Animation sent"}
            else:
                return {"success": False, "error": "Failed to send animation"}

        except Exception as e:
            logger.error(f"Error sending animation: {e}")
            self.stats["errors"] += 1
            return {"success": False, "error": str(e)}

    async def send_audio(self, audio_data: str, text: Optional[str] = None, format: str = "pcm") -> Dict[str, Any]:
        """Send audio data to current backend."""
        backend = self.plugin_manager.get_active_backend()

        if not backend:
            return {"success": False, "error": "No active backend"}

        try:
            # Decode base64 audio
            import base64

            audio_bytes = base64.b64decode(audio_data)

            # Create audio data object
            audio = AudioData(data=audio_bytes, format=format, text=text)

            # Send to backend
            success = await backend.send_audio_data(audio)

            if success:
                self.stats["audio_sent"] += 1
                return {"success": True, "message": "Audio sent"}
            else:
                return {"success": False, "error": "Failed to send audio"}

        except Exception as e:
            logger.error(f"Error sending audio: {e}")
            self.stats["errors"] += 1
            return {"success": False, "error": str(e)}

    async def capture_view(self, format: str = "jpeg") -> Dict[str, Any]:
        """Capture current view from agent perspective."""
        backend = self.plugin_manager.get_active_backend()

        if not backend:
            return {"success": False, "error": "No active backend"}

        try:
            frame = await backend.capture_video_frame()

            if frame:
                import base64

                self.stats["frames_captured"] += 1

                return {
                    "success": True,
                    "frame": {
                        "data": base64.b64encode(frame.data).decode("utf-8"),
                        "width": frame.width,
                        "height": frame.height,
                        "format": frame.format,
                        "timestamp": frame.timestamp,
                        "frame_number": frame.frame_number,
                    },
                }
            else:
                return {"success": False, "error": "No frame available"}

        except Exception as e:
            logger.error(f"Error capturing view: {e}")
            self.stats["errors"] += 1
            return {"success": False, "error": str(e)}

    async def receive_state(self) -> Dict[str, Any]:
        """Get current state from virtual environment."""
        backend = self.plugin_manager.get_active_backend()

        if not backend:
            return {"success": False, "error": "No active backend"}

        try:
            state = await backend.receive_state()

            if state:
                return {"success": True, "state": state.to_dict()}
            else:
                return {"success": False, "error": "No state available"}

        except Exception as e:
            logger.error(f"Error receiving state: {e}")
            self.stats["errors"] += 1
            return {"success": False, "error": str(e)}

    async def execute_behavior(self, behavior: str, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute high-level behavior."""
        backend = self.plugin_manager.get_active_backend()

        if not backend:
            return {"success": False, "error": "No active backend"}

        try:
            success = await backend.execute_behavior(behavior, parameters or {})

            if success:
                return {"success": True, "message": f"Behavior '{behavior}' executed"}
            else:
                return {"success": False, "error": f"Failed to execute behavior '{behavior}'"}

        except Exception as e:
            logger.error(f"Error executing behavior: {e}")
            self.stats["errors"] += 1
            return {"success": False, "error": str(e)}

    async def change_environment(self, environment: str, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Change virtual environment."""
        backend = self.plugin_manager.get_active_backend()

        if not backend:
            return {"success": False, "error": "No active backend"}

        try:
            success = await backend.set_environment(environment, **(parameters or {}))

            if success:
                return {"success": True, "message": f"Environment changed to '{environment}'"}
            else:
                return {"success": False, "error": f"Failed to change environment to '{environment}'"}

        except Exception as e:
            logger.error(f"Error changing environment: {e}")
            self.stats["errors"] += 1
            return {"success": False, "error": str(e)}

    async def list_backends(self) -> Dict[str, Any]:
        """List available backend plugins."""
        try:
            # Discover plugins
            await self.plugin_manager.discover_plugins()

            # Get detailed info
            plugin_info = self.plugin_manager.list_available_plugins()

            return {"success": True, "backends": plugin_info, "current": self.current_backend}

        except Exception as e:
            logger.error(f"Error listing backends: {e}")
            return {"success": False, "error": str(e)}

    async def get_backend_status(self) -> Dict[str, Any]:
        """Get status of current backend."""
        backend = self.plugin_manager.get_active_backend()

        if not backend:
            return {"success": False, "error": "No active backend"}

        try:
            health = await backend.health_check()
            stats = await backend.get_statistics()

            return {"success": True, "backend": self.current_backend, "health": health, "statistics": stats}

        except Exception as e:
            logger.error(f"Error getting backend status: {e}")
            return {"success": False, "error": str(e)}

    def _get_default_backend_config(self, backend: str) -> Dict[str, Any]:
        """Get default configuration for a backend."""
        configs = {
            "mock": {"world_name": "TestWorld", "simulate_events": True},
            "vrchat_remote": {
                "remote_host": os.getenv("VRCHAT_REMOTE_HOST", "192.168.0.150"),
                "bridge_port": 8021,
                "stream_port": 8022,
                "obs_port": 4455,
                "obs_password": os.getenv("OBS_PASSWORD"),
                "stream_token": os.getenv("STREAM_AUTH_TOKEN"),
                "avatar_config": "./config/avatars/default.yaml",
            },
            "blender": {"blender_path": "/usr/local/blender", "scene_file": "./scenes/default.blend"},
            "unity_websocket": {"websocket_url": "ws://localhost:8080", "api_key": os.getenv("UNITY_API_KEY")},
        }

        return configs.get(backend, {})  # type: ignore

    async def startup(self):
        """Startup tasks."""
        # Discover available plugins
        await self.plugin_manager.discover_plugins()

        # Load default backend if configured
        if self.config.get("default_backend"):
            try:
                await self.set_backend(
                    self.config["default_backend"], self._get_default_backend_config(self.config["default_backend"])
                )
                logger.info(f"Loaded default backend: {self.config['default_backend']}")
            except Exception as e:
                logger.error(f"Failed to load default backend: {e}")

    async def shutdown(self):
        """Shutdown tasks."""
        # Clean up plugin manager
        await self.plugin_manager.cleanup()

        # Cancel processing task if running
        if self.processing_task:
            self.processing_task.cancel()
            try:
                await self.processing_task
            except asyncio.CancelledError:
                pass

    def get_stats(self) -> Dict[str, Any]:
        """Get server statistics."""
        return {
            "server": self.name,
            "version": self.version,
            "current_backend": self.current_backend,
            "stats": self.stats,
            "config": self.config,
        }


def create_server(port: int = 8020) -> VirtualCharacterMCPServer:
    """
    Create and return a Virtual Character MCP Server instance.

    Args:
        port: Port to run the server on

    Returns:
        Server instance
    """
    return VirtualCharacterMCPServer(port=port)
