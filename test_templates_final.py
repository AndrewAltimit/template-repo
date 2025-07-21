#!/usr/bin/env python3
"""Final test of templates after property limitation fix"""

import json

import requests

print("Testing templates after property limitation fix...\n")

# Test one of the previously failing templates
print("Testing arctic_terrain template...")
response = requests.post(
    "http://192.168.0.152:8007/mcp/execute",
    json={
        "tool": "create_gaea2_from_template",
        "parameters": {"template_name": "arctic_terrain", "project_name": "test_arctic_final"},
    },
)

if response.status_code == 200:
    data = response.json()
    if "project_structure" in data:
        nodes = data["project_structure"]["Assets"]["$values"][0]["Terrain"]["Nodes"]

        # Check all problematic nodes
        problematic_nodes = ["Snow", "Glacier", "Lakes"]

        for node_id, node in nodes.items():
            if node_id == "$id":
                continue

            node_type = node.get("$type", "").split(".")[-2].split(",")[0] if "$type" in node else "Unknown"

            if node_type in problematic_nodes:
                properties = [
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
                        "SaveDefinition",
                        "NodeSize",
                        "PortCount",
                        "IsMaskable",
                    ]
                ]

                print(f"\n{node_type} node:")
                print(f"  Property count: {len(properties)} (should be ≤ 3)")
                print(f"  Properties: {', '.join(properties)}")

                if len(properties) > 3:
                    print("  ❌ TOO MANY PROPERTIES!")
                else:
                    print("  ✅ Property count is acceptable")

        # Save the file
        with open("test_arctic_final.terrain", "w") as f:
            json.dump(data["project_structure"], f, separators=(",", ":"))
        print("\n✓ Created test_arctic_final.terrain")

print("\n\nPlease test test_arctic_final.terrain in Gaea2.")
print("If it opens successfully, the property limitation fix is working!")
