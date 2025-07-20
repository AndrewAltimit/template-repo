#!/usr/bin/env python3
"""Comprehensive deep dive analysis of failing terrain file"""

import json
import os
from typing import Dict, List, Set, Any


def load_reference_files() -> Dict[str, Dict]:
    """Load all reference terrain files"""
    references = {}
    ref_dirs = [
        "reference projects/mikus files",
        "reference projects/Official Gaea Projects"
    ]
    
    for ref_dir in ref_dirs:
        if os.path.exists(ref_dir):
            for root, dirs, files in os.walk(ref_dir):
                for file in files:
                    if file.endswith(".terrain"):
                        path = os.path.join(root, file)
                        try:
                            with open(path, 'r') as f:
                                references[file] = json.load(f)
                        except:
                            pass
    
    return references


def analyze_id_references(data: Dict) -> None:
    """Analyze $id and $ref patterns"""
    print("\n=== ID REFERENCE ANALYSIS ===")
    
    ids_found = set()
    refs_found = set()
    
    def collect_ids_refs(obj, path=""):
        if isinstance(obj, dict):
            if "$id" in obj:
                ids_found.add(obj["$id"])
            if "$ref" in obj:
                refs_found.add(obj["$ref"])
            for key, value in obj.items():
                collect_ids_refs(value, f"{path}.{key}")
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                collect_ids_refs(item, f"{path}[{i}]")
    
    collect_ids_refs(data)
    
    print(f"\nTotal $id values: {len(ids_found)}")
    print(f"Total $ref values: {len(refs_found)}")
    
    # Check for missing references
    missing_refs = refs_found - ids_found
    if missing_refs:
        print(f"\n❌ Missing $id for these $ref values: {missing_refs}")
    
    # Check for duplicate IDs
    id_list = []
    def collect_id_list(obj):
        if isinstance(obj, dict):
            if "$id" in obj:
                id_list.append(obj["$id"])
            for value in obj.values():
                collect_id_list(value)
        elif isinstance(obj, list):
            for item in obj:
                collect_id_list(item)
    
    collect_id_list(data)
    duplicates = [x for x in id_list if id_list.count(x) > 1]
    if duplicates:
        print(f"\n❌ Duplicate $id values found: {set(duplicates)}")


def analyze_node_structure(failing_data: Dict, references: Dict) -> None:
    """Compare node structure with references"""
    print("\n=== NODE STRUCTURE ANALYSIS ===")
    
    # Get Level1.terrain as reference
    level1 = None
    for filename, data in references.items():
        if filename == "Level1.terrain":
            level1 = data
            break
    
    if not level1:
        print("❌ Could not find Level1.terrain for comparison")
        return
    
    # Compare node property order
    print("\nNode property order comparison:")
    
    failing_nodes = failing_data["Assets"]["$values"][0]["Terrain"]["Nodes"]
    ref_nodes = level1["Assets"]["$values"][0]["Terrain"]["Nodes"]
    
    # Find first node of each type
    node_types = ["Mountain", "Erosion2", "Rivers", "Export"]
    
    for node_type in node_types:
        failing_node = None
        ref_node = None
        
        # Find in failing
        for node_id, node in failing_nodes.items():
            if isinstance(node, dict) and node_type in node.get("$type", ""):
                failing_node = node
                break
        
        # Find in reference
        for node_id, node in ref_nodes.items():
            if isinstance(node, dict) and node_type in node.get("$type", ""):
                ref_node = node
                break
        
        if failing_node and ref_node:
            print(f"\n{node_type} property order:")
            failing_keys = list(failing_node.keys())[:15]
            ref_keys = list(ref_node.keys())[:15]
            
            print("  Failing file      | Reference file")
            print("  " + "-" * 40)
            for i in range(max(len(failing_keys), len(ref_keys))):
                fail_key = failing_keys[i] if i < len(failing_keys) else "---"
                ref_key = ref_keys[i] if i < len(ref_keys) else "---"
                match = "✓" if fail_key == ref_key else "✗"
                print(f"  {fail_key:<17} | {ref_key:<17} {match}")


def analyze_empty_objects(data: Dict) -> None:
    """Check for empty objects that should have structure"""
    print("\n=== EMPTY OBJECT ANALYSIS ===")
    
    empty_objects = []
    
    def find_empty(obj, path=""):
        if isinstance(obj, dict):
            if len(obj) == 0:
                empty_objects.append(path)
            for key, value in obj.items():
                find_empty(value, f"{path}.{key}")
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                find_empty(item, f"{path}[{i}]")
    
    find_empty(data)
    
    if empty_objects:
        print("\nEmpty objects found at:")
        for path in empty_objects:
            print(f"  - {path}")
            
            # Check what reference files have at these paths
            if "Groups" in path:
                print("    → Should have: {\"$id\": \"XX\", \"$values\": []}")
            elif "Notes" in path:
                print("    → Should have: {\"$id\": \"XX\", \"$values\": []}")
            elif "Variables" in path:
                print("    → Should have: {\"$id\": \"XX\"}")


def analyze_specific_issues(failing_data: Dict) -> None:
    """Check for specific known issues"""
    print("\n=== SPECIFIC ISSUE CHECKS ===")
    
    issues = []
    
    # Check 1: Groups and Notes objects
    terrain = failing_data["Assets"]["$values"][0]["Terrain"]
    if "Groups" in terrain and terrain["Groups"] == {}:
        issues.append("Groups is empty {} instead of {\"$id\": \"XX\"}")
    if "Notes" in terrain and terrain["Notes"] == {}:
        issues.append("Notes is empty {} instead of {\"$id\": \"XX\"}")
    
    # Check 2: Variables object
    automation = failing_data["Assets"]["$values"][0]["Automation"]
    if "Variables" in automation and automation["Variables"] == {}:
        issues.append("Variables is empty {} instead of {\"$id\": \"XX\"}")
    
    # Check 3: Missing Camera properties
    viewport = failing_data["Assets"]["$values"][0]["State"]["Viewport"]
    if "Camera" in viewport and viewport["Camera"] == {"$id": "74"}:
        issues.append("Camera object might be missing properties")
    
    # Check 4: BuildDefinition.Destination format
    build_def = failing_data["Assets"]["$values"][0]["BuildDefinition"]
    if "Destination" in build_def:
        dest = build_def["Destination"]
        if "\\" in dest:
            print(f"\n  Destination path uses backslashes: {dest}")
            print("  → This is normal for Windows paths")
    
    if issues:
        print("\n❌ Issues found:")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("\n✓ No specific issues found")


def compare_with_working_file(failing_data: Dict, references: Dict) -> None:
    """Compare with a known working file in detail"""
    print("\n=== DETAILED COMPARISON WITH WORKING FILE ===")
    
    # Pick a simple working file
    working_file = None
    for filename, data in references.items():
        if "Level1.terrain" in filename:
            working_file = data
            break
    
    if not working_file:
        return
    
    # Compare top-level structure
    def get_structure_keys(obj, depth=0, max_depth=3):
        if depth > max_depth or not isinstance(obj, dict):
            return {}
        
        result = {}
        for key, value in obj.items():
            if isinstance(value, dict):
                result[key] = get_structure_keys(value, depth + 1, max_depth)
            elif isinstance(value, list):
                result[key] = f"[{len(value)} items]"
            else:
                result[key] = type(value).__name__
        return result
    
    print("\nTop-level structure comparison:")
    fail_struct = get_structure_keys(failing_data)
    work_struct = get_structure_keys(working_file)
    
    import json
    print("\nFailing file structure:")
    print(json.dumps(fail_struct, indent=2)[:500] + "...")
    
    print("\nWorking file structure:")
    print(json.dumps(work_struct, indent=2)[:500] + "...")


def check_node_connections(data: Dict) -> None:
    """Verify all node connections are valid"""
    print("\n=== NODE CONNECTION VALIDATION ===")
    
    nodes = data["Assets"]["$values"][0]["Terrain"]["Nodes"]
    
    # Collect all node IDs
    node_ids = set()
    for node_id, node in nodes.items():
        if isinstance(node, dict):
            node_ids.add(int(node_id))
    
    print(f"\nNode IDs found: {sorted(node_ids)}")
    
    # Check all connections
    invalid_connections = []
    for node_id, node in nodes.items():
        if isinstance(node, dict) and "Ports" in node:
            for port in node["Ports"]["$values"]:
                if "Record" in port:
                    record = port["Record"]
                    from_id = record.get("From")
                    to_id = record.get("To")
                    
                    if from_id not in node_ids:
                        invalid_connections.append(f"Node {node_id}: Invalid From ID {from_id}")
                    if to_id not in node_ids:
                        invalid_connections.append(f"Node {node_id}: Invalid To ID {to_id}")
    
    if invalid_connections:
        print("\n❌ Invalid connections found:")
        for conn in invalid_connections:
            print(f"  - {conn}")
    else:
        print("\n✓ All connections are valid")


def main():
    print("COMPREHENSIVE DEEP DIVE ANALYSIS")
    print("=" * 60)
    
    # Load failing file
    with open("failing_terrain_new.json", "r") as f:
        failing_data = json.load(f)
    
    # Load reference files
    references = load_reference_files()
    print(f"Loaded {len(references)} reference files")
    
    # Run all analyses
    analyze_id_references(failing_data)
    analyze_node_structure(failing_data, references)
    analyze_empty_objects(failing_data)
    analyze_specific_issues(failing_data)
    compare_with_working_file(failing_data, references)
    check_node_connections(failing_data)
    
    print("\n" + "=" * 60)
    print("ANALYSIS COMPLETE")


if __name__ == "__main__":
    main()