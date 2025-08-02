"""Abstract interface for all AI agents."""

from abc import ABC, abstractmethod
from typing import Dict, List


class AIAgent(ABC):
    """Base interface that all AI agents must implement."""

    @abstractmethod
    async def generate_code(self, prompt: str, context: Dict[str, str]) -> str:
        """Generate code based on prompt and context.

        Args:
            prompt: The task or question for the agent
            context: Additional context (code, files, etc.)

        Returns:
            Generated code or response
        """
        pass

    @abstractmethod
    async def review_code(self, code: str, instructions: str) -> str:
        """Review code and provide feedback.

        Args:
            code: The code to review
            instructions: Specific review instructions

        Returns:
            Review feedback and suggestions
        """
        pass

    @abstractmethod
    def get_trigger_keyword(self) -> str:
        """Get the keyword that triggers this agent (e.g., 'Claude', 'Gemini').

        Returns:
            The trigger keyword without brackets
        """
        pass

    @abstractmethod
    def get_model_config(self) -> Dict[str, any]:
        """Get the model configuration for this agent.

        Returns:
            Dictionary with model settings (name, temperature, etc.)
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the agent is properly configured and available.

        Returns:
            True if agent can be used, False otherwise
        """
        pass

    def get_capabilities(self) -> List[str]:
        """Get list of capabilities this agent supports.

        Returns:
            List of capability strings (e.g., ['code_generation', 'code_review'])
        """
        return ["code_generation", "code_review"]

    def get_priority(self) -> int:
        """Get priority for agent selection (higher = preferred).

        Returns:
            Priority value (0-100)
        """
        return 50
