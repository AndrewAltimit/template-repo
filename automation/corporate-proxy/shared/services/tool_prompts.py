#!/usr/bin/env python3
"""
Tool Prompt Templates for Different AI Clients

This module contains the prompt templates for injecting tool instructions
into AI model prompts for clients that don't support native tool calling.
"""

TOOL_PROMPTS = {
    "opencode": {
        "examples": """2. **CRITICAL TOOL INVOCATION FORMAT - READ CAREFULLY**

   **CORRECT FORMAT - ALWAYS USE THIS:**
   ```python
   # File operations - MUST use camelCase parameters (filePath, NOT file_path):
   Write(filePath="filename.txt", content="content here")
   Read(filePath="path/to/file.txt")  # Optional: offset=0, limit=2000
   Edit(filePath="file.py", oldString="old text", newString="new text", replaceAll=False)

   # Command execution - ALWAYS include description parameter:
   Bash(command="python script.py", description="Run Python script")
   Bash(command="git status", description="Check Git status")
   Bash(command="npm install", description="Install dependencies")

   # Directory listing - Use Ls tool:
   Ls(path=".")  # List current directory
   Ls(path="src/")  # List src directory

   # Searching - ALWAYS include ALL required parameters:
   Grep(pattern="TODO", path="src/")  # Search for pattern in files
   Glob(pattern="*.py", path=".")  # Find files by pattern
   ```

   **NEVER DO THIS (WRONG):**
   - NEVER write: [Calling Read tool] or [Calling Write tool] - THIS IS NOT A TOOL CALL!
   - NEVER write: Read("file.txt") without parameter names
   - NEVER write: Bash("ls") without command= and description= parameters
   - NEVER omit required parameters
   - NEVER use snake_case like file_path or old_string - OpenCode uses camelCase!

   **PARAMETER RULES:**
   - ALWAYS use parameter names: Write(filePath="...", content="...")
   - ALWAYS use camelCase: filePath, oldString, newString (NOT file_path, old_string)
   - ALWAYS provide required parameters (filePath, content, command, pattern, path)
   - Bash REQUIRES description parameter: Bash(command="...", description="...")
   - Optional parameters can be omitted: offset, limit, replaceAll, timeout""",
        "patterns": """4. **COMPLETE WORKING EXAMPLES (COPY THESE PATTERNS):**

   **Creating a new file:**
   ```python
   Write(filePath="test.py", content="print('Hello World')")
   ```

   **Reading a file:**
   ```python
   Read(filePath="src/main.py")  # Read entire file
   Read(filePath="src/main.py", offset=100, limit=50)  # Read 50 lines starting from line 100
   ```

   **Modifying an existing file:**
   ```python
   # First read to see the content
   Read(filePath="config.json")
   # Then edit with exact strings
   Edit(filePath="config.json", oldString="false", newString="true", replaceAll=False)
   ```

   **Multiple edits to same file:**
   ```python
   MultiEdit(filePath="main.py", edits=[
     {"oldString": "import os", "newString": "import os, sys"},
     {"oldString": "DEBUG = False", "newString": "DEBUG = True"}
   ])
   ```

   **Listing directories:**
   ```python
   Ls(path=".")  # List current directory
   Ls(path="src/")  # List a specific directory
   ```

   **Running commands (MUST include description):**
   ```python
   Bash(command="pwd", description="Show current directory")
   Bash(command="python -m pytest tests/", description="Run test suite")
   Bash(command="git diff", description="Show uncommitted changes")
   ```

   **Searching for patterns:**
   ```python
   Grep(pattern="TODO", path=".")  # Search current directory
   Grep(pattern="import requests", path="src/")  # Search in src folder
   Glob(pattern="*.py", path=".")  # Find all Python files
   Glob(pattern="test_*.py", path="tests/")  # Find test files
   ```

   **REMEMBER: If you write [Calling xxx tool] instead of the proper Python code format, THE TOOL WILL NOT WORK!**""",
    },
    "crush": {
        "examples": """2. **CRITICAL TOOL INVOCATION FORMAT - READ CAREFULLY**

   **CORRECT FORMAT - ALWAYS USE THIS:**
   ```python
   # File operations - MUST use snake_case parameters (file_path, NOT filePath):
   Write(file_path="filename.txt", content="content here")
   View(file_path="path/to/file.txt")  # NOT Read! Optional: limit=100, offset=0
   Edit(file_path="file.py", old_string="old text", new_string="new text", replace_all=False)

   # Command execution - ALWAYS specify the command parameter:
   Bash(command="python script.py")
   Bash(command="git status")

   # Directory listing - Use Ls tool, not bash ls:
   Ls(path=".")  # List current directory
   Ls(path="src/")  # List src directory

   # Searching - ALWAYS include ALL required parameters:
   Grep(pattern="TODO", path="src/")  # path is REQUIRED
   Glob(pattern="*.py", path=".")     # path is REQUIRED, use "." for current dir
   ```

   **NEVER DO THIS (WRONG):**
   - NEVER write: [Calling View tool] or [Calling Write tool] - THIS IS NOT A TOOL CALL!
   - NEVER write: View("file.txt") without parameter names
   - NEVER use Read() - Crush uses View() instead!
   - NEVER write: Bash("ls") without command= parameter
   - NEVER omit required parameters
   - NEVER use camelCase like filePath or oldString

   **PARAMETER RULES:**
   - ALWAYS use parameter names: Write(file_path="...", content="...")
   - ALWAYS use snake_case: file_path, old_string, new_string (NOT filePath, oldString)
   - ALWAYS provide required parameters (file_path, content, command, pattern, path)
   - Optional parameters can be omitted: limit, offset, replace_all, timeout""",
        "patterns": """4. **COMPLETE WORKING EXAMPLES (COPY THESE PATTERNS):**

   **Creating a new file:**
   ```python
   Write(file_path="test.py", content="print('Hello World')")
   ```

   **Viewing/Reading a file (USE VIEW, NOT READ!):**
   ```python
   View(file_path="src/main.py")  # Crush uses View, not Read!
   ```

   **Modifying an existing file:**
   ```python
   # First view to see the content (USE VIEW!)
   View(file_path="config.json")
   # Then edit with exact strings
   Edit(file_path="config.json", old_string="false", new_string="true", replace_all=False)
   ```

   **Listing directories (Use Ls, not bash ls!):**
   ```python
   Ls(path=".")  # List current directory
   Ls(path="src/")  # List a specific directory
   ```

   **Running commands:**
   ```python
   Bash(command="pwd")
   Bash(command="python -m pytest tests/")
   Bash(command="git status")
   ```

   **Searching for patterns:**
   ```python
   Grep(pattern="TODO", path=".")  # Search current directory
   Grep(pattern="import requests", path="src/")  # Search in src folder
   Glob(pattern="*.py", path=".")  # Find all Python files
   Glob(pattern="test_*.py", path="tests/")  # Find test files
   ```

   **REMEMBER: If you write [Calling xxx tool] instead of the proper Python code format, THE TOOL WILL NOT WORK!**""",
    },
    "gemini": {
        "examples": """2. **Tool Invocation Format** - Use function calls in code blocks:
   ```
   # For file operations:
   functionCall: write
   args: {"path": "filename.txt", "content": "content here"}

   functionCall: read
   args: {"path": "path/to/file.txt"}

   functionCall: edit
   args: {"path": "file.py", "old_text": "old", "new_text": "new"}
   ```""",
        "patterns": """4. **Common Patterns:**
   - To create a file: Call write with path and content args
   - To modify a file: First read(path), then edit with old_text and new_text
   - To run commands: Call bash with command arg
   - To search code: Call grep or glob with appropriate args""",
    },
    "generic": {
        "examples": """2. **Tool Invocation Format** - Use Python code blocks:
   ```python
   # For file operations:
   Write("filename.txt", "content here")
   Read("path/to/file.txt")
   Edit("file.py", "old_text", "new_text")

   # For command execution:
   Bash("ls -la")

   # For searching:
   Grep("pattern", "path")
   Glob("*.py")
   ```""",
        "patterns": """4. **Common Patterns:**
   - To create a file: Use Write(file_path, content)
   - To modify a file: First Read(file_path), then Edit(file_path, old_string, new_string)
   - To run commands: Use Bash(command)
   - To search code: Use Grep(pattern, path) or Glob(pattern)""",
    },
}


def get_tool_instruction_template(client_type: str) -> str:
    """
    Get the instruction template for a specific client type.

    Args:
        client_type: Type of client ("opencode", "crush", "gemini", or "generic")

    Returns:
        The instruction template string with placeholders for tool descriptions and examples
    """
    if client_type == "opencode":
        return """CRITICAL: You MUST use these tools to complete ANY file or command tasks!

**Available Tools:**
{tool_descriptions}

**EXTREMELY IMPORTANT - HOW TO USE TOOLS**

1. **YOU MUST USE TOOLS** for ALL of these tasks:
   - Reading files: Use Read(filePath="...")
   - Writing files: Use Write(filePath="...", content="...")
   - Editing files: Use Edit(filePath="...", oldString="...", newString="...")
   - Running commands: Use Bash(command="...", description="...")
   - Searching code: Use Grep(pattern="...", path="...")
   - Finding files: Use Glob(pattern="...", path="...")
   - Listing directories: Use Ls(path="...")
   - Multiple edits: Use MultiEdit(filePath="...", edits=[...])

{tool_examples}

3. **CRITICAL RULES - FAILURE TO FOLLOW THESE WILL BREAK YOUR TOOLS:**
   - ONLY use Python code blocks with proper function calls
   - NEVER write text like [Calling Read tool] - this is NOT a tool call!
   - ALWAYS include parameter names (filePath=, content=, command=, etc.)
   - ALWAYS use camelCase for parameters (filePath NOT file_path)
   - Bash tool REQUIRES description parameter
   - Tool results will appear AFTER you invoke them - wait for results
   - If a tool does not work, check you are using the EXACT format shown above

{pattern_examples}

**Final Warning:** Without using these tools properly, you CANNOT read files, write files, or run commands.
The tools are your ONLY way to interact with the system. Use the EXACT formats shown above!"""
    elif client_type == "crush":
        return """CRITICAL: You MUST use these tools to complete ANY file or command tasks!

**Available Tools:**
{tool_descriptions}

**EXTREMELY IMPORTANT - HOW TO USE TOOLS**

1. **YOU MUST USE TOOLS** for ALL of these tasks:
   - Viewing/Reading files: Use View(file_path="...") **NOT Read() - Crush uses View!**
   - Writing files: Use Write(file_path="...", content="...")
   - Running commands: Use Bash(command="...")
   - Searching code: Use Grep(pattern="...", path="...")
   - Finding files: Use Glob(pattern="...", path="...")
   - Editing files: Use Edit(file_path="...", old_string="...", new_string="...")
   - Multiple edits: Use MultiEdit(file_path="...", edits=[...])
   - Listing directories: Use Ls(path="...")
   - Fetching URLs: Use Fetch(url="...")
   - Code search: Use Sourcegraph(query="...")

{tool_examples}

3. **CRITICAL RULES - FAILURE TO FOLLOW THESE WILL BREAK YOUR TOOLS:**
   - ONLY use Python code blocks with proper function calls
   - NEVER write text like [Calling View tool] - this is NOT a tool call!
   - ALWAYS include parameter names (file_path=, content=, command=, etc.)
   - ALWAYS use snake_case for parameters (file_path NOT filePath)
   - Tool results will appear AFTER you invoke them - wait for results
   - If a tool does not work, check you are using the EXACT format shown above

{pattern_examples}

**Final Warning:** Without using these tools properly, you CANNOT read files, write files, or run commands.
The tools are your ONLY way to interact with the system. Use the EXACT formats shown above!"""
    else:
        return """IMPORTANT: You have access to powerful tools that you MUST use to complete tasks effectively!

**Available Tools:**
{tool_descriptions}

**CRITICAL INSTRUCTIONS FOR TOOL USE:**

1. **ALWAYS use tools** when you need to:
   - Read or write files (use Read/Write tools)
   - Execute commands (use Bash tool)
   - Search for patterns (use Grep tool)
   - Navigate directories (use Glob tool)
   - Edit existing files (use Edit tool)

{tool_examples}

3. **Important Reminders:**
   - You CANNOT complete file-related tasks without using the appropriate tools
   - Tool results will appear after you invoke them - wait for results before continuing
   - Use tools multiple times if needed to complete a task thoroughly
   - Always use the exact tool names and parameter formats shown above

{pattern_examples}

Remember: You have full capability to interact with the filesystem and execute commands through these tools.
Use them confidently!"""


def get_default_system_prompt(client_type: str, has_tools: bool) -> str:
    """
    Get the default system prompt for a specific client type.

    Args:
        client_type: Type of client ("opencode", "crush", "gemini", or "generic")
        has_tools: Whether tools are available in the request

    Returns:
        The default system prompt string
    """
    if not has_tools:
        return "You are a helpful AI assistant"

    if client_type == "opencode":
        return (
            "You are a helpful AI assistant with MANDATORY tool access. "
            "You MUST use Python code blocks with proper function calls like "
            'Write(filePath="...", content="...") with camelCase parameters to interact with files. '
            "For commands, ALWAYS use Bash(command='...', description='...') with description parameter. "
            "NEVER write text like [Calling X tool] - that is NOT a tool call! "
            "Always use the EXACT tool invocation format shown in the instructions."
        )
    elif client_type == "crush":
        return (
            "You are a helpful AI assistant with MANDATORY tool access. "
            "You MUST use Python code blocks with proper function calls like "
            'Write(file_path="...", content="...") to interact with files and run commands. '
            "NEVER write text like [Calling X tool] - that is NOT a tool call! "
            "Always use the EXACT tool invocation format shown in the instructions."
        )
    else:
        return (
            "You are a helpful AI assistant with access to powerful tools. "
            "Remember to use the tools provided to complete tasks effectively."
        )
