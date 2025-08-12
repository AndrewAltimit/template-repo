#!/usr/bin/env python3
"""
Unit tests for MCPClient
"""

import os
from unittest.mock import Mock, patch

from tools.mcp.core.client import MCPClient


class TestMCPClient:
    """Test suite for MCPClient"""

    def test_init_with_base_url(self):
        """Test initialization with explicit base_url"""
        client = MCPClient(base_url="http://localhost:9999")
        assert client.base_url == "http://localhost:9999"

    def test_init_with_server_name(self):
        """Test initialization with server name"""
        client = MCPClient(server_name="gaea2")
        assert client.base_url == "http://localhost:8007"

    def test_init_with_invalid_server_name(self):
        """Test initialization with invalid server name defaults to code_quality"""
        client = MCPClient(server_name="nonexistent")
        assert client.base_url == "http://localhost:8010"

    def test_init_default(self):
        """Test default initialization"""
        client = MCPClient()
        assert client.base_url == "http://localhost:8010"

    @patch("tools.mcp.core.client.requests.post")
    def test_execute_tool_success(self, mock_post):
        """Test successful tool execution"""
        # Setup mock response
        mock_response = Mock()
        mock_response.json.return_value = {"success": True, "result": {"data": "test"}}
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        # Execute tool
        client = MCPClient(base_url="http://localhost:8010")
        result = client.execute_tool("test_tool", {"param": "value"})

        # Verify
        assert result == {"success": True, "result": {"data": "test"}}
        mock_post.assert_called_once_with(
            "http://localhost:8010/tools/execute",
            json={"tool": "test_tool", "arguments": {"param": "value"}},
        )

    @patch("tools.mcp.core.client.requests.post")
    def test_execute_tool_failure(self, mock_post):
        """Test tool execution with network error"""
        # Setup mock to raise exception
        mock_post.side_effect = Exception("Network error")

        # Execute tool
        client = MCPClient(base_url="http://localhost:8010")
        result = client.execute_tool("test_tool", {"param": "value"})

        # Verify error response
        assert result["success"] is False
        assert "Network error" in result["error"]

    @patch("tools.mcp.core.client.requests.get")
    def test_list_tools_success(self, mock_get):
        """Test successful tool listing"""
        # Setup mock response
        mock_response = Mock()
        mock_response.json.return_value = {"tools": ["tool1", "tool2"]}
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        # List tools
        client = MCPClient(base_url="http://localhost:8010")
        result = client.list_tools()

        # Verify
        assert result == {"tools": ["tool1", "tool2"]}
        mock_get.assert_called_once_with("http://localhost:8010/tools")

    @patch("tools.mcp.core.client.requests.get")
    def test_list_tools_failure(self, mock_get):
        """Test tool listing with network error"""
        # Setup mock to raise exception
        mock_get.side_effect = Exception("Network error")

        # List tools
        client = MCPClient(base_url="http://localhost:8010")
        result = client.list_tools()

        # Verify empty response on error
        assert result == {}

    @patch("tools.mcp.core.client.requests.get")
    def test_health_check_success(self, mock_get):
        """Test successful health check"""
        # Setup mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        # Check health
        client = MCPClient(base_url="http://localhost:8010")
        result = client.health_check()

        # Verify
        assert result is True
        mock_get.assert_called_once_with("http://localhost:8010/health", timeout=5)

    @patch("tools.mcp.core.client.requests.get")
    def test_health_check_failure(self, mock_get):
        """Test health check with server down"""
        # Setup mock response
        mock_response = Mock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response

        # Check health
        client = MCPClient(base_url="http://localhost:8010")
        result = client.health_check()

        # Verify
        assert result is False

    @patch("tools.mcp.core.client.requests.get")
    def test_health_check_timeout(self, mock_get):
        """Test health check with timeout"""
        # Setup mock to raise timeout
        mock_get.side_effect = Exception("Timeout")

        # Check health
        client = MCPClient(base_url="http://localhost:8010")
        result = client.health_check()

        # Verify
        assert result is False

    def test_server_urls(self):
        """Test that all server URLs are configured correctly"""
        expected_servers = {
            "code_quality": "http://localhost:8010",
            "content_creation": "http://localhost:8011",
            "gemini": "http://localhost:8006",
            "gaea2": "http://localhost:8007",
            "ai_toolkit": "http://localhost:8012",
            "comfyui": "http://localhost:8013",
            "opencode": "http://localhost:8014",
            "crush": "http://localhost:8015",
        }

        for server_name, expected_url in expected_servers.items():
            client = MCPClient(server_name=server_name)
            assert client.base_url == expected_url, f"Server {server_name} has wrong URL"

    @patch.dict(os.environ, {"MCP_CODE_QUALITY_URL": "http://custom:9000"})
    def test_environment_variable_override(self):
        """Test that environment variables override default URLs"""
        # Re-import to pick up env var
        import importlib

        import tools.mcp.core.client

        importlib.reload(tools.mcp.core.client)
        from tools.mcp.core.client import MCPClient

        client = MCPClient(server_name="code_quality")
        assert client.base_url == "http://custom:9000"
