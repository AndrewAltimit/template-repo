"""Task executor using Claude Code for autonomous task completion."""

import logging
from pathlib import Path
from typing import Dict

from economic_agents.agent.llm.executors.claude import ClaudeExecutor

logger = logging.getLogger(__name__)


class TaskExecutor:
    """Executes coding tasks using Claude Code."""

    def __init__(self, config: dict | None = None):
        """Initialize task executor.

        Args:
            config: Configuration dict for Claude executor
        """
        self.executor = ClaudeExecutor(config)
        self.workspace_root = Path("/tmp/task_workspace")
        self.workspace_root.mkdir(exist_ok=True)

    def execute_task(self, task: Dict, timeout: int = 300) -> Dict:
        """Execute a coding task using Claude Code.

        Args:
            task: Task dictionary with requirements
            timeout: Execution timeout in seconds

        Returns:
            dict with:
                - success: bool
                - code: str (solution code)
                - workspace_path: str
                - error: str (if failed)
        """
        task_id = task.get("id", "unknown")

        # Create workspace for this task
        workspace = self.workspace_root / task_id
        workspace.mkdir(exist_ok=True)

        logger.info("Executing task %s in %s", task_id, workspace)

        # Build prompt for Claude
        prompt = self._build_task_prompt(task, workspace)

        try:
            # Execute with Claude Code
            response = self.executor.execute(prompt, timeout=timeout)

            # Extract code from response
            code = self._extract_code(response)

            # Save code to workspace
            solution_file = workspace / "solution.py"
            solution_file.write_text(code)

            logger.info("Task %s completed, code saved to %s", task_id, solution_file)

            return {"success": True, "code": code, "workspace_path": str(workspace), "response": response}

        except Exception as e:
            logger.error("Task %s failed: %s", task_id, e)
            return {"success": False, "code": "", "workspace_path": str(workspace), "error": str(e)}

    def _build_task_prompt(self, task: Dict, workspace: Path) -> str:
        """Build Claude Code prompt for task execution.

        Args:
            task: Task dictionary
            workspace: Workspace path

        Returns:
            Formatted prompt
        """
        title = task.get("title", "Coding Task")
        description = task.get("description", "")
        requirements = task.get("requirements", {})
        spec = requirements.get("spec", "")
        function_name = requirements.get("function_name", "solution")
        tests = requirements.get("tests", [])

        prompt = f"""You are completing a coding task from a marketplace.

TASK: {title}
{description}

REQUIREMENTS:
{spec}

TESTS:
The solution must pass these test cases:
"""

        for i, test in enumerate(tests, 1):
            test_input = test.get("input")
            expected = test.get("expected")
            prompt += f"\nTest {i}:\n  Input: {test_input}\n  Expected: {expected}\n"

        prompt += f"""

INSTRUCTIONS:
1. Write a Python file at {workspace}/solution.py
2. The file should contain ONLY the function {function_name}
3. Do NOT include test code or if __name__ == "__main__" blocks
4. The function must be importable and ready for automated testing
5. Include docstring with clear parameter and return type documentation

Write the solution now. Output ONLY the Python code, nothing else.
"""

        return prompt

    def _extract_code(self, response: str) -> str:
        """Extract Python code from Claude's response.

        Args:
            response: Claude's response

        Returns:
            Extracted code
        """
        # Try to find Python code block
        if "```python" in response:
            start = response.find("```python") + 9
            end = response.find("```", start)
            code = response[start:end].strip()
        elif "```" in response:
            start = response.find("```") + 3
            end = response.find("```", start)
            code = response[start:end].strip()
        else:
            # Assume entire response is code
            code = response.strip()

        return code

    def cleanup_workspace(self, task_id: str):
        """Clean up task workspace.

        Args:
            task_id: Task ID
        """
        workspace = self.workspace_root / task_id
        if workspace.exists():
            import shutil

            shutil.rmtree(workspace)
            logger.info("Cleaned up workspace for task %s", task_id)
