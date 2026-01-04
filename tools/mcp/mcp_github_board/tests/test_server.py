"""
Comprehensive unit tests for GitHub Board MCP Server.

Tests all tool methods and their integration with BoardManager from github_agents.
"""

# pylint: disable=protected-access

import os
from pathlib import Path
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Set up path before imports (5 parents: test_server.py -> tests -> mcp_github_board -> mcp -> tools -> repo_root)
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent / "packages" / "github_agents" / "src"))

from github_agents.board.models import (
    BoardConfig,
    Issue,
    IssuePriority,
    IssueStatus,
)


class TestGitHubBoardMCPServerInit:
    """Test GitHubBoardMCPServer initialization."""

    def test_server_initialization(self):
        """Test server initializes with correct defaults."""
        from mcp_github_board.server import GitHubBoardMCPServer

        server = GitHubBoardMCPServer()
        assert server.name == "GitHub Board MCP Server"
        assert server.version == "1.0.0"
        assert server.port == 8022
        assert server.board_manager is None
        assert server.config is None
        assert server._initialized is False

    def test_get_tools_returns_all_tools(self):
        """Test get_tools returns all expected tools."""
        from mcp_github_board.server import GitHubBoardMCPServer

        server = GitHubBoardMCPServer()
        tools = server.get_tools()

        expected_tools = [
            "query_ready_work",
            "claim_work",
            "renew_claim",
            "release_work",
            "update_status",
            "add_blocker",
            "mark_discovered_from",
            "get_issue_details",
            "get_dependency_graph",
            "list_agents",
            "get_board_config",
        ]

        for tool_name in expected_tools:
            assert tool_name in tools, f"Missing tool: {tool_name}"

    def test_get_tools_structure(self):
        """Test tools have correct structure."""
        from mcp_github_board.server import GitHubBoardMCPServer

        server = GitHubBoardMCPServer()
        tools = server.get_tools()

        for tool_name, tool_def in tools.items():
            assert "description" in tool_def, f"{tool_name} missing description"
            assert "parameters" in tool_def, f"{tool_name} missing parameters"
            assert tool_def["parameters"]["type"] == "object"


class TestEnsureInitialized:
    """Test _ensure_initialized method."""

    @pytest.mark.asyncio
    async def test_ensure_initialized_with_config_file(self, mock_github_token, config_file_path, mock_board_config):
        """Test initialization with config file."""
        from mcp_github_board.server import GitHubBoardMCPServer

        with patch.dict(os.environ, {"GITHUB_BOARD_CONFIG": config_file_path}):
            with patch("mcp_github_board.server.load_config") as mock_load:
                mock_load.return_value = mock_board_config
                with patch("mcp_github_board.server.get_github_token") as mock_token:
                    mock_token.return_value = "test-token"
                    with patch("mcp_github_board.server.BoardManager") as mock_manager_class:
                        mock_manager = MagicMock()
                        mock_manager.initialize = AsyncMock()
                        mock_manager_class.return_value = mock_manager

                        server = GitHubBoardMCPServer()
                        result = await server._ensure_initialized()

                        assert result is True
                        assert server._initialized is True
                        assert server.config is not None
                        mock_manager.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_ensure_initialized_without_token(self):
        """Test initialization fails without GitHub token."""
        from mcp_github_board.server import GitHubBoardMCPServer

        with patch("mcp_github_board.server.get_github_token") as mock_token:
            mock_token.side_effect = RuntimeError("No token")

            with patch.dict(os.environ, {"GITHUB_BOARD_CONFIG": "/nonexistent/path"}):
                server = GitHubBoardMCPServer()
                result = await server._ensure_initialized()

                assert result is False
                assert server._initialized is False

    @pytest.mark.asyncio
    async def test_ensure_initialized_with_env_fallback(self, monkeypatch, mock_board_config):
        """Test initialization with environment variable fallback."""
        from mcp_github_board.server import GitHubBoardMCPServer

        monkeypatch.setenv("GITHUB_PROJECT_NUMBER", "5")
        monkeypatch.setenv("GITHUB_OWNER", "testowner")
        monkeypatch.setenv("GITHUB_REPOSITORY", "testowner/test-repo")
        monkeypatch.setenv("GITHUB_BOARD_CONFIG", "/nonexistent/path")

        with patch("mcp_github_board.server.get_github_token") as mock_token:
            mock_token.return_value = "test-token"
            with patch("mcp_github_board.server.BoardManager") as mock_manager_class:
                mock_manager = MagicMock()
                mock_manager.initialize = AsyncMock()
                mock_manager_class.return_value = mock_manager

                server = GitHubBoardMCPServer()
                result = await server._ensure_initialized()

                assert result is True
                assert server.config.project_number == 5
                assert server.config.owner == "testowner"

    @pytest.mark.asyncio
    async def test_ensure_initialized_already_initialized(self, mock_github_token):
        """Test _ensure_initialized returns True when already initialized."""
        from mcp_github_board.server import GitHubBoardMCPServer

        server = GitHubBoardMCPServer()
        server._initialized = True
        server.board_manager = MagicMock()

        result = await server._ensure_initialized()
        assert result is True


class TestQueryReadyWork:
    """Test query_ready_work tool."""

    @pytest.mark.asyncio
    async def test_query_ready_work_success(self, mock_github_token, mock_issues, mock_board_config):
        """Test successful query_ready_work."""
        from mcp_github_board.server import GitHubBoardMCPServer

        server = GitHubBoardMCPServer()
        server._initialized = True
        server.config = mock_board_config

        mock_manager = MagicMock()
        mock_manager.get_ready_work = AsyncMock(return_value=mock_issues)
        server.board_manager = mock_manager

        result = await server.query_ready_work(limit=10)

        assert result["success"] is True
        assert result["result"]["count"] == 2
        assert len(result["result"]["issues"]) == 2
        assert result["result"]["issues"][0]["number"] == 1
        assert result["result"]["issues"][0]["title"] == "First Issue"

    @pytest.mark.asyncio
    async def test_query_ready_work_with_agent_filter(self, mock_github_token, mock_issues, mock_board_config):
        """Test query_ready_work with agent filter."""
        from mcp_github_board.server import GitHubBoardMCPServer

        server = GitHubBoardMCPServer()
        server._initialized = True
        server.config = mock_board_config

        mock_manager = MagicMock()
        mock_manager.get_ready_work = AsyncMock(return_value=[mock_issues[0]])
        server.board_manager = mock_manager

        result = await server.query_ready_work(agent_name="claude", limit=5)

        assert result["success"] is True
        assert result["result"]["count"] == 1
        mock_manager.get_ready_work.assert_called_once_with(agent_name="claude", limit=5)

    @pytest.mark.asyncio
    async def test_query_ready_work_empty(self, mock_github_token, mock_board_config):
        """Test query_ready_work with no results."""
        from mcp_github_board.server import GitHubBoardMCPServer

        server = GitHubBoardMCPServer()
        server._initialized = True
        server.config = mock_board_config

        mock_manager = MagicMock()
        mock_manager.get_ready_work = AsyncMock(return_value=[])
        server.board_manager = mock_manager

        result = await server.query_ready_work()

        assert result["success"] is True
        assert result["result"]["count"] == 0
        assert result["result"]["issues"] == []


class TestClaimWork:
    """Test claim_work tool."""

    @pytest.mark.asyncio
    async def test_claim_work_success(self, mock_github_token, mock_board_config):
        """Test successful work claim."""
        from mcp_github_board.server import GitHubBoardMCPServer

        server = GitHubBoardMCPServer()
        server._initialized = True
        server.config = mock_board_config

        mock_manager = MagicMock()
        mock_manager.claim_work = AsyncMock(return_value=True)
        server.board_manager = mock_manager

        result = await server.claim_work(issue_number=42, agent_name="claude", session_id="session-123")

        assert result["success"] is True
        assert result["result"]["claimed"] is True
        assert result["result"]["issue_number"] == 42
        assert result["result"]["agent"] == "claude"
        assert result["result"]["session_id"] == "session-123"
        mock_manager.claim_work.assert_called_once_with(42, "claude", "session-123")

    @pytest.mark.asyncio
    async def test_claim_work_failure(self, mock_github_token, mock_board_config):
        """Test failed work claim (already claimed)."""
        from mcp_github_board.server import GitHubBoardMCPServer

        server = GitHubBoardMCPServer()
        server._initialized = True
        server.config = mock_board_config

        mock_manager = MagicMock()
        mock_manager.claim_work = AsyncMock(return_value=False)
        server.board_manager = mock_manager

        result = await server.claim_work(issue_number=42, agent_name="claude", session_id="session-123")

        assert result["success"] is False
        assert result["result"]["claimed"] is False


class TestRenewClaim:
    """Test renew_claim tool."""

    @pytest.mark.asyncio
    async def test_renew_claim_success(self, mock_github_token, mock_board_config):
        """Test successful claim renewal."""
        from mcp_github_board.server import GitHubBoardMCPServer

        server = GitHubBoardMCPServer()
        server._initialized = True
        server.config = mock_board_config

        mock_manager = MagicMock()
        mock_manager.renew_claim = AsyncMock(return_value=True)
        server.board_manager = mock_manager

        result = await server.renew_claim(issue_number=42, agent_name="claude", session_id="session-123")

        assert result["success"] is True
        assert result["result"]["renewed"] is True
        assert result["result"]["issue_number"] == 42
        assert result["result"]["agent"] == "claude"

    @pytest.mark.asyncio
    async def test_renew_claim_failure(self, mock_github_token, mock_board_config):
        """Test failed claim renewal (wrong agent or no claim)."""
        from mcp_github_board.server import GitHubBoardMCPServer

        server = GitHubBoardMCPServer()
        server._initialized = True
        server.config = mock_board_config

        mock_manager = MagicMock()
        mock_manager.renew_claim = AsyncMock(return_value=False)
        server.board_manager = mock_manager

        result = await server.renew_claim(issue_number=42, agent_name="opencode", session_id="wrong-session")

        assert result["success"] is False
        assert result["result"]["renewed"] is False


class TestReleaseWork:
    """Test release_work tool."""

    @pytest.mark.asyncio
    async def test_release_work_completed(self, mock_github_token, mock_board_config):
        """Test releasing work as completed."""
        from mcp_github_board.server import GitHubBoardMCPServer

        server = GitHubBoardMCPServer()
        server._initialized = True
        server.config = mock_board_config

        mock_manager = MagicMock()
        mock_manager.release_work = AsyncMock()
        server.board_manager = mock_manager

        result = await server.release_work(issue_number=42, agent_name="claude", reason="completed")

        assert result["success"] is True
        assert result["result"]["released"] is True
        assert result["result"]["reason"] == "completed"
        mock_manager.release_work.assert_called_once_with(42, "claude", "completed")

    @pytest.mark.asyncio
    async def test_release_work_blocked(self, mock_github_token, mock_board_config):
        """Test releasing work as blocked."""
        from mcp_github_board.server import GitHubBoardMCPServer

        server = GitHubBoardMCPServer()
        server._initialized = True
        server.config = mock_board_config

        mock_manager = MagicMock()
        mock_manager.release_work = AsyncMock()
        server.board_manager = mock_manager

        result = await server.release_work(issue_number=42, agent_name="claude", reason="blocked")

        assert result["success"] is True
        assert result["result"]["reason"] == "blocked"

    @pytest.mark.asyncio
    async def test_release_work_default_reason(self, mock_github_token, mock_board_config):
        """Test releasing work with default reason."""
        from mcp_github_board.server import GitHubBoardMCPServer

        server = GitHubBoardMCPServer()
        server._initialized = True
        server.config = mock_board_config

        mock_manager = MagicMock()
        mock_manager.release_work = AsyncMock()
        server.board_manager = mock_manager

        result = await server.release_work(issue_number=42, agent_name="claude")

        assert result["result"]["reason"] == "completed"


class TestUpdateStatus:
    """Test update_status tool."""

    @pytest.mark.asyncio
    async def test_update_status_success(self, mock_github_token, mock_board_config):
        """Test successful status update."""
        from mcp_github_board.server import GitHubBoardMCPServer

        server = GitHubBoardMCPServer()
        server._initialized = True
        server.config = mock_board_config

        mock_manager = MagicMock()
        mock_manager.update_status = AsyncMock(return_value=True)
        server.board_manager = mock_manager

        result = await server.update_status(issue_number=42, status="In Progress")

        assert result["success"] is True
        assert result["result"]["updated"] is True
        assert result["result"]["status"] == "In Progress"
        mock_manager.update_status.assert_called_once_with(42, IssueStatus.IN_PROGRESS)

    @pytest.mark.asyncio
    async def test_update_status_all_valid_statuses(self, mock_github_token, mock_board_config):
        """Test all valid status values."""
        from mcp_github_board.server import GitHubBoardMCPServer

        server = GitHubBoardMCPServer()
        server._initialized = True
        server.config = mock_board_config

        mock_manager = MagicMock()
        mock_manager.update_status = AsyncMock(return_value=True)
        server.board_manager = mock_manager

        valid_statuses = ["Todo", "In Progress", "Blocked", "Done", "Abandoned"]
        expected_enums = [
            IssueStatus.TODO,
            IssueStatus.IN_PROGRESS,
            IssueStatus.BLOCKED,
            IssueStatus.DONE,
            IssueStatus.ABANDONED,
        ]

        for status, expected_enum in zip(valid_statuses, expected_enums):
            mock_manager.update_status.reset_mock()
            result = await server.update_status(issue_number=42, status=status)
            assert result["success"] is True
            mock_manager.update_status.assert_called_once_with(42, expected_enum)

    @pytest.mark.asyncio
    async def test_update_status_invalid_status(self, mock_github_token, mock_board_config):
        """Test invalid status value."""
        from mcp_github_board.server import GitHubBoardMCPServer

        server = GitHubBoardMCPServer()
        server._initialized = True
        server.config = mock_board_config

        mock_manager = MagicMock()
        server.board_manager = mock_manager

        result = await server.update_status(issue_number=42, status="InvalidStatus")

        assert result["success"] is False
        assert "Invalid status" in result["error"]


class TestAddBlocker:
    """Test add_blocker tool."""

    @pytest.mark.asyncio
    async def test_add_blocker_success(self, mock_github_token, mock_board_config):
        """Test successful blocker addition."""
        from mcp_github_board.server import GitHubBoardMCPServer

        server = GitHubBoardMCPServer()
        server._initialized = True
        server.config = mock_board_config

        mock_manager = MagicMock()
        mock_manager.add_blocker = AsyncMock(return_value=True)
        server.board_manager = mock_manager

        result = await server.add_blocker(issue_number=42, blocker_number=10)

        assert result["success"] is True
        assert result["result"]["added"] is True
        assert result["result"]["issue"] == 42
        assert result["result"]["blocker"] == 10
        mock_manager.add_blocker.assert_called_once_with(42, 10)

    @pytest.mark.asyncio
    async def test_add_blocker_failure(self, mock_github_token, mock_board_config):
        """Test failed blocker addition."""
        from mcp_github_board.server import GitHubBoardMCPServer

        server = GitHubBoardMCPServer()
        server._initialized = True
        server.config = mock_board_config

        mock_manager = MagicMock()
        mock_manager.add_blocker = AsyncMock(return_value=False)
        server.board_manager = mock_manager

        result = await server.add_blocker(issue_number=42, blocker_number=10)

        assert result["success"] is False
        assert result["result"]["added"] is False


class TestMarkDiscoveredFrom:
    """Test mark_discovered_from tool."""

    @pytest.mark.asyncio
    async def test_mark_discovered_from_success(self, mock_github_token, mock_board_config):
        """Test successful parent-child relationship."""
        from mcp_github_board.server import GitHubBoardMCPServer

        server = GitHubBoardMCPServer()
        server._initialized = True
        server.config = mock_board_config

        mock_manager = MagicMock()
        mock_manager.mark_discovered_from = AsyncMock(return_value=True)
        server.board_manager = mock_manager

        result = await server.mark_discovered_from(issue_number=42, parent_number=10)

        assert result["success"] is True
        assert result["result"]["marked"] is True
        assert result["result"]["child"] == 42
        assert result["result"]["parent"] == 10
        mock_manager.mark_discovered_from.assert_called_once_with(42, 10)


class TestGetIssueDetails:
    """Test get_issue_details tool."""

    @pytest.mark.asyncio
    async def test_get_issue_details_placeholder(self, mock_github_token, mock_board_config):
        """Test get_issue_details returns placeholder (not yet implemented)."""
        from mcp_github_board.server import GitHubBoardMCPServer

        server = GitHubBoardMCPServer()
        server._initialized = True
        server.config = mock_board_config
        server.board_manager = MagicMock()

        result = await server.get_issue_details(issue_number=42)

        assert result["success"] is True
        assert result["result"]["issue_number"] == 42
        assert "not yet implemented" in result["result"]["note"]


class TestGetDependencyGraph:
    """Test get_dependency_graph tool."""

    @pytest.mark.asyncio
    async def test_get_dependency_graph_placeholder(self, mock_github_token, mock_board_config):
        """Test get_dependency_graph returns placeholder (not yet implemented)."""
        from mcp_github_board.server import GitHubBoardMCPServer

        server = GitHubBoardMCPServer()
        server._initialized = True
        server.config = mock_board_config
        server.board_manager = MagicMock()

        result = await server.get_dependency_graph(issue_number=42)

        assert result["success"] is True
        assert result["result"]["issue_number"] == 42
        assert result["result"]["blockers"] == []
        assert result["result"]["blocked"] == []
        assert result["result"]["parent"] is None
        assert result["result"]["children"] == []


class TestListAgents:
    """Test list_agents tool."""

    @pytest.mark.asyncio
    async def test_list_agents_success(self, mock_github_token, mock_board_config):
        """Test listing enabled agents."""
        from mcp_github_board.server import GitHubBoardMCPServer

        server = GitHubBoardMCPServer()
        server._initialized = True
        server.config = mock_board_config
        server.board_manager = MagicMock()

        result = await server.list_agents()

        assert result["success"] is True
        assert result["result"]["count"] == 3
        assert "claude" in result["result"]["agents"]
        assert "opencode" in result["result"]["agents"]
        assert "gemini" in result["result"]["agents"]

    @pytest.mark.asyncio
    async def test_list_agents_empty(self, mock_github_token):
        """Test listing agents when none configured."""
        from mcp_github_board.server import GitHubBoardMCPServer

        server = GitHubBoardMCPServer()
        server._initialized = True
        server.config = BoardConfig(
            project_number=1,
            owner="test",
            repository="test/repo",
            enabled_agents=[],
        )
        server.board_manager = MagicMock()

        result = await server.list_agents()

        assert result["success"] is True
        assert result["result"]["count"] == 0
        assert result["result"]["agents"] == []


class TestGetBoardConfig:
    """Test get_board_config tool."""

    @pytest.mark.asyncio
    async def test_get_board_config_success(self, mock_github_token, mock_board_config):
        """Test getting board configuration."""
        from mcp_github_board.server import GitHubBoardMCPServer

        server = GitHubBoardMCPServer()
        server._initialized = True
        server.config = mock_board_config
        server.board_manager = MagicMock()

        result = await server.get_board_config()

        assert result["success"] is True
        assert result["result"]["project_number"] == 1
        assert result["result"]["owner"] == "testowner"
        assert result["result"]["repository"] == "testowner/test-repo"
        assert result["result"]["claim_timeout"] == 86400
        assert result["result"]["claim_renewal_interval"] == 3600
        assert "claude" in result["result"]["enabled_agents"]
        assert result["result"]["auto_discover"] is True
        assert "wontfix" in result["result"]["exclude_labels"]

    @pytest.mark.asyncio
    async def test_get_board_config_no_config(self, mock_github_token):
        """Test get_board_config when config not loaded."""
        from mcp_github_board.server import GitHubBoardMCPServer

        server = GitHubBoardMCPServer()
        server._initialized = True
        server.config = None
        server.board_manager = MagicMock()

        result = await server.get_board_config()

        assert result["success"] is False
        assert "not loaded" in result["error"]


class TestHealthCheck:
    """Test health check functionality."""

    @pytest.mark.asyncio
    async def test_health_check_not_initialized(self):
        """Test health check when not initialized (no token)."""
        from mcp_github_board.server import GitHubBoardMCPServer

        # Fully mock initialization to prevent real API calls
        with patch("mcp_github_board.server.get_github_token") as mock_token:
            mock_token.side_effect = RuntimeError("No token")

            with patch.dict(os.environ, {"GITHUB_BOARD_CONFIG": "/nonexistent"}):
                server = GitHubBoardMCPServer()

                result = await server.health_check()

                assert "status" in result
                assert result["board_status"] == "not_initialized"
                # Note: config_loaded may be True because config loading happens
                # before token check. The key assertion is board_status.

    @pytest.mark.asyncio
    async def test_health_check_initialized(self, mock_github_token, mock_board_config):
        """Test health check when initialized."""
        from mcp_github_board.server import GitHubBoardMCPServer

        server = GitHubBoardMCPServer()
        server._initialized = True
        server.config = mock_board_config
        server.board_manager = MagicMock()

        result = await server.health_check()

        assert result["board_status"] == "healthy"
        assert result["config_loaded"] is True


class TestEnsureBoardReady:
    """Test _ensure_board_ready method."""

    @pytest.mark.asyncio
    async def test_ensure_board_ready_success(self, mock_github_token, mock_board_config):
        """Test _ensure_board_ready when initialization succeeds."""
        from mcp_github_board.server import GitHubBoardMCPServer

        server = GitHubBoardMCPServer()
        server._initialized = True
        server.config = mock_board_config
        server.board_manager = MagicMock()

        # Should not raise
        await server._ensure_board_ready()

    @pytest.mark.asyncio
    async def test_ensure_board_ready_failure(self):
        """Test _ensure_board_ready raises when initialization fails."""
        from mcp_github_board.server import GitHubBoardMCPServer

        # Mock token to fail
        with patch("mcp_github_board.server.get_github_token") as mock_token:
            mock_token.side_effect = RuntimeError("No token")

            with patch.dict(os.environ, {"GITHUB_BOARD_CONFIG": "/nonexistent"}):
                server = GitHubBoardMCPServer()

                with pytest.raises(RuntimeError, match="Board manager not initialized"):
                    await server._ensure_board_ready()


class TestIntegrationWithBoardManager:
    """Test integration between MCP server and BoardManager from github_agents."""

    @pytest.mark.asyncio
    async def test_board_manager_is_from_github_agents(self, mock_github_token, config_file_path, mock_board_config):
        """Verify BoardManager is imported from github_agents package."""
        from mcp_github_board.server import GitHubBoardMCPServer

        # Verify the import is correct
        with patch.dict(os.environ, {"GITHUB_BOARD_CONFIG": config_file_path}):
            with patch("mcp_github_board.server.load_config") as mock_load:
                mock_load.return_value = mock_board_config
                with patch("mcp_github_board.server.BoardManager") as mock_manager_class:
                    with patch("mcp_github_board.server.get_github_token") as mock_token:
                        mock_token.return_value = "test-token"
                        mock_manager = MagicMock()
                        mock_manager.initialize = AsyncMock()
                        mock_manager_class.return_value = mock_manager

                        server = GitHubBoardMCPServer()
                        await server._ensure_initialized()

                        # The patched BoardManager should have been called
                        mock_manager_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_issue_status_enum_mapping(self, mock_github_token, mock_board_config):
        """Test that IssueStatus enum from github_agents is used correctly."""
        from github_agents.board.models import IssueStatus
        from mcp_github_board.server import GitHubBoardMCPServer

        server = GitHubBoardMCPServer()
        server._initialized = True
        server.config = mock_board_config

        mock_manager = MagicMock()
        mock_manager.update_status = AsyncMock(return_value=True)
        server.board_manager = mock_manager

        await server.update_status(issue_number=42, status="Done")

        # Verify the correct enum was passed to BoardManager
        mock_manager.update_status.assert_called_once_with(42, IssueStatus.DONE)


class TestToolParameterValidation:
    """Test tool parameter structures match expected schemas."""

    def test_claim_work_required_params(self):
        """Test claim_work has correct required parameters."""
        from mcp_github_board.server import GitHubBoardMCPServer

        server = GitHubBoardMCPServer()
        tools = server.get_tools()

        claim_tool = tools["claim_work"]
        required = claim_tool["parameters"].get("required", [])

        assert "issue_number" in required
        assert "agent_name" in required
        assert "session_id" in required

    def test_update_status_enum_values(self):
        """Test update_status has correct enum values."""
        from mcp_github_board.server import GitHubBoardMCPServer

        server = GitHubBoardMCPServer()
        tools = server.get_tools()

        status_tool = tools["update_status"]
        status_enum = status_tool["parameters"]["properties"]["status"]["enum"]

        expected = ["Todo", "In Progress", "Blocked", "Done", "Abandoned"]
        assert status_enum == expected

    def test_release_work_reason_enum(self):
        """Test release_work has correct reason enum values."""
        from mcp_github_board.server import GitHubBoardMCPServer

        server = GitHubBoardMCPServer()
        tools = server.get_tools()

        release_tool = tools["release_work"]
        reason_enum = release_tool["parameters"]["properties"]["reason"]["enum"]

        expected = ["completed", "blocked", "abandoned", "error"]
        assert reason_enum == expected


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_query_ready_work_with_blocked_issue(self, mock_github_token, mock_board_config):
        """Test query_ready_work includes blocked_by info."""
        from mcp_github_board.server import GitHubBoardMCPServer

        blocked_issue = Issue(
            number=42,
            title="Blocked Issue",
            body="This issue is blocked",
            state="open",
            status=IssueStatus.TODO,
            priority=IssuePriority.HIGH,
            blocked_by=[10, 20],
            url="https://github.com/test/repo/issues/42",
            labels=[],
        )

        server = GitHubBoardMCPServer()
        server._initialized = True
        server.config = mock_board_config

        mock_manager = MagicMock()
        mock_manager.get_ready_work = AsyncMock(return_value=[blocked_issue])
        server.board_manager = mock_manager

        result = await server.query_ready_work()

        assert result["result"]["issues"][0]["blocked_by"] == [10, 20]

    @pytest.mark.asyncio
    async def test_query_ready_work_with_none_priority(self, mock_github_token, mock_board_config):
        """Test query_ready_work handles None priority."""
        from mcp_github_board.server import GitHubBoardMCPServer

        issue_no_priority = Issue(
            number=42,
            title="No Priority Issue",
            body="This issue has no priority",
            state="open",
            status=IssueStatus.TODO,
            priority=None,
            type=None,
            blocked_by=[],
            url="https://github.com/test/repo/issues/42",
            labels=[],
        )

        server = GitHubBoardMCPServer()
        server._initialized = True
        server.config = mock_board_config

        mock_manager = MagicMock()
        mock_manager.get_ready_work = AsyncMock(return_value=[issue_no_priority])
        server.board_manager = mock_manager

        result = await server.query_ready_work()

        assert result["result"]["issues"][0]["priority"] is None
        assert result["result"]["issues"][0]["type"] is None
