#!/usr/bin/env python3
"""Recreate Level1.terrain exactly using MCP server"""

import json

import requests


def recreate_level1():
    """Recreate Level1.terrain with exact specifications"""

    url = "http://192.168.0.152:8007/mcp/execute"

    # Extract exact structure from Level1.terrain
    # Using exact IDs, properties, and connections
    payload = {
        "tool": "create_gaea2_project",
        "parameters": {
            "project_name": "Level1_exact_recreation",
            "workflow": {
                "nodes": [
                    # Node 183 - Volcano
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
                            "X": 0.296276,  # Root level X
                            "Y": 0.5,  # Root level Y
                            "Seed": 44922,
                        },
                    },
                    # Node 668 - MountainSide
                    {
                        "id": 668,
                        "type": "MountainSide",
                        "position": {"x": 24472.023, "y": 26073.244},
                        "properties": {
                            "Detail": 0.25,
                            "Style": "Eroded",
                            "Seed": 13946,
                        },
                    },
                    # Node 281 - Combine
                    {
                        "id": 281,
                        "type": "Combine",
                        "position": {"x": 24766.27, "y": 26003.605},
                        "properties": {
                            "PortCount": 2,
                            "Ratio": 0.5,
                            "Mode": "Add",
                            "Clamp": "Clamp",
                        },
                        "node_size": "Small",
                    },
                    # Node 294 - Shear
                    {
                        "id": 294,
                        "type": "Shear",
                        "position": {"x": 24857.084, "y": 25988.941},
                        "properties": {"Strength": 0.5, "Seed": 37768},
                    },
                    # Node 639 - Stratify
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
                    # Node 975 - Crumble
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
                    # Node 514 - Erosion2
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
                    # Node 949 - Rivers
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
                        "node_size": "Standard",
                    },
                    # Node 287 - Sea
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
                    # Node 483 - TextureBase
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
                    # Node 427 - Adjust
                    {
                        "id": 427,
                        "type": "Adjust",
                        "position": {"x": 26481.227, "y": 26068.25},
                        "properties": {"Multiply": 1.0, "Equalize": True},
                        "node_size": "Small",
                    },
                    # Node 340 - SatMap (Blue)
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
                    # Node 800 - SatMap (Rock)
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
                    # Node 375 - SatMap (Color)
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
                    # Node 258 - SatMap
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
                    # Node 958 - Height
                    {
                        "id": 958,
                        "type": "Height",
                        "position": {"x": 26730.877, "y": 26374.682},
                        "properties": {
                            "Range": {"X": 0.87732744, "Y": 1.0},
                            "Falloff": 0.2,
                        },
                    },
                    # Node 245 - Combine (Color blend 1)
                    {
                        "id": 245,
                        "type": "Combine",
                        "position": {"x": 27028.691, "y": 26007.234},
                        "properties": {"PortCount": 2, "Ratio": 1.0, "Clamp": "Clamp"},
                        "node_size": "Small",
                        "render_intent_override": "Color",
                    },
                    # Node 490 - Combine (Color blend 2)
                    {
                        "id": 490,
                        "type": "Combine",
                        "position": {"x": 27150.984, "y": 26008.443},
                        "properties": {"PortCount": 2, "Ratio": 1.0, "Clamp": "Clamp"},
                        "node_size": "Small",
                        "render_intent_override": "Color",
                    },
                    # Node 174 - Combine (Final output)
                    {
                        "id": 174,
                        "type": "Combine",
                        "position": {"x": 27253.555, "y": 26008.443},
                        "properties": {
                            "PortCount": 2,
                            "Ratio": 1.0,
                            "Clamp": "Clamp",
                            "filename": "Combine",
                        },
                        "node_size": "Small",
                        "is_locked": True,
                        "render_intent_override": "Color",
                    },
                ],
                "connections": [
                    # Terrain flow
                    {
                        "from_node": 183,
                        "from_port": "Out",
                        "to_node": 281,
                        "to_port": "In",
                    },
                    {
                        "from_node": 668,
                        "from_port": "Out",
                        "to_node": 281,
                        "to_port": "Input2",
                    },
                    {
                        "from_node": 281,
                        "from_port": "Out",
                        "to_node": 294,
                        "to_port": "In",
                    },
                    {
                        "from_node": 294,
                        "from_port": "Out",
                        "to_node": 639,
                        "to_port": "In",
                    },
                    {
                        "from_node": 639,
                        "from_port": "Out",
                        "to_node": 975,
                        "to_port": "In",
                    },
                    {
                        "from_node": 975,
                        "from_port": "Out",
                        "to_node": 514,
                        "to_port": "In",
                    },
                    {
                        "from_node": 514,
                        "from_port": "Out",
                        "to_node": 949,
                        "to_port": "In",
                    },
                    {
                        "from_node": 949,
                        "from_port": "Out",
                        "to_node": 287,
                        "to_port": "In",
                    },
                    {
                        "from_node": 287,
                        "from_port": "Out",
                        "to_node": 483,
                        "to_port": "In",
                    },
                    # Rivers mask flow
                    {
                        "from_node": 949,
                        "from_port": "Rivers",
                        "to_node": 427,
                        "to_port": "In",
                    },
                    # Color mapping
                    {
                        "from_node": 483,
                        "from_port": "Out",
                        "to_node": 340,
                        "to_port": "In",
                    },
                    {
                        "from_node": 483,
                        "from_port": "Out",
                        "to_node": 800,
                        "to_port": "In",
                    },
                    {
                        "from_node": 483,
                        "from_port": "Out",
                        "to_node": 375,
                        "to_port": "In",
                    },
                    {
                        "from_node": 483,
                        "from_port": "Out",
                        "to_node": 258,
                        "to_port": "In",
                    },
                    # Height mask
                    {
                        "from_node": 287,
                        "from_port": "Out",
                        "to_node": 958,
                        "to_port": "In",
                    },
                    # Color blending
                    {
                        "from_node": 800,
                        "from_port": "Out",
                        "to_node": 245,
                        "to_port": "In",
                    },
                    {
                        "from_node": 375,
                        "from_port": "Out",
                        "to_node": 245,
                        "to_port": "Input2",
                    },
                    {
                        "from_node": 427,
                        "from_port": "Out",
                        "to_node": 245,
                        "to_port": "Mask",
                    },
                    {
                        "from_node": 245,
                        "from_port": "Out",
                        "to_node": 490,
                        "to_port": "In",
                    },
                    {
                        "from_node": 340,
                        "from_port": "Out",
                        "to_node": 490,
                        "to_port": "Input2",
                    },
                    {
                        "from_node": 287,
                        "from_port": "Water",
                        "to_node": 490,
                        "to_port": "Mask",
                    },
                    {
                        "from_node": 490,
                        "from_port": "Out",
                        "to_node": 174,
                        "to_port": "In",
                    },
                    {
                        "from_node": 258,
                        "from_port": "Out",
                        "to_node": 174,
                        "to_port": "Input2",
                    },
                    {
                        "from_node": 958,
                        "from_port": "Out",
                        "to_node": 174,
                        "to_port": "Mask",
                    },
                ],
            },
        },
    }

    try:
        print("Recreating Level1.terrain with MCP server...")
        print(f"Nodes: {len(payload['parameters']['workflow']['nodes'])}")
        print(f"Connections: {len(payload['parameters']['workflow']['connections'])}")

        response = requests.post(url, json=payload, timeout=60)
        response.raise_for_status()

        result = response.json()

        if result.get("success"):
            print(f"\n✓ Successfully created: {result.get('project_name')}")
            print(f"  Saved to: {result.get('saved_path')}")
            print(f"  Nodes: {result.get('node_count')}")
            print(f"  Connections: {result.get('connection_count')}")

            # Save locally for comparison
            if "project_structure" in result:
                with open("Level1_mcp_recreation.terrain", "w") as f:
                    json.dump(result["project_structure"], f)
                print("\n✓ Saved locally as: Level1_mcp_recreation.terrain")

                # Quick validation
                terrain = result["project_structure"]
                nodes = terrain["Assets"]["$values"][0]["Terrain"]["Nodes"]

                # Check some key nodes
                if "183" in nodes:
                    volcano = nodes["183"]
                    print(f"\nVolcano node check:")
                    print(f"  Has X at root: {'X' in volcano}")
                    print(f"  Has Y at root: {'Y' in volcano}")
                    print(f"  Id type: {type(volcano.get('Id'))}")

                print("\nThis recreation should match Level1.terrain structure!")

            return True
        else:
            print(f"✗ Failed: {result}")
            return False

    except Exception as e:
        print(f"✗ Error: {e}")
        if hasattr(e, "response") and e.response is not None:
            print(f"Response: {e.response.text}")
        return False


if __name__ == "__main__":
    recreate_level1()
