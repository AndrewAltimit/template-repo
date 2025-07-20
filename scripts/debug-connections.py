#!/usr/bin/env python3
"""
Debug connection processing in Gaea2 MCP server
"""

# Simulate what the server is doing
connections = [
    {"from_node": 949, "to_node": 427, "from_port": "Rivers", "to_port": "In"},
    {"from_node": 287, "to_node": 483, "from_port": "Out", "to_port": "In"},
    {"from_node": 514, "to_node": 949, "from_port": "Out", "to_port": "In"},
    {"from_node": 639, "to_node": 975, "from_port": "Out", "to_port": "In"},
    {"from_node": 287, "to_node": 958, "from_port": "Out", "to_port": "In"},
]

# Pre-process connections like the server does
node_connections = {}
for conn in connections:
    to_id = conn.get("to_node")
    to_port = conn.get("to_port", "In")
    if to_id not in node_connections:
        node_connections[to_id] = {}
    node_connections[to_id][to_port] = conn
    print(f"Added connection: {conn['from_node']} -> {to_id}:{to_port}")

print(f"\nnode_connections dict: {node_connections}")
print(f"\nKeys in node_connections: {list(node_connections.keys())}")

# Test lookups
test_ids = [427, 483, 949, 975, 958, "427", "483", "949", "975", "958"]
for test_id in test_ids:
    print(f"\n{test_id} (type: {type(test_id)}) in node_connections: {test_id in node_connections}")
    if test_id in node_connections:
        print(f"  Ports: {list(node_connections[test_id].keys())}")
