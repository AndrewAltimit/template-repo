#!/usr/bin/env python3
"""
Gemini CLI Integration Module
Provides automatic consultation with Gemini for second opinions and validation
"""

import asyncio
import logging
import re
import time
from datetime import datetime
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
        self.timeout = self.config.get("timeout", 60)
        self.rate_limit_delay = self.config.get("rate_limit_delay", 2.0)
        self.last_consultation = 0
        self.consultation_log = []
        self.max_context_length = self.config.get("max_context_length", 4000)
        self.model = self.config.get("model", "gemini-2.5-flash")

        # Conversation history for maintaining state
        self.conversation_history = []
        self.max_history_entries = self.config.get("max_history_entries", 10)
        self.include_history = self.config.get("include_history", True)

    async def consult_gemini(
        self,
        query: str,
        context: str = "",
        comparison_mode: bool = True,
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
                    self.conversation_history = self.conversation_history[
                        -self.max_history_entries :
                    ]

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
            logger.error(f"Error consulting Gemini: {str(e)}")
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
                sum(e.get("execution_time", 0) for e in completed) / len(completed)
                if completed
                else 0
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
            parts.append("Please provide a technical analysis and second opinion:")
            parts.append("")

        # Include conversation history if enabled and available
        if self.include_history and self.conversation_history:
            parts.append("Previous conversation:")
            parts.append("-" * 40)
            for i, (prev_q, prev_a) in enumerate(
                self.conversation_history[-self.max_history_entries :], 1
            ):
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

        parts.append("Current Question/Topic:")
        parts.append(query)

        if comparison_mode:
            parts.extend(
                [
                    "",
                    "Please structure your response with:",
                    "1. Your analysis and understanding",
                    "2. Recommendations or approach",
                    "3. Any concerns or considerations",
                    "4. Alternative approaches (if applicable)",
                ]
            )

        return "\n".join(parts)

    async def _execute_gemini_cli(self, query: str) -> Dict[str, Any]:
        """Execute Gemini CLI command and return results"""
        start_time = time.time()

        # Build command
        cmd = [self.cli_command]
        if self.model:
            cmd.extend(["-m", self.model])
        cmd.extend(["-p", query])  # Non-interactive mode

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=self.timeout
            )

            execution_time = time.time() - start_time

            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown error"
                if "authentication" in error_msg.lower():
                    error_msg += "\nTip: Run 'gemini' interactively to authenticate"
                raise Exception(f"Gemini CLI failed: {error_msg}")

            return {"output": stdout.decode().strip(), "execution_time": execution_time}

        except asyncio.TimeoutError:
            raise Exception(f"Gemini CLI timed out after {self.timeout} seconds")


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
    global _integration
    if _integration is None:
        _integration = GeminiIntegration(config)
    return _integration
