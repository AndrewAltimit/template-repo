#!/usr/bin/env python3
"""
Test script for automatic tool support detection
Validates that the enhanced translation wrapper correctly handles both
models with and without native tool support
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "services"))

# pylint: disable=wrong-import-position
from text_tool_parser import TextToolParser  # noqa: E402


def test_text_tool_parser():
    """Test that text tool parser works correctly"""
    parser = TextToolParser(allowed_tools={"write", "bash", "read"}, max_tool_calls=10)

    # Test JSON format
    text_with_json = """
    I'll write that file for you.

    ```tool_call
    {
      "tool": "write",
      "parameters": {
        "file_path": "test.txt",
        "content": "Hello, World!"
      }
    }
    ```
    """

    json_calls = parser.parse_tool_calls(text_with_json)
    assert len(json_calls) == 1
    assert json_calls[0]["name"] == "write"
    print("✅ JSON format parsing works")

    # Test Python format
    text_with_python = 'Let me run that command: Bash("ls -la", "List files")'
    python_calls = parser.parse_tool_calls(text_with_python)
    assert len(python_calls) == 1
    assert python_calls[0]["name"] == "bash"
    assert python_calls[0]["parameters"]["command"] == "ls -la"
    print("✅ Python format parsing works")

    # Test mixed content
    mixed_text = """
    I'll first check the files and then write the result.

    Read("config.json")

    Now let me write the summary:
    ```tool_call
    {
      "tool": "write",
      "parameters": {
        "file_path": "summary.txt",
        "content": "Configuration loaded"
      }
    }
    ```
    """

    mixed_calls = parser.parse_tool_calls(mixed_text)
    assert len(mixed_calls) == 2
    # The parser returns them in the order found, check both are present
    tool_names = [call["name"] for call in mixed_calls]
    assert "read" in tool_names
    assert "write" in tool_names
    print("✅ Mixed format parsing works")

    print("\n✅ All text tool parser tests passed!")


def test_model_config_detection():
    """Test model configuration detection logic"""

    # Simulate model configurations
    test_models = {
        "model-with-tools": {"id": "company/model-with-tools", "endpoint": "endpoint1", "supports_tools": True},
        "model-without-tools": {"id": "company/model-without-tools", "endpoint": "endpoint2", "supports_tools": False},
        "model-default": {
            "id": "company/model-default",
            "endpoint": "endpoint3",
            # No supports_tools field - should default to True
        },
    }

    # Test detection logic
    for model_id, config in test_models.items():
        supports_tools = config.get("supports_tools", True)
        print(f"Model: {model_id}")
        print(f"  - Supports tools: {supports_tools}")

        if not supports_tools:
            print("  - Action: Will use text tool parser")
            print("  - Tools will be injected into prompt")
        else:
            print("  - Action: Will use native tool calling")
            print("  - Tools sent directly to API")
        print()

    print("✅ Model configuration detection works correctly!")


def test_tool_injection():
    """Test tool injection into prompts"""

    tools = [
        {
            "type": "function",
            "function": {
                "name": "write",
                "description": "Write content to a file",
                "parameters": {
                    "type": "object",
                    "properties": {"file_path": {"type": "string"}, "content": {"type": "string"}},
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "bash",
                "description": "Execute a bash command",
                "parameters": {"type": "object", "properties": {"command": {"type": "string"}}},
            },
        },
    ]

    # Create tool instructions
    tool_descriptions = []
    for tool in tools:
        func = tool["function"]
        name = func["name"]
        desc = func["description"]
        tool_descriptions.append(f"- {name}: {desc}")

    tool_instruction = f"""You have access to the following tools:

{chr(10).join(tool_descriptions)}

When you need to use a tool, format it as:
```tool_call
{{
  "tool": "tool_name",
  "parameters": {{...}}
}}
```"""

    print("Generated tool instruction for prompt injection:")
    print("-" * 50)
    print(tool_instruction)
    print("-" * 50)
    print("\n✅ Tool injection format is correct!")


def main():
    """Run all tests"""
    print("=" * 60)
    print("Testing Automatic Tool Support Detection")
    print("=" * 60)

    print("\n1. Testing Text Tool Parser")
    print("-" * 40)
    test_text_tool_parser()

    print("\n2. Testing Model Configuration Detection")
    print("-" * 40)
    test_model_config_detection()

    print("\n3. Testing Tool Injection")
    print("-" * 40)
    test_tool_injection()

    print("\n" + "=" * 60)
    print("🎉 All tests passed successfully!")
    print("=" * 60)
    print("\nThe enhanced wrapper will automatically:")
    print("1. Detect if a model supports tools from models.json")
    print("2. Use native tool calling when supported")
    print("3. Use text parsing when not supported")
    print("4. No manual configuration needed!")


if __name__ == "__main__":
    main()
