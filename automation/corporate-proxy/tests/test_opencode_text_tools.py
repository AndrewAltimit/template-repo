#!/usr/bin/env python3
"""
Integration test for OpenCode text-based tool execution with corporate proxy.
This tests the critical configuration where:
- OpenCode has tool_call: true (to execute tools)
- Translation wrapper has supports_tools: false (to parse from text)
"""

import json
from pathlib import Path
import sys
import unittest

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))
# pylint: disable=wrong-import-position
# Import the production function from test utilities
from proxy_test_helpers import format_tool_calls_for_openai  # noqa: E402
from shared.services.text_tool_parser import TextToolParser  # noqa: E402


class TestOpenCodeTextTools(unittest.TestCase):
    """Test OpenCode text-based tool execution through corporate proxy"""

    def setUp(self):
        """Set up test fixtures"""
        self.parser = TextToolParser()

        # Company API responses with embedded Python-style tool calls
        self.company_responses = [
            {
                "id": "msg_1",
                "type": "message",
                "role": "assistant",
                "model": "claude-3-5-sonnet-20240620",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "I'll run the 'ls' command:\n\n```python\n"
                            'files = Bash("ls")\n'
                            'print("Current files in the directory:")\n'
                            "print(files)\n```"
                        ),
                    }
                ],
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 100, "output_tokens": 50},
            },
            {
                "id": "msg_2",
                "type": "message",
                "role": "assistant",
                "model": "claude-3-5-sonnet-20240620",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            'I\'ll create a file named "hello.md" with the content '
                            '"hello" using the Write tool:\n\n```python\n'
                            'Write("hello.md", "hello")\n```\n\n'
                            "Now, let's verify:\n\n```python\n"
                            'content = Read("hello.md")\n'
                            'print(f"Contents: {content}")\n```'
                        ),
                    }
                ],
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 150, "output_tokens": 75},
            },
            {
                "id": "msg_3",
                "type": "message",
                "role": "assistant",
                "model": "claude-3-5-sonnet-20240620",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            'First, let\'s read "miku.md":\n\n```python\n'
                            'content = Read("miku.md")\n'
                            'print(f"Contents of miku.md: {content}")\n```\n\n'
                            "Now list files:\n\n```python\n"
                            'files = Bash("ls")\n'
                            'print("Files in directory:")\n'
                            "print(files)\n```"
                        ),
                    }
                ],
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 200, "output_tokens": 100},
            },
        ]

        # Model configuration with the critical settings
        self.model_config = {
            "openrouter/anthropic/claude-3.5-sonnet": {
                "id": "company/claude-3.5-sonnet",
                "endpoint": "ai-coe-bedrock-claude35-sonnet-200k:analyze=null",
                "supports_tools": False,  # Critical: Forces text parsing
            }
        }

        self.opencode_model_config = {
            "openrouter/anthropic/claude-3.5-sonnet": {
                "id": "openrouter/anthropic/claude-3.5-sonnet",
                "tool_call": True,  # Critical: Enables tool execution in OpenCode
            }
        }

    def test_parse_bash_command(self):
        """Test parsing a simple Bash command"""
        response = self.company_responses[0]
        content = response["content"][0]["text"]

        tool_calls = self.parser.parse_tool_calls(content)

        self.assertEqual(len(tool_calls), 1)
        self.assertEqual(tool_calls[0]["name"], "bash")
        self.assertEqual(tool_calls[0]["parameters"]["command"], "ls")

    def test_parse_multiple_tools(self):
        """Test parsing multiple tool calls (Write and Read)"""
        response = self.company_responses[1]
        content = response["content"][0]["text"]

        tool_calls = self.parser.parse_tool_calls(content)

        self.assertEqual(len(tool_calls), 2)
        self.assertEqual(tool_calls[0]["name"], "write")
        self.assertEqual(tool_calls[0]["parameters"]["file_path"], "hello.md")
        self.assertEqual(tool_calls[0]["parameters"]["content"], "hello")

        self.assertEqual(tool_calls[1]["name"], "read")
        self.assertEqual(tool_calls[1]["parameters"]["file_path"], "hello.md")

    def test_format_for_openai(self):
        """Test formatting parsed tools for OpenAI/OpenCode"""
        response = self.company_responses[1]
        content = response["content"][0]["text"]

        tool_calls = self.parser.parse_tool_calls(content)
        formatted = format_tool_calls_for_openai(tool_calls)

        self.assertEqual(len(formatted), 2)

        # Check first tool call format
        first_call = formatted[0]
        self.assertEqual(first_call["type"], "function")
        self.assertEqual(first_call["function"]["name"], "write")

        # Parse arguments JSON
        # Note: The production function applies parameter mappings (file_path -> filePath)
        args = json.loads(first_call["function"]["arguments"])
        self.assertEqual(args["filePath"], "hello.md")  # Mapped from file_path
        self.assertEqual(args["content"], "hello")

    def test_strip_tool_calls(self):
        """Test that tool calls are properly stripped from content"""
        response = self.company_responses[1]
        content = response["content"][0]["text"]

        stripped = self.parser.strip_tool_calls(content)

        # Should remove Python code blocks but keep explanatory text
        self.assertIn("create a file", stripped)
        self.assertNotIn("Write(", stripped)
        self.assertNotIn("Read(", stripped)
        self.assertNotIn("```python", stripped)

    def test_complete_flow_with_config(self):
        """Test the complete flow with proper configuration"""
        # Simulate what happens in translation_wrapper.py

        for i, company_response in enumerate(self.company_responses):
            with self.subTest(response_index=i):
                # 1. Get model config
                model = "openrouter/anthropic/claude-3.5-sonnet"
                model_config = self.model_config[model]
                supports_tools = model_config["supports_tools"]

                # 2. Check if text parsing is needed
                self.assertFalse(supports_tools, "Model should have supports_tools: false")

                # 3. Extract content
                content = company_response["content"][0]["text"]

                # 4. Parse tool calls from text
                parsed_tool_calls = self.parser.parse_tool_calls(content)
                self.assertGreater(len(parsed_tool_calls), 0, "Should find tool calls")

                # 5. Format for OpenAI
                tool_calls = format_tool_calls_for_openai(parsed_tool_calls)

                # 6. Strip tool calls from content
                stripped_content = self.parser.strip_tool_calls(content)

                # 7. Create OpenAI response
                openai_response = {
                    "id": "chatcmpl-123",
                    "object": "chat.completion",
                    "model": model,
                    "choices": [
                        {
                            "index": 0,
                            "message": {
                                "role": "assistant",
                                "content": stripped_content if stripped_content else None,
                                "tool_calls": tool_calls if tool_calls else None,
                            },
                            "finish_reason": "tool_calls" if tool_calls else "stop",
                        }
                    ],
                    "usage": company_response.get("usage", {}),
                }

                # 8. Verify OpenCode receives tool_calls
                message = openai_response["choices"][0]["message"]
                self.assertIsNotNone(message.get("tool_calls"), "Should have tool_calls")
                self.assertGreater(len(message["tool_calls"]), 0, "Should have at least one tool call")

                # 9. Verify OpenCode model config allows execution
                opencode_config = self.opencode_model_config[model]
                self.assertTrue(opencode_config["tool_call"], "OpenCode should have tool_call: true")

    def test_configuration_requirements(self):
        """Test that configuration meets requirements for text-based tools"""
        # Translation wrapper config
        for model_id, config in self.model_config.items():
            with self.subTest(model=model_id):
                # Should have supports_tools: false to trigger text parsing
                self.assertFalse(
                    config.get("supports_tools", True),
                    f"Model {model_id} should have supports_tools: false for text parsing",
                )

        # OpenCode config
        for model_id, config in self.opencode_model_config.items():
            with self.subTest(model=model_id):
                # Should have tool_call: true to enable execution
                self.assertTrue(
                    config.get("tool_call", False),
                    f"Model {model_id} should have tool_call: true for execution",
                )

    def test_edge_cases(self):
        """Test edge cases in tool parsing"""
        edge_cases = [
            # Empty code block
            "```python\n\n```",
            # Code without tool calls
            '```python\nprint("hello")\n```',
            # Malformed tool call
            "```python\nBash(\n```",
            # Tool call with complex arguments
            'Write("test.py", """def main():\n    print("test")\n""")',
        ]

        for case in edge_cases:
            with self.subTest(case=case[:50]):
                tool_calls = self.parser.parse_tool_calls(case)
                # Should handle gracefully without crashing
                self.assertIsInstance(tool_calls, list)


if __name__ == "__main__":
    # Run with verbose output
    unittest.main(verbosity=2)
