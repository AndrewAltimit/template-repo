import copy
import json

# Load files
with open("working_project.json", "r") as f:
    working = json.load(f)

with open("test_minimal_mountain.json", "r") as f:
    generated = json.load(f)


def normalize_for_comparison(obj):
    """Remove all variable fields for comparison"""
    if isinstance(obj, dict):
        # Remove variable fields
        for key in ["Id", "DateCreated", "DateLastBuilt", "DateLastSaved", "Owner"]:
            if key in obj:
                obj[key] = "NORMALIZED"

        # Process all nested objects
        for k, v in list(obj.items()):
            obj[k] = normalize_for_comparison(v)

    elif isinstance(obj, list):
        for i in range(len(obj)):
            obj[i] = normalize_for_comparison(obj[i])

    return obj


# Create deep copies for normalization
work_norm = normalize_for_comparison(copy.deepcopy(working))
gen_norm = normalize_for_comparison(copy.deepcopy(generated))

# Compare as JSON strings
work_str = json.dumps(work_norm, sort_keys=True)
gen_str = json.dumps(gen_norm, sort_keys=True)

if work_str == gen_str:
    print("✅ Files are STRUCTURALLY IDENTICAL (only IDs/dates differ)")
else:
    print("❌ Files have structural differences")

    # Find differences
    work_keys = set(str(work_norm).split())
    gen_keys = set(str(gen_norm).split())

    only_work = work_keys - gen_keys
    only_gen = gen_keys - work_keys

    if only_work:
        print(f"\nOnly in working: {len(only_work)} unique tokens")
        for item in list(only_work)[:5]:
            print(f"  {item}")

    if only_gen:
        print(f"\nOnly in generated: {len(only_gen)} unique tokens")
        for item in list(only_gen)[:5]:
            print(f"  {item}")

# Check specific structural elements
print("\n=== Structural Comparison ===")
print(f"Working project name: {working['Metadata']['Name']}")
print(f"Generated project name: {generated['Metadata']['Name']}")

work_terrain = working["Assets"]["$values"][0]["Terrain"]
gen_terrain = generated["Assets"]["$values"][0]["Terrain"]

print(f"\nWorking nodes: {list(work_terrain['Nodes'].keys())}")
print(f"Generated nodes: {list(gen_terrain['Nodes'].keys())}")

# Check Mountain node structure
work_mountain = work_terrain["Nodes"]["1"]
gen_mountain = gen_terrain["Nodes"]["1"]

print(f"\nMountain node comparison:")
print(f"Working keys: {sorted(work_mountain.keys())}")
print(f"Generated keys: {sorted(gen_mountain.keys())}")

# Check for extra fields
extra_in_gen = set(gen_mountain.keys()) - set(work_mountain.keys())
if extra_in_gen:
    print(f"\nExtra fields in generated: {extra_in_gen}")

missing_in_gen = set(work_mountain.keys()) - set(gen_mountain.keys())
if missing_in_gen:
    print(f"\nMissing fields in generated: {missing_in_gen}")
