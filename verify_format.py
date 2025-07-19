#!/usr/bin/env python3
"""Verify our generated format matches reference files"""

import json


def compare_formats():
    """Compare our generated format with reference format"""

    # Load our generated file
    with open("rivers_output.json", "r") as f:
        our_format = json.load(f)

    print("=== FORMAT VERIFICATION ===\n")

    # Check 1: SaveDefinitions placement
    print("1. SaveDefinition Placement:")

    # Check if SaveDefinitions array exists at asset level (BAD)
    asset = our_format["Assets"]["$values"][0]
    if "SaveDefinitions" in asset:
        print("   ❌ WRONG: SaveDefinitions array found at asset level")
    else:
        print("   ✓ CORRECT: No SaveDefinitions array at asset level")

    # Check if Export nodes have embedded SaveDefinitions (GOOD)
    nodes = asset["Terrain"]["Nodes"]
    export_count = 0
    embedded_count = 0

    for node_id, node in nodes.items():
        if isinstance(node, str):
            continue
        if "Export" in node.get("$type", ""):
            export_count += 1
            if "SaveDefinition" in node:
                embedded_count += 1
                print(f"   ✓ Export node {node_id} has embedded SaveDefinition")

    print(f"   Summary: {embedded_count}/{export_count} Export nodes have embedded SaveDefinitions")

    # Check 2: Rivers node properties
    print("\n2. Rivers Node Properties:")
    rivers_found = False

    for node_id, node in nodes.items():
        if isinstance(node, str):
            continue
        if "Rivers" in node.get("$type", ""):
            rivers_found = True
            print(f"   Rivers node {node_id}:")

            # Check property names (should have no spaces)
            good_props = ["RiverValleyWidth", "RenderSurface"]
            bad_props = ["River Valley Width", "Render Surface", "Density"]

            for prop in good_props:
                if prop in node:
                    print(f"   ✓ Has {prop} (correct format)")

            for prop in bad_props:
                if prop in node:
                    print(f"   ❌ Has '{prop}' (WRONG format)")

            # Check essential properties
            essential = ["Water", "Width", "Depth", "Downcutting", "Headwaters", "Seed"]
            for prop in essential:
                if prop not in node:
                    print(f"   ⚠️  Missing {prop}")

    if not rivers_found:
        print("   No Rivers nodes found")

    # Check 3: Node structure
    print("\n3. Node Structure:")
    sample_node = None
    for node_id, node in nodes.items():
        if isinstance(node, dict):
            sample_node = node
            break

    if sample_node:
        required_fields = ["$id", "$type", "Id", "Name", "Position", "Ports"]
        optional_fields = ["Modifiers", "SnapIns", "SaveDefinition", "NodeSize", "IsMaskable"]

        print("   Required fields:")
        for field in required_fields:
            if field in sample_node:
                print(f"   ✓ {field}")
            else:
                print(f"   ❌ {field} MISSING")

        print("   Optional fields present:")
        for field in optional_fields:
            if field in sample_node:
                print(f"   - {field}")


def main():
    print("Verifying Generated Format Against Reference Files")
    print("=" * 50)

    compare_formats()

    print("\n" + "=" * 50)
    print("SUMMARY: Format should match reference files like Level1.terrain")
    print("Key requirements:")
    print("- SaveDefinitions embedded in nodes (not separate array)")
    print("- Rivers properties without spaces (RiverValleyWidth, RenderSurface)")
    print("- No invalid properties like 'Density'")


if __name__ == "__main__":
    main()
