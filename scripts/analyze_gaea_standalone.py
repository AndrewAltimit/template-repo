#!/usr/bin/env python3
"""
Standalone Gaea2 project analyzer

Usage:
    python analyze_gaea_standalone.py

Environment variables:
    GAEA_OFFICIAL_PROJECTS_DIR: Path to official Gaea projects directory
    GAEA_USER_PROJECTS_DIR: Path to user projects directory

Example:
    export GAEA_OFFICIAL_PROJECTS_DIR="/path/to/official/projects"
    export GAEA_USER_PROJECTS_DIR="/path/to/user/projects"
    python analyze_gaea_standalone.py
"""

import json
import logging
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path
# No imports needed from typing

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from tools.mcp.gaea2.utils.workflow_extractor import WorkflowExtractor  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Use the common workflow extractor
extract_workflow = WorkflowExtractor.extract_workflow


def analyze_projects():
    """Analyze all real Gaea2 projects"""
    print("=== Gaea2 Project Pattern Analysis ===\n")

    # Statistics
    node_frequency = Counter()
    node_sequences = defaultdict(list)
    property_values = defaultdict(lambda: defaultdict(list))
    workflow_patterns = []
    projects_analyzed = 0

    # Get project directories from environment or use defaults
    default_official_dir = os.path.join(
        os.path.expanduser("~"),
        "Documents",
        "references",
        "Real Projects",
        "Official Gaea Projects",
    )
    default_user_dir = os.path.join(
        os.path.expanduser("~"),
        "Documents",
        "references",
        "Real Projects",
        "user files",
    )

    official_dir = os.environ.get("GAEA_OFFICIAL_PROJECTS_DIR", default_official_dir)
    user_dir = os.environ.get("GAEA_USER_PROJECTS_DIR", default_user_dir)

    # Build list of directories that exist
    directories = []
    if os.path.exists(official_dir):
        directories.append(official_dir)
    else:
        print(f"Warning: Official projects directory not found: {official_dir}")
        print("Set GAEA_OFFICIAL_PROJECTS_DIR environment variable to specify the correct path")

    if os.path.exists(user_dir):
        directories.append(user_dir)
    else:
        print(f"Warning: User projects directory not found: {user_dir}")
        print("Set GAEA_USER_PROJECTS_DIR environment variable to specify the correct path")

    if not directories:
        print("\nNo project directories found. Please set environment variables.")
        return

    for directory in directories:
        print(f"\nAnalyzing projects in: {directory}")
        path = Path(directory)

        for file_path in path.glob("*.terrain"):
            try:
                with open(file_path, "r") as f:
                    project_data = json.load(f)

                nodes, connections = WorkflowExtractor.extract_workflow(project_data)

                if nodes:
                    projects_analyzed += 1
                    print(f"  ✓ {file_path.name}: {len(nodes)} nodes, {len(connections)} connections")

                    # Analyze node frequency
                    for node in nodes:
                        node_frequency[node["type"]] += 1

                        # Analyze properties
                        for prop, value in node.get("properties", {}).items():
                            if isinstance(value, (int, float, str, bool)):
                                property_values[node["type"]][prop].append(value)

                    # Analyze sequences
                    node_map = {n["id"]: n["type"] for n in nodes}
                    for conn in connections:
                        from_type = node_map.get(conn["from_node"])
                        to_type = node_map.get(conn["to_node"])
                        if from_type and to_type:
                            node_sequences[from_type].append(to_type)

                    # Extract workflow pattern
                    if len(nodes) >= 2:
                        pattern = []
                        # Find start node
                        incoming = {c["to_node"] for c in connections}
                        start_nodes = [n for n in nodes if n["id"] not in incoming]

                        if start_nodes:
                            current = start_nodes[0]
                            visited = set()

                            while current and current["id"] not in visited:
                                pattern.append(current["type"])
                                visited.add(current["id"])

                                # Find next
                                next_conn = next(
                                    (c for c in connections if c["from_node"] == current["id"]),
                                    None,
                                )
                                if next_conn:
                                    current = next(
                                        (n for n in nodes if n["id"] == next_conn["to_node"]),
                                        None,
                                    )
                                else:
                                    current = None

                            if len(pattern) >= 2:
                                workflow_patterns.append(pattern)

            except Exception as e:
                print(f"  ✗ Error analyzing {file_path.name}: {str(e)}")
                import traceback

                traceback.print_exc()

    # Generate report
    print("\n=== Analysis Complete ===")
    print(f"Total projects analyzed: {projects_analyzed}")
    print(f"Unique node types found: {len(node_frequency)}")

    print("\n=== Most Common Nodes (Top 20) ===")
    for node, count in node_frequency.most_common(20):
        print(f"  {node}: {count} occurrences")

    print("\n=== Common Node Sequences ===")
    for node, followers in node_sequences.items():
        if followers:
            follower_counts = Counter(followers)
            most_common = follower_counts.most_common(3)
            if most_common:
                print(f"\n{node} is commonly followed by:")
                for follower, count in most_common:
                    print(f"  → {follower} ({count} times)")

    print("\n=== Common Property Values ===")
    # Show property ranges for key nodes
    key_nodes = ["Mountain", "Erosion", "Erosion2", "Canyon", "Rivers", "Snow"]
    for node in key_nodes:
        if node in property_values:
            print(f"\n{node} properties:")
            for prop, values in property_values[node].items():
                if values and all(isinstance(v, (int, float)) for v in values):
                    min_val = min(values)
                    max_val = max(values)
                    avg_val = sum(values) / len(values)
                    print(f"  {prop}: min={min_val:.2f}, max={max_val:.2f}, avg={avg_val:.2f}")

    print("\n=== Common Workflow Patterns ===")
    # Count pattern frequency
    pattern_counts = Counter()
    for pattern in workflow_patterns:
        # Use first 3-4 nodes as pattern signature
        signature = "→".join(pattern[:4])
        pattern_counts[signature] += 1

    for pattern, count in pattern_counts.most_common(10):
        print(f"  {pattern} (used {count} times)")

    # Save results
    results = {
        "projects_analyzed": projects_analyzed,
        "node_frequency": dict(node_frequency),
        "node_sequences": {node: Counter(sequences).most_common(5) for node, sequences in node_sequences.items()},
        "workflow_patterns": [{"pattern": pattern, "count": count} for pattern, count in pattern_counts.most_common(20)],
    }

    with open("gaea2_analysis_results.json", "w") as f:
        json.dump(results, f, indent=2)

    print("\n✓ Results saved to gaea2_analysis_results.json")


if __name__ == "__main__":
    analyze_projects()
