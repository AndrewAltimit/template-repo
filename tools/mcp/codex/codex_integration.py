"""Codex Integration Module"""

import asyncio
import json
import logging
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
        self.logger = logging.getLogger(__name__)

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
            # Check if Codex CLI is available
            if not await self._check_codex_available():
                return {
                    "status": "error",
                    "error": "Codex CLI not available. Please install with: npm install -g @openai/codex",
                }

            # Build the prompt
            prompt = self._build_prompt(query, context, mode)

            # Execute Codex programmatically using Node.js script
            result = await self._execute_codex(prompt, mode)

            # Add to history if enabled
            if self.include_history and result.get("status") == "success":
                self._add_to_history(query, result)

            return result

        except Exception as e:
            self.stats["errors"] += 1
            return {
                "status": "error",
                "error": str(e),
                "mode": mode,
            }

    async def _execute_codex(self, prompt: str, mode: str) -> Dict[str, Any]:
        """Execute Codex using a programmatic approach"""
        try:
            # Determine execution mode based on environment
            # Default to safe sandboxed mode unless explicitly overridden
            exec_args = ["codex", "exec"]

            # Check for environment override (only for sandboxed VMs)
            if os.environ.get("CODEX_BYPASS_SANDBOX") == "true":
                # WARNING: Only use this in already-sandboxed environments (VMs, containers)
                exec_args.extend(["--json", "--dangerously-bypass-approvals-and-sandbox", prompt])
            else:
                # Default: Use safe sandboxed mode with workspace-write restrictions
                exec_args.extend(["--sandbox", "workspace-write", "--full-auto", "--json", prompt])

            process = await asyncio.create_subprocess_exec(
                *exec_args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=self.config.get("timeout", 300))

            except asyncio.TimeoutError:
                return {
                    "status": "error",
                    "error": f"Codex execution timed out after {self.config.get('timeout', 300)} seconds",
                    "mode": mode,
                }

            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Codex execution failed"
                return {
                    "status": "error",
                    "error": error_msg,
                    "mode": mode,
                }

            output = stdout.decode().strip()
            if not output:
                return {
                    "status": "error",
                    "error": "No output from Codex",
                    "mode": mode,
                }

            # Parse JSONL output from codex exec --json (now used in both modes)
            lines = output.split("\n")
            messages = []
            command_outputs = []

            for line in lines:
                if not line.strip():
                    continue
                try:
                    event = json.loads(line)

                    # Handle nested message structure
                    if "msg" in event:
                        msg = event["msg"]
                        msg_type = msg.get("type")

                        # Extract agent messages
                        if msg_type == "agent_message":
                            messages.append(msg.get("message", ""))

                        # Extract command execution output
                        elif msg_type == "exec_command_end":
                            if msg.get("stdout"):
                                command_outputs.append(msg.get("stdout").strip())

                        # Extract agent reasoning (optional, for context)
                        elif msg_type == "agent_reasoning":
                            text = msg.get("text", "")
                            if text and not text.startswith("**"):
                                messages.append(f"[Reasoning] {text}")

                    # Handle direct message events
                    elif event.get("type") == "message":
                        messages.append(event.get("message", ""))

                except json.JSONDecodeError:
                    self.logger.warning(f"Could not parse JSON line from Codex output: {line}")
                    # Fallback for non-JSON lines
                    if line and not line.startswith("["):
                        messages.append(line)

            # Combine messages and command outputs
            all_outputs = messages + command_outputs
            combined_output = "\n".join(all_outputs) if all_outputs else output

            return {
                "status": "success",
                "output": combined_output,
                "mode": mode,
                "message": "Codex executed successfully",
            }

        except Exception as e:
            return {
                "status": "error",
                "error": f"Failed to execute Codex: {str(e)}",
                "mode": mode,
            }

    async def _check_codex_available(self) -> bool:
        """Check if Codex CLI is available"""
        try:
            # Run synchronous subprocess calls in a thread pool to avoid blocking asyncio event loop
            loop = asyncio.get_running_loop()

            # Check for 'codex' command
            result = await loop.run_in_executor(
                None,
                lambda: subprocess.run(
                    ["which", "codex"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                ),
            )

            if result.returncode != 0:
                # If 'codex' not found, check for 'node' as a fallback
                node_result = await loop.run_in_executor(
                    None,
                    lambda: subprocess.run(
                        ["which", "node"],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    ),
                )
                return node_result.returncode == 0
            return True
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
                history_parts.append(
                    f"A: {entry['response'].get('output', entry['response'].get('message', 'Done'))[:200]}..."
                )

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

    async def get_status(self) -> Dict[str, Any]:
        """Get the current status of Codex integration"""
        return {
            "enabled": self.enabled,
            "auto_consult": self.auto_consult,
            "auth_exists": self.auth_path.exists(),
            "codex_available": await self._check_codex_available(),
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
