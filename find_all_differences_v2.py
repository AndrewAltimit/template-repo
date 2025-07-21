import json

# Load files
with open("test_basic_output.json", "r") as f:
    generated = json.load(f)

with open("gaea-references/Official Gaea Projects/Alien Surface.terrain", "r") as f:
    reference = json.load(f)

print("=== CRITICAL DIFFERENCES FOUND ===\n")

# 1. Port key ordering
print("1. PORT KEY ORDERING (CRITICAL):")
gen_node = generated["Assets"]["$values"][0]["Terrain"]["Nodes"]["101"]
ref_node = reference["Assets"]["$values"][0]["Terrain"]["Nodes"]["817"]

gen_port = gen_node["Ports"]["$values"][0]
ref_port = ref_node["Ports"]["$values"][0]

print(f"Generated: {list(gen_port.keys())}")
print(f"Reference: {list(ref_port.keys())}")
print("❌ Record must come BEFORE IsExporting and Parent")

# 2. Type field format
print("\n2. TYPE FIELD FORMAT:")
print(f"Generated: Type = '{gen_port['Type']}'")
print(f"Reference: Type = '{ref_port['Type']}'")
print("❌ Missing ', Required' suffix for required ports")

# 3. IsMaskable location
print("\n3. ISMASKABLE PROPERTY:")
gen_ismaskable = "IsMaskable" in gen_node
ref_ismaskable = "IsMaskable" in ref_node
print(f"Generated has IsMaskable at node level: {gen_ismaskable}")
print(f"Reference has IsMaskable at node level: {ref_ismaskable}")
if not gen_ismaskable and ref_ismaskable:
    print("❌ Missing IsMaskable at node level")

# 4. Check BuildDefinition location
print("\n4. BUILDDEFINITION LOCATION:")
# It's at the Asset level, not Terrain level
gen_build = generated["Assets"]["$values"][0].get("BuildDefinition")
ref_build = reference["Assets"]["$values"][0].get("BuildDefinition")

if gen_build:
    print("Generated BuildDefinition found at Asset level")
    print(f"  Destination: {repr(gen_build.get('Destination'))}")
else:
    print("❌ BuildDefinition not found at Asset level")

if ref_build:
    print("Reference BuildDefinition found at Asset level")
    print(f"  Destination: {repr(ref_build.get('Destination'))}")

# 5. Check where SnapIns property is
print("\n5. SNAPINS PROPERTY:")
print(f"Generated has SnapIns: {'SnapIns' in gen_node}")
print(f"Reference has SnapIns: {'SnapIns' in ref_node}")

# 6. Check property order in nodes
print("\n6. NODE PROPERTY ORDER:")
print("Generated node property order:")
for i, key in enumerate(list(gen_node.keys())[:10]):
    print(f"  {i+1}. {key}")
print("\nReference node property order:")
for i, key in enumerate(list(ref_node.keys())[:10]):
    print(f"  {i+1}. {key}")

# 7. Check Range object format in detail
print("\n7. RANGE/SIZE/HEIGHT OBJECTS:")
for node_id, node in reference["Assets"]["$values"][0]["Terrain"]["Nodes"].items():
    if node_id != "$id":
        if "Size" in node:
            print(f"Reference Size object: {node['Size']}")
            print(f"  Has $id: {'$id' in node['Size']}")
            break
