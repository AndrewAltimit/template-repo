#!/usr/bin/env python3
"""
Mock Company API Endpoint with Tool Support V2
Improved pattern matching and debug logging
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
    """Detect if the last message is asking to use a tool - IMPROVED VERSION"""
    if not messages or not tools:
        logger.debug("No messages or tools provided")
        return None, None

    last_message = messages[-1].get("content", "")
    logger.info(f"Analyzing message: '{last_message}'")
    last_message_lower = last_message.lower()

    # Log available tools
    available_tools = [t.get("function", {}).get("name", "") for t in tools]
    logger.debug(f"Available tools: {available_tools}")

    # Improved patterns that handle articles and variations
    tool_patterns = {
        "write": [
            r"\b(write|create|make|save)\s+(?:a\s+|an\s+|the\s+)?(?:new\s+)?file\b",
            r"\b(?:file|document)\s+(?:called|named)\s+[\w./]+",
            r"\bcreate\s+[\w./]+\.(txt|md|json|py|js|ts|go)",
            r"\b(write|save|put).+(?:to|in|into)\s+(?:a\s+|the\s+)?file\b",
        ],
        "ls": [
            r"\b(ls|list|show|display|what)\s+(?:are\s+|the\s+)?files?\b",
            r"\blist\s+(?:the\s+)?(?:current\s+)?director",
            r"\bshow\s+(?:me\s+)?(?:the\s+)?(?:files|content|directory)\b",
            r"\bwhat(?:'s|\s+is)\s+(?:in\s+)?(?:the\s+)?"
            r"(?:current\s+)?(?:directory|folder)\b",
        ],
        "view": [
            r"\b(view|read|show|cat|display|look\s+at|open|see)\s+(?:the\s+)?(?:file\s+)?[\w./]+\.(txt|md|json|py|js|ts|go|sh)",
            r"\bshow\s+(?:me\s+)?(?:the\s+)?(?:contents?\s+of\s+)?[\w./]+",
            r"\bread\s+(?:the\s+)?file\s+[\w./]+",
        ],
        "bash": [
            r"\b(run|execute|exec)\s+(?:the\s+)?(?:command|script|bash)\b",
            r"\brun\s+[`\"']?.+[`\"']?",
            r"\bexecute\s+.+",
        ],
        "grep": [
            r"\b(grep|search|find|look)\s+(?:for\s+)?.+(?:in\s+)?(?:files?|code)\b",
            r"\bfind\s+(?:all\s+)?(?:occurrences?\s+of\s+)?",
            r"\bsearch\s+(?:for\s+)?[\w\"']+",
        ],
        "edit": [
            r"\b(edit|modify|change|update)\s+(?:the\s+)?(?:file\s+)?[\w./]+",
            r"\bupdate\s+[\w./]+\s+(?:file|with|to)\b",
            r"\bmodify\s+(?:the\s+)?contents?\s+of\s+[\w./]+",
        ],
    }

    # Check each tool's patterns
    for tool_name, patterns in tool_patterns.items():
        # Only check if tool is available
        if tool_name not in available_tools:
            continue

        for pattern in patterns:
            if re.search(pattern, last_message_lower):
                logger.info(f"Matched tool '{tool_name}' with pattern: {pattern}")
                params = extract_tool_params(tool_name, last_message)
                logger.debug(f"Extracted params: {params}")
                return tool_name, params

    # If FORCE_TOOL_CALLS is enabled, always return a write tool for testing
    if FORCE_TOOL_CALLS and "write" in available_tools:
        logger.warning("FORCE_TOOL_CALLS enabled - returning write tool")
        return "write", {"file_path": "forced_test.txt", "content": "Forced tool call test"}

    logger.debug("No tool patterns matched")
    return None, None


def extract_tool_params(tool_name, message):
    """Extract parameters for a tool from the message - IMPROVED VERSION"""
    params = {}
    message_lower = message.lower()

    logger.debug(f"Extracting params for tool '{tool_name}' from: '{message}'")

    if tool_name == "ls":
        # Extract path if mentioned
        path_patterns = [
            r"(?:in|at|from)\s+(?:the\s+)?(?:directory|folder)?\s*([\w./]+)",
            r"(?:directory|folder)\s+([\w./]+)",
            r"([\w./]+)\s+(?:directory|folder)",
        ]

        for pattern in path_patterns:
            match = re.search(pattern, message_lower)
            if match:
                params["path"] = match.group(1)
                break

        if "path" not in params:
            params["path"] = "."

    elif tool_name == "view":
        # Extract filename - look for file extensions
        file_patterns = [
            r"(?:view|read|show|cat|display|look\s+at|open|see)\s+(?:the\s+)?(?:file\s+)?([\w./]+\.\w+)",
            r"(?:file|document)\s+(?:called|named)\s+([\w./]+)",
            r"([\w./]+\.\w+)",  # Any word with extension
        ]

        for pattern in file_patterns:
            match = re.search(pattern, message_lower)
            if match:
                params["file_path"] = match.group(1)
                break

    elif tool_name == "write":
        # Extract filename
        file_patterns = [
            r"(?:file|document)\s+(?:called|named)\s+([\w./]+)",
            r"(?:create|write|make)\s+(?:a\s+)?(?:file\s+)?(?:called\s+|named\s+)?([\w./]+\.\w+)",
            r"(?:into|to)\s+(?:file\s+)?([\w./]+)",
            r"([\w./]+\.txt)",  # Any .txt file mentioned
        ]

        for pattern in file_patterns:
            match = re.search(pattern, message_lower)
            if match:
                params["file_path"] = match.group(1)
                break

        # Default filename if not found
        if "file_path" not in params:
            params["file_path"] = "output.txt"

        # Extract content - look between quotes or after "with content/containing"
        content_patterns = [
            r'["\']([^"\']+)["\']',  # Content in quotes
            r'(?:with\s+)?(?:content|containing|text)\s+["\']?([^"\']+)["\']?',
            r'(?:write|put|save)\s+["\']?([^"\']+)["\']?\s+(?:to|in|into)',
        ]

        for pattern in content_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                params["content"] = match.group(1).strip()
                break

        # Default content if not found
        if "content" not in params:
            params["content"] = "File created by tool execution test"

    elif tool_name == "bash":
        # Extract command
        cmd_patterns = [
            r'(?:run|execute|exec)\s+["\'](.+)["\']',  # Command in quotes
            r"(?:run|execute|exec)\s+(?:the\s+)?(?:command\s+)?(.+)",
            r"`([^`]+)`",  # Command in backticks
        ]

        for pattern in cmd_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                params["command"] = match.group(1).strip()
                break

    elif tool_name == "grep":
        # Extract search term
        search_patterns = [
            r'(?:search|grep|find|look)\s+(?:for\s+)?["\']([^"\']+)["\']',
            r"(?:search|grep|find|look)\s+(?:for\s+)?(\w+)",
        ]

        for pattern in search_patterns:
            match = re.search(pattern, message_lower)
            if match:
                params["pattern"] = match.group(1)
                break

    elif tool_name == "edit":
        # Extract filename
        file_patterns = [
            r"(?:edit|modify|change|update)\s+(?:the\s+)?(?:file\s+)?([\w./]+\.\w+)",
            r"([\w./]+\.\w+)",
        ]

        for pattern in file_patterns:
            match = re.search(pattern, message_lower)
            if match:
                params["file_path"] = match.group(1)
                break

    logger.debug(f"Final params for {tool_name}: {params}")
    return params


@app.route("/api/v1/AI/GenAIExplorationLab/Models/<path:model_path>", methods=["POST"])
def mock_company_endpoint(model_path: str) -> Response:
    """Mock endpoint that handles tool calls properly"""

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

        # Return a tool call response
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
                    "function": {"name": tool_name, "arguments": json.dumps(tool_params)},
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
                "service": "mock_company_api_with_tools_v2",
                "timestamp": datetime.now().isoformat(),
                "force_tools": FORCE_TOOL_CALLS,
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
                "service": "Mock Company API with Tool Support V2",
                "description": "Improved pattern matching and debug logging",
                "endpoints": ["/api/v1/AI/GenAIExplorationLab/Models/<model_path>", "/health"],
                "auth": {"type": "Bearer token", "test_token": MOCK_SECRET_TOKEN},
                "features": [
                    "Improved tool detection patterns",
                    "Enhanced debug logging",
                    "Force tool mode for testing (FORCE_TOOL_CALLS env var)",
                    "Better parameter extraction",
                ],
            }
        ),
        200,
    )


if __name__ == "__main__":
    port = int(os.environ.get("MOCK_API_PORT", 8050))
    logger.info(f"Starting Mock Company API V2 with Tool Support on port {port}")
    logger.info(f"Test token: {MOCK_SECRET_TOKEN}")
    logger.info(f"Force tool calls: {FORCE_TOOL_CALLS}")
    logger.info("Debug logging enabled")
    model_endpoint = "ai-coe-bedrock-claude35-sonnet-200k:analyze=null"
    logger.info(f"Example endpoint: http://localhost:{port}/api/v1/AI/GenAIExplorationLab/Models/{model_endpoint}")
    debug_mode = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug_mode)
