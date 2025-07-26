"""HTTP Bridge for forwarding MCP requests to remote servers"""

import logging
import os
from typing import Any, Dict, Optional

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


class MCPRequest(BaseModel):
    """MCP request model"""

    method: str
    params: Dict[str, Any] = {}


class MCPResponse(BaseModel):
    """MCP response model"""

    result: Any
    error: Optional[Dict[str, Any]] = None


class ToolRequest(BaseModel):
    """Tool execution request"""

    tool: str
    arguments: Dict[str, Any] = {}


class HTTPBridge:
    """HTTP Bridge for forwarding requests to remote MCP servers"""

    def __init__(
        self,
        service_name: str,
        remote_url: str,
        port: int,
        timeout: int = 30,
        enable_cors: bool = True,
    ):
        self.service_name = service_name
        self.remote_url = remote_url
        self.port = port
        self.timeout = timeout
        self.logger = logging.getLogger(f"HTTPBridge.{service_name}")

        # Create FastAPI app
        self.app = FastAPI(title=f"{service_name} MCP HTTP Bridge")

        # Add CORS if enabled
        if enable_cors:
            self.app.add_middleware(
                CORSMiddleware,
                allow_origins=["*"],
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"],
            )

        # Setup routes
        self._setup_routes()

    def _setup_routes(self):
        """Setup HTTP routes"""
        self.app.get("/")(self.root)
        self.app.get("/health")(self.health)
        self.app.post("/mcp")(self.handle_mcp_request)
        self.app.get("/mcp/tools")(self.list_tools)
        self.app.post("/mcp/execute")(self.execute_tool)

    async def root(self):
        """Root endpoint"""
        return {
            "service": f"{self.service_name} MCP HTTP Bridge",
            "remote_url": self.remote_url,
            "status": "active",
        }

    async def health(self):
        """Health check endpoint"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.remote_url}/health", timeout=5.0)

            return {"status": "healthy", "remote_status": response.status_code == 200}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}

    async def handle_mcp_request(self, request: MCPRequest) -> MCPResponse:
        """Forward MCP request to remote server"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(f"{self.remote_url}/mcp", json=request.dict())

                if response.status_code != 200:
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=f"Remote server error: {response.text}",
                    )

                return MCPResponse(**response.json())

        except httpx.TimeoutException:
            self.logger.error(f"Timeout forwarding request to {self.remote_url}")
            return MCPResponse(
                result=None,
                error={
                    "code": -32000,
                    "message": "Request timeout",
                    "data": {"remote_url": self.remote_url},
                },
            )
        except httpx.RequestError as e:
            self.logger.error(f"Error forwarding request: {e}")
            return MCPResponse(
                result=None,
                error={
                    "code": -32000,
                    "message": "Network error",
                    "data": {"error": str(e)},
                },
            )
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}")
            return MCPResponse(
                result=None,
                error={
                    "code": -32603,
                    "message": "Internal error",
                    "data": {"error": str(e)},
                },
            )

    async def list_tools(self):
        """List available tools from remote server"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.remote_url}/mcp/tools")

                if response.status_code == 200:
                    return response.json()
                else:
                    raise HTTPException(status_code=response.status_code, detail="Failed to list tools")
        except Exception as e:
            self.logger.error(f"Error listing tools: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    async def execute_tool(self, request: ToolRequest):
        """Execute a tool on the remote server"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(f"{self.remote_url}/mcp/execute", json=request.dict())

                if response.status_code == 200:
                    return response.json()
                else:
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=f"Tool execution failed: {response.text}",
                    )
        except Exception as e:
            self.logger.error(f"Error executing tool {request.tool}: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    def run(self):
        """Run the HTTP bridge server"""
        import uvicorn

        self.logger.info(f"Starting {self.service_name} MCP HTTP Bridge")
        self.logger.info(f"Forwarding to: {self.remote_url}")
        self.logger.info(f"Listening on port: {self.port}")

        uvicorn.run(self.app, host="0.0.0.0", port=self.port)


def create_bridge_from_env(service_name: str, default_port: int = 8191) -> HTTPBridge:
    """Create an HTTP bridge from environment variables

    Environment variables:
        REMOTE_MCP_URL: Remote MCP server URL
        TIMEOUT: Request timeout in seconds
        PORT: Port to listen on (optional)
    """
    remote_url = os.getenv("REMOTE_MCP_URL", "http://localhost:8000")
    timeout = int(os.getenv("TIMEOUT", "30"))
    port = int(os.getenv("PORT", str(default_port)))

    return HTTPBridge(service_name=service_name, remote_url=remote_url, port=port, timeout=timeout)


if __name__ == "__main__":
    import argparse

    # Setup argument parser
    parser = argparse.ArgumentParser(description="HTTP Bridge for MCP servers")
    parser.add_argument("--service-name", default="MCP", help="Service name for the bridge")
    parser.add_argument("--remote-url", required=True, help="Remote MCP server URL")
    parser.add_argument("--port", type=int, default=8191, help="Port to listen on")
    parser.add_argument("--timeout", type=int, default=30, help="Request timeout in seconds")
    parser.add_argument("--no-cors", action="store_true", help="Disable CORS")

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(level=logging.INFO)

    # Create and run bridge
    bridge = HTTPBridge(
        service_name=args.service_name,
        remote_url=args.remote_url,
        port=args.port,
        timeout=args.timeout,
        enable_cors=not args.no_cors,
    )

    bridge.run()
