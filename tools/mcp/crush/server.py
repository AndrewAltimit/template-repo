"""Crush AI Integration MCP Server"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from ..core.base_server import BaseMCPServer
from ..core.utils import setup_logging


class CrushMCPServer(BaseMCPServer):
    """MCP Server for Crush AI integration and code generation"""

    def __init__(self, project_root: Optional[str] = None):
        super().__init__(
            name="Crush MCP Server",
            version="1.0.0",
            port=8015,  # New port for Crush
        )

        self.logger = setup_logging("CrushMCP")
        self.project_root = Path(project_root) if project_root else Path.cwd()

        # Initialize Crush integration
        self.crush_config = self._load_crush_config()
        self.crush = self._initialize_crush()

        # Track auto-consultation status
        self.last_response_uncertainty = None

    def _load_crush_config(self) -> Dict[str, Any]:
        """Load Crush configuration from environment or config file"""
        # Try to load .env file if it exists
        env_file = self.project_root / ".env"
        if env_file.exists():
            try:
                with open(env_file, "r") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            key, value = line.split("=", 1)
                            # Only set if not already in environment
                            if key not in os.environ:
                                os.environ[key] = value
            except Exception as e:
                self.logger.warning(f"Could not load .env file: {e}")

        config = {
            "enabled": os.getenv("CRUSH_ENABLED", "true").lower() == "true",
            "auto_consult": os.getenv("CRUSH_AUTO_CONSULT", "true").lower() == "true",
            "api_key": os.getenv("OPENROUTER_API_KEY", ""),
            "timeout": int(os.getenv("CRUSH_TIMEOUT", "300")),
            "max_prompt_length": int(os.getenv("CRUSH_MAX_PROMPT", "4000")),
            "log_consultations": os.getenv("CRUSH_LOG_CONSULTATIONS", "true").lower() == "true",
            "include_history": os.getenv("CRUSH_INCLUDE_HISTORY", "true").lower() == "true",
            "max_history_entries": int(os.getenv("CRUSH_MAX_HISTORY", "5")),
            "docker_service": "openrouter-agents",
            "container_command": ["crush", "run"],
            "quiet_mode": True,  # Always use quiet mode for non-interactive
        }

        # Try to load from config file
        config_file = self.project_root / "crush-config.json"
        if config_file.exists():
            try:
                with open(config_file, "r") as f:
                    file_config = json.load(f)
                config.update(file_config)
            except Exception as e:
                self.logger.warning(f"Could not load crush-config.json: {e}")

        return config

    def _initialize_crush(self):
        """Initialize Crush integration with lazy loading"""
        try:
            # Add parent directory to path for imports
            parent_dir = Path(__file__).parent.parent.parent.parent
            if str(parent_dir) not in sys.path:
                sys.path.insert(0, str(parent_dir))

            from .crush_integration import get_integration

            return get_integration(self.crush_config)
        except ImportError as e:
            self.logger.error(f"Failed to import Crush integration: {e}")

            # Return a mock object that always returns disabled status
            class MockCrush:
                def __init__(self):
                    self.enabled = False
                    self.auto_consult = False

                async def consult_crush(self, **kwargs):
                    return {
                        "status": "disabled",
                        "error": "Crush integration not available",
                    }

                def clear_conversation_history(self):
                    return {"message": "Crush integration not available"}

                def get_statistics(self):
                    return {}

            return MockCrush()

    def get_tools(self) -> Dict[str, Dict[str, Any]]:
        """Return available Crush tools"""
        return {
            "consult_crush": {
                "description": "Consult Crush AI for quick code generation, explanation, or conversion",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The coding question, task, or code to consult about",
                        },
                        "context": {
                            "type": "string",
                            "description": "Additional context or target language for conversion",
                            "default": "",
                        },
                        "mode": {
                            "type": "string",
                            "enum": ["generate", "explain", "convert", "quick"],
                            "default": "quick",
                            "description": "Consultation mode",
                        },
                        "comparison_mode": {
                            "type": "boolean",
                            "default": True,
                            "description": "Compare with previous Claude response",
                        },
                        "force": {
                            "type": "boolean",
                            "default": False,
                            "description": "Force consultation even if disabled",
                        },
                    },
                    "required": ["query"],
                },
            },
            "clear_crush_history": {
                "description": "Clear Crush conversation history",
                "parameters": {"type": "object", "properties": {}},
            },
            "crush_status": {
                "description": "Get Crush integration status and statistics",
                "parameters": {"type": "object", "properties": {}},
            },
            "toggle_crush_auto_consult": {
                "description": "Toggle automatic Crush consultation on uncertainty detection",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "enable": {
                            "type": "boolean",
                            "description": "Enable or disable auto-consultation",
                        }
                    },
                    "required": [],
                },
            },
        }

    async def consult_crush(
        self,
        query: str,
        context: str = "",
        mode: str = "quick",
        comparison_mode: bool = True,
        force: bool = False,
    ) -> Dict[str, Any]:
        """Consult Crush AI for coding assistance

        Args:
            query: The question, task, or code to consult about
            context: Additional context or target language for conversion
            mode: Consultation mode (generate, explain, convert, quick)
            comparison_mode: Compare with previous Claude response
            force: Force consultation even if disabled

        Returns:
            Dictionary with consultation results
        """
        if not query:
            return {
                "success": False,
                "error": "'query' parameter is required for Crush consultation",
            }

        # Build prompt based on mode
        if mode == "explain":
            prompt = "Explain the following code"
            if context:
                prompt += f", focusing on {context}"
            prompt += f":\n\n```\n{query}\n```"
        elif mode == "convert":
            if not context:
                return {
                    "success": False,
                    "error": "'context' parameter is required for conversion (target language)",
                }
            prompt = f"Convert the following code to {context}:\n\n```\n{query}\n```"
        elif mode == "generate":
            prompt = self._style_prompt(query, "detailed")
        else:  # quick mode
            prompt = self._style_prompt(query, "concise")

        # Consult Crush
        if hasattr(self.crush, "consult_crush"):
            result = await self.crush.consult_crush(
                query=prompt,
                context=context,
                comparison_mode=comparison_mode,
                force_consult=force,
            )
        else:
            # Fallback to generate_response for backward compatibility
            result = await self.crush.generate_response(prompt=prompt)

        # Format the response
        formatted_response = self._format_crush_response(result)

        return {
            "success": result.get("status") == "success",
            "result": formatted_response,
            "raw_result": result,
        }

    async def clear_crush_history(self) -> Dict[str, Any]:
        """Clear Crush conversation history"""
        result = self.crush.clear_conversation_history()
        return {"success": True, "message": result.get("message", "History cleared")}

    async def crush_status(self) -> Dict[str, Any]:
        """Get Crush integration status and statistics"""
        stats = self.crush.get_statistics() if hasattr(self.crush, "get_statistics") else {}

        status_info = {
            "enabled": getattr(self.crush, "enabled", False),
            "auto_consult": getattr(self.crush, "auto_consult", False),
            "timeout": self.crush_config.get("timeout", 300),
            "api_key_configured": bool(self.crush_config.get("api_key")),
            "statistics": stats,
        }

        return {"success": True, "status": status_info}

    async def toggle_crush_auto_consult(self, enable: Optional[bool] = None) -> Dict[str, Any]:
        """Toggle automatic Crush consultation

        Args:
            enable: True to enable, False to disable, None to toggle

        Returns:
            Dictionary with new status
        """
        if enable is None:
            # Toggle current state
            self.crush.auto_consult = not getattr(self.crush, "auto_consult", False)
        else:
            self.crush.auto_consult = bool(enable)

        status = "enabled" if self.crush.auto_consult else "disabled"
        return {
            "success": True,
            "status": status,
            "message": f"Crush auto-consultation is now {status}",
        }

    def _style_prompt(self, prompt: str, style: str) -> str:
        """Adjust prompt based on style preference"""
        if style == "concise":
            return f"{prompt} (be concise)"
        elif style == "detailed":
            return f"{prompt} (provide detailed implementation)"
        elif style == "explained":
            return f"{prompt} (include explanations)"
        return prompt

    def _format_crush_response(self, result: Dict[str, Any]) -> str:
        """Format Crush consultation response"""
        output_lines = []
        output_lines.append("⚡ Crush Consultation Response")
        output_lines.append("=" * 40)
        output_lines.append("")

        if result["status"] == "success":
            output_lines.append(f"✅ Consultation ID: {result.get('consultation_id', result.get('generation_id', 'N/A'))}")
            output_lines.append(f"⏱️  Execution time: {result.get('execution_time', 0):.2f}s")
            output_lines.append("")

            # Display the response
            response = result.get("response", "")
            if response:
                output_lines.append("📄 Response:")
                output_lines.append(response)

        elif result["status"] == "disabled":
            output_lines.append("ℹ️  Crush consultation is currently disabled")
            output_lines.append("💡 Enable with: toggle_crush_auto_consult")

        elif result["status"] == "timeout":
            output_lines.append(f"❌ {result.get('error', 'Timeout error')}")
            output_lines.append("💡 Try a simpler query or increase the timeout")

        else:  # error
            output_lines.append(f"❌ Error: {result.get('error', 'Unknown error')}")
            output_lines.append("")
            output_lines.append("💡 Troubleshooting:")
            output_lines.append("  1. Check if OPENROUTER_API_KEY is set")
            output_lines.append("  2. Verify the openrouter-agents container is running")
            output_lines.append("  3. Check the logs for more details")

        return "\n".join(output_lines)


def main():
    """Run the Crush MCP Server"""
    import argparse

    parser = argparse.ArgumentParser(description="Crush AI Integration MCP Server")
    parser.add_argument(
        "--mode",
        choices=["http", "stdio"],
        default="http",
        help="Server mode (http or stdio)",
    )
    parser.add_argument("--project-root", default=None, help="Project root directory")
    args = parser.parse_args()

    server = CrushMCPServer(project_root=args.project_root)
    server.run(mode=args.mode)


if __name__ == "__main__":
    main()
