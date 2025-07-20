#!/usr/bin/env python3
"""
Check Export nodes in reference files
"""

import json
from pathlib import Path

# Check multiple reference files for Export nodes
ref_files = list(Path("reference projects").rglob("*.terrain"))[:10]

print("Checking Export nodes in reference files...\n")

files_with_export = 0
files_without_export = 0

for ref_file in ref_files:
    try:
        with open(ref_file, "r") as f:
            data = json.load(f)

        nodes = data["Assets"]["$values"][0]["Terrain"]["Nodes"]
        export_nodes = []

        for node_id, node in nodes.items():
            if isinstance(node, dict) and "Export" in node.get("$type", ""):
                export_nodes.append((node_id, node))

        if export_nodes:
            files_with_export += 1
            print(f"{ref_file.name} - Found {len(export_nodes)} Export nodes")
            for node_id, node in export_nodes:
                props = [k for k in node.keys() if k not in ["$id", "Ports", "Modifiers", "SnapIns", "Position", "$type"]]
                print(f"  ID: {node_id}, Properties: {props}")
                if "Format" in node:
                    print("    Format value: {}".format(node["Format"]))
        else:
            files_without_export += 1

    except Exception as e:
        print(f"Error reading {ref_file.name}: {e}")

print("\n=== SUMMARY ===")
print(f"Files WITH Export nodes: {files_with_export}")
print(f"Files WITHOUT Export nodes: {files_without_export}")
print("\nCONCLUSION: If most working files don't have Export nodes, that might be our issue!")
