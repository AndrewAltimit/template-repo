#!/usr/bin/env python3
"""Check the structure of generated terrain files."""

import requests

# Create a minimal project
response = requests.post(
    "http://192.168.0.152:8007/mcp/execute",
    json={
        "tool": "create_gaea2_project",
        "parameters": {
            "project_name": "structure_check",
            "workflow": {
                "nodes": [
                    {
                        "id": "mountain1",
                        "type": "Mountain",
                        "name": "TestMountain",
                        "properties": {"height": 0.8},
                        "position": {"x": 100, "y": 100},
                    }
                ],
                "connections": [],
            },
        },
    },
)

result = response.json()
if result.get("success"):
    project = result["project"]

    # Check the structure
    print("Top-level keys:", list(project.keys()))
    print("\nAssets structure:")
    print("  Assets.$values[0] keys:", list(project["Assets"]["$values"][0].keys()))

    terrain = project["Assets"]["$values"][0]["Terrain"]
    print("\nTerrain keys:", list(terrain.keys()))

    # Check node structure
    node = terrain["Nodes"]["100"]
    print("\nMountain node keys:", list(node.keys()))

    # Check for any None values
    print("\nChecking for None values in Mountain node:")
    for key, value in node.items():
        if value is None:
            print(f"  {key}: None")

    # Check Groups/Notes structure
    print("\nGroups:", terrain.get("Groups"))
    print("Notes:", terrain.get("Notes"))
else:
    print("Failed:", result.get("error"))
