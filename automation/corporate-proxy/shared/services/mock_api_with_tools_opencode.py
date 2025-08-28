#!/usr/bin/env python3
"""
Mock Company API Endpoint with Tool Support for OpenCode
OpenCode expects tools in format: Write("file.txt", "content"), Bash("ls"), Read("README.md")
"""

import json
import logging
import os
import re
import time
from datetime import datetime

from flask import Flask, Response, jsonify, request
from flask_cors import CORS

# Setup enhanced logging
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Mock secret token for testing
MOCK_SECRET_TOKEN = "test-secret-token-123"

# Environment variable to force tool calls for testing
FORCE_TOOL_CALLS = os.environ.get("FORCE_TOOL_CALLS", "false").lower() == "true"


def detect_tool_request(messages, tools):
    """Detect if the last message is asking to use a tool - OpenCode version"""
    if not messages or not tools:
        logger.debug("No messages or tools provided")
        return None, None

    last_message = messages[-1].get("content", "")
    logger.info(f"Analyzing message: '{last_message}'")
    last_message_lower = last_message.lower()

    # Log available tools
    available_tools = [t.get("function", {}).get("name", "") for t in tools]
    logger.debug(f"Available tools: {available_tools}")

    # OpenCode tool patterns - note the different tool names
    tool_patterns = {
        "Write": [
            r"\b(write|create|make|save)\s+(?:a\s+|an\s+|the\s+)?(?:new\s+)?file\b",
            r"\b(?:file|document)\s+(?:called|named)\s+[\w./]+",
            r"\bcreate\s+[\w./]+\.(txt|md|json|py|js|ts|go)",
        ],
        "Bash": [
            r"\b(run|execute|exec)\s+(?:the\s+)?(?:command|script|bash)\b",
            r"\brun\s+[`\"']?.+[`\"']?",
            r"\bexecute\s+.+",
        ],
        "Read": [
            r"\b(view|read|show|cat|display|look\s+at|open|see)\s+(?:the\s+)?(?:file\s+)?[\w./]+\."
            r"(txt|md|json|py|js|ts|go|sh)",
            r"\bshow\s+(?:me\s+)?(?:the\s+)?(?:contents?\s+of\s+)?[\w./]+",
            r"\bread\s+(?:the\s+)?file\s+[\w./]+",
        ],
        "List": [
            r"\b(ls|list|show|display|what)\s+(?:are\s+|the\s+)?files?\b",
            r"\blist\s+(?:the\s+)?(?:current\s+)?director",
            r"\bshow\s+(?:me\s+)?(?:the\s+)?(?:files|content|directory)\b",
        ],
    }

    # Check each tool's patterns
    for tool_name, patterns in tool_patterns.items():
        # Only check if tool is available (check lowercase version)
        if tool_name.lower() not in [t.lower() for t in available_tools]:
            continue

        for pattern in patterns:
            if re.search(pattern, last_message_lower):
                logger.info(f"Matched tool '{tool_name}' with pattern: {pattern}")
                params = extract_tool_params_opencode(tool_name, last_message)
                logger.debug(f"Extracted params: {params}")
                return tool_name, params

    logger.debug("No tool patterns matched")
    return None, None


def extract_tool_params_opencode(tool_name, message):
    """Extract parameters for OpenCode-style tool calls"""
    message_lower = message.lower()

    if tool_name == "Write":
        # Extract filename
        file_patterns = [
            r"(?:file|document)\s+(?:called|named)\s+([\w./]+)",
            r"(?:create|write|make)\s+(?:a\s+)?(?:file\s+)?(?:called\s+|named\s+)?([\w./]+\.\w+)",
            r"([\w./]+\.txt)",  # Any .txt file mentioned
        ]

        filename = "output.txt"  # default
        for pattern in file_patterns:
            match = re.search(pattern, message_lower)
            if match:
                filename = match.group(1)
                break

        # Extract content
        content_patterns = [
            r'["\']([^"\']+)["\']',  # Content in quotes
            r'(?:with\s+)?(?:content|containing|text)\s+["\']?([^"\']+)["\']?',
        ]

        content = "File created by tool execution test"  # default
        for pattern in content_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                content = match.group(1).strip()
                break

        return {"filename": filename, "content": content}

    elif tool_name == "Bash":
        # Extract command
        cmd_patterns = [
            r'(?:run|execute|exec)\s+["\'](.+)["\']',  # Command in quotes
            r"(?:run|execute|exec)\s+(?:the\s+)?(?:command\s+)?(.+)",
            r"`([^`]+)`",  # Command in backticks
        ]

        command = "ls"  # default
        for pattern in cmd_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                command = match.group(1).strip()
                break

        return {"command": command}

    elif tool_name == "Read":
        # Extract filename
        file_patterns = [
            r"(?:view|read|show|cat|display|look\s+at|open|see)\s+(?:the\s+)?(?:file\s+)?([\w./]+\.\w+)",
            r"(?:file|document)\s+(?:called|named)\s+([\w./]+)",
            r"([\w./]+\.\w+)",  # Any word with extension
        ]

        filename = "README.md"  # default
        for pattern in file_patterns:
            match = re.search(pattern, message_lower)
            if match:
                filename = match.group(1)
                break

        return {"filename": filename}

    elif tool_name == "List":
        return {}  # List doesn't need parameters

    return {}


def format_opencode_tool_call(tool_name, params):
    """Format tool call in OpenCode style: Write("file.txt", "content")"""
    if tool_name == "Write":
        # OpenCode format: Write("filename", "content")
        return f'Write("{params.get("filename", "output.txt")}", "{params.get("content", "")}")'
    elif tool_name == "Bash":
        # OpenCode format: Bash("command")
        return f'Bash("{params.get("command", "ls")}")'
    elif tool_name == "Read":
        # OpenCode format: Read("filename")
        return f'Read("{params.get("filename", "README.md")}")'
    elif tool_name == "List":
        # OpenCode format: List() or ls
        return "List()"
    return tool_name


@app.route("/api/v1/AI/GenAIExplorationLab/Models/<path:model_path>", methods=["POST"])
def mock_company_endpoint(model_path: str) -> Response:
    """Mock endpoint that handles tool calls in OpenCode format"""

    # Log the request details
    logger.info(f"=== NEW REQUEST for model: {model_path} ===")

    # Check authorization
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        logger.warning("Missing Bearer token")
        return jsonify({"error": "Unauthorized"}), 401

    token = auth_header.replace("Bearer ", "")
    if token != MOCK_SECRET_TOKEN:
        logger.warning(f"Invalid token received: {token}")
        return jsonify({"error": "Invalid token"}), 401

    # Parse request body
    try:
        body = request.get_json()
        messages = body.get("messages", [])
        tools = body.get("tools", [])

        logger.info(f"Received {len(messages)} messages and {len(tools)} tools")
        if messages:
            logger.info(f"Last message: '{messages[-1].get('content', '')[:100]}...'")
        if tools:
            tool_names = [t.get("function", {}).get("name") for t in tools]
            logger.info(f"Available tools: {tool_names}")

    except Exception as e:
        logger.error(f"Error parsing request: {e}")
        return jsonify({"error": "Invalid request body"}), 400

    # Check if this is a tool result being sent back
    if messages and messages[-1].get("role") == "tool":
        logger.info("Received tool result, returning success message")
        # Tool was executed, return success message
        response = {
            "id": f"msg_mock_{int(time.time())}",
            "type": "message",
            "role": "assistant",
            "model": "mock-model",
            "content": [{"type": "text", "text": "Tool executed successfully!"}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 10, "output_tokens": 5},
        }
        logger.info(f"Returning: {response}")
        return jsonify(response), 200

    # Check if we should return a tool call
    tool_name, tool_params = detect_tool_request(messages, tools)

    if tool_name and tools:
        logger.info(f"TOOL DETECTED: {tool_name} with params: {tool_params}")

        # Format as OpenCode expects
        opencode_tool_call = format_opencode_tool_call(tool_name, tool_params)
        logger.info(f"OpenCode format: {opencode_tool_call}")

        # Return a tool call response in OpenCode format
        response = {
            "id": f"msg_mock_{int(time.time())}",
            "type": "message",
            "role": "assistant",
            "model": "mock-model",
            "content": [],  # Empty content when using tools
            "tool_calls": [
                {
                    "id": f"toolu_{int(time.time())}",
                    "type": "function",
                    # Send the tool call in OpenCode format
                    "function": {"name": opencode_tool_call, "arguments": "{}"},  # OpenCode puts args in the name itself
                }
            ],
            "stop_reason": "tool_use",
            "usage": {"input_tokens": 10, "output_tokens": 3},
        }
        logger.info(f"Returning TOOL CALL: {json.dumps(response, indent=2)}")
        return jsonify(response), 200
    else:
        logger.info("No tool detected, returning text response")
        # Return a normal text response
        response = {
            "id": f"msg_mock_{int(time.time())}",
            "type": "message",
            "role": "assistant",
            "model": "mock-model",
            "content": [{"type": "text", "text": "I'll help you with that task. Let me know what you need."}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 10, "output_tokens": 15},
        }
        return jsonify(response), 200


@app.route("/health", methods=["GET"])
def health_check() -> Response:
    """Health check endpoint"""
    return (
        jsonify(
            {
                "status": "healthy",
                "service": "mock_company_api_opencode",
                "timestamp": datetime.now().isoformat(),
                "format": "OpenCode tool format",
            }
        ),
        200,
    )


@app.route("/", methods=["GET"])
def root() -> Response:
    """Root endpoint with API info"""
    return (
        jsonify(
            {
                "service": "Mock Company API for OpenCode",
                "description": "Returns tool calls in OpenCode format: Write('file.txt', 'content')",
                "endpoints": ["/api/v1/AI/GenAIExplorationLab/Models/<model_path>", "/health"],
                "auth": {"type": "Bearer token", "test_token": MOCK_SECRET_TOKEN},
                "tool_format": "OpenCode style: Write(), Bash(), Read(), List()",
            }
        ),
        200,
    )


if __name__ == "__main__":
    port = int(os.environ.get("MOCK_API_PORT", 8050))
    logger.info(f"Starting Mock Company API for OpenCode on port {port}")
    logger.info(f"Test token: {MOCK_SECRET_TOKEN}")
    logger.info("Tool format: OpenCode style - Write('file.txt', 'content')")
    model_endpoint = "ai-coe-bedrock-claude35-sonnet-200k:analyze=null"
    logger.info(f"Example endpoint: http://localhost:{port}/api/v1/AI/GenAIExplorationLab/Models/{model_endpoint}")
    debug_mode = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug_mode)
