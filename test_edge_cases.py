#!/usr/bin/env python3
"""Test edge cases for Gaea2 property handling"""

import json

import requests

# Test the remote Gaea2 MCP server
MCP_SERVER = "http://192.168.0.152:8007"


def test_edge_cases():
    """Test various edge cases in property handling"""

    test_cases = [
        {
            "name": "Mixed Case Properties",
            "project_name": "test_mixed_case",
            "nodes": [
                {
                    "id": "erosion_1",
                    "type": "Erosion",
                    "name": "Test Erosion",
                    "properties": {
                        "rockSoftness": 0.5,  # camelCase
                        "BaseLevel": 0.2,  # PascalCase
                        "erosion scale": 1000,  # with space (should be fixed)
                    },
                    "position": {"x": 0, "y": 0},
                }
            ],
        },
        {
            "name": "Range Properties",
            "project_name": "test_range",
            "nodes": [
                {
                    "id": "satmap_1",
                    "type": "SatMap",
                    "name": "Test SatMap",
                    "properties": {"Library": "Rock", "Range": {"X": 0.2, "Y": 0.8}},  # Range object
                    "position": {"x": 0, "y": 0},
                }
            ],
        },
        {
            "name": "All Rivers Enum Values",
            "project_name": "test_rivers_enums",
            "nodes": [
                {"id": "mountain", "type": "Mountain", "name": "Base", "properties": {"Seed": 1}, "position": {"x": 0, "y": 0}}
            ]
            + [
                {
                    "id": f"rivers_{val}",
                    "type": "Rivers",
                    "name": f"Rivers {val}",
                    "properties": {"Water": 0.3, "RiverValleyWidth": val, "Headwaters": 100},
                    "position": {"x": 200 + i * 200, "y": 0},
                }
                for i, val in enumerate(["minus4", "minus2", "zero", "plus2", "plus4"])
            ],
        },
    ]

    results = []

    for test_case in test_cases:
        print(f"\n{'='*50}")
        print(f"Testing: {test_case['name']}")
        print(f"{'='*50}")

        # Add connections for Rivers test
        connections = []
        if "rivers" in test_case["project_name"]:
            for node in test_case["nodes"]:
                if node["id"].startswith("rivers_"):
                    connections.append({"from_node": "mountain", "from_port": "Out", "to_node": node["id"], "to_port": "In"})

        workflow = {"nodes": test_case["nodes"], "connections": connections}

        response = requests.post(
            f"{MCP_SERVER}/mcp/execute",
            json={
                "tool": "create_gaea2_project",
                "parameters": {
                    "project_name": test_case["project_name"],
                    "workflow": workflow,
                    "auto_validate": True,
                    "save_to_disk": False,
                },
            },
        )

        if response.status_code != 200:
            print(f"❌ Error: {response.status_code}")
            results.append({"test": test_case["name"], "success": False, "error": response.text})
            continue

        result = response.json()

        if not result.get("success"):
            print(f"❌ Failed: {result.get('error')}")
            results.append({"test": test_case["name"], "success": False, "error": result.get("error")})
            continue

        print("✓ Project created successfully!")

        # Analyze the result
        project = result.get("project_structure")
        if project:
            nodes = project["Assets"]["$values"][0]["Terrain"]["Nodes"]

            # Check specific properties based on test
            if "mixed_case" in test_case["project_name"]:
                # Find erosion node
                for node_id, node in nodes.items():
                    if isinstance(node, str):
                        continue
                    if "Erosion" in node.get("$type", ""):
                        print("\nProperty fixes:")
                        print(f"  - Rock Softness: {node.get('Rock Softness', 'MISSING')}")
                        print(f"  - Base Level: {node.get('Base Level', 'MISSING')}")
                        print(f"  - Erosion Scale: {node.get('Erosion Scale', 'MISSING')}")

            elif "range" in test_case["project_name"]:
                # Find SatMap node
                for node_id, node in nodes.items():
                    if isinstance(node, str):
                        continue
                    if "SatMap" in node.get("$type", ""):
                        range_prop = node.get("Range")
                        print(f"\nRange property: {json.dumps(range_prop, indent=2)}")
                        if isinstance(range_prop, dict) and "$id" in range_prop:
                            print("✓ Range has proper $id")
                        else:
                            print("❌ Range missing $id")

            elif "rivers_enums" in test_case["project_name"]:
                # Check all Rivers nodes
                print("\nRivers enum values:")
                for node_id, node in nodes.items():
                    if isinstance(node, str):
                        continue
                    if "Rivers" in node.get("$type", ""):
                        valley_width = node.get("RiverValleyWidth")
                        print(f"  - {node.get('Name')}: {valley_width}")

        results.append({"test": test_case["name"], "success": True})

    # Summary
    print(f"\n{'='*50}")
    print("TEST SUMMARY")
    print(f"{'='*50}")
    passed = sum(1 for r in results if r["success"])
    print(f"Passed: {passed}/{len(results)}")
    for result in results:
        status = "✓" if result["success"] else "❌"
        print(f"{status} {result['test']}")


def main():
    print("Testing Edge Cases for Gaea2 Property Handling")
    test_edge_cases()


if __name__ == "__main__":
    main()
