#!/usr/bin/env python3
"""
Enhanced Gaea2 validation module with comprehensive type checking
Based on accurate property definitions extracted from Gaea2 documentation
"""

from typing import Any, Dict, List, Optional, Tuple


class Gaea2Validator:
    """Comprehensive validator for Gaea2 project files"""

    def __init__(self, node_properties: Dict[str, Any]):
        """Initialize with node property definitions"""
        self.node_properties = node_properties

    def validate_property_value(self, prop_name: str, prop_value: Any, prop_def: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Validate a single property value against its definition

        Returns:
            Tuple of (is_valid, error_message)
        """
        prop_type = prop_def.get("type", "numeric")

        if prop_type == "numeric" or prop_type == "float":
            if not isinstance(prop_value, (int, float)):
                return False, f"Expected numeric value, got {type(prop_value).__name__}"
            # Check range if specified
            if "range" in prop_def:
                min_val = prop_def["range"].get("min", float("-inf"))
                max_val = prop_def["range"].get("max", float("inf"))
                if not min_val <= prop_value <= max_val:
                    return (
                        False,
                        f"Value {prop_value} outside range [{min_val}, {max_val}]",
                    )

        elif prop_type == "int":
            # Accept both int and float for integer properties
            # This matches Gaea's behavior where many whole numbers are stored as floats
            if isinstance(prop_value, float):
                # Check if float is actually a whole number
                if prop_value.is_integer():
                    prop_value = int(prop_value)
                else:
                    return (
                        False,
                        f"Expected integer value, got float {prop_value} with decimal part",
                    )
            elif not isinstance(prop_value, int):
                return False, f"Expected integer value, got {type(prop_value).__name__}"

            # Check range if specified
            if "range" in prop_def:
                min_val = prop_def["range"].get("min", 0)
                max_val = prop_def["range"].get("max", 999999)
                if not min_val <= prop_value <= max_val:
                    return (
                        False,
                        f"Value {prop_value} outside range [{min_val}, {max_val}]",
                    )

        elif prop_type == "bool" or prop_type == "boolean":
            if not isinstance(prop_value, bool):
                return False, f"Expected boolean value, got {type(prop_value).__name__}"

        elif prop_type == "string":
            if not isinstance(prop_value, str):
                return False, f"Expected string value, got {type(prop_value).__name__}"

        elif prop_type == "enum":
            valid_values = prop_def.get("values", [])
            if prop_value not in valid_values:
                return (
                    False,
                    f"Invalid enum value '{prop_value}'. Valid options: {', '.join(valid_values)}",
                )

        elif prop_type == "float2":
            # Validate Float2 type (2D vector with X and Y components)
            if not isinstance(prop_value, dict):
                return (
                    False,
                    f"Expected Float2 dict with X,Y components, got {type(prop_value).__name__}",
                )
            if "X" not in prop_value or "Y" not in prop_value:
                return False, "Float2 value must have 'X' and 'Y' components"
            if not isinstance(prop_value["X"], (int, float)) or not isinstance(prop_value["Y"], (int, float)):
                return False, "Float2 X and Y components must be numeric"
            # Check range if specified
            if "range" in prop_def:
                min_val = prop_def["range"].get("min", float("-inf"))
                max_val = prop_def["range"].get("max", float("inf"))
                if not (min_val <= prop_value["X"] <= max_val and min_val <= prop_value["Y"] <= max_val):
                    return (
                        False,
                        f"Float2 values outside range [{min_val}, {max_val}]",
                    )

        return True, ""

    def validate_node_properties(self, node_type: str, properties: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate all properties for a node

        Returns:
            Dictionary with validation results
        """
        errors = []
        warnings = []
        fixed_properties = {}

        # Get node definition
        node_def = self.node_properties.get(node_type, {})
        all_props = {}

        # Merge direct properties and sectioned properties
        if "properties" in node_def:
            all_props.update(node_def["properties"])

        if "sections" in node_def:
            for section_name, section_props in node_def["sections"].items():
                all_props.update(section_props)

        # Validate each property
        for prop_name, prop_value in properties.items():
            if prop_name in all_props:
                prop_def = all_props[prop_name]
                is_valid, error_msg = self.validate_property_value(prop_name, prop_value, prop_def)
                if not is_valid:
                    errors.append(f"{node_type}.{prop_name}: {error_msg}")
                else:
                    fixed_properties[prop_name] = prop_value
            else:
                warnings.append(f"Unknown property '{prop_name}' for node type {node_type}")
                # Still include it in case it's valid but undocumented
                fixed_properties[prop_name] = prop_value

        # Add missing required properties with defaults
        for prop_name, prop_def in all_props.items():
            if prop_name not in fixed_properties and "default" in prop_def:
                fixed_properties[prop_name] = prop_def["default"]

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "fixed_properties": fixed_properties,
        }

    def validate_workflow(
        self,
        nodes: List[Dict[str, Any]],
        connections: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Validate an entire workflow

        Returns:
            Dictionary with comprehensive validation results
        """
        from ..utils.gaea2_connection_utils import normalize_connections

        # Normalize connections to standard format
        if connections:
            connections = normalize_connections(connections)

        all_errors = []
        all_warnings = []
        fixed_nodes = []

        for node in nodes:
            node_type = node.get("type", "Unknown")
            node_name = node.get("name", "Unnamed")
            properties = node.get("properties", {})

            # Validate properties
            validation_result = self.validate_node_properties(node_type, properties)

            if not validation_result["valid"]:
                for error in validation_result["errors"]:
                    all_errors.append(f"Node '{node_name}': {error}")

            for warning in validation_result["warnings"]:
                all_warnings.append(f"Node '{node_name}': {warning}")

            # Create fixed node
            fixed_node = node.copy()
            fixed_node["properties"] = validation_result["fixed_properties"]
            fixed_nodes.append(fixed_node)

        # Validate connections if provided
        if connections:
            node_ids = {node.get("id", i) for i, node in enumerate(nodes)}
            for conn in connections:
                if conn.get("from_node") not in node_ids:
                    all_errors.append(f"Connection references non-existent source node: {conn.get('from_node')}")
                if conn.get("to_node") not in node_ids:
                    all_errors.append(f"Connection references non-existent target node: {conn.get('to_node')}")

        return {
            "valid": len(all_errors) == 0,
            "errors": all_errors,
            "warnings": all_warnings,
            "fixed_nodes": fixed_nodes,
            "node_count": len(nodes),
            "connection_count": len(connections) if connections else 0,
        }


# Import node properties from our generated file
try:
    from gaea_node_properties import GAEA_NODE_PROPERTIES
except ImportError:
    # Fallback for when running in different context
    GAEA_NODE_PROPERTIES = {}


def create_validator():
    """Create a validator instance with the latest node properties"""
    return Gaea2Validator(GAEA_NODE_PROPERTIES)


# Example usage and tests
if __name__ == "__main__":
    validator = create_validator()

    # Test 1: Validate Mountain node with old property names
    print("Test 1: Mountain with old property names")
    result = validator.validate_node_properties(
        "Mountain",
        {"Scale": 1.0, "Height": 0.7, "Style": "Rocky", "ReduceDetails": False},
    )
    print(f"Valid: {result['valid']}")
    print(f"Errors: {result['errors']}")
    print()

    # Test 2: Validate Mountain node with correct property names
    print("Test 2: Mountain with correct property names")
    result = validator.validate_node_properties(
        "Mountain",
        {"Scale": 1.0, "Height": 0.7, "Style": "Eroded", "Reduce Details": False},
    )
    print(f"Valid: {result['valid']}")
    print(f"Errors: {result['errors']}")
    print()

    # Test 3: Validate SatMap with various issues
    print("Test 3: SatMap with mixed issues")
    result = validator.validate_node_properties(
        "SatMap",
        {
            "Library": "Mountain",  # Invalid enum
            "LibraryItem": "Swiss Alps",  # Should be int
            "Enhance": 0.7,  # Should be enum
        },
    )
    print(f"Valid: {result['valid']}")
    print(f"Errors: {result['errors']}")
    print()

    # Test 4: Validate complete workflow
    print("Test 4: Complete workflow validation")
    test_nodes = [
        {
            "id": 100,
            "type": "Mountain",
            "name": "PrimaryMountain",
            "properties": {"Scale": 1.5, "Height": 0.85, "Style": "Alpine"},
        },
        {
            "id": 101,
            "type": "Erosion",
            "name": "NaturalErosion",
            "properties": {
                "Duration": 0.05,
                "RockSoftness": 0.4,  # Old name
                "Strength": 0.6,
                "FeatureScale": 2000,  # Old name
            },
        },
    ]
    result = validator.validate_workflow(test_nodes)
    print(f"Valid: {result['valid']}")
    print(f"Errors: {result['errors']}")
    print(f"Warnings: {result['warnings']}")
