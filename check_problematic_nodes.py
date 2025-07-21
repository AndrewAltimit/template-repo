#!/usr/bin/env python3
"""Check specific nodes that appear only in failing files"""

import json

# Nodes that appear ONLY in failing files
problematic_nodes = [
    "Beach",
    "Voronoi",
    "ThermalShatter",
    "SeaLevel",
    "LavaFlow",
    "Lakes",
    "Strata",
    "Coast",
    "Snow",
    "Glacier",
    "Terrace",
    "Ridge",
]

# Also check nodes that appear in both but might have issues
check_also = ["Rivers", "FractalTerraces"]

failing_files = [
    "regression_volcanic_island.json",
    "regression_mountain_range.json",
    "regression_detailed_mountain.json",
    "regression_coastal_cliffs.json",
    "regression_canyon_system.json",
    "regression_arctic_terrain.json",
]

print("=== PROBLEMATIC NODE ANALYSIS ===\n")

all_nodes_to_check = problematic_nodes + check_also

for filename in failing_files:
    with open(filename, "r") as f:
        data = json.load(f)

    terrain = data["Assets"]["$values"][0]["Terrain"]
    nodes = terrain["Nodes"]

    print(f"\n{filename}:")
    found_problematic = []

    for node_id, node in nodes.items():
        if node_id == "$id":
            continue

        node_type = node.get("$type", "").split(".")[-2] if "$type" in node else "Unknown"

        if node_type in all_nodes_to_check:
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
            found_problematic.append(
                {
                    "type": node_type,
                    "id": node.get("Id"),
                    "name": node.get("Name"),
                    "prop_count": len(properties),
                    "properties": properties,
                }
            )

    if found_problematic:
        for prob in found_problematic:
            print(f"  - {prob['type']} (ID: {prob['id']}, Name: {prob['name']})")
            print(
                f"    Properties ({prob['prop_count']}): {', '.join(prob['properties'][:10])}{'...' if len(prob['properties']) > 10 else ''}"
            )

# Let's also check a specific failing file in detail
print("\n\n=== DETAILED CHECK: regression_arctic_terrain.json ===")
with open("regression_arctic_terrain.json", "r") as f:
    arctic_data = json.load(f)

terrain = arctic_data["Assets"]["$values"][0]["Terrain"]
nodes = terrain["Nodes"]

print(f"Total nodes: {len([n for n in nodes if n != '$id'])}")
print("\nAll nodes:")
for node_id, node in nodes.items():
    if node_id == "$id":
        continue

    node_type = node.get("$type", "").split(".")[-2] if "$type" in node else "Unknown"
    node_name = node.get("Name", "Unknown")
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

    print(f"  {node_type} ({node_name}): {len(properties)} properties")

    # Check for specific issues
    if node_type == "Snow":
        print(f"    Snow properties: {properties}")
    if node_type == "Lakes":
        print(f"    Lakes properties: {properties}")

# Let's also check if property values might be the issue
print("\n\n=== CHECKING PROPERTY VALUES ===")
# Check Snow node in detail
for node_id, node in nodes.items():
    if node_id == "$id":
        continue

    node_type = node.get("$type", "").split(".")[-2] if "$type" in node else "Unknown"
    if node_type == "Snow":
        print(f"\nSnow node full details:")
        for key, value in node.items():
            if key not in ["Ports", "Modifiers"]:
                print(f"  {key}: {value}")
