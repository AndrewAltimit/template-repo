import json

# Load both files
with open("working_project.json", "r") as f:
    working = json.load(f)

with open("test_final_fix_inline.json", "r") as f:
    broken = json.load(f)

print("=== CRITICAL DIFFERENCES: WORKING vs BROKEN ===\n")

# 1. Check Mountain node structure
print("1. MOUNTAIN NODE COMPARISON:")
working_mountain = working["Assets"]["$values"][0]["Terrain"]["Nodes"]["1"]
broken_mountain = broken["Assets"]["$values"][0]["Terrain"]["Nodes"]["100"]

print("\nWORKING Mountain node keys:")
print(list(working_mountain.keys()))

print("\nBROKEN Mountain node keys:")
print(list(broken_mountain.keys()))

# Check key differences
working_keys = set(working_mountain.keys())
broken_keys = set(broken_mountain.keys())

print("\nKeys in BROKEN but NOT in WORKING:")
for key in sorted(broken_keys - working_keys):
    print(f"  - {key}: {broken_mountain[key]}")

print("\nKeys in WORKING but NOT in BROKEN:")
for key in sorted(working_keys - broken_keys):
    print(f"  - {key}: {working_mountain[key]}")

# 2. Check property ordering
print("\n\n2. PROPERTY ORDER ANALYSIS:")
print("\nWORKING node property order:")
for i, key in enumerate(list(working_mountain.keys())[:15]):
    print(f"  {i+1}. {key}")

print("\nBROKEN node property order:")
for i, key in enumerate(list(broken_mountain.keys())[:15]):
    print(f"  {i+1}. {key}")

# 3. Check node ID format
print("\n\n3. NODE ID FORMAT:")
print(f"WORKING node key in Nodes dict: '1' (type: {type('1')})")
print(f"BROKEN node key in Nodes dict: '100' (type: {type('100')})")
print(f"WORKING node Id property: {working_mountain['Id']} (type: {type(working_mountain['Id'])})")
print(f"BROKEN node Id property: {broken_mountain['Id']} (type: {type(broken_mountain['Id'])})")

# 4. Check if boolean case matters
print("\n\n4. BOOLEAN CASE ANALYSIS:")
# Check in JSON string
working_str = json.dumps(working)
broken_str = json.dumps(broken)

print(f"WORKING has 'true': {working_str.count('true')}")
print(f"WORKING has 'True': {working_str.count('True')}")
print(f"WORKING has 'false': {working_str.count('false')}")
print(f"WORKING has 'False': {working_str.count('False')}")

print(f"\nBROKEN has 'true': {broken_str.count('true')}")
print(f"BROKEN has 'True': {broken_str.count('True')}")
print(f"BROKEN has 'false': {broken_str.count('false')}")
print(f"BROKEN has 'False': {broken_str.count('False')}")

# 5. Check if the node has NO properties at all
print("\n\n5. NODE PROPERTIES:")
print("\nWORKING Mountain node properties (excluding system fields):")
exclude_fields = ["$id", "$type", "Id", "Name", "Position", "Ports", "Modifiers"]
working_props = {k: v for k, v in working_mountain.items() if k not in exclude_fields}
print(f"Properties: {working_props}")

print("\nBROKEN Mountain node properties (excluding system fields):")
broken_props = {k: v for k, v in broken_mountain.items() if k not in exclude_fields}
print(f"Properties: {broken_props}")

# 6. Check metadata differences
print("\n\n6. TERRAIN METADATA:")
working_meta = working["Assets"]["$values"][0]["Terrain"]["Metadata"]
broken_meta = broken["Assets"]["$values"][0]["Terrain"]["Metadata"]

print(f"\nWORKING Metadata: {list(working_meta.keys())}")
print(f"BROKEN Metadata: {list(broken_meta.keys())}")

# 7. Check top-level Id format
print("\n\n7. TOP-LEVEL ID FORMAT:")
print(f"WORKING top-level Id: '{working['Id']}' (length: {len(working['Id'])})")
print(f"BROKEN top-level Id: '{broken['Id']}' (length: {len(broken['Id'])})")

# 8. Check if order of main sections matters
print("\n\n8. MAIN SECTION ORDER:")
print(f"WORKING asset keys: {list(working['Assets']['$values'][0].keys())}")
print(f"BROKEN asset keys: {list(broken['Assets']['$values'][0].keys())}")
