"""AI agent implementations."""

from .base import AgentError, AgentExecutionError, AgentNotAvailableError, AgentTimeoutError, BaseAgent
from .claude import ClaudeAgent
from .containerized import ContainerizedCLIAgent
from .crush import CrushAgent
from .gemini import GeminiAgent
from .opencode import OpenCodeAgent


def get_best_available_agent():
    """Get the best available AI agent based on priority and availability.

    Returns:
        The best available agent instance, or None if no agents are available.
    """
    # Order agents by priority (highest to lowest)
    agent_classes = [
        ClaudeAgent,
        OpenCodeAgent,
        GeminiAgent,
        CrushAgent,
    ]

    for agent_class in agent_classes:
        try:
            agent = agent_class()
            if agent.is_available():
                return agent
        except Exception:
            # Skip agents that fail to initialize
            continue

    return None


__all__ = [
    "BaseAgent",
    "ContainerizedCLIAgent",
    "AgentError",
    "AgentNotAvailableError",
    "AgentExecutionError",
    "AgentTimeoutError",
    "ClaudeAgent",
    "OpenCodeAgent",
    "GeminiAgent",
    "CrushAgent",
    "get_best_available_agent",
]
