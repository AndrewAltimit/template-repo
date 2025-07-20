#!/usr/bin/env python3
"""Analyze all erosion node types in reference files"""

import json
import os


def analyze_all_erosion_types():
    """Find all erosion-related node types and their properties"""

    erosion_types = {}

    for root, dirs, files in os.walk("reference projects"):
        for file in files:
            if file.endswith(".terrain"):
                path = os.path.join(root, file)
                try:
                    with open(path, "r") as f:
                        data = json.load(f)

                    nodes = data["Assets"]["$values"][0]["Terrain"]["Nodes"]

                    for node_id, node in nodes.items():
                        if isinstance(node, dict):
                            node_type_full = node.get("$type", "")

                            # Check for any erosion-related node
                            if "Erosion" in node_type_full:
                                # Extract the node type name
                                if "." in node_type_full:
                                    node_type = node_type_full.split(".")[-2]
                                else:
                                    node_type = node_type_full

                                if node_type not in erosion_types:
                                    erosion_types[node_type] = {
                                        "properties": set(),
                                        "example_file": file,
                                        "example_values": {},
                                    }

                                # Collect properties
                                for key, value in node.items():
                                    if key not in [
                                        "$id",
                                        "$type",
                                        "Id",
                                        "Name",
                                        "Position",
                                        "Ports",
                                        "Modifiers",
                                        "SnapIns",
                                        "NodeSize",
                                        "IsMaskable",
                                        "SaveDefinition",
                                    ]:
                                        erosion_types[node_type]["properties"].add(key)
                                        if key not in erosion_types[node_type]["example_values"]:
                                            erosion_types[node_type]["example_values"][key] = value
                except:
                    pass

    # Display findings
    print("=== EROSION NODE TYPES AND PROPERTIES ===\n")

    for node_type, info in sorted(erosion_types.items()):
        print(f"{node_type}:")
        print(f"  Example file: {info['example_file']}")
        print(f"  Properties:")

        for prop in sorted(info["properties"]):
            has_space = " " in prop
            example_val = info["example_values"].get(prop, "")
            print(f"    {'[SPACE]' if has_space else '[NO-SPACE]'} {prop}: {example_val}")
        print()


def check_our_erosion2_usage():
    """Check what properties we're trying to use for Erosion2"""

    print("\n=== OUR EROSION2 USAGE ===\n")

    # From the failing terrain file
    print("Properties in failing terrain file:")
    print("  - Duration: 0.15")
    print("  - Rock Softness: 0.5  [WITH SPACE]")
    print("  - Downcutting: 0.3")
    print("  - Base Level: 0.1  [WITH SPACE]")
    print("  - Intensity: 0.5")

    print("\nThese properties with spaces don't exist in reference Erosion2 nodes!")


def main():
    analyze_all_erosion_types()
    check_our_erosion2_usage()

    print("\n=== RECOMMENDATIONS ===")
    print("1. Erosion2 should NOT use 'Rock Softness' or 'Base Level'")
    print("2. Valid Erosion2 properties from references: Duration, Downcutting, ErosionScale, Seed, etc.")
    print("3. Properties should NOT have spaces in Erosion2")
    print("4. The 'Rock Softness' property might belong to 'Erosion' node (not Erosion2)")


if __name__ == "__main__":
    main()
