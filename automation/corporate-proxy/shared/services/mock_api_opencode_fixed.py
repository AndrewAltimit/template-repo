#!/usr/bin/env python3
"""
Fixed Mock Company API server that simulates the corporate AI API for testing OpenCode.
Returns tool calls in the proper OpenAI format that OpenCode expects.
"""

import json
import logging
import os
import random
import re

from flask import Flask, jsonify, request

# Set up logging
logging.basicConfig(
    level=logging.DEBUG if os.environ.get("DEBUG") else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Expected token (for testing)
EXPECTED_TOKEN = os.environ.get("EXPECTED_TOKEN", "test-secret-token-123")

# Force tool calls for testing
FORCE_TOOL_CALLS = os.environ.get("FORCE_TOOL_CALLS", "false").lower() == "true"


def detect_tool_from_message(message_text, available_tools):
    """Detect which tool to use based on the message content."""

    # Tool detection patterns - more flexible to handle variations
    tool_patterns = {
        "write": [
            r"\b(write|create|make|save)\s+(?:a\s+|an\s+|the\s+)?(?:new\s+)?file\b",
            r"\b(?:file|document)\s+(?:called|named)\s+[\w./]+",
            r"Write\(",  # Handle OpenCode format
        ],
        "read": [
            r"\b(read|view|show|display|cat)\s+(?:a\s+|an\s+|the\s+)?(?:content\s+of\s+)?(?:file|document)\b",
            r"Read\(",  # Handle OpenCode format
        ],
        "bash": [
            r"\b(run|execute|shell|bash|command)\b",
            r"^\s*(ls|pwd|cd|mkdir|rm|cp|mv|echo|cat|grep|find)\b",
            r"Bash\(",  # Handle OpenCode format
        ],
        "edit": [
            r"\b(edit|modify|change|update)\s+(?:a\s+|an\s+|the\s+)?file\b",
            r"Edit\(",  # Handle OpenCode format
        ],
        "grep": [
            r"\b(search|find|grep|look)\s+(?:for|in)\b",
            r"Grep\(",  # Handle OpenCode format
        ],
        "list": [
            r"\b(list|ls|dir)\s+(?:files|directories|folder)?\b",
            r"List\(",  # Handle OpenCode format
        ],
    }

    # Check each tool pattern
    for tool, patterns in tool_patterns.items():
        if tool not in available_tools:
            continue
        for pattern in patterns:
            if re.search(pattern, message_text, re.IGNORECASE):
                logger.info(f"Matched tool '{tool}' with pattern: {pattern}")
                return tool, extract_params_for_tool(tool, message_text)

    # Special case: If message contains OpenCode function syntax
    opencode_match = re.search(r'(\w+)\("([^"]*)"(?:,\s*"([^"]*)")?\)', message_text)
    if opencode_match:
        tool_name = opencode_match.group(1).lower()
        param1 = opencode_match.group(2)
        param2 = opencode_match.group(3)

        if tool_name in available_tools:
            params = {}
            if tool_name == "write":
                params = {"filePath": param1, "content": param2 or "File created by tool execution test"}
            elif tool_name == "read":
                params = {"filePath": param1}
            elif tool_name == "bash":
                params = {"command": param1}
            logger.info(f"Matched OpenCode syntax for tool '{tool_name}' with params: {params}")
            return tool_name, params

    # Force tool calls for testing if enabled
    if FORCE_TOOL_CALLS and "write" in available_tools:
        logger.info("FORCE_TOOL_CALLS enabled, defaulting to 'write' tool")
        return "write", {"filePath": "test.txt", "content": "File created by forced tool execution"}

    logger.debug("No tool patterns matched")
    return None, None


def extract_params_for_tool(tool_name, message_text):
    """Extract parameters based on the tool and message."""
    params = {}

    if tool_name == "write":
        # Try to extract filename - improved regex
        # Match patterns like: "file called test.txt", "file named test.txt", "test.txt file"
        filename_patterns = [
            r'file\s+(?:called|named)\s+(["\']?)([^\s"\']+)\1',  # file called/named X
            r'(?:called|named)\s+(["\']?)([^\s"\']+)\1',  # called/named X (after "file")
            r'(["\']?)([^\s"\']+\.\w+)\1',  # any word with extension (e.g., test.txt)
        ]

        filename = None
        for pattern in filename_patterns:
            match = re.search(pattern, message_text, re.IGNORECASE)
            if match:
                potential_file = match.group(2) if match.lastindex >= 2 else match.group(1)
                # Check if it looks like a filename (has extension or common names)
                if "." in potential_file or potential_file in ["README", "Makefile", "Dockerfile"]:
                    filename = potential_file
                    break

        params["filePath"] = filename or "test.txt"

        # Extract content if specified - handle both "with X" and "with content X"
        content_patterns = [
            r'with\s+content\s+["\']([^"\']+)["\']',  # with content "X"
            r'with\s+["\']([^"\']+)["\']',  # with "X"
            r"with\s+(\w+(?:\s+\w+){0,4})",  # with Hello World (up to 5 words)
        ]

        content = None
        for pattern in content_patterns:
            match = re.search(pattern, message_text, re.IGNORECASE)
            if match:
                content = match.group(1)
                break

        params["content"] = content or "File created by tool execution test"

    elif tool_name == "read":
        # Try to extract filename
        filename_match = re.search(r'(?:read|view|show)\s+(?:file\s+)?(["\']?)(\S+)\1', message_text, re.IGNORECASE)
        if filename_match:
            params["filePath"] = filename_match.group(2)
        else:
            params["filePath"] = "README.md"

    elif tool_name == "bash":
        # Try to extract command - handle various formats
        command_patterns = [
            r'(?:run|execute)\s+["\'](.+?)["\']',  # run "command" or execute 'command'
            r"(?:run|execute)\s+(.+)",  # run command (rest of line)
            r'(?:bash|shell)\s+["\'](.+?)["\']',  # bash "command"
            r'command:?\s+["\']?(.+?)["\']?$',  # command: something
        ]

        command = None
        for pattern in command_patterns:
            match = re.search(pattern, message_text, re.IGNORECASE)
            if match:
                command = match.group(1).strip()
                break

        params["command"] = command or "ls -la"

    logger.debug(f"Extracted params for {tool_name}: {params}")
    return params


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({"status": "healthy", "service": "mock-company-api-opencode"}), 200


@app.route("/api/v1/AI/<group>/Models/<model>", methods=["POST"])
def chat_completion(group, model):
    """Main chat completion endpoint that mimics Company API."""

    # Log the request
    logger.info(f"=== NEW REQUEST for model: {model} ===")

    # Check authorization
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        logger.warning("Missing or invalid Authorization header")
        return jsonify({"error": "Unauthorized"}), 401

    token = auth_header[7:]  # Remove 'Bearer ' prefix
    if token != EXPECTED_TOKEN:
        logger.warning(f"Invalid token: {token[:10]}...")
        return jsonify({"error": "Invalid token"}), 403

    # Parse request
    data = request.json
    messages = data.get("messages", [])
    tools = data.get("tools", [])

    logger.info(f"Received {len(messages)} messages and {len(tools)} tools")

    # Get available tool names
    available_tools = [tool["function"]["name"] for tool in tools] if tools else []
    if available_tools:
        logger.info(f"Available tools: {available_tools}")

    # Get the last user message
    last_message = None
    for msg in reversed(messages):
        if msg.get("role") == "user":
            last_message = msg.get("content", "")
            break

    if last_message:
        logger.info(f"Last message: '{last_message[:100]}...'")

        # Check if this is a tool result message (starts with "Tool result:")
        if last_message.startswith("Tool result:"):
            logger.info("This is a tool result message, returning acknowledgment")
            return jsonify(
                {
                    "id": f"msg_mock_{random.randint(1000000000, 9999999999)}",
                    "type": "message",
                    "role": "assistant",
                    "model": "mock-model",
                    "content": [
                        {"type": "text", "text": "I've successfully created the file test.txt with the content 'Hello World'."}
                    ],
                    "stop_reason": "end_turn",
                    "usage": {"input_tokens": 10, "output_tokens": 15},
                }
            )

        # Try to detect tool usage
        if tools:
            logger.info(f"Analyzing message: '{last_message}'")
            tool_name, tool_params = detect_tool_from_message(last_message, available_tools)

            if tool_name:
                logger.info(f"TOOL DETECTED: {tool_name} with params: {tool_params}")

                # Return proper OpenAI format tool call
                tool_call_response = {
                    "id": f"msg_mock_{random.randint(1000000000, 9999999999)}",
                    "type": "message",
                    "role": "assistant",
                    "model": "mock-model",
                    "content": [],  # Empty content for tool calls
                    "tool_calls": [
                        {
                            "id": f"toolu_{random.randint(1000000000, 9999999999)}",
                            "type": "function",
                            "function": {
                                "name": tool_name,  # Just the tool name, e.g., "write"
                                "arguments": json.dumps(tool_params),  # Parameters as JSON string
                            },
                        }
                    ],
                    "stop_reason": "tool_use",
                    "usage": {"input_tokens": 10, "output_tokens": 3},
                }

                logger.info(f"Returning TOOL CALL: {json.dumps(tool_call_response, indent=2)}")
                return jsonify(tool_call_response)

    # Default response if no tool detected
    logger.info("No tool detected, returning text response")
    return jsonify(
        {
            "id": f"msg_mock_{random.randint(1000000000, 9999999999)}",
            "type": "message",
            "role": "assistant",
            "model": "mock-model",
            "content": [
                {
                    "type": "text",
                    "text": f"I understand you want me to help with: {last_message[:100] if last_message else 'your request'}",
                }
            ],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": len(str(messages)), "output_tokens": 20},
        }
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8050))
    logger.info(f"Starting Fixed Mock Company API for OpenCode on port {port}")
    logger.info(f"Test token: {EXPECTED_TOKEN}")
    logger.info("Tool format: OpenAI style - name='write', arguments=JSON")
    logger.info('Example tool call: name=\'write\', arguments=\'{"filePath": "test.txt", "content": "Hello"}\'')
    app.run(host="0.0.0.0", port=port, debug=False)
