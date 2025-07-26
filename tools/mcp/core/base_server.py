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
from fastapi.responses import JSONResponse, RedirectResponse, Response
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
        # OAuth2 bypass endpoints - no auth required
        self.app.get("/authorize")(self.oauth_authorize_bypass)
        self.app.post("/authorize")(self.oauth_authorize_bypass)
        self.app.get("/oauth/authorize")(self.oauth_authorize_bypass)
        self.app.post("/oauth/authorize")(self.oauth_authorize_bypass)
        self.app.post("/token")(self.oauth_token_bypass)
        self.app.post("/oauth/token")(self.oauth_token_bypass)
        self.app.get("/mcp/clients")(self.list_clients)
        self.app.get("/mcp/clients/{client_id}")(self.get_client_info)
        self.app.get("/mcp/stats")(self.get_stats)
        # OAuth discovery endpoints
        self.app.get("/.well-known/oauth-authorization-server")(self.oauth_discovery)
        self.app.get("/.well-known/oauth-authorization-server/mcp")(self.oauth_discovery)
        self.app.get("/.well-known/oauth-authorization-server/messages")(self.oauth_discovery)
        self.app.get("/.well-known/oauth-protected-resource")(self.oauth_protected_resource)
        # MCP protocol discovery endpoints
        self.app.get("/.well-known/mcp")(self.mcp_discovery)
        self.app.post("/mcp/initialize")(self.mcp_initialize)
        self.app.get("/mcp/capabilities")(self.mcp_capabilities)
        # NEW: Streamable HTTP transport - single endpoint for both regular and streaming
        self.app.get("/messages")(self.handle_messages_get)
        self.app.post("/messages")(self.handle_messages)
        # Legacy endpoints for backward compatibility
        self.app.get("/mcp")(self.handle_mcp_get)
        self.app.post("/mcp")(self.handle_jsonrpc)
        self.app.options("/mcp")(self.handle_options)  # CORS preflight
        self.app.post("/mcp/rpc")(self.handle_jsonrpc)
        # SSE endpoint for streaming after auth
        self.app.get("/mcp/sse")(self.handle_mcp_sse)

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

    async def oauth_authorize_bypass(self, request: Request):
        """Bypass OAuth2 authorization - immediately approve without auth"""
        # Get query parameters
        params = dict(request.query_params)
        redirect_uri = params.get("redirect_uri", "http://localhost")
        state = params.get("state", "")

        # Immediately redirect back with authorization code
        auth_code = "bypass-auth-code-no-auth-required"

        # Build redirect URL with code
        separator = "&" if "?" in redirect_uri else "?"
        redirect_url = f"{redirect_uri}{separator}code={auth_code}"
        if state:
            redirect_url += f"&state={state}"

        # Return redirect response
        return RedirectResponse(url=redirect_url, status_code=302)

    async def oauth_token_bypass(self, request: Request):
        """Bypass OAuth2 token exchange - immediately return access token"""
        # Handle both JSON and form-encoded requests
        try:
            if request.headers.get("content-type", "").startswith("application/json"):
                request_data = await request.json()
            else:
                form_data = await request.form()
                request_data = dict(form_data)
        except Exception:
            request_data = {}

        # Log the request for debugging
        self.logger.info(f"Token request data: {request_data}")

        # Return a valid token response without any validation
        return {
            "access_token": "bypass-token-no-auth-required",
            "token_type": "Bearer",
            "expires_in": 31536000,  # 1 year
            "scope": "full_access",
            "refresh_token": "bypass-refresh-token-no-auth-required",
        }

    async def oauth_discovery(self, request: Request):
        """OAuth 2.0 authorization server metadata"""
        base_url = f"{request.url.scheme}://{request.url.netloc}"
        return {
            "issuer": base_url,
            "authorization_endpoint": f"{base_url}/authorize",
            "token_endpoint": f"{base_url}/token",
            "registration_endpoint": f"{base_url}/register",
            "token_endpoint_auth_methods_supported": ["none"],
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code"],
            "code_challenge_methods_supported": ["S256"],
            "registration_endpoint_auth_methods_supported": ["none"],
        }

    async def oauth_protected_resource(self, request: Request):
        """OAuth 2.0 protected resource metadata"""
        base_url = f"{request.url.scheme}://{request.url.netloc}"
        return {
            "resource": f"{base_url}/messages",
            "authorization_servers": [base_url],
        }

    async def handle_mcp_get(self, request: Request):
        """Handle GET requests to /mcp endpoint for SSE streaming"""
        # For HTTP Stream Transport, GET is used to establish SSE stream
        import uuid

        from fastapi.responses import StreamingResponse

        # Generate session ID
        session_id = request.headers.get("Mcp-Session-Id", str(uuid.uuid4()))

        async def event_generator():
            # Send initial connection event with session ID
            connection_data = {
                "type": "connection",
                "sessionId": session_id,
                "status": "connected",
            }
            yield f"data: {json.dumps(connection_data)}\n\n"

            # Keep connection alive with ping messages
            import asyncio

            while True:
                await asyncio.sleep(15)  # Ping every 15 seconds as per spec
                ping_data = {"type": "ping", "timestamp": datetime.utcnow().isoformat()}
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

    async def handle_mcp_sse(self, request: Request):
        """Handle SSE requests for authenticated clients"""
        import asyncio

        from fastapi.responses import StreamingResponse

        # Check authorization
        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Unauthorized")

        async def event_generator():
            # Send initial connection event
            yield f"data: {json.dumps({'type': 'connected', 'message': 'SSE connection established'})}\n\n"

            # Keep connection alive
            while True:
                await asyncio.sleep(30)
                yield f"data: {json.dumps({'type': 'ping'})}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    async def handle_messages_get(self, request: Request):
        """Handle GET requests to /messages endpoint"""
        # For GET requests, return MCP server info
        return {
            "protocol": "mcp",
            "version": "1.0",
            "server": {
                "name": self.name,
                "version": self.version,
                "description": f"{self.name} MCP Server",
            },
            "auth": {
                "required": False,
                "type": "none",
            },
            "transport": {
                "type": "streamable-http",
                "endpoint": "/messages",
            },
        }

    async def handle_messages(self, request: Request):
        """Handle POST requests to /messages endpoint (HTTP Stream Transport)"""
        # Get session ID from header
        session_id = request.headers.get("Mcp-Session-Id")

        # Check response mode preference
        response_mode = request.headers.get("Mcp-Response-Mode", "batch").lower()

        # Check protocol version header
        protocol_version = request.headers.get("MCP-Protocol-Version")

        # Log headers for debugging
        self.logger.info(f"Messages request headers: {dict(request.headers)}")
        self.logger.info(f"Session ID: {session_id}, Response Mode: {response_mode}, Protocol Version: {protocol_version}")

        try:
            # Parse JSON-RPC request
            body = await request.json()
            self.logger.info(f"Messages request body: {json.dumps(body)}")

            # Check if this is an initialization request to generate session ID
            is_init_request = False
            if isinstance(body, dict) and body.get("method") == "initialize":
                is_init_request = True
                if not session_id:
                    # Generate a new session ID for initialization
                    import uuid

                    session_id = str(uuid.uuid4())
                    self.logger.info(f"Generated new session ID: {session_id}")

            # Process based on response mode
            if response_mode == "stream":
                # Return SSE response for streaming
                from fastapi.responses import StreamingResponse

                async def event_generator():
                    # Send session info first if available
                    if session_id:
                        yield f"data: {json.dumps({'type': 'session', 'sessionId': session_id})}\n\n"

                    # Process the request
                    if isinstance(body, list):
                        # Batch request
                        for req in body:
                            response = await self._process_jsonrpc_request(req)
                            if response:
                                yield f"data: {json.dumps(response)}\n\n"
                    else:
                        # Single request
                        response = await self._process_jsonrpc_request(body)
                        if response:
                            yield f"data: {json.dumps(response)}\n\n"

                    # Send completion event
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
            else:
                # Batch mode (default)
                if isinstance(body, list):
                    responses = []
                    has_notifications = False
                    for req in body:
                        response = await self._process_jsonrpc_request(req)
                        if response is None:
                            has_notifications = True
                        else:
                            responses.append(response)

                    # If all were notifications, return 202
                    if not responses and has_notifications:
                        return Response(
                            status_code=202,
                            headers={
                                "Mcp-Session-Id": session_id or "",
                            },
                        )

                    # Otherwise return the responses
                    return JSONResponse(
                        content=responses,
                        headers={
                            "Content-Type": "application/json",
                            "Mcp-Session-Id": session_id or "",
                        },
                    )
                else:
                    response = await self._process_jsonrpc_request(body)
                    # For single requests, check if it's a notification
                    if response is None:
                        # This is a notification - return 202 Accepted with no body
                        return Response(
                            status_code=202,
                            headers={
                                "Mcp-Session-Id": session_id or "",
                            },
                        )
                    else:
                        # This is a request - return the response
                        # Log session ID being returned
                        if is_init_request and session_id:
                            self.logger.info(f"Returning session ID in response: {session_id}")

                        return JSONResponse(
                            content=response,
                            headers={
                                "Content-Type": "application/json",
                                "Mcp-Session-Id": session_id or "",
                            },
                        )
        except Exception as e:
            self.logger.error(f"Messages endpoint error: {e}")
            return JSONResponse(
                content={
                    "jsonrpc": "2.0",
                    "error": {"code": -32700, "message": "Parse error", "data": str(e)},
                    "id": None,
                },
                status_code=400,
                headers={
                    "Content-Type": "application/json",
                    "Mcp-Session-Id": session_id or "",
                },
            )

    async def handle_jsonrpc(self, request: Request):
        """Handle JSON-RPC 2.0 requests for MCP protocol"""
        # Forward to the new streamable handler
        return await self.handle_messages(request)

    async def handle_options(self, request: Request):
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

        # Log the request for debugging
        self.logger.info(f"JSON-RPC request: method={method}, id={req_id}")

        # If no ID, this is a notification (no response expected)
        is_notification = req_id is None

        try:
            # Route to appropriate handler based on method
            if method == "initialize":
                result = await self._jsonrpc_initialize(params)
            elif method == "initialized":
                # Handle initialized notification
                self.logger.info("Client sent initialized notification")
                if is_notification:
                    return None  # No response for notification
                result = {"status": "acknowledged"}
            elif method == "tools/list":
                result = await self._jsonrpc_list_tools(params)
            elif method == "tools/call":
                result = await self._jsonrpc_call_tool(params)
            elif method == "completion/complete":
                # We don't support completions
                result = {"error": "Completions not supported"}
            elif method == "ping":
                result = {"pong": True}
            else:
                # Unknown method
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

            # Return response if not a notification
            if not is_notification:
                response = {"jsonrpc": jsonrpc, "result": result, "id": req_id}
                self.logger.info(f"JSON-RPC response: {json.dumps(response)}")

                # After successful initialization, log that we're ready for more requests
                if method == "initialize" and "protocolVersion" in result:
                    self.logger.info("Initialization complete, ready for tools/list request")
                    # Log what we're expecting next
                    self.logger.info("Expecting client to send 'tools/list' request next")

                return response
            return None

        except Exception as e:
            self.logger.error(f"Error processing method {method}: {e}")
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

        # Log client info
        self.logger.info(f"Client info: {client_info}, requested protocol: {protocol_version}")

        # Store the protocol version for later use
        self._protocol_version = protocol_version

        return {
            "protocolVersion": protocol_version,  # Echo back the client's requested version
            "serverInfo": {"name": self.name, "version": self.version},
            "capabilities": {
                "tools": {"listChanged": True},  # Indicate tools can change
                "resources": {},  # Empty object instead of None
                "prompts": {},  # Empty object instead of None
            },
        }

    async def _jsonrpc_list_tools(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tools/list request"""
        tools = self.get_tools()
        self.logger.info(f"Available tools from get_tools(): {list(tools.keys())}")

        tool_list = []

        for tool_name, tool_info in tools.items():
            tool_list.append(
                {
                    "name": tool_name,
                    "description": tool_info.get("description", ""),
                    "inputSchema": tool_info.get("parameters", {}),
                }
            )

        self.logger.info(f"Returning {len(tool_list)} tools to client")
        return {"tools": tool_list}

    async def _jsonrpc_call_tool(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tools/call request"""
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        if not tool_name:
            raise ValueError("Tool name is required")

        # Get available tools
        tools = self.get_tools()
        if tool_name not in tools:
            raise ValueError(f"Tool '{tool_name}' not found")

        # Get the tool function
        tool_func = getattr(self, tool_name, None)
        if not tool_func:
            raise ValueError(f"Tool '{tool_name}' not implemented")

        # Execute the tool
        try:
            result = await tool_func(**arguments)

            # Convert result to MCP content format
            if isinstance(result, dict):
                content_text = json.dumps(result, indent=2)
            else:
                content_text = str(result)

            return {"content": [{"type": "text", "text": content_text}]}
        except Exception as e:
            self.logger.error(f"Error calling tool {tool_name}: {e}")
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

    async def mcp_info(self):
        """MCP server information"""
        return {
            "protocol": "mcp",
            "version": "1.0",
            "server": {
                "name": self.name,
                "version": self.version,
                "description": f"{self.name} MCP Server",
            },
            "auth": {
                "required": False,
                "type": "none",
            },
        }

    async def mcp_initialize(self, request: Dict[str, Any]):
        """Initialize MCP session"""
        client_info = request.get("client", {})
        return {
            "session_id": f"session-{client_info.get('name', 'unknown')}-{int(datetime.utcnow().timestamp())}",
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
            "server": {
                "name": self.name,
                "version": self.version,
                "tools_count": len(self.get_tools()),
            },
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
