"""Virtual Character MCP Server for AI Agent Embodiment"""

import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from tools.mcp.core.base_server import BaseMCPServer  # noqa: E402

    HAS_MCP = True
except ImportError:
    # Minimal implementation for HTTP mode without full MCP library
    HAS_MCP = False
    import uuid
    from abc import ABC, abstractmethod

    from fastapi import FastAPI, Request, Response
    from fastapi.responses import JSONResponse, StreamingResponse

    class BaseMCPServer(ABC):  # type: ignore
        """Minimal MCP server implementation for HTTP mode"""

        def __init__(self, name: str, version: str = "1.0.0", port: int = 8000):
            self.name = name
            self.version = version
            self.port = port
            self.logger = logging.getLogger(name)
            self.app = FastAPI(title=name, version=version)
            self._setup_routes()

        def _setup_routes(self):
            """Setup MCP routes"""
            self.app.get("/health")(self.health_check)
            self.app.get("/messages")(self.handle_messages_get)
            self.app.post("/messages")(self.handle_messages)
            self.app.get("/mcp/tools")(self.list_tools_http)
            self.app.post("/mcp/execute")(self.execute_tool_http)

        async def health_check(self):
            return {"status": "healthy", "server": self.name, "version": self.version}

        async def handle_messages_get(self, request: Request):
            """Handle GET for SSE streaming"""
            session_id = request.headers.get("Mcp-Session-Id", str(uuid.uuid4()))

            async def event_generator():
                connection_data = {"type": "connection", "sessionId": session_id, "status": "connected"}
                yield f"data: {json.dumps(connection_data)}\n\n"

                while True:
                    await asyncio.sleep(15)
                    ping_data = {"type": "ping", "timestamp": datetime.utcnow().isoformat()}
                    yield f"data: {json.dumps(ping_data)}\n\n"

            return StreamingResponse(
                event_generator(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
            )

        async def handle_messages(self, request: Request):
            """Handle MCP messages"""
            session_id = request.headers.get("Mcp-Session-Id")

            try:
                body = await request.json()
                self.logger.info(f"Messages request: {json.dumps(body)}")

                response = await self._process_jsonrpc_request(body)

                if response:
                    return JSONResponse(content=response, headers={"Mcp-Session-Id": session_id or ""})
                else:
                    return Response(status_code=202, headers={"Mcp-Session-Id": session_id or ""})

            except Exception as e:
                self.logger.error(f"Error handling message: {e}")
                return JSONResponse(status_code=500, content={"error": str(e)})

        async def _process_jsonrpc_request(self, request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
            """Process JSON-RPC request"""
            jsonrpc = request.get("jsonrpc", "2.0")
            method = request.get("method")
            params = request.get("params", {})
            req_id = request.get("id")

            self.logger.info(f"Processing method: {method}")

            try:
                result = None

                if method == "initialize":
                    result = await self._jsonrpc_initialize(params)
                elif method == "tools/list":
                    result = await self._jsonrpc_list_tools(params)
                elif method == "tools/call":
                    result = await self._jsonrpc_call_tool(params)
                else:
                    self.logger.warning(f"Unknown method: {method}")
                    if req_id is not None:
                        return {
                            "jsonrpc": jsonrpc,
                            "error": {"code": -32601, "message": f"Method not found: {method}"},
                            "id": req_id,
                        }
                    return None

                if req_id is not None:
                    return {"jsonrpc": jsonrpc, "result": result, "id": req_id}
                return None

            except Exception as e:
                self.logger.error(f"Error processing method {method}: {e}")
                if req_id is not None:
                    return {
                        "jsonrpc": jsonrpc,
                        "error": {"code": -32603, "message": "Internal error", "data": str(e)},
                        "id": req_id,
                    }
                return None

        async def _jsonrpc_initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
            """Handle initialize request"""
            return {
                "protocolVersion": params.get("protocolVersion", "2024-11-05"),
                "serverInfo": {"name": self.name, "version": self.version},
                "capabilities": {"tools": {"listChanged": True}, "resources": {}, "prompts": {}},
            }

        async def _jsonrpc_list_tools(self, params: Dict[str, Any]) -> Dict[str, Any]:
            """Handle tools/list request"""
            tools = self.get_tools()
            tool_list = []

            for tool_name, tool_info in tools.items():
                tool_list.append(
                    {
                        "name": tool_name,
                        "description": tool_info.get("description", ""),
                        "inputSchema": tool_info.get("parameters", {}),
                    }
                )

            return {"tools": tool_list}

        async def _jsonrpc_call_tool(self, params: Dict[str, Any]) -> Dict[str, Any]:
            """Handle tools/call request"""
            tool_name = params.get("name")
            arguments = params.get("arguments", {})

            if not tool_name:
                raise ValueError("Tool name is required")

            tools = self.get_tools()
            if tool_name not in tools:
                raise ValueError(f"Tool '{tool_name}' not found")

            # Get the tool method
            tool_func = getattr(self, tool_name, None)
            if not tool_func:
                raise ValueError(f"Tool '{tool_name}' not implemented")

            try:
                result = await tool_func(**arguments)

                if isinstance(result, dict):
                    content_text = json.dumps(result, indent=2)
                else:
                    content_text = str(result)

                return {"content": [{"type": "text", "text": content_text}]}
            except Exception as e:
                self.logger.error(f"Error calling tool {tool_name}: {e}")
                return {"content": [{"type": "text", "text": f"Error: {str(e)}"}], "isError": True}

        async def list_tools_http(self):
            """List tools via HTTP endpoint"""
            tools = self.get_tools()
            return {"tools": list(tools.keys()), "count": len(tools)}

        async def execute_tool_http(self, request: Dict[str, Any]):
            """Execute tool via HTTP endpoint"""
            tool_name = request.get("tool")
            arguments = request.get("arguments", {})

            try:
                result = await self._jsonrpc_call_tool({"name": tool_name, "arguments": arguments})
                return {"success": True, "result": result}
            except Exception as e:
                return {"success": False, "error": str(e)}

        @abstractmethod
        def get_tools(self) -> Dict[str, Dict[str, Any]]:
            """Get available tools - must be implemented by subclass"""
            pass


from tools.mcp.virtual_character.backends.base import BackendAdapter  # noqa: E402
from tools.mcp.virtual_character.backends.mock import MockBackend  # noqa: E402
from tools.mcp.virtual_character.backends.vrchat_remote import VRChatRemoteBackend  # noqa: E402
from tools.mcp.virtual_character.models.canonical import (  # noqa: E402
    AudioData,
    CanonicalAnimationData,
    EmotionType,
    EventSequence,
    EventType,
    GestureType,
    SequenceEvent,
)

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class VirtualCharacterMCPServer(BaseMCPServer):
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
            "remote_host": "127.0.0.1",  # VRChat on same machine
            "osc_in_port": 9000,  # Port where VRChat receives (clearer: vrchat_recv_port)
            "osc_out_port": 9001,  # Port where VRChat sends (clearer: vrchat_send_port)
            "use_vrcemote": True,  # Most avatars use VRCEmote system
        }
        self.auto_connect = auto_connect
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 3

        # Event sequencing
        self.current_sequence: Optional[EventSequence] = None
        self.sequence_task: Optional[asyncio.Task] = None
        self.sequence_paused: bool = False
        self.sequence_time: float = 0.0

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
        async def play_audio(request: Dict[str, Any]) -> Dict[str, Any]:
            """
            Audio bridge endpoint - plays audio through virtual audio cable.

            Requirements:
            1. Install VB-Audio Virtual Cable or similar
            2. Set virtual cable as default playback device or specify device
            3. Set VRChat microphone input to virtual cable output

            The audio will be routed: App -> Virtual Cable Input -> Virtual Cable Output -> VRChat Mic
            """
            try:
                import base64
                import os
                import subprocess
                import tempfile

                audio_data = request.get("audio_data")
                format = request.get("format", "mp3")
                device_name = request.get("device", None)  # Optional: specific audio device

                if not audio_data:
                    return {"success": False, "error": "No audio data provided"}

                # Decode base64 audio
                if audio_data.startswith("data:"):
                    audio_data = audio_data.split(",")[1]
                audio_bytes = base64.b64decode(audio_data)

                # Save to temp file
                with tempfile.NamedTemporaryFile(suffix=f".{format}", delete=False) as tmp_file:
                    tmp_file.write(audio_bytes)
                    tmp_path = tmp_file.name

                # Play audio through virtual audio cable (Windows)
                if os.name == "nt":  # Windows
                    # Build ffplay command with audio device selection
                    cmd = ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet"]

                    # If specific device requested, route to it (e.g., "CABLE Input" for VB-Audio)
                    if device_name:
                        # For Windows, use -audio_device with the device name
                        cmd.extend(["-f", "lavfi", "-i", f"amovie={tmp_path},aformat=sample_fmts=s16:channel_layouts=stereo"])
                        cmd.extend(["-audio_device", device_name])
                    else:
                        cmd.append(tmp_path)

                    try:
                        # Try ffplay with virtual cable routing
                        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        self.logger.info(f"Playing audio through: {device_name or 'default device'}")
                    except FileNotFoundError:
                        # Fallback: Try using PowerShell with .NET to specify device
                        ps_script = f"""
                        Add-Type -AssemblyName System.Speech
                        $synthesizer = New-Object System.Speech.Synthesis.SpeechSynthesizer
                        # Play the audio file through default audio device
                        # Note: For virtual cable, set it as Windows default playback device
                        $player = New-Object System.Media.SoundPlayer '{tmp_path}'
                        $player.Play()
                        """
                        subprocess.Popen(
                            ["powershell", "-Command", ps_script], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                        )
                else:  # Linux/Mac
                    subprocess.Popen(
                        ["ffplay", "-nodisp", "-autoexit", tmp_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                    )

                self.logger.info(f"Playing audio file: {tmp_path}")
                return {"success": True, "message": "Audio playback started", "file": tmp_path}

            except Exception as e:
                self.logger.error(f"Error playing audio: {e}")
                return {"success": False, "error": str(e)}

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
                                    "description": (
                                        "DEPRECATED: Use vrchat_recv_port instead. " "OSC input port (where VRChat receives)"
                                    ),
                                },
                                "osc_out_port": {
                                    "type": "integer",
                                    "default": 9001,
                                    "description": (
                                        "DEPRECATED: Use vrchat_send_port instead. " "OSC output port (where VRChat sends)"
                                    ),
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
                "parameters": {
                    "type": "object",
                    "properties": {},
                },
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
                            "description": "Base64-encoded audio data or URL to audio file",
                        },
                        "format": {
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
                    "NOTE: This operates on a single, shared sequence builder. "
                    "Concurrent calls will interfere with each other."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Sequence name",
                        },
                        "description": {
                            "type": "string",
                            "description": "Optional description",
                        },
                        "loop": {
                            "type": "boolean",
                            "default": False,
                            "description": "Whether to loop the sequence",
                        },
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
                        "timestamp": {
                            "type": "number",
                            "description": "When to trigger (seconds from sequence start)",
                        },
                        "duration": {
                            "type": "number",
                            "description": "Event duration in seconds",
                        },
                        "animation_params": {
                            "type": "object",
                            "description": "Animation parameters (emotion, gesture, etc.)",
                        },
                        "audio_data": {
                            "type": "string",
                            "description": "Base64 audio data for audio events",
                        },
                        "audio_format": {
                            "type": "string",
                            "enum": ["mp3", "wav", "opus"],
                            "default": "mp3",
                        },
                        "wait_duration": {
                            "type": "number",
                            "description": "Duration for wait events",
                        },
                        "expression": {
                            "type": "string",
                            "enum": ["neutral", "happy", "sad", "angry", "surprised", "fearful", "disgusted"],
                        },
                        "expression_intensity": {
                            "type": "number",
                            "minimum": 0,
                            "maximum": 1,
                            "default": 1.0,
                        },
                        "movement_params": {
                            "type": "object",
                            "description": "Movement parameters",
                        },
                        "parallel_events": {
                            "type": "array",
                            "description": "Events to run in parallel",
                        },
                        "sync_with_audio": {
                            "type": "boolean",
                            "default": False,
                            "description": "Sync animation timing with audio duration",
                        },
                    },
                    "required": ["event_type", "timestamp"],
                },
            },
            "play_sequence": {
                "description": "Play the current or specified event sequence",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "sequence_name": {
                            "type": "string",
                            "description": "Name of sequence to play (uses current if not specified)",
                        },
                        "start_time": {
                            "type": "number",
                            "default": 0,
                            "description": "Start time within sequence",
                        },
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
                "description": (
                    "Emergency reset - stops all sequences and resets avatar to neutral state. "
                    "Useful for recovering from misbehaving animations or stuck states."
                ),
                "parameters": {"type": "object", "properties": {}},
            },
            "send_vrcemote": {
                "description": "Send a direct VRCEmote value (0-8) to VRChat backend for precise gesture control",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "emote_value": {
                            "type": "integer",
                            "minimum": 0,
                            "maximum": 8,
                            "description": (
                                "VRCEmote value: 0=clear, 1=wave, 2=clap, 3=point, "
                                "4=cheer, 5=dance, 6=backflip, 7=sadness, 8=die"
                            ),
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
                improved_config["remote_host"] = "127.0.0.1"  # Local VRChat on Windows machine

            success = await self.current_backend.connect(improved_config)

            if success:
                self.backend_name = backend
                self.config = improved_config  # Store config for reconnection
                return {"success": True, "backend": backend, "message": f"Connected to {backend}"}
            else:
                return {"success": False, "error": f"Failed to connect to {backend}"}

        except Exception as e:
            self.logger.error(f"Error setting backend: {e}")
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
            # Create animation data
            animation = CanonicalAnimationData(timestamp=asyncio.get_event_loop().time())

            # Set emotion if provided
            if emotion:
                animation.emotion = EmotionType[emotion.upper()]
                animation.emotion_intensity = emotion_intensity

            # Set gesture if provided
            if gesture:
                animation.gesture = GestureType[gesture.upper()]
                animation.gesture_intensity = gesture_intensity

            # Set parameters if provided
            if parameters:
                animation.parameters = parameters

            # Send to backend
            success = await self.current_backend.send_animation_data(animation)

            return {"success": success}

        except KeyError as e:
            return {"success": False, "error": f"Invalid value: {e}"}
        except Exception as e:
            self.logger.error(f"Error sending animation: {e}")
            return {"success": False, "error": str(e)}

    async def reset(self) -> Dict[str, Any]:
        """Reset all states - clear emotes and stop movement."""
        if not self.current_backend:
            return {"success": False, "error": "No backend connected. Use set_backend first."}

        try:
            # Call reset on the backend
            if hasattr(self.current_backend, "reset_all"):
                success = await self.current_backend.reset_all()
                return {"success": success, "message": "All states reset"}
            else:
                return {"success": False, "error": "Backend does not support reset"}
        except Exception as e:
            self.logger.error(f"Error resetting: {e}")
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
            self.logger.error(f"Error executing behavior: {e}")
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
            self.logger.error(f"Error getting backend status: {e}")
            return {"success": False, "error": str(e)}

    async def send_vrcemote(self, emote_value: int) -> Dict[str, Any]:
        """Send a direct VRCEmote value (0-8) to VRChat backend."""
        if not self.current_backend:
            return {"success": False, "error": "No backend connected. Use set_backend first."}

        if self.backend_name != "vrchat_remote":
            return {"success": False, "error": "VRCEmote is only supported on vrchat_remote backend"}

        if not 0 <= emote_value <= 8:
            return {"success": False, "error": "VRCEmote value must be between 0 and 8"}

        try:
            # Send directly through avatar parameters
            animation = CanonicalAnimationData(timestamp=asyncio.get_event_loop().time())
            animation.parameters = {"avatar_params": {"VRCEmote": emote_value}}

            success = await self.current_backend.send_animation_data(animation)

            # Map emote value to gesture name for feedback
            emote_names = {
                0: "none/clear",
                1: "wave",
                2: "clap",
                3: "point",
                4: "cheer",
                5: "dance",
                6: "backflip",
                7: "sadness",
                8: "die",
            }

            return {
                "success": success,
                "emote_value": emote_value,
                "gesture": emote_names.get(emote_value, "unknown"),
                "message": f"Sent VRCEmote {emote_value} ({emote_names.get(emote_value, 'unknown')})",
            }
        except Exception as e:
            self.logger.error(f"Error sending VRCEmote: {e}")
            return {"success": False, "error": str(e)}

    async def list_backends(self) -> Dict[str, Any]:
        """List available backends."""
        try:
            backends = []
            for name, backend_class in self.backends.items():
                backend_info = {"name": name, "class": backend_class.__name__, "active": name == self.backend_name}
                backends.append(backend_info)

            return {"success": True, "backends": backends}

        except Exception as e:
            self.logger.error(f"Error listing backends: {e}")
            return {"success": False, "error": str(e)}

    async def play_audio(
        self,
        audio_data: str,
        format: str = "mp3",
        text: Optional[str] = None,
        expression_tags: Optional[List[str]] = None,
        duration: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Play audio through the virtual character (text-to-speech output).

        Args:
            audio_data: Can be:
                - Base64-encoded audio data
                - Data URL (data:audio/mp3;base64,...)
                - HTTP/HTTPS URL to download audio from
                - File path (starts with / or ./)
            format: Audio format (mp3, wav, opus, pcm)
            text: Optional text transcript for lip-sync
            expression_tags: Optional expression tags from ElevenLabs
            duration: Optional audio duration in seconds
        """
        if not self.current_backend:
            return {"success": False, "error": "No backend connected. Use set_backend first."}

        try:
            import base64
            from pathlib import Path

            import aiohttp

            audio_bytes = None

            # Determine input type and get audio bytes
            if audio_data.startswith("data:"):
                # Data URL format
                self.logger.info("Processing data URL audio")
                audio_data = audio_data.split(",")[1]
                audio_bytes = base64.b64decode(audio_data)

            elif audio_data.startswith(("http://", "https://")):
                # URL - download the audio
                self.logger.info(f"Downloading audio from URL: {audio_data}")
                async with aiohttp.ClientSession() as session:
                    async with session.get(audio_data) as response:
                        if response.status == 200:
                            audio_bytes = await response.read()
                        else:
                            return {"success": False, "error": f"Failed to download audio: HTTP {response.status}"}

            elif audio_data.startswith("/") or audio_data.startswith("./"):
                # File path - read the file
                self.logger.info(f"Reading audio from file: {audio_data}")
                file_path = Path(audio_data)
                if file_path.exists():
                    with open(file_path, "rb") as f:
                        audio_bytes = f.read()
                else:
                    return {"success": False, "error": f"File not found: {audio_data}"}

            else:
                # Assume base64-encoded data
                self.logger.info("Processing base64-encoded audio")
                try:
                    audio_bytes = base64.b64decode(audio_data)
                except Exception as e:
                    return {"success": False, "error": f"Invalid base64 data: {str(e)}"}

            if not audio_bytes:
                return {"success": False, "error": "No audio data could be extracted"}

            # Create AudioData object
            audio = AudioData(
                data=audio_bytes, format=format, duration=duration or 0.0, text=text, expression_tags=expression_tags
            )

            # Send to backend
            success = await self.current_backend.send_audio_data(audio)
            return {"success": success}

        except Exception as e:
            self.logger.error(f"Error sending audio: {e}")
            return {"success": False, "error": str(e)}

    async def create_sequence(
        self,
        name: str,
        description: Optional[str] = None,
        loop: bool = False,
        interrupt_current: bool = True,
    ) -> Dict[str, Any]:
        """
        Create a new event sequence.

        IMPORTANT: This method uses a single, shared sequence builder
        (self.current_sequence). Concurrent calls will interfere with
        each other. Only one sequence can be built at a time.
        """
        try:
            # Stop current sequence if needed
            if interrupt_current and self.sequence_task:
                await self.stop_sequence()

            # Create new sequence
            self.current_sequence = EventSequence(
                name=name,
                description=description,
                loop=loop,
                interrupt_current=interrupt_current,
                created_timestamp=asyncio.get_event_loop().time(),
            )

            return {"success": True, "message": f"Created sequence: {name}"}

        except Exception as e:
            self.logger.error(f"Error creating sequence: {e}")
            return {"success": False, "error": str(e)}

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
        if not self.current_sequence:
            return {"success": False, "error": "No sequence created. Use create_sequence first."}

        try:
            # Convert arguments to dictionary format for unified parsing
            event_dict = {
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

            # Use centralized event creation logic
            event = await self._create_event_from_dict(event_dict)
            if not event:
                return {"success": False, "error": "Failed to create event from parameters"}

            # Add event to sequence
            self.current_sequence.add_event(event)

            return {"success": True, "message": f"Added {event_type} event at {timestamp}s"}

        except Exception as e:
            self.logger.error(f"Error adding event: {e}")
            return {"success": False, "error": str(e)}

    async def play_sequence(
        self,
        sequence_name: Optional[str] = None,
        start_time: float = 0.0,
    ) -> Dict[str, Any]:
        """Play an event sequence."""
        if not self.current_backend:
            return {"success": False, "error": "No backend connected. Use set_backend first."}

        if not self.current_sequence:
            return {"success": False, "error": "No sequence to play. Create and build a sequence first."}

        try:
            # Cancel any existing sequence
            if self.sequence_task and not self.sequence_task.done():
                self.sequence_task.cancel()
                await asyncio.sleep(0.1)

            # Start sequence playback
            self.sequence_time = start_time
            self.sequence_paused = False
            self.sequence_task = asyncio.create_task(self._execute_sequence())

            return {"success": True, "message": f"Started playing sequence: {self.current_sequence.name}"}

        except Exception as e:
            self.logger.error(f"Error playing sequence: {e}")
            return {"success": False, "error": str(e)}

    async def _execute_sequence(self) -> None:
        """Execute the current sequence with efficient event scheduling."""
        if not self.current_sequence or not self.current_backend:
            return

        try:
            # Reset avatar state before starting sequence
            await self._reset_avatar_state()

            # Sort events by timestamp for efficient execution
            sorted_events = sorted(self.current_sequence.events, key=lambda e: e.timestamp)

            start_time = asyncio.get_event_loop().time()

            # Execute events at their scheduled times
            for event in sorted_events:
                if self.sequence_paused:
                    # Handle pause
                    pause_start = asyncio.get_event_loop().time()
                    while self.sequence_paused:
                        await asyncio.sleep(0.1)
                    # Adjust start time for pause duration
                    pause_duration = asyncio.get_event_loop().time() - pause_start
                    start_time += pause_duration

                # Calculate time to wait until this event
                current_time = asyncio.get_event_loop().time() - start_time
                time_to_wait = event.timestamp - current_time

                if time_to_wait > 0:
                    await asyncio.sleep(time_to_wait)

                # Execute the event with error handling
                try:
                    await self._execute_event(event)
                except Exception as e:
                    self.logger.error(f"Error executing event at {event.timestamp}s: {e}")
                    # Continue with next event instead of stopping sequence

            # Wait for any remaining duration
            if self.current_sequence.total_duration:
                final_wait = self.current_sequence.total_duration - (asyncio.get_event_loop().time() - start_time)
                if final_wait > 0:
                    await asyncio.sleep(final_wait)

            # Handle looping
            if self.current_sequence.loop:
                self.sequence_time = 0
                # Recursively execute sequence again
                await self._execute_sequence()

        finally:
            # Always reset avatar state after sequence completes or errors
            await self._reset_avatar_state()
            self.current_sequence = None

    async def _reset_avatar_state(self) -> None:
        """Reset avatar to neutral state."""
        if not self.current_backend:
            return

        try:
            # Reset to neutral state
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
            await self.current_backend.send_animation_data(neutral_animation)

            # Give VRChat time to process the reset
            await asyncio.sleep(0.1)

        except Exception as e:
            self.logger.error(f"Error resetting avatar state: {e}")

    async def panic_reset(self) -> Dict[str, Any]:
        """Emergency reset - stops all sequences and resets avatar."""
        try:
            # Stop any running sequence
            if self.sequence_task and not self.sequence_task.done():
                self.sequence_task.cancel()
                await asyncio.sleep(0.1)

            # Clear sequence state
            self.current_sequence = None
            self.sequence_paused = False
            self.sequence_time = 0

            # Reset avatar
            await self._reset_avatar_state()

            # If using VRChat backend, recreate OSC connection
            if self.backend_name == "vrchat_remote" and self.current_backend:
                # Disconnect and reconnect to clear any stuck state
                await self.current_backend.disconnect()
                await asyncio.sleep(0.5)
                await self.current_backend.connect(self.config or {})

            return {"success": True, "message": "Emergency reset completed"}

        except Exception as e:
            self.logger.error(f"Error during panic reset: {e}")
            return {"success": False, "error": str(e)}

    async def _execute_event(self, event: SequenceEvent) -> None:
        """Execute a single event with error handling."""
        try:
            if event.event_type == EventType.ANIMATION and event.animation_data:
                if self.current_backend:
                    await self.current_backend.send_animation_data(event.animation_data)

            elif event.event_type == EventType.AUDIO and event.audio_data:
                if self.current_backend:
                    await self.current_backend.send_audio_data(event.audio_data)

            elif event.event_type == EventType.WAIT:
                # Wait is handled by the sequence executor timing
                pass

            elif event.event_type == EventType.EXPRESSION:
                # Create animation with just expression
                animation = CanonicalAnimationData(
                    timestamp=event.timestamp, emotion=event.expression, emotion_intensity=event.expression_intensity or 1.0
                )
                if self.current_backend:
                    await self.current_backend.send_animation_data(animation)

            elif event.event_type == EventType.MOVEMENT and event.movement_params:
                # Create animation with movement parameters
                animation = CanonicalAnimationData(timestamp=event.timestamp, parameters=event.movement_params)
                if self.current_backend:
                    await self.current_backend.send_animation_data(animation)

            elif event.event_type == EventType.PARALLEL and event.parallel_events:
                # Execute parallel events concurrently
                tasks = [self._execute_event(e) for e in event.parallel_events]
                await asyncio.gather(*tasks)

        except Exception as e:
            self.logger.error(f"Error executing event: {e}")

    async def pause_sequence(self) -> Dict[str, Any]:
        """Pause the currently playing sequence."""
        if not self.sequence_task:
            return {"success": False, "error": "No sequence is playing"}

        self.sequence_paused = True
        return {"success": True, "message": "Sequence paused"}

    async def resume_sequence(self) -> Dict[str, Any]:
        """Resume the paused sequence."""
        if not self.sequence_task:
            return {"success": False, "error": "No sequence to resume"}

        self.sequence_paused = False
        return {"success": True, "message": "Sequence resumed"}

    async def stop_sequence(self) -> Dict[str, Any]:
        """Stop the currently playing sequence."""
        if self.sequence_task:
            self.sequence_task.cancel()
            self.sequence_task = None
            self.sequence_time = 0.0
            return {"success": True, "message": "Sequence stopped"}

        return {"success": False, "error": "No sequence is playing"}

    async def _parse_event_dict(self, event_dict: Dict[str, Any]) -> Optional[SequenceEvent]:
        """Parse a dictionary into a SequenceEvent (for backward compatibility)."""
        return await self._create_event_from_dict(event_dict)

    async def _create_animation_event(self, event: SequenceEvent, params: Dict[str, Any]) -> None:
        """Create animation event from parameters."""
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

    async def _create_audio_event(self, event: SequenceEvent, event_dict: Dict[str, Any]) -> None:
        """Create audio event from data."""
        audio_data = event_dict.get("audio_data")
        if audio_data:
            import base64

            if audio_data.startswith("data:"):
                audio_data = audio_data.split(",")[1]
            audio_bytes = base64.b64decode(audio_data)
            event.audio_data = AudioData(
                data=audio_bytes,
                format=event_dict.get("audio_format", "mp3"),
                duration=event_dict.get("duration", 0.0),
            )

    async def _create_expression_event(self, event: SequenceEvent, event_dict: Dict[str, Any]) -> None:
        """Create expression event from parameters."""
        expression = event_dict.get("expression")
        if expression:
            event.expression = EmotionType[expression.upper()]
            event.expression_intensity = event_dict.get("expression_intensity", 1.0)

    async def _create_parallel_events(self, event: SequenceEvent, event_dict: Dict[str, Any]) -> None:
        """Create parallel events recursively."""
        parallel_events_data = event_dict.get("parallel_events", [])
        event.parallel_events = []
        for p_event_dict in parallel_events_data:
            p_event = await self._create_event_from_dict(p_event_dict)
            if p_event:
                event.parallel_events.append(p_event)

    async def _create_event_from_dict(self, event_dict: Dict[str, Any]) -> Optional[SequenceEvent]:
        """Centralized event creation logic from dictionary."""
        try:
            event_type = event_dict.get("event_type", "").upper()
            if not event_type or event_type not in EventType.__members__:
                self.logger.error(f"Invalid event_type: {event_type}")
                return None

            event = SequenceEvent(
                event_type=EventType[event_type],
                timestamp=event_dict.get("timestamp", 0.0),
                duration=event_dict.get("duration"),
                sync_with_audio=event_dict.get("sync_with_audio", False),
            )

            # Parse event-specific data based on type
            if event_type == "ANIMATION":
                animation_params = event_dict.get("animation_params", {})
                if animation_params:
                    await self._create_animation_event(event, animation_params)
            elif event_type == "AUDIO":
                await self._create_audio_event(event, event_dict)
            elif event_type == "EXPRESSION":
                await self._create_expression_event(event, event_dict)
            elif event_type == "MOVEMENT":
                event.movement_params = event_dict.get("movement_params")
            elif event_type == "WAIT":
                event.wait_duration = event_dict.get("wait_duration", event_dict.get("duration", 1.0))
            elif event_type == "PARALLEL":
                await self._create_parallel_events(event, event_dict)

            return event

        except Exception as e:
            self.logger.error(f"Error creating event from dict: {e}")
            return None

    async def get_sequence_status(self) -> Dict[str, Any]:
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

    async def startup_auto_connect(self):
        """Auto-connect to default backend on server startup."""
        # Wait for server to fully initialize
        await asyncio.sleep(2)

        if not self.auto_connect:
            logger.info("Auto-connect disabled. Use set_backend() to connect manually.")
            return

        try:
            logger.info(f"Auto-connecting to {self.default_backend} backend...")
            logger.info(
                f"Configuration: VRChat at {self.default_config['remote_host']}:" f"{self.default_config['osc_in_port']}"
            )

            result = await self.set_backend(self.default_backend, self.default_config)

            if result["success"]:
                logger.info(f"✓ Successfully auto-connected to {self.default_backend}")

                # Validate the connection works
                test_result = await self.validate_connection()
                if test_result:
                    logger.info("✓ Connection validated - OSC messages reaching VRChat")
                else:
                    logger.warning("⚠ Connection established but validation failed")
                    logger.info("Check that VRChat OSC is enabled and avatar supports VRCEmote")
            else:
                logger.warning(f"Failed to auto-connect: {result.get('error', 'Unknown error')}")
                logger.info("You can manually connect using set_backend()")

        except Exception as e:
            logger.error(f"Error during auto-connect: {e}")
            logger.info("You can manually connect using set_backend()")

    async def validate_connection(self) -> bool:
        """Validate that OSC messages actually reach VRChat."""
        if not self.current_backend:
            return False

        try:
            # Send a neutral reset to test connection
            test_animation = CanonicalAnimationData(
                timestamp=0,
                emotion=EmotionType.NEUTRAL,
                gesture=GestureType.NONE,
            )

            success = await self.current_backend.send_animation_data(test_animation)

            if success:
                # Check if we can get stats (indicates healthy connection)
                stats = await self.current_backend.get_statistics()
                return bool(stats.get("osc_messages_sent", 0) > 0)

            return False

        except Exception as e:
            logger.error(f"Connection validation failed: {e}")
            return False

    async def monitor_connection(self):
        """Background task to monitor and auto-reconnect if needed."""
        while True:
            await asyncio.sleep(30)  # Check every 30 seconds

            if self.current_backend and self.auto_connect:
                try:
                    health = await self.current_backend.health_check()
                    if not health.get("connected", False):
                        logger.warning("Connection lost, attempting reconnect...")
                        await self.auto_reconnect()
                except Exception as e:
                    logger.error(f"Health check failed: {e}")
                    await self.auto_reconnect()

    async def auto_reconnect(self):
        """Attempt to reconnect to the backend."""
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            logger.error("Max reconnection attempts reached. Manual intervention required.")
            return

        self.reconnect_attempts += 1
        logger.info(f"Reconnection attempt {self.reconnect_attempts}/{self.max_reconnect_attempts}")

        # Try to reconnect with stored config
        if self.backend_name and self.config:
            result = await self.set_backend(self.backend_name, self.config)
            if result["success"]:
                logger.info("✓ Successfully reconnected")
                self.reconnect_attempts = 0
            else:
                logger.error(f"Reconnection failed: {result.get('error')}")

    def _get_improved_port_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert clearer port names to internal format.
        Supports both old and new naming conventions.
        """
        improved_config = config.copy()

        # Support new clearer names
        if "vrchat_recv_port" in config:
            improved_config["osc_in_port"] = config["vrchat_recv_port"]
        if "vrchat_send_port" in config:
            improved_config["osc_out_port"] = config["vrchat_send_port"]

        # Default to sensible values if not specified
        if "osc_in_port" not in improved_config and "vrchat_recv_port" not in config:
            improved_config["osc_in_port"] = 9000  # VRChat receives here
        if "osc_out_port" not in improved_config and "vrchat_send_port" not in config:
            improved_config["osc_out_port"] = 9001  # VRChat sends here

        return improved_config


def main():
    """Main entry point for Virtual Character MCP server."""
    import argparse

    parser = argparse.ArgumentParser(description="Virtual Character MCP Server")
    parser.add_argument("--port", type=int, default=8020, help="Port to run server on")
    parser.add_argument("--mode", choices=["stdio", "http"], default="http", help="Server mode")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to (HTTP mode only)")

    args = parser.parse_args()

    if args.mode == "stdio":
        # STDIO mode for local MCP integration
        logger.info("Starting Virtual Character MCP server in STDIO mode...")
        # TODO: Implement STDIO mode similar to other MCP servers
        logger.error("STDIO mode not yet implemented for Virtual Character server")
        sys.exit(1)
    else:
        # HTTP mode for remote access
        logger.info(f"Starting Virtual Character MCP server on http://{args.host}:{args.port}")
        server = VirtualCharacterMCPServer(port=args.port)

        async def run_server():
            """Run server with auto-connect and monitoring"""
            # Start auto-connect task
            asyncio.create_task(server.startup_auto_connect())

            # Start connection monitor
            asyncio.create_task(server.monitor_connection())

            logger.info("Virtual Character MCP Server initialized with auto-connect")
            logger.info("Default configuration:")
            logger.info("  - Backend: vrchat_remote")
            logger.info("  - VRChat Host: 127.0.0.1")
            logger.info("  - VRChat Receive Port: 9000")
            logger.info("  - VRChat Send Port: 9001")
            logger.info("  - VRCEmote System: Enabled")

            # Run the server
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
