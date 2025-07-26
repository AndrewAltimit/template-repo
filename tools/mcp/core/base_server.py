"""Base MCP Server implementation with common functionality"""

import asyncio
import json
import logging
import os  # noqa: F401
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional

import mcp.server.stdio
import mcp.types as types
from fastapi import FastAPI, HTTPException, Request
from mcp.server import InitializationOptions, NotificationOptions, Server
from pydantic import BaseModel

# from .client_registry import ClientRegistry  # Disabled for home lab use


class ToolRequest(BaseModel):
    """Model for tool execution requests"""

    tool: str
    arguments: Optional[Dict[str, Any]] = None
    parameters: Optional[Dict[str, Any]] = None
    client_id: Optional[str] = None

    def get_args(self) -> Dict[str, Any]:
        """Get arguments, supporting both 'arguments' and 'parameters' fields"""
        return self.arguments or self.parameters or {}


class ToolResponse(BaseModel):
    """Model for tool execution responses"""

    success: bool
    result: Any
    error: Optional[str] = None


class BaseMCPServer(ABC):
    """Base class for all MCP servers"""

    def __init__(self, name: str, version: str = "1.0.0", port: int = 8000):
        self.name = name
        self.version = version
        self.port = port
        self.logger = logging.getLogger(name)
        self.app = FastAPI(title=name, version=version)
        # Skip client registry for home lab use
        # self.client_registry = ClientRegistry()
        self._setup_routes()
        self._setup_events()

    def _setup_events(self):
        """Setup startup/shutdown events"""

        @self.app.on_event("startup")
        async def startup_event():
            self.logger.info(f"{self.name} starting on port {self.port}")
            self.logger.info(f"Server version: {self.version}")
            self.logger.info("Server initialized successfully")

    def _setup_routes(self):
        """Setup common HTTP routes"""
        self.app.get("/health")(self.health_check)
        self.app.get("/mcp/tools")(self.list_tools)
        self.app.post("/mcp/execute")(self.execute_tool)
        self.app.post("/mcp/register")(self.register_client)
        self.app.post("/register")(self.register_client_oauth)  # OAuth2 style for Claude Code
        self.app.post("/oauth/register")(self.register_client_oauth)  # OAuth style endpoint
        self.app.get("/mcp/clients")(self.list_clients)
        self.app.get("/mcp/clients/{client_id}")(self.get_client_info)
        self.app.get("/mcp/stats")(self.get_stats)

    async def health_check(self):
        """Health check endpoint"""
        return {"status": "healthy", "server": self.name, "version": self.version}

    async def register_client(self, request: Dict[str, Any]):
        """Register a client - simplified for home lab use"""
        client_name = request.get("client", request.get("client_name", "unknown"))
        client_id = request.get("client_id", f"{client_name}_simple")

        # Simple response without tracking for home lab
        self.logger.info(f"Client registration request from: {client_name}")

        return {
            "status": "registered",
            "client": client_name,
            "client_id": client_id,
            "server": self.name,
            "version": self.version,
            "registration": {
                "client_id": client_id,
                "client_name": client_name,
                "registered": True,
                "is_update": False,
                "registration_time": datetime.utcnow().isoformat(),
                "server_time": datetime.utcnow().isoformat(),
            },
        }

    async def register_client_oauth(self, request_data: Dict[str, Any], request: Request):
        """OAuth2-style client registration - simplified for home lab use"""
        redirect_uris = request_data.get("redirect_uris", [])
        client_name = request_data.get("client_name", request_data.get("client", "claude-code"))
        client_id = f"{client_name}_oauth"

        # Simple OAuth2-compliant response without tracking
        self.logger.info(f"OAuth registration request from: {client_name}")

        return {
            "client_id": client_id,
            "client_name": client_name,
            "redirect_uris": redirect_uris if redirect_uris else ["http://localhost"],
            "grant_types": request_data.get("grant_types", ["authorization_code"]),
            "response_types": request_data.get("response_types", ["code"]),
            "token_endpoint_auth_method": request_data.get("token_endpoint_auth_method", "none"),
            "registration_access_token": "not-required-for-local-mcp",
            "registration_client_uri": f"{request.url.scheme}://{request.url.netloc}/mcp/clients/{client_id}",
            "client_id_issued_at": int(datetime.utcnow().timestamp()),
            "client_secret_expires_at": 0,  # Never expires
        }

    async def list_tools(self):
        """List available tools"""
        tools = self.get_tools()
        return {
            "tools": [
                {
                    "name": tool_name,
                    "description": tool_info.get("description", ""),
                    "parameters": tool_info.get("parameters", {}),
                }
                for tool_name, tool_info in tools.items()
            ]
        }

    async def execute_tool(self, request: ToolRequest):
        """Execute a tool with given arguments"""
        try:
            # Skip client tracking for home lab use

            tools = self.get_tools()
            if request.tool not in tools:
                raise HTTPException(status_code=404, detail=f"Tool '{request.tool}' not found")

            # Get the tool function
            tool_func = getattr(self, request.tool, None)
            if not tool_func:
                raise HTTPException(status_code=501, detail=f"Tool '{request.tool}' not implemented")

            # Execute the tool
            result = await tool_func(**request.get_args())

            return ToolResponse(success=True, result=result)

        except Exception as e:
            self.logger.error(f"Error executing tool {request.tool}: {str(e)}")
            return ToolResponse(success=False, result=None, error=str(e))

    async def list_clients(self, active_only: bool = True):
        """List clients - returns empty for home lab use"""
        return {"clients": [], "count": 0, "active_only": active_only}

    async def get_client_info(self, client_id: str):
        """Get client info - returns simple response for home lab use"""
        return {
            "client_id": client_id,
            "client_name": client_id.replace("_oauth", "").replace("_simple", ""),
            "active": True,
            "registered_at": datetime.utcnow().isoformat(),
        }

    async def get_stats(self):
        """Get server statistics - simplified for home lab use"""
        return {
            "server": {"name": self.name, "version": self.version, "tools_count": len(self.get_tools())},
            "clients": {
                "total_clients": 0,
                "active_clients": 0,
                "inactive_clients": 0,
                "clients_active_last_hour": 0,
                "total_requests": 0,
            },
        }

    @abstractmethod
    def get_tools(self) -> Dict[str, Dict[str, Any]]:
        """Return dictionary of available tools and their metadata"""
        pass

    async def run_stdio(self):
        """Run the server in stdio mode (for Claude desktop app)"""
        server = Server(self.name)

        # Store tools and their functions for later access
        self._tools = self.get_tools()
        self._tool_funcs = {}
        for tool_name, tool_info in self._tools.items():
            tool_func = getattr(self, tool_name, None)
            if tool_func:
                self._tool_funcs[tool_name] = tool_func

        @server.list_tools()
        async def list_tools() -> List[types.Tool]:
            """List available tools"""
            tools = []
            for tool_name, tool_info in self._tools.items():
                tools.append(
                    types.Tool(
                        name=tool_name,
                        description=tool_info.get("description", ""),
                        inputSchema=tool_info.get("parameters", {}),
                    )
                )
            return tools

        @server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> List[types.TextContent]:
            """Call a tool with given arguments"""
            if name not in self._tool_funcs:
                return [types.TextContent(type="text", text=f"Tool '{name}' not found")]

            try:
                # Call the tool function
                result = await self._tool_funcs[name](**arguments)

                # Convert result to MCP response format
                if isinstance(result, dict):
                    return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
                return [types.TextContent(type="text", text=str(result))]
            except Exception as e:
                self.logger.error(f"Error calling tool {name}: {str(e)}")
                return [types.TextContent(type="text", text=f"Error: {str(e)}")]

        # Run the stdio server
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name=self.name,
                    server_version=self.version,
                    capabilities=server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={},
                    ),
                ),
            )

    def run_http(self):
        """Run the server in HTTP mode"""
        import uvicorn

        uvicorn.run(self.app, host="0.0.0.0", port=self.port)

    def run(self, mode: str = "http"):
        """Run the server in specified mode"""
        if mode == "stdio":
            asyncio.run(self.run_stdio())
        elif mode == "http":
            self.run_http()
        else:
            raise ValueError(f"Unknown mode: {mode}. Use 'stdio' or 'http'.")
