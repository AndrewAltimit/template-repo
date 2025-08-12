"""Tests for PR monitor functionality."""

import json
from unittest.mock import MagicMock, patch

import pytest
from github_ai_agents.monitors.pr import PRMonitor


@pytest.fixture
def mock_env():
    """Mock environment variables."""
    with patch.dict("os.environ", {"GITHUB_REPOSITORY": "test/repo", "GITHUB_TOKEN": "test-token"}):
        yield


@pytest.fixture
def pr_monitor(mock_env):
    """Create PR monitor instance."""
    with patch("github_ai_agents.config.AgentConfig"), patch("github_ai_agents.security.SecurityManager"):
        return PRMonitor()


class TestPRMonitor:
    """Test PR monitor functionality."""

    def test_initialization(self, mock_env):
        """Test PR monitor initialization."""
        with patch("github_ai_agents.config.AgentConfig"), patch("github_ai_agents.security.SecurityManager"):
            monitor = PRMonitor()
            assert monitor.repo == "test/repo"
            assert monitor.agent_tag == "[AI Agent]"

    def test_initialization_without_repo(self):
        """Test initialization fails without GITHUB_REPOSITORY."""
        with pytest.raises(RuntimeError, match="GITHUB_REPOSITORY environment variable must be set"):
            PRMonitor()

    @patch("github_ai_agents.monitors.pr.run_gh_command")
    def test_get_open_prs(self, mock_gh_command, pr_monitor):
        """Test getting open PRs."""
        mock_gh_command.return_value = json.dumps(
            [
                {
                    "number": 123,
                    "title": "Test PR",
                    "updatedAt": "2024-01-20T10:00:00Z",
                    "headRefName": "feature-branch",
                }
            ]
        )

        prs = pr_monitor.get_open_prs()
        assert len(prs) == 1
        assert prs[0]["number"] == 123

    def test_check_review_trigger(self, pr_monitor):
        """Test checking review trigger patterns."""
        # Valid trigger
        comment = {"body": "Please [Fix][Claude] this issue", "author": "testuser"}
        result = pr_monitor._check_review_trigger(comment)
        assert result == ("Fix", "Claude", "testuser")

        # Multiple triggers (takes first)
        comment = {"body": "[Address][Gemini] and [Fix][Claude]", "author": "testuser"}
        result = pr_monitor._check_review_trigger(comment)
        assert result == ("Address", "Gemini", "testuser")

        # No trigger
        comment = {"body": "Just a regular comment", "author": "testuser"}
        result = pr_monitor._check_review_trigger(comment)
        assert result is None

    @patch("github_ai_agents.monitors.pr.run_gh_command")
    def test_get_review_comments(self, mock_gh_command, pr_monitor):
        """Test getting review comments."""
        # Mock review response
        mock_gh_command.side_effect = [
            json.dumps(
                {
                    "reviews": [
                        {
                            "id": "R1",
                            "body": "Please [Fix][Claude] this",
                            "author": {"login": "reviewer1"},
                            "submittedAt": "2024-01-20T10:00:00Z",
                        }
                    ]
                }
            ),
            json.dumps(
                {
                    "comments": [
                        {
                            "id": "C1",
                            "body": "[Address][Gemini] this concern",
                            "author": {"login": "commenter1"},
                            "createdAt": "2024-01-20T11:00:00Z",
                        }
                    ]
                }
            ),
        ]

        comments = pr_monitor._get_review_comments(123)
        assert len(comments) == 2
        assert comments[0]["type"] == "review"
        assert comments[1]["type"] == "comment"

    @patch("github_ai_agents.monitors.pr.run_gh_command")
    def test_process_pr_with_security_rejection(self, mock_gh_command, pr_monitor):
        """Test PR processing with security rejection."""
        # Mock PR data
        pr = {"number": 123, "title": "Test PR", "headRefName": "feature-branch"}

        # Mock review with trigger
        mock_gh_command.side_effect = [
            # Reviews
            json.dumps(
                {
                    "reviews": [
                        {
                            "id": "R1",
                            "body": "[Fix][Claude] this issue",
                            "author": {"login": "unauthorized_user"},
                        }
                    ]
                }
            ),
            # Comments
            json.dumps({"comments": []}),
            # Security rejection comment
            None,
        ]

        # Mock security check to fail
        pr_monitor.security_manager.perform_full_security_check.return_value = (
            False,
            "User not authorized",
        )

        pr_monitor._process_single_pr(pr)

        # Verify security rejection comment was posted
        assert mock_gh_command.call_count == 3
        last_call = mock_gh_command.call_args_list[-1]
        assert "comment" in last_call[0][0]
        assert "Security Notice" in last_call[0][0][-1]

    @patch("github_ai_agents.monitors.pr.asyncio.run")
    @patch("github_ai_agents.monitors.pr.run_gh_command")
    def test_handle_review_feedback_with_valid_agent(self, mock_gh_command, mock_asyncio_run, pr_monitor):
        """Test handling review feedback with valid agent."""
        pr = {"number": 123, "title": "Test PR"}
        comment = {"id": "C1", "body": "[Fix][Claude] this"}

        # Mock Claude agent
        mock_agent = MagicMock()
        mock_agent.name = "Claude"
        pr_monitor.agents = {"claude": mock_agent}

        # Mock starting work comment
        mock_gh_command.return_value = None

        pr_monitor._handle_review_feedback(pr, comment, "Claude", "feature-branch")

        # Verify starting work comment was posted
        assert mock_gh_command.called
        assert "I'm working on addressing this review feedback using Claude" in mock_gh_command.call_args[0][0][-1]

        # Verify async implementation was called
        assert mock_asyncio_run.called

    @patch("github_ai_agents.monitors.pr.run_gh_command")
    def test_handle_review_feedback_with_containerized_agent(self, mock_gh_command, pr_monitor):
        """Test handling review feedback with containerized agent."""
        pr = {"number": 123, "title": "Test PR"}
        comment = {"id": "C1", "body": "[Fix][OpenCode] this"}

        # No OpenCode agent available (containerized)
        pr_monitor.agents = {"claude": MagicMock()}

        pr_monitor._handle_review_feedback(pr, comment, "OpenCode", "feature-branch")

        # Verify error comment mentions containerized environment
        assert mock_gh_command.called
        error_comment = mock_gh_command.call_args[0][0][-1]
        assert "only available in the containerized environment" in error_comment
        assert "openrouter-agents" in error_comment

    def test_has_responded_to_comment(self, pr_monitor):
        """Test checking if already responded to comment."""
        # Currently returns False (placeholder implementation)
        assert not pr_monitor._has_responded_to_comment(123, "C1")

    @patch("github_ai_agents.monitors.pr.run_gh_command")
    def test_continuous_monitoring(self, mock_gh_command, pr_monitor):
        """Test continuous monitoring mode."""
        # Mock to raise KeyboardInterrupt after first iteration
        pr_monitor.process_prs = MagicMock(side_effect=[None, KeyboardInterrupt()])

        pr_monitor.run_continuous(interval=0.1)

        # Verify process_prs was called
        assert pr_monitor.process_prs.called
