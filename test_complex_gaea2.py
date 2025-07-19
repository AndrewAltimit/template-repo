#!/usr/bin/env python3
"""Test complex Gaea2 workflow with multiple node types"""

import json

import requests

# Test the remote Gaea2 MCP server
MCP_SERVER = "http://192.168.0.152:8007"


def test_complex_workflow():
    """Test a complex workflow with various node types"""

    workflow = {
        "nodes": [
            # Terrain generation
            {
                "id": "mountain_1",
                "type": "Mountain",
                "name": "Mountain Base",
                "properties": {"Seed": 12345, "Scale": 2.0, "Height": 0.8},
                "position": {"x": 0, "y": 0},
            },
            {
                "id": "ridge_1",
                "type": "Ridge",
                "name": "Ridge Detail",
                "properties": {"Scale": 1.5, "Detail": 0.7},
                "position": {"x": 0, "y": 200},
            },
            # Combine terrains
            {
                "id": "combine_1",
                "type": "Combine",
                "name": "Combine Terrains",
                "properties": {"Method": "Max", "Strength": 0.75},
                "position": {"x": 200, "y": 100},
            },
            # Erosion
            {
                "id": "erosion_1",
                "type": "Erosion2",  # Test Erosion2 type
                "name": "Advanced Erosion",
                "properties": {"Duration": 0.2, "Downcutting": 0.3, "Rock Softness": 0.6, "SedimentRemoval": 0.5},
                "position": {"x": 400, "y": 100},
            },
            # Water features
            {
                "id": "rivers_1",
                "type": "Rivers",
                "name": "River System",
                "properties": {
                    "Water": 0.3,
                    "Width": 0.5,
                    "Depth": 0.5,
                    "Downcutting": 0.2,
                    "RiverValleyWidth": "zero",
                    "Headwaters": 100,
                    "RenderSurface": False,
                    "Seed": 42,
                },
                "position": {"x": 600, "y": 100},
            },
            # Texturing
            {"id": "satmap_1", "type": "SatMap", "name": "Satellite Map", "properties": {}, "position": {"x": 800, "y": 0}},
            # Exports
            {
                "id": "export_height",
                "type": "Export",
                "name": "Height Export",
                "properties": {"format": "EXR", "filename": "complex_height", "channel": "Height"},
                "position": {"x": 800, "y": 200},
            },
            {
                "id": "export_rivers",
                "type": "Export",
                "name": "Rivers Export",
                "properties": {"format": "PNG", "filename": "complex_rivers", "channel": "Rivers"},
                "position": {"x": 800, "y": 400},
            },
        ],
        "connections": [
            # Combine mountain and ridge
            {"from_node": "mountain_1", "from_port": "Out", "to_node": "combine_1", "to_port": "In"},
            {"from_node": "ridge_1", "from_port": "Out", "to_node": "combine_1", "to_port": "Input2"},
            # Erode combined terrain
            {"from_node": "combine_1", "from_port": "Out", "to_node": "erosion_1", "to_port": "In"},
            # Add rivers
            {"from_node": "erosion_1", "from_port": "Out", "to_node": "rivers_1", "to_port": "In"},
            # Connect to outputs
            {"from_node": "rivers_1", "from_port": "Out", "to_node": "satmap_1", "to_port": "In"},
            {"from_node": "rivers_1", "from_port": "Out", "to_node": "export_height", "to_port": "In"},
            {"from_node": "rivers_1", "from_port": "Rivers", "to_node": "export_rivers", "to_port": "In"},
        ],
    }

    print("Creating complex workflow project...")
    print(f"Nodes: {len(workflow['nodes'])}")
    print(f"Connections: {len(workflow['connections'])}")
    print()

    # Create the project
    response = requests.post(
        f"{MCP_SERVER}/mcp/execute",
        json={
            "tool": "create_gaea2_project",
            "parameters": {
                "project_name": "complex_terrain_workflow",
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

    print("✓ Complex project created successfully!")
    print(f"  - Saved to: {result.get('saved_path')}")

    # Check validation results
    if result.get("validation_result"):
        val = result["validation_result"]["results"]
        print("\nValidation Results:")
        print(f"  - Valid: {val.get('is_valid')}")
        print(f"  - Errors fixed: {len(val.get('errors_fixed', []))}")
        print(f"  - Missing nodes added: {len(val.get('missing_nodes_added', []))}")

    return result.get("project_structure")


def analyze_complex_structure(project):
    """Analyze the complex structure"""
    if not project:
        return

    asset_value = project["Assets"]["$values"][0]
    nodes = asset_value["Terrain"]["Nodes"]

    print("\n=== COMPLEX WORKFLOW ANALYSIS ===")

    # Count node types
    node_types = {}
    for node_id, node in nodes.items():
        if isinstance(node, str):
            continue
        node_type = node.get("$type", "").split(".")[-2] if "." in node.get("$type", "") else "Unknown"
        node_types[node_type] = node_types.get(node_type, 0) + 1

    print("\n1. Node Type Distribution:")
    for node_type, count in sorted(node_types.items()):
        print(f"   - {node_type}: {count}")

    # Check SaveDefinitions (now embedded in nodes)
    print("\n2. SaveDefinitions (embedded in nodes):")
    save_def_count = 0
    for node_id, node in nodes.items():
        if isinstance(node, str):
            continue
        if "SaveDefinition" in node:
            save_def_count += 1
            sd = node["SaveDefinition"]
            print(f"   ✓ Node {node_id}: {sd['Filename']}.{sd['Format']}")

    if save_def_count > 0:
        print(f"   Total: {save_def_count} SaveDefinitions found")
    else:
        print("   ❌ No SaveDefinitions found")

    # Check special node properties
    print("\n3. Special Node Properties:")
    for node_id, node in nodes.items():
        if isinstance(node, str):
            continue
        node_type = node.get("$type", "").split(".")[-2] if "." in node.get("$type", "") else "Unknown"

        if node_type == "Combine":
            print(f"   - Combine node {node_id}:")
            print(f"     · PortCount: {node.get('PortCount', 'MISSING')}")
            print(f"     · IsMaskable: {node.get('IsMaskable', 'MISSING')}")
        elif node_type == "Rivers":
            print(f"   - Rivers node {node_id}:")
            print(f"     · NodeSize: {node.get('NodeSize', 'MISSING')}")
            print("     · Has multiple output ports")

    # Save to file
    with open("complex_output.json", "w") as f:
        json.dump(project, f, indent=2)
    print("\n✓ Full structure saved to: complex_output.json")


def main():
    print("Testing Complex Gaea2 Workflow")
    print("=" * 50)

    # Create complex project
    project = test_complex_workflow()

    # Analyze results
    analyze_complex_structure(project)


if __name__ == "__main__":
    main()
