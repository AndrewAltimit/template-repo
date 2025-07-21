#!/usr/bin/env python3
"""Check if reference files have properties on their nodes"""

import glob
import json
import os

reference_files = glob.glob("/home/miku/Documents/repos/template-repo/gaea-references/**/*.terrain", recursive=True)

print(f"Checking {len(reference_files)} reference files...\n")

files_with_properties = 0
files_without_properties = 0
total_nodes_checked = 0
nodes_with_properties = 0
nodes_without_properties = 0

# Fields that are NOT considered properties
SYSTEM_FIELDS = {
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
    "SaveDefinition",
    "IsLocked",
    "RenderIntentOverride",
    "SnapIns",
}

for file_path in reference_files[:10]:  # Check first 10 files
    try:
        with open(file_path, "r") as f:
            data = json.load(f)

        nodes = data["Assets"]["$values"][0]["Terrain"]["Nodes"]
        file_has_properties = False

        for node_id, node in nodes.items():
            if node_id != "$id" and isinstance(node, dict):
                total_nodes_checked += 1

                # Find actual properties (not system fields)
                props = [k for k in node.keys() if k not in SYSTEM_FIELDS]

                if props:
                    nodes_with_properties += 1
                    file_has_properties = True
                    if files_with_properties == 0:  # First example
                        print(f"Example from {os.path.basename(file_path)}:")
                        print(f"  Node '{node.get('Name', node_id)}' has properties: {props}")
                        print()
                else:
                    nodes_without_properties += 1

        if file_has_properties:
            files_with_properties += 1
        else:
            files_without_properties += 1

    except Exception as e:
        print(f"Error reading {file_path}: {e}")

print(f"\nSUMMARY:")
print(f"Files with properties: {files_with_properties}/{files_with_properties + files_without_properties}")
print(f"Files without properties: {files_without_properties}/{files_with_properties + files_without_properties}")
print(f"Nodes with properties: {nodes_with_properties}/{total_nodes_checked}")
print(f"Nodes without properties: {nodes_without_properties}/{total_nodes_checked}")

print(f"\nCONCLUSION:")
if files_with_properties > 0:
    print("✓ Reference files DO have node properties - they are valid!")
else:
    print("✗ Reference files have NO node properties")
