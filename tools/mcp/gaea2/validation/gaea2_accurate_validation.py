#!/usr/bin/env python3
"""
Accurate Gaea2 validation module using the complete schema.
This replaces the previous validation with deterministic checks based on documentation.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class AccurateGaea2Validator:
    """Validator using the complete Gaea2 schema from documentation"""

    def __init__(self):
        # Load the complete schema
        schema_path = Path(__file__).parent / "gaea2_complete_schema.json"
        if schema_path.exists():
            with open(schema_path) as f:
                self.schema = json.load(f)
        else:
            # Fallback to embedded schema
            from automation.analysis.generate_gaea2_schema import GAEA2_COMPLETE_SCHEMA

            self.schema = GAEA2_COMPLETE_SCHEMA
            # Convert set to list if needed
            if isinstance(self.schema["valid_node_types"], set):
                self.schema["valid_node_types"] = list(self.schema["valid_node_types"])

    def validate_node_type(self, node_type: str) -> bool:
        """Check if a node type is valid"""
        return node_type in self.schema["valid_node_types"]

    def get_node_properties(self, node_type: str) -> Dict[str, Any]:
        """Get property definitions for a node type"""
        # First check node-specific properties
        if node_type in self.schema["node_properties"]:
            properties = self.schema["node_properties"][node_type]
            assert isinstance(properties, dict)
            return properties

        # Fall back to common properties for nodes without specific definitions
        common_props = self.schema["common_properties"]
        assert isinstance(common_props, dict)
        return common_props

    def validate_and_coerce_property(self, node_type: str, prop_name: str, prop_value: Any) -> Tuple[bool, Optional[str], Any]:
        """
        Validate and coerce a property value for a node type.
        Returns (is_valid, error_message, corrected_value)
        """
        node_props = self.get_node_properties(node_type)

        # Check if property exists for this node
        if prop_name not in node_props:
            # Check common properties
            if prop_name in self.schema["common_properties"]:
                prop_def = self.schema["common_properties"][prop_name]
            else:
                # Unknown property - log warning but allow
                logger.warning(f"Unknown property '{prop_name}' for node type '{node_type}'")
                return True, None, prop_value
        else:
            prop_def = node_props[prop_name]

        prop_type = prop_def["type"]

        # Type validation and coercion
        if prop_type == "int":
            if isinstance(prop_value, float):
                if prop_value.is_integer():
                    prop_value = int(prop_value)
                else:
                    # Round with warning
                    logger.warning(f"{node_type}.{prop_name}: Rounding float {prop_value} to int")
                    prop_value = int(round(prop_value))
            elif isinstance(prop_value, str) and prop_value.isdigit():
                prop_value = int(prop_value)
            elif not isinstance(prop_value, int):
                return False, f"Property '{prop_name}' must be an integer", None

            # Range check
            if "range" in prop_def:
                min_val, max_val = prop_def["range"]
                if not min_val <= prop_value <= max_val:
                    return (
                        False,
                        f"Value {prop_value} outside range [{min_val}, {max_val}]",
                        None,
                    )

        elif prop_type == "float":
            if not isinstance(prop_value, (int, float)):
                return False, f"Property '{prop_name}' must be numeric", None
            prop_value = float(prop_value)

            # Range check
            if "range" in prop_def:
                min_val, max_val = prop_def["range"]
                if not min_val <= prop_value <= max_val:
                    return (
                        False,
                        f"Value {prop_value} outside range [{min_val}, {max_val}]",
                        None,
                    )

        elif prop_type == "bool":
            if not isinstance(prop_value, bool):
                # Coerce common boolean representations
                if prop_value in [0, 1, "0", "1", "true", "false", "True", "False"]:
                    prop_value = prop_value in [1, "1", "true", "True", True]
                else:
                    return False, f"Property '{prop_name}' must be boolean", None

        elif prop_type == "enum":
            if "values" not in prop_def:
                logger.warning(f"Enum property '{prop_name}' missing values definition")
                return True, None, prop_value

            if prop_value not in prop_def["values"]:
                return (
                    False,
                    f"Value '{prop_value}' not in allowed values: {prop_def['values']}",
                    None,
                )

        elif prop_type == "float2":
            if isinstance(prop_value, dict):
                if "X" not in prop_value or "Y" not in prop_value:
                    return False, f"Property '{prop_name}' must have X and Y keys", None
                # Ensure X and Y are floats
                prop_value = {"X": float(prop_value["X"]), "Y": float(prop_value["Y"])}
            elif isinstance(prop_value, (list, tuple)) and len(prop_value) >= 2:
                prop_value = {"X": float(prop_value[0]), "Y": float(prop_value[1])}
            else:
                return (
                    False,
                    f"Property '{prop_name}' must be a dict with X,Y or a list/tuple",
                    None,
                )

        elif prop_type == "string":
            prop_value = str(prop_value)

        else:
            # Unknown type, pass through
            logger.warning(f"Unknown property type '{prop_type}' for {node_type}.{prop_name}")

        return True, None, prop_value

    def validate_node(self, node_type: str, properties: Dict[str, Any]) -> Tuple[bool, List[str], Dict[str, Any]]:
        """
        Validate all properties for a specific node type.
        Returns (is_valid, error_messages, corrected_properties)
        """
        if not self.validate_node_type(node_type):
            return False, [f"Invalid node type: {node_type}"], {}

        errors = []
        corrected = {}

        for prop_name, prop_value in properties.items():
            is_valid, error, corrected_value = self.validate_and_coerce_property(node_type, prop_name, prop_value)

            if not is_valid:
                errors.append(f"{node_type}.{prop_name}: {error}")
            else:
                corrected[prop_name] = corrected_value

        # Add default values for missing required properties
        node_props = self.get_node_properties(node_type)
        for prop_name, prop_def in node_props.items():
            if prop_name not in corrected and "default" in prop_def:
                corrected[prop_name] = prop_def["default"]

        return len(errors) == 0, errors, corrected

    def validate_project(
        self,
        nodes: List[Dict[str, Any]],
        connections: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Validate a complete project configuration"""
        errors: List[str] = []
        warnings: List[str] = []
        corrected_nodes = []

        # Validate nodes
        for node in nodes:
            node_type = node.get("type")
            if not node_type:
                errors.append(f"Node missing 'type' field: {node}")
                continue

            is_valid, node_errors, corrected_props = self.validate_node(node_type, node.get("properties", {}))

            if not is_valid:
                errors.extend(node_errors)

            corrected_node = node.copy()
            corrected_node["properties"] = corrected_props
            corrected_nodes.append(corrected_node)

        # Validate connections
        if connections:
            node_ids = {n.get("id") for n in nodes}
            for conn in connections:
                if conn.get("from_node") not in node_ids:
                    errors.append(f"Connection references non-existent source node: {conn.get('from_node')}")
                if conn.get("to_node") not in node_ids:
                    errors.append(f"Connection references non-existent target node: {conn.get('to_node')}")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "corrected_nodes": corrected_nodes,
            "stats": {
                "total_nodes": len(nodes),
                "total_connections": len(connections) if connections else 0,
                "error_count": len(errors),
                "warning_count": len(warnings),
            },
        }


def create_accurate_validator():
    """Create an instance of the accurate validator"""
    return AccurateGaea2Validator()
