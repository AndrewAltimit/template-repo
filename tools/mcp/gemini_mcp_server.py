#!/usr/bin/env python3
"""
MCP Server with Gemini Integration
Provides development workflow automation with AI second opinions
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import mcp.server.stdio
import mcp.types as types
from mcp.server import InitializationOptions, NotificationOptions, Server


# Check if running in container BEFORE any other imports or operations
def check_container_and_exit():
    """Check if running in a container and exit immediately if true."""
    if os.path.exists("/.dockerenv") or os.environ.get("CONTAINER_ENV"):
        print("ERROR: Gemini MCP Server cannot run inside a container!", file=sys.stderr)
        print(
            "The Gemini CLI requires Docker access and must run on the host system.",
            file=sys.stderr,
        )
        print("Please launch this server directly on the host with:", file=sys.stderr)
        print("  python tools/mcp/gemini_mcp_server.py", file=sys.stderr)
        sys.exit(1)


# Perform container check immediately
check_container_and_exit()

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from tools.gemini.gemini_integration import get_integration  # noqa: E402


class MCPServer:
    def __init__(self, project_root: str = None):
        self.project_root = Path(project_root) if project_root else Path.cwd()
        self.server = Server("gemini-mcp-server")

        # Initialize Gemini integration with singleton pattern
        self.gemini_config = self._load_gemini_config()
        # Get the singleton instance, passing config on first call
        self.gemini = get_integration(self.gemini_config)

        # Track uncertainty for auto-consultation
        self.last_response_uncertainty = None

        self._setup_tools()

    def _load_gemini_config(self) -> Dict[str, Any]:
        """Load Gemini configuration from environment or config file."""
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
                print(f"Warning: Could not load .env file: {e}")

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
                print(f"Warning: Could not load gemini-config.json: {e}")

        return config

    def _setup_tools(self):
        """Register all MCP tools"""

        # Gemini consultation tool
        @self.server.call_tool()
        async def consult_gemini(arguments: Dict[str, Any]) -> List[types.TextContent]:
            """Consult Gemini CLI for a second opinion or validation."""
            query = arguments.get("query", "")
            context = arguments.get("context", "")
            comparison_mode = arguments.get("comparison_mode", True)
            force_consult = arguments.get("force", False)

            if not query:
                return [
                    types.TextContent(
                        type="text",
                        text="❌ Error: 'query' parameter is required for Gemini consultation",
                    )
                ]

            # Consult Gemini
            result = await self.gemini.consult_gemini(
                query=query,
                context=context,
                comparison_mode=comparison_mode,
                force_consult=force_consult,
            )

            # Format the response
            return await self._format_gemini_response(result)

        @self.server.call_tool()
        async def gemini_status(arguments: Dict[str, Any]) -> List[types.TextContent]:
            """Get Gemini integration status and statistics."""
            return await self._get_gemini_status()

        @self.server.call_tool()
        async def toggle_gemini_auto_consult(
            arguments: Dict[str, Any],
        ) -> List[types.TextContent]:
            """Toggle automatic Gemini consultation on uncertainty detection."""
            enable = arguments.get("enable", None)

            if enable is None:
                # Toggle current state
                self.gemini.auto_consult = not self.gemini.auto_consult
            else:
                self.gemini.auto_consult = bool(enable)

            status = "enabled" if self.gemini.auto_consult else "disabled"
            return [types.TextContent(type="text", text=f"✅ Gemini auto-consultation is now {status}")]

        @self.server.call_tool()
        async def clear_gemini_history(
            arguments: Dict[str, Any],
        ) -> List[types.TextContent]:
            """Clear Gemini conversation history."""
            result = self.gemini.clear_conversation_history()
            return [types.TextContent(type="text", text=f"✅ {result['message']}")]

    async def _format_gemini_response(self, result: Dict[str, Any]) -> List[types.TextContent]:
        """Format Gemini consultation response for MCP output."""
        output_lines = []
        output_lines.append("🤖 Gemini Consultation Response")
        output_lines.append("=" * 40)
        output_lines.append("")

        if result["status"] == "success":
            output_lines.append(f"✅ Consultation ID: {result['consultation_id']}")
            output_lines.append(f"⏱️  Execution time: {result['execution_time']:.2f}s")
            output_lines.append("")

            # Display the raw response (simplified format)
            response = result.get("response", "")
            if response:
                output_lines.append("📄 Response:")
                output_lines.append(response)

        elif result["status"] == "disabled":
            output_lines.append("ℹ️  Gemini consultation is currently disabled")
            output_lines.append("💡 Enable with: toggle_gemini_auto_consult")

        elif result["status"] == "timeout":
            output_lines.append(f"❌ {result['error']}")
            output_lines.append("💡 Try increasing the timeout or simplifying the query")

        else:  # error
            output_lines.append(f"❌ Error: {result.get('error', 'Unknown error')}")
            output_lines.append("")
            output_lines.append("💡 Troubleshooting:")
            output_lines.append("  1. Check if Gemini CLI is installed and in PATH")
            output_lines.append("  2. Verify Gemini CLI authentication")
            output_lines.append("  3. Check the logs for more details")

        return [types.TextContent(type="text", text="\n".join(output_lines))]

    async def _get_gemini_status(self) -> List[types.TextContent]:
        """Get Gemini integration status and statistics."""
        output_lines = []
        output_lines.append("🤖 Gemini Integration Status")
        output_lines.append("=" * 40)
        output_lines.append("")

        # Configuration status
        output_lines.append("⚙️  Configuration:")
        output_lines.append(f"  • Enabled: {'✅ Yes' if self.gemini.enabled else '❌ No'}")
        output_lines.append(f"  • Auto-consult: {'✅ Yes' if self.gemini.auto_consult else '❌ No'}")
        output_lines.append(f"  • CLI command: {self.gemini.cli_command}")
        output_lines.append(f"  • Timeout: {self.gemini.timeout}s")
        output_lines.append(f"  • Rate limit: {self.gemini.rate_limit_delay}s")
        output_lines.append("")

        # Check if Gemini CLI is available
        try:
            # Test with a simple prompt rather than --version (which may not be supported)
            check_process = await asyncio.create_subprocess_exec(
                self.gemini.cli_command,
                "-p",
                "test",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(check_process.communicate(), timeout=10)

            if check_process.returncode == 0:
                output_lines.append("✅ Gemini CLI is available and working")
                # Try to get version info from help or other means
                try:
                    help_process = await asyncio.create_subprocess_exec(
                        self.gemini.cli_command,
                        "--help",
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    help_stdout, _ = await help_process.communicate()
                    help_text = help_stdout.decode()
                    # Look for version in help output
                    if "version" in help_text.lower():
                        for line in help_text.split("\n"):
                            if "version" in line.lower():
                                output_lines.append(f"  {line.strip()}")
                                break
                except Exception:
                    pass
            else:
                error_msg = stderr.decode() if stderr else "Unknown error"
                output_lines.append("❌ Gemini CLI found but not working properly")
                output_lines.append(f"  Command tested: {self.gemini.cli_command}")
                output_lines.append(f"  Error: {error_msg}")

                # Check for authentication issues
                if "authentication" in error_msg.lower() or "api key" in error_msg.lower():
                    output_lines.append("")
                    output_lines.append("🔑 Authentication required:")
                    output_lines.append("  1. Set GEMINI_API_KEY environment variable, or")
                    output_lines.append("  2. Run 'gemini' interactively to authenticate with Google")

        except asyncio.TimeoutError:
            output_lines.append("❌ Gemini CLI test timed out")
            output_lines.append("  This may indicate authentication is required")
        except FileNotFoundError:
            output_lines.append("❌ Gemini CLI not found in PATH")
            output_lines.append(f"  Expected command: {self.gemini.cli_command}")
            output_lines.append("")
            output_lines.append("📦 Installation:")
            output_lines.append("  npm install -g @google/gemini-cli")
            output_lines.append("  OR")
            output_lines.append("  npx @google/gemini-cli")
        except Exception as e:
            output_lines.append(f"❌ Error checking Gemini CLI: {str(e)}")

        output_lines.append("")

        # Consultation statistics
        stats = self.gemini.get_consultation_stats()
        output_lines.append("📊 Consultation Statistics:")
        output_lines.append(f"  • Total consultations: {stats.get('total_consultations', 0)}")

        completed = stats.get("completed_consultations", 0)
        output_lines.append(f"  • Completed: {completed}")

        if completed > 0:
            avg_time = stats.get("average_execution_time", 0)
            output_lines.append(f"  • Average time: {avg_time:.2f}s")
            total_time = sum(e.get("execution_time", 0) for e in self.gemini.consultation_log if e.get("status") == "success")
            output_lines.append(f"  • Total time: {total_time:.2f}s")

        output_lines.append("")
        output_lines.append("💡 Usage:")
        output_lines.append("  • Direct: Use 'consult_gemini' tool")
        output_lines.append("  • Auto: Enable auto-consult for uncertainty detection")
        output_lines.append("  • Toggle: Use 'toggle_gemini_auto_consult' tool")

        return [types.TextContent(type="text", text="\n".join(output_lines))]

    def detect_response_uncertainty(self, response: str) -> Tuple[bool, List[str]]:
        """
        Detect uncertainty in a response for potential auto-consultation.
        This is a wrapper around the GeminiIntegration's detection.
        """
        return self.gemini.detect_uncertainty(response)

    async def maybe_consult_gemini(self, response: str, context: str = "") -> Optional[Dict[str, Any]]:
        """
        Check if response contains uncertainty and consult Gemini if needed.

        Args:
            response: The response to check for uncertainty
            context: Additional context for the consultation

        Returns:
            Gemini consultation result if consulted, None otherwise
        """
        if not self.gemini.auto_consult or not self.gemini.enabled:
            return None

        has_uncertainty, patterns = self.detect_response_uncertainty(response)

        if has_uncertainty:
            # Extract the main question or topic from the response
            query = f"Please provide a second opinion on this analysis:\n\n{response}"

            # Add uncertainty patterns to context
            enhanced_context = f"{context}\n\nUncertainty detected in: {', '.join(patterns)}"

            result = await self.gemini.consult_gemini(query=query, context=enhanced_context, comparison_mode=True)

            return result

        return None

    def run(self):
        """Run the MCP server."""

        async def main():
            async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
                await self.server.run(
                    read_stream,
                    write_stream,
                    InitializationOptions(
                        server_name="gemini-mcp-server",
                        server_version="1.0.0",
                        capabilities=self.server.get_capabilities(
                            notification_options=NotificationOptions(),
                            experimental_capabilities={},
                        ),
                    ),
                )

        asyncio.run(main())


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="MCP Server with Gemini Integration")
    parser.add_argument(
        "--project-root",
        type=str,
        default=".",
        help="Path to the project root directory",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Port for HTTP mode (if specified, runs as HTTP server instead of stdio)",
    )

    args = parser.parse_args()

    # Check if running in container - exit with instructions if true
    check_container_and_exit()

    # If port is specified, run as HTTP server (for backward compatibility/testing)
    if args.port:
        print("Warning: Running in HTTP mode. For production, use stdio mode (no --port argument)")
        # Import and run the HTTP server
        try:
            from gemini_mcp_server_http import run_http_server
        except ImportError:
            # Try with absolute import
            from tools.mcp.gemini_mcp_server_http import run_http_server
        run_http_server(args.port)
    else:
        # Run as stdio MCP server (recommended)
        server = MCPServer(args.project_root)
        server.run()
