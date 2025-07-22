#!/usr/bin/env python3
"""Test fixing only the Export node format conflict"""

import json

import requests

print("Testing with Export node format conflict fixed...\n")

# Create the exact failing configuration but fix the Export format conflict
response = requests.post(
    "http://192.168.0.152:8007/mcp/execute",
    json={
        "tool": "create_gaea2_project",
        "parameters": {
            "project_name": "test_export_format_fixed",
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
                        "Duration": 0.15,  # Increased from 0.04
                        "Downcutting": 0.3,
                        "ErosionScale": 5000.0,
                        "Seed": 12345,
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
                    "properties": {
                        # NO Format property here - only in save_definition
                    },
                    "save_definition": {
                        "filename": "TerrainExport",
                        "format": "EXR",  # Single consistent format
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

        # Check Export node structure
        nodes = project["Assets"]["$values"][0]["Terrain"]["Nodes"]
        export_node = nodes.get("104")

        if export_node:
            print("Export node structure:")
            print(f"  Has Format property: {'Format' in export_node}")
            if "Format" in export_node:
                print(f"  Format value: {export_node['Format']}")
            print(f"  Has SaveDefinition: {'SaveDefinition' in export_node}")
            if "SaveDefinition" in export_node:
                print(f"  SaveDefinition.Format: {export_node['SaveDefinition'].get('Format')}")

            # Check for format conflict
            node_format = export_node.get("Format")
            save_format = export_node.get("SaveDefinition", {}).get("Format")

            if node_format and save_format and node_format != save_format:
                print(f"\n❌ FORMAT CONFLICT: Node has '{node_format}', SaveDefinition has '{save_format}'")
            else:
                print(f"\n✓ No format conflict")

        # Save for testing
        with open("test_export_format_fixed.json", "w") as f:
            json.dump(project, f, separators=(",", ":"))

        print("\nSaved as test_export_format_fixed.json")
        print("\nThis file has:")
        print("  - All nodes and properties from failing file")
        print("  - Export node WITHOUT format conflict")
        print("  - Duration increased from 0.04 to 0.15")
else:
    print(f"Error: {response.status_code}")
    print(response.text)
