"""Unit tests for the multi-agent system."""

import asyncio
import os
from unittest.mock import AsyncMock, Mock, patch

import pytest

from scripts.agents.core.agent_interface import AIAgent
from scripts.agents.core.config_loader import AgentConfig
from scripts.agents.core.exceptions import AgentExecutionError, AgentNotAvailableError, AgentTimeoutError
from scripts.agents.implementations import ClaudeAgent, GeminiAgent
from scripts.agents.multi_agent_subagent_manager import MultiAgentSubagentManager


class TestAgentConfig:
    """Test the agent configuration loader."""

    def test_default_config(self):
        """Test loading default configuration."""
        with patch("os.path.exists", return_value=False):
            config = AgentConfig()
            assert "claude" in config.get_enabled_agents()
            assert config.get_agent_priority("issue_creation") == ["claude"]

    def test_load_config_file(self, tmp_path):
        """Test loading configuration from file."""
        config_file = tmp_path / ".agents.yaml"
        config_file.write_text(
            """
enabled_agents:
  - claude
  - gemini
  - opencode
agent_priorities:
  issue_creation: [opencode, claude]
"""
        )

        config = AgentConfig(str(config_file))
        assert "opencode" in config.get_enabled_agents()
        assert config.get_agent_priority("issue_creation")[0] == "opencode"


class TestClaudeAgent:
    """Test Claude agent implementation."""

    @pytest.mark.asyncio
    async def test_generate_code(self):
        """Test code generation with Claude."""
        agent = ClaudeAgent()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0

            with patch.object(agent, "_execute_with_timeout") as mock_exec:
                mock_exec.return_value = ("def hello():\n    print('Hello')", "")

                result = await agent.generate_code("Write a hello function", {})
                assert "def hello():" in result
                assert "print('Hello')" in result

    @pytest.mark.asyncio
    async def test_review_code(self):
        """Test code review with Claude."""
        agent = ClaudeAgent()

        with patch.object(agent, "_execute_with_timeout") as mock_exec:
            mock_exec.return_value = ("Code looks good. Consider adding type hints.", "")

            result = await agent.review_code("def add(a, b): return a + b", "Review for improvements")
            assert "type hints" in result

    def test_is_available(self):
        """Test agent availability check."""
        agent = ClaudeAgent()

        with patch("subprocess.run") as mock_run:
            # Simulate claude not found
            mock_run.side_effect = [
                Mock(returncode=1),  # which claude fails
            ]
            assert not agent.is_available()

            # Reset and simulate claude found
            agent._available = None
            mock_run.side_effect = [
                Mock(returncode=0),  # which claude succeeds
                Mock(returncode=0),  # claude --version succeeds
            ]
            assert agent.is_available()


class TestGeminiAgent:
    """Test Gemini agent implementation."""

    @pytest.mark.asyncio
    async def test_fallback_to_flash(self):
        """Test fallback from Pro to Flash model."""
        agent = GeminiAgent()

        with patch.object(agent, "_execute_with_timeout") as mock_exec:
            # First call fails with quota error
            mock_exec.side_effect = [
                AgentExecutionError("gemini", 1, "", "quota exceeded"),
                ("Generated with Flash model", ""),
            ]

            result = await agent.generate_code("Test prompt", {})
            assert result == "Generated with Flash model"
            assert agent.current_model == agent.flash_model


class TestMultiAgentSubagentManager:
    """Test the multi-agent subagent manager."""

    def test_initialize_agents(self):
        """Test agent initialization."""
        with patch("scripts.agents.implementations.ClaudeAgent") as MockClaude, patch(
            "scripts.agents.implementations.GeminiAgent"
        ) as MockGemini:
            mock_claude = Mock()
            mock_claude.is_available.return_value = True
            MockClaude.return_value = mock_claude

            mock_gemini = Mock()
            mock_gemini.is_available.return_value = True
            MockGemini.return_value = mock_gemini

            manager = MultiAgentSubagentManager()
            assert "claude" in manager.agents
            assert "gemini" in manager.agents

    def test_get_agent(self):
        """Test getting an agent by name."""
        manager = MultiAgentSubagentManager()

        # Mock agents
        manager.agents = {"claude": Mock(spec=AIAgent), "gemini": Mock(spec=AIAgent)}

        assert manager.get_agent("claude") == manager.agents["claude"]
        assert manager.get_agent("Claude") == manager.agents["claude"]  # Case insensitive

        with pytest.raises(AgentNotAvailableError):
            manager.get_agent("nonexistent")

    @pytest.mark.asyncio
    async def test_execute_with_agent_and_persona(self):
        """Test executing with specific agent and persona."""
        manager = MultiAgentSubagentManager()

        # Mock agent
        mock_agent = AsyncMock(spec=AIAgent)
        mock_agent.generate_code.return_value = "Generated code"
        manager.agents = {"claude": mock_agent}

        # Mock persona
        with patch.object(manager, "get_persona", return_value="You are a tech lead"):
            success, output, error = manager.execute_with_agent_and_persona("claude", "tech-lead", "Implement feature X", {})

            assert success
            assert output == "Generated code"
            assert error == ""
            mock_agent.generate_code.assert_called_once()


class TestErrorHandling:
    """Test error handling in the multi-agent system."""

    @pytest.mark.asyncio
    async def test_timeout_error(self):
        """Test handling of timeout errors."""
        from scripts.agents.core.cli_agent_wrapper import CLIAgentWrapper

        class TestAgent(CLIAgentWrapper):
            def __init__(self):
                super().__init__("test", {"executable": "test", "timeout": 1})

            def _build_command(self, prompt, context):
                return ["sleep", "10"]  # Will timeout

            def _parse_output(self, output, error):
                return output

            def get_trigger_keyword(self):
                return "Test"

            def get_model_config(self):
                return {}

        agent = TestAgent()

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.communicate.side_effect = asyncio.TimeoutError()
            mock_proc.terminate = Mock()
            mock_proc.kill = Mock()
            mock_proc.wait = AsyncMock()
            mock_exec.return_value = mock_proc

            with pytest.raises(AgentTimeoutError):
                await agent.generate_code("Test", {})


class TestTempFileCleanup:
    """Test temporary file cleanup."""

    def test_temp_file_tracking(self):
        """Test that temp files are tracked for cleanup."""
        from scripts.agents.core.cli_agent_wrapper import CLIAgentWrapper, _temp_files

        class TestAgent(CLIAgentWrapper):
            def __init__(self):
                super().__init__("test", {"executable": "test"})

            def get_trigger_keyword(self):
                return "Test"

            def get_model_config(self):
                return {}

        agent = TestAgent()

        # Create a temp file
        filepath = agent._save_to_temp_file("test content")

        # Check it's tracked
        assert filepath in _temp_files
        assert os.path.exists(filepath)

        # Clean up manually for test
        os.unlink(filepath)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
