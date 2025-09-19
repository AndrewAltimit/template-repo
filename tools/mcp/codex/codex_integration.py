"""Codex Integration Module"""

import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class CodexIntegration:
    """Integration with OpenAI Codex for code generation"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.enabled = config.get("enabled", True)
        self.auto_consult = config.get("auto_consult", True)
        self.auth_path = Path(config.get("auth_path", Path.home() / ".codex" / "auth.json"))

        # History tracking
        self.conversation_history: List[Dict[str, Any]] = []
        self.max_history = config.get("max_history_entries", 5)
        self.include_history = config.get("include_history", True)

        # Statistics
        self.stats: Dict[str, Any] = {
            "consultations": 0,
            "errors": 0,
            "last_consultation": None,
            "total_tokens": 0,
        }

        # Check if running in container
        self.is_container = os.path.exists("/.dockerenv")
        self.docker_service = config.get("docker_service", "codex-agent")

    async def consult_codex(
        self,
        query: str,
        context: str = "",
        mode: str = "quick",
        comparison_mode: bool = True,
    ) -> Dict[str, Any]:
        """Consult Codex for code generation or assistance"""

        # Update statistics
        self.stats["consultations"] += 1
        self.stats["last_consultation"] = datetime.now().isoformat()

        try:
            # Build the prompt (not used since Codex is interactive)
            _ = self._build_prompt(query, context, mode)

            # Check if Codex CLI is available
            if not self._check_codex_available():
                return {
                    "status": "error",
                    "error": "Codex CLI not available. Please install with: npm install -g @openai/codex",
                }

            # Since Codex primarily works in interactive mode, we'll return a structured response
            # that indicates the query would need to be used interactively
            response = {
                "status": "success",
                "mode": mode,
                "query": query,
                "context_provided": bool(context),
                "message": "Codex operates in interactive mode. Please use the Codex CLI directly for code generation.",
                "suggestion": f"Run: codex\nThen paste your query: {query[:100]}..." if len(query) > 100 else query,
            }

            # Add to history if enabled
            if self.include_history:
                self._add_to_history(query, response)

            return response

        except Exception as e:
            self.stats["errors"] += 1
            return {
                "status": "error",
                "error": str(e),
                "mode": mode,
            }

    def _check_codex_available(self) -> bool:
        """Check if Codex CLI is available"""
        try:
            if self.is_container:
                # Check in container
                result = subprocess.run(
                    ["which", "codex"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
            else:
                # Check on host
                result = subprocess.run(
                    ["which", "codex"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
            return result.returncode == 0
        except Exception:
            return False

    def _build_prompt(self, query: str, context: str, mode: str) -> str:
        """Build a prompt for Codex based on mode and context"""

        prompt_parts = []

        # Add mode-specific prefix
        if mode == "generate":
            prompt_parts.append("Generate code for the following requirement:")
        elif mode == "complete":
            prompt_parts.append("Complete the following code:")
        elif mode == "refactor":
            prompt_parts.append("Refactor the following code for better quality:")
        elif mode == "explain":
            prompt_parts.append("Explain the following code:")
        else:  # quick mode
            prompt_parts.append("Code task:")

        # Add context if provided
        if context:
            prompt_parts.append(f"\nContext:\n{context}\n")

        # Add the main query
        prompt_parts.append(f"\n{query}")

        # Add history if enabled and available
        if self.include_history and self.conversation_history:
            history_text = self._format_history()
            if history_text:
                prompt_parts.insert(0, f"Previous context:\n{history_text}\n---\n")

        return "\n".join(prompt_parts)

    def _format_history(self) -> str:
        """Format conversation history for context"""
        if not self.conversation_history:
            return ""

        history_parts = []
        for entry in self.conversation_history[-self.max_history :]:
            history_parts.append(f"Q: {entry['query'][:200]}...")
            if "response" in entry and entry["response"].get("status") == "success":
                history_parts.append(f"A: {entry['response'].get('message', 'Done')[:200]}...")

        return "\n".join(history_parts)

    def _add_to_history(self, query: str, response: Dict[str, Any]):
        """Add an interaction to the conversation history"""
        self.conversation_history.append(
            {
                "timestamp": datetime.now().isoformat(),
                "query": query,
                "response": response,
            }
        )

        # Trim history if it exceeds max size
        if len(self.conversation_history) > self.max_history * 2:
            self.conversation_history = self.conversation_history[-self.max_history :]

    async def clear_history(self) -> Dict[str, Any]:
        """Clear the conversation history"""
        self.conversation_history.clear()
        return {
            "status": "success",
            "message": "Codex conversation history cleared",
        }

    def get_status(self) -> Dict[str, Any]:
        """Get the current status of Codex integration"""
        return {
            "enabled": self.enabled,
            "auto_consult": self.auto_consult,
            "auth_exists": self.auth_path.exists(),
            "codex_available": self._check_codex_available(),
            "is_container": self.is_container,
            "stats": self.stats.copy(),
            "history_size": len(self.conversation_history),
        }

    def toggle_auto_consult(self, enable: Optional[bool] = None) -> Dict[str, Any]:
        """Toggle automatic consultation"""
        if enable is None:
            self.auto_consult = not self.auto_consult
        else:
            self.auto_consult = bool(enable)

        return {
            "enabled": self.auto_consult,
            "message": f"Codex auto-consultation {'enabled' if self.auto_consult else 'disabled'}",
        }


def get_integration(config: Dict[str, Any]) -> CodexIntegration:
    """Factory function to get Codex integration instance"""
    return CodexIntegration(config)
