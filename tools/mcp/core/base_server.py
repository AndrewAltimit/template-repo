"""Base MCP Server implementation with common functionality"""

import asyncio
import json  # noqa: F401
import logging
import os  # noqa: F401
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional  # noqa: F401

import mcp.server.stdio
import mcp.types as types  # noqa: F401
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel


class ToolRequest(BaseModel):
    """Model for tool execution requests"""

    tool: str
    arguments: Dict[str, Any]


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
        self._setup_routes()

    def _setup_routes(self):
        """Setup common HTTP routes"""
        self.app.get("/health")(self.health_check)
        self.app.get("/mcp/tools")(self.list_tools)
        self.app.post("/mcp/execute")(self.execute_tool)

    async def health_check(self):
        """Health check endpoint"""
        return {"status": "healthy", "server": self.name, "version": self.version}

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

            # Get the tool function
            tool_func = getattr(self, request.tool, None)
            if not tool_func:
                raise HTTPException(status_code=501, detail=f"Tool '{request.tool}' not implemented")

            # Execute the tool
            result = await tool_func(**request.arguments)

            return ToolResponse(success=True, result=result)

        except Exception as e:
            self.logger.error(f"Error executing tool {request.tool}: {str(e)}")
            return ToolResponse(success=False, result=None, error=str(e))

    @abstractmethod
    def get_tools(self) -> Dict[str, Dict[str, Any]]:
        """Return dictionary of available tools and their metadata"""
        pass

    async def run_stdio(self):
        """Run the server in stdio mode (for Claude desktop app)"""
        server = mcp.server.Server(self.name)

        # Register all tools
        tools = self.get_tools()
        for tool_name, tool_info in tools.items():
            tool_func = getattr(self, tool_name, None)
            if tool_func:

                @server.tool(
                    name=tool_name,
                    description=tool_info.get("description", ""),
                    input_schema=tool_info.get("parameters", {}),
                )
                async def handler(arguments: dict, func=tool_func):
                    return await func(**arguments)

        # Run the stdio server
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())

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
