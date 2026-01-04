"""GitHub Board MCP Server - Board operations and agent coordination

Provides MCP tools for interacting with GitHub Projects v2 boards,
managing work claims, dependencies, and agent coordination.
"""

import os
from pathlib import Path
import sys
import traceback
from typing import Any, Dict, Optional

# Add paths for imports (5 parents: server.py -> mcp_github_board -> mcp_github_board -> mcp -> tools -> repo_root)
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent / "packages" / "github_agents" / "src"))
# pylint: disable=wrong-import-position  # Imports must come after sys.path modification

from github_agents.board.config import BoardConfig, load_config  # noqa: E402

# GraphQL errors handled by base server
from github_agents.board.manager import BoardManager  # noqa: E402
from github_agents.board.models import IssueStatus  # noqa: E402
from github_agents.utils.github import get_github_token  # noqa: E402
from mcp_core.base_server import BaseMCPServer  # noqa: E402
from mcp_core.utils import setup_logging  # noqa: E402


class GitHubBoardMCPServer(BaseMCPServer):
    """MCP Server for GitHub Projects v2 board operations"""

    def __init__(self) -> None:
        super().__init__(
            name="GitHub Board MCP Server",
            version="1.0.0",
            port=8022,  # Port for GitHub Board server
        )
        self.logger = setup_logging("GitHubBoardMCP")
        self.board_manager: Optional[BoardManager] = None
        self.config: Optional[BoardConfig] = None
        self._initialized = False

    async def _ensure_initialized(self) -> bool:
        """Ensure board manager is initialized"""
        if self._initialized and self.board_manager:
            return True

        try:
            # Load configuration using shared load_config from github_agents
            config_path = os.getenv("GITHUB_BOARD_CONFIG")
            if config_path and os.path.exists(config_path):
                self.logger.info("Loading board config from %s", config_path)
                self.config = load_config(config_path)
            elif config_path:
                self.logger.warning("Config file not found at %s, using defaults", config_path)
                # Use environment variables for minimal config
                project_number = int(os.getenv("GITHUB_PROJECT_NUMBER", "1"))
                owner = os.getenv("GITHUB_OWNER", os.getenv("GITHUB_REPOSITORY", "").split("/")[0])
                repo = os.getenv("GITHUB_REPOSITORY", f"{owner}/repo")

                self.config = BoardConfig(
                    project_number=project_number,
                    owner=owner,
                    repository=repo,
                )
            else:
                # No explicit config path - try default locations
                self.logger.info("Using default config locations")
                self.config = load_config()

            # Initialize board manager using shared token utility
            try:
                github_token = get_github_token()
            except RuntimeError:
                self.logger.error("GITHUB_TOKEN environment variable not set")
                return False

            self.board_manager = BoardManager(config=self.config, github_token=github_token)
            await self.board_manager.initialize()
            self._initialized = True
            self.logger.info("Board manager initialized successfully")
            return True

        except Exception as e:
            self.logger.error("Failed to initialize board manager: %s", e)
            self.logger.debug(traceback.format_exc())
            return False

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

    async def _ensure_board_ready(self) -> None:
        """Ensure board manager is ready, raise exception if not"""
        if not await self._ensure_initialized():
            raise RuntimeError("Board manager not initialized. Check GITHUB_TOKEN and configuration.")
        assert self.board_manager is not None  # Type narrowing for mypy

    # Tool Implementation Methods

    async def query_ready_work(self, agent_name: Optional[str] = None, limit: int = 10) -> Dict[str, Any]:
        """Get ready work from board"""
        await self._ensure_board_ready()
        assert self.board_manager is not None  # Type narrowing for mypy

        issues = await self.board_manager.get_ready_work(agent_name=agent_name, limit=limit)

        return {
            "success": True,
            "result": {
                "count": len(issues),
                "issues": [
                    {
                        "number": issue.number,
                        "title": issue.title,
                        "status": issue.status.value,
                        "priority": issue.priority.value if issue.priority else None,
                        "type": issue.type.value if issue.type else None,
                        "url": issue.url,
                        "labels": issue.labels,
                        "blocked_by": issue.blocked_by,
                    }
                    for issue in issues
                ],
            },
        }

    async def claim_work(self, issue_number: int, agent_name: str, session_id: str) -> Dict[str, Any]:
        """Claim an issue"""
        await self._ensure_board_ready()
        assert self.board_manager is not None  # Type narrowing for mypy

        success = await self.board_manager.claim_work(issue_number, agent_name, session_id)

        return {
            "success": success,
            "result": {
                "claimed": success,
                "issue_number": issue_number,
                "agent": agent_name,
                "session_id": session_id,
            },
        }

    async def renew_claim(self, issue_number: int, agent_name: str, session_id: str) -> Dict[str, Any]:
        """Renew an active claim"""
        await self._ensure_board_ready()
        assert self.board_manager is not None  # Type narrowing for mypy

        success = await self.board_manager.renew_claim(issue_number, agent_name, session_id)

        return {
            "success": success,
            "result": {
                "renewed": success,
                "issue_number": issue_number,
                "agent": agent_name,
            },
        }

    async def release_work(self, issue_number: int, agent_name: str, reason: str = "completed") -> Dict[str, Any]:
        """Release claim on issue"""
        await self._ensure_board_ready()
        assert self.board_manager is not None  # Type narrowing for mypy

        await self.board_manager.release_work(issue_number, agent_name, reason)

        return {
            "success": True,
            "result": {
                "released": True,
                "issue_number": issue_number,
                "reason": reason,
            },
        }

    async def update_status(self, issue_number: int, status: str) -> Dict[str, Any]:
        """Update issue status"""
        await self._ensure_board_ready()
        assert self.board_manager is not None  # Type narrowing for mypy
        # Convert string to IssueStatus enum
        status_map = {
            "Todo": IssueStatus.TODO,
            "In Progress": IssueStatus.IN_PROGRESS,
            "Blocked": IssueStatus.BLOCKED,
            "Done": IssueStatus.DONE,
            "Abandoned": IssueStatus.ABANDONED,
        }
        issue_status = status_map.get(status)
        if not issue_status:
            return {"success": False, "error": f"Invalid status: {status}"}

        success = await self.board_manager.update_status(issue_number, issue_status)

        return {
            "success": success,
            "result": {
                "updated": success,
                "issue_number": issue_number,
                "status": status,
            },
        }

    async def add_blocker(self, issue_number: int, blocker_number: int) -> Dict[str, Any]:
        """Add blocker dependency"""
        await self._ensure_board_ready()
        assert self.board_manager is not None  # Type narrowing for mypy

        success = await self.board_manager.add_blocker(issue_number, blocker_number)

        return {
            "success": success,
            "result": {
                "added": success,
                "issue": issue_number,
                "blocker": blocker_number,
            },
        }

    async def mark_discovered_from(self, issue_number: int, parent_number: int) -> Dict[str, Any]:
        """Mark parent-child relationship"""
        await self._ensure_board_ready()
        assert self.board_manager is not None  # Type narrowing for mypy

        success = await self.board_manager.mark_discovered_from(issue_number, parent_number)

        return {
            "success": success,
            "result": {
                "marked": success,
                "child": issue_number,
                "parent": parent_number,
            },
        }

    async def get_issue_details(self, issue_number: int) -> Dict[str, Any]:
        """Get full issue details"""
        await self._ensure_board_ready()
        assert self.board_manager is not None  # Type narrowing for mypy

        # Use get_ready_work with specific filter
        # For now, return basic info - full implementation would query GraphQL directly
        return {
            "success": True,
            "result": {
                "issue_number": issue_number,
                "note": "Full details require direct GraphQL query - not yet implemented",
            },
        }

    async def get_dependency_graph(self, issue_number: int) -> Dict[str, Any]:
        """Get dependency graph"""
        await self._ensure_board_ready()
        assert self.board_manager is not None  # Type narrowing for mypy

        # Placeholder - full implementation would build complete graph
        return {
            "success": True,
            "result": {
                "issue_number": issue_number,
                "note": "Dependency graph building not yet fully implemented",
                "blockers": [],
                "blocked": [],
                "parent": None,
                "children": [],
            },
        }

    async def list_agents(self) -> Dict[str, Any]:
        """List enabled agents"""
        await self._ensure_board_ready()
        assert self.board_manager is not None  # Type narrowing for mypy
        enabled_agents = self.config.enabled_agents if self.config else []

        return {
            "success": True,
            "result": {
                "agents": enabled_agents,
                "count": len(enabled_agents),
            },
        }

    async def get_board_config(self) -> Dict[str, Any]:
        """Get board configuration"""
        await self._ensure_board_ready()
        assert self.board_manager is not None  # Type narrowing for mypy
        if not self.config:
            return {"success": False, "error": "Board configuration not loaded"}

        return {
            "success": True,
            "result": {
                "project_number": self.config.project_number,
                "owner": self.config.owner,
                "repository": self.config.repository,
                "claim_timeout": self.config.claim_timeout,
                "claim_renewal_interval": self.config.claim_renewal_interval,
                "enabled_agents": self.config.enabled_agents,
                "auto_discover": self.config.auto_discover,
                "exclude_labels": self.config.exclude_labels,
            },
        }

    async def health_check(self):
        """Enhanced health check with board status"""
        base_health = await super().health_check()

        # Check board manager status
        board_status = "not_initialized"
        if self._initialized and self.board_manager:
            board_status = "healthy"
        elif await self._ensure_initialized():
            board_status = "healthy"

        return {
            **base_health,
            "board_status": board_status,
            "config_loaded": self.config is not None,
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
