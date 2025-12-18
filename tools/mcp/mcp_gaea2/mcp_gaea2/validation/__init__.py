"""Gaea2 Validation Modules.

This module provides validation functionality for Gaea2 workflows.

The validation system has two layers:
1. CoreValidator (new, preferred): YAML schema-based validation
2. Gaea2Validator (legacy): Existing validation with error recovery

New code should use CoreValidator. The legacy Gaea2Validator is
maintained for backward compatibility and its error recovery features.
"""

# === New YAML-based Core Validator (preferred) ===
from .core_validator import (
    CoreValidator,
    create_core_validator,
    validate_node_type,
    validate_properties,
    validate_workflow,
)

# === Legacy Validator (for backward compatibility) ===
from .validator import Gaea2Validator

__all__ = [
    # New API
    "CoreValidator",
    "create_core_validator",
    "validate_workflow",
    "validate_node_type",
    "validate_properties",
    # Legacy API
    "Gaea2Validator",
]
