#!/usr/bin/env python3
"""Analyze failing Gaea2 files to find common patterns"""

import json
import sys
from collections import defaultdict

import requests

print("Analyzing failing Gaea2 files to find common patterns...\n")

# Define the working and failing files based on user feedback
working_files = [
    "test_minimal_mode",
    "test_full_mode",
    "test_regression_smart",
    "test_smart_mode",
    "regression_volcanic_terrain",
    "regression_river_valley",
    "regression_desert_canyon",
    "regression_basic_terrain",
]

failing_files = [
    "regression_volcanic_island",
    "regression_mountain_range",
    "regression_detailed_mountain",
    "regression_coastal_cliffs",
    "regression_canyon_system",
    "regression_arctic_terrain",
    "perf_test",
]


def fetch_file_from_server(project_name):
    """Fetch a project file from the Gaea2 server"""
    try:
        # Try to fetch the file using the list projects endpoint
        response = requests.post(
            "http://192.168.0.152:8007/mcp/execute",
            json={"tool": "list_gaea2_projects"},
        )

        if response.status_code == 200:
            data = response.json()
            projects = data.get("projects", [])

            # Find the project
            for project in projects:
                if project["name"] == project_name:
                    # Load the project content
                    with open(project["path"], "r") as f:
                        return json.load(f)

        # If not found, try direct file read
        # Assume these are in the same directory as other test files
        try:
            with open(f"{project_name}.terrain", "r") as f:
                return json.load(f)
        except:
            with open(f"{project_name}.json", "r") as f:
                return json.load(f)

    except Exception as e:
        print(f"  Error fetching {project_name}: {e}")
        return None


# Analyze node types and properties
failing_node_types = defaultdict(int)
working_node_types = defaultdict(int)
failing_properties = defaultdict(list)
working_properties = defaultdict(list)

print("Fetching and analyzing failing files...")
for file_name in failing_files:
    print(f"  Analyzing {file_name}...")
    content = fetch_file_from_server(file_name)
    if content and "Assets" in content:
        terrain = content["Assets"]["$values"][0]["Terrain"]
        nodes = terrain.get("Nodes", {})

        for node_id, node in nodes.items():
            if node_id not in ["$id"]:
                node_type = node.get("$type", "").split(".")[-2] if "$type" in node else "Unknown"
                failing_node_types[node_type] += 1

                # Collect properties
                props = [
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
                failing_properties[node_type].extend(props)

print("\nFetching and analyzing working files...")
for file_name in working_files:
    print(f"  Analyzing {file_name}...")
    content = fetch_file_from_server(file_name)
    if content and "Assets" in content:
        terrain = content["Assets"]["$values"][0]["Terrain"]
        nodes = terrain.get("Nodes", {})

        for node_id, node in nodes.items():
            if node_id not in ["$id"]:
                node_type = node.get("$type", "").split(".")[-2] if "$type" in node else "Unknown"
                working_node_types[node_type] += 1

                # Collect properties
                props = [
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
                working_properties[node_type].extend(props)

# Find nodes unique to failing files
print("\n=== ANALYSIS RESULTS ===\n")

print("Node types unique to FAILING files:")
failing_only = set(failing_node_types.keys()) - set(working_node_types.keys())
for node_type in failing_only:
    print(f"  - {node_type} (appears {failing_node_types[node_type]} times)")

print("\nNode types unique to WORKING files:")
working_only = set(working_node_types.keys()) - set(failing_node_types.keys())
for node_type in working_only:
    print(f"  - {node_type} (appears {working_node_types[node_type]} times)")

# Check for specific problematic nodes
print("\nChecking for specific problematic nodes...")
problematic_nodes = [
    "ColorSpace",
    "Rivers",
    "Lakes",
    "Sea",
    "Snow",
    "FractalTerraces",
    "Coast",
]
for node in problematic_nodes:
    in_failing = failing_node_types.get(node, 0)
    in_working = working_node_types.get(node, 0)
    if in_failing > 0:
        print(f"  {node}: {in_failing} in failing, {in_working} in working")

# Analyze property differences for common nodes
print("\nProperty analysis for common nodes:")
common_nodes = set(failing_node_types.keys()) & set(working_node_types.keys())
for node_type in sorted(common_nodes):
    failing_props_set = set(failing_properties[node_type])
    working_props_set = set(working_properties[node_type])

    # Properties only in failing files
    failing_only_props = failing_props_set - working_props_set
    if failing_only_props:
        print(f"\n  {node_type}:")
        print(f"    Properties only in failing: {failing_only_props}")

# Check for Export node differences
print("\n\nExport node analysis:")
failing_export_count = 0
working_export_count = 0

for file_name in failing_files:
    content = fetch_file_from_server(file_name)
    if content and "Assets" in content:
        terrain = content["Assets"]["$values"][0]["Terrain"]
        nodes = terrain.get("Nodes", {})
        export_count = sum(1 for n in nodes.values() if "Export" in str(n.get("$type", "")))
        if export_count > 0:
            failing_export_count += 1
            print(f"  {file_name}: {export_count} Export nodes")

print(f"\nTotal failing files with Export nodes: {failing_export_count}/{len(failing_files)}")

# Look for specific patterns in failing files
print("\n\nSpecific pattern analysis:")

# Check the first failing file in detail
print("\nDetailed analysis of regression_arctic_terrain:")
arctic_content = fetch_file_from_server("regression_arctic_terrain")
if arctic_content and "Assets" in arctic_content:
    terrain = arctic_content["Assets"]["$values"][0]["Terrain"]
    nodes = terrain.get("Nodes", {})

    # Check for ColorSpace node (known to be problematic)
    for node_id, node in nodes.items():
        if "ColorSpace" in str(node.get("$type", "")):
            print(f"  Found ColorSpace node: {node_id}")
            print(
                f"    Properties: {[k for k in node.keys() if k not in ['$id', '$type', 'Id', 'Name', 'Position', 'Ports', 'Modifiers']]}"
            )
        if "Sea" in str(node.get("$type", "")):
            print(f"  Found Sea node: {node_id}")
            print(
                f"    Properties: {[k for k in node.keys() if k not in ['$id', '$type', 'Id', 'Name', 'Position', 'Ports', 'Modifiers']]}"
            )

print("\n\nSummary:")
print("- Failing files tend to have more complex nodes")
print("- Check for ColorSpace, Rivers, Sea, Lakes nodes")
print("- Property counts and formats may differ")
print("- Export node configuration might be different")
