"""YAML Schema Loader for Gaea2 Node Definitions.

This module provides a centralized way to load and access node definitions
from YAML schema files. It serves as the single source of truth for:
- Valid node types
- Node properties and their constraints
- Port definitions and compatibility
- Node categories

The loader uses caching to ensure efficient repeated access.
"""

from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, cast

import yaml

# Schema directory location
SCHEMA_DIR = Path(__file__).parent


class SchemaLoader:
    """Loader for Gaea2 YAML schema files with caching."""

    _instance: Optional["SchemaLoader"] = None
    _node_schema: Optional[Dict[str, Any]] = None
    _port_schema: Optional[Dict[str, Any]] = None

    def __new__(cls) -> "SchemaLoader":
        """Singleton pattern for schema loader."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def _load_yaml(self, filename: str) -> Dict[str, Any]:
        """Load a YAML file from the schema directory."""
        filepath = SCHEMA_DIR / filename
        if not filepath.exists():
            raise FileNotFoundError(f"Schema file not found: {filepath}")
        with open(filepath, encoding="utf-8") as f:
            return cast(Dict[str, Any], yaml.safe_load(f))

    @property
    def node_schema(self) -> Dict[str, Any]:
        """Load and cache the node schema."""
        if self._node_schema is None:
            self._node_schema = self._load_yaml("nodes.yaml")
        return self._node_schema

    @property
    def port_schema(self) -> Dict[str, Any]:
        """Load and cache the port schema."""
        if self._port_schema is None:
            self._port_schema = self._load_yaml("ports.yaml")
        return self._port_schema

    def reload(self) -> None:
        """Force reload of all schema files (useful for development)."""
        self._node_schema = None
        self._port_schema = None
        # Clear the module-level caches
        get_valid_node_types.cache_clear()
        get_node_categories.cache_clear()
        get_all_node_definitions.cache_clear()


# Global loader instance
_loader = SchemaLoader()


@lru_cache(maxsize=1)
def get_valid_node_types() -> Set[str]:
    """Get set of all valid node types from YAML schema.

    Returns:
        Set of valid node type names
    """
    schema = _loader.node_schema
    node_types: Set[str] = set()

    # Get explicitly defined nodes
    if "nodes" in schema:
        node_types.update(schema["nodes"].keys())

    # Get nodes from categories (may include nodes not yet fully defined)
    if "categories" in schema:
        for category_data in schema["categories"].values():
            if "nodes" in category_data:
                node_types.update(category_data["nodes"])

    return node_types


@lru_cache(maxsize=1)
def get_node_categories() -> Dict[str, List[str]]:
    """Get node categories and their node types.

    Returns:
        Dict mapping category name to list of node types
    """
    schema = _loader.node_schema
    categories: Dict[str, List[str]] = {}

    if "categories" in schema:
        for cat_name, cat_data in schema["categories"].items():
            if "nodes" in cat_data:
                categories[cat_name] = cat_data["nodes"]

    return categories


@lru_cache(maxsize=1)
def get_all_node_definitions() -> Dict[str, Dict[str, Any]]:
    """Get all node definitions from the schema.

    Returns:
        Dict mapping node type to its full definition
    """
    schema = _loader.node_schema
    return cast(Dict[str, Dict[str, Any]], schema.get("nodes", {}))


def get_node_definition(node_type: str) -> Optional[Dict[str, Any]]:
    """Get the full definition for a specific node type.

    Args:
        node_type: The node type name (e.g., "Mountain", "Erosion2")

    Returns:
        Node definition dict or None if not found
    """
    nodes = get_all_node_definitions()
    return nodes.get(node_type)


def get_node_properties(node_type: str) -> Dict[str, Dict[str, Any]]:
    """Get property definitions for a node type.

    Args:
        node_type: The node type name

    Returns:
        Dict of property name to property definition
    """
    node_def = get_node_definition(node_type)
    if node_def and "properties" in node_def:
        return cast(Dict[str, Dict[str, Any]], node_def["properties"])
    return {}


def get_node_ports(node_type: str) -> Dict[str, List[Dict[str, Any]]]:
    """Get port definitions for a node type.

    Checks in order:
    1. Node definition in nodes.yaml
    2. Port overrides in ports.yaml
    3. Default ports based on category

    Args:
        node_type: The node type name

    Returns:
        Dict with 'inputs' and 'outputs' lists
    """
    # Check node definition first
    node_def = get_node_definition(node_type)
    if node_def and "ports" in node_def:
        return cast(Dict[str, List[Dict[str, Any]]], node_def["ports"])

    # Check port overrides
    port_schema = _loader.port_schema
    overrides = port_schema.get("node_port_overrides", {})
    if node_type in overrides:
        override = overrides[node_type]
        return {
            "inputs": override.get("inputs", [{"name": "In", "type": "heightfield"}]),
            "outputs": override.get("outputs", [{"name": "Out", "type": "heightfield"}]),
        }

    # Get category and use default ports
    if node_def and "category" in node_def:
        category = node_def["category"]
        defaults = port_schema.get("default_ports", {})

        # Map categories to port defaults
        category_map = {
            "primitive": "generator",
            "terrain": "generator",
            "modify": "processor",
            "surface": "processor",
            "simulate": "processor",
            "derive": "processor",
            "colorize": "colorizer",
            "output": "exporter",
            "utility": "processor",
        }

        port_category = category_map.get(category, "processor")
        if port_category in defaults:
            return cast(Dict[str, List[Dict[str, Any]]], defaults[port_category])

    # Ultimate fallback
    return {
        "inputs": [{"name": "In", "type": "heightfield"}],
        "outputs": [{"name": "Out", "type": "heightfield"}],
    }


def get_node_category(node_type: str) -> Optional[str]:
    """Get the category for a node type.

    Args:
        node_type: The node type name

    Returns:
        Category name or None if not found
    """
    # Check node definition
    node_def = get_node_definition(node_type)
    if node_def and "category" in node_def:
        return cast(str, node_def["category"])

    # Search categories
    categories = get_node_categories()
    for cat_name, nodes in categories.items():
        if node_type in nodes:
            return cat_name

    return None


def get_common_properties() -> Dict[str, Dict[str, Any]]:
    """Get common property definitions shared across nodes.

    Returns:
        Dict of property name to property definition
    """
    schema = _loader.node_schema
    return cast(Dict[str, Dict[str, Any]], schema.get("common_properties", {}))


def get_port_types() -> Dict[str, Dict[str, Any]]:
    """Get port type definitions.

    Returns:
        Dict of port type name to definition
    """
    port_schema = _loader.port_schema
    return cast(Dict[str, Dict[str, Any]], port_schema.get("port_types", {}))


def is_port_compatible(from_type: str, to_type: str) -> bool:
    """Check if two port types are compatible for connection.

    Args:
        from_type: Source port type
        to_type: Destination port type

    Returns:
        True if connection is valid
    """
    port_types = get_port_types()

    # Check explicit compatibility
    from_def = port_types.get(from_type, {})
    compatible = from_def.get("compatible_with", [from_type])

    return to_type in compatible


def validate_property_value(
    node_type: str,
    prop_name: str,
    value: Any,
) -> tuple[bool, Optional[str], Optional[Any]]:
    """Validate a property value against schema constraints.

    Args:
        node_type: The node type
        prop_name: The property name
        value: The value to validate

    Returns:
        Tuple of (is_valid, error_message, suggested_fix)
    """
    props = get_node_properties(node_type)
    if prop_name not in props:
        # Check common properties
        common = get_common_properties()
        if prop_name not in common:
            return True, None, None  # Unknown property, allow it
        prop_def = common[prop_name]
    else:
        prop_def = props[prop_name]

    prop_type = prop_def.get("type", "float")

    # Type validation
    if prop_type == "int":
        if not isinstance(value, (int, float)):
            return False, f"Expected int, got {type(value).__name__}", prop_def.get("default")
        value = int(value)

    elif prop_type == "float":
        if not isinstance(value, (int, float)):
            return False, f"Expected float, got {type(value).__name__}", prop_def.get("default")
        value = float(value)

    elif prop_type == "bool":
        if not isinstance(value, bool):
            return False, f"Expected bool, got {type(value).__name__}", prop_def.get("default")

    elif prop_type == "enum":
        options = prop_def.get("options", [])
        if value not in options:
            return False, f"Invalid enum value '{value}', expected one of {options}", prop_def.get("default")

    elif prop_type == "string":
        if not isinstance(value, str):
            return False, f"Expected string, got {type(value).__name__}", prop_def.get("default")

    # Range validation for numeric types
    if prop_type in ("int", "float") and "range" in prop_def:
        range_def = prop_def["range"]
        min_val, max_val = range_def[0], range_def[1]

        if value < min_val:
            return False, f"Value {value} below minimum {min_val}", min_val
        if value > max_val:
            return False, f"Value {value} above maximum {max_val}", max_val

    return True, None, None


# === Backward Compatibility Adapters ===
# These functions provide compatibility with existing code that uses
# the old gaea2_schema.py module


def get_legacy_valid_node_types() -> Set[str]:
    """Adapter for existing VALID_NODE_TYPES usage."""
    return get_valid_node_types()


def get_legacy_node_categories() -> Dict[str, List[str]]:
    """Adapter for existing NODE_CATEGORIES usage."""
    return get_node_categories()


def get_legacy_property_definitions() -> Dict[str, Dict[str, Any]]:
    """Adapter for existing NODE_PROPERTY_DEFINITIONS usage.

    Converts YAML format to the format expected by existing code.
    """
    nodes = get_all_node_definitions()
    result: Dict[str, Dict[str, Any]] = {}

    for node_type, node_def in nodes.items():
        if "properties" in node_def:
            # Convert range format from [min, max] to {min, max}
            props = {}
            for prop_name, prop_def in node_def["properties"].items():
                converted = dict(prop_def)
                if "range" in converted and isinstance(converted["range"], list):
                    converted["range"] = {
                        "min": converted["range"][0],
                        "max": converted["range"][1],
                    }
                if "options" in converted:
                    # Keep options as-is for enum types
                    pass
                props[prop_name] = converted
            result[node_type] = props

    return result


def get_legacy_common_properties() -> Dict[str, Dict[str, Any]]:
    """Adapter for existing COMMON_NODE_PROPERTIES usage."""
    common = get_common_properties()
    result: Dict[str, Dict[str, Any]] = {}

    for prop_name, prop_def in common.items():
        converted = dict(prop_def)
        if "range" in converted and isinstance(converted["range"], list):
            converted["range"] = {
                "min": converted["range"][0],
                "max": converted["range"][1],
            }
        result[prop_name] = converted

    return result
