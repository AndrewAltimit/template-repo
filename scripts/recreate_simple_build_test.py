#!/usr/bin/env python3
"""Recreate the simple_build_test terrain that previously failed to open"""

import json

import requests


def recreate_simple_build_test():
    """Recreate the terrain with fixed MCP server"""

    url = "http://192.168.0.152:8007/mcp/execute"

    # Recreate the exact same terrain structure
    payload = {
        "tool": "create_gaea2_project",
        "parameters": {
            "project_name": "simple_build_test_fixed",
            "nodes": [
                {
                    "type": "SlopeNoise",
                    "position": {"x": -100, "y": 0},
                    "properties": {"Scale": 50.0, "Seed": 12345},
                },
                {
                    "type": "Erosion2",
                    "position": {"x": 100, "y": 0},
                    "properties": {
                        "Duration": 10.0,
                        "Downcutting": 0.75,
                        "ErosionScale": 10000.0,
                    },
                },
                {
                    "type": "Export",
                    "position": {"x": 300, "y": 0},
                    "properties": {"Filename": "simple_output"},
                },
            ],
            "connections": [
                {
                    "from_node": "SlopeNoise",
                    "from_port": "Out",
                    "to_node": "Erosion2",
                    "to_port": "In",
                },
                {
                    "from_node": "Erosion2",
                    "from_port": "Out",
                    "to_node": "Export",
                    "to_port": "In",
                },
            ],
        },
    }

    try:
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()

        result = response.json()

        if result.get("success"):
            print(f"✓ Successfully created: {result.get('project_name')}")
            print(f"  Saved to: {result.get('saved_path')}")
            print(f"  Nodes: {result.get('node_count')}")
            print(f"  Connections: {result.get('connection_count')}")

            # Save locally for inspection
            if "project_structure" in result:
                with open("simple_build_test_fixed.terrain", "w") as f:
                    json.dump(result["project_structure"], f, indent=2)
                print("\n✓ Saved locally as: simple_build_test_fixed.terrain")
                print("\nThis file should now open correctly in Gaea2!")

            return True
        else:
            print(f"✗ Failed: {result}")
            return False

    except Exception as e:
        print(f"✗ Error: {e}")
        return False


if __name__ == "__main__":
    recreate_simple_build_test()
