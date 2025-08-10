"""Code Quality MCP Server - Format checking and linting tools"""

import asyncio
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple  # noqa: F401

import aiohttp

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
            result = subprocess.run(formatters[language], capture_output=True, text=True, check=False)

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

    async def lint(self, path: str, config: Optional[str] = None, linter: str = "flake8") -> Dict[str, Any]:
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
            result = subprocess.run(formatters[language], capture_output=True, text=True, check=False)

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

    async def check_markdown_links(
        self,
        path: str,
        check_external: bool = True,
        ignore_patterns: Optional[List[str]] = None,
        timeout: int = 10,
        concurrent_checks: int = 10,
    ) -> Dict[str, Any]:
        """Check links in markdown files for validity

        Args:
            path: Path to markdown file or directory
            check_external: Whether to check external HTTP/HTTPS links
            ignore_patterns: List of regex patterns for URLs to ignore
            timeout: Timeout for HTTP requests in seconds
            concurrent_checks: Maximum number of concurrent link checks

        Returns:
            Dictionary with link checking results
        """
        if ignore_patterns is None:
            ignore_patterns = [
                r"^http://localhost",
                r"^http://127\.0\.0\.1",
                r"^http://192\.168\.",
                r"^http://0\.0\.0\.0",
                r"^#",
                r"^mailto:",
                r"^chrome://",
                r"^file://",
                r"^ftp://",
            ]

        # Compile ignore patterns
        compiled_patterns = [re.compile(pattern) for pattern in ignore_patterns]

        # Find all markdown files
        markdown_files = []
        path_obj = Path(path)

        if path_obj.is_file() and path_obj.suffix in [".md", ".markdown"]:
            markdown_files = [path_obj]
        elif path_obj.is_dir():
            markdown_files = list(path_obj.rglob("*.md")) + list(path_obj.rglob("*.markdown"))
        else:
            return {"success": False, "error": f"Path {path} is not a valid markdown file or directory"}

        if not markdown_files:
            return {"success": True, "files_checked": 0, "message": "No markdown files found"}

        # Process all files
        all_results = []
        total_links = 0
        broken_links = 0

        for md_file in markdown_files:
            try:
                links = await self._extract_links_from_markdown(md_file)
                file_results = {"file": str(md_file), "links": [], "broken_count": 0, "total_count": len(links)}

                # Filter out ignored patterns
                links_to_check = []
                for link in links:
                    should_ignore = any(pattern.match(link) for pattern in compiled_patterns)
                    if not should_ignore:
                        if not check_external and link.startswith(("http://", "https://")):
                            continue
                        links_to_check.append(link)

                # Check links concurrently
                if links_to_check:
                    link_results = await self._check_links_batch(links_to_check, md_file.parent, timeout, concurrent_checks)

                    for link, is_valid, error in link_results:
                        file_results["links"].append({"url": link, "valid": is_valid, "error": error})  # type: ignore
                        total_links += 1
                        if not is_valid:
                            broken_links += 1
                            file_results["broken_count"] += 1  # type: ignore

                all_results.append(file_results)

            except Exception as e:
                self.logger.error(f"Error processing {md_file}: {str(e)}")
                all_results.append({"file": str(md_file), "error": str(e)})

        return {
            "success": True,
            "files_checked": len(markdown_files),
            "total_links": total_links,
            "broken_links": broken_links,
            "all_valid": broken_links == 0,
            "results": all_results,
        }

    async def _extract_links_from_markdown(self, file_path: Path) -> List[str]:
        """Extract all links from a markdown file"""
        try:
            content = file_path.read_text(encoding="utf-8")

            # Remove code blocks to avoid false positives
            # Remove fenced code blocks (```...```)
            content = re.sub(r"```[\s\S]*?```", "", content)
            # Remove inline code (`...`)
            content = re.sub(r"`[^`]+`", "", content)

            # Use regex to find all links in markdown
            # Matches [text](url) and raw URLs
            link_patterns = [
                r"\[([^\]]+)\]\(([^)]+)\)",  # [text](url)
                r"<(https?://[^>]+)>",  # <url>
                r"(?<!\[)(?<![\(\<])(https?://[^\s\)]+)",  # Raw URLs
            ]

            # Skip patterns that are clearly not links (placeholders, code examples)
            skip_patterns = [
                r"^\{.*\}$",  # {placeholder}
                r"^\.{3}$",  # ...
                r".*\|.*",  # TypeScript types
                r"^(share_url|embed_url|url)$",  # Variable names
                r".*;$",  # Lines ending with semicolon (code)
            ]

            links = []
            compiled_skip = [re.compile(p) for p in skip_patterns]

            for pattern in link_patterns:
                matches = re.finditer(pattern, content)
                for match in matches:
                    # Get the URL part (last group for markdown links)
                    url = match.group(2) if match.lastindex == 2 else match.group(1)
                    if url:
                        # Skip if it matches any skip pattern
                        if not any(skip.match(url) for skip in compiled_skip):
                            links.append(url)

            # Also look for reference-style links
            ref_pattern = r"^\[([^\]]+)\]:\s*(.+)$"
            for line in content.split("\n"):
                match = re.match(ref_pattern, line.strip())
                if match is not None:
                    links.append(match.group(2))

            return list(set(links))  # Remove duplicates

        except Exception as e:
            self.logger.error(f"Error extracting links from {file_path}: {str(e)}")
            return []

    async def _check_links_batch(
        self, links: List[str], base_dir: Path, timeout: int, max_concurrent: int
    ) -> List[Tuple[str, bool, Optional[str]]]:
        """Check multiple links concurrently"""
        semaphore = asyncio.Semaphore(max_concurrent)

        async def check_single_link(link: str) -> Tuple[str, bool, Optional[str]]:
            async with semaphore:
                return await self._check_single_link(link, base_dir, timeout)

        tasks = [check_single_link(link) for link in links]
        return await asyncio.gather(*tasks)

    async def _check_single_link(self, link: str, base_dir: Path, timeout: int) -> Tuple[str, bool, Optional[str]]:
        """Check if a single link is valid"""
        try:
            # Check if it's a relative file link
            if not link.startswith(("http://", "https://", "ftp://", "//")):
                # Handle relative paths
                if link.startswith("/"):
                    # Absolute path from repo root
                    file_path = Path(link[1:])
                else:
                    # Relative to current file
                    file_path = base_dir / link

                # Remove anchor if present
                if "#" in str(file_path):
                    file_path = Path(str(file_path).split("#")[0])

                # Check if file exists
                if file_path.exists():
                    return (link, True, None)
                else:
                    return (link, False, "File not found")

            # Check external links
            if link.startswith("//"):
                link = "https:" + link

            # Use aiohttp to check HTTP/HTTPS links
            timeout_config = aiohttp.ClientTimeout(total=timeout)
            async with aiohttp.ClientSession(timeout=timeout_config) as session:
                try:
                    async with session.head(link, allow_redirects=True) as response:
                        if response.status < 400:
                            return (link, True, None)
                        else:
                            return (link, False, f"HTTP {response.status}")
                except aiohttp.ClientError as e:
                    # Try GET if HEAD fails
                    try:
                        async with session.get(link, allow_redirects=True) as response:
                            if response.status < 400:
                                return (link, True, None)
                            else:
                                return (link, False, f"HTTP {response.status}")
                    except Exception:
                        return (link, False, str(e))

        except Exception as e:
            return (link, False, str(e))


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
