//! Core types for Gaea2 terrain generation.
//!
//! These types map to the Gaea2 2.2.6.0 file format.

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// A complete Gaea2 workflow with nodes and connections.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Workflow {
    pub nodes: Vec<Node>,
    pub connections: Vec<Connection>,
}

/// A single node in a Gaea2 workflow.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Node {
    /// Unique node identifier (integer in Gaea2)
    pub id: i32,
    /// Node type (e.g., "Mountain", "Erosion2", "Perlin")
    #[serde(rename = "type")]
    pub node_type: String,
    /// Display name
    #[serde(default)]
    pub name: String,
    /// Node position in the graph
    #[serde(default)]
    pub position: Position,
    /// Node-specific properties
    #[serde(default)]
    pub properties: HashMap<String, serde_json::Value>,
    /// Port definitions
    #[serde(default)]
    pub ports: Option<Vec<PortDefinition>>,
    /// Modifiers applied to the node
    #[serde(default)]
    pub modifiers: Option<Vec<Modifier>>,
    /// Save definition for export nodes
    #[serde(default)]
    pub save_definition: Option<SaveDefinition>,
}

/// Position in the graph editor.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct Position {
    #[serde(alias = "X", default = "default_position")]
    pub x: f64,
    #[serde(alias = "Y", default = "default_position")]
    pub y: f64,
}

fn default_position() -> f64 {
    25000.0
}

/// A connection between two nodes.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Connection {
    /// Source node ID
    #[serde(alias = "from", alias = "source")]
    pub from_node: i32,
    /// Target node ID
    #[serde(alias = "to", alias = "target")]
    pub to_node: i32,
    /// Source port name
    #[serde(default = "default_output_port", alias = "source_port")]
    pub from_port: String,
    /// Target port name
    #[serde(default = "default_input_port", alias = "target_port")]
    pub to_port: String,
}

fn default_output_port() -> String {
    "Out".to_string()
}

fn default_input_port() -> String {
    "In".to_string()
}

/// Port definition for a node.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PortDefinition {
    pub name: String,
    #[serde(rename = "type")]
    pub port_type: String,
    #[serde(default)]
    pub portal_state: Option<String>,
}

/// Modifier applied to a node.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Modifier {
    #[serde(rename = "type")]
    pub modifier_type: String,
    #[serde(default)]
    pub properties: HashMap<String, serde_json::Value>,
    #[serde(default)]
    pub order: Option<i32>,
    #[serde(default)]
    pub has_ui: bool,
}

/// Save definition for export nodes.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SaveDefinition {
    #[serde(default)]
    pub filename: String,
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

/// Build configuration for a Gaea2 project.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BuildConfig {
    #[serde(default = "default_build_type")]
    pub build_type: String,
    #[serde(default = "default_resolution")]
    pub resolution: i32,
    #[serde(default = "default_resolution")]
    pub bake_resolution: i32,
    #[serde(default = "default_tile_resolution")]
    pub tile_resolution: i32,
    #[serde(default = "default_number_of_tiles")]
    pub number_of_tiles: i32,
    #[serde(default = "default_edge_blending")]
    pub edge_blending: f64,
    #[serde(default = "default_color_space")]
    pub color_space: String,
}

fn default_build_type() -> String {
    "Standard".to_string()
}

fn default_resolution() -> i32 {
    2048
}

fn default_tile_resolution() -> i32 {
    1024
}

fn default_number_of_tiles() -> i32 {
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
            bake_resolution: default_resolution(),
            tile_resolution: default_tile_resolution(),
            number_of_tiles: default_number_of_tiles(),
            edge_blending: default_edge_blending(),
            color_space: default_color_space(),
        }
    }
}

/// Validation result from workflow validation.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ValidationResult {
    pub valid: bool,
    pub fixed: bool,
    pub errors: Vec<String>,
    #[serde(default)]
    pub fixes_applied: Vec<String>,
    pub workflow: Workflow,
}

/// Analysis result from workflow analysis.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AnalysisResult {
    pub patterns: Vec<String>,
    pub suggestions: Vec<String>,
    pub node_count: usize,
    pub connection_count: usize,
    pub complexity_score: f64,
}

/// Execution result from running a Gaea2 project.
#[derive(Debug, Clone, Serialize, Deserialize)]
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
    #[serde(skip_serializing_if = "Option::is_none")]
    pub note: Option<String>,
    /// Standard output from CLI execution
    #[serde(skip_serializing_if = "Option::is_none")]
    pub stdout: Option<String>,
    /// Standard error from CLI execution
    #[serde(skip_serializing_if = "Option::is_none")]
    pub stderr: Option<String>,
}

/// Project file metadata.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProjectMetadata {
    pub name: String,
    #[serde(default)]
    pub description: String,
    #[serde(default = "default_version")]
    pub version: String,
    #[serde(default)]
    pub edition: String,
    pub date_created: String,
    pub date_last_saved: String,
}

fn default_version() -> String {
    "2.2.6.0".to_string()
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
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum OptimizationMode {
    Performance,
    Quality,
    Balanced,
}

impl Default for OptimizationMode {
    fn default() -> Self {
        Self::Balanced
    }
}

/// Analysis type for workflow analysis.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum AnalysisType {
    Patterns,
    Performance,
    Quality,
    All,
}

impl Default for AnalysisType {
    fn default() -> Self {
        Self::All
    }
}
