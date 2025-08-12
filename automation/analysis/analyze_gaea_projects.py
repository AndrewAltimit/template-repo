#!/usr/bin/env python3
"""
Analyze real Gaea2 projects to learn patterns and best practices

Usage:
    python analyze_gaea_projects.py --official-dir /path/to/official --user-dir /path/to/user

    Or use environment variables:
    export GAEA_OFFICIAL_PROJECTS_DIR="/path/to/official/projects"
    export GAEA_USER_PROJECTS_DIR="/path/to/user/projects"
    python analyze_gaea_projects.py
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

# Import from the project - assumes script is run from project root or with proper PYTHONPATH
try:
    from tools.mcp.gaea2.repair.gaea2_project_repair import Gaea2ProjectRepair
    from tools.mcp.gaea2.utils.gaea2_workflow_analyzer import Gaea2WorkflowAnalyzer
except ImportError:
    print("Error: Unable to import Gaea2 modules. Please run from project root:")
    print("  python automation/analysis/analyze_gaea_projects.py")
    print("Or set PYTHONPATH:")
    print("  PYTHONPATH=/path/to/project python analyze_gaea_projects.py")
    sys.exit(1)


async def analyze_real_projects(official_dir=None, user_dir=None, output_file="gaea2_workflow_analysis.json"):
    """Analyze all real Gaea2 projects

    Args:
        official_dir: Path to official Gaea projects directory
        user_dir: Path to user projects directory
        output_file: Path to save analysis results
    """
    print("=== Gaea2 Project Analysis ===\n")

    # Initialize analyzer
    analyzer = Gaea2WorkflowAnalyzer()

    # Use provided directories or get from environment
    if not official_dir:
        official_dir = os.environ.get("GAEA_OFFICIAL_PROJECTS_DIR")
    if not user_dir:
        user_dir = os.environ.get("GAEA_USER_PROJECTS_DIR")

    # Check if at least one directory is provided
    if not official_dir and not user_dir:
        print("Error: No project directories specified.")
        print("\nPlease provide at least one directory using:")
        print("  --official-dir /path/to/official/projects")
        print("  --user-dir /path/to/user/projects")
        print("\nOr set environment variables:")
        print("  GAEA_OFFICIAL_PROJECTS_DIR")
        print("  GAEA_USER_PROJECTS_DIR")
        return False

    # Check if directories exist
    if not os.path.exists(official_dir):
        print(f"Warning: Official projects directory not found: {official_dir}")
        print("Set GAEA_OFFICIAL_PROJECTS_DIR environment variable to specify the correct path")
        official_results = {"projects_analyzed": 0}
    else:
        print(f"Analyzing official projects in: {official_dir}")
        official_results = analyzer.analyze_directory(official_dir)
        print(f"✓ Analyzed {official_results['projects_analyzed']} official projects")

    # Analyze user projects
    if not os.path.exists(user_dir):
        print(f"\nWarning: User projects directory not found: {user_dir}")
        print("Set GAEA_USER_PROJECTS_DIR environment variable to specify the correct path")
        user_results = {"projects_analyzed": official_results["projects_analyzed"]}
    else:
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
    analyzer.save_analysis(output_file)
    print(f"\n✓ Analysis saved to {output_file}")
    return True

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
    if os.path.exists(official_dir):
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


async def generate_knowledge_base(analysis_file="gaea2_workflow_analysis.json"):
    """Generate AI-friendly knowledge base from analysis"""
    print("\n=== Generating Knowledge Base ===")

    # Check if analysis file exists
    if not os.path.exists(analysis_file):
        print(f"Analysis file not found: {analysis_file}")
        print("Skipping knowledge base generation.")
        return

    # Load analysis
    with open(analysis_file, "r") as f:
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


async def main(official_dir=None, user_dir=None, output_file="gaea2_workflow_analysis.json"):
    """Main function"""
    success = await analyze_real_projects(official_dir, user_dir, output_file)
    if success:
        await generate_knowledge_base(output_file)
        print("\n✅ Analysis complete!")
    else:
        print("\n❌ Analysis skipped due to missing directories.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Analyze real Gaea2 projects to learn patterns and best practices",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  %(prog)s --official-dir /path/to/official --user-dir /path/to/user
  %(prog)s --official-dir ./gaea-projects/official

Environment variables:
  GAEA_OFFICIAL_PROJECTS_DIR: Default path to official projects
  GAEA_USER_PROJECTS_DIR: Default path to user projects""",
    )
    parser.add_argument("--official-dir", type=str, help="Path to official Gaea projects directory")
    parser.add_argument("--user-dir", type=str, help="Path to user projects directory")
    parser.add_argument(
        "--output",
        type=str,
        default="gaea2_workflow_analysis.json",
        help="Output file for analysis results (default: gaea2_workflow_analysis.json)",
    )

    args = parser.parse_args()

    asyncio.run(main(args.official_dir, args.user_dir, args.output))
