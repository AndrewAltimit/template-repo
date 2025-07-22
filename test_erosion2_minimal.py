#!/usr/bin/env python3
"""Test if Erosion2 needs all properties or just Duration"""

import json

import requests

print("Testing Erosion2 with minimal properties...\n")

# Test 1: Add just Duration
response1 = requests.post(
    "http://192.168.0.152:8007/mcp/execute",
    json={
        "tool": "create_gaea2_project",
        "parameters": {
            "project_name": "test_erosion2_duration_only",
            "nodes": [
                {
                    "id": 1,
                    "type": "Mountain",
                    "name": "Mountain",
                    "position": {"x": 25000, "y": 26000},
                    "properties": {"Scale": 1.0, "Height": 0.7, "X": 0.5, "Y": 0.5},
                },
                {
                    "id": 2,
                    "type": "Erosion2",
                    "name": "Erosion",
                    "position": {"x": 25500, "y": 26000},
                    "properties": {
                        "Duration": 0.15,  # Add this explicitly
                        "Downcutting": 0.3,
                        "ErosionScale": 5000.0,
                        "Seed": 12345,
                    },
                },
            ],
            "connections": [{"from_node": 1, "to_node": 2, "from_port": "Out", "to_port": "In"}],
        },
    },
)

if response1.status_code == 200:
    data1 = response1.json()
    if "project_structure" in data1:
        with open("test_erosion2_duration_only.json", "w") as f:
            json.dump(data1["project_structure"], f, separators=(",", ":"))
        print("✓ Created test_erosion2_duration_only.json")

        # Check what properties were added
        nodes = data1["project_structure"]["Assets"]["$values"][0]["Terrain"]["Nodes"]
        erosion = nodes.get("2", {})
        print(f"   Erosion2 Duration: {erosion.get('Duration', 'MISSING')}")

# Test 2: Change Export format to EXR
print("\n\nTesting with Export format EXR...")

response2 = requests.post(
    "http://192.168.0.152:8007/mcp/execute",
    json={
        "tool": "create_gaea2_project",
        "parameters": {
            "project_name": "test_export_exr",
            "nodes": [
                {
                    "id": 100,
                    "type": "Mountain",
                    "name": "BaseTerrain",
                    "position": {"x": 25000, "y": 26000},
                    "properties": {
                        "Scale": 1.0,
                        "Height": 0.7,
                        "Style": "Alpine",
                        "Bulk": "Medium",
                        "X": 0.0,
                        "Y": 0.0,
                    },
                },
                {
                    "id": 101,
                    "type": "Erosion2",
                    "name": "NaturalErosion",
                    "position": {"x": 25500, "y": 26000},
                    "properties": {
                        "Duration": 0.15,  # Explicit Duration
                        "Downcutting": 0.3,
                        "ErosionScale": 5000.0,
                        "Seed": 12345,
                        # Add all the missing properties
                        "BedLoadDischargeAmount": 0.0,
                        "BedLoadDischargeAngle": 0.0,
                        "CoarseSedimentsDischargeAmount": 0.0,
                        "CoarseSedimentsDischargeAngle": 0.0,
                        "SuspendedLoadDischargeAmount": 0.0,
                        "SuspendedLoadDischargeAngle": 0.0,
                        "Shape": 0.5,
                        "ShapeDetailScale": 0.5,
                        "ShapeSharpness": 0.5,
                    },
                },
                {
                    "id": 102,
                    "type": "TextureBase",
                    "name": "BaseTexture",
                    "position": {"x": 26000, "y": 26000},
                    "properties": {
                        "Slope": 0.5,
                        "Scale": 0.5,
                        "Soil": 0.5,
                        "Patches": 0.5,
                        "Chaos": 0.5,
                        "Seed": 0,
                    },
                },
                {
                    "id": 103,
                    "type": "SatMap",
                    "name": "ColorMap",
                    "position": {"x": 26500, "y": 26000},
                    "properties": {
                        "Library": "Rock",
                        "LibraryItem": 0,
                        "Randomize": False,
                        "Range": {"X": 0.5, "Y": 0.5},
                        "Bias": 0.5,
                        "Enhance": "None",
                        "Reverse": False,
                        "Rough": "None",
                        "Hue": 0.0,
                        "Saturation": 0.0,
                        "Lightness": 0.0,
                    },
                },
                {
                    "id": 104,
                    "type": "Export",
                    "name": "TerrainExport",
                    "position": {"x": 27000, "y": 26000},
                    "properties": {},
                    "save_definition": {
                        "filename": "TerrainExport",
                        "format": "EXR",  # Use EXR like working file
                        "enabled": True,
                    },
                },
            ],
            "connections": [
                {"from_node": 100, "to_node": 101, "from_port": "Out", "to_port": "In"},
                {"from_node": 101, "to_node": 102, "from_port": "Out", "to_port": "In"},
                {"from_node": 102, "to_node": 103, "from_port": "Out", "to_port": "In"},
                {"from_node": 103, "to_node": 104, "from_port": "Out", "to_port": "In"},
            ],
        },
    },
)

if response2.status_code == 200:
    data2 = response2.json()
    if "project_structure" in data2:
        with open("test_export_exr.json", "w") as f:
            json.dump(data2["project_structure"], f, separators=(",", ":"))
        print("✓ Created test_export_exr.json")

        # Check Export format
        nodes = data2["project_structure"]["Assets"]["$values"][0]["Terrain"]["Nodes"]
        export = nodes.get("104", {})
        print(f"   Export SaveDefinition.Format: {export.get('SaveDefinition', {}).get('Format')}")

        # Check Erosion2 properties
        erosion = nodes.get("101", {})
        erosion_props = {
            k: v for k, v in erosion.items() if k not in {"$id", "$type", "Id", "Name", "Position", "Ports", "Modifiers"}
        }
        print(f"   Erosion2 property count: {len(erosion_props)}")

print("\n\nThese files should work if:")
print("1. Erosion2 Duration is present")
print("2. Export format is EXR")
print("3. All Erosion2 properties are included")
