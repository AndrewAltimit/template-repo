"""Gaea2 Format Fixes - Corrections for proper terrain file generation"""

import random
from typing import Any, Dict, List, Optional, Tuple

# Node-specific property name mappings
# Based on analysis of reference terrain files
NODE_PROPERTY_MAPPINGS = {
    # Erosion2 properties - NO SPACES (from reference files)
    "Erosion2": {
        "erosionScale": "ErosionScale",
        "Erosion Scale": "ErosionScale",  # Fix if wrongly spaced
        "erosion scale": "ErosionScale",
        # Keep these as-is (no spaces)
        "Duration": "Duration",
        "Downcutting": "Downcutting",
        "ErosionScale": "ErosionScale",
        "Seed": "Seed",
        "Shape": "Shape",
        "ShapeDetailScale": "ShapeDetailScale",
        "ShapeSharpness": "ShapeSharpness",
        # Remove invalid properties
        "Rock Softness": None,  # Invalid for Erosion2
        "RockSoftness": None,  # Invalid for Erosion2
        "Base Level": None,  # Invalid for Erosion2
        "BaseLevel": None,  # Invalid for Erosion2
        "Intensity": None,  # Invalid for Erosion2
    },
    # Erosion (legacy) - redirect to Erosion2 properties
    "Erosion": {
        # Map all old Erosion properties to Erosion2 equivalents
        "Rock Softness": None,  # Remove - not valid
        "RockSoftness": None,  # Remove - not valid
        "Base Level": None,  # Remove - not valid
        "BaseLevel": None,  # Remove - not valid
        "Feature Scale": "ErosionScale",  # Map to ErosionScale
        "Real Scale": None,  # Remove - not valid
        "Aggressive Mode": None,  # Remove - not valid
        "Intensity": None,  # Remove - not valid
        "Strength": None,  # Remove - not valid
        # Valid properties
        "Duration": "Duration",
        "Downcutting": "Downcutting",
        "Seed": "Seed",
        "ErosionScale": "ErosionScale",
    },
    # Rivers properties - NO SPACES (from reference files)
    "Rivers": {
        "River Valley Width": "RiverValleyWidth",
        "river valley width": "RiverValleyWidth",
        "Render Surface": "RenderSurface",
        "render surface": "RenderSurface",
        "Sediment Removal": "SedimentRemoval",
        # Keep these as-is
        "Water": "Water",
        "Width": "Width",
        "Depth": "Depth",
        "Downcutting": "Downcutting",
        "RiverValleyWidth": "RiverValleyWidth",
        "Headwaters": "Headwaters",
        "RenderSurface": "RenderSurface",
        "Seed": "Seed",
    },
    # Sea node properties - NO SPACES
    "Sea": {
        "coastalErosion": "CoastalErosion",
        "coastal_erosion": "CoastalErosion",
        "Coastal Erosion": "CoastalErosion",
        "shoreSize": "ShoreSize",
        "shore_size": "ShoreSize",
        "Shore Size": "ShoreSize",
        "shoreHeight": "ShoreHeight",
        "shore_height": "ShoreHeight",
        "Shore Height": "ShoreHeight",
        "uniformVariations": "UniformVariations",
        "uniform_variations": "UniformVariations",
        "Uniform Variations": "UniformVariations",
        "extraCliffDetails": "ExtraCliffDetails",
        "extra_cliff_details": "ExtraCliffDetails",
        "Extra Cliff Details": "ExtraCliffDetails",
        "renderSurface": "RenderSurface",
        "render_surface": "RenderSurface",
        "Render Surface": "RenderSurface",
        # Keep as-is
        "Level": "Level",
        "Variation": "Variation",
    },
    # Volcano properties
    "Volcano": {
        "Surface": "Surface",  # Enum property, keep as-is
        "Mouth": "Mouth",
        "Bulk": "Bulk",
    },
    # MountainSide properties
    "MountainSide": {
        "Detail": "Detail",
        "Style": "Style",  # Enum property
        "Seed": "Seed",
    },
    # Weathering properties
    "Weathering": {
        "Scale": "Scale",
        "Creep": "Creep",
        "Dirt": "Dirt",
    },
    # Dusting properties
    "Dusting": {
        "snowline": "Snowline",
        "snow_line": "Snowline",
        "Snow Line": "Snowline",
        "Snowline": "Snowline",
        "Falloff": "Falloff",
        "Coverage": "Coverage",
        "Flow": "Flow",
        "Melt": "Melt",
        "Gritty": "Gritty",
        "Seed": "Seed",
    },
    # Stratify properties
    "Stratify": {
        "Spacing": "Spacing",
        "Octaves": "Octaves",
        "Intensity": "Intensity",
        "Seed": "Seed",
        "tiltAmount": "TiltAmount",
        "tilt_amount": "TiltAmount",
        "Tilt Amount": "TiltAmount",
        "TiltAmount": "TiltAmount",
    },
    # Perlin properties
    "Perlin": {
        "Type": "Type",  # Enum property
        "Scale": "Scale",
        "Octaves": "Octaves",
        "Gain": "Gain",
        "Clamp": "Clamp",
        "Seed": "Seed",
        "warpType": "WarpType",
        "warp_type": "WarpType",
        "Warp Type": "WarpType",
        "WarpType": "WarpType",
        "Frequency": "Frequency",
        "Amplitude": "Amplitude",
        "warpOctaves": "WarpOctaves",
        "warp_octaves": "WarpOctaves",
        "Warp Octaves": "WarpOctaves",
        "WarpOctaves": "WarpOctaves",
        "scaleX": "ScaleX",
        "scale_x": "ScaleX",
        "Scale X": "ScaleX",
        "ScaleX": "ScaleX",
        "scaleY": "ScaleY",
        "scale_y": "ScaleY",
        "Scale Y": "ScaleY",
        "ScaleY": "ScaleY",
        "X": "X",
        "Y": "Y",
    },
    # Generic mappings for other nodes
    "default": {
        "rockSoftness": "RockSoftness",
        "snowLine": "SnowLine",
        "settleDuration": "SettleDuration",
        "meltType": "MeltType",
        "slipOffAngle": "SlipOffAngle",
        "realScale": "RealScale",
        "baseLevel": "BaseLevel",
        "colorProduction": "ColorProduction",
    },
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
    "Sea": {
        "NodeSize": "Standard",
        "IsMaskable": True,
    },
    "Weathering": {
        "NodeSize": "Small",
        "IsMaskable": True,
    },
    "Volcano": {
        "IsMaskable": True,
    },
    "MountainSide": {
        "IsMaskable": True,
    },
    "Stratify": {
        "IsMaskable": True,
    },
    "Perlin": {
        "IsMaskable": False,  # Perlin typically doesn't use masks
    },
    "Dusting": {
        "IsMaskable": True,
    },
    "TextureBase": {
        "IsMaskable": True,
    },
    "FractalTerraces": {
        "IsMaskable": True,
    },
    "Height": {
        "IsMaskable": True,
    },
    "Crumble": {
        "IsMaskable": True,
    },
    "Shear": {
        "IsMaskable": True,
    },
    "Slump": {
        "IsMaskable": False,  # Primary generators typically don't use masks
    },
    "Island": {
        "IsMaskable": False,  # Primary generators typically don't use masks
    },
    "Blur": {
        "IsMaskable": True,
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


def fix_property_names(properties: Dict[str, Any], node_type: str = "default") -> Dict[str, Any]:
    """Fix property names to match Gaea2's exact format based on node type"""
    fixed: Dict[str, Any] = {}

    # Get the appropriate mapping for this node type
    mappings = NODE_PROPERTY_MAPPINGS.get(node_type, NODE_PROPERTY_MAPPINGS["default"])
    assert isinstance(mappings, dict)  # Type assertion for mypy

    for key, value in properties.items():
        # Ensure key is a string
        key_str = str(key) if not isinstance(key, str) else key

        # Check if we have a mapping for this property
        if key_str in mappings:
            mapped_key = mappings[key_str]
            # Skip if mapped to None (invalid property)
            if mapped_key is None:
                continue
        else:
            # Keep unmapped properties as-is
            mapped_key = key_str

        # Special handling for Range properties
        if key_str == "Range" and isinstance(value, dict) and "X" in value and "Y" in value:
            # Range should have its own $id
            fixed[mapped_key] = {
                "$id": str(random.randint(100, 200)),
                "X": float(value.get("X", 0.5)),
                "Y": float(value.get("Y", 1.0)),
            }
        # Fix enum values to lowercase for RiverValleyWidth
        elif mapped_key == "RiverValleyWidth" and isinstance(value, str):
            fixed[mapped_key] = value.lower()
        # Fix boolean properties that might come as strings
        elif mapped_key in ["RenderSurface", "IsMaskable"] and isinstance(value, str):
            fixed[mapped_key] = value.lower() == "true"
        else:
            fixed[mapped_key] = value

    return fixed


def add_node_specific_properties(node_type: str, node: Dict[str, Any]) -> None:
    """Add node-specific properties that are commonly missing"""
    if node_type in NODE_PROPERTIES:
        node_props = NODE_PROPERTIES[node_type]
        assert isinstance(node_props, dict)  # Type assertion for mypy
        for prop, value in node_props.items():
            if prop not in node:
                node[prop] = value

    # Add RenderIntentOverride for color-handling nodes
    if node_type in COLOR_NODES and "RenderIntentOverride" not in node:
        node["RenderIntentOverride"] = "Color"


def fix_empty_objects(project: Dict[str, Any], ref_counter: int) -> int:
    """Fix empty objects to use {"$id": "XX"} format"""
    # Fix Variables object
    assets_values = project.get("Assets", {}).get("$values", [])
    if not assets_values:
        return ref_counter

    if "Automation" in assets_values[0]:
        automation = assets_values[0]["Automation"]
        if "Variables" in automation and automation["Variables"] == {}:
            automation["Variables"] = {"$id": str(ref_counter)}
            ref_counter += 1

    return ref_counter


def create_proper_port_structure(node_id: int, node_type: str, ref_id_counter: int) -> Tuple[Dict[str, Any], int]:
    """Create proper port structure based on node type"""
    ports: Dict[str, Any] = {"$id": str(ref_id_counter), "$values": []}
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
        # Rivers node has multiple ports - some inputs, some outputs
        # Output ports first
        output_ports = ["Rivers", "Depth", "Surface", "Direction"]
        for i, port_name in enumerate(output_ports):
            ports["$values"].append(
                {
                    "$id": str(ref_id_counter + i),
                    "Name": port_name,
                    "Type": "Out",
                    "IsExporting": True,
                    "Parent": {"$ref": str(node_id)},
                }
            )
        ref_id_counter += len(output_ports)

        # Then input ports
        input_ports = ["Headwaters", "Mask"]
        for i, port_name in enumerate(input_ports):
            ports["$values"].append(
                {
                    "$id": str(ref_id_counter + i),
                    "Name": port_name,
                    "Type": "In",
                    "IsExporting": True,
                    "Parent": {"$ref": str(node_id)},
                }
            )
        ref_id_counter += len(input_ports)

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

    elif node_type == "Sea":
        # Sea node has multiple output ports and input ports
        # Output ports
        output_ports = ["Water", "Depth", "Shore", "Surface"]
        for i, port_name in enumerate(output_ports):
            ports["$values"].append(
                {
                    "$id": str(ref_id_counter + i),
                    "Name": port_name,
                    "Type": "Out",
                    "IsExporting": True,
                    "Parent": {"$ref": str(node_id)},
                }
            )
        ref_id_counter += len(output_ports)

        # Input ports
        input_ports = ["Edge", "Mask"]
        for i, port_name in enumerate(input_ports):
            ports["$values"].append(
                {
                    "$id": str(ref_id_counter + i),
                    "Name": port_name,
                    "Type": "In",
                    "IsExporting": True,
                    "Parent": {"$ref": str(node_id)},
                }
            )
        ref_id_counter += len(input_ports)

    elif node_type == "FractalTerraces":
        # FractalTerraces has Layers output and Modulation input
        ports["$values"].extend(
            [
                {
                    "$id": str(ref_id_counter),
                    "Name": "Layers",
                    "Type": "Out",
                    "IsExporting": True,
                    "Parent": {"$ref": str(node_id)},
                },
                {
                    "$id": str(ref_id_counter + 1),
                    "Name": "Modulation",
                    "Type": "In",
                    "IsExporting": True,
                    "Parent": {"$ref": str(node_id)},
                },
                {
                    "$id": str(ref_id_counter + 2),
                    "Name": "Mask",
                    "Type": "In",
                    "IsExporting": True,
                    "Parent": {"$ref": str(node_id)},
                },
            ]
        )
        ref_id_counter += 3

    elif node_type == "Stratify":
        # Stratify has Layers output
        ports["$values"].extend(
            [
                {
                    "$id": str(ref_id_counter),
                    "Name": "Layers",
                    "Type": "Out",
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

    elif node_type == "Crumble":
        # Crumble has Wear output and AreaMask input
        ports["$values"].extend(
            [
                {
                    "$id": str(ref_id_counter),
                    "Name": "Wear",
                    "Type": "Out",
                    "IsExporting": True,
                    "Parent": {"$ref": str(node_id)},
                },
                {
                    "$id": str(ref_id_counter + 1),
                    "Name": "AreaMask",
                    "Type": "In",
                    "IsExporting": True,
                    "Parent": {"$ref": str(node_id)},
                },
                {
                    "$id": str(ref_id_counter + 2),
                    "Name": "Mask",
                    "Type": "In",
                    "IsExporting": True,
                    "Parent": {"$ref": str(node_id)},
                },
            ]
        )
        ref_id_counter += 3

    return ports, ref_id_counter


def extract_and_fix_savedefinitions(project: Dict[str, Any], ref_counter: int) -> Tuple[List[Dict[str, Any]], int]:
    """Extract SaveDefinitions from Export nodes and create them as separate objects"""
    save_definitions: List[Dict[str, Any]] = []
    assets_values = project.get("Assets", {}).get("$values", [])
    if not assets_values or "Terrain" not in assets_values[0]:
        return save_definitions, ref_counter

    nodes = assets_values[0]["Terrain"]["Nodes"]

    # Find and extract SaveDefinitions from Export nodes
    for node_id, node in nodes.items():
        # Skip string references
        if isinstance(node, str):
            continue

        if "SaveDefinition" in node:
            # Extract the SaveDefinition
            save_def = node.pop("SaveDefinition")

            # Create a proper SaveDefinition object
            save_definition = {
                "$id": str(ref_counter),
                "Node": int(node_id),  # Reference to the node
                "Filename": save_def.get("Filename", "Export"),
                "Format": save_def.get("Format", "EXR"),
                "IsEnabled": save_def.get("IsEnabled", True),
            }
            ref_counter += 1
            save_definitions.append(save_definition)

    return save_definitions, ref_counter


def ensure_all_nodes_connected(project: Dict[str, Any]) -> None:
    """Ensure all nodes that should have connections are properly connected"""
    assets_values = project.get("Assets", {}).get("$values", [])
    if not assets_values or "Terrain" not in assets_values[0]:
        return

    nodes = assets_values[0]["Terrain"]["Nodes"]

    # Find nodes without incoming connections
    nodes_with_connections = set()
    for node_id, node in nodes.items():
        # Skip string references
        if isinstance(node, str):
            continue

        if "Ports" in node and "$values" in node["Ports"]:
            for port in node["Ports"]["$values"]:
                if "Record" in port:
                    nodes_with_connections.add(node_id)

    # Log disconnected nodes (for debugging)
    for node_id, node in nodes.items():
        # Skip string references
        if isinstance(node, str):
            continue

        if node_id not in nodes_with_connections:
            node_type = node.get("$type", "").split(".")[-2] if "." in node.get("$type", "") else "Unknown"
            # Note: We don't auto-connect as we don't know the intended workflow
            # This should be handled by proper connection setup
            print(f"Warning: Node {node_id} ({node_type}) has no incoming connections")


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
    assets_values = project.get("Assets", {}).get("$values", [])
    if assets_values and "Terrain" in assets_values[0] and "GraphTabs" in assets_values[0]["Terrain"]:
        tabs = assets_values[0]["Terrain"]["GraphTabs"]["$values"]
        if tabs and len(tabs) > 0:
            tabs[0]["ViewportLocation"]["X"] = 25531.445
            tabs[0]["ViewportLocation"]["Y"] = 25791.812
            tabs[0]["ZoomFactor"] = 0.5338687202362516

    # 3. DO NOT extract SaveDefinitions - they should remain embedded in nodes
    # Based on reference files analysis, SaveDefinitions must stay within the nodes
    # save_definitions, ref_counter = extract_and_fix_savedefinitions(project, ref_counter)

    # 4. DO NOT add SaveDefinitions as a separate array
    # if save_definitions:
    #     # Add SaveDefinitions to the Assets value object
    #     asset_value = project["Assets"]["$values"][0]
    #     if "SaveDefinitions" not in asset_value:
    #         asset_value["SaveDefinitions"] = {"$id": str(ref_counter), "$values": save_definitions}
    #         ref_counter += 1

    # 5. Ensure all nodes are properly connected
    ensure_all_nodes_connected(project)

    # 6. Fix node properties for all nodes
    if not assets_values or "Terrain" not in assets_values[0]:
        return project

    nodes_obj = assets_values[0]["Terrain"]["Nodes"]
    for node_id, node in nodes_obj.items():
        # Skip if node is just a string reference (like "$id": "6")
        if isinstance(node, str):
            continue

        # Get node type from $type
        node_type_full = node.get("$type", "")
        if "." in node_type_full:
            node_type = node_type_full.split(".")[-2]

            # Add node-specific properties
            add_node_specific_properties(node_type, node)

    return project
