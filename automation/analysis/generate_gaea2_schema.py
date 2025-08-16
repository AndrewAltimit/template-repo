#!/usr/bin/env python3
"""
Generate accurate Gaea2 schema from documentation and real project analysis.
This creates a deterministic validation system for the MCP tool.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Based on comprehensive analysis of the documentation
GAEA2_COMPLETE_SCHEMA: Dict[str, Any] = {
    "version": "2.0",
    "source": "Official Gaea2 Documentation + Real Project Analysis",
    "valid_node_types": [
        # Primitive nodes (24)
        "Cellular",
        "Cellular3D",
        "Cone",
        "Constant",
        "Cracks",
        "CutNoise",
        "DotNoise",
        "Draw",
        "DriftNoise",
        "File",
        "Gabor",
        "Hemisphere",
        "LinearGradient",
        "LineNoise",
        "MultiFractal",
        "Noise",
        "Object",
        "Pattern",
        "Perlin",
        "RadialGradient",
        "Shape",
        "TileInput",
        "Voronoi",
        "WaveShine",
        # Terrain nodes (14)
        "Canyon",
        "Crater",
        "CraterField",
        "DuneSea",
        "Island",
        "Mountain",
        "MountainRange",
        "MountainSide",
        "Plates",
        "Ridge",
        "Rugged",
        "Slump",
        "Uplift",
        "Volcano",
        # Modify nodes (46)
        "Adjust",
        "Aperture",
        "Autolevel",
        "BlobRemover",
        "Blur",
        "Clamp",
        "Clip",
        "Curve",
        "Deflate",
        "Denoise",
        "Dilate",
        "DirectionalWarp",
        "Distance",
        "Equalize",
        "Extend",
        "Filter",
        "Flip",
        "Fold",
        "GraphicEQ",
        "Heal",
        "Match",
        "Median",
        "Meshify",
        "Origami",
        "Pixelate",
        "Recurve",
        "Shaper",
        "Sharpen",
        "SlopeBlur",
        "SlopeWarp",
        "SoftClip",
        "Swirl",
        "ThermalShaper",
        "Threshold",
        "Transform",
        "Transform3D",
        "Transpose",
        "TriplanarDisplacement",
        "VariableBlur",
        "Warp",
        "Whorl",
        # Surface nodes (21)
        "Bomber",
        "Bulbous",
        "Contours",
        "Craggy",
        "Distress",
        "FractalTerraces",
        "Grid",
        "GroundTexture",
        "Outcrops",
        "Pockmarks",
        "RockNoise",
        "Rockscape",
        "Roughen",
        "Sand",
        "Sandstone",
        "Shatter",
        "Shear",
        "Steps",
        "Stones",
        "Stratify",
        "Terraces",
        # Simulate nodes (25)
        "Anastomosis",
        "Crumble",
        "Debris",
        "Dusting",
        "EasyErosion",
        "Erosion",
        "Erosion2",
        "Glacier",
        "Hillify",
        "HydroFix",
        "IceFloe",
        "Lake",
        "Lichtenberg",
        "Rivers",
        "Scree",
        "Sea",
        "Sediments",
        "Shrubs",
        "Snow",
        "Snowfield",
        "Thermal",
        "Thermal2",
        "Trees",
        "Wizard",
        "Wizard2",
        # Derive nodes (13)
        "Angle",
        "Curvature",
        "FlowMap",
        "FlowMapClassic",
        "Height",
        "Normals",
        "Occlusion",
        "Peaks",
        "RockMap",
        "Slope",
        "Soil",
        "TextureBase",
        "Texturizer",
        # Colorize nodes (13)
        "CLUTer",
        "ColorErosion",
        "Gamma",
        "HSL",
        "RGBMerge",
        "RGBSplit",
        "SatMap",
        "Splat",
        "SuperColor",
        "Synth",
        "Tint",
        "WaterColor",
        "Weathering",
        # Output nodes (14)
        "AO",
        "Cartography",
        "Export",
        "Halftone",
        "LightX",
        "MeshWarp",
        "Mesher",
        "PointCloud",
        "Shade",
        "Sunlight",
        "TextureBaker",
        "Unity",
        "Unreal",
        "VFX",
        # Utility nodes (23)
        "Accumulator",
        "Chokepoint",
        "Combine",
        "Compare",
        "Construction",
        "DataExtractor",
        "Edge",
        "Gate",
        "Layers",
        "LoopBegin",
        "LoopEnd",
        "Mask",
        "MathX",
        "Mixer",
        "Portal",
        "PortalReceive",
        "PortalTransmit",
        "Repeat",
        "Reseed",
        "Route",
        "Seamless",
        "Switch",
        "Var",
    ],
    # Node-specific properties based on documentation and real projects
    "node_properties": {
        "Mountain": {
            "Scale": {"type": "float", "default": 1.0, "range": [0.1, 10.0]},
            "Height": {"type": "float", "default": 0.7, "range": [0.0, 1.0]},
            "Style": {
                "type": "enum",
                "default": "Basic",
                "values": ["Basic", "Eroded", "Old", "Alpine", "Strata"],
            },
            "Bulk": {
                "type": "enum",
                "default": "Medium",
                "values": ["Low", "Medium", "High"],
            },
            "Reduce Details": {"type": "bool", "default": False},
            "Seed": {"type": "int", "default": 0, "range": [0, 999999]},
            "X": {"type": "float", "default": 0.0, "range": [-1000.0, 1000.0]},
            "Y": {"type": "float", "default": 0.0, "range": [-1000.0, 1000.0]},
        },
        "Volcano": {
            "Scale": {"type": "float", "default": 1.0, "range": [0.1, 5.0]},
            "Height": {"type": "float", "default": 0.8, "range": [0.0, 1.0]},
            "Mouth": {"type": "float", "default": 0.3, "range": [0.0, 1.0]},
            "Bulk": {"type": "float", "default": 0.5, "range": [0.0, 1.0]},
            "Surface": {
                "type": "enum",
                "default": "Smooth",
                "values": ["Smooth", "Eroded"],
            },
            "X": {"type": "float", "default": 0.0, "range": [-1000.0, 1000.0]},
            "Y": {"type": "float", "default": 0.0, "range": [-1000.0, 1000.0]},
            "Seed": {"type": "int", "default": 0, "range": [0, 999999]},
        },
        "Erosion2": {
            "Duration": {"type": "float", "default": 0.04, "range": [0.0, 20.0]},
            "Downcutting": {"type": "float", "default": 0.0, "range": [0.0, 1.0]},
            "ErosionScale": {
                "type": "float",
                "default": 100.0,
                "range": [10.0, 100000.0],
            },
            "Seed": {"type": "int", "default": 0, "range": [0, 999999]},
            "SuspendedLoadDischargeAmount": {
                "type": "float",
                "default": 0.5,
                "range": [0.0, 1.0],
            },
            "SuspendedLoadDischargeAngle": {
                "type": "float",
                "default": 30.0,
                "range": [0.0, 90.0],
            },
            "BedLoadDischargeAmount": {
                "type": "float",
                "default": 0.5,
                "range": [0.0, 1.0],
            },
            "BedLoadDischargeAngle": {
                "type": "float",
                "default": 30.0,
                "range": [0.0, 90.0],
            },
            "CoarseSedimentsDischargeAmount": {
                "type": "float",
                "default": 0.5,
                "range": [0.0, 1.0],
            },
            "CoarseSedimentsDischargeAngle": {
                "type": "float",
                "default": 30.0,
                "range": [0.0, 90.0],
            },
            "Shape": {"type": "float", "default": 0.2, "range": [0.0, 1.0]},
            "ShapeSharpness": {"type": "float", "default": 0.6, "range": [0.0, 1.0]},
            "ShapeDetailScale": {"type": "float", "default": 0.25, "range": [0.0, 1.0]},
        },
        "Erosion": {
            "Duration": {"type": "float", "default": 0.04, "range": [0.0, 1.0]},
            "Rock Softness": {"type": "float", "default": 0.4, "range": [0.0, 1.0]},
            "Strength": {"type": "float", "default": 0.5, "range": [0.0, 2.0]},
            "Feature Scale": {"type": "int", "default": 2000, "range": [50, 10000]},
            "Downcutting": {"type": "float", "default": 0.0, "range": [0.0, 1.0]},
            "Inhibition": {"type": "float", "default": 0.0, "range": [0.0, 1.0]},
            "Base Level": {"type": "float", "default": 0.0, "range": [0.0, 1.0]},
            "Real Scale": {"type": "bool", "default": False},
            "Seed": {"type": "int", "default": 0, "range": [0, 999999]},
            "Aggressive Mode": {"type": "bool", "default": False},
            "Deterministic": {"type": "bool", "default": False},
        },
        "Combine": {
            "Mode": {
                "type": "enum",
                "default": "Blend",
                "values": [
                    "Blend",
                    "Add",
                    "Screen",
                    "Subtract",
                    "Difference",
                    "Multiply",
                    "Divide",
                    "Divide2",
                    "Max",
                    "Min",
                    "Hypotenuse",
                    "Overlay",
                    "Power",
                    "Exclusion",
                    "Dodge",
                    "Burn",
                    "SoftLight",
                    "HardLight",
                    "PinLight",
                    "GrainMerge",
                    "GrainExtract",
                    "Reflect",
                    "Glow",
                    "Phoenix",
                ],
            },
            "Ratio": {"type": "float", "default": 0.5, "range": [0.0, 1.0]},
            "Clamp": {
                "type": "enum",
                "default": "Clamp",
                "values": ["None", "Clamp", "Normalize"],
            },
        },
        "SatMap": {
            "Library": {
                "type": "enum",
                "default": "Rock",
                "values": ["New", "Rock", "Sand", "Green", "Blue", "Color"],
            },
            "Randomize": {"type": "bool", "default": False},
            "LibraryItem": {"type": "int", "default": 0, "range": [0, 50]},
            "Range": {"type": "float2", "default": {"X": 0.0, "Y": 1.0}},
            "Bias": {"type": "float", "default": 0.5, "range": [0.0, 1.0]},
            "Enhance": {
                "type": "enum",
                "default": "None",
                "values": ["None", "Autolevel", "Equalize"],
            },
            "Reverse": {"type": "bool", "default": False},
            "Rough": {
                "type": "enum",
                "default": "None",
                "values": ["None", "Low", "Med", "High", "Ultra"],
            },
            "Hue": {"type": "float", "default": 0.0, "range": [-1.0, 1.0]},
            "Saturation": {"type": "float", "default": 0.0, "range": [-1.0, 1.0]},
            "Lightness": {"type": "float", "default": 0.0, "range": [-1.0, 1.0]},
        },
        "Rivers": {
            "Water": {"type": "float", "default": 0.3, "range": [0.0, 1.0]},
            "Width": {"type": "float", "default": 0.5, "range": [0.0, 1.0]},
            "Depth": {"type": "float", "default": 0.5, "range": [0.0, 1.0]},
            "Downcutting": {"type": "float", "default": 0.0, "range": [0.0, 1.0]},
            "River Valley Width": {
                "type": "enum",
                "default": "zero",
                "values": ["minus4", "minus2", "zero", "plus2", "plus4"],
            },
            "Headwaters": {"type": "int", "default": 100, "range": [10, 1000]},
            "Render Surface": {"type": "bool", "default": False},
            "Seed": {"type": "int", "default": 0, "range": [0, 999999]},
        },
        "Snow": {
            "Duration": {"type": "float", "default": 0.5, "range": [0.0, 1.0]},
            "Intensity": {"type": "float", "default": 0.5, "range": [0.0, 1.0]},
            "Settle Duration": {"type": "float", "default": 0.5, "range": [0.0, 1.0]},
            "Melt Type": {
                "type": "enum",
                "default": "Uniform",
                "values": ["Uniform", "Directional"],
            },
            "Melt": {"type": "float", "default": 0.0, "range": [0.0, 1.0]},
            "Melt Remnants": {"type": "float", "default": 0.0, "range": [0.0, 1.0]},
            "Direction": {"type": "float", "default": 0.0, "range": [0.0, 360.0]},
            "Snow Line": {"type": "float", "default": 0.7, "range": [0.0, 1.0]},
            "Slip-off angle": {"type": "float", "default": 35.0, "range": [0.0, 90.0]},
            "Real Scale": {"type": "bool", "default": False},
        },
        "Thermal": {
            "Strength": {"type": "float", "default": 0.5, "range": [0.0, 1.0]},
            "Angle": {"type": "float", "default": 35.0, "range": [0.0, 90.0]},
            "Amount": {"type": "float", "default": 0.5, "range": [0.0, 1.0]},
        },
        "CLUTer": {
            "CLUT": {
                "type": "enum",
                "default": "Default",
                "values": ["Default", "Cinematic", "Vintage", "Cool", "Warm"],
            },
            "Intensity": {"type": "float", "default": 1.0, "range": [0.0, 1.0]},
        },
        "Canyon": {
            "Style": {
                "type": "enum",
                "default": "Basic",
                "values": ["Basic", "Eroded"],
            },
            "Scale": {"type": "float", "default": 1.0, "range": [0.1, 5.0]},
            "Slot": {"type": "float", "default": 0.5, "range": [0.0, 1.0]},
            "Valley": {"type": "float", "default": 0.5, "range": [0.0, 1.0]},
            "Surrounding": {"type": "float", "default": 0.5, "range": [0.0, 1.0]},
            "Depth": {"type": "float", "default": 1.0, "range": [0.0, 2.0]},
            "Seed": {"type": "int", "default": 0, "range": [0, 999999]},
        },
    },
    # Common properties that appear in many nodes
    "common_properties": {
        "Seed": {"type": "int", "default": 0, "range": [0, 999999]},
        "Scale": {"type": "float", "default": 1.0, "range": [0.01, 10.0]},
        "Height": {"type": "float", "default": 0.5, "range": [0.0, 1.0]},
        "Strength": {"type": "float", "default": 0.5, "range": [0.0, 2.0]},
        "Size": {"type": "float", "default": 0.5, "range": [0.0, 1.0]},
        "X": {"type": "float", "default": 0.0, "range": [-1000.0, 1000.0]},
        "Y": {"type": "float", "default": 0.0, "range": [-1000.0, 1000.0]},
    },
}


def validate_node_type(node_type: str) -> bool:
    """Check if a node type is valid"""
    return node_type in GAEA2_COMPLETE_SCHEMA["valid_node_types"]


def get_node_properties(node_type: str) -> Dict[str, Any]:
    """Get property definitions for a node type"""
    # First check node-specific properties
    node_properties = GAEA2_COMPLETE_SCHEMA["node_properties"]
    assert isinstance(node_properties, dict)  # Type assertion for mypy

    if node_type in node_properties:
        node_type_props = node_properties[node_type]
        assert isinstance(node_type_props, dict)  # Type assertion for mypy
        return node_type_props

    # Fall back to common properties for nodes without specific definitions
    common_props = GAEA2_COMPLETE_SCHEMA["common_properties"]
    assert isinstance(common_props, dict)  # Type assertion for mypy
    return common_props


def validate_property(node_type: str, prop_name: str, prop_value: Any) -> tuple[bool, Optional[str], Any]:
    """
    Validate a property value for a node type.
    Returns (is_valid, error_message, corrected_value)
    """
    node_props = get_node_properties(node_type)

    # Check if property exists for this node
    if prop_name not in node_props:
        # Check common properties
        common_properties = GAEA2_COMPLETE_SCHEMA["common_properties"]
        assert isinstance(common_properties, dict)  # Type assertion for mypy

        if prop_name in common_properties:
            prop_def = common_properties[prop_name]
        else:
            # Unknown property - allow but warn
            return (
                True,
                f"Unknown property '{prop_name}' for node type '{node_type}'",
                prop_value,
            )
    else:
        prop_def = node_props[prop_name]

    prop_type = prop_def["type"]

    # Type validation and coercion
    if prop_type == "int":
        if isinstance(prop_value, float) and prop_value.is_integer():
            prop_value = int(prop_value)
        elif not isinstance(prop_value, int):
            return False, f"Property '{prop_name}' must be an integer", None

        # Range check
        if "range" in prop_def:
            min_val, max_val = prop_def["range"]
            if not min_val <= prop_value <= max_val:
                return (
                    False,
                    f"Property '{prop_name}' value {prop_value} outside range [{min_val}, {max_val}]",
                    None,
                )

    elif prop_type == "float":
        if not isinstance(prop_value, (int, float)):
            return False, f"Property '{prop_name}' must be numeric", None
        prop_value = float(prop_value)

        # Range check
        if "range" in prop_def:
            min_val, max_val = prop_def["range"]
            if not min_val <= prop_value <= max_val:
                return (
                    False,
                    f"Property '{prop_name}' value {prop_value} outside range [{min_val}, {max_val}]",
                    None,
                )

    elif prop_type == "bool":
        if not isinstance(prop_value, bool):
            return False, f"Property '{prop_name}' must be boolean", None

    elif prop_type == "enum":
        if prop_value not in prop_def["values"]:
            return (
                False,
                f"Property '{prop_name}' value '{prop_value}' not in allowed values: {prop_def['values']}",
                None,
            )

    elif prop_type == "float2":
        if not isinstance(prop_value, dict) or "X" not in prop_value or "Y" not in prop_value:
            return (
                False,
                f"Property '{prop_name}' must be a dict with X and Y keys",
                None,
            )

    return True, None, prop_value


def validate_gaea_project(nodes: List[Dict[str, Any]], connections: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Validate a complete Gaea project configuration"""
    errors = []
    warnings = []
    corrected_nodes = []

    # Validate nodes
    for node in nodes:
        node_type = node.get("type")
        if not node_type:
            errors.append(f"Node missing 'type' field: {node}")
            continue

        if not validate_node_type(node_type):
            errors.append(f"Invalid node type: {node_type}")
            continue

        # Validate properties
        corrected_node = node.copy()
        corrected_props = {}

        for prop_name, prop_value in node.get("properties", {}).items():
            is_valid, error, corrected_value = validate_property(node_type, prop_name, prop_value)

            if not is_valid:
                errors.append(f"Node '{node.get('name', 'unnamed')}' ({node_type}): {error}")
            else:
                if error:  # Warning
                    warnings.append(f"Node '{node.get('name', 'unnamed')}' ({node_type}): {error}")
                corrected_props[prop_name] = corrected_value

        corrected_node["properties"] = corrected_props
        corrected_nodes.append(corrected_node)

    # Validate connections
    if connections:
        node_ids = {n.get("id") for n in nodes}
        for conn in connections:
            if conn.get("from_node") not in node_ids:
                errors.append(f"Connection references non-existent source node: {conn.get('from_node')}")
            if conn.get("to_node") not in node_ids:
                errors.append(f"Connection references non-existent target node: {conn.get('to_node')}")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "corrected_nodes": corrected_nodes,
        "stats": {
            "total_nodes": len(nodes),
            "total_connections": len(connections) if connections else 0,
            "error_count": len(errors),
            "warning_count": len(warnings),
        },
    }


def main():
    """Save the schema and test validation"""

    # Save the complete schema
    schema_path = Path("tools/mcp/gaea2_complete_schema.json")
    with open(schema_path, "w") as f:
        json.dump(GAEA2_COMPLETE_SCHEMA, f, indent=2)

    logger.info(f"✅ Saved complete schema with {len(GAEA2_COMPLETE_SCHEMA['valid_node_types'])} node types")
    logger.info(f"✅ Defined properties for {len(GAEA2_COMPLETE_SCHEMA['node_properties'])} nodes")

    # Test validation with sample project
    test_project = {
        "nodes": [
            {
                "id": 100,
                "type": "Mountain",
                "name": "TestMountain",
                "properties": {
                    "Scale": 1.5,
                    "Height": 0.8,
                    "Style": "Alpine",
                    "Seed": 12345.0,  # Will be coerced to int
                },
            },
            {
                "id": 101,
                "type": "InvalidNode",  # Should fail
                "name": "BadNode",
                "properties": {},
            },
        ],
        "connections": [],
    }

    result = validate_gaea_project(test_project["nodes"], test_project["connections"])

    print("\nValidation Test Results:")
    print(f"Valid: {result['valid']}")
    print(f"Errors: {result['errors']}")
    print(f"Warnings: {result['warnings']}")


if __name__ == "__main__":
    main()
