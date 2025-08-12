#!/usr/bin/env python3
"""
Crush CLI Integration Module
Provides fast AI-powered code generation using Crush
"""

import asyncio
import logging
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CrushIntegration:
    """Handles Crush CLI integration for quick code generation"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.enabled = self.config.get("enabled", True)
        self.auto_consult = self.config.get("auto_consult", True)
        self.api_key = self.config.get("api_key", "")
        self.timeout = self.config.get("timeout", 300)
        self.max_prompt_length = self.config.get("max_prompt_length", 4000)
        self.docker_service = self.config.get("docker_service", "openrouter-agents")
        self.container_command = self.config.get("container_command", ["crush", "run"])
        self.quiet_mode = self.config.get("quiet_mode", True)

        # Generation log
        self.generation_log: List[Dict[str, Any]] = []

        # Conversation history for maintaining state
        self.conversation_history: List[Tuple[str, str]] = []
        self.max_history_entries = self.config.get("max_history_entries", 5)
        self.include_history = self.config.get("include_history", True)

    async def generate_response(
        self,
        prompt: str,
    ) -> Dict[str, Any]:
        """Generate response using Crush CLI"""
        if not self.enabled:
            return {"status": "disabled", "message": "Crush integration is disabled"}

        if not self.api_key:
            return {
                "status": "error",
                "error": "OPENROUTER_API_KEY not configured. Please set it in environment variables.",
            }

        generation_id = f"crush_gen_{int(time.time())}_{len(self.generation_log)}"

        try:
            # Prepare prompt with history if enabled
            full_prompt = self._prepare_prompt(prompt)

            # Execute Crush via Docker
            result = await self._execute_crush_docker(full_prompt)

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
            logger.error(f"Error generating response with Crush: {str(e)}")
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

    async def consult_crush(
        self,
        query: str,
        context: str = "",
        comparison_mode: bool = True,
        force_consult: bool = False,
    ) -> Dict[str, Any]:
        """Consult Crush for AI assistance

        This is an alias for generate_response that follows the Gemini-style consultation pattern.
        """
        if not self.auto_consult and not force_consult:
            return {
                "status": "disabled",
                "message": "Crush auto-consultation is disabled. Use force=True to override.",
            }

        # Map consultation to generate_response
        return await self.generate_response(prompt=query)

    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about consultations"""
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

    def _prepare_prompt(self, prompt: str) -> str:
        """Prepare the prompt with optional history"""
        if not self.include_history or not self.conversation_history:
            # No history to include, just check length
            if len(prompt) > self.max_prompt_length:
                return prompt[: self.max_prompt_length] + "... [truncated]"
            return prompt

        # Build prompt with history
        parts = []

        # Add recent history
        parts.append("Previous context:")
        for i, (prev_q, prev_a) in enumerate(self.conversation_history[-3:], 1):  # Last 3 exchanges
            parts.append(f"Q: {prev_q[:100]}..." if len(prev_q) > 100 else f"Q: {prev_q}")
            parts.append(f"A: {prev_a[:200]}..." if len(prev_a) > 200 else f"A: {prev_a}")
            parts.append("")

        parts.append("Current question:")
        parts.append(prompt)

        full_prompt = "\n".join(parts)

        # Truncate if too long
        if len(full_prompt) > self.max_prompt_length:
            # Keep the current prompt and truncate history
            return prompt[: self.max_prompt_length]

        return full_prompt

    def _is_running_in_container(self) -> bool:
        """Check if we're running inside a Docker container"""
        # Check for .dockerenv file
        if os.path.exists("/.dockerenv"):
            return True
        # Check for Docker in cgroup
        try:
            with open("/proc/1/cgroup", "r") as f:
                return "docker" in f.read()
        except (FileNotFoundError, IOError, OSError):
            return False

    async def _execute_crush_direct(self, prompt: str) -> Dict[str, Any]:
        """Execute Crush binary directly (when already in container)"""
        start_time = time.time()
        logger.info(f"Starting direct crush execution with prompt: {prompt[:50]}...")

        # Build crush command
        cmd = ["crush", "run"]

        # Add quiet flag if enabled
        if self.quiet_mode:
            cmd.append("-q")

        # Add the prompt
        cmd.append(prompt)

        logger.info(f"Command: {' '.join(cmd)}")

        try:
            # Set environment for the subprocess
            env = os.environ.copy()
            env["OPENROUTER_API_KEY"] = self.api_key
            env["OPENAI_API_KEY"] = self.api_key  # Some tools expect this
            env["HOME"] = "/home/node"  # Ensure HOME is set for crush database
            env["TERM"] = "dumb"  # Disable TTY features
            env["NO_COLOR"] = "1"  # Disable color output

            # Create process - run from workspace directory which is writable
            logger.info("Creating crush subprocess...")
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.DEVNULL,  # Explicitly close stdin
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                cwd="/home/node/workspace",  # Run from writable workspace directory
            )

            # Get output with timeout
            logger.info("Waiting for crush process to complete...")
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=self.timeout,
            )
            logger.info(f"Process completed with return code: {process.returncode}")

            execution_time = time.time() - start_time

            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown error"
                raise Exception(f"Crush failed with exit code {process.returncode}: {error_msg}")

            output = stdout.decode().strip()
            logger.info(f"Crush output: {output[:100]}...")

            # Log stderr if present (might contain warnings)
            if stderr:
                stderr_str = stderr.decode()
                if stderr_str.strip():
                    logger.warning(f"Crush stderr: {stderr_str}")

            return {"output": output, "execution_time": execution_time}

        except asyncio.TimeoutError:
            raise Exception(f"Crush timed out after {self.timeout} seconds")

    async def _execute_crush_local(self, prompt: str) -> Dict[str, Any]:
        """Execute Crush locally when not in container"""
        start_time = time.time()
        logger.info(f"Starting local crush execution with prompt: {prompt[:50]}...")

        # Build crush command
        cmd = ["crush", "run"]

        # Add quiet flag if enabled
        if self.quiet_mode:
            cmd.append("-q")

        # Add the prompt
        cmd.append(prompt)

        logger.info(f"Command: {' '.join(cmd)}")

        try:
            # Set environment for the subprocess
            env = os.environ.copy()
            env["OPENROUTER_API_KEY"] = self.api_key
            env["OPENAI_API_KEY"] = self.api_key  # Some tools expect this
            env["TERM"] = "dumb"  # Disable TTY features
            env["NO_COLOR"] = "1"  # Disable color output

            # Create process
            logger.info("Creating crush subprocess...")
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.DEVNULL,  # Explicitly close stdin
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )

            # Get output with timeout
            logger.info("Waiting for crush process to complete...")
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=self.timeout,
            )
            logger.info(f"Process completed with return code: {process.returncode}")

            execution_time = time.time() - start_time

            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown error"
                raise Exception(f"Crush failed with exit code {process.returncode}: {error_msg}")

            output = stdout.decode().strip()
            logger.info(f"Crush output: {output[:100]}...")

            # Log stderr if present (might contain warnings)
            if stderr:
                stderr_str = stderr.decode()
                if stderr_str.strip():
                    logger.warning(f"Crush stderr: {stderr_str}")

            return {"output": output, "execution_time": execution_time}

        except asyncio.TimeoutError:
            raise Exception(f"Crush timed out after {self.timeout} seconds")

    async def _execute_crush_docker(self, prompt: str) -> Dict[str, Any]:
        """Execute Crush via Docker container"""
        # If we're already in a container, use direct execution
        if self._is_running_in_container():
            logger.info("Running in container, using direct crush execution")
            return await self._execute_crush_direct(prompt)

        # If crush is available locally, use local execution
        try:
            result = await asyncio.create_subprocess_exec(
                "which",
                "crush",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await result.communicate()
            if result.returncode == 0 and stdout.strip():
                logger.info("Crush found locally, using local execution")
                return await self._execute_crush_local(prompt)
        except Exception:
            pass

        start_time = time.time()

        # Build docker-compose command
        cmd = [
            "/usr/local/bin/docker-compose",
            "run",
            "--rm",
        ]

        # Add environment variables
        cmd.extend(["-e", f"OPENROUTER_API_KEY={self.api_key}"])
        cmd.extend(["-e", f"OPENAI_API_KEY={self.api_key}"])  # Some tools expect this

        # Add the service name
        cmd.append(self.docker_service)

        # Add the Crush command
        cmd.extend(self.container_command)

        # Add quiet flag if enabled
        if self.quiet_mode:
            cmd.append("-q")

        # Add the prompt
        cmd.append(prompt)

        try:
            # Create process
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # Get output with timeout
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=self.timeout,
            )

            execution_time = time.time() - start_time

            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown error"
                raise Exception(f"Crush failed with exit code {process.returncode}: {error_msg}")

            output = stdout.decode().strip()

            # Log stderr if present (might contain warnings)
            if stderr:
                stderr_str = stderr.decode()
                if stderr_str.strip():
                    logger.warning(f"Crush stderr: {stderr_str}")

            return {"output": output, "execution_time": execution_time}

        except asyncio.TimeoutError:
            raise Exception(f"Crush timed out after {self.timeout} seconds")


# Singleton pattern implementation
_integration = None


def get_integration(config: Optional[Dict[str, Any]] = None) -> CrushIntegration:
    """
    Get or create the global Crush integration instance.

    This ensures that all parts of the application share the same instance,
    maintaining consistent state for conversation history and configuration.

    Args:
        config: Optional configuration dict. Only used on first call.

    Returns:
        The singleton CrushIntegration instance
    """
    global _integration
    if _integration is None:
        _integration = CrushIntegration(config)
    return _integration
