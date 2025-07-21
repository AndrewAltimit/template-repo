import json

# Load and compare character by character
with open("working_project.json", "r") as f:
    working = f.read().strip()

with open("test_truly_minimal.json", "r") as f:
    generated = f.read().strip()

# Find first difference
found_diff = False
for i, (w, g) in enumerate(zip(working, generated)):
    if w != g:
        print(f"First difference at position {i}:")
        print(f"  Working:   ...{working[max(0,i-20):i+20]}...")
        print(f"  Generated: ...{generated[max(0,i-20):i+20]}...")
        print(f"  Difference: {repr(w)} vs {repr(g)}")
        found_diff = True
        break

if not found_diff:
    print("Files are identical up to the shorter length")

print(f"\nLength: Working={len(working)}, Generated={len(generated)} (diff={len(generated)-len(working)})")

# Check if the only differences are in timestamps and IDs
work_json = json.loads(working)
gen_json = json.loads(generated)


# Zero out variable fields
def normalize_json(obj):
    if isinstance(obj, dict):
        for key in ["Id", "DateCreated", "DateLastBuilt", "DateLastSaved"]:
            if key in obj:
                obj[key] = "NORMALIZED"
        for k, v in obj.items():
            normalize_json(v)
    elif isinstance(obj, list):
        for item in obj:
            normalize_json(item)
    return obj


work_norm = normalize_json(json.loads(working))
gen_norm = normalize_json(json.loads(generated))

# Compare normalized
if json.dumps(work_norm, sort_keys=True) == json.dumps(gen_norm, sort_keys=True):
    print("\n✓ Files are IDENTICAL when normalized (only IDs/dates differ)")
else:
    print("\n❌ Files have structural differences beyond IDs/dates")
