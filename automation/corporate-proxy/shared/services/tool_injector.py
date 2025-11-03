#!/usr/bin/env python3
"""
Tool Injector for AI Agent Integration

Injects tool definitions into prompts and messages for text-mode processing.
"""

from typing import Any, Dict, List


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
