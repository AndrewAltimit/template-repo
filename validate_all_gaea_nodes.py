#!/usr/bin/env python3
"""
Comprehensive validation of all Gaea2 nodes against reference projects.
This tool will ensure our implementation matches exactly what Gaea2 expects.
"""

import json
import os
import sys
from collections import defaultdict
from typing import Any, Dict


class Gaea2NodeValidator:
    def __init__(self):
        self.reference_data = defaultdict(
            lambda: {
                "files": set(),
                "type_strings": set(),
                "properties": defaultdict(lambda: {"values": [], "types": set(), "files": set()}),
                "property_combinations": [],
                "ports": defaultdict(lambda: {"types": set(), "files": set()}),
                "structural_info": {
                    "has_node_size": False,
                    "node_sizes": set(),
                    "has_is_maskable": False,
                    "is_maskable_values": set(),
                    "has_save_definition": False,
                    "has_port_count": False,
                    "port_counts": set(),
                },
            }
        )

    def analyze_reference_projects(self) -> None:
        """Scan all reference projects and extract node information"""
        ref_dirs = ["reference projects/mikus files", "reference projects/Official Gaea Projects"]

        total_files = 0
        for ref_dir in ref_dirs:
            if os.path.exists(ref_dir):
                for root, dirs, files in os.walk(ref_dir):
                    for file in files:
                        if file.endswith(".terrain"):
                            path = os.path.join(root, file)
                            total_files += 1
                            self._analyze_terrain_file(path, file)

        print(f"Analyzed {total_files} terrain files")

    def _analyze_terrain_file(self, path: str, filename: str) -> None:
        """Analyze a single terrain file"""
        try:
            with open(path, "r") as f:
                data = json.load(f)

            terrain = data.get("Assets", {}).get("$values", [{}])[0].get("Terrain", {})
            nodes = terrain.get("Nodes", {})

            for node_id, node in nodes.items():
                if isinstance(node, dict) and "$type" in node:
                    self._analyze_node(node, filename)

        except Exception as e:
            print(f"Error analyzing {filename}: {e}")

    def _analyze_node(self, node: Dict, filename: str) -> None:
        """Analyze a single node"""
        type_string = node["$type"]
        # Extract clean node type (e.g., "Mountain" from "QuadSpinner.Gaea.Nodes.Mountain, Gaea.Nodes")
        if "Nodes." in type_string:
            # Split by "Nodes." and take what's after it
            after_nodes = type_string.split("Nodes.")[1]
            # Remove ", Gaea.Nodes" suffix
            node_type = after_nodes.split(",")[0].strip()
        else:
            node_type = type_string

        # Track basic info
        self.reference_data[node_type]["files"].add(filename)
        self.reference_data[node_type]["type_strings"].add(type_string)

        # Structural properties we expect
        structural_props = {
            "$id",
            "$type",
            "Id",
            "Name",
            "Position",
            "Ports",
            "Modifiers",
            "SnapIns",
            "NodeSize",
            "IsMaskable",
            "SaveDefinition",
            "PortCount",
        }

        # Track properties
        node_props = []
        for key, value in node.items():
            if key in structural_props:
                self._track_structural_property(node_type, key, value, filename)
            else:
                # This is a node-specific property
                node_props.append(key)
                self._track_property(node_type, key, value, filename)

        # Track property combinations
        self.reference_data[node_type]["property_combinations"].append({"file": filename, "props": sorted(node_props)})

        # Analyze ports
        if "Ports" in node and isinstance(node["Ports"], dict):
            ports = node["Ports"].get("$values", [])
            for port in ports:
                if isinstance(port, dict) and "Name" in port:
                    port_name = port["Name"]
                    port_type = port.get("Type", "Unknown")
                    self.reference_data[node_type]["ports"][port_name]["types"].add(port_type)
                    self.reference_data[node_type]["ports"][port_name]["files"].add(filename)

    def _track_structural_property(self, node_type: str, key: str, value: Any, filename: str) -> None:
        """Track structural properties"""
        info = self.reference_data[node_type]["structural_info"]

        if key == "NodeSize":
            info["has_node_size"] = True
            info["node_sizes"].add(value)
        elif key == "IsMaskable":
            info["has_is_maskable"] = True
            info["is_maskable_values"].add(value)
        elif key == "SaveDefinition":
            info["has_save_definition"] = True
        elif key == "PortCount":
            info["has_port_count"] = True
            info["port_counts"].add(value)

    def _track_property(self, node_type: str, key: str, value: Any, filename: str) -> None:
        """Track node-specific properties"""
        prop_data = self.reference_data[node_type]["properties"][key]
        prop_data["values"].append(value)
        prop_data["types"].add(type(value).__name__)
        prop_data["files"].add(filename)

    def compare_with_implementation(self) -> Dict[str, Any]:
        """Compare reference data with our implementation"""
        # Load our current definitions
        sys.path.insert(0, "tools/mcp")
        try:
            from gaea2_mcp_server import Gaea2MCPServer
            from gaea2_schema import NODE_PROPERTIES
        except ImportError as e:
            print(f"Error importing implementation: {e}")
            return {}

        issues = {
            "missing_nodes": [],
            "extra_nodes": [],
            "property_mismatches": defaultdict(list),
            "port_mismatches": defaultdict(list),
            "type_string_mismatches": defaultdict(str),
        }

        # Get node type mappings from server
        server = Gaea2MCPServer()
        node_type_map = server._get_node_type_mapping()

        # Check each reference node
        for ref_node_type, ref_data in self.reference_data.items():
            clean_type = ref_node_type  # Already cleaned in _analyze_node

            # Check if we support this node
            if clean_type not in node_type_map:
                issues["missing_nodes"].append(
                    {
                        "type": clean_type,
                        "full_type": ref_node_type,
                        "files": len(ref_data["files"]),
                        "type_strings": list(ref_data["type_strings"]),
                    }
                )
                continue

            # Check type string
            our_type_string = node_type_map[clean_type]
            ref_type_strings = ref_data["type_strings"]
            if our_type_string not in ref_type_strings:
                issues["type_string_mismatches"][clean_type] = {"ours": our_type_string, "reference": list(ref_type_strings)}

            # Check properties
            if clean_type in NODE_PROPERTIES:
                our_props = set(NODE_PROPERTIES[clean_type].keys())
                ref_props = set(ref_data["properties"].keys())

                # Properties we define but never seen in references
                extra_props = our_props - ref_props
                if extra_props:
                    issues["property_mismatches"][clean_type].append(
                        {"issue": "extra_properties", "properties": list(extra_props)}
                    )

                # Properties in references we don't define
                missing_props = ref_props - our_props
                if missing_props:
                    # Filter out common ones like X, Y which might be okay
                    significant_missing = [p for p in missing_props if p not in ["X", "Y"]]
                    if significant_missing:
                        issues["property_mismatches"][clean_type].append(
                            {
                                "issue": "missing_properties",
                                "properties": significant_missing,
                                "examples": {p: list(ref_data["properties"][p]["files"])[:2] for p in significant_missing},
                            }
                        )

        # Check for nodes we define but never appear in references
        for our_node in node_type_map.keys():
            ref_match = None
            for ref_type in self.reference_data.keys():
                if ref_type.startswith(our_node):
                    ref_match = ref_type
                    break

            if not ref_match:
                issues["extra_nodes"].append(our_node)

        return issues

    def generate_report(self) -> None:
        """Generate comprehensive validation report"""
        print("\n" + "=" * 80)
        print("GAEA2 NODE VALIDATION REPORT")
        print("=" * 80)

        # Summary statistics
        print(f"\nTotal node types found in references: {len(self.reference_data)}")

        # Most common nodes
        print("\nMost common node types:")
        sorted_by_usage = sorted(self.reference_data.items(), key=lambda x: len(x[1]["files"]), reverse=True)[:15]

        for node_type, data in sorted_by_usage:
            print(f"  {node_type}: {len(data['files'])} files")

        # Detailed analysis of each node
        print("\n" + "=" * 80)
        print("DETAILED NODE ANALYSIS")
        print("=" * 80)

        for node_type, data in sorted(self.reference_data.items()):
            print(f"\n{'='*60}")
            print(f"NODE: {node_type}")
            print(f"{'='*60}")

            print(f"Files: {len(data['files'])}")
            print(f"Type strings: {list(data['type_strings'])}")

            # Structural info
            info = data["structural_info"]
            if info["has_node_size"]:
                print(f"NodeSize values: {sorted(info['node_sizes'])}")
            if info["has_is_maskable"]:
                print(f"IsMaskable values: {sorted(info['is_maskable_values'])}")
            if info["has_save_definition"]:
                print("Has SaveDefinition: Yes")
            if info["has_port_count"]:
                print(f"PortCount values: {sorted(info['port_counts'])}")

            # Properties
            if data["properties"]:
                print("\nProperties:")
                for prop_name, prop_data in sorted(data["properties"].items()):
                    types = sorted(prop_data["types"])
                    file_count = len(prop_data["files"])
                    print(f"  - {prop_name} ({', '.join(types)}) [{file_count} files]")

                    # Show sample values for interesting properties
                    try:
                        # Handle different value types
                        if all(isinstance(v, (int, float, str, bool)) for v in prop_data["values"]):
                            unique_values = set(str(v) for v in prop_data["values"])
                            if len(unique_values) <= 5:
                                print(f"    Values: {sorted(unique_values)}")
                    except Exception:
                        pass

            # Property combinations
            combo_counts = defaultdict(int)
            for combo in data["property_combinations"]:
                combo_key = tuple(combo["props"])
                combo_counts[combo_key] += 1

            if combo_counts:
                print("\nCommon property combinations:")
                for combo, count in sorted(combo_counts.items(), key=lambda x: x[1], reverse=True)[:3]:
                    if combo:  # Skip empty combinations
                        print(f"  {count}x: {list(combo)}")

            # Ports
            if data["ports"]:
                print("\nPorts:")
                for port_name, port_data in sorted(data["ports"].items()):
                    types = sorted(port_data["types"])
                    print(f"  - {port_name}: {types}")

    def save_empirical_schema(self) -> None:
        """Save the empirical schema extracted from references"""
        output = {}

        for node_type, data in self.reference_data.items():
            clean_type = node_type  # Already cleaned

            # Build property schema
            properties = {}
            for prop_name, prop_data in data["properties"].items():
                # Determine type from values
                types = prop_data["types"]
                values = prop_data["values"]

                prop_schema = {"types": list(types), "file_count": len(prop_data["files"])}

                # Add value constraints if applicable
                if "int" in types or "float" in types:
                    numeric_values = [v for v in values if isinstance(v, (int, float))]
                    if numeric_values:
                        prop_schema["min"] = min(numeric_values)
                        prop_schema["max"] = max(numeric_values)

                if "str" in types:
                    str_values = [v for v in values if isinstance(v, str)]
                    unique_strs = set(str_values)
                    if len(unique_strs) <= 10:
                        prop_schema["enum"] = sorted(unique_strs)

                properties[prop_name] = prop_schema

            output[clean_type] = {
                "type_string": list(data["type_strings"])[0] if data["type_strings"] else "",
                "file_count": len(data["files"]),
                "properties": properties,
                "ports": {port_name: list(port_data["types"]) for port_name, port_data in data["ports"].items()},
                "structural": {k: list(v) if isinstance(v, set) else v for k, v in data["structural_info"].items()},
            }

        with open("gaea2_empirical_schema.json", "w") as f:
            json.dump(output, f, indent=2, sort_keys=True)

        print("\nEmpirical schema saved to gaea2_empirical_schema.json")


def main():
    validator = Gaea2NodeValidator()

    print("Analyzing reference projects...")
    validator.analyze_reference_projects()

    print("\nGenerating validation report...")
    validator.generate_report()

    print("\nComparing with implementation...")
    issues = validator.compare_with_implementation()

    if issues:
        print("\n" + "=" * 80)
        print("IMPLEMENTATION ISSUES FOUND")
        print("=" * 80)

        if issues["missing_nodes"]:
            print(f"\nMissing {len(issues['missing_nodes'])} node types:")
            for node in issues["missing_nodes"][:10]:
                print(f"  - {node['type']} (used in {node['files']} files)")
                print(f"    Type: {node['type_strings'][0]}")

        if issues["extra_nodes"]:
            print(f"\nExtra nodes we define but not in references: {issues['extra_nodes']}")

        if issues["property_mismatches"]:
            print(f"\nProperty mismatches in {len(issues['property_mismatches'])} nodes:")
            for node_type, mismatches in list(issues["property_mismatches"].items())[:5]:
                print(f"\n  {node_type}:")
                for mismatch in mismatches:
                    print(f"    {mismatch['issue']}: {mismatch['properties']}")

        if issues["type_string_mismatches"]:
            print("\nType string mismatches:")
            for node_type, mismatch in list(issues["type_string_mismatches"].items())[:5]:
                print(f"  {node_type}:")
                print(f"    Ours: {mismatch['ours']}")
                print(f"    Ref:  {mismatch['reference'][0]}")

    print("\nSaving empirical schema...")
    validator.save_empirical_schema()

    print("\nValidation complete!")


if __name__ == "__main__":
    main()
