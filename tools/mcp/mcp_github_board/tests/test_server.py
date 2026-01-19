"""
Unit tests for GitHub Board MCP Server.

Tests the CLI wrapper interface - all operations delegate to the Rust board-manager CLI.
"""

from unittest.mock import AsyncMock, patch

import pytest


class TestGitHubBoardMCPServerInit:
    """Test GitHubBoardMCPServer initialization."""

    def test_server_initialization(self):
        """Test server initializes with correct defaults."""
        from mcp_github_board.server import GitHubBoardMCPServer

        server = GitHubBoardMCPServer()
        assert server.name == "GitHub Board MCP Server"
        assert server.version == "2.0.0"
        assert server.port == 8022
        assert server._board_manager_path is None
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
    async def test_ensure_initialized_finds_binary(self, tmp_path, mock_github_token):
        """Test initialization finds board-manager binary."""
        from mcp_github_board.server import GitHubBoardMCPServer

        # Create a fake binary
        fake_binary = tmp_path / "board-manager"
        fake_binary.write_text("#!/bin/bash\necho 'fake'")
        fake_binary.chmod(0o755)

        server = GitHubBoardMCPServer()

        # Patch shutil.which to return our fake binary
        with patch("shutil.which", return_value=str(fake_binary)):
            result = await server._ensure_initialized()

        assert result is True
        assert server._initialized is True
        assert server._board_manager_path == str(fake_binary)

    @pytest.mark.asyncio
    async def test_ensure_initialized_no_binary(self):
        """Test initialization fails when binary not found."""
        from mcp_github_board.server import GitHubBoardMCPServer

        server = GitHubBoardMCPServer()

        # Mock all paths to not exist
        with patch("shutil.which", return_value=None):
            with patch("os.path.isfile", return_value=False):
                result = await server._ensure_initialized()

        assert result is False
        assert server._initialized is False

    @pytest.mark.asyncio
    async def test_ensure_initialized_already_initialized(self, mock_github_token):
        """Test _ensure_initialized returns True when already initialized."""
        from mcp_github_board.server import GitHubBoardMCPServer

        server = GitHubBoardMCPServer()
        server._initialized = True
        server._board_manager_path = "/usr/bin/board-manager"

        result = await server._ensure_initialized()
        assert result is True


class TestRunBoardManager:
    """Test _run_board_manager CLI execution."""

    @pytest.mark.asyncio
    async def test_run_board_manager_success(self, mock_github_token):
        """Test successful CLI execution."""
        from mcp_github_board.server import GitHubBoardMCPServer

        server = GitHubBoardMCPServer()
        server._initialized = True
        server._board_manager_path = "/usr/bin/board-manager"

        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b'{"issues": [], "count": 0}', b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await server._run_board_manager(["ready"])

        assert result["success"] is True
        assert result["result"]["count"] == 0

    @pytest.mark.asyncio
    async def test_run_board_manager_cli_error(self, mock_github_token):
        """Test CLI execution failure."""
        from mcp_github_board.server import GitHubBoardMCPServer

        server = GitHubBoardMCPServer()
        server._initialized = True
        server._board_manager_path = "/usr/bin/board-manager"

        mock_process = AsyncMock()
        mock_process.returncode = 1
        mock_process.communicate = AsyncMock(return_value=(b"", b"Error: not found"))

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await server._run_board_manager(["ready"])

        assert result["success"] is False
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_run_board_manager_not_initialized(self):
        """Test CLI execution when not initialized."""
        from mcp_github_board.server import GitHubBoardMCPServer

        server = GitHubBoardMCPServer()
        server._initialized = False

        # Mock _ensure_initialized to return False
        with patch.object(server, "_ensure_initialized", return_value=False):
            result = await server._run_board_manager(["ready"])

        assert result["success"] is False
        assert "not available" in result["error"]


class TestQueryReadyWork:
    """Test query_ready_work tool."""

    @pytest.mark.asyncio
    async def test_query_ready_work_success(self, mock_cli_response_issues):
        """Test successful query_ready_work."""
        from mcp_github_board.server import GitHubBoardMCPServer

        server = GitHubBoardMCPServer()

        with patch.object(server, "_run_board_manager", return_value=mock_cli_response_issues):
            result = await server.query_ready_work(limit=10)

        assert result["success"] is True
        assert result["result"]["count"] == 2

    @pytest.mark.asyncio
    async def test_query_ready_work_with_agent_filter(self, mock_cli_response_issues):
        """Test query_ready_work passes agent filter to CLI."""
        from mcp_github_board.server import GitHubBoardMCPServer

        server = GitHubBoardMCPServer()

        with patch.object(server, "_run_board_manager", return_value=mock_cli_response_issues) as mock_run:
            await server.query_ready_work(agent_name="claude", limit=5)

        # Verify correct CLI args were passed
        mock_run.assert_called_once_with(["ready", "--limit", "5", "--agent", "claude"])


class TestClaimWork:
    """Test claim_work tool."""

    @pytest.mark.asyncio
    async def test_claim_work_success(self, mock_cli_response_claim_success):
        """Test successful work claim."""
        from mcp_github_board.server import GitHubBoardMCPServer

        server = GitHubBoardMCPServer()

        with patch.object(server, "_run_board_manager", return_value=mock_cli_response_claim_success) as mock_run:
            result = await server.claim_work(issue_number=42, agent_name="claude", session_id="session-123")

        assert result["success"] is True
        mock_run.assert_called_once_with(["claim", "42", "--agent", "claude", "--session", "session-123"])


class TestRenewClaim:
    """Test renew_claim tool."""

    @pytest.mark.asyncio
    async def test_renew_claim_success(self):
        """Test successful claim renewal."""
        from mcp_github_board.server import GitHubBoardMCPServer

        server = GitHubBoardMCPServer()
        mock_response = {"success": True, "result": {"renewed": True}}

        with patch.object(server, "_run_board_manager", return_value=mock_response) as mock_run:
            result = await server.renew_claim(issue_number=42, agent_name="claude", session_id="session-123")

        assert result["success"] is True
        mock_run.assert_called_once_with(["renew", "42", "--agent", "claude", "--session", "session-123"])


class TestReleaseWork:
    """Test release_work tool."""

    @pytest.mark.asyncio
    async def test_release_work_completed(self):
        """Test releasing work as completed."""
        from mcp_github_board.server import GitHubBoardMCPServer

        server = GitHubBoardMCPServer()
        mock_response = {"success": True, "result": {"released": True}}

        with patch.object(server, "_run_board_manager", return_value=mock_response) as mock_run:
            result = await server.release_work(issue_number=42, agent_name="claude", reason="completed")

        assert result["success"] is True
        mock_run.assert_called_once_with(["release", "42", "--agent", "claude", "--reason", "completed"])

    @pytest.mark.asyncio
    async def test_release_work_blocked(self):
        """Test releasing work as blocked."""
        from mcp_github_board.server import GitHubBoardMCPServer

        server = GitHubBoardMCPServer()
        mock_response = {"success": True, "result": {"released": True}}

        with patch.object(server, "_run_board_manager", return_value=mock_response) as mock_run:
            await server.release_work(issue_number=42, agent_name="claude", reason="blocked")

        mock_run.assert_called_once_with(["release", "42", "--agent", "claude", "--reason", "blocked"])


class TestUpdateStatus:
    """Test update_status tool."""

    @pytest.mark.asyncio
    async def test_update_status_success(self):
        """Test successful status update."""
        from mcp_github_board.server import GitHubBoardMCPServer

        server = GitHubBoardMCPServer()
        mock_response = {"success": True, "result": {"updated": True}}

        with patch.object(server, "_run_board_manager", return_value=mock_response) as mock_run:
            result = await server.update_status(issue_number=42, status="In Progress")

        assert result["success"] is True
        mock_run.assert_called_once_with(["status", "42", "In Progress"])

    @pytest.mark.asyncio
    async def test_update_status_all_valid_statuses(self):
        """Test all valid status values pass through to CLI."""
        from mcp_github_board.server import GitHubBoardMCPServer

        server = GitHubBoardMCPServer()
        mock_response = {"success": True, "result": {"updated": True}}

        valid_statuses = ["Todo", "In Progress", "Blocked", "Done", "Abandoned"]

        for status in valid_statuses:
            with patch.object(server, "_run_board_manager", return_value=mock_response) as mock_run:
                await server.update_status(issue_number=42, status=status)
                mock_run.assert_called_once_with(["status", "42", status])


class TestAddBlocker:
    """Test add_blocker tool."""

    @pytest.mark.asyncio
    async def test_add_blocker_success(self):
        """Test successful blocker addition."""
        from mcp_github_board.server import GitHubBoardMCPServer

        server = GitHubBoardMCPServer()
        mock_response = {"success": True, "result": {"added": True}}

        with patch.object(server, "_run_board_manager", return_value=mock_response) as mock_run:
            result = await server.add_blocker(issue_number=42, blocker_number=10)

        assert result["success"] is True
        mock_run.assert_called_once_with(["block", "42", "--blocker", "10"])


class TestMarkDiscoveredFrom:
    """Test mark_discovered_from tool."""

    @pytest.mark.asyncio
    async def test_mark_discovered_from_success(self):
        """Test successful parent-child relationship."""
        from mcp_github_board.server import GitHubBoardMCPServer

        server = GitHubBoardMCPServer()
        mock_response = {"success": True, "result": {"marked": True}}

        with patch.object(server, "_run_board_manager", return_value=mock_response) as mock_run:
            result = await server.mark_discovered_from(issue_number=42, parent_number=10)

        assert result["success"] is True
        mock_run.assert_called_once_with(["discover-from", "42", "--parent", "10"])


class TestGetIssueDetails:
    """Test get_issue_details tool."""

    @pytest.mark.asyncio
    async def test_get_issue_details_success(self):
        """Test get_issue_details calls info command."""
        from mcp_github_board.server import GitHubBoardMCPServer

        server = GitHubBoardMCPServer()
        mock_response = {
            "success": True,
            "result": {
                "number": 42,
                "title": "Test Issue",
                "status": "Todo",
            },
        }

        with patch.object(server, "_run_board_manager", return_value=mock_response) as mock_run:
            result = await server.get_issue_details(issue_number=42)

        assert result["success"] is True
        mock_run.assert_called_once_with(["info", "42"])


class TestGetDependencyGraph:
    """Test get_dependency_graph tool."""

    @pytest.mark.asyncio
    async def test_get_dependency_graph_success(self):
        """Test get_dependency_graph calls info command."""
        from mcp_github_board.server import GitHubBoardMCPServer

        server = GitHubBoardMCPServer()
        mock_response = {
            "success": True,
            "result": {
                "number": 42,
                "blockers": [10],
                "blocked_by": [],
            },
        }

        with patch.object(server, "_run_board_manager", return_value=mock_response) as mock_run:
            result = await server.get_dependency_graph(issue_number=42)

        assert result["success"] is True
        mock_run.assert_called_once_with(["info", "42"])


class TestListAgents:
    """Test list_agents tool."""

    @pytest.mark.asyncio
    async def test_list_agents_success(self, mock_cli_response_agents):
        """Test listing enabled agents."""
        from mcp_github_board.server import GitHubBoardMCPServer

        server = GitHubBoardMCPServer()

        with patch.object(server, "_run_board_manager", return_value=mock_cli_response_agents) as mock_run:
            result = await server.list_agents()

        assert result["success"] is True
        assert result["result"]["count"] == 3
        mock_run.assert_called_once_with(["agents"])


class TestGetBoardConfig:
    """Test get_board_config tool."""

    @pytest.mark.asyncio
    async def test_get_board_config_success(self, mock_cli_response_config):
        """Test getting board configuration."""
        from mcp_github_board.server import GitHubBoardMCPServer

        server = GitHubBoardMCPServer()

        with patch.object(server, "_run_board_manager", return_value=mock_cli_response_config) as mock_run:
            result = await server.get_board_config()

        assert result["success"] is True
        assert result["result"]["project_number"] == 1
        mock_run.assert_called_once_with(["config"])


class TestHealthCheck:
    """Test health check functionality."""

    @pytest.mark.asyncio
    async def test_health_check_not_initialized(self):
        """Test health check when board-manager not found."""
        from mcp_github_board.server import GitHubBoardMCPServer

        server = GitHubBoardMCPServer()
        server._initialized = False

        with patch.object(server, "_ensure_initialized", return_value=False):
            result = await server.health_check()

        assert result["board_status"] == "not_initialized"

    @pytest.mark.asyncio
    async def test_health_check_initialized(self):
        """Test health check when initialized."""
        from mcp_github_board.server import GitHubBoardMCPServer

        server = GitHubBoardMCPServer()
        server._initialized = True
        server._board_manager_path = "/usr/bin/board-manager"

        with patch.object(server, "_ensure_initialized", return_value=True):
            result = await server.health_check()

        assert result["board_status"] == "healthy"
        assert result["board_manager_path"] == "/usr/bin/board-manager"


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
