#!/usr/bin/env python3
"""
Analyze connections in the Level1 terrain files
"""

import json
from typing import Dict, List, Tuple


def extract_connections_from_terrain(
    terrain_data: Dict,
) -> List[Tuple[int, int, str, str]]:
    """Extract all connections from a terrain file structure"""
    connections = []

    if isinstance(terrain_data, str):
        terrain_data = json.loads(terrain_data)

    # Navigate to nodes
    nodes = terrain_data.get("Assets", {}).get("$values", [{}])[0].get("Terrain", {}).get("Nodes", {})

    # For each node, check all ports for Record objects
    for node_id, node_data in nodes.items():
        if not isinstance(node_data, dict):
            continue

        ports = node_data.get("Ports", {}).get("$values", [])

        for port in ports:
            if "Record" in port:
                record = port["Record"]
                from_id = record.get("From")
                to_id = record.get("To")
                from_port = record.get("FromPort", "Out")
                to_port = record.get("ToPort", "In")

                if from_id and to_id:
                    connections.append((from_id, to_id, from_port, to_port))

    return sorted(connections)


def compare_connections(ref_connections: List[Tuple], gen_connections: List[Tuple]) -> None:
    """Compare two sets of connections and report differences"""
    ref_set = set(ref_connections)
    gen_set = set(gen_connections)

    missing = ref_set - gen_set
    extra = gen_set - ref_set

    print(f"\nReference has {len(ref_connections)} connections")
    print(f"Generated has {len(gen_connections)} connections")

    if missing:
        print(f"\nMISSING {len(missing)} connections in generated file:")
        for conn in sorted(missing):
            print(f"  {conn[0]} -> {conn[1]} (port: {conn[2]} -> {conn[3]})")
    else:
        print("\nNo missing connections! ✓")

    if extra:
        print(f"\nEXTRA {len(extra)} connections in generated file:")
        for conn in sorted(extra):
            print(f"  {conn[0]} -> {conn[1]} (port: {conn[2]} -> {conn[3]})")

    if not missing and not extra:
        print("\nConnections match perfectly! 🎉")


def main():
    # Read reference Level1.terrain
    ref_path = "reference projects/mikus files/Level1.terrain"
    gen_path = "output/gaea2/generated-level-1.terrain"

    print("Reading reference Level1.terrain...")
    try:
        with open(ref_path, "r") as f:
            ref_data = json.load(f)
    except Exception as e:
        print(f"Error reading reference file: {e}")
        return

    print("Reading generated terrain file...")
    try:
        with open(gen_path, "r") as f:
            gen_data = json.load(f)
    except Exception as e:
        print(f"Error reading generated file: {e}")
        print("File might not exist locally. The server generated it successfully.")
        return

    # Extract connections
    ref_connections = extract_connections_from_terrain(ref_data)
    gen_connections = extract_connections_from_terrain(gen_data)

    # Compare
    compare_connections(ref_connections, gen_connections)

    # Also check our test output from the API
    print("\n" + "=" * 50)
    print("Checking connections from our test script API response...")

    # The expected connections from our test script
    expected_connections = [
        (183, 281, "Out", "In"),
        (668, 281, "Out", "Input2"),
        (281, 294, "Out", "In"),
        (294, 639, "Out", "In"),
        (639, 975, "Out", "In"),
        (975, 514, "Out", "In"),
        (514, 949, "Out", "In"),
        (949, 287, "Out", "In"),
        (949, 427, "Rivers", "In"),
        (287, 483, "Out", "In"),
        (483, 800, "Out", "In"),
        (483, 375, "Out", "In"),
        (483, 340, "Out", "In"),
        (483, 258, "Out", "In"),
        (800, 245, "Out", "In"),
        (375, 245, "Out", "Input2"),
        (427, 245, "Out", "Mask"),
        (245, 490, "Out", "In"),
        (340, 490, "Out", "Input2"),
        (287, 490, "Water", "Mask"),
        (287, 958, "Out", "In"),
        (490, 174, "Out", "In"),
        (258, 174, "Out", "Input2"),
        (958, 174, "Out", "Mask"),
    ]

    print(f"\nWe requested {len(expected_connections)} connections")
    print(f"Reference file has {len(ref_connections)} connections")

    # Check which ones we requested are in the reference
    expected_set = set(expected_connections)
    ref_set = set(ref_connections)

    in_both = expected_set & ref_set
    print(f"\n{len(in_both)} of our requested connections match the reference")

    not_in_ref = expected_set - ref_set
    if not_in_ref:
        print(f"\n{len(not_in_ref)} connections we requested are NOT in reference:")
        for conn in sorted(not_in_ref):
            print(f"  {conn[0]} -> {conn[1]} (port: {conn[2]} -> {conn[3]})")


if __name__ == "__main__":
    main()
