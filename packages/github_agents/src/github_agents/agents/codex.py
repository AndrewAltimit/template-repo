"""Codex AI agent implementation.

Wraps OpenAI's Codex CLI for code generation tasks.
Requires ChatGPT Plus subscription and `npm install -g @openai/codex`.
"""

import asyncio
import json
import logging
import os
from typing import Any, Dict, List, Optional

from .base import AgentExecutionError, AgentTimeoutError, CLIAgent

logger = logging.getLogger(__name__)


class CodexAgent(CLIAgent):
    """Codex AI agent for code generation.

    Uses OpenAI's Codex CLI which requires:
    1. ChatGPT Plus subscription
    2. npm install -g @openai/codex
    3. codex auth (to authenticate)
    """

    def __init__(self, config: Optional[Any] = None) -> None:
        """Initialize Codex agent."""
        super().__init__("codex", "codex", timeout=300, config=config)

        # Check for bypass sandbox mode (only for already-sandboxed environments)
        self.bypass_sandbox = os.environ.get("CODEX_BYPASS_SANDBOX") == "true"

    def get_trigger_keyword(self) -> str:
        """Get trigger keyword for Codex."""
        return "Codex"

    def is_available(self) -> bool:
        """Check if Codex CLI is available and authenticated."""
        if self._available is not None:
            return self._available

        try:
            import subprocess

            # Check if codex command exists
            result = subprocess.run(
                ["which", "codex"],
                capture_output=True,
                timeout=5,
                check=False,
            )

            if result.returncode != 0:
                self._available = False
                return False

            # Check if auth exists
            from pathlib import Path

            auth_path = Path.home() / ".codex" / "auth.json"
            self._available = auth_path.exists()

            if not self._available:
                logger.warning("Codex auth not found at %s - run 'codex auth' first", auth_path)

            return self._available

        except (subprocess.TimeoutExpired, FileNotFoundError):
            self._available = False
            return False

    async def generate_code(self, prompt: str, context: Dict[str, Any]) -> str:
        """Generate code using Codex.

        Args:
            prompt: The task or question
            context: Additional context

        Returns:
            Generated code or response
        """
        # Build full prompt with context
        full_prompt = self._build_prompt(prompt, context)

        # Build command
        cmd = self._build_exec_command(full_prompt)

        logger.info("Executing Codex with prompt length: %d chars", len(full_prompt))
        logger.debug("Command: %s", " ".join(cmd[:5]) + "...")

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=self.timeout,
                )

                stdout_str = stdout.decode("utf-8", errors="replace")
                stderr_str = stderr.decode("utf-8", errors="replace")

                if proc.returncode != 0:
                    raise AgentExecutionError(
                        self.name,
                        proc.returncode or -1,
                        stdout_str,
                        stderr_str or "Codex execution failed",
                    )

                # Parse the JSONL output
                return self._parse_output(stdout_str)

            except asyncio.TimeoutError as exc:
                proc.terminate()
                try:
                    await asyncio.wait_for(proc.wait(), timeout=2.0)
                except asyncio.TimeoutError:
                    proc.kill()
                    await proc.wait()

                raise AgentTimeoutError(self.name, self.timeout) from exc

        except FileNotFoundError as exc:
            raise AgentExecutionError(self.name, -1, "", "Executable 'codex' not found") from exc

    def _build_prompt(self, prompt: str, context: Dict[str, Any]) -> str:
        """Build full prompt with context.

        Args:
            prompt: The main task or question
            context: Additional context dict

        Returns:
            Complete prompt string
        """
        parts = []

        # Add mode-specific prefix
        mode = context.get("mode", "quick")
        if mode == "generate":
            parts.append("Generate code for the following requirement:")
        elif mode == "complete":
            parts.append("Complete the following code:")
        elif mode == "refactor":
            parts.append("Refactor the following code for better quality:")
        elif mode == "explain":
            parts.append("Explain the following code:")
        elif mode == "review":
            parts.append("Review the following code and provide feedback:")
        elif mode == "analysis":
            parts.append("Analyze the following codebase and identify issues:")
        else:
            parts.append("Code task:")

        # Add code context if provided
        if code := context.get("code"):
            parts.append(f"\nCode context:\n```\n{code}\n```\n")

        # Add file context if provided
        if files := context.get("files"):
            parts.append(f"\nRelevant files:\n{files}\n")

        # Add main prompt
        parts.append(f"\n{prompt}")

        return "\n".join(parts)

    def _build_exec_command(self, prompt: str) -> List[str]:
        """Build Codex exec command.

        Args:
            prompt: The prompt to execute

        Returns:
            Command list for subprocess
        """
        cmd = ["codex", "exec"]

        if self.bypass_sandbox:
            # WARNING: Only use in already-sandboxed environments
            logger.warning("Using Codex with sandbox bypass - ensure environment is isolated")
            cmd.extend(["--json", "--dangerously-bypass-approvals-and-sandbox", "--", prompt])
        else:
            # Safe sandboxed mode with workspace-write restrictions
            # Use "--" separator to prevent prompt from being interpreted as flags
            cmd.extend(["--sandbox", "workspace-write", "--full-auto", "--json", "--", prompt])

        return cmd

    def _parse_output(self, output: str) -> str:
        """Parse JSONL output from codex exec --json.

        Args:
            output: Raw JSONL output from Codex

        Returns:
            Parsed response text
        """
        lines = output.split("\n")
        messages: List[str] = []
        command_outputs: List[str] = []

        for line in lines:
            if not line.strip():
                continue

            try:
                event = json.loads(line)
                self._parse_event(event, messages, command_outputs)
            except json.JSONDecodeError:
                # Not JSON, might be direct output
                logger.debug("Non-JSON line from Codex: %s", line[:100])
                if line and not line.startswith("["):
                    messages.append(line)

        all_outputs = messages + command_outputs

        if not all_outputs:
            # Return raw output if parsing failed
            return output.strip()

        return "\n".join(all_outputs)

    def _parse_event(
        self,
        event: Dict[str, Any],
        messages: List[str],
        command_outputs: List[str],
    ) -> None:
        """Parse a single Codex event.

        Args:
            event: JSON event from Codex
            messages: List to append messages to
            command_outputs: List to append command outputs to
        """
        # Handle nested message structure
        if "msg" in event:
            msg = event["msg"]
            msg_type = msg.get("type")

            if msg_type == "agent_message":
                if message := msg.get("message"):
                    messages.append(message)
            elif msg_type == "exec_command_end":
                if stdout := msg.get("stdout"):
                    command_outputs.append(stdout.strip())
            elif msg_type == "agent_reasoning":
                if text := msg.get("text"):
                    if not text.startswith("**"):
                        messages.append(f"[Reasoning] {text}")

        # Handle direct message events
        elif event.get("type") == "message":
            if message := event.get("message"):
                messages.append(message)

        # Handle item.completed events (v0.79.0+ format)
        elif event.get("type") == "item.completed":
            item = event.get("item", {})
            item_type = item.get("type", "")
            if item_type == "agent_message":
                if text := item.get("text"):
                    messages.append(text)
            elif item_type == "message":
                content = item.get("content", [])
                for part in content:
                    if part.get("type") == "text":
                        messages.append(part.get("text", ""))

    def get_capabilities(self) -> List[str]:
        """Get Codex capabilities."""
        return [
            "code_generation",
            "code_completion",
            "code_refactoring",
            "code_explanation",
            "code_review",
            "sandbox_execution",
        ]

    def get_priority(self) -> int:
        """Get priority for Codex."""
        return 85  # High priority - good for code-focused tasks
