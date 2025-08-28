#!/usr/bin/env python3
"""
Integration test for Crush and OpenCode tool execution.
Tests that tools actually execute when receiving properly formatted tool calls.
"""

import json
import logging
import os
import subprocess
import tempfile
import time
from pathlib import Path

import requests
from flask import Flask, jsonify, request

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class ToolCallTestServer:
    """Mock API server that sends proper tool call responses"""

    def __init__(self, port: int = 8050):
        self.app = Flask(__name__)
        self.port = port
        self.tool_responses = []
        self.setup_routes()

    def setup_routes(self):
        """Setup Flask routes"""

        @self.app.route("/health", methods=["GET"])
        def health():
            return jsonify({"status": "healthy"}), 200

        @self.app.route("/api/v1/AI/GenAIExplorationLab/Models/<path:model_path>", methods=["POST"])
        def handle_request(model_path):
            """Handle incoming requests and return tool calls"""
            data = request.json
            messages = data.get("messages", [])
            tools = data.get("tools", [])

            logger.info(f"Received request with {len(messages)} messages and {len(tools)} tools")

            # Check if this is a tool result being sent back
            if messages and messages[-1].get("role") == "tool":
                # Tool was executed, return success message
                return (
                    jsonify(
                        {
                            "id": "msg_test_success",
                            "type": "message",
                            "role": "assistant",
                            "model": "test-model",
                            "content": [{"type": "text", "text": "Tool executed successfully!"}],
                            "stop_reason": "end_turn",
                            "usage": {"input_tokens": 10, "output_tokens": 5},
                        }
                    ),
                    200,
                )

            # First request - return a tool call
            if tools and any(t.get("function", {}).get("name") == "write" for t in tools):
                # Return a write tool call
                response = {
                    "id": "msg_test_123",
                    "type": "message",
                    "role": "assistant",
                    "model": "test-model",
                    "content": [],
                    "tool_calls": [
                        {
                            "id": "toolu_test_001",
                            "type": "function",
                            "function": {
                                "name": "write",
                                "arguments": json.dumps(
                                    {"file_path": "test_output.txt", "content": "Integration test successful!"}
                                ),
                            },
                        }
                    ],
                    "stop_reason": "tool_use",
                    "usage": {"input_tokens": 10, "output_tokens": 3},
                }
                logger.info(f"Sending tool call response: {response}")
                return jsonify(response), 200

            # Default response
            return (
                jsonify(
                    {
                        "id": "msg_test_default",
                        "type": "message",
                        "role": "assistant",
                        "model": "test-model",
                        "content": [{"type": "text", "text": "No tools available"}],
                        "stop_reason": "end_turn",
                        "usage": {"input_tokens": 10, "output_tokens": 5},
                    }
                ),
                200,
            )

    def start(self):
        """Start the test server"""
        from threading import Thread

        thread = Thread(target=lambda: self.app.run(host="0.0.0.0", port=self.port, debug=False))
        thread.daemon = True
        thread.start()
        time.sleep(2)  # Wait for server to start
        logger.info(f"Test server started on port {self.port}")


class TranslationWrapperTestServer:
    """Translation wrapper that properly forwards tool calls"""

    def __init__(self, port: int = 8052, backend_port: int = 8050):
        self.app = Flask(__name__)
        self.port = port
        self.backend_port = backend_port
        self.setup_routes()

    def setup_routes(self):
        """Setup Flask routes"""

        @self.app.route("/health", methods=["GET"])
        def health():
            return jsonify({"status": "healthy"}), 200

        @self.app.route("/v1/chat/completions", methods=["POST"])
        def chat_completions():
            """Forward requests to backend and translate responses"""
            data = request.json
            logger.info(f"Translation wrapper received: {data.get('model')}")

            # Extract messages and tools
            messages = data.get("messages", [])
            tools = data.get("tools", [])

            # Forward to backend
            backend_url = f"http://localhost:{self.backend_port}/api/v1/AI/GenAIExplorationLab/Models/test"
            backend_request = {"messages": messages, "tools": tools, "max_tokens": data.get("max_tokens", 1000)}

            response = requests.post(backend_url, json=backend_request, headers={"Authorization": "Bearer test-token"})

            if response.status_code != 200:
                return jsonify({"error": "Backend error"}), 500

            backend_response = response.json()

            # Convert to OpenAI format
            if "tool_calls" in backend_response:
                # Tool call response
                openai_response = {
                    "id": backend_response.get("id"),
                    "object": "chat.completion",
                    "created": int(time.time()),
                    "model": data.get("model"),
                    "choices": [
                        {
                            "index": 0,
                            "message": {"role": "assistant", "content": None, "tool_calls": backend_response["tool_calls"]},
                            "finish_reason": "tool_calls",
                        }
                    ],
                    "usage": backend_response.get("usage", {}),
                }
            else:
                # Regular response
                content = backend_response.get("content", [])
                text = content[0].get("text", "") if content else ""
                openai_response = {
                    "id": backend_response.get("id"),
                    "object": "chat.completion",
                    "created": int(time.time()),
                    "model": data.get("model"),
                    "choices": [{"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": "stop"}],
                    "usage": backend_response.get("usage", {}),
                }

            logger.info(f"Returning OpenAI format: {openai_response}")
            return jsonify(openai_response), 200

    def start(self):
        """Start the wrapper server"""
        from threading import Thread

        thread = Thread(target=lambda: self.app.run(host="0.0.0.0", port=self.port, debug=False))
        thread.daemon = True
        thread.start()
        time.sleep(2)  # Wait for server to start
        logger.info(f"Translation wrapper started on port {self.port}")


def test_crush_tool_execution():
    """Test that Crush actually executes the write tool"""
    logger.info("=== Testing Crush Tool Execution ===")

    # Create a test directory
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test_output.txt"

        # Start test servers
        backend = ToolCallTestServer(port=8050)
        backend.start()

        wrapper = TranslationWrapperTestServer(port=8052, backend_port=8050)
        wrapper.start()

        # Run Crush with a simple request
        cmd = [
            "docker",
            "run",
            "--rm",
            "--user",
            f"{os.getuid()}:{os.getgid()}",
            "-v",
            f"{tmpdir}:/workspace",
            "-e",
            "HOME=/tmp",
            "-e",
            "OPENAI_API_KEY=test-token",
            "-e",
            "OPENAI_BASE_URL=http://host.docker.internal:8052/v1",
            "--add-host",
            "host.docker.internal:host-gateway",
            "crush-corporate:latest",
            "bash",
            "-c",
            "cd /workspace && /usr/local/bin/crush-binary run 'Create a test file'",
        ]

        logger.info(f"Running Crush: {' '.join(cmd)}")

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            logger.info(f"Crush stdout: {result.stdout}")
            logger.info(f"Crush stderr: {result.stderr}")

            # Check if file was created
            if test_file.exists():
                content = test_file.read_text()
                logger.info(f"✅ SUCCESS: File created with content: {content}")
                return True
            else:
                logger.error("❌ FAIL: File was not created")
                return False

        except subprocess.TimeoutExpired:
            logger.error("❌ FAIL: Command timed out")
            return False
        except Exception as e:
            logger.error(f"❌ FAIL: Error running command: {e}")
            return False


def test_opencode_tool_execution():
    """Test that OpenCode actually executes the write tool"""
    logger.info("=== Testing OpenCode Tool Execution ===")

    # Create a test directory
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test_output.txt"

        # Start test servers
        backend = ToolCallTestServer(port=8050)
        backend.start()

        wrapper = TranslationWrapperTestServer(port=8052, backend_port=8050)
        wrapper.start()

        # Run OpenCode with a simple request
        cmd = [
            "docker",
            "run",
            "--rm",
            "--user",
            f"{os.getuid()}:{os.getgid()}",
            "-v",
            f"{tmpdir}:/workspace",
            "-e",
            "HOME=/tmp",
            "-e",
            "OPENROUTER_API_KEY=test-token",
            "-e",
            "OPENROUTER_BASE_URL=http://host.docker.internal:8052/v1",
            "--add-host",
            "host.docker.internal:host-gateway",
            "opencode-corporate:latest",
            "bash",
            "-c",
            "cd /workspace && /usr/local/bin/opencode.bin run 'Create a test file'",
        ]

        logger.info(f"Running OpenCode: {' '.join(cmd)}")

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            logger.info(f"OpenCode stdout: {result.stdout}")
            logger.info(f"OpenCode stderr: {result.stderr}")

            # Check if file was created
            if test_file.exists():
                content = test_file.read_text()
                logger.info(f"✅ SUCCESS: File created with content: {content}")
                return True
            else:
                logger.error("❌ FAIL: File was not created")
                return False

        except subprocess.TimeoutExpired:
            logger.error("❌ FAIL: Command timed out")
            return False
        except Exception as e:
            logger.error(f"❌ FAIL: Error running command: {e}")
            return False


def main():
    """Run all integration tests"""
    logger.info("Starting Tool Execution Integration Tests")
    logger.info("=" * 60)

    # Check if containers exist
    crush_exists = subprocess.run(
        ["docker", "images", "-q", "crush-corporate:latest"], capture_output=True, text=True
    ).stdout.strip()

    opencode_exists = subprocess.run(
        ["docker", "images", "-q", "opencode-corporate:latest"], capture_output=True, text=True
    ).stdout.strip()

    results = []

    if crush_exists:
        logger.info("Testing Crush...")
        results.append(("Crush", test_crush_tool_execution()))
    else:
        logger.warning("Crush container not found, skipping test")
        logger.info("Build with: ./automation/corporate-proxy/crush/scripts/build.sh")

    if opencode_exists:
        logger.info("Testing OpenCode...")
        results.append(("OpenCode", test_opencode_tool_execution()))
    else:
        logger.warning("OpenCode container not found, skipping test")
        logger.info("Build with: ./automation/corporate-proxy/opencode/scripts/build.sh")

    # Print summary
    logger.info("\n" + "=" * 60)
    logger.info("Test Results Summary:")
    for name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        logger.info(f"  {name}: {status}")

    all_passed = all(passed for _, passed in results)
    if all_passed:
        logger.info("\n🎉 All tests passed!")
        return 0
    else:
        logger.error("\n❌ Some tests failed")
        return 1


if __name__ == "__main__":
    exit(main())
