#!/usr/bin/env python3
"""Compare MCP-generated Level1 with reference Level1.terrain"""

import json


def compare_terrain_files():
    """Compare key aspects of the generated vs reference terrain files"""

    # Load reference
    with open("gaea-references/Level1.terrain", "r") as f:
        reference = json.load(f)

    # Load generated
    with open("Level1_mcp_recreation.terrain", "r") as f:
        generated = json.load(f)

    print("Level1.terrain Format Comparison")
    print("=" * 50)

    # 1. Check Volcano node (183)
    print("\n1. Volcano Node (183) Comparison:")
    ref_volcano = reference["Assets"]["$values"][0]["Terrain"]["Nodes"]["183"]
    gen_volcano = generated["Assets"]["$values"][0]["Terrain"]["Nodes"].get("183", {})

    if gen_volcano:
        print(f"  Reference has X at root: {'X' in ref_volcano} = {ref_volcano.get('X')}")
        print(f"  Generated has X at root: {'X' in gen_volcano} = {gen_volcano.get('X')}")
        print(f"  Reference has Y at root: {'Y' in ref_volcano} = {ref_volcano.get('Y')}")
        print(f"  Generated has Y at root: {'Y' in gen_volcano} = {gen_volcano.get('Y')}")
        print(f"  Reference Id type: {type(ref_volcano['Id'])}")
        print(f"  Generated Id type: {type(gen_volcano.get('Id'))}")
    else:
        print("  ✗ Volcano node not found in generated!")

    # 2. Check Groups/Notes/Camera format
    print("\n2. Empty Object Format Comparison:")
    ref_terrain = reference["Assets"]["$values"][0]["Terrain"]
    gen_terrain = generated["Assets"]["$values"][0]["Terrain"]

    # Groups
    ref_groups = ref_terrain["Groups"]
    gen_groups = gen_terrain.get("Groups", {})
    print(f"  Reference Groups: {ref_groups}")
    print(f"  Generated Groups: {gen_groups}")
    print(f"  Groups match: {ref_groups.keys() == gen_groups.keys()}")

    # Notes
    ref_notes = ref_terrain["Notes"]
    gen_notes = gen_terrain.get("Notes", {})
    print(f"  Reference Notes: {ref_notes}")
    print(f"  Generated Notes: {gen_notes}")
    print(f"  Notes match: {ref_notes.keys() == gen_notes.keys()}")

    # Camera
    ref_camera = reference["Assets"]["$values"][0]["State"]["Viewport"]["Camera"]
    gen_camera = generated["Assets"]["$values"][0]["State"]["Viewport"]["Camera"]
    print(f"  Reference Camera: {ref_camera}")
    print(f"  Generated Camera: {gen_camera}")
    print(f"  Camera match: {ref_camera.keys() == gen_camera.keys()}")

    # 3. Check property names (no spaces)
    print("\n3. Property Name Format Check:")
    # Check Sea node for properties
    ref_sea = reference["Assets"]["$values"][0]["Terrain"]["Nodes"]["287"]
    gen_sea = generated["Assets"]["$values"][0]["Terrain"]["Nodes"].get("287", {})

    if gen_sea:
        properties_to_check = [
            "CoastalErosion",
            "ExtraCliffDetails",
            "UniformVariations",
        ]
        for prop in properties_to_check:
            ref_has = prop in ref_sea
            gen_has = prop in gen_sea
            print(f"  {prop}: Reference={ref_has}, Generated={gen_has}")

    # 4. Check Rivers node properties
    print("\n4. Rivers Node (949) Properties:")
    ref_rivers = reference["Assets"]["$values"][0]["Terrain"]["Nodes"]["949"]
    gen_rivers = generated["Assets"]["$values"][0]["Terrain"]["Nodes"].get("949", {})

    if gen_rivers:
        print(f"  RiverValleyWidth: Ref='{ref_rivers.get('RiverValleyWidth')}', Gen='{gen_rivers.get('RiverValleyWidth')}'")
        print(f"  NodeSize: Ref='{ref_rivers.get('NodeSize')}', Gen='{gen_rivers.get('NodeSize')}'")

    # 5. Check connections
    print("\n5. Connection Check:")
    # Count connections in ports
    ref_connections = 0
    gen_connections = 0

    for node_id, node in reference["Assets"]["$values"][0]["Terrain"]["Nodes"].items():
        if node_id != "$id" and "Ports" in node:
            for port in node["Ports"]["$values"]:
                if "Record" in port:
                    ref_connections += 1

    for node_id, node in generated["Assets"]["$values"][0]["Terrain"]["Nodes"].items():
        if node_id != "$id" and "Ports" in node:
            for port in node["Ports"]["$values"]:
                if "Record" in port:
                    gen_connections += 1

    print(f"  Reference connections: {ref_connections}")
    print(f"  Generated connections: {gen_connections}")

    # 6. Check node count
    print("\n6. Node Count:")
    ref_node_count = len([k for k in reference["Assets"]["$values"][0]["Terrain"]["Nodes"].keys() if k != "$id"])
    gen_node_count = len([k for k in generated["Assets"]["$values"][0]["Terrain"]["Nodes"].keys() if k != "$id"])
    print(f"  Reference nodes: {ref_node_count}")
    print(f"  Generated nodes: {gen_node_count}")

    # 7. Check specific node IDs
    print("\n7. Node ID Check (first 5):")
    ref_ids = sorted([int(k) for k in reference["Assets"]["$values"][0]["Terrain"]["Nodes"].keys() if k != "$id"])[:5]
    gen_ids = sorted([int(k) for k in generated["Assets"]["$values"][0]["Terrain"]["Nodes"].keys() if k != "$id"])[:5]
    print(f"  Reference IDs: {ref_ids}")
    print(f"  Generated IDs: {gen_ids}")

    print("\n" + "=" * 50)
    print("SUMMARY:")

    # Final verdict
    issues = []
    if not gen_volcano or "X" not in gen_volcano:
        issues.append("Volcano missing X/Y at root")
    if ref_groups.keys() != gen_groups.keys():
        issues.append("Groups format mismatch")
    if ref_connections != gen_connections:
        issues.append(f"Connection count mismatch ({ref_connections} vs {gen_connections})")

    if issues:
        print("✗ Issues found:")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("✓ Format appears to match reference!")


if __name__ == "__main__":
    compare_terrain_files()
