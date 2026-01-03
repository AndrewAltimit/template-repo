#!/usr/bin/env python3
"""
Tests for Unified Tool API - Mock service endpoints and dual API spec support.

Tests cover:
- Health and info endpoints
- Tool listing and execution
- OpenAI-compatible /chat/completions endpoint
- Anthropic-compatible /messages endpoint
- Dual API spec detection and conversion
- Bedrock endpoint with API spec support
"""

import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "shared" / "services"))


class TestUnifiedToolAPIBasics(unittest.TestCase):
    """Tests for basic endpoints: health, info, tools."""

    def setUp(self):
        """Set up test client."""
        with patch.dict("os.environ", {"API_MODE": "crush", "TOOL_API_SPEC": "openai"}):
            from unified_tool_api import app

            self.app = app
            self.client = app.test_client()

    def test_health_endpoint(self):
        """Test health check returns correct status."""
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)

        data = response.get_json()
        self.assertEqual(data["status"], "healthy")
        self.assertIn("mode", data)
        self.assertIn("version", data)
        self.assertIn("timestamp", data)

    def test_root_endpoint_info(self):
        """Test root endpoint returns API info."""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)

        data = response.get_json()
        self.assertEqual(data["service"], "Unified Tool API")
        self.assertIn("endpoints", data)
        self.assertIn("configuration", data)
        self.assertIn("api_spec_support", data)

        # Verify API spec documentation
        self.assertIn("openai", data["api_spec_support"])
        self.assertIn("anthropic", data["api_spec_support"])

    def test_list_tools_endpoint(self):
        """Test /tools endpoint lists available tools."""
        response = self.client.get("/tools")
        self.assertEqual(response.status_code, 200)

        data = response.get_json()
        self.assertIn("tools", data)
        self.assertIsInstance(data["tools"], list)
        self.assertGreater(len(data["tools"]), 0)

        # Verify tool structure
        tool = data["tools"][0]
        self.assertIn("name", tool)
        self.assertIn("description", tool)
        self.assertIn("parameters", tool)

    def test_list_tools_versioned_endpoints(self):
        """Test versioned /tools endpoints return same data."""
        for version in ["/v1/tools", "/v2/tools", "/v3/tools"]:
            response = self.client.get(version)
            self.assertEqual(response.status_code, 200, f"Failed for {version}")
            self.assertIn("tools", response.get_json())


class TestToolExecution(unittest.TestCase):
    """Tests for tool execution endpoint."""

    def setUp(self):
        """Set up test client."""
        with patch.dict("os.environ", {"API_MODE": "crush", "TOOL_API_SPEC": "openai"}):
            from unified_tool_api import app

            self.client = app.test_client()

    def test_execute_view_tool(self):
        """Test executing the view tool."""
        response = self.client.post(
            "/execute",
            json={"tool": "view", "parameters": {"filePath": "test.py"}},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

        data = response.get_json()
        self.assertTrue(data["success"])
        self.assertIn("content", data)

    def test_execute_write_tool(self):
        """Test executing the write tool."""
        response = self.client.post(
            "/execute",
            json={"tool": "write", "parameters": {"filePath": "test.txt", "content": "test content"}},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

        data = response.get_json()
        self.assertTrue(data["success"])
        self.assertIn("message", data)

    def test_execute_bash_tool(self):
        """Test executing the bash tool."""
        response = self.client.post(
            "/execute",
            json={"tool": "bash", "parameters": {"command": "echo test"}},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

        data = response.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["exitCode"], 0)

    def test_execute_unknown_tool(self):
        """Test executing an unknown tool returns error."""
        response = self.client.post(
            "/execute",
            json={"tool": "nonexistent_tool", "parameters": {}},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

        data = response.get_json()
        self.assertIn("error", data)
        self.assertIn("Unknown tool", data["error"])


class TestOpenAIChatCompletions(unittest.TestCase):
    """Tests for OpenAI-compatible /chat/completions endpoint."""

    def setUp(self):
        """Set up test client."""
        with patch.dict("os.environ", {"API_MODE": "crush", "TOOL_API_SPEC": "openai"}):
            from unified_tool_api import app

            self.client = app.test_client()

    def test_chat_completions_basic(self):
        """Test basic chat completion without tools."""
        response = self.client.post(
            "/chat/completions",
            json={"model": "test-model", "messages": [{"role": "user", "content": "Hello"}]},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

        data = response.get_json()
        self.assertEqual(data["object"], "chat.completion")
        self.assertIn("choices", data)
        self.assertEqual(len(data["choices"]), 1)
        self.assertEqual(data["choices"][0]["message"]["role"], "assistant")
        self.assertIn("usage", data)

    def test_chat_completions_with_tools(self):
        """Test chat completion with tools returns tool_calls."""
        response = self.client.post(
            "/chat/completions",
            json={
                "model": "test-model",
                "messages": [{"role": "user", "content": "Read file"}],
                "tools": [{"type": "function", "function": {"name": "view", "description": "View a file"}}],
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

        data = response.get_json()
        self.assertEqual(data["choices"][0]["finish_reason"], "tool_calls")
        self.assertIn("tool_calls", data["choices"][0]["message"])

        tool_call = data["choices"][0]["message"]["tool_calls"][0]
        self.assertEqual(tool_call["type"], "function")
        self.assertIn("id", tool_call)
        self.assertIn("function", tool_call)

    def test_chat_completions_versioned_endpoints(self):
        """Test versioned /chat/completions endpoints."""
        for version in ["/v1/chat/completions", "/v2/chat/completions", "/v3/chat/completions"]:
            response = self.client.post(
                version,
                json={"model": "test", "messages": [{"role": "user", "content": "Hi"}]},
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 200, f"Failed for {version}")


class TestAnthropicMessagesAPI(unittest.TestCase):
    """Tests for Anthropic-compatible /messages endpoint."""

    def setUp(self):
        """Set up test client."""
        with patch.dict("os.environ", {"API_MODE": "crush", "TOOL_API_SPEC": "anthropic"}):
            from unified_tool_api import app

            self.client = app.test_client()

    def test_messages_basic(self):
        """Test basic Anthropic messages endpoint without tools."""
        response = self.client.post(
            "/messages",
            json={"model": "test-model", "messages": [{"role": "user", "content": "Hello"}]},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

        data = response.get_json()
        self.assertEqual(data["type"], "message")
        self.assertEqual(data["role"], "assistant")
        self.assertIn("content", data)
        self.assertIsInstance(data["content"], list)
        self.assertEqual(data["stop_reason"], "end_turn")
        self.assertIn("usage", data)

    def test_messages_with_tools(self):
        """Test Anthropic messages with tools returns tool_use blocks."""
        response = self.client.post(
            "/messages",
            json={
                "model": "test-model",
                "messages": [{"role": "user", "content": "Read file"}],
                "tools": [{"name": "view", "description": "View a file", "input_schema": {"type": "object"}}],
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

        data = response.get_json()
        self.assertEqual(data["stop_reason"], "tool_use")

        # Check for tool_use block in content
        tool_use_blocks = [b for b in data["content"] if b.get("type") == "tool_use"]
        self.assertEqual(len(tool_use_blocks), 1)

        tool_use = tool_use_blocks[0]
        self.assertIn("id", tool_use)
        self.assertIn("name", tool_use)
        self.assertIn("input", tool_use)
        self.assertTrue(tool_use["id"].startswith("toolu_"))

    def test_messages_versioned_endpoint(self):
        """Test versioned /v1/messages endpoint."""
        response = self.client.post(
            "/v1/messages",
            json={"model": "test", "messages": [{"role": "user", "content": "Hi"}]},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["type"], "message")


class TestDualAPISpecDetection(unittest.TestCase):
    """Tests for dual API spec detection in /chat/completions."""

    def setUp(self):
        """Set up test client."""
        with patch.dict("os.environ", {"API_MODE": "crush", "TOOL_API_SPEC": "openai"}):
            from unified_tool_api import app

            self.client = app.test_client()

    def test_detect_anthropic_request_by_version(self):
        """Test detection of Anthropic format by anthropic_version field."""
        response = self.client.post(
            "/chat/completions",
            json={
                "anthropic_version": "bedrock-2023-05-31",
                "model": "claude-3",
                "messages": [{"role": "user", "content": "Hello"}],
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

        data = response.get_json()
        # Should return Anthropic format
        self.assertEqual(data["type"], "message")
        self.assertEqual(data["role"], "assistant")

    def test_detect_anthropic_request_by_system_string(self):
        """Test detection of Anthropic format by system as string field."""
        response = self.client.post(
            "/chat/completions",
            json={
                "system": "You are helpful",
                "model": "claude-3",
                "messages": [{"role": "user", "content": "Hello"}],
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

        data = response.get_json()
        # Should return Anthropic format
        self.assertEqual(data["type"], "message")

    def test_detect_anthropic_request_by_tool_result(self):
        """Test detection of Anthropic format by tool_result in content."""
        response = self.client.post(
            "/chat/completions",
            json={
                "model": "claude-3",
                "messages": [
                    {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "toolu_123", "content": "result"}]}
                ],
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

        data = response.get_json()
        # Should return Anthropic format
        self.assertEqual(data["type"], "message")

    def test_detect_openai_request_by_tool_role(self):
        """Test detection of OpenAI format by tool role messages."""
        response = self.client.post(
            "/chat/completions",
            json={
                "model": "gpt-4",
                "messages": [
                    {"role": "user", "content": "Hello"},
                    {"role": "tool", "tool_call_id": "call_123", "content": "result"},
                ],
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

        data = response.get_json()
        # Should return OpenAI format
        self.assertEqual(data["object"], "chat.completion")

    def test_detect_openai_request_by_tool_calls(self):
        """Test detection of OpenAI format by tool_calls in messages."""
        response = self.client.post(
            "/chat/completions",
            json={
                "model": "gpt-4",
                "messages": [
                    {"role": "user", "content": "Read file"},
                    {
                        "role": "assistant",
                        "tool_calls": [
                            {"id": "call_123", "type": "function", "function": {"name": "view", "arguments": "{}"}}
                        ],
                    },
                ],
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

        data = response.get_json()
        # Should return OpenAI format
        self.assertEqual(data["object"], "chat.completion")

    def test_default_to_openai_when_no_indicators(self):
        """Test that ambiguous requests default to OpenAI format."""
        response = self.client.post(
            "/chat/completions",
            json={"model": "test-model", "messages": [{"role": "user", "content": "Hello"}]},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

        data = response.get_json()
        # Should default to OpenAI format
        self.assertEqual(data["object"], "chat.completion")


class TestBedrockEndpoint(unittest.TestCase):
    """Tests for Bedrock-compatible endpoint with API spec support."""

    def setUp(self):
        """Set up test client for Gemini mode."""
        with patch.dict("os.environ", {"API_MODE": "gemini", "TOOL_API_SPEC": "openai"}):
            from unified_tool_api import app

            self.client = app.test_client()

    def test_bedrock_endpoint_basic_response(self):
        """Test Bedrock endpoint returns proper response."""
        response = self.client.post(
            "/api/v1/AI/GenAIExplorationLab/Models/test-model",
            json={"messages": [{"role": "user", "content": "Hello, how are you?"}]},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

        data = response.get_json()
        self.assertEqual(data["type"], "message")
        self.assertEqual(data["role"], "assistant")
        self.assertIn("content", data)

    def test_bedrock_endpoint_with_tools(self):
        """Test Bedrock endpoint handles requests with tools."""
        response = self.client.post(
            "/api/v1/AI/GenAIExplorationLab/Models/test-model",
            json={
                "messages": [{"role": "user", "content": "Please read the file test.py"}],
                "tools": [{"name": "read_file", "description": "Read a file"}],
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

        data = response.get_json()
        # Bedrock endpoint should return a valid message response
        self.assertEqual(data["type"], "message")
        self.assertEqual(data["role"], "assistant")
        # stop_reason depends on heuristics, but should be one of expected values
        self.assertIn(data["stop_reason"], ["tool_use", "end_turn"])

    def test_bedrock_endpoint_json_request(self):
        """Test Bedrock endpoint handles JSON generation requests."""
        response = self.client.post(
            "/api/v1/AI/GenAIExplorationLab/Models/test-model",
            json={"messages": [{"role": "user", "content": "Return a JSON response with the answer"}]},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

        data = response.get_json()
        self.assertEqual(data["stop_reason"], "end_turn")


class TestAPIModeCrushVsOpenCode(unittest.TestCase):
    """Tests for parameter naming differences between Crush and OpenCode modes."""

    def test_crush_mode_uses_camelcase_params(self):
        """Test Crush mode tools use camelCase parameters."""
        with patch.dict("os.environ", {"API_MODE": "crush", "TOOL_API_SPEC": "openai"}):
            # Re-import to get fresh module with new env
            import importlib

            import unified_tool_api

            importlib.reload(unified_tool_api)
            client = unified_tool_api.app.test_client()

            response = client.get("/tools")
            data = response.get_json()

            # Find the view tool
            view_tool = next((t for t in data["tools"] if t["name"] == "view"), None)
            self.assertIsNotNone(view_tool)

            # Should use camelCase
            param_names = [p["name"] for p in view_tool["parameters"]]
            self.assertIn("filePath", param_names)

    def test_opencode_mode_uses_snake_case_params(self):
        """Test OpenCode mode tools use snake_case parameters."""
        with patch.dict("os.environ", {"API_MODE": "opencode", "TOOL_API_SPEC": "openai"}):
            # Re-import to get fresh module with new env
            import importlib

            import unified_tool_api

            importlib.reload(unified_tool_api)
            client = unified_tool_api.app.test_client()

            response = client.get("/tools")
            data = response.get_json()

            # Find the view tool
            view_tool = next((t for t in data["tools"] if t["name"] == "view"), None)
            self.assertIsNotNone(view_tool)

            # Should use snake_case
            param_names = [p["name"] for p in view_tool["parameters"]]
            self.assertIn("file_path", param_names)


class TestToolCallIDGeneration(unittest.TestCase):
    """Tests for unique tool call ID generation."""

    def setUp(self):
        """Set up test client."""
        with patch.dict("os.environ", {"API_MODE": "crush", "TOOL_API_SPEC": "openai"}):
            from unified_tool_api import app

            self.client = app.test_client()

    def test_openai_tool_calls_have_call_prefix(self):
        """Test OpenAI format tool calls have call_ prefix."""
        response = self.client.post(
            "/chat/completions",
            json={
                "model": "test",
                "messages": [{"role": "user", "content": "Read file"}],
                "tools": [{"type": "function", "function": {"name": "view"}}],
            },
            content_type="application/json",
        )

        data = response.get_json()
        tool_call_id = data["choices"][0]["message"]["tool_calls"][0]["id"]
        self.assertTrue(tool_call_id.startswith("call_"))

    def test_anthropic_tool_use_has_toolu_prefix(self):
        """Test Anthropic format tool_use blocks have toolu_ prefix."""
        response = self.client.post(
            "/messages",
            json={
                "model": "test",
                "messages": [{"role": "user", "content": "Read file"}],
                "tools": [{"name": "view", "input_schema": {"type": "object"}}],
            },
            content_type="application/json",
        )

        data = response.get_json()
        tool_use_blocks = [b for b in data["content"] if b.get("type") == "tool_use"]
        tool_use_id = tool_use_blocks[0]["id"]
        self.assertTrue(tool_use_id.startswith("toolu_"))

    def test_tool_call_ids_are_unique(self):
        """Test that multiple requests generate unique tool call IDs."""
        ids = set()
        for _ in range(10):
            response = self.client.post(
                "/chat/completions",
                json={
                    "model": "test",
                    "messages": [{"role": "user", "content": "Read file"}],
                    "tools": [{"type": "function", "function": {"name": "view"}}],
                },
                content_type="application/json",
            )
            data = response.get_json()
            tool_call_id = data["choices"][0]["message"]["tool_calls"][0]["id"]
            ids.add(tool_call_id)

        # All IDs should be unique
        self.assertEqual(len(ids), 10)


class TestUsageMetrics(unittest.TestCase):
    """Tests for usage metrics in responses."""

    def setUp(self):
        """Set up test client."""
        with patch.dict("os.environ", {"API_MODE": "crush", "TOOL_API_SPEC": "openai"}):
            from unified_tool_api import app

            self.client = app.test_client()

    def test_openai_usage_format(self):
        """Test OpenAI response includes proper usage metrics."""
        response = self.client.post(
            "/chat/completions",
            json={"model": "test", "messages": [{"role": "user", "content": "Hello"}]},
            content_type="application/json",
        )

        data = response.get_json()
        self.assertIn("usage", data)
        self.assertIn("prompt_tokens", data["usage"])
        self.assertIn("completion_tokens", data["usage"])
        self.assertIn("total_tokens", data["usage"])

    def test_anthropic_usage_format(self):
        """Test Anthropic response includes proper usage metrics."""
        response = self.client.post(
            "/messages",
            json={"model": "test", "messages": [{"role": "user", "content": "Hello"}]},
            content_type="application/json",
        )

        data = response.get_json()
        self.assertIn("usage", data)
        self.assertIn("input_tokens", data["usage"])
        self.assertIn("output_tokens", data["usage"])


if __name__ == "__main__":
    unittest.main()
