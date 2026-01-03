"""Gemini MCP tools registry"""

# Tool registry - exported for compatibility with CI tests
# Tool functions are implemented and assigned by the MCP server at runtime.
# This registry is for discovery and compatibility with CI checks.
TOOLS = {
    "consult_gemini": None,
    "clear_gemini_history": None,
    "gemini_status": None,
    "toggle_gemini_auto_consult": None,
}
