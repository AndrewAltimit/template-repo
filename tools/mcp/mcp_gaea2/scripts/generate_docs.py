#!/usr/bin/env python3
"""Generate documentation from YAML schema files.

This script generates comprehensive markdown documentation for Gaea2 nodes,
properties, and templates from the YAML schema files.

Usage:
    python scripts/generate_docs.py                # Generate all docs
    python scripts/generate_docs.py --nodes        # Generate node reference only
    python scripts/generate_docs.py --templates    # Generate template docs only
    python scripts/generate_docs.py --output path  # Specify output directory
"""

import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any, Dict, List

# Add the parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp_gaea2.schema import (
    get_all_node_definitions,
    get_common_properties,
    get_node_categories,
    get_node_ports,
    get_port_types,
    get_valid_node_types,
)
from mcp_gaea2.templates import (
    get_all_templates,
    get_template_categories,
    get_template_metadata,
)


def generate_node_reference(output_path: Path) -> None:
    """Generate the node reference documentation.

    Args:
        output_path: Path to write the markdown file
    """
    lines: List[str] = []

    # Header
    lines.append("# Gaea2 Node Reference")
    lines.append("")
    lines.append("> Auto-generated from YAML schema. Do not edit manually.")
    lines.append(f"> Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    lines.append("")

    # Table of Contents
    lines.append("## Table of Contents")
    lines.append("")

    categories = get_node_categories()
    for cat_name in sorted(categories.keys()):
        cat_display = cat_name.replace("_", " ").title()
        lines.append(f"- [{cat_display}](#{cat_name})")

    lines.append("- [Common Properties](#common-properties)")
    lines.append("- [Port Types](#port-types)")
    lines.append("")

    # Overview
    node_types = get_valid_node_types()
    lines.append("## Overview")
    lines.append("")
    lines.append(f"Total nodes: **{len(node_types)}**")
    lines.append("")
    lines.append("| Category | Count | Description |")
    lines.append("|----------|-------|-------------|")

    for cat_name in sorted(categories.keys()):
        cat_nodes = categories[cat_name]
        cat_display = cat_name.replace("_", " ").title()
        # Get category description from schema if available
        desc = _get_category_description(cat_name)
        lines.append(f"| {cat_display} | {len(cat_nodes)} | {desc} |")

    lines.append("")

    # Node sections by category
    all_defs = get_all_node_definitions()

    for cat_name in sorted(categories.keys()):
        cat_display = cat_name.replace("_", " ").title()
        lines.append(f"## {cat_display}")
        lines.append("")
        lines.append(f'<a name="{cat_name}"></a>')
        lines.append("")

        cat_nodes = sorted(categories[cat_name])

        for node_type in cat_nodes:
            node_def = all_defs.get(node_type, {})
            lines.extend(_generate_node_section(node_type, node_def))

    # Common Properties
    lines.append("## Common Properties")
    lines.append("")
    lines.append("These properties are shared across multiple node types.")
    lines.append("")

    common = get_common_properties()
    lines.append("| Property | Type | Default | Range | Description |")
    lines.append("|----------|------|---------|-------|-------------|")

    for prop_name, prop_def in sorted(common.items()):
        prop_type = prop_def.get("type", "unknown")
        default = prop_def.get("default", "-")
        prop_range = _format_range(prop_def.get("range"))
        desc = prop_def.get("description", "")
        lines.append(f"| {prop_name} | {prop_type} | {default} | {prop_range} | {desc} |")

    lines.append("")

    # Port Types
    lines.append("## Port Types")
    lines.append("")

    port_types = get_port_types()
    lines.append("| Type | Description | Compatible With |")
    lines.append("|------|-------------|-----------------|")

    for port_name, port_def in sorted(port_types.items()):
        desc = port_def.get("description", "")
        compatible = ", ".join(port_def.get("compatible_with", []))
        lines.append(f"| {port_name} | {desc} | {compatible} |")

    lines.append("")

    # Write file
    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Generated: {output_path}")


def _get_category_description(cat_name: str) -> str:
    """Get description for a category."""
    descriptions = {
        "primitive": "Basic noise and shape generators",
        "terrain": "Natural terrain feature generators",
        "modify": "Height field modification nodes",
        "surface": "Surface detail and texture nodes",
        "simulate": "Physical simulation nodes (erosion, etc.)",
        "derive": "Data derivation and analysis nodes",
        "colorize": "Color map generation nodes",
        "output": "Export and output nodes",
        "utility": "Utility and helper nodes",
    }
    return descriptions.get(cat_name, "")


def _generate_node_section(node_type: str, node_def: Dict[str, Any]) -> List[str]:
    """Generate documentation section for a single node."""
    lines: List[str] = []

    lines.append(f"### {node_type}")
    lines.append("")

    # Description
    desc = node_def.get("description", "")
    if desc:
        lines.append(f"{desc}")
        lines.append("")

    # Ports
    ports = get_node_ports(node_type)
    inputs = ports.get("inputs", [])
    outputs = ports.get("outputs", [])

    if inputs or outputs:
        lines.append("**Ports:**")
        lines.append("")

        if inputs:
            lines.append("*Inputs:*")
            for port in inputs:
                port_name = port.get("name", "In")
                port_type = port.get("type", "heightfield")
                optional = " (optional)" if port.get("optional") else ""
                port_desc = port.get("description", "")
                desc_text = f" - {port_desc}" if port_desc else ""
                lines.append(f"- `{port_name}` ({port_type}){optional}{desc_text}")
            lines.append("")

        if outputs:
            lines.append("*Outputs:*")
            for port in outputs:
                port_name = port.get("name", "Out")
                port_type = port.get("type", "heightfield")
                port_desc = port.get("description", "")
                desc_text = f" - {port_desc}" if port_desc else ""
                lines.append(f"- `{port_name}` ({port_type}){desc_text}")
            lines.append("")

    # Properties
    props = node_def.get("properties", {})
    if props:
        lines.append("**Properties:**")
        lines.append("")
        lines.append("| Property | Type | Default | Range/Options |")
        lines.append("|----------|------|---------|---------------|")

        for prop_name, prop_def in sorted(props.items()):
            prop_type = prop_def.get("type", "unknown")
            default = prop_def.get("default", "-")

            if prop_type == "enum":
                options = prop_def.get("options", [])
                range_opts = ", ".join(str(o) for o in options[:5])
                if len(options) > 5:
                    range_opts += "..."
            else:
                range_opts = _format_range(prop_def.get("range"))

            lines.append(f"| {prop_name} | {prop_type} | {default} | {range_opts} |")

        lines.append("")

    lines.append("---")
    lines.append("")

    return lines


def _format_range(range_val: Any) -> str:
    """Format a range value for display."""
    if range_val is None:
        return "-"
    if isinstance(range_val, list) and len(range_val) == 2:
        return f"{range_val[0]} - {range_val[1]}"
    return str(range_val)


def generate_template_reference(output_path: Path) -> None:
    """Generate the template reference documentation.

    Args:
        output_path: Path to write the markdown file
    """
    lines: List[str] = []

    # Header
    lines.append("# Gaea2 Template Reference")
    lines.append("")
    lines.append("> Auto-generated from YAML schema. Do not edit manually.")
    lines.append(f"> Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    lines.append("")

    # Overview
    templates = get_all_templates()
    categories = get_template_categories()

    lines.append("## Overview")
    lines.append("")
    lines.append(f"Total templates: **{len(templates)}**")
    lines.append("")

    # Table of Contents by Category
    lines.append("## Templates by Category")
    lines.append("")

    for cat_name, cat_info in sorted(categories.items()):
        cat_display = cat_name.replace("_", " ").title()
        desc = cat_info.get("description", "")
        template_list = cat_info.get("templates", [])

        lines.append(f"### {cat_display}")
        lines.append("")
        if desc:
            lines.append(f"{desc}")
            lines.append("")

        for template_name in template_list:
            metadata = get_template_metadata(template_name)
            if metadata:
                desc = metadata.get("description", "")
                difficulty = metadata.get("difficulty", "intermediate")
                node_count = metadata.get("node_count", 0)
                lines.append(f"- **{template_name}** ({difficulty}) - {desc} [{node_count} nodes]")

        lines.append("")

    # Detailed Template Sections
    lines.append("## Template Details")
    lines.append("")

    for template_name, template_def in sorted(templates.items()):
        lines.extend(_generate_template_section(template_name, template_def))

    # Write file
    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Generated: {output_path}")


def _generate_template_section(template_name: str, template_def: Dict[str, Any]) -> List[str]:
    """Generate documentation section for a single template."""
    lines: List[str] = []

    display_name = template_name.replace("_", " ").title()
    lines.append(f"### {display_name}")
    lines.append("")

    # Metadata
    desc = template_def.get("description", "")
    category = template_def.get("category", "general")
    difficulty = template_def.get("difficulty", "intermediate")

    if desc:
        lines.append(f"{desc}")
        lines.append("")

    lines.append(f"- **Category:** {category}")
    lines.append(f"- **Difficulty:** {difficulty}")
    lines.append("")

    # Node list
    nodes = template_def.get("nodes", [])
    if nodes:
        lines.append("**Nodes:**")
        lines.append("")
        lines.append("| # | Type | Name | Key Properties |")
        lines.append("|---|------|------|----------------|")

        for i, node in enumerate(nodes, 1):
            node_type = node.get("type", "Unknown")
            node_name = node.get("name", "-")
            props = node.get("properties", {})

            # Format key properties
            key_props = []
            for k, v in list(props.items())[:3]:
                key_props.append(f"{k}={v}")
            props_str = ", ".join(key_props) if key_props else "-"

            lines.append(f"| {i} | {node_type} | {node_name} | {props_str} |")

        lines.append("")

    lines.append("---")
    lines.append("")

    return lines


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Generate documentation from YAML schema")
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=Path(__file__).parent.parent / "docs",
        help="Output directory for generated documentation",
    )
    parser.add_argument("--nodes", action="store_true", help="Generate node reference only")
    parser.add_argument("--templates", action="store_true", help="Generate template reference only")

    args = parser.parse_args()

    # Create output directory
    args.output.mkdir(parents=True, exist_ok=True)

    # Generate docs
    generate_all = not args.nodes and not args.templates

    if generate_all or args.nodes:
        generate_node_reference(args.output / "GAEA2_NODE_REFERENCE.md")

    if generate_all or args.templates:
        generate_template_reference(args.output / "GAEA2_TEMPLATE_REFERENCE.md")

    print("Documentation generation complete!")


if __name__ == "__main__":
    main()
