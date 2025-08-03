"""Tests for AI agents."""

import pytest

from github_ai_agents.agents import BaseAgent, OpenCodeAgent


class TestBaseAgent:
    """Test base agent functionality."""

    def test_agent_abstract(self):
        """Test that BaseAgent is abstract."""
        with pytest.raises(TypeError):
            BaseAgent("test")  # Should fail, abstract class


class TestOpenCodeAgent:
    """Test OpenCode agent."""

    def test_initialization(self):
        """Test OpenCode agent initialization."""
        agent = OpenCodeAgent()
        assert agent.name == "opencode"
        assert agent.executable == "opencode"
        assert agent.timeout == 300

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
