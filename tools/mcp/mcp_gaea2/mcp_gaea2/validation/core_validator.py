"""Unified Core Validator for Gaea2 Workflows.

This module provides a single entry point for all validation operations,
leveraging the YAML schema as the source of truth for:
- Node type validation
- Property validation with type checking and range enforcement
- Port compatibility checking
- Connection validation

The CoreValidator consolidates functionality from multiple legacy validators
while maintaining backward compatibility.
"""

import logging
from typing import Any, Dict, List, Optional, Set, Tuple

from mcp_gaea2.schema import (
    get_node_category,
    get_node_ports,
    get_node_properties,
    get_valid_node_types,
    is_port_compatible,
    validate_property_value,
)

logger = logging.getLogger(__name__)


class CoreValidator:
    """Unified validator using YAML schema as source of truth.

    This validator provides comprehensive validation for Gaea2 workflows
    including node types, properties, connections, and structure.
    """

    # Nodes with property count restrictions (Gaea2 limitation)
    PROPERTY_LIMITED_NODES: Set[str] = {
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
    MAX_PROPERTIES_FOR_LIMITED = 3

    # Generator nodes (no inputs required)
    GENERATOR_CATEGORIES: Set[str] = {"primitive", "terrain"}

    # Endpoint nodes (don't need to be connected to outputs)
    ENDPOINT_TYPES: Set[str] = {"Export", "SatMap", "OutputBuffer"}

    def __init__(self):
        """Initialize the core validator."""
        self._valid_node_types: Optional[Set[str]] = None

    @property
    def valid_node_types(self) -> Set[str]:
        """Get cached set of valid node types."""
        if self._valid_node_types is None:
            self._valid_node_types = get_valid_node_types()
        return self._valid_node_types

    # === Node Type Validation ===

    def is_valid_node_type(self, node_type: str) -> bool:
        """Check if a node type is valid.

        Args:
            node_type: The node type to validate

        Returns:
            True if node type is valid
        """
        return node_type in self.valid_node_types

    def validate_node_types(self, nodes: List[Dict[str, Any]]) -> List[str]:
        """Validate node types in a workflow.

        Args:
            nodes: List of node dictionaries

        Returns:
            List of error messages
        """
        errors = []
        for node in nodes:
            node_type = node.get("type")
            node_id = node.get("id", node.get("name", "unknown"))

            if not node_type:
                errors.append(f"Node '{node_id}' missing required 'type' field")
            elif not self.is_valid_node_type(node_type):
                errors.append(f"Invalid node type '{node_type}' for node '{node_id}'")

        return errors

    # === Property Validation ===

    def validate_node_properties(
        self,
        node_type: str,
        properties: Dict[str, Any],
        auto_fix: bool = True,
    ) -> Tuple[bool, List[str], List[str], Dict[str, Any]]:
        """Validate and optionally fix node properties.

        Args:
            node_type: The type of node
            properties: Property dict to validate
            auto_fix: Whether to auto-fix invalid values

        Returns:
            Tuple of (is_valid, errors, warnings, fixed_properties)
        """
        errors: List[str] = []
        warnings: List[str] = []
        fixed_props = dict(properties)

        # Get schema-defined properties
        schema_props = get_node_properties(node_type)

        for prop_name, prop_value in properties.items():
            is_valid, error_msg, suggested_fix = validate_property_value(node_type, prop_name, prop_value)

            if not is_valid:
                if auto_fix and suggested_fix is not None:
                    fixed_props[prop_name] = suggested_fix
                    warnings.append(f"Property '{prop_name}' value {prop_value} corrected to {suggested_fix}: {error_msg}")
                else:
                    errors.append(f"Property '{prop_name}': {error_msg}")

        # Check property count for limited nodes
        if node_type in self.PROPERTY_LIMITED_NODES:
            prop_count = len(fixed_props)
            if prop_count > self.MAX_PROPERTIES_FOR_LIMITED:
                # Remove non-essential properties
                schema_props = get_node_properties(node_type)
                essential_props = set(schema_props.keys())

                removed = []
                for prop_name in list(fixed_props.keys()):
                    if prop_name not in essential_props and len(fixed_props) > self.MAX_PROPERTIES_FOR_LIMITED:
                        removed.append(prop_name)
                        del fixed_props[prop_name]

                if removed:
                    warnings.append(
                        f"Node '{node_type}' limited to {self.MAX_PROPERTIES_FOR_LIMITED} properties. "
                        f"Removed: {', '.join(removed)}"
                    )

        return len(errors) == 0, errors, warnings, fixed_props

    def apply_default_properties(
        self,
        node_type: str,
        properties: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Apply default values for missing required properties.

        Args:
            node_type: The type of node
            properties: Existing properties

        Returns:
            Properties dict with defaults applied
        """
        result = dict(properties)
        schema_props = get_node_properties(node_type)

        for prop_name, prop_def in schema_props.items():
            if prop_name not in result and "default" in prop_def:
                result[prop_name] = prop_def["default"]

        return result

    # === Connection Validation ===

    def validate_connection(
        self,
        connection: Dict[str, Any],
        node_map: Dict[str, Dict[str, Any]],
    ) -> Tuple[bool, Optional[str]]:
        """Validate a single connection.

        Args:
            connection: Connection dict with source, target, ports
            node_map: Map of node_id -> node dict

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Extract connection info
        source_id = str(connection.get("source", connection.get("from_node", "")))
        target_id = str(connection.get("target", connection.get("to_node", "")))
        source_port = connection.get("source_port", connection.get("from_port", "Out"))
        target_port = connection.get("target_port", connection.get("to_port", "In"))

        # Check nodes exist
        if source_id not in node_map:
            return False, f"Connection source node '{source_id}' not found"
        if target_id not in node_map:
            return False, f"Connection target node '{target_id}' not found"

        source_node = node_map[source_id]
        target_node = node_map[target_id]

        source_type = source_node.get("type", "")
        target_type = target_node.get("type", "")

        # Get port definitions
        source_ports = get_node_ports(source_type)
        target_ports = get_node_ports(target_type)

        # Find the output port type
        output_port_type = "heightfield"  # Default
        for port in source_ports.get("outputs", []):
            if port.get("name") == source_port:
                output_port_type = port.get("type", "heightfield")
                break

        # Find the input port type
        input_port_type = "heightfield"  # Default
        for port in target_ports.get("inputs", []):
            if port.get("name") == target_port:
                input_port_type = port.get("type", "heightfield")
                break

        # Check compatibility
        if not is_port_compatible(output_port_type, input_port_type):
            return False, (
                f"Port type mismatch: {source_type}.{source_port} ({output_port_type}) "
                f"-> {target_type}.{target_port} ({input_port_type})"
            )

        return True, None

    def validate_connections(
        self,
        nodes: List[Dict[str, Any]],
        connections: List[Dict[str, Any]],
    ) -> Tuple[bool, List[str], List[str]]:
        """Validate all connections in a workflow.

        Args:
            nodes: List of node dicts
            connections: List of connection dicts

        Returns:
            Tuple of (is_valid, errors, warnings)
        """
        errors: List[str] = []
        warnings: List[str] = []

        # Build node map
        node_map = {}
        for node in nodes:
            node_id = str(node.get("id", node.get("name", "")))
            node_map[node_id] = node

        # Validate each connection
        for conn in connections:
            is_valid, error = self.validate_connection(conn, node_map)
            if not is_valid and error:
                errors.append(error)

        # Check for orphaned nodes
        connected_nodes: Set[str] = set()
        for conn in connections:
            source = str(conn.get("source", conn.get("from_node", "")))
            target = str(conn.get("target", conn.get("to_node", "")))
            connected_nodes.add(source)
            connected_nodes.add(target)

        for node_id, node in node_map.items():
            node_type = node.get("type", "")
            category = get_node_category(node_type)

            # Skip checking generators and endpoints
            if category in self.GENERATOR_CATEGORIES:
                continue
            if node_type in self.ENDPOINT_TYPES:
                continue

            if node_id not in connected_nodes:
                warnings.append(f"Node '{node_type}' (id: {node_id}) is not connected")

        return len(errors) == 0, errors, warnings

    # === Workflow Structure Validation ===

    def validate_node_structure(self, nodes: List[Dict[str, Any]]) -> List[str]:
        """Validate basic node structure requirements.

        Args:
            nodes: List of node dicts

        Returns:
            List of error messages
        """
        errors = []
        seen_ids: Set[str] = set()

        for i, node in enumerate(nodes):
            # Check required fields
            if "type" not in node:
                errors.append(f"Node at index {i} missing required 'type' field")

            node_id = node.get("id", node.get("name"))
            if not node_id:
                errors.append(f"Node at index {i} missing required 'id' or 'name' field")
            else:
                # Check for duplicate IDs
                node_id_str = str(node_id)
                if node_id_str in seen_ids:
                    errors.append(f"Duplicate node ID: {node_id_str}")
                seen_ids.add(node_id_str)

        return errors

    # === Full Workflow Validation ===

    def validate_workflow(
        self,
        workflow: Dict[str, Any],
        auto_fix: bool = True,
        strict: bool = False,
    ) -> Dict[str, Any]:
        """Comprehensive workflow validation.

        Args:
            workflow: Complete workflow dict
            auto_fix: Whether to auto-fix issues
            strict: Whether to fail on warnings

        Returns:
            Validation result dict with:
                - valid: bool
                - errors: List[str]
                - warnings: List[str]
                - fixed: bool (whether fixes were applied)
                - fixes_applied: List[str]
                - workflow: Updated workflow dict
        """
        nodes = workflow.get("nodes", [])
        connections = workflow.get("connections", [])

        all_errors: List[str] = []
        all_warnings: List[str] = []
        fixes_applied: List[str] = []
        fixed_nodes = []

        # Structure validation
        structure_errors = self.validate_node_structure(nodes)
        all_errors.extend(structure_errors)

        # Node type validation
        type_errors = self.validate_node_types(nodes)
        all_errors.extend(type_errors)

        # Property validation (with fixes)
        for node in nodes:
            node_type = node.get("type", "")
            node_id = node.get("id", node.get("name", "unknown"))
            properties = node.get("properties", {})

            is_valid, errors, warnings, fixed_props = self.validate_node_properties(node_type, properties, auto_fix=auto_fix)

            all_errors.extend([f"Node '{node_id}': {e}" for e in errors])
            all_warnings.extend([f"Node '{node_id}': {w}" for w in warnings])

            # Build fixed node
            fixed_node = dict(node)
            if auto_fix and fixed_props != properties:
                fixed_node["properties"] = fixed_props
                fixes_applied.append(f"Fixed properties for node '{node_id}'")

            fixed_nodes.append(fixed_node)

        # Connection validation
        conn_valid, conn_errors, conn_warnings = self.validate_connections(fixed_nodes, connections)
        all_errors.extend(conn_errors)
        all_warnings.extend(conn_warnings)

        # Determine validity
        is_valid = len(all_errors) == 0
        if strict and all_warnings:
            is_valid = False

        return {
            "valid": is_valid,
            "errors": all_errors,
            "warnings": all_warnings,
            "fixed": len(fixes_applied) > 0,
            "fixes_applied": fixes_applied,
            "workflow": {
                "nodes": fixed_nodes,
                "connections": connections,
            },
        }


# === Factory Functions ===


def create_core_validator() -> CoreValidator:
    """Create a new CoreValidator instance.

    Returns:
        Configured CoreValidator
    """
    return CoreValidator()


def validate_workflow(
    workflow: Dict[str, Any],
    auto_fix: bool = True,
    strict: bool = False,
) -> Dict[str, Any]:
    """Convenience function for workflow validation.

    Args:
        workflow: Workflow dict to validate
        auto_fix: Whether to auto-fix issues
        strict: Whether to fail on warnings

    Returns:
        Validation result dict
    """
    validator = create_core_validator()
    return validator.validate_workflow(workflow, auto_fix=auto_fix, strict=strict)


def validate_node_type(node_type: str) -> bool:
    """Check if a node type is valid.

    Args:
        node_type: Node type to check

    Returns:
        True if valid
    """
    return node_type in get_valid_node_types()


def validate_properties(
    node_type: str,
    properties: Dict[str, Any],
) -> Tuple[bool, List[str], Dict[str, Any]]:
    """Validate node properties.

    Args:
        node_type: Node type
        properties: Properties to validate

    Returns:
        Tuple of (is_valid, errors, fixed_properties)
    """
    validator = create_core_validator()
    is_valid, errors, warnings, fixed = validator.validate_node_properties(node_type, properties)
    # Combine errors and warnings for simple API
    all_issues = errors + warnings
    return is_valid, all_issues, fixed
