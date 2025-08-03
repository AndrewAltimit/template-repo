"""Integration tests for the multi-agent system."""

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from github_ai_agents.agents import OpenCodeAgent, get_best_available_agent
from github_ai_agents.monitors import IssueMonitor, PRMonitor
from github_ai_agents.security import SecurityManager


class TestMultiAgentIntegration:
    """Test multi-agent system integration."""

    @patch("github_ai_agents.agents.ClaudeAgent.is_available")
    @patch("github_ai_agents.agents.OpenCodeAgent.is_available")
    @patch("github_ai_agents.agents.GeminiAgent.is_available")
    def test_get_best_available_agent(self, mock_gemini, mock_opencode, mock_claude):
        """Test agent selection based on availability."""
        # Test when Claude is available (highest priority)
        mock_claude.return_value = True
        mock_opencode.return_value = True
        mock_gemini.return_value = True
        agent = get_best_available_agent()
        assert agent is not None
        assert agent.__class__.__name__ == "ClaudeAgent"

        # Test when only OpenCode is available
        mock_claude.return_value = False
        mock_opencode.return_value = True
        mock_gemini.return_value = False
        agent = get_best_available_agent()
        assert agent is not None
        assert agent.__class__.__name__ == "OpenCodeAgent"

        # Test when no agents are available
        mock_claude.return_value = False
        mock_opencode.return_value = False
        mock_gemini.return_value = False
        agent = get_best_available_agent()
        assert agent is None

    @patch.dict(os.environ, {"GITHUB_REPOSITORY": "test/repo"})
    @patch("github_ai_agents.monitors.issue.get_github_token")
    @patch("github_ai_agents.monitors.issue.run_gh_command")
    def test_issue_monitor_security_integration(self, mock_gh_command, mock_get_token):
        """Test issue monitor with security manager integration."""
        mock_get_token.return_value = "test-token"
        monitor = IssueMonitor()

        # Create a test issue with trigger from unauthorized user
        issue = {
            "number": 123,
            "title": "Test issue",
            "body": "Please fix this bug",
            "user": {"login": "unauthorized-user"},
            "updated_at": "2024-01-01T00:00:00Z",
        }

        # Mock comments with trigger
        comments = [
            {
                "body": "[Approved][Claude] Please fix this",
                "user": {"login": "unauthorized-user"},
            }
        ]
        mock_gh_command.return_value = (0, "[]", "")  # Empty comments initially

        # Process should reject due to unauthorized user
        with patch.object(monitor, "get_issue_comments", return_value=comments):
            with patch.object(monitor, "post_comment") as mock_post:
                monitor._process_actionable_issue(issue)
                # Should post security rejection message
                assert mock_post.called
                call_args = mock_post.call_args[0]
                assert "not authorized" in call_args[1].lower()

    @patch.dict(os.environ, {"GITHUB_REPOSITORY": "test/repo"})
    @patch("github_ai_agents.monitors.pr.get_github_token")
    async def test_agent_execution_flow(self, mock_get_token):
        """Test complete agent execution flow."""
        mock_get_token.return_value = "test-token"

        # Create a mock agent
        mock_agent = MagicMock()
        mock_agent.is_available.return_value = True
        mock_agent.generate_code = AsyncMock(return_value="Generated code here")

        with patch("github_ai_agents.agents.get_best_available_agent", return_value=mock_agent):
            # Test agent execution
            agent = get_best_available_agent()
            assert agent is not None

            # Run async generation
            result = await agent.generate_code("Fix the bug", {"context": "test"})
            assert result == "Generated code here"
            mock_agent.generate_code.assert_called_once_with("Fix the bug", {"context": "test"})

    def test_security_manager_singleton_behavior(self):
        """Test that security manager maintains consistent state."""
        manager1 = SecurityManager()
        manager2 = SecurityManager()

        # Both should have the same configuration
        assert manager1.config["allow_list"] == manager2.config["allow_list"]
        assert manager1.config["enabled"] == manager2.config["enabled"]

        # Rate limit state should be independent (each instance has its own state)
        # This is intentional to allow for distributed deployments
        manager1.check_rate_limit("testuser", "action")
        assert manager1._rate_limit_cache != {}
        # manager2 has its own cache
        assert hasattr(manager2, "_rate_limit_cache")

    @patch.dict(os.environ, {"GITHUB_REPOSITORY": "test/repo"})
    @patch("github_ai_agents.monitors.issue.get_github_token")
    @patch("github_ai_agents.monitors.issue.run_gh_command")
    def test_issue_to_pr_workflow(self, mock_gh_command, mock_get_token):
        """Test complete workflow from issue to PR creation."""
        mock_get_token.return_value = "test-token"
        monitor = IssueMonitor()

        # Create actionable issue
        issue = {
            "number": 789,
            "title": "Add new feature",
            "body": "Please add a new feature that does X, Y, and Z. " "It should handle edge cases and have tests.",
            "user": {"login": "AndrewAltimit"},
            "updated_at": "2024-01-01T00:00:00Z",
            "labels": [{"name": "enhancement"}],
        }

        # Mock successful agent execution
        mock_agent = MagicMock()
        mock_agent.is_available.return_value = True
        mock_agent.generate_code = AsyncMock(return_value="Implementation complete")

        # Mock GitHub operations
        mock_gh_command.return_value = (0, "[]", "")  # Empty comments

        with patch.object(monitor, "get_issue_comments", return_value=[]):
            with patch.object(monitor, "_has_trigger_keyword", return_value=True):
                with patch.object(monitor, "_get_trigger_info", return_value=("Implement", "Claude", "AndrewAltimit")):
                    with patch.object(monitor, "_process_actionable_issue") as mock_process:
                        # Simulate processing
                        monitor._process_single_issue(issue)
                        mock_process.assert_called_once_with(issue)

    @patch.dict(os.environ, {"GITHUB_REPOSITORY": "test/repo"})
    @patch("github_ai_agents.monitors.pr.get_github_token")
    def test_pr_review_to_fix_workflow(self, mock_get_token):
        """Test workflow from PR review to automated fixes."""
        mock_get_token.return_value = "test-token"
        monitor = PRMonitor()

        # Create PR with review
        pr = {
            "number": 456,
            "title": "Fix: resolve issue #789",
            "user": {"login": "AndrewAltimit"},
            "updated_at": "2024-01-01T00:00:00Z",
            "state": "open",
            "draft": False,
        }

        # Mock review with requested changes
        reviews = [
            {
                "state": "CHANGES_REQUESTED",
                "user": {"login": "gemini-bot"},
                "body": "Please address these issues:\n1. Add error handling\n2. Fix formatting",
            }
        ]

        # Mock successful fix
        with patch.object(monitor, "get_pr_reviews", return_value=reviews):
            with patch.object(monitor, "has_agent_addressed_review", return_value=False):
                with patch.object(monitor, "_has_trigger_keyword", return_value=True):
                    with patch.object(monitor, "_get_trigger_info", return_value=("Fix", "Claude", "AndrewAltimit")):
                        with patch.object(monitor, "_implement_review_feedback") as mock_implement:
                            monitor._process_single_pr(pr)
                            # Should attempt to implement feedback
                            assert mock_implement.called


class TestErrorHandling:
    """Test error handling in the multi-agent system."""

    @patch.dict(os.environ, {"GITHUB_REPOSITORY": "test/repo"})
    @patch("github_ai_agents.monitors.issue.get_github_token")
    def test_monitor_handles_api_errors(self, mock_get_token):
        """Test that monitors handle API errors gracefully."""
        mock_get_token.return_value = "test-token"
        monitor = IssueMonitor()

        with patch("github_ai_agents.monitors.issue.run_gh_command") as mock_gh:
            # Simulate API error
            mock_gh.return_value = (1, "", "API rate limit exceeded")

            # Should handle error without crashing
            issues = monitor.get_issues()
            assert issues == []

    @patch("github_ai_agents.agents.OpenCodeAgent._run_command")
    async def test_agent_timeout_handling(self, mock_run):
        """Test agent timeout handling."""
        agent = OpenCodeAgent()

        # Simulate timeout
        mock_run.side_effect = asyncio.TimeoutError()

        with pytest.raises(Exception):  # Should raise appropriate exception
            await agent.generate_code("Test prompt", {})
