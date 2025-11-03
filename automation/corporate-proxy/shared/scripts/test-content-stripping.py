#!/usr/bin/env python3
"""
Test script to verify that all tool call formats are properly stripped from content
"""

import re
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "services"))

# pylint: disable=wrong-import-position
from text_tool_parser import TextToolParser  # noqa: E402


def normalize_content(content):
    """Normalize content by removing extra whitespace and empty lines"""
    lines = [line.strip() for line in content.strip().split("\n")]
    # Remove empty lines but keep structure
    result = []
    for line in lines:
        if line or (result and result[-1]):  # Keep line if non-empty or after non-empty
            result.append(line)
    # Join with single newlines and then add double newlines between paragraphs
    text = "\n".join(result)
    # Replace multiple consecutive empty lines with double newline
    text = re.sub(r"\n\n+", "\n\n", text)
    return text.strip()


def test_content_stripping():
    """Test that all tool call formats are stripped correctly"""

    # Initialize the parser to use centralized stripping
    parser = TextToolParser(allowed_tools={"write", "bash", "read", "multiedit", "grep"}, max_tool_calls=20)

    # Test case 1: JSON format
    content1 = """
    I'll help you with that task.

    ```tool_call
    {
      "tool": "write",
      "parameters": {
        "file_path": "test.txt",
        "content": "Hello World"
      }
    }
    ```

    The file has been created.
    """

    # Use centralized stripping method
    content1_stripped = parser.strip_tool_calls(content1)
    content1_normalized = normalize_content(content1_stripped)
    expected1 = normalize_content("I'll help you with that task.\n\nThe file has been created.")
    assert content1_normalized == expected1, f"JSON format not stripped correctly: {content1_normalized}"
    print("✅ JSON format stripping works")

    # Test case 2: XML format
    content2 = """
    Let me check that for you.

    <tool>bash(command="ls -la", timeout=30)</tool>

    Here are the results.
    """

    # Use centralized stripping method
    content2_stripped = parser.strip_tool_calls(content2)
    content2_normalized = normalize_content(content2_stripped)
    expected2 = normalize_content("Let me check that for you.\n\nHere are the results.")
    assert content2_normalized == expected2, f"XML format not stripped correctly: {content2_normalized}"
    print("✅ XML format stripping works")

    # Test case 3: Python-style format
    content3 = """
    I'll write that file for you.

    Write("output.txt", "This is the content")

    And now let's check it:
    Read("output.txt")

    Done!
    """

    # Use centralized stripping method
    content3_stripped = parser.strip_tool_calls(content3)
    content3_normalized = normalize_content(content3_stripped)
    expected3 = normalize_content("I'll write that file for you.\n\nAnd now let's check it:\n\nDone!")
    assert content3_normalized == expected3, f"Python format not stripped correctly: {content3_normalized}"
    print("✅ Python-style format stripping works")

    # Test case 4: Mixed formats
    content4 = """
    Here's a complex example:

    First, I'll use Python style:
    Bash("echo 'Hello'")

    Then JSON:
    ```tool_call
    {"tool": "write", "parameters": {"file_path": "test.txt", "content": "data"}}
    ```

    And XML:
    <tool>read(file_path="test.txt")</tool>

    All done!
    """

    # Use centralized stripping method
    content4_stripped = parser.strip_tool_calls(content4)
    content4_normalized = normalize_content(content4_stripped)
    expected4 = normalize_content(
        "Here's a complex example:\n\nFirst, I'll use Python style:\n\nThen JSON:\n\nAnd XML:\n\nAll done!"
    )
    assert content4_normalized == expected4, f"Mixed formats not stripped correctly: {content4_normalized}"
    print("✅ Mixed format stripping works")

    # Test case 5: Complex Python calls with nested content
    content5 = """
    Let me create a complex file:

    Write("config.json", '{"name": "test", "values": [1, 2, 3]}')

    And another one:
    MultiEdit("file.py", [{"old": "foo", "new": "bar"}])

    All files updated.
    """

    # Use centralized stripping method
    content5_stripped = parser.strip_tool_calls(content5)
    content5_normalized = normalize_content(content5_stripped)
    expected5 = normalize_content("Let me create a complex file:\n\nAnd another one:\n\nAll files updated.")
    assert content5_normalized == expected5, f"Complex Python calls not stripped correctly: {content5_normalized}"
    print("✅ Complex Python call stripping works")

    # Test case 6: Verify centralized method is consistent
    test_text = """
    Here's a test with all formats:

    Write("test.txt", "content")

    ```tool_call
    {"tool": "bash", "parameters": {"command": "ls"}}
    ```

    <tool>read(file_path="test.txt")</tool>

    Done!
    """

    # Test that the centralized method produces same result as manual stripping
    centralized_result = parser.strip_tool_calls(test_text)

    # Also verify it leaves clean text
    expected_clean = normalize_content("Here's a test with all formats:\n\nDone!")
    assert normalize_content(centralized_result) == expected_clean, "Centralized stripping not working correctly"
    print("✅ Centralized strip_tool_calls method works correctly")

    print("\n✅ All content stripping tests passed!")
    print("The centralized stripping method correctly handles JSON, XML, and Python-style tool calls.")


if __name__ == "__main__":
    test_content_stripping()
