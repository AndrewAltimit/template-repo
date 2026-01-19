"""Base MCP Server implementation with common functionality"""

from abc import ABC, abstractmethod
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import json
import logging
from typing import Any, Dict, List, Optional
import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from mcp import types
from mcp.server import InitializationOptions, NotificationOptions, Server
import mcp.server.stdio
from pydantic import BaseModel


class ToolRequest(BaseModel):
    """Model for tool execution requests"""

    tool: str
    arguments: Optional[Dict[str, Any]] = None
    parameters: Optional[Dict[str, Any]] = None

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
        self._protocol_version: Optional[str] = None
        self._tools: Dict[str, Dict[str, Any]] = {}
        self._tool_funcs: Dict[str, Any] = {}
        self.app = FastAPI(title=name, version=version, lifespan=self._create_lifespan())
        self._setup_routes()

    def _create_lifespan(self):
        """Create lifespan context manager for startup/shutdown events."""
        server = self

        @asynccontextmanager
        async def lifespan(_app: FastAPI):
            server.logger.info("%s starting on port %s", server.name, server.port)
            server.logger.info("Server version: %s", server.version)
            server.logger.info("Server initialized successfully")
            yield

        return lifespan

    def _setup_routes(self):
        """Setup HTTP routes for MCP protocol"""
        # Health check
        self.app.get("/health")(self.health_check)

        # Tool operations
        self.app.get("/mcp/tools")(self.list_tools)
        self.app.post("/mcp/execute")(self.execute_tool)
        self.app.post("/tools/execute")(self.execute_tool)  # Legacy compatibility

        # MCP protocol discovery
        self.app.get("/.well-known/mcp")(self.mcp_discovery)
        self.app.post("/mcp/initialize")(self.mcp_initialize)
        self.app.get("/mcp/capabilities")(self.mcp_capabilities)

        # Streamable HTTP transport (MCP 2024-11-05 spec)
        self.app.get("/messages")(self.handle_messages_get)
        self.app.post("/messages")(self.handle_messages)

        # JSON-RPC endpoints
        self.app.get("/mcp")(self.handle_mcp_get)
        self.app.post("/mcp")(self.handle_jsonrpc)
        self.app.options("/mcp")(self.handle_options)
        self.app.post("/mcp/rpc")(self.handle_jsonrpc)

    async def health_check(self):
        """Health check endpoint"""
        return {"status": "healthy", "server": self.name, "version": self.version}

    async def handle_mcp_get(self, request: Request):
        """Handle GET requests to /mcp endpoint for SSE streaming"""
        from fastapi.responses import StreamingResponse

        session_id = request.headers.get("Mcp-Session-Id", str(uuid.uuid4()))

        async def event_generator():
            connection_data = {
                "type": "connection",
                "sessionId": session_id,
                "status": "connected",
            }
            yield f"data: {json.dumps(connection_data)}\n\n"

            while True:
                await asyncio.sleep(15)
                ping_data = {"type": "ping", "timestamp": datetime.now(timezone.utc).isoformat()}
                yield f"data: {json.dumps(ping_data)}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
                "Mcp-Session-Id": session_id,
            },
        )

    async def handle_messages_get(self, _request: Request):
        """Handle GET requests to /messages endpoint"""
        return {
            "protocol": "mcp",
            "version": "1.0",
            "server": {
                "name": self.name,
                "version": self.version,
                "description": f"{self.name} MCP Server",
            },
            "transport": {
                "type": "streamable-http",
                "endpoint": "/messages",
            },
        }

    async def _handle_streaming_response(self, body, session_id: Optional[str]):
        """Handle streaming response mode (SSE)."""
        from fastapi.responses import StreamingResponse

        async def event_generator():
            if session_id:
                yield f"data: {json.dumps({'type': 'session', 'sessionId': session_id})}\n\n"

            if isinstance(body, list):
                for req in body:
                    response = await self._process_jsonrpc_request(req)
                    if response:
                        yield f"data: {json.dumps(response)}\n\n"
            else:
                response = await self._process_jsonrpc_request(body)
                if response:
                    yield f"data: {json.dumps(response)}\n\n"

            yield f"data: {json.dumps({'type': 'completion'})}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
                "Mcp-Session-Id": session_id or "",
            },
        )

    async def _handle_batch_request(self, body: list, session_id: Optional[str]):
        """Handle batch JSON-RPC request."""
        responses = []
        has_notifications = False
        for req in body:
            response = await self._process_jsonrpc_request(req)
            if response is None:
                has_notifications = True
            else:
                responses.append(response)

        if not responses and has_notifications:
            return Response(status_code=202, headers={"Mcp-Session-Id": session_id or ""})

        return JSONResponse(
            content=responses,
            headers={"Content-Type": "application/json", "Mcp-Session-Id": session_id or ""},
        )

    async def _handle_single_request(self, body: dict, session_id: Optional[str], is_init_request: bool):
        """Handle single JSON-RPC request."""
        response = await self._process_jsonrpc_request(body)

        if response is None:
            return Response(status_code=202, headers={"Mcp-Session-Id": session_id or ""})

        if is_init_request and session_id:
            self.logger.info("Returning session ID in response: %s", session_id)

        return JSONResponse(
            content=response,
            headers={"Content-Type": "application/json", "Mcp-Session-Id": session_id or ""},
        )

    async def handle_messages(self, request: Request):
        """Handle POST requests to /messages endpoint (HTTP Stream Transport)"""
        session_id = request.headers.get("Mcp-Session-Id")
        response_mode = request.headers.get("Mcp-Response-Mode", "batch").lower()
        protocol_version = request.headers.get("MCP-Protocol-Version")

        self.logger.info("Messages request headers: %s", dict(request.headers))
        self.logger.info(
            "Session ID: %s, Response Mode: %s, Protocol Version: %s", session_id, response_mode, protocol_version
        )

        try:
            body = await request.json()
            self.logger.info("Messages request body: %s", json.dumps(body))

            is_init_request = isinstance(body, dict) and body.get("method") == "initialize"
            if is_init_request and not session_id:
                session_id = str(uuid.uuid4())
                self.logger.info("Generated new session ID: %s", session_id)

            if response_mode == "stream":
                return await self._handle_streaming_response(body, session_id)
            if isinstance(body, list):
                return await self._handle_batch_request(body, session_id)
            return await self._handle_single_request(body, session_id, is_init_request)

        except Exception as e:
            self.logger.error("Messages endpoint error: %s", e)
            return JSONResponse(
                content={
                    "jsonrpc": "2.0",
                    "error": {"code": -32700, "message": "Parse error", "data": str(e)},
                    "id": None,
                },
                status_code=400,
                headers={"Content-Type": "application/json", "Mcp-Session-Id": session_id or ""},
            )

    async def handle_jsonrpc(self, request: Request):
        """Handle JSON-RPC 2.0 requests for MCP protocol"""
        return await self.handle_messages(request)

    async def handle_options(self, _request: Request):
        """Handle OPTIONS requests for CORS preflight"""
        return Response(
            content="",
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, Authorization, Mcp-Session-Id, Mcp-Response-Mode",
                "Access-Control-Max-Age": "86400",
            },
        )

    async def _process_jsonrpc_request(self, request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process a single JSON-RPC request"""
        jsonrpc = request.get("jsonrpc", "2.0")
        method = request.get("method")
        params = request.get("params", {})
        req_id = request.get("id")

        self.logger.info("JSON-RPC request: method=%s, id=%s", method, req_id)

        is_notification = req_id is None

        try:
            if method == "initialize":
                result = await self._jsonrpc_initialize(params)
            elif method == "initialized":
                self.logger.info("Client sent initialized notification")
                if is_notification:
                    return None
                result = {"status": "acknowledged"}
            elif method == "tools/list":
                result = await self._jsonrpc_list_tools(params)
            elif method == "tools/call":
                result = await self._jsonrpc_call_tool(params)
            elif method == "completion/complete":
                result = {"error": "Completions not supported"}
            elif method == "ping":
                result = {"pong": True}
            else:
                if not is_notification:
                    return {
                        "jsonrpc": jsonrpc,
                        "error": {
                            "code": -32601,
                            "message": f"Method not found: {method}",
                        },
                        "id": req_id,
                    }
                return None

            if not is_notification:
                response = {"jsonrpc": jsonrpc, "result": result, "id": req_id}
                self.logger.info("JSON-RPC response: %s", json.dumps(response))

                if method == "initialize" and "protocolVersion" in result:
                    self.logger.info("Initialization complete, ready for tools/list request")

                return response
            return None

        except Exception as e:
            self.logger.error("Error processing method %s: %s", method, e)
            if not is_notification:
                return {
                    "jsonrpc": jsonrpc,
                    "error": {
                        "code": -32603,
                        "message": "Internal error",
                        "data": str(e),
                    },
                    "id": req_id,
                }
            return None

    async def _jsonrpc_initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle initialize request"""
        client_info = params.get("clientInfo", {})
        protocol_version = params.get("protocolVersion", "2024-11-05")

        self.logger.info("Client info: %s, requested protocol: %s", client_info, protocol_version)
        self._protocol_version = protocol_version

        return {
            "protocolVersion": protocol_version,
            "serverInfo": {"name": self.name, "version": self.version},
            "capabilities": {
                "tools": {"listChanged": True},
                "resources": {},
                "prompts": {},
            },
        }

    async def _jsonrpc_list_tools(self, _params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tools/list request"""
        tools = self.get_tools()
        self.logger.info("Available tools from get_tools(): %s", list(tools.keys()))

        tool_list = []
        for tool_name, tool_info in tools.items():
            tool_list.append(
                {
                    "name": tool_name,
                    "description": tool_info.get("description", ""),
                    "inputSchema": tool_info.get("parameters", {}),
                }
            )

        self.logger.info("Returning %s tools to client", len(tool_list))
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
            self.logger.error("Error calling tool %s: %s", tool_name, e)
            return {
                "content": [{"type": "text", "text": f"Error executing {tool_name}: {str(e)}"}],
                "isError": True,
            }

    async def mcp_discovery(self):
        """MCP protocol discovery endpoint"""
        return {
            "mcp_version": "1.0",
            "server_name": self.name,
            "server_version": self.version,
            "capabilities": {
                "tools": True,
                "prompts": False,
                "resources": False,
            },
            "endpoints": {
                "tools": "/mcp/tools",
                "execute": "/mcp/execute",
                "initialize": "/mcp/initialize",
                "capabilities": "/mcp/capabilities",
            },
        }

    async def mcp_initialize(self, request: Dict[str, Any]):
        """Initialize MCP session"""
        client_info = request.get("client", {})
        return {
            "session_id": f"session-{client_info.get('name', 'unknown')}-{int(datetime.now(timezone.utc).timestamp())}",
            "server": {
                "name": self.name,
                "version": self.version,
            },
            "capabilities": {
                "tools": True,
                "prompts": False,
                "resources": False,
            },
        }

    async def mcp_capabilities(self):
        """Return server capabilities"""
        tools = self.get_tools()
        return {
            "capabilities": {
                "tools": {
                    "list": list(tools.keys()),
                    "count": len(tools),
                },
                "prompts": {
                    "supported": False,
                },
                "resources": {
                    "supported": False,
                },
            },
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
            tools = self.get_tools()
            if request.tool not in tools:
                raise HTTPException(status_code=404, detail=f"Tool '{request.tool}' not found")

            tool_func = getattr(self, request.tool, None)
            if not tool_func:
                raise HTTPException(status_code=501, detail=f"Tool '{request.tool}' not implemented")

            result = await tool_func(**request.get_args())
            return ToolResponse(success=True, result=result)

        except Exception as e:
            self.logger.error("Error executing tool %s: %s", request.tool, str(e))
            return ToolResponse(success=False, result=None, error=str(e))

    @abstractmethod
    def get_tools(self) -> Dict[str, Dict[str, Any]]:
        """Return dictionary of available tools and their metadata"""

    async def run_stdio(self):
        """Run the server in stdio mode (for Claude desktop app)"""
        server = Server(self.name)

        self._tools = self.get_tools()
        self._tool_funcs = {}
        for tool_name, _tool_info in self._tools.items():
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
                result = await self._tool_funcs[name](**arguments)

                if isinstance(result, dict):
                    return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
                return [types.TextContent(type="text", text=str(result))]
            except Exception as e:
                self.logger.error("Error calling tool %s: %s", name, str(e))
                return [types.TextContent(type="text", text=f"Error: {str(e)}")]

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
