#!/usr/bin/env python3
"""
Demonstration of dual mode tool support
Shows both native and text parsing modes in action
"""

import json
from pathlib import Path
import sys

# Add paths for imports
sys.path.append(str(Path(__file__).parent))
sys.path.append(str(Path(__file__).parent / "gemini"))


from gemini_tool_executor import GEMINI_TOOLS, execute_tool_call  # noqa: E402
from shared.services.text_tool_parser import TextToolParser  # noqa: E402
from shared.services.tool_injector import ToolInjector  # noqa: E402


def demo_native_mode():
    """Demonstrate native mode with structured tool calls"""
    print("\n" + "=" * 60)
    print("DEMO: Native Mode (Structured Tool Calls)")
    print("=" * 60)

    # Simulate an API response with structured tool calls
    api_response = {
        "tool_calls": [
            {
                "id": "call_001",
                "type": "function",
                "function": {"name": "list_directory", "arguments": json.dumps({"path": "."})},
            }
        ],
        "content": [{"text": "I'll list the directory contents for you."}],
        "usage": {"input_tokens": 10, "output_tokens": 20},
    }

    print("\nAPI Response (with structured tool calls):")
    print(json.dumps(api_response, indent=2))

    # In native mode, tools are extracted directly
    if "tool_calls" in api_response:
        print("\n✓ Native mode detected structured tool calls")
        for tc in api_response["tool_calls"]:
            func = tc["function"]
            print(f"  - Tool: {func['name']}")
            print(f"    Args: {func['arguments']}")

            # Execute the tool
            args = json.loads(func["arguments"])
            result = execute_tool_call(func["name"], args)
            print(f"    Result: {result}")


def demo_text_mode():
    """Demonstrate text mode with parsing from response"""
    print("\n" + "=" * 60)
    print("DEMO: Text Mode (Parse Tools from Text)")
    print("=" * 60)

    # Initialize parser
    parser = TextToolParser(tool_executor=execute_tool_call)

    # Simulate an API response with embedded tool calls in text
    api_response = {
        "content": [
            {
                "text": """I'll help you with those files. Let me start by listing the directory.

```tool_call
{
  "tool": "list_directory",
  "parameters": {
    "path": "."
  }
}
```

After that, I'll read the configuration file.

```tool_call
{
  "tool": "read_file",
  "parameters": {
    "path": "config.json"
  }
}
```

This will give us the information we need."""
            }
        ],
        "usage": {"input_tokens": 50, "output_tokens": 100},
    }

    print("\nAPI Response (text with embedded tool calls):")
    print(api_response["content"][0]["text"])

    # Parse tool calls from text
    text = api_response["content"][0]["text"]
    tool_calls = parser.parse_tool_calls(text)

    print(f"\n✓ Text mode found {len(tool_calls)} tool call(s)")

    # Execute each tool
    results = parser.execute_tool_calls(tool_calls)

    for result in results:
        print(f"\n  Tool: {result['tool']}")
        print(f"  Parameters: {result['parameters']}")
        print(f"  Success: {result['result'].get('success', False)}")
        if result["result"].get("success"):
            # Show a preview of the result
            output = str(result["result"])[:100]
            print(f"  Output: {output}...")

    # Format results for continuation
    formatted = parser.format_tool_results(results)
    print("\nFormatted results for AI continuation:")
    print("-" * 40)
    print(formatted[:300] + "...")

    # Check if task is complete
    final_response = "Based on the directory listing and configuration, the task is complete."
    is_complete = parser.is_complete_response(final_response)
    print(f"\nTask complete: {is_complete}")


def demo_tool_injection():
    """Demonstrate tool injection for prompts"""
    print("\n" + "=" * 60)
    print("DEMO: Tool Injection into Prompts")
    print("=" * 60)

    # Define available tools
    tools = {"read_file": GEMINI_TOOLS["read_file"], "write_file": GEMINI_TOOLS["write_file"]}

    injector = ToolInjector(tools)

    # Original user message
    original_message = "Please read the README file and summarize it."

    print("\nOriginal user message:")
    print(original_message)

    # Inject tools into message
    messages = [{"role": "user", "content": original_message}]

    enhanced_messages = injector.inject_tools_into_messages(messages)

    print("\nEnhanced message with tool instructions:")
    print("-" * 40)
    enhanced_content = enhanced_messages[0]["content"]
    # Show first part of enhanced message
    print(enhanced_content[:500] + "...")

    # Also enhance system prompt
    original_system = "You are a helpful assistant."
    enhanced_system = injector.inject_system_prompt(original_system)

    print("\nEnhanced system prompt:")
    print("-" * 40)
    print(enhanced_system)


def main():
    """Run all demonstrations"""
    print("=" * 60)
    print("Dual Mode Tool Support Demonstration")
    print("=" * 60)

    print("\nThis demo shows how the corporate proxy handles tools in two modes:")
    print("1. Native Mode - APIs with built-in tool/function support")
    print("2. Text Mode - APIs that only return text (tools parsed from response)")

    # Demo each mode
    demo_native_mode()
    demo_text_mode()
    demo_tool_injection()

    print("\n" + "=" * 60)
    print("Demo Complete!")
    print("=" * 60)
    print("\nKey Takeaways:")
    print("- Native mode uses structured tool_calls from the API")
    print("- Text mode parses tool calls from ```tool_call``` blocks")
    print("- Tool injection adds instructions to prompts for text mode")
    print("- Both modes execute tools and can continue conversations")
    print("\nConfigure with TOOL_MODE environment variable:")
    print("  TOOL_MODE=native (default) - for tool-enabled APIs")
    print("  TOOL_MODE=text - for text-only APIs")


if __name__ == "__main__":
    main()
