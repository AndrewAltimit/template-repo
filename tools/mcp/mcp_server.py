#!/usr/bin/env python3
"""
MCP Server - Model Context Protocol Server
Provides various tools for development, AI assistance, and content creation
"""

import asyncio
import json
import logging
import os
import subprocess
import tempfile
from typing import Any, Dict, Optional

import mcp.server.stdio
import mcp.types as types
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="MCP Server", version="1.0.0")


class ToolRequest(BaseModel):
    tool: str
    arguments: Dict[str, Any]


class ToolResponse(BaseModel):
    success: bool
    result: Any
    error: Optional[str] = None


class MCPTools:
    """Collection of MCP tools"""

    @staticmethod
    async def format_check(path: str, language: str = "python") -> Dict[str, Any]:
        """Check code formatting"""
        formatters = {
            "python": ["black", "--check", path],
            "javascript": ["prettier", "--check", path],
            "typescript": ["prettier", "--check", path],
            "go": ["gofmt", "-l", path],
            "rust": ["rustfmt", "--check", path],
        }

        if language not in formatters:
            return {"error": f"Unsupported language: {language}"}

        try:
            result = subprocess.run(formatters[language], capture_output=True, text=True)
            return {
                "formatted": result.returncode == 0,
                "output": result.stdout or result.stderr,
            }
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    async def lint(path: str, config: Optional[str] = None) -> Dict[str, Any]:
        """Run code linting"""
        cmd = ["flake8", path]
        if config:
            cmd.extend(["--config", config])

        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            return {
                "success": result.returncode == 0,
                "issues": result.stdout.splitlines() if result.stdout else [],
            }
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    async def create_manim_animation(script: str, output_format: str = "mp4") -> Dict[str, Any]:
        """Create Manim animation from script"""
        try:
            # Create temporary file for script
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
                f.write(script)
                script_path = f.name

            # Output path
            output_dir = "/app/output/manim"
            os.makedirs(output_dir, exist_ok=True)

            # Run Manim
            cmd = [
                "manim",
                "-qm",
                "-f",
                output_format,
                "--output_dir",
                output_dir,
                script_path,
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)

            # Clean up
            os.unlink(script_path)

            if result.returncode == 0:
                # Find output file
                output_files = [f for f in os.listdir(output_dir) if f.endswith(f".{output_format}")]
                if output_files:
                    return {
                        "success": True,
                        "output_path": os.path.join(output_dir, output_files[0]),
                        "format": output_format,
                    }

            return {
                "success": False,
                "error": result.stderr or "Animation creation failed",
            }
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    async def compile_latex(content: str, format: str = "pdf") -> Dict[str, Any]:
        """Compile LaTeX document"""
        try:
            # Create temporary directory
            with tempfile.TemporaryDirectory() as tmpdir:
                # Write LaTeX file
                tex_file = os.path.join(tmpdir, "document.tex")
                with open(tex_file, "w") as f:
                    f.write(content)

                # Compile based on format
                if format == "pdf":
                    cmd = ["pdflatex", "-interaction=nonstopmode", tex_file]
                elif format == "dvi":
                    cmd = ["latex", "-interaction=nonstopmode", tex_file]
                elif format == "ps":
                    cmd = ["latex", "-interaction=nonstopmode", tex_file]
                else:
                    return {"error": f"Unsupported format: {format}"}

                # Run compilation (twice for references)
                for _ in range(2):
                    result = subprocess.run(cmd, cwd=tmpdir, capture_output=True, text=True)

                # Convert DVI to PS if needed
                if format == "ps" and result.returncode == 0:
                    dvi_file = os.path.join(tmpdir, "document.dvi")
                    ps_file = os.path.join(tmpdir, "document.ps")
                    subprocess.run(["dvips", dvi_file, "-o", ps_file])

                # Check for output
                output_file = os.path.join(tmpdir, f"document.{format}")
                if os.path.exists(output_file):
                    # Copy to output directory
                    output_dir = "/app/output/latex"
                    os.makedirs(output_dir, exist_ok=True)

                    import shutil

                    output_path = os.path.join(output_dir, f"document_{os.getpid()}.{format}")
                    shutil.copy(output_file, output_path)

                    return {
                        "success": True,
                        "output_path": output_path,
                        "format": format,
                    }

                return {
                    "success": False,
                    "error": result.stderr or "Compilation failed",
                }
        except Exception as e:
            return {"error": str(e)}


# Tool registry
TOOLS = {
    "format_check": MCPTools.format_check,
    "lint": MCPTools.lint,
    "create_manim_animation": MCPTools.create_manim_animation,
    "compile_latex": MCPTools.compile_latex,
}


@app.get("/")
async def root():
    """Root endpoint"""
    return {"name": "MCP Server", "version": "1.0.0", "tools": list(TOOLS.keys())}


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.post("/tools/execute", response_model=ToolResponse)
async def execute_tool(request: ToolRequest):
    """Execute a tool"""
    if request.tool not in TOOLS:
        raise HTTPException(status_code=404, detail=f"Tool not found: {request.tool}")

    try:
        result = await TOOLS[request.tool](**request.arguments)
        return ToolResponse(success=True, result=result)
    except Exception as e:
        logger.error(f"Tool execution failed: {str(e)}")
        return ToolResponse(success=False, result=None, error=str(e))


@app.get("/tools")
async def list_tools():
    """List available tools"""
    tools_info = {}
    for name, func in TOOLS.items():
        tools_info[name] = {
            "name": name,
            "description": func.__doc__.strip() if func.__doc__ else "No description",
            "parameters": {},  # Could be enhanced with parameter inspection
        }
    return tools_info


async def serve_mcp():
    """Serve MCP protocol"""
    server = mcp.server.Server("mcp-server")

    @server.list_tools()
    async def handle_list_tools() -> list[types.Tool]:
        tools = []
        for name, func in TOOLS.items():
            tools.append(
                types.Tool(
                    name=name,
                    description=(func.__doc__.strip() if func.__doc__ else "No description"),
                    inputSchema={
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                )
            )
        return tools

    @server.call_tool()
    async def handle_call_tool(name: str, arguments: dict) -> list[types.TextContent]:
        if name not in TOOLS:
            return [types.TextContent(type="text", text=f"Tool not found: {name}")]

        try:
            result = await TOOLS[name](**arguments)
            return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
        except Exception as e:
            return [types.TextContent(type="text", text=f"Error: {str(e)}")]

    # Run the server
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import sys

    if "--mcp" in sys.argv:
        # Run as MCP server
        asyncio.run(serve_mcp())
    else:
        # Run as HTTP API
        import uvicorn

        uvicorn.run(
            app,
            host=os.getenv("MCP_SERVER_HOST", "0.0.0.0"),
            port=int(os.getenv("MCP_SERVER_PORT", "8000")),
        )
