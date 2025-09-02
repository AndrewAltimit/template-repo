#!/usr/bin/env python3
"""
Test streaming responses with tool calls in corporate proxy.
Ensures tool calls have proper index fields for OpenCode compatibility.
"""

import json
import sys
import unittest
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))
from shared.services.text_tool_parser import TextToolParser  # noqa: E402

# Import the production function from test utilities
from test_utils import format_tool_calls_for_openai  # noqa: E402


class TestStreamingToolCalls(unittest.TestCase):
    """Test streaming response format with tool calls"""

    def setUp(self):
        """Set up test fixtures"""
        self.parser = TextToolParser()

        # Sample response with multiple tool calls
        self.company_response = {
            "id": "msg_bdrk_016S1ZMrPxNg3Wptro9aeyQZ",
            "type": "message",
            "role": "assistant",
            "model": "claude-3-5-sonnet-20240620",
            "content": [
                {
                    "type": "text",
                    "text": (
                        "I'll help you with these tasks:\n\n"
                        '```python\nWrite("hello.md", "hello")\n```\n\n'
                        '```python\ncontent = Read("hello.md")\n```\n\n'
                        '```python\nBash("/automation/ci-cd/run-ci.sh full")\n```'
                    ),
                }
            ],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 100, "output_tokens": 50},
        }

    def test_streaming_tool_calls_have_index(self):
        """Test that streaming tool calls include index field"""
        content = self.company_response["content"][0]["text"]

        # Parse tool calls
        tool_calls = self.parser.parse_tool_calls(content)

        # Should find 3 tool calls
        self.assertEqual(len(tool_calls), 3)

        # Format for streaming
        streaming_calls = format_tool_calls_for_openai(tool_calls, streaming=True)

        # Verify each has index field
        for i, call in enumerate(streaming_calls):
            self.assertIn("index", call, f"Tool call {i} missing index field")
            self.assertEqual(call["index"], i, f"Tool call {i} has wrong index")
            self.assertIn("id", call)
            self.assertIn("type", call)
            self.assertIn("function", call)

    def test_non_streaming_tool_calls_no_index(self):
        """Test that non-streaming tool calls don't have index field"""
        content = self.company_response["content"][0]["text"]

        # Parse tool calls
        tool_calls = self.parser.parse_tool_calls(content)

        # Format for non-streaming
        non_streaming_calls = format_tool_calls_for_openai(tool_calls, streaming=False)

        # Verify no index field
        for call in non_streaming_calls:
            self.assertNotIn("index", call, "Non-streaming call should not have index")
            self.assertIn("id", call)
            self.assertIn("type", call)
            self.assertIn("function", call)

    def test_streaming_response_structure(self):
        """Test the structure of streaming response chunks"""
        content = self.company_response["content"][0]["text"]

        # Parse and format tool calls for streaming
        tool_calls = self.parser.parse_tool_calls(content)
        streaming_calls = format_tool_calls_for_openai(tool_calls, streaming=True)

        # Simulate streaming chunks
        chunks = []

        # Initial chunk with role
        initial_chunk = {
            "id": "chatcmpl-123",
            "object": "chat.completion.chunk",
            "created": 1234567890,
            "model": "openrouter/anthropic/claude-3.5-sonnet",
            "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}],
        }
        chunks.append(initial_chunk)

        # Tool call chunks - one per tool call
        for tool_call in streaming_calls:
            chunk = {
                "id": "chatcmpl-123",
                "object": "chat.completion.chunk",
                "created": 1234567890,
                "model": "openrouter/anthropic/claude-3.5-sonnet",
                "choices": [{"index": 0, "delta": {"tool_calls": [tool_call]}, "finish_reason": None}],
            }
            chunks.append(chunk)

        # Final chunk
        final_chunk = {
            "id": "chatcmpl-123",
            "object": "chat.completion.chunk",
            "created": 1234567890,
            "model": "openrouter/anthropic/claude-3.5-sonnet",
            "choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}],
        }
        chunks.append(final_chunk)

        # Verify chunk structure
        self.assertEqual(len(chunks), 5)  # initial + 3 tool calls + final

        # Verify each tool call chunk has proper structure
        for i in range(1, 4):  # Tool call chunks
            chunk = chunks[i]
            self.assertEqual(chunk["object"], "chat.completion.chunk")
            delta = chunk["choices"][0]["delta"]
            self.assertIn("tool_calls", delta)
            self.assertEqual(len(delta["tool_calls"]), 1)
            tool_call = delta["tool_calls"][0]
            self.assertIn("index", tool_call)
            self.assertIn("id", tool_call)
            self.assertIn("type", tool_call)
            self.assertIn("function", tool_call)

    def test_tool_call_arguments_format(self):
        """Test that tool call arguments are properly JSON-encoded"""
        content = self.company_response["content"][0]["text"]

        tool_calls = self.parser.parse_tool_calls(content)
        streaming_calls = format_tool_calls_for_openai(tool_calls, streaming=True)

        # Check each tool call
        # Note: The production function applies parameter mappings (snake_case to camelCase)
        expected_tools = [
            ("write", {"filePath": "hello.md", "content": "hello"}),  # file_path -> filePath
            ("read", {"filePath": "hello.md"}),  # file_path -> filePath
            ("bash", {"command": "/automation/ci-cd/run-ci.sh full", "description": "Execute bash command"}),  # Added default
        ]

        for i, (expected_name, expected_params) in enumerate(expected_tools):
            call = streaming_calls[i]
            self.assertEqual(call["function"]["name"], expected_name)

            # Arguments should be JSON string
            args_str = call["function"]["arguments"]
            self.assertIsInstance(args_str, str)

            # Parse and verify arguments
            args = json.loads(args_str)
            self.assertEqual(args, expected_params)

    def test_edge_case_empty_tool_calls(self):
        """Test handling when no tool calls are found"""
        content = "Just a regular response without any tool calls."

        tool_calls = self.parser.parse_tool_calls(content)
        self.assertEqual(len(tool_calls), 0)

        # Format empty list
        streaming_calls = format_tool_calls_for_openai(tool_calls, streaming=True)
        self.assertEqual(len(streaming_calls), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
