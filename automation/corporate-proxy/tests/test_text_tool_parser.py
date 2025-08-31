#!/usr/bin/env python3
"""
Unit tests for the text-based tool parser
"""

import sys
import unittest
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))
from shared.services.text_tool_parser import TextToolParser, ToolInjector  # noqa: E402


class TestTextToolParser(unittest.TestCase):
    """Test the TextToolParser class"""

    def setUp(self):
        """Set up test fixtures"""
        self.parser = TextToolParser()
        self.sample_tools = {
            "read_file": {
                "description": "Read contents of a file",
                "parameters": {
                    "properties": {"path": {"type": "string", "description": "Path to file"}},
                    "required": ["path"],
                },
            },
            "write_file": {
                "description": "Write content to a file",
                "parameters": {
                    "properties": {
                        "path": {"type": "string", "description": "Path to file"},
                        "content": {"type": "string", "description": "Content to write"},
                    },
                    "required": ["path", "content"],
                },
            },
        }

    def test_parse_tool_calls_json_format(self):
        """Test parsing tool calls in JSON format"""
        text = """
        I'll read the file for you.

        ```tool_call
        {
          "tool": "read_file",
          "parameters": {
            "path": "/tmp/test.txt"
          }
        }
        ```

        Now let me check another file.
        """

        tool_calls = self.parser.parse_tool_calls(text)

        self.assertEqual(len(tool_calls), 1)
        self.assertEqual(tool_calls[0]["name"], "read_file")
        self.assertEqual(tool_calls[0]["parameters"]["path"], "/tmp/test.txt")

    def test_parse_multiple_tool_calls(self):
        """Test parsing multiple tool calls"""
        text = """
        Let me read and write some files.

        ```tool_call
        {
          "tool": "read_file",
          "parameters": {
            "path": "input.txt"
          }
        }
        ```

        Now I'll write to another file.

        ```tool_call
        {
          "tool": "write_file",
          "parameters": {
            "path": "output.txt",
            "content": "Hello World"
          }
        }
        ```
        """

        tool_calls = self.parser.parse_tool_calls(text)

        self.assertEqual(len(tool_calls), 2)
        self.assertEqual(tool_calls[0]["name"], "read_file")
        self.assertEqual(tool_calls[1]["name"], "write_file")
        self.assertEqual(tool_calls[1]["parameters"]["content"], "Hello World")

    def test_parse_python_style_format(self):
        """Test parsing Python-style function calls"""
        text = """
        I'll create the file and run the tests.

        Write("hello.md", "# Hello World\\n\\nThis is a test file.")

        Now let me run the command:

        Bash("./run.sh --verbose")
        """

        tool_calls = self.parser.parse_tool_calls(text)

        self.assertEqual(len(tool_calls), 2)
        # Tool names should be normalized to snake_case
        self.assertEqual(tool_calls[0]["name"], "write")
        self.assertEqual(tool_calls[0]["parameters"]["file_path"], "hello.md")
        self.assertIn("Hello World", tool_calls[0]["parameters"]["content"])

        self.assertEqual(tool_calls[1]["name"], "bash")
        self.assertEqual(tool_calls[1]["parameters"]["command"], "./run.sh --verbose")

    def test_parse_python_style_limitation(self):
        """Test that complex strings with ast.literal_eval have limitations"""
        # Multi-line content and complex escaping are challenging
        # This is a known limitation - models should use JSON format for complex content
        text = '''
        Write("test.py", """def main():
    print("Hello, World!")""")
        '''

        tool_calls = self.parser.parse_tool_calls(text)

        # The tool is detected but arguments may fail to parse
        # This is acceptable - we prefer predictable failures over incorrect parsing
        self.assertEqual(len(tool_calls), 1)
        self.assertEqual(tool_calls[0]["name"], "write")
        # With ast.literal_eval only, complex strings won't parse
        self.assertEqual(tool_calls[0]["parameters"], {})

    def test_parse_python_with_escaped_quotes(self):
        """Test parsing Python calls with escaped quotes"""
        text = r"""
        Let me run a command with quotes:

        Bash("echo \"Hello \\\"World\\\"\"")
        """

        tool_calls = self.parser.parse_tool_calls(text)

        self.assertEqual(len(tool_calls), 1)
        self.assertEqual(tool_calls[0]["name"], "bash")
        # The escaped quotes should be preserved in the parsed value
        self.assertIn("Hello", tool_calls[0]["parameters"]["command"])

    def test_parse_python_with_different_types(self):
        """Test parsing Python calls with different literal types"""
        text = """
        Testing different types:

        Read("config.json", 100, 50)
        """

        tool_calls = self.parser.parse_tool_calls(text)

        self.assertEqual(len(tool_calls), 1)
        self.assertEqual(tool_calls[0]["name"], "read")
        self.assertEqual(tool_calls[0]["parameters"]["file_path"], "config.json")
        self.assertEqual(tool_calls[0]["parameters"]["limit"], 100)
        self.assertEqual(tool_calls[0]["parameters"]["offset"], 50)

    def test_tool_name_normalization(self):
        """Test that PascalCase tool names are normalized to snake_case"""
        text = """
        MultiEdit("file.txt", [{"old": "foo", "new": "bar"}])
        WebFetch("https://example.com", "Get summary")
        """

        tool_calls = self.parser.parse_tool_calls(text)

        self.assertEqual(len(tool_calls), 2)
        self.assertEqual(tool_calls[0]["name"], "multi_edit")
        self.assertEqual(tool_calls[1]["name"], "web_fetch")

    def test_parse_alternative_format(self):
        """Test parsing alternative XML-like format"""
        text = """
        Let me read the file.

        <tool>read_file(path="test.txt")</tool>

        And write another one.

        <tool>write_file(path="output.txt", content="Test content")</tool>
        """

        tool_calls = self.parser.parse_tool_calls(text)

        self.assertEqual(len(tool_calls), 2)
        self.assertEqual(tool_calls[0]["name"], "read_file")
        self.assertEqual(tool_calls[0]["parameters"]["path"], "test.txt")
        self.assertEqual(tool_calls[1]["name"], "write_file")
        self.assertEqual(tool_calls[1]["parameters"]["content"], "Test content")

    def test_parse_invalid_json(self):
        """Test handling of invalid JSON in tool calls"""
        text = """
        ```tool_call
        {
          "tool": "read_file",
          "parameters": {
            "path": "missing_quote
          }
        }
        ```
        """

        tool_calls = self.parser.parse_tool_calls(text)

        # Should not parse invalid JSON
        self.assertEqual(len(tool_calls), 0)

    def test_format_tool_results_success(self):
        """Test formatting successful tool results"""
        results = [
            {
                "tool": "read_file",
                "parameters": {"path": "test.txt"},
                "result": {"success": True, "content": "File contents here"},
            }
        ]

        formatted = self.parser.format_tool_results(results)

        self.assertIn("Tool Result: read_file", formatted)
        self.assertIn("File contents here", formatted)

    def test_format_tool_results_error(self):
        """Test formatting tool error results"""
        results = [
            {
                "tool": "read_file",
                "parameters": {"path": "missing.txt"},
                "result": {"success": False, "error": "File not found"},
            }
        ]

        formatted = self.parser.format_tool_results(results)

        self.assertIn("Tool Error: read_file", formatted)
        self.assertIn("File not found", formatted)

    def test_is_complete_response(self):
        """Test completion detection"""
        complete_responses = [
            "The task is complete.",
            "I have completed the task successfully.",
            "Task has been completed.",
            "I've completed all the requested work.",
        ]

        incomplete_responses = ["Let me continue working on this.", "I need to do more work.", "Still processing the request."]

        for response in complete_responses:
            self.assertTrue(self.parser.is_complete_response(response), f"Should detect as complete: {response}")

        for response in incomplete_responses:
            self.assertFalse(self.parser.is_complete_response(response), f"Should detect as incomplete: {response}")

    def test_generate_tool_prompt(self):
        """Test tool prompt generation"""
        prompt = self.parser.generate_tool_prompt(self.sample_tools, "Read the config file")

        # Check that tools are described
        self.assertIn("read_file", prompt)
        self.assertIn("write_file", prompt)
        self.assertIn("Read the config file", prompt)
        self.assertIn("```tool_call```", prompt)
        self.assertIn('"tool": "tool_name"', prompt)

    def test_process_response_with_tools(self):
        """Test processing a response with tool calls"""
        response = """
        I'll read the file for you.

        ```tool_call
        {
          "tool": "read_file",
          "parameters": {
            "path": "config.json"
          }
        }
        ```
        """

        # Mock executor
        def mock_executor(tool_name, params):
            return {"success": True, "content": '{"setting": "value"}'}

        self.parser.tool_executor = mock_executor

        continuation, results, needs_continue = self.parser.process_response_with_tools(response)

        self.assertTrue(needs_continue)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["tool"], "read_file")
        self.assertIn("Tool Result: read_file", continuation)


class TestToolInjector(unittest.TestCase):
    """Test the ToolInjector class"""

    def setUp(self):
        """Set up test fixtures"""
        self.tools = {
            "test_tool": {
                "description": "A test tool",
                "parameters": {
                    "properties": {"param1": {"type": "string", "description": "First parameter"}},
                    "required": ["param1"],
                },
            }
        }
        self.injector = ToolInjector(self.tools)

    def test_inject_tools_into_messages(self):
        """Test injecting tools into message history"""
        messages = [
            {"role": "system", "content": "You are a helpful assistant"},
            {"role": "user", "content": "Hello, please help me"},
        ]

        modified = self.injector.inject_tools_into_messages(messages)

        # Should modify the first user message
        self.assertEqual(len(modified), 2)
        self.assertIn("test_tool", modified[1]["content"])
        self.assertIn("```tool_call```", modified[1]["content"])

    def test_inject_system_prompt(self):
        """Test enhancing system prompt with tool instructions"""
        original = "You are a helpful assistant."
        enhanced = self.injector.inject_system_prompt(original)

        self.assertIn(original, enhanced)
        self.assertIn("tools", enhanced.lower())
        self.assertIn("tool calling format", enhanced.lower())

    def test_inject_empty_tools(self):
        """Test injection with no tools"""
        injector = ToolInjector({})
        messages = [{"role": "user", "content": "Hello"}]

        modified = injector.inject_tools_into_messages(messages)

        # Should not modify if no tools
        self.assertEqual(messages, modified)


class TestToolCallFormats(unittest.TestCase):
    """Test various tool call formats"""

    def setUp(self):
        self.parser = TextToolParser()

    def test_nested_json_parameters(self):
        """Test parsing nested JSON parameters"""
        text = """
        ```tool_call
        {
          "tool": "complex_tool",
          "parameters": {
            "config": {
              "nested": true,
              "level": 2
            },
            "array": [1, 2, 3]
          }
        }
        ```
        """

        tool_calls = self.parser.parse_tool_calls(text)

        self.assertEqual(len(tool_calls), 1)
        self.assertEqual(tool_calls[0]["parameters"]["config"]["nested"], True)
        self.assertEqual(tool_calls[0]["parameters"]["array"], [1, 2, 3])

    def test_special_characters_in_parameters(self):
        """Test handling special characters in parameters"""
        text = """
        ```tool_call
        {
          "tool": "write_file",
          "parameters": {
            "path": "/path/with spaces/file.txt",
            "content": "Line 1\\nLine 2\\tTabbed"
          }
        }
        ```
        """

        tool_calls = self.parser.parse_tool_calls(text)

        self.assertEqual(len(tool_calls), 1)
        self.assertEqual(tool_calls[0]["parameters"]["path"], "/path/with spaces/file.txt")
        # JSON parsing converts \n to actual newline
        self.assertIn("\n", tool_calls[0]["parameters"]["content"])
        self.assertIn("\t", tool_calls[0]["parameters"]["content"])


if __name__ == "__main__":
    unittest.main()
