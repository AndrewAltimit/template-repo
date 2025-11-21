#!/usr/bin/env python3
"""
Comprehensive error handling for Gaea2 MCP operations
"""

import logging
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class ErrorSeverity(Enum):
    """Error severity levels"""

    CRITICAL = "critical"  # Project cannot be used
    ERROR = "error"  # Major issue that needs fixing
    WARNING = "warning"  # Minor issue, project still usable
    INFO = "info"  # Informational, no action needed


class ErrorCategory(Enum):
    """Error categories for better organization"""

    VALIDATION = "validation"
    CONNECTION = "connection"
    PROPERTY = "property"
    STRUCTURE = "structure"
    COMPATIBILITY = "compatibility"
    PERFORMANCE = "performance"


class Gaea2Error:
    """Represents a single error or issue"""

    def __init__(
        self,
        message: str,
        severity: ErrorSeverity,
        category: ErrorCategory,
        node_id: Optional[int] = None,
        property_name: Optional[str] = None,
        suggestion: Optional[str] = None,
        auto_fixable: bool = False,
    ):
        self.message = message
        self.severity = severity
        self.category = category
        self.node_id = node_id
        self.property_name = property_name
        self.suggestion = suggestion
        self.auto_fixable = auto_fixable

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "message": self.message,
            "severity": self.severity.value,
            "category": self.category.value,
            "node_id": self.node_id,
            "property_name": self.property_name,
            "suggestion": self.suggestion,
            "auto_fixable": self.auto_fixable,
        }


class Gaea2ErrorHandler:
    """Comprehensive error handler for Gaea2 operations"""

    def __init__(self):
        self.errors: List[Gaea2Error] = []
        self.auto_fix_enabled = True

    def add_error(self, error: Gaea2Error):
        """Add an error to the collection"""
        self.errors.append(error)

        # Log based on severity
        if error.severity == ErrorSeverity.CRITICAL:
            logger.critical(f"{error.category.value}: {error.message}")
        elif error.severity == ErrorSeverity.ERROR:
            logger.error(f"{error.category.value}: {error.message}")
        elif error.severity == ErrorSeverity.WARNING:
            logger.warning(f"{error.category.value}: {error.message}")
        else:
            logger.info(f"{error.category.value}: {error.message}")

    def clear_errors(self):
        """Clear all errors"""
        self.errors = []

    def get_errors_by_severity(self, severity: ErrorSeverity) -> List[Gaea2Error]:
        """Get all errors of a specific severity"""
        return [e for e in self.errors if e.severity == severity]

    def get_errors_by_category(self, category: ErrorCategory) -> List[Gaea2Error]:
        """Get all errors of a specific category"""
        return [e for e in self.errors if e.category == category]

    def get_errors_for_node(self, node_id: int) -> List[Gaea2Error]:
        """Get all errors for a specific node"""
        return [e for e in self.errors if e.node_id == node_id]

    def has_critical_errors(self) -> bool:
        """Check if there are any critical errors"""
        return any(e.severity == ErrorSeverity.CRITICAL for e in self.errors)

    def get_auto_fixable_errors(self) -> List[Gaea2Error]:
        """Get all auto-fixable errors"""
        return [e for e in self.errors if e.auto_fixable]

    def get_summary(self) -> Dict[str, Any]:
        """Get error summary"""
        return {
            "total_errors": len(self.errors),
            "critical": len(self.get_errors_by_severity(ErrorSeverity.CRITICAL)),
            "errors": len(self.get_errors_by_severity(ErrorSeverity.ERROR)),
            "warnings": len(self.get_errors_by_severity(ErrorSeverity.WARNING)),
            "info": len(self.get_errors_by_severity(ErrorSeverity.INFO)),
            "auto_fixable": len(self.get_auto_fixable_errors()),
            "has_critical": self.has_critical_errors(),
            "by_category": {category.value: len(self.get_errors_by_category(category)) for category in ErrorCategory},
        }

    def validate_node_connections(self, nodes: List[Dict[str, Any]], connections: List[Dict[str, Any]]) -> List[Gaea2Error]:
        """Validate node connections and add errors"""
        errors = []
        node_ids = {node.get("id") for node in nodes}

        # Check for orphaned nodes
        connected_nodes = set()
        for conn in connections:
            connected_nodes.add(conn.get("from_node"))
            connected_nodes.add(conn.get("to_node"))

        orphaned = node_ids - connected_nodes
        for node_id in orphaned:
            node = next((n for n in nodes if n.get("id") == node_id), None)
            if node and node.get("type") not in ["Export", "Unity", "Unreal"]:
                error = Gaea2Error(
                    message=f"Node '{node.get('name', 'Unnamed')}' is not connected to anything",
                    severity=ErrorSeverity.WARNING,
                    category=ErrorCategory.CONNECTION,
                    node_id=node_id,
                    suggestion="Connect this node to the workflow or remove it",
                    auto_fixable=False,
                )
                errors.append(error)
                self.add_error(error)

        # Check for circular dependencies
        for conn in connections:
            if conn.get("from_node") == conn.get("to_node"):
                error = Gaea2Error(
                    message=f"Node {conn.get('from_node')} connects to itself",
                    severity=ErrorSeverity.ERROR,
                    category=ErrorCategory.CONNECTION,
                    node_id=conn.get("from_node"),
                    suggestion="Remove self-connection",
                    auto_fixable=True,
                )
                errors.append(error)
                self.add_error(error)

        # Check for invalid connections
        for conn in connections:
            if conn.get("from_node") not in node_ids:
                error = Gaea2Error(
                    message=f"Connection references non-existent source node: {conn.get('from_node')}",
                    severity=ErrorSeverity.CRITICAL,
                    category=ErrorCategory.CONNECTION,
                    suggestion="Remove this connection or add the missing node",
                    auto_fixable=True,
                )
                errors.append(error)
                self.add_error(error)

            if conn.get("to_node") not in node_ids:
                error = Gaea2Error(
                    message=f"Connection references non-existent target node: {conn.get('to_node')}",
                    severity=ErrorSeverity.CRITICAL,
                    category=ErrorCategory.CONNECTION,
                    suggestion="Remove this connection or add the missing node",
                    auto_fixable=True,
                )
                errors.append(error)
                self.add_error(error)

        return errors

    def validate_property_ranges(self, node_type: str, properties: Dict[str, Any], schema: Dict[str, Any]) -> List[Gaea2Error]:
        """Validate property values against schema ranges"""
        errors: List[Gaea2Error] = []

        if node_type not in schema.get("node_properties", {}):
            return errors

        node_schema = schema["node_properties"][node_type]

        for prop_name, prop_value in properties.items():
            if prop_name in node_schema:
                prop_def = node_schema[prop_name]

                # Check numeric ranges
                if "range" in prop_def and isinstance(prop_value, (int, float)):
                    min_val, max_val = prop_def["range"]
                    if not min_val <= prop_value <= max_val:
                        error = Gaea2Error(
                            message=f"{prop_name} value {prop_value} is outside valid range [{min_val}, {max_val}]",
                            severity=ErrorSeverity.ERROR,
                            category=ErrorCategory.PROPERTY,
                            property_name=prop_name,
                            suggestion=f"Set value between {min_val} and {max_val}",
                            auto_fixable=True,
                        )
                        errors.append(error)
                        self.add_error(error)

                # Check enum values
                if prop_def.get("type") == "enum" and "values" in prop_def:
                    if prop_value not in prop_def["values"]:
                        error = Gaea2Error(
                            message=f"{prop_name} value '{prop_value}' is not valid",
                            severity=ErrorSeverity.ERROR,
                            category=ErrorCategory.PROPERTY,
                            property_name=prop_name,
                            suggestion=f"Use one of: {', '.join(prop_def['values'])}",
                            auto_fixable=True,
                        )
                        errors.append(error)
                        self.add_error(error)

        return errors

    def check_performance_issues(self, nodes: List[Dict[str, Any]], connections: List[Dict[str, Any]]) -> List[Gaea2Error]:
        """Check for potential performance issues"""
        errors = []

        # Count heavy nodes
        heavy_node_types = [
            "Erosion",
            "Erosion2",
            "Wizard",
            "Rivers",
            "Snow",
            "Thermal2",
        ]
        heavy_nodes = [n for n in nodes if n.get("type") in heavy_node_types]

        if len(heavy_nodes) > 5:
            error = Gaea2Error(
                message=f"Project has {len(heavy_nodes)} heavy computation nodes which may cause slow processing",
                severity=ErrorSeverity.WARNING,
                category=ErrorCategory.PERFORMANCE,
                suggestion="Consider reducing the number of erosion/simulation nodes or use lower settings",
                auto_fixable=False,
            )
            errors.append(error)
            self.add_error(error)

        # Check for erosion chains
        erosion_chains = []
        for node in nodes:
            if node.get("type") in ["Erosion", "Erosion2"]:
                node_id = node.get("id")
                if node_id is not None:
                    chain = self._trace_erosion_chain(node_id, nodes, connections)
                    if len(chain) > 3:
                        erosion_chains.append(chain)

        for chain in erosion_chains:
            error = Gaea2Error(
                message=f"Long erosion chain detected with {len(chain)} nodes",
                severity=ErrorSeverity.WARNING,
                category=ErrorCategory.PERFORMANCE,
                suggestion="Consider combining erosion effects or reducing chain length",
                auto_fixable=False,
            )
            errors.append(error)
            self.add_error(error)

        return errors

    def _trace_erosion_chain(
        self,
        start_node_id: int,
        nodes: List[Dict[str, Any]],
        connections: List[Dict[str, Any]],
    ) -> List[int]:
        """Trace erosion chain from a starting node"""
        chain = [start_node_id]
        current = start_node_id

        while True:
            # Find what this node connects to
            next_conn = next((c for c in connections if c.get("from_node") == current), None)
            if not next_conn:
                break

            next_id = next_conn.get("to_node")
            if next_id is None:
                break

            next_node = next((n for n in nodes if n.get("id") == next_id), None)

            if next_node and next_node.get("type") in ["Erosion", "Erosion2"]:
                chain.append(next_id)
                current = next_id
            else:
                break

        return chain

    def auto_fix_errors(
        self,
        nodes: List[Dict[str, Any]],
        connections: List[Dict[str, Any]],
        schema: Dict[str, Any],
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[str]]:
        """Attempt to auto-fix errors where possible"""
        fixes_applied: List[str] = []

        if not self.auto_fix_enabled:
            return nodes, connections, fixes_applied

        # Fix self-connections
        new_connections = []
        for conn in connections:
            if conn.get("from_node") != conn.get("to_node"):
                new_connections.append(conn)
            else:
                fixes_applied.append(f"Removed self-connection on node {conn.get('from_node')}")
        connections = new_connections

        # Fix property ranges
        for node in nodes:
            node_type = node.get("type")
            if node_type in schema.get("node_properties", {}):
                node_schema = schema["node_properties"][node_type]

                for prop_name, prop_def in node_schema.items():
                    if prop_name in node.get("properties", {}):
                        prop_value = node["properties"][prop_name]

                        # Fix numeric ranges
                        if "range" in prop_def and isinstance(prop_value, (int, float)):
                            min_val, max_val = prop_def["range"]
                            if prop_value < min_val:
                                node["properties"][prop_name] = min_val
                                fixes_applied.append(f"Fixed {node.get('name')}.{prop_name}: {prop_value} -> {min_val}")
                            elif prop_value > max_val:
                                node["properties"][prop_name] = max_val
                                fixes_applied.append(f"Fixed {node.get('name')}.{prop_name}: {prop_value} -> {max_val}")

        # Remove connections to non-existent nodes
        valid_node_ids = {n.get("id") for n in nodes}
        new_connections = []
        for conn in connections:
            if conn.get("from_node") in valid_node_ids and conn.get("to_node") in valid_node_ids:
                new_connections.append(conn)
            else:
                fixes_applied.append(f"Removed invalid connection: {conn.get('from_node')} -> {conn.get('to_node')}")
        connections = new_connections

        return nodes, connections, fixes_applied


# Create global error handler instance
error_handler = Gaea2ErrorHandler()
