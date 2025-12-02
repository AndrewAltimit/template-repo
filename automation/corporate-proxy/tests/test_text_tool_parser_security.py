#!/usr/bin/env python3
"""
Security and robustness tests for the text tool parser
Tests security features, performance optimizations, and edge cases identified by Gemini
"""

import json
import logging
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

# pylint: disable=wrong-import-position
from shared.services.streaming_tool_parser import StreamingToolParser  # noqa: E402
from shared.services.text_tool_parser import TextToolParser  # noqa: E402
from shared.services.tool_injector import ToolInjector  # noqa: E402


class TestTextToolParserSecurity(unittest.TestCase):
    """Test security features of the enhanced parser"""

    def test_allowed_tools_enforcement(self):
        """Test that only allowed tools are parsed"""
        allowed = {"read_file", "write_file"}
        parser = TextToolParser(allowed_tools=allowed, log_errors=False)

        text = """
        ```tool_call
        {"tool": "read_file", "parameters": {"path": "safe.txt"}}
        ```

        ```tool_call
        {"tool": "delete_system", "parameters": {"target": "/etc/passwd"}}
        ```

        ```tool_call
        {"tool": "write_file", "parameters": {"path": "output.txt", "content": "data"}}
        ```
        """

        results = parser.parse_tool_calls(text)

        # Should only parse allowed tools
        self.assertEqual(len(results), 2)
        tool_names = [r["name"] for r in results]
        self.assertIn("read_file", tool_names)
        self.assertIn("write_file", tool_names)
        self.assertNotIn("delete_system", tool_names)

        # Check statistics
        stats = parser.get_stats()
        self.assertEqual(stats["rejected_unauthorized"], 1)
        self.assertEqual(stats["total_parsed"], 2)

    def test_json_size_limit(self):
        """Test that oversized JSON payloads are rejected"""
        parser = TextToolParser(max_json_size=100, log_errors=False)  # 100 bytes limit

        # Create a large parameter value
        large_data = "x" * 200
        text = f"""
        ```tool_call
        {{"tool": "process", "parameters": {{"data": "{large_data}"}}}}
        ```
        """

        results = parser.parse_tool_calls(text)

        # Should reject oversized payload
        self.assertEqual(len(results), 0)

        stats = parser.get_stats()
        self.assertEqual(stats["rejected_size"], 1)
        self.assertEqual(stats["total_parsed"], 0)

    def test_max_tool_calls_limit(self):
        """Test that parser respects max tool calls limit"""
        parser = TextToolParser(max_tool_calls=3, log_errors=False)

        # Create text with many tool calls
        text = ""
        for i in range(10):
            text += f"""
            ```tool_call
            {{"tool": "tool_{i}", "parameters": {{"index": {i}}}}}
            ```
            """

        results = parser.parse_tool_calls(text)

        # Should only parse up to the limit
        self.assertEqual(len(results), 3)

        # Verify they are the first 3
        for i, result in enumerate(results):
            self.assertEqual(result["name"], f"tool_{i}")

    def test_no_allowed_tools_warning(self):
        """Test that parser works but logs when no allowed tools specified"""
        # This is dangerous in production but allowed for flexibility
        parser = TextToolParser(allowed_tools=None, log_errors=False)

        text = """
        ```tool_call
        {"tool": "any_tool", "parameters": {}}
        ```
        """

        results = parser.parse_tool_calls(text)

        # Should parse any tool when allowed_tools is None
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["name"], "any_tool")


class TestTextToolParserEdgeCases(unittest.TestCase):
    """Test edge cases and robustness"""

    def test_unicode_in_tool_names_and_params(self):
        """Test handling of Unicode characters"""
        parser = TextToolParser(log_errors=False)

        text = """
        ```tool_call
        {"tool": "读取文件", "parameters": {"路径": "文档.txt", "emoji": "🎉"}}
        ```
        """

        results = parser.parse_tool_calls(text)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["name"], "读取文件")
        self.assertEqual(results[0]["parameters"]["路径"], "文档.txt")
        self.assertEqual(results[0]["parameters"]["emoji"], "🎉")

    def test_mixed_json_and_xml_formats(self):
        """Test parsing both JSON and XML in same text"""
        parser = TextToolParser(log_errors=False)

        text = """
        First, let me read the file:

        ```tool_call
        {"tool": "read_file", "parameters": {"path": "input.txt"}}
        ```

        Then process it:

        <tool>process_data(input="input.txt", output="result.txt", mode="fast")</tool>

        Finally, save the results:

        ```tool_call
        {"tool": "save_results", "parameters": {"destination": "final.txt"}}
        ```
        """

        results = parser.parse_tool_calls(text)

        self.assertEqual(len(results), 3)

        # Get tool names
        tool_names = [r["name"] for r in results]
        self.assertIn("read_file", tool_names)
        self.assertIn("process_data", tool_names)
        self.assertIn("save_results", tool_names)

        # Check XML parsing worked correctly (find the process_data result)
        process_result = next(r for r in results if r["name"] == "process_data")
        self.assertEqual(process_result["parameters"]["mode"], "fast")

    def test_malformed_but_partially_valid_json(self):
        """Test handling of partially valid JSON"""
        parser = TextToolParser(log_errors=False)

        text = """
        ```tool_call
        {"tool": "valid_tool", "parameters": {"key": "value"}}
        ```

        ```tool_call
        {"tool": "broken_tool", "parameters": {"key": "value",}}
        ```

        ```tool_call
        {"tool": "another_valid", "parameters": {}}
        ```
        """

        results = parser.parse_tool_calls(text)

        # Should parse valid ones, skip malformed
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["name"], "valid_tool")
        self.assertEqual(results[1]["name"], "another_valid")

        stats = parser.get_stats()
        self.assertEqual(stats["parse_errors"], 1)

    def test_tool_call_with_complex_nested_json(self):
        """Test deeply nested and complex JSON structures"""
        parser = TextToolParser(log_errors=False)

        complex_params = {
            "config": {
                "database": {"host": "localhost", "port": 5432, "credentials": {"user": "admin", "password": "secret"}},
                "features": ["auth", "logging", "caching"],
                "metadata": {
                    "version": "1.0.0",
                    "tags": ["production", "critical"],
                    "settings": {"timeout": 30, "retries": 3, "backoff": [1, 2, 4, 8]},
                },
            }
        }

        text = f"""
        ```tool_call
        {{"tool": "complex_tool", "parameters": {json.dumps(complex_params)}}}
        ```
        """

        results = parser.parse_tool_calls(text)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["name"], "complex_tool")

        # Verify nested structure is preserved
        params = results[0]["parameters"]
        self.assertEqual(params["config"]["database"]["port"], 5432)
        self.assertEqual(params["config"]["features"], ["auth", "logging", "caching"])
        self.assertEqual(params["config"]["metadata"]["settings"]["backoff"], [1, 2, 4, 8])

    def test_xml_with_quoted_arguments(self):
        """Test XML parsing with various quote styles"""
        parser = TextToolParser(log_errors=False)

        text = """
        <tool>search(query="hello world", filter='type:article', count=10, enabled=true)</tool>
        <tool>process(data="contains, comma", path='has "quotes" inside')</tool>
        """

        results = parser.parse_tool_calls(text)

        self.assertEqual(len(results), 2)

        # First tool
        self.assertEqual(results[0]["name"], "search")
        self.assertEqual(results[0]["parameters"]["query"], "hello world")
        self.assertEqual(results[0]["parameters"]["filter"], "type:article")
        self.assertEqual(results[0]["parameters"]["count"], 10)
        self.assertEqual(results[0]["parameters"]["enabled"], True)

        # Second tool with special characters
        self.assertEqual(results[1]["name"], "process")
        self.assertEqual(results[1]["parameters"]["data"], "contains, comma")
        self.assertEqual(results[1]["parameters"]["path"], 'has "quotes" inside')

    def test_language_specifier_variations(self):
        """Test different language specifiers in code blocks"""
        parser = TextToolParser(log_errors=False)

        text = """
        ```tool_call
        {"tool": "tool1", "parameters": {}}
        ```

        ```tool_code
        {"tool": "tool2", "parameters": {}}
        ```

        ```json
        {"tool": "tool3", "parameters": {}}
        ```
        """

        results = parser.parse_tool_calls(text)

        # Should parse all variations
        self.assertEqual(len(results), 3)
        self.assertEqual(results[0]["name"], "tool1")
        self.assertEqual(results[1]["name"], "tool2")
        self.assertEqual(results[2]["name"], "tool3")

    def test_empty_and_null_parameters(self):
        """Test handling of empty, null, and missing parameters"""
        parser = TextToolParser(log_errors=False)

        text = """
        ```tool_call
        {"tool": "no_params"}
        ```

        ```tool_call
        {"tool": "empty_params", "parameters": {}}
        ```

        ```tool_call
        {"tool": "null_param", "parameters": {"value": null}}
        ```

        <tool>xml_no_params()</tool>
        """

        results = parser.parse_tool_calls(text)

        self.assertEqual(len(results), 4)

        # Missing parameters should default to empty dict
        self.assertEqual(results[0]["parameters"], {})

        # Empty parameters
        self.assertEqual(results[1]["parameters"], {})

        # Null value should be preserved
        self.assertEqual(results[2]["parameters"]["value"], None)

        # XML with no params
        self.assertEqual(results[3]["parameters"], {})


class TestStreamingToolParser(unittest.TestCase):
    """Test streaming parser functionality"""

    def test_basic_streaming(self):
        """Test parsing tool calls from streaming chunks"""
        parser = StreamingToolParser()

        # Simulate streaming response
        chunks = [
            "I'll help you with that. Let me first re",
            "ad the file:\n\n```tool_c",
            'all\n{"tool": "read_file", "par',
            'ameters": {"path": "test.txt"}}\n```',
            "\n\nNow let me process it.",
        ]

        all_results = []
        for chunk in chunks:
            results = parser.process_chunk(chunk)
            all_results.extend(results)

        # Should parse the complete tool call
        self.assertEqual(len(all_results), 1)
        self.assertEqual(all_results[0]["name"], "read_file")
        self.assertEqual(all_results[0]["parameters"]["path"], "test.txt")

    def test_multiple_tools_in_stream(self):
        """Test parsing multiple tool calls from stream"""
        parser = StreamingToolParser()

        chunks = [
            '```tool_call\n{"tool": "first", "parameters": {}}\n```\n',
            "Some text in between\n",
            '<tool>second(key="value")</tool>\n',
            'More text\n```tool_call\n{"tool": "thi',
            'rd", "parameters": {"test": true}}\n```',
        ]

        all_results = []
        for chunk in chunks:
            results = parser.process_chunk(chunk)
            all_results.extend(results)

        # Final flush to get any remaining
        final = parser.flush()
        all_results.extend(final)

        self.assertEqual(len(all_results), 3)
        self.assertEqual(all_results[0]["name"], "first")
        self.assertEqual(all_results[1]["name"], "second")
        self.assertEqual(all_results[2]["name"], "third")

    def test_buffer_overflow_protection(self):
        """Test that streaming parser prevents buffer overflow"""
        parser = StreamingToolParser(max_buffer_size=100)  # Small buffer

        # Create a large chunk that exceeds buffer
        large_chunk = "x" * 200

        with patch("logging.Logger.error") as mock_error:
            results = parser.process_chunk(large_chunk)

            # Should clear buffer and return empty
            self.assertEqual(len(results), 0)
            self.assertEqual(parser.buffer, "")

            # Should log error
            mock_error.assert_called_once()

    def test_incomplete_tool_at_stream_end(self):
        """Test handling incomplete tool call at stream end"""
        parser = StreamingToolParser()

        # Incomplete tool call
        chunks = [
            '```tool_call\n{"tool": "test", "param'
            # Stream ends abruptly
        ]

        for chunk in chunks:
            parser.process_chunk(chunk)

        # Flush should attempt to parse incomplete
        final = parser.flush()

        # Should not parse incomplete JSON
        self.assertEqual(len(final), 0)

    def test_no_duplicate_tool_calls(self):
        """Test that streaming parser avoids duplicates"""
        parser = StreamingToolParser()

        # First chunk contains complete tool
        chunk1 = '```tool_call\n{"tool": "test", "parameters": {}}\n```'
        results1 = parser.process_chunk(chunk1)

        self.assertEqual(len(results1), 1)

        # Second chunk with same content (shouldn't duplicate)
        chunk2 = "Some more text"
        results2 = parser.process_chunk(chunk2)

        self.assertEqual(len(results2), 0)

        # Verify no duplicates in completed list
        self.assertEqual(len(parser.completed_tool_calls), 1)


class TestToolInjector(unittest.TestCase):
    """Test backward compatibility with tool injection"""

    def test_tool_injection_into_messages(self):
        """Test injecting tools into user messages"""
        tools = [
            {
                "functionDeclarations": [
                    {
                        "name": "read_file",
                        "description": "Read a file from disk",
                        "parameters": {"properties": {"path": {"type": "string"}}},
                    },
                    {
                        "name": "write_file",
                        "description": "Write content to a file",
                        "parameters": {"properties": {"path": {"type": "string"}, "content": {"type": "string"}}},
                    },
                ]
            }
        ]

        injector = ToolInjector(tools)

        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Please read the config file."},
        ]

        modified = injector.inject_tools_into_messages(messages)

        # System message unchanged
        self.assertEqual(modified[0]["content"], "You are a helpful assistant.")

        # User message should have tools injected
        user_content = modified[1]["content"]
        self.assertIn("You have access to the following tools:", user_content)
        self.assertIn("read_file", user_content)
        self.assertIn("write_file", user_content)
        self.assertIn("```tool_call", user_content)
        self.assertIn("Please read the config file.", user_content)

    def test_no_injection_without_tools(self):
        """Test that messages are unchanged without tools"""
        injector = ToolInjector([])

        messages = [{"role": "user", "content": "Hello"}]

        modified = injector.inject_tools_into_messages(messages)

        self.assertEqual(modified, messages)


class TestParserStatistics(unittest.TestCase):
    """Test parser statistics and monitoring"""

    def test_statistics_tracking(self):
        """Test that parser tracks statistics correctly"""
        parser = TextToolParser(allowed_tools={"allowed_tool"}, max_json_size=100, log_errors=False)

        text = """
        ```tool_call
        {"tool": "allowed_tool", "parameters": {}}
        ```

        ```tool_call
        {"tool": "forbidden_tool", "parameters": {}}
        ```

        ```tool_call
        {invalid json}
        ```

        ```tool_call
        {"tool": "oversized", "parameters": {"data": "%s"}}
        ```
        """ % (
            "x" * 200
        )

        parser.parse_tool_calls(text)

        stats = parser.get_stats()
        self.assertEqual(stats["total_parsed"], 1)  # Only allowed_tool
        self.assertEqual(stats["rejected_unauthorized"], 1)  # forbidden_tool
        self.assertEqual(stats["parse_errors"], 1)  # invalid json
        self.assertEqual(stats["rejected_size"], 1)  # oversized

    def test_statistics_reset(self):
        """Test resetting statistics"""
        parser = TextToolParser(log_errors=False)

        # Parse some tools
        parser.parse_tool_calls('```tool_call\n{"tool": "test", "parameters": {}}\n```')

        stats = parser.get_stats()
        self.assertEqual(stats["total_parsed"], 1)

        # Reset
        parser.reset_stats()

        stats = parser.get_stats()
        self.assertEqual(stats["total_parsed"], 0)
        self.assertEqual(stats["rejected_unauthorized"], 0)
        self.assertEqual(stats["parse_errors"], 0)
        self.assertEqual(stats["rejected_size"], 0)


if __name__ == "__main__":
    # Configure logging for tests
    logging.basicConfig(level=logging.WARNING)
    unittest.main()
