#!/usr/bin/env python3
"""
Unit tests for Code Quality MCP Server

Tests cover:
- Format checking (multiple languages)
- Linting (multiple linters)
- Auto-formatting
- Test running
- Type checking
- Security scanning
- Dependency auditing
- Markdown link checking
- Path validation (security)
- Rate limiting
- Audit logging
- Status endpoint
"""

import json
import subprocess
from unittest.mock import Mock, patch

import pytest


class TestFormatCheck:
    """Tests for format_check tool."""

    @pytest.mark.asyncio
    async def test_format_check_python_success(self, server):
        """Test successful Python format check."""
        with patch.object(server, "_run_subprocess") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

            result = await server.format_check(path="/tmp/test.py", language="python")

            assert result["success"] is True
            assert result["formatted"] is True
            mock_run.assert_called_once()
            assert "black" in mock_run.call_args[0][0]

    @pytest.mark.asyncio
    async def test_format_check_python_unformatted(self, server):
        """Test Python format check with unformatted code."""
        with patch.object(server, "_run_subprocess") as mock_run:
            mock_run.return_value = Mock(returncode=1, stdout="would reformat test.py", stderr="")

            result = await server.format_check(path="/tmp/test.py", language="python")

            assert result["success"] is True
            assert result["formatted"] is False

    @pytest.mark.asyncio
    async def test_format_check_javascript(self, server):
        """Test JavaScript format check uses prettier."""
        with patch.object(server, "_run_subprocess") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

            result = await server.format_check(path="/tmp/test.js", language="javascript")

            assert result["success"] is True
            assert "prettier" in mock_run.call_args[0][0]

    @pytest.mark.asyncio
    async def test_format_check_typescript(self, server):
        """Test TypeScript format check uses prettier."""
        with patch.object(server, "_run_subprocess") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

            result = await server.format_check(path="/tmp/test.ts", language="typescript")

            assert result["success"] is True
            assert "prettier" in mock_run.call_args[0][0]

    @pytest.mark.asyncio
    async def test_format_check_go(self, server):
        """Test Go format check uses gofmt."""
        with patch.object(server, "_run_subprocess") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

            result = await server.format_check(path="/tmp/test.go", language="go")

            assert result["success"] is True
            assert "gofmt" in mock_run.call_args[0][0]

    @pytest.mark.asyncio
    async def test_format_check_rust(self, server):
        """Test Rust format check uses rustfmt."""
        with patch.object(server, "_run_subprocess") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

            result = await server.format_check(path="/tmp/test.rs", language="rust")

            assert result["success"] is True
            assert "rustfmt" in mock_run.call_args[0][0]

    @pytest.mark.asyncio
    async def test_format_check_unsupported_language(self, server):
        """Test format check with unsupported language."""
        result = await server.format_check(path="/tmp/test.xyz", language="xyz")

        assert result["success"] is False
        assert result["error_type"] == "unsupported_language"
        assert "supported_languages" in result

    @pytest.mark.asyncio
    async def test_format_check_tool_not_found(self, server):
        """Test format check when tool is not installed."""
        with patch.object(server, "_run_subprocess") as mock_run:
            mock_run.side_effect = FileNotFoundError()

            result = await server.format_check(path="/tmp/test.py", language="python")

            assert result["success"] is False
            assert result["error_type"] == "tool_not_found"

    @pytest.mark.asyncio
    async def test_format_check_timeout(self, server):
        """Test format check timeout handling."""
        with patch.object(server, "_run_subprocess") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd=["black"], timeout=600)

            result = await server.format_check(path="/tmp/test.py", language="python")

            assert result["success"] is False
            assert result["error_type"] == "timeout"


class TestLint:
    """Tests for lint tool."""

    @pytest.mark.asyncio
    async def test_lint_flake8_success(self, server):
        """Test successful flake8 linting."""
        with patch.object(server, "_run_subprocess") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

            result = await server.lint(path="/tmp/test.py", linter="flake8")

            assert result["success"] is True
            assert result["passed"] is True
            assert result["issue_count"] == 0

    @pytest.mark.asyncio
    async def test_lint_flake8_with_issues(self, server):
        """Test flake8 linting with issues found."""
        with patch.object(server, "_run_subprocess") as mock_run:
            mock_run.return_value = Mock(
                returncode=1,
                stdout="test.py:10:1: E302 expected 2 blank lines\ntest.py:20:80: E501 line too long",
                stderr="",
            )

            result = await server.lint(path="/tmp/test.py", linter="flake8")

            assert result["success"] is True
            assert result["passed"] is False
            assert result["issue_count"] == 2
            assert "E302" in result["issues"][0]
            assert "E501" in result["issues"][1]

    @pytest.mark.asyncio
    async def test_lint_ruff(self, server):
        """Test ruff linting."""
        with patch.object(server, "_run_subprocess") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

            result = await server.lint(path="/tmp/test.py", linter="ruff")

            assert result["success"] is True
            assert "ruff" in mock_run.call_args[0][0]

    @pytest.mark.asyncio
    async def test_lint_eslint(self, server):
        """Test eslint linting."""
        with patch.object(server, "_run_subprocess") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

            result = await server.lint(path="/tmp/test.js", linter="eslint")

            assert result["success"] is True
            assert "eslint" in mock_run.call_args[0][0]

    @pytest.mark.asyncio
    async def test_lint_with_config(self, server):
        """Test linting with config file."""
        with patch.object(server, "_run_subprocess") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

            result = await server.lint(path="/tmp/test.py", linter="flake8", config="/tmp/.flake8")

            assert result["success"] is True
            cmd = mock_run.call_args[0][0]
            assert "--config" in cmd
            assert "/tmp/.flake8" in cmd

    @pytest.mark.asyncio
    async def test_lint_unsupported_linter(self, server):
        """Test lint with unsupported linter."""
        result = await server.lint(path="/tmp/test.py", linter="unknown")

        assert result["success"] is False
        assert result["error_type"] == "unsupported_linter"


class TestAutoformat:
    """Tests for autoformat tool."""

    @pytest.mark.asyncio
    async def test_autoformat_python(self, server):
        """Test Python auto-formatting."""
        with patch.object(server, "_run_subprocess") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="reformatted test.py", stderr="")

            result = await server.autoformat(path="/tmp/test.py", language="python")

            assert result["success"] is True
            assert result["formatted"] is True
            assert "black" in mock_run.call_args[0][0]

    @pytest.mark.asyncio
    async def test_autoformat_javascript(self, server):
        """Test JavaScript auto-formatting."""
        with patch.object(server, "_run_subprocess") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

            result = await server.autoformat(path="/tmp/test.js", language="javascript")

            assert result["success"] is True
            cmd = mock_run.call_args[0][0]
            assert "prettier" in cmd
            assert "--write" in cmd


class TestRunTests:
    """Tests for run_tests tool."""

    @pytest.mark.asyncio
    async def test_run_tests_success(self, server):
        """Test successful test run."""
        with patch.object(server, "_run_subprocess") as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout="===== 10 passed =====",
                stderr="",
            )

            result = await server.run_tests(path="/tmp/tests/")

            assert result["success"] is True
            assert result["passed"] is True
            assert "pytest" in mock_run.call_args[0][0]

    @pytest.mark.asyncio
    async def test_run_tests_with_failures(self, server):
        """Test run with test failures."""
        with patch.object(server, "_run_subprocess") as mock_run:
            mock_run.return_value = Mock(
                returncode=1,
                stdout="===== 2 failed, 8 passed =====",
                stderr="",
            )

            result = await server.run_tests(path="/tmp/tests/")

            assert result["success"] is True
            assert result["passed"] is False
            assert result["returncode"] == 1

    @pytest.mark.asyncio
    async def test_run_tests_with_coverage(self, server):
        """Test run with coverage enabled."""
        with patch.object(server, "_run_subprocess") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

            result = await server.run_tests(path="/tmp/tests/", coverage=True)

            assert result["success"] is True
            cmd = mock_run.call_args[0][0]
            assert "--cov=." in cmd

    @pytest.mark.asyncio
    async def test_run_tests_with_verbose(self, server):
        """Test run with verbose output."""
        with patch.object(server, "_run_subprocess") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

            result = await server.run_tests(path="/tmp/tests/", verbose=True)

            assert result["success"] is True
            assert "-v" in mock_run.call_args[0][0]

    @pytest.mark.asyncio
    async def test_run_tests_fail_fast(self, server):
        """Test run with fail fast option."""
        with patch.object(server, "_run_subprocess") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

            result = await server.run_tests(path="/tmp/tests/", fail_fast=True)

            assert result["success"] is True
            assert "-x" in mock_run.call_args[0][0]

    @pytest.mark.asyncio
    async def test_run_tests_with_markers(self, server):
        """Test run with marker expression."""
        with patch.object(server, "_run_subprocess") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

            result = await server.run_tests(path="/tmp/tests/", markers="not slow")

            assert result["success"] is True
            cmd = mock_run.call_args[0][0]
            assert "-m" in cmd
            assert "not slow" in cmd


class TestTypeCheck:
    """Tests for type_check tool."""

    @pytest.mark.asyncio
    async def test_type_check_success(self, server):
        """Test successful type check."""
        with patch.object(server, "_run_subprocess") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="Success: no issues found", stderr="")

            result = await server.type_check(path="/tmp/test.py")

            assert result["success"] is True
            assert result["passed"] is True
            assert "ty" in mock_run.call_args[0][0]

    @pytest.mark.asyncio
    async def test_type_check_with_errors(self, server):
        """Test type check with errors."""
        with patch.object(server, "_run_subprocess") as mock_run:
            mock_run.return_value = Mock(
                returncode=1,
                stdout='test.py:10: error: Argument 1 has incompatible type "str"; expected "int"',
                stderr="",
            )

            result = await server.type_check(path="/tmp/test.py")

            assert result["success"] is True
            assert result["passed"] is False
            assert result["issue_count"] == 1

    @pytest.mark.asyncio
    async def test_type_check_strict_mode(self, server):
        """Test type check with strict mode."""
        with patch.object(server, "_run_subprocess") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

            result = await server.type_check(path="/tmp/test.py", strict=True)

            assert result["success"] is True
            assert "--strict" in mock_run.call_args[0][0]


class TestSecurityScan:
    """Tests for security_scan tool."""

    @pytest.mark.asyncio
    async def test_security_scan_success(self, server):
        """Test successful security scan with no findings."""
        with patch.object(server, "_run_subprocess") as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout='{"results": []}',
                stderr="",
            )

            result = await server.security_scan(path="/tmp/test.py")

            assert result["success"] is True
            assert result["passed"] is True
            assert result["finding_count"] == 0
            assert "bandit" in mock_run.call_args[0][0]

    @pytest.mark.asyncio
    async def test_security_scan_with_findings(self, server):
        """Test security scan with findings."""
        findings = [
            {"severity": "HIGH", "confidence": "HIGH", "issue_text": "Hardcoded password"},
            {"severity": "MEDIUM", "confidence": "MEDIUM", "issue_text": "Possible SQL injection"},
        ]
        with patch.object(server, "_run_subprocess") as mock_run:
            mock_run.return_value = Mock(
                returncode=1,
                stdout=json.dumps({"results": findings}),
                stderr="",
            )

            result = await server.security_scan(path="/tmp/test.py")

            assert result["success"] is True
            assert result["passed"] is False
            assert result["finding_count"] == 2

    @pytest.mark.asyncio
    async def test_security_scan_severity_filter(self, server):
        """Test security scan with severity filter."""
        with patch.object(server, "_run_subprocess") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout='{"results": []}', stderr="")

            result = await server.security_scan(path="/tmp/test.py", severity="high")

            assert result["success"] is True
            cmd = mock_run.call_args[0][0]
            assert "--severity-level=high" in cmd  # high severity


class TestAuditDependencies:
    """Tests for audit_dependencies tool."""

    @pytest.mark.asyncio
    async def test_audit_dependencies_success(self, server):
        """Test successful dependency audit with no vulnerabilities."""
        with patch.object(server, "_run_subprocess") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="[]", stderr="")

            result = await server.audit_dependencies(requirements_file="/tmp/requirements.txt")

            assert result["success"] is True
            assert result["passed"] is True
            assert result["vulnerability_count"] == 0
            assert "pip-audit" in mock_run.call_args[0][0]

    @pytest.mark.asyncio
    async def test_audit_dependencies_with_vulnerabilities(self, server):
        """Test dependency audit with vulnerabilities found."""
        vulns = [{"name": "requests", "version": "2.20.0", "vulns": ["CVE-2023-1234"]}]
        with patch.object(server, "_run_subprocess") as mock_run:
            mock_run.return_value = Mock(returncode=1, stdout=json.dumps(vulns), stderr="")

            result = await server.audit_dependencies(requirements_file="/tmp/requirements.txt")

            assert result["success"] is True
            assert result["passed"] is False
            assert result["vulnerability_count"] == 1


class TestPathValidation:
    """Tests for path validation security feature."""

    @pytest.mark.asyncio
    async def test_path_not_allowed(self, server):
        """Test that paths outside allowed directories are rejected."""
        # /etc is not in allowed paths
        result = await server.format_check(path="/etc/passwd", language="python")

        assert result["success"] is False
        assert result["error_type"] == "path_validation"
        assert "allowed_paths" in result

    @pytest.mark.asyncio
    async def test_path_allowed(self, server):
        """Test that paths in allowed directories are accepted."""
        with patch.object(server, "_run_subprocess") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

            # /tmp is in allowed paths from fixture
            result = await server.format_check(path="/tmp/test.py", language="python")

            assert result["success"] is True


class TestRateLimiting:
    """Tests for rate limiting feature."""

    @pytest.mark.asyncio
    async def test_rate_limit_enforcement(self, monkeypatch):
        """Test that rate limiting is enforced."""
        from mcp_code_quality.server import CodeQualityMCPServer

        monkeypatch.setenv("MCP_CODE_QUALITY_ALLOWED_PATHS", "/tmp")
        monkeypatch.setenv("MCP_CODE_QUALITY_AUDIT_LOG", "/tmp/test-audit.log")
        monkeypatch.setenv("MCP_CODE_QUALITY_RATE_LIMIT", "true")

        server = CodeQualityMCPServer()

        # Manually fill up the rate limit tracker
        import time

        server._rate_limit_tracker["format_check"] = [time.time() for _ in range(100)]

        result = await server.format_check(path="/tmp/test.py", language="python")

        assert result["success"] is False
        assert result["error_type"] == "rate_limit"

    @pytest.mark.asyncio
    async def test_rate_limit_disabled(self, server):
        """Test that rate limiting can be disabled."""
        # Rate limiting is disabled via fixture
        with patch.object(server, "_run_subprocess") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

            # Should work even with many calls
            for _ in range(10):
                result = await server.format_check(path="/tmp/test.py", language="python")
                assert result["success"] is True


class TestAuditLog:
    """Tests for audit logging feature."""

    @pytest.mark.asyncio
    async def test_audit_log_written(self, server, tmp_path):
        """Test that operations are logged to audit log."""
        audit_path = tmp_path / "audit.log"
        server.audit_log_path = audit_path

        with patch.object(server, "_run_subprocess") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

            await server.format_check(path="/tmp/test.py", language="python")

        # Check audit log was written
        assert audit_path.exists()
        content = audit_path.read_text()
        entry = json.loads(content.strip())
        assert entry["operation"] == "format_check"
        assert entry["path"] == "/tmp/test.py"
        assert entry["success"] is True

    @pytest.mark.asyncio
    async def test_get_audit_log(self, server, tmp_path):
        """Test retrieving audit log entries."""
        audit_path = tmp_path / "audit.log"
        server.audit_log_path = audit_path

        # Write some entries
        entries = [
            {"timestamp": "2024-01-01T00:00:00Z", "operation": "format_check", "path": "/tmp/a.py", "success": True},
            {"timestamp": "2024-01-01T00:01:00Z", "operation": "lint", "path": "/tmp/b.py", "success": False},
        ]
        with open(audit_path, "w") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")

        result = await server.get_audit_log(limit=10)

        assert result["success"] is True
        assert result["count"] == 2

    @pytest.mark.asyncio
    async def test_get_audit_log_filtered(self, server, tmp_path):
        """Test retrieving filtered audit log entries."""
        audit_path = tmp_path / "audit.log"
        server.audit_log_path = audit_path

        entries = [
            {"timestamp": "2024-01-01T00:00:00Z", "operation": "format_check", "path": "/tmp/a.py", "success": True},
            {"timestamp": "2024-01-01T00:01:00Z", "operation": "lint", "path": "/tmp/b.py", "success": False},
        ]
        with open(audit_path, "w") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")

        result = await server.get_audit_log(limit=10, operation="lint")

        assert result["success"] is True
        assert result["count"] == 1
        assert result["entries"][0]["operation"] == "lint"


class TestGetStatus:
    """Tests for get_status endpoint."""

    @pytest.mark.asyncio
    async def test_get_status(self, server):
        """Test status endpoint returns expected information."""
        with patch.object(server, "_run_subprocess") as mock_run:
            # Mock tool version checks
            mock_run.return_value = Mock(returncode=0, stdout="black, 24.1.0", stderr="")

            result = await server.get_status()

            assert result["server"] == "Code Quality MCP Server"
            assert result["version"] == "2.0.0"
            assert "timeout_seconds" in result
            assert "allowed_paths" in result
            assert "tools" in result


class TestToolSchemas:
    """Tests for tool schema definitions."""

    def test_get_tools_returns_all_tools(self, server):
        """Test that get_tools returns all expected tools."""
        tools = server.get_tools()

        expected_tools = [
            "format_check",
            "lint",
            "autoformat",
            "run_tests",
            "type_check",
            "security_scan",
            "audit_dependencies",
            "check_markdown_links",
            "get_status",
            "get_audit_log",
        ]

        for tool_name in expected_tools:
            assert tool_name in tools
            assert "description" in tools[tool_name]
            assert "parameters" in tools[tool_name]

    def test_tool_schemas_have_required_fields(self, server):
        """Test that tool schemas have proper structure."""
        tools = server.get_tools()

        for tool_name, tool_def in tools.items():
            assert "description" in tool_def, f"{tool_name} missing description"
            assert "parameters" in tool_def, f"{tool_name} missing parameters"
            assert tool_def["parameters"]["type"] == "object", f"{tool_name} parameters not object type"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
