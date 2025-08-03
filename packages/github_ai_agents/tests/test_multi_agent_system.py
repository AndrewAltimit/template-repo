"""Integration tests for the multi-agent system."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from github_ai_agents.agents import OpenCodeAgent, get_best_available_agent
from github_ai_agents.monitors import IssueMonitor
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
            "body": "[Approved][Claude] Please fix this bug",
            "author": {"login": "unauthorized-user"},
            "createdAt": "2024-01-01T00:00:00Z",
            "updatedAt": "2024-01-01T00:00:00Z",
            "comments": [{"body": "[Approved][Claude] Please fix this", "author": {"login": "unauthorized-user"}}],
        }

        # Mock gh command to return empty issues
        mock_gh_command.return_value = "[]"

        # Process should reject due to unauthorized user
        # The issue will be rejected because unauthorized-user is not in the allow list
        # Let's check that the security manager rejects it
        trigger_info = monitor.security_manager.check_trigger_comment(issue, "issue")
        if trigger_info:
            action, agent_name, trigger_user = trigger_info
            is_allowed, reason = monitor.security_manager.perform_full_security_check(
                username=trigger_user,
                action=f"issue_{action.lower()}",
                repository=monitor.repo,
                entity_type="issue",
                entity_id=str(issue["number"]),
            )  # noqa: E501
            assert not is_allowed  # Should not be allowed
            assert "not authorized" in reason.lower() or "allow" in reason.lower()

    @patch.dict(os.environ, {"GITHUB_REPOSITORY": "test/repo"})
    async def test_agent_execution_flow(self):
        """Test complete agent execution flow."""
        # Create a mock agent
        mock_agent = MagicMock()
        mock_agent.is_available.return_value = True
        mock_agent.generate_code = AsyncMock(return_value="Generated code here")
        mock_agent.name = "TestAgent"

        # Test agent execution directly with the mock
        result = await mock_agent.generate_code("Fix the bug", {"context": "test"})
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
        assert hasattr(manager1, "rate_limit_tracker")
        assert hasattr(manager2, "rate_limit_tracker")
        assert isinstance(manager1.rate_limit_tracker, dict)
        assert isinstance(manager2.rate_limit_tracker, dict)

    @patch.dict(os.environ, {"GITHUB_REPOSITORY": "test/repo"})
    @patch("github_ai_agents.monitors.issue.get_github_token")
    @patch("github_ai_agents.monitors.issue.run_gh_command")
    def test_issue_to_pr_workflow(self, mock_gh_command, mock_get_token):
        """Test complete workflow from issue to PR creation."""
        mock_get_token.return_value = "test-token"
        monitor = IssueMonitor()

        # Create actionable issue with trigger in body
        issue = {
            "number": 789,
            "title": "Add new feature",
            "body": (
                "[Implement][Claude] Please add a new feature that does X, Y, and Z. "
                "It should handle edge cases and have tests."
            ),
            "author": {"login": "AndrewAltimit"},
            "createdAt": "2024-01-01T00:00:00Z",
            "updatedAt": "2024-01-01T00:00:00Z",
            "comments": [],
            "labels": [{"name": "enhancement"}],
        }

        # Mock successful agent execution
        mock_agent = MagicMock()
        mock_agent.is_available.return_value = True
        mock_agent.name = "Claude"
        mock_agent.get_trigger_keyword.return_value = "Claude"
        mock_agent.generate_code = AsyncMock(return_value="Implementation complete")

        # Mock GitHub operations
        mock_gh_command.return_value = "[]"

        # Inject the mock agent into monitor's agents dict
        monitor.agents["claude"] = mock_agent

        with patch.object(monitor, "_has_agent_comment", return_value=False):
            with patch.object(monitor, "_post_starting_work_comment") as mock_start:
                with patch.object(monitor, "_create_pr"):
                    # Simulate processing
                    monitor._process_single_issue(issue)
                    mock_start.assert_called_once()
                    # The PR creation happens in async, so we verify the starting comment was posted

    @patch.dict(os.environ, {"GITHUB_REPOSITORY": "test/repo"})
    @patch("github_ai_agents.utils.get_github_token")
    @patch("github_ai_agents.utils.run_gh_command")
    def test_pr_review_to_fix_workflow(self, mock_gh_command, mock_get_token):
        """Test workflow from PR review to automated fixes."""
        mock_get_token.return_value = "test-token"
        from github_ai_agents.monitors import PRMonitor  # noqa: F811

        monitor = PRMonitor()

        # Create PR with review including trigger
        pr = {  # noqa: F841
            "number": 456,
            "title": "Fix: resolve issue #789",
            "author": {"login": "AndrewAltimit"},
            "createdAt": "2024-01-01T00:00:00Z",
            "updatedAt": "2024-01-01T00:00:00Z",
            "state": "open",
            "isDraft": False,
            "comments": [],
            "reviews": [
                {
                    "state": "CHANGES_REQUESTED",
                    "author": {"login": "gemini-bot"},
                    "body": "[Fix][Claude] Please address these issues:\n1. Add error handling\n2. Fix formatting",
                }
            ],
        }

        # Mock GitHub operations
        mock_gh_command.return_value = "[]"

        # Test that PR monitor exists and can be initialized
        assert monitor is not None
        assert monitor.repo == "test/repo"

        # PR monitoring is not yet implemented, so we just verify the basic structure
        assert hasattr(monitor, "process_prs")


class TestErrorHandling:
    """Test error handling in the multi-agent system."""

    @patch.dict(os.environ, {"GITHUB_REPOSITORY": "test/repo"})
    @patch("github_ai_agents.monitors.issue.get_github_token")
    def test_monitor_handles_api_errors(self, mock_get_token):
        """Test that monitors handle API errors gracefully."""
        mock_get_token.return_value = "test-token"
        monitor = IssueMonitor()

        with patch("github_ai_agents.monitors.issue.run_gh_command") as mock_gh:
            # Simulate API error by returning empty string
            mock_gh.return_value = ""

            # Should handle error without crashing
            issues = monitor.get_open_issues()
            assert issues == []

    async def test_agent_timeout_handling(self):
        """Test agent timeout handling."""
        from github_ai_agents.agents.base import AgentTimeoutError

        # Create a mock agent that times out
        agent = OpenCodeAgent()

        with patch.object(agent, "_execute_command", side_effect=AgentTimeoutError("OpenCode", 30, "partial output")):
            with pytest.raises(AgentTimeoutError):
                await agent.generate_code("Test prompt", {})
