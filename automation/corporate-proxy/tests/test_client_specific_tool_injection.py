#!/usr/bin/env python3
"""
Test client-specific tool syntax injection in translation wrapper.
Ensures each AI agent (OpenCode, Crush, Gemini) gets appropriate tool invocation syntax.
"""

import sys
import unittest
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

# Add shared/services to path for text_tool_parser import
sys.path.append(str(Path(__file__).parent.parent / "shared" / "services"))

# Import the production function from translation_wrapper
from shared.services.translation_wrapper import inject_tools_into_prompt  # noqa: E402


class TestClientSpecificToolInjection(unittest.TestCase):
    """Test that each client gets correct tool invocation syntax"""

    def setUp(self):
        """Set up test fixtures"""
        # Sample tools that would be provided
        self.tools = [
            {
                "function": {
                    "name": "write",
                    "description": "Write content to a file",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_path": {"type": "string", "description": "Path to file"},
                            "content": {"type": "string", "description": "Content to write"},
                        },
                        "required": ["file_path", "content"],
                    },
                }
            },
            {
                "function": {
                    "name": "edit",
                    "description": "Edit an existing file",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_path": {"type": "string", "description": "Path to file"},
                            "old_string": {"type": "string", "description": "Text to replace"},
                            "new_string": {"type": "string", "description": "Replacement text"},
                            "replace_all": {"type": "boolean", "description": "Replace all occurrences"},
                        },
                        "required": ["file_path", "old_string", "new_string"],
                    },
                }
            },
        ]

        self.messages = [{"role": "user", "content": "Help me write some code"}]

    def test_opencode_tool_syntax(self):
        """Test that OpenCode gets camelCase parameter examples"""
        result = inject_tools_into_prompt(self.messages, self.tools, client_type="opencode")

        # Extract the system message
        system_msg = None
        for msg in result:
            if msg.get("role") == "system":
                system_msg = msg.get("content", "")
                break

        self.assertIsNotNone(system_msg)

        # Check for OpenCode-specific syntax with camelCase
        self.assertIn('filePath="', system_msg)
        self.assertIn("Write(filePath=", system_msg)
        self.assertIn("Edit(filePath=", system_msg)
        self.assertIn("oldString=", system_msg)
        self.assertIn("newString=", system_msg)
        self.assertIn("Bash(command=", system_msg)
        self.assertIn("description=", system_msg)  # Bash requires description

        # Should NOT contain snake_case versions
        self.assertNotIn('file_path="', system_msg)
        self.assertNotIn("old_string=", system_msg)
        self.assertNotIn("new_string=", system_msg)
        self.assertNotIn("params: file_path, old_string, new_string, replace_all", system_msg)

    def test_crush_tool_syntax(self):
        """Test that Crush gets snake_case parameter examples"""
        result = inject_tools_into_prompt(self.messages, self.tools, client_type="crush")

        # Extract the system message
        system_msg = None
        for msg in result:
            if msg.get("role") == "system":
                system_msg = msg.get("content", "")
                break

        self.assertIsNotNone(system_msg)

        # Check for Crush-specific syntax with snake_case
        self.assertIn('file_path="', system_msg)
        self.assertIn("Write(file_path=", system_msg)
        self.assertIn("Edit(file_path=", system_msg)
        self.assertIn("old_string=", system_msg)
        self.assertIn("new_string=", system_msg)
        self.assertIn("View(", system_msg)  # Crush uses View not Read
        self.assertIn("Bash(command=", system_msg)

        # Should NOT contain camelCase versions
        self.assertNotIn('filePath="', system_msg)
        self.assertNotIn("oldString=", system_msg)
        self.assertNotIn("newString=", system_msg)
        self.assertNotIn("params: filePath, oldString, newString, replaceAll", system_msg)

    def test_gemini_tool_syntax(self):
        """Test that Gemini gets functionCall format"""
        result = inject_tools_into_prompt(self.messages, self.tools, client_type="gemini")

        # Extract the system message
        system_msg = None
        for msg in result:
            if msg.get("role") == "system":
                system_msg = msg.get("content", "")
                break

        self.assertIsNotNone(system_msg)

        # Check for Gemini-specific Python function syntax
        self.assertIn("write_file(file_path=", system_msg)
        self.assertIn("read_file(absolute_path=", system_msg)
        self.assertIn("edit(file_path=", system_msg)
        self.assertIn("old_string=", system_msg)
        self.assertIn("new_string=", system_msg)
        self.assertIn("run_shell_command(command=", system_msg)

        # Check for Gemini-specific parameter warnings
        self.assertIn("read_file uses absolute_path", system_msg)
        self.assertIn("write_file and edit use file_path", system_msg)

    def test_generic_fallback_syntax(self):
        """Test that generic/unknown clients get default syntax"""
        result = inject_tools_into_prompt(self.messages, self.tools, client_type="generic")

        # Extract the system message
        system_msg = None
        for msg in result:
            if msg.get("role") == "system":
                system_msg = msg.get("content", "")
                break

        self.assertIsNotNone(system_msg)

        # Check for generic syntax
        self.assertIn("Write(", system_msg)
        self.assertIn("Edit(", system_msg)
        self.assertIn("Read(", system_msg)

        # Should not have specific parameter comments
        self.assertNotIn("# last param is", system_msg)

    def test_no_client_type_uses_generic(self):
        """Test that omitting client_type uses generic format"""
        # Call without specifying client_type
        result = inject_tools_into_prompt(self.messages, self.tools)

        # Extract the system message
        system_msg = None
        for msg in result:
            if msg.get("role") == "system":
                system_msg = msg.get("content", "")
                break

        self.assertIsNotNone(system_msg)

        # Should use generic format
        self.assertIn("Write(", system_msg)
        self.assertIn("Edit(", system_msg)
        self.assertIn("Read(", system_msg)

    def test_tool_descriptions_present(self):
        """Test that tool descriptions are included for all clients"""
        for client_type in ["opencode", "crush", "gemini", "generic"]:
            with self.subTest(client_type=client_type):
                result = inject_tools_into_prompt(self.messages, self.tools, client_type=client_type)

                # Extract the system message
                system_msg = None
                for msg in result:
                    if msg.get("role") == "system":
                        system_msg = msg.get("content", "")
                        break

                self.assertIsNotNone(system_msg)

                # Check that tool descriptions are present
                self.assertIn("**write**: Write content to a file", system_msg)
                self.assertIn("**edit**: Edit an existing file", system_msg)
                self.assertIn("file_path (string, required)", system_msg)
                self.assertIn("content (string, required)", system_msg)

    def test_common_instructions_present(self):
        """Test that common instructions are present for all clients"""
        for client_type in ["opencode", "crush", "gemini", "generic"]:
            with self.subTest(client_type=client_type):
                result = inject_tools_into_prompt(self.messages, self.tools, client_type=client_type)

                # Extract the system message
                system_msg = None
                for msg in result:
                    if msg.get("role") == "system":
                        system_msg = msg.get("content", "")
                        break

                self.assertIsNotNone(system_msg)

                # Check common instructions
                if client_type == "generic":
                    self.assertIn("IMPORTANT: You have access to powerful tools", system_msg)
                    self.assertIn("ALWAYS use tools", system_msg)
                else:
                    self.assertIn("CRITICAL: You MUST use these tools", system_msg)
                    self.assertIn("YOU MUST USE TOOLS", system_msg)

    def test_preserves_existing_system_message(self):
        """Test that existing system message is preserved"""
        messages_with_system = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Help me write code"},
        ]

        result = inject_tools_into_prompt(messages_with_system, self.tools, client_type="opencode")

        # Find system message
        system_msg = None
        for msg in result:
            if msg.get("role") == "system":
                system_msg = msg.get("content", "")
                break

        self.assertIsNotNone(system_msg)

        # Check that both tool instructions and original content are present
        self.assertIn("CRITICAL: You MUST use these tools", system_msg)
        self.assertIn("You are a helpful assistant.", system_msg)

    def test_handles_empty_tools(self):
        """Test that empty tools list returns unchanged messages"""
        result = inject_tools_into_prompt(self.messages, [], client_type="opencode")
        self.assertEqual(result, self.messages)

    def test_bash_and_search_tools(self):
        """Test that Bash and search tools are correctly formatted"""
        for client_type in ["opencode", "crush", "generic"]:
            with self.subTest(client_type=client_type):
                result = inject_tools_into_prompt(self.messages, self.tools, client_type=client_type)

                # Extract the system message
                system_msg = None
                for msg in result:
                    if msg.get("role") == "system":
                        system_msg = msg.get("content", "")
                        break

                # All Python-style clients should have these examples
                if client_type == "generic":
                    # Generic uses simpler format
                    self.assertIn("Bash(", system_msg)
                    self.assertIn("Grep(", system_msg)
                    self.assertIn("Glob(", system_msg)
                else:
                    # OpenCode and Crush use parameter names
                    self.assertIn("Bash(command=", system_msg)
                    self.assertIn("Grep(pattern=", system_msg)
                    self.assertIn("Glob(pattern=", system_msg)


if __name__ == "__main__":
    unittest.main(verbosity=2)
