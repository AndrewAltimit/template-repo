#!/usr/bin/env python3
"""Gaea 2 Knowledge Graph - Enhanced node relationships and intelligent suggestions

This module implements a knowledge graph structure to improve the reliability and
intelligence of the Gaea 2 MCP tool by:
1. Capturing relationships between nodes
2. Understanding common workflows and patterns
3. Providing intelligent suggestions and validation
4. Detecting incompatible combinations
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class RelationType(Enum):
    """Types of relationships between Gaea nodes"""

    REQUIRES = "requires"  # Node A requires Node B to function properly
    ENHANCES = "enhances"  # Node A enhances the output of Node B
    CONFLICTS = "conflicts"  # Node A conflicts with Node B
    FOLLOWS = "follows"  # Node A typically follows Node B in workflow
    PRECEDES = "precedes"  # Node A typically precedes Node B
    COMBINES_WITH = "combines_with"  # Node A combines well with Node B
    ALTERNATIVE_TO = "alternative_to"  # Node A is an alternative to Node B
    PROVIDES_DATA_FOR = "provides_data_for"  # Node A provides data for Node B
    CONSUMES_DATA_FROM = "consumes_data_from"  # Node A consumes data from Node B


@dataclass
class NodeRelationship:
    """Represents a relationship between two nodes"""

    from_node: str
    to_node: str
    relation_type: RelationType
    strength: float = 1.0  # 0.0 to 1.0, how strong the relationship is
    description: str = ""
    conditions: Dict[str, Any] = field(default_factory=dict)  # Conditions for the relationship


@dataclass
class NodePattern:
    """Represents a common usage pattern for nodes"""

    name: str
    description: str
    nodes: List[str]
    connections: List[Tuple[str, str]]  # (from_node, to_node) pairs
    tags: List[str] = field(default_factory=list)
    frequency: float = 1.0  # How commonly this pattern is used


@dataclass
class PropertyConstraint:
    """Constraints between node properties"""

    node_a: str
    property_a: str
    node_b: str
    property_b: str
    constraint_type: str  # "equals", "less_than", "greater_than", "proportional"
    factor: float = 1.0
    description: str = ""


class Gaea2KnowledgeGraph:
    """Knowledge graph for Gaea 2 nodes and their relationships"""

    def __init__(self):
        self.relationships: List[NodeRelationship] = []
        self.patterns: List[NodePattern] = []
        self.property_constraints: List[PropertyConstraint] = []
        self.node_categories: Dict[str, str] = {}
        self.node_descriptions: Dict[str, str] = {}
        self.common_properties: Dict[str, List[str]] = {}
        self.blend_mode_purposes: Dict[str, str] = {}

        # Initialize with known relationships
        self._initialize_relationships()
        self._initialize_patterns()
        self._initialize_constraints()
        self._initialize_categories()
        self._initialize_blend_modes()

    def _initialize_relationships(self):
        """Initialize known node relationships"""
        # Terrain generation relationships
        self.add_relationship(
            "Mountain",
            "Erosion",
            RelationType.PRECEDES,
            0.9,
            "Mountains are typically eroded for realism",
        )
        self.add_relationship(
            "Erosion",
            "Mountain",
            RelationType.REQUIRES,
            1.0,
            "Erosion requires terrain input",
        )
        self.add_relationship(
            "Erosion",
            "Rivers",
            RelationType.ENHANCES,
            0.8,
            "Erosion creates natural paths for rivers",
        )
        self.add_relationship(
            "Rivers",
            "Erosion",
            RelationType.FOLLOWS,
            0.7,
            "Rivers often follow erosion patterns",
        )

        # Erosion data outputs
        self.add_relationship(
            "Erosion",
            "Wear",
            RelationType.PROVIDES_DATA_FOR,
            1.0,
            "Erosion produces Wear data map",
        )
        self.add_relationship(
            "Erosion",
            "Flow",
            RelationType.PROVIDES_DATA_FOR,
            1.0,
            "Erosion produces Flow data map",
        )
        self.add_relationship(
            "Erosion",
            "Deposits",
            RelationType.PROVIDES_DATA_FOR,
            1.0,
            "Erosion produces Deposits data map",
        )

        # Thermal erosion relationships
        self.add_relationship(
            "Erosion",
            "Thermal",
            RelationType.PRECEDES,
            0.8,
            "Erosion followed by thermal for combined effect",
        )
        self.add_relationship(
            "Thermal",
            "Erosion",
            RelationType.PRECEDES,
            0.8,
            "Thermal can also precede erosion",
        )
        self.add_relationship(
            "Thermal",
            "Thermal2",
            RelationType.ALTERNATIVE_TO,
            1.0,
            "Thermal2 is an alternative algorithm",
        )

        # Snow and altitude relationships
        self.add_relationship(
            "Snow",
            "Mountain",
            RelationType.FOLLOWS,
            0.8,
            "Snow is typically added to mountain peaks",
        )
        self.add_relationship(
            "Snow",
            "Slope",
            RelationType.CONSUMES_DATA_FROM,
            0.9,
            "Snow uses slope data for realistic distribution",
        )

        # Water system relationships
        self.add_relationship(
            "Rivers",
            "Lake",
            RelationType.COMBINES_WITH,
            0.8,
            "Rivers and lakes create comprehensive water systems",
        )
        self.add_relationship(
            "Lake",
            "Rivers",
            RelationType.COMBINES_WITH,
            0.8,
            "Lakes work with rivers for water systems",
        )

        # Texture and color relationships
        self.add_relationship(
            "SatMap",
            "TextureBase",
            RelationType.COMBINES_WITH,
            0.9,
            "SatMap and TextureBase work together for realistic texturing",
        )
        self.add_relationship(
            "SatMap",
            "Slope",
            RelationType.CONSUMES_DATA_FROM,
            0.8,
            "SatMap uses slope data for texture distribution",
        )
        self.add_relationship(
            "CLUTer",
            "Flow",
            RelationType.CONSUMES_DATA_FROM,
            0.9,
            "CLUTer uses flow maps for gradient coloring",
        )
        self.add_relationship(
            "CLUTer",
            "Wear",
            RelationType.CONSUMES_DATA_FROM,
            0.9,
            "CLUTer uses wear maps for edge coloring",
        )
        self.add_relationship(
            "CLUTer",
            "Deposits",
            RelationType.CONSUMES_DATA_FROM,
            0.9,
            "CLUTer uses deposit maps for sediment coloring",
        )

        # Analysis node relationships
        self.add_relationship(
            "Slope",
            "Any",
            RelationType.PROVIDES_DATA_FOR,
            0.9,
            "Slope analysis provides data for many nodes",
        )
        self.add_relationship(
            "Curvature",
            "Any",
            RelationType.PROVIDES_DATA_FOR,
            0.8,
            "Curvature data is useful for various effects",
        )
        self.add_relationship(
            "Height",
            "Any",
            RelationType.PROVIDES_DATA_FOR,
            0.8,
            "Height maps provide altitude-based masking",
        )
        self.add_relationship(
            "FlowMap",
            "FlowMapClassic",
            RelationType.ALTERNATIVE_TO,
            1.0,
            "FlowMapClassic is legacy version of FlowMap",
        )

        # Masking relationships
        self.add_relationship(
            "Slope",
            "Mask",
            RelationType.PROVIDES_DATA_FOR,
            0.9,
            "Slope creates masks for selective processing",
        )
        self.add_relationship(
            "Height",
            "Mask",
            RelationType.PROVIDES_DATA_FOR,
            0.9,
            "Height creates altitude-based masks",
        )

        # Enhancement nodes
        self.add_relationship(
            "Autolevel",
            "Erosion",
            RelationType.FOLLOWS,
            0.8,
            "Autolevel enhances erosion data outputs",
        )
        self.add_relationship(
            "Equalize",
            "Erosion",
            RelationType.FOLLOWS,
            0.7,
            "Equalize increases contrast in erosion maps",
        )

        # Warping relationships
        self.add_relationship(
            "Warp",
            "Any",
            RelationType.ENHANCES,
            0.7,
            "Warp adds organic variation to any input",
        )
        self.add_relationship(
            "DirectionalWarp",
            "Warp",
            RelationType.ALTERNATIVE_TO,
            0.9,
            "DirectionalWarp provides controlled warping",
        )

        # Alternative erosion nodes
        self.add_relationship(
            "Erosion",
            "EasyErosion",
            RelationType.ALTERNATIVE_TO,
            0.9,
            "EasyErosion is simplified version",
        )
        self.add_relationship(
            "Erosion",
            "Wizard",
            RelationType.ALTERNATIVE_TO,
            0.8,
            "Wizard provides automated multi-pass erosion",
        )

        # Conflicting relationships
        self.add_relationship(
            "Erosion",
            "Erosion2",
            RelationType.CONFLICTS,
            0.9,
            "Multiple erosion nodes can over-process terrain",
        )

        # Portal relationships
        self.add_relationship(
            "PortalTransmit",
            "PortalReceive",
            RelationType.REQUIRES,
            1.0,
            "Portal transmit requires matching receive node",
        )
        self.add_relationship(
            "Chokepoint",
            "Portal",
            RelationType.ALTERNATIVE_TO,
            0.8,
            "Chokepoint can be converted to Portal for organization",
        )

        # Combine node relationships
        self.add_relationship(
            "Combine",
            "Any",
            RelationType.FOLLOWS,
            0.8,
            "Combine merges multiple terrain inputs",
        )

        # Utility relationships
        self.add_relationship(
            "Accumulator",
            "Snow",
            RelationType.CONSUMES_DATA_FROM,
            0.9,
            "Accumulator collects Snow mask",
        )
        self.add_relationship(
            "Accumulator",
            "Lake",
            RelationType.CONSUMES_DATA_FROM,
            0.9,
            "Accumulator collects Lake mask",
        )
        self.add_relationship(
            "Accumulator",
            "Debris",
            RelationType.CONSUMES_DATA_FROM,
            0.9,
            "Accumulator collects Debris mask",
        )

        # Seamless tiling
        self.add_relationship(
            "Seamless",
            "Repeat",
            RelationType.PRECEDES,
            0.9,
            "Seamless prepares terrain for tiling with Repeat",
        )

        # Canyon relationships
        self.add_relationship(
            "Canyon",
            "Stratify",
            RelationType.PRECEDES,
            0.9,
            "Canyon benefits from rock stratification",
        )
        self.add_relationship(
            "Canyon",
            "FractalTerraces",
            RelationType.COMBINES_WITH,
            0.8,
            "Adds realistic rock layers to canyon",
        )

        # Crater relationships
        self.add_relationship(
            "Crater",
            "Combine",
            RelationType.PRECEDES,
            0.7,
            "Craters often combined with base terrain",
        )
        self.add_relationship(
            "CraterField",
            "Erosion",
            RelationType.PRECEDES,
            0.6,
            "Crater fields can be eroded for age",
        )

        # Island relationships
        self.add_relationship(
            "Island",
            "Sea",
            RelationType.COMBINES_WITH,
            0.9,
            "Islands naturally combine with sea/water",
        )
        self.add_relationship(
            "Island",
            "Beach",
            RelationType.PRECEDES,
            0.8,
            "Islands benefit from beach/coast details",
        )

        # Wizard relationships
        self.add_relationship(
            "Mountain",
            "Wizard",
            RelationType.PRECEDES,
            0.8,
            "Wizard provides simplified erosion for any terrain",
        )
        self.add_relationship(
            "Wizard",
            "Erosion",
            RelationType.ALTERNATIVE_TO,
            0.9,
            "Wizard is easier alternative to Erosion",
        )
        self.add_relationship(
            "Wizard",
            "Wizard2",
            RelationType.ALTERNATIVE_TO,
            1.0,
            "Wizard2 is updated version of Wizard",
        )

        # HydroFix relationships
        self.add_relationship(
            "Any",
            "HydroFix",
            RelationType.PRECEDES,
            0.7,
            "HydroFix creates coherent water flows",
        )
        self.add_relationship(
            "HydroFix",
            "FlowMap",
            RelationType.PRECEDES,
            0.9,
            "HydroFix improves FlowMap generation",
        )
        self.add_relationship(
            "HydroFix",
            "Rivers",
            RelationType.PRECEDES,
            0.8,
            "HydroFix helps river placement",
        )

        # Surface detail relationships
        self.add_relationship(
            "Any",
            "Outcrops",
            RelationType.COMBINES_WITH,
            0.7,
            "Outcrops add rock protrusions to any terrain",
        )
        self.add_relationship(
            "Any",
            "Stones",
            RelationType.COMBINES_WITH,
            0.7,
            "Stones add surface detail to terrain",
        )
        self.add_relationship(
            "Any",
            "Bomber",
            RelationType.COMBINES_WITH,
            0.6,
            "Bomber stamps patterns across terrain",
        )

        # Stratify relationships
        self.add_relationship(
            "Stratify",
            "Terraces",
            RelationType.ALTERNATIVE_TO,
            0.8,
            "Stratify creates more natural layers than Terraces",
        )
        self.add_relationship(
            "Mountain",
            "Stratify",
            RelationType.COMBINES_WITH,
            0.7,
            "Stratify adds rock layers to mountains",
        )

        # Blur and sharpen relationships
        self.add_relationship(
            "Any",
            "Blur",
            RelationType.ENHANCES,
            0.6,
            "Blur softens sharp features",
        )
        self.add_relationship(
            "Blur",
            "Sharpen",
            RelationType.CONFLICTS,
            0.8,
            "Blur and Sharpen have opposite effects",
        )

        # Mask node relationships (Gaea 2 specific)
        self.add_relationship(
            "Any",
            "Mask",
            RelationType.FOLLOWS,
            0.9,
            "Mask node for post-process masking (more efficient)",
        )
        self.add_relationship(
            "Erosion",
            "Mask",
            RelationType.PRECEDES,
            0.8,
            "Apply effects before masking for efficiency",
        )

        # Data map enhancement relationships
        self.add_relationship(
            "Wear",
            "CLUTer",
            RelationType.PRECEDES,
            0.9,
            "Wear maps create edge coloring in CLUTer",
        )
        self.add_relationship(
            "Deposits",
            "CLUTer",
            RelationType.PRECEDES,
            0.9,
            "Deposit maps show sediment in CLUTer",
        )
        self.add_relationship(
            "Flow",
            "CLUTer",
            RelationType.PRECEDES,
            0.9,
            "Flow maps indicate moisture in CLUTer",
        )

        # Splat relationships
        self.add_relationship(
            "Any",
            "Splat",
            RelationType.PRECEDES,
            0.7,
            "Splat encodes heightfields to RGB channels",
        )
        self.add_relationship(
            "Splat",
            "RGBMerge",
            RelationType.ALTERNATIVE_TO,
            0.8,
            "Splat similar to RGBMerge for channel encoding",
        )

        # Route automation relationships
        self.add_relationship(
            "Any",
            "Route",
            RelationType.COMBINES_WITH,
            0.5,
            "Route provides conditional flow control",
        )

        # Rock surface workflows
        self.add_relationship(
            "Any",
            "RockMap",
            RelationType.PRECEDES,
            0.8,
            "RockMap derives rock placement data",
        )
        self.add_relationship(
            "RockMap",
            "Outcrops",
            RelationType.PRECEDES,
            0.9,
            "RockMap guides Outcrop placement",
        )

        # Sand/desert relationships
        self.add_relationship(
            "DuneSea",
            "Sand",
            RelationType.COMBINES_WITH,
            0.9,
            "DuneSea and Sand create complete desert",
        )
        self.add_relationship(
            "Sand",
            "Warp",
            RelationType.FOLLOWS,
            0.8,
            "Warp adds organic variation to sand",
        )

        # Performance optimization relationships
        self.add_relationship(
            "Edge",
            "Bomber",
            RelationType.PRECEDES,
            0.7,
            "Edge controls Bomber stamp placement",
        )
        self.add_relationship(
            "Clip",
            "Bomber",
            RelationType.PRECEDES,
            0.7,
            "Clip controls Bomber stamp placement",
        )

    def _initialize_patterns(self):
        """Initialize common workflow patterns"""
        # Basic terrain workflow
        self.add_pattern(
            "Basic Terrain",
            "Simple terrain generation with erosion",
            ["Mountain", "Erosion", "TextureBase", "SatMap"],
            [
                ("Mountain", "Erosion"),
                ("Erosion", "TextureBase"),
                ("TextureBase", "SatMap"),
            ],
            ["beginner", "quick", "terrain"],
        )

        # Advanced mountain workflow
        self.add_pattern(
            "Realistic Mountain",
            "Detailed mountain with multiple erosion passes and snow",
            ["Mountain", "Erosion", "Rivers", "Snow", "SatMap"],
            [
                ("Mountain", "Erosion"),
                ("Erosion", "Rivers"),
                ("Rivers", "Snow"),
                ("Snow", "SatMap"),
            ],
            ["advanced", "mountain", "realistic"],
        )

        # Desert workflow
        self.add_pattern(
            "Desert Terrain",
            "Desert with dunes and wind erosion",
            ["DuneSea", "Erosion", "Sand", "SatMap"],
            [("DuneSea", "Erosion"), ("Erosion", "Sand"), ("Sand", "SatMap")],
            ["desert", "dunes", "arid"],
        )

        # Volcanic workflow
        self.add_pattern(
            "Volcanic Landscape",
            "Volcanic terrain with lava flows",
            ["Volcano", "Thermal", "Erosion", "SatMap"],
            [("Volcano", "Thermal"), ("Thermal", "Erosion"), ("Erosion", "SatMap")],
            ["volcanic", "lava", "thermal"],
        )

        # Analysis workflow
        self.add_pattern(
            "Terrain Analysis",
            "Extract terrain data for texturing",
            ["Mountain", "Slope", "Curvature", "FlowMap", "SatMap"],
            [
                ("Mountain", "Slope"),
                ("Mountain", "Curvature"),
                ("Mountain", "FlowMap"),
                ("Slope", "SatMap"),
            ],
            ["analysis", "data", "texturing"],
        )

        # Data-driven texturing
        self.add_pattern(
            "Data-Driven Texturing",
            "Use erosion outputs for realistic coloring",
            ["Mountain", "Erosion", "Autolevel", "CLUTer"],
            [
                ("Mountain", "Erosion"),
                ("Erosion", "Autolevel"),
                ("Autolevel", "CLUTer"),
            ],
            ["texturing", "erosion-based", "data-driven"],
        )

        # Combined erosion
        self.add_pattern(
            "Combined Erosion",
            "Chain multiple erosion types for realism",
            ["Mountain", "Erosion", "Thermal", "Rivers", "SatMap"],
            [
                ("Mountain", "Erosion"),
                ("Erosion", "Thermal"),
                ("Thermal", "Rivers"),
                ("Rivers", "SatMap"),
            ],
            ["erosion", "combined", "realistic"],
        )

        # Water system
        self.add_pattern(
            "Complete Water System",
            "Rivers and lakes with proper flow",
            ["Mountain", "Erosion", "Rivers", "Lake", "Combine", "SatMap"],
            [
                ("Mountain", "Erosion"),
                ("Erosion", "Rivers"),
                ("Erosion", "Lake"),
                ("Rivers", "Combine"),
                ("Lake", "Combine"),
                ("Combine", "SatMap"),
            ],
            ["water", "rivers", "lakes"],
        )

        # Selective processing
        self.add_pattern(
            "Selective Erosion",
            "Masked erosion using slope data",
            ["Mountain", "Slope", "Erosion", "SatMap"],
            [
                ("Mountain", "Slope"),
                ("Mountain", "Erosion"),
                ("Slope", "Erosion"),
                ("Erosion", "SatMap"),
            ],
            ["selective", "masked", "controlled"],
        )

        # Portal-based workflow
        self.add_pattern(
            "Modular Portal Workflow",
            "Use portals for organization",
            [
                "Mountain",
                "PortalTransmit",
                "PortalReceive",
                "Erosion",
                "PortalTransmit",
                "PortalReceive",
                "SatMap",
            ],
            [
                ("Mountain", "PortalTransmit"),
                ("PortalReceive", "Erosion"),
                ("Erosion", "PortalTransmit"),
                ("PortalReceive", "SatMap"),
            ],
            ["portal", "modular", "organized"],
        )

        # Canyon workflow
        self.add_pattern(
            "Stratified Canyon",
            "Canyon with rock layers",
            ["Canyon", "Stratify", "FractalTerraces", "Erosion", "SatMap"],
            [
                ("Canyon", "Stratify"),
                ("Stratify", "FractalTerraces"),
                ("FractalTerraces", "Erosion"),
                ("Erosion", "SatMap"),
            ],
            ["canyon", "stratified", "layered"],
        )

        # Arctic terrain
        self.add_pattern(
            "Arctic Landscape",
            "Glaciated terrain with snow",
            ["Mountain", "Glacier", "Snow", "Snowfield", "SatMap"],
            [
                ("Mountain", "Glacier"),
                ("Glacier", "Snow"),
                ("Snow", "Snowfield"),
                ("Snowfield", "SatMap"),
            ],
            ["arctic", "glacier", "snow"],
        )

        # Professional multi-effect workflow
        self.add_pattern(
            "Professional Mountain",
            "Complex workflow with post-process masking",
            ["Mountain", "Erosion", "Sandstone", "Thermal2", "Mask", "SatMap"],
            [
                ("Mountain", "Erosion"),
                ("Erosion", "Sandstone"),
                ("Sandstone", "Thermal2"),
                ("Thermal2", "Mask"),
                ("Mountain", "Mask"),  # Connect to pre-effect for masking
                ("Mask", "SatMap"),
            ],
            ["professional", "complex", "masked"],
        )

        # Wizard-based simplified workflow
        self.add_pattern(
            "Quick Erosion",
            "Simplified erosion using Wizard node",
            ["Mountain", "Wizard", "TextureBase", "SatMap"],
            [
                ("Mountain", "Wizard"),
                ("Wizard", "TextureBase"),
                ("TextureBase", "SatMap"),
            ],
            ["quick", "simple", "wizard"],
        )

        # Island workflow
        self.add_pattern(
            "Tropical Island",
            "Island with beaches and vegetation",
            ["Island", "Erosion", "Beach", "Sea", "Combine", "SatMap"],
            [
                ("Island", "Erosion"),
                ("Erosion", "Beach"),
                ("Island", "Sea"),
                ("Beach", "Combine"),
                ("Sea", "Combine"),
                ("Combine", "SatMap"),
            ],
            ["island", "tropical", "beach"],
        )

        # Rock surface detail
        self.add_pattern(
            "Detailed Rock Surface",
            "Enhanced rock detail workflow",
            ["Mountain", "RockMap", "Outcrops", "Stratify", "Combine"],
            [
                ("Mountain", "RockMap"),
                ("RockMap", "Outcrops"),
                ("Mountain", "Stratify"),
                ("Outcrops", "Combine"),
                ("Stratify", "Combine"),
            ],
            ["rock", "detail", "surface"],
        )

        # HydroFix water flow
        self.add_pattern(
            "Coherent Water Flow",
            "Improved water flow patterns",
            ["Mountain", "HydroFix", "FlowMap", "Rivers", "Lake", "SatMap"],
            [
                ("Mountain", "HydroFix"),
                ("HydroFix", "FlowMap"),
                ("FlowMap", "Rivers"),
                ("FlowMap", "Lake"),
                ("Rivers", "SatMap"),
            ],
            ["water", "hydrofix", "flow"],
        )

        # Crater impact workflow
        self.add_pattern(
            "Impact Crater",
            "Realistic impact crater integration",
            ["Mountain", "Crater", "Combine", "Erosion", "Debris", "SatMap"],
            [
                ("Mountain", "Combine"),
                ("Crater", "Combine"),
                ("Combine", "Erosion"),
                ("Erosion", "Debris"),
                ("Debris", "SatMap"),
            ],
            ["crater", "impact", "debris"],
        )

        # Advanced texturing with data maps
        self.add_pattern(
            "Erosion Data Texturing",
            "Use all erosion outputs for texturing",
            ["Mountain", "Erosion", "Autolevel", "CLUTer", "Combine", "SatMap"],
            [
                ("Mountain", "Erosion"),
                ("Erosion", "Autolevel"),  # Enhance Wear/Flow/Deposits
                ("Autolevel", "CLUTer"),
                ("CLUTer", "Combine"),
                ("Mountain", "Combine"),
                ("Combine", "SatMap"),
            ],
            ["texturing", "data-maps", "advanced"],
        )

        # Seamless terrain pattern
        self.add_pattern(
            "Tileable Terrain",
            "Create seamless tileable terrain",
            ["Mountain", "Erosion", "Seamless", "Repeat", "SatMap"],
            [
                ("Mountain", "Erosion"),
                ("Erosion", "Seamless"),
                ("Seamless", "Repeat"),
                ("Repeat", "SatMap"),
            ],
            ["seamless", "tileable", "repeat"],
        )

        # Performance preview workflow
        self.add_pattern(
            "Fast Preview",
            "Quick preview with reduced settings",
            ["Mountain", "EasyErosion", "SatMap"],
            [("Mountain", "EasyErosion"), ("EasyErosion", "SatMap")],
            ["preview", "fast", "performance"],
        )

    def _initialize_constraints(self):
        """Initialize property constraints between nodes"""
        # Erosion feature scale should match terrain scale
        self.add_constraint(
            "Mountain",
            "Scale",
            "Erosion",
            "FeatureScale",
            "proportional",
            2000.0,
            "Erosion feature scale should be ~2000x terrain scale",
        )

        # Snow altitude should be relative to mountain height
        self.add_constraint(
            "Mountain",
            "Height",
            "Snow",
            "Altitude",
            "proportional",
            0.8,
            "Snow altitude typically at 80% of mountain height",
        )

        # River depth relative to erosion strength
        self.add_constraint(
            "Erosion",
            "Strength",
            "Rivers",
            "Depth",
            "proportional",
            0.8,
            "River depth correlates with erosion strength",
        )

        # Warp size relative to terrain scale
        self.add_constraint(
            "Mountain",
            "Scale",
            "Warp",
            "Size",
            "proportional",
            1.0,
            "Warp size should match terrain scale",
        )

        # Stratify spacing based on terrain height
        self.add_constraint(
            "Mountain",
            "Height",
            "Stratify",
            "Spacing",
            "proportional",
            0.1,
            "Stratify spacing relative to terrain height",
        )

        # Bomber scale relative to terrain
        self.add_constraint(
            "Any",
            "Scale",
            "Bomber",
            "Scale",
            "proportional",
            0.5,
            "Bomber pattern scale relative to terrain",
        )

        # Thermal angle based on rock softness
        self.add_constraint(
            "Erosion",
            "RockSoftness",
            "Thermal",
            "Angle",
            "inversely_proportional",
            45.0,
            "Softer rock allows steeper thermal angles",
        )

        # Lake level relative to terrain height
        self.add_constraint(
            "Mountain",
            "Height",
            "Lake",
            "Level",
            "proportional",
            0.3,
            "Lake level typically at 30% of terrain height",
        )

        # Glacier coverage based on altitude
        self.add_constraint(
            "Mountain",
            "Height",
            "Glacier",
            "Coverage",
            "proportional",
            0.7,
            "Glacier coverage increases with altitude",
        )

        # Sand accumulation in low areas
        self.add_constraint(
            "Canyon",
            "Depth",
            "Sand",
            "Amount",
            "proportional",
            0.6,
            "Sand accumulates in deeper canyon areas",
        )

        # Outcrop size relative to terrain
        self.add_constraint(
            "Mountain",
            "Scale",
            "Outcrops",
            "Size",
            "proportional",
            0.3,
            "Outcrop size proportional to terrain scale",
        )

        # Wizard bulk protection
        self.add_constraint(
            "Mountain",
            "Height",
            "Wizard",
            "Bulk",
            "proportional",
            0.5,
            "Higher terrains need more bulk protection",
        )

    def add_relationship(
        self,
        from_node: str,
        to_node: str,
        relation_type: RelationType,
        strength: float = 1.0,
        description: str = "",
        conditions: Optional[Dict[str, Any]] = None,
    ):
        """Add a relationship between nodes"""
        rel = NodeRelationship(
            from_node=from_node,
            to_node=to_node,
            relation_type=relation_type,
            strength=strength,
            description=description,
            conditions=conditions or {},
        )
        self.relationships.append(rel)

    def add_pattern(
        self,
        name: str,
        description: str,
        nodes: List[str],
        connections: List[Tuple[str, str]],
        tags: Optional[List[str]] = None,
    ):
        """Add a workflow pattern"""
        pattern = NodePattern(
            name=name,
            description=description,
            nodes=nodes,
            connections=connections,
            tags=tags or [],
        )
        self.patterns.append(pattern)

    def add_constraint(
        self,
        node_a: str,
        property_a: str,
        node_b: str,
        property_b: str,
        constraint_type: str,
        factor: float = 1.0,
        description: str = "",
    ):
        """Add a property constraint between nodes"""
        constraint = PropertyConstraint(
            node_a=node_a,
            property_a=property_a,
            node_b=node_b,
            property_b=property_b,
            constraint_type=constraint_type,
            factor=factor,
            description=description,
        )
        self.property_constraints.append(constraint)

    def get_relationships(self, node: str, relation_type: Optional[RelationType] = None) -> List[NodeRelationship]:
        """Get all relationships for a node, optionally filtered by type"""
        relationships = []
        for rel in self.relationships:
            if (rel.from_node == node or rel.to_node == node) and (
                relation_type is None or rel.relation_type == relation_type
            ):
                relationships.append(rel)
        return relationships

    def get_suggested_next_nodes(self, current_nodes: List[str]) -> List[Tuple[str, float]]:
        """Suggest next nodes based on current workflow"""
        suggestions: Dict[str, float] = {}

        # Check what typically follows current nodes
        for node in current_nodes:
            follows = self.get_relationships(node, RelationType.PRECEDES)
            for rel in follows:
                if rel.to_node not in current_nodes:
                    suggestions[rel.to_node] = max(suggestions.get(rel.to_node, 0), rel.strength)

        # Check patterns that contain current nodes
        for pattern in self.patterns:
            if all(node in pattern.nodes for node in current_nodes):
                # Suggest remaining nodes from the pattern
                for node in pattern.nodes:
                    if node not in current_nodes:
                        suggestions[node] = max(suggestions.get(node, 0), pattern.frequency * 0.8)

        # Sort by suggestion strength
        return sorted(suggestions.items(), key=lambda x: x[1], reverse=True)

    def validate_workflow(self, nodes: List[str], connections: List[Tuple[str, str]]) -> Dict[str, Any]:
        """Validate a workflow for potential issues"""
        issues = []
        warnings = []
        suggestions = []

        # Check for conflicts
        for i, node_a in enumerate(nodes):
            for node_b in nodes[i + 1 :]:
                conflicts = self.get_relationships(node_a, RelationType.CONFLICTS)
                for rel in conflicts:
                    if rel.to_node == node_b:
                        issues.append(f"{node_a} conflicts with {node_b}: {rel.description}")

        # Check for missing requirements
        for node in nodes:
            requirements = self.get_relationships(node, RelationType.REQUIRES)
            for rel in requirements:
                if rel.relation_type == RelationType.REQUIRES and rel.from_node == node and rel.to_node not in nodes:
                    warnings.append(f"{node} typically requires {rel.to_node}")

        # Check for enhancement opportunities
        for node in nodes:
            enhancements = self.get_relationships(node, RelationType.ENHANCES)
            for rel in enhancements:
                if rel.to_node in nodes and rel.from_node not in nodes:
                    suggestions.append(f"Consider adding {rel.from_node} to enhance {rel.to_node}")

        # Suggest next steps
        next_nodes = self.get_suggested_next_nodes(nodes)
        if next_nodes:
            suggestions.append(f"Consider adding: {', '.join([n[0] for n in next_nodes[:3]])}")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "suggestions": suggestions,
        }

    def _initialize_categories(self):
        """Initialize node categories for better organization"""
        # Terrain generators
        for node in [
            "Mountain",
            "Ridge",
            "Island",
            "Volcano",
            "Canyon",
            "Crater",
            "DuneSea",
            "Plates",
        ]:
            self.node_categories[node] = "terrain"

        # Erosion and simulation
        for node in [
            "Erosion",
            "Erosion2",
            "Thermal",
            "Thermal2",
            "Rivers",
            "Lake",
            "Glacier",
            "Snow",
            "Wizard",
            "Wizard2",
        ]:
            self.node_categories[node] = "simulate"

        # Surface detail
        for node in [
            "Outcrops",
            "Stones",
            "Sand",
            "Stratify",
            "Terraces",
            "Bomber",
            "Sandstone",
        ]:
            self.node_categories[node] = "surface"

        # Modification
        for node in ["Warp", "Blur", "Sharpen", "Transform", "Clip", "Clamp", "Mask"]:
            self.node_categories[node] = "modify"

        # Data derivation
        for node in ["Slope", "Height", "Curvature", "FlowMap", "RockMap", "Angle"]:
            self.node_categories[node] = "derive"

        # Utility
        for node in [
            "Combine",
            "Portal",
            "PortalTransmit",
            "PortalReceive",
            "Accumulator",
            "Route",
            "Seamless",
            "Repeat",
        ]:
            self.node_categories[node] = "utility"

        # Color and texture
        for node in ["SatMap", "CLUTer", "TextureBase", "Splat", "RGBMerge", "Tint"]:
            self.node_categories[node] = "colorize"

    def _initialize_blend_modes(self):
        """Initialize blend mode purposes for Combine node"""
        self.blend_mode_purposes = {
            "Blend": "Standard 50/50 mix, general purpose blending",
            "Add": "Brightening, building up height, accumulation",
            "Screen": "Soft brightening, light overlay effects",
            "Subtract": "Carving, creating depressions",
            "Difference": "Edge detection, contrast creation",
            "Multiply": "Darkening, deepening shadows",
            "Divide": "Mathematical division operation",
            "Max": "Keep highest features from both inputs",
            "Min": "Keep lowest features, valley creation",
            "Overlay": "Contrast enhancement, detail preservation",
            "SoftLight": "Gentle surface detail addition",
            "HardLight": "Strong contrast, dramatic effects",
            "Power": "Exponential blending, extreme effects",
            "Dodge": "Extreme brightening, highlight enhancement",
            "Burn": "Extreme darkening, shadow deepening",
            "Exclusion": "Inverted difference, special effects",
            "Reflect": "Mirror-like combination effects",
            "Glow": "Luminous, radiant effects",
            "Phoenix": "Special artistic blending mode",
        }

    def suggest_property_values(self, nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Suggest property values based on constraints"""
        suggestions = []

        # Create node lookup
        node_map = {node["name"]: node for node in nodes}

        # Check constraints
        for constraint in self.property_constraints:
            if constraint.node_a in node_map and constraint.node_b in node_map:
                node_a = node_map[constraint.node_a]

                if constraint.property_a in node_a.get("properties", {}):
                    value_a = node_a["properties"][constraint.property_a]

                    if constraint.constraint_type == "proportional":
                        suggested_value = value_a * constraint.factor

                        # Check if this property should be an integer
                        if constraint.property_b in [
                            "FeatureScale",
                            "Layers",
                            "Levels",
                            "Steps",
                            "Terraces",
                            "Count",
                            "Vertices",
                            "PixelSize",
                            "GridSmallCount",
                            "GridLargeCount",
                        ]:
                            suggested_value = int(round(suggested_value))

                        suggestions.append(
                            {
                                "node": constraint.node_b,
                                "property": constraint.property_b,
                                "suggested_value": suggested_value,
                                "reason": constraint.description,
                            }
                        )
                    elif constraint.constraint_type == "inversely_proportional":
                        # For inverse relationships, factor represents base value
                        if value_a > 0:
                            suggested_value = constraint.factor / value_a
                        else:
                            suggested_value = constraint.factor
                        suggestions.append(
                            {
                                "node": constraint.node_b,
                                "property": constraint.property_b,
                                "suggested_value": suggested_value,
                                "reason": constraint.description,
                            }
                        )

        return suggestions

    def find_similar_patterns(self, nodes: List[str], threshold: float = 0.5) -> List[NodePattern]:
        """Find patterns similar to the given node list"""
        similar_patterns = []

        for pattern in self.patterns:
            # Calculate similarity as Jaccard index
            intersection = len(set(nodes) & set(pattern.nodes))
            union = len(set(nodes) | set(pattern.nodes))
            similarity = intersection / union if union > 0 else 0

            if similarity >= threshold:
                similar_patterns.append((pattern, similarity))

        # Sort by similarity
        similar_patterns.sort(key=lambda x: x[1], reverse=True)
        return [p[0] for p in similar_patterns]


# Create a global knowledge graph instance
knowledge_graph = Gaea2KnowledgeGraph()


def enhance_workflow_with_knowledge(nodes: List[Dict[str, Any]], connections: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Enhance a workflow using the knowledge graph"""
    node_names = [node["name"] for node in nodes]
    connection_pairs = [(c["from_node"], c["to_node"]) for c in connections]

    # Validate the workflow
    validation = knowledge_graph.validate_workflow(node_names, connection_pairs)

    # Get property suggestions
    property_suggestions = knowledge_graph.suggest_property_values(nodes)

    # Find similar patterns
    similar_patterns = knowledge_graph.find_similar_patterns(node_names)

    # Get next node suggestions
    next_nodes = knowledge_graph.get_suggested_next_nodes(node_names)

    return {
        "validation": validation,
        "property_suggestions": property_suggestions,
        "similar_patterns": [p.name for p in similar_patterns[:3]],
        "next_nodes": next_nodes[:5],
        "enhancement_summary": {
            "issues_found": len(validation["issues"]),
            "warnings": len(validation["warnings"]),
            "suggestions": len(validation["suggestions"]),
            "property_adjustments": len(property_suggestions),
        },
    }
