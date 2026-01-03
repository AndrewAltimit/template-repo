#!/usr/bin/env python3
"""
Tests for API Spec Converter - OpenAI/Anthropic tool format conversion.
"""

import json
from pathlib import Path
import sys

import pytest

# Add shared services to path
sys.path.insert(0, str(Path(__file__).parent.parent / "shared" / "services"))

from api_spec_converter import APISpecConverter


class TestAPISpecDetection:
    """Tests for API spec auto-detection."""

    def setup_method(self):
        """Set up converter for each test."""
        self.converter = APISpecConverter(default_spec="openai", auto_detect=True)

    def test_detect_openai_by_tool_role(self):
        """Test detection of OpenAI format by tool role messages."""
        request = {
            "model": "gpt-4",
            "messages": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi", "tool_calls": []},
                {"role": "tool", "tool_call_id": "call_123", "content": "result"},
            ],
        }
        assert self.converter.detect_spec(request) == "openai"

    def test_detect_openai_by_tool_calls(self):
        """Test detection of OpenAI format by tool_calls in messages."""
        request = {
            "model": "gpt-4",
            "messages": [
                {"role": "user", "content": "Read file"},
                {
                    "role": "assistant",
                    "tool_calls": [{"id": "call_123", "type": "function", "function": {"name": "read", "arguments": "{}"}}],
                },
            ],
        }
        assert self.converter.detect_spec(request) == "openai"

    def test_detect_anthropic_by_version(self):
        """Test detection of Anthropic format by anthropic_version field."""
        request = {"anthropic_version": "bedrock-2023-05-31", "model": "claude-3", "messages": []}
        assert self.converter.detect_spec(request) == "anthropic"

    def test_detect_anthropic_by_system_string(self):
        """Test detection of Anthropic format by system as string."""
        request = {"system": "You are a helpful assistant", "messages": [{"role": "user", "content": "Hello"}]}
        assert self.converter.detect_spec(request) == "anthropic"

    def test_detect_anthropic_by_tool_result(self):
        """Test detection of Anthropic format by tool_result content blocks."""
        request = {
            "messages": [
                {
                    "role": "user",
                    "content": [{"type": "tool_result", "tool_use_id": "toolu_123", "content": "result"}],
                }
            ]
        }
        assert self.converter.detect_spec(request) == "anthropic"

    def test_default_spec_when_no_indicators(self):
        """Test that default spec is returned when no indicators found."""
        request = {"model": "test", "messages": [{"role": "user", "content": "Hello"}]}
        assert self.converter.detect_spec(request) == "openai"

    def test_auto_detect_disabled(self):
        """Test that auto-detect returns default when disabled."""
        converter = APISpecConverter(default_spec="anthropic", auto_detect=False)
        request = {"messages": [{"role": "tool", "content": "result"}]}
        assert converter.detect_spec(request) == "anthropic"


class TestToolDefinitionConversion:
    """Tests for tool definition conversion between formats."""

    def setup_method(self):
        """Set up converter for each test."""
        self.converter = APISpecConverter()

    def test_convert_openai_tools_to_anthropic(self):
        """Test converting OpenAI tool format to Anthropic format."""
        openai_tools = [
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Read a file",
                    "parameters": {"type": "object", "properties": {"path": {"type": "string"}}},
                },
            }
        ]
        anthropic_tools = self.converter.convert_tools_to_anthropic(openai_tools)

        assert len(anthropic_tools) == 1
        assert anthropic_tools[0]["name"] == "read_file"
        assert anthropic_tools[0]["description"] == "Read a file"
        assert "input_schema" in anthropic_tools[0]
        assert anthropic_tools[0]["input_schema"]["properties"]["path"]["type"] == "string"

    def test_convert_anthropic_tools_to_openai(self):
        """Test converting Anthropic tool format to OpenAI format."""
        anthropic_tools = [
            {
                "name": "write_file",
                "description": "Write to a file",
                "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}},
            }
        ]
        openai_tools = self.converter.convert_tools_to_openai(anthropic_tools)

        assert len(openai_tools) == 1
        assert openai_tools[0]["type"] == "function"
        assert openai_tools[0]["function"]["name"] == "write_file"
        assert openai_tools[0]["function"]["description"] == "Write to a file"
        assert "parameters" in openai_tools[0]["function"]

    def test_idempotent_openai_conversion(self):
        """Test that converting OpenAI tools to OpenAI is idempotent."""
        openai_tools = [{"type": "function", "function": {"name": "test", "description": "Test"}}]
        converted = self.converter.convert_tools_to_openai(openai_tools)
        assert converted[0]["type"] == "function"
        assert converted[0]["function"]["name"] == "test"


class TestToolCallConversion:
    """Tests for tool call conversion between formats."""

    def setup_method(self):
        """Set up converter for each test."""
        self.converter = APISpecConverter()

    def test_convert_openai_tool_calls_to_anthropic(self):
        """Test converting OpenAI tool calls to Anthropic format."""
        openai_calls = [
            {"id": "call_abc", "type": "function", "function": {"name": "read", "arguments": '{"path": "test.py"}'}}
        ]
        anthropic_calls = self.converter.convert_tool_calls_to_anthropic(openai_calls)

        assert len(anthropic_calls) == 1
        assert anthropic_calls[0]["type"] == "tool_use"
        assert anthropic_calls[0]["id"] == "call_abc"
        assert anthropic_calls[0]["name"] == "read"
        assert anthropic_calls[0]["input"] == {"path": "test.py"}

    def test_convert_anthropic_tool_calls_to_openai(self):
        """Test converting Anthropic tool calls to OpenAI format."""
        anthropic_calls = [{"type": "tool_use", "id": "toolu_xyz", "name": "write", "input": {"content": "hello"}}]
        openai_calls = self.converter.convert_tool_calls_to_openai(anthropic_calls)

        assert len(openai_calls) == 1
        assert openai_calls[0]["type"] == "function"
        assert openai_calls[0]["id"] == "toolu_xyz"
        assert openai_calls[0]["function"]["name"] == "write"
        assert json.loads(openai_calls[0]["function"]["arguments"]) == {"content": "hello"}

    def test_streaming_adds_index(self):
        """Test that streaming mode adds index to tool calls."""
        calls = [{"name": "test", "parameters": {}}]
        openai_calls = self.converter.convert_tool_calls_to_openai(calls, streaming=True)
        assert "index" in openai_calls[0]
        assert openai_calls[0]["index"] == 0


class TestMessageConversion:
    """Tests for message conversion between formats."""

    def setup_method(self):
        """Set up converter for each test."""
        self.converter = APISpecConverter()

    def test_convert_openai_messages_to_anthropic(self):
        """Test converting OpenAI messages to Anthropic format."""
        openai_messages = [
            {"role": "system", "content": "You are helpful"},
            {"role": "user", "content": "Hello"},
            {
                "role": "assistant",
                "content": "Hi",
                "tool_calls": [{"id": "call_1", "type": "function", "function": {"name": "read", "arguments": "{}"}}],
            },
            {"role": "tool", "tool_call_id": "call_1", "content": "file content"},
        ]

        system, anthropic_messages = self.converter.convert_messages_to_anthropic(openai_messages)

        assert system == "You are helpful"
        assert len(anthropic_messages) >= 2
        # User message should be converted
        assert any(m["role"] == "user" for m in anthropic_messages)
        # Tool results should be in user message
        assert any(
            m["role"] == "user" and any(b.get("type") == "tool_result" for b in m.get("content", []))
            for m in anthropic_messages
        )

    def test_convert_anthropic_messages_to_openai(self):
        """Test converting Anthropic messages to OpenAI format."""
        anthropic_messages = [
            {"role": "user", "content": [{"type": "text", "text": "Hello"}]},
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "Hi"},
                    {"type": "tool_use", "id": "toolu_1", "name": "read", "input": {}},
                ],
            },
            {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "toolu_1", "content": "result"}]},
        ]

        openai_messages = self.converter.convert_messages_to_openai(anthropic_messages)

        assert len(openai_messages) >= 2
        # Tool results should become tool role messages
        assert any(m["role"] == "tool" for m in openai_messages)


class TestResponseConversion:
    """Tests for full response conversion between formats."""

    def setup_method(self):
        """Set up converter for each test."""
        self.converter = APISpecConverter()

    def test_convert_openai_response_to_anthropic(self):
        """Test converting OpenAI response to Anthropic format."""
        openai_response = {
            "id": "chatcmpl-123",
            "object": "chat.completion",
            "created": 1234567890,
            "model": "gpt-4",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "Hello",
                        "tool_calls": [
                            {"id": "call_1", "type": "function", "function": {"name": "read", "arguments": '{"path": "test"}'}}
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        }

        anthropic_response = self.converter.convert_response_to_anthropic(openai_response)

        assert anthropic_response["type"] == "message"
        assert anthropic_response["role"] == "assistant"
        assert anthropic_response["stop_reason"] == "tool_use"
        assert any(b["type"] == "tool_use" for b in anthropic_response["content"])

    def test_convert_anthropic_response_to_openai(self):
        """Test converting Anthropic response to OpenAI format."""
        anthropic_response = {
            "id": "msg_123",
            "type": "message",
            "role": "assistant",
            "model": "claude-3",
            "content": [{"type": "text", "text": "Hello"}, {"type": "tool_use", "id": "toolu_1", "name": "read", "input": {}}],
            "stop_reason": "tool_use",
            "usage": {"input_tokens": 10, "output_tokens": 20},
        }

        openai_response = self.converter.convert_response_to_openai(anthropic_response)

        assert openai_response["object"] == "chat.completion"
        assert openai_response["choices"][0]["finish_reason"] == "tool_calls"
        assert "tool_calls" in openai_response["choices"][0]["message"]


class TestToolCallIdGeneration:
    """Tests for tool call ID generation."""

    def setup_method(self):
        """Set up converter for each test."""
        self.converter = APISpecConverter()

    def test_generate_unique_ids(self):
        """Test that generated IDs are unique."""
        ids = {self.converter.generate_tool_call_id() for _ in range(100)}
        assert len(ids) == 100

    def test_id_prefix(self):
        """Test that IDs use the correct prefix."""
        openai_id = self.converter.generate_tool_call_id("call")
        anthropic_id = self.converter.generate_tool_call_id("toolu")

        assert openai_id.startswith("call_")
        assert anthropic_id.startswith("toolu_")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
