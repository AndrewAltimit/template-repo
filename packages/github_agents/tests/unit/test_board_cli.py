"""Tests for board CLI."""

import argparse
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from github_agents.board.cli import (
    cmd_block,
    cmd_claim,
    cmd_create,
    cmd_graph,
    cmd_info,
    cmd_ready,
    cmd_release,
    cmd_status,
    format_issue,
    load_board_manager,
    main,
    output_result,
)
from github_agents.board.models import AgentClaim, DependencyGraph, Issue, IssuePriority, IssueStatus, IssueType


@pytest.fixture
def mock_board_manager():
    """Create mock board manager."""
    manager = MagicMock()
    manager.initialize = AsyncMock()
    return manager


@pytest.fixture
def mock_issue():
    """Create mock issue."""
    return Issue(
        number=123,
        title="Test Issue",
        body="Test body",
        state="open",
        status=IssueStatus.TODO,
        priority=IssuePriority.HIGH,
        type=IssueType.FEATURE,
        agent="claude",
        blocked_by=[456],
        url="https://github.com/test/repo/issues/123",
    )


@pytest.fixture
def mock_dependency_graph():
    """Create mock dependency graph."""
    main_issue = Issue(number=123, title="Main Issue", body="Main body", state="open", status=IssueStatus.TODO)

    blocker_issue = Issue(number=789, title="Blocker Issue", body="Blocker body", state="open", status=IssueStatus.IN_PROGRESS)

    blocked_by_issue = Issue(
        number=456, title="Blocked By Issue", body="Blocked by body", state="open", status=IssueStatus.TODO
    )

    parent_issue = Issue(number=100, title="Parent Issue", body="Parent body", state="open", status=IssueStatus.DONE)

    return DependencyGraph(
        issue=main_issue, blocks=[blocker_issue], blocked_by=[blocked_by_issue], children=[], parent=parent_issue
    )


@pytest.fixture
def mock_claim():
    """Create mock agent claim."""
    from datetime import datetime

    return AgentClaim(
        issue_number=123, agent="claude", timestamp=datetime(2025, 10, 25, 14, 30, 0), session_id="test-session-123"
    )


class TestFormatIssue:
    """Tests for format_issue function."""

    def test_format_issue_basic(self, mock_issue):
        """Test basic issue formatting."""
        result = format_issue(mock_issue, verbose=False)
        assert "#123: Test Issue" in result
        assert "Status:" not in result  # Not verbose

    def test_format_issue_verbose(self, mock_issue):
        """Test verbose issue formatting."""
        result = format_issue(mock_issue, verbose=True)
        assert "#123: Test Issue" in result
        assert "Status: Todo" in result
        assert "Priority: High" in result
        assert "Type: Feature" in result
        assert "Agent: claude" in result
        assert "Blocked by: #456" in result


class TestOutputResult:
    """Tests for output_result function."""

    def test_output_json(self, capsys):
        """Test JSON output."""
        data = {"test": "value"}
        output_result(data, json_output=True)
        captured = capsys.readouterr()
        assert '"test"' in captured.out
        assert '"value"' in captured.out

    def test_output_list_empty(self, capsys):
        """Test empty list output."""
        output_result([], json_output=False)
        captured = capsys.readouterr()
        assert "No results found" in captured.out

    def test_output_list_issues(self, capsys, mock_issue):
        """Test list of issues output."""
        output_result([mock_issue], json_output=False, verbose=False)
        captured = capsys.readouterr()
        assert "#123: Test Issue" in captured.out

    def test_output_dict(self, capsys):
        """Test dictionary output."""
        data = {"key1": "value1", "key2": "value2"}
        output_result(data, json_output=False)
        captured = capsys.readouterr()
        assert "key1: value1" in captured.out
        assert "key2: value2" in captured.out


class TestLoadBoardManager:
    """Tests for load_board_manager function."""

    @patch("github_agents.board.cli.Path")
    @patch("github_agents.board.cli.os.getenv")
    def test_load_board_manager_missing_config(self, mock_getenv, mock_path):
        """Test load_board_manager with missing config."""
        mock_path.return_value.exists.return_value = False
        mock_getenv.return_value = "test-token"

        with pytest.raises(SystemExit) as exc_info:
            load_board_manager()
        assert exc_info.value.code == 1

    @patch("github_agents.board.cli.Path")
    @patch("github_agents.board.cli.os.getenv")
    def test_load_board_manager_missing_token(self, mock_getenv, mock_path):
        """Test load_board_manager with missing GitHub token."""
        mock_path.return_value.exists.return_value = True
        mock_getenv.return_value = None

        with pytest.raises(SystemExit) as exc_info:
            load_board_manager()
        assert exc_info.value.code == 1


class TestCmdReady:
    """Tests for cmd_ready command."""

    @pytest.mark.asyncio
    @patch("github_agents.board.cli.load_board_manager")
    async def test_cmd_ready_success(self, mock_load, capsys, mock_issue):
        """Test cmd_ready success."""
        manager = MagicMock()
        manager.initialize = AsyncMock()
        manager.get_ready_work = AsyncMock(return_value=[mock_issue])
        mock_load.return_value = manager

        args = argparse.Namespace(agent=None, priority=None, limit=10, json=False, verbose=False)

        await cmd_ready(args)

        captured = capsys.readouterr()
        assert "Found 1 ready work items" in captured.out
        assert "#123: Test Issue" in captured.out

    @pytest.mark.asyncio
    @patch("github_agents.board.cli.load_board_manager")
    async def test_cmd_ready_empty(self, mock_load, capsys):
        """Test cmd_ready with no results."""
        manager = MagicMock()
        manager.initialize = AsyncMock()
        manager.get_ready_work = AsyncMock(return_value=[])
        mock_load.return_value = manager

        args = argparse.Namespace(agent=None, priority=None, limit=10, json=False, verbose=False)

        await cmd_ready(args)

        captured = capsys.readouterr()
        assert "No ready work found" in captured.out

    @pytest.mark.asyncio
    @patch("github_agents.board.cli.load_board_manager")
    async def test_cmd_ready_json(self, mock_load, capsys, mock_issue):
        """Test cmd_ready with JSON output."""
        manager = MagicMock()
        manager.initialize = AsyncMock()
        manager.get_ready_work = AsyncMock(return_value=[mock_issue])
        mock_load.return_value = manager

        args = argparse.Namespace(agent="claude", priority="high", limit=5, json=True, verbose=False)

        await cmd_ready(args)

        captured = capsys.readouterr()
        assert '"number": 123' in captured.out
        assert '"title": "Test Issue"' in captured.out


class TestCmdCreate:
    """Tests for cmd_create command."""

    @pytest.mark.asyncio
    @patch("github_agents.board.cli.load_board_manager")
    async def test_cmd_create_success(self, mock_load, capsys, mock_issue):
        """Test cmd_create success."""
        manager = MagicMock()
        manager.initialize = AsyncMock()
        manager.create_issue_with_metadata = AsyncMock(return_value=mock_issue)
        mock_load.return_value = manager

        args = argparse.Namespace(
            title="New Issue", body="Description", type="feature", priority="high", agent="claude", size="m", json=False
        )

        await cmd_create(args)

        captured = capsys.readouterr()
        assert "Created issue #123" in captured.out
        assert "Test Issue" in captured.out


class TestCmdBlock:
    """Tests for cmd_block command."""

    @pytest.mark.asyncio
    @patch("github_agents.board.cli.load_board_manager")
    async def test_cmd_block_success(self, mock_load, capsys):
        """Test cmd_block success."""
        manager = MagicMock()
        manager.initialize = AsyncMock()
        manager.add_blocker = AsyncMock(return_value=True)
        mock_load.return_value = manager

        args = argparse.Namespace(issue=123, blocked_by=456, json=False)

        await cmd_block(args)

        captured = capsys.readouterr()
        assert "Added blocker" in captured.out
        assert "#123" in captured.out
        assert "#456" in captured.out


class TestCmdStatus:
    """Tests for cmd_status command."""

    @pytest.mark.asyncio
    @patch("github_agents.board.cli.load_board_manager")
    async def test_cmd_status_success(self, mock_load, capsys):
        """Test cmd_status success."""
        manager = MagicMock()
        manager.initialize = AsyncMock()
        manager.update_status = AsyncMock(return_value=True)
        manager.assign_to_agent = AsyncMock()
        mock_load.return_value = manager

        args = argparse.Namespace(issue=123, status="in-progress", agent="claude", json=False)

        await cmd_status(args)

        captured = capsys.readouterr()
        assert "Updated issue #123" in captured.out
        assert "In Progress" in captured.out

    @pytest.mark.asyncio
    @patch("github_agents.board.cli.load_board_manager")
    async def test_cmd_status_invalid_status(self, mock_load):
        """Test cmd_status with invalid status."""
        manager = MagicMock()
        manager.initialize = AsyncMock()
        mock_load.return_value = manager

        args = argparse.Namespace(issue=123, status="invalid-status", agent=None, json=False)

        with pytest.raises(SystemExit):
            await cmd_status(args)


class TestCmdGraph:
    """Tests for cmd_graph command."""

    @pytest.mark.asyncio
    @patch("github_agents.board.cli.load_board_manager")
    async def test_cmd_graph_success(self, mock_load, capsys, mock_dependency_graph):
        """Test cmd_graph success."""
        manager = MagicMock()
        manager.initialize = AsyncMock()
        manager.get_dependency_graph = AsyncMock(return_value=mock_dependency_graph)
        mock_load.return_value = manager

        args = argparse.Namespace(issue=123, depth=3, json=False)

        await cmd_graph(args)

        captured = capsys.readouterr()
        assert "Dependency graph for issue #123" in captured.out
        # The graph is returned as Issue objects, check for the parent issue
        assert "Discovered from: #100" in captured.out


class TestCmdClaim:
    """Tests for cmd_claim command."""

    @pytest.mark.asyncio
    @patch("github_agents.board.cli.load_board_manager")
    async def test_cmd_claim_success(self, mock_load, capsys):
        """Test cmd_claim success."""
        manager = MagicMock()
        manager.initialize = AsyncMock()
        manager.claim_work = AsyncMock(return_value=True)
        mock_load.return_value = manager

        args = argparse.Namespace(issue=123, agent="claude", json=False)

        await cmd_claim(args)

        captured = capsys.readouterr()
        assert "Successfully claimed issue #123" in captured.out
        assert "claude" in captured.out

    @pytest.mark.asyncio
    @patch("github_agents.board.cli.load_board_manager")
    async def test_cmd_claim_already_claimed(self, mock_load):
        """Test cmd_claim when already claimed."""
        manager = MagicMock()
        manager.initialize = AsyncMock()
        manager.claim_work = AsyncMock(return_value=False)
        mock_load.return_value = manager

        args = argparse.Namespace(issue=123, agent="claude", json=False)

        with pytest.raises(SystemExit):
            await cmd_claim(args)


class TestCmdRelease:
    """Tests for cmd_release command."""

    @pytest.mark.asyncio
    @patch("github_agents.board.cli.load_board_manager")
    async def test_cmd_release_success(self, mock_load, capsys):
        """Test cmd_release success."""
        manager = MagicMock()
        manager.initialize = AsyncMock()
        manager.release_work = AsyncMock()
        mock_load.return_value = manager

        args = argparse.Namespace(issue=123, agent="claude", reason="completed", json=False)

        await cmd_release(args)

        captured = capsys.readouterr()
        assert "Released claim on issue #123" in captured.out
        assert "completed" in captured.out


class TestCmdInfo:
    """Tests for cmd_info command."""

    @pytest.mark.asyncio
    @patch("github_agents.board.cli.load_board_manager")
    async def test_cmd_info_success(self, mock_load, capsys, mock_issue, mock_claim):  # pylint: disable=unused-argument
        """Test cmd_info success."""
        manager = MagicMock()
        manager.initialize = AsyncMock()

        # Mock get_issue to return the issue
        manager.get_issue = AsyncMock(return_value=mock_issue)
        mock_load.return_value = manager

        args = argparse.Namespace(issue=mock_issue.number, json=False)

        await cmd_info(args)

        captured = capsys.readouterr()
        assert f"#{mock_issue.number}: {mock_issue.title}" in captured.out


class TestMainCLI:
    """Tests for main CLI entry point."""

    @patch("github_agents.board.cli.sys.argv", ["board-cli"])
    def test_main_no_command(self):
        """Test main with no command."""
        with pytest.raises(SystemExit):
            main()

    @patch("github_agents.board.cli.sys.argv", ["board-cli", "ready", "--limit", "5"])
    @patch("github_agents.board.cli.cmd_ready")
    @patch("github_agents.board.cli.setup_logging")
    def test_main_ready_command(self, _mock_logging, mock_cmd_ready):
        """Test main with ready command."""
        main()
        mock_cmd_ready.assert_called_once()

    @patch("github_agents.board.cli.sys.argv", ["board-cli", "create", "Test Issue", "--type", "bug"])
    @patch("github_agents.board.cli.cmd_create")
    @patch("github_agents.board.cli.setup_logging")
    def test_main_create_command(self, _mock_logging, mock_cmd_create):
        """Test main with create command."""
        main()
        mock_cmd_create.assert_called_once()

    @patch("github_agents.board.cli.sys.argv", ["board-cli", "--verbose", "info", "123"])
    @patch("github_agents.board.cli.cmd_info")
    @patch("github_agents.board.cli.setup_logging")
    def test_main_with_verbose(self, mock_logging, _mock_cmd_info):
        """Test main with verbose flag."""
        main()
        mock_logging.assert_called_once_with(True)
