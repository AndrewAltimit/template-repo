#!/usr/bin/env python3
"""
Check which nodes from reference files we might be missing in our implementation
"""

import json


def check_node_coverage():
    """Compare nodes in references vs our implementation"""

    # Load empirical schema
    with open("gaea2_empirical_schema.json", "r") as f:
        empirical = json.load(f)

    # Our currently supported nodes (from gaea2_mcp_server.py)
    our_nodes = {
        # Primitives
        "Mountain",
        "Ridge",
        "Primitive",
        "Perlin",
        "Canyon",
        "Dunes",
        "Fault",
        "Crater",
        "Volcano",
        "Island",
        # Erosion
        "Erosion",
        "Erosion2",
        "Thermal",
        "Rivers",
        "FlowMap",
        "Snow",
        "Snowfall",
        "Stratify",
        "Slump",
        "Shear",
        "Crumble",
        # Water
        "Sea",
        "Lakes",
        "Water",
        "Coast",
        # Adjustment
        "Combine",
        "FractalTerraces",
        "Adjust",
        "Transform",
        "Warp",
        "Blur",
        "Sharpen",
        "Smooth",
        # Data
        "Mask",
        "Height",
        "Slope",
        "Curvature",
        "Occlusion",
        # Color
        "SatMap",
        "Texture",
        "TextureBase",
        "Color",
        # Output
        "Export",
        "Portal",
        "PortalTransmit",
        "PortalReceive",
        # Filters
        "Terrace",
        "Repulse",
        "Swirl",
        "Twist",
        "Whorl",
        # Geology
        "Strata",
        "Rock",
        "Deposit",
        "Sediment",
        "Fold",
        "Displace",
        # Nature
        "SoilMap",
        "Vegetation",
        "Meadow",
        "Sand",
        "Beach",
        "Rocks",
    }

    # Get all node types from references
    reference_nodes = set(empirical.keys())

    # Analysis
    print("NODE COVERAGE ANALYSIS")
    print("=" * 60)

    print(f"\nTotal nodes in references: {len(reference_nodes)}")
    print(f"Total nodes we support: {len(our_nodes)}")

    # Nodes in references we don't support
    missing_nodes = reference_nodes - our_nodes
    print(f"\n\nNODES IN REFERENCES WE DON'T SUPPORT ({len(missing_nodes)}):")
    print("-" * 60)

    # Sort by frequency of use
    missing_sorted = sorted(
        [(node, empirical[node]["file_count"]) for node in missing_nodes], key=lambda x: x[1], reverse=True
    )

    for node, count in missing_sorted:
        if count >= 2:  # Only show nodes used in 2+ files
            print(f"  {node}: {count} files")
            # Show type string
            type_str = empirical[node]["type_string"]
            print(f"    Type: {type_str}")

    # Nodes we support but not in references
    extra_nodes = our_nodes - reference_nodes
    print(f"\n\nNODES WE SUPPORT NOT IN REFERENCES ({len(extra_nodes)}):")
    print("-" * 60)
    for node in sorted(extra_nodes):
        print(f"  - {node}")

    # Common nodes we do support
    print("\n\nMOST COMMON NODES WE DO SUPPORT:")
    print("-" * 60)
    supported_common = []
    for node in reference_nodes & our_nodes:
        count = empirical[node]["file_count"]
        if count >= 5:
            supported_common.append((node, count))

    for node, count in sorted(supported_common, key=lambda x: x[1], reverse=True)[:15]:
        print(f"  {node}: {count} files ✅")


def generate_implementation_priority():
    """Generate priority list for implementing missing nodes"""

    with open("gaea2_empirical_schema.json", "r") as f:
        empirical = json.load(f)

    our_nodes = {
        "Mountain",
        "Ridge",
        "Primitive",
        "Perlin",
        "Canyon",
        "Dunes",
        "Fault",
        "Crater",
        "Volcano",
        "Island",
        "Erosion",
        "Erosion2",
        "Thermal",
        "Rivers",
        "FlowMap",
        "Snow",
        "Snowfall",
        "Stratify",
        "Slump",
        "Shear",
        "Crumble",
        "Sea",
        "Lakes",
        "Water",
        "Coast",
        "Combine",
        "FractalTerraces",
        "Adjust",
        "Transform",
        "Warp",
        "Blur",
        "Sharpen",
        "Smooth",
        "Mask",
        "Height",
        "Slope",
        "Curvature",
        "Occlusion",
        "SatMap",
        "Texture",
        "TextureBase",
        "Color",
        "Export",
        "Portal",
        "PortalTransmit",
        "PortalReceive",
        "Terrace",
        "Repulse",
        "Swirl",
        "Twist",
        "Whorl",
        "Strata",
        "Rock",
        "Deposit",
        "Sediment",
        "Fold",
        "Displace",
        "SoilMap",
        "Vegetation",
        "Meadow",
        "Sand",
        "Beach",
        "Rocks",
    }

    reference_nodes = set(empirical.keys())
    missing_nodes = reference_nodes - our_nodes

    print("\n\nIMPLEMENTATION PRIORITY")
    print("=" * 60)
    print("\nHigh priority nodes to add (used in 5+ files):")

    high_priority = []
    medium_priority = []
    low_priority = []

    for node in missing_nodes:
        count = empirical[node]["file_count"]
        if count >= 5:
            high_priority.append((node, count))
        elif count >= 2:
            medium_priority.append((node, count))
        else:
            low_priority.append((node, count))

    print("\nHIGH PRIORITY (5+ files):")
    for node, count in sorted(high_priority, key=lambda x: x[1], reverse=True):
        print(f"  - {node}: {count} files")

    print("\nMEDIUM PRIORITY (2-4 files):")
    for node, count in sorted(medium_priority, key=lambda x: x[1], reverse=True)[:10]:
        print(f"  - {node}: {count} files")


if __name__ == "__main__":
    check_node_coverage()
    generate_implementation_priority()
