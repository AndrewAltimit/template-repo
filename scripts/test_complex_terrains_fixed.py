#!/usr/bin/env python3
"""Test complex terrain generation with fixed MCP server"""

import json
import time

import requests


def test_terrain(name, tool="create_gaea2_from_template", params=None):
    """Test a terrain configuration"""
    url = "http://192.168.0.152:8007/mcp/execute"

    if params is None:
        params = {"template_name": name, "project_name": f"{name}_test_fixed"}

    payload = {"tool": tool, "parameters": params}

    try:
        print(f"\nTesting: {name}")
        print("-" * 50)

        response = requests.post(url, json=payload, timeout=60)
        response.raise_for_status()

        result = response.json()

        if result.get("success"):
            print(f"✓ Success: {result.get('project_name', name)}")
            print(f"  Nodes: {result.get('node_count', 'N/A')}")
            print(f"  Connections: {result.get('connection_count', 'N/A')}")

            # Verify format fixes are present
            if "project_structure" in result:
                terrain = result["project_structure"]
                asset = terrain["Assets"]["$values"][0]

                checks = []
                if "Groups" in asset["Terrain"]:
                    has_values = "$values" in asset["Terrain"]["Groups"]
                    checks.append(("Groups format", has_values))

                if "Notes" in asset["Terrain"]:
                    has_values = "$values" in asset["Terrain"]["Notes"]
                    checks.append(("Notes format", has_values))

                if "Camera" in asset["State"]["Viewport"]:
                    has_props = "Position" in asset["State"]["Viewport"]["Camera"]
                    checks.append(("Camera format", has_props))

                for check_name, passed in checks:
                    status = "✓" if passed else "✗"
                    print(f"  {status} {check_name}")

            return True
        else:
            print(f"✗ Failed: {result.get('error', 'Unknown error')}")
            return False

    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def main():
    """Test various terrain configurations"""

    print("Testing Complex Terrains with Format Fixes")
    print("=" * 50)

    # Test templates
    templates = [
        "mountain_range",
        "volcanic_terrain",
        "river_valley",
        "detailed_mountain",
        "coastal_cliffs",
    ]

    results = []
    for template in templates:
        success = test_terrain(template)
        results.append((template, success))
        time.sleep(1)  # Be nice to the server

    # Test Level1 recreation
    print("\nTesting Level1 Recreation...")
    level1_params = {
        "project_name": "Level1_recreated_fixed",
        "workflow": {
            "nodes": [
                {"type": "Mountain", "id": "1", "position": {"x": -368, "y": -112}},
                {"type": "Terrace", "id": "9", "position": {"x": -144, "y": 32}},
                {
                    "type": "FractalTerraces",
                    "id": "20",
                    "position": {"x": 80, "y": -112},
                },
                {"type": "Erosion2", "id": "25", "position": {"x": 304, "y": 32}},
                {"type": "Rivers", "id": "29", "position": {"x": 528, "y": -112}},
                {"type": "Lakes", "id": "49", "position": {"x": 752, "y": 32}},
                {"type": "Combine", "id": "71", "position": {"x": 976, "y": -112}},
                {"type": "Export", "id": "99", "position": {"x": 1200, "y": 32}},
            ],
            "connections": [
                {"from_node": "1", "from_port": "Out", "to_node": "9", "to_port": "In"},
                {
                    "from_node": "9",
                    "from_port": "Out",
                    "to_node": "20",
                    "to_port": "In",
                },
                {
                    "from_node": "20",
                    "from_port": "Out",
                    "to_node": "25",
                    "to_port": "In",
                },
                {
                    "from_node": "25",
                    "from_port": "Out",
                    "to_node": "29",
                    "to_port": "In",
                },
                {
                    "from_node": "29",
                    "from_port": "Out",
                    "to_node": "49",
                    "to_port": "In",
                },
                {
                    "from_node": "49",
                    "from_port": "Out",
                    "to_node": "71",
                    "to_port": "In",
                },
                {
                    "from_node": "29",
                    "from_port": "Rivers",
                    "to_node": "71",
                    "to_port": "Input2",
                },
                {
                    "from_node": "71",
                    "from_port": "Out",
                    "to_node": "99",
                    "to_port": "In",
                },
            ],
        },
    }

    success = test_terrain("Level1_recreation", "create_gaea2_project", level1_params)
    results.append(("Level1 Recreation", success))

    # Summary
    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)

    passed = sum(1 for _, success in results if success)
    total = len(results)

    for name, success in results:
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"{status} - {name}")

    print(f"\nTotal: {passed}/{total} passed")

    if passed == total:
        print("\n🎉 All terrain files should now open correctly in Gaea2!")

    return passed == total


if __name__ == "__main__":
    import sys

    sys.exit(0 if main() else 1)
