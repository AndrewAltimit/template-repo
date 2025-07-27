#!/usr/bin/env python3
"""
Main application entry point
Example of integrating with modular MCP services
"""

import asyncio
import logging
import os
from typing import Any, Dict, Optional

import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# MCP Server endpoints for the modular architecture
MCP_SERVERS = {
    "code_quality": os.getenv("MCP_CODE_QUALITY_URL", "http://localhost:8010"),
    "content_creation": os.getenv("MCP_CONTENT_URL", "http://localhost:8011"),
    "gemini": os.getenv("MCP_GEMINI_URL", "http://localhost:8006"),
    "gaea2": os.getenv("MCP_GAEA2_URL", "http://localhost:8007"),
}


class MCPClient:
    """Client for interacting with MCP servers"""

    def __init__(
        self, server_name: Optional[str] = None, base_url: Optional[str] = None
    ):
        if base_url:
            self.base_url = base_url
        elif server_name and server_name in MCP_SERVERS:
            self.base_url = MCP_SERVERS[server_name]
        else:
            # Default to code quality server for backward compatibility
            self.base_url = MCP_SERVERS["code_quality"]

    def execute_tool(self, tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute an MCP tool"""
        url = f"{self.base_url}/tools/execute"

        try:
            response = requests.post(url, json={"tool": tool, "arguments": arguments})
            response.raise_for_status()
            result = response.json()
            assert isinstance(result, dict)  # Type assertion for mypy
            return result
        except requests.exceptions.RequestException as e:
            logger.error(f"Error executing tool {tool}: {e}")
            return {"success": False, "error": str(e)}

    def list_tools(self) -> Dict[str, Any]:
        """List available MCP tools"""
        url = f"{self.base_url}/tools"

        try:
            response = requests.get(url)
            response.raise_for_status()
            result = response.json()
            assert isinstance(result, dict)  # Type assertion for mypy
            return result
        except requests.exceptions.RequestException as e:
            logger.error(f"Error listing tools: {e}")
            return {}

    def health_check(self) -> bool:
        """Check if MCP server is healthy"""
        url = f"{self.base_url}/health"

        try:
            response = requests.get(url, timeout=5)
            return response.status_code == 200
        except Exception:
            return False


async def example_workflow():
    """Example workflow using modular MCP services"""

    # Check health of all servers
    logger.info("Checking MCP servers health...")
    for server_name, url in MCP_SERVERS.items():
        client = MCPClient(server_name=server_name)
        if client.health_check():
            logger.info(f"✅ {server_name} server is healthy at {url}")
        else:
            logger.warning(f"⚠️  {server_name} server is not available at {url}")

    # Example 1: Code Quality - Format check
    logger.info("\n--- Code Quality Server: Format check ---")
    code_client = MCPClient(server_name="code_quality")
    result = code_client.execute_tool(
        "format_check", {"path": ".", "language": "python"}
    )

    if result.get("success"):
        formatted = result["result"].get("formatted", False)
        logger.info(
            f"Code formatting: {'✅ Correct' if formatted else '⚠️  Needs formatting'}"
        )

    # Example 2: Gemini Server - Consult AI
    logger.info("\n--- Gemini Server: AI Consultation ---")
    gemini_client = MCPClient(server_name="gemini")

    if gemini_client.health_check():
        result = gemini_client.execute_tool(
            "consult_gemini",
            {
                "prompt": "What are the best practices for Python async programming?",
                "context": {"source": "main.py example"},
            },
        )

        if result.get("success"):
            response = result["result"].get("response", "")
            logger.info(f"AI Response: {response[:200]}...")
    else:
        logger.warning("Gemini server not available - skipping AI consultation")

    # Example 3: Content Creation - LaTeX compilation
    logger.info("\n--- Content Creation Server: LaTeX compilation ---")
    content_client = MCPClient(server_name="content_creation")

    latex_content = r"""
\documentclass{article}
\title{MCP Services Documentation}
\author{Modular MCP System}
\date{\today}
\begin{document}
\maketitle
\section{Introduction}
This document was generated using the modular MCP content creation service.
\end{document}
    """

    result = content_client.execute_tool(
        "compile_latex", {"content": latex_content, "format": "pdf"}
    )

    if result.get("success"):
        output_path = result["result"].get("output_path", "")
        logger.info(f"Documentation created: {output_path}")

    # Example 4: Gaea2 Server - Terrain validation (if available)
    logger.info("\n--- Gaea2 Server: Workflow validation ---")
    gaea2_client = MCPClient(server_name="gaea2")

    if gaea2_client.health_check():
        # Simple terrain workflow
        workflow = {
            "nodes": [
                {"id": 1, "type": "Mountain", "position": {"x": 0, "y": 0}},
                {"id": 2, "type": "Export", "position": {"x": 200, "y": 0}},
            ],
            "connections": [
                {"from_node": 1, "to_node": 2, "from_port": "Out", "to_port": "In"}
            ],
        }

        result = gaea2_client.execute_tool(
            "validate_and_fix_workflow", {"workflow": workflow}
        )
        if result.get("success"):
            logger.info("✅ Gaea2 workflow validation successful")
    else:
        logger.warning("Gaea2 server not available - skipping terrain validation")


def main():
    """Main entry point"""
    logger.info("🚀 Starting MCP Template Application")

    # Run example workflow
    asyncio.run(example_workflow())

    logger.info("\n✨ Application completed successfully!")


if __name__ == "__main__":
    main()
