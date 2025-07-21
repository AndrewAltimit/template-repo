#!/usr/bin/env python3
"""Analyze all Gaea reference projects to understand structure and patterns."""

import json
import os
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple


def analyze_terrain_file(file_path: Path) -> Dict[str, Any]:
    """Analyze a single terrain file and extract key information."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        terrain = data["Assets"]["$values"][0]["Terrain"]
        nodes = terrain.get("Nodes", {})

        # Extract node information
        node_info = []
        connections = []

        for node_id, node_data in nodes.items():
            if node_id == "$id":
                continue

            node_type = node_data.get("$type", "").split(".")[-2] if "$type" in node_data else "Unknown"
            node_name = node_data.get("Name", "Unnamed")

            node_info.append(
                {
                    "id": node_id,
                    "type": node_type,
                    "name": node_name,
                    "position": node_data.get("Position", {}),
                    "properties": {
                        k: v
                        for k, v in node_data.items()
                        if k
                        not in [
                            "$id",
                            "$type",
                            "Name",
                            "Position",
                            "Ports",
                            "Id",
                            "Modifiers",
                            "SnapIns",
                        ]
                    },
                }
            )

            # Extract connections from ports
            ports = node_data.get("Ports", {}).get("$values", [])
            for port in ports:
                if "Record" in port and port["Record"]:
                    record = port["Record"]
                    connections.append(
                        {
                            "from": str(record.get("From", "")),
                            "to": str(record.get("To", "")),
                            "from_port": record.get("FromPort", ""),
                            "to_port": record.get("ToPort", ""),
                        }
                    )

        # Get automation variables if present
        automation = terrain.get("Automation", {})
        variables = automation.get("Variables", {})
        bindings = automation.get("Bindings", {}).get("$values", [])

        return {
            "file": file_path.name,
            "nodes": node_info,
            "connections": connections,
            "node_count": len(node_info),
            "connection_count": len(connections),
            "variables": variables,
            "bindings": bindings,
            "metadata": terrain.get("Metadata", {}),
        }
    except Exception as e:
        return {"file": file_path.name, "error": str(e), "nodes": [], "connections": []}


def analyze_all_references():
    """Analyze all Gaea reference files."""
    ref_dir = Path("/home/miku/Documents/repos/template-repo/gaea-references")
    terrain_files = sorted(ref_dir.glob("*.terrain"))

    print(f"Found {len(terrain_files)} reference terrain files\n")

    all_analyses = []
    node_type_counter = Counter()
    connection_patterns = defaultdict(lambda: defaultdict(int))
    property_patterns = defaultdict(set)

    for terrain_file in terrain_files:
        print(f"\n{'='*60}")
        print(f"Analyzing: {terrain_file.name}")
        print("=" * 60)

        analysis = analyze_terrain_file(terrain_file)
        all_analyses.append(analysis)

        if "error" in analysis:
            print(f"ERROR: {analysis['error']}")
            continue

        print(f"Nodes: {analysis['node_count']}")
        print(f"Connections: {analysis['connection_count']}")

        # Print node types
        print("\nNode Types:")
        node_types = Counter(node["type"] for node in analysis["nodes"])
        for node_type, count in node_types.most_common():
            print(f"  - {node_type}: {count}")
            node_type_counter[node_type] += count

        # Analyze connection patterns
        print("\nConnection Patterns:")
        for conn in analysis["connections"]:
            from_node = next((n for n in analysis["nodes"] if n["id"] == conn["from"]), None)
            to_node = next((n for n in analysis["nodes"] if n["id"] == conn["to"]), None)

            if from_node and to_node:
                pattern = f"{from_node['type']} -> {to_node['type']}"
                connection_patterns[pattern][f"{conn['from_port']} -> {conn['to_port']}"] += 1

        # Collect property patterns
        for node in analysis["nodes"]:
            for prop_name in node["properties"]:
                property_patterns[node["type"]].add(prop_name)

        # Show variables if present
        if analysis["variables"]:
            print("\nVariables:")
            for var_name, var_value in analysis["variables"].items():
                print(f"  - {var_name}: {var_value}")

        # Show bindings if present
        if analysis["bindings"]:
            print("\nBindings:")
            for binding in analysis["bindings"]:
                print(
                    f"  - Node {binding.get('Node')} property '{binding.get('Property')}' -> Variable '{binding.get('Variable')}'"
                )

    # Summary statistics
    print(f"\n\n{'='*60}")
    print("OVERALL SUMMARY")
    print("=" * 60)

    print("\nMost Common Node Types Across All Projects:")
    for node_type, count in node_type_counter.most_common(15):
        print(f"  - {node_type}: {count}")

    print("\nMost Common Connection Patterns:")
    pattern_counter = Counter()
    for pattern, ports in connection_patterns.items():
        total = sum(ports.values())
        pattern_counter[pattern] = total

    for pattern, count in pattern_counter.most_common(10):
        print(f"  - {pattern}: {count}")
        # Show port details for this pattern
        for port_pattern, port_count in sorted(connection_patterns[pattern].items(), key=lambda x: x[1], reverse=True)[:3]:
            print(f"      {port_pattern}: {port_count}")

    print("\nCommon Properties by Node Type:")
    for node_type in sorted(list(property_patterns.keys()))[:10]:
        props = sorted(property_patterns[node_type])
        if props:
            print(f"\n  {node_type}:")
            for prop in props[:10]:  # Show first 10 properties
                print(f"    - {prop}")

    # Test-worthy scenarios
    print(f"\n\n{'='*60}")
    print("TEST-WORTHY SCENARIOS")
    print("=" * 60)

    print("\n1. Complex Workflows:")
    for analysis in all_analyses:
        if analysis["node_count"] > 15:
            print(f"   - {analysis['file']}: {analysis['node_count']} nodes, {analysis['connection_count']} connections")

    print("\n2. Variable/Automation Usage:")
    for analysis in all_analyses:
        if analysis["variables"] or analysis["bindings"]:
            print(f"   - {analysis['file']}: {len(analysis['variables'])} variables, {len(analysis['bindings'])} bindings")

    print("\n3. Unique Node Types:")
    unique_types = set()
    for analysis in all_analyses:
        for node in analysis["nodes"]:
            if node_type_counter[node["type"]] <= 2:  # Rare nodes
                unique_types.add(node["type"])

    if unique_types:
        print("   Rare node types to test:")
        for node_type in sorted(unique_types):
            print(f"   - {node_type}")

    print("\n4. Multi-port Connections:")
    multi_port_nodes = set()
    for pattern, ports in connection_patterns.items():
        if len(ports) > 1:  # Multiple port combinations
            src, dst = pattern.split(" -> ")
            multi_port_nodes.add(src)
            multi_port_nodes.add(dst)

    if multi_port_nodes:
        print("   Nodes with multiple port configurations:")
        for node_type in sorted(multi_port_nodes)[:10]:
            print(f"   - {node_type}")


if __name__ == "__main__":
    analyze_all_references()
