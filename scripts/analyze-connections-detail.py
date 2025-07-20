#!/usr/bin/env python3
"""
Analyze connections in detail from both files
"""

import json


def extract_connections(filename):
    """Extract all connections from a terrain file"""
    connections = []

    try:
        with open(filename, "r") as f:
            content = f.read()
            # Handle both minified and formatted JSON
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
    # Analyze reference file
    ref_connections = extract_connections("reference projects/mikus files/Level1.terrain")
    print(f"Reference Level1.terrain connections: {len(ref_connections)}")

    # Analyze generated file
    gen_connections = extract_connections("output/gaea2/generated-level-1.terrain")
    print(f"Generated Level1.terrain connections: {len(gen_connections)}")

    # Find missing connections
    ref_set = {(c["from"], c["to"], c["from_port"], c["to_port"]) for c in ref_connections}
    gen_set = {(c["from"], c["to"], c["from_port"], c["to_port"]) for c in gen_connections}

    missing = ref_set - gen_set
    extra = gen_set - ref_set

    print(f"\nMissing connections: {len(missing)}")
    for conn in sorted(missing):
        print(f"  {conn[0]} -> {conn[1]} ({conn[2]} -> {conn[3]})")

    print(f"\nExtra connections: {len(extra)}")
    for conn in sorted(extra):
        print(f"  {conn[0]} -> {conn[1]} ({conn[2]} -> {conn[3]})")

    # Show what connections we do have
    print("\nGenerated connections:")
    for conn in sorted(gen_connections, key=lambda x: (x["from"], x["to"])):
        print(f"  {conn['from']} -> {conn['to']} ({conn['from_port']} -> {conn['to_port']})")


if __name__ == "__main__":
    main()
