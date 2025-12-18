"""Gaea2 Templates Module.

This module provides access to workflow templates for terrain generation.

The template system has two layers:
1. YAML Templates (new, preferred): Single source of truth in templates.yaml
2. Python Templates (legacy): Existing definitions in gaea2_schema.py

New code should use the template_loader functions. The legacy WORKFLOW_TEMPLATES
is maintained for backward compatibility.
"""

# === New YAML-based Template API (preferred) ===
from .template_loader import (
    create_workflow_from_template_yaml,
    get_all_templates,
    # Backward compatibility adapters
    get_legacy_workflow_templates,
    get_template,
    get_template_categories,
    get_template_metadata,
    # Core functions
    get_template_names,
    get_templates_by_category,
    get_templates_by_difficulty,
    instantiate_template,
    list_templates,
)

__all__ = [
    # New API
    "get_template_names",
    "get_template_categories",
    "get_all_templates",
    "get_template",
    "get_template_metadata",
    "get_templates_by_category",
    "get_templates_by_difficulty",
    "instantiate_template",
    "list_templates",
    # Legacy adapters
    "get_legacy_workflow_templates",
    "create_workflow_from_template_yaml",
]
