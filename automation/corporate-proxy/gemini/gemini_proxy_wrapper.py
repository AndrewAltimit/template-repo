#!/usr/bin/env python3
"""
Gemini API Proxy Wrapper
Intercepts Gemini API calls and redirects them through the corporate proxy
"""

import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path

import requests
from flask import Flask, Response, jsonify, request, stream_with_context
from flask_cors import CORS

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Load configuration
CONFIG_PATH = Path(__file__).parent / "config" / "gemini-config.json"
with open(CONFIG_PATH, "r") as f:
    CONFIG = json.load(f)

# Configuration from environment and config file
COMPANY_API_BASE = os.environ.get("COMPANY_API_BASE", CONFIG["corporate_api"]["base_url"])
COMPANY_API_TOKEN = os.environ.get(CONFIG["corporate_api"]["token_env_var"], CONFIG["corporate_api"]["default_token"])
USE_MOCK = os.environ.get("USE_MOCK_API", str(CONFIG["mock_settings"]["enabled"])).lower() == "true"
PROXY_PORT = int(os.environ.get("GEMINI_PROXY_PORT", CONFIG["proxy_settings"]["port"]))


def translate_gemini_to_company(gemini_request):
    """Translate Gemini API request format to Company API format"""

    # Extract model and map it
    model = gemini_request.get("model", "gemini-2.5-flash")
    model_config = CONFIG["models"].get(model)

    if not model_config:
        logger.warning(f"Unknown model {model}, using default")
        model_config = CONFIG["models"]["gemini-2.5-flash"]

    endpoint = model_config["endpoint"]

    # Convert Gemini format to Company format
    messages = []
    system_prompt = ""

    # Handle different Gemini request formats
    if "messages" in gemini_request:
        # Chat format
        for msg in gemini_request["messages"]:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "system":
                system_prompt = content
            else:
                # Map Gemini roles to Company roles
                if role == "model":
                    role = "assistant"
                messages.append({"role": role, "content": content})

    elif "prompt" in gemini_request:
        # Single prompt format
        messages.append({"role": "user", "content": gemini_request["prompt"]})

    elif "contents" in gemini_request:
        # Contents format (used by Google AI SDK)
        for content in gemini_request["contents"]:
            role = content.get("role", "user")
            parts = content.get("parts", [])

            # Combine all text parts
            text_parts = []
            for part in parts:
                if isinstance(part, dict) and "text" in part:
                    text_parts.append(part["text"])
                elif isinstance(part, str):
                    text_parts.append(part)

            combined_text = "\n".join(text_parts)

            if role == "model":
                role = "assistant"

            messages.append({"role": role, "content": combined_text})

    # Build Company API request
    company_request = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": gemini_request.get("max_output_tokens", 1000),
        "system": system_prompt or "You are a helpful AI assistant",
        "messages": messages,
        "temperature": gemini_request.get("temperature", 0.7),
    }

    return endpoint, company_request


def translate_company_to_gemini(company_response, original_request):
    """Translate Company API response back to Gemini format"""

    # Get the response text
    response_text = company_response["content"][0]["text"]

    # Check if we're in mock mode
    if USE_MOCK and CONFIG["mock_settings"]["enabled"]:
        # Add delay for realism
        delay_ms = CONFIG["mock_settings"]["delay_ms"] / 1000
        time.sleep(delay_ms)

    # Build Gemini-style response
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


@app.route("/v1/models/<model>/generateContent", methods=["POST"])
@app.route("/v1/models/<model>:generateContent", methods=["POST"])
@app.route("/v1beta/models/<model>:generateContent", methods=["POST"])
@app.route("/models/<model>:generateContent", methods=["POST"])
@app.route("/v1beta/models/<path:model>", methods=["POST"])  # Catch-all for v1beta
def generate_content(model):
    """Handle Gemini generateContent API calls"""

    try:
        gemini_request = request.json
        gemini_request["model"] = model

        logger.info(f"Received Gemini request for model: {model}")
        logger.debug(f"Request body: {gemini_request}")

        # Translate to Company format
        endpoint, company_request = translate_gemini_to_company(gemini_request)

        # Make request to Company API
        company_url = f"{COMPANY_API_BASE}/api/v1/AI/GenAIExplorationLab/Models/{endpoint}"

        logger.info(f"Forwarding to Company API: {company_url}")

        response = requests.post(
            company_url,
            json=company_request,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {COMPANY_API_TOKEN}"},
            timeout=CONFIG["proxy_settings"]["timeout"],
        )

        if response.status_code != 200:
            logger.error(f"Company API error: {response.status_code} {response.text}")
            return jsonify({"error": "Upstream API error"}), response.status_code

        company_response = response.json()

        # Translate back to Gemini format
        gemini_response = translate_company_to_gemini(company_response, gemini_request)

        return jsonify(gemini_response)

    except requests.exceptions.Timeout:
        logger.error("Company API timeout")
        return jsonify({"error": "Request timeout"}), 504
    except Exception as e:
        logger.error(f"Error processing request: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/v1/models/<model>/streamGenerateContent", methods=["POST"])
@app.route("/v1/models/<model>:streamGenerateContent", methods=["POST"])
@app.route("/v1beta/models/<model>:streamGenerateContent", methods=["POST"])
@app.route("/models/<model>:streamGenerateContent", methods=["POST"])
def stream_generate_content(model):
    """Handle Gemini streaming API calls"""

    try:
        gemini_request = request.json
        gemini_request["model"] = model

        logger.info(f"Received streaming request for model: {model}")

        # Translate to Company format
        endpoint, company_request = translate_gemini_to_company(gemini_request)

        # Make request to Company API
        company_url = f"{COMPANY_API_BASE}/api/v1/AI/GenAIExplorationLab/Models/{endpoint}"

        response = requests.post(
            company_url,
            json=company_request,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {COMPANY_API_TOKEN}"},
            timeout=CONFIG["proxy_settings"]["timeout"],
        )

        if response.status_code != 200:
            logger.error(f"Company API error: {response.status_code}")
            return jsonify({"error": "Upstream API error"}), response.status_code

        company_response = response.json()

        # Simulate streaming by chunking the response
        def generate():
            response_text = company_response["content"][0]["text"]

            # Split response into chunks for streaming effect
            chunk_size = 20  # characters per chunk
            chunks = [response_text[i : i + chunk_size] for i in range(0, len(response_text), chunk_size)]

            for i, chunk in enumerate(chunks):
                gemini_chunk = {
                    "candidates": [
                        {
                            "content": {"parts": [{"text": chunk}], "role": "model"},
                            "finishReason": "STOP" if i == len(chunks) - 1 else None,
                            "index": 0,
                        }
                    ]
                }

                yield f"data: {json.dumps(gemini_chunk)}\n\n"

                # Small delay between chunks for realism
                time.sleep(0.05)

        return Response(
            stream_with_context(generate()),
            mimetype="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    except Exception as e:
        logger.error(f"Streaming error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/v1/models", methods=["GET"])
def list_models():
    """List available models in Gemini format"""

    models = []
    for model_id, model_config in CONFIG["models"].items():
        models.append(
            {
                "name": f"models/{model_id}",
                "version": "001",
                "displayName": model_id.replace("-", " ").title(),
                "description": model_config.get("description", ""),
                "inputTokenLimit": 200000,
                "outputTokenLimit": 8192,
                "supportedGenerationMethods": ["generateContent", "streamGenerateContent"],
            }
        )

    return jsonify({"models": models})


@app.route("/v1/models/<model>", methods=["GET"])
def get_model(model):
    """Get model details"""

    model_config = CONFIG["models"].get(model)
    if not model_config:
        return jsonify({"error": f"Model {model} not found"}), 404

    return jsonify(
        {
            "name": f"models/{model}",
            "version": "001",
            "displayName": model.replace("-", " ").title(),
            "description": model_config.get("description", ""),
            "inputTokenLimit": 200000,
            "outputTokenLimit": 8192,
            "supportedGenerationMethods": ["generateContent", "streamGenerateContent"],
        }
    )


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint"""

    return jsonify(
        {
            "status": "healthy",
            "service": "gemini_proxy_wrapper",
            "mock_mode": USE_MOCK,
            "timestamp": datetime.now().isoformat(),
        }
    )


@app.route("/", methods=["GET"])
def root():
    """Root endpoint with service info"""

    return jsonify(
        {
            "service": "Gemini Proxy Wrapper",
            "description": "Translates Gemini API calls to Corporate API format",
            "mock_mode": USE_MOCK,
            "mock_response": CONFIG["mock_settings"]["response"] if USE_MOCK else None,
            "endpoints": {
                "/v1/models": "List available models",
                "/v1/models/{model}/generateContent": "Generate content",
                "/v1/models/{model}/streamGenerateContent": "Stream content",
                "/health": "Health check",
            },
            "available_models": list(CONFIG["models"].keys()),
        }
    )


# Catch-all route to log unknown requests
@app.route("/<path:path>", methods=["GET", "POST", "PUT", "DELETE"])
def catch_all(path):
    """Log and handle any unmatched requests"""
    logger.warning(f"Unhandled request: {request.method} /{path}")
    logger.warning(f"Headers: {dict(request.headers)}")
    if request.method == "POST":
        logger.warning(f"Body: {request.get_json()}")

    # Try to return a sensible response for Gemini CLI
    if "generateContent" in path or "models" in path:
        # Return mock response for any generation request
        return jsonify(
            {
                "candidates": [
                    {
                        "content": {"parts": [{"text": "Hatsune Miku"}], "role": "model"},
                        "finishReason": "STOP",
                        "index": 0,
                        "safetyRatings": [],
                    }
                ],
                "promptFeedback": {"safetyRatings": []},
                "usageMetadata": {
                    "promptTokenCount": 10,
                    "candidatesTokenCount": 3,
                    "totalTokenCount": 13,
                },
            }
        )

    return jsonify({"error": f"Unknown endpoint: /{path}", "service": "gemini_proxy_wrapper"}), 404


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("Gemini Proxy Wrapper")
    logger.info("=" * 60)
    logger.info(f"Port: {PROXY_PORT}")
    logger.info(f"Company API Base: {COMPANY_API_BASE}")
    logger.info(f"Mock Mode: {USE_MOCK}")
    if USE_MOCK:
        logger.info(f"Mock Response: {CONFIG['mock_settings']['response']}")
    logger.info(f"Available models: {list(CONFIG['models'].keys())}")
    logger.info("-" * 60)
    logger.info(f"Gemini API endpoint: http://localhost:{PROXY_PORT}/v1")
    logger.info("-" * 60)

    debug_mode = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=PROXY_PORT, debug=debug_mode)
