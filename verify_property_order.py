#!/usr/bin/env python3
"""Verify property order matches reference files"""

import json


def check_property_order():
    """Compare property order between our output and reference"""

    print("=== PROPERTY ORDER VERIFICATION ===\n")

    # Load our generated file
    with open("rivers_fix_output.json", "r") as f:
        our_data = json.load(f)

    # Load reference file
    with open("reference projects/mikus files/Level1.terrain", "r") as f:
        ref_data = json.load(f)

    # Find Rivers nodes
    our_rivers = None
    ref_rivers = None

    # Our file
    for node_id, node in our_data["Assets"]["$values"][0]["Terrain"]["Nodes"].items():
        if isinstance(node, dict) and "Rivers" in node.get("$type", ""):
            our_rivers = node
            print(f"Our Rivers node (ID: {node_id}):")
            break

    # Reference file
    for node_id, node in ref_data["Assets"]["$values"][0]["Terrain"]["Nodes"].items():
        if isinstance(node, dict) and "Rivers" in node.get("$type", ""):
            ref_rivers = node
            print(f"\nReference Rivers node (ID: {node_id}):")
            break

    if our_rivers and ref_rivers:
        # Compare first 20 properties
        our_keys = list(our_rivers.keys())[:20]
        ref_keys = list(ref_rivers.keys())[:20]

        print("\nProperty order comparison:")
        print("-" * 50)
        print(f"{'Position':<4} {'Our Output':<25} {'Reference':<25}")
        print("-" * 50)

        max_len = max(len(our_keys), len(ref_keys))
        for i in range(max_len):
            our_prop = our_keys[i] if i < len(our_keys) else "---"
            ref_prop = ref_keys[i] if i < len(ref_keys) else "---"
            match = "✓" if our_prop == ref_prop else "✗"
            print(f"{i+1:<4} {our_prop:<25} {ref_prop:<25} {match}")

    # Check if properties come before standard fields
    print("\n\nProperty placement analysis:")
    if our_rivers:
        # Find where Id appears
        keys = list(our_rivers.keys())
        id_index = keys.index("Id") if "Id" in keys else -1

        if id_index > 0:
            props_before_id = [k for k in keys[:id_index] if k not in ["$id", "$type"]]
            print(f"Properties before 'Id': {props_before_id}")

            # These should be node-specific properties
            expected_props = [
                "Water",
                "Width",
                "Depth",
                "Downcutting",
                "RiverValleyWidth",
                "Headwaters",
                "RenderSurface",
                "Seed",
            ]

            missing = [p for p in expected_props if p not in props_before_id]
            if missing:
                print(f"❌ Missing properties: {missing}")
            else:
                print("✓ All Rivers properties correctly placed before 'Id'")


def check_node_metadata_placement():
    """Check placement of NodeSize, IsMaskable, etc."""

    print("\n\n=== NODE METADATA PLACEMENT ===\n")

    with open("rivers_fix_output.json", "r") as f:
        data = json.load(f)

    nodes = data["Assets"]["$values"][0]["Terrain"]["Nodes"]

    for node_id, node in nodes.items():
        if isinstance(node, dict):
            node_type = node.get("$type", "").split(".")[-2] if "." in node.get("$type", "") else "Unknown"

            if node_type in ["Rivers", "Combine", "Erosion2"]:
                print(f"\n{node_type} node {node_id}:")
                keys = list(node.keys())

                # Find positions of key elements
                positions = {}
                for key in ["Id", "Name", "NodeSize", "Position", "Ports", "IsMaskable"]:
                    if key in keys:
                        positions[key] = keys.index(key) + 1

                print("  Element positions:")
                for key, pos in sorted(positions.items(), key=lambda x: x[1]):
                    print(f"    {pos:2d}. {key}")

                # Check order
                if "NodeSize" in positions and "Name" in positions:
                    if positions["NodeSize"] == positions["Name"] + 1:
                        print("  ✓ NodeSize correctly after Name")
                    else:
                        print("  ✗ NodeSize not after Name")

                if "IsMaskable" in positions and "Ports" in positions:
                    if positions["IsMaskable"] > positions["Ports"]:
                        print("  ✓ IsMaskable correctly after Ports")
                    else:
                        print("  ✗ IsMaskable not after Ports")


def main():
    check_property_order()
    check_node_metadata_placement()

    print("\n" + "=" * 50)
    print("VERIFICATION COMPLETE")


if __name__ == "__main__":
    main()
