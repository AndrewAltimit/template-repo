import json
import os

# Load reference files and our generated file
reference_files = [
    "gaea-references/Official Gaea Projects/Alien Surface.terrain",
    "gaea-references/Official Gaea Projects/Canyon River with Sea.terrain",
    "gaea-references/Official Gaea Projects/Modular Portal - Terrain.terrain",
]

with open("test_final_fix_inline.json", "r") as f:
    generated = json.load(f)

print("=== ULTRA DEEP COMPARISON ===\n")

# 1. Check empty vs null values
print("1. EMPTY/NULL VALUE ANALYSIS:")


def check_empty_values(obj, path=""):
    if isinstance(obj, dict):
        for key, value in obj.items():
            if value == "" or value is None or value == {}:
                print(f"  {path}.{key} = {repr(value)}")
            elif isinstance(value, (dict, list)):
                check_empty_values(value, f"{path}.{key}")
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            if isinstance(item, (dict, list)):
                check_empty_values(item, f"{path}[{i}]")


print("\nGenerated file empty/null values:")
check_empty_values(generated)

# 2. Check numeric types
print("\n\n2. NUMERIC TYPE ANALYSIS:")


def analyze_numeric_types(obj, path=""):
    if isinstance(obj, dict):
        for key, value in obj.items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                print(f"  {path}.{key}: {type(value).__name__} = {value}")
            elif isinstance(value, (dict, list)):
                analyze_numeric_types(value, f"{path}.{key}")


print("\nSample numeric values from generated:")
analyze_numeric_types(generated["Assets"]["$values"][0]["Terrain"]["Nodes"]["100"])

# 3. Compare with reference numeric types
if os.path.exists(reference_files[0]):
    with open(reference_files[0], "r") as f:
        ref = json.load(f)
    print("\nSample numeric values from reference:")
    ref_nodes = ref["Assets"]["$values"][0]["Terrain"]["Nodes"]
    for node_id, node in ref_nodes.items():
        if node_id != "$id":
            analyze_numeric_types(node)
            break

# 4. Check Variables object
print("\n\n3. VARIABLES OBJECT CHECK:")
print(f"Generated Variables: {generated['Assets']['$values'][0]['Automation']['Variables']}")
for ref_file in reference_files:
    if os.path.exists(ref_file):
        with open(ref_file, "r") as f:
            ref = json.load(f)
        ref_vars = ref["Assets"]["$values"][0]["Automation"]["Variables"]
        print(f"Reference Variables ({os.path.basename(ref_file)}): {ref_vars}")
        break

# 5. Check Groups and Notes
print("\n\n4. GROUPS AND NOTES CHECK:")
print(f"Generated Groups: {generated['Assets']['$values'][0]['Terrain']['Groups']}")
print(f"Generated Notes: {generated['Assets']['$values'][0]['Terrain']['Notes']}")

# 6. Check for missing or extra keys at each level
print("\n\n5. KEY PRESENCE ANALYSIS:")


def get_all_keys(obj, depth=0, max_depth=3):
    keys = set()
    if depth > max_depth or not isinstance(obj, dict):
        return keys
    for key, value in obj.items():
        keys.add(key)
        if isinstance(value, dict):
            sub_keys = get_all_keys(value, depth + 1, max_depth)
            for sk in sub_keys:
                keys.add(f"{key}.{sk}")
    return keys


gen_keys = get_all_keys(generated)
ref_keys = set()
for ref_file in reference_files[:1]:  # Just check first reference
    if os.path.exists(ref_file):
        with open(ref_file, "r") as f:
            ref = json.load(f)
        ref_keys = get_all_keys(ref)

missing_in_gen = ref_keys - gen_keys
extra_in_gen = gen_keys - ref_keys

if missing_in_gen:
    print("\nKeys in reference but NOT in generated:")
    for key in sorted(missing_in_gen)[:10]:  # First 10
        print(f"  - {key}")

if extra_in_gen:
    print("\nKeys in generated but NOT in reference:")
    for key in sorted(extra_in_gen)[:10]:  # First 10
        print(f"  - {key}")

# 7. Check metadata fields
print("\n\n6. METADATA COMPARISON:")
gen_meta = generated["Assets"]["$values"][0]["Terrain"]["Metadata"]
print("Generated Metadata keys:", list(gen_meta.keys()))
if os.path.exists(reference_files[0]):
    with open(reference_files[0], "r") as f:
        ref = json.load(f)
    ref_meta = ref["Assets"]["$values"][0]["Terrain"]["Metadata"]
    print("Reference Metadata keys:", list(ref_meta.keys()))

    # Check for differences
    for key in ref_meta:
        if key not in gen_meta:
            print(f"  Missing in generated: {key} = {ref_meta[key]}")

# 8. Check boolean value consistency
print("\n\n7. BOOLEAN VALUE CHECK:")


def find_booleans(obj, path=""):
    if isinstance(obj, dict):
        for key, value in obj.items():
            if isinstance(value, bool):
                print(f"  {path}.{key} = {value} (lowercase: {str(value).lower()})")
            elif isinstance(value, (dict, list)):
                find_booleans(value, f"{path}.{key}")


find_booleans(generated)
