#!/usr/bin/env python3
"""Test creating minimal Gaea2 projects with no properties or Export nodes"""

import json

import requests

print("Testing minimal Gaea2 project creation...")

# Test 1: Single Mountain node with no properties (like working example)
response = requests.post(
    "http://192.168.0.152:8007/mcp/execute",
    json={
        "tool": "create_gaea2_project",
        "parameters": {
            "project_name": "test_minimal_mountain",
            "nodes": [
                {
                    "id": 1,
                    "type": "Mountain",
                    "name": "Mountain",
                    "position": {"x": 24000, "y": 26000},
                    # No properties! This is key
                }
            ],
            "connections": [],
        },
    },
)

if response.status_code == 200:
    data = response.json()
    if "project_structure" in data:
        project = data["project_structure"]

        # Check if Export node was added (it shouldn't be)
        nodes = project["Assets"]["$values"][0]["Terrain"]["Nodes"]
        export_found = False
        for node_id, node in nodes.items():
            if node_id != "$id" and "Export" in node.get("$type", ""):
                export_found = True
                print("❌ Export node was added (shouldn't be there)")
                break

        if not export_found:
            print("✓ No Export node added (correct)")

        # Check Mountain node properties
        if "1" in nodes:
            mountain = nodes["1"]

            # Check if properties were added
            prop_count = 0
            for key in mountain:
                if key not in ["$id", "$type", "Id", "Name", "Position", "Ports", "Modifiers"]:
                    prop_count += 1
                    print(f"  Found property: {key} = {mountain[key]}")

            if prop_count == 0:
                print("✓ Mountain node has no properties (correct)")
            else:
                print(f"❌ Mountain node has {prop_count} properties (should be 0)")

        # Save for inspection
        with open("test_minimal_mountain.json", "w") as f:
            json.dump(project, f, separators=(",", ":"))

        print("\nSaved as test_minimal_mountain.json")
else:
    print(f"Error: {response.status_code}")
    print(response.text)

# Test 2: Test with template to ensure no Export nodes added
print("\n\nTesting template creation...")
response = requests.post(
    "http://192.168.0.152:8007/mcp/execute",
    json={
        "tool": "create_gaea2_from_template",
        "parameters": {"template_name": "basic_terrain", "project_name": "test_minimal_template"},
    },
)

if response.status_code == 200:
    data = response.json()
    if "project_structure" in data:
        project = data["project_structure"]

        # Check nodes
        nodes = project["Assets"]["$values"][0]["Terrain"]["Nodes"]
        node_count = len([k for k in nodes.keys() if k != "$id"])
        export_count = 0
        nodes_with_props = 0

        for node_id, node in nodes.items():
            if node_id != "$id":
                if "Export" in node.get("$type", ""):
                    export_count += 1

                # Count properties
                prop_count = 0
                for key in node:
                    if key not in [
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
                        "IsLocked",
                        "RenderIntentOverride",
                        "SaveDefinition",
                    ]:
                        prop_count += 1

                if prop_count > 0:
                    nodes_with_props += 1
                    print(f"  Node {node.get('Name')} has {prop_count} properties")

        print(f"\nTemplate results:")
        print(f"  Total nodes: {node_count}")
        print(f"  Export nodes: {export_count}")
        print(f"  Nodes with properties: {nodes_with_props}")

        # Save for inspection
        with open("test_minimal_template.json", "w") as f:
            json.dump(project, f, separators=(",", ":"))

        print("\nSaved as test_minimal_template.json")
else:
    print(f"Error: {response.status_code}")
    print(response.text)

print("\nDone! Check the generated JSON files.")
