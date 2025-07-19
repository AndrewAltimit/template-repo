#!/usr/bin/env python3
"""Debug script to create a minimal terrain file and check its content."""

import requests

# Create a minimal project
response = requests.post(
    "http://192.168.0.152:8007/mcp/execute",
    json={
        "tool": "create_gaea2_project",
        "parameters": {
            "project_name": "minimal_debug",
            "workflow": {
                "nodes": [
                    {
                        "id": "mountain1",
                        "type": "Mountain",
                        "name": "Mountain",
                        "properties": {},
                        "position": {"x": 0, "y": 0},
                    }
                ],
                "connections": [],
            },
        },
    },
)

result = response.json()
if result.get("success"):
    print("Project created successfully")
    print(f"File saved to: {result['project'].get('file_path')}")

    # Extract some key fields to check
    project = result["project"]
    print("\nChecking key boolean fields:")

    # Check a boolean in the main structure
    tile_zero = project["BuildDefinition"]["TileZeroIndex"]
    print(f"TileZeroIndex: {tile_zero} (type: {type(tile_zero)})")

    # Check a boolean in nodes
    mountain_node = project["Assets"]["$values"][0]["Terrain"]["Nodes"]["100"]
    print(f"ReduceDetails: {mountain_node.get('ReduceDetails')} (type: {type(mountain_node.get('ReduceDetails'))})")

    # Check IsExporting
    port = mountain_node["Ports"]["$values"][0]
    print(f"IsExporting: {port['IsExporting']} (type: {type(port['IsExporting'])})")

else:
    print(f"Failed to create project: {result.get('error')}")
