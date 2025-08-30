#!/usr/bin/env python3
"""
Text-Based Tool Parser and Executor
Handles tool execution for non-tool-enabled API endpoints by:
1. Embedding tool definitions in prompts
2. Parsing tool calls from generated text
3. Executing tools and feeding results back
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

# Setup logging
logger = logging.getLogger(__name__)


class TextToolParser:
    """Parse and execute tools from text-based responses"""

    def __init__(self, tool_executor=None):
        """Initialize with an optional tool executor"""
        self.tool_executor = tool_executor

    def generate_tool_prompt(self, tools: Dict[str, Any], user_message: str) -> str:
        """Generate a prompt that includes tool definitions for non-tool-enabled endpoints"""

        tool_descriptions = []
        for tool_name, tool_def in tools.items():
            desc = f"- **{tool_name}**: {tool_def.get('description', '')}"
            if "parameters" in tool_def and "properties" in tool_def["parameters"]:
                params = []
                for param_name, param_def in tool_def["parameters"]["properties"].items():
                    param_desc = param_def.get("description", "")
                    param_type = param_def.get("type", "string")
                    required = param_name in tool_def["parameters"].get("required", [])
                    req_str = " (required)" if required else " (optional)"
                    params.append(f"  - {param_name} ({param_type}): {param_desc}{req_str}")
                if params:
                    desc += "\n" + "\n".join(params)
            tool_descriptions.append(desc)

        tool_prompt = f"""You have access to the following tools to help complete tasks:

{chr(10).join(tool_descriptions)}

To use a tool, respond with a tool call in the following JSON format on its own line:
```tool_call
{{
  "tool": "tool_name",
  "parameters": {{
    "param1": "value1",
    "param2": "value2"
  }}
}}
```

You can make multiple tool calls in your response. After making tool calls, you will receive the results and can continue working on the task.

Important guidelines:
1. Always use the exact tool names and parameter names as specified
2. Ensure all required parameters are provided
3. Tool calls must be valid JSON inside ```tool_call``` blocks
4. You can explain what you're doing before and after tool calls
5. Wait for tool results before proceeding with tasks that depend on them

User's request: {user_message}"""

        return tool_prompt

    def parse_tool_calls(self, text: str) -> List[Dict[str, Any]]:
        """Extract tool calls from generated text"""

        tool_calls = []

        # Look for tool calls in ```tool_call``` blocks (with optional whitespace)
        pattern = r"```tool_call\s*\n(.*?)\n\s*```"
        matches = re.findall(pattern, text, re.DOTALL)

        for match in matches:
            try:
                # Parse the JSON tool call
                tool_call = json.loads(match.strip())
                if "tool" in tool_call:
                    tool_calls.append(
                        {"name": tool_call["tool"], "parameters": tool_call.get("parameters", {}), "raw": match.strip()}
                    )
                    logger.info(f"Parsed tool call: {tool_call['tool']}")
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse tool call JSON: {e}")
                logger.debug(f"Raw content: {match}")

        # Also look for alternative formats (for compatibility)
        # Format: <tool>tool_name(param1="value1", param2="value2")</tool>
        alt_pattern = r"<tool>(.*?)\((.*?)\)</tool>"
        alt_matches = re.findall(alt_pattern, text)

        for tool_name, params_str in alt_matches:
            try:
                # Parse parameters from function-like syntax
                params = {}
                if params_str:
                    # Simple parameter parsing (handles key="value" format)
                    param_pattern = r'(\w+)=["\'](.*?)["\']'
                    param_matches = re.findall(param_pattern, params_str)
                    params = {key: value for key, value in param_matches}

                tool_calls.append(
                    {"name": tool_name.strip(), "parameters": params, "raw": f"<tool>{tool_name}({params_str})</tool>"}
                )
                logger.info(f"Parsed alt format tool call: {tool_name}")
            except Exception as e:
                logger.warning(f"Failed to parse alternative tool call: {e}")

        return tool_calls

    def execute_tool_calls(self, tool_calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Execute parsed tool calls and return results"""

        results = []

        for tool_call in tool_calls:
            tool_name = tool_call["name"]
            parameters = tool_call["parameters"]

            logger.info(f"Executing tool: {tool_name} with parameters: {parameters}")

            if self.tool_executor:
                # Use provided tool executor
                result = self.tool_executor(tool_name, parameters)
            else:
                # Mock execution for testing
                result = {
                    "success": True,
                    "tool": tool_name,
                    "output": f"Mock result for {tool_name} with params {parameters}",
                }

            results.append({"tool": tool_name, "parameters": parameters, "result": result})

        return results

    def format_tool_results(self, results: List[Dict[str, Any]]) -> str:
        """Format tool execution results for feeding back to the AI"""

        if not results:
            return ""

        formatted_results = []
        for result in results:
            tool_name = result["tool"]
            tool_result = result["result"]

            # Format based on success/failure
            if tool_result.get("success"):
                # Extract the main output from the result
                if "content" in tool_result:
                    output = tool_result["content"]
                elif "output" in tool_result:
                    output = tool_result["output"]
                elif "stdout" in tool_result:
                    output = tool_result["stdout"]
                    if tool_result.get("stderr"):
                        output += f"\nStderr: {tool_result['stderr']}"
                elif "message" in tool_result:
                    output = tool_result["message"]
                else:
                    output = json.dumps(tool_result, indent=2)

                formatted_results.append(f"### Tool Result: {tool_name}\n```\n{output}\n```")
            else:
                error = tool_result.get("error", "Unknown error")
                formatted_results.append(f"### Tool Error: {tool_name}\n```\nError: {error}\n```")

        return "\n\n".join(formatted_results)

    def process_response_with_tools(
        self, response_text: str, continue_prompt: Optional[str] = None
    ) -> Tuple[str, List[Dict[str, Any]], bool]:
        """
        Process a response, execute any tool calls, and determine if continuation is needed

        Returns:
            - Formatted results to send back to AI
            - List of executed tool calls
            - Whether continuation is needed
        """

        # Parse tool calls from the response
        tool_calls = self.parse_tool_calls(response_text)

        if not tool_calls:
            # No tool calls found, response is complete
            return response_text, [], False

        # Execute the tool calls
        results = self.execute_tool_calls(tool_calls)

        # Format results for feedback
        formatted_results = self.format_tool_results(results)

        # Build continuation message
        if continue_prompt:
            continuation_message = f"{formatted_results}\n\n{continue_prompt}"
        else:
            continuation_message = f"""{formatted_results}

Based on the tool results above, please continue with the task. If the task is complete, provide a summary of what was accomplished."""

        # Check if we should continue (heuristic: if tools were called, we likely need continuation)
        needs_continuation = len(tool_calls) > 0

        return continuation_message, results, needs_continuation

    def is_complete_response(self, text: str) -> bool:
        """
        Determine if a response is complete or needs continuation
        Simple heuristic: check for completion indicators
        """

        completion_indicators = [
            "task is complete",
            "task has been completed",
            "successfully completed",
            "completed the task",
            "finished the task",
            "done with",
            "accomplished",
            "i've completed",
            "i have completed",
        ]

        text_lower = text.lower()
        return any(indicator in text_lower for indicator in completion_indicators)


class ToolInjector:
    """Inject tool capabilities into prompts for non-tool-enabled endpoints"""

    def __init__(self, tools: Dict[str, Any]):
        """Initialize with tool definitions"""
        self.tools = tools
        self.parser = TextToolParser()

    def inject_tools_into_messages(self, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        Inject tool definitions into the message history
        Modifies the first user message to include tool descriptions
        """

        if not messages or not self.tools:
            return messages

        # Find the first user message
        modified_messages = messages.copy()
        for i, msg in enumerate(modified_messages):
            if msg.get("role") == "user":
                # Inject tool prompt into the first user message
                original_content = msg.get("content", "")
                tool_prompt = self.parser.generate_tool_prompt(self.tools, original_content)
                modified_messages[i] = {"role": "user", "content": tool_prompt}
                break

        return modified_messages

    def inject_system_prompt(self, system_prompt: str) -> str:
        """
        Enhance system prompt with tool usage instructions
        """

        if not self.tools:
            return system_prompt

        tool_system_prompt = """You are an AI assistant with access to various tools. When you need to perform actions like reading files, running commands, or searching for information, use the appropriate tools.

Always follow the tool calling format specified in the user's message. Make sure to wait for tool results before proceeding with dependent tasks."""

        if system_prompt:
            return f"{system_prompt}\n\n{tool_system_prompt}"
        return tool_system_prompt
