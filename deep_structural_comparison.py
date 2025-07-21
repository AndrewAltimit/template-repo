import json
import os

# Load files
with open("working_project.json", "r") as f:
    working = json.load(f)

with open("test_no_props_arctic.json", "r") as f:
    generated = json.load(f)

print("=== DEEP STRUCTURAL COMPARISON ===\n")

# 1. Check JSON string differences
working_str = json.dumps(working, separators=(",", ":"))
generated_str = json.dumps(generated, separators=(",", ":"))

print("1. RAW JSON CHARACTERISTICS:")
print(f"Working size: {len(working_str)} chars")
print(f"Generated size: {len(generated_str)} chars")

# 2. Check ID formats in detail
print("\n2. ID FORMAT ANALYSIS:")
print(f"Working top Id: '{working['Id']}' (len={len(working['Id'])})")
print(f"Generated top Id: '{generated['Id']}' (len={len(generated['Id'])})")

# Check if IDs have hyphens
print(f"\nWorking has hyphens in IDs: {'-' in working_str}")
print(f"Generated has hyphens in IDs: {'-' in generated_str}")

# 3. Check SaveDefinition presence
print("\n3. SAVEDEFINITION CHECK:")
working_has_savedef = "SaveDefinition" in working_str
generated_has_savedef = "SaveDefinition" in generated_str
print(f"Working has SaveDefinition: {working_has_savedef}")
print(f"Generated has SaveDefinition: {generated_has_savedef}")

if generated_has_savedef:
    # Find Export node
    gen_nodes = generated["Assets"]["$values"][0]["Terrain"]["Nodes"]
    for node_id, node in gen_nodes.items():
        if node_id != "$id" and "Export" in node.get("$type", ""):
            print(f"\nExport node SaveDefinition: {node.get('SaveDefinition')}")
            break

# 4. Check Format field in Export node
print("\n4. EXPORT NODE FORMAT FIELD:")
work_nodes = working["Assets"]["$values"][0]["Terrain"]["Nodes"]
gen_nodes = generated["Assets"]["$values"][0]["Terrain"]["Nodes"]

# Working doesn't have Export, but let's check generated
for node_id, node in gen_nodes.items():
    if node_id != "$id" and "Export" in node.get("$type", ""):
        exclude = ["$id", "$type", "Id", "Name", "Position", "Ports", "Modifiers", "NodeSize", "SaveDefinition"]
        props = {k: v for k, v in node.items() if k not in exclude}
        print(f"Export node extra fields: {props}")
        break

# 5. Check Modifiers structure
print("\n5. MODIFIERS STRUCTURE:")
# Check first node's Modifiers
for node_id, node in work_nodes.items():
    if node_id != "$id":
        print(f"Working Modifiers: {node.get('Modifiers')}")
        break

for node_id, node in gen_nodes.items():
    if node_id != "$id":
        print(f"Generated Modifiers: {node.get('Modifiers')}")
        break

# 6. Check Camera object
print("\n6. CAMERA OBJECT:")
work_camera = working["Assets"]["$values"][0]["State"]["Viewport"]["Camera"]
gen_camera = generated["Assets"]["$values"][0]["State"]["Viewport"]["Camera"]
print(f"Working Camera: {work_camera}")
print(f"Generated Camera: {gen_camera}")

# 7. Check exact field ordering at Asset level
print("\n7. ASSET-LEVEL FIELD ORDER:")
work_asset = working["Assets"]["$values"][0]
gen_asset = generated["Assets"]["$values"][0]

print("Working asset field order:")
for i, key in enumerate(list(work_asset.keys())):
    print(f"  {i+1}. {key}")

print("\nGenerated asset field order:")
for i, key in enumerate(list(gen_asset.keys())):
    print(f"  {i+1}. {key}")

# 8. Check if any values are None vs empty dict
print("\n8. NULL vs EMPTY OBJECT CHECK:")


def find_nulls_and_empty(obj, path=""):
    if obj is None:
        print(f"  NULL at: {path}")
    elif obj == {}:
        print(f"  EMPTY DICT at: {path}")
    elif isinstance(obj, dict):
        for k, v in obj.items():
            find_nulls_and_empty(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            find_nulls_and_empty(v, f"{path}[{i}]")


print("\nWorking file:")
find_nulls_and_empty(working)
print("\nGenerated file:")
find_nulls_and_empty(generated)

# 9. Check specific string patterns
print("\n9. STRING PATTERN CHECK:")
patterns = [
    "QuadSpinner.Gaea.Nodes",
    "Gaea.Nodes",
    ", Gaea.Nodes",
    "PrimaryIn, Required",
    "NodeSize",
    "IsMaskable",
    "PortCount",
]

for pattern in patterns:
    work_count = working_str.count(pattern)
    gen_count = generated_str.count(pattern)
    if work_count != gen_count:
        print(f"'{pattern}': Working={work_count}, Generated={gen_count}")
