"""Tests for AI agents."""

import os
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from github_ai_agents.agents import BaseAgent, ClaudeAgent, CrushAgent, GeminiAgent, OpenCodeAgent


class TestBaseAgent:
    """Test base agent functionality."""

    def test_agent_abstract(self):
        """Test that BaseAgent is abstract."""
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            BaseAgent("test")  # pylint: disable=abstract-class-instantiated


class TestOpenCodeAgent:
    """Test OpenCode agent."""

    def test_initialization(self):
        """Test OpenCode agent initialization."""
        agent = OpenCodeAgent()
        assert agent.name == "opencode"
        assert agent.executable == "opencode"  # OpenCode uses its own CLI
        assert agent.timeout == 300
        assert agent._use_docker is False
        assert agent._project_root is None

    def test_initialization_with_api_key(self):
        """Test initialization with API key."""
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}):
            agent = OpenCodeAgent()
            assert agent.env_vars["OPENROUTER_API_KEY"] == "test-key"
            assert agent.env_vars["OPENCODE_MODEL"] == "openrouter/qwen/qwen-2.5-coder-32b-instruct"

    def test_trigger_keyword(self):
        """Test trigger keyword."""
        agent = OpenCodeAgent()
        assert agent.get_trigger_keyword() == "OpenCode"

    def test_capabilities(self):
        """Test agent capabilities."""
        agent = OpenCodeAgent()
        capabilities = agent.get_capabilities()
        assert "code_generation" in capabilities
        assert "openrouter_models" in capabilities

    def test_priority(self):
        """Test agent priority."""
        agent = OpenCodeAgent()
        assert agent.get_priority() == 80

    @patch("subprocess.run")
    @patch("shutil.which")
    def test_is_available_docker_preferred(self, mock_which, mock_run):
        """Test that Docker is preferred over local."""
        agent = OpenCodeAgent()

        # Mock project root finding
        with patch.object(agent, "_find_project_root", return_value=Path("/fake/root")):
            # Mock docker-compose.yml exists
            with patch("pathlib.Path.exists", return_value=True):
                # Mock successful Docker check
                mock_run.return_value.returncode = 0
                mock_run.return_value.stdout = "openrouter-agents\n"

                # Even if local is available, should use Docker
                mock_which.return_value = "/usr/local/bin/opencode"

                assert agent.is_available() is True
                assert agent._use_docker is True
                assert agent._available is True

                # Docker check should be called first
                mock_run.assert_called_once_with(
                    [
                        "docker-compose",
                        "-f",
                        "/fake/root/docker-compose.yml",
                        "config",
                        "--services",
                    ],
                    capture_output=True,
                    timeout=5,
                    text=True,
                )

    @patch("subprocess.run")
    @patch("shutil.which")
    def test_is_available_falls_back_to_local(self, mock_which, mock_run):
        """Test fallback to local when Docker not available."""
        agent = OpenCodeAgent()

        # Mock project root not found (no Docker)
        with patch.object(agent, "_find_project_root", return_value=None):
            # Mock local executable available
            mock_which.return_value = "/usr/local/bin/opencode"
            mock_run.return_value.returncode = 0

            assert agent.is_available() is True
            assert agent._use_docker is False
            assert agent._available is True

    @patch("subprocess.run")
    @patch("shutil.which")
    def test_is_available_not_found(self, mock_which, mock_run):
        """Test when neither Docker nor local is available."""
        agent = OpenCodeAgent()

        # Mock project root not found
        with patch.object(agent, "_find_project_root", return_value=None):
            # Mock local executable not found
            mock_which.return_value = None

            assert agent.is_available() is False
            assert agent._available is False

    def test_build_command_docker(self):
        """Test command building for Docker."""
        agent = OpenCodeAgent()
        agent._use_docker = True

        with patch.object(agent, "_find_project_root", return_value=Path("/fake/root")):
            with patch("pathlib.Path.exists", return_value=True):
                with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}):
                    agent.env_vars["OPENROUTER_API_KEY"] = "test-key"

                    cmd = agent._build_command()  # No arguments - uses stdin

                    assert cmd == [
                        "docker-compose",
                        "-f",
                        "/fake/root/docker-compose.yml",
                        "run",
                        "--rm",
                        "-T",
                        "-e",
                        "OPENROUTER_API_KEY=test-key",
                        "-e",
                        "OPENCODE_MODEL=qwen/qwen-2.5-coder-32b-instruct",
                        "openrouter-agents",
                        "opencode",
                        "run",
                        "-m",
                        "openrouter/qwen/qwen-2.5-coder-32b-instruct",
                    ]

    def test_build_command_local(self):
        """Test command building for local execution."""
        agent = OpenCodeAgent()
        agent._use_docker = False

        cmd = agent._build_command()  # No arguments - uses stdin

        assert cmd == [
            "opencode",
            "run",
            "-m",
            "openrouter/qwen/qwen-2.5-coder-32b-instruct",
        ]

    @pytest.mark.asyncio
    async def test_generate_code(self):
        """Test code generation."""
        agent = OpenCodeAgent()
        agent._use_docker = False

        # Mock command execution
        with patch.object(agent, "_execute_command", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = ("def hello():\n    print('Hello')", "")

            result = await agent.generate_code("Generate a validation function", {"code": "# existing code"})

            assert result == "def hello():\n    print('Hello')"


class TestCrushAgent:
    """Test Crush agent."""

    def test_initialization(self):
        """Test Crush agent initialization."""
        agent = CrushAgent()
        assert agent.name == "crush"
        assert agent.executable == "crush"  # Note: crush is the actual executable
        assert agent.timeout == 300

    def test_trigger_keyword(self):
        """Test trigger keyword."""
        agent = CrushAgent()
        assert agent.get_trigger_keyword() == "Crush"

    def test_priority(self):
        """Test agent priority."""
        agent = CrushAgent()
        assert agent.get_priority() == 60

    def test_docker_preferred(self):
        """Test that Docker is preferred for Crush."""
        agent = CrushAgent()

        with patch("subprocess.run") as mock_run:
            with patch.object(agent, "_find_project_root", return_value=Path("/fake/root")):
                with patch("pathlib.Path.exists", return_value=True):
                    mock_run.return_value.returncode = 0
                    mock_run.return_value.stdout = "openrouter-agents\n"

                    assert agent.is_available() is True
                    assert agent._use_docker is True


class TestClaudeAgent:
    """Test Claude agent."""

    def test_initialization(self):
        """Test Claude agent initialization."""
        agent = ClaudeAgent()
        assert agent.name == "claude"
        assert agent.executable == "claude"

    def test_trigger_keyword(self):
        """Test trigger keyword."""
        agent = ClaudeAgent()
        assert agent.get_trigger_keyword() == "Claude"

    def test_priority(self):
        """Test agent priority."""
        agent = ClaudeAgent()
        assert agent.get_priority() == 100  # Highest priority

    @patch("subprocess.run")
    @patch("shutil.which")
    def test_is_available(self, mock_which, mock_run):
        """Test Claude availability check."""
        agent = ClaudeAgent()

        # Mock claude executable exists
        mock_which.return_value = "/usr/local/bin/claude"
        mock_run.return_value.returncode = 0

        assert agent.is_available() is True


class TestGeminiAgent:
    """Test Gemini agent."""

    def test_initialization(self):
        """Test Gemini agent initialization."""
        agent = GeminiAgent()
        assert agent.name == "gemini"
        assert agent.executable == "gemini"

    def test_trigger_keyword(self):
        """Test trigger keyword."""
        agent = GeminiAgent()
        assert agent.get_trigger_keyword() == "Gemini"

    def test_priority(self):
        """Test agent priority."""
        agent = GeminiAgent()
        assert agent.get_priority() == 90

    @patch("subprocess.run")
    @patch("shutil.which")
    def test_is_available(self, mock_which, mock_run):
        """Test Gemini availability check using --help."""
        agent = GeminiAgent()

        # Mock gemini executable exists
        mock_which.return_value = "/usr/local/bin/gemini"
        mock_run.return_value.returncode = 0

        assert agent.is_available() is True

        # Should use --help instead of making API calls
        mock_run.assert_called_with(["gemini", "--help"], capture_output=True, timeout=5, text=True)
