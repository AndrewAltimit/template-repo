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
        self.assertIn("Write(filePath, content)", system_msg)
        self.assertIn("Edit(filePath, oldString, newString)", system_msg)
        self.assertIn("# last param is replaceAll", system_msg)

        # Should NOT contain snake_case versions
        self.assertNotIn("Write(file_path, content)", system_msg)
        self.assertNotIn("Edit(file_path, old_string, new_string)", system_msg)
        self.assertNotIn("# last param is replace_all", system_msg)

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
        self.assertIn("Write(file_path, content)", system_msg)
        self.assertIn("Edit(file_path, old_string, new_string)", system_msg)
        self.assertIn("# last param is replace_all", system_msg)

        # Should NOT contain camelCase versions
        self.assertNotIn("Write(filePath, content)", system_msg)
        self.assertNotIn("Edit(filePath, oldString, newString)", system_msg)
        self.assertNotIn("# last param is replaceAll", system_msg)

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

        # Check for Gemini-specific syntax
        self.assertIn("functionCall: write", system_msg)
        self.assertIn('args: {"path":', system_msg)
        self.assertIn("functionCall: edit", system_msg)
        self.assertIn('"old_text":', system_msg)
        self.assertIn('"new_text":', system_msg)

        # Should NOT contain Python-style calls
        self.assertNotIn("Write(", system_msg)
        self.assertNotIn("Edit(", system_msg)

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

        # Check for generic syntax (should be snake_case by default)
        self.assertIn("Write(file_path, content)", system_msg)
        self.assertIn("Edit(file_path, old_string, new_string)", system_msg)

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
        self.assertIn("Write(file_path, content)", system_msg)
        self.assertIn("Edit(file_path, old_string, new_string)", system_msg)

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
                self.assertIn("IMPORTANT: You have access to powerful tools", system_msg)
                self.assertIn("ALWAYS use tools", system_msg)
                self.assertIn("Read or write files", system_msg)
                self.assertIn("Execute commands", system_msg)

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
        self.assertIn("IMPORTANT: You have access to powerful tools", system_msg)
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

                # All Python-style clients should have these
                self.assertIn('Bash("ls -la")', system_msg)
                self.assertIn('Grep("pattern", "path")', system_msg)
                self.assertIn('Glob("*.py")', system_msg)


if __name__ == "__main__":
    unittest.main(verbosity=2)
