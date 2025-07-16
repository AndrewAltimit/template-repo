#!/usr/bin/env python3
"""
Gemini MCP Server - HTTP version for testing and development
This is a simplified HTTP-based server. For production, use the stdio version.
"""
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel


# Check if running in container BEFORE any other imports or operations
def check_container_and_exit():
    """Check if running in a container and exit immediately if true."""
    if os.path.exists("/.dockerenv") or os.environ.get("CONTAINER_ENV"):
        print("ERROR: Gemini MCP Server cannot run inside a container!", file=sys.stderr)
        print(
            "The Gemini CLI requires Docker access and must run on the host system.",
            file=sys.stderr,
        )
        print("Please launch this server directly on the host with:", file=sys.stderr)
        print("  python tools/mcp/gemini_mcp_server_http.py", file=sys.stderr)
        sys.exit(1)


# Perform container check immediately
check_container_and_exit()

# Import Gemini integration after container check
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from tools.gemini.gemini_integration import GeminiIntegration  # noqa: E402

app = FastAPI(title="Gemini MCP Server (HTTP)", version="1.0.0")

# Initialize Gemini integration
gemini = GeminiIntegration()


class ConsultGeminiRequest(BaseModel):
    prompt: str
    context: Optional[Dict[str, Any]] = None
    max_retries: Optional[int] = 3


class ConsultGeminiResponse(BaseModel):
    response: str
    conversation_id: str
    timestamp: str


class ClearHistoryResponse(BaseModel):
    message: str
    cleared_count: int


@app.get("/")
async def root():
    """Root endpoint providing server information."""
    return {
        "name": "Gemini MCP Server (HTTP)",
        "version": "1.0.0",
        "description": "HTTP-based MCP server for Gemini CLI integration (testing/development)",
        "status": "running",
        "note": "This server must run on the host system, not in a container",
        "recommendation": "For production, use the stdio version without --port argument",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


@app.post("/tools/consult_gemini", response_model=ConsultGeminiResponse)
async def consult_gemini(request: ConsultGeminiRequest):
    """
    Consult Gemini AI for assistance with a given prompt.

    This tool uses the Gemini CLI which requires Docker access,
    so it must run on the host system.
    """
    try:
        # Use the existing GeminiIntegration
        # Convert context dict to JSON string if provided
        context_str = ""
        if request.context:
            context_str = json.dumps(request.context, indent=2)

        result = await gemini.consult_gemini(
            request.prompt,
            context=context_str,
            comparison_mode=True,
            force_consult=False,
        )

        return ConsultGeminiResponse(
            response=result.get("response", ""),
            conversation_id=result.get("consultation_id", ""),
            timestamp=result.get("timestamp", datetime.utcnow().isoformat()),
        )
    except subprocess.CalledProcessError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Gemini CLI command failed: {e.stderr if hasattr(e, 'stderr') else str(e)}",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/clear_gemini_history", response_model=ClearHistoryResponse)
async def clear_gemini_history():
    """
    Clear Gemini conversation history for fresh responses.

    This is useful when you want to start a new conversation context
    without influence from previous interactions.
    """
    try:
        result = gemini.clear_conversation_history()
        cleared_count = result.get("cleared_entries", 0)

        return ClearHistoryResponse(
            message="Gemini conversation history cleared successfully",
            cleared_count=cleared_count,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/mcp/tools")
async def list_tools():
    """List available MCP tools provided by this server."""
    return {
        "tools": [
            {
                "name": "consult_gemini",
                "description": "Consult Gemini AI for assistance (requires host execution)",
                "input_schema": ConsultGeminiRequest.schema(),
            },
            {
                "name": "clear_gemini_history",
                "description": "Clear Gemini conversation history",
                "input_schema": {},
            },
        ]
    }


def run_http_server(port: int):
    """Run the HTTP server"""
    host = os.environ.get("GEMINI_MCP_HOST", "127.0.0.1")

    print(f"Starting Gemini MCP Server (HTTP mode) on {host}:{port}")
    print("NOTE: This server must run on the host system, not in a container")
    print("WARNING: HTTP mode is for testing only. Use stdio mode for production.")

    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    # Default to port 8006 for HTTP mode
    port = int(os.environ.get("GEMINI_MCP_PORT", "8006"))
    run_http_server(port)
