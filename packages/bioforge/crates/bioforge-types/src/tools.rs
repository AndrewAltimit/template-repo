//! MCP tool parameter and result types.

use serde::{Deserialize, Serialize};

use crate::protocol::{LightingMode, ThermalZone};

/// Result of a dispense operation.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DispenseResult {
    pub status: ToolStatus,
    pub actual_volume_ul: f64,
    pub target: String,
    pub reagent: String,
}

/// Result of a thermal operation.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ThermalResult {
    pub status: ToolStatus,
    pub zone: ThermalZone,
    pub current_c: f64,
    pub target_c: f64,
    pub stable: bool,
}

/// Result of a heat shock sequence.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HeatShockResult {
    pub status: ToolStatus,
    pub actual_hold_s: f64,
    pub peak_temp_c: f64,
    pub min_temp_during_hold_c: f64,
    pub thermal_profile_uri: Option<String>,
}

/// Result of an image capture.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CaptureResult {
    pub status: ToolStatus,
    pub image_id: String,
    pub plate_id: String,
    pub lighting_mode: LightingMode,
    pub image_path: String,
}

/// Result of colony counting.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ColonyCountResult {
    pub status: ToolStatus,
    pub plate_id: String,
    pub colony_count: u32,
    pub mean_diameter_px: f64,
    pub size_distribution: Vec<f64>,
}

/// System status snapshot.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SystemStatus {
    pub state: String,
    pub cold_zone_c: f64,
    pub warm_zone_c: f64,
    pub ambient_c: f64,
    pub ambient_humidity: f64,
    pub estop_active: bool,
    pub gantry_position: [f64; 3],
    pub active_protocol: Option<String>,
}

/// Generic tool execution status.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum ToolStatus {
    Complete,
    InProgress,
    PendingHumanApproval,
    Error,
    Aborted,
}
