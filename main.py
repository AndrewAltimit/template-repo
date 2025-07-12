#!/usr/bin/env python3
"""
Main application entry point
Example of integrating with MCP tools
"""

import asyncio
import logging
import os
from typing import Any, Dict

import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class MCPClient:
    """Client for interacting with MCP server"""

    def __init__(self, base_url: str = None):
        self.base_url = base_url or os.getenv("MCP_SERVER_URL", "http://localhost:8000")

    def execute_tool(self, tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute an MCP tool"""
        url = f"{self.base_url}/tools/execute"

        try:
            response = requests.post(url, json={"tool": tool, "arguments": arguments})
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error executing tool {tool}: {e}")
            return {"success": False, "error": str(e)}

    def list_tools(self) -> Dict[str, Any]:
        """List available MCP tools"""
        url = f"{self.base_url}/tools"

        try:
            response = requests.get(url)
            response.raise_for_status()
            return response.json()
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
    """Example workflow using MCP tools"""
    client = MCPClient()

    # Check server health
    logger.info("Checking MCP server health...")
    if not client.health_check():
        logger.error("MCP server is not available!")
        return

    logger.info("MCP server is healthy")

    # List available tools
    logger.info("Fetching available tools...")
    tools = client.list_tools()
    logger.info(f"Available tools: {', '.join(tools.keys())}")

    # Example 1: Format check
    logger.info("\n--- Running format check ---")
    result = client.execute_tool("format_check", {"path": ".", "language": "python"})

    if result.get("success"):
        formatted = result["result"].get("formatted", False)
        logger.info(
            f"Code formatting: {'✅ Correct' if formatted else '⚠️  Needs formatting'}"
        )

    # Example 2: Consult AI
    logger.info("\n--- Consulting AI ---")
    result = client.execute_tool(
        "consult_gemini",
        {
            "question": "What are the best practices for Python async programming?",
            "context": "I'm building a web application with FastAPI",
        },
    )

    if result.get("success"):
        response = result["result"].get("response", "")
        logger.info(f"AI Response: {response[:200]}...")

    # Example 3: Create documentation
    logger.info("\n--- Creating documentation ---")
    latex_content = r"""
\documentclass{article}
\title{Project Documentation}
\author{MCP Client}
\date{\today}
\begin{document}
\maketitle
\section{Introduction}
This document was generated using MCP tools.
\end{document}
    """

    result = client.execute_tool(
        "compile_latex", {"content": latex_content, "format": "pdf"}
    )

    if result.get("success"):
        output_path = result["result"].get("output_path", "")
        logger.info(f"Documentation created: {output_path}")


def main():
    """Main entry point"""
    logger.info("🚀 Starting MCP Template Application")

    # Run example workflow
    asyncio.run(example_workflow())

    logger.info("\n✨ Application completed successfully!")


if __name__ == "__main__":
    main()
