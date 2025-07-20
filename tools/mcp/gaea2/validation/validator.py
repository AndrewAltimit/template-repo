"""Gaea2 workflow validator"""

import logging
from typing import Any, Dict, List, Tuple

# Use stubs for now
from ..stubs import (
    Gaea2ConnectionValidator,
    Gaea2ErrorRecovery,
    Gaea2PropertyValidator,
    create_accurate_validator,
    validate_gaea2_project,
)


class Gaea2Validator:
    """Comprehensive Gaea2 workflow validation"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.accurate_validator = create_accurate_validator()
        self.connection_validator = Gaea2ConnectionValidator()
        self.property_validator = Gaea2PropertyValidator()
        self.error_recovery = Gaea2ErrorRecovery()

    async def validate_and_fix(self, workflow: Dict[str, Any], strict_mode: bool = False) -> Dict[str, Any]:
        """Validate and automatically fix a workflow"""

        nodes = workflow.get("nodes", [])
        connections = workflow.get("connections", [])

        # First, use the error recovery system
        recovery_result = self.error_recovery.fix_workflow(nodes, connections)

        # Then validate the fixed workflow
        validation_result = validate_gaea2_project(
            {
                "nodes": recovery_result["nodes"],
                "connections": recovery_result["connections"],
            }
        )

        return {
            "valid": validation_result["valid"],
            "errors": validation_result.get("errors", []),
            "fixed": recovery_result["fixed"],
            "fixes_applied": recovery_result.get("fixes_applied", []),
            "workflow": {
                "nodes": recovery_result["nodes"],
                "connections": recovery_result["connections"],
            },
        }

    async def validate_connections(
        self, nodes: List[Dict[str, Any]], connections: List[Dict[str, Any]]
    ) -> Tuple[bool, List[str]]:
        """Validate connections between nodes"""

        # Create a node lookup map
        node_map = {str(node.get("id", node.get("node_id"))): node for node in nodes}

        errors = []
        for conn in connections:
            is_valid, error = self.connection_validator.validate_connection(conn, node_map)
            if not is_valid and error:
                errors.append(error)

        return len(errors) == 0, errors

    async def validate_properties(self, node_type: str, properties: Dict[str, Any]) -> Tuple[bool, List[str], Dict[str, Any]]:
        """Validate and correct node properties"""

        return self.property_validator.validate_properties(node_type, properties)
