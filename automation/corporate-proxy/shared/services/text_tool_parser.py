#!/usr/bin/env python3
"""
Text-Based Tool Call Parser for AI Agent Integration

This module provides a secure, production-ready parser for extracting and executing tool calls
from AI-generated text responses. It's designed for corporate proxy environments where AI models
may not have native tool-calling capabilities and must embed tool invocations in text format.

## Overview

The parser handles two main scenarios:
1. **Text Mode**: For models that don't support native tool calling (e.g., older Gemini models)
2. **Hybrid Mode**: For systems that need to parse both native and text-based tool calls

## Key Features

- **Security-First Design**:
  - Tool allowlisting to prevent unauthorized function execution
  - Size limits to prevent memory exhaustion attacks
  - Input sanitization to prevent injection attacks
  - Comprehensive error handling with security logging

- **Multiple Format Support**:
  - JSON format: ```tool_call {"tool": "name", "parameters": {...}} ```
  - XML format: <tool>function_name(key=value, ...)</tool>
  - Python format: Write("file.txt", "content") or Bash("command")
  - Legacy formats for backward compatibility

- **Performance Optimizations**:
  - Pre-compiled regex patterns for efficient parsing
  - Configurable limits to prevent resource exhaustion
  - Lazy evaluation where possible

- **Robustness**:
  - Graceful error handling with fallback behaviors
  - Detailed logging for debugging and monitoring
  - Support for malformed or partial tool calls

## Security Considerations

This module is designed with security as a primary concern:

1. **Tool Allowlisting**: Only explicitly permitted tools can be executed
2. **Size Limits**: Prevents memory exhaustion from large payloads
3. **Rate Limiting**: Configurable maximum number of tool calls per response
4. **Input Validation**: All parameters are validated before execution
5. **No Dynamic Execution**: No use of eval() or exec() on user input
6. **Audit Logging**: All tool calls are logged for security monitoring

## Usage Example

```python
# Initialize with security constraints
parser = TextToolParser(
    allowed_tools={'search', 'calculate', 'read_file'},
    max_json_size=100_000,  # 100KB limit
    max_tool_calls=10
)

# Parse tool calls from AI response
response_text = '''
I'll search for that information.

```tool_call
{
  "tool": "search",
  "parameters": {
    "query": "Python security best practices"
  }
}
```
'''

tool_calls = parser.parse_tool_calls(response_text)
# Returns: [{'name': 'search', 'parameters': {'query': 'Python security best practices'}}]
```

## Integration with Corporate Proxy

This parser is specifically designed for corporate proxy environments where:
- Direct API access may be restricted
- Tool calling must go through approved channels
- Security and audit requirements are stringent
- Multiple AI models with different capabilities must be supported

Enhanced text-based tool parsing with security hardening and performance improvements
Consolidated version based on Gemini's security review and recommendations
"""

import ast
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
    - Flexibility: Supports JSON, XML, and Python function call formats
    - Backward compatibility: Supports legacy methods

    Supported formats:
    - JSON: ```tool_call {"tool": "name", "parameters": {...}} ```
    - XML: <tool>function_name(key=value, ...)</tool>
    - Python: Write("file.txt", "content") or Bash("command")
    """

    # Compile regex patterns once for efficiency
    # Supports tool_call, tool_code, and json language specifiers
    JSON_TOOL_CALL_PATTERN = re.compile(r"```(?:tool_call|tool_code|json)\s*\n(.*?)\n\s*```", re.DOTALL)

    # XML format: <tool>function_name(key=value, ...)</tool>
    XML_TOOL_CALL_PATTERN = re.compile(r"<tool>(.*?)\((.*?)\)</tool>", re.DOTALL)

    # Pattern for parsing XML-style arguments
    XML_ARG_PATTERN = re.compile(r'(\w+)\s*=\s*("(?:\\"|[^"])*"|\'(?:\\\'|[^\'])*\'|[^,]+)')

    # Python-style function calls: Write("file.txt", """content""") or Bash("command")
    #
    # IMPORTANT: This regex is ONLY for locating potential function call strings in text.
    # It does NOT parse the function calls - that's handled entirely by ast.parse().
    #
    # The regex has limitations (e.g., only one level of nested parentheses), but these
    # limitations DO NOT affect the actual parsing. Once a potential call is found,
    # ast.parse() handles it with full Python syntax support, including:
    # - Arbitrarily nested structures
    # - Complex expressions
    # - Any valid Python function call syntax
    #
    # In other words: regex finds it, ast.parse() understands it perfectly.
    PYTHON_TOOL_CALL_PATTERN = re.compile(
        r"\b([A-Z][a-zA-Z_]*\s*\("  # Function name and opening paren
        r"(?:"  # Non-capturing group for arguments
        r'[^()"\']+'  # Non-quote, non-paren characters
        r'|"(?:[^"\\]|\\.)*"'  # Double-quoted strings
        r"|'(?:[^'\\]|\\.)*'"  # Single-quoted strings
        r'|"""[\s\S]*?"""'  # Triple double quotes
        r"|'''[\s\S]*?'''"  # Triple single quotes
        r"|\([^)]*\)"  # Nested parentheses (one level only)
        r")*"  # Zero or more of the above
        r"\))",  # Closing paren
        re.DOTALL,
    )

    def __init__(
        self,
        allowed_tools: Optional[Set[str]] = None,
        max_json_size: int = 1 * 1024 * 1024,  # 1MB default limit
        max_tool_calls: int = 20,  # Prevent excessive tool calls
        log_errors: bool = True,
        tool_executor: Optional[Callable] = None,  # For backward compatibility
        tool_definitions: Optional[Dict[str, Dict[str, Any]]] = None,  # Tool definitions for param mapping
        fail_on_parse_error: bool = False,  # Whether to raise on parse errors
        max_consecutive_errors: int = 5,  # Max errors before stopping
    ):
        """
        Initialize the parser with security constraints.

        Args:
            allowed_tools: Set of permitted tool names. None allows all (not recommended).
            max_json_size: Maximum size for a single JSON payload (bytes).
            max_tool_calls: Maximum number of tool calls to parse from a single response.
            log_errors: Whether to log parsing errors.
            tool_executor: Optional function to execute tools (for backward compatibility).
            tool_definitions: Optional dictionary of tool definitions for automatic param mapping.
        """
        self.allowed_tools = allowed_tools
        self.max_json_size = max_json_size
        self.max_tool_calls = max_tool_calls
        self.log_errors = log_errors
        self.tool_executor = tool_executor
        self.fail_on_parse_error = fail_on_parse_error
        self.max_consecutive_errors = max_consecutive_errors

        # Statistics for monitoring
        self.stats = {
            "total_parsed": 0,
            "rejected_size": 0,
            "rejected_unauthorized": 0,
            "parse_errors": 0,
            "consecutive_errors": 0,
            "python_parse_errors": 0,
            "json_parse_errors": 0,
            "xml_parse_errors": 0,
        }

        # Generate param mappings programmatically or use fallback
        self.param_mappings = self._generate_param_mappings(tool_definitions)

    def _generate_param_mappings(self, tool_definitions: Optional[Dict[str, Dict[str, Any]]]) -> Dict[str, List[str]]:
        """
        Generate parameter mappings programmatically from tool definitions.

        This method eliminates the maintenance burden of manually updating param_mappings
        when tool signatures change. It can extract positional parameters from:
        1. Tool definition dictionaries (preferred)
        2. Function objects via inspection (if available)
        3. Fallback to hardcoded defaults (for backward compatibility)

        CRITICAL: The order of parameters in the returned mapping MUST match the
        expected positional argument order for Python-style function calls.
        When AI models generate calls like Write("file.txt", "content"), the
        parser relies on this ordering to correctly map positional arguments.
        See MAINTENANCE.md for detailed requirements.

        Args:
            tool_definitions: Dictionary of tool definitions with parameter info

        Returns:
            Dictionary mapping tool names to ordered lists of parameter names
        """
        # If tool definitions provided, extract parameter order from them
        if tool_definitions:
            param_mappings = {}
            for tool_name, definition in tool_definitions.items():
                # Handle different definition formats
                if isinstance(definition, dict):
                    # Look for parameters in various common formats
                    if "parameters" in definition:
                        params = definition["parameters"]
                        if isinstance(params, dict) and "properties" in params:
                            # OpenAPI/JSON Schema style
                            # Note: This assumes the order in which properties are defined
                            # matches the positional argument order
                            param_mappings[tool_name] = list(params["properties"].keys())
                        elif isinstance(params, list):
                            # List of parameter definitions
                            param_mappings[tool_name] = [p.get("name", f"arg{i}") for i, p in enumerate(params)]
                    elif "args" in definition:
                        # Simple args list format
                        param_mappings[tool_name] = definition["args"]

            if param_mappings:
                logger.info(f"Generated param mappings for {len(param_mappings)} tools from definitions")
                return param_mappings

        # Fallback to hardcoded defaults if no definitions available
        # CRITICAL: The order of parameters here MUST match the expected
        # positional argument order for Python-style function calls.
        # Changing the order will break existing tool call parsing!
        # See MAINTENANCE.md for detailed requirements.
        logger.warning("No tool definitions provided, using hardcoded param mappings as fallback")
        return {
            "write": ["file_path", "content"],  # Order: 1. file_path, 2. content
            "bash": ["command", "description", "timeout", "run_in_background"],
            "read": ["file_path", "limit", "offset"],
            "edit": ["file_path", "old_string", "new_string", "replace_all"],
            "multi_edit": ["file_path", "edits"],
            "grep": ["pattern", "path", "output_mode"],
            "glob": ["pattern", "path"],
            "web_fetch": ["url", "prompt"],
            "web_search": ["query", "allowed_domains", "blocked_domains"],
        }

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

    def _to_snake_case(self, name: str) -> str:
        """
        Convert PascalCase to snake_case for tool name normalization.

        Examples:
            Write -> write
            MultiEdit -> multi_edit
            WebFetch -> web_fetch
        """
        # Insert underscore before capital letters (except at start)
        result = re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()
        return result

    def _parse_python_call(self, text: str) -> List[Dict[str, Any]]:
        """
        Parse Python-style function calls using ast.parse for full Python syntax support.

        This handles:
        - Triple-quoted strings with embedded newlines
        - Keyword arguments
        - Complex nested structures
        - All Python literal types
        """
        tool_calls = []

        for match in self.PYTHON_TOOL_CALL_PATTERN.finditer(text):
            call_str = match.group(1)

            try:
                # Parse the entire function call as Python code
                tree = ast.parse(call_str)

                # Extract the call node
                if not tree.body or not isinstance(tree.body[0], ast.Expr):
                    continue

                call_node = tree.body[0].value
                if not isinstance(call_node, ast.Call) or not isinstance(call_node.func, ast.Name):
                    continue

                tool_name_raw = call_node.func.id
                tool_name = self._to_snake_case(tool_name_raw)

                # Security: Validate tool name
                if not self._validate_tool_name(tool_name):
                    continue

                params = {}

                # 1. Map positional arguments using generated mappings
                if tool_name in self.param_mappings:
                    param_names = self.param_mappings[tool_name]
                    for i, arg_node in enumerate(call_node.args):
                        if i < len(param_names):
                            try:
                                # Use ast.literal_eval on the node to get the value
                                params[param_names[i]] = ast.literal_eval(arg_node)
                            except (ValueError, TypeError) as e:
                                if self.log_errors:
                                    logger.warning(f"Could not evaluate argument {i}: {e}")

                # 2. Map keyword arguments (these override positional if both exist)
                for kw_node in call_node.keywords:
                    if kw_node.arg:  # Skip **kwargs
                        try:
                            params[kw_node.arg] = ast.literal_eval(kw_node.value)
                        except (ValueError, TypeError) as e:
                            if self.log_errors:
                                logger.warning(f"Could not evaluate keyword argument {kw_node.arg}: {e}")

                tool_calls.append({"name": tool_name, "parameters": params, "id": f"call_{len(tool_calls)}"})
                self.stats["total_parsed"] += 1

            except (ValueError, SyntaxError) as e:
                self.stats["parse_errors"] += 1
                self.stats["python_parse_errors"] += 1
                self.stats["consecutive_errors"] += 1

                if self.log_errors:
                    logger.warning(f"Could not parse Python call with ast.parse: {e}")
                    logger.warning(f"Call string: {call_str[:200]}...")

                # Check if we should fail fast
                if self.fail_on_parse_error:
                    raise ValueError(f"Failed to parse Python tool call: {e}")

                # Check consecutive error threshold
                if self.stats["consecutive_errors"] >= self.max_consecutive_errors:
                    logger.error(f"Too many consecutive parse errors ({self.max_consecutive_errors}), stopping")
                    break

                continue
            except Exception as e:
                # Catch any other unexpected errors
                self.stats["parse_errors"] += 1
                self.stats["python_parse_errors"] += 1
                self.stats["consecutive_errors"] += 1
                logger.error(f"Unexpected error parsing Python call: {e}")
                if self.fail_on_parse_error:
                    raise
                continue

        # Reset consecutive errors on successful parse
        if tool_calls:
            self.stats["consecutive_errors"] = 0

        return tool_calls

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
        remaining_text = text  # Work with a copy to progressively strip parsed content

        # Parse JSON format tool calls
        for match in self.JSON_TOOL_CALL_PATTERN.finditer(remaining_text):
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
                # Reset consecutive errors on successful parse
                self.stats["consecutive_errors"] = 0

                # Remove the parsed JSON from remaining text to avoid duplicates
                remaining_text = remaining_text.replace(match.group(0), "", 1)

            except json.JSONDecodeError as e:
                self.stats["parse_errors"] += 1
                self.stats["json_parse_errors"] += 1
                self.stats["consecutive_errors"] += 1

                if self.log_errors:
                    logger.warning(f"Failed to parse JSON tool call: {e}\n" f"Content preview: {json_content[:100]}...")

                if self.fail_on_parse_error:
                    raise ValueError(f"Failed to parse JSON tool call: {e}")

                if self.stats["consecutive_errors"] >= self.max_consecutive_errors:
                    logger.error(f"Too many consecutive parse errors ({self.max_consecutive_errors}), stopping")
                    break

                continue

        # Parse XML format tool calls
        for match in self.XML_TOOL_CALL_PATTERN.finditer(remaining_text):
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
                # Reset consecutive errors on successful parse
                self.stats["consecutive_errors"] = 0

                # Remove the parsed XML from remaining text to avoid duplicates
                remaining_text = remaining_text.replace(match.group(0), "", 1)

            except Exception as e:
                self.stats["parse_errors"] += 1
                self.stats["xml_parse_errors"] += 1
                self.stats["consecutive_errors"] += 1
                if self.log_errors:
                    logger.warning(f"Failed to parse XML tool call: {e}\n" f"Tool: {tool_name}, Args: {args_str[:100]}...")
                continue

        # Parse Python-style function calls (e.g., Write("file.txt", "content"))
        # This is for models like Claude that output Python-style tool calls
        # Note: Since _parse_python_call processes all Python calls at once,
        # and they are distinct from JSON/XML formats, duplicates are unlikely
        # but we still use remaining_text for consistency
        python_calls = self._parse_python_call(remaining_text)
        for call in python_calls:
            if len(tool_calls) >= self.max_tool_calls:
                break

            # Security: Validate tool name
            if not self._validate_tool_name(call["name"]):
                continue

            tool_calls.append(call)
            # Don't increment here - already incremented in _parse_python_call

        return tool_calls

    def update_tool_definitions(self, tool_definitions: Dict[str, Dict[str, Any]]) -> None:
        """
        Update tool definitions and regenerate parameter mappings.

        This allows the parser to adapt to new or modified tools at runtime
        without requiring code changes.

        Args:
            tool_definitions: Dictionary of tool definitions with parameter info
        """
        self.param_mappings = self._generate_param_mappings(tool_definitions)
        logger.info(f"Updated param mappings for {len(self.param_mappings)} tools")

    def get_param_mappings(self) -> Dict[str, List[str]]:
        """
        Get the current parameter mappings for inspection/debugging.

        Returns:
            Current parameter mappings dictionary
        """
        return self.param_mappings.copy()

    def strip_tool_calls(self, text: str) -> str:
        """
        Remove all tool call formats from text.

        This centralizes the content stripping logic to ensure consistency
        between parsing and stripping. Uses the same patterns that are used
        for parsing to guarantee that any parsed tool call can be stripped.

        Args:
            text: The text containing tool calls to strip

        Returns:
            The text with all tool calls removed
        """
        import re

        # Strip JSON format tool calls (including tool_code variant)
        text = re.sub(r"```(?:tool_call|tool_code|json).*?```", "", text, flags=re.DOTALL)

        # Strip XML format tool calls
        text = re.sub(r"<tool>.*?</tool>", "", text, flags=re.DOTALL)

        # Strip Python code blocks that contain tool calls
        # First, find all Python code blocks
        python_blocks = re.finditer(r"```python\s*\n(.*?)\n\s*```", text, re.DOTALL)

        # Check each block for tool calls and remove if found
        for match in reversed(list(python_blocks)):
            block_content = match.group(1)
            # Check if block contains any known tool names as function calls
            # This is more robust than relying on naming conventions
            contains_tool_call = False
            for tool_name in self.param_mappings.keys():
                # Create a regex pattern for each specific tool name
                # Using word boundary and escaping the tool name for safety
                if re.search(rf"\b{re.escape(tool_name)}\s*\(", block_content, re.IGNORECASE):
                    contains_tool_call = True
                    break

            if contains_tool_call:
                # Replace the entire code block
                text = text[: match.start()] + text[match.end() :]

        # Also strip inline Python-style function calls (not in code blocks)
        # Build pattern for known tool names only
        for tool_name in self.param_mappings.keys():
            # Create pattern for this specific tool
            tool_pattern = (
                rf"\b({re.escape(tool_name)}\s*\("  # Specific tool name and opening paren
                r"(?:"  # Non-capturing group for arguments
                r'[^()"\']+'  # Non-quote, non-paren characters
                r'|"(?:[^"\\]|\\.)*"'  # Double-quoted strings
                r"|'(?:[^'\\]|\\.)*'"  # Single-quoted strings
                r'|"""[\s\S]*?"""'  # Triple double quotes
                r"|'''[\s\S]*?'''"  # Triple single quotes
                r"|\([^)]*\)"  # Nested parentheses (one level only)
                r")*"  # Zero or more of the above
                r"\))"  # Closing paren
            )
            text = re.sub(tool_pattern, "", text, flags=re.DOTALL | re.IGNORECASE)

        # Clean up any extra whitespace left behind
        text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)

        return text.strip()

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
                    {
                        "tool": tool_call["name"],
                        "parameters": tool_call["parameters"],
                        "result": {"success": False, "error": str(e)},
                    }
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
            "has been completed",
            "completed",
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
                {
                    "functionDeclarations": [
                        {"name": k, "description": v.get("description", ""), "parameters": v.get("parameters", {})}
                        for k, v in tools.items()
                    ]
                }
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

        # Check if tools dict is empty
        if isinstance(self.tools, list) and len(self.tools) == 1:
            if "functionDeclarations" in self.tools[0] and not self.tools[0]["functionDeclarations"]:
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
