"""Tests for issue and PR monitors."""

import json
import os
from unittest.mock import patch

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
    def test_has_agent_comment(self, mock_get_token):
        """Test checking for agent comments."""
        mock_get_token.return_value = "test-token"
        monitor = IssueMonitor()

        # Test with agent comment present
        comments = [
            {"body": "Regular comment"},
            {"body": "[AI Agent] I've created a PR to address this issue..."},
        ]
        assert monitor.has_agent_comment(comments) is True

        # Test without agent comment
        comments = [
            {"body": "Regular comment"},
            {"body": "Another regular comment"},
        ]
        assert monitor.has_agent_comment(comments) is False

    @patch.dict(os.environ, {"GITHUB_REPOSITORY": "test/repo"})
    @patch("github_ai_agents.monitors.issue.get_github_token")
    def test_filter_issues_time_window(self, mock_get_token):
        """Test filtering issues by time window."""
        mock_get_token.return_value = "test-token"
        monitor = IssueMonitor()

        # Create test issues with different ages
        from datetime import datetime, timedelta, timezone

        now = datetime.now(timezone.utc)
        recent_issue = {
            "number": 1,
            "updated_at": (now - timedelta(hours=12)).isoformat(),
            "title": "Recent issue",
        }
        old_issue = {
            "number": 2,
            "updated_at": (now - timedelta(hours=48)).isoformat(),
            "title": "Old issue",
        }

        issues = [recent_issue, old_issue]
        filtered = monitor._filter_issues_by_time_window(issues, cutoff_hours=24)

        assert len(filtered) == 1
        assert filtered[0]["number"] == 1

    @patch.dict(os.environ, {"GITHUB_REPOSITORY": "test/repo"})
    @patch("github_ai_agents.monitors.issue.get_github_token")
    @patch("github_ai_agents.monitors.issue.run_gh_command")
    def test_get_issue_comments(self, mock_gh_command, mock_get_token):
        """Test getting issue comments."""
        mock_get_token.return_value = "test-token"
        monitor = IssueMonitor()

        # Mock gh command response
        mock_comments = [
            {"body": "Comment 1", "user": {"login": "user1"}},
            {"body": "Comment 2", "user": {"login": "user2"}},
        ]
        mock_gh_command.return_value = (0, json.dumps(mock_comments), "")

        comments = monitor.get_issue_comments(123)
        assert len(comments) == 2
        assert comments[0]["body"] == "Comment 1"

    @patch.dict(os.environ, {"GITHUB_REPOSITORY": "test/repo"})
    @patch("github_ai_agents.monitors.issue.get_github_token")
    def test_needs_more_info(self, mock_get_token):
        """Test checking if issue needs more info."""
        mock_get_token.return_value = "test-token"
        monitor = IssueMonitor()

        # Test issue with insufficient description
        issue_short = {"body": "Bug"}
        assert monitor._needs_more_info(issue_short) is True

        # Test issue with sufficient description
        issue_detailed = {
            "body": "This is a detailed bug report with steps to reproduce the issue. "
            "First, do this. Then, do that. Expected: X. Actual: Y."
        }
        assert monitor._needs_more_info(issue_detailed) is False

        # Test issue with no body
        issue_no_body = {"body": None}
        assert monitor._needs_more_info(issue_no_body) is True


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
    def test_has_agent_addressed_review(self, mock_get_token):
        """Test checking if agent has addressed review."""
        mock_get_token.return_value = "test-token"
        monitor = PRMonitor()

        # Test with addressed comment
        comments = [
            {"body": "Regular comment"},
            {"body": "[AI Agent] I've reviewed and addressed the feedback..."},
        ]
        assert monitor.has_agent_addressed_review(comments) is True

        # Test without addressed comment
        comments = [
            {"body": "Regular comment"},
            {"body": "[AI Agent] Looking into this..."},
        ]
        assert monitor.has_agent_addressed_review(comments) is False

    @patch.dict(os.environ, {"GITHUB_REPOSITORY": "test/repo"})
    @patch("github_ai_agents.monitors.pr.get_github_token")
    @patch("github_ai_agents.monitors.pr.run_gh_command")
    def test_get_pr_reviews(self, mock_gh_command, mock_get_token):
        """Test getting PR reviews."""
        mock_get_token.return_value = "test-token"
        monitor = PRMonitor()

        # Mock gh command response
        mock_reviews = [
            {
                "state": "CHANGES_REQUESTED",
                "user": {"login": "reviewer1"},
                "body": "Please fix these issues",
            },
            {"state": "APPROVED", "user": {"login": "reviewer2"}, "body": "LGTM"},
        ]
        mock_gh_command.return_value = (0, json.dumps(mock_reviews), "")

        reviews = monitor.get_pr_reviews(456)
        assert len(reviews) == 2
        assert reviews[0]["state"] == "CHANGES_REQUESTED"

    @patch.dict(os.environ, {"GITHUB_REPOSITORY": "test/repo"})
    @patch("github_ai_agents.monitors.pr.get_github_token")
    def test_extract_review_items(self, mock_get_token):
        """Test extracting review items from comments."""
        mock_get_token.return_value = "test-token"
        monitor = PRMonitor()

        review_body = """
        Here are my review comments:

        1. Fix the typo in line 10
        2. Add error handling for the API call
        3. Update the documentation

        Also, please run the tests.
        """

        comment = {"body": "Please fix line 15", "path": "main.py", "line": 15}

        items = monitor._extract_review_items(review_body, [comment])

        # Should extract numbered items from review body
        assert any("typo" in item["text"] for item in items)
        assert any("error handling" in item["text"] for item in items)
        assert any("documentation" in item["text"] for item in items)

        # Should include inline comment
        assert any("line 15" in item["text"] for item in items)

    @patch.dict(os.environ, {"GITHUB_REPOSITORY": "test/repo"})
    @patch("github_ai_agents.monitors.pr.get_github_token")
    def test_parse_pipeline_error(self, mock_get_token):
        """Test parsing pipeline errors."""
        mock_get_token.return_value = "test-token"
        monitor = PRMonitor()

        # Test with linting errors
        error_log = """
        Running flake8...
        main.py:10:1: E302 expected 2 blank lines, found 1
        main.py:20:80: E501 line too long (85 > 79 characters)
        test.py:5:1: F401 'os' imported but unused
        """

        errors = monitor._parse_pipeline_error(error_log)
        assert len(errors) > 0
        assert any("E302" in error for error in errors)
        assert any("E501" in error for error in errors)
        assert any("F401" in error for error in errors)
