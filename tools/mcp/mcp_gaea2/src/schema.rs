//! Schema knowledge for Gaea2 node types, ports and properties.
//!
//! The node-type lists cover Gaea2 2.2.6.0. Port and property knowledge is
//! necessarily partial (Gaea2 does not publish a machine-readable schema); it
//! was consolidated from the analysis of reference `.terrain` files that the
//! earlier Python implementation was built from. Where knowledge is partial the
//! validator emits *warnings* rather than errors so valid-but-unknown inputs are
//! never rejected.

use std::collections::{BTreeMap, HashMap, HashSet};
use std::sync::LazyLock;

use serde::Serialize;

/// Primitive/generator nodes.
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

/// Terrain generation nodes.
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

/// Modify/transform nodes.
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

/// Surface detail nodes.
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

/// Simulation nodes.
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
    "Sediments",
    "Shrubs",
    "Snow",
    "Snowfield",
    "Thermal",
    "Thermal2",
    "Trees",
    "Wizard",
    "Wizard2",
];

/// Derive/mask nodes.
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

/// Colorize nodes.
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

/// Output nodes.
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

/// Utility nodes.
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

/// All categories in display order: (name, nodes).
pub static CATEGORIES: &[(&str, &[&str])] = &[
    ("Primitive", PRIMITIVE_NODES),
    ("Terrain", TERRAIN_NODES),
    ("Modify", MODIFY_NODES),
    ("Surface", SURFACE_NODES),
    ("Simulate", SIMULATE_NODES),
    ("Derive", DERIVE_NODES),
    ("Colorize", COLORIZE_NODES),
    ("Output", OUTPUT_NODES),
    ("Utility", UTILITY_NODES),
];

/// All valid Gaea2 node types.
pub static VALID_NODE_TYPES: LazyLock<HashSet<&'static str>> = LazyLock::new(|| {
    CATEGORIES
        .iter()
        .flat_map(|(_, nodes)| nodes.iter().copied())
        .collect()
});

/// Lower-cased type name -> canonical type name.
static NODE_TYPES_LOWER: LazyLock<HashMap<String, &'static str>> = LazyLock::new(|| {
    VALID_NODE_TYPES
        .iter()
        .map(|t| (t.to_ascii_lowercase(), *t))
        .collect()
});

/// Nodes that carry a `Seed` property (a random one is assigned when missing).
pub static GENERATOR_NODES: &[&str] = &[
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
    // Simulation nodes with a seed
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
];

/// Nodes whose primary output is RGB color data rather than a heightfield.
pub static COLOR_OUTPUT_NODES: &[&str] = &[
    "CLUTer",
    "Colorize",
    "Gamma",
    "HSL",
    "QuickColor",
    "RGBMerge",
    "SatMap",
    "Satmaps",
    "SuperColor",
    "Synth",
    "Tint",
    "WaterColor",
];

/// Nodes that can meaningfully accept color data on their inputs.
fn accepts_color(node_type: &str) -> bool {
    COLORIZE_NODES.contains(&node_type)
        || OUTPUT_NODES.contains(&node_type)
        || matches!(
            node_type,
            "Combine"
                | "Blend"
                | "Mixer2"
                | "Switch"
                | "Route"
                | "Portal"
                | "PortalTransmit"
                | "Gate"
                | "Var"
                | "Adjust"
                | "Blur"
        )
}

/// Check if a node type is valid (case-sensitive, as Gaea2 requires).
pub fn is_valid_node_type(node_type: &str) -> bool {
    VALID_NODE_TYPES.contains(node_type)
}

/// Check if a node type is a generator (has a Seed property).
pub fn is_generator_node(node_type: &str) -> bool {
    GENERATOR_NODES.contains(&node_type)
}

/// Whether a node's primary output carries color data.
pub fn outputs_color(node_type: &str) -> bool {
    COLOR_OUTPUT_NODES.contains(&node_type)
}

/// Whether feeding color data into `node_type` is suspicious.
pub fn rejects_color_input(node_type: &str) -> bool {
    !accepts_color(node_type)
}

/// Get the category for a node type.
pub fn get_node_category(node_type: &str) -> Option<&'static str> {
    CATEGORIES
        .iter()
        .find(|(_, nodes)| nodes.contains(&node_type))
        .map(|(name, _)| *name)
}

/// Suggest the most likely valid node type for an invalid one.
///
/// Tries, in order: case-insensitive match, match ignoring separators
/// (`"erosion_2"` -> `Erosion2`), common aliases, then the closest name by
/// edit distance (at most 2 edits).
pub fn suggest_node_type(invalid_type: &str) -> Option<&'static str> {
    let lower = invalid_type.trim().to_ascii_lowercase();
    if let Some(t) = NODE_TYPES_LOWER.get(&lower) {
        return Some(t);
    }
    let squashed: String = lower
        .chars()
        .filter(|c| c.is_ascii_alphanumeric())
        .collect();
    if let Some(t) = NODE_TYPES_LOWER.get(&squashed) {
        return Some(t);
    }

    const ALIASES: &[(&str, &str)] = &[
        ("hydraulicerosion", "Erosion2"),
        ("erosion3", "Erosion2"),
        ("river", "Rivers"),
        ("dunes", "DuneSea"),
        ("dune", "DuneSea"),
        ("rocks", "Stones"),
        ("rock", "Stones"),
        ("colormap", "SatMap"),
        ("satellitemap", "SatMap"),
        ("texture", "TextureBase"),
        ("ocean", "Sea"),
        ("water", "Sea"),
        ("terrace", "Terraces"),
        ("mixer", "Mixer"),
        ("output", "Output"),
        ("exporter", "Export"),
        ("heightmap", "Export"),
        ("simplexnoise", "Noise"),
        ("fractalnoise", "MultiFractal"),
        ("worley", "Voronoi"),
    ];
    if let Some((_, t)) = ALIASES.iter().find(|(alias, _)| *alias == squashed) {
        return Some(t);
    }

    // Closest by edit distance, ties broken alphabetically for determinism.
    let mut best: Option<(usize, &'static str)> = None;
    for (candidate_lower, canonical) in NODE_TYPES_LOWER.iter() {
        let d = levenshtein(&squashed, candidate_lower);
        let better = match best {
            None => true,
            Some((bd, bt)) => d < bd || (d == bd && *canonical < bt),
        };
        if better {
            best = Some((d, canonical));
        }
    }
    best.filter(|(d, _)| *d <= 2 && squashed.len() > 3)
        .map(|(_, t)| t)
}

/// Classic Levenshtein edit distance (ASCII-oriented, small inputs).
fn levenshtein(a: &str, b: &str) -> usize {
    let a: Vec<char> = a.chars().collect();
    let b: Vec<char> = b.chars().collect();
    let mut prev: Vec<usize> = (0..=b.len()).collect();
    let mut cur = vec![0; b.len() + 1];
    for i in 1..=a.len() {
        cur[0] = i;
        for j in 1..=b.len() {
            let cost = usize::from(a[i - 1] != b[j - 1]);
            cur[j] = (prev[j] + 1).min(cur[j - 1] + 1).min(prev[j - 1] + cost);
        }
        std::mem::swap(&mut prev, &mut cur);
    }
    prev[b.len()]
}

// =============================================================================
// Ports
// =============================================================================

/// Direction of a port, derived from its Gaea2 type string.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PortDirection {
    Input,
    Output,
}

/// Classify a Gaea2 port type string (`PrimaryIn`, `In`, `PrimaryOut`, `Out`,
/// optionally followed by `, Required`).
pub fn port_direction(port_type: &str) -> Option<PortDirection> {
    let base = port_type.split(',').next().unwrap_or("").trim();
    match base {
        "PrimaryIn" | "In" => Some(PortDirection::Input),
        "PrimaryOut" | "Out" => Some(PortDirection::Output),
        _ => None,
    }
}

/// Default ports for a node type as `(name, gaea_port_type)` pairs.
pub fn get_default_ports(node_type: &str) -> Vec<(&'static str, &'static str)> {
    let mut ports = vec![("In", "PrimaryIn"), ("Out", "PrimaryOut")];

    match node_type {
        "Erosion2" | "Erosion" => {
            ports.extend([("Flow", "Out"), ("Wear", "Out"), ("Deposits", "Out")]);
        },
        "Rivers" => {
            ports.extend([
                ("Headwaters", "In"),
                ("Mask", "In"),
                ("Rivers", "Out"),
                ("Flow", "Out"),
                ("Depth", "Out"),
                ("Wear", "Out"),
                ("Surface", "Out"),
                ("Direction", "Out"),
            ]);
        },
        "Sea" => {
            ports.extend([
                ("Water", "Out"),
                ("Beach", "Out"),
                ("Depth", "Out"),
                ("Shore", "Out"),
                ("Surface", "Out"),
            ]);
        },
        "Lake" => {
            ports.extend([
                ("Water", "Out"),
                ("Beach", "Out"),
                ("Depth", "Out"),
                ("Shore", "Out"),
            ]);
        },
        "Snow" | "Snowfield" => ports.push(("Snow", "Out")),
        "Thermal" | "Thermal2" => ports.push(("Talus", "Out")),
        "Sandstone" => ports.push(("Layers", "Out")),
        "Canyon" => ports.push(("Depth", "Out")),
        "FlowMap" | "FlowMapClassic" => ports.push(("Flow", "Out")),
        "Height" | "Slope" | "HeightMask" | "SlopeMask" | "Blur" | "Adjust" => {
            ports.push(("Mask", "In"));
        },
        "Combine" | "Max" | "Min" | "Multiply" | "Blend" | "Compare" => {
            ports.extend([("Input2", "In"), ("Mask", "In")]);
        },
        "Mixer" | "Mixer2" => ports.push(("Terrain", "In")),
        "WaterColor" => ports.push(("Water", "In")),
        "Export" | "Unity" | "Unreal" | "PortalTransmit" => {
            ports.retain(|(name, _)| *name != "Out");
        },
        "PortalReceive" => ports.retain(|(name, _)| *name != "In"),
        // Pure generators have no inputs.
        "Mountain" | "MountainRange" | "MountainSide" | "Volcano" | "Island" | "Crater"
        | "CraterField" | "DuneSea" | "Perlin" | "Voronoi" | "Cellular" | "Noise"
        | "LinearGradient" | "RadialGradient" | "Constant" | "Shape" => {
            ports.retain(|(name, _)| *name != "In");
        },
        _ => {},
    }

    ports
}

// =============================================================================
// Properties
// =============================================================================

/// Kind and constraints of a known node property.
#[derive(Debug, Clone, Copy, PartialEq, Serialize)]
#[serde(tag = "type", rename_all = "lowercase")]
pub enum PropKind {
    Float { min: f64, max: f64 },
    Int { min: i64, max: i64 },
    Bool,
    Enum { options: &'static [&'static str] },
    String,
}

/// A known property of a node type.
#[derive(Debug, Clone, Copy, Serialize)]
pub struct PropSpec {
    pub name: &'static str,
    #[serde(flatten)]
    pub kind: PropKind,
}

const fn f(name: &'static str, min: f64, max: f64) -> PropSpec {
    PropSpec {
        name,
        kind: PropKind::Float { min, max },
    }
}
const fn i(name: &'static str, min: i64, max: i64) -> PropSpec {
    PropSpec {
        name,
        kind: PropKind::Int { min, max },
    }
}
const fn b(name: &'static str) -> PropSpec {
    PropSpec {
        name,
        kind: PropKind::Bool,
    }
}
const fn e(name: &'static str, options: &'static [&'static str]) -> PropSpec {
    PropSpec {
        name,
        kind: PropKind::Enum { options },
    }
}
const fn s(name: &'static str) -> PropSpec {
    PropSpec {
        name,
        kind: PropKind::String,
    }
}

/// Seed property shared by all generator nodes.
pub const SEED_SPEC: PropSpec = i("Seed", 0, i32::MAX as i64);

static PROPERTY_SPECS: LazyLock<BTreeMap<&'static str, Vec<PropSpec>>> = LazyLock::new(|| {
    let mut m: BTreeMap<&'static str, Vec<PropSpec>> = BTreeMap::new();
    m.insert(
        "Mountain",
        vec![
            f("Scale", 0.1, 5.0),
            f("Height", 0.0, 1.0),
            e("Style", &["Basic", "Eroded", "Old", "Alpine", "Strata"]),
            e("Bulk", &["Low", "Medium", "High"]),
            b("ReduceDetails"),
            f("X", -1000.0, 1000.0),
            f("Y", -1000.0, 1000.0),
        ],
    );
    m.insert(
        "Volcano",
        vec![
            f("Scale", 0.1, 5.0),
            f("Height", 0.0, 1.0),
            f("Mouth", 0.0, 1.0),
            f("Bulk", 0.0, 1.0),
            e("Surface", &["Smooth", "Eroded"]),
            f("X", -1000.0, 1000.0),
            f("Y", -1000.0, 1000.0),
        ],
    );
    m.insert(
        "Island",
        vec![
            f("Size", 0.1, 1.0),
            f("Chaos", 0.0, 1.0),
            f("Height", 0.0, 1.0),
            f("Beaches", 0.0, 1.0),
        ],
    );
    m.insert(
        "Canyon",
        vec![
            f("Depth", 0.0, 1.0),
            f("Width", 0.0, 1.0),
            f("Scale", 0.1, 5.0),
        ],
    );
    m.insert(
        "Crater",
        vec![
            f("Radius", 0.1, 1.0),
            f("Depth", 0.0, 1.0),
            f("InnerSlope", 0.0, 1.0),
            f("OuterSlope", 0.0, 1.0),
        ],
    );
    m.insert(
        "Erosion2",
        vec![
            f("Duration", 0.01, 2.0),
            f("Downcutting", 0.0, 1.0),
            f("ErosionScale", 1000.0, 20000.0),
            f("Shape", 0.0, 1.0),
            f("ShapeDetailScale", 0.0, 1.0),
            f("ShapeSharpness", 0.0, 1.0),
        ],
    );
    m.insert(
        "Erosion",
        vec![
            f("Duration", 0.0, 20.0),
            f("RockSoftness", 0.0, 1.0),
            f("Strength", 0.0, 2.0),
            f("Downcutting", 0.0, 1.0),
            i("FeatureScale", 50, 10000),
        ],
    );
    m.insert(
        "EasyErosion",
        vec![
            e(
                "Style",
                &["Alpine", "Fluvial", "Coastal", "Glacial", "Desert"],
            ),
            f("Influence", 0.0, 1.0),
        ],
    );
    m.insert(
        "Rivers",
        vec![
            f("Water", 0.0, 1.0),
            f("Width", 0.0, 1.0),
            f("Depth", 0.0, 1.0),
            f("Downcutting", 0.0, 1.0),
            i("Headwaters", 10, 1000),
            b("RenderSurface"),
        ],
    );
    m.insert(
        "Lake",
        vec![
            f("Precipitation", 0.0, 100.0),
            f("SmallLakes", 0.0, 1.0),
            f("ShoreSize", 0.0, 1.0),
            f("AltitudeBias", -1.0, 1.0),
        ],
    );
    m.insert(
        "Sea",
        vec![
            f("Level", 0.0, 1.0),
            f("BeachSize", 0.0, 1.0),
            f("CoastalErosion", 0.0, 1.0),
            f("ShoreSize", 0.0, 1.0),
            f("ShoreHeight", 0.0, 1.0),
            f("Variation", 0.0, 1.0),
            b("UniformVariations"),
            b("ExtraCliffDetails"),
            b("RenderSurface"),
        ],
    );
    m.insert(
        "Snow",
        vec![
            f("Duration", 0.0, 1.0),
            f("Intensity", 0.0, 1.0),
            f("SettleDuration", 0.0, 1.0),
            e("MeltType", &["Uniform", "Directional"]),
            f("Melt", 0.0, 1.0),
            f("SnowLine", 0.0, 1.0),
            f("SlipOffAngle", 0.0, 90.0),
        ],
    );
    m.insert(
        "Thermal",
        vec![
            f("Strength", 0.0, 1.0),
            i("Iterations", 1, 50),
            f("Angle", 0.0, 90.0),
            f("Intensity", 0.0, 1.0),
        ],
    );
    m.insert(
        "FractalTerraces",
        vec![
            f("Intensity", 0.0, 1.0),
            f("Spacing", 0.1, 0.4),
            i("Octaves", 1, 16),
            i("MacroOctaves", 1, 8),
            f("StrataDetails", 0.0, 1.0),
            f("WarpAmount", 0.0, 1.0),
        ],
    );
    m.insert(
        "Terraces",
        vec![
            i("NumTerraces", 2, 256),
            f("Uniformity", 0.0, 1.0),
            f("Steepness", 0.0, 1.0),
        ],
    );
    m.insert(
        "Stratify",
        vec![
            i("Layers", 2, 50),
            f("Strength", 0.0, 1.0),
            f("Spacing", 0.0, 1.0),
            i("Octaves", 1, 16),
            f("Intensity", 0.0, 1.0),
            f("TiltAmount", 0.0, 1.0),
        ],
    );
    m.insert(
        "Crumble",
        vec![f("Intensity", 0.0, 1.0), f("Size", 0.0, 1.0)],
    );
    m.insert(
        "Shear",
        vec![f("Intensity", 0.0, 1.0), f("Angle", 0.0, 360.0)],
    );
    m.insert(
        "Combine",
        vec![
            e(
                "Mode",
                &[
                    "Blend",
                    "Add",
                    "Screen",
                    "Subtract",
                    "Difference",
                    "Multiply",
                    "Divide",
                    "Max",
                    "Min",
                    "Overlay",
                    "Power",
                ],
            ),
            f("Ratio", 0.0, 1.0),
            e("Clamp", &["None", "Clamp", "Normalize"]),
            i("PortCount", 2, 16),
        ],
    );
    m.insert(
        "SatMap",
        vec![
            e(
                "Library",
                &["New", "Rock", "Sand", "Green", "Blue", "Color"],
            ),
            i("LibraryItem", 0, 50),
            b("Randomize"),
            f("Bias", 0.0, 1.0),
            e("Enhance", &["None", "Autolevel", "Equalize"]),
            b("Reverse"),
            f("Hue", -1.0, 1.0),
            f("Saturation", -1.0, 1.0),
            f("Lightness", -1.0, 1.0),
        ],
    );
    m.insert("Height", vec![f("Low", 0.0, 1.0), f("High", 0.0, 1.0)]);
    m.insert(
        "Slope",
        vec![f("MinAngle", 0.0, 90.0), f("MaxAngle", 0.0, 90.0)],
    );
    m.insert("FlowMap", vec![i("Iterations", 10, 500)]);
    m.insert("Blur", vec![f("Amount", 0.0, 1.0)]);
    m.insert(
        "Adjust",
        vec![f("Brightness", -1.0, 1.0), f("Contrast", -1.0, 1.0)],
    );
    m.insert("Warp", vec![f("Strength", 0.0, 1.0), f("Scale", 0.1, 10.0)]);
    m.insert("PortalTransmit", vec![s("PortalName")]);
    m.insert("PortalReceive", vec![s("PortalName")]);
    m.insert(
        "Portal",
        vec![s("PortalName"), e("Direction", &["Transmit", "Receive"])],
    );
    m.insert(
        "Perlin",
        vec![
            f("Scale", 0.1, 10.0),
            i("Octaves", 1, 16),
            f("Persistence", 0.0, 1.0),
            f("Gain", 0.0, 1.0),
        ],
    );
    m.insert(
        "Voronoi",
        vec![f("Scale", 0.1, 10.0), f("Jitter", 0.0, 1.0)],
    );
    m.insert("LinearGradient", vec![f("Angle", 0.0, 360.0)]);
    m.insert(
        "Noise",
        vec![
            e("Type", &["Perlin", "Simplex", "Value", "Worley"]),
            f("Scale", 0.1, 10.0),
        ],
    );
    m
});

/// Known property specs for a node type, if the schema covers it.
///
/// `Seed` is not included here; see [`property_spec`].
pub fn property_specs(node_type: &str) -> Option<&'static [PropSpec]> {
    PROPERTY_SPECS.get(node_type).map(Vec::as_slice)
}

/// Look up one property spec. Handles the universal `Seed` property.
pub fn property_spec(node_type: &str, prop: &str) -> Option<PropSpec> {
    if prop == "Seed" {
        return Some(SEED_SPEC);
    }
    property_specs(node_type)?
        .iter()
        .find(|s| s.name == prop)
        .copied()
}

/// Keys that the generator owns; users must not set them as properties.
pub const RESERVED_PROPERTY_KEYS: &[&str] = &[
    "$id",
    "$type",
    "$ref",
    "$values",
    "Id",
    "Name",
    "Position",
    "Ports",
    "Modifiers",
    "SaveDefinition",
];

/// Convert a property name to Gaea2's PascalCase convention
/// (`"erosion scale"` / `"erosion_scale"` / `"erosionScale"` -> `"ErosionScale"`).
/// Returns `None` when the name is already in canonical form.
pub fn canonical_property_name(name: &str) -> Option<String> {
    let mut out = String::with_capacity(name.len());
    let mut upper_next = true;
    for c in name.chars() {
        if c == ' ' || c == '_' || c == '-' {
            upper_next = true;
            continue;
        }
        if upper_next {
            out.extend(c.to_uppercase());
            upper_next = false;
        } else {
            out.push(c);
        }
    }
    if out.is_empty() || out == name {
        None
    } else {
        Some(out)
    }
}

// =============================================================================
// Suggestions
// =============================================================================

/// A suggested node with the reason it was suggested.
#[derive(Debug, Clone, Serialize, PartialEq)]
pub struct NodeSuggestion {
    pub node: &'static str,
    pub category: &'static str,
    pub reason: String,
}

/// Common follow-up nodes observed in reference projects: node -> next nodes.
static COMMON_FOLLOWERS: &[(&str, &[&str])] = &[
    ("Mountain", &["Erosion2"]),
    ("MountainRange", &["Erosion2"]),
    ("Ridge", &["Erosion2", "Outcrops"]),
    ("Canyon", &["Stratify", "Sandstone"]),
    ("Island", &["Adjust", "Blur"]),
    ("Volcano", &["Thermal2", "Erosion2"]),
    ("Slump", &["FractalTerraces"]),
    ("FractalTerraces", &["Combine", "Shear"]),
    ("Crumble", &["Erosion2"]),
    ("Erosion2", &["Rivers", "TextureBase", "ColorErosion"]),
    ("Rivers", &["Adjust", "Height"]),
    ("Sandstone", &["Stratify"]),
    ("Stratify", &["SlopeBlur", "Erosion2"]),
    ("TextureBase", &["SatMap"]),
    ("SatMap", &["Combine", "ColorErosion"]),
    ("Weathering", &["Combine"]),
    ("Combine", &["Shear", "Weathering"]),
    ("Adjust", &["Combine", "Blur"]),
];

/// Context keywords -> nodes that fit that kind of terrain.
static CONTEXT_NODES: &[(&[&str], &[&str])] = &[
    (
        &["mountain", "alpine", "peak", "ridge"],
        &["Snow", "Glacier", "Stones", "Outcrops"],
    ),
    (
        &["desert", "dune", "sand", "arid"],
        &["DuneSea", "Sand", "Sandstone", "SlopeWarp"],
    ),
    (
        &["coast", "beach", "island", "ocean", "sea", "shore"],
        &["Coast", "Beach", "Sea"],
    ),
    (
        &["volcan", "lava", "crater"],
        &["Volcano", "Thermal2", "Stratify"],
    ),
    (
        &["canyon", "mesa", "gorge"],
        &["Canyon", "Stratify", "FractalTerraces", "Rivers"],
    ),
    (
        &["river", "valley", "stream"],
        &["Rivers", "Sediment", "Lake"],
    ),
    (
        &["arctic", "glacier", "ice", "snow", "tundra"],
        &["Glacier", "Snow", "IceFloe", "Snowfield"],
    ),
    (&["lake", "pond"], &["Lake", "Rivers"]),
    (
        &["terrace", "strata", "layer"],
        &["Stratify", "Terraces", "FractalTerraces"],
    ),
];

/// Suggest nodes for the current workflow and an optional terrain description.
///
/// Every suggestion is a valid Gaea2 node type and is not already present.
pub fn suggest_nodes(current_nodes: &[String], context: Option<&str>) -> Vec<NodeSuggestion> {
    let present: HashSet<&str> = current_nodes.iter().map(String::as_str).collect();
    let mut out: Vec<NodeSuggestion> = Vec::new();
    let push = |node: &'static str, reason: String, out: &mut Vec<NodeSuggestion>| {
        if present.contains(node) || out.iter().any(|s| s.node == node) {
            return;
        }
        out.push(NodeSuggestion {
            node,
            category: get_node_category(node).unwrap_or("Unknown"),
            reason,
        });
    };

    let has_base = current_nodes.iter().any(|n| {
        let n = n.as_str();
        TERRAIN_NODES.contains(&n) || PRIMITIVE_NODES.contains(&n)
    });
    let has_erosion = current_nodes
        .iter()
        .any(|n| matches!(n.as_str(), "Erosion" | "Erosion2" | "EasyErosion"));
    let has_color = current_nodes
        .iter()
        .any(|n| COLORIZE_NODES.contains(&n.as_str()));
    let has_output = current_nodes
        .iter()
        .any(|n| OUTPUT_NODES.contains(&n.as_str()));

    if !has_base {
        for node in ["Mountain", "Perlin", "Voronoi"] {
            push(node, "No base terrain generator yet".to_string(), &mut out);
        }
    }
    if has_base && !has_erosion {
        push(
            "Erosion2",
            "Hydraulic erosion is the single biggest realism improvement".to_string(),
            &mut out,
        );
    }

    // Follow-ups for the most recently added node types.
    for current in current_nodes.iter().rev().take(3) {
        if let Some((_, next)) = COMMON_FOLLOWERS.iter().find(|(n, _)| n == current) {
            for node in next.iter() {
                push(
                    node,
                    format!("Commonly follows {current} in reference projects"),
                    &mut out,
                );
            }
        }
    }

    if let Some(ctx) = context {
        let ctx_lower = ctx.to_lowercase();
        for (keywords, nodes) in CONTEXT_NODES {
            if let Some(kw) = keywords.iter().find(|k| ctx_lower.contains(*k)) {
                for node in nodes.iter() {
                    push(node, format!("Fits '{kw}' terrain"), &mut out);
                }
            }
        }
    }

    if !has_color {
        push(
            "TextureBase",
            "Texture data for colorization".to_string(),
            &mut out,
        );
        push("SatMap", "No colorization node yet".to_string(), &mut out);
    }
    if !has_output {
        push(
            "Export",
            "No Export node - nothing will be written on build".to_string(),
            &mut out,
        );
    }

    out
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
        assert!(!is_valid_node_type("mountain"));
    }

    #[test]
    fn test_generator_nodes() {
        assert!(is_generator_node("Mountain"));
        assert!(is_generator_node("Perlin"));
        assert!(!is_generator_node("Output"));
        assert!(!is_generator_node("Blur"));
        for g in GENERATOR_NODES {
            assert!(is_valid_node_type(g), "generator {g} not a valid type");
        }
    }

    #[test]
    fn test_node_category() {
        assert_eq!(get_node_category("Mountain"), Some("Terrain"));
        assert_eq!(get_node_category("Erosion2"), Some("Simulate"));
        assert_eq!(get_node_category("Output"), Some("Output"));
        assert_eq!(get_node_category("Invalid"), None);
    }

    #[test]
    fn all_schema_node_references_are_valid() {
        for n in COLOR_OUTPUT_NODES {
            assert!(is_valid_node_type(n), "{n}");
        }
        for n in PROPERTY_SPECS.keys() {
            assert!(is_valid_node_type(n), "{n}");
        }
        for (n, next) in COMMON_FOLLOWERS {
            assert!(is_valid_node_type(n), "{n}");
            for m in next.iter() {
                assert!(is_valid_node_type(m), "{m}");
            }
        }
        for (_, nodes) in CONTEXT_NODES {
            for n in nodes.iter() {
                assert!(is_valid_node_type(n), "{n}");
            }
        }
    }

    #[test]
    fn suggest_node_type_fixes_common_mistakes() {
        assert_eq!(suggest_node_type("mountain"), Some("Mountain"));
        assert_eq!(suggest_node_type("erosion_2"), Some("Erosion2"));
        assert_eq!(suggest_node_type("Erosoin2"), Some("Erosion2"));
        assert_eq!(suggest_node_type("Dunes"), Some("DuneSea"));
        assert_eq!(suggest_node_type("SatelliteMap"), Some("SatMap"));
        assert_eq!(suggest_node_type("CompletelyBogus"), None);
        assert_eq!(suggest_node_type("xy"), None);
    }

    #[test]
    fn port_directions() {
        assert_eq!(port_direction("PrimaryIn"), Some(PortDirection::Input));
        assert_eq!(
            port_direction("PrimaryIn, Required"),
            Some(PortDirection::Input)
        );
        assert_eq!(port_direction("Out"), Some(PortDirection::Output));
        assert_eq!(port_direction("Bogus"), None);
    }

    #[test]
    fn default_ports_shape() {
        let m = get_default_ports("Mountain");
        assert!(!m.iter().any(|(n, _)| *n == "In"));
        let e = get_default_ports("Export");
        assert!(!e.iter().any(|(n, _)| *n == "Out"));
        let c = get_default_ports("Combine");
        assert!(c.iter().any(|(n, _)| *n == "Input2"));
    }

    #[test]
    fn property_name_canonicalization() {
        assert_eq!(
            canonical_property_name("erosion scale").as_deref(),
            Some("ErosionScale")
        );
        assert_eq!(
            canonical_property_name("rock_softness").as_deref(),
            Some("RockSoftness")
        );
        assert_eq!(
            canonical_property_name("erosionScale").as_deref(),
            Some("ErosionScale")
        );
        assert_eq!(canonical_property_name("Duration"), None);
    }

    #[test]
    fn suggestions_are_valid_and_new() {
        let current = vec!["Mountain".to_string()];
        let s = suggest_nodes(&current, Some("volcanic desert island"));
        assert!(!s.is_empty());
        for sug in &s {
            assert!(is_valid_node_type(sug.node), "{}", sug.node);
            assert_ne!(sug.node, "Mountain");
        }
        assert!(s.iter().any(|x| x.node == "Erosion2"));
        assert!(s.iter().any(|x| x.node == "Volcano"));
        assert!(s.iter().any(|x| x.node == "DuneSea"));
        assert!(s.iter().any(|x| x.node == "Sea"));
    }

    #[test]
    fn complete_workflow_gets_few_basic_suggestions() {
        let current: Vec<String> = ["Mountain", "Erosion2", "SatMap", "Export"]
            .iter()
            .map(|s| s.to_string())
            .collect();
        let s = suggest_nodes(&current, None);
        assert!(!s.iter().any(|x| x.node == "Export" || x.node == "Mountain"));
    }
}
