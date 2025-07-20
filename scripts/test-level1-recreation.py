#!/usr/bin/env python3
"""
Test script to recreate Level1.terrain with all proper connections
"""

import json
from datetime import datetime

import requests


def create_level1_terrain():
    """Create Level1 terrain with all nodes and connections"""

    # Define all nodes based on the reference Level1.terrain
    nodes = [
        {
            "id": 183,
            "type": "Volcano",
            "position": {"x": 24472.023, "y": 25987.605},
            "properties": {
                "Scale": 1.0131434,
                "Height": 0.5547645,
                "Mouth": 0.85706466,
                "Bulk": -0.1467689,
                "Surface": "Eroded",
                "X": 0.296276,
                "Y": 0.5,
                "Seed": 44922,
            },
        },
        {
            "id": 668,
            "type": "MountainSide",
            "position": {"x": 24472.023, "y": 26073.244},
            "properties": {"Detail": 0.25, "Style": "Eroded", "Seed": 13946},
        },
        {
            "id": 427,
            "type": "Adjust",
            "position": {"x": 26481.227, "y": 26068.25},
            "properties": {"Multiply": 1.0, "Equalize": True},
        },
        {
            "id": 281,
            "type": "Combine",
            "position": {"x": 24766.27, "y": 26003.605},
            "properties": {"Ratio": 0.5, "Mode": "Add", "Clamp": "Clamp"},
        },
        {
            "id": 294,
            "type": "Shear",
            "position": {"x": 24857.084, "y": 25988.941},
            "properties": {"Strength": 0.5, "Seed": 37768},
        },
        {
            "id": 949,
            "type": "Rivers",
            "position": {"x": 25814.795, "y": 26000.443},
            "properties": {
                "Water": 0.5,
                "Width": 0.8865791,
                "Depth": 0.9246184,
                "Downcutting": 0.3400796,
                "RiverValleyWidth": "zero",
                "Headwaters": 200,
                "RenderSurface": True,
                "Seed": 21713,
            },
            "save_definition": {"filename": "Rivers", "format": "EXR", "enabled": True},
        },
        {
            "id": 483,
            "type": "TextureBase",
            "position": {"x": 26398.227, "y": 25987.605},
            "properties": {
                "Slope": 0.48291308,
                "Scale": 0.15,
                "Soil": 0.6,
                "Patches": 0.4,
                "Chaos": 0.1,
                "Seed": 48091,
            },
        },
        {
            "id": 800,
            "type": "SatMap",
            "position": {"x": 26730.877, "y": 25991.234},
            "properties": {
                "Library": "Rock",
                "LibraryItem": 33,
                "Enhance": "Autolevel",
            },
        },
        {
            "id": 375,
            "type": "SatMap",
            "position": {"x": 26730.877, "y": 26127.748},
            "properties": {
                "Library": "Color",
                "LibraryItem": 1,
                "Enhance": "Autolevel",
                "Reverse": True,
            },
        },
        {
            "id": 245,
            "type": "Combine",
            "position": {"x": 27028.691, "y": 26007.234},
            "properties": {"Ratio": 1.0, "Clamp": "Clamp"},
            "render_intent_override": "Color",
        },
        {
            "id": 958,
            "type": "Height",
            "position": {"x": 26730.877, "y": 26374.682},
            "properties": {"Range": {"X": 0.87732744, "Y": 1.0}, "Falloff": 0.2},
        },
        {
            "id": 174,
            "type": "Combine",
            "position": {"x": 27253.555, "y": 26008.443},
            "properties": {"Ratio": 1.0, "Clamp": "Clamp"},
            "is_locked": True,
            "render_intent_override": "Color",
            "save_definition": {
                "filename": "Combine",
                "format": "EXR",
                "enabled": True,
            },
        },
        {
            "id": 258,
            "type": "SatMap",
            "position": {"x": 26730.877, "y": 26268.732},
            "properties": {
                "LibraryItem": 497,
                "Range": {"X": 4.77996e-09, "Y": 1.0},
                "Bias": -0.03888215,
                "Enhance": "Autolevel",
                "Reverse": True,
            },
        },
        {
            "id": 975,
            "type": "Crumble",
            "position": {"x": 25354.795, "y": 25993.234},
            "properties": {
                "Duration": 0.49972618,
                "Strength": 0.8713034,
                "Coverage": 0.75,
                "Horizontal": 0.45,
                "RockHardness": 0.45,
                "Edge": 0.45,
                "Depth": 0.2,
            },
        },
        {
            "id": 639,
            "type": "Stratify",
            "position": {"x": 25087.084, "y": 25988.941},
            "properties": {
                "Spacing": 0.1,
                "Octaves": 12,
                "Intensity": 0.5,
                "Seed": 28787,
                "TiltAmount": 0.5,
            },
        },
        {
            "id": 514,
            "type": "Erosion2",
            "position": {"x": 25584.795, "y": 25997.244},
            "properties": {
                "Duration": 1.6352992,
                "Downcutting": 0.8118839,
                "ErosionScale": 15620.922,
                "Seed": 22790,
                "SuspendedLoadDischargeAmount": 1.0,
                "SuspendedLoadDischargeAngle": 13.726726,
                "BedLoadDischargeAmount": 0.65662646,
                "BedLoadDischargeAngle": 38.36254,
                "CoarseSedimentsDischargeAmount": 0.4989047,
                "CoarseSedimentsDischargeAngle": 18.901972,
                "Shape": 0.4234392,
                "ShapeSharpness": 0.6,
                "ShapeDetailScale": 0.25,
            },
        },
        {
            "id": 287,
            "type": "Sea",
            "position": {"x": 26090.918, "y": 25997.244},
            "properties": {
                "Level": 0.1,
                "CoastalErosion": True,
                "ShoreSize": 0.68630886,
                "ShoreHeight": 0.2,
                "Variation": 0.48576123,
                "UniformVariations": True,
                "ExtraCliffDetails": True,
                "RenderSurface": True,
            },
        },
        {
            "id": 490,
            "type": "Combine",
            "position": {"x": 27150.984, "y": 26008.443},
            "properties": {"Ratio": 1.0, "Clamp": "Clamp"},
            "render_intent_override": "Color",
        },
        {
            "id": 340,
            "type": "SatMap",
            "position": {"x": 26730.877, "y": 25873.07},
            "properties": {
                "Library": "Blue",
                "LibraryItem": 66,
                "Enhance": "Autolevel",
            },
        },
    ]

    # Define all connections based on the reference Level1.terrain
    connections = [
        # Basic terrain flow
        {"from_node": 183, "to_node": 281, "from_port": "Out", "to_port": "In"},
        {"from_node": 668, "to_node": 281, "from_port": "Out", "to_port": "Input2"},
        {"from_node": 281, "to_node": 294, "from_port": "Out", "to_port": "In"},
        {"from_node": 294, "to_node": 639, "from_port": "Out", "to_port": "In"},
        {"from_node": 639, "to_node": 975, "from_port": "Out", "to_port": "In"},
        {"from_node": 975, "to_node": 514, "from_port": "Out", "to_port": "In"},
        {"from_node": 514, "to_node": 949, "from_port": "Out", "to_port": "In"},
        {"from_node": 949, "to_node": 287, "from_port": "Out", "to_port": "In"},
        # Rivers to Adjust
        {"from_node": 949, "to_node": 427, "from_port": "Rivers", "to_port": "In"},
        # Sea to TextureBase
        {"from_node": 287, "to_node": 483, "from_port": "Out", "to_port": "In"},
        # TextureBase to SatMaps
        {"from_node": 483, "to_node": 800, "from_port": "Out", "to_port": "In"},
        {"from_node": 483, "to_node": 375, "from_port": "Out", "to_port": "In"},
        {"from_node": 483, "to_node": 340, "from_port": "Out", "to_port": "In"},
        {"from_node": 483, "to_node": 258, "from_port": "Out", "to_port": "In"},
        # First Combine (245)
        {"from_node": 800, "to_node": 245, "from_port": "Out", "to_port": "In"},
        {"from_node": 375, "to_node": 245, "from_port": "Out", "to_port": "Input2"},
        {"from_node": 427, "to_node": 245, "from_port": "Out", "to_port": "Mask"},
        # Second Combine (490)
        {"from_node": 245, "to_node": 490, "from_port": "Out", "to_port": "In"},
        {"from_node": 340, "to_node": 490, "from_port": "Out", "to_port": "Input2"},
        {"from_node": 287, "to_node": 490, "from_port": "Water", "to_port": "Mask"},
        # Height selector
        {"from_node": 287, "to_node": 958, "from_port": "Out", "to_port": "In"},
        # Final Combine (174)
        {"from_node": 490, "to_node": 174, "from_port": "Out", "to_port": "In"},
        {"from_node": 258, "to_node": 174, "from_port": "Out", "to_port": "Input2"},
        {"from_node": 958, "to_node": 174, "from_port": "Out", "to_port": "Mask"},
    ]

    # Create the request
    url = "http://192.168.0.152:8007/mcp/execute"

    payload = {
        "tool": "create_gaea2_project",
        "parameters": {
            "project_name": "level1_complete_fixed",
            "nodes": nodes,
            "connections": connections,
            "auto_validate": False,  # Don't let validation remove connections
            "output_path": "output/gaea2/level1_complete_fixed.terrain",
        },
    }

    print(f"Creating Level1 terrain with {len(nodes)} nodes and {len(connections)} connections...")
    print(f"Request URL: {url}")
    print(f"Timestamp: {datetime.now().isoformat()}")

    try:
        response = requests.post(url, json=payload, timeout=30)
        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            print("Success!")
            print(json.dumps(result, indent=2))
        else:
            print(f"Error: {response.text}")

    except Exception as e:
        print(f"Failed to connect to Gaea2 MCP server: {e}")
        print("Make sure the server is running at 192.168.0.152:8007")


if __name__ == "__main__":
    create_level1_terrain()
