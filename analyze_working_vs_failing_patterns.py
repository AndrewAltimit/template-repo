#!/usr/bin/env python3
"""Deep analysis of working vs failing Gaea2 files"""

import json
from collections import defaultdict

# Based on user feedback
working_files = [
    "regression_volcanic_terrain.json",
    "regression_river_valley.json",
    "regression_desert_canyon.json",
    "regression_basic_terrain.json",
]

failing_files = [
    "regression_volcanic_island.json",
    "regression_mountain_range.json",
    "regression_detailed_mountain.json",
    "regression_coastal_cliffs.json",
    "regression_canyon_system.json",
    "regression_arctic_terrain.json",
]


def analyze_file(filename):
    """Analyze a single file for key characteristics"""
    try:
        with open(filename, "r") as f:
            data = json.load(f)

        terrain = data["Assets"]["$values"][0]["Terrain"]
        nodes = terrain["Nodes"]

        # Count node types
        node_types = defaultdict(int)
        node_details = {}

        for node_id, node in nodes.items():
            if node_id == "$id":
                continue

            node_type = node.get("$type", "").split(".")[-2] if "$type" in node else "Unknown"
            node_types[node_type] += 1

            # Store details for specific problematic nodes
            if node_type in [
                "ColorSpace",
                "Rivers",
                "Lakes",
                "Sea",
                "Snow",
                "Coast",
                "FractalTerraces",
            ]:
                node_details[f"{node_type}_{node_id}"] = {
                    "type": node_type,
                    "id": node_id,
                    "properties": [
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
                    ],
                    "prop_count": len(
                        [
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
                    ),
                }

        # Count total nodes and connections
        total_nodes = len([n for n in nodes if n != "$id"])

        # Count connections
        total_connections = 0
        for node in nodes.values():
            if isinstance(node, dict) and "Ports" in node:
                for port in node["Ports"].get("$values", []):
                    if "Record" in port:
                        total_connections += 1

        return {
            "filename": filename,
            "total_nodes": total_nodes,
            "total_connections": total_connections,
            "node_types": dict(node_types),
            "node_details": node_details,
        }
    except Exception as e:
        print(f"Error analyzing {filename}: {e}")
        return None


print("=== WORKING VS FAILING FILES ANALYSIS ===\n")

# Analyze working files
print("WORKING FILES:")
working_analyses = []
for file in working_files:
    analysis = analyze_file(file)
    if analysis:
        working_analyses.append(analysis)
        print(f"\n{file}:")
        print(f"  Total nodes: {analysis['total_nodes']}")
        print(f"  Total connections: {analysis['total_connections']}")
        print(f"  Node types: {', '.join(analysis['node_types'].keys())}")
        if analysis["node_details"]:
            print(f"  Problematic nodes found: {', '.join(analysis['node_details'].keys())}")

# Analyze failing files
print("\n\nFAILING FILES:")
failing_analyses = []
for file in failing_files:
    analysis = analyze_file(file)
    if analysis:
        failing_analyses.append(analysis)
        print(f"\n{file}:")
        print(f"  Total nodes: {analysis['total_nodes']}")
        print(f"  Total connections: {analysis['total_connections']}")
        print(f"  Node types: {', '.join(analysis['node_types'].keys())}")
        if analysis["node_details"]:
            print(f"  Problematic nodes found: {', '.join(analysis['node_details'].keys())}")

# Find patterns
print("\n\n=== PATTERN ANALYSIS ===")

# Collect all node types
all_working_nodes = set()
all_failing_nodes = set()

for analysis in working_analyses:
    all_working_nodes.update(analysis["node_types"].keys())

for analysis in failing_analyses:
    all_failing_nodes.update(analysis["node_types"].keys())

# Nodes unique to failing files
failing_only_nodes = all_failing_nodes - all_working_nodes
print(f"\nNode types ONLY in failing files: {failing_only_nodes}")

# Specific problematic nodes
problematic_in_failing = defaultdict(list)
for analysis in failing_analyses:
    for detail_key, detail in analysis["node_details"].items():
        problematic_in_failing[detail["type"]].append(
            {
                "file": analysis["filename"],
                "prop_count": detail["prop_count"],
                "properties": detail["properties"],
            }
        )

if problematic_in_failing:
    print("\nProblematic nodes in failing files:")
    for node_type, occurrences in problematic_in_failing.items():
        print(f"\n  {node_type}:")
        for occ in occurrences:
            print(f"    - {occ['file']}: {occ['prop_count']} properties")
            if occ["prop_count"] > 0:
                print(f"      Properties: {', '.join(occ['properties'][:5])}{'...' if len(occ['properties']) > 5 else ''}")

# Check for ColorSpace node specifically
print("\n\n=== COLORSPACE NODE ANALYSIS ===")
for analysis in failing_analyses:
    if "ColorSpace" in analysis["node_types"]:
        print(f"\n{analysis['filename']} has ColorSpace node")

# Let's also check specific nodes that might be problematic
print("\n\n=== SPECIFIC NODE CHECK ===")
suspicious_nodes = ["ColorSpace", "Rivers", "Sea", "Lakes", "Coast", "Snow"]
for node in suspicious_nodes:
    in_working = sum(1 for a in working_analyses if node in a["node_types"])
    in_failing = sum(1 for a in failing_analyses if node in a["node_types"])
    if in_failing > 0:
        print(
            f"{node}: {in_failing}/{len(failing_analyses)} failing files, {in_working}/{len(working_analyses)} working files"
        )

print("\n\n=== RECOMMENDATIONS ===")
print("1. ColorSpace node appears to be problematic")
print("2. Complex water nodes (Rivers, Sea, Lakes) may need special handling")
print("3. Check if these nodes have specific property requirements")
print("4. Consider removing or replacing ColorSpace nodes")
