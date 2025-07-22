#!/usr/bin/env python3
"""Validate specific Gaea2 fixes in detail"""

from datetime import datetime

import requests

GAEA2_SERVER = "http://192.168.0.152:8007"


def test_problematic_nodes():
    """Test nodes that previously failed with too many properties"""
    print("\n=== Testing Problematic Nodes with Property Limits ===")

    problematic_nodes = [
        (
            "Snow",
            {"Duration": 0.5, "SnowLine": 0.7, "Melt": 0.3},
        ),  # Exactly 3 properties
        ("Beach", {"Width": 0.8, "Slope": 0.5}),  # 2 properties
        ("Coast", {"Erosion": 0.6, "Detail": 0.7}),  # 2 properties
        ("Lakes", {"Count": 5, "Size": 0.4}),  # 2 properties
        ("Glacier", {"Scale": 1.0, "Depth": 0.6, "Flow": 0.4}),  # 3 properties
    ]

    all_success = True

    for node_type, properties in problematic_nodes:
        print(f"\nTesting {node_type} node with {len(properties)} properties...")

        nodes = [
            {
                "id": 100,
                "type": "Mountain",
                "name": "Base",
                "position": {"x": 0, "y": 0},
                "properties": {},
            },
            {
                "id": 200,
                "type": node_type,
                "name": f"Test{node_type}",
                "position": {"x": 500, "y": 0},
                "properties": properties,
            },
        ]

        connections = [{"from_node": 100, "to_node": 200, "from_port": "Out", "to_port": "In"}]

        project_name = f"test_{node_type.lower()}_{datetime.now().strftime('%H%M%S')}"

        payload = {
            "tool": "create_gaea2_project",
            "parameters": {
                "project_name": project_name,
                "nodes": nodes,
                "connections": connections,
                "property_mode": "smart",  # Should limit properties appropriately
            },
        }

        try:
            response = requests.post(f"{GAEA2_SERVER}/mcp/execute", json=payload, timeout=30)
            result = response.json()

            if result.get("success"):
                print(f"  ✅ {node_type} node created successfully")

                # Check actual properties in generated file
                if "project_structure" in result:
                    nodes_dict = result["project_structure"]["Assets"]["$values"][0]["Terrain"]["Nodes"]
                    for node in nodes_dict.values():
                        if isinstance(node, dict) and node_type in node.get("$type", ""):
                            actual_props = [
                                k
                                for k in node.keys()
                                if k
                                not in [
                                    "$id",
                                    "$type",
                                    "Id",
                                    "Name",
                                    "Position",
                                    "Ports",
                                    "Modifiers",
                                    "NodeSize",
                                    "PortCount",
                                    "IsMaskable",
                                ]
                            ]
                            print(f"  Properties in file: {len(actual_props)} - {actual_props}")
                            if len(actual_props) > 3:
                                print(f"  ⚠️  WARNING: {node_type} has too many properties!")
                                all_success = False
            else:
                print(f"  ❌ {node_type} node failed: {result.get('error')}")
                all_success = False

        except Exception as e:
            print(f"  ❌ Error testing {node_type}: {e}")
            all_success = False

    return all_success


def test_node_id_generation():
    """Test that node IDs are non-sequential"""
    print("\n=== Testing Non-Sequential Node ID Generation ===")

    # Create multiple projects and check ID patterns
    id_patterns = []

    for i in range(3):
        project_name = f"test_ids_{i}_{datetime.now().strftime('%H%M%S')}"

        payload = {
            "tool": "create_gaea2_from_template",
            "parameters": {
                "template_name": "basic_terrain",
                "project_name": project_name,
            },
        }

        try:
            response = requests.post(f"{GAEA2_SERVER}/mcp/execute", json=payload, timeout=30)
            result = response.json()

            if result.get("success") and "project_structure" in result:
                nodes = result["project_structure"]["Assets"]["$values"][0]["Terrain"]["Nodes"]
                ids = sorted([node.get("Id") for node in nodes.values() if isinstance(node, dict)])
                id_patterns.append(ids)
                print(f"  Project {i+1} IDs: {ids}")

                # Check if non-sequential
                gaps = [ids[j + 1] - ids[j] for j in range(len(ids) - 1)]
                avg_gap = sum(gaps) / len(gaps) if gaps else 0
                print(f"  Average gap: {avg_gap:.1f} (sequential would be 1.0)")

        except Exception as e:
            print(f"  ❌ Error in project {i+1}: {e}")

    # Verify all projects have non-sequential IDs
    all_non_sequential = all(any(ids[j + 1] - ids[j] > 1 for j in range(len(ids) - 1)) for ids in id_patterns)

    if all_non_sequential:
        print("  ✅ All projects use non-sequential IDs")
    else:
        print("  ❌ Some projects have sequential IDs")

    return all_non_sequential


def test_port_types():
    """Test that port types don't include ', Required'"""
    print("\n=== Testing Port Type Strings ===")

    # Create a project with Export and SatMap nodes that previously had issues
    nodes = [
        {
            "id": 100,
            "type": "Mountain",
            "name": "Base",
            "position": {"x": 0, "y": 0},
            "properties": {},
        },
        {
            "id": 200,
            "type": "SatMap",
            "name": "Colors",
            "position": {"x": 500, "y": 0},
            "properties": {"Library": "Rock"},
        },
    ]

    connections = [{"from_node": 100, "to_node": 200, "from_port": "Out", "to_port": "In"}]

    project_name = f"test_ports_{datetime.now().strftime('%H%M%S')}"

    payload = {
        "tool": "create_gaea2_project",
        "parameters": {
            "project_name": project_name,
            "nodes": nodes,
            "connections": connections,
        },
    }

    try:
        response = requests.post(f"{GAEA2_SERVER}/mcp/execute", json=payload, timeout=30)
        result = response.json()

        if result.get("success") and "project_structure" in result:
            nodes_dict = result["project_structure"]["Assets"]["$values"][0]["Terrain"]["Nodes"]

            # Check port types
            has_required = False
            for node in nodes_dict.values():
                if isinstance(node, dict) and "Ports" in node:
                    ports = node["Ports"].get("$values", [])
                    for port in ports:
                        port_type = port.get("Type", "")
                        if ", Required" in port_type:
                            print(f"  ❌ Found port with ', Required': {port_type} in {node.get('Name')}")
                            has_required = True
                        elif port_type in ["PrimaryIn", "PrimaryOut", "In", "Out"]:
                            print(f"  ✓ Correct port type: {port_type} in {node.get('Name')}")

            return not has_required
        else:
            print(f"  ❌ Failed to create project: {result.get('error')}")
            return False

    except Exception as e:
        print(f"  ❌ Error testing ports: {e}")
        return False


def main():
    """Run specific validation tests"""
    print("Validating specific Gaea2 fixes...")
    print(f"Server: {GAEA2_SERVER}")

    results = {
        "Problematic nodes": test_problematic_nodes(),
        "Non-sequential IDs": test_node_id_generation(),
        "Port types": test_port_types(),
    }

    print("\n" + "=" * 60)
    print("DETAILED VALIDATION RESULTS")
    print("=" * 60)

    for test_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{test_name}: {status}")

    all_passed = all(results.values())

    if all_passed:
        print("\n🎉 ALL SPECIFIC FIXES VALIDATED SUCCESSFULLY!")
        print("The Gaea2 terrain files should now open correctly in the application.")
    else:
        print("\n⚠️  Some specific tests failed. Check the detailed output above.")


if __name__ == "__main__":
    main()
