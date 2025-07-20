#!/usr/bin/env python3
"""
Summarize key discrepancies between our Gaea2 implementation and reference files
"""

import json
import sys
from typing import Dict


def load_empirical_schema() -> Dict:
    """Load the empirical schema we extracted from references"""
    with open("gaea2_empirical_schema.json", "r") as f:
        return json.load(f)


def analyze_critical_issues() -> None:
    """Identify critical issues we need to fix"""
    schema = load_empirical_schema()

    print("CRITICAL GAEA2 NODE IMPLEMENTATION ISSUES")
    print("=" * 60)

    # 1. Check for Erosion vs Erosion2
    print("\n1. EROSION NODES:")
    print("-" * 40)
    if "Erosion" in schema:
        print(f"❌ Plain 'Erosion' found in {schema['Erosion']['file_count']} files")
    else:
        print("✅ No plain 'Erosion' nodes found (all use Erosion2)")

    if "Erosion2" in schema:
        erosion2 = schema["Erosion2"]
        print(f"✅ Erosion2 found in {erosion2['file_count']} files")
        print("\nValid Erosion2 properties:")
        for prop in sorted(erosion2["properties"].keys()):
            print(f"  - {prop}")

    # 2. Check Rivers properties
    print("\n\n2. RIVERS NODE PROPERTIES:")
    print("-" * 40)
    if "Rivers" in schema:
        rivers = schema["Rivers"]
        print(f"Rivers found in {rivers['file_count']} files")
        print("\nValid Rivers properties:")
        for prop in sorted(rivers["properties"].keys()):
            prop_info = rivers["properties"][prop]
            if "enum" in prop_info:
                print(f"  - {prop}: {prop_info['enum']}")
            else:
                print(f"  - {prop}")

    # 3. Check Mountain properties
    print("\n\n3. MOUNTAIN NODE PROPERTIES:")
    print("-" * 40)
    if "Mountain" in schema:
        mountain = schema["Mountain"]
        print(f"Mountain found in {mountain['file_count']} files")
        print("\nValid Mountain properties:")
        for prop in sorted(mountain["properties"].keys()):
            prop_info = mountain["properties"][prop]
            if prop in ["X", "Y"]:
                print(f"  - {prop} ✅ (Valid at root level!)")
            else:
                print(f"  - {prop}")

    # 4. Check common nodes we might be missing
    print("\n\n4. MOST COMMON NODES IN REFERENCES:")
    print("-" * 40)
    sorted_by_usage = sorted(schema.items(), key=lambda x: x[1]["file_count"], reverse=True)[:15]
    for node_type, data in sorted_by_usage:
        print(f"  {node_type}: {data['file_count']} files")

    # 5. Node-specific issues
    print("\n\n5. SPECIFIC NODE ISSUES TO FIX:")
    print("-" * 40)

    # Check for properties with spaces
    properties_with_spaces = []
    for node_type, node_data in schema.items():
        for prop_name in node_data["properties"].keys():
            if " " in prop_name:
                properties_with_spaces.append((node_type, prop_name))

    if properties_with_spaces:
        print("\n❌ Properties with spaces found:")
        for node_type, prop in properties_with_spaces[:10]:
            print(f"  - {node_type}.{prop}")
    else:
        print("\n✅ No properties with spaces found in references")

    # 6. Port configurations
    print("\n\n6. PORT CONFIGURATIONS:")
    print("-" * 40)

    # Check Rivers ports
    if "Rivers" in schema:
        rivers_ports = schema["Rivers"]["ports"]
        print("Rivers ports:")
        for port_name, port_types in sorted(rivers_ports.items()):
            print(f"  - {port_name}: {port_types}")

    # Check Erosion2 ports
    if "Erosion2" in schema:
        erosion2_ports = schema["Erosion2"]["ports"]
        print("\nErosion2 ports:")
        for port_name, port_types in sorted(erosion2_ports.items()):
            print(f"  - {port_name}: {port_types}")


def generate_fix_recommendations() -> None:
    """Generate specific recommendations for fixes"""
    print("\n\n" + "=" * 60)
    print("RECOMMENDED FIXES")
    print("=" * 60)

    schema = load_empirical_schema()

    print("\n1. NODE TYPE FIXES:")
    print("   - Keep 'Erosion' redirecting to 'Erosion2' ✅ (already fixed)")
    print("   - Ensure all templates use 'Erosion2' not 'Erosion'")

    print("\n2. PROPERTY FIXES:")
    print("   - Mountain nodes: X,Y at root level are VALID (don't remove)")
    print("   - Erosion2: Remove any properties not in this list:")
    erosion2_props = sorted(schema.get("Erosion2", {}).get("properties", {}).keys())
    for prop in erosion2_props[:5]:
        print(f"     • {prop}")
    print("     • ... (see full list above)")

    print("\n3. TEMPLATE FIXES NEEDED:")
    print("   - Review all templates in gaea2_schema.py")
    print("   - Ensure they only use properties found in references")
    print("   - Update property values to match reference ranges")

    print("\n4. COMMON PATTERNS FROM REFERENCES:")
    # Find most common property combinations
    for node_type, node_data in schema.items():
        if node_type in ["Mountain", "Erosion2", "Rivers", "SatMap", "Combine"]:
            print(f"\n   {node_type} common patterns:")
            # Just show the property count
            prop_count = len(node_data["properties"])
            file_count = node_data["file_count"]
            print(f"     - {prop_count} unique properties across {file_count} files")

            # Show if it has special structural properties
            structural = node_data.get("structural", {})
            if structural.get("has_node_size"):
                print(f"     - NodeSize values: {structural.get('node_sizes', [])}")
            if structural.get("has_is_maskable"):
                print(f"     - IsMaskable: {structural.get('is_maskable_values', [])}")


def main():
    try:
        analyze_critical_issues()
        generate_fix_recommendations()
    except FileNotFoundError:
        print("Error: gaea2_empirical_schema.json not found.")
        print("Please run validate_all_gaea_nodes.py first.")
        sys.exit(1)


if __name__ == "__main__":
    main()
