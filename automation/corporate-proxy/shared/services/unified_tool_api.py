#!/usr/bin/env python3
"""
Unified Tool API - Configurable for all corporate proxy tools
Consolidates all mock API versions into a single, maintainable service
"""

import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List

from flask import Flask, jsonify, request

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuration from environment
API_MODE = os.getenv("API_MODE", "crush").lower()  # "crush" or "opencode"
API_VERSION = os.getenv("API_VERSION", "v3")  # v1, v2, or v3
DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"


# Tool Definitions with proper schemas
@dataclass
class ToolParameter:
    name: str
    type: str
    description: str
    required: bool = True


@dataclass
class Tool:
    name: str
    description: str
    parameters: List[ToolParameter]


# Define tools (shared between Crush and OpenCode with slight variations)
CRUSH_TOOLS = {
    "write": Tool(
        name="write",
        description="Write content to a file",
        parameters=[
            ToolParameter("filePath", "string", "Path to the file to write"),
            ToolParameter("content", "string", "Content to write to the file"),
        ],
    ),
    "view": Tool(
        name="view",
        description="View file contents with optional offset/limit",
        parameters=[
            ToolParameter("filePath", "string", "Path to the file to read"),
            ToolParameter("offset", "integer", "Line offset to start reading", required=False),
            ToolParameter("limit", "integer", "Number of lines to read", required=False),
        ],
    ),
    "bash": Tool(
        name="bash",
        description="Execute a shell command",
        parameters=[
            ToolParameter("command", "string", "Shell command to execute"),
            ToolParameter("timeout", "integer", "Timeout in seconds", required=False),
        ],
    ),
    "edit": Tool(
        name="edit",
        description="Edit a file by replacing content",
        parameters=[
            ToolParameter("filePath", "string", "Path to the file to edit"),
            ToolParameter("oldString", "string", "Content to replace"),
            ToolParameter("newString", "string", "New content to insert"),
            ToolParameter("replaceAll", "boolean", "Replace all occurrences", required=False),
        ],
    ),
    "ls": Tool(
        name="ls",
        description="List files in a directory",
        parameters=[
            ToolParameter("path", "string", "Directory path to list", required=False),
            ToolParameter("ignore", "array", "Patterns to ignore", required=False),
        ],
    ),
    "grep": Tool(
        name="grep",
        description="Search for patterns in files",
        parameters=[
            ToolParameter("pattern", "string", "Pattern to search for"),
            ToolParameter("path", "string", "Path to search in", required=False),
            ToolParameter("type", "string", "File type filter", required=False),
            ToolParameter("glob", "string", "Glob pattern for files", required=False),
            ToolParameter("outputMode", "string", "Output format (content/files/count)", required=False),
        ],
    ),
    "fetch": Tool(
        name="fetch",
        description="Fetch content from a URL",
        parameters=[
            ToolParameter("url", "string", "URL to fetch"),
            ToolParameter("timeout", "integer", "Timeout in seconds", required=False),
        ],
    ),
    "glob": Tool(
        name="glob",
        description="Find files matching a pattern",
        parameters=[
            ToolParameter("pattern", "string", "Glob pattern to match"),
            ToolParameter("path", "string", "Base path to search", required=False),
        ],
    ),
    "multi-edit": Tool(
        name="multi-edit",
        description="Edit multiple files in one operation",
        parameters=[
            ToolParameter("filePath", "string", "Path to the file to edit"),
            ToolParameter("edits", "array", "Array of edit operations"),
        ],
    ),
    "write-notebook": Tool(
        name="write-notebook",
        description="Write to Jupyter notebook cells",
        parameters=[
            ToolParameter("filePath", "string", "Path to the notebook file"),
            ToolParameter("cellId", "string", "Cell identifier"),
            ToolParameter("content", "string", "Content for the cell"),
            ToolParameter("editMode", "string", "Edit mode (replace/insert/delete)", required=False),
        ],
    ),
    "todo": Tool(
        name="todo",
        description="Manage todo list",
        parameters=[ToolParameter("todos", "array", "Array of todo items")],
    ),
    "task": Tool(
        name="task",
        description="Launch a task agent",
        parameters=[
            ToolParameter("description", "string", "Task description"),
            ToolParameter("prompt", "string", "Detailed task instructions"),
            ToolParameter("subagentType", "string", "Type of subagent", required=False),
        ],
    ),
}

# OpenCode uses the same tools but with different parameter naming conventions
OPENCODE_TOOLS = {
    name: Tool(
        name=tool.name,
        description=tool.description,
        parameters=[
            ToolParameter(
                # Convert camelCase to snake_case for OpenCode compatibility
                (
                    "file_path"
                    if p.name == "filePath"
                    else (
                        "old_string"
                        if p.name == "oldString"
                        else (
                            "new_string"
                            if p.name == "newString"
                            else (
                                "replace_all"
                                if p.name == "replaceAll"
                                else (
                                    "output_mode"
                                    if p.name == "outputMode"
                                    else (
                                        "cell_id"
                                        if p.name == "cellId"
                                        else (
                                            "edit_mode"
                                            if p.name == "editMode"
                                            else "subagent_type" if p.name == "subagentType" else p.name
                                        )
                                    )
                                )
                            )
                        )
                    )
                ),
                p.type,
                p.description,
                p.required,
            )
            for p in tool.parameters
        ],
    )
    for name, tool in CRUSH_TOOLS.items()
}


def get_active_tools() -> Dict[str, Tool]:
    """Get the appropriate tool set based on configuration"""
    if API_MODE == "opencode":
        return OPENCODE_TOOLS
    return CRUSH_TOOLS


def execute_tool(tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a tool with the given parameters"""
    logger.info(f"Executing tool: {tool_name} with parameters: {parameters}")

    # Mock execution - returns success with realistic responses
    if tool_name == "view":
        file_path = parameters.get("filePath") or parameters.get("file_path", "unknown")
        return {
            "success": True,
            "content": f"Content of {file_path}:\nThis is a mock file content.\nLine 2\nLine 3",
            "lineCount": 3,
        }
    elif tool_name == "write":
        file_path = parameters.get("filePath") or parameters.get("file_path", "unknown")
        return {"success": True, "message": f"Successfully wrote to {file_path}"}
    elif tool_name == "bash":
        command = parameters.get("command", "echo 'test'")
        return {"success": True, "output": f"Mock output from: {command}", "exitCode": 0}
    elif tool_name == "ls":
        return {
            "success": True,
            "files": ["file1.py", "file2.py", "README.md"],
            "directories": ["src", "tests", "docs"],
        }
    elif tool_name == "grep":
        return {"success": True, "matches": ["file1.py:10:matched line"], "matchCount": 1}
    elif tool_name == "glob":
        return {"success": True, "files": ["src/main.py", "src/utils.py"], "count": 2}
    elif tool_name == "fetch":
        return {"success": True, "content": "Mock webpage content", "statusCode": 200}
    elif tool_name == "edit":
        file_path = parameters.get("filePath") or parameters.get("file_path", "unknown")
        return {"success": True, "message": f"Successfully edited {file_path}"}
    elif tool_name == "multi-edit":
        return {"success": True, "message": "Applied all edits successfully", "editCount": 3}
    elif tool_name == "write-notebook":
        return {"success": True, "message": "Successfully updated notebook cell"}
    elif tool_name == "todo":
        return {"success": True, "message": "Todo list updated", "todoCount": 5}
    elif tool_name == "task":
        return {"success": True, "message": "Task launched successfully", "taskId": "task-123"}
    else:
        return {"success": False, "error": f"Unknown tool: {tool_name}"}


# API Routes
@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "mode": API_MODE, "version": API_VERSION, "timestamp": time.time()})


@app.route("/v1/tools", methods=["GET"])
@app.route("/v2/tools", methods=["GET"])
@app.route("/v3/tools", methods=["GET"])
@app.route("/tools", methods=["GET"])
def list_tools():
    """List available tools"""
    tools = get_active_tools()
    return jsonify(
        {
            "tools": [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": [
                        {
                            "name": p.name,
                            "type": p.type,
                            "description": p.description,
                            "required": p.required,
                        }
                        for p in tool.parameters
                    ],
                }
                for tool in tools.values()
            ]
        }
    )


@app.route("/v1/execute", methods=["POST"])
@app.route("/v2/execute", methods=["POST"])
@app.route("/v3/execute", methods=["POST"])
@app.route("/execute", methods=["POST"])
def execute():
    """Execute a tool"""
    data = request.json
    tool_name = data.get("tool")
    parameters = data.get("parameters", {})

    # Log the request if in debug mode
    if DEBUG_MODE:
        logger.debug(f"Execute request: tool={tool_name}, params={parameters}")

    # Validate tool exists
    tools = get_active_tools()
    if tool_name not in tools:
        return jsonify({"error": f"Unknown tool: {tool_name}"}), 400

    # Execute the tool
    result = execute_tool(tool_name, parameters)

    # Return result
    if result.get("success"):
        return jsonify(result)
    else:
        return jsonify(result), 500


@app.route("/v1/chat/completions", methods=["POST"])
@app.route("/v2/chat/completions", methods=["POST"])
@app.route("/v3/chat/completions", methods=["POST"])
@app.route("/chat/completions", methods=["POST"])
def chat_completions():
    """OpenAI-compatible chat completions endpoint with tools"""
    data = request.json
    # messages = data.get("messages", [])  # Reserved for future use
    tools = data.get("tools", [])

    # Simple mock response that includes tool calls
    response = {
        "id": "chatcmpl-mock123",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": f"mock-{API_MODE}-model",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "I'll help you with that task.",
                    "tool_calls": (
                        [
                            {
                                "id": "call_abc123",
                                "type": "function",
                                "function": {
                                    "name": "view",
                                    "arguments": json.dumps({"filePath": "test.py"}),
                                },
                            }
                        ]
                        if tools
                        else None
                    ),
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
    }

    # Remove tool_calls if no tools were provided
    if not tools:
        response["choices"][0]["message"].pop("tool_calls", None)

    return jsonify(response)


@app.route("/", methods=["GET"])
def index():
    """Root endpoint with API info"""
    return jsonify(
        {
            "service": "Unified Tool API",
            "mode": API_MODE,
            "version": API_VERSION,
            "endpoints": {
                "/health": "Health check",
                "/tools": "List available tools",
                "/execute": "Execute a tool",
                "/chat/completions": "OpenAI-compatible chat endpoint",
                "/v1/*": "Version 1 endpoints",
                "/v2/*": "Version 2 endpoints",
                "/v3/*": "Version 3 endpoints",
            },
            "configuration": {
                "API_MODE": "Set to 'crush' or 'opencode'",
                "API_VERSION": "Set to 'v1', 'v2', or 'v3'",
                "DEBUG_MODE": "Set to 'true' for verbose logging",
            },
        }
    )


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    host = os.getenv("HOST", "0.0.0.0")

    logger.info(f"Starting Unified Tool API in {API_MODE} mode (version {API_VERSION})")
    logger.info(f"Listening on {host}:{port}")
    logger.info(f"Debug mode: {DEBUG_MODE}")

    app.run(host=host, port=port, debug=DEBUG_MODE)
