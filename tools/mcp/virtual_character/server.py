"""Virtual Character MCP Server for AI Agent Embodiment"""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Any, Dict, Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tools.mcp.core.base_server import BaseMCPServer  # noqa: E402
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

    def get_tools(self):
        """Return available MCP tools."""
        return {}

    def setup_routes(self):
        """Setup FastAPI routes for virtual character control."""
        super().setup_routes()

        @self.app.post("/set_backend")
        async def set_backend(request: Dict[str, Any]) -> Dict[str, Any]:
            """Connect to a specific backend."""
            backend = request.get("backend", "mock")
            config = request.get("config", {})

            try:
                # Disconnect current backend if any
                if self.current_backend:
                    await self.current_backend.disconnect()

                # Create and connect new backend
                if backend not in self.backends:
                    return {"success": False, "error": f"Unknown backend: {backend}"}

                backend_class = self.backends[backend]
                self.current_backend = backend_class()
                success = await self.current_backend.connect(config)

                if success:
                    self.backend_name = backend
                    return {"success": True, "backend": backend, "message": f"Connected to {backend}"}
                else:
                    return {"success": False, "error": f"Failed to connect to {backend}"}

            except Exception as e:
                logger.error(f"Error setting backend: {e}")
                return {"success": False, "error": str(e)}

        @self.app.post("/send_animation")
        async def send_animation(request: Dict[str, Any]) -> Dict[str, Any]:
            """Send animation data to the current backend."""
            if not self.current_backend:
                return {"success": False, "error": "No backend connected"}

            try:
                # Create animation data
                animation = CanonicalAnimationData(timestamp=asyncio.get_event_loop().time())

                # Set emotion if provided
                if "emotion" in request:
                    emotion_str = request["emotion"]
                    animation.emotion = EmotionType[emotion_str.upper()]
                    animation.emotion_intensity = request.get("emotion_intensity", 1.0)

                # Set gesture if provided
                if "gesture" in request:
                    gesture_str = request["gesture"]
                    animation.gesture = GestureType[gesture_str.upper()]
                    animation.gesture_intensity = request.get("gesture_intensity", 1.0)

                # Set blend shapes if provided
                if "blend_shapes" in request:
                    animation.blend_shapes = request["blend_shapes"]

                # Set parameters if provided
                if "parameters" in request:
                    animation.parameters = request["parameters"]

                # Send to backend
                success = await self.current_backend.send_animation_data(animation)

                return {"success": success}

            except KeyError as e:
                return {"success": False, "error": f"Invalid enum value: {e}"}
            except Exception as e:
                logger.error(f"Error sending animation: {e}")
                return {"success": False, "error": str(e)}

        @self.app.post("/execute_behavior")
        async def execute_behavior(request: Dict[str, Any]) -> Dict[str, Any]:
            """Execute a high-level behavior."""
            if not self.current_backend:
                return {"success": False, "error": "No backend connected"}

            try:
                behavior = request.get("behavior", "")
                parameters = request.get("parameters", {})

                if not behavior:
                    return {"success": False, "error": "No behavior specified"}

                success = await self.current_backend.execute_behavior(behavior, parameters)

                return {"success": success}

            except Exception as e:
                logger.error(f"Error executing behavior: {e}")
                return {"success": False, "error": str(e)}

        @self.app.get("/receive_state")
        async def receive_state() -> Dict[str, Any]:
            """Receive current state from the backend."""
            if not self.current_backend:
                return {"success": False, "error": "No backend connected"}

            try:
                state = await self.current_backend.receive_state()

                if state:
                    return {
                        "success": True,
                        "state": {
                            "world_name": state.world_name,
                            "agent_position": state.agent_position,
                            "agent_rotation": state.agent_rotation,
                        },
                    }
                else:
                    return {"success": False, "error": "No state available"}

            except Exception as e:
                logger.error(f"Error receiving state: {e}")
                return {"success": False, "error": str(e)}

        @self.app.get("/list_backends")
        async def list_backends() -> Dict[str, Any]:
            """List available backends."""
            try:
                backends = []
                for name, backend_class in self.backends.items():
                    backend_info = {
                        "name": name,
                        "class": backend_class.__name__,
                        "loaded": True,
                        "active": name == self.backend_name,
                    }
                    backends.append(backend_info)

                return {"success": True, "backends": backends}

            except Exception as e:
                logger.error(f"Error listing backends: {e}")
                return {"success": False, "error": str(e)}

        @self.app.get("/get_backend_status")
        async def get_backend_status() -> Dict[str, Any]:
            """Get status of current backend."""
            if not self.current_backend:
                return {
                    "success": True,
                    "backend": None,
                    "connected": False,
                    "health": "No backend connected",
                }

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
                logger.error(f"Error getting backend status: {e}")
                return {"success": False, "error": str(e)}

    async def execute_tool(self, request) -> Any:
        """Execute MCP tool - maps tool names to backend methods."""
        # Extract tool and arguments from request
        tool = request.tool if hasattr(request, "tool") else request.get("tool")
        # arguments = request.arguments if hasattr(request, 'arguments') else request.get('arguments', {})

        # For now, just return a simple response indicating the tool isn't implemented via MCP
        # The HTTP endpoints handle the actual functionality
        return {"message": f"Tool {tool} should be called via HTTP endpoints", "success": False}

    async def cleanup(self):
        """Cleanup on server shutdown."""
        if self.current_backend:
            try:
                await self.current_backend.disconnect()
            except Exception as e:
                logger.error(f"Error disconnecting backend: {e}")


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
