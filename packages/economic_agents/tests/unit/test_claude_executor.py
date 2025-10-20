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
    @patch("economic_agents.agent.llm.executors.claude.tempfile.NamedTemporaryFile")
    def test_execute_success(self, mock_tempfile, mock_run):
        """Test successful Claude execution."""
        # Setup mocks
        mock_file = MagicMock()
        mock_file.name = "/tmp/test_prompt.txt"
        mock_tempfile.return_value.__enter__.return_value = mock_file

        mock_result = MagicMock()
        mock_result.stdout = '{"task_work_hours": 1.0, "company_work_hours": 0.0}'
        mock_run.return_value = mock_result

        # Execute
        executor = ClaudeExecutor()
        response = executor.execute("Test prompt")

        # Verify
        assert response == '{"task_work_hours": 1.0, "company_work_hours": 0.0}'
        mock_run.assert_called_once()

        # Verify command includes correct flags
        call_args = mock_run.call_args
        command = call_args[0][0]
        assert "claude --prompt-file" in command[-1]
        assert "--dangerously-skip-permissions" in command[-1]

    @patch("economic_agents.agent.llm.executors.claude.subprocess.run")
    @patch("economic_agents.agent.llm.executors.claude.tempfile.NamedTemporaryFile")
    def test_execute_timeout(self, mock_tempfile, mock_run):
        """Test Claude execution timeout."""
        # Setup mocks
        mock_file = MagicMock()
        mock_file.name = "/tmp/test_prompt.txt"
        mock_tempfile.return_value.__enter__.return_value = mock_file

        mock_run.side_effect = subprocess.TimeoutExpired("claude", 900)

        # Execute and expect timeout
        executor = ClaudeExecutor()
        with pytest.raises(TimeoutError) as exc_info:
            executor.execute("Test prompt")

        assert "900s" in str(exc_info.value)
        assert "15.0 minutes" in str(exc_info.value)

    @patch("economic_agents.agent.llm.executors.claude.subprocess.run")
    @patch("economic_agents.agent.llm.executors.claude.tempfile.NamedTemporaryFile")
    def test_execute_custom_timeout(self, mock_tempfile, mock_run):
        """Test Claude execution with custom timeout."""
        # Setup mocks
        mock_file = MagicMock()
        mock_file.name = "/tmp/test_prompt.txt"
        mock_tempfile.return_value.__enter__.return_value = mock_file

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
    @patch("economic_agents.agent.llm.executors.claude.tempfile.NamedTemporaryFile")
    def test_execute_failure(self, mock_tempfile, mock_run):
        """Test Claude execution failure."""
        # Setup mocks
        mock_file = MagicMock()
        mock_file.name = "/tmp/test_prompt.txt"
        mock_tempfile.return_value.__enter__.return_value = mock_file

        mock_run.side_effect = subprocess.CalledProcessError(1, "claude", stderr="Claude error")

        # Execute and expect runtime error
        executor = ClaudeExecutor()
        with pytest.raises(RuntimeError) as exc_info:
            executor.execute("Test prompt")

        assert "Claude execution failed" in str(exc_info.value)

    @patch("economic_agents.agent.llm.executors.claude.subprocess.run")
    @patch("economic_agents.agent.llm.executors.claude.tempfile.NamedTemporaryFile")
    @patch("economic_agents.agent.llm.executors.claude.os.path.exists")
    @patch("economic_agents.agent.llm.executors.claude.os.unlink")
    def test_execute_cleans_up_temp_file(self, mock_unlink, mock_exists, mock_tempfile, mock_run):
        """Test that temporary prompt file is cleaned up."""
        # Setup mocks
        mock_file = MagicMock()
        mock_file.name = "/tmp/test_prompt.txt"
        mock_tempfile.return_value.__enter__.return_value = mock_file
        mock_exists.return_value = True

        mock_result = MagicMock()
        mock_result.stdout = '{"response": "ok"}'
        mock_run.return_value = mock_result

        # Execute
        executor = ClaudeExecutor()
        executor.execute("Test prompt")

        # Verify cleanup
        mock_unlink.assert_called_once_with("/tmp/test_prompt.txt")

    @patch("economic_agents.agent.llm.executors.claude.subprocess.run")
    @patch("economic_agents.agent.llm.executors.claude.tempfile.NamedTemporaryFile")
    @patch("economic_agents.agent.llm.executors.claude.os.path.exists")
    @patch("economic_agents.agent.llm.executors.claude.os.unlink")
    def test_execute_cleans_up_on_error(self, mock_unlink, mock_exists, mock_tempfile, mock_run):
        """Test that temporary file is cleaned up even on error."""
        # Setup mocks
        mock_file = MagicMock()
        mock_file.name = "/tmp/test_prompt.txt"
        mock_tempfile.return_value.__enter__.return_value = mock_file
        mock_exists.return_value = True

        mock_run.side_effect = subprocess.TimeoutExpired("claude", 900)

        # Execute and expect error
        executor = ClaudeExecutor()
        with pytest.raises(TimeoutError):
            executor.execute("Test prompt")

        # Verify cleanup still happened
        mock_unlink.assert_called_once_with("/tmp/test_prompt.txt")
