#!/usr/bin/env python3
"""Test the Gaea2 format fixes"""

import json

import requests

# Test the remote Gaea2 MCP server
MCP_SERVER = "http://192.168.0.152:8007"


def test_create_project():
    """Test creating a simple Gaea2 project with fixes"""

    # Create a simple workflow
    workflow = {
        "nodes": [
            {
                "id": "mountain_1",
                "type": "Mountain",
                "name": "Mountain",
                "properties": {"Seed": 42, "Scale": 1.0, "Height": 1.0, "rockSoftness": 0.5},  # Test property name fixing
                "position": {"x": 0, "y": 0},
            },
            {
                "id": "erosion_1",
                "type": "Erosion",
                "name": "Erosion",
                "properties": {
                    "Duration": 0.1,
                    "Intensity": 0.5,
                    "RockSoftness": 0.5,  # Test with different case
                    "baseLevel": 0.1,  # Test property name fixing
                },
                "position": {"x": 200, "y": 0},
            },
            {"id": "satmap_1", "type": "SatMap", "name": "AutoSatMap", "properties": {}, "position": {"x": 400, "y": 0}},
        ],
        "connections": [
            {"from_node": "mountain_1", "from_port": "Out", "to_node": "erosion_1", "to_port": "In"},
            {"from_node": "erosion_1", "from_port": "Out", "to_node": "satmap_1", "to_port": "In"},
        ],
    }

    # Create the project
    response = requests.post(
        f"{MCP_SERVER}/mcp/execute",
        json={
            "tool": "create_gaea2_project",
            "parameters": {
                "project_name": "test_fixed_terrain",
                "workflow": workflow,
                "auto_validate": True,
                "save_to_disk": False,  # Don't save, just get the structure
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

    # Get the project structure
    project_structure = result.get("project_structure")
    if not project_structure:
        print("No project structure returned")
        return None

    return project_structure


def analyze_structure(project):
    """Analyze the generated structure for issues"""
    print("\n=== ANALYZING GAEA2 PROJECT STRUCTURE ===\n")

    # Check basic structure
    print("1. Basic Structure:")
    print(f"   - Has Assets: {'Assets' in project}")
    print(f"   - Has Id: {'Id' in project}")
    print(f"   - Has Metadata: {'Metadata' in project}")

    # Navigate to nodes
    terrain = project["Assets"]["$values"][0]["Terrain"]
    nodes = terrain["Nodes"]

    print(f"\n2. Nodes ({len(nodes)} total):")
    for node_id, node in nodes.items():
        if isinstance(node, str):
            print(f"   - Node {node_id}: String reference ({node})")
            continue
        node_type = node.get("$type", "").split(".")[-2] if "." in node.get("$type", "") else "Unknown"
        print(f"   - Node {node_id}: {node_type}")

        # Check for SaveDefinition inside node (BAD)
        if "SaveDefinition" in node:
            print(f"     ❌ ERROR: SaveDefinition nested inside {node_type} node!")

        # Check properties
        properties = {
            k: v
            for k, v in node.items()
            if k not in ["$id", "$type", "Id", "Name", "Position", "Ports", "Modifiers", "SnapIns"]
        }
        if properties:
            print(f"     Properties: {list(properties.keys())}")

            # Check for spaces in property names
            for prop in properties:
                if " " in prop:
                    print(f"     ✓ Has spaced property: '{prop}'")

        # Check for essential properties
        if node_type in ["Combine", "SatMap", "Rivers"]:
            missing = []
            if "NodeSize" not in node:
                missing.append("NodeSize")
            if "PortCount" not in node and node_type == "Combine":
                missing.append("PortCount")
            if "IsMaskable" not in node and node_type in ["Combine", "Rivers"]:
                missing.append("IsMaskable")

            if missing:
                print(f"     ⚠️  Missing properties: {missing}")

        # Check connections
        if "Ports" in node and "$values" in node["Ports"]:
            connected_ports = []
            disconnected_ports = []
            for port in node["Ports"]["$values"]:
                if port.get("Type", "").startswith("PrimaryIn") or port.get("Type") == "In":
                    if "Record" in port:
                        connected_ports.append(port["Name"])
                    else:
                        disconnected_ports.append(port["Name"])

            if connected_ports:
                print(f"     ✓ Connected inputs: {connected_ports}")
            if disconnected_ports:
                print(f"     ❌ Disconnected inputs: {disconnected_ports}")

    # Check for SaveDefinitions (GOOD)
    print("\n3. SaveDefinitions:")
    asset_value = project["Assets"]["$values"][0]
    if "SaveDefinitions" in asset_value:
        save_defs = asset_value["SaveDefinitions"]["$values"]
        print(f"   ✓ Found {len(save_defs)} SaveDefinitions (separate from nodes)")
        for save_def in save_defs:
            print(f"     - Node {save_def['Node']}: {save_def['Filename']}.{save_def['Format']}")
    else:
        print("   - No SaveDefinitions found")

    # Check Variables format
    print("\n4. Variables Object:")
    automation = asset_value.get("Automation", {})
    variables = automation.get("Variables", {})
    if isinstance(variables, dict) and "$id" in variables:
        print('   ✓ Variables has correct format: {"$id": "..."}')
    else:
        print(f"   ❌ Variables has incorrect format: {variables}")

    return True


def main():
    print("Testing Gaea2 format fixes...")

    # Create a test project
    project = test_create_project()
    if not project:
        print("Failed to create project")
        return

    # Analyze the structure
    analyze_structure(project)

    # Pretty print a sample for inspection
    print("\n=== SAMPLE NODE STRUCTURE ===")
    nodes = project["Assets"]["$values"][0]["Terrain"]["Nodes"]
    # Skip the $id entry
    node_ids = [k for k in nodes.keys() if k != "$id"]
    if node_ids:
        first_node_id = node_ids[0]
        print(json.dumps(nodes[first_node_id], indent=2))

    # Also save the full structure for inspection
    with open("test_output.json", "w") as f:
        json.dump(project, f, indent=2)


if __name__ == "__main__":
    main()
