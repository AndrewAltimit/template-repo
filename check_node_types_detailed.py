#!/usr/bin/env python3
"""Check node types in detail"""

import json


def get_node_type(node):
    """Extract node type from $type field"""
    if "$type" in node:
        # Format: "QuadSpinner.Gaea.Nodes.Mountain, Gaea.Nodes"
        type_str = node["$type"]
        parts = type_str.split(".")
        if len(parts) >= 4:
            return parts[3].split(",")[0]  # Get "Mountain" from "Mountain, Gaea"
    return "Unknown"


failing_files = [
    "regression_volcanic_island.json",
    "regression_mountain_range.json",
    "regression_detailed_mountain.json",
    "regression_coastal_cliffs.json",
    "regression_canyon_system.json",
    "regression_arctic_terrain.json",
]

print("=== NODE TYPE ANALYSIS ===\n")

# Collect all unique node types from failing files
all_node_types = set()
node_occurrences = {}

for filename in failing_files:
    with open(filename, "r") as f:
        data = json.load(f)

    terrain = data["Assets"]["$values"][0]["Terrain"]
    nodes = terrain["Nodes"]

    print(f"{filename}:")
    file_nodes = []

    for node_id, node in nodes.items():
        if node_id == "$id":
            continue

        node_type = get_node_type(node)
        all_node_types.add(node_type)

        if node_type not in node_occurrences:
            node_occurrences[node_type] = []
        node_occurrences[node_type].append(filename)

        file_nodes.append(node_type)

    print(f"  Nodes: {', '.join(file_nodes)}\n")

# Find nodes that appear in multiple failing files
print("\n=== NODE FREQUENCY IN FAILING FILES ===")
for node_type, files in sorted(node_occurrences.items()):
    if len(files) > 1:
        print(f"{node_type}: appears in {len(files)} files")

# Check specific problematic nodes
problematic = [
    "Beach",
    "Coast",
    "Lakes",
    "Snow",
    "Glacier",
    "SeaLevel",
    "LavaFlow",
    "ThermalShatter",
]
print("\n=== CHECKING SPECIFIC PROBLEMATIC NODES ===")
for prob in problematic:
    if prob in node_occurrences:
        print(f"\n{prob} appears in:")
        for file in node_occurrences[prob]:
            print(f"  - {file}")

# Let's check the Snow node specifically since it appears in multiple failing files
print("\n\n=== SNOW NODE DETAILED ANALYSIS ===")
for filename in [
    "regression_mountain_range.json",
    "regression_detailed_mountain.json",
    "regression_arctic_terrain.json",
]:
    try:
        with open(filename, "r") as f:
            data = json.load(f)

        terrain = data["Assets"]["$values"][0]["Terrain"]
        nodes = terrain["Nodes"]

        for node_id, node in nodes.items():
            if node_id == "$id":
                continue

            node_type = get_node_type(node)
            if node_type == "Snow":
                print(f"\n{filename} - Snow node:")
                properties = {
                    k: v
                    for k, v in node.items()
                    if k
                    not in [
                        "$id",
                        "$type",
                        "Id",
                        "Name",
                        "Position",
                        "Ports",
                        "Modifiers",
                    ]
                }
                print(f"  Properties ({len(properties)}):")
                for k, v in properties.items():
                    print(f"    {k}: {v}")
                break
    except:
        pass
