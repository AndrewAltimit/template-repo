#!/usr/bin/env python3
"""
OpenCode CLI Integration Module
Provides AI-powered code generation using OpenCode
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OpenCodeIntegration:
    """Handles OpenCode CLI integration for code generation"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.enabled = self.config.get("enabled", True)
        self.api_key = self.config.get("api_key", "")
        self.model = self.config.get("model", "qwen/qwen-2.5-coder-32b-instruct")
        self.timeout = self.config.get("timeout", 300)
        self.max_context_length = self.config.get("max_context_length", 8000)
        self.docker_service = self.config.get("docker_service", "openrouter-agents")
        self.container_command = self.config.get("container_command", ["opencode", "run"])

        # Generation log
        self.generation_log: List[Dict[str, Any]] = []

        # Conversation history for maintaining state
        self.conversation_history: List[Tuple[str, str]] = []
        self.max_history_entries = self.config.get("max_history_entries", 5)
        self.include_history = self.config.get("include_history", True)

    async def generate_code(
        self,
        prompt: str,
        context: str = "",
        language: str = "",
        include_tests: bool = False,
        plan_mode: bool = False,
    ) -> Dict[str, Any]:
        """Generate code using OpenCode CLI"""
        if not self.enabled:
            return {"status": "disabled", "message": "OpenCode integration is disabled"}

        if not self.api_key:
            return {
                "status": "error",
                "error": "OPENROUTER_API_KEY not configured. Please set it in environment variables.",
            }

        generation_id = f"gen_{int(time.time())}_{len(self.generation_log)}"

        try:
            # Prepare prompt with context
            full_prompt = self._prepare_prompt(prompt, context, language, include_tests, plan_mode)

            # Execute OpenCode via Docker
            result = await self._execute_opencode_docker(full_prompt)

            # Save to conversation history
            if self.include_history and result.get("output"):
                self.conversation_history.append((prompt, result["output"]))
                # Trim history if it exceeds max entries
                if len(self.conversation_history) > self.max_history_entries:
                    self.conversation_history = self.conversation_history[-self.max_history_entries :]

            # Log generation
            if self.config.get("log_generations", True):
                self.generation_log.append(
                    {
                        "id": generation_id,
                        "timestamp": datetime.now().isoformat(),
                        "prompt": (prompt[:200] + "..." if len(prompt) > 200 else prompt),
                        "status": "success",
                        "execution_time": result.get("execution_time", 0),
                    }
                )

            return {
                "status": "success",
                "response": result["output"],
                "execution_time": result["execution_time"],
                "generation_id": generation_id,
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error generating code with OpenCode: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
                "generation_id": generation_id,
            }

    def clear_conversation_history(self) -> Dict[str, Any]:
        """Clear the conversation history"""
        old_count = len(self.conversation_history)
        self.conversation_history = []
        return {
            "status": "success",
            "cleared_entries": old_count,
            "message": f"Cleared {old_count} conversation entries",
        }

    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about code generations"""
        if not self.generation_log:
            return {"total_generations": 0}

        completed = [e for e in self.generation_log if e.get("status") == "success"]

        return {
            "total_generations": len(self.generation_log),
            "completed_generations": len(completed),
            "average_execution_time": (
                sum(e.get("execution_time", 0) for e in completed) / len(completed) if completed else 0
            ),
            "conversation_history_size": len(self.conversation_history),
        }

    def _prepare_prompt(
        self,
        prompt: str,
        context: str,
        language: str,
        include_tests: bool,
        plan_mode: bool,
    ) -> str:
        """Prepare the full prompt for OpenCode"""
        parts = []

        # Include conversation history if enabled and available
        if self.include_history and self.conversation_history:
            parts.append("Previous conversation:")
            parts.append("-" * 40)
            for i, (prev_q, prev_a) in enumerate(self.conversation_history[-self.max_history_entries :], 1):
                parts.append(f"Q{i}: {prev_q}")
                # Truncate long responses in history
                if len(prev_a) > 1000:
                    parts.append(f"A{i}: {prev_a[:1000]}... [truncated]")
                else:
                    parts.append(f"A{i}: {prev_a}")
                parts.append("")
            parts.append("-" * 40)
            parts.append("")

        # Add context if provided
        if context:
            # Truncate context if too long
            if len(context) > self.max_context_length:
                context = context[: self.max_context_length] + "\n[Context truncated...]"

            parts.append("Context/Existing Code:")
            parts.append("```")
            parts.append(context)
            parts.append("```")
            parts.append("")

        # Add language hint if provided
        if language:
            parts.append(f"Language: {language}")
            parts.append("")

        # Add mode indicators
        if plan_mode:
            parts.append("Mode: Plan Mode (provide step-by-step implementation plan)")
            parts.append("")

        # Add the main prompt
        parts.append("Task:")
        parts.append(prompt)

        # Add test requirement if requested
        if include_tests:
            parts.append("")
            parts.append("Additional requirement: Include comprehensive unit tests for the generated code.")

        return "\n".join(parts)

    async def _execute_opencode_docker(self, prompt: str) -> Dict[str, Any]:
        """Execute OpenCode via Docker container"""
        start_time = time.time()

        # Build docker-compose command
        cmd = [
            "docker-compose",
            "run",
            "--rm",
            "-T",  # Disable pseudo-TTY allocation for stdin
        ]

        # Add environment variables
        cmd.extend(["-e", f"OPENROUTER_API_KEY={self.api_key}"])
        cmd.extend(["-e", f"OPENCODE_MODEL={self.model}"])

        # Add the service name
        cmd.append(self.docker_service)

        # Add the OpenCode command
        cmd.extend(self.container_command)

        # Add model flag
        cmd.extend(["-m", f"openrouter/{self.model}"])

        try:
            # Create process with stdin
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # Send prompt via stdin and get output
            stdout, stderr = await asyncio.wait_for(
                process.communicate(input=prompt.encode("utf-8")),
                timeout=self.timeout,
            )

            execution_time = time.time() - start_time

            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown error"
                raise Exception(f"OpenCode failed with exit code {process.returncode}: {error_msg}")

            output = stdout.decode().strip()

            # Log stderr if present (might contain warnings)
            if stderr:
                logger.warning(f"OpenCode stderr: {stderr.decode()}")

            return {"output": output, "execution_time": execution_time}

        except asyncio.TimeoutError:
            raise Exception(f"OpenCode timed out after {self.timeout} seconds")


# Singleton pattern implementation
_integration = None


def get_integration(config: Optional[Dict[str, Any]] = None) -> OpenCodeIntegration:
    """
    Get or create the global OpenCode integration instance.

    This ensures that all parts of the application share the same instance,
    maintaining consistent state for conversation history and configuration.

    Args:
        config: Optional configuration dict. Only used on first call.

    Returns:
        The singleton OpenCodeIntegration instance
    """
    global _integration
    if _integration is None:
        _integration = OpenCodeIntegration(config)
    return _integration
