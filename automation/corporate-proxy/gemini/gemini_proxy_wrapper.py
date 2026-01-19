#!/usr/bin/env python3
"""
Gemini API Proxy Wrapper with Dual Mode Tool Support
Intercepts Gemini API calls and redirects them through the corporate proxy
Supports both tool-enabled and non-tool-enabled endpoints
"""

from datetime import datetime
import json
import logging
import os
from pathlib import Path

# Import text-based tool parser for non-tool-enabled mode
import sys
import time

from flask import Flask, Response, jsonify, request, stream_with_context
from flask_cors import CORS

# Import tool executor module
from gemini_tool_executor import GEMINI_TOOLS, execute_tool_call
import requests

# Import translation functions from the new module
from translation import get_model_tool_mode, translate_company_to_gemini, translate_gemini_to_company

sys.path.append(str(Path(__file__).parent.parent))
from shared.services.text_tool_parser import TextToolParser  # noqa: E402

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Load configuration
CONFIG_PATH = Path(__file__).parent / "config" / "gemini-config.json"
with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    CONFIG = json.load(f)

# Configuration from environment and config file
COMPANY_API_BASE = os.environ.get("COMPANY_API_BASE", CONFIG["corporate_api"]["base_url"])
COMPANY_API_TOKEN = os.environ.get(CONFIG["corporate_api"]["token_env_var"], CONFIG["corporate_api"]["default_token"])
USE_MOCK = os.environ.get("USE_MOCK_API", str(CONFIG["mock_settings"]["enabled"])).lower() == "true"
PROXY_PORT = int(os.environ.get("GEMINI_PROXY_PORT", CONFIG["proxy_settings"]["port"]))

# Default tool mode configuration (can be overridden per model)
DEFAULT_TOOL_MODE = os.environ.get("DEFAULT_TOOL_MODE", CONFIG.get("default_tool_mode", "native")).lower()
MAX_TOOL_ITERATIONS = int(os.environ.get("MAX_TOOL_ITERATIONS", CONFIG.get("max_tool_iterations", 5)))

# Initialize text tool parser for text mode
text_tool_parser = TextToolParser(tool_executor=execute_tool_call)


# Translation functions are now imported from the translation module
# This improves code organization and separation of concerns

# Re-export translation functions for backward compatibility with tests
__all__ = ["get_model_tool_mode", "translate_gemini_to_company", "translate_company_to_gemini"]


@app.route("/v1/models/<model>/generateContent", methods=["POST"])
@app.route("/v1/models/<model>:generateContent", methods=["POST"])
@app.route("/v1beta/models/<model>:generateContent", methods=["POST"])
@app.route("/models/<model>:generateContent", methods=["POST"])
@app.route("/v1beta/models/<path:model>", methods=["POST"])  # Catch-all for v1beta
def generate_content(model):
    """Handle Gemini generateContent API calls with tool support"""

    try:
        gemini_request = request.json
        gemini_request["model"] = model

        logger.info("Received Gemini request for model: %s", model)
        logger.debug("Request body: %s", json.dumps(gemini_request, indent=2))

        # Check if tools are provided
        tools = gemini_request.get("tools", [])
        if tools:
            logger.info("Tools provided: %d tool(s)", len(tools))
            for tool in tools:
                if "functionDeclarations" in tool:
                    for func in tool["functionDeclarations"]:
                        logger.info("  - Tool: %s", func.get("name", "unknown"))

        # Translate to Company format
        endpoint, company_request, tools = translate_gemini_to_company(gemini_request)

        # Make request to Company API or use mock
        if USE_MOCK:
            # In mock mode, call the unified_tool_api which now supports Gemini mode
            mock_api_base = os.environ.get("MOCK_API_BASE", "http://localhost:8050")
            company_url = f"{mock_api_base}/api/v1/AI/GenAIExplorationLab/Models/{endpoint}"

            logger.info("Mock mode: Forwarding to unified_tool_api: %s", company_url)

            try:
                response = requests.post(
                    company_url,
                    json=company_request,
                    headers={"Content-Type": "application/json"},
                    timeout=10,
                )

                if response.status_code != 200:
                    logger.warning("Mock API error: %d, using fallback response", response.status_code)
                    # Fallback response if mock API is not available
                    company_response = {
                        "content": [{"text": f"Mock API unavailable at {mock_api_base}. This is a fallback response."}],
                        "usage": {"input_tokens": 10, "output_tokens": 20},
                    }
                else:
                    company_response = response.json()
            except (requests.exceptions.RequestException, requests.exceptions.Timeout):
                logger.warning("Could not connect to mock API, using fallback response")
                # Fallback response if mock API is not available
                company_response = {
                    "content": [{"text": f"Mock API unavailable at {mock_api_base}. This is a fallback response."}],
                    "usage": {"input_tokens": 10, "output_tokens": 20},
                }
        else:
            company_url = f"{COMPANY_API_BASE}/api/v1/AI/GenAIExplorationLab/Models/{endpoint}"

            logger.info("Forwarding to Company API: %s", company_url)

            response = requests.post(
                company_url,
                json=company_request,
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {COMPANY_API_TOKEN}"},
                timeout=CONFIG["proxy_settings"]["timeout"],
            )

            if response.status_code != 200:
                logger.error("Company API error: %d %s", response.status_code, response.text)
                # Return a proper Gemini error response instead of just an error
                error_response = {
                    "candidates": [
                        {
                            "content": {"parts": [{"text": f"API error: {response.status_code}"}], "role": "model"},
                            "finishReason": "STOP",
                            "index": 0,
                            "safetyRatings": [],
                        }
                    ],
                    "promptFeedback": {"safetyRatings": []},
                    "usageMetadata": {
                        "promptTokenCount": 0,
                        "candidatesTokenCount": 0,
                        "totalTokenCount": 0,
                    },
                }
                return jsonify(error_response)

            # Try to parse JSON response
            try:
                company_response = response.json()
            except json.JSONDecodeError as e:
                logger.error("Failed to parse Company API response as JSON: %s", e)
                logger.error("Raw response: %s", response.text[:500])
                # If response is plain text, wrap it in expected format
                company_response = {
                    "content": [{"text": response.text}],
                    "usage": {"input_tokens": 10, "output_tokens": len(response.text.split())},
                }

        # Translate back to Gemini format
        gemini_response = translate_company_to_gemini(company_response, gemini_request, tools)

        logger.debug("Gemini response: %s", json.dumps(gemini_response, indent=2))

        return jsonify(gemini_response)

    except requests.exceptions.Timeout:
        logger.error("Company API timeout")
        error_response = {
            "candidates": [
                {
                    "content": {"parts": [{"text": "Request timeout"}], "role": "model"},
                    "finishReason": "STOP",
                    "index": 0,
                    "safetyRatings": [],
                }
            ],
            "promptFeedback": {"safetyRatings": []},
            "usageMetadata": {
                "promptTokenCount": 0,
                "candidatesTokenCount": 0,
                "totalTokenCount": 0,
            },
        }
        return jsonify(error_response)
    except Exception as e:
        logger.error("Error processing request: %s", e, exc_info=True)
        # Return a proper Gemini format error response
        error_response = {
            "candidates": [
                {
                    "content": {"parts": [{"text": f"Internal error: {str(e)}"}], "role": "model"},
                    "finishReason": "STOP",
                    "index": 0,
                    "safetyRatings": [],
                }
            ],
            "promptFeedback": {"safetyRatings": []},
            "usageMetadata": {
                "promptTokenCount": 0,
                "candidatesTokenCount": 0,
                "totalTokenCount": 0,
            },
        }
        return jsonify(error_response)


@app.route("/v1/models/<model>/streamGenerateContent", methods=["POST"])
@app.route("/v1/models/<model>:streamGenerateContent", methods=["POST"])
@app.route("/v1beta/models/<model>:streamGenerateContent", methods=["POST"])
@app.route("/models/<model>:streamGenerateContent", methods=["POST"])
def stream_generate_content(model):
    """Handle Gemini streaming API calls with tool support"""

    try:
        gemini_request = request.json
        gemini_request["model"] = model

        logger.info("Received streaming request for model: %s", model)

        # Translate to Company format
        endpoint, company_request, tools = translate_gemini_to_company(gemini_request)

        # For streaming with tools, we need to handle it differently
        if tools:
            # Can't truly stream with tools, but we can simulate it
            logger.warning("Streaming with tools is not fully supported; simulating streaming response.")

            # Get the non-streaming response
            endpoint, company_request, _tools_list = translate_gemini_to_company(gemini_request)

            if USE_MOCK:
                # In mock mode, call the unified_tool_api
                mock_api_base = os.environ.get("MOCK_API_BASE", "http://localhost:8050")
                company_url = f"{mock_api_base}/api/v1/AI/GenAIExplorationLab/Models/{endpoint}"

                try:
                    response = requests.post(
                        company_url,
                        json=company_request,
                        headers={"Content-Type": "application/json"},
                        timeout=10,
                    )

                    if response.status_code != 200:
                        company_response = {
                            "content": [{"text": "Mock API error. Fallback response."}],
                            "usage": {"input_tokens": 10, "output_tokens": 5},
                        }
                    else:
                        company_response = response.json()
                except (requests.exceptions.RequestException, requests.exceptions.Timeout):
                    company_response = {
                        "content": [{"text": "Mock API unavailable. Fallback response."}],
                        "usage": {"input_tokens": 10, "output_tokens": 5},
                    }
            else:
                company_url = f"{COMPANY_API_BASE}/api/v1/AI/GenAIExplorationLab/Models/{endpoint}"
                response = requests.post(
                    company_url,
                    json=company_request,
                    headers={"Content-Type": "application/json", "Authorization": f"Bearer {COMPANY_API_TOKEN}"},
                    timeout=CONFIG["proxy_settings"]["timeout"],
                )

                if response.status_code != 200:
                    company_response = {
                        "content": [{"text": f"API error: {response.status_code}"}],
                        "usage": {"input_tokens": 10, "output_tokens": 5},
                    }
                else:
                    try:
                        company_response = response.json()
                    except json.JSONDecodeError as e:
                        logger.error("Failed to parse streaming response as JSON: %s", e)
                        company_response = {
                            "content": [{"text": response.text}],
                            "usage": {"input_tokens": 10, "output_tokens": len(response.text.split())},
                        }

            # Convert to streaming format
            gemini_response = translate_company_to_gemini(company_response, gemini_request, tools)

            # Create a streaming response
            def generate_tool_stream():
                # Send the response as a single chunk for now
                # This ensures proper JSON formatting
                chunk = {
                    "candidates": gemini_response.get("candidates", []),
                    "promptFeedback": gemini_response.get("promptFeedback", {"safetyRatings": []}),
                    "usageMetadata": gemini_response.get("usageMetadata", {}),
                }
                yield f"data: {json.dumps(chunk)}\n\n"

            return Response(
                stream_with_context(generate_tool_stream()),
                mimetype="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )

        # Make request to Company API
        if USE_MOCK:
            company_response = {
                "content": [{"text": "This is a streaming mock response from Gemini proxy."}],
                "usage": {"input_tokens": 10, "output_tokens": 20},
            }
        else:
            company_url = f"{COMPANY_API_BASE}/api/v1/AI/GenAIExplorationLab/Models/{endpoint}"

            response = requests.post(
                company_url,
                json=company_request,
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {COMPANY_API_TOKEN}"},
                timeout=CONFIG["proxy_settings"]["timeout"],
            )

            if response.status_code != 200:
                logger.error("Company API error: %d", response.status_code)
                # Return error in streaming format
                error_response = {
                    "candidates": [
                        {
                            "content": {"parts": [{"text": f"API error: {response.status_code}"}], "role": "model"},
                            "finishReason": "STOP",
                            "index": 0,
                        }
                    ]
                }

                def generate_error():
                    yield f"data: {json.dumps(error_response)}\n\n"

                return Response(
                    stream_with_context(generate_error()),
                    mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
                )

            try:
                company_response = response.json()
            except json.JSONDecodeError as e:
                logger.error("Failed to parse response as JSON: %s", e)
                company_response = {
                    "content": [{"text": response.text}],
                    "usage": {"input_tokens": 10, "output_tokens": len(response.text.split())},
                }

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
        logger.error("Streaming error: %s", e)
        # Return error in Gemini format
        error_response = {
            "candidates": [
                {
                    "content": {"parts": [{"text": f"Streaming error: {str(e)}"}], "role": "model"},
                    "finishReason": "STOP",
                    "index": 0,
                    "safetyRatings": [],
                }
            ],
            "promptFeedback": {"safetyRatings": []},
            "usageMetadata": {
                "promptTokenCount": 0,
                "candidatesTokenCount": 0,
                "totalTokenCount": 0,
            },
        }
        return jsonify(error_response)


@app.route("/v1/models", methods=["GET"])
def list_models():
    """List available models in Gemini format"""

    models = []
    for model_name, model_cfg in CONFIG["models"].items():
        models.append(
            {
                "name": f"models/{model_name}",
                "version": "001",
                "displayName": model_name.replace("-", " ").title(),
                "description": model_cfg.get("description", ""),
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
        # Return error in Gemini format
        error_response = {
            "candidates": [
                {
                    "content": {"parts": [{"text": f"Model {model} not found"}], "role": "model"},
                    "finishReason": "STOP",
                    "index": 0,
                    "safetyRatings": [],
                }
            ],
            "promptFeedback": {"safetyRatings": []},
            "usageMetadata": {
                "promptTokenCount": 0,
                "candidatesTokenCount": 0,
                "totalTokenCount": 0,
            },
        }
        return jsonify(error_response)

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

    # Get tool modes for all models
    model_tool_modes = {}
    for model_name in CONFIG["models"].keys():
        model_tool_modes[model_name] = get_model_tool_mode(model_name)

    return jsonify(
        {
            "status": "healthy",
            "service": "gemini_proxy_wrapper",
            "mock_mode": USE_MOCK,
            "tools_enabled": True,
            "default_tool_mode": DEFAULT_TOOL_MODE,
            "model_tool_modes": model_tool_modes,
            "timestamp": datetime.now().isoformat(),
        }
    )


@app.route("/tools", methods=["GET"])
def list_tools():
    """List available tools with per-model mode information"""

    # Get tool modes for all models
    model_tool_modes = {}
    for model_name in CONFIG["models"].keys():
        model_tool_modes[model_name] = get_model_tool_mode(model_name)

    return jsonify(
        {
            "tools": list(GEMINI_TOOLS.keys()),
            "definitions": GEMINI_TOOLS,
            "default_mode": DEFAULT_TOOL_MODE,
            "model_tool_modes": model_tool_modes,
        }
    )


@app.route("/execute", methods=["POST"])
def execute_tool():
    """Direct tool execution endpoint for testing"""

    data = request.json
    tool_name = data.get("tool")
    parameters = data.get("parameters", {})

    if tool_name not in GEMINI_TOOLS:
        # Return error in Gemini format
        error_response = {
            "candidates": [
                {
                    "content": {"parts": [{"text": f"Unknown tool: {tool_name}"}], "role": "model"},
                    "finishReason": "STOP",
                    "index": 0,
                    "safetyRatings": [],
                }
            ],
            "promptFeedback": {"safetyRatings": []},
            "usageMetadata": {
                "promptTokenCount": 0,
                "candidatesTokenCount": 0,
                "totalTokenCount": 0,
            },
        }
        return jsonify(error_response)

    result = execute_tool_call(tool_name, parameters)
    return jsonify(result)


@app.route("/v1/models/<model>/continueWithTools", methods=["POST"])
@app.route("/v1/models/<model>:continueWithTools", methods=["POST"])
def continue_with_tools(model):
    """
    Continue a conversation after tool execution in text mode
    This endpoint handles the feedback loop for non-tool-enabled endpoints
    """

    try:
        data = request.json

        # Extract the previous response and tool results
        previous_response = data.get("previous_response", "")
        tool_results = data.get("tool_results", [])
        original_request = data.get("original_request", {})
        conversation_history = data.get("conversation_history", [])

        logger.info("Continuing conversation with %d tool results", len(tool_results))

        # Format tool results for feedback
        formatted_results = text_tool_parser.format_tool_results(tool_results)

        # Build continuation prompt
        continuation_prompt = f"""Here are the results from the tool executions:

{formatted_results}

Based on these results, please continue with the task. If you need to use more tools, you can do so. \
If the task is complete, provide a summary of what was accomplished."""

        # Add the previous AI response and tool results to conversation history
        updated_messages = conversation_history.copy()
        updated_messages.append({"role": "assistant", "content": previous_response})
        updated_messages.append({"role": "user", "content": continuation_prompt})

        # Create new request for the Company API
        endpoint = CONFIG["models"].get(model, CONFIG["models"]["gemini-2.5-flash"])["endpoint"]

        company_request = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": original_request.get("generationConfig", {}).get("maxOutputTokens", 1000),
            "system": original_request.get("system_prompt", "You are a helpful AI assistant with tool access"),
            "messages": updated_messages,
            "temperature": original_request.get("generationConfig", {}).get("temperature", 0.7),
        }

        # Make request to Company API
        if USE_MOCK:
            mock_api_base = os.environ.get("MOCK_API_BASE", "http://localhost:8050")
            company_url = f"{mock_api_base}/api/v1/AI/GenAIExplorationLab/Models/{endpoint}"

            response = requests.post(
                company_url,
                json=company_request,
                headers={"Content-Type": "application/json"},
                timeout=10,
            )

            if response.status_code != 200:
                company_response = {
                    "content": [{"text": "Continuing with mock response after tool execution."}],
                    "usage": {"input_tokens": 10, "output_tokens": 20},
                }
            else:
                company_response = response.json()
        else:
            company_url = f"{COMPANY_API_BASE}/api/v1/AI/GenAIExplorationLab/Models/{endpoint}"

            response = requests.post(
                company_url,
                json=company_request,
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {COMPANY_API_TOKEN}"},
                timeout=CONFIG["proxy_settings"]["timeout"],
            )

            if response.status_code != 200:
                logger.error("Company API error: %d", response.status_code)
                # Return error in Gemini format
                error_response = {
                    "candidates": [
                        {
                            "content": {"parts": [{"text": f"Upstream API error: {response.status_code}"}], "role": "model"},
                            "finishReason": "STOP",
                            "index": 0,
                            "safetyRatings": [],
                        }
                    ],
                    "promptFeedback": {"safetyRatings": []},
                    "usageMetadata": {
                        "promptTokenCount": 0,
                        "candidatesTokenCount": 0,
                        "totalTokenCount": 0,
                    },
                }
                return jsonify(error_response)

            company_response = response.json()

        # Check if the new response has more tool calls
        response_text = company_response.get("content", [{"text": ""}])[0].get("text", "")
        new_tool_calls = text_tool_parser.parse_tool_calls(response_text)

        # Build response
        result = {
            "response": response_text,
            "has_tool_calls": len(new_tool_calls) > 0,
            "tool_calls": new_tool_calls,
            "conversation_history": updated_messages,
            "complete": text_tool_parser.is_complete_response(response_text),
        }

        return jsonify(result)

    except Exception as e:
        logger.error("Error in continue_with_tools: %s", e, exc_info=True)
        # Return error in Gemini format
        error_response = {
            "candidates": [
                {
                    "content": {"parts": [{"text": f"Error: {str(e)}"}], "role": "model"},
                    "finishReason": "STOP",
                    "index": 0,
                    "safetyRatings": [],
                }
            ],
            "promptFeedback": {"safetyRatings": []},
            "usageMetadata": {
                "promptTokenCount": 0,
                "candidatesTokenCount": 0,
                "totalTokenCount": 0,
            },
        }
        return jsonify(error_response)


@app.route("/", methods=["GET"])
def root():
    """Root endpoint with service info"""

    # Build model info with tool modes
    model_info = {}
    for model_name, model_config in CONFIG["models"].items():
        tool_mode = get_model_tool_mode(model_name)
        model_info[model_name] = {
            "endpoint": model_config["endpoint"],
            "tool_mode": tool_mode,
            "supports_tools": model_config.get("supports_tools", tool_mode == "native"),
        }

    return jsonify(
        {
            "service": "Gemini Proxy Wrapper with Per-Model Tool Support",
            "description": "Translates Gemini API calls to Corporate API format with model-specific tool handling",
            "mock_mode": USE_MOCK,
            "tools_enabled": True,
            "default_tool_mode": DEFAULT_TOOL_MODE,
            "endpoints": {
                "/v1/models": "List available models",
                "/v1/models/{model}/generateContent": "Generate content with tool support",
                "/v1/models/{model}/streamGenerateContent": "Stream content",
                "/v1/models/{model}/continueWithTools": "Continue conversation after tool execution (text mode)",
                "/tools": "List available tools",
                "/execute": "Execute a tool directly",
                "/health": "Health check with model configurations",
            },
            "configuration": {
                "DEFAULT_TOOL_MODE": f"{DEFAULT_TOOL_MODE} (native=tool-enabled endpoints, text=parse from text)",
                "MAX_TOOL_ITERATIONS": MAX_TOOL_ITERATIONS,
                "MODEL_OVERRIDE_FORMAT": "GEMINI_MODEL_OVERRIDE_<model>_tool_mode=<mode>",
            },
            "models": model_info,
            "available_tools": list(GEMINI_TOOLS.keys()),
        }
    )


# Catch-all route to log unknown requests
@app.route("/<path:path>", methods=["GET", "POST", "PUT", "DELETE"])
def catch_all(path):
    """Log and handle any unmatched requests"""
    logger.warning("Unhandled request: %s /%s", request.method, path)
    logger.warning("Headers: %s", dict(request.headers))
    if request.method == "POST":
        logger.warning("Body: %s", request.get_json())

    # Try to return a sensible response for Gemini CLI
    if "generateContent" in path or "models" in path:
        # Return mock response for any generation request
        return jsonify(
            {
                "candidates": [
                    {
                        "content": {"parts": [{"text": "Mock response from Gemini proxy"}], "role": "model"},
                        "finishReason": "STOP",
                        "index": 0,
                        "safetyRatings": [],
                    }
                ],
                "promptFeedback": {"safetyRatings": []},
                "usageMetadata": {
                    "promptTokenCount": 10,
                    "candidatesTokenCount": 5,
                    "totalTokenCount": 15,
                },
            }
        )

    # Return error in Gemini format
    error_response = {
        "candidates": [
            {
                "content": {"parts": [{"text": f"Unknown endpoint: /{path}"}], "role": "model"},
                "finishReason": "STOP",
                "index": 0,
                "safetyRatings": [],
            }
        ],
        "promptFeedback": {"safetyRatings": []},
        "usageMetadata": {
            "promptTokenCount": 0,
            "candidatesTokenCount": 0,
            "totalTokenCount": 0,
        },
    }
    return jsonify(error_response)


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("Gemini Proxy Wrapper with Per-Model Tool Support")
    logger.info("=" * 60)
    logger.info("Port: %d", PROXY_PORT)
    logger.info("Company API Base: %s", COMPANY_API_BASE)
    logger.info("Mock Mode: %s", USE_MOCK)
    logger.info("Default Tool Mode: %s", DEFAULT_TOOL_MODE)
    logger.info("Max Tool Iterations: %d", MAX_TOOL_ITERATIONS)
    logger.info("-" * 60)
    logger.info("Model Configurations:")
    for model_id, config in CONFIG["models"].items():
        mode = get_model_tool_mode(model_id)
        supports_tools = config.get("supports_tools", mode == "native")
        logger.info("  %s: tool_mode=%s, supports_tools=%s", model_id, mode, supports_tools)
    logger.info("-" * 60)
    logger.info("Tool execution handled by gemini_tool_executor module")
    logger.info("Available tools: %s", list(GEMINI_TOOLS.keys()))
    logger.info("-" * 60)
    logger.info("Gemini API endpoint: http://localhost:%d/v1", PROXY_PORT)
    logger.info("Models with text mode will parse tools from response text")
    logger.info("Use /v1/models/{model}/continueWithTools for text mode feedback loop")
    logger.info("-" * 60)
    logger.info("Override model settings with environment variables:")
    logger.info("  GEMINI_MODEL_OVERRIDE_<model>_tool_mode=<native|text>")
    logger.info("-" * 60)

    debug_mode = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=PROXY_PORT, debug=debug_mode)
