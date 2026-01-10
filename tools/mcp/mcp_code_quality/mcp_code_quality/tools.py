"""Code Quality MCP tools registry"""

# Tool registry - exported for compatibility with CI tests
# Tool functions are implemented as methods on CodeQualityMCPServer.
# This registry is for discovery and compatibility with CI checks.
TOOLS = {
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
