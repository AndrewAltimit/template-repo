#!/usr/bin/env python3
"""Analyze Snow nodes from working reference files"""

import json

reference_files = [
    "gaea-references/Official Gaea Projects/Canyon River with Sea.terrain",
    "gaea-references/Official Gaea Projects/Summer Tuts Examples/tut-highMountain.terrain",
    "gaea-references/Level10.terrain",
]

print("Analyzing Snow nodes from working reference files...\n")

for ref_file in reference_files:
    try:
        with open(ref_file, "r") as f:
            data = json.load(f)

        print(f"\n{ref_file}:")

        # Find Snow nodes
        terrain = data["Assets"]["$values"][0]["Terrain"]
        nodes = terrain["Nodes"]

        found_snow = False
        for node_id, node in nodes.items():
            if node_id == "$id":
                continue

            if "Snow" in str(node.get("$type", "")):
                found_snow = True
                node_name = node.get("Name", "Unknown")
                print(f"  Found Snow node: {node_name} (ID: {node.get('Id')})")

                # Extract properties
                props = {
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
                        "SaveDefinition",
                        "NodeSize",
                        "PortCount",
                        "IsMaskable",
                    ]
                }

                print(f"  Properties ({len(props)}):")
                for k, v in sorted(props.items()):
                    print(f"    {k}: {v} (type: {type(v).__name__})")

                # Check for specific problematic properties
                if "RealScale" in props:
                    print(f"  ⚠️  Has RealScale: {props['RealScale']}")
                if "MeltType" in props:
                    print(f"  ⚠️  Has MeltType: {props['MeltType']}")

        if not found_snow:
            print("  No Snow nodes found")

    except Exception as e:
        print(f"  Error reading file: {e}")

print("\n\nSummary:")
print("These are WORKING files from gaea-references that contain Snow nodes.")
print("Compare their Snow node properties with our failing Snow nodes.")
