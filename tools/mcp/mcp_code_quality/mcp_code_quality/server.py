"""
Code Quality MCP Server - Enterprise Security Boundary for CI/CD Operations

This MCP server provides a controlled interface for code quality operations,
designed for enterprise environments where agents cannot have direct shell access.

Instead of granting unrestricted shell permissions, this server provides:
- Path validation (only approved directories)
- Tool allowlist (only approved operations)
- Timeout enforcement (no hanging processes)
- Audit logging (all operations recorded)
- Rate limiting (DoS protection)

Usage:
    # STDIO mode (for Claude Code)
    python -m mcp_code_quality.server --mode stdio

    # HTTP mode (for remote access)
    python -m mcp_code_quality.server --mode http --port 8010
"""

from collections import defaultdict
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import subprocess
import time
from typing import Any, Dict, List, Optional

from mcp_core.base_server import BaseMCPServer

# Try to import markdown link checker, but make it optional
try:
    from tools.cli.utilities.markdown_link_checker import MarkdownLinkChecker

    MARKDOWN_CHECKER_AVAILABLE = True
except ImportError:
    MARKDOWN_CHECKER_AVAILABLE = False

logger = logging.getLogger(__name__)

# Default timeout for subprocess operations (10 minutes)
DEFAULT_TIMEOUT = 600

# Rate limiting configuration (generous for trusted environments)
RATE_LIMITS = {
    "format_check": {"calls": 100, "period": 60},  # 100 calls per minute
    "lint": {"calls": 50, "period": 60},  # 50 calls per minute
    "autoformat": {"calls": 50, "period": 60},  # 50 calls per minute
    "run_tests": {"calls": 20, "period": 60},  # 20 calls per minute
    "type_check": {"calls": 30, "period": 60},  # 30 calls per minute
    "security_scan": {"calls": 20, "period": 60},  # 20 calls per minute
    "audit_dependencies": {"calls": 10, "period": 60},  # 10 calls per minute
    "check_markdown_links": {"calls": 20, "period": 60},  # 20 calls per minute
}


class CodeQualityMCPServer(BaseMCPServer):
    """
    MCP Server for code quality operations with enterprise security features.

    Provides a controlled security boundary for CI/CD operations:
    - Format checking and auto-formatting
    - Linting with multiple tools
    - Test execution with pytest
    - Type checking with ty (Astral's fast type checker)
    - Security scanning with bandit
    - Dependency vulnerability auditing
    - Markdown link checking

    Security features:
    - Path allowlist validation
    - Operation audit logging
    - Subprocess timeout enforcement
    - Rate limiting per operation
    """

    def __init__(self, port: int = 8010):
        """
        Initialize the Code Quality MCP Server.

        Args:
            port: HTTP port for server (default: 8010)
        """
        super().__init__(
            name="Code Quality MCP Server",
            version="2.0.0",
            port=port,
        )

        # Configuration from environment
        self.timeout = int(os.getenv("MCP_CODE_QUALITY_TIMEOUT", str(DEFAULT_TIMEOUT)))
        self.allowed_paths = self._parse_allowed_paths()
        self.audit_log_path = Path(os.getenv("MCP_CODE_QUALITY_AUDIT_LOG", "/var/log/mcp-code-quality/audit.log"))
        self.rate_limiting_enabled = os.getenv("MCP_CODE_QUALITY_RATE_LIMIT", "true").lower() == "true"

        # Rate limiting state
        self._rate_limit_tracker: Dict[str, List[float]] = defaultdict(list)

        # Markdown link checker (lazy init)
        self._link_checker: Optional[Any] = None

        # Ensure audit log directory exists
        self._init_audit_log()

        logger.info(
            "CodeQualityMCPServer initialized: timeout=%ds, allowed_paths=%s, audit_log=%s",
            self.timeout,
            self.allowed_paths,
            self.audit_log_path,
        )

    def _parse_allowed_paths(self) -> List[str]:
        """Parse allowed paths from environment variable."""
        default_paths = "/workspace,/app,/home"
        paths_str = os.getenv("MCP_CODE_QUALITY_ALLOWED_PATHS", default_paths)
        return [p.strip() for p in paths_str.split(",") if p.strip()]

    def _init_audit_log(self) -> None:
        """Initialize audit log file and directory."""
        try:
            self.audit_log_path.parent.mkdir(parents=True, exist_ok=True)
            # Test write access
            if not self.audit_log_path.exists():
                self.audit_log_path.touch()
        except (PermissionError, OSError) as e:
            # Fall back to temp directory if configured path is not writable
            fallback_path = Path("/tmp/mcp-code-quality-audit.log")
            logger.warning("Cannot write to %s (%s), falling back to %s", self.audit_log_path, e, fallback_path)
            self.audit_log_path = fallback_path
            try:
                self.audit_log_path.touch()
            except (PermissionError, OSError):
                logger.error("Cannot create audit log at fallback path either")

    def _validate_path(self, path: str) -> bool:
        """
        Validate that a path is within allowed directories.

        Args:
            path: Path to validate

        Returns:
            True if path is allowed, False otherwise
        """
        try:
            resolved = Path(path).resolve()

            for allowed in self.allowed_paths:
                allowed_path = Path(allowed).resolve()
                # Use is_relative_to for proper path containment check
                # (avoids prefix matching vulnerability, e.g., /app/data vs /app/database)
                if resolved.is_relative_to(allowed_path):
                    return True

            return False
        except (ValueError, OSError):
            return False

    def _check_rate_limit(self, operation: str) -> bool:
        """
        Check if operation is within rate limits.

        Args:
            operation: Name of the operation

        Returns:
            True if within limits, False if rate limited
        """
        if not self.rate_limiting_enabled:
            return True

        limits = RATE_LIMITS.get(operation, {"calls": 100, "period": 60})
        now = time.time()
        window_start = now - limits["period"]

        # Clean old entries
        self._rate_limit_tracker[operation] = [t for t in self._rate_limit_tracker[operation] if t > window_start]

        # Check limit
        if len(self._rate_limit_tracker[operation]) >= limits["calls"]:
            return False

        # Record this call
        self._rate_limit_tracker[operation].append(now)
        return True

    def _audit_log(self, operation: str, path: str, success: bool, details: Optional[Dict[str, Any]] = None) -> None:
        """
        Log an operation to the audit log.

        Args:
            operation: Name of the operation
            path: Path that was operated on
            success: Whether the operation succeeded
            details: Additional details to log
        """
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
            "operation": operation,
            "path": path,
            "success": success,
            "details": details or {},
        }

        try:
            with open(self.audit_log_path, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except (PermissionError, OSError) as e:
            logger.warning("Failed to write audit log: %s", e)

    def _run_subprocess(
        self,
        command: List[str],
        timeout: Optional[int] = None,
        cwd: Optional[str] = None,
    ) -> subprocess.CompletedProcess:
        """
        Run a subprocess with timeout and safety measures.

        Args:
            command: Command and arguments as list
            timeout: Timeout in seconds (defaults to self.timeout)
            cwd: Working directory

        Returns:
            CompletedProcess result

        Raises:
            subprocess.TimeoutExpired: If command times out
            FileNotFoundError: If command not found
        """
        effective_timeout = timeout or self.timeout

        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=effective_timeout,
            check=False,
            cwd=cwd,
        )

    def get_tools(self) -> Dict[str, Dict[str, Any]]:
        """Return available code quality tools with JSON schema definitions."""
        tools = {
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
                            "enum": ["python", "javascript", "typescript", "go", "rust"],
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
                            "enum": ["flake8", "ruff", "eslint", "golint", "clippy"],
                            "default": "ruff",
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
                            "enum": ["python", "javascript", "typescript", "go", "rust"],
                            "default": "python",
                            "description": "Programming language",
                        },
                    },
                    "required": ["path"],
                },
            },
            "run_tests": {
                "description": "Run pytest tests with controlled parameters",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path to test file or directory",
                            "default": "tests/",
                        },
                        "pattern": {
                            "type": "string",
                            "description": "Test file pattern (e.g., test_*.py)",
                        },
                        "verbose": {
                            "type": "boolean",
                            "default": False,
                            "description": "Enable verbose output",
                        },
                        "coverage": {
                            "type": "boolean",
                            "default": False,
                            "description": "Generate coverage report",
                        },
                        "fail_fast": {
                            "type": "boolean",
                            "default": False,
                            "description": "Stop on first failure",
                        },
                        "markers": {
                            "type": "string",
                            "description": "Run tests matching marker expression (e.g., 'not slow')",
                        },
                    },
                    "required": [],
                },
            },
            "type_check": {
                "description": "Run ty type checking (Astral's fast type checker, 10-60x faster than mypy)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path to file or directory to check",
                        },
                        "strict": {
                            "type": "boolean",
                            "default": False,
                            "description": "Enable strict mode (currently unused, ty uses pyproject.toml config)",
                        },
                        "config": {
                            "type": "string",
                            "description": "Path to pyproject.toml configuration file (optional)",
                        },
                    },
                    "required": ["path"],
                },
            },
            "security_scan": {
                "description": "Run security analysis with bandit",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path to file or directory to scan",
                        },
                        "severity": {
                            "type": "string",
                            "enum": ["low", "medium", "high"],
                            "default": "low",
                            "description": "Minimum severity level to report",
                        },
                        "confidence": {
                            "type": "string",
                            "enum": ["low", "medium", "high"],
                            "default": "low",
                            "description": "Minimum confidence level to report",
                        },
                    },
                    "required": ["path"],
                },
            },
            "audit_dependencies": {
                "description": "Check dependencies for known vulnerabilities",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "requirements_file": {
                            "type": "string",
                            "default": "requirements.txt",
                            "description": "Path to requirements file",
                        },
                    },
                    "required": [],
                },
            },
            "check_markdown_links": {
                "description": "Check links in markdown files for validity",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path to markdown file or directory",
                        },
                        "check_external": {
                            "type": "boolean",
                            "default": True,
                            "description": "Check external HTTP/HTTPS links",
                        },
                        "ignore_patterns": {
                            "type": "array",
                            "items": {"type": "string"},
                            "default": [],
                            "description": "Regex patterns for URLs to ignore",
                        },
                        "timeout": {
                            "type": "integer",
                            "default": 10,
                            "description": "Timeout for HTTP requests in seconds",
                        },
                        "concurrent_checks": {
                            "type": "integer",
                            "default": 10,
                            "description": "Maximum number of concurrent link checks",
                        },
                    },
                    "required": ["path"],
                },
            },
            "get_status": {
                "description": "Get server status, available tools, and their versions",
                "parameters": {
                    "type": "object",
                    "properties": {},
                },
            },
            "get_audit_log": {
                "description": "Get recent audit log entries for compliance review",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "limit": {
                            "type": "integer",
                            "default": 100,
                            "description": "Maximum number of entries to return",
                        },
                        "operation": {
                            "type": "string",
                            "description": "Filter by operation name",
                        },
                    },
                    "required": [],
                },
            },
        }

        return tools

    async def format_check(self, path: str, language: str = "python") -> Dict[str, Any]:
        """
        Check code formatting for various languages.

        Args:
            path: Path to file or directory to check
            language: Programming language (python, javascript, typescript, go, rust)

        Returns:
            Dictionary with formatting status and any issues found
        """
        # Rate limiting
        if not self._check_rate_limit("format_check"):
            return {"success": False, "error": "Rate limit exceeded", "error_type": "rate_limit"}

        # Path validation
        if not self._validate_path(path):
            self._audit_log("format_check", path, False, {"reason": "path_not_allowed"})
            return {
                "success": False,
                "error": f"Path not allowed: {path}",
                "error_type": "path_validation",
                "allowed_paths": self.allowed_paths,
            }

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
                "error_type": "unsupported_language",
                "supported_languages": list(formatters.keys()),
            }

        try:
            logger.info("Checking %s formatting for: %s", language, path)
            result = self._run_subprocess(formatters[language])

            success = result.returncode == 0
            self._audit_log("format_check", path, success, {"language": language, "formatted": success})

            return {
                "success": True,
                "formatted": success,
                "output": result.stdout or result.stderr,
                "command": " ".join(formatters[language]),
            }
        except subprocess.TimeoutExpired:
            self._audit_log("format_check", path, False, {"reason": "timeout"})
            return {
                "success": False,
                "error": f"Format check timed out after {self.timeout}s",
                "error_type": "timeout",
            }
        except FileNotFoundError:
            tool = formatters[language][0]
            self._audit_log("format_check", path, False, {"reason": "tool_not_found", "tool": tool})
            return {
                "success": False,
                "error": f"{tool} not found. Please install it first.",
                "error_type": "tool_not_found",
            }
        except Exception as e:
            logger.error("Format check error: %s", str(e))
            self._audit_log("format_check", path, False, {"reason": "exception", "error": str(e)})
            return {"success": False, "error": str(e), "error_type": "exception"}

    async def lint(self, path: str, config: Optional[str] = None, linter: str = "ruff") -> Dict[str, Any]:
        """
        Run code linting with various linters.

        Args:
            path: Path to file or directory to lint
            config: Optional path to linting configuration file
            linter: Linter to use (flake8, ruff, eslint, golint, clippy)

        Returns:
            Dictionary with linting results and any issues found
        """
        # Rate limiting
        if not self._check_rate_limit("lint"):
            return {"success": False, "error": "Rate limit exceeded", "error_type": "rate_limit"}

        # Path validation
        if not self._validate_path(path):
            self._audit_log("lint", path, False, {"reason": "path_not_allowed"})
            return {
                "success": False,
                "error": f"Path not allowed: {path}",
                "error_type": "path_validation",
                "allowed_paths": self.allowed_paths,
            }

        linter_commands = {
            "flake8": ["flake8"],
            "ruff": ["ruff", "check"],
            "eslint": ["eslint"],
            "golint": ["golint"],
            "clippy": ["cargo", "clippy"],
        }

        if linter not in linter_commands:
            return {
                "success": False,
                "error": f"Unsupported linter: {linter}",
                "error_type": "unsupported_linter",
                "supported_linters": list(linter_commands.keys()),
            }

        cmd = linter_commands[linter] + [path]

        # Add config file if provided
        if config:
            if not self._validate_path(config):
                return {
                    "success": False,
                    "error": f"Config path not allowed: {config}",
                    "error_type": "path_validation",
                }
            if linter == "flake8":
                cmd.extend(["--config", config])
            elif linter == "ruff":
                cmd.extend(["--config", config])
            elif linter == "eslint":
                cmd.extend(["--config", config])

        try:
            logger.info("Running %s on: %s", linter, path)
            result = self._run_subprocess(cmd)

            issues = []
            if result.stdout:
                issues = result.stdout.splitlines()

            passed = result.returncode == 0
            self._audit_log("lint", path, passed, {"linter": linter, "issue_count": len(issues)})

            return {
                "success": True,
                "passed": passed,
                "issues": issues,
                "issue_count": len(issues),
                "command": " ".join(cmd),
            }
        except subprocess.TimeoutExpired:
            self._audit_log("lint", path, False, {"reason": "timeout"})
            return {
                "success": False,
                "error": f"Linting timed out after {self.timeout}s",
                "error_type": "timeout",
            }
        except FileNotFoundError:
            self._audit_log("lint", path, False, {"reason": "tool_not_found", "tool": linter})
            return {
                "success": False,
                "error": f"{linter} not found. Please install it first.",
                "error_type": "tool_not_found",
            }
        except Exception as e:
            logger.error("Linting error: %s", str(e))
            self._audit_log("lint", path, False, {"reason": "exception", "error": str(e)})
            return {"success": False, "error": str(e), "error_type": "exception"}

    async def autoformat(self, path: str, language: str = "python") -> Dict[str, Any]:
        """
        Automatically format code files.

        Args:
            path: Path to file or directory to format
            language: Programming language

        Returns:
            Dictionary with formatting results
        """
        # Rate limiting
        if not self._check_rate_limit("autoformat"):
            return {"success": False, "error": "Rate limit exceeded", "error_type": "rate_limit"}

        # Path validation
        if not self._validate_path(path):
            self._audit_log("autoformat", path, False, {"reason": "path_not_allowed"})
            return {
                "success": False,
                "error": f"Path not allowed: {path}",
                "error_type": "path_validation",
                "allowed_paths": self.allowed_paths,
            }

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
                "error_type": "unsupported_language",
                "supported_languages": list(formatters.keys()),
            }

        try:
            logger.info("Auto-formatting %s code in: %s", language, path)
            result = self._run_subprocess(formatters[language])

            success = result.returncode == 0
            self._audit_log("autoformat", path, success, {"language": language})

            return {
                "success": success,
                "formatted": True,
                "output": result.stdout or result.stderr,
                "command": " ".join(formatters[language]),
            }
        except subprocess.TimeoutExpired:
            self._audit_log("autoformat", path, False, {"reason": "timeout"})
            return {
                "success": False,
                "error": f"Auto-format timed out after {self.timeout}s",
                "error_type": "timeout",
            }
        except FileNotFoundError:
            tool = formatters[language][0]
            self._audit_log("autoformat", path, False, {"reason": "tool_not_found", "tool": tool})
            return {
                "success": False,
                "error": f"{tool} not found. Please install it first.",
                "error_type": "tool_not_found",
            }
        except Exception as e:
            logger.error("Auto-format error: %s", str(e))
            self._audit_log("autoformat", path, False, {"reason": "exception", "error": str(e)})
            return {"success": False, "error": str(e), "error_type": "exception"}

    async def run_tests(
        self,
        path: str = "tests/",
        pattern: Optional[str] = None,
        verbose: bool = False,
        coverage: bool = False,
        fail_fast: bool = False,
        markers: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Run pytest tests with controlled parameters.

        Args:
            path: Path to test file or directory
            pattern: Test file pattern (e.g., test_*.py)
            verbose: Enable verbose output
            coverage: Generate coverage report
            fail_fast: Stop on first failure
            markers: Run tests matching marker expression

        Returns:
            Dictionary with test results
        """
        # Rate limiting
        if not self._check_rate_limit("run_tests"):
            return {"success": False, "error": "Rate limit exceeded", "error_type": "rate_limit"}

        # Path validation
        if not self._validate_path(path):
            self._audit_log("run_tests", path, False, {"reason": "path_not_allowed"})
            return {
                "success": False,
                "error": f"Path not allowed: {path}",
                "error_type": "path_validation",
                "allowed_paths": self.allowed_paths,
            }

        cmd = ["pytest", path]

        if verbose:
            cmd.append("-v")
        if fail_fast:
            cmd.append("-x")
        if coverage:
            cmd.extend(["--cov=.", "--cov-report=term-missing"])
        if pattern:
            cmd.extend(["-k", pattern])
        if markers:
            cmd.extend(["-m", markers])

        try:
            logger.info("Running tests: %s", " ".join(cmd))
            result = self._run_subprocess(cmd)

            # Parse test results from output
            output = result.stdout + result.stderr
            passed = result.returncode == 0

            self._audit_log("run_tests", path, passed, {"returncode": result.returncode})

            return {
                "success": True,
                "passed": passed,
                "returncode": result.returncode,
                "output": output,
                "command": " ".join(cmd),
            }
        except subprocess.TimeoutExpired:
            self._audit_log("run_tests", path, False, {"reason": "timeout"})
            return {
                "success": False,
                "error": f"Tests timed out after {self.timeout}s",
                "error_type": "timeout",
            }
        except FileNotFoundError:
            self._audit_log("run_tests", path, False, {"reason": "tool_not_found", "tool": "pytest"})
            return {
                "success": False,
                "error": "pytest not found. Please install it first.",
                "error_type": "tool_not_found",
            }
        except Exception as e:
            logger.error("Test run error: %s", str(e))
            self._audit_log("run_tests", path, False, {"reason": "exception", "error": str(e)})
            return {"success": False, "error": str(e), "error_type": "exception"}

    async def type_check(self, path: str, strict: bool = False, config: Optional[str] = None) -> Dict[str, Any]:
        """
        Run ty type checking (Astral's fast type checker).

        Args:
            path: Path to file or directory to check
            strict: Enable strict mode (currently unused, ty uses pyproject.toml config)
            config: Path to pyproject.toml configuration file (optional)

        Returns:
            Dictionary with type checking results
        """
        # Rate limiting
        if not self._check_rate_limit("type_check"):
            return {"success": False, "error": "Rate limit exceeded", "error_type": "rate_limit"}

        # Path validation
        if not self._validate_path(path):
            self._audit_log("type_check", path, False, {"reason": "path_not_allowed"})
            return {
                "success": False,
                "error": f"Path not allowed: {path}",
                "error_type": "path_validation",
                "allowed_paths": self.allowed_paths,
            }

        # ty check command - uses pyproject.toml for configuration
        cmd = ["ty", "check", path]

        # Config file support (ty reads from pyproject.toml by default)
        if config:
            if not self._validate_path(config):
                return {
                    "success": False,
                    "error": f"Config path not allowed: {config}",
                    "error_type": "path_validation",
                }
            cmd.extend(["--config", config])

        try:
            logger.info("Running ty on: %s", path)
            result = self._run_subprocess(cmd)

            issues = []
            if result.stdout:
                issues = result.stdout.splitlines()

            # ty returns 0 on success, non-zero on errors
            passed = result.returncode == 0
            self._audit_log("type_check", path, passed, {"issue_count": len(issues)})

            return {
                "success": True,
                "passed": passed,
                "issues": issues,
                "issue_count": len(issues),
                "command": " ".join(cmd),
            }
        except subprocess.TimeoutExpired:
            self._audit_log("type_check", path, False, {"reason": "timeout"})
            return {
                "success": False,
                "error": f"Type check timed out after {self.timeout}s",
                "error_type": "timeout",
            }
        except FileNotFoundError:
            self._audit_log("type_check", path, False, {"reason": "tool_not_found", "tool": "ty"})
            return {
                "success": False,
                "error": "ty not found. Install with: pip install ty",
                "error_type": "tool_not_found",
            }
        except Exception as e:
            logger.error("Type check error: %s", str(e))
            self._audit_log("type_check", path, False, {"reason": "exception", "error": str(e)})
            return {"success": False, "error": str(e), "error_type": "exception"}

    async def security_scan(
        self,
        path: str,
        severity: str = "low",
        confidence: str = "low",
    ) -> Dict[str, Any]:
        """
        Run security analysis with bandit.

        Args:
            path: Path to file or directory to scan
            severity: Minimum severity level (low, medium, high)
            confidence: Minimum confidence level (low, medium, high)

        Returns:
            Dictionary with security scan results
        """
        # Rate limiting
        if not self._check_rate_limit("security_scan"):
            return {"success": False, "error": "Rate limit exceeded", "error_type": "rate_limit"}

        # Path validation
        if not self._validate_path(path):
            self._audit_log("security_scan", path, False, {"reason": "path_not_allowed"})
            return {
                "success": False,
                "error": f"Path not allowed: {path}",
                "error_type": "path_validation",
                "allowed_paths": self.allowed_paths,
            }

        # Use explicit --severity-level and --confidence-level flags
        # (The short flags -l/-ll/-lll and -i/-ii/-iii are for repeating, not values)
        cmd = ["bandit", "-r", path, f"--severity-level={severity}", f"--confidence-level={confidence}", "-f", "json"]

        try:
            logger.info("Running security scan on: %s", path)
            result = self._run_subprocess(cmd)

            # Parse JSON output
            findings = []
            try:
                if result.stdout:
                    data = json.loads(result.stdout)
                    findings = data.get("results", [])
            except json.JSONDecodeError:
                pass

            # returncode 0 = no issues, 1 = issues found
            passed = result.returncode == 0
            self._audit_log("security_scan", path, passed, {"finding_count": len(findings)})

            return {
                "success": True,
                "passed": passed,
                "findings": findings,
                "finding_count": len(findings),
                "command": " ".join(cmd),
            }
        except subprocess.TimeoutExpired:
            self._audit_log("security_scan", path, False, {"reason": "timeout"})
            return {
                "success": False,
                "error": f"Security scan timed out after {self.timeout}s",
                "error_type": "timeout",
            }
        except FileNotFoundError:
            self._audit_log("security_scan", path, False, {"reason": "tool_not_found", "tool": "bandit"})
            return {
                "success": False,
                "error": "bandit not found. Please install it first.",
                "error_type": "tool_not_found",
            }
        except Exception as e:
            logger.error("Security scan error: %s", str(e))
            self._audit_log("security_scan", path, False, {"reason": "exception", "error": str(e)})
            return {"success": False, "error": str(e), "error_type": "exception"}

    async def audit_dependencies(self, requirements_file: str = "requirements.txt") -> Dict[str, Any]:
        """
        Check dependencies for known vulnerabilities using pip-audit.

        Args:
            requirements_file: Path to requirements file

        Returns:
            Dictionary with vulnerability audit results
        """
        # Rate limiting
        if not self._check_rate_limit("audit_dependencies"):
            return {"success": False, "error": "Rate limit exceeded", "error_type": "rate_limit"}

        # Path validation
        if not self._validate_path(requirements_file):
            self._audit_log("audit_dependencies", requirements_file, False, {"reason": "path_not_allowed"})
            return {
                "success": False,
                "error": f"Path not allowed: {requirements_file}",
                "error_type": "path_validation",
                "allowed_paths": self.allowed_paths,
            }

        cmd = ["pip-audit", "-r", requirements_file, "--format", "json"]

        try:
            logger.info("Auditing dependencies: %s", requirements_file)
            result = self._run_subprocess(cmd)

            # Parse JSON output
            vulnerabilities = []
            try:
                if result.stdout:
                    vulnerabilities = json.loads(result.stdout)
            except json.JSONDecodeError:
                pass

            passed = result.returncode == 0
            self._audit_log("audit_dependencies", requirements_file, passed, {"vulnerability_count": len(vulnerabilities)})

            return {
                "success": True,
                "passed": passed,
                "vulnerabilities": vulnerabilities,
                "vulnerability_count": len(vulnerabilities),
                "command": " ".join(cmd),
            }
        except subprocess.TimeoutExpired:
            self._audit_log("audit_dependencies", requirements_file, False, {"reason": "timeout"})
            return {
                "success": False,
                "error": f"Dependency audit timed out after {self.timeout}s",
                "error_type": "timeout",
            }
        except FileNotFoundError:
            self._audit_log("audit_dependencies", requirements_file, False, {"reason": "tool_not_found", "tool": "pip-audit"})
            return {
                "success": False,
                "error": "pip-audit not found. Please install it first.",
                "error_type": "tool_not_found",
            }
        except Exception as e:
            logger.error("Dependency audit error: %s", str(e))
            self._audit_log("audit_dependencies", requirements_file, False, {"reason": "exception", "error": str(e)})
            return {"success": False, "error": str(e), "error_type": "exception"}

    async def check_markdown_links(
        self,
        path: str,
        check_external: bool = True,
        ignore_patterns: Optional[List[str]] = None,
        timeout: int = 10,
        concurrent_checks: int = 10,
    ) -> Dict[str, Any]:
        """
        Check links in markdown files for validity.

        Args:
            path: Path to markdown file or directory
            check_external: Whether to check external HTTP/HTTPS links
            ignore_patterns: List of regex patterns for URLs to ignore
            timeout: Timeout for HTTP requests in seconds
            concurrent_checks: Maximum number of concurrent link checks

        Returns:
            Dictionary with link checking results
        """
        # Rate limiting
        if not self._check_rate_limit("check_markdown_links"):
            return {"success": False, "error": "Rate limit exceeded", "error_type": "rate_limit"}

        # Path validation
        if not self._validate_path(path):
            self._audit_log("check_markdown_links", path, False, {"reason": "path_not_allowed"})
            return {
                "success": False,
                "error": f"Path not allowed: {path}",
                "error_type": "path_validation",
                "allowed_paths": self.allowed_paths,
            }

        if not MARKDOWN_CHECKER_AVAILABLE:
            return {
                "success": False,
                "error": "Markdown link checker not available",
                "error_type": "tool_not_found",
            }

        # Lazy init link checker
        if self._link_checker is None:
            self._link_checker = MarkdownLinkChecker()

        try:
            result = await self._link_checker.check_markdown_links(
                path=path,
                check_external=check_external,
                ignore_patterns=ignore_patterns,
                timeout=timeout,
                concurrent_checks=concurrent_checks,
            )

            self._audit_log("check_markdown_links", path, result.get("success", False))
            return result
        except Exception as e:
            logger.error("Markdown link check error: %s", str(e))
            self._audit_log("check_markdown_links", path, False, {"reason": "exception", "error": str(e)})
            return {"success": False, "error": str(e), "error_type": "exception"}

    async def get_status(self) -> Dict[str, Any]:
        """
        Get server status, available tools, and their versions.

        Returns:
            Dictionary with server status information
        """
        tools_status = {}

        # Check each tool's availability
        tool_checks = [
            ("black", ["black", "--version"]),
            ("flake8", ["flake8", "--version"]),
            ("ruff", ["ruff", "--version"]),
            ("ty", ["ty", "--version"]),
            ("pytest", ["pytest", "--version"]),
            ("bandit", ["bandit", "--version"]),
            ("pip-audit", ["pip-audit", "--version"]),
            ("prettier", ["prettier", "--version"]),
            ("eslint", ["eslint", "--version"]),
        ]

        for tool_name, cmd in tool_checks:
            try:
                result = self._run_subprocess(cmd, timeout=10)
                version = result.stdout.strip().split("\n")[0] if result.stdout else "unknown"
                tools_status[tool_name] = {
                    "available": result.returncode == 0,
                    "version": version,
                }
            except FileNotFoundError:
                tools_status[tool_name] = {"available": False, "reason": "Not installed"}
            except subprocess.TimeoutExpired:
                tools_status[tool_name] = {"available": False, "reason": "Version check timed out"}
            except Exception as e:
                tools_status[tool_name] = {"available": False, "reason": str(e)}

        return {
            "server": "Code Quality MCP Server",
            "version": "2.0.0",
            "timeout_seconds": self.timeout,
            "allowed_paths": self.allowed_paths,
            "rate_limiting_enabled": self.rate_limiting_enabled,
            "audit_log_path": str(self.audit_log_path),
            "markdown_checker_available": MARKDOWN_CHECKER_AVAILABLE,
            "tools": tools_status,
        }

    async def get_audit_log(self, limit: int = 100, operation: Optional[str] = None) -> Dict[str, Any]:
        """
        Get recent audit log entries for compliance review.

        Args:
            limit: Maximum number of entries to return
            operation: Filter by operation name

        Returns:
            Dictionary with audit log entries
        """
        try:
            entries = []
            if self.audit_log_path.exists():
                with open(self.audit_log_path) as f:
                    for line in f:
                        try:
                            entry = json.loads(line.strip())
                            if operation is None or entry.get("operation") == operation:
                                entries.append(entry)
                        except json.JSONDecodeError:
                            continue

            # Return most recent entries
            entries = entries[-limit:]

            return {
                "success": True,
                "entries": entries,
                "count": len(entries),
                "log_path": str(self.audit_log_path),
            }
        except Exception as e:
            logger.error("Failed to read audit log: %s", str(e))
            return {"success": False, "error": str(e), "error_type": "exception"}


def main():
    """Run the Code Quality MCP Server."""
    import argparse

    parser = argparse.ArgumentParser(description="Code Quality MCP Server")
    parser.add_argument(
        "--mode",
        choices=["http", "stdio"],
        default="http",
        help="Server mode (http or stdio)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8010,
        help="HTTP port (default: 8010)",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Log level (default: INFO)",
    )

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    server = CodeQualityMCPServer(port=args.port)
    server.run(mode=args.mode)


if __name__ == "__main__":
    main()
