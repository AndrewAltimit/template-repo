#!/usr/bin/env python3
"""
Analyze real Gaea2 projects to learn patterns and best practices
"""

import asyncio
import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from tools.mcp.gaea2_project_repair import Gaea2ProjectRepair  # noqa: E402
from tools.mcp.gaea2_workflow_analyzer import Gaea2WorkflowAnalyzer  # noqa: E402


async def analyze_real_projects():
    """Analyze all real Gaea2 projects"""
    print("=== Gaea2 Project Analysis ===\n")

    # Initialize analyzer
    analyzer = Gaea2WorkflowAnalyzer()

    # Analyze official projects
    official_dir = "/home/miku/Documents/references/Real Projects/Official Gaea Projects"
    print(f"Analyzing official projects in: {official_dir}")

    official_results = analyzer.analyze_directory(official_dir)
    print(f"✓ Analyzed {official_results['projects_analyzed']} official projects")

    # Analyze user projects
    user_dir = "/home/miku/Documents/references/Real Projects/mikus files"
    print(f"\nAnalyzing user projects in: {user_dir}")

    user_results = analyzer.analyze_directory(user_dir)
    print(f"✓ Analyzed {user_results['projects_analyzed'] - official_results['projects_analyzed']} user projects")

    # Get overall statistics
    stats = analyzer.get_statistics()

    print("\n=== Analysis Results ===")
    print(f"\nTotal projects analyzed: {stats['projects_analyzed']}")
    print(f"Unique node types found: {stats['unique_node_types']}")
    print(f"Total patterns discovered: {stats['total_patterns']}")

    print("\n=== Most Common Nodes ===")
    for node, count in stats["most_common_nodes"].items():
        print(f"  {node}: {count} occurrences")

    print("\n=== Most Common Patterns ===")
    for i, pattern in enumerate(stats["most_common_patterns"][:5], 1):
        print(f"\n{i}. Pattern: {pattern['name']}")
        print(f"   Frequency: {pattern['frequency']}")
        print(f"   Nodes: {' → '.join(pattern['nodes'])}")

    # Save analysis
    analyzer.save_analysis("gaea2_workflow_analysis.json")
    print("\n✓ Analysis saved to gaea2_workflow_analysis.json")

    # Test recommendations
    print("\n=== Testing Recommendations ===")
    test_workflow = ["Mountain", "Erosion"]
    recommendations = analyzer.get_recommendations(test_workflow)

    print(f"\nFor workflow: {' → '.join(test_workflow)}")
    print("\nRecommended next nodes:")
    for rec in recommendations["next_nodes"][:3]:
        print(f"  - {rec['node']} (used {rec['frequency']} times)")

    print("\nSimilar patterns found:")
    for pattern in recommendations["similar_patterns"][:3]:
        print(f"  - {pattern['name']} (similarity: {pattern['similarity']:.2f})")

    # Test repair functionality
    print("\n=== Testing Project Repair ===")

    # Find a project to test
    test_project = None
    for file_path in Path(official_dir).glob("*.terrain"):
        test_project = str(file_path)
        break

    if test_project:
        print(f"\nAnalyzing project: {Path(test_project).name}")

        repair = Gaea2ProjectRepair()
        with open(test_project, "r") as f:
            project_data = json.load(f)

        analysis = repair.analyze_project(project_data)

        if analysis["success"]:
            health_score = analysis["analysis"]["health_score"]
            errors = analysis["analysis"]["errors"]

            print(f"  Health Score: {health_score:.1f}/100")
            print(f"  Critical Errors: {errors['critical']}")
            print(f"  Errors: {errors['errors']}")
            print(f"  Warnings: {errors['warnings']}")
            print(f"  Auto-fixable: {errors['auto_fixable']}")

            if errors["total_errors"] > 0:
                print("\n  Sample errors:")
                for error in analysis["errors"][:3]:
                    print(f"    - [{error['severity']}] {error['message']}")
                    if error["suggestion"]:
                        print(f"      Suggestion: {error['suggestion']}")


async def generate_knowledge_base():
    """Generate AI-friendly knowledge base from analysis"""
    print("\n=== Generating Knowledge Base ===")

    # Load analysis
    with open("gaea2_workflow_analysis.json", "r") as f:
        analysis = json.load(f)

    knowledge_base = {
        "common_workflows": [],
        "node_best_practices": {},
        "property_recommendations": {},
        "performance_tips": [],
    }

    # Extract common workflows
    for pattern in analysis["patterns"][:10]:
        workflow = {
            "name": pattern["name"],
            "description": f"Common workflow used {pattern['frequency']} times",
            "nodes": pattern["nodes"],
            "properties": pattern.get("properties", {}),
        }
        knowledge_base["common_workflows"].append(workflow)

    # Extract node best practices
    for node, sequences in analysis["node_sequences"].items():
        if sequences:
            knowledge_base["node_best_practices"][node] = {
                "commonly_followed_by": [s[0] for s in sequences[:3]],
                "usage_tips": [],
            }

    # Add performance tips based on patterns
    knowledge_base["performance_tips"] = [
        "Limit erosion chains to 3 nodes or less for better performance",
        "Use lower Duration values (0.04-0.1) for Erosion nodes in production",
        "Combine multiple Erosion effects rather than chaining them",
        "Place heavy computation nodes (Erosion2, Rivers) early in the workflow",
        "Use SatMap or CLUTer at the end for colorization",
    ]

    # Save knowledge base
    with open("gaea2_knowledge_base.json", "w") as f:
        json.dump(knowledge_base, f, indent=2)

    print("✓ Knowledge base saved to gaea2_knowledge_base.json")

    # Generate markdown documentation
    with open("GAEA2_PATTERNS.md", "w") as f:
        f.write("# Gaea2 Common Patterns and Best Practices\n\n")
        f.write("Generated from analysis of real Gaea2 projects.\n\n")

        f.write("## Common Workflows\n\n")
        for i, workflow in enumerate(knowledge_base["common_workflows"][:5], 1):
            f.write(f"### {i}. {workflow['name']}\n")
            f.write(f"- **Usage**: {workflow['description']}\n")
            f.write(f"- **Nodes**: {' → '.join(workflow['nodes'])}\n\n")

        f.write("## Node Best Practices\n\n")
        for node, practices in list(knowledge_base["node_best_practices"].items())[:10]:
            f.write(f"### {node}\n")
            f.write(f"- **Commonly followed by**: {', '.join(practices['commonly_followed_by'])}\n\n")

        f.write("## Performance Tips\n\n")
        for tip in knowledge_base["performance_tips"]:
            f.write(f"- {tip}\n")

    print("✓ Documentation saved to GAEA2_PATTERNS.md")


async def main():
    """Main function"""
    await analyze_real_projects()
    await generate_knowledge_base()
    print("\n✅ Analysis complete!")


if __name__ == "__main__":
    asyncio.run(main())
