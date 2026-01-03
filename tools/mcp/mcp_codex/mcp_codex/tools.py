"""Codex MCP tools registry"""

# Tool registry - exported for compatibility with CI tests
# Tool functions are implemented and assigned by the MCP server at runtime.
# This registry is for discovery and compatibility with CI checks.
TOOLS = {
    "consult_codex": None,
    "clear_codex_history": None,
    "codex_status": None,
    "toggle_codex_auto_consult": None,
}
