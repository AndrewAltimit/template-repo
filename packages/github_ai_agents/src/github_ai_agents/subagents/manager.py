"""Subagent manager for executing AI agents with specialized personas."""

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Type

logger = logging.getLogger(__name__)


class SubagentManager:
    """Manages execution of AI agents with specialized personas."""

    def __init__(self, personas_dir: Optional[Path] = None):
        """Initialize the subagent manager.

        Args:
            personas_dir: Directory containing persona markdown files.
                         Defaults to package docs/subagents directory.
        """
        if personas_dir is None:
            # Default to package docs/subagents directory
            package_root = Path(__file__).parent.parent.parent.parent
            personas_dir = package_root / "docs" / "subagents"

        self.personas_dir = Path(personas_dir)
        self.personas = self._load_personas()

    def _load_personas(self) -> Dict[str, str]:
        """Load all persona definitions from markdown files.

        Returns:
            Dictionary mapping persona names to their content.
        """
        personas: Dict[str, str] = {}

        if not self.personas_dir.exists():
            logger.warning(f"Personas directory not found: {self.personas_dir}")
            return personas

        for persona_file in self.personas_dir.glob("*.md"):
            persona_name = persona_file.stem
            try:
                with open(persona_file, "r") as f:
                    personas[persona_name] = f.read()
                logger.info(f"Loaded persona: {persona_name}")
            except Exception as e:
                logger.error(f"Failed to load persona {persona_name}: {e}")

        return personas

    def execute_with_persona(
        self,
        persona: str,
        task: str,
        context: Optional[Dict[str, Any]] = None,
        agent_name: Optional[str] = None,
    ) -> Tuple[bool, str, str]:
        """Execute a task using a specific persona.

        Args:
            persona: Name of the persona to use (e.g., "tech-lead", "qa-reviewer")
            task: The task description to execute
            context: Additional context for the task
            agent_name: Specific agent to use (defaults to best available)

        Returns:
            Tuple of (success, stdout, stderr)
        """
        # Check if persona exists
        if persona not in self.personas:
            available = ", ".join(self.personas.keys())
            error_msg = f"Persona '{persona}' not found. Available: {available}"
            logger.error(error_msg)
            return False, "", error_msg

        # Build the full prompt
        prompt = self._build_prompt(persona, task, context)

        # Import here to avoid circular imports
        from ..agents import get_best_available_agent

        # Get the appropriate agent
        if agent_name:
            # Use specific agent if requested
            from ..agents import ClaudeAgent, CrushAgent, GeminiAgent, OpenCodeAgent
            from ..agents.base import BaseAgent

            agent_map: Dict[str, Type[BaseAgent]] = {
                "claude": ClaudeAgent,
                "opencode": OpenCodeAgent,
                "gemini": GeminiAgent,
                "crush": CrushAgent,
            }
            agent_class = agent_map.get(agent_name.lower())
            if not agent_class:
                return False, "", f"Unknown agent: {agent_name}"
            agent = agent_class(config=None)  # type: ignore[call-arg]
        else:
            # Use best available agent
            agent = get_best_available_agent()
            if not agent:
                return False, "", "No AI agents available"

        try:
            # Execute the task
            logger.info(f"Executing with {agent.__class__.__name__} using {persona} persona")

            # Run the agent asynchronously
            import asyncio

            loop = asyncio.get_event_loop()
            result = loop.run_until_complete(agent.generate_code(prompt, context or {}))

            return True, result, ""

        except Exception as e:
            error_msg = f"Failed to execute with persona: {e}"
            logger.error(error_msg)
            return False, "", error_msg

    def _build_prompt(self, persona: str, task: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Build the full prompt with persona and task.

        Args:
            persona: The persona name
            task: The task description
            context: Additional context

        Returns:
            The complete prompt string
        """
        persona_content = self.personas[persona]

        prompt_parts = [
            "# AI Agent Persona",
            "",
            persona_content,
            "",
            "# Task",
            "",
            task,
        ]

        # Add context if provided
        if context:
            prompt_parts.extend(["", "# Additional Context", ""])
            for key, value in context.items():
                prompt_parts.append(f"- **{key}**: {value}")

        return "\n".join(prompt_parts)

    def list_personas(self) -> list:
        """List all available personas.

        Returns:
            List of persona names
        """
        return list(self.personas.keys())


# Convenience functions for common personas
def implement_issue_with_tech_lead(issue_data: Dict[str, Any], branch_name: str) -> Tuple[bool, str]:
    """Implement an issue using the tech-lead persona.

    Args:
        issue_data: Issue information
        branch_name: Branch to work on

    Returns:
        Tuple of (success, output)
    """
    manager = SubagentManager()

    task = f"Implement the following issue:\n\n{issue_data.get('body', '')}"

    context = {
        "issue_number": issue_data.get("number"),
        "issue_title": issue_data.get("title"),
        "branch_name": branch_name,
        "repository": os.environ.get("GITHUB_REPOSITORY", ""),
    }

    success, stdout, stderr = manager.execute_with_persona("tech-lead", task, context)

    output = stdout if success else stderr
    return success, output


def review_pr_with_qa(pr_data: Dict[str, Any], review_comments: list) -> Tuple[bool, str]:
    """Review a PR using the qa-reviewer persona.

    Args:
        pr_data: PR information
        review_comments: List of review comments to address

    Returns:
        Tuple of (success, output)
    """
    manager = SubagentManager()

    # Format review comments
    comments_text = "\n".join([f"- {comment.get('body', '')}" for comment in review_comments])

    task = f"Address the following PR review feedback:\n\n{comments_text}"

    context = {
        "pr_number": pr_data.get("number"),
        "pr_title": pr_data.get("title"),
        "repository": os.environ.get("GITHUB_REPOSITORY", ""),
    }

    success, stdout, stderr = manager.execute_with_persona("qa-reviewer", task, context)

    output = stdout if success else stderr
    return success, output
