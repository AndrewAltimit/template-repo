#!/usr/bin/env python3
"""Tests for AI Agent MCP tools

Note: All AI agent MCP servers have been migrated to Rust and are tested separately:
- Codex MCP server: tools/mcp/mcp_codex/
- Gemini MCP server: tools/mcp/mcp_gemini/
- Crush MCP server: tools/mcp/mcp_crush/
- OpenCode MCP server: tools/mcp/mcp_opencode/

Run Rust tests with: cargo test (in each server directory)
"""

import pytest

# Note: TestToolImports removed - OpenCode MCP server has been migrated to Rust
# Note: TestOpenCodeMCPServer removed - OpenCode MCP server has been migrated to Rust
# Note: TestCrushMCPServer removed - Crush MCP server has been migrated to Rust
# Note: TestGeminiMCPServer removed - Gemini MCP server has been migrated to Rust
# Note: TestCodexMCPServer removed - Codex MCP server has been migrated to Rust
# Note: TestIntegrationMocks removed - All AI agent MCP servers are now Rust
# Note: TestToolModes removed - OpenCode MCP server has been migrated to Rust


class TestPlaceholder:
    """Placeholder test class to keep the test file valid.

    All AI agent MCP servers have been migrated to Rust.
    Tests for these servers are now in their respective Cargo.toml workspaces.
    """

    def test_all_ai_agents_migrated_to_rust(self):
        """Verify that all AI agent MCP servers have been migrated to Rust."""
        # This is a placeholder test to document that all AI agent MCP servers
        # have been migrated from Python to Rust for better performance.
        #
        # The Rust implementations are tested via cargo test in their respective
        # directories:
        #   - tools/mcp/mcp_codex/
        #   - tools/mcp/mcp_gemini/
        #   - tools/mcp/mcp_crush/
        #   - tools/mcp/mcp_opencode/
        assert True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
