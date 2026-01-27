#!/usr/bin/env python3
"""Tests for AI Agent MCP tools (Crush, OpenCode)

Note: Codex and Gemini MCP servers have been migrated to Rust and are tested separately.
"""

from unittest.mock import patch

import pytest


class TestToolImports:
    """Test that AI agent MCP tool imports work correctly"""

    def test_crush_tools_import(self):
        """Test that Crush tools can be imported"""
        from mcp_crush.tools import TOOLS as CRUSH_TOOLS

        assert CRUSH_TOOLS is not None
        assert isinstance(CRUSH_TOOLS, dict)
        assert "consult_crush" in CRUSH_TOOLS
        assert "clear_crush_history" in CRUSH_TOOLS
        assert "crush_status" in CRUSH_TOOLS
        assert "toggle_crush_auto_consult" in CRUSH_TOOLS

    def test_opencode_tools_import(self):
        """Test that OpenCode tools can be imported"""
        from mcp_opencode.tools import TOOLS as OPENCODE_TOOLS

        assert OPENCODE_TOOLS is not None
        assert isinstance(OPENCODE_TOOLS, dict)
        assert "consult_opencode" in OPENCODE_TOOLS
        assert "clear_opencode_history" in OPENCODE_TOOLS
        assert "opencode_status" in OPENCODE_TOOLS
        assert "toggle_opencode_auto_consult" in OPENCODE_TOOLS

    # Note: Gemini MCP server has been migrated to Rust and is tested separately
    # Note: Codex MCP server has been migrated to Rust and is tested separately


class TestCrushMCPServer:
    """Tests for Crush MCP Server"""

    def test_server_initialization(self):
        """Test Crush MCP server can be initialized"""
        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "test_key"}):
            from mcp_crush.server import CrushMCPServer

            server = CrushMCPServer()
            assert server.name == "Crush MCP Server"
            assert server.version == "1.1.0"
            assert server.port == 8015

    def test_server_get_tools(self):
        """Test Crush server returns correct tools"""
        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "test_key"}):
            from mcp_crush.server import CrushMCPServer

            server = CrushMCPServer()
            tools = server.get_tools()

            assert "consult_crush" in tools
            assert "clear_crush_history" in tools
            assert "crush_status" in tools
            assert "toggle_crush_auto_consult" in tools

            # Check tool definitions have required fields
            consult_tool = tools["consult_crush"]
            assert "description" in consult_tool
            assert "parameters" in consult_tool

    @pytest.mark.asyncio
    async def test_crush_status(self):
        """Test crush_status returns expected format"""
        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "test_key"}):
            from mcp_crush.server import CrushMCPServer

            server = CrushMCPServer()
            result = await server.crush_status()

            assert "success" in result
            assert result["success"] is True
            assert "status" in result
            assert "enabled" in result["status"]
            assert "auto_consult" in result["status"]

    @pytest.mark.asyncio
    async def test_clear_crush_history(self):
        """Test clear_crush_history returns success"""
        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "test_key"}):
            from mcp_crush.server import CrushMCPServer

            server = CrushMCPServer()
            result = await server.clear_crush_history()

            assert "success" in result
            assert result["success"] is True
            assert "message" in result

    @pytest.mark.asyncio
    async def test_toggle_crush_auto_consult(self):
        """Test toggle_crush_auto_consult works correctly"""
        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "test_key"}):
            from mcp_crush.server import CrushMCPServer

            server = CrushMCPServer()

            # Test disable
            result = await server.toggle_crush_auto_consult(enable=False)
            assert result["success"] is True
            assert result["status"] == "disabled"

            # Test enable
            result = await server.toggle_crush_auto_consult(enable=True)
            assert result["success"] is True
            assert result["status"] == "enabled"

    @pytest.mark.asyncio
    async def test_consult_crush_empty_query(self):
        """Test consult_crush with empty query returns error"""
        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "test_key"}):
            from mcp_crush.server import CrushMCPServer

            server = CrushMCPServer()
            result = await server.consult_crush(query="")

            assert result["success"] is False
            assert "error" in result

    @pytest.mark.asyncio
    async def test_consult_crush_convert_mode_without_context(self):
        """Test consult_crush convert mode requires context"""
        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "test_key"}):
            from mcp_crush.server import CrushMCPServer

            server = CrushMCPServer()
            result = await server.consult_crush(query="code here", mode="convert", context="")

            assert result["success"] is False
            assert "context" in result["error"].lower()


class TestOpenCodeMCPServer:
    """Tests for OpenCode MCP Server"""

    def test_server_initialization(self):
        """Test OpenCode MCP server can be initialized"""
        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "test_key"}):
            from mcp_opencode.server import OpenCodeMCPServer

            server = OpenCodeMCPServer()
            assert server.name == "OpenCode MCP Server"
            assert server.version == "1.1.0"
            assert server.port == 8014

    def test_server_get_tools(self):
        """Test OpenCode server returns correct tools"""
        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "test_key"}):
            from mcp_opencode.server import OpenCodeMCPServer

            server = OpenCodeMCPServer()
            tools = server.get_tools()

            assert "consult_opencode" in tools
            assert "clear_opencode_history" in tools
            assert "opencode_status" in tools
            assert "toggle_opencode_auto_consult" in tools

    @pytest.mark.asyncio
    async def test_opencode_status(self):
        """Test opencode_status returns expected format"""
        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "test_key"}):
            from mcp_opencode.server import OpenCodeMCPServer

            server = OpenCodeMCPServer()
            result = await server.opencode_status()

            assert "success" in result
            assert result["success"] is True
            assert "status" in result

    @pytest.mark.asyncio
    async def test_clear_opencode_history(self):
        """Test clear_opencode_history returns success"""
        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "test_key"}):
            from mcp_opencode.server import OpenCodeMCPServer

            server = OpenCodeMCPServer()
            result = await server.clear_opencode_history()

            assert "success" in result
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_consult_opencode_empty_query(self):
        """Test consult_opencode with empty query returns error"""
        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "test_key"}):
            from mcp_opencode.server import OpenCodeMCPServer

            server = OpenCodeMCPServer()
            result = await server.consult_opencode(query="")

            assert result["success"] is False
            assert "error" in result


# Note: TestGeminiMCPServer removed - Gemini MCP server has been migrated to Rust
# Note: TestCodexMCPServer removed - Codex MCP server has been migrated to Rust


class TestIntegrationMocks:
    """Test that mock integrations work correctly when real integrations are unavailable"""

    def test_crush_mock_integration(self):
        """Test Crush falls back to mock when integration unavailable"""
        with patch.dict("os.environ", {"OPENROUTER_API_KEY": ""}):
            from mcp_crush.server import CrushMCPServer

            server = CrushMCPServer()
            # Server should still initialize with mock
            assert server.crush is not None

    def test_opencode_mock_integration(self):
        """Test OpenCode falls back to mock when integration unavailable"""
        with patch.dict("os.environ", {"OPENROUTER_API_KEY": ""}):
            from mcp_opencode.server import OpenCodeMCPServer

            server = OpenCodeMCPServer()
            # Server should still initialize with mock
            assert server.opencode is not None

    # Note: test_gemini_mock_integration removed - Gemini MCP server is now Rust
    # Note: test_codex_mock_integration removed - Codex MCP server is now Rust


class TestToolModes:
    """Test different consultation modes"""

    @pytest.mark.asyncio
    async def test_crush_explain_mode(self):
        """Test Crush explain mode formatting"""
        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "test_key"}):
            from mcp_crush.server import CrushMCPServer

            server = CrushMCPServer()
            # Test that explain mode is handled (won't actually call API)
            # We just verify the server accepts the mode
            tools = server.get_tools()
            modes = tools["consult_crush"]["parameters"]["properties"]["mode"]["enum"]
            assert "explain" in modes
            assert "generate" in modes
            assert "convert" in modes
            assert "quick" in modes

    @pytest.mark.asyncio
    async def test_opencode_modes(self):
        """Test OpenCode consultation modes"""
        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "test_key"}):
            from mcp_opencode.server import OpenCodeMCPServer

            server = OpenCodeMCPServer()
            tools = server.get_tools()
            modes = tools["consult_opencode"]["parameters"]["properties"]["mode"]["enum"]
            assert "generate" in modes
            assert "refactor" in modes
            assert "review" in modes
            assert "explain" in modes
            assert "quick" in modes


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
