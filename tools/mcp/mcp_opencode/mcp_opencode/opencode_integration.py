#!/usr/bin/env python3
"""
OpenCode CLI Integration Module
Provides AI-powered code generation using OpenCode
"""

import asyncio
from datetime import datetime
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OpenCodeIntegration:
    """Handles OpenCode CLI integration for code generation"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.enabled = self.config.get("enabled", True)
        self.auto_consult = self.config.get("auto_consult", True)
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
            if self.config.get("log_consultations", self.config.get("log_generations", True)):
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
            logger.error("Error generating code with OpenCode: %s", str(e))
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

    async def consult_opencode(
        self,
        query: str,
        context: str = "",
        comparison_mode: bool = True,
        force_consult: bool = False,
    ) -> Dict[str, Any]:
        """Consult OpenCode for AI assistance

        This is an alias for generate_code that follows the Gemini-style consultation pattern.
        """
        if not self.auto_consult and not force_consult:
            return {
                "status": "disabled",
                "message": "OpenCode auto-consultation is disabled. Use force=True to override.",
            }

        # Map consultation to generate_code
        return await self.generate_code(
            prompt=query,
            context=context,
        )

    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about code generations"""
        if not self.generation_log:
            return {"total_consultations": 0}

        completed = [e for e in self.generation_log if e.get("status") == "success"]

        return {
            "total_consultations": len(self.generation_log),
            "completed_consultations": len(completed),
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
        """Execute OpenCode via direct API call"""
        start_time = time.time()

        # Use HTTP API approach instead of trying to run docker commands
        import aiohttp

        try:
            # Prepare the request
            url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/AndrewAltimit/template-repo",
                "X-Title": "OpenCode MCP Server",
            }

            data = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
                "max_tokens": 4000,
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    headers=headers,
                    json=data,
                    timeout=aiohttp.ClientTimeout(total=self.timeout),
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise RuntimeError(f"API request failed with status {response.status}: {error_text}")

                    result = await response.json()
                    output = result.get("choices", [{}])[0].get("message", {}).get("content", "")

                    execution_time = time.time() - start_time

                    return {"output": output, "execution_time": execution_time}

        except asyncio.TimeoutError as exc:
            raise TimeoutError(f"OpenCode API request timed out after {self.timeout} seconds") from exc


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
    global _integration  # pylint: disable=global-statement
    if _integration is None:
        _integration = OpenCodeIntegration(config)
    return _integration
