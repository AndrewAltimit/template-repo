#!/usr/bin/env python3
"""
Subagent Manager for Claude Code Integration

This module manages Claude Code subagents with different personas for specialized tasks.
It loads persona definitions from markdown files and integrates them with Claude Code CLI.
"""

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from logging_security import get_secure_logger, mask_secrets

logger = get_secure_logger(__name__)


class SubagentManager:
    """Manages Claude Code subagents with different personas."""

    def __init__(self):
        self.subagents_dir = Path(__file__).parent / "subagents"
        self.personas: Dict[str, str] = {}
        self._load_personas()

    def _load_personas(self) -> None:
        """Load all persona definitions from markdown files."""
        if not self.subagents_dir.exists():
            logger.warning(f"Subagents directory not found: {self.subagents_dir}")
            return

        for persona_file in self.subagents_dir.glob("*.md"):
            persona_name = persona_file.stem
            try:
                with open(persona_file, "r") as f:
                    self.personas[persona_name] = f.read()
                logger.info(f"Loaded persona: {persona_name}")
            except Exception as e:
                logger.error(f"Failed to load persona {persona_name}: {e}")

    def get_persona(self, persona_name: str) -> Optional[str]:
        """Get a specific persona definition."""
        return self.personas.get(persona_name)

    def list_personas(self) -> List[str]:
        """List all available personas."""
        return list(self.personas.keys())

    def execute_with_persona(
        self,
        persona_name: str,
        task: str,
        context: Optional[Dict] = None,
        working_directory: Optional[str] = None,
        timeout: int = 300,
    ) -> Tuple[bool, str, str]:
        """
        Execute a task using Claude Code with a specific persona.

        Args:
            persona_name: Name of the persona to use (e.g., 'tech-lead', 'qa-reviewer')
            task: The task description/prompt for Claude Code
            context: Additional context (issue content, PR details, etc.)
            working_directory: Directory to execute in
            timeout: Command timeout in seconds

        Returns:
            Tuple of (success, stdout, stderr)
        """
        persona_content = self.get_persona(persona_name)
        if not persona_content:
            logger.error(f"Persona not found: {persona_name}")
            return False, "", f"Persona '{persona_name}' not found"

        # Build the complete prompt with persona and task
        full_prompt = self._build_prompt(persona_content, task, context)

        # Create a temporary markdown file for the subagent
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as tmp_file:
            tmp_file.write(full_prompt)
            tmp_file_path = tmp_file.name

        try:
            # Execute Claude Code with the subagent
            return self._run_claude_code(tmp_file_path, working_directory, timeout)
        finally:
            # Clean up temporary file
            try:
                os.unlink(tmp_file_path)
            except Exception as e:
                logger.warning(f"Failed to delete temp file: {e}")

    def _build_prompt(self, persona_content: str, task: str, context: Optional[Dict]) -> str:
        """Build the complete prompt with persona, task, and context."""
        prompt_parts = [persona_content, "\n\n## Current Task\n\n", task]

        if context:
            prompt_parts.append("\n\n## Additional Context\n\n")

            # Add issue/PR specific context
            if "issue_number" in context:
                prompt_parts.append(f"**Issue Number**: #{context['issue_number']}\n")
            if "issue_title" in context:
                prompt_parts.append(f"**Issue Title**: {context['issue_title']}\n")
            if "issue_body" in context:
                prompt_parts.append(f"\n**Issue Description**:\n{context['issue_body']}\n")

            if "pr_number" in context:
                prompt_parts.append(f"**PR Number**: #{context['pr_number']}\n")
            if "pr_title" in context:
                prompt_parts.append(f"**PR Title**: {context['pr_title']}\n")
            if "review_comments" in context:
                prompt_parts.append(f"\n**Review Comments**:\n{context['review_comments']}\n")

            if "branch_name" in context:
                prompt_parts.append(f"\n**Branch**: {context['branch_name']}\n")
            if "commit_sha" in context:
                prompt_parts.append(f"**Commit SHA**: {context['commit_sha']}\n")

        # Add security reminder
        prompt_parts.append("\n\n## Security Reminder\n\n")
        prompt_parts.append("- Never commit secrets or credentials\n")
        prompt_parts.append("- Follow the project's security guidelines\n")
        prompt_parts.append("- Validate all inputs and outputs\n")
        prompt_parts.append("- Ensure changes don't introduce vulnerabilities\n")

        return "".join(prompt_parts)

    def _run_claude_code(
        self,
        subagent_file: str,
        working_directory: Optional[str] = None,
        timeout: int = 300,
    ) -> Tuple[bool, str, str]:
        """
        Run Claude Code with a subagent file.

        Returns:
            Tuple of (success, stdout, stderr)
        """
        # Build the Claude Code command
        # Using the format: claude code /path/to/subagent.md
        cmd = ["claude", "code", subagent_file]

        # Set up environment
        env = os.environ.copy()

        # Add any necessary environment variables
        if "ANTHROPIC_API_KEY" not in env:
            logger.warning("ANTHROPIC_API_KEY not set, Claude Code may not work")

        try:
            logger.info(f"Executing Claude Code with subagent: {subagent_file}")

            result = subprocess.run(
                cmd,
                cwd=working_directory,
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            # Mask any secrets in the output
            stdout = mask_secrets(result.stdout)
            stderr = mask_secrets(result.stderr)

            if result.returncode == 0:
                logger.info("Claude Code execution completed successfully")
                return True, stdout, stderr
            else:
                logger.error(f"Claude Code execution failed with code {result.returncode}")
                return False, stdout, stderr

        except subprocess.TimeoutExpired:
            logger.error(f"Claude Code execution timed out after {timeout} seconds")
            return False, "", "Command timed out"
        except Exception as e:
            logger.error(f"Failed to execute Claude Code: {e}")
            return False, "", str(e)

    def create_implementation_task(self, issue_data: Dict) -> str:
        """Create a task description for implementing an issue."""
        task_parts = []

        task_parts.append(f"Implement the feature described in issue #{issue_data.get('number', 'unknown')}.")
        task_parts.append("\n\nRequirements:")

        # Extract requirements from issue body
        if issue_body := issue_data.get("body", ""):
            task_parts.append(f"\n{issue_body}")

        task_parts.append("\n\nDeliverables:")
        task_parts.append("1. Implement the requested feature following project conventions")
        task_parts.append("2. Add comprehensive tests for the new functionality")
        task_parts.append("3. Update documentation as needed")
        task_parts.append("4. Ensure all CI/CD checks pass")
        task_parts.append("5. Create a detailed PR description explaining the implementation")

        return "\n".join(task_parts)

    def create_review_task(self, pr_data: Dict, review_comments: List[Dict]) -> str:
        """Create a task description for addressing PR review comments."""
        task_parts = []

        task_parts.append(f"Address the review feedback for PR #{pr_data.get('number', 'unknown')}.")
        task_parts.append("\n\nReview Comments to Address:")

        for i, comment in enumerate(review_comments, 1):
            task_parts.append(f"\n{i}. {comment.get('body', '')}")
            if comment.get("path"):
                task_parts.append(f"   File: {comment['path']}")
            if comment.get("line"):
                task_parts.append(f"   Line: {comment['line']}")

        task_parts.append("\n\nActions Required:")
        task_parts.append("1. Address each review comment")
        task_parts.append("2. Fix any identified issues")
        task_parts.append("3. Run tests to ensure no regressions")
        task_parts.append("4. Update the PR with explanations of changes made")

        return "\n".join(task_parts)


# Example usage functions
def implement_issue_with_tech_lead(issue_data: Dict, branch_name: str) -> Tuple[bool, str]:
    """Use the tech-lead persona to implement an issue."""
    manager = SubagentManager()

    task = manager.create_implementation_task(issue_data)
    context = {
        "issue_number": issue_data.get("number"),
        "issue_title": issue_data.get("title"),
        "issue_body": issue_data.get("body"),
        "branch_name": branch_name,
    }

    success, stdout, stderr = manager.execute_with_persona(
        "tech-lead", task, context, timeout=600  # 10 minutes for implementation
    )

    if success:
        return True, stdout
    else:
        return False, f"Error: {stderr}"


def review_pr_with_qa(pr_data: Dict, review_comments: List[Dict]) -> Tuple[bool, str]:
    """Use the qa-reviewer persona to address PR reviews."""
    manager = SubagentManager()

    task = manager.create_review_task(pr_data, review_comments)
    context = {
        "pr_number": pr_data.get("number"),
        "pr_title": pr_data.get("title"),
        "branch_name": pr_data.get("head", {}).get("ref"),
        "commit_sha": pr_data.get("head", {}).get("sha"),
        "review_comments": "\n".join([c.get("body", "") for c in review_comments]),
    }

    success, stdout, stderr = manager.execute_with_persona(
        "qa-reviewer", task, context, timeout=300  # 5 minutes for review fixes
    )

    if success:
        return True, stdout
    else:
        return False, f"Error: {stderr}"


if __name__ == "__main__":
    # Test the subagent manager
    manager = SubagentManager()

    print("Available personas:")
    for persona in manager.list_personas():
        print(f"  - {persona}")

    # Example test
    if "tech-lead" in manager.list_personas():
        print("\nTech Lead persona content preview:")
        content = manager.get_persona("tech-lead")
        if content:
            print(content[:200] + "...")
