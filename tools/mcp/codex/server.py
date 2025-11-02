"""Codex AI Integration MCP Server"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv

from ..core.base_server import BaseMCPServer
from ..core.utils import setup_logging

# Load environment variables from .env file
load_dotenv()


class CodexMCPServer(BaseMCPServer):
    """MCP Server for Codex AI integration and code generation"""

    def __init__(self, project_root: Optional[str] = None):
        super().__init__(
            name="Codex MCP Server",
            version="1.0.0",
            port=8021,  # New port for Codex
        )

        self.logger = setup_logging("CodexMCP")
        self.project_root = Path(project_root) if project_root else Path.cwd()

        # Initialize Codex integration
        self.codex_config = self._load_codex_config()
        self.codex = self._initialize_codex()

        # Track auto-consultation status
        self.last_response_uncertainty = None

    def _load_codex_config(self) -> Dict[str, Any]:
        """Load Codex configuration from environment or config file"""
        config = {
            "enabled": os.getenv("CODEX_ENABLED", "true").lower() == "true",
            "auto_consult": os.getenv("CODEX_AUTO_CONSULT", "true").lower() == "true",
            "auth_path": os.getenv("CODEX_AUTH_PATH", str(Path.home() / ".codex" / "auth.json")),
            "timeout": int(os.getenv("CODEX_TIMEOUT", "300")),
            "max_context_length": int(os.getenv("CODEX_MAX_CONTEXT", "8000")),
            "log_consultations": os.getenv("CODEX_LOG_CONSULTATIONS", "true").lower() == "true",
            "include_history": os.getenv("CODEX_INCLUDE_HISTORY", "true").lower() == "true",
            "max_history_entries": int(os.getenv("CODEX_MAX_HISTORY", "5")),
            "docker_service": "codex-agent",
            "container_command": ["codex"],
        }

        # Try to load from config file
        config_file = self.project_root / "codex-config.json"
        if config_file.exists():
            try:
                with open(config_file, "r", encoding="utf-8") as f:
                    file_config = json.load(f)
                config.update(file_config)
            except Exception as e:
                self.logger.warning("Could not load codex-config.json: %s", e)

        return config

    def _initialize_codex(self):
        """Initialize Codex integration with lazy loading"""
        try:
            # Add parent directory to path for imports
            parent_dir = Path(__file__).parent.parent.parent.parent
            if str(parent_dir) not in sys.path:
                sys.path.insert(0, str(parent_dir))

            from .codex_integration import get_integration

            return get_integration(self.codex_config)
        except ImportError as e:
            self.logger.error("Failed to import Codex integration: %s", e)

            # Return a mock object that always returns disabled status
            class MockCodex:
                def __init__(self):
                    self.enabled = False
                    self.auto_consult = False

                async def consult_codex(self, **kwargs):
                    return {
                        "status": "disabled",
                        "error": "Codex integration not available",
                    }

                async def clear_history(self):
                    return {"status": "disabled"}

                async def get_status(self):
                    return {
                        "enabled": False,
                        "auto_consult": False,
                        "error": "Integration not available",
                    }

                def toggle_auto_consult(self, enable: Optional[bool] = None):
                    return {"enabled": False, "error": "Integration not available"}

            return MockCodex()

    async def consult_codex(
        self,
        query: str,
        context: str = "",
        mode: str = "quick",
        comparison_mode: bool = True,
        force: bool = False,
    ) -> Dict[str, Any]:
        """Consult Codex for code generation or assistance"""
        try:
            if not self.codex_config["enabled"] and not force:
                return {
                    "status": "disabled",
                    "message": "Codex consultation is disabled. Use 'force=true' to override.",
                }

            # Check for auth
            auth_path = Path(self.codex_config["auth_path"])
            if not auth_path.exists():
                return {
                    "status": "error",
                    "error": f"Codex authentication not found at {auth_path}. Please run 'codex auth' first.",
                }

            result = await self.codex.consult_codex(
                query=query,
                context=context,
                mode=mode,
                comparison_mode=comparison_mode,
            )

            # Log consultation if enabled
            if self.codex_config["log_consultations"]:
                self.logger.info(f"Codex consultation: mode={mode}, query_length={len(query)}")
                self.logger.info("Codex result: %s", result)

            return result  # type: ignore[no-any-return]
        except Exception as e:
            self.logger.error("Codex consultation failed: %s", e)
            return {"status": "error", "error": str(e)}

    async def clear_codex_history(self) -> Dict[str, Any]:
        """Clear the Codex conversation history"""
        try:
            result = await self.codex.clear_history()
            self.logger.info("Codex history cleared")
            return result  # type: ignore[no-any-return]
        except Exception as e:
            self.logger.error("Failed to clear Codex history: %s", e)
            return {"status": "error", "error": str(e)}

    async def codex_status(self) -> Dict[str, Any]:
        """Get the current status of Codex integration"""
        try:
            status = await self.codex.get_status()
            status.update(
                {
                    "config": {
                        "enabled": self.codex_config["enabled"],
                        "auto_consult": self.codex_config["auto_consult"],
                        "auth_exists": Path(self.codex_config["auth_path"]).exists(),
                        "timeout": self.codex_config["timeout"],
                        "max_context": self.codex_config["max_context_length"],
                    }
                }
            )
            return status  # type: ignore[no-any-return]
        except Exception as e:
            self.logger.error("Failed to get Codex status: %s", e)
            return {"status": "error", "error": str(e)}

    async def toggle_codex_auto_consult(self, enable: Optional[bool] = None) -> Dict[str, Any]:
        """Toggle automatic Codex consultation"""
        try:
            result = self.codex.toggle_auto_consult(enable)
            self.codex_config["auto_consult"] = result.get("enabled", False)
            self.logger.info("Codex auto-consult toggled: %s", result)
            return result  # type: ignore[no-any-return]
        except Exception as e:
            self.logger.error("Failed to toggle Codex auto-consult: %s", e)
            return {"status": "error", "error": str(e)}

    def get_tools(self) -> Dict[str, Dict[str, Any]]:
        """Return dictionary of available tools and their metadata"""
        return {
            "consult_codex": {
                "description": "Consult Codex AI for code generation, completion, or refactoring",
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
                            "enum": ["generate", "complete", "refactor", "explain", "quick"],
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
            "clear_codex_history": {
                "description": "Clear Codex conversation history",
                "parameters": {"type": "object", "properties": {}},
            },
            "codex_status": {
                "description": "Get Codex integration status and statistics",
                "parameters": {"type": "object", "properties": {}},
            },
            "toggle_codex_auto_consult": {
                "description": "Toggle automatic Codex consultation on uncertainty detection",
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


def main():
    """Main entry point for the server"""
    import argparse

    parser = argparse.ArgumentParser(description="Codex MCP Server")
    parser.add_argument(
        "--mode",
        choices=["stdio", "http"],
        default="stdio",
        help="Server mode (stdio or http)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8021,
        help="Port for HTTP mode (default: 8021)",
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host for HTTP mode (default: 0.0.0.0)",
    )
    args = parser.parse_args()

    server = CodexMCPServer()
    server.port = args.port

    # Use the base server's run method which handles mode switching correctly
    server.run(mode=args.mode)


if __name__ == "__main__":
    main()
