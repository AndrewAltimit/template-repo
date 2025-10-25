"""Tests for issue and PR monitors."""

import json
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from github_ai_agents.monitors import IssueMonitor, PRMonitor


class TestIssueMonitor:
    """Test issue monitor functionality."""

    @patch.dict(os.environ, {"GITHUB_REPOSITORY": "test/repo"})
    @patch("github_ai_agents.monitors.issue.get_github_token")
    def test_initialization(self, mock_get_token):
        """Test issue monitor initialization."""
        mock_get_token.return_value = "test-token"
        monitor = IssueMonitor()
        assert monitor.repo == "test/repo"
        assert monitor.token == "test-token"
        assert monitor.agent_tag == "[AI Agent]"

    @patch.dict(os.environ, {"GITHUB_REPOSITORY": "test/repo"})
    @patch("github_ai_agents.monitors.issue.get_github_token")
    @patch("github_ai_agents.monitors.issue.run_gh_command")
    def test_get_open_issues(self, mock_gh_command, mock_get_token):
        """Test getting open issues."""
        mock_get_token.return_value = "test-token"
        monitor = IssueMonitor()

        # Mock successful response
        now = datetime.now(timezone.utc)
        mock_issues = [
            {
                "number": 1,
                "title": "Recent issue",
                "body": "Issue body",
                "author": {"login": "user1"},
                "createdAt": (now - timedelta(hours=12)).isoformat(),
                "updatedAt": (now - timedelta(hours=12)).isoformat(),
                "labels": [],
                "comments": [],
            },
            {
                "number": 2,
                "title": "Old issue",
                "body": "Old issue body",
                "author": {"login": "user2"},
                "createdAt": (now - timedelta(hours=48)).isoformat(),
                "updatedAt": (now - timedelta(hours=48)).isoformat(),
                "labels": [],
                "comments": [],
            },
        ]
        mock_gh_command.return_value = json.dumps(mock_issues)

        issues = monitor.get_open_issues()
        assert len(issues) == 1  # Only recent issue
        assert issues[0]["number"] == 1

    @patch.dict(os.environ, {"GITHUB_REPOSITORY": "test/repo"})
    @patch("github_ai_agents.monitors.issue.get_github_token")
    def test_has_agent_comment(self, mock_get_token):
        """Test checking for agent comments."""
        mock_get_token.return_value = "test-token"
        monitor = IssueMonitor()

        with patch("github_ai_agents.monitors.issue.run_gh_command") as mock_gh:
            # Mock issue with agent comment
            mock_gh.return_value = json.dumps(
                {
                    "comments": [
                        {"body": "Regular comment"},
                        {"body": "[AI Agent] I've created a PR"},
                    ]
                }
            )

            assert monitor._has_agent_comment(1, "issue") is True

            # Mock issue without agent comment
            mock_gh.return_value = json.dumps(
                {
                    "comments": [
                        {"body": "Regular comment"},
                        {"body": "Another regular comment"},
                    ]
                }
            )

            assert monitor._has_agent_comment(2, "issue") is False

    @patch.dict(os.environ, {"GITHUB_REPOSITORY": "test/repo"})
    @patch("github_ai_agents.monitors.issue.get_github_token")
    @patch("github_ai_agents.monitors.issue.run_gh_command")
    def test_process_single_issue_with_trigger(self, mock_gh_command, mock_get_token):
        """Test processing issue with valid trigger."""
        mock_get_token.return_value = "test-token"
        monitor = IssueMonitor()

        # Mock agent initialization
        mock_agent = MagicMock()
        mock_agent.is_available.return_value = True
        mock_agent.get_trigger_keyword.return_value = "claude"
        monitor.agents = {"claude": mock_agent}

        # Mock security check
        with patch.object(monitor.security_manager, "check_trigger_comment") as mock_check:
            mock_check.return_value = ("approved", "claude", "AndrewAltimit")

            with patch.object(monitor.security_manager, "perform_full_security_check") as mock_security:
                mock_security.return_value = (True, "")

                with patch.object(monitor, "_has_agent_comment") as mock_has_comment:
                    mock_has_comment.return_value = False

                    with patch.object(monitor, "_handle_implementation") as mock_impl:
                        issue = {
                            "number": 1,
                            "title": "Test issue",
                            "body": "Issue body",
                            "author": {"login": "user1"},
                        }

                        monitor._process_single_issue(issue)

                        # Should call implementation handler
                        mock_impl.assert_called_once_with(issue, "claude")

    @patch.dict(os.environ, {"GITHUB_REPOSITORY": "test/repo"})
    @patch("github_ai_agents.monitors.issue.get_github_token")
    def test_process_single_issue_security_rejected(self, mock_get_token):
        """Test processing issue with security rejection."""
        mock_get_token.return_value = "test-token"
        monitor = IssueMonitor()

        with patch.object(monitor.security_manager, "check_trigger_comment") as mock_check:
            mock_check.return_value = ("approved", "claude", "hacker")

            with patch.object(monitor.security_manager, "perform_full_security_check") as mock_security:
                mock_security.return_value = (False, "User not authorized")

                with patch.object(monitor, "_post_security_rejection") as mock_reject:
                    issue = {"number": 1, "title": "Test issue", "body": "Issue body"}

                    monitor._process_single_issue(issue)

                    # Should post security rejection
                    mock_reject.assert_called_once_with(1, "User not authorized")

    @patch.dict(os.environ, {"GITHUB_REPOSITORY": "test/repo"})
    @patch("github_ai_agents.monitors.issue.get_github_token")
    @patch("github_ai_agents.monitors.issue.run_gh_command")
    def test_post_starting_work_comment(self, mock_gh_command, mock_get_token):
        """Test posting starting work comment."""
        mock_get_token.return_value = "test-token"
        monitor = IssueMonitor()

        monitor._post_starting_work_comment(1, "fix-issue-1-claude-abc123", "Claude")

        # Should call gh command with correct parameters
        mock_gh_command.assert_called_once()
        call_args = mock_gh_command.call_args[0][0]
        assert call_args[0] == "issue"
        assert call_args[1] == "comment"
        assert call_args[2] == "1"
        assert "--repo" in call_args
        assert "test/repo" in call_args


class TestPRMonitor:
    """Test PR monitor functionality."""

    @patch.dict(os.environ, {"GITHUB_REPOSITORY": "test/repo"})
    @patch("github_ai_agents.monitors.pr.get_github_token")
    def test_initialization(self, mock_get_token):
        """Test PR monitor initialization."""
        mock_get_token.return_value = "test-token"
        monitor = PRMonitor()
        assert monitor.repo == "test/repo"
        assert monitor.token == "test-token"
        assert monitor.agent_tag == "[AI Agent]"

    @patch.dict(os.environ, {"GITHUB_REPOSITORY": "test/repo"})
    @patch("github_ai_agents.monitors.pr.get_github_token")
    @patch("github_ai_agents.monitors.pr.run_gh_command")
    def test_get_open_prs(self, mock_gh_command, mock_get_token):
        """Test getting open PRs."""
        mock_get_token.return_value = "test-token"
        monitor = PRMonitor()

        # Mock successful response
        mock_prs = [
            {
                "number": 10,
                "title": "Fix bug",
                "body": "PR body",
                "author": {"login": "user1"},
                "draft": False,
                "labels": [],
            },
            {
                "number": 11,
                "title": "WIP: New feature",
                "body": "Draft PR",
                "author": {"login": "user2"},
                "draft": True,
                "labels": [],
            },
        ]
        mock_gh_command.return_value = json.dumps(mock_prs)

        prs = monitor.get_open_prs()
        assert len(prs) == 1  # Only non-draft PR
        assert prs[0]["number"] == 10

    @patch.dict(os.environ, {"GITHUB_REPOSITORY": "test/repo"})
    @patch("github_ai_agents.monitors.pr.get_github_token")
    def test_check_trigger_comment_pr(self, mock_get_token):
        """Test checking trigger comment in PR."""
        mock_get_token.return_value = "test-token"
        monitor = PRMonitor()

        with patch.object(monitor.security_manager, "check_trigger_comment") as mock_check:
            mock_check.return_value = ("fix", "claude", "AndrewAltimit")

            pr = {
                "number": 10,
                "body": "PR with [Fix][Claude]",
                "author": {"login": "user1"},
            }

            result = monitor._check_trigger_comment(pr)
            assert result == ("fix", "claude", "AndrewAltimit")

    @patch.dict(os.environ, {"GITHUB_REPOSITORY": "test/repo"})
    @patch("github_ai_agents.monitors.pr.get_github_token")
    @patch("github_ai_agents.monitors.pr.run_gh_command")
    def test_process_single_pr_with_changes_requested(self, mock_gh_command, mock_get_token):
        """Test processing PR with changes requested."""
        mock_get_token.return_value = "test-token"
        monitor = PRMonitor()

        # Mock agent
        mock_agent = MagicMock()
        mock_agent.is_available.return_value = True
        mock_agent.get_trigger_keyword.return_value = "claude"
        monitor.agents = {"claude": mock_agent}

        # Mock methods
        with patch.object(monitor, "_check_trigger_comment") as mock_trigger:
            mock_trigger.return_value = ("fix", "claude", "AndrewAltimit")

            with patch.object(monitor.security_manager, "perform_full_security_check") as mock_security:
                mock_security.return_value = (True, "")

                with patch.object(monitor, "_get_pr_reviews") as mock_reviews:
                    mock_reviews.return_value = [
                        {
                            "state": "CHANGES_REQUESTED",
                            "body": "Please fix these issues",
                            "user": {"login": "reviewer1"},
                        }
                    ]

                    with patch.object(monitor, "_has_agent_addressed") as mock_addressed:
                        mock_addressed.return_value = False

                        with patch.object(monitor, "_handle_review_feedback") as mock_handle:
                            pr = {"number": 10, "title": "Test PR", "body": "PR body"}

                            monitor._process_single_pr(pr)

                            # Should handle review feedback
                            mock_handle.assert_called_once()

    @patch.dict(os.environ, {"GITHUB_REPOSITORY": "test/repo"})
    @patch("github_ai_agents.monitors.pr.get_github_token")
    def test_extract_review_items(self, mock_get_token):
        """Test extracting review items."""
        mock_get_token.return_value = "test-token"
        monitor = PRMonitor()

        review = {
            "body": """
            Here are my review comments:
            1. Fix the typo in line 10
            2. Add error handling
            - Update documentation
            * Run tests
            """,
            "user": {"login": "reviewer"},
        }

        items = monitor._extract_review_items(review)

        assert len(items) >= 4
        assert any("typo" in item["text"] for item in items)
        assert any("error handling" in item["text"] for item in items)
        assert any("documentation" in item["text"] for item in items)
        assert any("tests" in item["text"] for item in items)

    @patch.dict(os.environ, {"GITHUB_REPOSITORY": "test/repo"})
    @patch("github_ai_agents.monitors.pr.get_github_token")
    @patch("github_ai_agents.monitors.pr.run_gh_command")
    def test_post_error_comment(self, mock_gh_command, mock_get_token):
        """Test posting error comment."""
        mock_get_token.return_value = "test-token"
        monitor = PRMonitor()

        monitor._post_error_comment(10, "Test error message", "pr")

        # Should call gh command with correct parameters
        mock_gh_command.assert_called_once()
        call_args = mock_gh_command.call_args[0][0]
        assert call_args[0] == "pr"
        assert call_args[1] == "comment"
        assert call_args[2] == "10"
        assert "--repo" in call_args
        assert "test/repo" in call_args

        # Check comment body
        body_index = call_args.index("--body") + 1
        body = call_args[body_index]
        assert "[AI Agent]" in body
        assert "Test error message" in body
