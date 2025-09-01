#!/usr/bin/env python3
"""
Test message filtering for company API compatibility.
Ensures tool_calls and other unsupported fields are removed.
"""

import sys
import unittest
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))


def filter_messages_for_company_api(messages):
    """Filter messages to remove unsupported fields for company API"""
    filtered_messages = []

    for msg in messages:
        if msg["role"] == "system":
            # System messages are handled separately in the wrapper
            continue
        elif msg["role"] == "tool":
            # Convert tool messages to user messages
            filtered_messages.append({"role": "user", "content": f"Tool result: {msg.get('content', '')}"})
        else:
            # Filter out tool_calls and cache_control from assistant/user messages
            filtered_msg = {"role": msg["role"]}

            # Handle content
            if "tool_calls" in msg:
                # Convert tool_calls to text if no content
                content = msg.get("content", "")
                if not content and msg.get("tool_calls"):
                    tool_descriptions = []
                    for tc in msg["tool_calls"]:
                        if tc.get("function"):
                            func = tc["function"]
                            tool_descriptions.append(f"[Calling {func.get('name', 'unknown')} tool]")
                    content = " ".join(tool_descriptions) if tool_descriptions else ""
                filtered_msg["content"] = content
            else:
                filtered_msg["content"] = msg.get("content", "")

            # Remove any cache_control fields
            # (OpenCode might add these but company API doesn't support them)

            filtered_messages.append(filtered_msg)

    return filtered_messages


class TestMessageFiltering(unittest.TestCase):
    """Test message filtering for company API compatibility"""

    def test_filter_tool_calls_from_assistant(self):
        """Test that tool_calls are removed from assistant messages"""
        messages = [
            {"role": "user", "content": "write hello into hello.md"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_0",
                        "type": "function",
                        "function": {"name": "write", "arguments": '{"filePath":"hello.md","content":"hello"}'},
                    }
                ],
            },
        ]

        filtered = filter_messages_for_company_api(messages)

        # Should have 2 messages (no system message added)
        self.assertEqual(len(filtered), 2)

        # Check assistant message has no tool_calls
        assistant_msg = filtered[1]
        self.assertNotIn("tool_calls", assistant_msg)
        self.assertEqual(assistant_msg["role"], "assistant")
        self.assertEqual(assistant_msg["content"], "[Calling write tool]")

    def test_filter_cache_control(self):
        """Test that cache_control fields are removed"""
        messages = [
            {"role": "user", "content": "test"},
            {
                "role": "assistant",
                "content": "response",
                "tool_calls": [
                    {
                        "id": "call_0",
                        "type": "function",
                        "function": {"name": "bash", "arguments": "{}"},
                        "cache_control": {"type": "ephemeral"},  # This should be filtered
                    }
                ],
            },
        ]

        filtered = filter_messages_for_company_api(messages)

        # Check no cache_control in output
        for msg in filtered:
            self.assertNotIn("cache_control", msg)
            if "tool_calls" in msg:
                for tc in msg["tool_calls"]:
                    self.assertNotIn("cache_control", tc)

    def test_convert_tool_messages(self):
        """Test that tool role messages are converted to user messages"""
        messages = [
            {"role": "user", "content": "run a command"},
            {"role": "assistant", "content": "I'll run ls"},
            {"role": "tool", "content": "file1.txt\nfile2.txt"},
        ]

        filtered = filter_messages_for_company_api(messages)

        # Tool message should be converted to user
        self.assertEqual(len(filtered), 3)
        tool_msg = filtered[2]
        self.assertEqual(tool_msg["role"], "user")
        self.assertEqual(tool_msg["content"], "Tool result: file1.txt\nfile2.txt")

    def test_system_messages_filtered(self):
        """Test that system messages are filtered out (handled separately)"""
        messages = [
            {"role": "system", "content": "You are a helpful assistant"},
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]

        filtered = filter_messages_for_company_api(messages)

        # System message should be removed
        self.assertEqual(len(filtered), 2)
        self.assertEqual(filtered[0]["role"], "user")
        self.assertEqual(filtered[1]["role"], "assistant")

    def test_empty_content_with_tool_calls(self):
        """Test handling of empty content when tool_calls are present"""
        messages = [
            {"role": "user", "content": "do something"},
            {
                "role": "assistant",
                "content": "",  # Empty content
                "tool_calls": [
                    {"id": "call_0", "type": "function", "function": {"name": "write", "arguments": "{}"}},
                    {"id": "call_1", "type": "function", "function": {"name": "bash", "arguments": "{}"}},
                ],
            },
        ]

        filtered = filter_messages_for_company_api(messages)

        assistant_msg = filtered[1]
        self.assertNotIn("tool_calls", assistant_msg)
        # Should have generated content from tool calls
        self.assertEqual(assistant_msg["content"], "[Calling write tool] [Calling bash tool]")

    def test_mixed_content_and_tool_calls(self):
        """Test when message has both content and tool_calls"""
        messages = [
            {"role": "user", "content": "help me"},
            {
                "role": "assistant",
                "content": "I'll help you with that.",
                "tool_calls": [{"id": "call_0", "type": "function", "function": {"name": "read", "arguments": "{}"}}],
            },
        ]

        filtered = filter_messages_for_company_api(messages)

        assistant_msg = filtered[1]
        self.assertNotIn("tool_calls", assistant_msg)
        # Should preserve existing content
        self.assertEqual(assistant_msg["content"], "I'll help you with that.")

    def test_preserve_normal_messages(self):
        """Test that normal messages without tool_calls are preserved"""
        messages = [
            {"role": "user", "content": "What's 2+2?"},
            {"role": "assistant", "content": "2+2 equals 4."},
            {"role": "user", "content": "Thanks!"},
            {"role": "assistant", "content": "You're welcome!"},
        ]

        filtered = filter_messages_for_company_api(messages)

        self.assertEqual(len(filtered), 4)
        for i, msg in enumerate(filtered):
            self.assertEqual(msg["role"], messages[i]["role"])
            self.assertEqual(msg["content"], messages[i]["content"])
            self.assertNotIn("tool_calls", msg)

    def test_complex_conversation(self):
        """Test a complex conversation with multiple message types"""
        messages = [
            {"role": "system", "content": "You are helpful"},
            {"role": "user", "content": "write hello to test.txt"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [{"id": "call_0", "type": "function", "function": {"name": "write", "arguments": "{}"}}],
            },
            {"role": "tool", "content": "File written successfully"},
            {"role": "assistant", "content": "I've written 'hello' to test.txt"},
            {"role": "user", "content": "now read it"},
            {
                "role": "assistant",
                "content": "Let me read that file for you.",
                "tool_calls": [{"id": "call_1", "type": "function", "function": {"name": "read", "arguments": "{}"}}],
            },
            {"role": "tool", "content": "hello"},
            {"role": "assistant", "content": "The file contains: hello"},
        ]

        filtered = filter_messages_for_company_api(messages)

        # System message filtered, tool messages converted
        expected_roles = ["user", "assistant", "user", "assistant", "user", "assistant", "user", "assistant"]
        self.assertEqual(len(filtered), len(expected_roles))

        for i, expected_role in enumerate(expected_roles):
            self.assertEqual(filtered[i]["role"], expected_role)
            self.assertNotIn("tool_calls", filtered[i])


if __name__ == "__main__":
    unittest.main(verbosity=2)
