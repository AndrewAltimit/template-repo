//! Core data types for Gaea2 terrain workflows.
//!
//! These are the *API-level* types that tools accept and return. They are
//! converted into the Gaea2 2.2.6.0 `.terrain` JSON layout by
//! [`crate::generation`].

use serde::{Deserialize, Serialize};
use serde_json::{Map, Value};

/// A complete Gaea2 workflow: a DAG of nodes plus the connections between them.
#[derive(Debug, Clone, Default, Serialize, Deserialize, PartialEq)]
pub struct Workflow {
    pub nodes: Vec<Node>,
    pub connections: Vec<Connection>,
}

/// A single node in a Gaea2 workflow.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct Node {
    /// Unique node identifier (becomes the node's `Id` and dictionary key).
    pub id: i32,
    /// Node type, e.g. `"Mountain"`, `"Erosion2"`, `"SatMap"`.
    #[serde(rename = "type")]
    pub node_type: String,
    /// Display name (defaults to the node type).
    #[serde(default)]
    pub name: String,
    /// Position in the graph editor. `None` means "auto-layout".
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub position: Option<Position>,
    /// Node-specific properties (PascalCase Gaea2 property names).
    #[serde(default)]
    pub properties: Map<String, Value>,
    /// Explicit port definitions. `None` uses the built-in defaults for the type.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub ports: Option<Vec<PortDefinition>>,
    /// Modifiers applied to the node.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub modifiers: Option<Vec<Modifier>>,
    /// Save definition (used by Export-style nodes to write files on build).
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub save_definition: Option<SaveDefinition>,
    /// Optional node size in the graph editor (`"Small"`, `"Standard"`, ...).
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub node_size: Option<String>,
    /// Whether the node exposes a mask input in the editor (default: true).
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub is_maskable: Option<bool>,
}

impl Node {
    /// Create a node with the given id and type and all optional fields empty.
    pub fn new(id: i32, node_type: impl Into<String>) -> Self {
        let node_type = node_type.into();
        Self {
            id,
            name: node_type.clone(),
            node_type,
            position: None,
            properties: Map::new(),
            ports: None,
            modifiers: None,
            save_definition: None,
            node_size: None,
            is_maskable: None,
        }
    }
}

/// Position in the graph editor (Gaea2 uses coordinates around 25000).
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq)]
pub struct Position {
    #[serde(alias = "X", default = "default_position")]
    pub x: f64,
    #[serde(alias = "Y", default = "default_position")]
    pub y: f64,
}

impl Default for Position {
    fn default() -> Self {
        Self {
            x: default_position(),
            y: default_position(),
        }
    }
}

fn default_position() -> f64 {
    25000.0
}

/// A connection from an output port of one node to an input port of another.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, Hash)]
pub struct Connection {
    /// Source node ID
    pub from_node: i32,
    /// Target node ID
    pub to_node: i32,
    /// Source (output) port name
    #[serde(default = "default_output_port")]
    pub from_port: String,
    /// Target (input) port name
    #[serde(default = "default_input_port")]
    pub to_port: String,
}

impl Connection {
    /// Convenience constructor.
    pub fn new(from_node: i32, from_port: &str, to_node: i32, to_port: &str) -> Self {
        Self {
            from_node,
            to_node,
            from_port: from_port.to_string(),
            to_port: to_port.to_string(),
        }
    }
}

pub fn default_output_port() -> String {
    "Out".to_string()
}

pub fn default_input_port() -> String {
    "In".to_string()
}

/// Explicit port definition for a node.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(deny_unknown_fields)]
pub struct PortDefinition {
    pub name: String,
    /// Gaea2 port type: `PrimaryIn`, `In`, `PrimaryOut` or `Out`.
    #[serde(rename = "type")]
    pub port_type: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub portal_state: Option<String>,
}

/// Modifier applied to a node (e.g. `Height`, `Blur`, `Invert`).
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(deny_unknown_fields)]
pub struct Modifier {
    #[serde(rename = "type")]
    pub modifier_type: String,
    #[serde(default)]
    pub properties: Map<String, Value>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub order: Option<i32>,
    #[serde(default)]
    pub has_ui: bool,
}

/// Save definition for export nodes.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(deny_unknown_fields)]
pub struct SaveDefinition {
    /// Output file name (without extension). Defaults to the node name.
    #[serde(default)]
    pub filename: String,
    /// Output format, e.g. `PNG16`, `PNG64`, `EXR`, `RAW16`, `TIFF`.
    #[serde(default = "default_format")]
    pub format: String,
    #[serde(default = "default_enabled")]
    pub enabled: bool,
    #[serde(default)]
    pub disabled_profiles: Vec<String>,
}

fn default_format() -> String {
    "PNG64".to_string()
}

fn default_enabled() -> bool {
    true
}

/// Build configuration for a Gaea2 project (`BuildDefinition` in the file).
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(deny_unknown_fields)]
pub struct BuildConfig {
    #[serde(default = "default_build_type")]
    pub build_type: String,
    #[serde(default = "default_resolution")]
    pub resolution: u32,
    /// Defaults to `resolution` when omitted.
    #[serde(default)]
    pub bake_resolution: Option<u32>,
    #[serde(default = "default_tile_resolution")]
    pub tile_resolution: u32,
    #[serde(default = "default_number_of_tiles")]
    pub number_of_tiles: u32,
    #[serde(default = "default_edge_blending")]
    pub edge_blending: f64,
    #[serde(default = "default_color_space")]
    pub color_space: String,
}

fn default_build_type() -> String {
    "Standard".to_string()
}

fn default_resolution() -> u32 {
    2048
}

fn default_tile_resolution() -> u32 {
    1024
}

fn default_number_of_tiles() -> u32 {
    3
}

fn default_edge_blending() -> f64 {
    0.25
}

fn default_color_space() -> String {
    "sRGB".to_string()
}

impl Default for BuildConfig {
    fn default() -> Self {
        Self {
            build_type: default_build_type(),
            resolution: default_resolution(),
            bake_resolution: None,
            tile_resolution: default_tile_resolution(),
            number_of_tiles: default_number_of_tiles(),
            edge_blending: default_edge_blending(),
            color_space: default_color_space(),
        }
    }
}

/// Valid square build resolutions accepted by Gaea2.
pub const VALID_RESOLUTIONS: &[u32] = &[256, 512, 1024, 2048, 4096, 8192, 16384];

impl BuildConfig {
    /// Effective bake resolution.
    pub fn bake_resolution(&self) -> u32 {
        self.bake_resolution.unwrap_or(self.resolution)
    }

    /// Check the configuration for values Gaea2 cannot build.
    pub fn validate(&self) -> Result<(), String> {
        for (label, value) in [
            ("resolution", self.resolution),
            ("bake_resolution", self.bake_resolution()),
            ("tile_resolution", self.tile_resolution),
        ] {
            if !VALID_RESOLUTIONS.contains(&value) {
                return Err(format!(
                    "build_config.{label} must be one of {VALID_RESOLUTIONS:?}, got {value}"
                ));
            }
        }
        if !(1..=64).contains(&self.number_of_tiles) {
            return Err(format!(
                "build_config.number_of_tiles must be between 1 and 64, got {}",
                self.number_of_tiles
            ));
        }
        if !(0.0..=1.0).contains(&self.edge_blending) {
            return Err(format!(
                "build_config.edge_blending must be between 0.0 and 1.0, got {}",
                self.edge_blending
            ));
        }
        if self.build_type.trim().is_empty() || self.color_space.trim().is_empty() {
            return Err("build_config.build_type and color_space must not be empty".to_string());
        }
        Ok(())
    }
}

/// Validation result from workflow validation.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ValidationResult {
    /// True when no blocking errors remain in `workflow`.
    pub valid: bool,
    /// True when at least one automatic fix was applied.
    pub fixed: bool,
    /// Blocking problems that remain after fixing (the file would be invalid).
    pub errors: Vec<String>,
    /// Non-blocking observations (unknown properties, dangling nodes, ...).
    #[serde(default)]
    pub warnings: Vec<String>,
    /// Human-readable list of the fixes that were applied.
    #[serde(default)]
    pub fixes_applied: Vec<String>,
    /// The (possibly fixed) workflow.
    pub workflow: Workflow,
}

/// Execution result from running a Gaea2 project through Gaea.Swarm.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct ExecutionResult {
    pub success: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub output_dir: Option<String>,
    #[serde(default)]
    pub output_files: Vec<String>,
    #[serde(default)]
    pub file_count: usize,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub execution_time: Option<f64>,
    /// Process exit code, when the process ran to completion.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub exit_code: Option<i32>,
    /// True when the build was killed because it exceeded its timeout.
    #[serde(default)]
    pub timed_out: bool,
    /// Standard output from CLI execution (tail, truncated)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub stdout: Option<String>,
    /// Standard error from CLI execution (tail, truncated)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub stderr: Option<String>,
}

impl ExecutionResult {
    /// A failed result with just an error message.
    pub fn failure(error: impl Into<String>) -> Self {
        Self {
            success: false,
            error: Some(error.into()),
            ..Default::default()
        }
    }
}

/// Execution history entry.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExecutionHistoryEntry {
    pub timestamp: String,
    pub project: String,
    pub result: ExecutionResult,
}

/// Template definition.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Template {
    pub name: String,
    #[serde(default)]
    pub description: String,
    pub nodes: Vec<Node>,
    pub connections: Vec<Connection>,
}

/// File listing info.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FileInfo {
    pub filename: String,
    pub path: String,
    pub size: u64,
    pub modified: String,
}

/// Optimization mode for node properties.
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum OptimizationMode {
    Performance,
    Quality,
    #[default]
    Balanced,
}

/// Analysis type for workflow analysis.
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum AnalysisType {
    Patterns,
    Performance,
    Quality,
    #[default]
    All,
}
