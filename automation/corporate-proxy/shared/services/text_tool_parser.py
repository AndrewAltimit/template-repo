#!/usr/bin/env python3
"""
Enhanced text-based tool parsing with security hardening and performance improvements
Consolidated version based on Gemini's security review and recommendations
"""

import json
import logging
import re
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class TextToolParser:
    """
    Production-ready parser for extracting tool calls from AI-generated text.

    Features:
    - Security: Tool allowlist and size limits
    - Performance: Compiled regex patterns
    - Robustness: Better error handling and logging
    - Flexibility: Supports JSON and XML formats
    - Backward compatibility: Supports legacy methods
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
        tool_executor: Optional[Callable] = None,  # For backward compatibility
    ):
        """
        Initialize the parser with security constraints.

        Args:
            allowed_tools: Set of permitted tool names. None allows all (not recommended).
            max_json_size: Maximum size for a single JSON payload (bytes).
            max_tool_calls: Maximum number of tool calls to parse from a single response.
            log_errors: Whether to log parsing errors.
            tool_executor: Optional function to execute tools (for backward compatibility).
        """
        self.allowed_tools = allowed_tools
        self.max_json_size = max_json_size
        self.max_tool_calls = max_tool_calls
        self.log_errors = log_errors
        self.tool_executor = tool_executor

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

    # ========== Backward Compatibility Methods ==========

    def execute_tool_calls(self, tool_calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Execute a list of tool calls (backward compatibility)."""
        if not self.tool_executor:
            raise ValueError("No tool executor configured")

        results = []
        for tool_call in tool_calls:
            try:
                result = self.tool_executor(tool_call["name"], tool_call["parameters"])
                results.append({"tool": tool_call["name"], "parameters": tool_call["parameters"], "result": result})
            except Exception as e:
                results.append(
                    {"tool": tool_call["name"], "parameters": tool_call["parameters"], "result": {"success": False, "error": str(e)}}
                )

        return results

    def format_tool_results(self, results: List[Dict[str, Any]]) -> str:
        """Format tool execution results for AI continuation."""
        if not results:
            return ""

        formatted_parts = []
        for result in results:
            tool_name = result.get("tool", "unknown")
            tool_result = result.get("result", {})

            if tool_result.get("success", False):
                formatted_parts.append(f"Tool Result: {tool_name}")
                # Format the output nicely
                if "content" in tool_result:
                    formatted_parts.append(tool_result["content"])
                elif "data" in tool_result:
                    formatted_parts.append(json.dumps(tool_result["data"], indent=2))
                else:
                    formatted_parts.append(json.dumps(tool_result, indent=2))
            else:
                formatted_parts.append(f"Tool Error: {tool_name}")
                formatted_parts.append(tool_result.get("error", "Unknown error"))

            formatted_parts.append("")  # Empty line between results

        return "\n".join(formatted_parts)

    def is_complete_response(self, text: str) -> bool:
        """Check if the response indicates task completion."""
        completion_indicators = [
            "task is complete",
            "completed successfully",
            "finished",
            "done",
            "task complete",
            "completed the task",
            "all done",
            "complete.",
        ]

        text_lower = text.lower()
        return any(indicator in text_lower for indicator in completion_indicators)

    def process_response_with_tools(self, response: str, executor: Optional[Callable] = None):
        """Process a response that may contain tool calls."""
        if executor:
            self.tool_executor = executor

        tool_calls = self.parse_tool_calls(response)

        if not tool_calls:
            return "", [], False

        results = self.execute_tool_calls(tool_calls)
        formatted = self.format_tool_results(results)

        # Check if response indicates completion
        is_complete = self.is_complete_response(response)

        return formatted, results, not is_complete

    def generate_tool_prompt(self, tools: Dict[str, Any], user_query: str) -> str:
        """Generate a prompt with tool instructions (backward compatibility)."""
        prompt_parts = ["You have access to the following tools:", ""]

        for tool_name, tool_def in tools.items():
            prompt_parts.append(f"- {tool_name}: {tool_def.get('description', 'No description')}")
            if "parameters" in tool_def:
                params = tool_def["parameters"].get("properties", {})
                if params:
                    param_list = ", ".join(params.keys())
                    prompt_parts.append(f"  Parameters: {param_list}")

        prompt_parts.extend(
            [
                "",
                "To use a tool, include a code block in your response like this:",
                "```tool_call",
                "{",
                '  "tool": "tool_name",',
                '  "parameters": {',
                '    "param1": "value1"',
                "  }",
                "}",
                "```",
                "",
                "User Query:",
                user_query,
            ]
        )

        return "\n".join(prompt_parts)


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


class ToolInjector:
    """
    Inject tool definitions into prompts for text-mode processing.
    """

    def __init__(self, tools: List[Dict[str, Any]]):
        """
        Initialize with tool definitions.

        Args:
            tools: List of tool definitions or dictionary of tools.
        """
        # Handle both list and dict formats
        if isinstance(tools, dict):
            # Convert dict to list format
            self.tools = [
                {"functionDeclarations": [{"name": k, "description": v.get("description", ""), "parameters": v.get("parameters", {})} for k, v in tools.items()]}
            ]
        else:
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

        # Make a copy to avoid modifying the original
        messages = [msg.copy() for msg in messages]

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

    def inject_system_prompt(self, original_prompt: str) -> str:
        """
        Enhance system prompt with tool-use instructions.

        Args:
            original_prompt: The original system prompt.

        Returns:
            Enhanced system prompt with tool instructions.
        """
        tool_instruction = (
            "You are equipped with tools that you should use when appropriate. "
            "When you need to use a tool, output a tool_call code block with the tool name and parameters. "
            "Wait for the tool result before continuing. "
            "Use the tool calling format shown in the user message."
        )

        return f"{original_prompt}\n\n{tool_instruction}"

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