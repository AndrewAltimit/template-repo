#!/usr/bin/env python3
"""
Test creating terrain without Export nodes
"""

# import json
# from pathlib import Path

# Create a simple workflow without Export nodes
workflow = {
    "nodes": [
        {
            "id": 100,
            "type": "Mountain",
            "name": "SimpleMountain",
            "position": {"x": 25000, "y": 26000},
            "properties": {"Scale": 1.0, "Height": 0.5, "Style": "Basic", "Seed": 12345, "X": 0.5, "Y": 0.5},
        },
        {
            "id": 101,
            "type": "Erosion2",
            "name": "BasicErosion",
            "position": {"x": 25500, "y": 26000},
            "properties": {"Duration": 0.03, "Downcutting": 0.3, "ErosionScale": 5000, "Seed": 54321},
        },
    ],
    "connections": [{"from_node": 100, "to_node": 101, "from_port": "Out", "to_port": "In"}],
}

print("Testing workflow WITHOUT Export nodes:")
print("Nodes: {}".format([n["type"] for n in workflow["nodes"]]))
print("This matches reference files which have NO Export nodes")
