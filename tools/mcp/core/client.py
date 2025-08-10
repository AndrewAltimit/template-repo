"""MCP Client for interacting with MCP servers"""

import logging
import os
from typing import Any, Dict, Optional

import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# MCP Server endpoints for the modular architecture
MCP_SERVERS = {
    "code_quality": os.getenv("MCP_CODE_QUALITY_URL", "http://localhost:8010"),
    "content_creation": os.getenv("MCP_CONTENT_URL", "http://localhost:8011"),
    "gemini": os.getenv("MCP_GEMINI_URL", "http://localhost:8006"),
    "gaea2": os.getenv("MCP_GAEA2_URL", "http://localhost:8007"),
    "ai_toolkit": os.getenv("MCP_AI_TOOLKIT_URL", "http://localhost:8012"),
    "comfyui": os.getenv("MCP_COMFYUI_URL", "http://localhost:8013"),
    "opencode": os.getenv("MCP_OPENCODE_URL", "http://localhost:8014"),
    "crush": os.getenv("MCP_CRUSH_URL", "http://localhost:8015"),
}


class MCPClient:
    """Client for interacting with MCP servers"""

    def __init__(self, server_name: Optional[str] = None, base_url: Optional[str] = None):
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
        except Exception as e:
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
        except Exception as e:
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
