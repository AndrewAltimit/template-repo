#!/usr/bin/env python3
"""
Test enhanced system prompt injection for better tool usage.
"""

from pathlib import Path
import sys
import unittest

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))
# Also add services directory for text_tool_parser import
sys.path.append(str(Path(__file__).parent.parent / "shared" / "services"))
# pylint: disable=wrong-import-position
from shared.services.translation_wrapper import inject_tools_into_prompt  # noqa: E402


class TestEnhancedPrompt(unittest.TestCase):
    """Test enhanced system prompt injection"""

    def test_enhanced_prompt_injection(self):
        """Test that tool instructions are properly injected into system prompt"""
        messages = [{"role": "system", "content": "You are a coding assistant"}]

        tools = [
            {
                "function": {
                    "name": "Write",
                    "description": "Write content to a file",
                    "parameters": {
                        "properties": {
                            "file_path": {"type": "string", "description": "Path to the file"},
                            "content": {"type": "string", "description": "Content to write"},
                        },
                        "required": ["file_path", "content"],
                    },
                }
            },
            {
                "function": {
                    "name": "Bash",
                    "description": "Execute a bash command",
                    "parameters": {
                        "properties": {
                            "command": {"type": "string", "description": "The command to execute"},
                            "description": {"type": "string", "description": "Description of the command"},
                        },
                        "required": ["command"],
                    },
                }
            },
        ]

        enhanced = inject_tools_into_prompt(messages, tools)

        # Check that system message was enhanced
        self.assertEqual(len(enhanced), 1)
        self.assertEqual(enhanced[0]["role"], "system")

        system_content = enhanced[0]["content"]

        # Check for key elements of enhanced prompt
        self.assertIn("🛠️ IMPORTANT", system_content)
        self.assertIn("Available Tools:", system_content)
        self.assertIn("**Write**:", system_content)
        self.assertIn("**Bash**:", system_content)
        self.assertIn("CRITICAL INSTRUCTIONS", system_content)
        self.assertIn("Python code blocks", system_content)
        self.assertIn('Write("filename.txt", "content here")', system_content)
        self.assertIn('Bash("ls -la")', system_content)

        # Check parameter details are included
        self.assertIn("file_path (string, required)", system_content)
        self.assertIn("content (string, required)", system_content)
        self.assertIn("command (string, required)", system_content)
        self.assertIn("description (string)", system_content)  # Not required

        # Check original system message is preserved
        self.assertIn("You are a coding assistant", system_content)

    def test_no_system_message_creates_one(self):
        """Test that a system message is created if none exists"""
        messages = [{"role": "user", "content": "Hello"}]

        tools = [{"function": {"name": "Read", "description": "Read a file", "parameters": {"properties": {}}}}]

        enhanced = inject_tools_into_prompt(messages, tools)

        # Should have system message first, then user message
        self.assertEqual(len(enhanced), 2)
        self.assertEqual(enhanced[0]["role"], "system")
        self.assertEqual(enhanced[1]["role"], "user")

        # Check system message has tool instructions
        self.assertIn("Available Tools:", enhanced[0]["content"])
        self.assertIn("**Read**:", enhanced[0]["content"])

    def test_empty_tools_no_injection(self):
        """Test that empty tools list doesn't modify messages"""
        messages = [
            {"role": "system", "content": "Original system"},
            {"role": "user", "content": "Hello"},
        ]

        enhanced = inject_tools_into_prompt(messages, [])

        # Messages should be unchanged
        self.assertEqual(enhanced, messages)

    def test_detailed_parameter_formatting(self):
        """Test that parameter details are properly formatted"""
        messages = []
        tools = [
            {
                "function": {
                    "name": "Edit",
                    "description": "Edit a file",
                    "parameters": {
                        "properties": {
                            "file_path": {"type": "string", "description": "Path to file"},
                            "old_string": {"type": "string", "description": "Text to replace"},
                            "new_string": {"type": "string", "description": "Replacement text"},
                            "replace_all": {
                                "type": "boolean",
                                "description": "Replace all occurrences",
                            },
                        },
                        "required": ["file_path", "old_string", "new_string"],
                    },
                }
            }
        ]

        enhanced = inject_tools_into_prompt(messages, tools)

        content = enhanced[0]["content"]

        # Check all parameters are listed with correct format
        self.assertIn("file_path (string, required)", content)
        self.assertIn("old_string (string, required)", content)
        self.assertIn("new_string (string, required)", content)
        self.assertIn("replace_all (boolean):", content)  # Not required

        # Check Edit example is included
        self.assertIn('Edit("file.py", "old_text", "new_text")', content)


if __name__ == "__main__":
    unittest.main(verbosity=2)
