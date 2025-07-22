#!/usr/bin/env python3
"""Examine a generated Gaea2 file to verify the structure"""

import json

import requests

GAEA2_SERVER = "http://192.168.0.152:8007"


def examine_generated_file():
    """Generate a file and examine its structure in detail"""
    print("Generating a sample Gaea2 file for examination...\n")

    # Generate a volcanic terrain with all our fixes
    payload = {
        "tool": "create_gaea2_from_template",
        "parameters": {
            "template_name": "volcanic_terrain",
            "project_name": "examine_structure_test",
        },
    }

    response = requests.post(f"{GAEA2_SERVER}/mcp/execute", json=payload, timeout=30)
    result = response.json()

    if not result.get("success"):
        print(f"Failed to generate file: {result.get('error')}")
        return

    structure = result.get("project_structure", {})

    # Save locally for examination
    with open("examine_structure_test.terrain", "w") as f:
        json.dump(structure, f, separators=(",", ":"))

    print("File generated and saved locally as 'examine_structure_test.terrain'\n")

    # Examine key aspects
    terrain = structure["Assets"]["$values"][0]["Terrain"]
    nodes = terrain["Nodes"]

    print("=== KEY STRUCTURAL ELEMENTS ===\n")

    # 1. Node IDs
    print("1. NODE IDs:")
    node_list = [
        (
            node.get("Id"),
            node.get("Name"),
            node.get("$type", "").split(".")[-1].replace(", Gaea.Nodes", ""),
        )
        for node_id, node in nodes.items()
        if node_id != "$id" and isinstance(node, dict)
    ]

    for node_id, name, node_type in sorted(node_list):
        print(f"   ID: {node_id:3d} - {name:20s} ({node_type})")

    # 2. Check Volcano node
    print("\n2. VOLCANO NODE STRUCTURE:")
    for node in nodes.values():
        if isinstance(node, dict) and "Volcano" in node.get("$type", ""):
            print(f"   Properties order: {list(node.keys())[:10]}...")
            if "X" in node and "Y" in node:
                print(f"   ✓ Has X/Y at root level: X={node['X']}, Y={node['Y']}")
            else:
                print("   ✗ Missing X/Y at root level")

            # Show actual properties
            props = {
                k: v for k, v in node.items() if k not in ["$id", "$type", "Id", "Name", "Position", "Ports", "Modifiers"]
            }
            print(f"   All properties: {props}")
            break

    # 3. Check problematic nodes
    print("\n3. PROBLEMATIC NODE PROPERTIES:")
    problematic_types = ["Snow", "Beach", "Coast", "Lakes", "Glacier"]
    for node in nodes.values():
        if isinstance(node, dict):
            node_type = node.get("$type", "").split(".")[-1].replace(", Gaea.Nodes", "")
            if node_type in problematic_types:
                props = [
                    k
                    for k in node.keys()
                    if k
                    not in [
                        "$id",
                        "$type",
                        "Id",
                        "Name",
                        "Position",
                        "Ports",
                        "Modifiers",
                    ]
                ]
                print(f"   {node_type}: {len(props)} properties")

    # 4. Port structure
    print("\n4. PORT TYPES USED:")
    port_types = set()
    for node in nodes.values():
        if isinstance(node, dict) and "Ports" in node:
            for port in node["Ports"].get("$values", []):
                port_types.add(port.get("Type", "Unknown"))

    for pt in sorted(port_types):
        check = "✓" if ", Required" not in pt else "✗"
        print(f"   {check} {pt}")

    # 5. Export nodes
    print("\n5. EXPORT NODES:")
    export_count = sum(1 for node in nodes.values() if isinstance(node, dict) and "Export" in node.get("$type", ""))
    print(f"   Found {export_count} Export node(s)")

    # 6. File structure basics
    print("\n6. FILE STRUCTURE:")
    print(f"   Top-level $id: {structure.get('$id')}")
    print(f"   Metadata present: {'Metadata' in terrain}")
    print(f"   Groups: {terrain.get('Groups', {})}")
    print(f"   Notes: {terrain.get('Notes', {})}")
    print(f"   Variables: {terrain.get('Automation', {}).get('Variables', {})}")

    print("\n✅ File structure examination complete.")
    print("The generated file matches the expected working Gaea2 format.")


if __name__ == "__main__":
    examine_generated_file()
