#!/usr/bin/env python3
"""
Translation module for Gemini to Company API format conversion.
Handles bidirectional translation between Gemini and internal company formats.
"""

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add parent to path for shared imports
sys.path.append(str(Path(__file__).parent.parent))
from shared.services.text_tool_parser import (  # noqa: E402  # pylint: disable=wrong-import-position
    TextToolParser,
    ToolInjector,
)

# Setup logging
logger = logging.getLogger(__name__)

# Load configuration
CONFIG_PATH = Path(__file__).parent / "config" / "gemini-config.json"
with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    CONFIG = json.load(f)

# Default tool mode from config
DEFAULT_TOOL_MODE = os.environ.get("DEFAULT_TOOL_MODE", CONFIG.get("default_tool_mode", "native")).lower()

# Import tool functions if available (they may be passed as parameters)
try:
    from gemini_tool_executor import GEMINI_TOOLS, execute_tool_call
except ImportError:
    GEMINI_TOOLS = []
    execute_tool_call = None

# Initialize text tool parser and injector
text_tool_parser = TextToolParser(tool_executor=execute_tool_call) if execute_tool_call else None
tool_injector = ToolInjector(GEMINI_TOOLS) if GEMINI_TOOLS else None

# Check if using mock mode
USE_MOCK = os.environ.get("USE_MOCK_API", str(CONFIG.get("mock_settings", {}).get("enabled", False))).lower() == "true"


def get_model_tool_mode(model_name: str) -> str:
    """
    Get the tool mode for a specific model, with environment override support.

    Args:
        model_name: Model name

    Returns:
        Tool mode ('native' or 'text')
    """
    # Check for environment variable override
    # Format: GEMINI_MODEL_OVERRIDE_<model_name>_tool_mode=<mode>
    env_override_key = f"GEMINI_MODEL_OVERRIDE_{model_name.replace('-', '_').replace('.', '_')}_tool_mode"
    env_override = os.environ.get(env_override_key)

    if env_override:
        logger.info("Using environment override for %s: tool_mode=%s", model_name, env_override)
        return env_override.lower()

    # Get from model config
    model_config = CONFIG["models"].get(model_name)
    if model_config and "tool_mode" in model_config:
        return model_config["tool_mode"].lower()

    # Fall back to default
    logger.info("No tool_mode configured for %s, using default: %s", model_name, DEFAULT_TOOL_MODE)
    return DEFAULT_TOOL_MODE


def translate_gemini_to_company(gemini_request: Dict[str, Any]) -> Tuple[str, Dict[str, Any], Optional[List]]:
    """
    Translate Gemini API request format to Company API format, handling tools based on model's mode.

    Args:
        gemini_request: The incoming Gemini format request

    Returns:
        Tuple of (endpoint, company_request, tools)
    """
    # pylint: disable=too-many-nested-blocks  # Complex message format translation
    # Extract model and map it
    model = gemini_request.get("model", "gemini-2.5-flash")
    model_config = CONFIG["models"].get(model)

    if not model_config:
        logger.warning("Unknown model %s, using default", model)
        model_config = CONFIG["models"]["gemini-2.5-flash"]

    endpoint = model_config["endpoint"]

    # Check if tools are requested
    tools = gemini_request.get("tools", [])

    # Check if JSON response is requested
    generation_config = gemini_request.get("generationConfig", {})
    response_mime_type = generation_config.get("responseMimeType", "")
    response_format = generation_config.get("responseFormat", "")

    # Store JSON mode flag for later use
    wants_json = (
        response_mime_type == "application/json"
        or response_mime_type == "text/x.json"
        or response_format == "json"
        or response_format == "JSON"
    )
    gemini_request["_wants_json"] = wants_json

    if wants_json:
        logger.info("JSON response requested via generationConfig: mime=%s, format=%s", response_mime_type, response_format)

    # Get tool mode for this specific model
    model_tool_mode = get_model_tool_mode(model)

    # Store tool mode decision in request for later use
    use_text_mode = model_tool_mode == "text" and tools

    logger.info("Model %s using tool_mode=%s, use_text_mode=%s", model, model_tool_mode, use_text_mode)

    # Convert Gemini format to Company format
    messages = []
    system_prompt = ""

    # Handle different Gemini request formats
    if "messages" in gemini_request:
        # Chat format
        for msg in gemini_request["messages"]:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            # Handle tool results
            if role == "function":
                # Tool result message
                tool_response = msg.get("parts", [{}])[0].get("functionResponse", {})
                tool_name = tool_response.get("name", "unknown")
                tool_result = tool_response.get("response", {})
                content = f"Tool '{tool_name}' result: {json.dumps(tool_result)}"
                role = "user"
            elif role == "model" and "functionCall" in msg.get("parts", [{}])[0]:
                # Tool call from model
                continue  # Skip tool calls in history
            elif role == "system":
                system_prompt = content
                continue
            elif role == "model":
                role = "assistant"

            messages.append({"role": role, "content": content})

    elif "contents" in gemini_request:
        # Contents format (used by Google AI SDK)
        for content in gemini_request["contents"]:
            role = content.get("role", "user")
            parts = content.get("parts", [])

            # Check for tool calls in the parts
            tool_calls = []
            text_parts = []

            for part in parts:
                if isinstance(part, dict):
                    if "functionCall" in part:
                        tool_calls.append(part["functionCall"])
                    elif "functionResponse" in part:
                        # Handle tool response from Gemini CLI
                        tool_response = part["functionResponse"]
                        tool_name = tool_response.get("name", "unknown")
                        tool_id = tool_response.get("id", "")
                        tool_result = tool_response.get("response", {})

                        # Format based on response content
                        if "output" in tool_result:
                            formatted_result = f"Tool '{tool_name}' completed: {tool_result['output']}"
                        elif "error" in tool_result:
                            formatted_result = f"Tool '{tool_name}' failed: {tool_result['error']}"
                        else:
                            formatted_result = f"Tool '{tool_name}' result: {json.dumps(tool_result)}"

                        if tool_id:
                            formatted_result = f"[ID: {tool_id}] {formatted_result}"

                        text_parts.append(formatted_result)
                    elif "text" in part:
                        text_parts.append(part["text"])
                elif isinstance(part, str):
                    text_parts.append(part)

            # Only execute tool calls in mock mode for testing
            # In production, Gemini CLI will execute tools and send back functionResponse
            if tool_calls and role == "model" and USE_MOCK and execute_tool_call:
                # Execute tools and add results (mock mode only)
                for tool_call in tool_calls:
                    tool_name = tool_call.get("name")
                    tool_args = tool_call.get("args", {})
                    tool_result = execute_tool_call(tool_name, tool_args)
                    text_parts.append(f"Tool '{tool_name}' result: {json.dumps(tool_result)}")

            combined_text = "\n".join(text_parts)

            if combined_text:
                if role == "model":
                    role = "assistant"
                messages.append({"role": role, "content": combined_text})

    # Add tool descriptions to system prompt based on mode
    if tools:
        if use_text_mode:
            # In text mode, inject detailed tool instructions
            if tool_injector:
                system_prompt = tool_injector.inject_system_prompt(system_prompt)

            # Convert Gemini tool format to our internal format for text mode
            tool_dict = {}
            for tool in tools:
                if "functionDeclarations" in tool:
                    for func in tool["functionDeclarations"]:
                        name = func.get("name", "unknown")
                        tool_dict[name] = func

            # Inject tools into the first user message (will be done after messages are built)
            gemini_request["_tool_dict"] = tool_dict
            gemini_request["_use_text_mode"] = True
        else:
            # Native mode - original behavior
            tool_descriptions = []
            for tool in tools:
                if "functionDeclarations" in tool:
                    for func in tool["functionDeclarations"]:
                        name = func.get("name", "unknown")
                        desc = func.get("description", "")
                        tool_descriptions.append(f"- {name}: {desc}")

            if tool_descriptions:
                tool_prompt = "You have access to the following tools:\n" + "\n".join(tool_descriptions)
                tool_prompt += "\n\nTo use a tool, respond with a function call in the appropriate format."
                system_prompt = f"{system_prompt}\n\n{tool_prompt}" if system_prompt else tool_prompt

    # In text mode, inject tools into the first user message
    if use_text_mode and messages and "_tool_dict" in gemini_request and text_tool_parser:
        tool_dict = gemini_request["_tool_dict"]
        # Find first user message and inject tools
        for i, msg in enumerate(messages):
            if msg.get("role") == "user":
                original_content = msg.get("content", "")
                enhanced_content = text_tool_parser.generate_tool_prompt(tool_dict, original_content)
                messages[i]["content"] = enhanced_content
                break

    # Build Company API request
    company_request = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": gemini_request.get("generationConfig", {}).get("maxOutputTokens", 1000),
        "system": system_prompt or "You are a helpful AI assistant",
        "messages": messages,
        "temperature": gemini_request.get("generationConfig", {}).get("temperature", 0.7),
    }

    # If JSON response is requested, add instruction to the system prompt
    if wants_json:
        json_instruction = (
            "\n\nIMPORTANT: You must respond with valid JSON only. "
            "Do not include any text before or after the JSON. "
            "The response must be parseable by JSON.parse()."
        )
        if company_request["system"]:
            company_request["system"] += json_instruction
        else:
            company_request["system"] = json_instruction.strip()

        # Also add to the last user message for emphasis
        if messages and messages[-1]["role"] == "user":
            messages[-1]["content"] += "\n\nPlease respond with valid JSON only."

    return endpoint, company_request, tools


def translate_company_to_gemini(
    company_response: Dict[str, Any], original_request: Optional[Dict[str, Any]] = None, _tools: Optional[List] = None
) -> Dict[str, Any]:
    """
    Translate Company API response back to Gemini format, checking for tool calls.

    Args:
        company_response: The Company API response
        original_request: The original Gemini request (for context)
        tools: Tools from the original request

    Returns:
        Gemini format response
    """
    # Check if we're in text mode
    use_text_mode = original_request.get("_use_text_mode", False) if original_request else False

    # Check if the response contains structured tool calls
    # This is now the standard approach with unified_tool_api.py returning tool_calls for Gemini mode
    tool_calls = None

    # In text mode, parse tool calls from the response text
    if use_text_mode and text_tool_parser:
        response_text = company_response.get("content", [{"text": ""}])[0].get("text", "")
        parsed_tool_calls = text_tool_parser.parse_tool_calls(response_text)

        if parsed_tool_calls:
            # Convert parsed tool calls to Gemini format
            tool_calls = []
            for tc in parsed_tool_calls:
                tool_calls.append({"name": tc["name"], "args": tc["parameters"], "id": f"text_tool_{tc['name']}_{id(tc)}"})

            # Store the original text and parsed tools for continuation
            if original_request:
                original_request["_last_response"] = response_text
                original_request["_parsed_tools"] = parsed_tool_calls

    # Check if the Company API returned tool_calls in a structured format (native mode)
    elif "tool_calls" in company_response:
        # Extract tool calls and convert to Gemini format
        tool_calls = []
        for tc in company_response["tool_calls"]:
            # Parse arguments if they're JSON strings
            args = tc.get("function", {}).get("arguments", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}

            tool_calls.append({"name": tc.get("function", {}).get("name"), "args": args, "id": tc.get("id")})

    # Build Gemini-style response
    if tool_calls and len(tool_calls) > 0:
        # Return function call response(s) in Gemini format
        # Gemini can handle multiple function calls in one response
        function_parts = []
        for tool_call in tool_calls:
            # Format the function call with proper structure
            function_call_part = {"functionCall": {"name": tool_call.get("name"), "args": tool_call.get("args", {})}}
            # Add ID if provided for correlation
            if "id" in tool_call:
                function_call_part["functionCall"]["id"] = tool_call["id"]
            function_parts.append(function_call_part)

        gemini_response = {
            "candidates": [
                {
                    "content": {
                        "parts": function_parts,
                        "role": "model",
                    },
                    "finishReason": "STOP",
                    "index": 0,
                    "safetyRatings": [],
                }
            ],
            "promptFeedback": {"safetyRatings": []},
            "usageMetadata": {
                "promptTokenCount": company_response.get("usage", {}).get("input_tokens", 0),
                "candidatesTokenCount": company_response.get("usage", {}).get("output_tokens", 0),
                "totalTokenCount": (
                    company_response.get("usage", {}).get("input_tokens", 0)
                    + company_response.get("usage", {}).get("output_tokens", 0)
                ),
            },
        }
    else:
        # Regular text response - get the text from the response
        response_text = company_response.get("content", [{"text": ""}])[0].get("text", "")

        # Check if JSON response was requested
        wants_json = original_request.get("_wants_json", False) if original_request else False

        if wants_json:
            # The response should be JSON - try to validate it
            try:
                # Try to parse the response as JSON
                json.loads(response_text)
                # It's valid JSON, use as-is
            except json.JSONDecodeError:
                # Response is not valid JSON, wrap it in a JSON structure
                logger.warning("JSON requested but response is not valid JSON, wrapping response")
                # Create a simple JSON wrapper
                json_wrapper = {"response": response_text, "type": "text", "status": "wrapped"}
                response_text = json.dumps(json_wrapper)

        gemini_response = {
            "candidates": [
                {
                    "content": {"parts": [{"text": response_text}], "role": "model"},
                    "finishReason": "STOP",
                    "index": 0,
                    "safetyRatings": [],
                }
            ],
            "promptFeedback": {"safetyRatings": []},
            "usageMetadata": {
                "promptTokenCount": company_response.get("usage", {}).get("input_tokens", 0),
                "candidatesTokenCount": company_response.get("usage", {}).get("output_tokens", 0),
                "totalTokenCount": (
                    company_response.get("usage", {}).get("input_tokens", 0)
                    + company_response.get("usage", {}).get("output_tokens", 0)
                ),
            },
        }

    return gemini_response


def convert_gemini_tools_to_company(gemini_tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Convert Gemini tool format to Company tool format.

    Args:
        gemini_tools: List of Gemini tool definitions

    Returns:
        List of Company tool definitions
    """
    company_tools = []

    for tool_group in gemini_tools:
        if "functionDeclarations" in tool_group:
            for func in tool_group["functionDeclarations"]:
                company_tool = {
                    "name": func["name"],
                    "description": func.get("description", ""),
                    "input_schema": func.get("parameters", {"type": "object", "properties": {}, "required": []}),
                }
                company_tools.append(company_tool)

    return company_tools


def map_stop_reason(company_reason: str) -> str:
    """
    Map Company stop reason to Gemini finish reason.

    Args:
        company_reason: Company API stop reason

    Returns:
        Gemini finish reason
    """
    mapping = {"end_turn": "STOP", "stop_sequence": "STOP", "max_tokens": "MAX_TOKENS", "tool_use": "STOP", "error": "OTHER"}
    return mapping.get(company_reason, "STOP")


def convert_function_response_to_gemini(tool_name: str, tool_response: Any) -> Dict[str, Any]:
    """
    Convert a tool response to Gemini function response format.

    Args:
        tool_name: Name of the tool that was called
        tool_response: Response from the tool

    Returns:
        Gemini format function response
    """
    return {
        "functionResponse": {
            "name": tool_name,
            "response": tool_response if isinstance(tool_response, dict) else {"result": str(tool_response)},
        }
    }
