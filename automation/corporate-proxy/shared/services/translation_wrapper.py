#!/usr/bin/env python3
"""
Company API Translation Wrapper with Automatic Tool Support Detection
Automatically uses text-based tool parsing for models that don't support native tools
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List

import requests
from flask import Flask, Response, jsonify, request, stream_with_context
from flask_cors import CORS

# Import the text tool parser
from text_tool_parser import TextToolParser

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Configuration
COMPANY_API_BASE = os.environ.get("COMPANY_API_BASE", "http://localhost:8050")
COMPANY_API_TOKEN = os.environ.get("COMPANY_API_TOKEN", "test-secret-token-123")

# Global model configuration cache
MODEL_CONFIG: Dict[str, Dict[str, Any]] = {}
MODEL_ENDPOINTS: Dict[str, str] = {}
TOOL_CONFIG: Dict[str, Any] = {}

# Production mode detection
IS_PRODUCTION = os.environ.get("PRODUCTION", "false").lower() == "true"


def load_tool_config():
    """Load tool configuration from tool_config.json"""
    global TOOL_CONFIG

    config_path = Path(__file__).parent.parent / "configs" / "tool_config.json"
    try:
        with open(config_path, "r") as f:
            TOOL_CONFIG = json.load(f)
            logger.info(f"Loaded tool configuration with {len(TOOL_CONFIG.get('allowed_tools', []))} tools")
            return TOOL_CONFIG
    except Exception as e:
        if IS_PRODUCTION:
            logger.error(f"CRITICAL: Failed to load tool_config.json in production: {e}")
            raise RuntimeError(f"Cannot start in production without tool configuration: {e}")
        else:
            logger.warning(f"Failed to load tool_config.json, using defaults: {e}")
            # Fallback configuration for development
            TOOL_CONFIG = {
                "allowed_tools": ["write", "bash", "read", "edit", "grep", "glob"],
                "parser_config": {"max_tool_calls": 20, "log_errors": True},
            }
            return TOOL_CONFIG


# Load tool configuration
load_tool_config()

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
        with open(config_path, "r") as f:
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

        logger.info(f"Loaded {len(MODEL_CONFIG)} model configurations")
        return MODEL_ENDPOINTS
    except Exception as e:
        if IS_PRODUCTION:
            logger.error(f"CRITICAL: Failed to load models.json in production: {e}")
            raise RuntimeError(f"Cannot start in production without model configuration: {e}")
        else:
            logger.warning(f"Failed to load models.json, using fallback configuration: {e}")
            # Fallback configuration for development only
            fallback_models = {
                "gpt-4": {"endpoint": "ai-coe-bedrock-claude35-sonnet-200k:analyze=null", "supports_tools": True},
                "gpt-3.5-turbo": {"endpoint": "ai-coe-bedrock-claude3-opus:analyze=null", "supports_tools": True},
            }
            for model_id, data in fallback_models.items():
                MODEL_CONFIG[model_id] = data
                MODEL_ENDPOINTS[model_id] = data["endpoint"]
            return MODEL_ENDPOINTS


# Load configuration on startup
load_model_config()


def format_tool_calls_for_openai(tool_calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Format parsed tool calls into OpenAI format"""
    formatted_calls = []
    for i, call in enumerate(tool_calls):
        formatted_call = {
            "id": f"call_{i}",
            "type": "function",
            "function": {"name": call.get("name", call.get("tool")), "arguments": json.dumps(call.get("parameters", {}))},
        }
        formatted_calls.append(formatted_call)
    return formatted_calls


def inject_tools_into_prompt(messages: List[Dict], tools: List[Dict]) -> List[Dict]:
    """Inject tool definitions into the prompt for models without native tool support"""
    if not tools:
        return messages

    # Create a tool description to prepend to the system message
    tool_descriptions = []
    for tool in tools:
        func = tool.get("function", {})
        name = func.get("name", "unknown")
        desc = func.get("description", "")

        tool_descriptions.append(f"- {name}: {desc}")

    tool_instruction = """You have access to the following tools:

{}

When you need to use a tool, format it as:
```tool_call
{{
  "tool": "tool_name",
  "parameters": {{
    "param1": "value1",
    "param2": "value2"
  }}
}}
```

Or use the Python-style format:
ToolName(param1="value1", param2="value2")
""".format(
        "\n".join(tool_descriptions)
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


@app.route("/v1/chat/completions", methods=["POST"])
def chat_completions():
    """Handle OpenAI-format chat completions with automatic tool support detection"""
    try:
        data = request.json
        model = data.get("model", "gpt-4")

        logger.info(f"Received request for model: {model}")

        # Get model configuration
        model_config = MODEL_CONFIG.get(model, {})
        endpoint = MODEL_ENDPOINTS.get(model)

        if not endpoint:
            logger.error(f"Unknown model: {model}")
            return jsonify({"error": f"Model not found: {model}"}), 404

        # Check if model supports tools
        supports_tools = model_config.get("supports_tools", True)
        logger.info(f"Model {model} supports tools: {supports_tools}")

        # Extract messages and tools
        messages = data.get("messages", [])
        tools = data.get("tools", [])

        # If model doesn't support tools but tools are provided, inject them into prompt
        if not supports_tools and tools:
            logger.info(f"Model doesn't support tools, injecting {len(tools)} tools into prompt")
            messages = inject_tools_into_prompt(messages, tools)
            # Don't send tools to the API since it doesn't support them
            tools_to_send = []
        else:
            tools_to_send = tools

        # Process messages for company API format
        system_prompt = ""
        user_messages = []

        for msg in messages:
            if msg["role"] == "system":
                system_prompt = msg["content"]
            elif msg["role"] == "tool":
                user_messages.append({"role": "user", "content": f"Tool result: {msg.get('content', '')}"})
            else:
                if "tool_calls" in msg:
                    user_messages.append(
                        {"role": msg["role"], "content": msg.get("content", ""), "tool_calls": msg["tool_calls"]}
                    )
                else:
                    user_messages.append({"role": msg["role"], "content": msg.get("content", "")})

        # Build Company API request
        company_url = f"{COMPANY_API_BASE}/api/v1/AI/GenAIExplorationLab/Models/{endpoint}"
        company_request = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": data.get("max_tokens", 1000),
            "system": system_prompt or "You are a helpful AI assistant",
            "messages": user_messages,
            "temperature": data.get("temperature", 0.7),
        }

        # Only include tools if model supports them
        if tools_to_send:
            company_request["tools"] = tools_to_send
            logger.info(f"Forwarding {len(tools_to_send)} tools to Company API")

        logger.info(f"Sending to Company API: {company_url}")

        # Make request to Company API
        response = requests.post(
            company_url,
            json=company_request,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {COMPANY_API_TOKEN}"},
        )

        if response.status_code != 200:
            logger.error(f"Company API error: {response.status_code} {response.text}")
            return jsonify({"error": "Company API error"}), response.status_code

        company_response = response.json()

        # Extract content from response
        content = ""
        if company_response.get("content"):
            if isinstance(company_response["content"], list):
                content = company_response["content"][0].get("text", "")
            else:
                content = company_response["content"]

        # Check for tool calls in response
        tool_calls = company_response.get("tool_calls", [])

        # If model doesn't support tools but we had tools in the request,
        # parse the response text for tool calls
        if not supports_tools and data.get("tools") and content:
            logger.info("Parsing response for text-based tool calls")
            parsed_tool_calls = text_tool_parser.parse_tool_calls(content)
            if parsed_tool_calls:
                logger.info(f"Found {len(parsed_tool_calls)} tool calls in text")
                tool_calls = format_tool_calls_for_openai(parsed_tool_calls)
                # Use centralized stripping logic from text_tool_parser
                content = text_tool_parser.strip_tool_calls(content)

        # Handle streaming vs non-streaming
        if data.get("stream", False):

            def generate():
                if tool_calls:
                    # Send tool call chunk
                    chunk = {
                        "id": company_response.get("id", "chatcmpl-123"),
                        "object": "chat.completion.chunk",
                        "created": 1234567890,
                        "model": model,
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"role": "assistant", "tool_calls": tool_calls},
                                "finish_reason": "tool_calls",
                            }
                        ],
                    }
                    yield f"data: {json.dumps(chunk)}\n\n"
                else:
                    # Send content chunk
                    chunk = {
                        "id": company_response.get("id", "chatcmpl-123"),
                        "object": "chat.completion.chunk",
                        "created": 1234567890,
                        "model": model,
                        "choices": [{"index": 0, "delta": {"role": "assistant", "content": content}, "finish_reason": None}],
                    }
                    yield f"data: {json.dumps(chunk)}\n\n"

                # Send final chunk
                final_chunk = {
                    "id": company_response.get("id", "chatcmpl-123"),
                    "object": "chat.completion.chunk",
                    "created": 1234567890,
                    "model": model,
                    "choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls" if tool_calls else "stop"}],
                }
                yield f"data: {json.dumps(final_chunk)}\n\n"
                yield "data: [DONE]\n\n"

            return Response(stream_with_context(generate()), content_type="text/event-stream")
        else:
            # Non-streaming response
            if tool_calls:
                openai_response = {
                    "id": company_response.get("id", "chatcmpl-123"),
                    "object": "chat.completion",
                    "created": 1234567890,
                    "model": model,
                    "choices": [
                        {
                            "index": 0,
                            "message": {
                                "role": "assistant",
                                "content": content if content else None,
                                "tool_calls": tool_calls,
                            },
                            "finish_reason": "tool_calls",
                        }
                    ],
                    "usage": company_response.get("usage", {}),
                }
            else:
                openai_response = {
                    "id": company_response.get("id", "chatcmpl-123"),
                    "object": "chat.completion",
                    "created": 1234567890,
                    "model": model,
                    "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
                    "usage": company_response.get("usage", {}),
                }

            return jsonify(openai_response), 200

    except Exception as e:
        logger.error(f"Error processing request: {e}")
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
    logger.info(f"Starting Translation Wrapper on port {port}")
    logger.info("Automatic tool support detection enabled")
    logger.info(f"Models loaded: {list(MODEL_CONFIG.keys())}")
    app.run(host="0.0.0.0", port=port, debug=False)
