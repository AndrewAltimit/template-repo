#!/usr/bin/env python3
"""
Unit tests for Code Quality MCP Server
"""

import os
import sys
from unittest.mock import Mock, patch

import pytest

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.mcp.code_quality.tools import format_check, lint  # noqa: E402


class TestCodeQualityTools:
    """Test suite for Code Quality MCP tools"""

    @pytest.mark.asyncio
    async def test_format_check_python(self):
        """Test format check for Python files"""
        with patch("subprocess.run") as mock_run:
            # Mock successful format check
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

            result = await format_check(path="test.py", language="python")

            assert result["formatted"] is True
            mock_run.assert_called_once_with(["black", "--check", "test.py"], capture_output=True, text=True)

    @pytest.mark.asyncio
    async def test_format_check_javascript(self):
        """Test format check for JavaScript files"""
        with patch("subprocess.run") as mock_run:
            # Mock successful format check
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

            result = await format_check(path="test.js", language="javascript")

            assert result["formatted"] is True
            mock_run.assert_called_once_with(["prettier", "--check", "test.js"], capture_output=True, text=True)

    @pytest.mark.asyncio
    async def test_format_check_go(self):
        """Test format check for Go files"""
        with patch("subprocess.run") as mock_run:
            # Mock successful format check
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

            result = await format_check(path="test.go", language="go")

            assert result["formatted"] is True
            mock_run.assert_called_once_with(["gofmt", "-l", "test.go"], capture_output=True, text=True)

    @pytest.mark.asyncio
    async def test_format_check_rust(self):
        """Test format check for Rust files"""
        with patch("subprocess.run") as mock_run:
            # Mock successful format check
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

            result = await format_check(path="test.rs", language="rust")

            assert result["formatted"] is True
            mock_run.assert_called_once_with(["rustfmt", "--check", "test.rs"], capture_output=True, text=True)

    @pytest.mark.asyncio
    async def test_format_check_unformatted(self):
        """Test format check with unformatted code"""
        with patch("subprocess.run") as mock_run:
            # Mock unformatted code
            mock_run.return_value = Mock(returncode=1, stdout="File would be reformatted", stderr="")

            result = await format_check(path="test.py", language="python")

            assert result["formatted"] is False
            assert "would be reformatted" in result.get("output", "")

    @pytest.mark.asyncio
    async def test_format_check_unsupported_language(self):
        """Test format check with unsupported language"""
        result = await format_check(path="test.xyz", language="xyz")

        assert "error" in result
        assert "Unsupported language" in result["error"]

    @pytest.mark.asyncio
    async def test_lint_success(self):
        """Test successful linting"""
        with patch("subprocess.run") as mock_run:
            # Mock successful lint
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

            result = await lint(path="test.py")

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

            result = await lint(path="test.py")

            assert result["success"] is False
            assert len(result["issues"]) == 2
            assert "E302" in result["issues"][0]
            assert "E501" in result["issues"][1]

    @pytest.mark.asyncio
    async def test_lint_command_error(self):
        """Test linting with command error"""
        with patch("subprocess.run") as mock_run:
            # Mock command failure
            mock_run.side_effect = Exception("Command not found")

            result = await lint(path="test.py")

            assert "error" in result
            assert "Command not found" in result["error"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
