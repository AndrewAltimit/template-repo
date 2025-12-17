"""Tests for monitor board integration."""

# pylint: disable=protected-access  # Testing protected members is legitimate in tests

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from github_agents.board.models import IssueStatus
from github_agents.monitors.issue import IssueMonitor
from github_agents.monitors.pr import PRMonitor


class TestIssueMonitorBoardIntegration:
    """Test issue monitor board integration."""

    @pytest.fixture
    def mock_board_manager(self):
        """Create a mock board manager."""
        manager = AsyncMock()
        manager.initialize = AsyncMock()
        manager.claim_work = AsyncMock(return_value=True)
        manager.release_work = AsyncMock()
        manager.update_status = AsyncMock(return_value=True)
        return manager

    @pytest.fixture
    def issue_monitor(self, mock_board_manager, monkeypatch):
        """Create an issue monitor with mocked board manager."""
        monkeypatch.setenv("GITHUB_REPOSITORY", "test-owner/test-repo")
        monkeypatch.setenv("GITHUB_TOKEN", "fake-token")
        monitor = IssueMonitor()
        monitor.board_manager = mock_board_manager
        return monitor

    @pytest.mark.asyncio
    async def test_board_manager_initialization_with_config(self, monkeypatch):
        """Test board manager is initialized when config exists."""
        monkeypatch.setenv("GITHUB_REPOSITORY", "test-owner/test-repo")
        monkeypatch.setenv("GITHUB_TOKEN", "fake-token")
        with (
            patch("github_agents.monitors.issue.Path.exists", return_value=True),
            patch("github_agents.monitors.issue.load_config") as mock_load_config,
        ):
            mock_load_config.return_value = MagicMock()
            monitor = IssueMonitor()

            assert monitor.board_manager is not None

    @pytest.mark.asyncio
    async def test_board_manager_not_initialized_without_config(self, monkeypatch):
        """Test board manager is not initialized when config doesn't exist."""
        monkeypatch.setenv("GITHUB_REPOSITORY", "test-owner/test-repo")
        monkeypatch.setenv("GITHUB_TOKEN", "fake-token")
        with patch("github_agents.monitors.issue.Path.exists", return_value=False):
            monitor = IssueMonitor()
            assert monitor.board_manager is None

    @pytest.mark.asyncio
    async def test_claim_work_on_implementation(self, issue_monitor, mock_board_manager):
        """Test work is claimed when issue implementation starts."""
        issue = {"number": 42, "title": "Test Issue", "body": "Test body"}
        agent_name = "claude"

        # Mock the agent and other dependencies
        mock_agent = AsyncMock()
        mock_agent.generate_code = AsyncMock(return_value="# Test code")
        issue_monitor.agents = {"claude": mock_agent}

        with (
            patch.object(issue_monitor, "_post_starting_work_comment"),
            patch.object(issue_monitor, "_post_comment"),
            patch("github_agents.monitors.issue.run_gh_command_async"),
            patch("github_agents.monitors.issue.run_git_command_async"),
            patch("github_agents.code_parser.CodeParser.extract_and_apply", return_value=([], {})),
        ):
            await issue_monitor._handle_implementation_async(issue, agent_name)

            # Verify board manager was called to claim work
            mock_board_manager.initialize.assert_called_once()
            mock_board_manager.claim_work.assert_called_once()
            args = mock_board_manager.claim_work.call_args[0]
            assert args[0] == 42  # issue_number
            assert args[1] == "claude"  # agent_name

    @pytest.mark.asyncio
    async def test_release_work_on_pr_creation(self, issue_monitor, mock_board_manager):
        """Test work is released when PR is successfully created."""
        issue = {"number": 42, "title": "Test Issue", "body": "Test body"}

        with (
            patch("github_agents.monitors.issue.run_git_command_async") as mock_git,
            patch("github_agents.monitors.issue.run_gh_command_async") as mock_gh,
            patch("github_agents.code_parser.CodeParser.extract_and_apply", return_value=([], {"test.py": "created"})),
        ):
            # Mock git commands
            mock_git.return_value = "file changed"  # status --porcelain
            mock_gh.return_value = "https://github.com/test/repo/pull/1"

            await issue_monitor._create_pr(issue, "test-branch", "claude", "# code", "session-123")

            # Verify work was released
            mock_board_manager.release_work.assert_called_once()
            args = mock_board_manager.release_work.call_args[0]
            assert args[0] == 42  # issue_number
            assert args[1] == "claude"  # agent_name
            assert args[2] == "completed"  # reason

    @pytest.mark.asyncio
    async def test_release_work_as_abandoned_when_no_changes(self, issue_monitor, mock_board_manager):
        """Test work is released as abandoned when no changes are generated."""
        issue = {"number": 42, "title": "Test Issue", "body": "Test body"}

        with (
            patch("github_agents.monitors.issue.run_git_command_async") as mock_git,
            patch("github_agents.monitors.issue.run_gh_command_async"),
            patch("github_agents.code_parser.CodeParser.extract_and_apply", return_value=([], {})),
        ):
            # Mock git status to return empty (no changes)
            mock_git.return_value = ""

            await issue_monitor._create_pr(issue, "test-branch", "claude", "# code", "session-123")

            # Verify work was released as abandoned
            mock_board_manager.release_work.assert_called_once()
            args = mock_board_manager.release_work.call_args[0]
            assert args[0] == 42
            assert args[1] == "claude"
            assert args[2] == "abandoned"


class TestPRMonitorBoardIntegration:
    """Test PR monitor board integration."""

    @pytest.fixture
    def mock_board_manager(self):
        """Create a mock board manager."""
        manager = AsyncMock()
        manager.initialize = AsyncMock()
        manager.update_status = AsyncMock(return_value=True)
        return manager

    @pytest.fixture
    def pr_monitor(self, mock_board_manager, monkeypatch):
        """Create a PR monitor with mocked board manager."""
        monkeypatch.setenv("GITHUB_REPOSITORY", "test-owner/test-repo")
        monkeypatch.setenv("GITHUB_TOKEN", "fake-token")
        monitor = PRMonitor()
        monitor.board_manager = mock_board_manager
        return monitor

    def test_extract_issue_numbers_from_pr_body(self, pr_monitor):
        """Test extraction of issue numbers from PR body."""
        pr_body = """
        This PR implements the following changes:
        - Added new feature
        - Fixed bugs

        Closes #42
        Fixes #123
        Resolves #456
        """

        issue_numbers = pr_monitor._extract_issue_numbers(pr_body)
        assert 42 in issue_numbers
        assert 123 in issue_numbers
        assert 456 in issue_numbers
        assert len(issue_numbers) == 3

    def test_extract_issue_numbers_case_insensitive(self, pr_monitor):
        """Test issue extraction is case insensitive."""
        pr_body = "CLOSES #1, fixes #2, Resolves #3"
        issue_numbers = pr_monitor._extract_issue_numbers(pr_body)
        assert issue_numbers == [1, 2, 3]

    def test_extract_issue_numbers_various_formats(self, pr_monitor):
        """Test various closing keyword formats."""
        pr_body = "Close #1, Closed #2, Closing #3, Fix #4, Fixed #5, Fixing #6, Resolve #7, Resolved #8, Resolving #9"
        issue_numbers = pr_monitor._extract_issue_numbers(pr_body)
        assert len(issue_numbers) == 9
        assert all(i in issue_numbers for i in range(1, 10))

    @pytest.mark.asyncio
    async def test_update_board_on_pr_merge(self, pr_monitor, mock_board_manager):
        """Test board is updated when PR is merged."""
        pr_number = 100
        pr_body = "Closes #42\nFixes #123"

        await pr_monitor._update_board_on_pr_merge(pr_number, pr_body)

        # Verify board manager was initialized
        mock_board_manager.initialize.assert_called_once()

        # Verify both issues were updated to Done
        assert mock_board_manager.update_status.call_count == 2

        # Check the calls
        calls = mock_board_manager.update_status.call_args_list
        issue_numbers = [call[0][0] for call in calls]
        assert 42 in issue_numbers
        assert 123 in issue_numbers

        # Check status is DONE
        for call in calls:
            assert call[0][1] == IssueStatus.DONE

    @pytest.mark.asyncio
    async def test_update_board_no_linked_issues(self, pr_monitor, mock_board_manager):
        """Test board update handles PR with no linked issues."""
        pr_number = 100
        pr_body = "Just some changes, no linked issues"

        await pr_monitor._update_board_on_pr_merge(pr_number, pr_body)

        # Board manager should not be called if no issues found
        mock_board_manager.update_status.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_board_without_board_manager(self, monkeypatch):
        """Test update handles missing board manager gracefully."""
        monkeypatch.setenv("GITHUB_REPOSITORY", "test-owner/test-repo")
        monkeypatch.setenv("GITHUB_TOKEN", "fake-token")
        monitor = PRMonitor()
        monitor.board_manager = None

        # Should not raise exception
        await monitor._update_board_on_pr_merge(100, "Closes #42")

    @pytest.mark.asyncio
    async def test_board_manager_initialization_with_config(self, monkeypatch):
        """Test board manager is initialized when config exists."""
        monkeypatch.setenv("GITHUB_REPOSITORY", "test-owner/test-repo")
        monkeypatch.setenv("GITHUB_TOKEN", "fake-token")
        with (
            patch("github_agents.monitors.pr.Path.exists", return_value=True),
            patch("github_agents.monitors.pr.load_config") as mock_load_config,
        ):
            mock_load_config.return_value = MagicMock()
            monitor = PRMonitor()

            assert monitor.board_manager is not None

    @pytest.mark.asyncio
    async def test_board_manager_not_initialized_without_token(self, monkeypatch):
        """Test board manager is not initialized without GitHub token."""
        monkeypatch.setenv("GITHUB_REPOSITORY", "test-owner/test-repo")
        monkeypatch.setenv("GITHUB_TOKEN", "fake-token")
        # Mock os.getenv to return None only for GITHUB_TOKEN check in _init_board_manager
        with (
            patch("github_agents.monitors.pr.Path.exists", return_value=True),
            patch("github_agents.monitors.pr.load_config") as mock_load_config,
            patch("github_agents.monitors.pr.os.getenv") as mock_getenv,
        ):
            mock_load_config.return_value = MagicMock()
            # Make getenv return None when checking for GITHUB_TOKEN in _init_board_manager
            mock_getenv.return_value = None
            monitor = PRMonitor()

            assert monitor.board_manager is None
