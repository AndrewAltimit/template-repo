#!/usr/bin/env python3
"""Test removing problematic nodes from a failing template"""

import json

import requests

print("Testing template modification to remove problematic nodes...\n")

# First, let's get the arctic terrain template (which fails)
print("1. Fetching arctic_terrain template configuration...")
response = requests.post(
    "http://192.168.0.152:8007/mcp/execute",
    json={
        "tool": "create_gaea2_from_template",
        "parameters": {
            "template_name": "arctic_terrain",
            "project_name": "test_arctic_original",
            "save_to_disk": False,  # Just get the structure
        },
    },
)

if response.status_code == 200:
    data = response.json()
    original_structure = data.get("project_structure")

    if original_structure:
        # Extract nodes
        nodes = original_structure["Assets"]["$values"][0]["Terrain"]["Nodes"]

        # Find problematic nodes
        problematic_found = []
        for node_id, node in nodes.items():
            if node_id == "$id":
                continue

            node_type = node.get("$type", "").split(".")[-2].split(",")[0] if "$type" in node else "Unknown"
            if node_type in ["Snow", "Glacier", "Lakes"]:
                problematic_found.append((node_id, node_type, node.get("Name")))

        print(f"  Found problematic nodes: {problematic_found}")

        # Now create a modified version without problematic nodes
        print("\n2. Creating modified arctic terrain without Snow, Glacier, and Lakes...")

        # Modified arctic terrain - simpler version
        modified_config = {
            "project_name": "test_arctic_modified",
            "property_mode": "smart",
            "nodes": [
                {
                    "id": 1,
                    "type": "Mountain",
                    "name": "ArcticMountains",
                    "position": {"x": 25000, "y": 26000},
                    "properties": {"Scale": 3.0, "Height": 0.9, "Style": "Alpine", "Bulk": "High", "Seed": 67890},
                },
                {
                    "id": 2,
                    "type": "Thermal",
                    "name": "FrostShatter",
                    "position": {"x": 25500, "y": 26000},
                    "properties": {"Duration": 0.8, "Intensity": 0.6, "Slip": 0.3, "Seed": 11111},
                },
                {
                    "id": 3,
                    "type": "Erosion2",
                    "name": "GlacialErosion",
                    "position": {"x": 26000, "y": 26000},
                    "properties": {"Duration": 0.20, "Downcutting": 0.2, "ErosionScale": 8000.0, "Seed": 22222},
                },
                {
                    "id": 4,
                    "type": "SatMap",
                    "name": "ArcticColors",
                    "position": {"x": 26500, "y": 26000},
                    "properties": {"Library": "Snow", "Enhance": "Autolevel"},
                },
                {
                    "id": 5,
                    "type": "Export",
                    "name": "TerrainExport",
                    "position": {"x": 27000, "y": 26000},
                    "properties": {},
                    "save_definition": {"filename": "arctic_terrain", "format": "EXR", "enabled": True},
                },
            ],
            "connections": [
                {"from_node": 1, "to_node": 2, "from_port": "Out", "to_port": "In"},
                {"from_node": 2, "to_node": 3, "from_port": "Out", "to_port": "In"},
                {"from_node": 3, "to_node": 4, "from_port": "Out", "to_port": "In"},
                {"from_node": 4, "to_node": 5, "from_port": "Out", "to_port": "In"},
            ],
        }

        response2 = requests.post(
            "http://192.168.0.152:8007/mcp/execute", json={"tool": "create_gaea2_project", "parameters": modified_config}
        )

        if response2.status_code == 200:
            data2 = response2.json()
            if "project_structure" in data2:
                with open("test_arctic_modified.terrain", "w") as f:
                    json.dump(data2["project_structure"], f, separators=(",", ":"))
                print("  ✓ Created test_arctic_modified.terrain (without problematic nodes)")

# Test another failing template - mountain_range
print("\n3. Creating modified mountain_range without Snow and Ridge...")
modified_mountain_config = {
    "project_name": "test_mountain_modified",
    "property_mode": "smart",
    "nodes": [
        {
            "id": 1,
            "type": "Mountain",
            "name": "MainMountain",
            "position": {"x": 25000, "y": 26000},
            "properties": {"Scale": 2.0, "Height": 0.8, "Style": "Alpine", "Seed": 12345},
        },
        {
            "id": 2,
            "type": "Mountain",  # Replace Ridge with another Mountain
            "name": "SecondaryPeaks",
            "position": {"x": 25000, "y": 26500},
            "properties": {"Scale": 1.5, "Height": 0.6, "Style": "Eroded", "Seed": 23456},
        },
        {
            "id": 3,
            "type": "Combine",
            "name": "MergePeaks",
            "position": {"x": 25500, "y": 26250},
            "properties": {"Mode": "Max", "Ratio": 0.6},
        },
        {
            "id": 4,
            "type": "Erosion2",
            "name": "MountainErosion",
            "position": {"x": 26000, "y": 26250},
            "properties": {"Duration": 0.15, "Downcutting": 0.4, "ErosionScale": 6000.0},
        },
        {
            "id": 5,
            "type": "SatMap",
            "name": "MountainColors",
            "position": {"x": 26500, "y": 26250},
            "properties": {"Library": "Rock", "Enhance": "Equalize"},
        },
        {
            "id": 6,
            "type": "Export",
            "name": "TerrainExport",
            "position": {"x": 27000, "y": 26250},
            "properties": {},
            "save_definition": {"filename": "mountain_range", "format": "EXR", "enabled": True},
        },
    ],
    "connections": [
        {"from_node": 1, "to_node": 3, "from_port": "Out", "to_port": "In"},
        {"from_node": 2, "to_node": 3, "from_port": "Out", "to_port": "Input2"},
        {"from_node": 3, "to_node": 4, "from_port": "Out", "to_port": "In"},
        {"from_node": 4, "to_node": 5, "from_port": "Out", "to_port": "In"},
        {"from_node": 5, "to_node": 6, "from_port": "Out", "to_port": "In"},
    ],
}

response3 = requests.post(
    "http://192.168.0.152:8007/mcp/execute", json={"tool": "create_gaea2_project", "parameters": modified_mountain_config}
)

if response3.status_code == 200:
    data3 = response3.json()
    if "project_structure" in data3:
        with open("test_mountain_modified.terrain", "w") as f:
            json.dump(data3["project_structure"], f, separators=(",", ":"))
        print("  ✓ Created test_mountain_modified.terrain (without Snow and Ridge)")

print("\n\nSummary:")
print("Created two modified terrain files that should work:")
print("1. test_arctic_modified.terrain - Arctic terrain without Snow, Glacier, Lakes")
print("2. test_mountain_modified.terrain - Mountain range without Snow and Ridge")
print("\nThese use only nodes that are known to work from the successful files.")
