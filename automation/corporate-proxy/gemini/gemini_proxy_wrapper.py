#!/usr/bin/env python3
"""
Gemini API Proxy Wrapper with Tool Support
Intercepts Gemini API calls and redirects them through the corporate proxy
Handles tool/function calls for Gemini CLI
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

# Import tool executor module
from gemini_tool_executor import GEMINI_TOOLS, execute_tool_call

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
    """Translate Gemini API request format to Company API format, handling tools"""

    # Extract model and map it
    model = gemini_request.get("model", "gemini-2.5-flash")
    model_config = CONFIG["models"].get(model)

    if not model_config:
        logger.warning(f"Unknown model {model}, using default")
        model_config = CONFIG["models"]["gemini-2.5-flash"]

    endpoint = model_config["endpoint"]

    # Check if tools are requested
    tools = gemini_request.get("tools", [])

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
            if tool_calls and role == "model" and USE_MOCK:
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

    # Add tool descriptions to system prompt if tools are provided
    if tools:
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

    # Build Company API request
    company_request = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": gemini_request.get("generationConfig", {}).get("maxOutputTokens", 1000),
        "system": system_prompt or "You are a helpful AI assistant",
        "messages": messages,
        "temperature": gemini_request.get("generationConfig", {}).get("temperature", 0.7),
    }

    return endpoint, company_request, tools


def translate_company_to_gemini(company_response, original_request, tools=None):
    """Translate Company API response back to Gemini format, checking for tool calls"""

    # Check if the response contains structured tool calls
    # This is now the standard approach with unified_tool_api.py returning tool_calls for Gemini mode
    tool_calls = None

    # Check if the Company API returned tool_calls in a structured format
    if "tool_calls" in company_response:
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
    """Handle Gemini generateContent API calls with tool support"""

    try:
        gemini_request = request.json
        gemini_request["model"] = model

        logger.info(f"Received Gemini request for model: {model}")
        logger.debug(f"Request body: {json.dumps(gemini_request, indent=2)}")

        # Check if tools are provided
        tools = gemini_request.get("tools", [])
        if tools:
            logger.info(f"Tools provided: {len(tools)} tool(s)")
            for tool in tools:
                if "functionDeclarations" in tool:
                    for func in tool["functionDeclarations"]:
                        logger.info(f"  - Tool: {func.get('name', 'unknown')}")

        # Translate to Company format
        endpoint, company_request, tools = translate_gemini_to_company(gemini_request)

        # Make request to Company API or use mock
        if USE_MOCK:
            # In mock mode, call the unified_tool_api which now supports Gemini mode
            mock_api_base = os.environ.get("MOCK_API_BASE", "http://localhost:8050")
            company_url = f"{mock_api_base}/api/v1/AI/GenAIExplorationLab/Models/{endpoint}"

            logger.info(f"Mock mode: Forwarding to unified_tool_api: {company_url}")

            try:
                response = requests.post(
                    company_url,
                    json=company_request,
                    headers={"Content-Type": "application/json"},
                    timeout=10,
                )

                if response.status_code != 200:
                    logger.warning(f"Mock API error: {response.status_code}, using fallback response")
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
        gemini_response = translate_company_to_gemini(company_response, gemini_request, tools)

        logger.debug(f"Gemini response: {json.dumps(gemini_response, indent=2)}")

        return jsonify(gemini_response)

    except requests.exceptions.Timeout:
        logger.error("Company API timeout")
        return jsonify({"error": "Request timeout"}), 504
    except Exception as e:
        logger.error(f"Error processing request: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/v1/models/<model>/streamGenerateContent", methods=["POST"])
@app.route("/v1/models/<model>:streamGenerateContent", methods=["POST"])
@app.route("/v1beta/models/<model>:streamGenerateContent", methods=["POST"])
@app.route("/models/<model>:streamGenerateContent", methods=["POST"])
def stream_generate_content(model):
    """Handle Gemini streaming API calls with tool support"""

    try:
        gemini_request = request.json
        gemini_request["model"] = model

        logger.info(f"Received streaming request for model: {model}")

        # Translate to Company format
        endpoint, company_request, tools = translate_gemini_to_company(gemini_request)

        # For streaming with tools, we need to handle it differently
        if tools:
            # Can't truly stream with tools, but we can simulate it
            logger.warning("Streaming with tools is not fully supported; simulating streaming response.")

            # Get the non-streaming response
            endpoint, company_request, tools_list = translate_gemini_to_company(gemini_request)

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
                        "content": [{"text": "API error occurred."}],
                        "usage": {"input_tokens": 10, "output_tokens": 5},
                    }
                else:
                    company_response = response.json()

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
            "tools_enabled": True,
            "timestamp": datetime.now().isoformat(),
        }
    )


@app.route("/tools", methods=["GET"])
def list_tools():
    """List available tools"""

    return jsonify({"tools": list(GEMINI_TOOLS.keys()), "definitions": GEMINI_TOOLS})


@app.route("/execute", methods=["POST"])
def execute_tool():
    """Direct tool execution endpoint for testing"""

    data = request.json
    tool_name = data.get("tool")
    parameters = data.get("parameters", {})

    if tool_name not in GEMINI_TOOLS:
        return jsonify({"error": f"Unknown tool: {tool_name}"}), 400

    result = execute_tool_call(tool_name, parameters)
    return jsonify(result)


@app.route("/", methods=["GET"])
def root():
    """Root endpoint with service info"""

    return jsonify(
        {
            "service": "Gemini Proxy Wrapper with Tools",
            "description": "Translates Gemini API calls to Corporate API format with tool support",
            "mock_mode": USE_MOCK,
            "tools_enabled": True,
            "endpoints": {
                "/v1/models": "List available models",
                "/v1/models/{model}/generateContent": "Generate content with tool support",
                "/v1/models/{model}/streamGenerateContent": "Stream content",
                "/tools": "List available tools",
                "/execute": "Execute a tool directly",
                "/health": "Health check",
            },
            "available_models": list(CONFIG["models"].keys()),
            "available_tools": list(GEMINI_TOOLS.keys()),
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

    return jsonify({"error": f"Unknown endpoint: /{path}", "service": "gemini_proxy_wrapper"}), 404


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("Gemini Proxy Wrapper with Tool Support")
    logger.info("=" * 60)
    logger.info(f"Port: {PROXY_PORT}")
    logger.info(f"Company API Base: {COMPANY_API_BASE}")
    logger.info(f"Mock Mode: {USE_MOCK}")
    logger.info("Tool execution handled by gemini_tool_executor module")
    logger.info(f"Available models: {list(CONFIG['models'].keys())}")
    logger.info(f"Available tools: {list(GEMINI_TOOLS.keys())}")
    logger.info("-" * 60)
    logger.info(f"Gemini API endpoint: http://localhost:{PROXY_PORT}/v1")
    logger.info("-" * 60)

    debug_mode = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=PROXY_PORT, debug=debug_mode)
