"""Gaea2 project generator"""

import logging
from typing import Any, Dict, List

from mcp_gaea2.validation.gaea2_format_fixes import generate_non_sequential_id

# Import real implementations
from .project_generator import EnhancedGaea2Tools


class Gaea2ProjectGenerator:
    """Generate Gaea2 terrain projects"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.enhanced_tools = EnhancedGaea2Tools()
        # No longer need workflow_tools since we're using enhanced_tools directly

    async def create_project(
        self,
        project_name: str,
        nodes: List[Dict[str, Any]],
        connections: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Create a Gaea2 project structure"""

        # Use the real implementation from enhanced tools
        project_data = await self.enhanced_tools.create_advanced_gaea2_project(
            project_name=project_name, nodes=nodes, connections=connections
        )

        # Ensure we return a proper dict
        if not isinstance(project_data, dict):
            return {"success": False, "error": "Invalid project data"}
        return project_data

    def generate_node_id(self) -> str:
        """Generate a non-sequential node ID"""
        return str(generate_non_sequential_id())
