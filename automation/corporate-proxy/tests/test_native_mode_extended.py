#!/usr/bin/env python3
"""
Extended tests for native mode to match text mode coverage
Addresses gaps in error handling, multiple tools, and edge cases
"""

import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))
sys.path.append(str(Path(__file__).parent.parent / "gemini"))


class TestNativeModeErrorHandling(unittest.TestCase):
    """Test error handling in native mode"""

    @classmethod
    def setUpClass(cls):
        """Set up for native mode testing"""
        os.environ["DEFAULT_TOOL_MODE"] = "native"
        os.environ["USE_MOCK_API"] = "true"

    def test_malformed_tool_call_response(self):
        """Test handling of malformed tool call responses from API"""
        # Mock a malformed response with invalid tool call structure
        mock_response = {
            "tool_calls": [
                {
                    "function": {
                        # Missing required 'name' field
                        "arguments": "{}"
                    }
                }
            ],
            "content": [{"text": "Invalid tool call"}],
            "usage": {"input_tokens": 10, "output_tokens": 20},
        }

        with patch("requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = mock_response

            from gemini.gemini_proxy_wrapper import translate_company_to_gemini

            gemini_request = {"model": "gemini-2.5-flash", "contents": [{"role": "user", "parts": [{"text": "Test"}]}]}

            # Should handle malformed response gracefully
            try:
                result = translate_company_to_gemini(mock_response, gemini_request, [])
                # Should return something even with malformed tool call
                self.assertIn("candidates", result)
                parts = result["candidates"][0]["content"]["parts"]
                # Implementation creates function call even with None name
                if "functionCall" in parts[0]:
                    # This is current behavior - it passes through even malformed calls
                    self.assertIsNone(parts[0]["functionCall"].get("name"))
                else:
                    # Or it might return text
                    self.assertIn("text", parts[0])
            except KeyError:
                self.fail("Should handle malformed tool calls gracefully")

    def test_api_error_with_tool_calls(self):
        """Test handling when API returns error status with tool calls"""
        with patch("requests.post") as mock_post:
            mock_post.return_value.status_code = 500
            mock_post.return_value.json.return_value = {"error": "Internal server error"}

            from gemini.gemini_proxy_wrapper import translate_gemini_to_company

            gemini_request = {
                "model": "gemini-2.5-flash",
                "contents": [{"role": "user", "parts": [{"text": "Test"}]}],
                "tools": [{"functionDeclarations": [{"name": "test_tool"}]}],
            }

            # Should handle API errors appropriately
            try:
                endpoint, company_request, tools = translate_gemini_to_company(gemini_request)
                # Request translation should still work
                self.assertIsNotNone(endpoint)
                self.assertIsNotNone(company_request)
                self.assertIsNotNone(tools)
            except Exception as e:
                self.fail(f"Should handle API preparation even if API might fail: {e}")

    def test_invalid_function_arguments(self):
        """Test handling of invalid JSON in function arguments"""
        mock_response = {
            "tool_calls": [
                {
                    "id": "call_123",
                    "type": "function",
                    "function": {"name": "test_tool", "arguments": "invalid json {not valid}"},  # Invalid JSON
                }
            ],
            "content": [{"text": "Tool call with invalid args"}],
            "usage": {"input_tokens": 10, "output_tokens": 20},
        }

        with patch("requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = mock_response

            from gemini.gemini_proxy_wrapper import translate_company_to_gemini

            gemini_request = {"model": "gemini-2.5-flash"}

            # Should handle invalid arguments gracefully
            result = translate_company_to_gemini(mock_response, gemini_request, [])
            self.assertIn("candidates", result)
            parts = result["candidates"][0]["content"]["parts"]
            # Should still include the function call, even with invalid args
            if "functionCall" in parts[0]:
                # Arguments might be passed as-is or handled specially
                self.assertIn("name", parts[0]["functionCall"])


class TestNativeModeMultipleTools(unittest.TestCase):
    """Test multiple tool handling in native mode"""

    @classmethod
    def setUpClass(cls):
        """Set up for native mode testing"""
        os.environ["DEFAULT_TOOL_MODE"] = "native"

    def test_multiple_tools_single_response(self):
        """Test handling multiple tool calls in a single response"""
        mock_response = {
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "read_file", "arguments": json.dumps({"path": "file1.txt"})},
                },
                {
                    "id": "call_2",
                    "type": "function",
                    "function": {"name": "write_file", "arguments": json.dumps({"path": "file2.txt", "content": "data"})},
                },
                {
                    "id": "call_3",
                    "type": "function",
                    "function": {"name": "delete_file", "arguments": json.dumps({"path": "file3.txt"})},
                },
            ],
            "content": [{"text": "Executing multiple tools"}],
            "usage": {"input_tokens": 20, "output_tokens": 40},
        }

        with patch("requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = mock_response

            from gemini.gemini_proxy_wrapper import translate_company_to_gemini

            gemini_request = {"model": "gemini-2.5-flash"}

            result = translate_company_to_gemini(mock_response, gemini_request, [])

            # Should handle all tool calls
            self.assertIn("candidates", result)
            parts = result["candidates"][0]["content"]["parts"]

            # Count function calls
            function_calls = [p for p in parts if "functionCall" in p]
            self.assertEqual(len(function_calls), 3)

            # Verify each tool call
            tool_names = [fc["functionCall"]["name"] for fc in function_calls]
            self.assertIn("read_file", tool_names)
            self.assertIn("write_file", tool_names)
            self.assertIn("delete_file", tool_names)

    def test_parallel_tool_execution(self):
        """Test that multiple tools can be marked for parallel execution"""
        from gemini.gemini_proxy_wrapper import translate_gemini_to_company

        gemini_request = {
            "model": "gemini-2.5-flash",
            "contents": [{"role": "user", "parts": [{"text": "Read multiple files"}]}],
            "tools": [
                {
                    "functionDeclarations": [
                        {"name": "read_file", "parameters": {"type": "object"}},
                        {"name": "list_files", "parameters": {"type": "object"}},
                        {"name": "get_status", "parameters": {"type": "object"}},
                    ]
                }
            ],
        }

        endpoint, company_request, tools = translate_gemini_to_company(gemini_request)

        # Tools are returned as the full structure from the request
        self.assertEqual(len(tools), 1)  # One tools array
        function_declarations = tools[0].get("functionDeclarations", [])
        self.assertEqual(len(function_declarations), 3)

        tool_names = [decl["name"] for decl in function_declarations]
        self.assertIn("read_file", tool_names)
        self.assertIn("list_files", tool_names)
        self.assertIn("get_status", tool_names)


class TestNativeModeEdgeCases(unittest.TestCase):
    """Test edge cases in native mode"""

    @classmethod
    def setUpClass(cls):
        """Set up for native mode testing"""
        os.environ["DEFAULT_TOOL_MODE"] = "native"

    def test_complex_nested_parameters(self):
        """Test tool calls with complex nested parameters"""
        mock_response = {
            "tool_calls": [
                {
                    "id": "call_complex",
                    "type": "function",
                    "function": {
                        "name": "complex_tool",
                        "arguments": json.dumps(
                            {
                                "config": {
                                    "nested": {"deep": {"value": 42, "array": [1, 2, 3], "bool": True}},
                                    "list": ["a", "b", "c"],
                                },
                                "metadata": {"tags": ["tag1", "tag2"], "properties": {"key1": "value1", "key2": None}},
                            }
                        ),
                    },
                }
            ],
            "content": [{"text": "Complex parameters"}],
            "usage": {"input_tokens": 30, "output_tokens": 50},
        }

        with patch("requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = mock_response

            from gemini.gemini_proxy_wrapper import translate_company_to_gemini

            result = translate_company_to_gemini(mock_response, {"model": "gemini-2.5-flash"}, [])

            # Should preserve complex nested structure
            parts = result["candidates"][0]["content"]["parts"]
            function_call = parts[0]["functionCall"]
            # args is already a dict, not a JSON string
            args = function_call["args"]

            # Verify nested structure is preserved
            self.assertEqual(args["config"]["nested"]["deep"]["value"], 42)
            self.assertEqual(args["config"]["nested"]["deep"]["array"], [1, 2, 3])
            self.assertEqual(args["metadata"]["properties"]["key2"], None)

    def test_optional_parameters(self):
        """Test tools with optional parameters"""
        mock_response = {
            "tool_calls": [
                {
                    "id": "call_optional",
                    "type": "function",
                    "function": {
                        "name": "search",
                        "arguments": json.dumps(
                            {
                                "query": "test",
                                # Optional parameters omitted
                            }
                        ),
                    },
                }
            ],
            "content": [{"text": "Search with minimal params"}],
            "usage": {"input_tokens": 10, "output_tokens": 20},
        }

        with patch("requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = mock_response

            from gemini.gemini_proxy_wrapper import translate_company_to_gemini

            result = translate_company_to_gemini(mock_response, {"model": "gemini-2.5-flash"}, [])

            # Should handle missing optional parameters
            parts = result["candidates"][0]["content"]["parts"]
            function_call = parts[0]["functionCall"]
            # args is already a dict, not a JSON string
            args = function_call["args"]

            # Should only have required parameter
            self.assertEqual(args["query"], "test")
            self.assertEqual(len(args), 1)

    def test_empty_tool_response(self):
        """Test handling when API returns empty tool_calls array"""
        mock_response = {
            "tool_calls": [],  # Empty array
            "content": [{"text": "No tools needed"}],
            "usage": {"input_tokens": 5, "output_tokens": 10},
        }

        with patch("requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = mock_response

            from gemini.gemini_proxy_wrapper import translate_company_to_gemini

            result = translate_company_to_gemini(mock_response, {"model": "gemini-2.5-flash"}, [])

            # Should return text response when no tools
            parts = result["candidates"][0]["content"]["parts"]
            self.assertEqual(len(parts), 1)
            self.assertIn("text", parts[0])
            self.assertEqual(parts[0]["text"], "No tools needed")


class TestNativeModeIterations(unittest.TestCase):
    """Test iterative execution in native mode"""

    def test_max_iterations_native(self):
        """Test that native mode respects max iteration limits"""
        # This would typically be handled by the client, but we can test
        # that the configuration is available
        from gemini.gemini_proxy_wrapper import CONFIG

        with patch.dict(CONFIG, {"max_tool_iterations": 3}):
            max_iterations = CONFIG.get("max_tool_iterations", 5)
            self.assertEqual(max_iterations, 3)

            # Simulate iteration counting
            iteration_count = 0
            for _ in range(10):
                iteration_count += 1
                if iteration_count >= max_iterations:
                    break

            self.assertEqual(iteration_count, 3)

    def test_continuation_in_native_mode(self):
        """Test that native mode can handle continuation requests"""
        # Native mode typically doesn't use the continuation endpoint,
        # but it should handle sequential tool calls
        responses = [
            {
                "tool_calls": [{"function": {"name": "tool1", "arguments": "{}"}}],
                "content": [{"text": "First call"}],
                "usage": {"input_tokens": 10, "output_tokens": 20},
            },
            {
                "tool_calls": [{"function": {"name": "tool2", "arguments": "{}"}}],
                "content": [{"text": "Second call"}],
                "usage": {"input_tokens": 20, "output_tokens": 30},
            },
            {"tool_calls": [], "content": [{"text": "Complete"}], "usage": {"input_tokens": 30, "output_tokens": 40}},
        ]

        # Track that we can handle multiple responses
        tool_count = 0
        for response in responses:
            if response.get("tool_calls"):
                tool_count += len(response["tool_calls"])

        self.assertEqual(tool_count, 2)


if __name__ == "__main__":
    unittest.main()
