"""Gaea2 project generator"""

import json  # noqa: F401
import logging
import uuid  # noqa: F401
from datetime import datetime  # noqa: F401
from pathlib import Path  # noqa: F401
from typing import Any, Dict, List, Optional  # noqa: F401

# Use stub implementations for now to avoid circular dependencies
from .stub_implementations import (  # noqa: F401
    EnhancedGaea2Tools,
    Gaea2WorkflowTools,
    apply_format_fixes,
    fix_property_names,
    generate_non_sequential_id,
)


class Gaea2ProjectGenerator:
    """Generate Gaea2 terrain projects"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.enhanced_tools = EnhancedGaea2Tools()
        self.workflow_tools = Gaea2WorkflowTools()

    async def create_project(
        self,
        project_name: str,
        nodes: List[Dict[str, Any]],
        connections: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Create a Gaea2 project structure"""

        # Use existing implementation from workflow tools
        result = await self.workflow_tools.create_gaea2_project(
            project_name=project_name, nodes=nodes, connections=connections
        )

        if result.get("success"):
            return result["project_data"]
        else:
            raise Exception(result.get("error", "Failed to create project"))

    def generate_node_id(self) -> str:
        """Generate a non-sequential node ID"""
        return generate_non_sequential_id()
