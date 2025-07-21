#!/usr/bin/env python3
"""Extract specific test scenarios from Gaea reference projects."""

import json
import os
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple


def load_terrain_file(file_path: Path) -> Dict[str, Any]:
    """Load and parse a terrain file."""
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_node_details(terrain_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract detailed node information including all properties."""
    nodes = []
    terrain = terrain_data["Assets"]["$values"][0]["Terrain"]
    node_dict = terrain.get("Nodes", {})

    for node_id, node_data in node_dict.items():
        if node_id == "$id":
            continue

        node_type = node_data.get("$type", "").split(".")[-2] if "$type" in node_data else "Unknown"

        # Extract all non-standard properties
        properties = {}
        standard_keys = {
            "$id",
            "$type",
            "Id",
            "Name",
            "Position",
            "Ports",
            "Modifiers",
            "SnapIns",
        }

        for key, value in node_data.items():
            if key not in standard_keys:
                properties[key] = value

        # Extract port information
        ports = []
        for port in node_data.get("Ports", {}).get("$values", []):
            port_info = {"name": port.get("Name"), "type": port.get("Type")}
            if "Record" in port and port["Record"]:
                port_info["connection"] = port["Record"]
            ports.append(port_info)

        nodes.append(
            {
                "id": node_id,
                "type": node_type,
                "name": node_data.get("Name", "Unnamed"),
                "properties": properties,
                "ports": ports,
            }
        )

    return nodes


def find_test_scenarios(ref_dir: Path):
    """Find specific test scenarios from reference files."""
    terrain_files = sorted(ref_dir.glob("*.terrain"))

    scenarios = {
        "basic_workflows": [],
        "complex_chains": [],
        "multi_input_nodes": [],
        "special_properties": [],
        "port_variations": [],
        "automation_examples": [],
        "unique_configurations": [],
    }

    # Track unique property combinations
    property_combinations = defaultdict(list)

    for terrain_file in terrain_files:
        data = load_terrain_file(terrain_file)
        nodes = extract_node_details(data)
        terrain = data["Assets"]["$values"][0]["Terrain"]

        # 1. Basic workflow patterns (simple chains)
        if len(nodes) <= 5:
            scenarios["basic_workflows"].append(
                {
                    "file": terrain_file.name,
                    "workflow": " -> ".join([n["type"] for n in nodes[:5]]),
                }
            )

        # 2. Complex chains (long connection sequences)
        connection_chains = []
        for node in nodes:
            for port in node["ports"]:
                if "connection" in port:
                    conn = port["connection"]
                    from_node = next((n for n in nodes if n["id"] == str(conn["From"])), None)
                    to_node = next((n for n in nodes if n["id"] == str(conn["To"])), None)
                    if from_node and to_node:
                        connection_chains.append((from_node["type"], to_node["type"]))

        if len(connection_chains) > 15:
            scenarios["complex_chains"].append(
                {
                    "file": terrain_file.name,
                    "chain_count": len(connection_chains),
                    "unique_patterns": len(set(connection_chains)),
                }
            )

        # 3. Multi-input nodes (Combine with multiple inputs)
        for node in nodes:
            if node["type"] == "Combine, Gaea":
                input_ports = [p for p in node["ports"] if "connection" in p and p["name"] in ["In", "Input2", "Mask"]]
                if len(input_ports) >= 3:
                    scenarios["multi_input_nodes"].append(
                        {
                            "file": terrain_file.name,
                            "node": node["name"],
                            "inputs": [(p["name"], p["connection"]["FromPort"]) for p in input_ports],
                        }
                    )

        # 4. Special properties (unusual or complex property values)
        for node in nodes:
            special_props = {}
            for prop, value in node["properties"].items():
                # Look for complex values
                if isinstance(value, dict) and "$id" in value:
                    special_props[prop] = "Complex object"
                elif isinstance(value, (int, float)) and value not in [0, 1, 0.5]:
                    special_props[prop] = value
                elif prop in ["SaveDefinition", "RenderIntentOverride", "IsLocked"]:
                    special_props[prop] = value

            if special_props:
                scenarios["special_properties"].append(
                    {
                        "file": terrain_file.name,
                        "node": f"{node['type']} ({node['name']})",
                        "properties": special_props,
                    }
                )

        # 5. Port variations (nodes with multiple output ports)
        for node in nodes:
            output_ports = [p for p in node["ports"] if p.get("type") and "Out" in p.get("type", "")]
            if len(output_ports) > 1:
                scenarios["port_variations"].append(
                    {
                        "file": terrain_file.name,
                        "node": f"{node['type']} ({node['name']})",
                        "output_ports": [p["name"] for p in output_ports],
                    }
                )

        # 6. Automation (variables and bindings)
        automation = terrain.get("Automation", {})
        if automation.get("Variables") or automation.get("Bindings", {}).get("$values"):
            scenarios["automation_examples"].append(
                {
                    "file": terrain_file.name,
                    "variables": automation.get("Variables", {}),
                    "bindings": len(automation.get("Bindings", {}).get("$values", [])),
                }
            )

        # 7. Track unique property combinations
        for node in nodes:
            if node["properties"]:
                prop_key = f"{node['type']}:{','.join(sorted(node['properties'].keys()))}"
                property_combinations[prop_key].append(
                    {
                        "file": terrain_file.name,
                        "node": node["name"],
                        "values": node["properties"],
                    }
                )

    # Find unique configurations
    for prop_key, examples in property_combinations.items():
        if len(examples) == 1:  # Unique to one file
            scenarios["unique_configurations"].append(examples[0])

    # Print scenarios
    print("TEST SCENARIOS FROM GAEA REFERENCE PROJECTS")
    print("=" * 60)

    print("\n1. BASIC WORKFLOW PATTERNS:")
    for scenario in scenarios["basic_workflows"][:3]:
        print(f"   {scenario['file']}: {scenario['workflow']}")

    print("\n2. COMPLEX CHAINS (>15 connections):")
    for scenario in scenarios["complex_chains"]:
        print(f"   {scenario['file']}: {scenario['chain_count']} connections, {scenario['unique_patterns']} unique patterns")

    print("\n3. MULTI-INPUT COMBINE NODES:")
    for scenario in scenarios["multi_input_nodes"][:5]:
        print(f"   {scenario['file']}: {scenario['node']}")
        for port_name, from_port in scenario["inputs"]:
            print(f"      - {port_name} <- {from_port}")

    print("\n4. NODES WITH SPECIAL PROPERTIES:")
    special_by_type = defaultdict(list)
    for scenario in scenarios["special_properties"]:
        special_by_type[scenario["node"].split(" ")[0]].append(scenario)

    for node_type, examples in list(special_by_type.items())[:10]:
        print(f"\n   {node_type}:")
        for example in examples[:2]:
            print(f"      {example['file']}: {list(example['properties'].keys())}")

    print("\n5. NODES WITH MULTIPLE OUTPUT PORTS:")
    port_by_type = defaultdict(set)
    for scenario in scenarios["port_variations"]:
        node_type = scenario["node"].split(" ")[0]
        for port in scenario["output_ports"]:
            port_by_type[node_type].add(port)

    for node_type, ports in sorted(port_by_type.items()):
        print(f"   {node_type}: {sorted(ports)}")

    print("\n6. AUTOMATION EXAMPLES:")
    for scenario in scenarios["automation_examples"]:
        print(f"   {scenario['file']}: {len(scenario['variables'])} variables, {scenario['bindings']} bindings")
        if scenario["variables"]:
            for var, val in list(scenario["variables"].items())[:3]:
                print(f"      - {var} = {val}")

    print("\n7. UNIQUE NODE CONFIGURATIONS:")
    unique_count = 0
    for scenario in scenarios["unique_configurations"][:10]:
        node_type = scenario["file"].split(":")[0] if ":" in scenario["file"] else "Unknown"
        print(f"   {scenario['file']} - {scenario['node']}: {list(scenario['values'].keys())[:5]}")
        unique_count += 1

    if len(scenarios["unique_configurations"]) > 10:
        print(f"   ... and {len(scenarios['unique_configurations']) - 10} more unique configurations")

    # Create test recommendations
    print("\n\nRECOMMENDED TEST CASES:")
    print("=" * 60)

    print("\n1. Node Connection Tests:")
    print("   - Rivers -> Adjust (Rivers port -> In port)")
    print("   - TextureBase -> Multiple SatMaps")
    print("   - Height -> Combine (as Mask)")
    print("   - Sea -> Combine (Water port -> Mask)")

    print("\n2. Property Value Tests:")
    print("   - Range objects (e.g., Height node)")
    print("   - Seed propagation through Variables")
    print("   - SaveDefinition on export nodes")
    print("   - NodeSize variations (Small, Standard)")

    print("\n3. Complex Workflow Tests:")
    print("   - Slump -> FractalTerraces -> Combine -> Shear -> Crumble -> Erosion2")
    print("   - Parallel paths merging in Combine nodes")
    print("   - Multiple masks applied to single node")

    print("\n4. Edge Cases:")
    print("   - Nodes with no input connections (generators)")
    print("   - Multiple Combine nodes chained together")
    print("   - Nodes with both standard and special output ports")


if __name__ == "__main__":
    ref_dir = Path("/home/miku/Documents/repos/template-repo/gaea-references")
    find_test_scenarios(ref_dir)
