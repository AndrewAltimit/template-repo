#!/usr/bin/env python3
"""
Unified Tool API - Configurable for all corporate proxy tools
Consolidates all mock API versions into a single, maintainable service
"""

from dataclasses import dataclass
import json
import logging
import os
import time
from typing import Any, Dict, List

from flask import Flask, jsonify, request

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuration from environment
API_MODE = os.getenv("API_MODE", "crush").lower()  # "crush", "opencode", or "gemini"
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


def camel_to_snake_case(param_name: str) -> str:
    """Convert camelCase parameter names to snake_case for OpenCode compatibility.

    This maintains a clear mapping between Crush tools (camelCase) and
    OpenCode tools (snake_case), ensuring consistency across both toolsets.
    """
    # Define explicit mappings for clarity
    param_mappings = {
        "filePath": "file_path",
        "oldString": "old_string",
        "newString": "new_string",
        "replaceAll": "replace_all",
        "outputMode": "output_mode",
        "cellId": "cell_id",
        "editMode": "edit_mode",
        "subagentType": "subagent_type",
    }

    # Return mapped name or original if not in mapping
    return param_mappings.get(param_name, param_name)


# OpenCode uses the same tools but with different parameter naming conventions
# Generate OPENCODE_TOOLS by converting CRUSH_TOOLS parameter names
OPENCODE_TOOLS = {
    name: Tool(
        name=tool.name,
        description=tool.description,
        parameters=[
            ToolParameter(
                camel_to_snake_case(p.name),  # Convert parameter naming convention
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
    logger.info("Executing tool: %s with parameters: %s", tool_name, parameters)

    # Mock execution - returns success with realistic responses
    if tool_name == "view":
        file_path = parameters.get("filePath") or parameters.get("file_path", "unknown")
        return {
            "success": True,
            "content": f"Content of {file_path}:\nThis is a mock file content.\nLine 2\nLine 3",
            "lineCount": 3,
        }
    if tool_name == "write":
        file_path = parameters.get("filePath") or parameters.get("file_path", "unknown")
        return {"success": True, "message": f"Successfully wrote to {file_path}"}
    if tool_name == "bash":
        command = parameters.get("command", "echo 'test'")
        return {"success": True, "output": f"Mock output from: {command}", "exitCode": 0}
    if tool_name == "ls":
        return {
            "success": True,
            "files": ["file1.py", "file2.py", "README.md"],
            "directories": ["src", "tests", "docs"],
        }
    if tool_name == "grep":
        return {"success": True, "matches": ["file1.py:10:matched line"], "matchCount": 1}
    if tool_name == "glob":
        return {"success": True, "files": ["src/main.py", "src/utils.py"], "count": 2}
    if tool_name == "fetch":
        return {"success": True, "content": "Mock webpage content", "statusCode": 200}
    if tool_name == "edit":
        file_path = parameters.get("filePath") or parameters.get("file_path", "unknown")
        return {"success": True, "message": f"Successfully edited {file_path}"}
    if tool_name == "multi-edit":
        return {"success": True, "message": "Applied all edits successfully", "editCount": 3}
    if tool_name == "write-notebook":
        return {"success": True, "message": "Successfully updated notebook cell"}
    if tool_name == "todo":
        return {"success": True, "message": "Todo list updated", "todoCount": 5}
    if tool_name == "task":
        return {"success": True, "message": "Task launched successfully", "taskId": "task-123"}
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
        logger.debug("Execute request: tool=%s, params=%s", tool_name, parameters)

    # Validate tool exists
    tools = get_active_tools()
    if tool_name not in tools:
        return jsonify({"error": f"Unknown tool: {tool_name}"}), 400

    # Execute the tool
    result = execute_tool(tool_name, parameters)

    # Return result
    if result.get("success"):
        return jsonify(result)
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


@app.route("/api/v1/AI/GenAIExplorationLab/Models/<path:model_path>", methods=["POST"])
def bedrock_endpoint(_model_path):
    """Bedrock-compatible endpoint that returns structured tool calls for Gemini mode"""
    data = request.json
    tools_present = "tools" in data or (
        "messages" in data and any(msg.get("role") == "assistant" and "tool_calls" in msg for msg in data.get("messages", []))
    )

    # For Gemini mode, we need to be more selective about when to return tool calls
    # Only return tool calls if the user is explicitly asking for tool usage
    if API_MODE == "gemini":
        # Check if the last user message mentions using tools or performing actions
        messages = data.get("messages", [])
        last_user_msg = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                last_user_msg = msg.get("content", "").lower()
                break

        # Check if this is a JSON generation request (Gemini CLI internal use)
        # These requests typically ask for JSON output explicitly or analyze responses
        is_json_request = (
            "json" in last_user_msg
            or ("return" in last_user_msg and "{" in last_user_msg)
            or "analyze" in last_user_msg
            and "who should" in last_user_msg
            or "decision rules" in last_user_msg
        )

        if is_json_request:
            # Return a simple JSON response for Gemini CLI's internal operations
            response = {
                "id": "msg_gemini_json",
                "type": "message",
                "role": "assistant",
                "model": "gemini-mock",
                "content": [{"type": "text", "text": '{"response": "continue", "shouldContinue": false}'}],
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 10, "output_tokens": 5},
            }
        elif tools_present:
            # Heuristic to simulate LLM tool-use reasoning in mock mode.
            # Only trigger tool calls for prompts containing action-oriented keywords.
            # This prevents false positives for simple conversational requests.
            action_keywords = [
                "read",
                "write",
                "search",
                "list",
                "run",
                "execute",
                "show",
                "find",
                "create",
                "delete",
                "check",
            ]
            should_use_tools = any(keyword in last_user_msg for keyword in action_keywords)

            if should_use_tools:
                # Return a response with structured tool_calls
                response = {
                    "id": "msg_gemini_mock",
                    "type": "message",
                    "role": "assistant",
                    "model": "gemini-mock",
                    "content": [{"type": "text", "text": "I'll help you with that using the appropriate tool."}],
                    "tool_calls": [
                        {
                            "id": "toolu_gemini_001",
                            "type": "function",
                            "function": {"name": "read_file", "arguments": json.dumps({"path": "test.py"})},
                        }
                    ],
                    "stop_reason": "tool_use",
                    "usage": {"input_tokens": 10, "output_tokens": 5},
                }
            else:
                # Return conversational response without tool calls
                response = {
                    "id": "msg_gemini_text",
                    "type": "message",
                    "role": "assistant",
                    "model": "gemini-mock",
                    "content": [
                        {"type": "text", "text": "Hello! I'm Gemini running through a mock API. How can I help you today?"}
                    ],
                    "stop_reason": "end_turn",
                    "usage": {"input_tokens": 10, "output_tokens": 12},
                }
        else:
            # Return conversational response for non-tool requests
            response = {
                "id": "msg_gemini_text",
                "type": "message",
                "role": "assistant",
                "model": "gemini-mock",
                "content": [
                    {"type": "text", "text": "Hello! I'm Gemini running through a mock API. How can I help you today?"}
                ],
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 10, "output_tokens": 12},
            }
    else:
        # Return simple text response for non-Gemini modes
        response = {
            "id": "msg_gemini_text",
            "type": "message",
            "role": "assistant",
            "model": "gemini-mock",
            "content": [{"type": "text", "text": "Hello! I'm running through a mock API. How can I help you today?"}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 10, "output_tokens": 12},
        }

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
                "/api/v1/AI/GenAIExplorationLab/Models/*": "Bedrock-compatible endpoint",
                "/v1/*": "Version 1 endpoints",
                "/v2/*": "Version 2 endpoints",
                "/v3/*": "Version 3 endpoints",
            },
            "configuration": {
                "API_MODE": "Set to 'crush', 'opencode', or 'gemini'",
                "API_VERSION": "Set to 'v1', 'v2', or 'v3'",
                "DEBUG_MODE": "Set to 'true' for verbose logging",
            },
        }
    )


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    host = os.getenv("HOST", "0.0.0.0")

    logger.info("Starting Unified Tool API in %s mode (version %s)", API_MODE, API_VERSION)
    logger.info("Listening on %s:%d", host, port)
    logger.info("Debug mode: %s", DEBUG_MODE)

    app.run(host=host, port=port, debug=DEBUG_MODE)
