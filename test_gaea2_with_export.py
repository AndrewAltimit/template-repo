#!/usr/bin/env python3
"""Test the updated Gaea2 MCP server with Export nodes and SaveDefinitions"""

import json

import requests

# Test the remote Gaea2 MCP server
MCP_SERVER = "http://192.168.0.152:8007"


def test_create_project_with_export():
    """Test creating a Gaea2 project with Export node"""

    # Create a workflow with Export node
    workflow = {
        "nodes": [
            {
                "id": "mountain_1",
                "type": "Mountain",
                "name": "Mountain",
                "properties": {
                    "Seed": 42,
                    "Scale": 1.0,
                    "Height": 1.0,
                    "Octaves": 8,
                    "Complexity": 0.5,
                    "RidgeWeight": 0.5,
                    "Persistence": 0.5,
                    "Lacunarity": 2.0,
                },
                "position": {"x": 0, "y": 0},
            },
            {
                "id": "erosion_1",
                "type": "Erosion",
                "name": "Erosion",
                "properties": {
                    "Downcutting": 0.25,
                    "Duration": 0.1,
                    "Intensity": 0.5,
                    "Rock Softness": 0.5,  # Test with space
                    "Base Level": 0.1,
                },
                "position": {"x": 200, "y": 0},
            },
            {
                "id": "export_1",
                "type": "Export",
                "name": "Export",
                "properties": {"format": "PNG", "filename": "mountain_test"},
                "position": {"x": 400, "y": 0},
            },
            {"id": "satmap_1", "type": "SatMap", "name": "AutoSatMap", "properties": {}, "position": {"x": 600, "y": 0}},
        ],
        "connections": [
            {"from_node": "mountain_1", "from_port": "Out", "to_node": "erosion_1", "to_port": "In"},
            {"from_node": "erosion_1", "from_port": "Out", "to_node": "export_1", "to_port": "In"},
            {"from_node": "erosion_1", "from_port": "Out", "to_node": "satmap_1", "to_port": "In"},
        ],
    }

    print("Creating project with workflow:")
    print(json.dumps(workflow, indent=2))
    print("\n" + "=" * 50 + "\n")

    # Create the project
    response = requests.post(
        f"{MCP_SERVER}/mcp/execute",
        json={
            "tool": "create_gaea2_project",
            "parameters": {
                "project_name": "test_mountain_with_export",
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

    print("✓ Project created successfully!")
    print(f"  - Saved to: {result.get('saved_path')}")
    print(f"  - Nodes: {result.get('node_count')}")
    print(f"  - Connections: {result.get('connection_count')}")

    # Get the project structure
    project_structure = result.get("project_structure")
    if not project_structure:
        print("No project structure returned")
        return None

    return project_structure, result.get("saved_path")


def analyze_structure_detailed(project):
    """Detailed analysis of the generated structure"""
    print("\n=== DETAILED STRUCTURE ANALYSIS ===\n")

    # Navigate to the asset value
    asset_value = project["Assets"]["$values"][0]
    terrain = asset_value["Terrain"]
    nodes = terrain["Nodes"]

    print("1. Nodes Analysis:")
    export_nodes = []
    for node_id, node in nodes.items():
        if node_id == "$id":
            continue

        node_type = node.get("$type", "").split(".")[-2] if "." in node.get("$type", "") else "Unknown"
        print(f"\n   Node {node_id} ({node_type}):")

        # Check for nested SaveDefinition (should not exist)
        if "SaveDefinition" in node:
            print("     ❌ ERROR: SaveDefinition still nested in node!")
            print(f"        Content: {node['SaveDefinition']}")
        else:
            print("     ✓ No nested SaveDefinition")

        # Track Export nodes
        if node_type == "Export":
            export_nodes.append(node_id)
            print("     → Export node found")

        # Check properties
        properties = {
            k: v
            for k, v in node.items()
            if k not in ["$id", "$type", "Id", "Name", "Position", "Ports", "Modifiers", "SnapIns"]
        }
        if properties:
            for prop, value in properties.items():
                if " " in prop:
                    print(f"     ✓ Property with space: '{prop}' = {value}")
                else:
                    print(f"     · Property: {prop} = {value}")

    print("\n2. SaveDefinitions Analysis:")
    if "SaveDefinitions" in asset_value:
        save_defs = asset_value["SaveDefinitions"]
        print("   ✓ SaveDefinitions found at correct location (asset level)")
        print(f"   · Structure: {json.dumps(save_defs, indent=6)}")

        if "$values" in save_defs:
            for save_def in save_defs["$values"]:
                node_ref = save_def.get("Node")
                filename = save_def.get("Filename")
                format = save_def.get("Format")
                print("\n   SaveDefinition:")
                print(f"     - References Node: {node_ref}")
                print(f"     - Filename: {filename}")
                print(f"     - Format: {format}")
                print(f"     - IsEnabled: {save_def.get('IsEnabled')}")

                # Check if it references an Export node
                if str(node_ref) in export_nodes:
                    print("     ✓ References Export node correctly")
    else:
        print("   ❌ No SaveDefinitions found")
        if export_nodes:
            print(f"   ⚠️  But found {len(export_nodes)} Export nodes: {export_nodes}")

    print("\n3. Connection Validation:")
    disconnected_count = 0
    for node_id, node in nodes.items():
        if node_id == "$id":
            continue

        if "Ports" in node and "$values" in node["Ports"]:
            for port in node["Ports"]["$values"]:
                if port.get("Type", "").startswith("PrimaryIn") or port.get("Type") == "In":
                    if "Record" not in port:
                        node_type = node.get("$type", "").split(".")[-2] if "." in node.get("$type", "") else "Unknown"
                        # Mountain nodes shouldn't have input connections
                        if node_type != "Mountain":
                            print(f"   ⚠️  Node {node_id} ({node_type}) port {port['Name']} is disconnected")
                            disconnected_count += 1

    if disconnected_count == 0:
        print("   ✓ All nodes properly connected (except source nodes)")

    return True


def save_and_display_json(project, filename="test_export_output.json"):
    """Save the full JSON for inspection"""
    with open(filename, "w") as f:
        json.dump(project, f, indent=2)
    print(f"\n✓ Full project structure saved to: {filename}")

    # Display a prettified sample
    print("\n=== SAMPLE: First 80 lines of generated JSON ===")
    with open(filename, "r") as f:
        lines = f.readlines()
        for i, line in enumerate(lines[:80]):
            print(line.rstrip())


def main():
    print("Testing Updated Gaea2 MCP Server with Export Nodes")
    print("=" * 50)

    # Create a test project with Export node
    result = test_create_project_with_export()
    if not result:
        print("Failed to create project")
        return

    project, saved_path = result

    # Analyze the structure
    analyze_structure_detailed(project)

    # Save for inspection
    save_and_display_json(project)

    print(f"\n✓ Test completed! Project saved to: {saved_path}")
    print("\nYou can now open this file in Gaea2 to verify it loads correctly.")


if __name__ == "__main__":
    main()
