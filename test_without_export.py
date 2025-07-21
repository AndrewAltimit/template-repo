#!/usr/bin/env python3
"""Test creating a project with properties but NO Export node"""

import json

import requests

print("Testing project with properties but NO Export node...\n")

# Create a workflow similar to failing one but without Export
response = requests.post(
    "http://192.168.0.152:8007/mcp/execute",
    json={
        "tool": "create_gaea2_project",
        "parameters": {
            "project_name": "test_no_export",
            "nodes": [
                {
                    "id": 1,  # Use simple ID
                    "type": "Mountain",
                    "name": "Mountain",
                    "position": {"x": 25000, "y": 26000},
                    "properties": {
                        "Scale": 1.0,
                        "Height": 0.7,
                        "Style": "Alpine",
                        "Bulk": "Medium",
                        "X": 0.5,  # This is valid!
                        "Y": 0.5,
                        "Seed": 12345,
                    },
                },
                {
                    "id": 2,
                    "type": "Erosion2",
                    "name": "Erosion",
                    "position": {"x": 25500, "y": 26000},
                    "properties": {"Duration": 0.15, "Downcutting": 0.3, "ErosionScale": 5000.0, "Seed": 12345},
                },
                {
                    "id": 3,
                    "type": "SatMap",
                    "name": "ColorMap",
                    "position": {"x": 26000, "y": 26000},
                    "properties": {"Library": "Rock", "LibraryItem": 0, "Enhance": "None"},
                },
            ],
            "connections": [
                {"from_node": 1, "to_node": 2, "from_port": "Out", "to_port": "In"},
                {"from_node": 2, "to_node": 3, "from_port": "Out", "to_port": "In"},
            ],
        },
    },
)

if response.status_code == 200:
    data = response.json()
    if "project_structure" in data:
        project = data["project_structure"]

        # Check nodes
        nodes = project["Assets"]["$values"][0]["Terrain"]["Nodes"]
        node_count = len([k for k in nodes.keys() if k != "$id"])

        has_export = False
        nodes_with_props = 0

        for node_id, node in nodes.items():
            if node_id != "$id":
                if "Export" in node.get("$type", ""):
                    has_export = True

                # Count actual properties
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
                        "NodeSize",
                        "IsMaskable",
                        "PortCount",
                        "SaveDefinition",
                        "IsLocked",
                        "RenderIntentOverride",
                        "SnapIns",
                    ]
                ]
                if props:
                    nodes_with_props += 1
                    print(f"Node {node.get('Name')} has {len(props)} properties: {props[:5]}...")

        print(f"\nResults:")
        print(f"  Total nodes: {node_count}")
        print(f"  Has Export node: {has_export}")
        print(f"  Nodes with properties: {nodes_with_props}")

        # Save for testing
        with open("test_no_export.json", "w") as f:
            json.dump(project, f, separators=(",", ":"))

        print("\nSaved as test_no_export.json")
        print("\nThis file has:")
        print("  ✓ Properties on nodes (like reference files)")
        print("  ✓ Multiple connected nodes")
        print("  ✓ NO Export node")
        print("  ✓ Simple node IDs (1,2,3)")
else:
    print(f"Error: {response.status_code}")
    print(response.text)
