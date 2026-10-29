#!/usr/bin/env python3
"""
Test OpenCode parameter mapping for corporate proxy.
Ensures parsed tool calls are mapped to the OpenCode 2.x tool schema
(read/write/edit take `path`, commands go through `shell`).
"""

import json
from pathlib import Path
import sys
import unittest

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

# Import the production function from test utilities
from proxy_test_helpers import (  # noqa: E402
    OPENCODE_PARAM_MAPPINGS,
    OPENCODE_TOOL_RENAMES,
    format_tool_calls_for_openai,
)
from shared.services.text_tool_parser import TextToolParser  # noqa: E402

# Parameters OpenCode 2.2.1 declares for its built-in tools (captured from the
# tool definitions it sends with a chat request). Mapping targets must be
# names from these lists, or OpenCode rejects the call.
OPENCODE_TOOL_SCHEMA = {
    "edit": {"path", "oldString", "newString", "replaceAll"},
    "glob": {"pattern", "path", "hidden", "limit"},
    "grep": {"pattern", "path", "include", "caseSensitive", "literal", "limit"},
    "read": {"path", "offset", "limit"},
    "shell": {"command", "workdir", "timeout", "background"},
    "webfetch": {"url", "format", "timeout"},
    "websearch": {"query"},
    "write": {"path", "content"},
}


class TestOpenCodeParamMapping(unittest.TestCase):
    """Test OpenCode parameter name mapping"""

    def setUp(self):
        """Set up test fixtures"""
        self.parser = TextToolParser()

    def _args(self, formatted, index=0):
        return json.loads(formatted[index]["function"]["arguments"])

    def test_mapping_targets_match_opencode_schema(self):
        """Every mapped tool and parameter exists in the OpenCode 2.x schema"""
        for tool, mappings in OPENCODE_PARAM_MAPPINGS.items():
            self.assertIn(tool, OPENCODE_TOOL_SCHEMA, f"unknown OpenCode tool {tool}")
            for source, target in mappings.items():
                if source.startswith("_"):
                    continue
                self.assertIn(target, OPENCODE_TOOL_SCHEMA[tool], f"{tool}.{source} -> {target}")
        for source, target in OPENCODE_TOOL_RENAMES.items():
            self.assertIn(target, OPENCODE_TOOL_SCHEMA, f"rename {source} -> {target}")

    def test_write_parameter_mapping(self):
        """Test that write tool parameters are mapped to `path`"""
        text = 'Write("hello.md", "Hello World")'

        tool_calls = self.parser.parse_tool_calls(text)
        formatted = format_tool_calls_for_openai(tool_calls)

        self.assertEqual(len(formatted), 1)
        args = self._args(formatted)
        self.assertEqual(formatted[0]["function"]["name"], "write")
        self.assertEqual(args["path"], "hello.md")
        self.assertEqual(args["content"], "Hello World")
        self.assertNotIn("file_path", args)
        self.assertNotIn("filePath", args)

    def test_camelcase_file_path_is_mapped(self):
        """The 1.x filePath spelling still reaches OpenCode as `path`"""
        text = 'Read(filePath="notes.txt")'

        formatted = format_tool_calls_for_openai(self.parser.parse_tool_calls(text))

        args = self._args(formatted)
        self.assertEqual(args, {"path": "notes.txt"})

    def test_bash_is_renamed_to_shell(self):
        """Bash calls become OpenCode's shell tool without the old description parameter"""
        text = 'Bash(command="ls -la", description="List files")'

        tool_calls = self.parser.parse_tool_calls(text)
        formatted = format_tool_calls_for_openai(tool_calls)

        self.assertEqual(len(formatted), 1)
        self.assertEqual(formatted[0]["function"]["name"], "shell")
        args = self._args(formatted)
        self.assertEqual(args, {"command": "ls -la"})

    def test_shell_positional_command(self):
        """Shell("...") maps its positional argument to command"""
        text = 'Shell(command="git status", workdir="repo")'

        formatted = format_tool_calls_for_openai(self.parser.parse_tool_calls(text))

        self.assertEqual(formatted[0]["function"]["name"], "shell")
        self.assertEqual(self._args(formatted), {"command": "git status", "workdir": "repo"})

    def test_edit_parameter_mapping(self):
        """Test that edit tool parameters are mapped correctly"""
        text = 'Edit("config.py", "DEBUG = False", "DEBUG = True", True)'

        tool_calls = self.parser.parse_tool_calls(text)
        formatted = format_tool_calls_for_openai(tool_calls)

        self.assertEqual(len(formatted), 1)
        args = self._args(formatted)
        self.assertEqual(args["path"], "config.py")
        self.assertEqual(args["oldString"], "DEBUG = False")
        self.assertEqual(args["newString"], "DEBUG = True")
        self.assertEqual(args["replaceAll"], True)
        for snake in ("file_path", "old_string", "new_string", "replace_all"):
            self.assertNotIn(snake, args)

    def test_read_with_optional_params(self):
        """Test read tool with optional parameters"""
        text = 'Read("large_file.txt", 100, 50)'

        tool_calls = self.parser.parse_tool_calls(text)
        formatted = format_tool_calls_for_openai(tool_calls)

        self.assertEqual(len(formatted), 1)
        args = self._args(formatted)
        self.assertEqual(args["path"], "large_file.txt")
        self.assertEqual(args["limit"], 100)
        self.assertEqual(args["offset"], 50)

    def test_unmapped_tool_preserves_names(self):
        """Test that tools without mappings preserve their parameter names"""
        tool_calls = [{"name": "custom_tool", "parameters": {"some_param": "value", "another_param": 123}}]

        formatted = format_tool_calls_for_openai(tool_calls)

        self.assertEqual(len(formatted), 1)
        self.assertEqual(formatted[0]["function"]["name"], "custom_tool")
        args = self._args(formatted)
        self.assertEqual(args, {"some_param": "value", "another_param": 123})

    def test_crush_mode_leaves_calls_unchanged(self):
        """Without OpenCode mappings, names and parameters pass through"""
        tool_calls = [{"name": "bash", "parameters": {"command": "ls", "description": "d"}}]

        formatted = format_tool_calls_for_openai(tool_calls, apply_opencode_mappings=False)

        self.assertEqual(formatted[0]["function"]["name"], "bash")
        self.assertEqual(self._args(formatted), {"command": "ls", "description": "d"})

    def test_streaming_with_mapping(self):
        """Test that streaming mode works with parameter mapping"""
        text = 'Write("test.md", "Test")'

        tool_calls = self.parser.parse_tool_calls(text)
        formatted = format_tool_calls_for_openai(tool_calls, streaming=True)

        self.assertEqual(len(formatted), 1)
        self.assertEqual(formatted[0]["index"], 0)
        args = self._args(formatted)
        self.assertIn("path", args)
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
        self.assertEqual([f["function"]["name"] for f in formatted], ["write", "shell", "read"])
        self.assertEqual(self._args(formatted, 0)["path"], "file1.txt")
        self.assertEqual(self._args(formatted, 1), {"command": "echo test"})
        self.assertEqual(self._args(formatted, 2)["path"], "file2.txt")

    def test_grep_mapping(self):
        """Test grep parameters map to the OpenCode 2.x names"""
        tool_calls = [
            {
                "name": "grep",
                "parameters": {
                    "pattern": "TODO",
                    "path": ".",
                    "glob": "*.py",
                    "case_sensitive": False,
                    "head_limit": 20,
                },
            }
        ]

        formatted = format_tool_calls_for_openai(tool_calls)
        args = self._args(formatted)

        self.assertEqual(
            args,
            {"pattern": "TODO", "path": ".", "include": "*.py", "caseSensitive": False, "limit": 20},
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
