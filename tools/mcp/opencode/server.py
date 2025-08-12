"""OpenCode AI Integration MCP Server"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from ..core.base_server import BaseMCPServer
from ..core.utils import setup_logging


class OpenCodeMCPServer(BaseMCPServer):
    """MCP Server for OpenCode AI integration and code generation"""

    def __init__(self, project_root: Optional[str] = None):
        super().__init__(
            name="OpenCode MCP Server",
            version="1.0.0",
            port=8014,  # New port for OpenCode
        )

        self.logger = setup_logging("OpenCodeMCP")
        self.project_root = Path(project_root) if project_root else Path.cwd()

        # Initialize OpenCode integration
        self.opencode_config = self._load_opencode_config()
        self.opencode = self._initialize_opencode()

        # Track auto-consultation status
        self.last_response_uncertainty = None

    def _load_opencode_config(self) -> Dict[str, Any]:
        """Load OpenCode configuration from environment or config file"""
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
            "enabled": os.getenv("OPENCODE_ENABLED", "true").lower() == "true",
            "auto_consult": os.getenv("OPENCODE_AUTO_CONSULT", "true").lower() == "true",
            "api_key": os.getenv("OPENROUTER_API_KEY", ""),
            "model": os.getenv("OPENCODE_MODEL", "qwen/qwen-2.5-coder-32b-instruct"),
            "timeout": int(os.getenv("OPENCODE_TIMEOUT", "300")),
            "max_context_length": int(os.getenv("OPENCODE_MAX_CONTEXT", "8000")),
            "log_consultations": os.getenv("OPENCODE_LOG_CONSULTATIONS", "true").lower() == "true",
            "include_history": os.getenv("OPENCODE_INCLUDE_HISTORY", "true").lower() == "true",
            "max_history_entries": int(os.getenv("OPENCODE_MAX_HISTORY", "5")),
            "docker_service": "openrouter-agents",
            "container_command": ["opencode", "run"],
        }

        # Try to load from config file
        config_file = self.project_root / "opencode-config.json"
        if config_file.exists():
            try:
                with open(config_file, "r") as f:
                    file_config = json.load(f)
                config.update(file_config)
            except Exception as e:
                self.logger.warning(f"Could not load opencode-config.json: {e}")

        return config

    def _initialize_opencode(self):
        """Initialize OpenCode integration with lazy loading"""
        try:
            # Add parent directory to path for imports
            parent_dir = Path(__file__).parent.parent.parent.parent
            if str(parent_dir) not in sys.path:
                sys.path.insert(0, str(parent_dir))

            from .opencode_integration import get_integration

            return get_integration(self.opencode_config)
        except ImportError as e:
            self.logger.error(f"Failed to import OpenCode integration: {e}")

            # Return a mock object that always returns disabled status
            class MockOpenCode:
                def __init__(self):
                    self.enabled = False
                    self.auto_consult = False

                async def consult_opencode(self, **kwargs):
                    return {
                        "status": "disabled",
                        "error": "OpenCode integration not available",
                    }

                def clear_conversation_history(self):
                    return {"message": "OpenCode integration not available"}

                def get_statistics(self):
                    return {}

            return MockOpenCode()

    def get_tools(self) -> Dict[str, Dict[str, Any]]:
        """Return available OpenCode tools"""
        return {
            "consult_opencode": {
                "description": "Consult OpenCode AI for code generation, refactoring, or review",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The coding question, task, or code to consult about",
                        },
                        "context": {
                            "type": "string",
                            "description": "Additional context or existing code",
                            "default": "",
                        },
                        "mode": {
                            "type": "string",
                            "enum": ["generate", "refactor", "review", "explain", "quick"],
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
            "clear_opencode_history": {
                "description": "Clear OpenCode conversation history",
                "parameters": {"type": "object", "properties": {}},
            },
            "opencode_status": {
                "description": "Get OpenCode integration status and statistics",
                "parameters": {"type": "object", "properties": {}},
            },
            "toggle_opencode_auto_consult": {
                "description": "Toggle automatic OpenCode consultation on uncertainty detection",
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

    async def consult_opencode(
        self,
        query: str,
        context: str = "",
        mode: str = "quick",
        comparison_mode: bool = True,
        force: bool = False,
    ) -> Dict[str, Any]:
        """Consult OpenCode AI for coding assistance

        Args:
            query: The question, task, or code to consult about
            context: Additional context
            mode: Consultation mode (generate, refactor, review, explain, quick)
            comparison_mode: Compare with previous Claude response
            force: Force consultation even if disabled

        Returns:
            Dictionary with consultation results
        """
        if not query:
            return {
                "success": False,
                "error": "'query' parameter is required for OpenCode consultation",
            }

        # Build prompt based on mode
        if mode == "refactor":
            prompt = f"Refactor the following code: {query}"
            if context:
                prompt += f"\n\nInstructions: {context}"
        elif mode == "review":
            prompt = f"Review the following code and provide feedback: {query}"
            if context:
                prompt += f"\n\nFocus areas: {context}"
        elif mode == "explain":
            prompt = f"Explain the following code: {query}"
            if context:
                prompt += f"\n\nSpecific focus: {context}"
        elif mode == "generate":
            prompt = query
            if context:
                prompt += f"\n\nContext: {context}"
        else:  # quick mode (default)
            # Quick mode handles general queries without specific formatting
            prompt = query
            if context:
                prompt += f"\n\nContext: {context}"

        # Consult OpenCode
        if hasattr(self.opencode, "consult_opencode"):
            result = await self.opencode.consult_opencode(
                query=prompt,
                context=context,
                comparison_mode=comparison_mode,
                force_consult=force,
            )
        else:
            # Fallback to generate_code for backward compatibility
            result = await self.opencode.generate_code(
                prompt=prompt,
                context=context,
            )

        # Format the response
        formatted_response = self._format_opencode_response(result)

        return {
            "success": result.get("status") == "success",
            "result": formatted_response,
            "raw_result": result,
        }

    async def clear_opencode_history(self) -> Dict[str, Any]:
        """Clear OpenCode conversation history"""
        result = self.opencode.clear_conversation_history()
        return {"success": True, "message": result.get("message", "History cleared")}

    async def opencode_status(self) -> Dict[str, Any]:
        """Get OpenCode integration status and statistics"""
        stats = self.opencode.get_statistics() if hasattr(self.opencode, "get_statistics") else {}

        status_info = {
            "enabled": getattr(self.opencode, "enabled", False),
            "auto_consult": getattr(self.opencode, "auto_consult", False),
            "model": self.opencode_config.get("model", "unknown"),
            "timeout": self.opencode_config.get("timeout", 300),
            "api_key_configured": bool(self.opencode_config.get("api_key")),
            "statistics": stats,
        }

        return {"success": True, "status": status_info}

    async def toggle_opencode_auto_consult(self, enable: Optional[bool] = None) -> Dict[str, Any]:
        """Toggle automatic OpenCode consultation

        Args:
            enable: True to enable, False to disable, None to toggle

        Returns:
            Dictionary with new status
        """
        if enable is None:
            # Toggle current state
            self.opencode.auto_consult = not getattr(self.opencode, "auto_consult", False)
        else:
            self.opencode.auto_consult = bool(enable)

        status = "enabled" if self.opencode.auto_consult else "disabled"
        return {
            "success": True,
            "status": status,
            "message": f"OpenCode auto-consultation is now {status}",
        }

    def _format_opencode_response(self, result: Dict[str, Any]) -> str:
        """Format OpenCode consultation response"""
        output_lines = []
        output_lines.append("🤖 OpenCode Consultation Response")
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
            output_lines.append("ℹ️  OpenCode consultation is currently disabled")
            output_lines.append("💡 Enable with: toggle_opencode_auto_consult")

        elif result["status"] == "timeout":
            output_lines.append(f"❌ {result.get('error', 'Timeout error')}")
            output_lines.append("💡 Try increasing the timeout or simplifying the query")

        else:  # error
            output_lines.append(f"❌ Error: {result.get('error', 'Unknown error')}")
            output_lines.append("")
            output_lines.append("💡 Troubleshooting:")
            output_lines.append("  1. Check if OPENROUTER_API_KEY is set")
            output_lines.append("  2. Verify the openrouter-agents container is running")
            output_lines.append("  3. Check the logs for more details")

        return "\n".join(output_lines)


def main():
    """Run the OpenCode MCP Server"""
    import argparse

    parser = argparse.ArgumentParser(description="OpenCode AI Integration MCP Server")
    parser.add_argument(
        "--mode",
        choices=["http", "stdio"],
        default="http",
        help="Server mode (http or stdio)",
    )
    parser.add_argument("--project-root", default=None, help="Project root directory")
    args = parser.parse_args()

    server = OpenCodeMCPServer(project_root=args.project_root)
    server.run(mode=args.mode)


if __name__ == "__main__":
    main()
