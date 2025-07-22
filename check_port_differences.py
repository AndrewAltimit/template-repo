import json

# Load files
with open("gaea-references/Official Gaea Projects/Alien Surface.terrain", "r") as f:
    reference = json.load(f)

with open("test_arctic_final.json", "r") as f:
    generated = json.load(f)

print("=== DETAILED PORT COMPARISON ===\n")

# Find a port with Record in reference
ref_port = None
ref_nodes = reference["Assets"]["$values"][0]["Terrain"]["Nodes"]
for node_id, node in ref_nodes.items():
    if node_id != "$id" and "Ports" in node:
        ports = node["Ports"]["$values"]
        for port in ports:
            if "Record" in port:
                ref_port = port
                print("REFERENCE PORT (with Record):")
                print(json.dumps(port, indent=2))
                break
        if ref_port:
            break

# Find a port with Record in generated
gen_port = None
gen_nodes = generated["Assets"]["$values"][0]["Terrain"]["Nodes"]
for node_id, node in gen_nodes.items():
    if node_id != "$id" and "Ports" in node:
        ports = node["Ports"]["$values"]
        for port in ports:
            if "Record" in port:
                gen_port = port
                print("\nGENERATED PORT (with Record):")
                print(json.dumps(port, indent=2))
                break
        if gen_port:
            break

# Compare key by key
print("\n=== KEY BY KEY COMPARISON ===")
if ref_port and gen_port:
    ref_keys = list(ref_port.keys())
    gen_keys = list(gen_port.keys())

    print(f"\nReference keys: {ref_keys}")
    print(f"Generated keys: {gen_keys}")

    if ref_keys != gen_keys:
        print("\n❌ KEY ORDER MISMATCH!")
    else:
        print("\n✓ Key order matches")

# Check for subtle differences
print("\n=== CHECKING SUBTLE DIFFERENCES ===")

# Check if IsExporting is boolean
print(f"\nReference IsExporting type: {type(ref_port.get('IsExporting'))}")
print(f"Generated IsExporting type: {type(gen_port.get('IsExporting'))}")

# Check Parent structure
print(f"\nReference Parent: {ref_port.get('Parent')}")
print(f"Generated Parent: {gen_port.get('Parent')}")

# Look for SatMap node specifically
print("\n=== SATMAP NODE CHECK ===")
for node_id, node in gen_nodes.items():
    if node_id != "$id" and "SatMap" in node.get("$type", ""):
        print(f"\nFound SatMap node: {node['Name']}")
        # Check its In port
        if "Ports" in node:
            for port in node["Ports"]["$values"]:
                if port["Name"] == "In":
                    print("SatMap In port:")
                    print(json.dumps(port, indent=2))
                    # Check if Record comes after Type but before IsExporting
                    keys = list(port.keys())
                    if "Record" in keys:
                        type_idx = keys.index("Type")
                        record_idx = keys.index("Record")
                        export_idx = keys.index("IsExporting")
                        print(f"\nKey positions: Type={type_idx}, Record={record_idx}, IsExporting={export_idx}")
                        if record_idx > type_idx and record_idx < export_idx:
                            print("✓ Record is between Type and IsExporting")
                        else:
                            print("❌ Record position is wrong!")
                    break
