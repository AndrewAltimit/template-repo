#!/usr/bin/env python3
"""Debug the text tool parser"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent))

from shared.services.text_tool_parser import TextToolParser

parser = TextToolParser()

# Test the actual failing test case
failing_text = """
        I'll read the file for you.

        ```tool_call
        {
          "tool": "read_file",
          "parameters": {
            "path": "/tmp/test.txt"
          }
        }
        ```

        Now let me check another file.
        """

print("Testing actual failing case:")
print("Input text starts with:", repr(failing_text[:50]))
result = parser.parse_tool_calls(failing_text)
print("Parsed tool calls:", result)
print()

# Debug the regex
import re

pattern = r"```tool_call\s*\n(.*?)\n```"
matches = re.findall(pattern, failing_text, re.DOTALL)
print("Regex matches found:", len(matches))
if matches:
    print("First match:", repr(matches[0][:50]))
