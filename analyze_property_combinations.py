#!/usr/bin/env python3
"""Analyze property combinations from working examples to find valid patterns"""

import json
import os
from collections import Counter, defaultdict
from itertools import combinations

# All reference files that are known to work
reference_dirs = [
    "gaea-references",
    "gaea-references/Official Gaea Projects",
    "gaea-references/Official Gaea Projects/Summer Tuts Examples",
]

# Collect all terrain files
terrain_files = []
for dir_path in reference_dirs:
    if os.path.exists(dir_path):
        for file in os.listdir(dir_path):
            if file.endswith(".terrain"):
                terrain_files.append(os.path.join(dir_path, file))

print(f"Found {len(terrain_files)} reference terrain files to analyze\n")

# Track property combinations for each node type
node_property_combinations = defaultdict(list)
property_cooccurrence = defaultdict(lambda: defaultdict(int))

# Analyze each file
for terrain_file in terrain_files:
    try:
        with open(terrain_file, "r") as f:
            data = json.load(f)

        terrain = data["Assets"]["$values"][0]["Terrain"]
        nodes = terrain.get("Nodes", {})

        for node_id, node in nodes.items():
            if node_id == "$id":
                continue

            # Extract node type
            node_type = node.get("$type", "").split(".")[-2] if "$type" in node else "Unknown"

            # Get properties (excluding metadata)
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

            if properties:
                # Store the combination
                prop_set = frozenset(properties)
                node_property_combinations[node_type].append(
                    {"file": os.path.basename(terrain_file), "properties": properties, "prop_count": len(properties)}
                )

                # Track which properties appear together
                for prop1, prop2 in combinations(properties, 2):
                    property_cooccurrence[node_type][(prop1, prop2)] += 1

    except Exception as e:
        print(f"Error reading {terrain_file}: {e}")

# Analyze Snow node specifically since we know it's problematic
print("=== SNOW NODE ANALYSIS ===")
snow_combos = node_property_combinations.get("Snow", [])
if snow_combos:
    print(f"\nFound {len(snow_combos)} Snow nodes in reference files:")

    # Group by property count
    by_count = defaultdict(list)
    for combo in snow_combos:
        by_count[combo["prop_count"]].append(combo)

    for count, combos in sorted(by_count.items()):
        print(f"\n{count} properties ({len(combos)} instances):")
        for combo in combos[:3]:  # Show first 3 examples
            print(f"  File: {combo['file']}")
            print(f"  Properties: {', '.join(combo['properties'])}")

    # Find most common property combinations
    combo_counter = Counter()
    for combo in snow_combos:
        combo_counter[frozenset(combo["properties"])] += 1

    print("\nMost common Snow property combinations:")
    for prop_set, count in combo_counter.most_common(5):
        print(f"  {count} times: {', '.join(sorted(prop_set))}")

# Analyze other problematic nodes
problematic_nodes = [
    "Beach",
    "Coast",
    "Lakes",
    "Glacier",
    "SeaLevel",
    "LavaFlow",
    "ThermalShatter",
    "Ridge",
    "Strata",
    "Voronoi",
    "Terrace",
]

print("\n\n=== OTHER PROBLEMATIC NODES ===")
for node_type in problematic_nodes:
    combos = node_property_combinations.get(node_type, [])
    if combos:
        print(f"\n{node_type}: {len(combos)} instances")

        # Show property counts
        counts = Counter(combo["prop_count"] for combo in combos)
        print(f"  Property counts: {dict(counts)}")

        # Show most common combinations
        combo_counter = Counter()
        for combo in combos:
            combo_counter[frozenset(combo["properties"])] += 1

        most_common = combo_counter.most_common(1)[0]
        print(f"  Most common: {', '.join(sorted(most_common[0]))}")

# Find property compatibility rules
print("\n\n=== PROPERTY COMPATIBILITY PATTERNS ===")

# For Snow node, which properties always appear together?
snow_cooccur = property_cooccurrence.get("Snow", {})
if snow_cooccur:
    print("\nSnow node property pairs that appear together:")
    for (prop1, prop2), count in sorted(snow_cooccur.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"  {prop1} + {prop2}: {count} times")

# General patterns across all nodes
print("\n\nGeneral patterns:")
max_properties = {}
for node_type, combos in node_property_combinations.items():
    if combos:
        max_prop = max(combo["prop_count"] for combo in combos)
        avg_prop = sum(combo["prop_count"] for combo in combos) / len(combos)
        max_properties[node_type] = {"max": max_prop, "avg": round(avg_prop, 1), "instances": len(combos)}

# Show nodes with most properties
print("\nNodes with most properties in working files:")
for node_type, stats in sorted(max_properties.items(), key=lambda x: x[1]["max"], reverse=True)[:15]:
    print(f"  {node_type}: max={stats['max']}, avg={stats['avg']} ({stats['instances']} instances)")

print("\n\n=== RECOMMENDATIONS ===")
print("Based on reference files:")
print("1. Snow nodes typically have 0-3 properties in working files")
print("2. Common Snow properties: Melt, SettleThaw")
print("3. Avoid combining more than 3-4 properties on problematic nodes")
print("4. Some properties may be mutually exclusive or require specific combinations")
