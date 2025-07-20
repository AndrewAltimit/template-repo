#!/usr/bin/env python3
"""Test Rivers node with the latest fixes"""

import json

import requests

# Test the remote Gaea2 MCP server
MCP_SERVER = "http://192.168.0.152:8007"


def test_rivers_workflow():
    """Test a workflow specifically focused on Rivers node"""

    workflow = {
        "nodes": [
            # Base terrain
            {
                "id": "mountain_1",
                "type": "Mountain",
                "name": "Base Terrain",
                "properties": {"Seed": 12345, "Scale": 2.0, "Height": 0.8},
                "position": {"x": 0, "y": 0},
            },
            # Erosion before rivers
            {
                "id": "erosion_1",
                "type": "Erosion2",
                "name": "Initial Erosion",
                "properties": {"Duration": 0.15, "Downcutting": 0.3, "ErosionScale": 5000.0, "Seed": 12345},
                "position": {"x": 200, "y": 0},
            },
            # Rivers node - testing all properties
            {
                "id": "rivers_1",
                "type": "Rivers",
                "name": "River System",
                "properties": {
                    "Water": 0.3,
                    "Width": 0.5,
                    "Depth": 0.5,
                    "Downcutting": 0.2,
                    "RiverValleyWidth": "zero",  # Testing fixed property name
                    "Headwaters": 100,
                    "RenderSurface": False,  # Testing fixed property name
                    "Seed": 42,
                },
                "position": {"x": 400, "y": 0},
            },
            # SatMap for visualization
            {
                "id": "satmap_1",
                "type": "SatMap",
                "name": "Terrain Colors",
                "properties": {},
                "position": {"x": 600, "y": 0},
            },
            # Export nodes
            {
                "id": "export_height",
                "type": "Export",
                "name": "Height Export",
                "properties": {"format": "EXR", "filename": "rivers_test_height"},
                "position": {"x": 600, "y": 200},
            },
            {
                "id": "export_rivers",
                "type": "Export",
                "name": "Rivers Export",
                "properties": {"format": "PNG", "filename": "rivers_test_rivers"},
                "position": {"x": 800, "y": 100},
            },
        ],
        "connections": [
            # Basic flow
            {"from_node": "mountain_1", "from_port": "Out", "to_node": "erosion_1", "to_port": "In"},
            {"from_node": "erosion_1", "from_port": "Out", "to_node": "rivers_1", "to_port": "In"},
            {"from_node": "rivers_1", "from_port": "Out", "to_node": "satmap_1", "to_port": "In"},
            {"from_node": "rivers_1", "from_port": "Out", "to_node": "export_height", "to_port": "In"},
            # Rivers output to export
            {"from_node": "rivers_1", "from_port": "Rivers", "to_node": "export_rivers", "to_port": "In"},
        ],
    }

    print("Testing Rivers workflow with latest fixes...")
    print("=" * 50)

    # Create the project
    response = requests.post(
        f"{MCP_SERVER}/mcp/execute",
        json={
            "tool": "create_gaea2_project",
            "parameters": {
                "project_name": "rivers_fix_test",
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

    # Check validation results
    if result.get("validation_result"):
        val = result["validation_result"]["results"]
        print("\nValidation Results:")
        print(f"  - Valid: {val.get('is_valid')}")
        print(f"  - Errors fixed: {len(val.get('errors_fixed', []))}")
        if val.get("errors_fixed"):
            for error in val["errors_fixed"]:
                print(f"    • {error}")

    return result.get("project_structure")


def verify_rivers_node(project):
    """Verify the Rivers node structure is correct"""
    if not project:
        return

    print("\n=== RIVERS NODE VERIFICATION ===")

    nodes = project["Assets"]["$values"][0]["Terrain"]["Nodes"]

    # Find Rivers node
    rivers_node = None
    rivers_id = None
    for node_id, node in nodes.items():
        if isinstance(node, dict) and "Rivers" in node.get("$type", ""):
            rivers_node = node
            rivers_id = node_id
            break

    if not rivers_node:
        print("❌ Rivers node not found!")
        return

    print(f"\nRivers Node (ID: {rivers_id}):")

    # Check property names
    print("\n1. Property Names (should have no spaces):")
    for prop in ["RiverValleyWidth", "RenderSurface"]:
        if prop in rivers_node:
            print(f"  ✓ {prop}: {rivers_node[prop]}")
        else:
            print(f"  ❌ {prop}: NOT FOUND")

    # Check property order
    print("\n2. Property Order:")
    keys = list(rivers_node.keys())
    for i, key in enumerate(keys[:15]):
        print(f"  {i+1}. {key}")

    # Check ports
    print("\n3. Port Configuration:")
    if "Ports" in rivers_node:
        ports = rivers_node["Ports"]["$values"]
        for port in ports:
            name = port.get("Name")
            port_type = port.get("Type")
            if name in ["Mask", "Headwaters"]:
                expected = "In"
                status = "✓" if port_type == expected else "❌"
                print(f"  {status} {name}: Type='{port_type}' (expected '{expected}')")
            elif name in ["Rivers", "Depth", "Surface", "Direction"]:
                expected = "Out"
                status = "✓" if port_type == expected else "❌"
                print(f"  {status} {name}: Type='{port_type}' (expected '{expected}')")

    # Check SaveDefinition placement
    print("\n4. SaveDefinition Placement:")
    # Check if SaveDefinition is embedded in Export nodes
    export_count = 0
    for node_id, node in nodes.items():
        if isinstance(node, dict) and "Export" in node.get("$type", ""):
            if "SaveDefinition" in node:
                export_count += 1
                print(f"  ✓ Export node {node_id} has embedded SaveDefinition")

    if export_count == 0:
        print("  ❌ No Export nodes have SaveDefinitions!")

    # Save for manual inspection
    with open("rivers_fix_output.json", "w") as f:
        json.dump(project, f, indent=2)
    print("\n✓ Full structure saved to: rivers_fix_output.json")

    # Create a compact version for easy copying
    compact = json.dumps(project, separators=(",", ":"))
    with open("rivers_fix_compact.json", "w") as f:
        f.write(compact)
    print("✓ Compact version saved to: rivers_fix_compact.json")


def main():
    # Test Rivers workflow
    project = test_rivers_workflow()

    # Verify the structure
    verify_rivers_node(project)

    print("\n" + "=" * 50)
    print("TEST COMPLETE - Check if the terrain file opens in Gaea2!")


if __name__ == "__main__":
    main()
