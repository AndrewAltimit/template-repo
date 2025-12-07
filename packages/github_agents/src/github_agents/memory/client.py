"""Memory client for GitHub agents.

This client communicates with the AgentCore Memory MCP server
to store and retrieve memories for AI agents.
"""

import asyncio
import json
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class MemoryClient:
    """Client for interacting with AgentCore Memory MCP server.

    The client uses docker-compose to run the MCP server and
    communicates via stdin/stdout in JSON-RPC format.
    """

    def __init__(
        self,
        provider: str = "chromadb",
        docker_compose_file: str = "./docker-compose.yml",
    ):
        """Initialize memory client.

        Args:
            provider: Memory provider ('chromadb' or 'agentcore')
            docker_compose_file: Path to docker-compose.yml
        """
        self.provider = provider
        self.docker_compose_file = docker_compose_file
        self._enabled = self._check_enabled()

    def _check_enabled(self) -> bool:
        """Check if memory integration is enabled."""
        # Can be disabled via environment variable
        if os.environ.get("DISABLE_AGENT_MEMORY", "").lower() == "true":
            logger.info("Agent memory disabled via DISABLE_AGENT_MEMORY")
            return False
        return True

    async def _call_mcp_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Call an MCP tool via docker-compose.

        Args:
            tool_name: Name of the MCP tool to call
            arguments: Tool arguments

        Returns:
            Tool result or None on error
        """
        if not self._enabled:
            return None

        # Build the Python command to call the tool
        python_code = f"""
import asyncio
import json
from mcp_agentcore_memory.server import AgentCoreMemoryServer

async def call_tool():
    server = AgentCoreMemoryServer()
    result = await server.call_tool("{tool_name}", {json.dumps(arguments)})
    print(json.dumps(result))

asyncio.run(call_tool())
"""

        try:
            # Run via docker-compose
            result = await asyncio.create_subprocess_exec(
                "docker-compose",
                "-f",
                self.docker_compose_file,
                "--profile",
                "memory",
                "run",
                "--rm",
                "-T",
                "mcp-agentcore-memory",
                "python",
                "-c",
                python_code,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**os.environ, "MEMORY_PROVIDER": self.provider},
            )

            stdout, stderr = await asyncio.wait_for(result.communicate(), timeout=30.0)

            if result.returncode != 0:
                logger.error("MCP tool call failed: %s", stderr.decode())
                return None

            # Parse the JSON output
            output = stdout.decode().strip()
            if output:
                # Find the last JSON object in output (skip docker warnings)
                lines = output.split("\n")
                for line in reversed(lines):
                    line = line.strip()
                    if line.startswith("{"):
                        parsed: Dict[str, Any] = json.loads(line)
                        return parsed

            return None

        except asyncio.TimeoutError:
            logger.error("MCP tool call timed out")
            return None
        except Exception as e:
            logger.error("MCP tool call error: %s", e)
            return None

    async def store_event(
        self,
        content: str,
        actor_id: str,
        session_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Store a short-term memory event.

        Args:
            content: Event content to store
            actor_id: Agent identifier (e.g., 'issue-monitor', 'pr-monitor')
            session_id: Session identifier (e.g., issue number, PR number)

        Returns:
            Result dict with event_id on success, None on error
        """
        return await self._call_mcp_tool(
            "store_event",
            {
                "content": content,
                "actor_id": actor_id,
                "session_id": session_id,
            },
        )

    async def store_facts(
        self,
        facts: List[str],
        namespace: str,
        source: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Store long-term memory facts.

        Args:
            facts: List of facts to store
            namespace: Namespace for organization (e.g., 'codebase/patterns')
            source: Source attribution (e.g., 'PR #42')

        Returns:
            Result dict with created count on success, None on error
        """
        return await self._call_mcp_tool(
            "store_facts",
            {
                "facts": facts,
                "namespace": namespace,
                "source": source or "github-agent",
            },
        )

    async def search_memories(
        self,
        query: str,
        namespace: str,
        top_k: int = 5,
    ) -> Optional[Dict[str, Any]]:
        """Search memories using semantic query.

        Args:
            query: Search query
            namespace: Namespace to search
            top_k: Maximum results to return

        Returns:
            Result dict with memories list on success, None on error
        """
        return await self._call_mcp_tool(
            "search_memories",
            {
                "query": query,
                "namespace": namespace,
                "top_k": top_k,
            },
        )

    async def list_session_events(
        self,
        actor_id: str,
        session_id: str,
        limit: int = 50,
    ) -> Optional[Dict[str, Any]]:
        """List events from a specific session.

        Args:
            actor_id: Agent identifier
            session_id: Session identifier
            limit: Maximum events to return

        Returns:
            Result dict with events list on success, None on error
        """
        return await self._call_mcp_tool(
            "list_session_events",
            {
                "actor_id": actor_id,
                "session_id": session_id,
                "limit": limit,
            },
        )

    async def health_check(self) -> bool:
        """Check if memory service is healthy.

        Returns:
            True if healthy, False otherwise
        """
        result = await self._call_mcp_tool("memory_status", {})
        return result is not None and result.get("status") == "connected"
