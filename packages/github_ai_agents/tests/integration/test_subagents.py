"""Tests for the subagent system."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from github_ai_agents.subagents import SubagentManager


class TestSubagentManager:
    """Test subagent manager functionality."""

    def test_initialization_default_path(self):
        """Test subagent manager initialization with default path."""
        manager = SubagentManager()
        assert manager.personas_dir.name == "subagents"
        assert "docs" in str(manager.personas_dir)

    def test_initialization_custom_path(self):
        """Test subagent manager initialization with custom path."""
        custom_path = Path("/tmp/test_personas")
        manager = SubagentManager(personas_dir=custom_path)
        assert manager.personas_dir == custom_path

    @patch("github_ai_agents.subagents.manager.Path.exists")
    @patch("github_ai_agents.subagents.manager.Path.glob")
    def test_load_personas(self, mock_glob, mock_exists):
        """Test loading persona definitions."""
        mock_exists.return_value = True

        # Create mock persona files
        mock_tech_lead = MagicMock()
        mock_tech_lead.stem = "tech-lead"
        mock_tech_lead.read_text.return_value = "# Tech Lead Persona\nContent here"

        mock_qa = MagicMock()
        mock_qa.stem = "qa-reviewer"
        mock_qa.read_text.return_value = "# QA Reviewer Persona\nContent here"

        mock_glob.return_value = [mock_tech_lead, mock_qa]

        # Create manager and trigger persona loading
        manager = SubagentManager()

        # Manually call _load_personas since we're mocking
        with patch("builtins.open", MagicMock()):
            personas = manager._load_personas()

        assert len(personas) == 2
        assert "tech-lead" in personas
        assert "qa-reviewer" in personas

    def test_list_personas(self):
        """Test listing available personas."""
        manager = SubagentManager()
        # Mock some personas
        manager.personas = {
            "tech-lead": "content",
            "qa-reviewer": "content",
            "security-auditor": "content",
        }

        personas = manager.list_personas()
        assert len(personas) == 3
        assert "tech-lead" in personas
        assert "qa-reviewer" in personas
        assert "security-auditor" in personas

    def test_build_prompt(self):
        """Test prompt building with persona and context."""
        manager = SubagentManager()
        manager.personas = {"tech-lead": "You are a technical leader..."}

        prompt = manager._build_prompt(
            "tech-lead",
            "Implement user authentication",
            {"issue_number": 123, "branch_name": "feature-auth"},
        )

        assert "# AI Agent Persona" in prompt
        assert "You are a technical leader" in prompt
        assert "# Task" in prompt
        assert "Implement user authentication" in prompt
        assert "# Additional Context" in prompt
        assert "issue_number" in prompt
        assert "123" in prompt

    @patch("github_ai_agents.subagents.manager.get_best_available_agent")
    def test_execute_with_persona_no_agent(self, mock_get_agent):
        """Test execution when no agent is available."""
        mock_get_agent.return_value = None
        manager = SubagentManager()
        manager.personas = {"tech-lead": "content"}

        success, stdout, stderr = manager.execute_with_persona("tech-lead", "Task")

        assert success is False
        assert stdout == ""
        assert "No AI agents available" in stderr

    def test_execute_with_unknown_persona(self):
        """Test execution with unknown persona."""
        manager = SubagentManager()
        manager.personas = {"tech-lead": "content"}

        success, stdout, stderr = manager.execute_with_persona("unknown-persona", "Task")

        assert success is False
        assert stdout == ""
        assert "Persona 'unknown-persona' not found" in stderr
        assert "Available: tech-lead" in stderr

    @patch("github_ai_agents.subagents.manager.get_best_available_agent")
    @patch("github_ai_agents.subagents.manager.asyncio.get_event_loop")
    def test_execute_with_persona_success(self, mock_loop, mock_get_agent):
        """Test successful execution with persona."""
        # Mock agent
        mock_agent = MagicMock()
        mock_agent.__class__.__name__ = "TestAgent"
        mock_get_agent.return_value = mock_agent

        # Mock event loop
        mock_loop_instance = MagicMock()
        mock_loop_instance.run_until_complete.return_value = "Generated code output"
        mock_loop.return_value = mock_loop_instance

        manager = SubagentManager()
        manager.personas = {"tech-lead": "You are a tech lead..."}

        success, stdout, stderr = manager.execute_with_persona("tech-lead", "Implement feature X", {"context": "test"})

        assert success is True
        assert stdout == "Generated code output"
        assert stderr == ""

    @patch("github_ai_agents.subagents.manager.ClaudeAgent")
    @patch("github_ai_agents.subagents.manager.asyncio.get_event_loop")
    def test_execute_with_specific_agent(self, mock_loop, mock_claude_class):
        """Test execution with specific agent requested."""
        # Mock agent instance
        mock_agent = MagicMock()
        mock_agent.__class__.__name__ = "ClaudeAgent"
        mock_claude_class.return_value = mock_agent

        # Mock event loop
        mock_loop_instance = MagicMock()
        mock_loop_instance.run_until_complete.return_value = "Claude output"
        mock_loop.return_value = mock_loop_instance

        manager = SubagentManager()
        manager.personas = {"tech-lead": "content"}

        success, stdout, stderr = manager.execute_with_persona("tech-lead", "Task", agent_name="claude")

        assert success is True
        assert stdout == "Claude output"
        mock_claude_class.assert_called_once()

    def test_execute_with_unknown_agent(self):
        """Test execution with unknown agent name."""
        manager = SubagentManager()
        manager.personas = {"tech-lead": "content"}

        success, stdout, stderr = manager.execute_with_persona("tech-lead", "Task", agent_name="unknown-agent")

        assert success is False
        assert "Unknown agent: unknown-agent" in stderr


class TestConvenienceFunctions:
    """Test convenience functions for common personas."""

    @patch("github_ai_agents.subagents.manager.SubagentManager")
    def test_implement_issue_with_tech_lead(self, mock_manager_class):
        """Test tech lead convenience function."""
        from github_ai_agents.subagents.manager import implement_issue_with_tech_lead

        # Mock manager instance
        mock_manager = MagicMock()
        mock_manager.execute_with_persona.return_value = (True, "Success output", "")
        mock_manager_class.return_value = mock_manager

        # Test data
        issue_data = {
            "number": 123,
            "title": "Add feature X",
            "body": "Please implement feature X with Y and Z",
        }

        success, output = implement_issue_with_tech_lead(issue_data, "feature-x")

        assert success is True
        assert output == "Success output"

        # Verify the call
        mock_manager.execute_with_persona.assert_called_once()
        call_args = mock_manager.execute_with_persona.call_args
        assert call_args[0][0] == "tech-lead"
        assert "Please implement feature X" in call_args[0][1]

    @patch("github_ai_agents.subagents.manager.SubagentManager")
    def test_review_pr_with_qa(self, mock_manager_class):
        """Test QA reviewer convenience function."""
        from github_ai_agents.subagents.manager import review_pr_with_qa

        # Mock manager instance
        mock_manager = MagicMock()
        mock_manager.execute_with_persona.return_value = (True, "Review complete", "")
        mock_manager_class.return_value = mock_manager

        # Test data
        pr_data = {"number": 456, "title": "Fix: resolve issue #123"}
        review_comments = [
            {"body": "Please add error handling"},
            {"body": "Fix the formatting issue"},
        ]

        success, output = review_pr_with_qa(pr_data, review_comments)

        assert success is True
        assert output == "Review complete"

        # Verify the call
        mock_manager.execute_with_persona.assert_called_once()
        call_args = mock_manager.execute_with_persona.call_args
        assert call_args[0][0] == "qa-reviewer"
        assert "add error handling" in call_args[0][1]
        assert "Fix the formatting" in call_args[0][1]
