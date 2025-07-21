import json

# Load both files
with open("test_basic_output.json", "r") as f:
    generated = json.load(f)

with open("gaea-references/Official Gaea Projects/Alien Surface.terrain", "r") as f:
    reference = json.load(f)

# Compare a node's port structure
print("=== GENERATED PORT STRUCTURE ===")
gen_nodes = generated["Assets"]["$values"][0]["Terrain"]["Nodes"]
for node_id, node in gen_nodes.items():
    if node_id == "101":  # Erosion2 node
        ports = node.get("Ports", {}).get("$values", [])
        if ports:
            port = ports[0]  # First port
            print(json.dumps(port, indent=2))
            print(f"\nPort key order: {list(port.keys())}")
        break

print("\n=== REFERENCE PORT STRUCTURE ===")
ref_nodes = reference["Assets"]["$values"][0]["Terrain"]["Nodes"]
for node_id, node in ref_nodes.items():
    if node_id != "$id":
        ports = node.get("Ports", {}).get("$values", [])
        if ports and ports[0].get("Record"):  # Port with connection
            port = ports[0]
            print(json.dumps(port, indent=2))
            print(f"\nPort key order: {list(port.keys())}")
        break
