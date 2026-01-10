"""Code Quality MCP tools registry.

This module exports a TOOLS dictionary for CI compatibility checks.
The tools are dynamically extracted from CodeQualityMCPServer.get_tools()
to ensure the registry stays in sync with the actual implementation.
"""

from typing import Any, Dict


def _get_tools_from_server() -> Dict[str, Any]:
    """Extract tool names from the server to keep registry in sync."""
    try:
        from mcp_code_quality.server import CodeQualityMCPServer

        server = CodeQualityMCPServer()
        tools: Dict[str, Any] = server.get_tools()
        return tools
    except Exception:
        # Fallback for environments where server can't be instantiated
        return {
            "format_check": None,
            "lint": None,
            "autoformat": None,
            "run_tests": None,
            "type_check": None,
            "security_scan": None,
            "audit_dependencies": None,
            "check_markdown_links": None,
            "get_status": None,
            "get_audit_log": None,
        }


# Tool registry - dynamically populated from server for accuracy
TOOLS = _get_tools_from_server()
