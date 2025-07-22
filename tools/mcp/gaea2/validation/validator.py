"""Gaea2 workflow validator"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from ..errors.gaea2_error_recovery import Gaea2ErrorRecovery
from .gaea2_accurate_validation import create_accurate_validator
from .gaea2_connection_validator import Gaea2ConnectionValidator
from .gaea2_property_validator import Gaea2PropertyValidator


class Gaea2Validator:
    """Comprehensive Gaea2 workflow validation"""

    # Nodes that must have <= 3 properties to open in Gaea2
    PROPERTY_LIMITED_NODES = {
        "Snow",
        "Beach",
        "Coast",
        "Lakes",
        "Glacier",
        "SeaLevel",
        "LavaFlow",
        "ThermalShatter",
        "Ridge",
        "Strata",
        "Voronoi",
        "Terrace",
    }

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.accurate_validator = create_accurate_validator()
        self.connection_validator = Gaea2ConnectionValidator()
        self.property_validator = Gaea2PropertyValidator()
        self.error_recovery = Gaea2ErrorRecovery()
        self.cli_available = None  # Cache CLI availability status

    async def validate_and_fix(self, workflow: Dict[str, Any], strict_mode: bool = False) -> Dict[str, Any]:
        """Validate and automatically fix a workflow"""

        nodes = workflow.get("nodes", [])
        connections = workflow.get("connections", [])

        # Initialize errors list
        all_errors = []
        warnings = []

        # Step 1: Validate node structure (check for required fields)
        for i, node in enumerate(nodes):
            if "type" not in node:
                all_errors.append(f"Node at index {i} (id: {node.get('id', 'unknown')}) missing required 'type' field")
            if "id" not in node:
                all_errors.append(f"Node at index {i} missing required 'id' field")

        # Step 2: Validate node types
        for node in nodes:
            node_type = node.get("type")
            if node_type and not self.accurate_validator.validate_node_type(node_type):
                all_errors.append(f"Invalid node type '{node_type}' for node id '{node.get('id', 'unknown')}'")

        # Step 3: Validate property count limits for problematic nodes
        for node in nodes:
            node_type = node.get("type")
            if node_type in self.PROPERTY_LIMITED_NODES:
                prop_count = len(node.get("properties", {}))
                if prop_count > 3:
                    all_errors.append(
                        f"Node '{node_type}' (id: {node.get('id', 'unknown')}) has {prop_count} properties. "
                        f"This node type must have <= 3 properties to open in Gaea2."
                    )

        # Step 4: Validate workflow connectivity
        node_ids = {str(node.get("id")) for node in nodes}
        connected_nodes = set()

        for conn in connections:
            source = str(conn.get("source", conn.get("from_node", "")))
            target = str(conn.get("target", conn.get("to_node", "")))

            if source not in node_ids:
                all_errors.append(f"Connection references non-existent source node: {source}")
            else:
                connected_nodes.add(source)

            if target not in node_ids:
                all_errors.append(f"Connection references non-existent target node: {target}")
            else:
                connected_nodes.add(target)

        # Check for orphaned nodes (excluding Export and SatMap which can be endpoints)
        endpoint_types = {"Export", "SatMap", "OutputBuffer"}
        for node in nodes:
            node_id = str(node.get("id"))
            node_type = node.get("type")
            if node_id not in connected_nodes and node_type not in endpoint_types:
                warnings.append(f"Node '{node_type}' (id: {node_id}) is not connected to any other nodes")

        # If there are structural errors, return early in strict mode
        if all_errors and strict_mode:
            return {
                "valid": False,
                "errors": all_errors,
                "warnings": warnings,
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
        if conn_warnings:
            warnings.extend(conn_warnings)

        # For simple workflow validation, we don't use validate_gaea2_project
        # since it expects a full project structure
        is_valid = len(all_errors) == 0 and conn_valid

        return {
            "valid": is_valid,
            "errors": all_errors,
            "warnings": warnings,
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

        result: Tuple[bool, List[str], Dict[str, Any]] = self.property_validator.validate_properties(node_type, properties)
        return result

    async def validate_project_can_open(self, project_path: str, cli_runner=None) -> Dict[str, Any]:
        """Test if a project can actually open in Gaea2 by attempting to run it"""

        if not cli_runner:
            self.logger.warning("CLI runner not provided for project validation")
            return {
                "can_open": None,
                "tested": False,
                "error": "CLI runner not available for validation",
            }

        try:
            # Try to run the project with minimal settings
            result = await cli_runner.run_gaea2_project(
                project_path=project_path,
                resolution="512",  # Use smallest resolution for speed
                format="png",
                timeout=30,  # Short timeout for validation
            )

            # Check if the command succeeded
            if result.get("success", False):
                return {
                    "can_open": True,
                    "tested": True,
                    "execution_time": result.get("execution_time", 0),
                    "output": result.get("stdout", "")[:500],  # First 500 chars of output
                }
            else:
                # Parse the error to determine if it's a file format issue
                stdout = result.get("stdout", "")
                stderr = result.get("stderr", "")
                error_msg = stdout + stderr

                # Common Gaea2 error patterns when files can't open
                cant_open_patterns = [
                    "Failed to load",
                    "Invalid file",
                    "Unable to parse",
                    "Corrupt terrain file",
                    "Unknown node type",
                    "Property error",
                ]

                is_format_error = any(pattern in error_msg for pattern in cant_open_patterns)

                return {
                    "can_open": False,
                    "tested": True,
                    "is_format_error": is_format_error,
                    "error": error_msg[:1000],  # First 1000 chars of error
                }

        except Exception as e:
            self.logger.error(f"Error testing project: {e}")
            return {"can_open": False, "tested": True, "error": str(e)}

    async def validate_workflow_comprehensive(
        self,
        workflow: Dict[str, Any],
        project_path: Optional[str] = None,
        cli_runner=None,
        test_opening: bool = True,
    ) -> Dict[str, Any]:
        """Comprehensive validation including actual Gaea2 opening test"""

        # First do standard validation
        validation_result = await self.validate_and_fix(workflow)

        # If we have a project path and CLI runner, test if it actually opens
        if test_opening and project_path and cli_runner and validation_result["valid"]:
            open_test = await self.validate_project_can_open(project_path, cli_runner)
            validation_result["gaea2_open_test"] = open_test

            # If it can't open, mark as invalid
            if open_test["tested"] and not open_test["can_open"]:
                validation_result["valid"] = False
                validation_result["errors"].append(
                    f"Project validation failed: File cannot be opened in Gaea2. {open_test.get('error', '')}"
                )

        return validation_result
