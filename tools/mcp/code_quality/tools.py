"""Code quality tools for MCP"""

import os  # noqa: F401
import subprocess
from typing import Any, Dict, Optional

# Tool registry
TOOLS = {}


def register_tool(name: str):
    """Decorator to register a tool"""

    def decorator(func):
        TOOLS[name] = func
        return func

    return decorator


@register_tool("format_check")
async def format_check(path: str, language: str, config: Optional[str] = None) -> Dict[str, Any]:
    """Check code formatting"""
    formatters = {
        "python": ["black", "--check"],
        "javascript": ["prettier", "--check"],
        "typescript": ["prettier", "--check"],
        "go": ["gofmt", "-l"],
        "rust": ["rustfmt", "--check"],
    }

    if language not in formatters:
        return {"error": f"Unsupported language: {language}"}

    command = formatters[language] + [path]
    if config:
        command.extend(["--config", config])

    try:
        result = subprocess.run(command, capture_output=True, text=True)
        return {
            "formatted": result.returncode == 0,
            "output": result.stdout + result.stderr,
        }
    except Exception as e:
        return {"error": str(e)}


@register_tool("lint")
async def lint(path: str, config: Optional[str] = None) -> Dict[str, Any]:
    """Run linter on code"""
    linter_command = ["flake8", path]
    if config:
        linter_command.extend(["--config", config])

    try:
        result = subprocess.run(linter_command, capture_output=True, text=True)
        issues = []
        if result.stdout:
            issues = result.stdout.strip().split("\n")

        return {
            "success": result.returncode == 0,
            "issues": issues,
            "output": result.stdout + result.stderr,
        }
    except Exception as e:
        return {"error": str(e)}
