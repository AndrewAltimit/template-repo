//! Schema definitions for Gaea2 node types and properties.
//!
//! Contains the complete list of valid node types and their categories.
//! Based on Gaea2 2.2.6.0 node schema with 184 node types across 9 categories.

use std::collections::HashSet;
use std::sync::LazyLock;

/// All valid Gaea2 node types organized by category.
pub static VALID_NODE_TYPES: LazyLock<HashSet<&'static str>> = LazyLock::new(|| {
    let mut types = HashSet::new();

    // Primitive nodes (generators)
    for t in PRIMITIVE_NODES.iter() {
        types.insert(*t);
    }

    // Terrain nodes
    for t in TERRAIN_NODES.iter() {
        types.insert(*t);
    }

    // Modify nodes
    for t in MODIFY_NODES.iter() {
        types.insert(*t);
    }

    // Surface nodes
    for t in SURFACE_NODES.iter() {
        types.insert(*t);
    }

    // Simulate nodes
    for t in SIMULATE_NODES.iter() {
        types.insert(*t);
    }

    // Derive nodes
    for t in DERIVE_NODES.iter() {
        types.insert(*t);
    }

    // Colorize nodes
    for t in COLORIZE_NODES.iter() {
        types.insert(*t);
    }

    // Output nodes
    for t in OUTPUT_NODES.iter() {
        types.insert(*t);
    }

    // Utility nodes
    for t in UTILITY_NODES.iter() {
        types.insert(*t);
    }

    types
});

/// Primitive/generator nodes (24 types).
pub static PRIMITIVE_NODES: &[&str] = &[
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
    "Gradient",
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
];

/// Terrain generation nodes (14 types).
pub static TERRAIN_NODES: &[&str] = &[
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
];

/// Modify/transform nodes (41 types).
pub static MODIFY_NODES: &[&str] = &[
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
];

/// Surface nodes (21 types).
pub static SURFACE_NODES: &[&str] = &[
    "Bomber",
    "Bulbous",
    "Contours",
    "Craggy",
    "Details",
    "Distress",
    "FractalTerraces",
    "Grid",
    "GroundTexture",
    "Outcrops",
    "Pockmarks",
    "RockNoise",
    "Rockmap",
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
];

/// Simulation nodes (25 types).
pub static SIMULATE_NODES: &[&str] = &[
    "Anastomosis",
    "Beach",
    "Coast",
    "Crumble",
    "Debris",
    "Dusting",
    "EasyErosion",
    "Erosion",
    "Erosion2",
    "Fluvial",
    "Glacier",
    "Hillify",
    "HydroFix",
    "IceFloe",
    "Lake",
    "Lichtenberg",
    "Rivers",
    "Scree",
    "Sea",
    "Sediment",
    "Shrubs",
    "Snow",
    "Snowfield",
    "Thermal",
    "Thermal2",
    "Trees",
    "Wizard",
    "Wizard2",
];

/// Derive/mask nodes (13 types).
pub static DERIVE_NODES: &[&str] = &[
    "Angle",
    "Curvature",
    "FlowMap",
    "FlowMapClassic",
    "Height",
    "HeightMask",
    "Normals",
    "Occlusion",
    "Peaks",
    "RockMap",
    "Slope",
    "SlopeMask",
    "Soil",
    "TextureBase",
    "Texturizer",
];

/// Colorize nodes (13 types).
pub static COLORIZE_NODES: &[&str] = &[
    "CLUTer",
    "ColorErosion",
    "Colorize",
    "Gamma",
    "HSL",
    "Mixer",
    "QuickColor",
    "RGBMerge",
    "RGBSplit",
    "SatMap",
    "Satmaps",
    "Splat",
    "SuperColor",
    "Synth",
    "Tint",
    "WaterColor",
    "Weathering",
];

/// Output nodes (13 types).
pub static OUTPUT_NODES: &[&str] = &[
    "AO",
    "Cartography",
    "Export",
    "Halftone",
    "LightX",
    "Mesher",
    "Output",
    "PointCloud",
    "Shade",
    "Sunlight",
    "TextureBaker",
    "Unity",
    "Unreal",
    "VFX",
];

/// Utility nodes (20 types).
pub static UTILITY_NODES: &[&str] = &[
    "Accumulator",
    "Blend",
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
    "Max",
    "Min",
    "Mixer2",
    "Multiply",
    "Portal",
    "PortalReceive",
    "PortalTransmit",
    "Repeat",
    "Reseed",
    "Route",
    "Seamless",
    "Switch",
    "Var",
];

/// Nodes that generate terrain (have a Seed property).
pub static GENERATOR_NODES: LazyLock<HashSet<&'static str>> = LazyLock::new(|| {
    let mut nodes = HashSet::new();
    for t in [
        // Terrain generators
        "Mountain",
        "MountainRange",
        "MountainSide",
        "Volcano",
        "Island",
        "Canyon",
        "Crater",
        "CraterField",
        "DuneSea",
        "Ridge",
        "Rugged",
        "Slump",
        // Primitive generators
        "Perlin",
        "Voronoi",
        "Cellular",
        "Cellular3D",
        "Noise",
        "LineNoise",
        "MultiFractal",
        "Gabor",
        "DriftNoise",
        "CutNoise",
        "DotNoise",
        "WaveShine",
        // Simulation with seed
        "Erosion",
        "Erosion2",
        "EasyErosion",
        "Rivers",
        "Snow",
        "Snowfield",
        "Beach",
        "Coast",
        "Lake",
        "Sea",
        "Glacier",
        "IceFloe",
        "Thermal",
        "Thermal2",
        "Crumble",
        "Sediment",
        "Warp",
        "FractalTerraces",
        "Terraces",
        "Lichtenberg",
    ] {
        nodes.insert(t);
    }
    nodes
});

/// Check if a node type is valid.
pub fn is_valid_node_type(node_type: &str) -> bool {
    VALID_NODE_TYPES.contains(node_type)
}

/// Check if a node type is a generator (has Seed property).
pub fn is_generator_node(node_type: &str) -> bool {
    GENERATOR_NODES.contains(node_type)
}

/// Get the category for a node type.
pub fn get_node_category(node_type: &str) -> Option<&'static str> {
    if PRIMITIVE_NODES.contains(&node_type) {
        Some("Primitive")
    } else if TERRAIN_NODES.contains(&node_type) {
        Some("Terrain")
    } else if MODIFY_NODES.contains(&node_type) {
        Some("Modify")
    } else if SURFACE_NODES.contains(&node_type) {
        Some("Surface")
    } else if SIMULATE_NODES.contains(&node_type) {
        Some("Simulate")
    } else if DERIVE_NODES.contains(&node_type) {
        Some("Derive")
    } else if COLORIZE_NODES.contains(&node_type) {
        Some("Colorize")
    } else if OUTPUT_NODES.contains(&node_type) {
        Some("Output")
    } else if UTILITY_NODES.contains(&node_type) {
        Some("Utility")
    } else {
        None
    }
}

/// Get default ports for a node type.
pub fn get_default_ports(node_type: &str) -> Vec<(&'static str, &'static str)> {
    let mut ports = vec![("In", "PrimaryIn"), ("Out", "PrimaryOut")];

    match node_type {
        "Erosion2" | "Erosion" => {
            ports.push(("Flow", "Out"));
            ports.push(("Wear", "Out"));
            ports.push(("Deposits", "Out"));
        },
        "Rivers" => {
            ports.push(("Rivers", "Out"));
            ports.push(("Flow", "Out"));
            ports.push(("Depth", "Out"));
            ports.push(("Wear", "Out"));
        },
        "Lake" | "Sea" => {
            ports.push(("Water", "Out"));
            ports.push(("Beach", "Out"));
            ports.push(("Depth", "Out"));
            ports.push(("Shore", "Out"));
        },
        "Snow" | "Snowfield" => {
            ports.push(("Snow", "Out"));
        },
        "Thermal" | "Thermal2" => {
            ports.push(("Talus", "Out"));
        },
        "Sandstone" => {
            ports.push(("Layers", "Out"));
        },
        "Canyon" => {
            ports.push(("Depth", "Out"));
        },
        "FlowMap" | "FlowMapClassic" => {
            ports.push(("Flow", "Out"));
        },
        "Height" | "Slope" | "HeightMask" | "SlopeMask" => {
            ports.push(("Mask", "In"));
        },
        "Combine" | "Max" | "Min" | "Multiply" | "Blend" | "Compare" => {
            ports.push(("Input2", "In"));
            ports.push(("Mask", "In"));
        },
        "Mixer" | "Mixer2" => {
            ports.push(("Terrain", "In"));
            // Mixer has up to 8 layer ports
        },
        "SatMap" | "Satmaps" | "CLUTer" | "Colorize" | "QuickColor" => {
            // Colorize nodes output color instead of heightfield
        },
        "WaterColor" => {
            ports.push(("Water", "In"));
        },
        "Export" | "Unity" | "Unreal" => {
            // Output nodes have no outputs
            ports.retain(|(name, _)| *name != "Out");
        },
        "PortalTransmit" => {
            ports.retain(|(name, _)| *name != "Out");
        },
        "PortalReceive" => {
            ports.retain(|(name, _)| *name != "In");
        },
        // Generators have no inputs
        "Mountain" | "MountainRange" | "MountainSide" | "Volcano" | "Island" | "Crater"
        | "CraterField" | "DuneSea" | "Perlin" | "Voronoi" | "Cellular" | "Noise"
        | "LinearGradient" | "RadialGradient" | "Constant" | "Shape" => {
            ports.retain(|(name, _)| *name != "In");
        },
        _ => {},
    }

    ports
}

/// Suggest nodes based on the current workflow context.
pub fn suggest_nodes(current_nodes: &[String], context: Option<&str>) -> Vec<String> {
    let mut suggestions = Vec::new();

    let has_generator = current_nodes.iter().any(|n| is_generator_node(n));
    let has_erosion = current_nodes
        .iter()
        .any(|n| n == "Erosion2" || n == "Erosion");
    let has_colorize = current_nodes
        .iter()
        .any(|n| COLORIZE_NODES.contains(&n.as_str()));
    let has_output = current_nodes
        .iter()
        .any(|n| OUTPUT_NODES.contains(&n.as_str()));

    // Suggest based on missing components
    if !has_generator {
        suggestions.push("Mountain".to_string());
        suggestions.push("Perlin".to_string());
        suggestions.push("Voronoi".to_string());
    }

    if has_generator && !has_erosion {
        suggestions.push("Erosion2".to_string());
    }

    if !has_colorize {
        suggestions.push("QuickColor".to_string());
        suggestions.push("Satmaps".to_string());
    }

    if !has_output {
        suggestions.push("Output".to_string());
    }

    // Context-based suggestions
    if let Some(ctx) = context {
        let ctx_lower = ctx.to_lowercase();
        if ctx_lower.contains("mountain") || ctx_lower.contains("alpine") {
            suggestions.extend(["Snow", "Glacier", "Rocks"].map(String::from));
        } else if ctx_lower.contains("desert") || ctx_lower.contains("dune") {
            suggestions.extend(["Dunes", "Sandstone", "SlopeWarp"].map(String::from));
        } else if ctx_lower.contains("coast") || ctx_lower.contains("beach") {
            suggestions.extend(["Coast", "Beach", "Lake"].map(String::from));
        } else if ctx_lower.contains("volcano") {
            suggestions.extend(["Volcano", "Thermal", "Stratify"].map(String::from));
        } else if ctx_lower.contains("canyon") {
            suggestions.extend(["Canyon", "Stratify", "Rivers"].map(String::from));
        }
    }

    // Remove duplicates and nodes already in workflow
    suggestions.retain(|s| !current_nodes.contains(s));
    suggestions.sort();
    suggestions.dedup();

    suggestions
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_valid_node_types() {
        assert!(is_valid_node_type("Mountain"));
        assert!(is_valid_node_type("Erosion2"));
        assert!(is_valid_node_type("Output"));
        assert!(!is_valid_node_type("InvalidNode"));
    }

    #[test]
    fn test_generator_nodes() {
        assert!(is_generator_node("Mountain"));
        assert!(is_generator_node("Perlin"));
        assert!(!is_generator_node("Output"));
        assert!(!is_generator_node("Blur"));
    }

    #[test]
    fn test_node_category() {
        assert_eq!(get_node_category("Mountain"), Some("Terrain"));
        assert_eq!(get_node_category("Erosion2"), Some("Simulate"));
        assert_eq!(get_node_category("Output"), Some("Output"));
        assert_eq!(get_node_category("Invalid"), None);
    }
}
