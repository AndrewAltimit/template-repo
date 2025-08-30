#!/usr/bin/env python3
"""
Company API Translation Wrapper with Tool Support
Translates between OpenAI format (from OpenCode/Crush) and Company Bedrock format
Properly handles tool calls and tool results
"""

import json
import logging
import os
from pathlib import Path

import requests
from flask import Flask, Response, jsonify, request, stream_with_context
from flask_cors import CORS

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Configuration
COMPANY_API_BASE = os.environ.get("COMPANY_API_BASE", "http://localhost:8050")
COMPANY_API_TOKEN = os.environ.get("COMPANY_API_TOKEN", "test-secret-token-123")


# Load model configuration from JSON file
def load_model_config():
    """Load model configuration from models.json"""
    config_path = Path(__file__).parent.parent / "configs" / "models.json"
    try:
        with open(config_path, "r") as f:
            config = json.load(f)

        # Build MODEL_ENDPOINTS from config
        endpoints = {}

        # Add direct model mappings
        for model_key, model_data in config.get("models", {}).items():
            endpoints[model_data["id"]] = model_data["endpoint"]
            # Also add by key for compatibility
            endpoints[model_key] = model_data["endpoint"]

        # Add model aliases
        for alias, target in config.get("model_aliases", {}).items():
            if target in config.get("models", {}):
                endpoints[alias] = config["models"][target]["endpoint"]

        # Add hardcoded OpenAI model mappings for Crush compatibility
        # Maps common OpenAI model names to Company endpoints
        if "claude-3.5-sonnet" in config.get("models", {}):
            endpoints["gpt-4"] = config["models"]["claude-3.5-sonnet"]["endpoint"]
        if "claude-3-opus" in config.get("models", {}):
            endpoints["gpt-3.5-turbo"] = config["models"]["claude-3-opus"]["endpoint"]

        return endpoints
    except Exception as e:
        logger.error(f"Failed to load models.json, using fallback configuration: {e}")
        # Fallback to hardcoded values if config file is unavailable
        return {
            "gpt-4": "ai-coe-bedrock-claude35-sonnet-200k:analyze=null",
            "gpt-3.5-turbo": "ai-coe-bedrock-claude3-opus:analyze=null",
            "company/claude-3.5-sonnet": "ai-coe-bedrock-claude35-sonnet-200k:analyze=null",
            "company/claude-3-opus": "ai-coe-bedrock-claude3-opus:analyze=null",
            "company/gpt-4": "ai-coe-bedrock-gpt4:analyze=null",
            "openrouter/anthropic/claude-3.5-sonnet": "ai-coe-bedrock-claude35-sonnet-200k:analyze=null",
            "openrouter/anthropic/claude-3-opus": "ai-coe-bedrock-claude3-opus:analyze=null",
            "openrouter/openai/gpt-4": "ai-coe-bedrock-gpt4:analyze=null",
        }


# Load model endpoints from configuration
MODEL_ENDPOINTS = load_model_config()


@app.route("/v1/chat/completions", methods=["POST"])
def chat_completions():
    """Handle OpenAI-format chat completions and translate to Company format"""
    try:
        data = request.json
        logger.info(f"Received request for model: {data.get('model')}")
        logger.info(f"Full request data: {json.dumps(data, indent=2)}")

        # Log specific details about messages and tools
        if "messages" in data:
            logger.info(f"Messages count: {len(data['messages'])}")
            for i, msg in enumerate(data["messages"]):
                logger.info(f"Message {i}: role={msg.get('role')}, content={msg.get('content', '')[:100]}")

        if "tools" in data:
            tool_list = [t.get("type", "unknown") + ":" + t.get("function", {}).get("name", "unnamed") for t in data["tools"]]
            logger.info(f"Tools provided: {tool_list}")

        model = data.get("model", "company/claude-3.5-sonnet")
        endpoint = MODEL_ENDPOINTS.get(model)

        if not endpoint:
            logger.error(f"Unknown model: {model}")
            return jsonify({"error": f"Model not found: {model}"}), 404

        # Extract messages, tools, and system prompt
        messages = data.get("messages", [])
        tools = data.get("tools", [])
        system_prompt = ""
        user_messages = []

        # Process messages
        for msg in messages:
            if msg["role"] == "system":
                system_prompt = msg["content"]
            elif msg["role"] == "tool":
                # Handle tool results - convert to assistant format
                user_messages.append({"role": "user", "content": f"Tool result: {msg.get('content', '')}"})
            else:
                # Check if message has tool_calls (from assistant)
                if "tool_calls" in msg:
                    # This is an assistant message with tool calls
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

        # Include tools if present
        if tools:
            company_request["tools"] = tools
            logger.info(f"Forwarding {len(tools)} tools to Company API")

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
        logger.info(f"Company API response: {json.dumps(company_response, indent=2)}")

        # Handle streaming vs non-streaming
        if data.get("stream", False):

            def generate():
                # Check if response contains tool calls
                if "tool_calls" in company_response:
                    # Send tool call chunk with proper index for each tool call
                    tool_calls_with_index = []
                    for i, tc in enumerate(company_response["tool_calls"]):
                        tc_copy = tc.copy()
                        tc_copy["index"] = i
                        tool_calls_with_index.append(tc_copy)

                    chunk = {
                        "id": company_response.get("id", "chatcmpl-123"),
                        "object": "chat.completion.chunk",
                        "created": 1234567890,
                        "model": model,
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"role": "assistant", "tool_calls": tool_calls_with_index},
                                "finish_reason": "tool_calls",
                            }
                        ],
                    }
                    yield f"data: {json.dumps(chunk)}\n\n"
                else:
                    # Send content chunk
                    content = ""
                    if company_response.get("content"):
                        if isinstance(company_response["content"], list):
                            content = company_response["content"][0].get("text", "")
                        else:
                            content = company_response["content"]

                    chunk = {
                        "id": company_response.get("id", "chatcmpl-123"),
                        "object": "chat.completion.chunk",
                        "created": 1234567890,
                        "model": model,
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"role": "assistant", "content": content},
                                "finish_reason": None,
                            }
                        ],
                    }
                    yield f"data: {json.dumps(chunk)}\n\n"

                # Send final chunk
                final_chunk = {
                    "id": company_response.get("id", "chatcmpl-123"),
                    "object": "chat.completion.chunk",
                    "created": 1234567890,
                    "model": model,
                    "choices": [
                        {
                            "index": 0,
                            "delta": {},
                            "finish_reason": company_response.get("stop_reason", "stop"),
                        }
                    ],
                }
                yield f"data: {json.dumps(final_chunk)}\n\n"
                yield "data: [DONE]\n\n"

            return Response(stream_with_context(generate()), content_type="text/event-stream")
        else:
            # Non-streaming response
            # Check if response contains tool calls
            if "tool_calls" in company_response:
                # Format tool call response
                openai_response = {
                    "id": company_response.get("id", "chatcmpl-123"),
                    "object": "chat.completion",
                    "created": 1234567890,
                    "model": model,
                    "choices": [
                        {
                            "index": 0,
                            "message": {"role": "assistant", "content": None, "tool_calls": company_response["tool_calls"]},
                            "finish_reason": "tool_calls",
                        }
                    ],
                    "usage": company_response.get("usage", {}),
                }
            else:
                # Extract content from Company response format
                content = ""
                if company_response.get("content"):
                    if isinstance(company_response["content"], list):
                        content = company_response["content"][0].get("text", "")
                    else:
                        content = company_response["content"]

                # Convert to OpenAI format
                openai_response = {
                    "id": company_response.get("id", "chatcmpl-123"),
                    "object": "chat.completion",
                    "created": 1234567890,
                    "model": model,
                    "choices": [
                        {
                            "index": 0,
                            "message": {"role": "assistant", "content": content},
                            "finish_reason": company_response.get("stop_reason", "stop"),
                        }
                    ],
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
    return (
        jsonify(
            {
                "status": "healthy",
                "service": "translation_wrapper_with_tools",
                "company_api_base": COMPANY_API_BASE,
                "models_available": len(MODEL_ENDPOINTS),
            }
        ),
        200,
    )


@app.route("/", methods=["GET"])
def root():
    """Root endpoint with API info"""
    return (
        jsonify(
            {
                "service": "Company API Translation Wrapper with Tool Support",
                "description": "Translates between OpenAI and Company Bedrock formats with tool call support",
                "endpoints": {
                    "/v1/chat/completions": "OpenAI-compatible chat completions endpoint",
                    "/health": "Health check endpoint",
                },
                "models": list(MODEL_ENDPOINTS.keys()),
                "features": [
                    "Tool definition forwarding",
                    "Tool call response handling",
                    "Tool result message translation",
                    "Streaming and non-streaming support",
                ],
            }
        ),
        200,
    )


if __name__ == "__main__":
    port = int(os.environ.get("WRAPPER_PORT", 8052))
    logger.info(f"Starting Translation Wrapper with Tool Support on port {port}")
    logger.info(f"Company API base: {COMPANY_API_BASE}")
    logger.info(f"Available models: {list(MODEL_ENDPOINTS.keys())}")
    debug_mode = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug_mode)
