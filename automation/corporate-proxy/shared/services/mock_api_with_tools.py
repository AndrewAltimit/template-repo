#!/usr/bin/env python3
"""
Mock Company API Endpoint with Tool Support
Handles tool calls properly for Crush and OpenCode
"""

import json
import logging
import os
import re
import time
from datetime import datetime

from flask import Flask, Response, jsonify, request
from flask_cors import CORS

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Mock secret token for testing
MOCK_SECRET_TOKEN = "test-secret-token-123"


def detect_tool_request(messages, tools):
    """Detect if the last message is asking to use a tool"""
    if not messages or not tools:
        return None, None

    last_message = messages[-1].get("content", "").lower()

    # Common tool-related patterns
    tool_patterns = {
        "ls": r"\b(ls|list|show files|list files|what files|show directory)\b",
        "view": r"\b(view|read|show|cat|display|look at|open)\s+[\w./]+",
        "write": r"\b(write|create|save|make)\s+(file|to)\b",
        "bash": r"\b(run|execute|bash|shell|command)\b",
        "grep": r"\b(grep|search|find|look for)\b",
        "edit": r"\b(edit|modify|change|update)\s+[\w./]+",
    }

    # Check if any tool pattern matches
    for tool_name, pattern in tool_patterns.items():
        if re.search(pattern, last_message):
            # Check if this tool is available
            for tool in tools:
                if tool.get("function", {}).get("name", "") == tool_name:
                    # Extract parameters from the message
                    params = extract_tool_params(tool_name, last_message)
                    return tool_name, params

    return None, None


def extract_tool_params(tool_name, message):
    """Extract parameters for a tool from the message"""
    params = {}

    if tool_name == "ls":
        # Extract path if mentioned
        path_match = re.search(r"(?:in|at|directory|folder)\s+([\w./]+)", message)
        if path_match:
            params["path"] = path_match.group(1)
        else:
            params["path"] = "."

    elif tool_name == "view":
        # Extract filename
        file_match = re.search(r"(?:view|read|show|cat|display|look at|open)\s+([\w./]+)", message)
        if file_match:
            params["file_path"] = file_match.group(1)

    elif tool_name == "write":
        # Extract filename and content
        file_match = re.search(r"(?:file|called|named)\s+([\w./]+)", message)
        if file_match:
            params["file_path"] = file_match.group(1)

        # Try to extract content between quotes
        content_match = re.search(r'"([^"]+)"', message) or re.search(r"'([^']+)'", message)
        if content_match:
            params["content"] = content_match.group(1)
        else:
            # Default content if not specified
            params["content"] = "Hello from Crush/OpenCode"

    elif tool_name == "bash":
        # Extract command
        cmd_match = re.search(r"(?:run|execute)\s+(.+)", message)
        if cmd_match:
            params["command"] = cmd_match.group(1)

    return params


@app.route("/api/v1/AI/GenAIExplorationLab/Models/<path:model_path>", methods=["POST"])
def mock_company_endpoint(model_path: str) -> Response:
    """Mock endpoint that handles tool calls properly"""

    # Log the request details
    logger.info(f"Received request for model: {model_path}")

    # Check authorization
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
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
        if tools:
            logger.info(f"Available tools: {[t.get('function', {}).get('name') for t in tools]}")

    except Exception as e:
        logger.error(f"Error parsing request: {e}")
        return jsonify({"error": "Invalid request body"}), 400

    # Check if we should return a tool call
    tool_name, tool_params = detect_tool_request(messages, tools)

    if tool_name and tools:
        logger.info(f"Detected tool request: {tool_name} with params: {tool_params}")

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
            "stop_sequence": None,
            "usage": {"input_tokens": 10, "output_tokens": 3},
        }
    else:
        # Return a normal text response
        response = {
            "id": f"msg_mock_{int(time.time())}",
            "type": "message",
            "role": "assistant",
            "model": "mock-model",
            "content": [{"type": "text", "text": "I'll help you with that task. Let me know what you need."}],
            "stop_reason": "end_turn",
            "stop_sequence": None,
            "usage": {"input_tokens": 10, "output_tokens": 15},
        }

    logger.info(f"Returning response: {response}")
    return jsonify(response), 200


@app.route("/health", methods=["GET"])
def health_check() -> Response:
    """Health check endpoint"""
    return (
        jsonify({"status": "healthy", "service": "mock_company_api_with_tools", "timestamp": datetime.now().isoformat()}),
        200,
    )


@app.route("/", methods=["GET"])
def root() -> Response:
    """Root endpoint with API info"""
    return (
        jsonify(
            {
                "service": "Mock Company API with Tool Support",
                "description": "Mock endpoint that handles tool calls for Crush and OpenCode",
                "endpoints": ["/api/v1/AI/GenAIExplorationLab/Models/<model_path>", "/health"],
                "auth": {"type": "Bearer token", "test_token": MOCK_SECRET_TOKEN},
                "features": ["Tool call detection", "Tool parameter extraction", "Proper tool call response format"],
            }
        ),
        200,
    )


if __name__ == "__main__":
    port = int(os.environ.get("MOCK_API_PORT", 8050))
    logger.info(f"Starting Mock Company API with Tool Support on port {port}")
    logger.info(f"Test token: {MOCK_SECRET_TOKEN}")
    model_endpoint = "ai-coe-bedrock-claude35-sonnet-200k:analyze=null"
    logger.info(f"Example endpoint: http://localhost:{port}/api/v1/AI/GenAIExplorationLab/Models/{model_endpoint}")
    debug_mode = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug_mode)
