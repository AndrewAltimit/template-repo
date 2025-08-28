#!/usr/bin/env python3
"""
Structured Tool API V2 - Enhanced JSON handling for complex content
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


class EnhancedToolHandler:
    """Enhanced tool detection with better JSON handling."""

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

    def parse_natural_language_enhanced(self, message: str, available_tools: List[str]) -> Optional[Dict[str, Any]]:
        """
        Enhanced parser that handles complex JSON content properly.
        """
        message_lower = message.lower()

        # Enhanced write detection
        if any(word in message_lower for word in ["write", "create", "save"]) and "write" in available_tools:
            import re

            # Multiple patterns to extract file and content
            patterns = [
                # Pattern 1: "Write package.json with {...}"
                r"(?:write|create|save)\s+([^\s]+)\s+with\s+(.+)$",
                # Pattern 2: "Write a file called package.json with {...}"
                r"(?:write|create|save)\s+(?:a\s+)?(?:file\s+)?(?:called\s+|named\s+)?([^\s]+)\s+with\s+(.+)$",
                # Pattern 3: "Create package.json containing {...}"
                r"(?:write|create|save)\s+([^\s]+)\s+containing\s+(.+)$",
            ]

            for pattern in patterns:
                match = re.search(pattern, message, re.IGNORECASE)
                if match:
                    file_path = match.group(1).strip("\"'")
                    content = match.group(2)

                    # Don't strip quotes from JSON content
                    # Only strip outer quotes if they wrap the entire content
                    if content.startswith('"') and content.endswith('"') and not content.startswith('{"'):
                        content = content[1:-1]
                    elif content.startswith("'") and content.endswith("'") and not content.startswith("{'"):
                        content = content[1:-1]

                    logger.info(f"Detected write: file={file_path}, content={content[:50]}...")

                    return {"tool": "write", "arguments": {"filePath": file_path, "content": content}}

        elif any(word in message_lower for word in ["read", "view", "show", "cat"]) and "read" in available_tools:
            import re

            patterns = [
                r"(?:read|view|show|cat)\s+([^\s]+)",
                r"(?:read|view|show)\s+(?:the\s+)?(?:file\s+)?([^\s]+)",
            ]

            for pattern in patterns:
                match = re.search(pattern, message, re.IGNORECASE)
                if match:
                    return {"tool": "read", "arguments": {"filePath": match.group(1).strip("\"'")}}

        elif any(word in message_lower for word in ["run", "execute", "bash"]) and "bash" in available_tools:
            import re

            patterns = [
                r'(?:run|execute|bash)\s+["\']?(.+?)["\']?$',
                r'(?:run|execute)\s+(?:the\s+)?(?:command\s+)?["\']?(.+?)["\']?$',
            ]

            for pattern in patterns:
                match = re.search(pattern, message, re.IGNORECASE)
                if match:
                    return {"tool": "bash", "arguments": {"command": match.group(1).strip("\"'")}}

        elif any(word in message_lower for word in ["list", "ls", "dir"]) and "list" in available_tools:
            import re

            match = re.search(r"(?:list|ls|dir)\s+([^\s]+)", message, re.IGNORECASE)
            if match:
                return {"tool": "list", "arguments": {"path": match.group(1).strip("\"'")}}
            else:
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


handler = EnhancedToolHandler()


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({"status": "healthy", "service": "structured-tool-api-v2"}), 200


@app.route("/v1/chat/completions", methods=["POST"])
def chat_completions():
    """OpenAI-compatible chat completions endpoint with enhanced tool handling."""

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

        logger.info(f"Processing message: {last_message}")

        # Parse the natural language into a structured tool call
        tool_call = handler.parse_natural_language_enhanced(last_message, available_tools)

        if tool_call:
            # Validate the tool call
            is_valid, error_msg = handler.validate_tool_call(tool_call["tool"], tool_call["arguments"])

            if is_valid:
                logger.info(f"Structured tool call: {tool_call['tool']} with args")

                # Return structured tool call in OpenAI format
                return jsonify(
                    {
                        "id": "msg_structured_123",
                        "object": "chat.completion",
                        "created": 1234567890,
                        "model": "structured-tool-model-v2",
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
                "model": "structured-tool-model-v2",
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
        logger.error(f"Error processing request: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/v1/tools", methods=["GET"])
def get_tools():
    """Endpoint to get available tool schemas."""
    return jsonify({"tools": handler.get_tool_schemas()})


if __name__ == "__main__":
    import os

    port = int(os.environ.get("PORT", 8054))

    logger.info(f"Starting Enhanced Structured Tool API V2 on port {port}")
    logger.info("Enhanced JSON handling for complex content")
    logger.info(f"Available tools: {list(AVAILABLE_TOOLS.keys())}")

    app.run(host="0.0.0.0", port=port, debug=False)
