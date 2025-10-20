"""Unit tests for ClaudeExecutor."""

import subprocess
from unittest.mock import MagicMock, patch

import pytest
from economic_agents.agent.llm.executors import ClaudeExecutor


class TestClaudeExecutor:
    """Tests for ClaudeExecutor class."""

    def test_initialization_default_config(self):
        """Test ClaudeExecutor initializes with default configuration."""
        executor = ClaudeExecutor()

        assert executor.node_version == "22.16.0"
        assert executor.timeout == 900  # 15 minutes
        assert executor.unattended is True

    def test_initialization_custom_config(self):
        """Test ClaudeExecutor initializes with custom configuration."""
        config = {
            "node_version": "20.0.0",
            "llm_timeout": 600,  # 10 minutes
        }
        executor = ClaudeExecutor(config)

        assert executor.node_version == "20.0.0"
        assert executor.timeout == 600
        assert executor.unattended is True  # Always True

    @patch("economic_agents.agent.llm.executors.claude.subprocess.run")
    def test_execute_success(self, mock_run):
        """Test successful Claude execution via stdin."""
        # Setup mock
        mock_result = MagicMock()
        mock_result.stdout = '{"task_work_hours": 1.0, "company_work_hours": 0.0}'
        mock_run.return_value = mock_result

        # Execute
        executor = ClaudeExecutor()
        response = executor.execute("Test prompt")

        # Verify
        assert response == '{"task_work_hours": 1.0, "company_work_hours": 0.0}'
        mock_run.assert_called_once()

        # Verify command uses stdin with -p flag
        call_args = mock_run.call_args
        command_list = call_args[0][0]
        assert command_list[0] == "bash"
        assert command_list[1] == "-c"
        command = command_list[2]
        assert "claude -p" in command
        assert "--dangerously-skip-permissions" in command
        assert call_args[1]["input"] == "Test prompt"
        assert call_args[1]["text"] is True
        assert call_args[1]["capture_output"] is True

    @patch("economic_agents.agent.llm.executors.claude.subprocess.run")
    def test_execute_timeout(self, mock_run):
        """Test Claude execution timeout."""
        mock_run.side_effect = subprocess.TimeoutExpired("claude", 900)

        # Execute and expect timeout
        executor = ClaudeExecutor()
        with pytest.raises(TimeoutError) as exc_info:
            executor.execute("Test prompt")

        assert "900s" in str(exc_info.value)
        assert "15.0 minutes" in str(exc_info.value)

    @patch("economic_agents.agent.llm.executors.claude.subprocess.run")
    def test_execute_custom_timeout(self, mock_run):
        """Test Claude execution with custom timeout."""
        mock_result = MagicMock()
        mock_result.stdout = '{"response": "ok"}'
        mock_run.return_value = mock_result

        # Execute with custom timeout
        executor = ClaudeExecutor()
        executor.execute("Test prompt", timeout=300)  # 5 minutes

        # Verify timeout was used
        call_args = mock_run.call_args
        assert call_args[1]["timeout"] == 300

    @patch("economic_agents.agent.llm.executors.claude.subprocess.run")
    def test_execute_failure(self, mock_run):
        """Test Claude execution failure."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "claude", stderr="Claude error")

        # Execute and expect runtime error
        executor = ClaudeExecutor()
        with pytest.raises(RuntimeError) as exc_info:
            executor.execute("Test prompt")

        assert "Claude execution failed" in str(exc_info.value)

    @patch("economic_agents.agent.llm.executors.claude.subprocess.run")
    def test_execute_unexpected_error(self, mock_run):
        """Test Claude execution with unexpected error."""
        mock_run.side_effect = ValueError("Unexpected error")

        # Execute and expect runtime error
        executor = ClaudeExecutor()
        with pytest.raises(RuntimeError) as exc_info:
            executor.execute("Test prompt")

        assert "Unexpected error during Claude execution" in str(exc_info.value)

    @patch("economic_agents.agent.llm.executors.claude.subprocess.run")
    def test_execute_uses_nvm(self, mock_run):
        """Test that execution uses nvm with correct node version."""
        mock_result = MagicMock()
        mock_result.stdout = '{"response": "ok"}'
        mock_run.return_value = mock_result

        executor = ClaudeExecutor({"node_version": "18.0.0"})
        executor.execute("Test prompt")

        # Verify nvm command structure
        call_args = mock_run.call_args
        command_list = call_args[0][0]
        command = command_list[2]
        assert "source ~/.nvm/nvm.sh" in command
        assert "nvm use 18.0.0" in command

    @patch("economic_agents.agent.llm.executors.claude.subprocess.run")
    def test_execute_with_long_prompt(self, mock_run):
        """Test execution with a very long prompt."""
        mock_result = MagicMock()
        mock_result.stdout = '{"response": "ok"}'
        mock_run.return_value = mock_result

        # Create a long prompt
        long_prompt = "A" * 10000

        executor = ClaudeExecutor()
        executor.execute(long_prompt)

        # Verify prompt was passed via stdin
        call_args = mock_run.call_args
        assert call_args[1]["input"] == long_prompt
