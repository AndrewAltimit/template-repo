"""Code Quality MCP Server - Format checking and linting tools"""

import subprocess
from typing import Any, Dict, List, Optional  # noqa: F401

from ..core.base_server import BaseMCPServer
from ..core.utils import setup_logging


class CodeQualityMCPServer(BaseMCPServer):
    """MCP Server for code quality tools - formatting and linting"""

    def __init__(self):
        super().__init__(
            name="Code Quality MCP Server",
            version="1.0.0",
            port=8010,  # New port for code quality server
        )
        self.logger = setup_logging("CodeQualityMCP")

    def get_tools(self) -> Dict[str, Dict[str, Any]]:
        """Return available code quality tools"""
        return {
            "format_check": {
                "description": "Check code formatting for various languages",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path to file or directory to check",
                        },
                        "language": {
                            "type": "string",
                            "enum": [
                                "python",
                                "javascript",
                                "typescript",
                                "go",
                                "rust",
                            ],
                            "default": "python",
                            "description": "Programming language",
                        },
                    },
                    "required": ["path"],
                },
            },
            "lint": {
                "description": "Run code linting with optional configuration",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path to file or directory to lint",
                        },
                        "config": {
                            "type": "string",
                            "description": "Path to linting configuration file",
                        },
                        "linter": {
                            "type": "string",
                            "enum": ["flake8", "pylint", "eslint", "golint", "clippy"],
                            "default": "flake8",
                            "description": "Linter to use",
                        },
                    },
                    "required": ["path"],
                },
            },
            "autoformat": {
                "description": "Automatically format code files",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path to file or directory to format",
                        },
                        "language": {
                            "type": "string",
                            "enum": [
                                "python",
                                "javascript",
                                "typescript",
                                "go",
                                "rust",
                            ],
                            "default": "python",
                            "description": "Programming language",
                        },
                    },
                    "required": ["path"],
                },
            },
            "hello_world": {
                "description": "Simple hello world tool for testing",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
        }

    async def format_check(self, path: str, language: str = "python") -> Dict[str, Any]:
        """Check code formatting for various languages

        Args:
            path: Path to file or directory to check
            language: Programming language (python, javascript, typescript, go, rust)

        Returns:
            Dictionary with formatting status and any issues found
        """
        formatters = {
            "python": ["black", "--check", path],
            "javascript": ["prettier", "--check", path],
            "typescript": ["prettier", "--check", path],
            "go": ["gofmt", "-l", path],
            "rust": ["rustfmt", "--check", path],
        }

        if language not in formatters:
            return {
                "success": False,
                "error": f"Unsupported language: {language}",
                "supported_languages": list(formatters.keys()),
            }

        try:
            self.logger.info(f"Checking {language} formatting for: {path}")
            result = subprocess.run(
                formatters[language], capture_output=True, text=True, check=False
            )

            return {
                "success": True,
                "formatted": result.returncode == 0,
                "output": result.stdout or result.stderr,
                "command": " ".join(formatters[language]),
            }
        except FileNotFoundError:
            return {
                "success": False,
                "error": f"{formatters[language][0]} not found. Please install it first.",
            }
        except Exception as e:
            self.logger.error(f"Format check error: {str(e)}")
            return {"success": False, "error": str(e)}

    async def lint(
        self, path: str, config: Optional[str] = None, linter: str = "flake8"
    ) -> Dict[str, Any]:
        """Run code linting with various linters

        Args:
            path: Path to file or directory to lint
            config: Optional path to linting configuration file
            linter: Linter to use (flake8, pylint, eslint, golint, clippy)

        Returns:
            Dictionary with linting results and any issues found
        """
        # Build linter command based on type
        linter_commands = {
            "flake8": ["flake8"],
            "pylint": ["pylint"],
            "eslint": ["eslint"],
            "golint": ["golint"],
            "clippy": ["cargo", "clippy"],
        }

        if linter not in linter_commands:
            return {
                "success": False,
                "error": f"Unsupported linter: {linter}",
                "supported_linters": list(linter_commands.keys()),
            }

        cmd = linter_commands[linter] + [path]

        # Add config file if provided
        if config:
            if linter == "flake8":
                cmd.extend(["--config", config])
            elif linter == "pylint":
                cmd.extend(["--rcfile", config])
            elif linter == "eslint":
                cmd.extend(["--config", config])

        try:
            self.logger.info(f"Running {linter} on: {path}")
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)

            # Parse output based on linter type
            issues = []
            if result.stdout:
                issues = result.stdout.splitlines()

            return {
                "success": True,
                "passed": result.returncode == 0,
                "issues": issues,
                "issue_count": len(issues),
                "command": " ".join(cmd),
            }
        except FileNotFoundError:
            return {
                "success": False,
                "error": f"{linter} not found. Please install it first.",
            }
        except Exception as e:
            self.logger.error(f"Linting error: {str(e)}")
            return {"success": False, "error": str(e)}

    async def autoformat(self, path: str, language: str = "python") -> Dict[str, Any]:
        """Automatically format code files

        Args:
            path: Path to file or directory to format
            language: Programming language

        Returns:
            Dictionary with formatting results
        """
        formatters = {
            "python": ["black", path],
            "javascript": ["prettier", "--write", path],
            "typescript": ["prettier", "--write", path],
            "go": ["gofmt", "-w", path],
            "rust": ["rustfmt", path],
        }

        if language not in formatters:
            return {
                "success": False,
                "error": f"Unsupported language: {language}",
                "supported_languages": list(formatters.keys()),
            }

        try:
            self.logger.info(f"Auto-formatting {language} code in: {path}")
            result = subprocess.run(
                formatters[language], capture_output=True, text=True, check=False
            )

            return {
                "success": result.returncode == 0,
                "formatted": True,
                "output": result.stdout or result.stderr,
                "command": " ".join(formatters[language]),
            }
        except FileNotFoundError:
            return {
                "success": False,
                "error": f"{formatters[language][0]} not found. Please install it first.",
            }
        except Exception as e:
            self.logger.error(f"Auto-format error: {str(e)}")
            return {"success": False, "error": str(e)}

    async def hello_world(self) -> Dict[str, Any]:
        """Simple hello world tool for testing

        Returns:
            Dictionary with hello world message
        """
        try:
            self.logger.info("Executing hello_world tool")
            return {
                "success": True,
                "message": "Hello, World!",
            }
        except Exception as e:
            self.logger.error(f"Hello world error: {str(e)}")
            return {"success": False, "error": str(e)}


def main():
    """Run the Code Quality MCP Server"""
    import argparse

    parser = argparse.ArgumentParser(description="Code Quality MCP Server")
    parser.add_argument(
        "--mode",
        choices=["http", "stdio"],
        default="http",
        help="Server mode (http or stdio)",
    )
    args = parser.parse_args()

    server = CodeQualityMCPServer()
    server.run(mode=args.mode)


if __name__ == "__main__":
    main()
