import json

# Load files
with open("test_basic_output.json", "r") as f:
    generated = json.load(f)

with open("gaea-references/Official Gaea Projects/Alien Surface.terrain", "r") as f:
    reference = json.load(f)

print("=== KEY DIFFERENCES FOUND ===\n")

# 1. Port key ordering
print("1. PORT KEY ORDERING:")
gen_node = generated["Assets"]["$values"][0]["Terrain"]["Nodes"]["101"]
ref_node = reference["Assets"]["$values"][0]["Terrain"]["Nodes"]["817"]

gen_port = gen_node["Ports"]["$values"][0]
ref_port = ref_node["Ports"]["$values"][0]

print(f"Generated: {list(gen_port.keys())}")
print(f"Reference: {list(ref_port.keys())}")

# 2. Type field format
print("\n2. TYPE FIELD FORMAT:")
print(f"Generated: Type = '{gen_port['Type']}'")
print(f"Reference: Type = '{ref_port['Type']}'")

# 3. Check if nodes have IsMaskable
print("\n3. NODE-LEVEL PROPERTIES:")
print(f"Generated node keys: {list(gen_node.keys())}")
print(f"Reference node keys: {list(ref_node.keys())}")

# 4. Check BuildDefinition
print("\n4. BUILDDEFINITION DIFFERENCES:")
gen_build = generated["Assets"]["$values"][0]["Terrain"]["BuildDefinition"]
ref_build = reference["Assets"]["$values"][0]["Terrain"]["BuildDefinition"]

for key in ["Destination", "TilePattern"]:
    print(f"{key}:")
    print(f"  Generated: {repr(gen_build.get(key))}")
    print(f"  Reference: {repr(ref_build.get(key))}")

# 5. Check Range objects
print("\n5. RANGE OBJECT FORMAT:")
# Find a node with Range property
for node_id, node in generated["Assets"]["$values"][0]["Terrain"]["Nodes"].items():
    if node_id != "$id" and "Range" in str(node):
        if "SatMap" in node.get("$type", ""):
            print(f"Generated SatMap Range: {node.get('Range')}")
            break

for node_id, node in reference["Assets"]["$values"][0]["Terrain"]["Nodes"].items():
    if node_id != "$id" and "Range" in str(node):
        print(f"Reference node {node_id} Range: {node.get('Range')}")
        if "Size" in node:
            print(f"Reference node Size: {node.get('Size')}")
        if "Height" in node:
            print(f"Reference node Height: {node.get('Height')}")
        break
