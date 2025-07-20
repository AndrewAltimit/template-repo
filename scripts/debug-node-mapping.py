#!/usr/bin/env python3
"""Debug node ID mapping issue"""

# Simulate what happens in the server
nodes = [
    {"id": 183, "type": "Volcano"},
    {"id": 287, "type": "Sea"},
    {"id": 483, "type": "TextureBase"},
    {"id": 949, "type": "Rivers"},
    {"id": 427, "type": "Adjust"},
]

connections = [
    {"from_node": 287, "to_node": 483, "from_port": "Out", "to_port": "In"},
    {"from_node": 949, "to_node": 427, "from_port": "Rivers", "to_port": "In"},
]

# Build node_id_map like the server does
node_id_map = {}
for i, node in enumerate(nodes):
    node_id = node.get("id")  # This returns an integer
    node_id_map[node.get("id", f"node_{i}")] = node_id

print("node_id_map:")
for k, v in node_id_map.items():
    print(f"  {k} ({type(k)}) -> {v} ({type(v)})")

# Build node_connections with string keys
node_connections = {}
for conn in connections:
    to_id = conn.get("to_node")
    to_port = conn.get("to_port", "In")
    to_id_str = str(to_id) if to_id is not None else None
    if to_id_str not in node_connections:
        node_connections[to_id_str] = {}
    node_connections[to_id_str][to_port] = conn

print("\nnode_connections:")
for k, v in node_connections.items():
    print(f"  {k} ({type(k)}) -> {v}")

# Test lookups
print("\nTesting lookups:")
for node in nodes:
    node_str_id = str(node.get("id"))
    print(f"\nProcessing node {node_str_id}:")

    if node_str_id in node_connections:
        conn = node_connections[node_str_id]["In"]
        from_node = conn.get("from_node")  # This is an integer
        print(f"  from_node: {from_node} ({type(from_node)})")

        # Try lookup
        from_id = node_id_map.get(from_node)
        print(f"  node_id_map.get({from_node}) = {from_id}")

        if from_id is None:
            print(f"  FAILED! {from_node} not found in node_id_map keys: {list(node_id_map.keys())}")
