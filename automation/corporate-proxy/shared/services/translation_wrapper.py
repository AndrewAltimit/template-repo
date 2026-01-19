#!/usr/bin/env python3
"""
Company API Translation Wrapper with Automatic Tool Support Detection
Automatically uses text-based tool parsing for models that don't support native tools
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple

from flask import Flask, Response, jsonify, request, stream_with_context
from flask_cors import CORS
import requests

# Import the text tool parser
from text_tool_parser import TextToolParser

# Import from local module
from tool_prompts import (
    TOOL_PROMPTS,
    get_default_system_prompt,
    get_tool_instruction_template,
)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Configuration
COMPANY_API_BASE = os.environ.get("COMPANY_API_BASE", "http://localhost:8050")
COMPANY_API_TOKEN = os.environ.get("COMPANY_API_TOKEN", "test-secret-token-123")
AGENT_CLIENT = os.environ.get("AGENT_CLIENT", "").lower()  # Can be: opencode, crush, gemini, etc.

# Global model configuration cache
MODEL_CONFIG: Dict[str, Dict[str, Any]] = {}
MODEL_ENDPOINTS: Dict[str, str] = {}
TOOL_CONFIG: Dict[str, Any] = {}
OPENCODE_PARAM_MAPPINGS: Dict[str, Dict[str, str]] = {}

# Production mode detection
IS_PRODUCTION = os.environ.get("PRODUCTION", "false").lower() == "true"


def load_tool_config():
    """Load tool configuration from tool_config.json"""
    global TOOL_CONFIG

    config_path = Path(__file__).parent.parent / "configs" / "tool_config.json"
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            TOOL_CONFIG = json.load(f)
            logger.info("Loaded tool configuration with %d tools", len(TOOL_CONFIG.get("allowed_tools", [])))
            return TOOL_CONFIG
    except Exception as e:
        if IS_PRODUCTION:
            logger.error("CRITICAL: Failed to load tool_config.json in production: %s", e)
            raise RuntimeError(f"Cannot start in production without tool configuration: {e}") from e
        logger.warning("Failed to load tool_config.json, using defaults: %s", e)
        # Fallback configuration for development
        TOOL_CONFIG = {
            "allowed_tools": ["write", "bash", "read", "edit", "grep", "glob"],
            "parser_config": {"max_tool_calls": 20, "log_errors": True},
        }
        return TOOL_CONFIG


def load_opencode_param_mappings():
    """Load OpenCode parameter mappings from JSON file"""
    global OPENCODE_PARAM_MAPPINGS

    config_path = Path(__file__).parent.parent / "configs" / "opencode_param_mappings.json"
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
            OPENCODE_PARAM_MAPPINGS = config.get("parameter_mappings", {})
            logger.info("Loaded OpenCode parameter mappings for %d tools", len(OPENCODE_PARAM_MAPPINGS))
            return OPENCODE_PARAM_MAPPINGS
    except FileNotFoundError:
        # File doesn't exist - use fallback but log differently
        logger.warning("OpenCode parameter mappings file not found at %s, using defaults", config_path)
    except json.JSONDecodeError as e:
        # JSON syntax error - this should fail loudly in production
        error_msg = f"JSON syntax error in OpenCode parameter mappings: {e}"
        if IS_PRODUCTION:
            logger.error("CRITICAL: %s", error_msg)
            raise RuntimeError(f"Cannot start in production with invalid parameter mappings: {e}") from e
        logger.error("%s", error_msg)
    except Exception as e:
        # Other errors - log with appropriate severity
        error_msg = f"Failed to load OpenCode parameter mappings: {e}"
        if IS_PRODUCTION:
            logger.error("CRITICAL: %s", error_msg)
            # In production, we should consider this critical but still allow fallback
            # to avoid breaking the service entirely
        else:
            logger.warning(error_msg)

    # Fallback mappings for critical tools
    logger.info("Using fallback OpenCode parameter mappings")
    OPENCODE_PARAM_MAPPINGS = {
        "write": {"file_path": "filePath", "content": "content"},
        "bash": {"command": "command", "_required_defaults": {"description": "Execute bash command"}},
        "read": {"file_path": "filePath", "limit": "limit", "offset": "offset"},
        "edit": {
            "file_path": "filePath",
            "old_string": "oldString",
            "new_string": "newString",
            "replace_all": "replaceAll",
        },
    }
    return OPENCODE_PARAM_MAPPINGS


# Load tool configuration
load_tool_config()

# Load OpenCode parameter mappings
load_opencode_param_mappings()

# Initialize text tool parser with configuration
text_tool_parser = TextToolParser(
    allowed_tools=set(TOOL_CONFIG.get("allowed_tools", [])),
    max_tool_calls=TOOL_CONFIG.get("parser_config", {}).get("max_tool_calls", 20),
    max_json_size=TOOL_CONFIG.get("parser_config", {}).get("max_json_size", 1048576),
    log_errors=TOOL_CONFIG.get("parser_config", {}).get("log_errors", True),
)


def load_model_config():
    """Load complete model configuration from models.json"""
    global MODEL_CONFIG, MODEL_ENDPOINTS

    config_path = Path(__file__).parent.parent / "configs" / "models.json"
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        # Store full model configuration
        MODEL_CONFIG = {}
        MODEL_ENDPOINTS = {}

        # Process direct model mappings
        for model_key, model_data in config.get("models", {}).items():
            MODEL_CONFIG[model_data["id"]] = model_data
            MODEL_CONFIG[model_key] = model_data
            MODEL_ENDPOINTS[model_data["id"]] = model_data["endpoint"]
            MODEL_ENDPOINTS[model_key] = model_data["endpoint"]

        # Process model aliases
        for alias, target in config.get("model_aliases", {}).items():
            if target in config.get("models", {}):
                model_data = config["models"][target]
                MODEL_CONFIG[alias] = model_data
                MODEL_ENDPOINTS[alias] = model_data["endpoint"]

        # Add OpenAI model mappings for compatibility
        if "claude-3.5-sonnet" in config.get("models", {}):
            MODEL_CONFIG["gpt-4"] = config["models"]["claude-3.5-sonnet"]
            MODEL_ENDPOINTS["gpt-4"] = config["models"]["claude-3.5-sonnet"]["endpoint"]
        if "claude-3-opus" in config.get("models", {}):
            MODEL_CONFIG["gpt-3.5-turbo"] = config["models"]["claude-3-opus"]
            MODEL_ENDPOINTS["gpt-3.5-turbo"] = config["models"]["claude-3-opus"]["endpoint"]

        logger.info("Loaded %d model configurations", len(MODEL_CONFIG))
        return MODEL_ENDPOINTS
    except Exception as e:
        if IS_PRODUCTION:
            logger.error("CRITICAL: Failed to load models.json in production: %s", e)
            raise RuntimeError(f"Cannot start in production without model configuration: {e}") from e
        logger.warning("Failed to load models.json, using fallback configuration: %s", e)
        # Fallback configuration for development only
        fallback_models = {
            "gpt-4": {"endpoint": "ai-coe-bedrock-claude35-sonnet-200k:analyze=null", "supports_tools": True},
            "gpt-3.5-turbo": {"endpoint": "ai-coe-bedrock-claude3-opus:analyze=null", "supports_tools": True},
            # Add OpenRouter model mappings for OpenCode compatibility
            "openrouter/openai/gpt-4": {
                "endpoint": "ai-coe-bedrock-claude35-sonnet-200k:analyze=null",
                "supports_tools": True,
            },
            "openrouter/anthropic/claude-3.5-sonnet": {
                "endpoint": "ai-coe-bedrock-claude35-sonnet-200k:analyze=null",
                "supports_tools": True,
            },
            "openrouter/anthropic/claude-3-opus": {
                "endpoint": "ai-coe-bedrock-claude3-opus:analyze=null",
                "supports_tools": True,
            },
            # Add Company model mappings for Crush compatibility
            "company/claude-3.5-sonnet": {
                "endpoint": "ai-coe-bedrock-claude35-sonnet-200k:analyze=null",
                "supports_tools": True,
            },
            "company/claude-3-opus": {"endpoint": "ai-coe-bedrock-claude3-opus:analyze=null", "supports_tools": True},
            "company/gpt-4": {"endpoint": "ai-coe-bedrock-claude35-sonnet-200k:analyze=null", "supports_tools": True},
        }
        for model_id, data in fallback_models.items():
            MODEL_CONFIG[model_id] = data
            MODEL_ENDPOINTS[model_id] = data["endpoint"]
        return MODEL_ENDPOINTS


# Load configuration on startup
load_model_config()


def format_tool_calls_for_openai(
    tool_calls: List[Dict[str, Any]], streaming: bool = False, apply_opencode_mappings: bool = True
) -> List[Dict[str, Any]]:
    """Format parsed tool calls into OpenAI format with optional OpenCode parameter mapping

    Args:
        tool_calls: List of parsed tool calls
        streaming: If True, add index field for streaming responses
        apply_opencode_mappings: If True, apply OpenCode parameter mappings (camelCase)
                                If False, keep original snake_case for Crush compatibility
    """
    formatted_calls = []
    for i, call in enumerate(tool_calls):
        tool_name = call.get("name", call.get("tool"))
        params = call.get("parameters", {})

        # Only apply OpenCode parameter mappings if requested (for OpenCode clients)
        # Crush clients need snake_case parameters unchanged
        if apply_opencode_mappings and tool_name in OPENCODE_PARAM_MAPPINGS:
            mappings = OPENCODE_PARAM_MAPPINGS[tool_name]
            mapped_params = {}

            # Map parameter names from snake_case to camelCase
            for snake_key, value in params.items():
                camel_key = mappings.get(snake_key, snake_key)  # Use original if no mapping
                mapped_params[camel_key] = value

            # Add required default parameters if specified
            if "_required_defaults" in mappings:
                for key, default_value in mappings["_required_defaults"].items():
                    if key not in mapped_params:
                        mapped_params[key] = default_value

            params = mapped_params

        formatted_call = {
            "id": f"call_{i}",
            "type": "function",
            "function": {"name": tool_name, "arguments": json.dumps(params)},
        }
        # Add index for streaming responses
        if streaming:
            formatted_call["index"] = i
        formatted_calls.append(formatted_call)
    return formatted_calls


def inject_tools_into_prompt(messages: List[Dict], tools: List[Dict], client_type: str = "generic") -> List[Dict]:
    """Inject tool definitions into the prompt for models without native tool support

    Args:
        messages: List of message dicts
        tools: List of tool definitions
        client_type: Type of client ("opencode", "crush", "gemini", or "generic")
    """
    if not tools:
        return messages

    # Create detailed tool descriptions with parameter information
    tool_descriptions = []
    for tool in tools:
        func = tool.get("function", {})
        name = func.get("name", "unknown")
        desc = func.get("description", "")

        # Add parameter details if available
        params = func.get("parameters", {})
        param_props = params.get("properties", {})
        required = params.get("required", [])

        tool_desc = f"**{name}**: {desc}"
        if param_props:
            param_list = []
            for param_name, param_info in param_props.items():
                param_type = param_info.get("type", "string")
                is_required = param_name in required
                param_desc = param_info.get("description", "")
                param_list.append(f"    - {param_name} ({param_type}{', required' if is_required else ''}): {param_desc}")
            if param_list:
                tool_desc += "\n" + "\n".join(param_list)

        tool_descriptions.append(tool_desc)

    # Get prompts from configuration
    prompts = TOOL_PROMPTS.get(client_type, TOOL_PROMPTS["generic"])
    tool_examples = prompts["examples"]
    pattern_examples = prompts["patterns"]

    # Get the instruction template
    tool_instruction = get_tool_instruction_template(client_type).format(
        tool_descriptions="\n".join(tool_descriptions), tool_examples=tool_examples, pattern_examples=pattern_examples
    )

    # Prepend to system message or create one
    new_messages = messages.copy()
    system_msg_found = False

    for i, msg in enumerate(new_messages):
        if msg.get("role") == "system":
            new_messages[i] = {"role": "system", "content": tool_instruction + "\n\n" + msg.get("content", "")}
            system_msg_found = True
            break

    if not system_msg_found:
        new_messages.insert(0, {"role": "system", "content": tool_instruction})

    return new_messages


def filter_messages_for_company_api(messages: List[Dict[str, Any]]) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Filter messages to remove unsupported fields for company API.

    The company API doesn't support:
    - tool_calls in message history
    - tool role messages
    - system messages in the messages array (handled separately)

    Args:
        messages: List of OpenAI-format messages

    Returns:
        Tuple of (system_prompt, filtered_messages)
    """

    system_prompt = ""
    filtered_messages = []

    for msg in messages:
        if msg["role"] == "system":
            # System messages are handled separately in the company API
            system_prompt = msg["content"]
        elif msg["role"] == "tool":
            # Convert tool messages to user messages with prefix
            filtered_messages.append({"role": "user", "content": f"Tool result: {msg.get('content', '')}"})
        else:
            # Filter out tool_calls and cache_control from assistant/user messages
            filtered_msg = {"role": msg["role"]}

            # Handle content and tool_calls
            if "tool_calls" in msg:
                # Convert tool_calls to text representation if there's no content
                content = msg.get("content", "")
                if not content and msg.get("tool_calls"):
                    # Create a text representation of the tool calls
                    tool_descriptions = []
                    for tc in msg["tool_calls"]:
                        if tc.get("function"):
                            func = tc["function"]
                            tool_descriptions.append(f"[Calling {func.get('name', 'unknown')} tool]")
                    content = " ".join(tool_descriptions) if tool_descriptions else ""
                filtered_msg["content"] = content
            else:
                filtered_msg["content"] = msg.get("content", "")

            # Remove any cache_control fields
            # (OpenCode might add these but company API doesn't support them)

            filtered_messages.append(filtered_msg)

    return system_prompt, filtered_messages


def _determine_client_info() -> Tuple[str, bool, bool, bool]:
    """Determine client type from environment variable."""
    agent_client = AGENT_CLIENT if AGENT_CLIENT else "crush"
    is_crush = agent_client == "crush"
    is_opencode = agent_client == "opencode"
    is_gemini = agent_client == "gemini"
    logger.info("Using agent client: %s (from %s)", agent_client, "env var" if AGENT_CLIENT else "default")
    return agent_client, is_crush, is_opencode, is_gemini


def _prepare_tools_and_messages(
    messages: List[Dict], tools: List[Dict], supports_tools: bool, is_crush: bool, is_opencode: bool, is_gemini: bool
) -> Tuple[List[Dict], List[Dict]]:
    """Prepare tools and messages based on model support."""
    if not supports_tools and tools:
        client_type = "crush" if is_crush else "opencode" if is_opencode else "gemini" if is_gemini else "generic"
        logger.info("Model doesn't support tools, injecting %d tools into prompt for %s client", len(tools), client_type)
        messages = inject_tools_into_prompt(messages, tools, client_type)
        return messages, []
    return messages, tools


def _build_company_request(
    data: Dict, system_prompt: str, user_messages: List[Dict], tools_to_send: List, agent_client: str, supports_tools: bool
) -> Dict[str, Any]:
    """Build the request payload for Company API."""
    has_tools = not supports_tools and data.get("tools")
    default_system = get_default_system_prompt(client_type=agent_client if has_tools else "generic", has_tools=has_tools)
    req = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": data.get("max_tokens", 1000),
        "system": system_prompt or default_system,
        "messages": user_messages,
        "temperature": data.get("temperature", 0.7),
    }
    if tools_to_send:
        req["tools"] = tools_to_send
        logger.info("Forwarding %d tools to Company API", len(tools_to_send))
    return req


def _extract_response_content(company_response: Dict) -> str:
    """Extract text content from company API response."""
    content = ""
    if company_response.get("content"):
        if isinstance(company_response["content"], list):
            content = company_response["content"][0].get("text", "")
        else:
            content = company_response["content"]
    return content


def _parse_text_tool_calls(content: str, data: Dict, supports_tools: bool, is_opencode: bool) -> Tuple[List, str]:
    """Parse tool calls from text response if needed."""
    tool_calls = []
    if not supports_tools and data.get("tools") and content:
        logger.info("Parsing response for text-based tool calls")
        parsed_tool_calls = text_tool_parser.parse_tool_calls(content)
        if parsed_tool_calls:
            logger.info("Found %d tool calls in text", len(parsed_tool_calls))
            is_streaming = data.get("stream", False)
            tool_calls = format_tool_calls_for_openai(
                parsed_tool_calls, streaming=is_streaming, apply_opencode_mappings=is_opencode
            )
            content = text_tool_parser.strip_tool_calls(content)
    return tool_calls, content


def _generate_streaming_chunks(response_id: str, model: str, tool_calls: List, content: str):
    """Generate streaming response chunks."""
    if tool_calls:
        initial_chunk = {
            "id": response_id,
            "object": "chat.completion.chunk",
            "created": 1234567890,
            "model": model,
            "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}],
        }
        yield f"data: {json.dumps(initial_chunk)}\n\n"

        for tool_call in tool_calls:
            chunk = {
                "id": response_id,
                "object": "chat.completion.chunk",
                "created": 1234567890,
                "model": model,
                "choices": [{"index": 0, "delta": {"tool_calls": [tool_call]}, "finish_reason": None}],
            }
            yield f"data: {json.dumps(chunk)}\n\n"
    elif content:
        chunk = {
            "id": response_id,
            "object": "chat.completion.chunk",
            "created": 1234567890,
            "model": model,
            "choices": [{"index": 0, "delta": {"role": "assistant", "content": content}, "finish_reason": None}],
        }
        yield f"data: {json.dumps(chunk)}\n\n"

    final_chunk = {
        "id": response_id,
        "object": "chat.completion.chunk",
        "created": 1234567890,
        "model": model,
        "choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls" if tool_calls else "stop"}],
    }
    yield f"data: {json.dumps(final_chunk)}\n\n"
    yield "data: [DONE]\n\n"


def _build_openai_response(response_id: str, model: str, content: str, tool_calls: List, usage: Dict) -> Dict:
    """Build non-streaming OpenAI-format response."""
    if tool_calls:
        return {
            "id": response_id,
            "object": "chat.completion",
            "created": 1234567890,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": content if content else None, "tool_calls": tool_calls},
                    "finish_reason": "tool_calls",
                }
            ],
            "usage": usage,
        }
    return {
        "id": response_id,
        "object": "chat.completion",
        "created": 1234567890,
        "model": model,
        "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
        "usage": usage,
    }


@app.route("/v1/chat/completions", methods=["POST"])
def chat_completions():
    """Handle OpenAI-format chat completions with automatic tool support detection"""
    try:
        data = request.json
        model = data.get("model", "gpt-4")
        logger.info("Received request for model: %s", model)

        agent_client, is_crush, is_opencode, is_gemini = _determine_client_info()

        model_config = MODEL_CONFIG.get(model, {})
        endpoint = MODEL_ENDPOINTS.get(model)
        if not endpoint:
            logger.error("Unknown model: %s", model)
            return jsonify({"error": f"Model not found: {model}"}), 404

        supports_tools = model_config.get("supports_tools", True)
        logger.info("Model %s supports tools: %s", model, supports_tools)

        messages, tools_to_send = _prepare_tools_and_messages(
            data.get("messages", []), data.get("tools", []), supports_tools, is_crush, is_opencode, is_gemini
        )
        system_prompt, user_messages = filter_messages_for_company_api(messages)

        company_url = f"{COMPANY_API_BASE}/api/v1/AI/GenAIExplorationLab/Models/{endpoint}"
        company_request = _build_company_request(
            data, system_prompt, user_messages, tools_to_send, agent_client, supports_tools
        )

        logger.info("Sending to Company API: %s", company_url)
        response = requests.post(
            company_url,
            json=company_request,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {COMPANY_API_TOKEN}"},
            timeout=30,
        )

        if response.status_code != 200:
            logger.error("Company API error: %d %s", response.status_code, response.text)
            return jsonify({"error": "Company API error"}), response.status_code

        company_response = response.json()
        content = _extract_response_content(company_response)
        tool_calls = company_response.get("tool_calls", [])

        if not tool_calls:
            tool_calls, content = _parse_text_tool_calls(content, data, supports_tools, is_opencode)

        response_id = company_response.get("id", "chatcmpl-123")

        if data.get("stream", False):
            return Response(
                stream_with_context(_generate_streaming_chunks(response_id, model, tool_calls, content)),
                content_type="text/event-stream",
            )

        openai_response = _build_openai_response(response_id, model, content, tool_calls, company_response.get("usage", {}))
        return jsonify(openai_response), 200

    except Exception as e:
        logger.error("Error processing request: %s", e)
        import traceback

        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint"""
    models_with_tool_support = sum(1 for m in MODEL_CONFIG.values() if m.get("supports_tools", True))
    models_without_tool_support = len(MODEL_CONFIG) - models_with_tool_support

    return (
        jsonify(
            {
                "status": "healthy",
                "service": "translation_wrapper",
                "company_api_base": COMPANY_API_BASE,
                "models_available": len(MODEL_CONFIG),
                "models_with_tool_support": models_with_tool_support,
                "models_without_tool_support": models_without_tool_support,
                "text_tool_parser": "enabled",
            }
        ),
        200,
    )


@app.route("/models", methods=["GET"])
def list_models():
    """List available models and their capabilities"""
    models = []
    for model_id, config in MODEL_CONFIG.items():
        models.append(
            {
                "id": model_id,
                "name": config.get("name", model_id),
                "supports_tools": config.get("supports_tools", True),
                "max_tokens": config.get("max_output_tokens", 4096),
            }
        )
    return jsonify({"models": models}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8052))
    logger.info("Starting Translation Wrapper on port %d", port)
    logger.info("Automatic tool support detection enabled")
    logger.info("Models loaded: %s", list(MODEL_CONFIG.keys()))
    app.run(host="0.0.0.0", port=port, debug=False)
