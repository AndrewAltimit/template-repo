#!/usr/bin/env python3
"""Test that MCP format fixes allow terrain files to open in Gaea2"""

import json
import sys

import requests


def test_simple_terrain():
    """Create a simple terrain with the fixed MCP server"""

    # Remote MCP server
    url = "http://192.168.0.152:8007/mcp/execute"

    # Create a simple terrain project
    payload = {
        "tool": "create_gaea2_project",
        "parameters": {
            "project_name": "test_format_fix",
            "nodes": [
                {
                    "type": "Fractal",
                    "position": {"x": 0, "y": 0},
                    "properties": {"Seed": 42},
                },
                {
                    "type": "Erosion2",
                    "position": {"x": 200, "y": 0},
                    "properties": {
                        "Duration": 5.0,
                        "Downcutting": 0.5,
                        "Shape": 0.5,
                        "ShapeSharpness": 0.5,
                        "ShapeDetailScale": 0.5,
                    },
                },
                {
                    "type": "Export",
                    "position": {"x": 400, "y": 0},
                    "properties": {"Filename": "test_output"},
                },
            ],
            "connections": [
                {
                    "from_node": "Fractal",
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

        # Check if the result contains the project data
        if "project_structure" in result:
            terrain_data = result["project_structure"]

            # Verify our fixes are present (correct format)
            terrain_obj = terrain_data["Assets"]["$values"][0]["Terrain"]
            state_obj = terrain_data["Assets"]["$values"][0]["State"]

            # Check node IDs are integers
            first_node_key = list(terrain_obj["Nodes"].keys())[1]  # Skip $id key
            first_node = terrain_obj["Nodes"][first_node_key]
            node_id_is_int = isinstance(first_node.get("Id"), int)

            # Check no X/Y at root level of nodes
            has_root_xy = "X" in first_node or "Y" in first_node

            # Check Groups/Notes/Camera format (should NOT have $values)
            groups_correct = "Groups" in terrain_obj and "$values" not in terrain_obj["Groups"]
            notes_correct = "Notes" in terrain_obj and "$values" not in terrain_obj["Notes"]
            camera_correct = "Camera" in state_obj["Viewport"] and "$values" not in state_obj["Viewport"]["Camera"]

            checks = {
                "Node ID is integer": node_id_is_int,
                "No X/Y at node root": not has_root_xy,
                "Groups format correct (no $values)": groups_correct,
                "Notes format correct (no $values)": notes_correct,
                "Camera format correct (no $values)": camera_correct,
            }

            print("Format Fix Verification:")
            print("-" * 40)

            for check, passed in checks.items():
                status = "✓ PASS" if passed else "✗ FAIL"
                print(f"{check}: {status}")

            # Show the actual structures
            print("\nActual Structures:")
            print("-" * 40)

            print(f"First node ID type: {type(first_node.get('Id'))} = {first_node.get('Id')}")
            print(f"Node has X at root: {'X' in first_node}")
            print(f"Node has Y at root: {'Y' in first_node}")

            groups = terrain_obj.get("Groups", {})
            print(f"\nGroups: {json.dumps(groups, indent=2)}")

            notes = terrain_obj.get("Notes", {})
            print(f"Notes: {json.dumps(notes, indent=2)}")

            camera = state_obj["Viewport"].get("Camera", {})
            print(f"Camera: {json.dumps(camera, indent=2)}")

            # Save the test file
            output_path = "/home/miku/Documents/repos/template-repo/test_format_fix.terrain"
            with open(output_path, "w") as f:
                json.dump(terrain_data, f, indent=2)

            print(f"\nTest terrain saved to: {output_path}")
            print("\nNOTE: The MCP server needs to be restarted to pick up the fixes!")

            return all(checks.values())
        else:
            print("Error: No terrain file in response")
            print(f"Response: {json.dumps(result, indent=2)}")
            return False

    except Exception as e:
        print(f"Error testing MCP server: {e}")
        return False


if __name__ == "__main__":
    success = test_simple_terrain()
    sys.exit(0 if success else 1)
