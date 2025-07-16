#!/usr/bin/env python3
"""Enhanced test script for Gaea2 knowledge graph showing all new features"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from tools.mcp.gaea2_knowledge_graph import knowledge_graph  # noqa: E402
from tools.mcp.mcp_server import MCPTools  # noqa: E402


async def test_enhanced_features():
    """Test the enhanced knowledge graph features"""
    print("=== Testing Enhanced Gaea2 Knowledge Graph ===\n")

    # Test 1: Show category-aware suggestions
    print("1. Category-aware node suggestions:")
    nodes = ["Mountain", "Erosion"]
    suggestions = await MCPTools.suggest_gaea2_nodes(nodes)
    print(f"  Current nodes: {nodes}")
    print("  Suggestions by category:")
    categories = {}
    for sugg in suggestions["suggestions"][:10]:
        cat = sugg["category"]
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(f"{sugg['node']} ({sugg['confidence']:.2f})")

    for cat, nodes_list in categories.items():
        print(f"    {cat}: {', '.join(nodes_list)}")
    print()

    # Test 2: Test new workflow patterns
    print("2. Testing new workflow patterns:")
    patterns = [
        "Professional Mountain",
        "Quick Erosion",
        "Tropical Island",
        "Coherent Water Flow",
        "Erosion Data Texturing",
    ]

    for pattern_name in patterns:
        # Find the pattern
        pattern = next((p for p in knowledge_graph.patterns if p.name == pattern_name), None)
        if pattern:
            print(f"  {pattern_name}:")
            print(f"    Nodes: {len(pattern.nodes)}")
            print(f"    Tags: {', '.join(pattern.tags)}")
    print()

    # Test 3: Advanced property constraints
    print("3. Testing advanced property constraints:")
    test_nodes = [
        {
            "name": "Mountain",
            "type": "Mountain",
            "properties": {"Scale": 2.0, "Height": 0.8},
        },
        {"name": "Warp", "type": "Warp", "properties": {}},
        {"name": "Stratify", "type": "Stratify", "properties": {}},
        {"name": "Lake", "type": "Lake", "properties": {}},
        {"name": "Thermal", "type": "Thermal", "properties": {}},
        {"name": "Erosion", "type": "Erosion", "properties": {"RockSoftness": 0.8}},
    ]

    optimization = await MCPTools.optimize_gaea2_properties(test_nodes)
    print(f"  Properties optimized: {optimization['summary']['properties_adjusted']}")
    for sugg in optimization["applied_suggestions"]:
        print(f"    - {sugg['node']}.{sugg['property']}: → {sugg['new_value']:.2f}")
        print(f"      ({sugg['reason']})")
    print()

    # Test 4: New node relationships
    print("4. Testing new node relationships:")
    test_pairs = [
        ("Canyon", "Stratify"),
        ("Island", "Sea"),
        ("Wizard", "Erosion"),
        ("HydroFix", "FlowMap"),
        ("Mask", "Any"),
        ("Splat", "RGBMerge"),
    ]

    for from_node, to_node in test_pairs:
        rels = knowledge_graph.get_relationships(from_node)
        matching = [r for r in rels if r.to_node == to_node or r.from_node == to_node]
        if matching:
            rel = matching[0]
            print(f"  {from_node} → {to_node}: {rel.relation_type.value} ({rel.strength:.1f})")
            print(f"    {rel.description}")
    print()

    # Test 5: Blend mode suggestions
    print("5. Combine node blend modes:")
    for mode, purpose in list(knowledge_graph.blend_mode_purposes.items())[:5]:
        print(f"  {mode}: {purpose}")
    print()

    # Test 6: Complex workflow validation
    print("6. Testing complex masked workflow:")
    complex_nodes = [
        {"name": "Mountain", "type": "Mountain"},
        {"name": "Erosion", "type": "Erosion"},
        {"name": "Sandstone", "type": "Sandstone"},
        {"name": "Thermal2", "type": "Thermal2"},
        {"name": "Mask", "type": "Mask"},
        {"name": "SatMap", "type": "SatMap"},
    ]

    analysis = await MCPTools.analyze_gaea2_workflow(complex_nodes)
    print(f"  Workflow valid: {analysis['validation']['valid']}")
    print(f"  Pattern match: {[p['name'] for p in analysis['similar_patterns']]}")
    print()

    # Test 7: Alternative node suggestions
    print("7. Alternative node suggestions:")
    alternatives = [
        ("Erosion", ["EasyErosion", "Wizard"]),
        ("Thermal", ["Thermal2"]),
        ("FlowMap", ["FlowMapClassic"]),
        ("Terraces", ["Stratify"]),
    ]

    for node, expected in alternatives:
        rels = knowledge_graph.get_relationships(node)
        alts = [r.to_node for r in rels if r.relation_type.value == "alternative_to"]
        if alts:
            print(f"  {node} alternatives: {', '.join(alts)}")
    print()

    # Test 8: Performance optimization patterns
    print("8. Performance optimization tips:")
    perf_nodes = ["Edge", "Bomber"]
    analysis = await MCPTools.analyze_gaea2_workflow([{"name": n, "type": n} for n in perf_nodes])
    if analysis["validation"]["suggestions"]:
        print(f"  Suggestions: {analysis['validation']['suggestions'][0]}")

    # Show fast preview pattern
    fast_pattern = next((p for p in knowledge_graph.patterns if p.name == "Fast Preview"), None)
    if fast_pattern:
        print(f"  Fast Preview pattern: {' → '.join(fast_pattern.nodes)}")
    print()

    print("=== Enhanced Knowledge Graph Tests Complete ===")


async def show_statistics():
    """Show knowledge graph statistics"""
    print("\n=== Knowledge Graph Statistics ===")
    print(f"Total relationships: {len(knowledge_graph.relationships)}")
    print(f"Total patterns: {len(knowledge_graph.patterns)}")
    print(f"Total constraints: {len(knowledge_graph.property_constraints)}")
    print(f"Node categories: {len(set(knowledge_graph.node_categories.values()))}")
    print(f"Blend modes documented: {len(knowledge_graph.blend_mode_purposes)}")

    # Count relationship types
    rel_types = {}
    for rel in knowledge_graph.relationships:
        rel_type = rel.relation_type.value
        rel_types[rel_type] = rel_types.get(rel_type, 0) + 1

    print("\nRelationship type distribution:")
    for rel_type, count in sorted(rel_types.items(), key=lambda x: x[1], reverse=True):
        print(f"  {rel_type}: {count}")

    # Show pattern complexity
    print("\nPattern complexity:")
    patterns_by_size = sorted(knowledge_graph.patterns, key=lambda p: len(p.nodes), reverse=True)
    for pattern in patterns_by_size[:5]:
        print(f"  {pattern.name}: {len(pattern.nodes)} nodes")


async def main():
    """Main test function"""
    try:
        await test_enhanced_features()
        await show_statistics()
    except Exception as e:
        print(f"Error during testing: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
