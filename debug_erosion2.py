#!/usr/bin/env python3
"""Debug why Erosion2 still has invalid properties"""

import json

# Check the actual output
with open("rivers_fix_output.json", "r") as f:
    data = json.load(f)

nodes = data["Assets"]["$values"][0]["Terrain"]["Nodes"]

# Find Erosion2 node
for node_id, node in nodes.items():
    if isinstance(node, dict) and "Erosion2" in node.get("$type", ""):
        print(f"Erosion2 node {node_id}:")
        print("\nAll properties in order:")
        for i, (key, value) in enumerate(node.items()):
            if key not in ["Ports", "Modifiers", "SnapIns"]:  # Skip large objects
                print(f"  {i+1}. {key}: {value}")
        
        print("\n❌ INVALID PROPERTIES FOUND:")
        invalid_props = ["Rock Softness", "Base Level", "Intensity"]
        for prop in invalid_props:
            if prop in node:
                print(f"  - {prop}: {node[prop]}")