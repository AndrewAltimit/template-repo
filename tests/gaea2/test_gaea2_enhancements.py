#!/usr/bin/env python3
"""
Test script for Gaea2 MCP enhancements
"""

import asyncio
import json
import os
import sys

import pytest

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Import Gaea2 MCP server
from tools.mcp.gaea2.server import Gaea2MCPServer  # noqa: E402
from tools.mcp.gaea2.utils.gaea2_pattern_knowledge import (  # noqa: E402
    get_next_node_suggestions,
    get_workflow_for_terrain_type,
    suggest_properties_for_node,
)


# Create a mock MCPTools class for backward compatibility
class MCPTools:
    server = None

    @classmethod
    def _get_server(cls):
        if cls.server is None:
            # Mock the environment check for testing
            import unittest.mock

            with unittest.mock.patch.dict(os.environ, {"GAEA2_TEST_MODE": "1"}):
                cls.server = Gaea2MCPServer()
        return cls.server

    @classmethod
    async def analyze_workflow_patterns(cls, **kwargs):
        server = cls._get_server()
        # Call the method directly
        return await server.analyze_workflow_patterns(**kwargs)

    @classmethod
    async def repair_gaea2_project(cls, **kwargs):
        server = cls._get_server()
        # Call the method directly
        return await server.repair_gaea2_project(**kwargs)

    @classmethod
    async def create_gaea2_project(cls, **kwargs):
        server = cls._get_server()
        # Call the method directly (not private)
        return await server.create_gaea2_project(**kwargs)


@pytest.mark.asyncio
async def test_pattern_knowledge():
    """Test pattern knowledge functions"""
    print("=== Testing Pattern Knowledge ===\n")

    # Test next node suggestions
    print("1. Testing next node suggestions:")
    print("   After Mountain node:")
    suggestions = get_next_node_suggestions("Mountain")
    for s in suggestions:
        print(f"   - {s['node']}: {s['probability']:.0%} probability")

    print("\n   After Erosion2 node:")
    suggestions = get_next_node_suggestions("Erosion2")
    for s in suggestions:
        print(f"   - {s['node']}: {s['probability']:.0%} probability")

    # Test workflow recommendations
    print("\n2. Testing workflow recommendations:")
    for terrain_type in ["mountain", "canyon", "volcano", "terraced"]:
        workflow = get_workflow_for_terrain_type(terrain_type)
        if workflow:
            print(f"   {terrain_type}: {' → '.join(workflow['nodes'])}")

    # Test property suggestions
    print("\n3. Testing property suggestions:")
    props = suggest_properties_for_node("Erosion2", {"performance_priority": True})
    print(f"   Erosion2 (performance mode): {json.dumps(props, indent=2)}")


@pytest.mark.asyncio
async def test_workflow_analyzer():
    """Test workflow analyzer with pattern knowledge"""
    print("\n=== Testing Workflow Analyzer ===\n")

    # Test with a simple workflow
    test_nodes = [
        {"type": "Mountain", "name": "Mountain1"},
        {"type": "Erosion2", "name": "Erosion1"},
    ]

    # Create a workflow dict with nodes
    test_workflow = {"nodes": test_nodes, "connections": []}
    result = await MCPTools.analyze_workflow_patterns(workflow_or_directory=test_workflow)

    if result["success"]:
        print("Workflow analysis successful!")
        if "recommendations" in result:
            recs = result["recommendations"]
            print("\nRecommended next nodes:")
            for node in recs.get("next_nodes", [])[:3]:
                print(f"  - {node['node']} (used {node['frequency']} times)")
    else:
        print(f"Error: {result.get('error')}")


@pytest.mark.asyncio
async def test_project_repair():
    """Test project repair functionality"""
    print("\n=== Testing Project Repair ===\n")

    # Create a test project with some issues
    # test_project = {
    #     "type": "Mountain",
    #     "name": "TestMountain",
    #     "properties": {"Scale": "wrong_type", "InvalidProp": 123},  # Should be float  # Invalid property
    # }

    # Create a minimal project structure
    project_data = {
        "$id": "1",
        "Assets": {
            "$id": "2",
            "$values": [
                {
                    "$id": "3",
                    "Terrain": {
                        "$id": "4",
                        "Nodes": {
                            "100": {
                                "$id": "7",
                                "$type": "QuadSpinner.Gaea.Nodes.Mountain, Gaea.Nodes",
                                "Id": 100,
                                "Name": "TestMountain",
                                "Scale": "wrong_type",
                                "InvalidProp": 123,
                                "Ports": {"$id": "8", "$values": []},
                            }
                        },
                    },
                }
            ],
        },
    }

    # Write project to a temporary file
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".terrain", delete=False) as f:
        json.dump(project_data, f)
        temp_path = f.name

    try:
        result = await MCPTools.repair_gaea2_project(project_path=temp_path, backup=True)
    finally:
        # Clean up temp file
        os.unlink(temp_path)

    if result["success"]:
        print("Project repair successful!")
        issues = result.get("issues_found", [])
        fixes = result.get("fixes_applied", [])

        print(f"Issues found: {len(issues)}")
        print(f"Fixes applied: {len(fixes)}")

        if issues:
            print("\nIssues found:")
            for issue in issues[:3]:
                print(f"  - {issue}")

        if fixes:
            print("\nFixes applied:")
            for fix in fixes[:3]:
                print(f"  - {fix}")
    else:
        print(f"Error: {result.get('error')}")


@pytest.mark.asyncio
async def test_template_with_knowledge():
    """Test creating project from template with pattern knowledge"""
    print("\n=== Testing Template Creation with Knowledge ===\n")

    # Get a workflow template
    workflow = get_workflow_for_terrain_type("mountain")
    if workflow:
        print(f"Using workflow: {workflow['description']}")
        print(f"Nodes: {' → '.join(workflow['nodes'])}")

        # Create nodes from the workflow
        nodes = []
        x_offset = 0
        for i, node_type in enumerate(workflow["nodes"]):
            node = {
                "id": 100 + i,
                "type": node_type,
                "name": f"{node_type}_{i}",
                "position": {"x": 25000 + x_offset, "y": 25000},
            }

            # Add suggested properties
            props = suggest_properties_for_node(node_type)
            if props:
                node["properties"] = {}
                for prop_name, prop_info in props.items():
                    if isinstance(prop_info, dict) and "default" in prop_info:
                        node["properties"][prop_name] = prop_info["default"]

            nodes.append(node)
            x_offset += 1500

        # Create connections based on sequence
        connections = []
        for i in range(len(nodes) - 1):
            connections.append(
                {
                    "from_node": nodes[i]["id"],
                    "to_node": nodes[i + 1]["id"],
                    "from_port": "Out",
                    "to_port": "In",
                }
            )

        # Create the project
        result = await MCPTools.create_gaea2_project(
            project_name="Knowledge-Based Mountain",
            nodes=nodes,
            connections=connections,
            output_path="test_knowledge_mountain.terrain",
        )

        if result["success"]:
            print("\n✓ Project created successfully!")
            print(f"  Nodes: {result['node_count']}")
            print(f"  Connections: {result['connection_count']}")
            print(f"  Output: {result['output_path']}")
        else:
            print(f"Error: {result.get('error')}")


async def main():
    """Run all tests"""
    print("Testing Gaea2 MCP Enhancements\n")
    print("=" * 50)

    await test_pattern_knowledge()
    await test_workflow_analyzer()
    await test_project_repair()
    await test_template_with_knowledge()

    print("\n" + "=" * 50)
    print("✅ All tests completed!")


if __name__ == "__main__":
    asyncio.run(main())
