"""GitHub Board MCP Server - Board operations and agent coordination

Provides MCP tools for interacting with GitHub Projects v2 boards,
managing work claims, dependencies, and agent coordination.

This server wraps the Rust `board-manager` CLI for all board operations.
"""

import asyncio
import json
import os
import shutil
import traceback
from typing import Any, Dict, List, Optional

from mcp_core.base_server import BaseMCPServer
from mcp_core.utils import setup_logging


class GitHubBoardMCPServer(BaseMCPServer):
    """MCP Server for GitHub Projects v2 board operations

    Uses the Rust `board-manager` CLI for all operations.
    """

    def __init__(self) -> None:
        super().__init__(
            name="GitHub Board MCP Server",
            version="2.0.0",  # Version bump for Rust CLI migration
            port=8022,
        )
        self.logger = setup_logging("GitHubBoardMCP")
        self._board_manager_path: Optional[str] = None
        self._initialized = False

    async def _ensure_initialized(self) -> bool:
        """Ensure board-manager CLI is available"""
        if self._initialized:
            return True

        # Find board-manager binary
        # Check common locations
        search_paths = [
            # Installed in PATH
            shutil.which("board-manager"),
            # Local build
            os.path.join(os.getcwd(), "tools/rust/board-manager/target/release/board-manager"),
            # Relative to this file
            os.path.join(os.path.dirname(__file__), "../../../../../tools/rust/board-manager/target/release/board-manager"),
            # Home local bin
            os.path.expanduser("~/.local/bin/board-manager"),
        ]

        for path in search_paths:
            if path and os.path.isfile(path) and os.access(path, os.X_OK):
                self._board_manager_path = path
                self.logger.info("Found board-manager at %s", path)
                self._initialized = True
                return True

        self.logger.error("board-manager CLI not found. Please install or build it.")
        return False

    async def _run_board_manager(self, args: List[str]) -> Dict[str, Any]:
        """Run board-manager CLI and return parsed JSON output"""
        if not await self._ensure_initialized() or self._board_manager_path is None:
            return {"success": False, "error": "board-manager CLI not available"}

        cmd: List[str] = [self._board_manager_path, "--format", "json"] + args
        self.logger.debug("Running: %s", " ".join(cmd))

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**os.environ},
            )
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                error_msg = stderr.decode().strip() if stderr else f"Exit code {process.returncode}"
                self.logger.error("board-manager failed: %s", error_msg)
                return {"success": False, "error": error_msg}

            # Parse JSON output
            output = stdout.decode().strip()
            if output:
                try:
                    return {"success": True, "result": json.loads(output)}
                except json.JSONDecodeError as e:
                    self.logger.warning("Failed to parse JSON output: %s", e)
                    return {"success": True, "result": {"raw_output": output}}
            return {"success": True, "result": {}}

        except Exception as e:
            self.logger.error("Error running board-manager: %s", e)
            self.logger.debug(traceback.format_exc())
            return {"success": False, "error": str(e)}

    def get_tools(self) -> Dict[str, Dict[str, Any]]:
        """Return available GitHub board tools"""
        return {
            "query_ready_work": {
                "description": "Get ready work from the board (unblocked, unclaimed TODO issues)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "agent_name": {
                            "type": "string",
                            "description": "Filter for specific agent (optional)",
                        },
                        "limit": {
                            "type": "integer",
                            "default": 10,
                            "description": "Maximum number of issues to return",
                        },
                    },
                },
            },
            "claim_work": {
                "description": "Claim an issue for implementation",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "issue_number": {
                            "type": "integer",
                            "description": "Issue number to claim",
                        },
                        "agent_name": {
                            "type": "string",
                            "description": "Agent claiming the issue",
                        },
                        "session_id": {
                            "type": "string",
                            "description": "Unique session identifier",
                        },
                    },
                    "required": ["issue_number", "agent_name", "session_id"],
                },
            },
            "renew_claim": {
                "description": "Renew an active claim for long-running tasks",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "issue_number": {
                            "type": "integer",
                            "description": "Issue number with active claim",
                        },
                        "agent_name": {
                            "type": "string",
                            "description": "Agent renewing the claim",
                        },
                        "session_id": {
                            "type": "string",
                            "description": "Session identifier from original claim",
                        },
                    },
                    "required": ["issue_number", "agent_name", "session_id"],
                },
            },
            "release_work": {
                "description": "Release claim on an issue",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "issue_number": {
                            "type": "integer",
                            "description": "Issue number to release",
                        },
                        "agent_name": {
                            "type": "string",
                            "description": "Agent releasing the claim",
                        },
                        "reason": {
                            "type": "string",
                            "enum": ["completed", "blocked", "abandoned", "error"],
                            "default": "completed",
                            "description": "Reason for release",
                        },
                    },
                    "required": ["issue_number", "agent_name"],
                },
            },
            "update_status": {
                "description": "Update issue status on the board",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "issue_number": {
                            "type": "integer",
                            "description": "Issue number to update",
                        },
                        "status": {
                            "type": "string",
                            "enum": ["Todo", "In Progress", "Blocked", "Done", "Abandoned"],
                            "description": "New status",
                        },
                    },
                    "required": ["issue_number", "status"],
                },
            },
            "add_blocker": {
                "description": "Add a blocking dependency between issues",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "issue_number": {
                            "type": "integer",
                            "description": "Issue that is blocked",
                        },
                        "blocker_number": {
                            "type": "integer",
                            "description": "Issue that blocks",
                        },
                    },
                    "required": ["issue_number", "blocker_number"],
                },
            },
            "mark_discovered_from": {
                "description": "Mark an issue as discovered from another (parent-child relationship)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "issue_number": {
                            "type": "integer",
                            "description": "Child issue number",
                        },
                        "parent_number": {
                            "type": "integer",
                            "description": "Parent issue number",
                        },
                    },
                    "required": ["issue_number", "parent_number"],
                },
            },
            "get_issue_details": {
                "description": "Get full details for a specific issue",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "issue_number": {
                            "type": "integer",
                            "description": "Issue number to query",
                        },
                    },
                    "required": ["issue_number"],
                },
            },
            "get_dependency_graph": {
                "description": "Get dependency graph for an issue (blockers, blocked, parent, children)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "issue_number": {
                            "type": "integer",
                            "description": "Issue number to query",
                        },
                    },
                    "required": ["issue_number"],
                },
            },
            "list_agents": {
                "description": "Get list of enabled agents for this board",
                "parameters": {
                    "type": "object",
                    "properties": {},
                },
            },
            "get_board_config": {
                "description": "Get current board configuration",
                "parameters": {
                    "type": "object",
                    "properties": {},
                },
            },
        }

    # Tool Implementation Methods - all delegate to board-manager CLI

    async def query_ready_work(self, agent_name: Optional[str] = None, limit: int = 10) -> Dict[str, Any]:
        """Get ready work from board"""
        args = ["ready", "--limit", str(limit)]
        if agent_name:
            args.extend(["--agent", agent_name])
        return await self._run_board_manager(args)

    async def claim_work(self, issue_number: int, agent_name: str, session_id: str) -> Dict[str, Any]:
        """Claim an issue"""
        args = ["claim", str(issue_number), "--agent", agent_name, "--session", session_id]
        return await self._run_board_manager(args)

    async def renew_claim(self, issue_number: int, agent_name: str, session_id: str) -> Dict[str, Any]:
        """Renew an active claim"""
        args = ["renew", str(issue_number), "--agent", agent_name, "--session", session_id]
        return await self._run_board_manager(args)

    async def release_work(self, issue_number: int, agent_name: str, reason: str = "completed") -> Dict[str, Any]:
        """Release claim on issue"""
        args = ["release", str(issue_number), "--agent", agent_name, "--reason", reason]
        return await self._run_board_manager(args)

    async def update_status(self, issue_number: int, status: str) -> Dict[str, Any]:
        """Update issue status"""
        args = ["status", str(issue_number), status]
        return await self._run_board_manager(args)

    async def add_blocker(self, issue_number: int, blocker_number: int) -> Dict[str, Any]:
        """Add blocker dependency"""
        args = ["block", str(issue_number), "--blocker", str(blocker_number)]
        return await self._run_board_manager(args)

    async def mark_discovered_from(self, issue_number: int, parent_number: int) -> Dict[str, Any]:
        """Mark parent-child relationship"""
        args = ["discover-from", str(issue_number), "--parent", str(parent_number)]
        return await self._run_board_manager(args)

    async def get_issue_details(self, issue_number: int) -> Dict[str, Any]:
        """Get full issue details"""
        args = ["info", str(issue_number)]
        return await self._run_board_manager(args)

    async def get_dependency_graph(self, issue_number: int) -> Dict[str, Any]:
        """Get dependency graph"""
        # The info command includes dependency information
        args = ["info", str(issue_number)]
        return await self._run_board_manager(args)

    async def list_agents(self) -> Dict[str, Any]:
        """List enabled agents"""
        args = ["agents"]
        return await self._run_board_manager(args)

    async def get_board_config(self) -> Dict[str, Any]:
        """Get board configuration"""
        args = ["config"]
        return await self._run_board_manager(args)

    async def health_check(self):
        """Enhanced health check with board status"""
        base_health = await super().health_check()

        # Check board-manager availability
        board_status = "not_initialized"
        if await self._ensure_initialized():
            board_status = "healthy"

        return {
            **base_health,
            "board_status": board_status,
            "board_manager_path": self._board_manager_path,
        }


def main():
    """Run the GitHub Board MCP Server"""
    import argparse

    parser = argparse.ArgumentParser(description="GitHub Board MCP Server")
    parser.add_argument(
        "--mode",
        choices=["http", "stdio"],
        default="http",
        help="Server mode (http or stdio)",
    )
    args = parser.parse_args()

    server = GitHubBoardMCPServer()
    server.run(mode=args.mode)


if __name__ == "__main__":
    main()
