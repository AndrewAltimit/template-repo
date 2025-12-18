"""Gaea2 Schema Module.

This module provides access to node definitions, property constraints,
and port configurations for Gaea2 terrain generation.

The schema system has two layers:
1. YAML Schema (new, preferred): Single source of truth in nodes.yaml and ports.yaml
2. Python Schema (legacy): Existing definitions in gaea2_schema.py

New code should use the schema_loader functions. The legacy exports are
maintained for backward compatibility.
"""

# === New YAML-based Schema API (preferred) ===
# === Legacy Python Schema Exports (for backward compatibility) ===
# These are imported from gaea2_schema.py which will eventually be deprecated
from .gaea2_schema import (
    # Property definitions
    COMMON_NODE_PROPERTIES,
    # Node type definitions
    NODE_CATEGORIES,
    NODE_PROPERTY_DEFINITIONS,
    VALID_NODE_TYPES,
    # Template functions (will be moved to templates module)
    WORKFLOW_TEMPLATES,
    apply_default_properties,
    create_workflow_from_template,
    get_node_category as legacy_get_node_category,
    get_node_ports as legacy_get_node_ports,
    validate_connection,
    # Validation functions
    validate_node_properties,
    validate_property,
)
from .schema_loader import (
    get_all_node_definitions,
    get_common_properties,
    get_legacy_common_properties,
    get_legacy_node_categories,
    get_legacy_property_definitions,
    # Backward compatibility adapters
    get_legacy_valid_node_types,
    get_node_categories,
    get_node_category,
    get_node_definition,
    get_node_ports,
    get_node_properties,
    get_port_types,
    # Core functions
    get_valid_node_types,
    is_port_compatible,
    validate_property_value,
)

__all__ = [
    # New API
    "get_valid_node_types",
    "get_node_categories",
    "get_all_node_definitions",
    "get_node_definition",
    "get_node_properties",
    "get_node_ports",
    "get_node_category",
    "get_common_properties",
    "get_port_types",
    "is_port_compatible",
    "validate_property_value",
    # Legacy adapters
    "get_legacy_valid_node_types",
    "get_legacy_node_categories",
    "get_legacy_property_definitions",
    "get_legacy_common_properties",
    # Legacy exports (deprecated but maintained for compatibility)
    "NODE_CATEGORIES",
    "VALID_NODE_TYPES",
    "COMMON_NODE_PROPERTIES",
    "NODE_PROPERTY_DEFINITIONS",
    "validate_node_properties",
    "validate_connection",
    "apply_default_properties",
    "legacy_get_node_category",
    "legacy_get_node_ports",
    "WORKFLOW_TEMPLATES",
    "create_workflow_from_template",
    "validate_property",
]
