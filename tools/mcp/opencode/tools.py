"""OpenCode MCP tools registry"""

# Tool registry - exported for compatibility with CI tests
# Tool functions are implemented and assigned by the MCP server at runtime.
# This registry is for discovery and compatibility with CI checks.
TOOLS = {
    "consult_opencode": None,
    "clear_opencode_history": None,
    "opencode_status": None,
    "toggle_opencode_auto_consult": None,
}
