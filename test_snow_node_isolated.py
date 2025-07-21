#!/usr/bin/env python3
"""Test creating a simple project with just a Snow node to isolate the issue"""

import json

import requests

print("Testing Snow node in isolation...\n")

# Test 1: Minimal project with Snow node
print("1. Creating minimal project with Snow node (property_mode=minimal)...")
config1 = {
    "project_name": "test_snow_minimal",
    "property_mode": "minimal",
    "nodes": [
        {"id": 1, "type": "Mountain", "name": "BaseTerrain", "position": {"x": 25000, "y": 26000}},
        {"id": 2, "type": "Snow", "name": "SnowLayer", "position": {"x": 25500, "y": 26000}},
    ],
    "connections": [{"from_node": 1, "to_node": 2, "from_port": "Out", "to_port": "In"}],
}

response1 = requests.post(
    "http://192.168.0.152:8007/mcp/execute", json={"tool": "create_gaea2_project", "parameters": config1}
)

if response1.status_code == 200:
    data1 = response1.json()
    if "project_structure" in data1:
        with open("test_snow_minimal.terrain", "w") as f:
            json.dump(data1["project_structure"], f, separators=(",", ":"))
        print("  ✓ Created test_snow_minimal.terrain")

# Test 2: Snow node with full properties
print("\n2. Creating project with Snow node (property_mode=full)...")
config2 = {
    "project_name": "test_snow_full",
    "property_mode": "full",
    "nodes": [
        {"id": 1, "type": "Mountain", "name": "BaseTerrain", "position": {"x": 25000, "y": 26000}},
        {"id": 2, "type": "Snow", "name": "SnowLayer", "position": {"x": 25500, "y": 26000}},
    ],
    "connections": [{"from_node": 1, "to_node": 2, "from_port": "Out", "to_port": "In"}],
}

response2 = requests.post(
    "http://192.168.0.152:8007/mcp/execute", json={"tool": "create_gaea2_project", "parameters": config2}
)

if response2.status_code == 200:
    data2 = response2.json()
    if "project_structure" in data2:
        nodes = data2["project_structure"]["Assets"]["$values"][0]["Terrain"]["Nodes"]
        snow_node = nodes.get("2", {})
        print(
            f"  Snow node properties: {[k for k in snow_node.keys() if k not in ['$id', '$type', 'Id', 'Name', 'Position', 'Ports', 'Modifiers']]}"
        )

        with open("test_snow_full.terrain", "w") as f:
            json.dump(data2["project_structure"], f, separators=(",", ":"))
        print("  ✓ Created test_snow_full.terrain")

# Test 3: Just Mountain without Snow (control)
print("\n3. Creating control project without Snow...")
config3 = {
    "project_name": "test_no_snow",
    "property_mode": "minimal",
    "nodes": [{"id": 1, "type": "Mountain", "name": "BaseTerrain", "position": {"x": 25000, "y": 26000}}],
    "connections": [],
}

response3 = requests.post(
    "http://192.168.0.152:8007/mcp/execute", json={"tool": "create_gaea2_project", "parameters": config3}
)

if response3.status_code == 200:
    data3 = response3.json()
    if "project_structure" in data3:
        with open("test_no_snow.terrain", "w") as f:
            json.dump(data3["project_structure"], f, separators=(",", ":"))
        print("  ✓ Created test_no_snow.terrain (control)")

print("\n\nTest Summary:")
print("1. test_snow_minimal.terrain - Snow with no properties")
print("2. test_snow_full.terrain - Snow with all default properties")
print("3. test_no_snow.terrain - Control without Snow")
print("\nIf test_no_snow works but the Snow ones fail, the Snow node is the issue.")
print("If test_snow_minimal works but test_snow_full fails, it's a property issue.")
