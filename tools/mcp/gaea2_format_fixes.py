"""Gaea2 Format Fixes - Corrections for proper terrain file generation"""

import random
from typing import Any, Dict, List, Optional, Tuple

# Property name mapping: Python-friendly names to Gaea2 exact names
PROPERTY_NAME_MAPPING = {
    # Common property mappings
    "rockSoftness": "Rock Softness",
    "RockSoftness": "Rock Softness",  # Also handle camelCase variant
    "snowLine": "Snow Line",
    "settleDuration": "Settle Duration",
    "meltType": "Melt Type",
    "meltRemnants": "Melt Remnants",
    "slipOffAngle": "Slip-off angle",
    "realScale": "Real Scale",
    "erosionScale": "Erosion Scale",
    "baseLevel": "Base Level",
    "BaseLevel": "Base Level",  # Handle both cases
    "colorProduction": "Color Production",
    "reduceDetails": "ReduceDetails",
    # Keep exact names that are already correct
    "Scale": "Scale",
    "Height": "Height",
    "Seed": "Seed",
    "Duration": "Duration",
    "Downcutting": "Downcutting",
    "Strength": "Strength",
    "Detail": "Detail",
    "Iterations": "Iterations",
    "Library": "Library",
    "Enhance": "Enhance",
    "Style": "Style",
    "Format": "Format",
}

# Node types that should have specific additional properties
NODE_PROPERTIES = {
    "Combine": {
        "PortCount": 2,
        "NodeSize": "Small",
        "IsMaskable": True,
    },
    "Adjust": {
        "NodeSize": "Small",
        "IsMaskable": True,
    },
    "Rivers": {
        "NodeSize": "Standard",
        "IsMaskable": True,
    },
    "Export": {
        "NodeSize": "Standard",
    },
    "SatMap": {
        "NodeSize": "Standard",
    },
}

# Properties that commonly have RenderIntentOverride
COLOR_NODES = ["Combine", "SatMap", "ColorMap", "CLUTer", "HSL"]


def generate_non_sequential_id(base: int = 100, used_ids: Optional[List[int]] = None) -> int:
    """Generate non-sequential IDs similar to real Gaea2 projects"""
    if used_ids is None:
        used_ids = []

    # Common ID patterns from real projects
    id_patterns = [
        183,
        668,
        427,
        281,
        294,
        949,
        483,
        800,
        375,
        245,
        958,
        174,
        258,
        975,
        639,
        514,
        287,
        490,
        340,
    ]

    # Try to use a pattern ID first
    for pattern_id in id_patterns:
        if pattern_id not in used_ids:
            return pattern_id

    # Generate a more random ID
    attempts = 0
    while attempts < 100:
        # Generate IDs in ranges similar to real projects
        ranges = [
            (100, 200),
            (240, 350),
            (370, 500),
            (630, 700),
            (790, 850),
            (940, 1000),
        ]
        range_choice = random.choice(ranges)
        new_id = random.randint(range_choice[0], range_choice[1])

        if new_id not in used_ids:
            return new_id
        attempts += 1

    # Fallback to sequential if we can't find a good random one
    return base + len(used_ids) * 10


def fix_property_names(properties: Dict[str, Any]) -> Dict[str, Any]:
    """Fix property names to match Gaea2's exact format"""
    fixed = {}

    for key, value in properties.items():
        # Check if we have a mapping for this property
        mapped_key = PROPERTY_NAME_MAPPING.get(key, key)

        # Special handling for Range properties
        if key == "Range" and isinstance(value, dict) and "X" in value and "Y" in value:
            # Range should have its own $id
            fixed[mapped_key] = {
                "$id": str(random.randint(100, 200)),
                "X": float(value.get("X", 0.5)),
                "Y": float(value.get("Y", 1.0)),
            }
        else:
            fixed[mapped_key] = value

    return fixed


def add_node_specific_properties(node_type: str, node: Dict[str, Any]) -> None:
    """Add node-specific properties that are commonly missing"""
    if node_type in NODE_PROPERTIES:
        for prop, value in NODE_PROPERTIES[node_type].items():
            if prop not in node:
                node[prop] = value

    # Add RenderIntentOverride for color-handling nodes
    if node_type in COLOR_NODES and "RenderIntentOverride" not in node:
        node["RenderIntentOverride"] = "Color"


def fix_empty_objects(project: Dict[str, Any], ref_counter: int) -> int:
    """Fix empty objects to use {"$id": "XX"} format"""
    # Fix Variables object
    if "Automation" in project.get("Assets", {}).get("$values", [{}])[0]:
        automation = project["Assets"]["$values"][0]["Automation"]
        if "Variables" in automation and automation["Variables"] == {}:
            automation["Variables"] = {"$id": str(ref_counter)}
            ref_counter += 1

    return ref_counter


def create_proper_port_structure(node_id: int, node_type: str, ref_id_counter: int) -> Tuple[Dict[str, Any], int]:
    """Create proper port structure based on node type"""
    ports = {"$id": str(ref_id_counter), "$values": []}
    ref_id_counter += 1

    # Standard input/output ports
    standard_ports = [
        {
            "$id": str(ref_id_counter),
            "Name": "In",
            "Type": "PrimaryIn",
            "IsExporting": True,
            "Parent": {"$ref": str(node_id)},
        },
        {
            "$id": str(ref_id_counter + 1),
            "Name": "Out",
            "Type": "PrimaryOut",
            "IsExporting": True,
            "Parent": {"$ref": str(node_id)},
        },
    ]
    ref_id_counter += 2

    ports["$values"].extend(standard_ports)

    # Add additional ports for specific node types
    if node_type == "Combine":
        # Combine nodes have Input2 and Mask ports
        ports["$values"].extend(
            [
                {
                    "$id": str(ref_id_counter),
                    "Name": "Input2",
                    "Type": "In",
                    "IsExporting": True,
                    "Parent": {"$ref": str(node_id)},
                },
                {
                    "$id": str(ref_id_counter + 1),
                    "Name": "Mask",
                    "Type": "In",
                    "IsExporting": True,
                    "Parent": {"$ref": str(node_id)},
                },
            ]
        )
        ref_id_counter += 2

    elif node_type == "Rivers":
        # Rivers node has multiple output ports
        additional_ports = [
            "Headwaters",
            "Rivers",
            "Depth",
            "Surface",
            "Direction",
            "Mask",
        ]
        for i, port_name in enumerate(additional_ports):
            port_type = "In" if port_name in ["Headwaters", "Mask"] else "Out"
            ports["$values"].append(
                {
                    "$id": str(ref_id_counter + i),
                    "Name": port_name,
                    "Type": port_type,
                    "IsExporting": True,
                    "Parent": {"$ref": str(node_id)},
                }
            )
        ref_id_counter += len(additional_ports)

    elif node_type == "Erosion2":
        # Erosion2 has additional output ports
        additional_ports = ["Flow", "Wear", "Deposits", "Mask"]
        for i, port_name in enumerate(additional_ports):
            port_type = "In" if port_name == "Mask" else "Out"
            ports["$values"].append(
                {
                    "$id": str(ref_id_counter + i),
                    "Name": port_name,
                    "Type": port_type,
                    "IsExporting": True,
                    "Parent": {"$ref": str(node_id)},
                }
            )
        ref_id_counter += len(additional_ports)

    return ports, ref_id_counter


def apply_format_fixes(
    project: Dict[str, Any],
    nodes: List[Dict[str, Any]],
    connections: Optional[List[Dict[str, Any]]],
) -> Dict[str, Any]:
    """Apply all format fixes to make the terrain file Gaea2-compatible"""
    # This will be called from the main create_gaea2_project function
    # to fix the format issues

    # 1. Fix empty objects
    ref_counter = 300  # Start from a high number to avoid conflicts
    ref_counter = fix_empty_objects(project, ref_counter)

    # 2. Update GraphTabs with proper viewport location
    if "GraphTabs" in project["Assets"]["$values"][0]["Terrain"]:
        tabs = project["Assets"]["$values"][0]["Terrain"]["GraphTabs"]["$values"]
        if tabs and len(tabs) > 0:
            tabs[0]["ViewportLocation"]["X"] = 25531.445
            tabs[0]["ViewportLocation"]["Y"] = 25791.812
            tabs[0]["ZoomFactor"] = 0.5338687202362516

    return project
