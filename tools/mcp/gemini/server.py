"""Gemini AI Integration MCP Server"""

import asyncio  # noqa: F401
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from ..core.base_server import BaseMCPServer
from ..core.utils import check_container_environment, setup_logging


class GeminiMCPServer(BaseMCPServer):
    """MCP Server for Gemini AI integration and consultation"""

    def __init__(self, project_root: Optional[str] = None):
        # Check if running in container and exit if true
        if check_container_environment():
            print(
                "ERROR: Gemini MCP Server cannot run inside a container!",
                file=sys.stderr,
            )
            print(
                "The Gemini CLI requires Docker access and must run on the host system.",
                file=sys.stderr,
            )
            print("Please launch this server directly on the host with:", file=sys.stderr)
            print("  python -m tools.mcp.gemini.server", file=sys.stderr)
            sys.exit(1)

        super().__init__(
            name="Gemini MCP Server",
            version="1.0.0",
            port=8006,  # Standard Gemini MCP port
        )

        self.logger = setup_logging("GeminiMCP")
        self.project_root = Path(project_root) if project_root else Path.cwd()

        # Initialize Gemini integration
        self.gemini_config = self._load_gemini_config()
        self.gemini = self._initialize_gemini()

        # Track uncertainty for auto-consultation
        self.last_response_uncertainty = None

    def _load_gemini_config(self) -> Dict[str, Any]:
        """Load Gemini configuration from environment or config file"""
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
            "enabled": os.getenv("GEMINI_ENABLED", "true").lower() == "true",
            "auto_consult": os.getenv("GEMINI_AUTO_CONSULT", "true").lower() == "true",
            "cli_command": os.getenv("GEMINI_CLI_COMMAND", "gemini"),
            "timeout": int(os.getenv("GEMINI_TIMEOUT", "60")),
            "rate_limit_delay": float(os.getenv("GEMINI_RATE_LIMIT", "2")),
            "max_context_length": int(os.getenv("GEMINI_MAX_CONTEXT", "4000")),
            "log_consultations": os.getenv("GEMINI_LOG_CONSULTATIONS", "true").lower() == "true",
            "model": os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
            "sandbox_mode": os.getenv("GEMINI_SANDBOX", "false").lower() == "true",
            "debug_mode": os.getenv("GEMINI_DEBUG", "false").lower() == "true",
            "include_history": os.getenv("GEMINI_INCLUDE_HISTORY", "true").lower() == "true",
            "max_history_entries": int(os.getenv("GEMINI_MAX_HISTORY", "10")),
        }

        # Try to load from config file
        config_file = self.project_root / "gemini-config.json"
        if config_file.exists():
            try:
                with open(config_file, "r") as f:
                    file_config = json.load(f)
                config.update(file_config)
            except Exception as e:
                self.logger.warning(f"Could not load gemini-config.json: {e}")

        return config

    def _initialize_gemini(self):
        """Initialize Gemini integration with lazy loading"""
        try:
            # Add parent directory to path for imports
            parent_dir = Path(__file__).parent.parent.parent.parent
            if str(parent_dir) not in sys.path:
                sys.path.insert(0, str(parent_dir))

            from .gemini_integration import get_integration

            return get_integration(self.gemini_config)
        except ImportError as e:
            self.logger.error(f"Failed to import Gemini integration: {e}")

            # Return a mock object that always returns disabled status
            class MockGemini:
                def __init__(self):
                    self.auto_consult = False
                    self.enabled = False

                async def consult_gemini(self, **kwargs):
                    return {
                        "status": "disabled",
                        "error": "Gemini integration not available",
                    }

                def clear_conversation_history(self):
                    return {"message": "Gemini integration not available"}

                def get_statistics(self):
                    return {}

            return MockGemini()

    def get_tools(self) -> Dict[str, Dict[str, Any]]:
        """Return available Gemini tools"""
        return {
            "consult_gemini": {
                "description": "Consult Gemini AI for a second opinion or validation",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The question or code to consult Gemini about",
                        },
                        "context": {
                            "type": "string",
                            "description": "Additional context for the consultation",
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
            "clear_gemini_history": {
                "description": "Clear Gemini conversation history",
                "parameters": {"type": "object", "properties": {}},
            },
            "gemini_status": {
                "description": "Get Gemini integration status and statistics",
                "parameters": {"type": "object", "properties": {}},
            },
            "toggle_gemini_auto_consult": {
                "description": "Toggle automatic Gemini consultation on uncertainty detection",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "enable": {
                            "type": "boolean",
                            "description": "Enable or disable auto-consultation",
                        }
                    },
                },
            },
        }

    async def consult_gemini(
        self,
        query: str,
        context: str = "",
        comparison_mode: bool = True,
        force: bool = False,
    ) -> Dict[str, Any]:
        """Consult Gemini AI for a second opinion

        Args:
            query: The question or code to consult about
            context: Additional context
            comparison_mode: Compare with previous Claude response
            force: Force consultation even if disabled

        Returns:
            Dictionary with consultation results
        """
        if not query:
            return {
                "success": False,
                "error": "'query' parameter is required for Gemini consultation",
            }

        # Consult Gemini
        result = await self.gemini.consult_gemini(
            query=query,
            context=context,
            comparison_mode=comparison_mode,
            force_consult=force,
        )

        # Format the response
        formatted_response = self._format_gemini_response(result)

        return {
            "success": result.get("status") == "success",
            "result": formatted_response,
            "raw_result": result,
        }

    async def clear_gemini_history(self) -> Dict[str, Any]:
        """Clear Gemini conversation history"""
        result = self.gemini.clear_conversation_history()
        return {"success": True, "message": result.get("message", "History cleared")}

    async def gemini_status(self) -> Dict[str, Any]:
        """Get Gemini integration status and statistics"""
        stats = self.gemini.get_statistics() if hasattr(self.gemini, "get_statistics") else {}

        status_info = {
            "enabled": getattr(self.gemini, "enabled", False),
            "auto_consult": getattr(self.gemini, "auto_consult", False),
            "model": self.gemini_config.get("model", "unknown"),
            "timeout": self.gemini_config.get("timeout", 60),
            "statistics": stats,
        }

        return {"success": True, "status": status_info}

    async def toggle_gemini_auto_consult(self, enable: Optional[bool] = None) -> Dict[str, Any]:
        """Toggle automatic Gemini consultation

        Args:
            enable: True to enable, False to disable, None to toggle

        Returns:
            Dictionary with new status
        """
        if enable is None:
            # Toggle current state
            self.gemini.auto_consult = not getattr(self.gemini, "auto_consult", False)
        else:
            self.gemini.auto_consult = bool(enable)

        status = "enabled" if self.gemini.auto_consult else "disabled"
        return {
            "success": True,
            "status": status,
            "message": f"Gemini auto-consultation is now {status}",
        }

    def _format_gemini_response(self, result: Dict[str, Any]) -> str:
        """Format Gemini consultation response"""
        output_lines = []
        output_lines.append("🤖 Gemini Consultation Response")
        output_lines.append("=" * 40)
        output_lines.append("")

        if result["status"] == "success":
            output_lines.append(f"✅ Consultation ID: {result.get('consultation_id', 'N/A')}")
            output_lines.append(f"⏱️  Execution time: {result.get('execution_time', 0):.2f}s")
            output_lines.append("")

            # Display the raw response
            response = result.get("response", "")
            if response:
                output_lines.append("📄 Response:")
                output_lines.append(response)

        elif result["status"] == "disabled":
            output_lines.append("ℹ️  Gemini consultation is currently disabled")
            output_lines.append("💡 Enable with: toggle_gemini_auto_consult")

        elif result["status"] == "timeout":
            output_lines.append(f"❌ {result.get('error', 'Timeout error')}")
            output_lines.append("💡 Try increasing the timeout or simplifying the query")

        else:  # error
            output_lines.append(f"❌ Error: {result.get('error', 'Unknown error')}")
            output_lines.append("")
            output_lines.append("💡 Troubleshooting:")
            output_lines.append("  1. Check if Gemini CLI is installed and in PATH")
            output_lines.append("  2. Verify Gemini CLI authentication")
            output_lines.append("  3. Check the logs for more details")

        return "\n".join(output_lines)

    # Remove the custom run_stdio method to use the base class implementation
    # The base class will automatically handle tool registration and stdio mode


def main():
    """Run the Gemini MCP Server"""
    import argparse

    parser = argparse.ArgumentParser(description="Gemini AI Integration MCP Server")
    parser.add_argument(
        "--mode",
        choices=["http", "stdio"],
        default="stdio",  # Default to stdio for Gemini
        help="Server mode (http or stdio)",
    )
    parser.add_argument("--project-root", default=None, help="Project root directory")
    args = parser.parse_args()

    server = GeminiMCPServer(project_root=args.project_root)
    server.run(mode=args.mode)


if __name__ == "__main__":
    main()
