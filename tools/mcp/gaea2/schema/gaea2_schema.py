#!/usr/bin/env python3
"""Gaea 2 node schema and validation functions - Version 2

This module provides comprehensive validation for Gaea 2 project files,
based on deep analysis of the official Gaea 2 documentation.
Updated with accurate node types, properties, and validation rules.
"""

from typing import Any, Dict, List, Tuple

# Complete node types extracted from Gaea 2 documentation
# Organized by category for better understanding and validation
NODE_CATEGORIES = {
    "primitive": [
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
    ],
    "terrain": [
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
    ],
    "modify": [
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
    ],
    "surface": [
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
    ],
    "simulate": [
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
    ],
    "derive": [
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
    ],
    "colorize": [
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
    ],
    "output": [
        "AO",
        "Cartography",
        "Export",
        "Halftone",
        "LightX",
        "Mesher",
        "PointCloud",
        "Shade",
        "Sunlight",
        "TextureBaker",
        "Unity",
        "Unreal",
        "VFX",
    ],
    "utility": [
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
        "Math",
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
}

# Flatten all node types into a single set for validation
VALID_NODE_TYPES = set()
for category_nodes in NODE_CATEGORIES.values():
    VALID_NODE_TYPES.update(category_nodes)

# Common node properties with their types and typical ranges
# Based on analysis from documentation
COMMON_NODE_PROPERTIES = {
    # Most common properties (used in 10+ nodes)
    "Seed": {
        "type": "int",
        "default": 0,
        "range": {"min": 0, "max": 999999},
        "description": "Randomization seed for the node's process",
    },
    "Scale": {
        "type": "float",
        "default": 1.0,
        "range": {"min": 0.01, "max": 10.0},
        "description": "Perceptual scale of the effect",
    },
    "Height": {
        "type": "float",
        "default": 0.5,
        "range": {"min": 0.0, "max": 1.0},
        "description": "Height or intensity of the effect",
    },
    "Size": {
        "type": "float",
        "default": 0.5,
        "range": {"min": 0.0, "max": 1.0},
        "description": "Size of features",
    },
    "Density": {
        "type": "float",
        "default": 0.5,
        "range": {"min": 0.0, "max": 1.0},
        "description": "Density of features",
    },
    "Octaves": {
        "type": "int",
        "default": 8,
        "range": {"min": 1, "max": 16},
        "description": "Number of noise octaves",
    },
    "Strength": {
        "type": "float",
        "default": 0.5,
        "range": {"min": 0.0, "max": 2.0},
        "description": "Strength of the effect",
    },
    "X": {
        "type": "float",
        "default": 0.0,
        "range": {"min": -1000.0, "max": 1000.0},
        "description": "X position or offset",
    },
    "Y": {
        "type": "float",
        "default": 0.0,
        "range": {"min": -1000.0, "max": 1000.0},
        "description": "Y position or offset",
    },
}

# Node-specific property definitions
# These override or extend the common properties
NODE_PROPERTY_DEFINITIONS = {
    "Mountain": {
        "Scale": {"type": "float", "default": 1.0, "range": {"min": 0.1, "max": 5.0}},
        "Height": {"type": "float", "default": 0.7, "range": {"min": 0.0, "max": 1.0}},
        "Style": {
            "type": "enum",
            "options": ["Basic", "Eroded", "Old", "Alpine", "Strata"],
            "default": "Basic",
        },
        "Bulk": {
            "type": "enum",
            "options": ["Low", "Medium", "High"],
            "default": "Medium",
        },
        "ReduceDetails": {"type": "bool", "default": False},
        "Seed": {"type": "int", "default": 0, "range": {"min": 0, "max": 999999}},
        "X": {
            "type": "float",
            "default": 0.0,
            "range": {"min": -1000.0, "max": 1000.0},
        },
        "Y": {
            "type": "float",
            "default": 0.0,
            "range": {"min": -1000.0, "max": 1000.0},
        },
    },
    "Erosion": {
        # Erosion section
        "Duration": {
            "type": "float",
            "default": 0.04,
            "range": {"min": 0.0, "max": 20.0},
            "description": "Duration of erosion simulation",
        },
        "RockSoftness": {
            "type": "float",
            "default": 0.4,
            "range": {"min": 0.0, "max": 1.0},
            "description": "Softness of rock material",
        },
        "Strength": {
            "type": "float",
            "default": 0.5,
            "range": {"min": 0.0, "max": 2.0},
            "description": "Strength of fluvial erosion",
        },
        # Downcutting section
        "Downcutting": {
            "type": "float",
            "default": 0.0,
            "range": {"min": 0.0, "max": 1.0},
        },
        "Inhibition": {
            "type": "float",
            "default": 0.0,
            "range": {"min": 0.0, "max": 1.0},
        },
        "BaseLevel": {
            "type": "float",
            "default": 0.0,
            "range": {"min": 0.0, "max": 1.0},
        },
        # Scale section
        "FeatureScale": {
            "type": "int",
            "default": 2000,
            "range": {"min": 50, "max": 10000},
            "description": "Size of erosion features in meters",
        },
        "RealScale": {"type": "bool", "default": False},
        # Other Settings section
        "Seed": {"type": "int", "default": 0, "range": {"min": 0, "max": 999999}},
        "AggressiveMode": {"type": "bool", "default": False},
        "Deterministic": {"type": "bool", "default": False},
    },
    "Combine": {
        "Mode": {
            "type": "enum",
            "options": [
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
            "default": "Blend",
        },
        "Ratio": {"type": "float", "default": 0.5, "range": {"min": 0.0, "max": 1.0}},
        "Clamp": {
            "type": "enum",
            "default": "Clamp",
            "options": ["None", "Clamp", "Normalize"],
        },
    },
    "SatMap": {
        # Main properties
        "Library": {
            "type": "enum",
            "options": ["New", "Rock", "Sand", "Green", "Blue", "Color"],
            "default": "Rock",
        },
        "Randomize": {"type": "bool", "default": False},
        "LibraryItem": {"type": "int", "default": 0, "range": {"min": 0, "max": 50}},
        "Range": {
            "type": "float2",
            "default": {"X": 0.5, "Y": 0.5},
            "range": {"min": 0.0, "max": 1.0},
            "description": "Range values for X and Y",
        },
        "Bias": {"type": "float", "default": 0.5, "range": {"min": 0.0, "max": 1.0}},
        # Processing section
        "Enhance": {
            "type": "enum",
            "options": ["None", "Autolevel", "Equalize"],
            "default": "None",
        },
        "Reverse": {"type": "bool", "default": False},
        "Rough": {
            "type": "enum",
            "options": ["None", "Low", "Med", "High", "Ultra"],
            "default": "None",
        },
        "Hue": {"type": "float", "default": 0.0, "range": {"min": -1.0, "max": 1.0}},
        "Saturation": {
            "type": "float",
            "default": 0.0,
            "range": {"min": -1.0, "max": 1.0},
        },
        "Lightness": {
            "type": "float",
            "default": 0.0,
            "range": {"min": -1.0, "max": 1.0},
        },
    },
    "Rivers": {
        "Water": {"type": "float", "default": 0.3, "range": {"min": 0.0, "max": 1.0}},
        "Width": {"type": "float", "default": 0.5, "range": {"min": 0.0, "max": 1.0}},
        "Depth": {"type": "float", "default": 0.5, "range": {"min": 0.0, "max": 1.0}},
        "Downcutting": {
            "type": "float",
            "default": 0.0,
            "range": {"min": 0.0, "max": 1.0},
        },
        "RiverValleyWidth": {
            "type": "enum",
            "options": ["minus4", "minus2", "zero", "plus2", "plus4"],
            "default": "zero",
        },
        "Headwaters": {
            "type": "int",
            "default": 100,
            "range": {"min": 10, "max": 1000},
        },
        "RenderSurface": {"type": "bool", "default": False},
        "Seed": {"type": "int", "default": 0, "range": {"min": 0, "max": 999999}},
    },
    "Snow": {
        # Snow section
        "Duration": {
            "type": "float",
            "default": 0.5,
            "range": {"min": 0.0, "max": 1.0},
        },
        "Intensity": {
            "type": "float",
            "default": 0.5,
            "range": {"min": 0.0, "max": 1.0},
        },
        "SettleDuration": {
            "type": "float",
            "default": 0.5,
            "range": {"min": 0.0, "max": 1.0},
        },
        # Melt section
        "MeltType": {
            "type": "enum",
            "options": ["Uniform", "Directional"],
            "default": "Uniform",
        },
        "Melt": {"type": "float", "default": 0.0, "range": {"min": 0.0, "max": 1.0}},
        "MeltRemnants": {
            "type": "float",
            "default": 0.0,
            "range": {"min": 0.0, "max": 1.0},
        },
        "Direction": {
            "type": "float",
            "default": 0.0,
            "range": {"min": 0.0, "max": 360.0},
        },
        "SnowLine": {
            "type": "float",
            "default": 0.7,
            "range": {"min": 0.0, "max": 1.0},
        },
        # Advanced section
        "SlipOffAngle": {
            "type": "float",
            "default": 35.0,
            "range": {"min": 0.0, "max": 90.0},
        },
        "RealScale": {"type": "bool", "default": False},
    },
    "Volcano": {
        "Scale": {"type": "float", "default": 1.0, "range": {"min": 0.1, "max": 5.0}},
        "Height": {"type": "float", "default": 0.8, "range": {"min": 0.0, "max": 1.0}},
        "Mouth": {"type": "float", "default": 0.3, "range": {"min": 0.0, "max": 1.0}},
        "Bulk": {"type": "float", "default": 0.5, "range": {"min": 0.0, "max": 1.0}},
        "Surface": {
            "type": "enum",
            "options": ["Smooth", "Eroded"],
            "default": "Smooth",
        },
        "X": {
            "type": "float",
            "default": 0.0,
            "range": {"min": -1000.0, "max": 1000.0},
        },
        "Y": {
            "type": "float",
            "default": 0.0,
            "range": {"min": -1000.0, "max": 1000.0},
        },
        "Seed": {"type": "int", "default": 0, "range": {"min": 0, "max": 999999}},
    },
    "Portal": {
        "PortalName": {
            "type": "string",
            "default": "Portal_1",
            "description": "Unique identifier for this portal connection",
        },
        "Direction": {
            "type": "enum",
            "options": ["Transmit", "Receive"],
            "default": "Transmit",
            "description": "Whether this portal sends or receives data",
        },
    },
    "PortalTransmit": {
        "PortalName": {
            "type": "string",
            "default": "Portal_1",
            "description": "Unique identifier for this portal connection",
        },
    },
    "PortalReceive": {
        "PortalName": {
            "type": "string",
            "default": "Portal_1",
            "description": "Unique identifier for this portal connection",
        },
    },
    "Stratify": {
        "Layers": {
            "type": "int",
            "default": 12,
            "range": {"min": 2, "max": 50},
            "description": "Number of stratification layers",
        },
        "Strength": {
            "type": "float",
            "default": 0.6,
            "range": {"min": 0.0, "max": 1.0},
        },
        "Spacing": {"type": "float", "default": 0.5, "range": {"min": 0.0, "max": 1.0}},
    },
    # Removed duplicate FractalTerraces - keeping the more complete one below
    "Terraces": {
        "Terraces": {
            "type": "int",
            "default": 10,
            "range": {"min": 2, "max": 50},
            "description": "Number of terraces",
        },
        "Uniformity": {
            "type": "float",
            "default": 0.5,
            "range": {"min": 0.0, "max": 1.0},
        },
        "Steepness": {
            "type": "float",
            "default": 0.5,
            "range": {"min": 0.0, "max": 1.0},
        },
    },
    "Steps": {
        "Steps": {
            "type": "int",
            "default": 5,
            "range": {"min": 2, "max": 20},
            "description": "Number of steps",
        },
        "Height": {"type": "float", "default": 0.5, "range": {"min": 0.0, "max": 1.0}},
    },
    "Pixelate": {
        "PixelSize": {
            "type": "int",
            "default": 16,
            "range": {"min": 2, "max": 128},
            "description": "Size of pixels",
        },
    },
    "Trees": {
        "Count": {
            "type": "int",
            "default": 1000,
            "range": {"min": 10, "max": 10000},
            "description": "Number of trees (in thousands)",
        },
        "Seed": {"type": "int", "default": 0, "range": {"min": 0, "max": 999999}},
    },
    "Shrubs": {
        "Count": {
            "type": "int",
            "default": 1000,
            "range": {"min": 10, "max": 10000},
            "description": "Number of shrubs (in thousands)",
        },
        "Seed": {"type": "int", "default": 0, "range": {"min": 0, "max": 999999}},
    },
    "Grid": {
        "GridSmallCount": {
            "type": "int",
            "default": 10,
            "range": {"min": 1, "max": 50},
            "description": "Small grid count",
        },
        "GridLargeCount": {
            "type": "int",
            "default": 5,
            "range": {"min": 1, "max": 20},
            "description": "Large grid count",
        },
    },
    "Aperture": {
        "Vertices": {
            "type": "int",
            "default": 6,
            "range": {"min": 3, "max": 12},
            "description": "Number of aperture vertices",
        },
    },
    # Priority 1: Most frequently used nodes
    "Erosion2": {
        "Duration": {
            "type": "float",
            "default": 0.15,
            "range": {"min": 0.01, "max": 2.0},
            "description": "Simulation duration",
        },
        "Downcutting": {
            "type": "float",
            "default": 0.3,
            "range": {"min": 0.0, "max": 1.0},
            "description": "Vertical erosion strength",
        },
        "ErosionScale": {
            "type": "float",
            "default": 5000.0,
            "range": {"min": 1000.0, "max": 20000.0},
            "description": "Erosion scale in meters",
        },
        "Seed": {
            "type": "int",
            "default": 0,
            "range": {"min": 0, "max": 999999},
            "description": "Random seed",
        },
        "BedLoadDischargeAmount": {
            "type": "float",
            "default": 0.0,
            "range": {"min": 0.0, "max": 1.0},
            "description": "Bed load discharge amount",
        },
        "BedLoadDischargeAngle": {
            "type": "float",
            "default": 0.0,
            "range": {"min": 0.0, "max": 360.0},
            "description": "Bed load discharge angle",
        },
        "CoarseSedimentsDischargeAmount": {
            "type": "float",
            "default": 0.0,
            "range": {"min": 0.0, "max": 1.0},
            "description": "Coarse sediments discharge amount",
        },
        "CoarseSedimentsDischargeAngle": {
            "type": "float",
            "default": 0.0,
            "range": {"min": 0.0, "max": 360.0},
            "description": "Coarse sediments discharge angle",
        },
        "SuspendedLoadDischargeAmount": {
            "type": "float",
            "default": 0.0,
            "range": {"min": 0.0, "max": 1.0},
            "description": "Suspended load discharge amount",
        },
        "SuspendedLoadDischargeAngle": {
            "type": "float",
            "default": 0.0,
            "range": {"min": 0.0, "max": 360.0},
            "description": "Suspended load discharge angle",
        },
        "Shape": {
            "type": "float",
            "default": 0.5,
            "range": {"min": 0.0, "max": 1.0},
            "description": "Erosion shape",
        },
        "ShapeDetailScale": {
            "type": "float",
            "default": 0.5,
            "range": {"min": 0.0, "max": 1.0},
            "description": "Shape detail scale",
        },
        "ShapeSharpness": {
            "type": "float",
            "default": 0.5,
            "range": {"min": 0.0, "max": 1.0},
            "description": "Shape sharpness",
        },
    },
    "FractalTerraces": {
        "Intensity": {
            "type": "float",
            "default": 0.5,
            "range": {"min": 0.0, "max": 1.0},
            "description": "Terrace intensity",
        },
        "Spacing": {
            "type": "float",
            "default": 0.2,
            "range": {"min": 0.1, "max": 0.4},
            "description": "Terrace spacing",
        },
        "Octaves": {
            "type": "int",
            "default": 12,
            "range": {"min": 1, "max": 16},
            "description": "Number of noise octaves",
        },
        "MacroOctaves": {
            "type": "int",
            "default": 5,
            "range": {"min": 1, "max": 8},
            "description": "Number of macro octaves",
        },
        "StrataDetails": {
            "type": "float",
            "default": 0.6,
            "range": {"min": 0.0, "max": 1.0},
            "description": "Strata detail level",
        },
        "TiltAmount": {
            "type": "float",
            "default": 0.5,
            "range": {"min": 0.0, "max": 1.0},
            "description": "Tilt amount",
        },
        "TiltSeed": {
            "type": "int",
            "default": 12345,
            "range": {"min": 0, "max": 999999},
            "description": "Tilt randomization seed",
        },
        "WarpAmount": {
            "type": "float",
            "default": 0.33,
            "range": {"min": 0.0, "max": 1.0},
            "description": "Warp amount",
        },
        "WarpSize": {
            "type": "float",
            "default": 0.33,
            "range": {"min": 0.0, "max": 1.0},
            "description": "Warp size",
        },
        "Seed": {
            "type": "int",
            "default": 0,
            "range": {"min": 0, "max": 999999},
            "description": "Random seed",
        },
    },
    # Priority 2: Commonly used nodes
    "Island": {
        "Size": {
            "type": "float",
            "default": 0.6,
            "range": {"min": 0.1, "max": 1.0},
            "description": "Island size relative to terrain",
        },
        "Chaos": {
            "type": "float",
            "default": 0.3,
            "range": {"min": 0.0, "max": 1.0},
            "description": "Island shape complexity",
        },
        "Height": {
            "type": "float",
            "default": 0.7,
            "range": {"min": 0.0, "max": 1.0},
            "description": "Maximum island height",
        },
        "Beaches": {
            "type": "float",
            "default": 0.8,
            "range": {"min": 0.0, "max": 1.0},
            "description": "Beach area extent",
        },
        "Seed": {"type": "int", "default": 0, "range": {"min": 0, "max": 999999}},
    },
    # Priority 3: Less common but important nodes
    "Crater": {
        "Radius": {
            "type": "float",
            "default": 0.4,
            "range": {"min": 0.1, "max": 1.0},
            "description": "Crater radius",
        },
        "Depth": {
            "type": "float",
            "default": 0.8,
            "range": {"min": 0.0, "max": 1.0},
            "description": "Crater depth",
        },
        "InnerSlope": {
            "type": "float",
            "default": 0.7,
            "range": {"min": 0.0, "max": 1.0},
            "description": "Inner crater wall slope",
        },
        "OuterSlope": {
            "type": "float",
            "default": 0.3,
            "range": {"min": 0.0, "max": 1.0},
            "description": "Outer crater rim slope",
        },
    },
    "Thermal": {
        "Strength": {
            "type": "float",
            "default": 0.4,
            "range": {"min": 0.0, "max": 1.0},
            "description": "Thermal erosion strength",
        },
        "Iterations": {
            "type": "int",
            "default": 15,
            "range": {"min": 1, "max": 50},
            "description": "Number of thermal iterations",
        },
        "Angle": {
            "type": "float",
            "default": 35.0,
            "range": {"min": 0.0, "max": 90.0},
            "description": "Repose angle in degrees",
        },
        "Intensity": {
            "type": "float",
            "default": 0.5,
            "range": {"min": 0.0, "max": 1.0},
            "description": "Thermal erosion intensity",
        },
    },
    "Sediments": {
        "Passes": {
            "type": "int",
            "default": 3,
            "range": {"min": 1, "max": 10},
            "description": "Number of sediment passes",
        },
        "Scale": {
            "type": "float",
            "default": 0.028,
            "range": {"min": 0.01, "max": 0.1},
            "description": "Sediment scale",
        },
        "Deposition": {
            "type": "float",
            "default": 0.5,
            "range": {"min": 0.0, "max": 1.0},
            "description": "Deposition amount",
        },
        "Sediments": {
            "type": "float",
            "default": 0.3,
            "range": {"min": 0.0, "max": 1.0},
            "description": "Sediment intensity",
        },
        "Seed": {
            "type": "int",
            "default": 0,
            "range": {"min": 0, "max": 999999},
            "description": "Random seed",
        },
    },
    # Water-related nodes
    "SeaLevel": {
        "Level": {
            "type": "float",
            "default": 0.0,
            "range": {"min": -1.0, "max": 1.0},
            "description": "Sea level height",
        },
        "Precision": {
            "type": "float",
            "default": 0.9,
            "range": {"min": 0.0, "max": 1.0},
            "description": "Water mask precision",
        },
    },
    "Beach": {
        "Width": {
            "type": "float",
            "default": 100.0,
            "range": {"min": 10.0, "max": 500.0},
            "description": "Beach width in meters",
        },
        "Slope": {
            "type": "float",
            "default": 0.1,
            "range": {"min": 0.0, "max": 1.0},
            "description": "Beach slope angle",
        },
    },
    "Coast": {
        "Erosion": {
            "type": "float",
            "default": 0.5,
            "range": {"min": 0.0, "max": 1.0},
            "description": "Coastal erosion strength",
        },
        "Detail": {
            "type": "float",
            "default": 0.5,
            "range": {"min": 0.0, "max": 1.0},
            "description": "Coastline detail level",
        },
    },
    "Lakes": {
        "Count": {
            "type": "int",
            "default": 3,
            "range": {"min": 1, "max": 20},
            "description": "Number of lakes",
        },
        "Size": {
            "type": "float",
            "default": 0.3,
            "range": {"min": 0.1, "max": 1.0},
            "description": "Average lake size",
        },
    },
    # Removed duplicate Rivers - keeping the more complete one above
    # Special effect nodes
    "LavaFlow": {
        "Temperature": {
            "type": "float",
            "default": 1200.0,
            "range": {"min": 800.0, "max": 1500.0},
            "description": "Lava temperature in Celsius",
        },
        "Viscosity": {
            "type": "float",
            "default": 0.5,
            "range": {"min": 0.0, "max": 1.0},
            "description": "Lava viscosity",
        },
    },
    "ThermalShatter": {
        "Intensity": {
            "type": "float",
            "default": 0.5,
            "range": {"min": 0.0, "max": 1.0},
            "description": "Thermal shattering intensity",
        },
        "Scale": {
            "type": "float",
            "default": 0.3,
            "range": {"min": 0.1, "max": 1.0},
            "description": "Shatter pattern scale",
        },
    },
    # Selector nodes
    "HeightSelector": {
        "Min": {
            "type": "float",
            "default": 0.0,
            "range": {"min": -1000.0, "max": 10000.0},
            "description": "Minimum height",
        },
        "Max": {
            "type": "float",
            "default": 500.0,
            "range": {"min": -1000.0, "max": 10000.0},
            "description": "Maximum height",
        },
        "Falloff": {
            "type": "float",
            "default": 0.1,
            "range": {"min": 0.0, "max": 1.0},
            "description": "Selection falloff",
        },
    },
    "SlopeSelector": {
        "MinAngle": {
            "type": "float",
            "default": 0.0,
            "range": {"min": 0.0, "max": 90.0},
            "description": "Minimum slope angle in degrees",
        },
        "MaxAngle": {
            "type": "float",
            "default": 30.0,
            "range": {"min": 0.0, "max": 90.0},
            "description": "Maximum slope angle in degrees",
        },
        "Falloff": {
            "type": "float",
            "default": 0.1,
            "range": {"min": 0.0, "max": 1.0},
            "description": "Selection falloff",
        },
    },
    # Composition nodes
    "Layers": {
        "BlendMode": {
            "type": "enum",
            "options": ["Normal", "Multiply", "Add", "Subtract", "Max", "Min"],
            "default": "Normal",
            "description": "Layer blending mode",
        },
        "Opacity": {
            "type": "float",
            "default": 1.0,
            "range": {"min": 0.0, "max": 1.0},
            "description": "Layer opacity",
        },
    },
    # Export node properties
    "Export": {
        "Format": {
            "type": "enum",
            "options": ["PNG", "TIF", "EXR", "RAW", "Terrain", "Build"],
            "default": "PNG",
            "description": "Export file format",
        },
        "BitDepth": {
            "type": "enum",
            "options": ["8", "16", "32"],
            "default": "16",
            "description": "Bit depth for export",
        },
        # Note: filename, format, and enabled are typically in save_definition, not properties
    },
    # Sea node with comprehensive properties from real projects
    "Sea": {
        "Level": {
            "type": "float",
            "default": 0.0,
            "range": {"min": -1.0, "max": 1.0},
            "description": "Sea level height",
        },
        "CoastalErosion": {
            "type": "bool",
            "default": False,
            "description": "Enable coastal erosion effects",
        },
        "ShoreSize": {
            "type": "float",
            "default": 0.5,
            "range": {"min": 0.0, "max": 1.0},
            "description": "Size of the shore area",
        },
        "ShoreHeight": {
            "type": "float",
            "default": 0.1,
            "range": {"min": 0.0, "max": 1.0},
            "description": "Height of shore features",
        },
        "Variation": {
            "type": "float",
            "default": 0.5,
            "range": {"min": 0.0, "max": 1.0},
            "description": "Shore variation amount",
        },
        "UniformVariations": {
            "type": "bool",
            "default": False,
            "description": "Use uniform variations",
        },
        "ExtraCliffDetails": {
            "type": "bool",
            "default": False,
            "description": "Add extra cliff details",
        },
        "RenderSurface": {
            "type": "bool",
            "default": False,
            "description": "Render water surface",
        },
    },
    # MountainSide node
    "MountainSide": {
        "Detail": {
            "type": "float",
            "default": 0.25,
            "range": {"min": 0.0, "max": 1.0},
            "description": "Level of detail",
        },
        "Style": {
            "type": "enum",
            "options": ["Smooth", "Eroded", "Rocky"],
            "default": "Smooth",
            "description": "Mountain side style",
        },
        "Seed": {
            "type": "int",
            "default": 0,
            "range": {"min": 0, "max": 999999},
            "description": "Random seed",
        },
    },
    # Weathering node
    "Weathering": {
        "Scale": {
            "type": "float",
            "default": 0.5,
            "range": {"min": 0.0, "max": 1.0},
            "description": "Weathering scale",
        },
        "Creep": {
            "type": "float",
            "default": 0.5,
            "range": {"min": 0.0, "max": 1.0},
            "description": "Material creep amount",
        },
        "Dirt": {
            "type": "float",
            "default": 0.5,
            "range": {"min": 0.0, "max": 1.0},
            "description": "Dirt accumulation",
        },
    },
    # Dusting node
    "Dusting": {
        "Snowline": {
            "type": "float",
            "default": 0.7,
            "range": {"min": 0.0, "max": 1.0},
            "description": "Snow/dust line height",
        },
        "Falloff": {
            "type": "float",
            "default": 0.2,
            "range": {"min": 0.0, "max": 1.0},
            "description": "Falloff amount",
        },
        "Coverage": {
            "type": "float",
            "default": 0.5,
            "range": {"min": 0.0, "max": 1.0},
            "description": "Coverage amount",
        },
        "Flow": {
            "type": "float",
            "default": 0.3,
            "range": {"min": 0.0, "max": 1.0},
            "description": "Flow amount",
        },
        "Melt": {
            "type": "float",
            "default": 0.0,
            "range": {"min": 0.0, "max": 1.0},
            "description": "Melt amount",
        },
        "Gritty": {
            "type": "bool",
            "default": False,
            "description": "Add gritty texture",
        },
        "Seed": {
            "type": "int",
            "default": 0,
            "range": {"min": 0, "max": 999999},
            "description": "Random seed",
        },
    },
    # Comprehensive Perlin node
    "Perlin": {
        "Type": {
            "type": "enum",
            "options": ["Default", "Ridged", "Billowy"],
            "default": "Default",
            "description": "Perlin noise type",
        },
        "Scale": {
            "type": "float",
            "default": 1.0,
            "range": {"min": 0.0, "max": 1.0},
            "description": "Base scale",
        },
        "Octaves": {
            "type": "int",
            "default": 8,
            "range": {"min": 1, "max": 10},
            "description": "Number of octaves",
        },
        "Gain": {
            "type": "float",
            "default": 0.5,
            "range": {"min": 0.0, "max": 1.0},
            "description": "Gain amount",
        },
        "Clamp": {
            "type": "float",
            "default": 1.0,
            "range": {"min": 0.0, "max": 1.0},
            "description": "Clamp value",
        },
        "Seed": {
            "type": "int",
            "default": 0,
            "range": {"min": 0, "max": 999999},
            "description": "Random seed",
        },
        "WarpType": {
            "type": "enum",
            "options": ["None", "Simple", "Complex"],
            "default": "None",
            "description": "Warp type",
        },
        "Frequency": {
            "type": "float",
            "default": 0.5,
            "range": {"min": 0.0, "max": 1.0},
            "description": "Warp frequency",
        },
        "Amplitude": {
            "type": "float",
            "default": 0.5,
            "range": {"min": 0.0, "max": 1.0},
            "description": "Warp amplitude",
        },
        "WarpOctaves": {
            "type": "int",
            "default": 4,
            "range": {"min": 1, "max": 10},
            "description": "Warp octaves",
        },
        "ScaleX": {
            "type": "float",
            "default": 1.0,
            "range": {"min": 0.1, "max": 10.0},
            "description": "X scale multiplier",
        },
        "ScaleY": {
            "type": "float",
            "default": 1.0,
            "range": {"min": 0.1, "max": 10.0},
            "description": "Y scale multiplier",
        },
        "X": {
            "type": "float",
            "default": 0.0,
            "range": {"min": -1000.0, "max": 1000.0},
            "description": "X position",
        },
        "Y": {
            "type": "float",
            "default": 0.0,
            "range": {"min": -1000.0, "max": 1000.0},
            "description": "Y position",
        },
    },
    # TextureBase node
    "TextureBase": {
        "Slope": {
            "type": "float",
            "default": 0.5,
            "range": {"min": 0.0, "max": 1.0},
            "description": "Slope influence",
        },
        "Scale": {
            "type": "float",
            "default": 0.5,
            "range": {"min": 0.0, "max": 1.0},
            "description": "Texture scale",
        },
        "Soil": {
            "type": "float",
            "default": 0.5,
            "range": {"min": 0.0, "max": 1.0},
            "description": "Soil coverage",
        },
        "Patches": {
            "type": "float",
            "default": 0.5,
            "range": {"min": 0.0, "max": 1.0},
            "description": "Patch variation",
        },
        "Chaos": {
            "type": "float",
            "default": 0.5,
            "range": {"min": 0.0, "max": 1.0},
            "description": "Chaos amount",
        },
        "Seed": {
            "type": "int",
            "default": 0,
            "range": {"min": 0, "max": 999999},
            "description": "Random seed",
        },
    },
    # Height node
    "Height": {
        "Range": {
            "type": "float2",
            "default": {"X": 0.0, "Y": 1.0},
            "range": {"min": 0.0, "max": 1.0},
            "description": "Height range (min, max)",
        },
        "Falloff": {
            "type": "float",
            "default": 0.1,
            "range": {"min": 0.0, "max": 1.0},
            "description": "Edge falloff",
        },
    },
    # Adjust node
    "Adjust": {
        "Multiply": {
            "type": "float",
            "default": 1.0,
            "range": {"min": 0.0, "max": 10.0},
            "description": "Multiplication factor",
        },
        "Add": {
            "type": "float",
            "default": 0.0,
            "range": {"min": -1.0, "max": 1.0},
            "description": "Addition value",
        },
        "Shaper": {
            "type": "float",
            "default": 0.5,
            "range": {"min": 0.0, "max": 1.0},
            "description": "Shape adjustment",
        },
        "Clamp": {
            "type": "float2",
            "default": {"X": 0.0, "Y": 1.0},
            "range": {"min": 0.0, "max": 1.0},
            "description": "Clamp range",
        },
        "Equalize": {
            "type": "bool",
            "default": False,
            "description": "Apply equalization",
        },
        "Invert": {
            "type": "bool",
            "default": False,
            "description": "Invert values",
        },
    },
    # Slump node
    "Slump": {
        "Scale": {
            "type": "float",
            "default": 1.0,
            "range": {"min": 0.0, "max": 1.0},
            "description": "Slump scale",
        },
        "Seed": {
            "type": "int",
            "default": 0,
            "range": {"min": 0, "max": 999999},
            "description": "Random seed",
        },
    },
    # Blur node
    "Blur": {
        "Radius": {
            "type": "float",
            "default": 0.5,
            "range": {"min": 0.0, "max": 1.0},
            "description": "Blur radius",
        },
    },
    # Shear node
    "Shear": {
        "Strength": {
            "type": "float",
            "default": 0.5,
            "range": {"min": 0.0, "max": 1.0},
            "description": "Shear strength",
        },
        "Seed": {
            "type": "int",
            "default": 0,
            "range": {"min": 0, "max": 999999},
            "description": "Random seed",
        },
    },
    # Crumble node
    "Crumble": {
        "Duration": {
            "type": "float",
            "default": 0.5,
            "range": {"min": 0.0, "max": 1.0},
            "description": "Crumble duration",
        },
        "Strength": {
            "type": "float",
            "default": 0.5,
            "range": {"min": 0.0, "max": 1.0},
            "description": "Crumble strength",
        },
        "Coverage": {
            "type": "float",
            "default": 0.5,
            "range": {"min": 0.0, "max": 1.0},
            "description": "Coverage area",
        },
        "Horizontal": {
            "type": "float",
            "default": 0.5,
            "range": {"min": 0.0, "max": 1.0},
            "description": "Horizontal spread",
        },
        "RockHardness": {
            "type": "float",
            "default": 0.5,
            "range": {"min": 0.0, "max": 1.0},
            "description": "Rock hardness",
        },
        "Edge": {
            "type": "float",
            "default": 0.5,
            "range": {"min": 0.0, "max": 1.0},
            "description": "Edge preservation",
        },
        "Depth": {
            "type": "float",
            "default": 0.5,
            "range": {"min": 0.0, "max": 1.0},
            "description": "Crumble depth",
        },
    },
}

# Port definitions and compatibility rules
# Based on node categories and typical connections
PORT_TYPES = {
    "heightfield": "Primary terrain or mask data",
    "color": "RGB color data",
    "mask": "Grayscale mask data",
    "data": "Analysis data (flow, wear, etc.)",
    "vector": "Vector field data",
}

# Port compatibility matrix
# Defines which output port types can connect to which input port types
PORT_COMPATIBILITY = {
    "heightfield": ["heightfield", "mask"],  # Heightfields can be used as masks
    "color": ["color"],  # Colors only connect to colors
    "mask": ["heightfield", "mask"],  # Masks are interchangeable with heightfields
    "data": ["mask"],  # Data maps can be used as masks
    "vector": ["vector"],  # Vectors only connect to vectors
}

# Node port definitions by category
NODE_PORT_DEFINITIONS = {
    # Generators have no inputs, only outputs
    "primitive": {"inputs": [], "outputs": [{"name": "Out", "type": "heightfield"}]},
    "terrain": {"inputs": [], "outputs": [{"name": "Out", "type": "heightfield"}]},
    # Modifiers have input and output
    "modify": {
        "inputs": [{"name": "In", "type": "heightfield"}],
        "outputs": [{"name": "Out", "type": "heightfield"}],
    },
    "surface": {
        "inputs": [{"name": "In", "type": "heightfield"}],
        "outputs": [{"name": "Out", "type": "heightfield"}],
    },
    "simulate": {
        "inputs": [{"name": "In", "type": "heightfield"}],
        "outputs": [
            {"name": "Out", "type": "heightfield"},
            {"name": "Wear", "type": "data"},
            {"name": "Flow", "type": "data"},
            {"name": "Deposits", "type": "data"},
        ],
    },
    # Analyzers output data maps
    "derive": {
        "inputs": [{"name": "In", "type": "heightfield"}],
        "outputs": [{"name": "Out", "type": "data"}],
    },
    # Colorizers work with color data
    "colorize": {
        "inputs": [
            {"name": "In", "type": "heightfield"},
            {"name": "Mask", "type": "mask", "optional": True},
        ],
        "outputs": [{"name": "Out", "type": "color"}],
    },
    # Special cases
    "combine": {
        "inputs": [
            {"name": "Input1", "type": "heightfield"},
            {"name": "Input2", "type": "heightfield"},
            {"name": "Mask", "type": "mask", "optional": True},
        ],
        "outputs": [
            {"name": "Out", "type": "heightfield"},
            {"name": "Separation", "type": "mask"},
        ],
    },
    "portal": {
        "inputs": [{"name": "In", "type": "heightfield"}],
        "outputs": [],  # Portal only stores data for later retrieval
    },
    "portaltransmit": {
        "inputs": [{"name": "In", "type": "heightfield"}],
        "outputs": [],  # Transmit portal doesn't have direct outputs
    },
    "portalreceive": {
        "inputs": [],  # Receive portal doesn't have direct inputs
        "outputs": [{"name": "Out", "type": "heightfield"}],
    },
    # Multi-output nodes discovered from real projects
    "sea": {
        "inputs": [
            {"name": "In", "type": "heightfield"},
            {"name": "Edge", "type": "mask", "optional": True},
            {"name": "Mask", "type": "mask", "optional": True},
        ],
        "outputs": [
            {"name": "Out", "type": "heightfield"},
            {"name": "Water", "type": "mask"},
            {"name": "Shore", "type": "mask"},
            {"name": "Depth", "type": "data"},
            {"name": "Surface", "type": "data"},
        ],
    },
    "rivers": {
        "inputs": [
            {"name": "In", "type": "heightfield"},
            {"name": "Mask", "type": "mask", "optional": True},
        ],
        "outputs": [
            {"name": "Out", "type": "heightfield"},
            {"name": "Rivers", "type": "mask"},
            {"name": "Depth", "type": "data"},
            {"name": "Surface", "type": "data"},
            {"name": "Direction", "type": "vector"},
        ],
    },
    "fractalterraces": {
        "inputs": [
            {"name": "In", "type": "heightfield"},
            {"name": "Modulation", "type": "heightfield", "optional": True},
            {"name": "Mask", "type": "mask", "optional": True},
        ],
        "outputs": [
            {"name": "Out", "type": "heightfield"},
            {"name": "Layers", "type": "mask"},
        ],
    },
    "stratify": {
        "inputs": [
            {"name": "In", "type": "heightfield"},
            {"name": "Mask", "type": "mask", "optional": True},
        ],
        "outputs": [
            {"name": "Out", "type": "heightfield"},
            {"name": "Layers", "type": "mask"},
        ],
    },
    "crumble": {
        "inputs": [
            {"name": "In", "type": "heightfield"},
            {"name": "AreaMask", "type": "mask", "optional": True},
            {"name": "Mask", "type": "mask", "optional": True},
        ],
        "outputs": [
            {"name": "Out", "type": "heightfield"},
            {"name": "Wear", "type": "data"},
        ],
    },
    "erosion2": {
        "inputs": [
            {"name": "In", "type": "heightfield"},
            {"name": "Mask", "type": "mask", "optional": True},
        ],
        "outputs": [
            {"name": "Out", "type": "heightfield"},
            {"name": "Flow", "type": "data"},
            {"name": "Wear", "type": "data"},
            {"name": "Deposits", "type": "data"},
        ],
    },
}

# Enhanced workflow templates based on documentation examples
WORKFLOW_TEMPLATES = {
    "basic_terrain": [
        {
            "type": "Mountain",
            "name": "BaseTerrain",
            "properties": {"Scale": 1.0, "Height": 0.7, "Style": "Alpine"},
        },
        {
            "type": "Erosion2",
            "name": "NaturalErosion",
            "properties": {
                "Duration": 0.15,
                "Downcutting": 0.3,
                "ErosionScale": 5000.0,
                "Seed": 12345,
            },
        },
        {"type": "TextureBase", "name": "BaseTexture", "properties": {}},
        {
            "type": "SatMap",
            "name": "ColorMap",
            "properties": {"Library": "Rock", "LibraryItem": 0},
        },
    ],
    "detailed_mountain": [
        {
            "type": "Mountain",
            "name": "PrimaryMountain",
            "properties": {
                "Scale": 1.5,
                "Height": 0.85,
                "Style": "Alpine",
                "Bulk": "High",
            },
        },
        {
            "type": "Mountain",
            "name": "SecondaryPeaks",
            "properties": {"Scale": 0.8, "Height": 0.6, "Style": "Eroded"},
        },
        {
            "type": "Combine",
            "name": "MergePeaks",
            "properties": {"Mode": "Max", "Ratio": 0.7},
        },
        {
            "type": "Erosion2",
            "name": "InitialErosion",
            "properties": {
                "Duration": 0.15,
                "Downcutting": 0.35,
                "ErosionScale": 6000.0,
                "Seed": 23456,
            },
        },
        {
            "type": "Rivers",
            "name": "MountainStreams",
            "properties": {"Water": 0.3, "Width": 0.5, "Depth": 0.4},
        },
        {
            "type": "Snow",
            "name": "SnowCaps",
            "properties": {"Duration": 0.6, "SnowLine": 0.75},
        },
        {
            "type": "SatMap",
            "name": "RealisticColors",
            "properties": {"Library": "Rock", "Enhance": "Autolevel"},
        },
    ],
    "volcanic_terrain": [
        {
            "type": "Volcano",
            "name": "MainVolcano",
            "properties": {
                "Scale": 1.2,
                "Height": 0.8,
                "Mouth": 0.3,
                "X": 0.296276,
                "Y": 0.5,
            },
        },
        {
            "type": "Island",
            "name": "VolcanicIsland",
            "properties": {"Size": 0.5, "Chaos": 0.3, "Seed": 12345},
        },
        {
            "type": "Combine",
            "name": "MergeVolcano",
            "properties": {"Mode": "Add", "Ratio": 0.8},
        },
        {
            "type": "Erosion2",
            "name": "LavaErosion",
            "properties": {
                "Duration": 0.15,
                "Downcutting": 0.4,
                "ErosionScale": 4000.0,
                "Seed": 34567,
            },
        },
        {
            "type": "Thermal",
            "name": "ThermalWeathering",
            "properties": {"Strength": 0.5, "Angle": 35.0},
        },
        {
            "type": "SatMap",
            "name": "VolcanicColors",
            "properties": {"Library": "Rock", "LibraryItem": 1},
        },
    ],
    "desert_canyon": [
        {
            "type": "Canyon",
            "name": "MainCanyon",
            "properties": {"Scale": 1.5, "Depth": 0.7},
        },
        {
            "type": "Stratify",
            "name": "RockLayers",
            "properties": {"Layers": 12, "Strength": 0.6},
        },
        {
            "type": "FractalTerraces",
            "name": "TerraceFormation",
            "properties": {
                "Intensity": 0.5,
                "Spacing": 0.2,
                "Octaves": 12,
                "MacroOctaves": 5,
                "StrataDetails": 0.6,
                "Seed": 54321,
            },
        },
        {
            "type": "Erosion2",
            "name": "WindErosion",
            "properties": {
                "Duration": 0.10,
                "Downcutting": 0.2,
                "ErosionScale": 3000.0,
                "Seed": 45678,
            },
        },
        {
            "type": "Sand",
            "name": "SandAccumulation",
            "properties": {"Amount": 0.4, "Scale": 0.5},
        },
        {
            "type": "SatMap",
            "name": "DesertColors",
            "properties": {"Library": "Sand", "LibraryItem": 0},
        },
    ],
    "modular_portal_terrain": [
        {
            "type": "Mountain",
            "name": "PrimaryShape",
            "properties": {"Scale": 1.2, "Height": 0.8, "Style": "Alpine"},
        },
        {
            "type": "PortalTransmit",
            "name": "ShapePortal",
            "properties": {"PortalName": "Primary_Shape"},
        },
        {
            "type": "PortalReceive",
            "name": "ShapeForErosion",
            "properties": {"PortalName": "Primary_Shape"},
        },
        {
            "type": "Erosion2",
            "name": "DetailedErosion",
            "properties": {
                "Duration": 0.20,
                "Downcutting": 0.4,
                "ErosionScale": 8000.0,
                "Seed": 56789,
            },
        },
        {
            "type": "PortalTransmit",
            "name": "ErodedPortal",
            "properties": {"PortalName": "Eroded_Terrain"},
        },
        {
            "type": "PortalReceive",
            "name": "ShapeForAnalysis",
            "properties": {"PortalName": "Primary_Shape"},
        },
        {
            "type": "Slope",
            "name": "SlopeAnalysis",
            "properties": {},
        },
        {
            "type": "PortalReceive",
            "name": "FinalTerrain",
            "properties": {"PortalName": "Eroded_Terrain"},
        },
        {
            "type": "SatMap",
            "name": "TerrainColors",
            "properties": {"Library": "Rock", "LibraryItem": 2},
        },
    ],
    # Alias for test compatibility
    "mountain_range": [
        {
            "type": "Mountain",
            "name": "MainRange",
            "properties": {
                "Scale": 2.0,
                "Height": 0.9,
                "Style": "Alpine",
                "Bulk": "High",
                "Seed": 12345,
            },
        },
        {
            "type": "Ridge",
            "name": "RidgeDetail",
            "properties": {"Scale": 0.5, "Complexity": 0.7},
        },
        {
            "type": "Combine",
            "name": "MergeRidge",
            "properties": {"Mode": "Add", "Ratio": 0.3},
        },
        {
            "type": "Erosion2",
            "name": "AdvancedErosion",
            "properties": {
                "Duration": 0.15,
                "Downcutting": 0.3,
                "ErosionScale": 7000.0,
                "Seed": 54321,
            },
        },
        {
            "type": "Snow",
            "name": "SnowLine",
            "properties": {"Duration": 0.7, "SnowLine": 0.7, "Melt": 0.2},
        },
        {
            "type": "SatMap",
            "name": "MountainColors",
            "properties": {"Library": "Rock", "LibraryItem": 1, "Enhance": "Autolevel"},
        },
    ],
    "volcanic_island": [
        {
            "type": "Island",
            "name": "BaseIsland",
            "properties": {"Size": 0.8, "Height": 0.5, "Beaches": 0.7},
        },
        {
            "type": "Volcano",
            "name": "CentralVolcano",
            "properties": {
                "Scale": 0.6,
                "Height": 1.0,
                "Mouth": 0.35,
                "X": 0.5,
                "Y": 0.5,
            },
        },
        {
            "type": "Combine",
            "name": "MergeVolcano",
            "properties": {"Mode": "Max", "Ratio": 0.9},
        },
        {
            "type": "LavaFlow",
            "name": "LavaChannels",
            "properties": {"Temperature": 1200.0, "Viscosity": 0.6},
        },
        {
            "type": "ThermalShatter",
            "name": "ThermalBreakdown",
            "properties": {"Intensity": 0.7, "Scale": 0.4},
        },
        {
            "type": "Beach",
            "name": "CoastalBeaches",
            "properties": {"Width": 150.0, "Slope": 0.15},
        },
        {
            "type": "SatMap",
            "name": "VolcanicColors",
            "properties": {"Library": "Rock", "LibraryItem": 3, "Bias": 0.2},
        },
    ],
    "canyon_system": [
        {
            "type": "Strata",
            "name": "RockLayers",
            "properties": {"Scale": 1.5, "Layers": 12, "Variation": 0.3},
        },
        {
            "type": "Voronoi",
            "name": "CanyonPattern",
            "properties": {"Scale": 0.8, "Jitter": 0.7, "Style": "Euclidean"},
        },
        {
            "type": "Combine",
            "name": "CarveCanyons",
            "properties": {"Mode": "Subtract", "Ratio": 0.6},
        },
        {
            "type": "Erosion2",
            "name": "RiverErosion",
            "properties": {
                "Duration": 0.15,
                "Downcutting": 0.5,
                "ErosionScale": 6000.0,
                "Seed": 98765,
            },
        },
        {
            "type": "Thermal",
            "name": "RockfallErosion",
            "properties": {"Strength": 0.3, "Iterations": 20, "Angle": 38.0},
        },
        {
            "type": "Sediments",
            "name": "ValleyFill",
            "properties": {"Deposition": 0.4, "Sediments": 0.2, "Seed": 24680},
        },
        {
            "type": "SatMap",
            "name": "CanyonColors",
            "properties": {"Library": "Desert", "Enhance": "Equalize"},
        },
    ],
    "coastal_cliffs": [
        {
            "type": "Mountain",
            "name": "CoastalTerrain",
            "properties": {"Scale": 1.0, "Height": 0.6, "Style": "Eroded"},
        },
        {
            "type": "SeaLevel",
            "name": "OceanLevel",
            "properties": {"Level": 0.0, "Precision": 0.95},
        },
        {
            "type": "Coast",
            "name": "Coastline",
            "properties": {"Erosion": 0.7, "Detail": 0.8},
        },
        {
            "type": "Terrace",
            "name": "CliffTerraces",
            "properties": {"Levels": 5, "Uniformity": 0.2, "Sharp": 0.8},
        },
        {
            "type": "Beach",
            "name": "SandyBeaches",
            "properties": {"Width": 200.0, "Slope": 0.1},
        },
        {
            "type": "Erosion2",
            "name": "CoastalErosion",
            "properties": {
                "Duration": 0.15,
                "Downcutting": 0.1,
                "ErosionScale": 5000.0,
                "Seed": 67890,
            },
        },
        {
            "type": "SatMap",
            "name": "CoastalColors",
            "properties": {"Library": "Blue", "LibraryItem": 4, "Reverse": True},
        },
    ],
    "arctic_terrain": [
        {
            "type": "Mountain",
            "name": "ArcticMountains",
            "properties": {"Scale": 1.5, "Height": 0.7, "Style": "Old"},
        },
        {
            "type": "Glacier",
            "name": "IceFlow",
            "properties": {"Scale": 2.0, "Depth": 0.6, "Flow": 0.4},
        },
        {
            "type": "Combine",
            "name": "GlacialCarving",
            "properties": {"Mode": "Subtract", "Ratio": 0.4},
        },
        {
            "type": "Snow",
            "name": "SnowCover",
            "properties": {"Duration": 0.9, "SnowLine": 0.1, "Melt": 0.05},
        },
        {
            "type": "Thermal",
            "name": "FrostShatter",
            "properties": {"Strength": 0.6, "Iterations": 30, "Angle": 32.0},
        },
        {
            "type": "Lakes",
            "name": "GlacialLakes",
            "properties": {"Count": 5, "Size": 0.2},
        },
        {
            "type": "SatMap",
            "name": "ArcticColors",
            "properties": {"Library": "Snow", "Enhance": "Autolevel"},
        },
    ],
    "river_valley": [
        {
            "type": "Mountain",
            "name": "ValleyBase",
            "properties": {"Scale": 1.2, "Height": 0.5, "Style": "Basic"},
        },
        {
            "type": "Rivers",
            "name": "MainRiver",
            "properties": {
                "Width": 0.4,
                "Depth": 0.6,
                "Downcutting": 0.3,
                "Headwaters": 100,
                "RiverValleyWidth": "plus2",
                "RenderSurface": False,
                "Water": 0.3,
                "Seed": 12345,
            },
        },
        {
            "type": "Sediments",
            "name": "Floodplain",
            "properties": {"Deposition": 0.5, "Sediments": 0.3, "Seed": 67890},
        },
        {
            "type": "FractalTerraces",
            "name": "RiverTerraces",
            "properties": {
                "Intensity": 0.5,
                "Spacing": 0.25,
                "Octaves": 12,
                "MacroOctaves": 5,
                "StrataDetails": 0.6,
                "Seed": 98765,
            },
        },
        {
            "type": "Erosion2",
            "name": "ValleyErosion",
            "properties": {
                "Duration": 0.15,
                "Downcutting": 0.3,
                "ErosionScale": 5000.0,
                "Seed": 12345,
            },
        },
        {
            "type": "SatMap",
            "name": "ValleyColors",
            "properties": {
                "Library": "Green",
                "LibraryItem": 2,
                "Enhance": "Autolevel",
            },
        },
    ],
}


def get_node_category(node_type: str) -> str:
    """Get the category of a node type."""
    for category, nodes in NODE_CATEGORIES.items():
        if node_type in nodes:
            return category
    return "unknown"


def get_node_ports(node_type: str) -> Dict[str, List[Dict[str, Any]]]:
    """Get the port definitions for a node type."""
    # Special cases first - check in lowercase
    node_type_lower = node_type.lower()
    if node_type_lower in NODE_PORT_DEFINITIONS:
        port_def = NODE_PORT_DEFINITIONS[node_type_lower]
        assert isinstance(port_def, dict)  # Type assertion for mypy
        return port_def

    # Special cases with specific names
    if node_type == "Combine":
        port_def = NODE_PORT_DEFINITIONS["combine"]
        assert isinstance(port_def, dict)
        return port_def
    elif node_type in ["Portal", "PortalTransmit", "PortalReceive"]:
        port_def = NODE_PORT_DEFINITIONS[node_type.lower()]
        assert isinstance(port_def, dict)
        return port_def
    elif node_type == "Sea":
        port_def = NODE_PORT_DEFINITIONS["sea"]
        assert isinstance(port_def, dict)
        return port_def
    elif node_type == "Rivers":
        port_def = NODE_PORT_DEFINITIONS["rivers"]
        assert isinstance(port_def, dict)
        return port_def
    elif node_type == "FractalTerraces":
        port_def = NODE_PORT_DEFINITIONS["fractalterraces"]
        assert isinstance(port_def, dict)
        return port_def
    elif node_type == "Stratify":
        port_def = NODE_PORT_DEFINITIONS["stratify"]
        assert isinstance(port_def, dict)
        return port_def
    elif node_type == "Crumble":
        port_def = NODE_PORT_DEFINITIONS["crumble"]
        assert isinstance(port_def, dict)
        return port_def
    elif node_type == "Erosion2":
        port_def = NODE_PORT_DEFINITIONS["erosion2"]
        assert isinstance(port_def, dict)
        return port_def

    # Get by category
    category = get_node_category(node_type)
    if category in NODE_PORT_DEFINITIONS:
        port_def = NODE_PORT_DEFINITIONS[category]
        assert isinstance(port_def, dict)
        return port_def

    # Default: one input, one output
    return {
        "inputs": [{"name": "In", "type": "heightfield"}],
        "outputs": [{"name": "Out", "type": "heightfield"}],
    }


def validate_node_properties(node_type: str, properties: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    """Validate node properties against known definitions.

    Returns:
        Tuple of (errors, warnings)
    """
    errors: List[str] = []
    warnings: List[str] = []

    # Get property definitions for this node type
    if node_type in NODE_PROPERTY_DEFINITIONS:
        prop_defs = NODE_PROPERTY_DEFINITIONS[node_type]
        assert isinstance(prop_defs, dict)  # Type assertion for mypy
    else:
        prop_defs = {}

    # Validate each property
    for prop_name, prop_value in properties.items():
        # Check if property is defined for this node
        if prop_name in prop_defs:
            prop_def = prop_defs[prop_name]
        elif prop_name in COMMON_NODE_PROPERTIES:
            prop_def = COMMON_NODE_PROPERTIES[prop_name]
        else:
            warnings.append(f"Unknown property '{prop_name}' for node type {node_type}")
            continue

        # Type validation
        expected_type = prop_def.get("type", "float")

        if expected_type == "float":
            if not isinstance(prop_value, (int, float)):
                errors.append(f"Property '{prop_name}' should be numeric, got {type(prop_value).__name__}")
            elif "range" in prop_def:
                min_val = prop_def["range"].get("min", float("-inf"))
                max_val = prop_def["range"].get("max", float("inf"))
                if not min_val <= prop_value <= max_val:
                    warnings.append(
                        f"Property '{prop_name}' value {prop_value} outside " f"recommended range [{min_val}, {max_val}]"
                    )

        elif expected_type == "int":
            if not isinstance(prop_value, int):
                errors.append(f"Property '{prop_name}' should be integer, got {type(prop_value).__name__}")

        elif expected_type == "bool":
            if not isinstance(prop_value, bool):
                errors.append(f"Property '{prop_name}' should be boolean, got {type(prop_value).__name__}")

        elif expected_type == "enum":
            options = prop_def.get("options", [])
            if prop_value not in options:
                errors.append(f"Property '{prop_name}' value '{prop_value}' not in " f"valid options: {', '.join(options)}")

        elif expected_type == "string":
            if not isinstance(prop_value, str):
                errors.append(f"Property '{prop_name}' should be string, got {type(prop_value).__name__}")

    return errors, warnings


def validate_connection(from_node: Dict[str, Any], to_node: Dict[str, Any], from_port: str, to_port: str) -> Tuple[bool, str]:
    """Validate a connection between two nodes.

    Returns:
        Tuple of (is_valid, error_message)
    """
    # Get port definitions
    from_ports = get_node_ports(from_node["type"])
    to_ports = get_node_ports(to_node["type"])

    # Find the output port
    output_port = None
    for port in from_ports.get("outputs", []):
        if port["name"] == from_port:
            output_port = port
            break

    if not output_port:
        return False, f"Node {from_node['name']} has no output port '{from_port}'"

    # Find the input port
    input_port = None
    for port in to_ports.get("inputs", []):
        if port["name"] == to_port:
            input_port = port
            break

    if not input_port:
        return False, f"Node {to_node['name']} has no input port '{to_port}'"

    # Check type compatibility
    output_type = output_port.get("type", "heightfield")
    input_type = input_port.get("type", "heightfield")

    compatible_types = PORT_COMPATIBILITY.get(output_type, [output_type])
    if input_type not in compatible_types:
        return False, (
            f"Port type mismatch: {from_node['name']}.{from_port} "
            f"({output_type}) cannot connect to {to_node['name']}.{to_port} "
            f"({input_type})"
        )

    return True, ""


def apply_default_properties(node_type: str, properties: Dict[str, Any]) -> Dict[str, Any]:
    """Apply default values for missing properties."""
    result = properties.copy()

    # Get property definitions for this node type
    if node_type in NODE_PROPERTY_DEFINITIONS:
        prop_defs = NODE_PROPERTY_DEFINITIONS[node_type]
        assert isinstance(prop_defs, dict)  # Type assertion for mypy

        # Add defaults for missing properties
        for prop_name, prop_def in prop_defs.items():
            if prop_name not in result and "default" in prop_def:
                result[prop_name] = prop_def["default"]

    # Add common defaults (only if not already present)
    if node_type in VALID_NODE_TYPES:
        # Seed is common to most nodes
        if "Seed" not in result and get_node_category(node_type) in [
            "primitive",
            "terrain",
            "surface",
        ]:
            result["Seed"] = 0

    return result


def create_workflow_from_template(
    template_name: str, start_position: Tuple[float, float] = (25000, 26000)
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Create nodes and connections from a workflow template.

    Args:
        template_name: Name of the workflow template
        start_position: Starting position for node layout

    Returns:
        Tuple of (nodes, connections)
    """
    if template_name not in WORKFLOW_TEMPLATES:
        raise ValueError(f"Unknown template: {template_name}")

    template = WORKFLOW_TEMPLATES[template_name]
    assert isinstance(template, list)  # Type assertion for mypy
    nodes = []
    connections = []

    # Nodes that fail with too many properties
    limited_property_nodes = [
        "Snow",
        "Beach",
        "Coast",
        "Lakes",
        "Glacier",
        "SeaLevel",
        "LavaFlow",
        "ThermalShatter",
        "Ridge",
        "Strata",
        "Voronoi",
        "Terrace",
    ]

    # Create nodes with automatic positioning
    # Use non-sequential IDs like working Gaea2 files (e.g., 183, 668, 427, 281, 294, 949)
    import random

    used_ids = set()
    x_offset = 0
    for i, node_template in enumerate(template):
        # Generate a random 3-digit ID that hasn't been used yet
        node_id = random.randint(100, 999)
        while node_id in used_ids:
            node_id = random.randint(100, 999)
        used_ids.add(node_id)
        node_type = node_template["type"]
        assert isinstance(node_type, str)  # Type assertion for mypy

        # Only apply default properties for nodes that can handle them
        if node_type in limited_property_nodes:
            # Use only the properties defined in the template
            template_props = node_template.get("properties", {})
            assert isinstance(template_props, dict)  # Type assertion for mypy
            properties = template_props.copy()
        else:
            # Apply default properties for other nodes
            template_props = node_template.get("properties", {})
            assert isinstance(template_props, dict)  # Type assertion for mypy
            properties = apply_default_properties(node_type, template_props)

        node = {
            "id": node_id,
            "type": node_type,
            "name": node_template["name"],
            "position": {"x": start_position[0] + x_offset, "y": start_position[1]},
            "properties": properties,
        }
        nodes.append(node)

        # Create connection to previous node (skip for Portal nodes)
        if i > 0:
            prev_node = nodes[i - 1]

            # Skip connections for Portal nodes - they don't follow linear flow
            if node["type"] in [
                "PortalTransmit",
                "PortalReceive",
                "Portal",
            ] or prev_node[
                "type"
            ] in ["PortalTransmit", "PortalReceive", "Portal"]:
                continue

            # Handle special connection cases
            if node["type"] == "Combine":
                # Combine nodes need special handling
                # For sequential templates, we assume:
                # - Primary input (In) comes from node i-2 (the node before the previous)
                # - Secondary input (Input2) comes from node i-1 (the previous node)

                # Connect previous node to Input2
                connections.append(
                    {
                        "from_node": prev_node["id"],
                        "to_node": node["id"],
                        "from_port": "Out",
                        "to_port": "Input2",
                    }
                )

                # Connect node before previous to primary In (if it exists)
                if i >= 2:
                    connections.append(
                        {
                            "from_node": nodes[i - 2]["id"],
                            "to_node": node["id"],
                            "from_port": "Out",
                            "to_port": "In",
                        }
                    )
            else:
                # Normal connection
                connections.append(
                    {
                        "from_node": prev_node["id"],
                        "to_node": node["id"],
                        "from_port": "Out",
                        "to_port": "In",
                    }
                )

        x_offset += 500  # Space nodes horizontally

    # Handle manual connections for Portal-based templates
    if template_name == "modular_portal_terrain":
        # Find node IDs by name for Portal connections
        node_map = {node["name"]: node["id"] for node in nodes}

        # Manual connections for the portal workflow
        portal_connections = [
            # Mountain -> Portal Transmit
            {
                "from_node": node_map["PrimaryShape"],
                "to_node": node_map["ShapePortal"],
                "from_port": "Out",
                "to_port": "In",
            },
            # Portal Receive -> Erosion
            {
                "from_node": node_map["ShapeForErosion"],
                "to_node": node_map["DetailedErosion"],
                "from_port": "Out",
                "to_port": "In",
            },
            # Erosion -> Portal Transmit
            {
                "from_node": node_map["DetailedErosion"],
                "to_node": node_map["ErodedPortal"],
                "from_port": "Out",
                "to_port": "In",
            },
            # Portal Receive -> Slope
            {
                "from_node": node_map["ShapeForAnalysis"],
                "to_node": node_map["SlopeAnalysis"],
                "from_port": "Out",
                "to_port": "In",
            },
            # Portal Receive -> SatMap
            {
                "from_node": node_map["FinalTerrain"],
                "to_node": node_map["TerrainColors"],
                "from_port": "Out",
                "to_port": "In",
            },
        ]
        connections.extend(portal_connections)

    # Export nodes are not required - many working Gaea2 files don't have them

    return nodes, connections


def validate_gaea2_project(project_data: Dict[str, Any]) -> Dict[str, Any]:
    """Comprehensive validation of a Gaea 2 project structure.

    Returns:
        Dictionary with validation results including:
        - valid: bool
        - errors: List[str]
        - warnings: List[str]
        - node_count: int
        - connection_count: int
        - suggestions: List[str]
    """
    # Try to use optimized validator for better performance
    try:
        from .gaea2_optimized_validator import get_optimized_validator

        use_optimized = True
        optimized_validator = get_optimized_validator()
    except ImportError:
        use_optimized = False

    errors: List[str] = []
    warnings: List[str] = []
    suggestions: List[str] = []

    # Check basic structure
    if "$id" not in project_data:
        errors.append("Missing required field: $id")

    if "Assets" not in project_data:
        errors.append("Missing required field: Assets")
        return {
            "valid": False,
            "errors": errors,
            "warnings": warnings,
            "suggestions": suggestions,
            "node_count": 0,
            "connection_count": 0,
        }

    # Navigate to terrain data
    try:
        terrain = project_data["Assets"]["$values"][0]["Terrain"]
    except (KeyError, IndexError, TypeError):
        errors.append("Invalid project structure: Cannot find Terrain data")
        return {
            "valid": False,
            "errors": errors,
            "warnings": warnings,
            "suggestions": suggestions,
            "node_count": 0,
            "connection_count": 0,
        }

    # Validate nodes
    nodes = terrain.get("Nodes", {})
    node_count = 0
    node_ids = set()
    node_types_used = set()

    # Prepare nodes for batch validation if using optimized validator
    if use_optimized:
        nodes_for_validation = []

    for node_id, node_data in nodes.items():
        if not isinstance(node_data, dict):
            continue

        node_count += 1
        node_ids.add(int(node_id))

        # Extract node type
        type_field = node_data.get("$type", "")
        if type_field:
            # Format: "QuadSpinner.Gaea.Nodes.Mountain, Gaea.Nodes"
            parts = type_field.split(".")
            if len(parts) >= 4:
                node_type = parts[3].split(",")[0]
                node_types_used.add(node_type)

                # Validate node type
                if node_type not in VALID_NODE_TYPES:
                    warnings.append(f"Unknown node type: {node_type}")

                # Extract properties
                props = {}
                for key, value in node_data.items():
                    if not key.startswith("$") and key not in [
                        "Name",
                        "Position",
                        "Ports",
                        "Modifiers",
                        "SnapIns",
                    ]:
                        props[key] = value

                if use_optimized:
                    # Collect node for batch validation
                    nodes_for_validation.append(
                        {
                            "id": int(node_id),
                            "type": node_type,
                            "name": node_data.get("Name", f"Node_{node_id}"),
                            "properties": props,
                        }
                    )
                else:
                    # Use regular validation
                    prop_errors, prop_warnings = validate_node_properties(node_type, props)
                    errors.extend(prop_errors)
                    warnings.extend(prop_warnings)

    # Validate connections
    connection_count = 0
    connections_found = []

    # Look for connections in port records
    for node_id, node_data in nodes.items():
        if isinstance(node_data, dict) and "Ports" in node_data:
            ports = node_data["Ports"]
            if isinstance(ports, dict) and "$values" in ports:
                for port in ports["$values"]:
                    if isinstance(port, dict) and "Record" in port:
                        record = port["Record"]
                        if isinstance(record, dict):
                            connection_count += 1
                            connections_found.append(
                                {
                                    "from_node": record.get("From"),
                                    "to_node": record.get("To"),
                                    "from_port": record.get("FromPort", "Out"),
                                    "to_port": record.get("ToPort", "In"),
                                }
                            )

    # Perform batch validation if using optimized validator
    if use_optimized and nodes_for_validation:
        # Run optimized validation
        validation_result = optimized_validator.validate_workflow(nodes_for_validation, connections_found)
        errors.extend(validation_result.get("errors", []))
        warnings.extend(validation_result.get("warnings", []))

        # Update with fixed nodes if any
        if validation_result.get("fixed_nodes"):
            # Store fixed nodes for potential future use
            pass
    else:
        # Regular connection validation
        for conn in connections_found:
            if conn["from_node"] not in node_ids:
                errors.append(f"Connection references non-existent node: {conn['from_node']}")
            if conn["to_node"] not in node_ids:
                errors.append(f"Connection references non-existent node: {conn['to_node']}")

    # Generate suggestions
    if node_count == 0:
        suggestions.append("Add some nodes to create terrain")
    elif "Mountain" not in node_types_used and "Terrain" not in node_types_used:
        suggestions.append("Consider adding a terrain generator node (Mountain, Island, etc.)")

    if "Erosion" not in node_types_used and node_count > 0:
        suggestions.append("Add an Erosion node for more realistic terrain")

    if connection_count == 0 and node_count > 1:
        suggestions.append("Connect your nodes to create a processing flow")

    # Determine overall validity
    valid = len(errors) == 0

    result = {
        "valid": valid,
        "errors": errors,
        "warnings": warnings,
        "suggestions": suggestions,
        "node_count": node_count,
        "connection_count": connection_count,
        "node_types": list(node_types_used),
    }

    # Add performance stats if using optimized validator
    if use_optimized and hasattr(optimized_validator, "_get_cache_stats"):
        result["performance_stats"] = optimized_validator._get_cache_stats()

    return result


# Export all public functions and constants
__all__ = [
    "VALID_NODE_TYPES",
    "NODE_CATEGORIES",
    "NODE_PROPERTY_DEFINITIONS",
    "WORKFLOW_TEMPLATES",
    "validate_node_properties",
    "validate_connection",
    "validate_gaea2_project",
    "apply_default_properties",
    "create_workflow_from_template",
    "get_node_category",
    "get_node_ports",
]
