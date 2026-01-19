#!/usr/bin/env python3
"""
Test Crush parameter mapping for corporate proxy.
Ensures snake_case parameters are preserved for Crush (not converted to camelCase).
"""

import json
from pathlib import Path
import sys
import unittest

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

# Import the production function from test utilities
from proxy_test_helpers import format_tool_calls_for_openai  # noqa: E402
from shared.services.text_tool_parser import TextToolParser  # noqa: E402


class TestCrushParamMapping(unittest.TestCase):
    """Test Crush parameter name preservation (snake_case)"""

    def setUp(self):
        """Set up test fixtures"""
        self.parser = TextToolParser()

    def test_write_parameter_preservation(self):
        """Test that write tool parameters keep snake_case for Crush"""
        text = 'Write("hello.md", "Hello World")'

        tool_calls = self.parser.parse_tool_calls(text)
        # Format with apply_opencode_mappings=False for Crush
        formatted = format_tool_calls_for_openai(tool_calls, apply_opencode_mappings=False)

        self.assertEqual(len(formatted), 1)
        args = json.loads(formatted[0]["function"]["arguments"])

        # Check that snake_case is preserved for Crush
        self.assertIn("file_path", args)
        self.assertEqual(args["file_path"], "hello.md")
        self.assertIn("content", args)
        self.assertEqual(args["content"], "Hello World")

        # camelCase should NOT be present
        self.assertNotIn("filePath", args)

    def test_bash_no_extra_defaults(self):
        """Test that bash tool doesn't get extra defaults for Crush"""
        text = 'Bash("ls -la")'

        tool_calls = self.parser.parse_tool_calls(text)
        # Format with apply_opencode_mappings=False for Crush
        formatted = format_tool_calls_for_openai(tool_calls, apply_opencode_mappings=False)

        self.assertEqual(len(formatted), 1)
        args = json.loads(formatted[0]["function"]["arguments"])

        # Check command is present
        self.assertIn("command", args)
        self.assertEqual(args["command"], "ls -la")

        # No default description should be added for Crush
        self.assertNotIn("description", args)

    def test_edit_parameter_preservation(self):
        """Test that edit tool parameters keep snake_case for Crush"""
        text = 'Edit("config.py", "DEBUG = False", "DEBUG = True", True)'

        tool_calls = self.parser.parse_tool_calls(text)
        # Format with apply_opencode_mappings=False for Crush
        formatted = format_tool_calls_for_openai(tool_calls, apply_opencode_mappings=False)

        self.assertEqual(len(formatted), 1)
        args = json.loads(formatted[0]["function"]["arguments"])

        # Check all parameters are in snake_case
        self.assertIn("file_path", args)
        self.assertEqual(args["file_path"], "config.py")
        self.assertIn("old_string", args)
        self.assertEqual(args["old_string"], "DEBUG = False")
        self.assertIn("new_string", args)
        self.assertEqual(args["new_string"], "DEBUG = True")
        self.assertIn("replace_all", args)
        self.assertEqual(args["replace_all"], True)

        # camelCase should NOT be present
        self.assertNotIn("filePath", args)
        self.assertNotIn("oldString", args)
        self.assertNotIn("newString", args)
        self.assertNotIn("replaceAll", args)

    def test_read_with_optional_params(self):
        """Test read tool with optional parameters for Crush"""
        text = 'Read("large_file.txt", 100, 50)'

        tool_calls = self.parser.parse_tool_calls(text)
        # Format with apply_opencode_mappings=False for Crush
        formatted = format_tool_calls_for_openai(tool_calls, apply_opencode_mappings=False)

        self.assertEqual(len(formatted), 1)
        args = json.loads(formatted[0]["function"]["arguments"])

        # Check snake_case parameters
        self.assertIn("file_path", args)
        self.assertEqual(args["file_path"], "large_file.txt")
        self.assertIn("limit", args)
        self.assertEqual(args["limit"], 100)
        self.assertIn("offset", args)
        self.assertEqual(args["offset"], 50)

        # camelCase should NOT be present
        self.assertNotIn("filePath", args)

    def test_comparison_opencode_vs_crush(self):
        """Test that the same tool call produces different output for OpenCode vs Crush"""
        text = 'Write("test.txt", "content")'

        tool_calls = self.parser.parse_tool_calls(text)

        # Format for OpenCode (default behavior)
        opencode_formatted = format_tool_calls_for_openai(tool_calls, apply_opencode_mappings=True)
        opencode_args = json.loads(opencode_formatted[0]["function"]["arguments"])

        # Format for Crush
        crush_formatted = format_tool_calls_for_openai(tool_calls, apply_opencode_mappings=False)
        crush_args = json.loads(crush_formatted[0]["function"]["arguments"])

        # OpenCode should have camelCase
        self.assertIn("filePath", opencode_args)
        self.assertNotIn("file_path", opencode_args)

        # Crush should have snake_case
        self.assertIn("file_path", crush_args)
        self.assertNotIn("filePath", crush_args)

        # Values should be the same
        self.assertEqual(opencode_args["filePath"], crush_args["file_path"])
        self.assertEqual(opencode_args["content"], crush_args["content"])

    def test_streaming_with_preservation(self):
        """Test that streaming mode works with parameter preservation for Crush"""
        text = 'Write("test.md", "Test")'

        tool_calls = self.parser.parse_tool_calls(text)
        # Format with streaming and no OpenCode mappings
        formatted = format_tool_calls_for_openai(tool_calls, streaming=True, apply_opencode_mappings=False)

        self.assertEqual(len(formatted), 1)

        # Check index is present for streaming
        self.assertIn("index", formatted[0])
        self.assertEqual(formatted[0]["index"], 0)

        # Check parameters are still in snake_case
        args = json.loads(formatted[0]["function"]["arguments"])
        self.assertIn("file_path", args)
        self.assertNotIn("filePath", args)

    def test_multiple_tools_with_preservation(self):
        """Test multiple tool calls with snake_case preservation for Crush"""
        text = """
        Write("file1.txt", "content1")
        Bash("echo test")
        Read("file2.txt")
        """

        tool_calls = self.parser.parse_tool_calls(text)
        # Format with no OpenCode mappings
        formatted = format_tool_calls_for_openai(tool_calls, apply_opencode_mappings=False)

        self.assertEqual(len(formatted), 3)

        # Check first tool (Write)
        args0 = json.loads(formatted[0]["function"]["arguments"])
        self.assertIn("file_path", args0)
        self.assertEqual(args0["file_path"], "file1.txt")
        self.assertNotIn("filePath", args0)

        # Check second tool (Bash)
        args1 = json.loads(formatted[1]["function"]["arguments"])
        self.assertIn("command", args1)
        self.assertNotIn("description", args1)  # No default for Crush

        # Check third tool (Read)
        args2 = json.loads(formatted[2]["function"]["arguments"])
        self.assertIn("file_path", args2)
        self.assertEqual(args2["file_path"], "file2.txt")
        self.assertNotIn("filePath", args2)

    def test_grep_no_complex_mapping(self):
        """Test grep tool without complex parameter mappings for Crush"""
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

        # Format with no OpenCode mappings
        formatted = format_tool_calls_for_openai(tool_calls, apply_opencode_mappings=False)
        args = json.loads(formatted[0]["function"]["arguments"])

        # Check parameters are preserved as-is
        self.assertEqual(args["pattern"], "TODO")
        self.assertEqual(args["path"], ".")
        self.assertEqual(args["output_mode"], "content")  # Not converted to outputMode
        self.assertEqual(args["-n"], True)  # Not converted to showLineNumbers
        self.assertEqual(args["-i"], True)  # Not converted to caseInsensitive
        self.assertEqual(args["-A"], 2)  # Not converted to linesAfter

        # Mapped names should NOT be present
        self.assertNotIn("outputMode", args)
        self.assertNotIn("showLineNumbers", args)
        self.assertNotIn("caseInsensitive", args)
        self.assertNotIn("linesAfter", args)


if __name__ == "__main__":
    unittest.main(verbosity=2)
