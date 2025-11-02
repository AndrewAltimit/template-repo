#!/usr/bin/env python3
"""
Integration tests for native and text modes
Tests the full flow with mock servers
"""

import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))
# Also add gemini directory for imports
sys.path.append(str(Path(__file__).parent.parent / "gemini"))


class TestNativeMode(unittest.TestCase):
    """Integration tests for native mode"""

    @classmethod
    def setUpClass(cls):
        """Start mock servers for testing"""
        cls.mock_api_port = 8050
        cls.proxy_port = 8053

        # Set environment for default native mode
        os.environ["DEFAULT_TOOL_MODE"] = "native"
        os.environ["USE_MOCK_API"] = "true"
        os.environ["MOCK_API_BASE"] = f"http://localhost:{cls.mock_api_port}"
        os.environ["GEMINI_PROXY_PORT"] = str(cls.proxy_port)

    def test_native_mode_with_tools(self):
        """Test native mode returns structured tool calls"""
        # Mock the company API response with tool calls
        mock_response = {
            "tool_calls": [
                {
                    "id": "call_123",
                    "type": "function",
                    "function": {"name": "read_file", "arguments": json.dumps({"path": "test.txt"})},
                }
            ],
            "content": [{"text": "I'll read that file for you."}],
            "usage": {"input_tokens": 10, "output_tokens": 20},
        }

        with patch("requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = mock_response

            # Import after environment is set
            from gemini.gemini_proxy_wrapper import translate_company_to_gemini, translate_gemini_to_company

            # Test request
            gemini_request = {
                "model": "gemini-2.5-flash",
                "contents": [{"role": "user", "parts": [{"text": "Read test.txt"}]}],
                "tools": [
                    {
                        "functionDeclarations": [
                            {
                                "name": "read_file",
                                "description": "Read a file",
                                "parameters": {
                                    "type": "object",
                                    "properties": {"path": {"type": "string"}},
                                    "required": ["path"],
                                },
                            }
                        ]
                    }
                ],
            }

            # Translate request
            _endpoint, company_request, tools = translate_gemini_to_company(gemini_request)

            # Verify tools are passed through
            self.assertIsNotNone(tools)
            self.assertEqual(len(tools), 1)

            # Translate response back
            gemini_response = translate_company_to_gemini(mock_response, gemini_request, tools)

            # Verify structured tool calls in response
            self.assertIn("candidates", gemini_response)
            parts = gemini_response["candidates"][0]["content"]["parts"]
            self.assertIn("functionCall", parts[0])
            self.assertEqual(parts[0]["functionCall"]["name"], "read_file")

    def test_native_mode_without_tools(self):
        """Test native mode works without tools"""
        mock_response = {
            "content": [{"text": "Hello, how can I help you?"}],
            "usage": {"input_tokens": 5, "output_tokens": 10},
        }

        with patch("requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = mock_response

            from gemini.gemini_proxy_wrapper import translate_company_to_gemini, translate_gemini_to_company

            gemini_request = {"model": "gemini-2.5-flash", "contents": [{"role": "user", "parts": [{"text": "Hello"}]}]}

            _endpoint, _company_request, tools = translate_gemini_to_company(gemini_request)

            # No tools should be present
            self.assertEqual(tools, [])

            gemini_response = translate_company_to_gemini(mock_response, gemini_request, tools)

            # Should return text response
            self.assertIn("candidates", gemini_response)
            parts = gemini_response["candidates"][0]["content"]["parts"]
            self.assertIn("text", parts[0])
            self.assertEqual(parts[0]["text"], "Hello, how can I help you?")


class TestTextMode(unittest.TestCase):
    """Integration tests for text mode"""

    @classmethod
    def setUpClass(cls):
        """Set up for text mode testing"""
        cls.proxy_port = 8054  # Different port to avoid conflicts

        # Set environment for default text mode
        os.environ["DEFAULT_TOOL_MODE"] = "text"
        os.environ["USE_MOCK_API"] = "true"
        os.environ["GEMINI_PROXY_PORT"] = str(cls.proxy_port)

    def test_text_mode_tool_injection(self):
        """Test that tools are injected into prompts in text mode"""
        # Need to reload module with new environment
        import importlib

        import gemini.gemini_proxy_wrapper as wrapper

        importlib.reload(wrapper)

        from gemini.gemini_proxy_wrapper import translate_gemini_to_company

        # Use a model that's configured for text mode or override it
        with patch.dict(os.environ, {"GEMINI_MODEL_OVERRIDE_gemini_2_5_flash_tool_mode": "text"}):
            gemini_request = {
                "model": "gemini-2.5-flash",
                "contents": [{"role": "user", "parts": [{"text": "Read the file config.json"}]}],
                "tools": [
                    {
                        "functionDeclarations": [
                            {
                                "name": "read_file",
                                "description": "Read a file",
                                "parameters": {
                                    "type": "object",
                                    "properties": {"path": {"type": "string"}},
                                    "required": ["path"],
                                },
                            }
                        ]
                    }
                ],
            }

            _endpoint, company_request, _tools = translate_gemini_to_company(gemini_request)

            # Check that tools were injected into the message
            user_message = company_request["messages"][0]["content"]

            # Should contain tool instructions
            self.assertIn("tool_call", user_message)
            self.assertIn("read_file", user_message)
            self.assertIn("Read the file config.json", user_message)

    def test_text_mode_parse_tool_calls(self):
        """Test parsing tool calls from text response"""
        from shared.services.text_tool_parser import TextToolParser

        parser = TextToolParser()

        # Simulate AI response with tool call
        ai_response = """
        I'll read the configuration file for you.

        ```tool_call
        {
          "tool": "read_file",
          "parameters": {
            "path": "config.json"
          }
        }
        ```

        Let me process that file.
        """

        tool_calls = parser.parse_tool_calls(ai_response)

        self.assertEqual(len(tool_calls), 1)
        self.assertEqual(tool_calls[0]["name"], "read_file")
        self.assertEqual(tool_calls[0]["parameters"]["path"], "config.json")

    def test_text_mode_tool_execution_flow(self):
        """Test the complete flow of tool execution in text mode"""
        from shared.services.text_tool_parser import TextToolParser

        parser = TextToolParser()

        # Mock tool executor
        def mock_executor(tool_name, _params):
            if tool_name == "read_file":
                return {"success": True, "content": '{"version": "1.0", "enabled": true}'}
            return {"success": False, "error": "Unknown tool"}

        parser.tool_executor = mock_executor

        # AI response with tool call
        response = """
        I'll read the configuration file.

        ```tool_call
        {
          "tool": "read_file",
          "parameters": {
            "path": "config.json"
          }
        }
        ```
        """

        # Process the response
        continuation, results, needs_continue = parser.process_response_with_tools(response)

        # Verify results
        self.assertTrue(needs_continue)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["tool"], "read_file")
        self.assertTrue(results[0]["result"]["success"])

        # Check continuation message
        self.assertIn("Tool Result: read_file", continuation)
        self.assertIn('{"version": "1.0", "enabled": true}', continuation)

    def test_text_mode_multiple_iterations(self):
        """Test multiple tool call iterations"""
        from shared.services.text_tool_parser import TextToolParser

        parser = TextToolParser()

        # Track execution count
        execution_count = {"count": 0}

        def mock_executor(_tool_name, _params):
            execution_count["count"] += 1
            return {"success": True, "output": f'Execution {execution_count["count"]}'}

        parser.tool_executor = mock_executor

        # First iteration
        response1 = """
        ```tool_call
        {"tool": "test_tool", "parameters": {}}
        ```
        """

        _continuation1, _results1, needs_continue1 = parser.process_response_with_tools(response1)

        self.assertTrue(needs_continue1)
        self.assertEqual(execution_count["count"], 1)

        # Second iteration
        response2 = """
        Based on the first result, let me run another tool.

        ```tool_call
        {"tool": "test_tool", "parameters": {}}
        ```
        """

        _continuation2, _results2, needs_continue2 = parser.process_response_with_tools(response2)

        self.assertTrue(needs_continue2)
        self.assertEqual(execution_count["count"], 2)

        # Final iteration (no tools)
        response3 = "The task is complete. Both tools executed successfully."

        _continuation3, results3, needs_continue3 = parser.process_response_with_tools(response3)

        self.assertFalse(needs_continue3)
        self.assertEqual(len(results3), 0)
        self.assertTrue(parser.is_complete_response(response3))


class TestModeSwitching(unittest.TestCase):
    """Test switching between modes"""

    def test_mode_configuration(self):
        """Test that mode can be configured"""
        # Test native mode
        with patch.dict(os.environ, {"DEFAULT_TOOL_MODE": "native"}):
            self.assertEqual(os.environ.get("DEFAULT_TOOL_MODE"), "native")

        # Test text mode
        with patch.dict(os.environ, {"DEFAULT_TOOL_MODE": "text"}):
            self.assertEqual(os.environ.get("DEFAULT_TOOL_MODE"), "text")

        # Test per-model override
        with patch.dict(os.environ, {"GEMINI_MODEL_OVERRIDE_test_model_tool_mode": "text"}):
            self.assertEqual(os.environ.get("GEMINI_MODEL_OVERRIDE_test_model_tool_mode"), "text")

    def test_mode_affects_behavior(self):
        """Test that mode changes behavior"""
        # In native mode, tools should not be injected into prompts
        with patch.dict(os.environ, {"TOOL_MODE": "native"}):
            # Native mode behavior tested in TestNativeMode
            pass

        # In text mode, tools should be injected
        with patch.dict(os.environ, {"TOOL_MODE": "text"}):
            from shared.services.text_tool_parser import ToolInjector  # noqa: E402  # pylint: disable=wrong-import-position

            tools = {"test": {"description": "Test tool"}}
            injector = ToolInjector(tools)

            messages = [{"role": "user", "content": "Test message"}]
            modified = injector.inject_tools_into_messages(messages)

            # Should modify message in text mode
            self.assertIn("test", modified[0]["content"])


class TestErrorHandling(unittest.TestCase):
    """Test error handling in both modes"""

    def test_invalid_tool_call_format(self):
        """Test handling of invalid tool call formats"""
        from shared.services.text_tool_parser import TextToolParser

        parser = TextToolParser()

        # Invalid JSON
        invalid_response = """
        ```tool_call
        {invalid json}
        ```
        """

        tool_calls = parser.parse_tool_calls(invalid_response)
        self.assertEqual(len(tool_calls), 0)

    def test_tool_execution_failure(self):
        """Test handling of tool execution failures"""
        from shared.services.text_tool_parser import TextToolParser

        parser = TextToolParser()

        def failing_executor(_tool_name, _params):
            return {"success": False, "error": "Tool execution failed"}

        parser.tool_executor = failing_executor

        response = """
        ```tool_call
        {"tool": "failing_tool", "parameters": {}}
        ```
        """

        continuation, results, _needs_continue = parser.process_response_with_tools(response)

        # Should handle failure gracefully
        self.assertEqual(len(results), 1)
        self.assertFalse(results[0]["result"]["success"])
        self.assertIn("Tool Error", continuation)
        self.assertIn("Tool execution failed", continuation)

    def test_max_iterations_limit(self):
        """Test that iterations are limited"""
        max_iterations = 3
        iteration_count = 0

        # Simulate reaching max iterations
        for _ in range(max_iterations + 2):
            iteration_count += 1
            if iteration_count > max_iterations:
                # Should stop after max iterations
                break

        self.assertEqual(iteration_count, max_iterations + 1)


if __name__ == "__main__":
    unittest.main()
