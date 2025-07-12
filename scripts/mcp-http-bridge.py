#!/usr/bin/env python3
"""
MCP HTTP Bridge
Forwards MCP requests to remote MCP servers
"""

import logging
import os
from typing import Any, Dict

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="MCP HTTP Bridge")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
REMOTE_MCP_URL = os.getenv("REMOTE_MCP_URL", "http://localhost:8000")
SERVICE_NAME = os.getenv("SERVICE_NAME", "mcp-bridge")
TIMEOUT = int(os.getenv("TIMEOUT", "30"))


class MCPRequest(BaseModel):
    """MCP request model"""

    method: str
    params: Dict[str, Any] = {}


class MCPResponse(BaseModel):
    """MCP response model"""

    result: Any
    error: Dict[str, Any] = None


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": f"{SERVICE_NAME} MCP HTTP Bridge",
        "remote_url": REMOTE_MCP_URL,
        "status": "active",
    }


@app.get("/health")
async def health():
    """Health check endpoint"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{REMOTE_MCP_URL}/health", timeout=5.0)

        return {"status": "healthy", "remote_status": response.status_code == 200}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


@app.post("/mcp")
async def handle_mcp_request(request: MCPRequest) -> MCPResponse:
    """Forward MCP request to remote server"""
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            # Forward the request
            response = await client.post(f"{REMOTE_MCP_URL}/mcp", json=request.dict())

            # Check response
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Remote server error: {response.text}",
                )

            # Return response
            return MCPResponse(**response.json())

    except httpx.TimeoutException:
        logger.error(f"Timeout forwarding request to {REMOTE_MCP_URL}")
        return MCPResponse(
            result=None,
            error={
                "code": -32000,
                "message": "Request timeout",
                "data": {"remote_url": REMOTE_MCP_URL},
            },
        )
    except httpx.RequestError as e:
        logger.error(f"Error forwarding request: {e}")
        return MCPResponse(
            result=None,
            error={
                "code": -32000,
                "message": "Network error",
                "data": {"error": str(e)},
            },
        )
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return MCPResponse(
            result=None,
            error={
                "code": -32603,
                "message": "Internal error",
                "data": {"error": str(e)},
            },
        )


@app.post("/tools/list")
async def list_tools():
    """List available tools from remote server"""
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.get(f"{REMOTE_MCP_URL}/tools")

            if response.status_code == 200:
                return response.json()
            else:
                raise HTTPException(status_code=response.status_code, detail="Failed to list tools")
    except Exception as e:
        logger.error(f"Error listing tools: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/execute")
async def execute_tool(tool_name: str, arguments: Dict[str, Any] = {}):
    """Execute a tool on the remote server"""
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.post(
                f"{REMOTE_MCP_URL}/tools/execute",
                json={"tool": tool_name, "arguments": arguments},
            )

            if response.status_code == 200:
                return response.json()
            else:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Tool execution failed: {response.text}",
                )
    except Exception as e:
        logger.error(f"Error executing tool {tool_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    # Determine port based on service
    port_map = {"comfyui": 8189, "ai-toolkit": 8190, "mcp-bridge": 8191}

    port = port_map.get(SERVICE_NAME, 8191)

    logger.info(f"Starting {SERVICE_NAME} MCP HTTP Bridge")
    logger.info(f"Forwarding to: {REMOTE_MCP_URL}")
    logger.info(f"Listening on port: {port}")

    uvicorn.run(app, host="0.0.0.0", port=port)
