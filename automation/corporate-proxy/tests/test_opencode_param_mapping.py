#!/usr/bin/env python3
"""
Test OpenCode parameter mapping for corporate proxy.
Ensures snake_case parameters are correctly mapped to camelCase for OpenCode.
"""

import json
import sys
import unittest
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))
from shared.services.text_tool_parser import TextToolParser  # noqa: E402

# Mock the global mappings
OPENCODE_PARAM_MAPPINGS = {
    "write": {"file_path": "filePath", "content": "content"},
    "bash": {"command": "command", "_required_defaults": {"description": "Execute bash command"}},
    "read": {"file_path": "filePath", "limit": "limit", "offset": "offset"},
    "edit": {
        "file_path": "filePath",
        "old_string": "oldString",
        "new_string": "newString",
        "replace_all": "replaceAll",
    },
    "grep": {
        "pattern": "pattern",
        "path": "path",
        "output_mode": "outputMode",
        "-n": "showLineNumbers",
        "-A": "linesAfter",
        "-B": "linesBefore",
        "-i": "caseInsensitive",
    },
}


def format_tool_calls_for_openai(tool_calls, streaming=False):
    """Format parsed tool calls into OpenAI format with OpenCode parameter mapping"""
    formatted_calls = []
    for i, call in enumerate(tool_calls):
        tool_name = call.get("name", call.get("tool"))
        params = call.get("parameters", {})

        # Apply OpenCode parameter mappings if available
        if tool_name in OPENCODE_PARAM_MAPPINGS:
            mappings = OPENCODE_PARAM_MAPPINGS[tool_name]
            mapped_params = {}

            # Map parameter names from snake_case to camelCase
            for snake_key, value in params.items():
                camel_key = mappings.get(snake_key, snake_key)  # Use original if no mapping
                mapped_params[camel_key] = value

            # Add required default parameters if specified
            if "_required_defaults" in mappings:
                for key, default_value in mappings["_required_defaults"].items():
                    if key not in mapped_params:
                        mapped_params[key] = default_value

            params = mapped_params

        formatted_call = {
            "id": f"call_{i}",
            "type": "function",
            "function": {"name": tool_name, "arguments": json.dumps(params)},
        }
        # Add index for streaming responses
        if streaming:
            formatted_call["index"] = i
        formatted_calls.append(formatted_call)
    return formatted_calls


class TestOpenCodeParamMapping(unittest.TestCase):
    """Test OpenCode parameter name mapping"""

    def setUp(self):
        """Set up test fixtures"""
        self.parser = TextToolParser()

    def test_write_parameter_mapping(self):
        """Test that write tool parameters are mapped to camelCase"""
        text = 'Write("hello.md", "Hello World")'

        tool_calls = self.parser.parse_tool_calls(text)
        formatted = format_tool_calls_for_openai(tool_calls)

        self.assertEqual(len(formatted), 1)
        args = json.loads(formatted[0]["function"]["arguments"])

        # Check mapped parameters
        self.assertIn("filePath", args)
        self.assertEqual(args["filePath"], "hello.md")
        self.assertIn("content", args)
        self.assertEqual(args["content"], "Hello World")

        # Original snake_case should not be present
        self.assertNotIn("file_path", args)

    def test_bash_required_defaults(self):
        """Test that bash tool gets required default parameters"""
        text = 'Bash("ls -la")'

        tool_calls = self.parser.parse_tool_calls(text)
        formatted = format_tool_calls_for_openai(tool_calls)

        self.assertEqual(len(formatted), 1)
        args = json.loads(formatted[0]["function"]["arguments"])

        # Check command is present
        self.assertIn("command", args)
        self.assertEqual(args["command"], "ls -la")

        # Check required default description is added
        self.assertIn("description", args)
        self.assertEqual(args["description"], "Execute bash command")

    def test_edit_parameter_mapping(self):
        """Test that edit tool parameters are mapped correctly"""
        text = 'Edit("config.py", "DEBUG = False", "DEBUG = True", True)'

        tool_calls = self.parser.parse_tool_calls(text)
        formatted = format_tool_calls_for_openai(tool_calls)

        self.assertEqual(len(formatted), 1)
        args = json.loads(formatted[0]["function"]["arguments"])

        # Check all mapped parameters
        self.assertIn("filePath", args)
        self.assertEqual(args["filePath"], "config.py")
        self.assertIn("oldString", args)
        self.assertEqual(args["oldString"], "DEBUG = False")
        self.assertIn("newString", args)
        self.assertEqual(args["newString"], "DEBUG = True")
        self.assertIn("replaceAll", args)
        self.assertEqual(args["replaceAll"], True)

        # Original snake_case should not be present
        self.assertNotIn("file_path", args)
        self.assertNotIn("old_string", args)
        self.assertNotIn("new_string", args)
        self.assertNotIn("replace_all", args)

    def test_read_with_optional_params(self):
        """Test read tool with optional parameters"""
        text = 'Read("large_file.txt", 100, 50)'

        tool_calls = self.parser.parse_tool_calls(text)
        formatted = format_tool_calls_for_openai(tool_calls)

        self.assertEqual(len(formatted), 1)
        args = json.loads(formatted[0]["function"]["arguments"])

        # Check mapped parameters
        self.assertIn("filePath", args)
        self.assertEqual(args["filePath"], "large_file.txt")
        self.assertIn("limit", args)
        self.assertEqual(args["limit"], 100)
        self.assertIn("offset", args)
        self.assertEqual(args["offset"], 50)

    def test_unmapped_tool_preserves_names(self):
        """Test that tools without mappings preserve their parameter names"""
        # Create a tool call that's not in our mappings
        tool_calls = [{"name": "custom_tool", "parameters": {"some_param": "value", "another_param": 123}}]

        formatted = format_tool_calls_for_openai(tool_calls)

        self.assertEqual(len(formatted), 1)
        args = json.loads(formatted[0]["function"]["arguments"])

        # Original names should be preserved
        self.assertIn("some_param", args)
        self.assertEqual(args["some_param"], "value")
        self.assertIn("another_param", args)
        self.assertEqual(args["another_param"], 123)

    def test_streaming_with_mapping(self):
        """Test that streaming mode works with parameter mapping"""
        text = 'Write("test.md", "Test")'

        tool_calls = self.parser.parse_tool_calls(text)
        formatted = format_tool_calls_for_openai(tool_calls, streaming=True)

        self.assertEqual(len(formatted), 1)

        # Check index is present for streaming
        self.assertIn("index", formatted[0])
        self.assertEqual(formatted[0]["index"], 0)

        # Check parameters are still mapped
        args = json.loads(formatted[0]["function"]["arguments"])
        self.assertIn("filePath", args)
        self.assertNotIn("file_path", args)

    def test_multiple_tools_with_mapping(self):
        """Test multiple tool calls with different mappings"""
        text = """
        Write("file1.txt", "content1")
        Bash("echo test")
        Read("file2.txt")
        """

        tool_calls = self.parser.parse_tool_calls(text)
        formatted = format_tool_calls_for_openai(tool_calls)

        self.assertEqual(len(formatted), 3)

        # Check first tool (Write)
        args0 = json.loads(formatted[0]["function"]["arguments"])
        self.assertIn("filePath", args0)
        self.assertEqual(args0["filePath"], "file1.txt")

        # Check second tool (Bash)
        args1 = json.loads(formatted[1]["function"]["arguments"])
        self.assertIn("command", args1)
        self.assertIn("description", args1)  # Required default

        # Check third tool (Read)
        args2 = json.loads(formatted[2]["function"]["arguments"])
        self.assertIn("filePath", args2)
        self.assertEqual(args2["filePath"], "file2.txt")

    def test_grep_complex_mapping(self):
        """Test grep tool with complex parameter mappings"""
        # Simulate parsed grep tool call with various parameters
        tool_calls = [
            {
                "name": "grep",
                "parameters": {
                    "pattern": "TODO",
                    "path": ".",
                    "output_mode": "content",
                    "-n": True,
                    "-i": True,
                    "-A": 2,
                },
            }
        ]

        formatted = format_tool_calls_for_openai(tool_calls)
        args = json.loads(formatted[0]["function"]["arguments"])

        # Check mapped parameters
        self.assertEqual(args["pattern"], "TODO")
        self.assertEqual(args["path"], ".")
        self.assertEqual(args["outputMode"], "content")  # output_mode -> outputMode
        self.assertEqual(args["showLineNumbers"], True)  # -n -> showLineNumbers
        self.assertEqual(args["caseInsensitive"], True)  # -i -> caseInsensitive
        self.assertEqual(args["linesAfter"], 2)  # -A -> linesAfter

        # Original names should not be present
        self.assertNotIn("output_mode", args)
        self.assertNotIn("-n", args)
        self.assertNotIn("-i", args)
        self.assertNotIn("-A", args)


if __name__ == "__main__":
    unittest.main(verbosity=2)
