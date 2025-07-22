#!/usr/bin/env python3
"""Test the exact configuration that was failing before our fixes"""

import json

import requests

print("Testing previously failing configuration with fixes...\n")

# Create the exact same configuration that was failing
response = requests.post(
    "http://192.168.0.152:8007/mcp/execute",
    json={
        "tool": "create_gaea2_project",
        "parameters": {
            "project_name": "test_fixed_regression",
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
                        "ReduceDetails": False,
                        "Seed": 0,
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
                        # Duration will now default to 0.15 instead of 0.04
                        "Downcutting": 0.3,
                        "ErosionScale": 5000.0,
                        "Seed": 12345,
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
                    "properties": {
                        "Format": "PNG",  # This should be removed by our fix
                    },
                    "save_definition": {
                        "filename": "TerrainExport",
                        "format": "EXR",
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

if response.status_code == 200:
    data = response.json()
    if "project_structure" in data:
        project = data["project_structure"]

        # Check if our fixes are applied
        nodes = project["Assets"]["$values"][0]["Terrain"]["Nodes"]

        print("Checking fixes:\n")

        # 1. Check Export node format handling
        export_node = nodes.get("104")
        if export_node:
            has_format_prop = "Format" in export_node
            save_def_format = export_node.get("SaveDefinition", {}).get("Format")

            print("1. Export node format fix:")
            print(f"   Has Format property: {has_format_prop}")
            print(f"   SaveDefinition.Format: {save_def_format}")

            if not has_format_prop and save_def_format:
                print("   ✓ Format conflict fixed!")
            else:
                print("   ✗ Format conflict still present")

        # 2. Check Erosion2 Duration
        erosion_node = nodes.get("101")
        if erosion_node:
            duration = erosion_node.get("Duration", "not set")
            print(f"\n2. Erosion2 Duration:")
            print(f"   Duration value: {duration}")

            if duration == "not set" or (isinstance(duration, (int, float)) and duration >= 0.15):
                print("   ✓ Duration is reasonable (>= 0.15 or using default)")
            else:
                print(f"   ✗ Duration too low: {duration}")

        # 3. Check all connections
        connection_count = 0
        for node_id, node in nodes.items():
            if node_id != "$id" and "Ports" in node:
                for port in node["Ports"].get("$values", []):
                    if "Record" in port:
                        connection_count += 1

        print(f"\n3. Connections:")
        print(f"   Total connections: {connection_count}")
        print(f"   Expected: 4")
        if connection_count == 4:
            print("   ✓ All connections present")

        # Save the file
        with open("test_fixed_regression.json", "w") as f:
            json.dump(project, f, separators=(",", ":"))

        print("\nSaved as test_fixed_regression.json")
        print("\nThis file should now open in Gaea2!")

        # Also test the basic template
        print("\n\n=== Testing basic_terrain template ===")

        response2 = requests.post(
            "http://192.168.0.152:8007/mcp/execute",
            json={
                "tool": "create_gaea2_from_template",
                "parameters": {
                    "template_name": "basic_terrain",
                    "project_name": "test_fixed_template",
                },
            },
        )

        if response2.status_code == 200:
            data2 = response2.json()
            if "project_structure" in data2:
                with open("test_fixed_template.json", "w") as f:
                    json.dump(data2["project_structure"], f, separators=(",", ":"))
                print("✓ Created test_fixed_template.json from template")
else:
    print(f"Error: {response.status_code}")
    print(response.text)
