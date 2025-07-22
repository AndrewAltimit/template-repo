#!/usr/bin/env python3
"""Validate Gaea2 fixes by generating terrain maps via remote MCP server"""

from datetime import datetime

import requests

# Remote Gaea2 MCP server
GAEA2_SERVER = "http://192.168.0.152:8007"


def test_template(template_name):
    """Test creating a project from a template"""
    print(f"\n{'='*60}")
    print(f"Testing template: {template_name}")
    print("=" * 60)

    project_name = f"test_{template_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    payload = {
        "tool": "create_gaea2_from_template",
        "parameters": {"template_name": template_name, "project_name": project_name},
    }

    try:
        response = requests.post(f"{GAEA2_SERVER}/mcp/execute", json=payload, timeout=30)
        result = response.json()

        if result.get("success"):
            print(f"✅ SUCCESS: Generated {template_name}")
            print(f"   Project: {project_name}")
            print(f"   Path: {result.get('saved_path', 'N/A')}")
            print(f"   Nodes: {result.get('node_count', 'N/A')}")
            print(f"   Connections: {result.get('connection_count', 'N/A')}")

            # Check for validation results
            if "validation_result" in result:
                val = result["validation_result"]
                if val and "results" in val:
                    fixes = val["results"].get("fixes_applied", [])
                    if fixes:
                        print(f"   Fixes applied: {len(fixes)}")
                        for fix in fixes[:3]:  # Show first 3 fixes
                            print(f"     - {fix}")

            # Check the generated structure
            if "project_structure" in result:
                structure = result["project_structure"]
                if "Assets" in structure:
                    nodes = structure["Assets"]["$values"][0]["Terrain"]["Nodes"]

                    # Check node IDs
                    node_ids = []
                    for node_id, node in nodes.items():
                        if node_id != "$id" and isinstance(node, dict):
                            node_ids.append(node.get("Id"))

                    if node_ids:
                        sorted_ids = sorted(node_ids)[:5]
                        non_sequential = sorted_ids[1] - sorted_ids[0] > 1
                        print(f"   Node IDs: {sorted_ids}... " f"(non-sequential: {non_sequential})")

                    # Check for Export nodes
                    has_export = any("Export" in node.get("$type", "") for node in nodes.values() if isinstance(node, dict))
                    print(f"   Has Export node: {'Yes' if has_export else 'No'}")

                    # Check for problematic nodes with limited properties
                    problematic_nodes = ["Snow", "Beach", "Coast", "Lakes", "Glacier"]
                    for node in nodes.values():
                        if isinstance(node, dict):
                            node_type = node.get("$type", "").split(".")[-1].replace(", Gaea.Nodes", "")
                            if node_type in problematic_nodes:
                                props = [
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
                                print(f"   {node_type} node properties: " f"{len(props)} - {props[:3]}")

                    # Check Volcano for X/Y
                    for node in nodes.values():
                        if isinstance(node, dict) and "Volcano" in node.get("$type", ""):
                            has_xy = "X" in node and "Y" in node
                            if has_xy:
                                print(f"   Volcano has X/Y: ✓ " f"(X={node['X']}, Y={node['Y']})")
                            else:
                                print("   Volcano has X/Y: ✗")
                            break

            return True

        else:
            print(f"❌ FAILED: {template_name}")
            print(f"   Error: {result.get('error', 'Unknown error')}")
            return False

    except Exception as e:
        print(f"❌ ERROR testing {template_name}: {e}")
        return False


def test_custom_workflow():
    """Test creating a custom workflow with specific nodes"""
    print("\n" + "=" * 60)
    print("Testing custom workflow with problematic nodes")
    print("=" * 60)

    # Create a workflow with nodes that previously had issues
    nodes = [
        {
            "id": 123,
            "type": "Mountain",
            "name": "BaseTerrain",
            "position": {"x": 0, "y": 0},
            "properties": {},  # No properties - should work fine
        },
        {
            "id": 456,
            "type": "Snow",
            "name": "SnowCover",
            "position": {"x": 500, "y": 0},
            "properties": {
                "Duration": 0.5,
                "SnowLine": 0.7,
                # Only 2 properties - should work
            },
        },
        {
            "id": 789,
            "type": "Erosion2",
            "name": "DetailedErosion",
            "position": {"x": 1000, "y": 0},
            "properties": {"Duration": 0.15, "Downcutting": 0.4},
        },
        {
            "id": 321,
            "type": "SatMap",
            "name": "FinalColors",
            "position": {"x": 1500, "y": 0},
            "properties": {"Library": "Rock"},
        },
    ]

    connections = [
        {"from_node": 123, "to_node": 456, "from_port": "Out", "to_port": "In"},
        {"from_node": 456, "to_node": 789, "from_port": "Out", "to_port": "In"},
        {"from_node": 789, "to_node": 321, "from_port": "Out", "to_port": "In"},
    ]

    project_name = f"test_custom_workflow_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    payload = {
        "tool": "create_gaea2_project",
        "parameters": {
            "project_name": project_name,
            "nodes": nodes,
            "connections": connections,
            "property_mode": "none",  # Use none mode to avoid adding defaults
        },
    }

    try:
        response = requests.post(f"{GAEA2_SERVER}/mcp/execute", json=payload, timeout=30)
        result = response.json()

        if result.get("success"):
            print("✅ SUCCESS: Generated custom workflow")
            print(f"   Project: {project_name}")
            print(f"   Nodes: {result.get('node_count', 'N/A')}")
            print(f"   Connections: {result.get('connection_count', 'N/A')}")

            # Verify our node IDs were preserved
            if "project_structure" in result:
                nodes = result["project_structure"]["Assets"]["$values"][0]["Terrain"]["Nodes"]
                node_ids = [node.get("Id") for node in nodes.values() if isinstance(node, dict)]
                print(f"   Node IDs used: {sorted(node_ids)}")

            return True
        else:
            print("❌ FAILED: Custom workflow")
            print(f"   Error: {result.get('error', 'Unknown error')}")
            return False

    except Exception as e:
        print(f"❌ ERROR testing custom workflow: {e}")
        return False


def main():
    """Run all validation tests"""
    print("Validating Gaea2 fixes on remote MCP server...")
    print(f"Server: {GAEA2_SERVER}")

    # Test all available templates
    templates = [
        "basic_terrain",
        "volcanic_terrain",
        "mountain_range",
        "desert_canyon",
        "coastal_cliffs",
        "arctic_terrain",
        "river_valley",
    ]

    success_count = 0

    # Test templates
    for template in templates:
        if test_template(template):
            success_count += 1

    # Test custom workflow
    if test_custom_workflow():
        success_count += 1

    total_tests = len(templates) + 1

    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)
    print(f"✅ Successful: {success_count}/{total_tests}")
    print(f"❌ Failed: {total_tests - success_count}/{total_tests}")

    if success_count == total_tests:
        print("\n🎉 ALL TESTS PASSED! Gaea2 fixes are working correctly.")
    else:
        print("\n⚠️  Some tests failed. Check the output above for details.")


if __name__ == "__main__":
    main()
