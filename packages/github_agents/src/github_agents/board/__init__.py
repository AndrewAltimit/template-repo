"""
GitHub Projects v2 board integration for AI agent coordination.

This module provides functionality for AI agents to use GitHub Projects v2 as an
external memory system for tracking work, dependencies, and state across sessions.
"""

from github_agents.board.errors import (
    BoardError,
    BoardNotFoundError,
    GraphQLError,
    RateLimitError,
)
from github_agents.board.manager import BoardManager
from github_agents.board.models import AgentClaim, BoardConfig, Issue, IssueStatus

__all__ = [
    "BoardManager",
    "BoardConfig",
    "Issue",
    "IssueStatus",
    "AgentClaim",
    "BoardError",
    "BoardNotFoundError",
    "GraphQLError",
    "RateLimitError",
]

__version__ = "0.2.0"
