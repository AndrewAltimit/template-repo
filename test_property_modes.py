#!/usr/bin/env python3
"""Test the new property_mode parameter"""

import json

import requests

print("Testing property modes for Gaea2 project creation...\n")

# The same configuration but with different property modes
base_config = {
    "project_name": "test_property_mode",
    "nodes": [
        {
            "id": 100,
            "type": "Mountain",
            "name": "BaseTerrain",
            "position": {"x": 25000, "y": 26000},
            "properties": {"Scale": 1.0, "Height": 0.7, "X": 0.0, "Y": 0.0},
        },
        {
            "id": 101,
            "type": "Erosion2",
            "name": "NaturalErosion",
            "position": {"x": 25500, "y": 26000},
            "properties": {
                # Only provide a few properties
                "Downcutting": 0.3,
                "ErosionScale": 5000.0,
                "Seed": 12345
                # Missing: Duration and many others
            },
        },
        {
            "id": 102,
            "type": "Export",
            "name": "TerrainExport",
            "position": {"x": 26000, "y": 26000},
            "properties": {},
            "save_definition": {"filename": "terrain_output", "format": "EXR", "enabled": True},
        },
    ],
    "connections": [
        {"from_node": 100, "to_node": 101, "from_port": "Out", "to_port": "In"},
        {"from_node": 101, "to_node": 102, "from_port": "Out", "to_port": "In"},
    ],
}

# Test 1: Minimal mode (default)
print("1. Testing minimal mode (default):")
config1 = base_config.copy()
config1["project_name"] = "test_minimal_mode"

response1 = requests.post(
    "http://192.168.0.152:8007/mcp/execute", json={"tool": "create_gaea2_project", "parameters": config1}
)

if response1.status_code == 200:
    data1 = response1.json()
    if "project_structure" in data1:
        nodes = data1["project_structure"]["Assets"]["$values"][0]["Terrain"]["Nodes"]
        erosion = nodes.get("101", {})
        print(f"   Erosion2 has Duration: {'Duration' in erosion}")
        print(
            f"   Erosion2 property count: {len([k for k in erosion.keys() if k not in ['$id', '$type', 'Id', 'Name', 'Position', 'Ports', 'Modifiers']])}"
        )

# Test 2: Full mode (like templates)
print("\n2. Testing full mode:")
config2 = base_config.copy()
config2["project_name"] = "test_full_mode"
config2["property_mode"] = "full"

response2 = requests.post(
    "http://192.168.0.152:8007/mcp/execute", json={"tool": "create_gaea2_project", "parameters": config2}
)

if response2.status_code == 200:
    data2 = response2.json()
    if "project_structure" in data2:
        nodes = data2["project_structure"]["Assets"]["$values"][0]["Terrain"]["Nodes"]
        erosion = nodes.get("101", {})
        print(f"   Erosion2 has Duration: {'Duration' in erosion}")
        print(f"   Erosion2 Duration value: {erosion.get('Duration', 'MISSING')}")
        print(
            f"   Erosion2 property count: {len([k for k in erosion.keys() if k not in ['$id', '$type', 'Id', 'Name', 'Position', 'Ports', 'Modifiers']])}"
        )

        with open("test_full_mode.json", "w") as f:
            json.dump(data2["project_structure"], f, separators=(",", ":"))
        print("   ✓ Saved as test_full_mode.json")

# Test 3: Smart mode
print("\n3. Testing smart mode:")
config3 = base_config.copy()
config3["project_name"] = "test_smart_mode"
config3["property_mode"] = "smart"

response3 = requests.post(
    "http://192.168.0.152:8007/mcp/execute", json={"tool": "create_gaea2_project", "parameters": config3}
)

if response3.status_code == 200:
    data3 = response3.json()
    if "project_structure" in data3:
        nodes = data3["project_structure"]["Assets"]["$values"][0]["Terrain"]["Nodes"]

        mountain = nodes.get("100", {})
        erosion = nodes.get("101", {})

        mountain_props = len(
            [k for k in mountain.keys() if k not in ["$id", "$type", "Id", "Name", "Position", "Ports", "Modifiers"]]
        )
        erosion_props = len(
            [k for k in erosion.keys() if k not in ["$id", "$type", "Id", "Name", "Position", "Ports", "Modifiers"]]
        )

        print(f"   Mountain property count: {mountain_props} (should be minimal)")
        print(f"   Erosion2 property count: {erosion_props} (should be full)")
        print(f"   Erosion2 has Duration: {'Duration' in erosion}")

        with open("test_smart_mode.json", "w") as f:
            json.dump(data3["project_structure"], f, separators=(",", ":"))
        print("   ✓ Saved as test_smart_mode.json")

print("\n\nSummary:")
print("- minimal mode: Only uses provided properties")
print("- full mode: Adds all default properties (like templates)")
print("- smart mode: Adds defaults only for complex nodes like Erosion2")
print("\nThe 'full' and 'smart' mode files should work with Gaea2!")
