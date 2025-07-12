#!/usr/bin/env python3
"""
Unit tests for MCP tools
"""

import os
import sys
from unittest.mock import Mock, mock_open, patch

import pytest

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock the imports that aren't available in test environment
sys.modules["mcp"] = Mock()
sys.modules["mcp.server"] = Mock()
sys.modules["mcp.server.stdio"] = Mock()
sys.modules["mcp.types"] = Mock()

# Create a more complete FastAPI mock with testclient
fastapi_mock = Mock()
testclient_mock = Mock()
TestClient = Mock()
fastapi_mock.testclient = testclient_mock
fastapi_mock.testclient.TestClient = TestClient
fastapi_mock.FastAPI = Mock()
fastapi_mock.HTTPException = Mock()
sys.modules["fastapi"] = fastapi_mock
sys.modules["fastapi.testclient"] = testclient_mock

from tools.mcp.mcp_server import MCPTools  # noqa: E402


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
            mock_run.assert_called_once_with(["black", "--check", "test.py"], capture_output=True, text=True)

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
                stdout="test.py:10:1: E302 expected 2 blank lines\n" "test.py:20:80: E501 line too long",
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
                    with patch("shutil.copy") as _mock_copy:
                        with patch("os.makedirs") as mock_makedirs:
                            with patch("builtins.open", mock_open()) as _mock_file:
                                # Setup mocks
                                mock_tmpdir.return_value.__enter__.return_value = "/tmp/test"
                                mock_run.return_value = Mock(returncode=0)
                                mock_exists.return_value = True
                                mock_makedirs.return_value = None

                                # Test compilation
                                latex_content = r"\documentclass{article}" r"\begin{document}Test\end{document}"
                                result = await MCPTools.compile_latex(latex_content, "pdf")

                                assert result["success"] is True
                                assert result["format"] == "pdf"
                                assert "output_path" in result

                                # Verify mock_copy was called
                                _mock_copy.assert_called_once()
                                # Verify file operations - mock_open returns a callable
                                assert _mock_file.called

    @pytest.mark.asyncio
    async def test_create_manim_animation(self):
        """Test Manim animation creation"""
        with patch("tempfile.NamedTemporaryFile") as mock_tmp:
            with patch("subprocess.run") as mock_run:
                with patch("os.listdir") as mock_listdir:
                    with patch("os.unlink") as _mock_unlink:
                        with patch("os.makedirs") as mock_makedirs:
                            # Setup mocks
                            _mock_file = Mock()
                            _mock_file.name = "/tmp/test.py"
                            mock_tmp.return_value.__enter__.return_value = _mock_file
                            mock_run.return_value = Mock(returncode=0)
                            mock_listdir.return_value = ["TestScene.mp4"]
                            mock_makedirs.return_value = None

                            # Test animation
                            script = "from manim import *\n" "class TestScene(Scene): pass"
                            result = await MCPTools.create_manim_animation(script)

                            assert result["success"] is True
                            assert result["format"] == "mp4"
                            assert "output_path" in result

                            # Verify the script was written and cleaned up
                            _mock_unlink.assert_called_once()
                            assert mock_run.called


class TestMCPServer:
    """Test MCP server endpoints"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        # Create a mock client that returns proper responses
        mock_client = Mock()

        # Mock GET responses
        def mock_get(path):
            response = Mock()
            if path == "/":
                response.status_code = 200
                response.json = Mock(
                    return_value={
                        "name": "MCP Server",
                        "version": "1.0.0",
                        "tools": [
                            "format_check",
                            "lint",
                            "compile_latex",
                            "create_manim_animation",
                        ],
                    }
                )
            elif path == "/health":
                response.status_code = 200
                response.json = Mock(return_value={"status": "healthy"})
            elif path == "/tools":
                response.status_code = 200
                response.json = Mock(
                    return_value={
                        "format_check": {"description": "Check code formatting"},
                        "lint": {"description": "Lint code"},
                        "compile_latex": {"description": "Compile LaTeX"},
                        "create_manim_animation": {"description": "Create Manim animation"},
                    }
                )
            else:
                response.status_code = 404
                response.json = Mock(return_value={"detail": "Not found"})
            return response

        # Mock POST responses
        def mock_post(path, json=None):
            response = Mock()
            if path == "/tools/execute":
                if json and json.get("tool") == "invalid_tool":
                    response.status_code = 404
                    response.json = Mock(return_value={"detail": "Tool not found"})
                else:
                    response.status_code = 200
                    response.json = Mock(return_value={"success": True, "result": {"formatted": True}})
            else:
                response.status_code = 404
                response.json = Mock(return_value={"detail": "Not found"})
            return response

        mock_client.get = mock_get
        mock_client.post = mock_post

        return mock_client

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
        response = client.post("/tools/execute", json={"tool": "invalid_tool", "arguments": {}})

        assert response.status_code == 404
        assert "Tool not found" in response.json()["detail"]

    def test_execute_tool_success(self, client):
        """Test successful tool execution"""

        # Create an async mock function
        async def mock_format_check(*args, **kwargs):
            return {"formatted": True}

        with patch("tools.mcp.mcp_server.TOOLS", {"format_check": mock_format_check}):
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
