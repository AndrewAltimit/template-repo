#!/usr/bin/env python3
"""Analyze Rivers nodes from reference projects"""

import json


def analyze_rivers_node(node_data, file_name):
    """Extract and analyze a Rivers node structure"""
    print(f"\n{'='*60}")
    print(f"File: {file_name}")
    print(f"{'='*60}")

    # Get all properties at the node level
    excluded_keys = {"$id", "$type", "Id", "Name", "Position", "Ports", "Modifiers", "SnapIns", "SaveDefinition"}

    properties = {k: v for k, v in node_data.items() if k not in excluded_keys}

    print("\nAll Properties at Node Level:")
    for key, value in sorted(properties.items()):
        print(f"  - {key}: {value} ({type(value).__name__})")

    # Check for SaveDefinition
    if "SaveDefinition" in node_data:
        print("\nSaveDefinition (EMBEDDED in node):")
        save_def = node_data["SaveDefinition"]
        print(f"  - Node: {save_def.get('Node')}")
        print(f"  - Filename: {save_def.get('Filename')}")
        print(f"  - Format: {save_def.get('Format')}")
        print(f"  - IsEnabled: {save_def.get('IsEnabled')}")

    # Check ports
    if "Ports" in node_data:
        ports = node_data["Ports"]["$values"]
        print(f"\nPorts ({len(ports)} total):")
        for port in ports:
            print(f"  - {port['Name']} ({port['Type']})")

    return properties


def find_rivers_nodes(file_path):
    """Find all Rivers nodes in a terrain file"""
    try:
        with open(file_path, "r") as f:
            data = json.load(f)

        nodes = data["Assets"]["$values"][0]["Terrain"]["Nodes"]
        rivers_nodes = []

        for node_id, node in nodes.items():
            if isinstance(node, dict) and "Rivers" in node.get("$type", ""):
                rivers_nodes.append((node_id, node))

        return rivers_nodes
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return []


def main():
    # Files that contain Rivers nodes
    files_to_check = [
        "reference projects/mikus files/Level1.terrain",
        "reference projects/mikus files/Level3.terrain",
        "reference projects/Official Gaea Projects/Summer Tuts Examples/tut-riverValley.terrain",
        "reference projects/mikus files/Level8.terrain",
    ]

    all_properties = {}

    for file_path in files_to_check:
        full_path = f"/home/miku/Documents/repos/template-repo/{file_path}"
        rivers_nodes = find_rivers_nodes(full_path)

        for node_id, node_data in rivers_nodes:
            props = analyze_rivers_node(node_data, file_path)

            # Collect all unique properties
            for prop, value in props.items():
                if prop not in all_properties:
                    all_properties[prop] = []
                all_properties[prop].append((file_path, value))

    print(f"\n{'='*60}")
    print("SUMMARY: All Unique Properties Found in Rivers Nodes")
    print(f"{'='*60}")

    for prop, occurrences in sorted(all_properties.items()):
        print(f"\n{prop}:")
        for file_path, value in occurrences[:3]:  # Show first 3 examples
            print(f"  - {file_path.split('/')[-1]}: {value}")


if __name__ == "__main__":
    main()
