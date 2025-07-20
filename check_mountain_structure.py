#!/usr/bin/env python3
"""
Check Mountain node structure in reference files
"""

import json
from pathlib import Path

# Find all terrain files
terrain_files = list(Path("reference projects").rglob("*.terrain"))

print(f"Checking Mountain nodes in {len(terrain_files)} files...\n")

mountain_nodes_found = 0
mountains_with_xy = 0
mountains_with_fractal = 0
mountains_with_properties_at_root = 0

for terrain_file in terrain_files:
    try:
        with open(terrain_file, "r") as f:
            data = json.load(f)

        nodes = data["Assets"]["$values"][0]["Terrain"]["Nodes"]

        for node_id, node in nodes.items():
            if node_id == "$id":
                continue

            if isinstance(node, dict) and "Mountain" in node.get("$type", ""):
                mountain_nodes_found += 1

                # Check for X,Y at root
                if "X" in node and "Y" in node:
                    mountains_with_xy += 1
                    print(f"\n{terrain_file.name} - Mountain node:")
                    print(f"  Has X,Y at root: X={node['X']}, Y={node['Y']}")

                # Check for Fractal object
                if "Fractal" in node:
                    mountains_with_fractal += 1
                    print(f"  Has Fractal object with keys: {list(node['Fractal'].keys())}")

                # Check for fractal properties at root
                fractal_props = ["Octaves", "Complexity", "RidgeWeight", "Persistence", "Lacunarity"]
                root_fractal_props = [p for p in fractal_props if p in node]
                if root_fractal_props:
                    mountains_with_properties_at_root += 1
                    print(f"  ❌ Has fractal properties at ROOT: {root_fractal_props}")

                # Show all root keys for first few
                if mountain_nodes_found <= 3:
                    print(f"  All root keys: {sorted(node.keys())}")

    except Exception:
        pass

print("\n=== SUMMARY ===")
print(f"Mountain nodes found: {mountain_nodes_found}")
print(f"Mountains with X,Y at root: {mountains_with_xy}")
print(f"Mountains with Fractal object: {mountains_with_fractal}")
print(f"Mountains with fractal props at root: {mountains_with_properties_at_root}")

print("\n=== CONCLUSION ===")
if mountains_with_xy == mountain_nodes_found:
    print("✅ ALL Mountain nodes have X,Y at root level")
else:
    print("❌ Some Mountain nodes are missing X,Y at root")

if mountains_with_fractal > 0 and mountains_with_properties_at_root == 0:
    print("✅ Fractal properties are properly nested")
elif mountains_with_properties_at_root > 0:
    print("❌ Some Mountains have fractal properties at root (should be nested)")
