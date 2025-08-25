#!/usr/bin/env python3
"""
Mock Company API Endpoint
Mimics the company's AI Gateway API format for testing
Always returns "Hatsune Miku" as response
"""

import logging
import os
import time
from datetime import datetime

from flask import Flask, Response, jsonify, request
from flask_cors import CORS

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Mock secret token for testing
MOCK_SECRET_TOKEN = "test-secret-token-123"


@app.route("/api/v1/AI/GenAIExplorationLab/Models/<path:model_path>", methods=["POST"])
def mock_company_endpoint(model_path: str) -> Response:
    """Mock endpoint that mimics the company API format"""

    # Log the request details
    logger.info(f"Received request for model: {model_path}")
    logger.info(f"Headers: {dict(request.headers)}")
    logger.info(f"Body: {request.get_json()}")

    # Check authorization
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return jsonify({"error": "Unauthorized"}), 401

    token = auth_header.replace("Bearer ", "")
    if token != MOCK_SECRET_TOKEN:
        logger.warning(f"Invalid token received: {token}")
        return jsonify({"error": "Invalid token"}), 401

    # Parse request body
    try:
        body = request.get_json()
        messages = body.get("messages", [])
        max_tokens = body.get("max_tokens", 1000)
        system_prompt = body.get("system", "")

        # Log what we received
        logger.info(f"System prompt: {system_prompt}")
        logger.info(f"Messages: {messages}")
        logger.info(f"Max tokens: {max_tokens}")

    except Exception as e:
        logger.error(f"Error parsing request: {e}")
        return jsonify({"error": "Invalid request body"}), 400

    # Always return "Hatsune Miku" as the response
    response = {
        "id": f"msg_mock_{int(time.time())}",
        "type": "message",
        "role": "assistant",
        "model": "mock-model",
        "content": [{"type": "text", "text": "Hatsune Miku"}],
        "stop_reason": "end_turn",
        "stop_sequence": None,
        "usage": {"input_tokens": 10, "output_tokens": 3},
    }

    logger.info(f"Returning mock response: {response}")
    return jsonify(response), 200


@app.route("/health", methods=["GET"])
def health_check() -> Response:
    """Health check endpoint"""
    return jsonify({"status": "healthy", "service": "mock_company_api", "timestamp": datetime.now().isoformat()}), 200


@app.route("/", methods=["GET"])
def root() -> Response:
    """Root endpoint with API info"""
    return (
        jsonify(
            {
                "service": "Mock Company API",
                "description": "Mock endpoint that always returns 'Hatsune Miku'",
                "endpoints": ["/api/v1/AI/GenAIExplorationLab/Models/<model_path>", "/health"],
                "auth": {"type": "Bearer token", "test_token": MOCK_SECRET_TOKEN},
            }
        ),
        200,
    )


if __name__ == "__main__":
    port = int(os.environ.get("MOCK_API_PORT", 8050))
    logger.info(f"Starting Mock Company API on port {port}")
    logger.info(f"Test token: {MOCK_SECRET_TOKEN}")
    model_endpoint = "ai-coe-bedrock-claude35-sonnet-200k:analyze=null"
    logger.info(f"Example endpoint: http://localhost:{port}/api/v1/AI/GenAIExplorationLab/Models/{model_endpoint}")
    debug_mode = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug_mode)
