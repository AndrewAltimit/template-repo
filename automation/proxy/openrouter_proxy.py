#!/usr/bin/env python3
"""
OpenRouter to Company API Proxy
Intercepts OpenRouter API calls and translates them to company API format
"""

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

import requests
from flask import Flask, Response, jsonify, request, stream_with_context
from flask_cors import CORS

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Configuration
MOCK_MODE = os.getenv("PROXY_MOCK_MODE", "true").lower() == "true"
COMPANY_API_URL = os.getenv("COMPANY_API_URL", "http://localhost:8050")
COMPANY_API_TOKEN = os.getenv("COMPANY_API_TOKEN", "test-secret-token-123")

# Model mapping from OpenRouter to Company format
MODEL_MAPPING = {
    "anthropic/claude-3.5-sonnet": "ai-coe-bedrock-claude35-sonnet-200k:analyze=null",
    "anthropic/claude-3-opus": "ai-coe-bedrock-claude3-opus:analyze=null",
    "openai/gpt-4": "ai-coe-openai-gpt4:analyze=null",
    "qwen/qwen-2.5-coder-32b-instruct": "ai-coe-bedrock-claude35-sonnet-200k:analyze=null",  # Map to Claude for now
}


def translate_openrouter_to_company(openrouter_request: Dict[str, Any]) -> Dict[str, Any]:
    """Translate OpenRouter API format to Company API format"""

    # Extract messages and system prompt
    messages = openrouter_request.get("messages", [])
    system_messages = [m for m in messages if m.get("role") == "system"]
    user_messages = [m for m in messages if m.get("role") != "system"]

    system_prompt = ""
    if system_messages:
        system_prompt = "\n".join([m.get("content", "") for m in system_messages])

    # Build company API request
    company_request = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": openrouter_request.get("max_tokens", 1000),
        "messages": user_messages,
    }

    if system_prompt:
        company_request["system"] = system_prompt

    # Add temperature if present
    if "temperature" in openrouter_request:
        company_request["temperature"] = openrouter_request["temperature"]

    return company_request


def translate_company_to_openrouter(company_response: Dict[str, Any]) -> Dict[str, Any]:
    """Translate Company API response to OpenRouter format"""

    # Extract content
    content_blocks = company_response.get("content", [])
    text_content = ""

    for block in content_blocks:
        if block.get("type") == "text":
            text_content = block.get("text", "")
            break

    # Build OpenRouter response
    openrouter_response = {
        "id": company_response.get("id", f"msg_{int(time.time())}"),
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": text_content},
                "finish_reason": company_response.get("stop_reason", "stop"),
            }
        ],
        "model": company_response.get("model", "unknown"),
        "usage": {
            "prompt_tokens": company_response.get("usage", {}).get("input_tokens", 0),
            "completion_tokens": company_response.get("usage", {}).get("output_tokens", 0),
            "total_tokens": (
                company_response.get("usage", {}).get("input_tokens", 0)
                + company_response.get("usage", {}).get("output_tokens", 0)
            ),
        },
    }

    return openrouter_response


@app.route("/api/v1/chat/completions", methods=["POST", "OPTIONS"])
def proxy_openrouter_request() -> Response:
    """Proxy OpenRouter chat completion requests to company API"""

    if request.method == "OPTIONS":
        # Handle CORS preflight
        return "", 204

    try:
        # Log incoming request
        logger.info("Received OpenRouter-style request")
        openrouter_request = request.get_json()
        logger.info(f"Request body: {json.dumps(openrouter_request, indent=2)}")

        # Extract model from request
        requested_model = openrouter_request.get("model", "")
        company_model = MODEL_MAPPING.get(requested_model, requested_model)

        if MOCK_MODE:
            logger.info("Running in MOCK MODE - returning Hatsune Miku")

            # Translate request format
            company_request = translate_openrouter_to_company(openrouter_request)

            # Make request to mock endpoint
            company_url = f"{COMPANY_API_URL}/api/v1/AI/GenAIExplorationLab/Models/{company_model}"
            logger.info(f"Proxying to: {company_url}")

            headers = {"Content-Type": "application/json", "Authorization": f"Bearer {COMPANY_API_TOKEN}"}

            response = requests.post(company_url, json=company_request, headers=headers, timeout=30)

            if response.status_code != 200:
                logger.error(f"Company API error: {response.status_code} - {response.text}")
                return jsonify({"error": response.text}), response.status_code

            company_response = response.json()
            logger.info(f"Company response: {json.dumps(company_response, indent=2)}")

            # Translate response back to OpenRouter format
            openrouter_response = translate_company_to_openrouter(company_response)
            logger.info(f"Translated response: {json.dumps(openrouter_response, indent=2)}")

            # Handle streaming if requested
            if openrouter_request.get("stream", False):
                # For streaming, we'll send the response in chunks
                def generate():
                    # Send initial chunk
                    chunk = {
                        "id": openrouter_response["id"],
                        "choices": [
                            {
                                "index": 0,
                                "delta": {
                                    "role": "assistant",
                                    "content": openrouter_response["choices"][0]["message"]["content"],
                                },
                                "finish_reason": None,
                            }
                        ],
                    }
                    yield f"data: {json.dumps(chunk)}\n\n"

                    # Send final chunk
                    final_chunk = {
                        "id": openrouter_response["id"],
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
                return jsonify(openrouter_response), 200

        else:
            # Production mode - forward to real company API
            # This would be implemented when ready to use real endpoints
            return (
                jsonify(
                    {
                        "error": "Production mode not yet implemented",
                        "message": "Set PROXY_MOCK_MODE=true to use mock endpoint",
                    }
                ),
                501,
            )

    except Exception as e:
        logger.error(f"Error in proxy: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/health", methods=["GET"])
def health_check() -> Response:
    """Health check endpoint"""
    return (
        jsonify(
            {
                "status": "healthy",
                "service": "openrouter_proxy",
                "mode": "mock" if MOCK_MODE else "production",
                "company_api_url": COMPANY_API_URL,
                "timestamp": time.time(),
            }
        ),
        200,
    )


@app.route("/", methods=["GET"])
def root() -> Response:
    """Root endpoint with proxy info"""
    return (
        jsonify(
            {
                "service": "OpenRouter to Company API Proxy",
                "description": "Translates OpenRouter API calls to company format",
                "mode": "mock" if MOCK_MODE else "production",
                "endpoints": ["/api/v1/chat/completions", "/health"],
                "model_mapping": MODEL_MAPPING,
                "company_api": COMPANY_API_URL,
            }
        ),
        200,
    )


if __name__ == "__main__":
    port = 8051
    logger.info(f"Starting OpenRouter Proxy on port {port}")
    logger.info(f"Mode: {'MOCK' if MOCK_MODE else 'PRODUCTION'}")
    logger.info(f"Company API URL: {COMPANY_API_URL}")
    logger.info(f"Proxy endpoint: http://localhost:{port}/api/v1/chat/completions")
    app.run(host="0.0.0.0", port=port, debug=True)
