#!/usr/bin/env python3
"""Test Rivers node specifically with the updated server"""

import json

import requests

# Test the remote Gaea2 MCP server
MCP_SERVER = "http://192.168.0.152:8007"


def test_rivers_workflow():
    """Test a simple workflow focused on Rivers node"""

    workflow = {
        "nodes": [
            {
                "id": "mountain_1",
                "type": "Mountain",
                "name": "Base Terrain",
                "properties": {"Seed": 42, "Scale": 1.5, "Height": 0.7},
                "position": {"x": 0, "y": 0},
            },
            {
                "id": "rivers_1",
                "type": "Rivers",
                "name": "River System",
                "properties": {
                    "Water": 0.4,
                    "Width": 0.6,
                    "Depth": 0.7,
                    "Downcutting": 0.3,
                    "RiverValleyWidth": "plus2",  # Test different enum value
                    "Headwaters": 150,
                    "RenderSurface": True,  # Test true value
                    "Seed": 12345,
                },
                "position": {"x": 200, "y": 0},
            },
            {
                "id": "export_terrain",
                "type": "Export",
                "name": "Terrain Export",
                "properties": {"format": "EXR", "filename": "rivers_terrain"},
                "position": {"x": 400, "y": 0},
            },
            {
                "id": "export_rivers",
                "type": "Export",
                "name": "Rivers Mask Export",
                "properties": {"format": "PNG", "filename": "rivers_mask"},
                "position": {"x": 400, "y": 200},
            },
        ],
        "connections": [
            {"from_node": "mountain_1", "from_port": "Out", "to_node": "rivers_1", "to_port": "In"},
            {"from_node": "rivers_1", "from_port": "Out", "to_node": "export_terrain", "to_port": "In"},
            {"from_node": "rivers_1", "from_port": "Rivers", "to_node": "export_rivers", "to_port": "In"},
        ],
    }

    print("Creating Rivers-focused workflow...")
    print(f"Nodes: {len(workflow['nodes'])}")
    print(f"Connections: {len(workflow['connections'])}")
    print()

    # Create the project
    response = requests.post(
        f"{MCP_SERVER}/mcp/execute",
        json={
            "tool": "create_gaea2_project",
            "parameters": {
                "project_name": "test_rivers_workflow",
                "workflow": workflow,
                "auto_validate": True,
                "save_to_disk": True,
            },
        },
    )

    if response.status_code != 200:
        print(f"Error: {response.status_code}")
        print(response.text)
        return None

    result = response.json()

    if not result.get("success"):
        print(f"Failed: {result.get('error')}")
        return None

    print("✓ Rivers project created successfully!")
    print(f"  - Saved to: {result.get('saved_path')}")

    return result.get("project_structure")


def analyze_rivers_node(project):
    """Analyze the Rivers node in detail"""
    if not project:
        return

    nodes = project["Assets"]["$values"][0]["Terrain"]["Nodes"]

    print("\n=== RIVERS NODE ANALYSIS ===")

    # Find Rivers node
    rivers_node = None
    for node_id, node in nodes.items():
        if isinstance(node, str):
            continue
        if "Rivers" in node.get("$type", ""):
            rivers_node = node
            break

    if not rivers_node:
        print("❌ No Rivers node found!")
        return

    print(f"\nRivers Node (ID: {rivers_node['Id']}):")
    print("Properties:")

    # Check all properties
    expected_props = ["Water", "Width", "Depth", "Downcutting", "RiverValleyWidth", "Headwaters", "RenderSurface", "Seed"]

    for prop in expected_props:
        if prop in rivers_node:
            print(f"  ✓ {prop}: {rivers_node[prop]}")
        else:
            print(f"  ❌ {prop}: MISSING")

    # Check for invalid properties
    invalid_props = []
    for prop in rivers_node:
        if prop not in expected_props and prop not in [
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
        ]:
            invalid_props.append(prop)

    if invalid_props:
        print(f"\n❌ Invalid properties found: {invalid_props}")
    else:
        print("\n✓ No invalid properties")

    # Check ports
    print(f"\nPorts ({len(rivers_node['Ports']['$values'])} total):")
    for port in rivers_node["Ports"]["$values"]:
        print(f"  - {port['Name']} ({port['Type']})")

    # Save for inspection
    with open("rivers_output.json", "w") as f:
        json.dump(project, f, indent=2)
    print("\n✓ Full structure saved to: rivers_output.json")


def main():
    print("Testing Rivers Node with Updated Server")
    print("=" * 50)

    # Create Rivers project
    project = test_rivers_workflow()

    # Analyze results
    analyze_rivers_node(project)


if __name__ == "__main__":
    main()
