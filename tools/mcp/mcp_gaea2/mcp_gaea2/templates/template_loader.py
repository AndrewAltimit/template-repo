"""YAML Template Loader for Gaea2 Workflows.

This module provides functions to load and instantiate workflow templates
from YAML files. It serves as the single source of truth for:
- Available workflow templates
- Template categories and metadata
- Template instantiation with customization

The loader uses caching for efficient repeated access.
"""

import copy
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, cast

import yaml

# Template directory location
TEMPLATE_DIR = Path(__file__).parent


class TemplateLoader:
    """Loader for Gaea2 YAML template files with caching."""

    _instance: Optional["TemplateLoader"] = None
    _template_schema: Optional[Dict[str, Any]] = None

    def __new__(cls) -> "TemplateLoader":
        """Singleton pattern for template loader."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def _load_yaml(self, filename: str) -> Dict[str, Any]:
        """Load a YAML file from the template directory."""
        filepath = TEMPLATE_DIR / filename
        if not filepath.exists():
            raise FileNotFoundError(f"Template file not found: {filepath}")
        with open(filepath, encoding="utf-8") as f:
            return cast(Dict[str, Any], yaml.safe_load(f))

    @property
    def template_schema(self) -> Dict[str, Any]:
        """Load and cache the template schema."""
        if self._template_schema is None:
            self._template_schema = self._load_yaml("templates.yaml")
        return self._template_schema

    def reload(self) -> None:
        """Force reload of template files (useful for development)."""
        self._template_schema = None
        # Clear module-level caches
        get_template_names.cache_clear()
        get_template_categories.cache_clear()
        get_all_templates.cache_clear()


# Global loader instance
_loader = TemplateLoader()


@lru_cache(maxsize=1)
def get_template_names() -> Set[str]:
    """Get set of all available template names.

    Returns:
        Set of template names
    """
    schema = _loader.template_schema
    templates = schema.get("templates", {})
    return set(templates.keys())


@lru_cache(maxsize=1)
def get_template_categories() -> Dict[str, Dict[str, Any]]:
    """Get template categories with their metadata.

    Returns:
        Dict mapping category name to category info
    """
    schema = _loader.template_schema
    return cast(Dict[str, Dict[str, Any]], schema.get("categories", {}))


@lru_cache(maxsize=1)
def get_all_templates() -> Dict[str, Dict[str, Any]]:
    """Get all template definitions.

    Returns:
        Dict mapping template name to its full definition
    """
    schema = _loader.template_schema
    return cast(Dict[str, Dict[str, Any]], schema.get("templates", {}))


def get_template(name: str) -> Optional[Dict[str, Any]]:
    """Get a specific template definition.

    Args:
        name: Template name (e.g., "basic_terrain", "volcanic_island")

    Returns:
        Template definition dict or None if not found
    """
    templates = get_all_templates()
    return templates.get(name)


def get_template_metadata(name: str) -> Optional[Dict[str, Any]]:
    """Get metadata for a template (description, category, difficulty).

    Args:
        name: Template name

    Returns:
        Dict with description, category, difficulty or None
    """
    template = get_template(name)
    if template is None:
        return None

    return {
        "name": name,
        "description": template.get("description", ""),
        "category": template.get("category", "general"),
        "difficulty": template.get("difficulty", "intermediate"),
        "node_count": len(template.get("nodes", [])),
    }


def get_templates_by_category(category: str) -> List[str]:
    """Get all template names in a category.

    Args:
        category: Category name (e.g., "mountain", "volcanic")

    Returns:
        List of template names in the category
    """
    categories = get_template_categories()
    cat_info = categories.get(category, {})
    return cast(List[str], cat_info.get("templates", []))


def get_templates_by_difficulty(difficulty: str) -> List[str]:
    """Get all template names of a given difficulty.

    Args:
        difficulty: Difficulty level ("beginner", "intermediate", "advanced")

    Returns:
        List of template names with the specified difficulty
    """
    templates = get_all_templates()
    result = []
    for name, template in templates.items():
        if template.get("difficulty") == difficulty:
            result.append(name)
    return result


def instantiate_template(
    name: str,
    customizations: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Instantiate a template with optional customizations.

    Creates a copy of the template nodes with any property
    overrides applied.

    Args:
        name: Template name
        customizations: Optional dict of node_name -> {property: value}
            Example: {"BaseTerrain": {"Scale": 2.0, "Height": 0.9}}

    Returns:
        List of node definitions ready for workflow creation

    Raises:
        ValueError: If template not found
    """
    template = get_template(name)
    if template is None:
        raise ValueError(f"Template not found: {name}")

    # Deep copy to avoid modifying the cached template
    nodes: List[Dict[str, Any]] = copy.deepcopy(template.get("nodes", []))

    # Apply customizations
    if customizations:
        for node in nodes:
            node_name = node.get("name")
            if node_name in customizations:
                custom_props = customizations[node_name]
                if "properties" not in node:
                    node["properties"] = {}
                node["properties"].update(custom_props)

    return nodes


def list_templates(
    category: Optional[str] = None,
    difficulty: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """List templates with optional filtering.

    Args:
        category: Optional category filter
        difficulty: Optional difficulty filter

    Returns:
        List of template metadata dicts
    """
    templates = get_all_templates()
    result = []

    for name, template in templates.items():
        # Apply filters
        if category and template.get("category") != category:
            continue
        if difficulty and template.get("difficulty") != difficulty:
            continue

        result.append(
            {
                "name": name,
                "description": template.get("description", ""),
                "category": template.get("category", "general"),
                "difficulty": template.get("difficulty", "intermediate"),
                "node_count": len(template.get("nodes", [])),
            }
        )

    return result


# === Backward Compatibility Adapters ===
# These functions provide compatibility with existing code that uses
# the WORKFLOW_TEMPLATES dict from gaea2_schema.py


def get_legacy_workflow_templates() -> Dict[str, List[Dict[str, Any]]]:
    """Adapter for existing WORKFLOW_TEMPLATES usage.

    Returns templates in the legacy format (dict of name -> list of nodes).
    """
    templates = get_all_templates()
    result: Dict[str, List[Dict[str, Any]]] = {}

    for name, template in templates.items():
        # Convert to legacy format (just the nodes list)
        nodes = template.get("nodes", [])
        # Convert boolean 'enabled' to Python format if needed
        legacy_nodes = []
        for node in nodes:
            node_copy = dict(node)
            if "save_definition" in node_copy:
                save_def = dict(node_copy["save_definition"])
                # YAML loads 'true' as True already, so this is just for safety
                if "enabled" in save_def:
                    save_def["enabled"] = bool(save_def["enabled"])
                node_copy["save_definition"] = save_def
            legacy_nodes.append(node_copy)
        result[name] = legacy_nodes

    return result


def create_workflow_from_template_yaml(
    template_name: str,
    project_name: str = "terrain_project",
    output_directory: str = "./output",
) -> Dict[str, Any]:
    """Create a workflow structure from a template.

    This is a YAML-based replacement for create_workflow_from_template
    in gaea2_schema.py.

    Args:
        template_name: Name of the template
        project_name: Name for the project
        output_directory: Output directory for exports

    Returns:
        Complete workflow dict ready for JSON serialization
    """
    nodes = instantiate_template(template_name)
    if not nodes:
        raise ValueError(f"Template '{template_name}' not found or empty")

    # Update export node paths if present
    for node in nodes:
        if node.get("type") == "Export" and "save_definition" in node:
            save_def = node["save_definition"]
            if "filename" in save_def:
                save_def["filename"] = f"{output_directory}/{save_def['filename']}"

    # Build connections based on node order (linear chain by default)
    connections = []
    for i in range(len(nodes) - 1):
        # Simple linear connections - more complex templates should define explicit connections
        source = nodes[i]["name"]
        target = nodes[i + 1]["name"]

        # Skip connection if target is a generator (no input)
        target_type = nodes[i + 1].get("type", "")
        if target_type in (
            "Mountain",
            "Volcano",
            "Island",
            "Canyon",
            "Perlin",
            "Voronoi",
            "Cellular",
            "Gradient",
            "Constant",
            "PortalReceive",
            "Strata",
        ):
            continue

        connections.append(
            {
                "source": source,
                "target": target,
                "source_port": "Out",
                "target_port": "In",
            }
        )

    return {
        "name": project_name,
        "nodes": nodes,
        "connections": connections,
        "version": "2.2.6.0",
    }
