"""Tests for issue monitor functionality."""

import json
from unittest.mock import MagicMock, patch

import pytest
from github_ai_agents.monitors.issue import IssueMonitor


@pytest.fixture
def mock_env():
    """Mock environment variables."""
    with patch.dict("os.environ", {"GITHUB_REPOSITORY": "test/repo", "GITHUB_TOKEN": "test-token"}):
        yield


@pytest.fixture
def issue_monitor(mock_env):
    """Create issue monitor instance."""
    with patch("github_ai_agents.config.AgentConfig"), patch("github_ai_agents.security.SecurityManager"):
        return IssueMonitor()


class TestIssueMonitor:
    """Test issue monitor functionality."""

    def test_initialization(self, mock_env):
        """Test issue monitor initialization."""
        with patch("github_ai_agents.config.AgentConfig"), patch("github_ai_agents.security.SecurityManager"):
            monitor = IssueMonitor()
            assert monitor.repo == "test/repo"
            assert monitor.agent_tag == "[AI Agent]"

    def test_initialization_without_repo(self):
        """Test initialization fails without GITHUB_REPOSITORY."""
        with pytest.raises(RuntimeError, match="GITHUB_REPOSITORY environment variable must be set"):
            IssueMonitor()

    @patch("github_ai_agents.monitors.issue.run_gh_command")
    def test_get_open_issues(self, mock_gh_command, issue_monitor):
        """Test getting open issues."""
        mock_gh_command.return_value = json.dumps(
            [
                {
                    "number": 456,
                    "title": "Test Issue",
                    "body": "Issue description",
                    "createdAt": "2024-01-20T10:00:00Z",
                    "author": {"login": "testuser"},
                }
            ]
        )

        issues = issue_monitor.get_open_issues()
        assert len(issues) == 1
        assert issues[0]["number"] == 456

    @patch("github_ai_agents.monitors.issue.run_gh_command")
    def test_process_issue_with_trigger(self, mock_gh_command, issue_monitor):
        """Test processing issue with valid trigger."""
        issue = {
            "number": 456,
            "title": "Test Issue",
            "body": "Issue body",
            "comments": [{"body": "[Approved][Claude]", "author": {"login": "authorized_user"}}],
        }

        # Mock security check
        issue_monitor.security_manager.check_trigger_comment.return_value = (
            "Approved",
            "Claude",
            "authorized_user",
        )
        issue_monitor.security_manager.perform_full_security_check.return_value = (
            True,
            None,
        )

        # Mock has_agent_comment to return False
        mock_gh_command.side_effect = [
            json.dumps({"comments": []}),  # No existing agent comments
            None,  # Starting work comment
        ]

        # Mock agent
        mock_agent = MagicMock()
        mock_agent.name = "Claude"
        issue_monitor.agents = {"claude": mock_agent}

        with patch("github_ai_agents.monitors.issue.asyncio.run"):
            issue_monitor._process_single_issue(issue)

        # Verify starting work comment was posted
        assert mock_gh_command.call_count == 2

    @patch("github_ai_agents.monitors.issue.run_gh_command")
    def test_handle_close_action(self, mock_gh_command, issue_monitor):
        """Test handling close action."""
        issue_monitor.security_manager.check_trigger_comment.return_value = (
            "Close",
            "Claude",
            "authorized_user",
        )
        issue_monitor.security_manager.perform_full_security_check.return_value = (
            True,
            None,
        )

        # Mock no existing comments
        mock_gh_command.side_effect = [
            json.dumps({"comments": []}),  # No existing agent comments
            None,  # Close issue
            None,  # Post comment
        ]

        issue = {"number": 789, "comments": [{"body": "[Close][Claude]"}]}
        issue_monitor._process_single_issue(issue)

        # Verify issue was closed
        calls = mock_gh_command.call_args_list
        assert any("close" in str(call) for call in calls)

    @patch("github_ai_agents.monitors.issue.run_gh_command")
    def test_handle_summarize_action(self, mock_gh_command, issue_monitor):
        """Test handling summarize action."""
        issue_monitor.security_manager.check_trigger_comment.return_value = (
            "Summarize",
            "Claude",
            "authorized_user",
        )
        issue_monitor.security_manager.perform_full_security_check.return_value = (
            True,
            None,
        )

        # Mock no existing comments
        mock_gh_command.side_effect = [
            json.dumps({"comments": []}),
            None,
        ]  # No existing agent comments  # Post summary

        issue = {
            "number": 101,
            "title": "Test Issue",
            "body": "Long issue body" * 20,
            "labels": [{"name": "bug"}, {"name": "enhancement"}],
            "comments": [{"body": "[Summarize][Claude]"}],
        }
        issue_monitor._process_single_issue(issue)

        # Verify summary was posted
        summary_call = mock_gh_command.call_args_list[-1]
        summary_text = summary_call[0][0][-1]
        assert "Issue Summary" in summary_text
        assert "bug, enhancement" in summary_text

    @patch("github_ai_agents.monitors.issue.run_gh_command")
    def test_security_rejection(self, mock_gh_command, issue_monitor):
        """Test security rejection flow."""
        issue_monitor.security_manager.check_trigger_comment.return_value = (
            "Approved",
            "Claude",
            "unauthorized_user",
        )
        issue_monitor.security_manager.perform_full_security_check.return_value = (
            False,
            "User not in allow list",
        )

        mock_gh_command.return_value = None

        issue = {"number": 202, "comments": [{"body": "[Approved][Claude]"}]}
        issue_monitor._process_single_issue(issue)

        # Verify security rejection comment was posted
        assert mock_gh_command.called
        security_comment = mock_gh_command.call_args[0][0][-1]
        assert "Security Notice" in security_comment

    @patch("github_ai_agents.monitors.issue.run_gh_command")
    def test_containerized_agent_error(self, mock_gh_command, issue_monitor):
        """Test error when requesting containerized agent on host."""
        issue_monitor.security_manager.check_trigger_comment.return_value = (
            "Approved",
            "OpenCode",
            "authorized_user",
        )
        issue_monitor.security_manager.perform_full_security_check.return_value = (
            True,
            None,
        )

        # Mock no existing comments
        mock_gh_command.side_effect = [
            json.dumps({"comments": []}),
            None,
        ]  # No existing agent comments  # Error comment

        # Only Claude available (host mode)
        issue_monitor.agents = {"claude": MagicMock()}

        issue = {"number": 303, "comments": [{"body": "[Approved][OpenCode]"}]}
        issue_monitor._process_single_issue(issue)

        # Verify error mentions containerized environment
        error_call = mock_gh_command.call_args_list[-1]
        error_text = error_call[0][0][-1]
        assert "only available in the containerized environment" in error_text

    def test_continuous_monitoring(self, issue_monitor):
        """Test continuous monitoring mode."""
        # Mock to raise KeyboardInterrupt after first iteration
        issue_monitor.process_issues = MagicMock(side_effect=[None, KeyboardInterrupt()])

        issue_monitor.run_continuous(interval=0.1)

        # Verify process_issues was called
        assert issue_monitor.process_issues.called
