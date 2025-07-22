"""Gaea2 workflow validator"""

import logging
from typing import Any, Dict, List, Tuple

from ..errors.gaea2_error_recovery import Gaea2ErrorRecovery
from .gaea2_accurate_validation import create_accurate_validator
from .gaea2_connection_validator import Gaea2ConnectionValidator
from .gaea2_property_validator import Gaea2PropertyValidator


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

        # Initialize errors list
        all_errors = []

        # Validate node structure (check for required fields)
        for i, node in enumerate(nodes):
            if "type" not in node:
                all_errors.append(f"Node at index {i} (id: {node.get('id', 'unknown')}) missing required 'type' field")
            if "id" not in node:
                all_errors.append(f"Node at index {i} missing required 'id' field")

        # If there are structural errors, return early
        if all_errors and strict_mode:
            return {
                "valid": False,
                "errors": all_errors,
                "fixed": False,
                "fixes_applied": [],
                "workflow": workflow,
            }

        # Use the error recovery system to fix issues
        recovery_result = self.error_recovery.fix_workflow(nodes, connections)

        # Validate connections for circular dependencies
        conn_valid, conn_errors, conn_warnings = self.connection_validator.validate_connections(
            recovery_result["nodes"], recovery_result["connections"]
        )

        # Add connection errors to the main error list
        if conn_errors:
            all_errors.extend(conn_errors)

        # For simple workflow validation, we don't use validate_gaea2_project
        # since it expects a full project structure
        is_valid = len(all_errors) == 0 and conn_valid

        return {
            "valid": is_valid,
            "errors": all_errors,
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
