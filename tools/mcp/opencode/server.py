"""OpenCode AI Integration MCP Server"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

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
            "api_key": os.getenv("OPENROUTER_API_KEY", ""),
            "model": os.getenv("OPENCODE_MODEL", "qwen/qwen-2.5-coder-32b-instruct"),
            "timeout": int(os.getenv("OPENCODE_TIMEOUT", "300")),
            "max_context_length": int(os.getenv("OPENCODE_MAX_CONTEXT", "8000")),
            "log_generations": os.getenv("OPENCODE_LOG_GENERATIONS", "true").lower() == "true",
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

                async def generate_code(self, **kwargs):
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
            "generate_code": {
                "description": "Generate code using OpenCode AI",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "prompt": {
                            "type": "string",
                            "description": "The coding task or question",
                        },
                        "context": {
                            "type": "string",
                            "description": "Additional context or existing code",
                        },
                        "language": {
                            "type": "string",
                            "description": "Programming language (optional)",
                        },
                        "include_tests": {
                            "type": "boolean",
                            "default": False,
                            "description": "Include unit tests in the generated code",
                        },
                        "plan_mode": {
                            "type": "boolean",
                            "default": False,
                            "description": "Use plan mode for multi-step tasks",
                        },
                    },
                    "required": ["prompt"],
                },
            },
            "refactor_code": {
                "description": "Refactor existing code using OpenCode",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "code": {
                            "type": "string",
                            "description": "The code to refactor",
                        },
                        "instructions": {
                            "type": "string",
                            "description": "Refactoring instructions or goals",
                        },
                        "preserve_functionality": {
                            "type": "boolean",
                            "default": True,
                            "description": "Ensure refactoring preserves functionality",
                        },
                    },
                    "required": ["code", "instructions"],
                },
            },
            "review_code": {
                "description": "Review code and provide feedback",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "code": {
                            "type": "string",
                            "description": "The code to review",
                        },
                        "focus_areas": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Specific areas to focus on (e.g., security, performance)",
                        },
                    },
                    "required": ["code"],
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
        }

    async def generate_code(
        self,
        prompt: str,
        context: str = "",
        language: str = "",
        include_tests: bool = False,
        plan_mode: bool = False,
    ) -> Dict[str, Any]:
        """Generate code using OpenCode AI

        Args:
            prompt: The coding task or question
            context: Additional context or existing code
            language: Programming language (optional)
            include_tests: Include unit tests
            plan_mode: Use plan mode for multi-step tasks

        Returns:
            Dictionary with generation results
        """
        if not prompt:
            return {
                "success": False,
                "error": "'prompt' parameter is required for code generation",
            }

        # Generate code
        result = await self.opencode.generate_code(
            prompt=prompt,
            context=context,
            language=language,
            include_tests=include_tests,
            plan_mode=plan_mode,
        )

        # Format the response
        formatted_response = self._format_opencode_response(result)

        return {
            "success": result.get("status") == "success",
            "result": formatted_response,
            "raw_result": result,
        }

    async def refactor_code(
        self,
        code: str,
        instructions: str,
        preserve_functionality: bool = True,
    ) -> Dict[str, Any]:
        """Refactor existing code

        Args:
            code: The code to refactor
            instructions: Refactoring instructions
            preserve_functionality: Ensure functionality is preserved

        Returns:
            Dictionary with refactored code
        """
        if not code or not instructions:
            return {
                "success": False,
                "error": "Both 'code' and 'instructions' parameters are required",
            }

        # Use generate_code with refactoring prompt
        refactor_prompt = f"""Refactor the following code according to these instructions: {instructions}

{"IMPORTANT: Preserve all existing functionality." if preserve_functionality else ""}

Code to refactor:
```
{code}
```"""

        result = await self.opencode.generate_code(
            prompt=refactor_prompt,
            context=code,
        )

        formatted_response = self._format_opencode_response(result)

        return {
            "success": result.get("status") == "success",
            "result": formatted_response,
            "raw_result": result,
        }

    async def review_code(
        self,
        code: str,
        focus_areas: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Review code and provide feedback

        Args:
            code: The code to review
            focus_areas: Specific areas to focus on

        Returns:
            Dictionary with review feedback
        """
        if not code:
            return {
                "success": False,
                "error": "'code' parameter is required for code review",
            }

        # Build review prompt
        review_prompt = "Please review the following code and provide feedback"
        if focus_areas:
            review_prompt += f" focusing on: {', '.join(focus_areas)}"
        review_prompt += "."

        result = await self.opencode.generate_code(
            prompt=review_prompt,
            context=code,
        )

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
            "model": self.opencode_config.get("model", "unknown"),
            "timeout": self.opencode_config.get("timeout", 300),
            "api_key_configured": bool(self.opencode_config.get("api_key")),
            "statistics": stats,
        }

        return {"success": True, "status": status_info}

    def _format_opencode_response(self, result: Dict[str, Any]) -> str:
        """Format OpenCode generation response"""
        output_lines = []
        output_lines.append("🤖 OpenCode Response")
        output_lines.append("=" * 40)
        output_lines.append("")

        if result["status"] == "success":
            output_lines.append(f"✅ Generation ID: {result.get('generation_id', 'N/A')}")
            output_lines.append(f"⏱️  Execution time: {result.get('execution_time', 0):.2f}s")
            output_lines.append("")

            # Display the generated code or response
            response = result.get("response", "")
            if response:
                output_lines.append("📄 Generated Code:")
                output_lines.append(response)

        elif result["status"] == "disabled":
            output_lines.append("ℹ️  OpenCode integration is currently disabled")
            output_lines.append("💡 Enable by setting OPENCODE_ENABLED=true")

        elif result["status"] == "timeout":
            output_lines.append(f"❌ {result.get('error', 'Timeout error')}")
            output_lines.append("💡 Try increasing the timeout or simplifying the task")

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
