#!/usr/bin/env python3
"""
Unit tests for MCP tools
"""

import json
import os
import sys
from unittest.mock import AsyncMock, Mock, patch

import pytest

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.mcp.mcp_server import MCPTools


class TestMCPTools:
    """Test suite for MCP tools"""

    @pytest.mark.asyncio
    async def test_format_check_python(self):
        """Test format check for Python files"""
        with patch("subprocess.run") as mock_run:
            # Mock successful format check
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

            result = await MCPTools.format_check("test.py", "python")

            assert result["formatted"] is True
            mock_run.assert_called_once_with(
                ["black", "--check", "test.py"], capture_output=True, text=True
            )

    @pytest.mark.asyncio
    async def test_format_check_unsupported_language(self):
        """Test format check with unsupported language"""
        result = await MCPTools.format_check("test.xyz", "xyz")

        assert "error" in result
        assert "Unsupported language" in result["error"]

    @pytest.mark.asyncio
    async def test_lint_success(self):
        """Test successful linting"""
        with patch("subprocess.run") as mock_run:
            # Mock successful lint
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

            result = await MCPTools.lint("test.py")

            assert result["success"] is True
            assert result["issues"] == []

    @pytest.mark.asyncio
    async def test_lint_with_issues(self):
        """Test linting with issues"""
        with patch("subprocess.run") as mock_run:
            # Mock lint with issues
            mock_run.return_value = Mock(
                returncode=1,
                stdout="test.py:10:1: E302 expected 2 blank lines\ntest.py:20:80: E501 line too long",
                stderr="",
            )

            result = await MCPTools.lint("test.py")

            assert result["success"] is False
            assert len(result["issues"]) == 2

    @pytest.mark.asyncio
    async def test_compile_latex_pdf(self):
        """Test LaTeX compilation to PDF"""
        with patch("tempfile.TemporaryDirectory") as mock_tmpdir:
            with patch("subprocess.run") as mock_run:
                with patch("os.path.exists") as mock_exists:
                    with patch("shutil.copy") as mock_copy:
                        # Setup mocks
                        mock_tmpdir.return_value.__enter__.return_value = "/tmp/test"
                        mock_run.return_value = Mock(returncode=0)
                        mock_exists.return_value = True

                        # Test compilation
                        latex_content = (
                            r"\documentclass{article}\begin{document}Test\end{document}"
                        )
                        result = await MCPTools.compile_latex(latex_content, "pdf")

                        assert result["success"] is True
                        assert result["format"] == "pdf"
                        assert "output_path" in result

    @pytest.mark.asyncio
    async def test_create_manim_animation(self):
        """Test Manim animation creation"""
        with patch("tempfile.NamedTemporaryFile") as mock_tmp:
            with patch("subprocess.run") as mock_run:
                with patch("os.listdir") as mock_listdir:
                    with patch("os.unlink") as mock_unlink:
                        # Setup mocks
                        mock_tmp.return_value.__enter__.return_value.name = (
                            "/tmp/test.py"
                        )
                        mock_run.return_value = Mock(returncode=0)
                        mock_listdir.return_value = ["TestScene.mp4"]

                        # Test animation
                        script = "from manim import *\nclass TestScene(Scene): pass"
                        result = await MCPTools.create_manim_animation(script)

                        assert result["success"] is True
                        assert result["format"] == "mp4"
                        assert "output_path" in result


class TestMCPServer:
    """Test MCP server endpoints"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        from fastapi.testclient import TestClient

        from tools.mcp.mcp_server import app

        return TestClient(app)

    def test_root_endpoint(self, client):
        """Test root endpoint"""
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert "tools" in data

    def test_health_endpoint(self, client):
        """Test health check"""
        response = client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}

    def test_list_tools(self, client):
        """Test tool listing"""
        response = client.get("/tools")

        assert response.status_code == 200
        tools = response.json()
        assert isinstance(tools, dict)
        assert "format_check" in tools
        assert "lint" in tools
        assert "compile_latex" in tools
        assert "create_manim_animation" in tools

    def test_execute_tool_invalid(self, client):
        """Test executing invalid tool"""
        response = client.post(
            "/tools/execute", json={"tool": "invalid_tool", "arguments": {}}
        )

        assert response.status_code == 404
        assert "Tool not found" in response.json()["detail"]

    @patch("tools.mcp.mcp_server.MCPTools.format_check")
    def test_execute_tool_success(self, mock_format_check, client):
        """Test successful tool execution"""
        # Mock the tool
        mock_format_check.return_value = {"formatted": True}

        response = client.post(
            "/tools/execute",
            json={
                "tool": "format_check",
                "arguments": {"path": "test.py", "language": "python"},
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["result"]["formatted"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
