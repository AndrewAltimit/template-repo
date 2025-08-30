#!/usr/bin/env python3
"""
Enhanced text-based tool parsing with security hardening and performance improvements
Based on Gemini's security review and recommendations
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class TextToolParser:
    """
    Production-ready parser for extracting tool calls from AI-generated text.

    Features:
    - Security: Tool allowlist and size limits
    - Performance: Compiled regex patterns
    - Robustness: Better error handling and logging
    - Flexibility: Supports JSON and XML formats
    """

    # Compile regex patterns once for efficiency
    # Supports tool_call, tool_code, and json language specifiers
    JSON_TOOL_CALL_PATTERN = re.compile(r"```(?:tool_call|tool_code|json)\s*\n(.*?)\n\s*```", re.DOTALL)

    # XML format: <tool>function_name(key=value, ...)</tool>
    XML_TOOL_CALL_PATTERN = re.compile(r"<tool>(.*?)\((.*?)\)</tool>", re.DOTALL)

    # Pattern for parsing XML-style arguments
    XML_ARG_PATTERN = re.compile(r'(\w+)\s*=\s*("(?:\\"|[^"])*"|\'(?:\\\'|[^\'])*\'|[^,]+)')

    def __init__(
        self,
        allowed_tools: Optional[Set[str]] = None,
        max_json_size: int = 1 * 1024 * 1024,  # 1MB default limit
        max_tool_calls: int = 20,  # Prevent excessive tool calls
        log_errors: bool = True,
    ):
        """
        Initialize the parser with security constraints.

        Args:
            allowed_tools: Set of permitted tool names. None allows all (not recommended).
            max_json_size: Maximum size for a single JSON payload (bytes).
            max_tool_calls: Maximum number of tool calls to parse from a single response.
            log_errors: Whether to log parsing errors.
        """
        self.allowed_tools = allowed_tools
        self.max_json_size = max_json_size
        self.max_tool_calls = max_tool_calls
        self.log_errors = log_errors

        # Statistics for monitoring
        self.stats = {"total_parsed": 0, "rejected_size": 0, "rejected_unauthorized": 0, "parse_errors": 0}

    def _parse_xml_args(self, args_str: str) -> Dict[str, Any]:
        """
        Parse XML-style function arguments.

        Handles formats like:
        - path="file.txt", mode="r"
        - count=5, enabled=true
        - name='test', data=[1,2,3]
        """
        params = {}

        for match in self.XML_ARG_PATTERN.finditer(args_str):
            key = match.group(1).strip()
            value_str = match.group(2).strip()

            try:
                # Try to parse as JSON for proper type conversion
                # This handles numbers, bools, arrays, and quoted strings
                params[key] = json.loads(value_str)
            except json.JSONDecodeError:
                # Fallback for unquoted strings
                params[key] = value_str.strip("\"'")

        return params

    def _validate_tool_name(self, tool_name: str) -> bool:
        """
        Validate that a tool name is allowed.

        Args:
            tool_name: The tool name to validate.

        Returns:
            True if the tool is allowed, False otherwise.
        """
        if self.allowed_tools is None:
            return True

        is_allowed = tool_name in self.allowed_tools
        if not is_allowed:
            self.stats["rejected_unauthorized"] += 1
            if self.log_errors:
                logger.warning(
                    f"Rejected unauthorized tool call: '{tool_name}' " f"(allowed: {', '.join(sorted(self.allowed_tools))})"
                )

        return is_allowed

    def _validate_json_size(self, json_content: str) -> bool:
        """
        Check if JSON content is within size limits.

        Args:
            json_content: The JSON string to check.

        Returns:
            True if within limits, False otherwise.
        """
        size = len(json_content.encode("utf-8"))
        if size > self.max_json_size:
            self.stats["rejected_size"] += 1
            if self.log_errors:
                logger.warning(f"Rejected oversized JSON payload: {size} bytes " f"(max: {self.max_json_size})")
            return False
        return True

    def parse_tool_calls(self, text: str) -> List[Dict[str, Any]]:
        """
        Parse tool calls from AI-generated text.

        Args:
            text: The text containing potential tool calls.

        Returns:
            List of parsed tool call dictionaries with keys:
            - name: Tool name
            - parameters: Tool parameters
            - id: Unique identifier for the call
        """
        if not text:
            return []

        tool_calls = []

        # Parse JSON format tool calls
        for match in self.JSON_TOOL_CALL_PATTERN.finditer(text):
            if len(tool_calls) >= self.max_tool_calls:
                if self.log_errors:
                    logger.warning(f"Reached max tool calls limit ({self.max_tool_calls})")
                break

            json_content = match.group(1).strip()

            # Security: Check size before parsing
            if not self._validate_json_size(json_content):
                continue

            try:
                tool_data = json.loads(json_content)
                tool_name = tool_data.get("tool")

                if not tool_name:
                    self.stats["parse_errors"] += 1
                    if self.log_errors:
                        logger.warning("Tool call missing 'tool' key in JSON")
                    continue

                # Security: Validate tool name
                if not self._validate_tool_name(tool_name):
                    continue

                tool_calls.append(
                    {
                        "name": tool_name,
                        "parameters": tool_data.get("parameters", {}),
                        "id": tool_data.get("id", f"call_{len(tool_calls)}"),
                    }
                )
                self.stats["total_parsed"] += 1

            except json.JSONDecodeError as e:
                self.stats["parse_errors"] += 1
                if self.log_errors:
                    logger.warning(f"Failed to parse JSON tool call: {e}\n" f"Content preview: {json_content[:100]}...")
                continue

        # Parse XML format tool calls
        for match in self.XML_TOOL_CALL_PATTERN.finditer(text):
            if len(tool_calls) >= self.max_tool_calls:
                break

            func_name, args_str = match.groups()
            tool_name = func_name.strip()

            # Security: Validate tool name
            if not self._validate_tool_name(tool_name):
                continue

            try:
                parameters = self._parse_xml_args(args_str)
                tool_calls.append({"name": tool_name, "parameters": parameters, "id": f"call_{len(tool_calls)}"})
                self.stats["total_parsed"] += 1

            except Exception as e:
                self.stats["parse_errors"] += 1
                if self.log_errors:
                    logger.warning(f"Failed to parse XML tool call: {e}\n" f"Tool: {tool_name}, Args: {args_str[:100]}...")
                continue

        return tool_calls

    def get_stats(self) -> Dict[str, int]:
        """Get parsing statistics for monitoring."""
        return self.stats.copy()

    def reset_stats(self):
        """Reset parsing statistics."""
        self.stats = {"total_parsed": 0, "rejected_size": 0, "rejected_unauthorized": 0, "parse_errors": 0}


class StreamingToolParser:
    """
    Stateful parser for handling streaming AI responses.

    Buffers incomplete tool calls and parses them when complete.
    """

    def __init__(
        self,
        allowed_tools: Optional[Set[str]] = None,
        max_json_size: int = 1 * 1024 * 1024,
        max_buffer_size: int = 10 * 1024 * 1024,  # 10MB buffer limit
    ):
        """
        Initialize the streaming parser.

        Args:
            allowed_tools: Set of permitted tool names.
            max_json_size: Maximum size for a single JSON payload.
            max_buffer_size: Maximum size for the internal buffer.
        """
        self.parser = TextToolParser(allowed_tools=allowed_tools, max_json_size=max_json_size)
        self.buffer = ""
        self.max_buffer_size = max_buffer_size
        self.completed_tool_calls = []

    def process_chunk(self, chunk: str) -> List[Dict[str, Any]]:
        """
        Process a streaming chunk and extract any complete tool calls.

        Args:
            chunk: New text chunk from the stream.

        Returns:
            List of newly completed tool calls.
        """
        self.buffer += chunk

        # Security: Prevent buffer overflow
        if len(self.buffer) > self.max_buffer_size:
            logger.error(f"Buffer overflow, clearing buffer (size: {len(self.buffer)})")
            self.buffer = ""
            return []

        new_tool_calls = []

        # Look for complete JSON blocks
        json_pattern = r"```(?:tool_call|tool_code|json)\s*\n.*?\n\s*```"
        json_matches = list(re.finditer(json_pattern, self.buffer, re.DOTALL))

        # Look for complete XML blocks
        xml_pattern = r"<tool>.*?</tool>"
        xml_matches = list(re.finditer(xml_pattern, self.buffer, re.DOTALL))

        # Process and remove complete blocks from buffer
        all_matches = sorted(json_matches + xml_matches, key=lambda m: m.start())

        offset = 0
        for match in all_matches:
            # Parse the complete block
            block_text = match.group()
            parsed = self.parser.parse_tool_calls(block_text)

            for tool_call in parsed:
                # Avoid duplicates
                if tool_call not in self.completed_tool_calls:
                    new_tool_calls.append(tool_call)
                    self.completed_tool_calls.append(tool_call)

            # Mark this section for removal from buffer
            offset = match.end()

        # Remove processed content from buffer
        if offset > 0:
            self.buffer = self.buffer[offset:]

        return new_tool_calls

    def flush(self) -> List[Dict[str, Any]]:
        """
        Process any remaining buffer content at stream end.

        Returns:
            Any tool calls found in the remaining buffer.
        """
        if not self.buffer:
            return []

        # Try to parse whatever is left
        remaining_calls = self.parser.parse_tool_calls(self.buffer)
        self.buffer = ""

        # Filter out duplicates
        new_calls = []
        for call in remaining_calls:
            if call not in self.completed_tool_calls:
                new_calls.append(call)
                self.completed_tool_calls.append(call)

        return new_calls

    def reset(self):
        """Reset the parser state for a new stream."""
        self.buffer = ""
        self.completed_tool_calls = []
        self.parser.reset_stats()


# Backward compatibility with original implementation
class ToolInjector:
    """
    Inject tool definitions into prompts for text-mode processing.

    This class is maintained for backward compatibility.
    """

    def __init__(self, tools: List[Dict[str, Any]]):
        """
        Initialize with tool definitions.

        Args:
            tools: List of tool definitions.
        """
        self.tools = tools

    def inject_tools_into_messages(self, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        Inject tool instructions into the user message.

        Args:
            messages: List of message dictionaries.

        Returns:
            Modified messages with tool instructions.
        """
        if not self.tools or not messages:
            return messages

        # Find the last user message to inject tools
        for i in range(len(messages) - 1, -1, -1):
            if messages[i].get("role") == "user":
                original_content = messages[i]["content"]

                # Create tool instructions
                tool_instructions = self._create_tool_instructions()

                # Inject at the beginning of the user message
                messages[i]["content"] = f"{tool_instructions}\n\n{original_content}"
                break

        return messages

    def _create_tool_instructions(self) -> str:
        """Create formatted tool instructions."""
        instructions = ["You have access to the following tools:", ""]

        # Add tool definitions
        for tool in self.tools:
            if isinstance(tool, dict) and "functionDeclarations" in tool:
                # Gemini format
                for func in tool["functionDeclarations"]:
                    instructions.append(f"- {func['name']}: {func.get('description', 'No description')}")
                    if "parameters" in func and "properties" in func["parameters"]:
                        instructions.append(f"  Parameters: {', '.join(func['parameters']['properties'].keys())}")
            else:
                # Simple format
                instructions.append(f"- {tool.get('name', 'unknown')}: {tool.get('description', 'No description')}")

        instructions.extend(
            [
                "",
                "To use a tool, respond with a code block like this:",
                "```tool_call",
                "{",
                '  "tool": "tool_name",',
                '  "parameters": {',
                '    "param1": "value1",',
                '    "param2": "value2"',
                "  }",
                "}",
                "```",
                "",
            ]
        )

        return "\n".join(instructions)
