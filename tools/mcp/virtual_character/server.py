"""Virtual Character MCP Server for AI Agent Embodiment"""

import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

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


from tools.mcp.virtual_character.backends.base import BackendAdapter  # noqa: E402
from tools.mcp.virtual_character.backends.mock import MockBackend  # noqa: E402
from tools.mcp.virtual_character.backends.vrchat_remote import VRChatRemoteBackend  # noqa: E402
from tools.mcp.virtual_character.models.canonical import (  # noqa: E402
    CanonicalAnimationData,
    EmotionType,
    GestureType,
)

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class VirtualCharacterMCPServer(BaseMCPServer):
    """MCP Server for Virtual Character Control"""

    def __init__(self, port: int = 8020):
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
                                "osc_in_port": {"type": "integer", "default": 9000, "description": "OSC input port"},
                                "osc_out_port": {"type": "integer", "default": 9001, "description": "OSC output port"},
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
                            "enum": ["none", "wave", "point", "thumbs_up", "nod", "shake_head", "clap", "dance"],
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
        }

    async def set_backend(self, backend: str, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Connect to a specific backend."""
        if config is None:
            config = {}

        try:
            # Disconnect current backend if any
            if self.current_backend:
                await self.current_backend.disconnect()

            # Create and connect new backend
            if backend not in self.backends:
                return {"success": False, "error": f"Unknown backend: {backend}"}

            backend_class = self.backends[backend]
            self.current_backend = backend_class()

            # Set default config for vrchat_remote if not provided
            if backend == "vrchat_remote" and "remote_host" not in config:
                config["remote_host"] = "127.0.0.1"  # Local VRChat on Windows machine

            success = await self.current_backend.connect(config)

            if success:
                self.backend_name = backend
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

        try:
            import uvicorn

            uvicorn.run(server.app, host=args.host, port=args.port)
        except ImportError:
            logger.error("uvicorn not installed. Install with: pip install uvicorn")
            sys.exit(1)


if __name__ == "__main__":
    main()
