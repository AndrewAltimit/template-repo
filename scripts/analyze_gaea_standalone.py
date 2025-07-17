#!/usr/bin/env python3
"""
Standalone Gaea2 project analyzer
"""

import json
import logging
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def extract_workflow(project_data: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Extract nodes and connections from project data"""
    nodes = []
    connections = []

    # Navigate the project structure
    assets = project_data.get("Assets", {})

    # Handle both direct assets and $values format
    if "$values" in assets and isinstance(assets["$values"], list):
        assets_list = assets["$values"]
        if not assets_list or not isinstance(assets_list[0], dict):
            return nodes, connections
        terrain = assets_list[0].get("Terrain", {})
    else:
        # Some projects might have terrain directly
        terrain = project_data.get("Terrain", {})
    nodes_dict = terrain.get("Nodes", {})

    # Convert nodes dict to list
    for node_id, node_data in nodes_dict.items():
        # Skip non-dict entries
        if not isinstance(node_data, dict):
            continue

        node = {
            "id": node_data.get("Id", int(node_id) if node_id.isdigit() else 0),
            "type": node_data.get("$type", "").split(".")[-2] if "$type" in node_data else "Unknown",
            "name": node_data.get("Name", ""),
            "properties": {},
        }

        # Extract properties
        for key, value in node_data.items():
            if key not in ["$id", "$type", "Id", "Name", "Position", "Ports", "Modifiers", "SnapIns"]:
                node["properties"][key] = value

        nodes.append(node)

    # Extract connections from ports
    for node_id, node_data in nodes_dict.items():
        # Skip non-dict entries
        if not isinstance(node_data, dict):
            continue

        ports = node_data.get("Ports", {}).get("$values", [])
        for port in ports:
            if port.get("Record"):
                record = port["Record"]
                connections.append(
                    {
                        "from_node": record.get("From"),
                        "to_node": record.get("To"),
                        "from_port": record.get("FromPort", "Out"),
                        "to_port": record.get("ToPort", "In"),
                    }
                )

    return nodes, connections


def analyze_projects():
    """Analyze all real Gaea2 projects"""
    print("=== Gaea2 Project Pattern Analysis ===\n")

    # Statistics
    node_frequency = Counter()
    node_sequences = defaultdict(list)
    property_values = defaultdict(lambda: defaultdict(list))
    workflow_patterns = []
    projects_analyzed = 0

    # Analyze directories
    directories = [
        "/home/miku/Documents/references/Real Projects/Official Gaea Projects",
        "/home/miku/Documents/references/Real Projects/mikus files",
    ]

    for directory in directories:
        print(f"\nAnalyzing projects in: {directory}")
        path = Path(directory)

        for file_path in path.glob("*.terrain"):
            try:
                with open(file_path, "r") as f:
                    project_data = json.load(f)

                nodes, connections = extract_workflow(project_data)

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
                                next_conn = next((c for c in connections if c["from_node"] == current["id"]), None)
                                if next_conn:
                                    current = next((n for n in nodes if n["id"] == next_conn["to_node"]), None)
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
