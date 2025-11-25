"""Crush MCP tools registry"""

# Tool registry - exported for compatibility with CI tests
# Tool functions are implemented and assigned by the MCP server at runtime.
# This registry is for discovery and compatibility with CI checks.
TOOLS = {
    "consult_crush": None,
    "clear_crush_history": None,
    "crush_status": None,
    "toggle_crush_auto_consult": None,
}
