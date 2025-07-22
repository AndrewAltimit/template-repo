#!/usr/bin/env python3
"""Check how X,Y properties are used in reference Mountain/Volcano nodes"""

import glob
import json

reference_files = glob.glob(
    "/home/miku/Documents/repos/template-repo/gaea-references/**/*.terrain",
    recursive=True,
)

print("=== CHECKING X,Y PROPERTIES IN MOUNTAIN/VOLCANO NODES ===\n")

found_examples = 0
for file_path in reference_files:
    if found_examples >= 5:
        break

    try:
        with open(file_path, "r") as f:
            data = json.load(f)

        nodes = data["Assets"]["$values"][0]["Terrain"]["Nodes"]

        for node_id, node in nodes.items():
            if node_id != "$id" and isinstance(node, dict):
                node_type = node.get("$type", "")
                if "Mountain" in node_type or "Volcano" in node_type:
                    if "X" in node or "Y" in node:
                        found_examples += 1
                        print(f"File: {file_path.split('/')[-1]}")
                        print(f"  Node: {node.get('Name')} ({node_type.split('.')[3]})")
                        print(f"  X property: {node.get('X', 'not present')}")
                        print(f"  Y property: {node.get('Y', 'not present')}")
                        print(f"  Position: {node.get('Position')}")

                        # Show all properties
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
                                "NodeSize",
                                "IsMaskable",
                                "PortCount",
                                "SaveDefinition",
                                "IsLocked",
                                "RenderIntentOverride",
                                "SnapIns",
                            ]
                        ]
                        print(f"  All properties: {props}")
                        print()

                        if found_examples >= 5:
                            break

    except Exception as e:
        pass

if found_examples == 0:
    print("No Mountain/Volcano nodes with X,Y properties found!")
else:
    print(f"\n=== CONCLUSION ===")
    print(f"Found {found_examples} examples of Mountain/Volcano nodes with X,Y properties")
    print("These X,Y are node-level parameters (0-1 range), NOT position coordinates!")
    print("They control the terrain generation, not the node placement on canvas")
