#!/usr/bin/env python3
"""Compare failing terrain structure with reference Level1.terrain"""

import json


def load_json_from_compact(json_str):
    """Load JSON from compact string"""
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        print(f"JSON decode error: {e}")
        # Find the position
        pos = e.pos
        start = max(0, pos - 50)
        end = min(len(json_str), pos + 50)
        print(f"Around position {pos}:")
        print(json_str[start:end])
        print(" " * (pos - start) + "^")
        return None


def analyze_differences():
    """Analyze structural differences between our file and reference"""

    # Load reference file
    with open("reference projects/mikus files/Level1.terrain", "r") as f:
        ref_content = f.read()
        reference = json.loads(ref_content)

    # Load our failing file
    with open("failing_terrain.json", "r") as f:
        failing_content = f.read()

    print("Checking for JSON issues in our file...")
    our_file = load_json_from_compact(failing_content)

    if not our_file:
        return

    print("\n=== STRUCTURAL COMPARISON ===\n")

    # 1. Check top-level structure
    print("1. Top-level keys:")
    ref_keys = set(reference.keys())
    our_keys = set(our_file.keys())

    print(f"   Reference: {sorted(ref_keys)}")
    print(f"   Ours:      {sorted(our_keys)}")

    missing = ref_keys - our_keys
    extra = our_keys - ref_keys
    if missing:
        print(f"   ❌ Missing: {missing}")
    if extra:
        print(f"   ❌ Extra: {extra}")

    # 2. Check Rivers node differences
    print("\n2. Rivers Node Comparison:")

    # Find Rivers in reference
    ref_nodes = reference["Assets"]["$values"][0]["Terrain"]["Nodes"]
    ref_rivers = None
    for node_id, node in ref_nodes.items():
        if isinstance(node, dict) and "Rivers" in node.get("$type", ""):
            ref_rivers = node
            print(f"   Reference Rivers node ID: {node_id}")
            break

    # Find Rivers in ours
    our_nodes = our_file["Assets"]["$values"][0]["Terrain"]["Nodes"]
    our_rivers = None
    for node_id, node in our_nodes.items():
        if isinstance(node, dict) and "Rivers" in node.get("$type", ""):
            our_rivers = node
            print(f"   Our Rivers node ID: {node_id}")
            break

    if ref_rivers and our_rivers:
        # Compare properties at node level
        print("\n   Property order comparison:")
        ref_props = list(ref_rivers.keys())
        our_props = list(our_rivers.keys())

        print("   Reference order:")
        for i, prop in enumerate(ref_props[:15]):  # First 15 properties
            print(f"     {i+1}. {prop}")

        print("\n   Our order:")
        for i, prop in enumerate(our_props[:15]):
            print(f"     {i+1}. {prop}")

    # 3. Check specific issues
    print("\n3. Specific Issues:")

    # Check Mask port type
    if our_rivers:
        ports = our_rivers.get("Ports", {}).get("$values", [])
        for port in ports:
            if port.get("Name") == "Mask":
                print(f"   Mask port type: '{port.get('Type')}' (should be 'In', not 'Out')")

    # 4. Check property placement in Rivers
    if our_rivers:
        print("\n4. Rivers Node Properties:")

        # Properties that should come BEFORE standard fields
        prop_order = []
        for key in our_rivers:
            if key not in ["$id", "$type", "Id", "Name", "Position", "Ports", "Modifiers", "SnapIns"]:
                prop_order.append(key)

        print(f"   Properties before standard fields: {prop_order}")

        # In reference, are properties before or after Id/Name/Position?
        if ref_rivers:
            ref_prop_order = []
            found_id = False
            for key in ref_rivers:
                if key == "Id":
                    found_id = True
                if not found_id and key not in ["$id", "$type"]:
                    ref_prop_order.append(key)

            print(f"   Reference properties before Id: {ref_prop_order}")


def check_port_issues():
    """Check for specific port-related issues"""
    with open("failing_terrain.json", "r") as f:
        content = f.read()

    # Check for Mask port issues
    if '"Name":"Mask","Type":"Out"' in content:
        print("\n❌ ISSUE FOUND: Mask port has Type='Out' but should be Type='In'")


def main():
    print("Deep Dive: Comparing Failing Terrain with Reference Level1.terrain")
    print("=" * 70)

    analyze_differences()
    check_port_issues()

    print("\n" + "=" * 70)
    print("Key areas to investigate:")
    print("- Property order in nodes")
    print("- Port types (especially Mask ports)")
    print("- Any structural differences")


if __name__ == "__main__":
    main()
