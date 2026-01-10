"""Pytest configuration for Code Quality MCP Server tests."""

import os
import sys

import pytest

# Add the package to the path for testing
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Also add mcp_core to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "mcp_core"))


@pytest.fixture
def mock_allowed_paths(monkeypatch):
    """Set up allowed paths for testing."""
    monkeypatch.setenv("MCP_CODE_QUALITY_ALLOWED_PATHS", "/tmp,/home,/workspace,/app")
    monkeypatch.setenv("MCP_CODE_QUALITY_AUDIT_LOG", "/tmp/test-audit.log")
    monkeypatch.setenv("MCP_CODE_QUALITY_RATE_LIMIT", "false")


@pytest.fixture
def server(mock_allowed_paths):
    """Create a CodeQualityMCPServer instance for testing."""
    from mcp_code_quality.server import CodeQualityMCPServer

    return CodeQualityMCPServer()
