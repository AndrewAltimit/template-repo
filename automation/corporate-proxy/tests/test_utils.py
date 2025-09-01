"""
Shared test utilities for corporate proxy tests.

This module provides common test functions and utilities to avoid code duplication
across test files and ensure we're testing against production logic.

IMPORTANT: The format_tool_calls_for_openai function here is kept in sync with the
production implementation in shared/services/translation_wrapper.py. If you modify
the production function, update this test utility as well.
"""

import json
from typing import Any, Dict, List

# OpenCode parameter mappings - must match production configuration
OPENCODE_PARAM_MAPPINGS = {
    "write": {"file_path": "filePath", "content": "content"},
    "bash": {"command": "command", "_required_defaults": {"description": "Execute bash command"}},
    "read": {"file_path": "filePath", "limit": "limit", "offset": "offset"},
    "edit": {
        "file_path": "filePath",
        "old_string": "oldString",
        "new_string": "newString",
        "replace_all": "replaceAll",
    },
    "grep": {
        "pattern": "pattern",
        "path": "path",
        "output_mode": "outputMode",
        "-n": "showLineNumbers",
        "-A": "linesAfter",
        "-B": "linesBefore",
        "-i": "caseInsensitive",
    },
}


def format_tool_calls_for_openai(tool_calls: List[Dict[str, Any]], streaming: bool = False) -> List[Dict[str, Any]]:
    """
    Format parsed tool calls into OpenAI format with OpenCode parameter mapping.

    This function mirrors the production implementation in translation_wrapper.py
    to ensure tests are using the same logic as production code.

    Args:
        tool_calls: List of parsed tool calls
        streaming: If True, add index field for streaming responses

    Returns:
        List of formatted tool calls in OpenAI format
    """
    formatted_calls = []
    for i, call in enumerate(tool_calls):
        tool_name = call.get("name", call.get("tool"))
        params = call.get("parameters", {})

        # Apply OpenCode parameter mappings if available
        if tool_name in OPENCODE_PARAM_MAPPINGS:
            mappings = OPENCODE_PARAM_MAPPINGS[tool_name]
            mapped_params = {}

            # Map parameter names from snake_case to camelCase
            for snake_key, value in params.items():
                camel_key = mappings.get(snake_key, snake_key)  # Use original if no mapping
                mapped_params[camel_key] = value

            # Add required default parameters if specified
            if "_required_defaults" in mappings:
                for key, default_value in mappings["_required_defaults"].items():
                    if key not in mapped_params:
                        mapped_params[key] = default_value

            params = mapped_params

        formatted_call = {
            "id": f"call_{i}",
            "type": "function",
            "function": {"name": tool_name, "arguments": json.dumps(params)},
        }
        # Add index for streaming responses
        if streaming:
            formatted_call["index"] = i
        formatted_calls.append(formatted_call)
    return formatted_calls


# Re-export for convenient test imports
__all__ = ["format_tool_calls_for_openai", "OPENCODE_PARAM_MAPPINGS"]
