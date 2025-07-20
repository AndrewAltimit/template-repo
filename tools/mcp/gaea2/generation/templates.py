"""Gaea2 workflow templates"""

import logging
from typing import Any, Dict, List, Optional

# Use stubs for now
from ..stubs import WORKFLOW_TEMPLATES, create_workflow_from_template


class Gaea2Templates:
    """Manage Gaea2 workflow templates"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.templates = WORKFLOW_TEMPLATES

    async def get_template(self, template_name: str) -> Optional[Dict[str, Any]]:
        """Get a workflow template by name"""
        if template_name not in self.templates:
            return None

        # Use existing implementation
        return create_workflow_from_template(template_name)

    def list_templates(self) -> List[str]:
        """List available template names"""
        return list(self.templates.keys())

    def get_template_info(self, template_name: str) -> Optional[Dict[str, Any]]:
        """Get information about a template"""
        if template_name not in self.templates:
            return None

        template = self.templates[template_name]
        return {
            "name": template_name,
            "node_count": len(template.get("nodes", [])),
            "connection_count": len(template.get("connections", [])),
            "description": f"Template for {template_name.replace('_', ' ')}",
        }
