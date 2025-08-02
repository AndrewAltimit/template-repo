#!/usr/bin/env python3
"""
Multi-Agent Subagent Manager

This module extends the SubagentManager to support multiple AI agents (Claude, Gemini, OpenCode, etc.)
It dynamically selects the appropriate agent based on the trigger keyword.
"""

import asyncio
import os
from typing import Dict, List, Optional, Tuple

from core import AgentConfig
from core.exceptions import AgentNotAvailableError
from implementations import ClaudeAgent, CodexAgent, CrushAgent, GeminiAgent, OpenCodeAgent
from logging_security import get_secure_logger
from subagent_manager import SubagentManager

logger = get_secure_logger(__name__)


class MultiAgentSubagentManager(SubagentManager):
    """Extends SubagentManager to support multiple AI agents."""

    def __init__(self):
        """Initialize multi-agent subagent manager."""
        super().__init__()
        self.config = AgentConfig()
        self.agents = self._initialize_agents()

    def _initialize_agents(self) -> Dict[str, any]:
        """Initialize all available agents."""
        agents = {}

        # Initialize Claude
        try:
            claude = ClaudeAgent(agent_config=self.config)
            if claude.is_available():
                agents["claude"] = claude
                logger.info("Claude agent initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize Claude agent: {e}")

        # Initialize Gemini
        try:
            gemini = GeminiAgent(agent_config=self.config)
            if gemini.is_available():
                agents["gemini"] = gemini
                logger.info("Gemini agent initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize Gemini agent: {e}")

        # Initialize OpenCode
        try:
            opencode = OpenCodeAgent(agent_config=self.config)
            if opencode.is_available():
                agents["opencode"] = opencode
                logger.info("OpenCode agent initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize OpenCode agent: {e}")

        # Initialize Codex
        try:
            codex = CodexAgent(agent_config=self.config)
            if codex.is_available():
                agents["codex"] = codex
                logger.info("Codex agent initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize Codex agent: {e}")

        # Initialize Crush
        try:
            crush = CrushAgent(agent_config=self.config)
            if crush.is_available():
                agents["crush"] = crush
                logger.info("Crush agent initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize Crush agent: {e}")

        return agents

    def get_agent(self, agent_name: str):
        """Get an agent by name."""
        agent_key = agent_name.lower()
        if agent_key not in self.agents:
            available = list(self.agents.keys())
            raise AgentNotAvailableError(agent_name, f"Agent not available. Available agents: {available}")
        return self.agents[agent_key]

    def execute_with_agent_and_persona(
        self,
        agent_name: str,
        persona_name: str,
        task: str,
        context: Optional[Dict] = None,
        working_directory: Optional[str] = None,
        timeout: int = 300,
    ) -> Tuple[bool, str, str]:
        """
        Execute a task using a specific agent with a persona.

        Args:
            agent_name: Name of the agent to use (e.g., 'Claude', 'Gemini')
            persona_name: Name of the persona to use (e.g., 'tech-lead', 'qa-reviewer')
            task: The task description/prompt
            context: Additional context
            working_directory: Directory to execute in
            timeout: Command timeout in seconds

        Returns:
            Tuple of (success, stdout, stderr)
        """
        try:
            agent = self.get_agent(agent_name)
        except AgentNotAvailableError as e:
            logger.error(str(e))
            return False, "", str(e)

        persona_content = self.get_persona(persona_name)
        if not persona_content:
            logger.error(f"Persona not found: {persona_name}")
            return False, "", f"Persona '{persona_name}' not found"

        # Build the complete prompt with persona and task
        full_prompt = self._build_prompt(persona_content, task, context)

        # Change to working directory if specified
        original_cwd = os.getcwd()
        if working_directory:
            try:
                os.chdir(working_directory)
            except Exception as e:
                return False, "", f"Failed to change directory: {e}"

        try:
            # Use async execution
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're already in an async context
                result = asyncio.create_task(agent.generate_code(full_prompt, context or {}))
                output = asyncio.run_coroutine_threadsafe(result, loop).result(timeout)
            else:
                # Create new event loop
                output = asyncio.run(asyncio.wait_for(agent.generate_code(full_prompt, context or {}), timeout=timeout))

            return True, output, ""

        except asyncio.TimeoutError:
            error_msg = f"{agent_name} agent timed out after {timeout}s"
            logger.error(error_msg)
            return False, "", error_msg
        except Exception as e:
            logger.error(f"Error executing {agent_name} agent: {e}")
            return False, "", str(e)
        finally:
            # Restore original directory
            os.chdir(original_cwd)


def implement_issue_with_agent(issue_data: Dict, branch_name: str, agent_name: str = "Claude") -> Tuple[bool, str]:
    """
    Use a specific agent with tech-lead persona to implement an issue.

    Args:
        issue_data: GitHub issue data
        branch_name: Git branch name
        agent_name: Which agent to use (defaults to Claude)

    Returns:
        Tuple of (success, output/error message)
    """
    manager = MultiAgentSubagentManager()
    task = manager.create_implementation_task(issue_data)

    context = {
        "issue_number": issue_data.get("number"),
        "issue_title": issue_data.get("title"),
        "issue_body": issue_data.get("body"),
        "branch_name": branch_name,
    }

    success, stdout, stderr = manager.execute_with_agent_and_persona(
        agent_name, "tech-lead", task, context, timeout=600  # 10 minutes for implementation
    )

    if success:
        return True, stdout
    else:
        return False, f"Error: {stderr}"


def review_pr_with_agent(
    pr_data: Dict, review_comments: List[Dict], agent_name: str = "Gemini", timeout: int = 600
) -> Tuple[bool, str]:
    """
    Use a specific agent with qa-reviewer persona to address PR reviews.

    Args:
        pr_data: GitHub PR data
        review_comments: List of review comments
        agent_name: Which agent to use (defaults to Gemini for reviews)
        timeout: Timeout in seconds

    Returns:
        Tuple of (success, output/error message)
    """
    manager = MultiAgentSubagentManager()
    task = manager.create_review_task(pr_data, review_comments)

    context = {
        "pr_number": pr_data.get("number"),
        "pr_title": pr_data.get("title"),
        "branch_name": pr_data.get("head", {}).get("ref"),
        "commit_sha": pr_data.get("head", {}).get("sha"),
        "review_comments": "\n".join([c.get("body", "") for c in review_comments]),
    }

    success, stdout, stderr = manager.execute_with_agent_and_persona(agent_name, "qa-reviewer", task, context, timeout=timeout)

    if success:
        return True, stdout
    else:
        return False, f"Error: {stderr}"


if __name__ == "__main__":
    # Test the multi-agent subagent manager
    manager = MultiAgentSubagentManager()
    print("Available personas:")
    for persona in manager.list_personas():
        print(f"  - {persona}")

    print("\nAvailable agents:")
    for agent_name in manager.agents:
        print(f"  - {agent_name}")
