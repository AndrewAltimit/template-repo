#!/usr/bin/env python3
"""
Gemini Tool Executor Module
Handles tool execution logic for the Gemini proxy wrapper
Separated from the main wrapper for better separation of concerns
"""

import glob as glob_module
import logging
import os
import shlex
import subprocess
from typing import Any, Dict

# Setup logging
logger = logging.getLogger(__name__)

# Configurable output limit for run_command tool (default 100KB, max 10MB for safety)
DEFAULT_MAX_OUTPUT_SIZE = 100 * 1024  # 100KB default
MAX_OUTPUT_SIZE = min(
    int(os.environ.get("GEMINI_MAX_OUTPUT_SIZE", DEFAULT_MAX_OUTPUT_SIZE)), 10 * 1024 * 1024  # 10MB hard limit for safety
)

# Define Gemini tool schemas
GEMINI_TOOLS = {
    "read_file": {
        "name": "read_file",
        "description": "Read contents of a file",
        "parameters": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Path to the file to read"}},
            "required": ["path"],
        },
    },
    "write_file": {
        "name": "write_file",
        "description": "Write content to a file",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file"},
                "content": {"type": "string", "description": "Content to write"},
            },
            "required": ["path", "content"],
        },
    },
    "run_command": {
        "name": "run_command",
        "description": (
            "Execute a system command with arguments. "
            "Note: This does not support shell features like pipes, redirection, or variable expansion"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Command to execute"},
                "timeout": {"type": "number", "description": "Timeout in seconds (default: 30, max: 300)", "default": 30},
            },
            "required": ["command"],
        },
    },
    "list_directory": {
        "name": "list_directory",
        "description": "List contents of a directory",
        "parameters": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Directory path", "default": "."}},
        },
    },
    "search_files": {
        "name": "search_files",
        "description": "Search for files matching a pattern",
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Search pattern or glob"},
                "path": {"type": "string", "description": "Base path to search from", "default": "."},
            },
            "required": ["pattern"],
        },
    },
    "web_search": {
        "name": "web_search",
        "description": "Search the web for information",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Search query"}},
            "required": ["query"],
        },
    },
}


# Tool executor functions
def _execute_read_file(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Execute read_file tool"""
    path = parameters.get("path", "")
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        return {"success": True, "content": content, "path": path}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _execute_write_file(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Execute write_file tool"""
    path = parameters.get("path", "")
    content = parameters.get("content", "")
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return {"success": True, "message": f"Successfully wrote to {path}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _execute_run_command(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Execute run_command tool"""
    command = parameters.get("command", "")
    # Allow configurable timeout (default 30s, max 300s for safety)
    timeout = min(parameters.get("timeout", 30), 300)

    try:
        # Use shlex.split to safely parse the command and prevent shell injection vulnerabilities.
        # This ensures that user input is properly tokenized without invoking a shell interpreter,
        # preventing malicious command chaining or variable expansion attacks.
        cmd_list = shlex.split(command)
        result = subprocess.run(cmd_list, capture_output=True, text=True, timeout=timeout, check=False)

        # Truncate output if it's too large to prevent memory issues
        stdout = result.stdout
        stderr = result.stderr

        if len(stdout) > MAX_OUTPUT_SIZE:
            stdout = stdout[:MAX_OUTPUT_SIZE] + f"\n... (truncated, output was {len(result.stdout)} bytes)"
        if len(stderr) > MAX_OUTPUT_SIZE:
            stderr = stderr[:MAX_OUTPUT_SIZE] + f"\n... (truncated, output was {len(result.stderr)} bytes)"

        return {"success": True, "stdout": stdout, "stderr": stderr, "exit_code": result.returncode}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"Command timed out after {timeout} seconds"}
    except ValueError as e:
        # shlex.split can raise ValueError for unmatched quotes
        return {"success": False, "error": f"Invalid command format: {e}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _execute_list_directory(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Execute list_directory tool"""
    path = parameters.get("path", ".")
    try:
        items = os.listdir(path)
        files = []
        directories = []
        for item in items:
            item_path = os.path.join(path, item)
            if os.path.isdir(item_path):
                directories.append(item)
            else:
                files.append(item)
        return {"success": True, "files": files, "directories": directories, "total": len(items)}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _execute_search_files(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Execute search_files tool"""
    pattern = parameters.get("pattern", "")
    base_path = parameters.get("path", ".")
    try:
        # Use glob to find matching files
        search_pattern = os.path.join(base_path, "**", pattern)
        matches = glob_module.glob(search_pattern, recursive=True)
        return {"success": True, "matches": matches, "count": len(matches)}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _execute_web_search(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Execute web_search tool"""
    query = parameters.get("query", "")
    # Mock web search result
    return {
        "success": True,
        "results": [
            {
                "title": f"Search result for: {query}",
                "snippet": "This is a mock search result. In production, this would connect to a search API.",
                "url": f"https://example.com/search?q={query}",
            }
        ],
    }


# Dictionary-based tool dispatcher for better scalability
TOOL_EXECUTORS = {
    "read_file": _execute_read_file,
    "write_file": _execute_write_file,
    "run_command": _execute_run_command,
    "list_directory": _execute_list_directory,
    "search_files": _execute_search_files,
    "web_search": _execute_web_search,
}


def execute_tool_call(tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a tool call and return the result using dictionary-based dispatch"""

    logger.info("Executing tool: %s with parameters: %s", tool_name, parameters)

    try:
        # Use dictionary dispatcher for better scalability
        executor = TOOL_EXECUTORS.get(tool_name)
        if executor:
            return executor(parameters)
        return {"success": False, "error": f"Unknown tool: {tool_name}"}

    except Exception as e:
        logger.error("Tool execution error: %s", e)
        return {"success": False, "error": str(e)}
