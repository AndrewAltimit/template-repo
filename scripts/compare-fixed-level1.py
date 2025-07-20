#!/usr/bin/env python3
"""
Compare the fixed Level1 with the reference
"""

import json


def extract_connections(filename):
    """Extract all connections from a terrain file"""
    connections = []

    try:
        with open(filename, "r") as f:
            content = f.read()
            data = json.loads(content)

        # Navigate to terrain nodes
        terrain = data.get("Assets", {}).get("$values", [{}])[0].get("Terrain", {})
        nodes = terrain.get("Nodes", {})

        for node_id, node_data in nodes.items():
            if isinstance(node_id, str) and node_id.startswith("$"):
                continue

            if isinstance(node_data, dict) and "Ports" in node_data:
                ports = node_data["Ports"].get("$values", [])
                for port in ports:
                    if isinstance(port, dict) and "Record" in port:
                        record = port["Record"]
                        connections.append(
                            {
                                "from": record["From"],
                                "to": record["To"],
                                "from_port": record["FromPort"],
                                "to_port": record["ToPort"],
                            }
                        )

    except Exception as e:
        print(f"Error reading {filename}: {e}")
        return []

    return connections


def main():
    # Compare reference and fixed files
    ref_connections = extract_connections("reference projects/mikus files/Level1.terrain")
    fixed_connections = extract_connections("output/gaea2/level1_fixed.terrain")

    print(f"Reference Level1.terrain: {len(ref_connections)} connections")
    print(f"Fixed Level1.terrain: {len(fixed_connections)} connections")

    # Find differences
    ref_set = {(c["from"], c["to"], c["from_port"], c["to_port"]) for c in ref_connections}
    fixed_set = {(c["from"], c["to"], c["from_port"], c["to_port"]) for c in fixed_connections}

    missing = ref_set - fixed_set
    extra = fixed_set - ref_set

    if missing:
        print(f"\nMissing connections: {len(missing)}")
        for conn in sorted(missing):
            print(f"  {conn[0]} -> {conn[1]} ({conn[2]} -> {conn[3]})")
    else:
        print("\n✓ No missing connections!")

    if extra:
        print(f"\nExtra connections: {len(extra)}")
        for conn in sorted(extra):
            print(f"  {conn[0]} -> {conn[1]} ({conn[2]} -> {conn[3]})")
    else:
        print("✓ No extra connections!")

    if not missing and not extra:
        print("\n🎉 Perfect match! The fixed Level1 has all the same connections as the reference!")


if __name__ == "__main__":
    main()
