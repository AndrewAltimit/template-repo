#!/usr/bin/env python3
"""
Structured Tool API - Implements Gemini's recommendation for proper tool handling
instead of regex-based pattern matching.
"""

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from flask import Flask, jsonify, request

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)


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


# Define available tools with clear schemas
AVAILABLE_TOOLS = {
    "write": Tool(
        name="write",
        description="Write content to a file",
        parameters=[
            ToolParameter("filePath", "string", "Path to the file to write"),
            ToolParameter("content", "string", "Content to write to the file"),
        ],
    ),
    "read": Tool(
        name="read",
        description="Read content from a file",
        parameters=[ToolParameter("filePath", "string", "Path to the file to read")],
    ),
    "bash": Tool(
        name="bash",
        description="Execute a shell command",
        parameters=[
            ToolParameter("command", "string", "Shell command to execute"),
            ToolParameter("description", "string", "Description of what the command does", required=False),
        ],
    ),
    "edit": Tool(
        name="edit",
        description="Edit a file by replacing content",
        parameters=[
            ToolParameter("filePath", "string", "Path to the file to edit"),
            ToolParameter("oldContent", "string", "Content to replace"),
            ToolParameter("newContent", "string", "New content to insert"),
        ],
    ),
    "list": Tool(
        name="list",
        description="List files in a directory",
        parameters=[ToolParameter("path", "string", "Directory path to list", required=False)],
    ),
    "grep": Tool(
        name="grep",
        description="Search for patterns in files",
        parameters=[
            ToolParameter("pattern", "string", "Pattern to search for"),
            ToolParameter("path", "string", "Path to search in", required=False),
        ],
    ),
}


class StructuredToolHandler:
    """Handles tool detection and execution using structured approach."""

    def __init__(self):
        self.tools = AVAILABLE_TOOLS

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """Get tool schemas in OpenAI format."""
        schemas = []
        for tool_name, tool in self.tools.items():
            schema = {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            }

            for param in tool.parameters:
                schema["function"]["parameters"]["properties"][param.name] = {
                    "type": param.type,
                    "description": param.description,
                }
                if param.required:
                    schema["function"]["parameters"]["required"].append(param.name)

            schemas.append(schema)
        return schemas

    def parse_natural_language(self, message: str, available_tools: List[str]) -> Optional[Dict[str, Any]]:
        """
        Parse natural language to structured tool call.
        This is a simplified version - in production, you'd use an LLM with tool-use capabilities.
        """
        message_lower = message.lower()

        # Simple keyword-based detection for demonstration
        # In production, this would be replaced with LLM tool-use API
        if any(word in message_lower for word in ["write", "create", "save"]) and "write" in available_tools:
            # Extract file path and content
            parts = message.split(" with ", 1)
            if len(parts) == 2:
                file_part = parts[0]
                content = parts[1]

                # Extract filename
                import re

                file_match = re.search(r"(?:file|called|named)\s+([^\s]+)", file_part)
                if file_match:
                    return {
                        "tool": "write",
                        "arguments": {"filePath": file_match.group(1).strip("\"'"), "content": content.strip("\"'")},
                    }

        elif any(word in message_lower for word in ["read", "view", "show", "cat"]) and "read" in available_tools:
            import re

            file_match = re.search(r"(?:read|view|show|cat)\s+([^\s]+)", message, re.IGNORECASE)
            if file_match:
                return {"tool": "read", "arguments": {"filePath": file_match.group(1).strip("\"'")}}

        elif any(word in message_lower for word in ["run", "execute", "bash"]) and "bash" in available_tools:
            import re

            cmd_match = re.search(r'(?:run|execute|bash)\s+["\']?(.+?)["\']?$', message, re.IGNORECASE)
            if cmd_match:
                return {"tool": "bash", "arguments": {"command": cmd_match.group(1).strip("\"'")}}

        elif any(word in message_lower for word in ["list", "ls", "dir"]) and "list" in available_tools:
            return {"tool": "list", "arguments": {"path": "."}}

        return None

    def validate_tool_call(self, tool_name: str, arguments: Dict[str, Any]) -> tuple[bool, str]:
        """Validate that a tool call has the required parameters."""
        if tool_name not in self.tools:
            return False, f"Unknown tool: {tool_name}"

        tool = self.tools[tool_name]

        # Check required parameters
        for param in tool.parameters:
            if param.required and param.name not in arguments:
                return False, f"Missing required parameter: {param.name}"

        return True, "Valid"


handler = StructuredToolHandler()


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({"status": "healthy", "service": "structured-tool-api"}), 200


@app.route("/v1/chat/completions", methods=["POST"])
def chat_completions():
    """OpenAI-compatible chat completions endpoint with structured tool handling."""

    try:
        data = request.json
        messages = data.get("messages", [])
        tools = data.get("tools", [])

        # Get available tool names
        available_tools = [tool.get("function", {}).get("name") for tool in tools]

        logger.info(f"Received request with {len(messages)} messages and {len(available_tools)} tools")

        # Get the last user message
        last_message = None
        for msg in reversed(messages):
            if msg.get("role") == "user":
                last_message = msg.get("content", "")
                break

        if not last_message:
            return jsonify({"choices": [{"message": {"role": "assistant", "content": "I need a message to process."}}]})

        # Parse the natural language into a structured tool call
        tool_call = handler.parse_natural_language(last_message, available_tools)

        if tool_call:
            # Validate the tool call
            is_valid, error_msg = handler.validate_tool_call(tool_call["tool"], tool_call["arguments"])

            if is_valid:
                logger.info(f"Structured tool call: {tool_call['tool']} with {tool_call['arguments']}")

                # Return structured tool call in OpenAI format
                return jsonify(
                    {
                        "id": "msg_structured_123",
                        "object": "chat.completion",
                        "created": 1234567890,
                        "model": "structured-tool-model",
                        "choices": [
                            {
                                "index": 0,
                                "message": {
                                    "role": "assistant",
                                    "content": None,
                                    "tool_calls": [
                                        {
                                            "id": "call_123",
                                            "type": "function",
                                            "function": {
                                                "name": tool_call["tool"],
                                                "arguments": json.dumps(tool_call["arguments"]),
                                            },
                                        }
                                    ],
                                },
                                "finish_reason": "tool_calls",
                            }
                        ],
                        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
                    }
                )
            else:
                logger.warning(f"Invalid tool call: {error_msg}")

        # No tool detected, return plain response
        return jsonify(
            {
                "id": "msg_structured_456",
                "object": "chat.completion",
                "created": 1234567890,
                "model": "structured-tool-model",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": f"I'll help you with: {last_message}"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
            }
        )

    except Exception as e:
        logger.error(f"Error processing request: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/v1/tools", methods=["GET"])
def get_tools():
    """Endpoint to get available tool schemas."""
    return jsonify({"tools": handler.get_tool_schemas()})


if __name__ == "__main__":
    import os

    port = int(os.environ.get("PORT", 8053))

    logger.info(f"Starting Structured Tool API on port {port}")
    logger.info("This implements Gemini's recommendation for structured tool handling")
    logger.info(f"Available tools: {list(AVAILABLE_TOOLS.keys())}")

    app.run(host="0.0.0.0", port=port, debug=False)
