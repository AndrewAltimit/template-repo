#!/usr/bin/env python3
"""Debug Erosion node properties."""

import requests

# Create a project with an Erosion node
response = requests.post(
    "http://192.168.0.152:8007/mcp/execute",
    json={
        "tool": "create_gaea2_project",
        "parameters": {
            "project_name": "erosion_debug",
            "workflow": {
                "nodes": [
                    {
                        "id": "erosion1",
                        "type": "Erosion",
                        "name": "TestErosion",
                        "properties": {"strength": 0.7, "rockSoftness": 0.5},  # camelCase input
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

    # Check the Erosion node properties
    erosion_node = result["project"]["Assets"]["$values"][0]["Terrain"]["Nodes"]["100"]
    print("\nErosion node properties:")
    for key, value in erosion_node.items():
        if key not in ["$id", "$type", "Id", "Name", "Position", "Ports", "Modifiers", "SnapIns"]:
            print(f"  {key}: {value}")
else:
    print(f"Failed: {result.get('error')}")
