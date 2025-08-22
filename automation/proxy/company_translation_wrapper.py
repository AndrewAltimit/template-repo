#!/usr/bin/env python3
"""
Company API Translation Wrapper
Translates between OpenAI format (from OpenCode) and Company Bedrock format
"""

import json
import logging
import os

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

# Model mapping from OpenCode to Company endpoints
MODEL_ENDPOINTS = {
    # Company naming
    "company/claude-3.5-sonnet": "ai-coe-bedrock-claude35-sonnet-200k:analyze=null",
    "company/claude-3-opus": "ai-coe-bedrock-claude3-opus:analyze=null",
    "company/gpt-4": "ai-coe-bedrock-gpt4:analyze=null",
    # OpenRouter naming (for compatibility)
    "openrouter/anthropic/claude-3.5-sonnet": "ai-coe-bedrock-claude35-sonnet-200k:analyze=null",
    "openrouter/anthropic/claude-3-opus": "ai-coe-bedrock-claude3-opus:analyze=null",
    "openrouter/openai/gpt-4": "ai-coe-bedrock-gpt4:analyze=null",
}


@app.route("/v1/chat/completions", methods=["POST"])
def chat_completions():
    """Handle OpenAI-format chat completions and translate to Company format"""
    try:
        data = request.json
        logger.info(f"Received request for model: {data.get('model')}")

        model = data.get("model", "company/claude-3.5-sonnet")
        endpoint = MODEL_ENDPOINTS.get(model)

        if not endpoint:
            logger.error(f"Unknown model: {model}")
            return jsonify({"error": f"Model not found: {model}"}), 404

        # Extract messages and system prompt
        messages = data.get("messages", [])
        system_prompt = ""
        user_messages = []

        for msg in messages:
            if msg["role"] == "system":
                system_prompt = msg["content"]
            else:
                user_messages.append({"role": msg["role"], "content": msg["content"]})

        # Build Company API request
        company_url = f"{COMPANY_API_BASE}/api/v1/AI/GenAIExplorationLab/Models/{endpoint}"
        company_request = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": data.get("max_tokens", 1000),
            "system": system_prompt or "You are a helpful AI assistant",
            "messages": user_messages,
            "temperature": data.get("temperature", 0.7),
        }

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
        logger.info(f"Company API response: {company_response}")

        # Handle streaming vs non-streaming
        if data.get("stream", False):
            # Stream response
            def generate():
                # Send initial chunk
                chunk = {
                    "id": company_response.get("id", "chatcmpl-123"),
                    "object": "chat.completion.chunk",
                    "created": 1234567890,
                    "model": model,
                    "choices": [
                        {
                            "index": 0,
                            "delta": {"role": "assistant", "content": company_response["content"][0]["text"]},
                            "finish_reason": None,
                        }
                    ],
                }
                yield f"data: {json.dumps(chunk)}\n\n"

                # Send finish chunk
                finish_chunk = {
                    "id": company_response.get("id", "chatcmpl-123"),
                    "object": "chat.completion.chunk",
                    "created": 1234567890,
                    "model": model,
                    "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                }
                yield f"data: {json.dumps(finish_chunk)}\n\n"
                yield "data: [DONE]\n\n"

            return Response(
                stream_with_context(generate()),
                mimetype="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )
        else:
            # Non-streaming response
            openai_response = {
                "id": company_response.get("id", "chatcmpl-123"),
                "object": "chat.completion",
                "created": 1234567890,
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": company_response["content"][0]["text"]},
                        "finish_reason": "stop",
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

            return jsonify(openai_response)

    except Exception as e:
        logger.error(f"Error processing request: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/v1/models", methods=["GET"])
def list_models():
    """List available models in OpenAI format"""
    models = []
    for model_id in MODEL_ENDPOINTS.keys():
        models.append({"id": model_id, "object": "model", "created": 1234567890, "owned_by": "company"})

    return jsonify({"data": models, "object": "list"})


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "service": "company_translation_wrapper"})


if __name__ == "__main__":
    port = int(os.environ.get("WRAPPER_PORT", 8052))
    logger.info("=" * 60)
    logger.info("Company API Translation Wrapper")
    logger.info("=" * 60)
    logger.info(f"Port: {port}")
    logger.info(f"Company API Base: {COMPANY_API_BASE}")
    logger.info(f"Available models: {list(MODEL_ENDPOINTS.keys())}")
    logger.info("-" * 60)
    logger.info(f"OpenCode endpoint: http://localhost:{port}/v1/chat/completions")
    logger.info(f"Configure OpenCode to use baseURL: http://localhost:{port}/v1")
    logger.info("=" * 60)

    debug_mode = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug_mode)
