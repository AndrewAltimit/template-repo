#!/usr/bin/env python3
"""
API Spec Converter - Converts between OpenAI and Anthropic tool API specifications.

This module provides bidirectional conversion between:
- OpenAI Chat Completions API format (tool_calls array with function objects)
- Anthropic Messages API format (content array with tool_use blocks)

The API spec can be configured via:
- TOOL_API_SPEC environment variable: "openai" or "anthropic"
- tool_config.json api_spec.default setting
- Auto-detection based on request format
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple
import uuid

logger = logging.getLogger(__name__)

# Environment variable for API spec override
API_SPEC_ENV = os.environ.get("TOOL_API_SPEC", "").lower()


class APISpecConverter:
    """Converts between OpenAI and Anthropic tool API specifications."""

    def __init__(self, default_spec: str = "openai", auto_detect: bool = True):
        """Initialize the converter.

        Args:
            default_spec: Default API spec to use ("openai" or "anthropic")
            auto_detect: Whether to auto-detect spec from request format
        """
        self.default_spec = API_SPEC_ENV if API_SPEC_ENV else default_spec
        self.auto_detect = auto_detect
        logger.info("APISpecConverter initialized with default_spec=%s, auto_detect=%s", self.default_spec, self.auto_detect)

    def detect_spec(self, request_data: Dict[str, Any]) -> str:
        """Auto-detect the API spec from request format.

        Args:
            request_data: The incoming request data

        Returns:
            "openai" or "anthropic" based on detected format
        """
        # When auto-detect is disabled, respect the configured default_spec
        # (from constructor or environment at init time)
        if not self.auto_detect:
            env_spec = os.environ.get("TOOL_API_SPEC", "").lower()
            return env_spec if env_spec else self.default_spec

        # When auto-detect is enabled, check env at runtime with "openai" as fallback
        # This ensures consistent behavior regardless of singleton init order in tests
        current_default = os.environ.get("TOOL_API_SPEC", "openai").lower()

        # Anthropic indicators
        if "anthropic_version" in request_data:
            return "anthropic"

        # Check if system is a string (Anthropic) vs in messages (OpenAI)
        if isinstance(request_data.get("system"), str):
            return "anthropic"

        # Check messages for format indicators
        messages = request_data.get("messages", [])
        for msg in messages:
            # OpenAI: role="tool" for tool results
            if msg.get("role") == "tool":
                return "openai"

            # OpenAI: tool_calls array in assistant messages
            if msg.get("tool_calls"):
                return "openai"

            # Anthropic: content array with type indicators
            content = msg.get("content")
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict):
                        block_type = block.get("type")
                        # Anthropic-specific types
                        if block_type in ("tool_use", "tool_result"):
                            return "anthropic"

        return current_default

    def generate_tool_call_id(self, prefix: str = "call") -> str:
        """Generate a unique tool call ID.

        Args:
            prefix: Prefix for the ID ("call" for OpenAI, "toolu" for Anthropic)

        Returns:
            Unique ID string
        """
        return f"{prefix}_{uuid.uuid4().hex[:12]}"

    # =========================================================================
    # Tool Definition Conversion
    # =========================================================================

    def convert_tools_to_openai(self, tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert tool definitions to OpenAI format.

        Args:
            tools: Tool definitions (may be in either format)

        Returns:
            Tools in OpenAI format
        """
        converted = []
        for tool in tools:
            if tool.get("type") == "function":
                # Already in OpenAI format
                converted.append(tool)
            elif "input_schema" in tool:
                # Anthropic format -> OpenAI format
                converted.append(
                    {
                        "type": "function",
                        "function": {
                            "name": tool.get("name"),
                            "description": tool.get("description", ""),
                            "parameters": tool.get("input_schema", {}),
                        },
                    }
                )
            else:
                # Assume it's a simple tool definition
                converted.append(
                    {
                        "type": "function",
                        "function": {
                            "name": tool.get("name"),
                            "description": tool.get("description", ""),
                            "parameters": tool.get("parameters", {}),
                        },
                    }
                )
        return converted

    def convert_tools_to_anthropic(self, tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert tool definitions to Anthropic format.

        Args:
            tools: Tool definitions (may be in either format)

        Returns:
            Tools in Anthropic format
        """
        converted = []
        for tool in tools:
            if "input_schema" in tool and tool.get("type") != "function":
                # Already in Anthropic format
                converted.append(tool)
            elif tool.get("type") == "function":
                # OpenAI format -> Anthropic format
                func = tool.get("function", {})
                converted.append(
                    {
                        "name": func.get("name"),
                        "description": func.get("description", ""),
                        "input_schema": func.get("parameters", {"type": "object", "properties": {}}),
                    }
                )
            else:
                # Simple format -> Anthropic format
                converted.append(
                    {
                        "name": tool.get("name"),
                        "description": tool.get("description", ""),
                        "input_schema": tool.get("parameters", {"type": "object", "properties": {}}),
                    }
                )
        return converted

    # =========================================================================
    # Tool Call Conversion (Response Format)
    # =========================================================================

    def convert_tool_calls_to_openai(self, tool_calls: List[Dict[str, Any]], streaming: bool = False) -> List[Dict[str, Any]]:
        """Convert tool calls to OpenAI format.

        Args:
            tool_calls: Tool calls (may be in either format)
            streaming: Whether this is for a streaming response

        Returns:
            Tool calls in OpenAI format
        """
        converted = []
        for i, call in enumerate(tool_calls):
            # Check if already in OpenAI format
            if call.get("type") == "function" and "function" in call:
                formatted_call = call.copy()
                if streaming and "index" not in formatted_call:
                    formatted_call["index"] = i
                converted.append(formatted_call)
            elif call.get("type") == "tool_use":
                # Anthropic format -> OpenAI format
                arguments = call.get("input", {})
                if isinstance(arguments, dict):
                    arguments = json.dumps(arguments)
                formatted_call = {
                    "id": call.get("id", self.generate_tool_call_id("call")),
                    "type": "function",
                    "function": {"name": call.get("name"), "arguments": arguments},
                }
                if streaming:
                    formatted_call["index"] = i
                converted.append(formatted_call)
            else:
                # Generic format
                params = call.get("parameters", call.get("input", call.get("arguments", {})))
                if isinstance(params, dict):
                    params = json.dumps(params)
                formatted_call = {
                    "id": call.get("id", self.generate_tool_call_id("call")),
                    "type": "function",
                    "function": {"name": call.get("name", call.get("tool")), "arguments": params},
                }
                if streaming:
                    formatted_call["index"] = i
                converted.append(formatted_call)
        return converted

    def convert_tool_calls_to_anthropic(self, tool_calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert tool calls to Anthropic format (content blocks).

        Args:
            tool_calls: Tool calls (may be in either format)

        Returns:
            Tool calls as Anthropic content blocks
        """
        converted = []
        for call in tool_calls:
            if call.get("type") == "tool_use":
                # Already in Anthropic format
                converted.append(call)
            elif call.get("type") == "function":
                # OpenAI format -> Anthropic format
                func = call.get("function", {})
                arguments = func.get("arguments", "{}")
                if isinstance(arguments, str):
                    try:
                        arguments = json.loads(arguments)
                    except json.JSONDecodeError:
                        arguments = {}
                converted.append(
                    {
                        "type": "tool_use",
                        "id": call.get("id", self.generate_tool_call_id("toolu")),
                        "name": func.get("name"),
                        "input": arguments,
                    }
                )
            else:
                # Generic format
                params = call.get("parameters", call.get("input", call.get("arguments", {})))
                if isinstance(params, str):
                    try:
                        params = json.loads(params)
                    except json.JSONDecodeError:
                        params = {}
                converted.append(
                    {
                        "type": "tool_use",
                        "id": call.get("id", self.generate_tool_call_id("toolu")),
                        "name": call.get("name", call.get("tool")),
                        "input": params,
                    }
                )
        return converted

    # =========================================================================
    # Message Conversion
    # =========================================================================

    def convert_messages_to_openai(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert messages to OpenAI format.

        Args:
            messages: Messages (may be in either format)

        Returns:
            Messages in OpenAI format
        """
        converted = []
        for msg in messages:
            role = msg.get("role")
            content = msg.get("content")

            if role == "assistant":
                # Handle assistant messages with potential tool calls
                new_msg = {"role": "assistant"}

                if isinstance(content, list):
                    # Anthropic format: content is array of blocks
                    text_parts = []
                    tool_calls = []
                    for block in content:
                        if block.get("type") == "text":
                            text_parts.append(block.get("text", ""))
                        elif block.get("type") == "tool_use":
                            tool_calls.append(block)

                    new_msg["content"] = "\n".join(text_parts) if text_parts else None
                    if tool_calls:
                        new_msg["tool_calls"] = self.convert_tool_calls_to_openai(tool_calls)
                else:
                    new_msg["content"] = content
                    if msg.get("tool_calls"):
                        new_msg["tool_calls"] = self.convert_tool_calls_to_openai(msg["tool_calls"])

                converted.append(new_msg)

            elif role == "user":
                # Handle user messages with potential tool results
                if isinstance(content, list):
                    # Check for tool_result blocks (Anthropic format)
                    tool_results = []
                    text_parts = []
                    for block in content:
                        if block.get("type") == "tool_result":
                            tool_results.append(block)
                        elif block.get("type") == "text":
                            text_parts.append(block.get("text", ""))
                        elif isinstance(block, str):
                            text_parts.append(block)

                    # Convert tool results to separate tool role messages
                    for result in tool_results:
                        converted.append(
                            {
                                "role": "tool",
                                "tool_call_id": result.get("tool_use_id"),
                                "content": result.get("content", ""),
                            }
                        )

                    # Add any remaining text as user message
                    if text_parts:
                        converted.append({"role": "user", "content": "\n".join(text_parts)})
                else:
                    converted.append({"role": "user", "content": content})

            elif role == "tool":
                # Already in OpenAI format
                converted.append(msg)

            else:
                # Pass through other roles (system, etc.)
                converted.append(msg)

        return converted

    def convert_messages_to_anthropic(
        self, messages: List[Dict[str, Any]], system: Optional[str] = None
    ) -> Tuple[Optional[str], List[Dict[str, Any]]]:
        """Convert messages to Anthropic format.

        Args:
            messages: Messages (may be in either format)
            system: Optional system message to extract

        Returns:
            Tuple of (system_prompt, converted_messages)
        """
        system_prompt = system
        converted = []
        pending_tool_results = []

        for msg in messages:
            role = msg.get("role")
            content = msg.get("content")

            if role == "system":
                # Extract system message
                system_prompt = content
                continue

            if role == "assistant":
                new_msg = {"role": "assistant", "content": []}

                # Add text content
                if content:
                    if isinstance(content, str):
                        new_msg["content"].append({"type": "text", "text": content})
                    elif isinstance(content, list):
                        new_msg["content"].extend(content)

                # Add tool calls
                if msg.get("tool_calls"):
                    tool_use_blocks = self.convert_tool_calls_to_anthropic(msg["tool_calls"])
                    new_msg["content"].extend(tool_use_blocks)

                if new_msg["content"]:
                    converted.append(new_msg)

            elif role == "tool":
                # Collect tool results to add to next user message
                pending_tool_results.append(
                    {"type": "tool_result", "tool_use_id": msg.get("tool_call_id"), "content": content or ""}
                )

            elif role == "user":
                new_msg = {"role": "user", "content": []}

                # Add any pending tool results first
                if pending_tool_results:
                    new_msg["content"].extend(pending_tool_results)
                    pending_tool_results = []

                # Add user content
                if content:
                    if isinstance(content, str):
                        new_msg["content"].append({"type": "text", "text": content})
                    elif isinstance(content, list):
                        new_msg["content"].extend(content)

                if new_msg["content"]:
                    converted.append(new_msg)

        # Handle any remaining tool results
        if pending_tool_results:
            converted.append({"role": "user", "content": pending_tool_results})

        return system_prompt, converted

    # =========================================================================
    # Full Response Conversion
    # =========================================================================

    def convert_response_to_openai(self, response: Dict[str, Any], model: str = "mock") -> Dict[str, Any]:
        """Convert a response to OpenAI Chat Completions format.

        Args:
            response: Response data (may be in either format)
            model: Model name for the response

        Returns:
            Response in OpenAI format
        """
        # Check if already in OpenAI format
        if response.get("object") == "chat.completion":
            return response

        # Convert from Anthropic format
        content_blocks = response.get("content", [])
        text_parts = []
        tool_calls = []

        for block in content_blocks:
            if block.get("type") == "text":
                text_parts.append(block.get("text", ""))
            elif block.get("type") == "tool_use":
                tool_calls.append(block)

        message = {"role": "assistant", "content": "\n".join(text_parts) if text_parts else None}

        if tool_calls:
            message["tool_calls"] = self.convert_tool_calls_to_openai(tool_calls)

        stop_reason = response.get("stop_reason", "stop")
        finish_reason = "tool_calls" if stop_reason == "tool_use" else "stop"

        return {
            "id": response.get("id", f"chatcmpl-{uuid.uuid4().hex[:8]}"),
            "object": "chat.completion",
            "created": response.get("created", 0),
            "model": model,
            "choices": [{"index": 0, "message": message, "finish_reason": finish_reason}],
            "usage": response.get("usage", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}),
        }

    def convert_response_to_anthropic(self, response: Dict[str, Any], model: str = "mock") -> Dict[str, Any]:
        """Convert a response to Anthropic Messages format.

        Args:
            response: Response data (may be in either format)
            model: Model name for the response

        Returns:
            Response in Anthropic format
        """
        # Check if already in Anthropic format
        if response.get("type") == "message":
            return response

        # Convert from OpenAI format
        content = []
        stop_reason = "end_turn"

        if response.get("choices"):
            choice = response["choices"][0]
            message = choice.get("message", {})

            # Add text content
            if message.get("content"):
                content.append({"type": "text", "text": message["content"]})

            # Add tool calls
            if message.get("tool_calls"):
                tool_use_blocks = self.convert_tool_calls_to_anthropic(message["tool_calls"])
                content.extend(tool_use_blocks)
                stop_reason = "tool_use"

            if choice.get("finish_reason") == "tool_calls":
                stop_reason = "tool_use"

        usage = response.get("usage", {})

        return {
            "id": response.get("id", f"msg_{uuid.uuid4().hex[:8]}"),
            "type": "message",
            "role": "assistant",
            "model": model,
            "content": content,
            "stop_reason": stop_reason,
            "usage": {
                "input_tokens": usage.get("prompt_tokens", 0),
                "output_tokens": usage.get("completion_tokens", 0),
            },
        }


# Singleton instance for convenience
_converter_instance: Optional[APISpecConverter] = None


def get_converter(default_spec: str = "openai", auto_detect: bool = True) -> APISpecConverter:
    """Get or create a singleton converter instance.

    Args:
        default_spec: Default API spec to use
        auto_detect: Whether to auto-detect spec

    Returns:
        APISpecConverter instance
    """
    global _converter_instance  # pylint: disable=global-statement
    if _converter_instance is None:
        _converter_instance = APISpecConverter(default_spec, auto_detect)
    return _converter_instance
