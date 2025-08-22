#!/usr/bin/env python3
"""
API Translation Wrapper
Translates between OpenCode's expected API format and company's API format
This is NOT an OpenRouter proxy - it's a translation service that makes
the company API compatible with OpenCode's custom endpoint support.
"""

import json
import logging
import os
import time
from typing import Any, Dict

import requests
from flask import Flask, Response, jsonify, request, stream_with_context
from flask_cors import CORS

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Configuration
MOCK_MODE = os.getenv("WRAPPER_MOCK_MODE", "true").lower() == "true"
COMPANY_API_BASE = os.getenv("COMPANY_API_BASE", "http://localhost:8050")
COMPANY_API_TOKEN = os.getenv("COMPANY_API_TOKEN", "test-secret-token-123")

# Default model to use if none specified
DEFAULT_COMPANY_MODEL = "ai-coe-bedrock-claude35-sonnet-200k:analyze=null"

# Model mapping from OpenCode format to Company format
# OpenCode will send model IDs, we map them to company endpoints
MODEL_MAPPING = {
    # Company provider format (our custom provider)
    "company/claude-3.5-sonnet": "ai-coe-bedrock-claude35-sonnet-200k:analyze=null",
    "company/claude-3-opus": "ai-coe-bedrock-claude3-opus:analyze=null",
    "company/gpt-4": "ai-coe-openai-gpt4:analyze=null",
    # OpenRouter format (for backwards compatibility)
    "openrouter/anthropic/claude-3.5-sonnet": "ai-coe-bedrock-claude35-sonnet-200k:analyze=null",
    "openrouter/anthropic/claude-3-opus": "ai-coe-bedrock-claude3-opus:analyze=null",
    "openrouter/openai/gpt-4": "ai-coe-openai-gpt4:analyze=null",
    # With provider prefix (OpenRouter format)
    "anthropic/claude-3.5-sonnet": "ai-coe-bedrock-claude35-sonnet-200k:analyze=null",
    "anthropic/claude-3-opus": "ai-coe-bedrock-claude3-opus:analyze=null",
    "openai/gpt-4": "ai-coe-openai-gpt4:analyze=null",
    # Without prefix
    "claude-3.5-sonnet": "ai-coe-bedrock-claude35-sonnet-200k:analyze=null",
    "claude-3-opus": "ai-coe-bedrock-claude3-opus:analyze=null",
    "gpt-4": "ai-coe-openai-gpt4:analyze=null",
    "default": DEFAULT_COMPANY_MODEL,
}


def translate_to_company_format(opencode_request: Dict[str, Any]) -> tuple[Dict[str, Any], str]:
    """
    Translate OpenCode's API format to Company API format
    Returns: (translated_request, model_endpoint)
    """

    # Extract messages and system prompt
    messages = opencode_request.get("messages", [])
    system_messages = [m for m in messages if m.get("role") == "system"]
    user_messages = [m for m in messages if m.get("role") != "system"]

    system_prompt = ""
    if system_messages:
        system_prompt = "\n".join([m.get("content", "") for m in system_messages])

    # Determine which model endpoint to use
    requested_model = opencode_request.get("model", "default")
    model_endpoint = MODEL_MAPPING.get(requested_model, MODEL_MAPPING["default"])

    # Build company API request
    company_request = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": opencode_request.get("max_tokens", 1000),
        "messages": user_messages,
    }

    if system_prompt:
        company_request["system"] = system_prompt

    # Add optional parameters if present
    if "temperature" in opencode_request:
        company_request["temperature"] = opencode_request["temperature"]

    return company_request, model_endpoint


def translate_from_company_format(company_response: Dict[str, Any]) -> Dict[str, Any]:
    """
    Translate Company API response to OpenCode's expected format
    OpenCode uses the ai SDK which expects a specific format
    """

    # Extract content from company response
    content_blocks = company_response.get("content", [])
    text_content = ""

    for block in content_blocks:
        if block.get("type") == "text":
            text_content = block.get("text", "")
            break

    # Build response in format expected by OpenCode/ai SDK
    # This matches the format that ai SDK providers typically return
    opencode_response = {
        "id": company_response.get("id", f"msg_{int(time.time())}"),
        "object": "chat.completion",
        "created": int(time.time()),
        "model": company_response.get("model", "company-model"),
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": text_content},
                "finish_reason": company_response.get("stop_reason", "stop"),
            }
        ],
        "usage": {
            "prompt_tokens": company_response.get("usage", {}).get("input_tokens", 0),
            "completion_tokens": company_response.get("usage", {}).get("output_tokens", 0),
            "total_tokens": (
                company_response.get("usage", {}).get("input_tokens", 0)
                + company_response.get("usage", {}).get("output_tokens", 0)
            ),
        },
    }

    return opencode_response


@app.route("/v1/chat/completions", methods=["POST", "OPTIONS"])
def handle_chat_completion() -> Response:
    """
    Main endpoint that OpenCode will call
    Translates between OpenCode format and Company API format
    """

    if request.method == "OPTIONS":
        # Handle CORS preflight
        return "", 204

    try:
        # Log incoming request
        logger.info("Received OpenCode request")
        opencode_request = request.get_json()
        logger.info(f"Request body: {json.dumps(opencode_request, indent=2)}")

        # Translate to company format
        company_request, model_endpoint = translate_to_company_format(opencode_request)
        logger.info(f"Translated to company format: {json.dumps(company_request, indent=2)}")
        logger.info(f"Using model endpoint: {model_endpoint}")

        if MOCK_MODE:
            # In mock mode, call our mock company API
            company_url = f"{COMPANY_API_BASE}/api/v1/AI/GenAIExplorationLab/Models/{model_endpoint}"
        else:
            # In production, use real company API
            # Parse the base URL properly
            company_base = COMPANY_API_BASE.rstrip("/")
            if not company_base.startswith("http"):
                company_base = f"https://{company_base}"
            company_url = f"{company_base}/api/v1/AI/GenAIExplorationLab/Models/{model_endpoint}"

        logger.info(f"Calling company API: {company_url}")

        # Make request to company API
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {COMPANY_API_TOKEN}"}

        response = requests.post(company_url, json=company_request, headers=headers, timeout=60)

        if response.status_code != 200:
            logger.error(f"Company API error: {response.status_code} - {response.text}")
            # Return error in OpenCode-compatible format
            return (
                jsonify(
                    {
                        "error": {
                            "message": f"Company API error: {response.text}",
                            "type": "api_error",
                            "code": response.status_code,
                        }
                    }
                ),
                response.status_code,
            )

        company_response = response.json()
        logger.info(f"Company response: {json.dumps(company_response, indent=2)}")

        # Translate response back to OpenCode format
        opencode_response = translate_from_company_format(company_response)
        logger.info(f"Translated response: {json.dumps(opencode_response, indent=2)}")

        # Handle streaming if requested
        if opencode_request.get("stream", False):
            # For streaming, send response in SSE format
            def generate():
                # Send the content in chunks
                content = opencode_response["choices"][0]["message"]["content"]
                chunk_size = 10  # Send 10 characters at a time for demo

                for i in range(0, len(content), chunk_size):
                    chunk = {
                        "id": opencode_response["id"],
                        "object": "chat.completion.chunk",
                        "created": opencode_response["created"],
                        "model": opencode_response["model"],
                        "choices": [{"index": 0, "delta": {"content": content[i : i + chunk_size]}, "finish_reason": None}],
                    }
                    yield f"data: {json.dumps(chunk)}\n\n"

                # Send final chunk
                final_chunk = {
                    "id": opencode_response["id"],
                    "object": "chat.completion.chunk",
                    "created": opencode_response["created"],
                    "model": opencode_response["model"],
                    "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                }
                yield f"data: {json.dumps(final_chunk)}\n\n"
                yield "data: [DONE]\n\n"

            return Response(
                stream_with_context(generate()),
                mimetype="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )
        else:
            return jsonify(opencode_response), 200

    except Exception as e:
        logger.error(f"Error in translation wrapper: {str(e)}", exc_info=True)
        return jsonify({"error": {"message": str(e), "type": "internal_error", "code": 500}}), 500


@app.route("/v1/models", methods=["GET"])
def list_models() -> Response:
    """List available models - required by some AI SDK implementations"""
    # Show our custom provider models
    supported_models = ["company/claude-3.5-sonnet", "company/claude-3-opus", "company/gpt-4"]

    models = [
        {
            "id": model_id,
            "object": "model",
            "created": int(time.time()),
            "owned_by": "company-proxy",
            "permission": [],
            "root": model_id,
            "parent": None,
        }
        for model_id in supported_models
    ]

    return jsonify({"object": "list", "data": models}), 200


@app.route("/health", methods=["GET"])
def health_check() -> Response:
    """Health check endpoint"""
    return (
        jsonify(
            {
                "status": "healthy",
                "service": "api_translation_wrapper",
                "mode": "mock" if MOCK_MODE else "production",
                "company_api_base": COMPANY_API_BASE,
                "available_models": ["anthropic/claude-3.5-sonnet", "anthropic/claude-3-opus", "openai/gpt-4"],
                "timestamp": time.time(),
            }
        ),
        200,
    )


@app.route("/", methods=["GET"])
def root() -> Response:
    """Root endpoint with service info"""
    return (
        jsonify(
            {
                "service": "API Translation Wrapper",
                "description": "Translates between OpenCode's expected format and Company API format",
                "mode": "mock" if MOCK_MODE else "production",
                "endpoints": {
                    "/v1/chat/completions": "Main chat completion endpoint (POST)",
                    "/v1/models": "List available models (GET)",
                    "/health": "Health check (GET)",
                },
                "configuration": {
                    "company_api_base": COMPANY_API_BASE,
                    "mock_mode": MOCK_MODE,
                    "available_models": MODEL_MAPPING,
                },
                "note": "Configure OpenCode to use this service as a custom provider",
            }
        ),
        200,
    )


if __name__ == "__main__":
    port = 8052
    logger.info("=" * 60)
    logger.info("API Translation Wrapper for OpenCode")
    logger.info("=" * 60)
    logger.info(f"Port: {port}")
    logger.info(f"Mode: {'MOCK' if MOCK_MODE else 'PRODUCTION'}")
    logger.info(f"Company API Base: {COMPANY_API_BASE}")
    logger.info(f"Available models: {list(MODEL_MAPPING.keys())}")
    logger.info("-" * 60)
    logger.info(f"OpenCode endpoint: http://localhost:{port}/v1/chat/completions")
    logger.info("Configure OpenCode to use this as baseURL")
    logger.info("=" * 60)
    app.run(host="0.0.0.0", port=port, debug=True)
