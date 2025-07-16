#!/usr/bin/env python3
"""Test script for Gaea2 knowledge graph enhancements"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from tools.mcp.mcp_server import MCPTools  # noqa: E402


async def test_knowledge_graph():
    """Test the knowledge graph functionality"""
    print("=== Testing Gaea2 Knowledge Graph Enhancements ===\n")

    # Test 1: Analyze a basic workflow
    print("1. Analyzing basic mountain workflow:")
    basic_nodes = [
        {
            "name": "Mountain",
            "type": "Mountain",
            "properties": {"Scale": 1.0, "Height": 0.7},
        },
        {"name": "Erosion", "type": "Erosion", "properties": {"Duration": 0.04}},
    ]
    basic_connections = [
        {
            "from_node": "Mountain",
            "to_node": "Erosion",
            "from_port": "Out",
            "to_port": "In",
        }
    ]

    analysis = await MCPTools.analyze_gaea2_workflow(basic_nodes, basic_connections)
    print(f"  Valid workflow: {analysis['validation']['valid']}")
    print(f"  Issues: {analysis['validation']['issues']}")
    print(f"  Warnings: {analysis['validation']['warnings']}")
    print(f"  Suggestions: {analysis['validation']['suggestions']}")
    print(f"  Similar patterns: {[p['name'] for p in analysis['similar_patterns']]}")
    print()

    # Test 2: Get node suggestions
    print("2. Getting node suggestions for current workflow:")
    current_nodes = ["Mountain", "Erosion"]
    suggestions = await MCPTools.suggest_gaea2_nodes(current_nodes)
    print(f"  Current nodes: {suggestions['current_nodes']}")
    print("  Suggested next nodes:")
    for sugg in suggestions["suggestions"][:5]:
        print(f"    - {sugg['node']} (confidence: {sugg['confidence']:.2f})")
    print()

    # Test 3: Optimize properties
    print("3. Optimizing node properties:")
    nodes_to_optimize = [
        {
            "name": "Mountain",
            "type": "Mountain",
            "properties": {"Scale": 1.0, "Height": 0.7},
        },
        {"name": "Erosion", "type": "Erosion", "properties": {"Duration": 0.04}},
        {"name": "Snow", "type": "Snow", "properties": {"Coverage": 0.5}},
    ]

    optimization = await MCPTools.optimize_gaea2_properties(nodes_to_optimize)
    print(f"  Properties adjusted: {optimization['summary']['properties_adjusted']}")
    for sugg in optimization["applied_suggestions"]:
        print(f"    - {sugg['node']}.{sugg['property']}: {sugg['old_value']} → {sugg['new_value']}")
        print(f"      Reason: {sugg['reason']}")
    print()

    # Test 4: Validate conflicting nodes
    print("4. Testing conflict detection:")
    conflicting_nodes = [
        {"name": "Erosion", "type": "Erosion"},
        {"name": "Erosion2", "type": "Erosion2"},
    ]
    conflict_analysis = await MCPTools.analyze_gaea2_workflow(conflicting_nodes, [])
    print(f"  Issues found: {conflict_analysis['validation']['issues']}")
    print()

    # Test 5: Find patterns for desert terrain
    print("5. Finding patterns for desert terrain:")
    desert_nodes = ["DuneSea", "Sand"]
    desert_suggestions = await MCPTools.suggest_gaea2_nodes(desert_nodes)
    print("  Matching patterns:")
    for pattern in desert_suggestions["matching_patterns"][:3]:
        print(f"    - {pattern['pattern']} (match: {pattern['match_strength']:.2f})")
        print(f"      Missing nodes: {pattern['missing_nodes']}")
    print()

    # Test 6: Portal workflow validation
    print("6. Testing portal workflow:")
    portal_nodes = [
        {"name": "Mountain", "type": "Mountain"},
        {
            "name": "Transmit1",
            "type": "PortalTransmit",
            "properties": {"PortalName": "Portal_1"},
        },
        {
            "name": "Receive1",
            "type": "PortalReceive",
            "properties": {"PortalName": "Portal_1"},
        },
        {"name": "Erosion", "type": "Erosion"},
    ]
    portal_connections = [
        {"from_node": "Mountain", "to_node": "Transmit1"},
        {"from_node": "Receive1", "to_node": "Erosion"},
    ]
    portal_analysis = await MCPTools.analyze_gaea2_workflow(portal_nodes, portal_connections)
    print(f"  Portal workflow valid: {portal_analysis['validation']['valid']}")
    print()

    # Test 7: List enhanced templates
    print("7. Listing templates with knowledge graph patterns:")
    templates = await MCPTools.list_gaea2_templates()
    print(f"  Built-in templates: {len(templates['templates'])}")
    if "knowledge_graph_patterns" in templates:
        print(f"  Knowledge graph patterns: {len(templates.get('knowledge_graph_patterns', {}))}")
    print()

    # Test 8: Complex workflow analysis
    print("8. Analyzing complex workflow:")
    complex_nodes = [
        {"name": "Mountain", "type": "Mountain", "properties": {"Scale": 1.5}},
        {
            "name": "Erosion",
            "type": "Erosion",
            "properties": {"Duration": 0.05, "FeatureScale": 2500},
        },
        {"name": "Thermal", "type": "Thermal", "properties": {"Strength": 0.5}},
        {"name": "Rivers", "type": "Rivers", "properties": {"Water": 0.3}},
        {"name": "Lake", "type": "Lake", "properties": {}},
        {"name": "Snow", "type": "Snow", "properties": {"Altitude": 0.7}},
        {"name": "SatMap", "type": "SatMap", "properties": {"Library": "Mountain"}},
    ]
    complex_analysis = await MCPTools.analyze_gaea2_workflow(complex_nodes)
    print("  Workflow summary:")
    print(f"    - Valid: {complex_analysis['summary']['workflow_valid']}")
    print(f"    - Total suggestions: {complex_analysis['summary']['total_suggestions']}")
    print(f"    - Similar to: {[p['name'] for p in complex_analysis['similar_patterns']]}")

    # Show property suggestions
    if complex_analysis["analysis"]["property_suggestions"]:
        print("  Property optimization suggestions:")
        for sugg in complex_analysis["analysis"]["property_suggestions"]:
            print(f"    - {sugg['node']}.{sugg['property']} → {sugg['suggested_value']}")

    print("\n=== Knowledge Graph Tests Complete ===")


async def main():
    """Main test function"""
    try:
        await test_knowledge_graph()
    except Exception as e:
        print(f"Error during testing: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
