#!/usr/bin/env python3
"""
Gemini CLI Integration Module
Provides automatic consultation with Gemini for second opinions and validation
"""

import asyncio
from datetime import datetime
import logging
import os
import re
import shutil
import tempfile
import time
from typing import Any, Dict, List, Optional, Tuple

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Uncertainty patterns that trigger automatic Gemini consultation
UNCERTAINTY_PATTERNS = [
    r"\bI'm not sure\b",
    r"\bI think\b",
    r"\bpossibly\b",
    r"\bprobably\b",
    r"\bmight be\b",
    r"\bcould be\b",
    r"\bI believe\b",
    r"\bIt seems\b",
    r"\bappears to be\b",
    r"\buncertain\b",
    r"\bI would guess\b",
    r"\blikely\b",
    r"\bperhaps\b",
    r"\bmaybe\b",
    r"\bI assume\b",
]

# Complex decision patterns that benefit from second opinions
COMPLEX_DECISION_PATTERNS = [
    r"\bmultiple approaches\b",
    r"\bseveral options\b",
    r"\btrade-offs?\b",
    r"\bconsider(?:ing)?\b",
    r"\balternatives?\b",
    r"\bpros and cons\b",
    r"\bweigh(?:ing)? the options\b",
    r"\bchoice between\b",
    r"\bdecision\b",
]

# Critical operations that should trigger consultation
CRITICAL_OPERATION_PATTERNS = [
    r"\bproduction\b",
    r"\bdatabase migration\b",
    r"\bsecurity\b",
    r"\bauthentication\b",
    r"\bencryption\b",
    r"\bAPI key\b",
    r"\bcredentials?\b",
    r"\bperformance\s+critical\b",
]


class GeminiIntegration:
    """Handles Gemini CLI integration for second opinions and validation"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.enabled = self.config.get("enabled", True)
        self.auto_consult = self.config.get("auto_consult", True)
        self.cli_command = self.config.get("cli_command", "gemini")
        self.timeout = self.config.get("timeout", 600)  # 10 minutes for agentic model
        self.rate_limit_delay = self.config.get("rate_limit_delay", 2.0)
        self.last_consultation = 0
        self.consultation_log: List[Dict[str, Any]] = []
        self.max_context_length = self.config.get(
            "max_context_length", 100000
        )  # Large context for comprehensive understanding
        # API key mode supports explicit model selection via --model flag
        self.model = self.config.get("model", "gemini-3-flash-preview")

        # Container configuration
        self.use_container = self.config.get("use_container", True)
        self.container_image = self.config.get("container_image", "gemini-corporate-proxy:latest")
        self.container_script = self.config.get(
            "container_script", "/workspace/automation/corporate-proxy/gemini/scripts/run.sh"
        )
        self.yolo_mode = self.config.get("yolo_mode", False)

        # Conversation history for maintaining state
        self.conversation_history: List[Tuple[str, str]] = []
        self.max_history_entries = self.config.get("max_history_entries", 10)
        self.include_history = self.config.get("include_history", True)

    async def consult_gemini(
        self,
        query: str,
        context: str = "",
        comparison_mode: bool = False,  # Disabled by default to avoid CLI issues
        force_consult: bool = False,
    ) -> Dict[str, Any]:
        """Consult Gemini CLI for second opinion"""
        if not self.enabled and not force_consult:
            return {"status": "disabled", "message": "Gemini integration is disabled"}

        if not force_consult:
            await self._enforce_rate_limit()

        consultation_id = f"consult_{int(time.time())}_{len(self.consultation_log)}"

        try:
            # Prepare query with context
            full_query = self._prepare_query(query, context, comparison_mode)

            # Execute Gemini CLI command
            result = await self._execute_gemini_cli(full_query)

            # Save to conversation history
            if self.include_history and result.get("output"):
                self.conversation_history.append((query, result["output"]))
                # Trim history if it exceeds max entries
                if len(self.conversation_history) > self.max_history_entries:
                    self.conversation_history = self.conversation_history[-self.max_history_entries :]

            # Log consultation
            if self.config.get("log_consultations", True):
                self.consultation_log.append(
                    {
                        "id": consultation_id,
                        "timestamp": datetime.now().isoformat(),
                        "query": (query[:200] + "..." if len(query) > 200 else query),
                        "status": "success",
                        "execution_time": result.get("execution_time", 0),
                    }
                )

            return {
                "status": "success",
                "response": result["output"],
                "execution_time": result["execution_time"],
                "consultation_id": consultation_id,
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error("Error consulting Gemini: %s", str(e))
            return {
                "status": "error",
                "error": str(e),
                "consultation_id": consultation_id,
            }

    def detect_uncertainty(self, text: str) -> Tuple[bool, List[str]]:
        """Detect if text contains uncertainty patterns"""
        found_patterns = []

        # Check uncertainty patterns
        for pattern in UNCERTAINTY_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                found_patterns.append(f"uncertainty: {pattern}")

        # Check complex decision patterns
        for pattern in COMPLEX_DECISION_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                found_patterns.append(f"complex_decision: {pattern}")

        # Check critical operation patterns
        for pattern in CRITICAL_OPERATION_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                found_patterns.append(f"critical_operation: {pattern}")

        return len(found_patterns) > 0, found_patterns

    def clear_conversation_history(self) -> Dict[str, Any]:
        """Clear the conversation history"""
        old_count = len(self.conversation_history)
        self.conversation_history = []
        return {
            "status": "success",
            "cleared_entries": old_count,
            "message": f"Cleared {old_count} conversation entries",
        }

    def get_consultation_stats(self) -> Dict[str, Any]:
        """Get statistics about consultations"""
        if not self.consultation_log:
            return {"total_consultations": 0}

        completed = [e for e in self.consultation_log if e.get("status") == "success"]

        return {
            "total_consultations": len(self.consultation_log),
            "completed_consultations": len(completed),
            "average_execution_time": (
                sum(e.get("execution_time", 0) for e in completed) / len(completed) if completed else 0
            ),
            "conversation_history_size": len(self.conversation_history),
        }

    async def _enforce_rate_limit(self):
        """Enforce rate limiting between consultations"""
        current_time = time.time()
        time_since_last = current_time - self.last_consultation

        if time_since_last < self.rate_limit_delay:
            sleep_time = self.rate_limit_delay - time_since_last
            await asyncio.sleep(sleep_time)

        self.last_consultation = time.time()

    def _prepare_query(self, query: str, context: str, comparison_mode: bool) -> str:
        """Prepare the full query for Gemini CLI"""
        parts = []

        if comparison_mode:
            # Note: Avoid phrases that trigger special CLI features (causes 404)
            parts.append("Please analyze the following:")
            parts.append("")

        # Include conversation history if enabled and available
        if self.include_history and self.conversation_history:
            parts.append("Previous conversation:")
            parts.append("-" * 40)
            for i, (prev_q, prev_a) in enumerate(self.conversation_history[-self.max_history_entries :], 1):
                parts.append(f"Q{i}: {prev_q}")
                # Truncate long responses in history
                if len(prev_a) > 500:
                    parts.append(f"A{i}: {prev_a[:500]}... [truncated]")
                else:
                    parts.append(f"A{i}: {prev_a}")
                parts.append("")
            parts.append("-" * 40)
            parts.append("")

        # Truncate context if too long
        if len(context) > self.max_context_length:
            context = context[: self.max_context_length] + "\n[Context truncated...]"

        if context:
            parts.append("Context:")
            parts.append(context)
            parts.append("")

        parts.append(query)

        # Note: Simplified structure to avoid triggering CLI special features
        if comparison_mode:
            parts.extend(
                [
                    "",
                    "Please include analysis, recommendations, and any concerns.",
                ]
            )

        return "\n".join(parts)

    async def _execute_gemini_cli(self, query: str) -> Dict[str, Any]:
        """Execute Gemini CLI command and return results"""
        start_time = time.time()

        if self.use_container:
            return await self._execute_gemini_container(query, start_time)
        return await self._execute_gemini_direct(query, start_time)

    async def _execute_gemini_direct(self, query: str, start_time: float) -> Dict[str, Any]:
        """Execute Gemini CLI directly on the host"""
        # Build command - use stdin for multi-line prompts
        # With API key, we can use --model flag for explicit model selection
        # In container: use globally installed gemini CLI
        # On host: use npx for reliability
        cmd = [self.cli_command, "prompt"]

        # Add model if specified
        if self.model:
            cmd.extend(["--model", self.model])

        cmd.extend(["--output-format", "text"])
        stdin_input = query.encode("utf-8")

        # Get API key from environment (supports both GOOGLE_API_KEY and GEMINI_API_KEY)
        env = os.environ.copy()
        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if api_key:
            env["GOOGLE_API_KEY"] = api_key

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )

            stdout, stderr = await asyncio.wait_for(process.communicate(input=stdin_input), timeout=self.timeout)

            execution_time = time.time() - start_time

            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown error"
                if "authentication" in error_msg.lower() or "login required" in error_msg.lower():
                    error_msg = (
                        "Gemini authentication required. Please run 'gemini' interactively on the host "
                        "to complete authentication. Note: Gemini uses Google account authentication, not API keys."
                    )
                raise RuntimeError(f"Gemini CLI failed: {error_msg}")

            output = stdout.decode().strip()

            # Check for authentication messages in stdout
            if "login required" in output.lower() or "waiting for authentication" in output.lower():
                raise PermissionError(
                    "Gemini authentication required. Please run 'gemini' interactively on the host "
                    "to complete authentication. Note: Gemini uses Google account authentication, not API keys."
                )

            return {"output": output, "execution_time": execution_time}

        except asyncio.TimeoutError as exc:
            raise TimeoutError(f"Gemini CLI timed out after {self.timeout} seconds") from exc

    def _prepare_gemini_temp_dir(self) -> str:
        """Create and populate temporary .gemini directory for container."""
        temp_gemini_dir = tempfile.mkdtemp(prefix="gemini_")
        src_gemini = os.path.expanduser("~/.gemini")

        if os.path.exists(src_gemini):
            for item in os.listdir(src_gemini):
                src_item = os.path.join(src_gemini, item)
                dst_item = os.path.join(temp_gemini_dir, item)
                if os.path.isfile(src_item):
                    shutil.copy2(src_item, dst_item)
                elif os.path.isdir(src_item):
                    shutil.copytree(src_item, dst_item)

            os.chmod(temp_gemini_dir, 0o755)
            for root, dirs, files in os.walk(temp_gemini_dir):
                for d in dirs:
                    os.chmod(os.path.join(root, d), 0o755)
                for f in files:
                    os.chmod(os.path.join(root, f), 0o644)

        return temp_gemini_dir

    def _build_docker_command(self, temp_gemini_dir: str) -> List[str]:
        """Build Docker command for Gemini container execution."""
        user_id = os.getuid()
        group_id = os.getgid()

        cmd = [
            "docker",
            "run",
            "--rm",
            "-i",
            "-u",
            f"{user_id}:{group_id}",
            "-v",
            f"{temp_gemini_dir}:/home/node/.gemini",
            "-v",
            f"{os.getcwd()}:/workspace",
        ]

        if self.yolo_mode:
            cmd.extend(["-e", "GEMINI_APPROVAL_MODE=yolo"])

        cmd.append(self.container_image)
        cmd.extend(["prompt"])

        if self.model:
            cmd.extend(["--model", self.model])

        cmd.extend(["--output-format", "text"])
        return cmd

    def _handle_container_error(self, stderr: bytes, container_image: str) -> str:
        """Convert container error to user-friendly message."""
        error_msg = stderr.decode() if stderr else "Unknown error"
        if "authentication" in error_msg.lower() or "login required" in error_msg.lower():
            return (
                "Gemini authentication required. Please ensure ~/.gemini exists on the host "
                "with valid authentication. Run 'gemini' interactively on the host to authenticate."
            )
        if "docker" in error_msg.lower() and "not found" in error_msg.lower():
            return "Docker is not installed or not in PATH. Container mode requires Docker."
        if "no such image" in error_msg.lower():
            return f"Container image '{container_image}' not found. Please build or pull it first."
        return error_msg

    async def _execute_gemini_container(self, _query: str, start_time: float) -> Dict[str, Any]:
        """Execute Gemini CLI through Docker container"""
        temp_gemini_dir = None
        try:
            temp_gemini_dir = self._prepare_gemini_temp_dir()
            cmd = self._build_docker_command(temp_gemini_dir)

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=None,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=self.timeout)
            execution_time = time.time() - start_time

            if process.returncode != 0:
                error_msg = self._handle_container_error(stderr, self.container_image)
                raise RuntimeError(f"Gemini container execution failed: {error_msg}")

            output = stdout.decode().strip()

            if "login required" in output.lower() or "waiting for authentication" in output.lower():
                raise PermissionError(
                    "Gemini authentication required. Please ensure ~/.gemini exists on the host "
                    "with valid authentication. Run 'gemini' interactively on the host to authenticate."
                )

            return {"output": output, "execution_time": execution_time}

        except asyncio.TimeoutError as exc:
            raise TimeoutError(f"Gemini container execution timed out after {self.timeout} seconds") from exc
        finally:
            # Clean up temporary directory
            if temp_gemini_dir and os.path.exists(temp_gemini_dir):
                try:
                    shutil.rmtree(temp_gemini_dir)
                except Exception:
                    pass


# Singleton pattern implementation
_integration = None


def get_integration(config: Optional[Dict[str, Any]] = None) -> GeminiIntegration:
    """
    Get or create the global Gemini integration instance.

    This ensures that all parts of the application share the same instance,
    maintaining consistent state for rate limiting, consultation history,
    and configuration across all tool calls.

    Args:
        config: Optional configuration dict. Only used on first call.

    Returns:
        The singleton GeminiIntegration instance
    """
    global _integration  # pylint: disable=global-statement
    if _integration is None:
        _integration = GeminiIntegration(config)
    return _integration
