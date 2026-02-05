//! BioForge MCP tool implementations.
//!
//! Phase 2: Tools validate inputs through SafetyEnforcer before returning
//! mock responses. Real hardware drivers will be wired in subsequent phases.

use std::sync::Arc;

use async_trait::async_trait;
use bioforge_safety::enforcer::SafetyEnforcer;
use mcp_core::prelude::*;
use serde_json::{Value, json};

/// Extract a required string parameter, returning an MCP error if missing.
fn require_str<'a>(args: &'a Value, key: &str) -> Result<&'a str> {
    args.get(key)
        .and_then(|v| v.as_str())
        .ok_or_else(|| MCPError::InvalidParameters(format!("missing required parameter: {key}")))
}

/// Extract a required f64 parameter, returning an MCP error if missing.
fn require_f64(args: &Value, key: &str) -> Result<f64> {
    args.get(key)
        .and_then(|v| v.as_f64())
        .ok_or_else(|| MCPError::InvalidParameters(format!("missing required parameter: {key}")))
}

/// Extract a required u64 parameter, returning an MCP error if missing.
fn require_u64(args: &Value, key: &str) -> Result<u64> {
    args.get(key)
        .and_then(|v| v.as_u64())
        .ok_or_else(|| MCPError::InvalidParameters(format!("missing required parameter: {key}")))
}

/// Map a BioForgeError to an MCP InvalidParameters error.
fn safety_err(e: bioforge_types::error::BioForgeError) -> MCPError {
    MCPError::InvalidParameters(e.to_string())
}

/// Server state shared across all tool implementations.
pub struct BioForgeServer {
    enforcer: Arc<SafetyEnforcer>,
}

impl BioForgeServer {
    pub fn new(enforcer: Arc<SafetyEnforcer>) -> Self {
        Self { enforcer }
    }

    pub fn tools(&self) -> Vec<BoxedTool> {
        let e = &self.enforcer;
        vec![
            Arc::new(DispenseTool(e.clone())),
            Arc::new(AspirateTool(e.clone())),
            Arc::new(MixTool(e.clone())),
            Arc::new(MoveToTool(e.clone())),
            Arc::new(SetTemperatureTool(e.clone())),
            Arc::new(HeatShockTool(e.clone())),
            Arc::new(IncubateTool(e.clone())),
            Arc::new(CaptureImageTool),
            Arc::new(CountColoniesTool),
            Arc::new(LoadProtocolTool),
            Arc::new(GetSystemStatusTool),
            Arc::new(RequestHumanActionTool),
            Arc::new(EmergencyStopTool),
        ]
    }
}

// ============================================================================
// Tool: dispense
// ============================================================================

struct DispenseTool(Arc<SafetyEnforcer>);

#[async_trait]
impl Tool for DispenseTool {
    fn name(&self) -> &str {
        "dispense"
    }

    fn description(&self) -> &str {
        "Dispense precise volume to a target well or plate position. Validates against max volume and reagent inventory."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": "Target well or plate position (e.g., 'plate_1:A1')"
                },
                "volume_ul": {
                    "type": "number",
                    "description": "Volume to dispense in microliters"
                },
                "reagent": {
                    "type": "string",
                    "description": "Reagent name from inventory"
                },
                "flow_rate": {
                    "type": "number",
                    "description": "Flow rate in uL/s (optional, uses default if omitted)"
                }
            },
            "required": ["target", "volume_ul", "reagent"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let target = require_str(&args, "target")?;
        let volume_ul = require_f64(&args, "volume_ul")?;
        let reagent = require_str(&args, "reagent")?;

        self.0.check_rate_limit().map_err(safety_err)?;
        self.0.check_actuator_interval().map_err(safety_err)?;
        self.0
            .validate_and_track_dispense(volume_ul)
            .map_err(safety_err)?;

        if let Some(rate) = args.get("flow_rate").and_then(|v| v.as_f64()) {
            self.0.validate_flow_rate(rate).map_err(safety_err)?;
        }

        tracing::info!(target, volume_ul, reagent, "mock: dispense");

        ToolResult::json(&json!({
            "status": "complete",
            "actual_volume_ul": volume_ul,
            "target": target,
            "reagent": reagent
        }))
    }
}

// ============================================================================
// Tool: aspirate
// ============================================================================

struct AspirateTool(Arc<SafetyEnforcer>);

#[async_trait]
impl Tool for AspirateTool {
    fn name(&self) -> &str {
        "aspirate"
    }

    fn description(&self) -> &str {
        "Aspirate from a source container. Tracks remaining volume in source."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": "Source container identifier"
                },
                "volume_ul": {
                    "type": "number",
                    "description": "Volume to aspirate in microliters"
                },
                "flow_rate": {
                    "type": "number",
                    "description": "Flow rate in uL/s (optional)"
                }
            },
            "required": ["source", "volume_ul"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let source = require_str(&args, "source")?;
        let volume_ul = require_f64(&args, "volume_ul")?;

        self.0.check_rate_limit().map_err(safety_err)?;
        self.0.check_actuator_interval().map_err(safety_err)?;
        self.0.validate_volume(volume_ul).map_err(safety_err)?;

        if let Some(rate) = args.get("flow_rate").and_then(|v| v.as_f64()) {
            self.0.validate_flow_rate(rate).map_err(safety_err)?;
        }

        tracing::info!(source, volume_ul, "mock: aspirate");

        ToolResult::json(&json!({
            "status": "complete",
            "actual_volume_ul": volume_ul,
            "source": source
        }))
    }
}

// ============================================================================
// Tool: mix
// ============================================================================

struct MixTool(Arc<SafetyEnforcer>);

#[async_trait]
impl Tool for MixTool {
    fn name(&self) -> &str {
        "mix"
    }

    fn description(&self) -> &str {
        "Aspirate and dispense repeatedly to mix contents in place."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": "Target well to mix"
                },
                "volume_ul": {
                    "type": "number",
                    "description": "Volume per mixing cycle in microliters"
                },
                "cycles": {
                    "type": "integer",
                    "description": "Number of aspirate-dispense cycles"
                },
                "flow_rate": {
                    "type": "number",
                    "description": "Flow rate in uL/s (optional)"
                }
            },
            "required": ["target", "volume_ul", "cycles"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let target = require_str(&args, "target")?;
        let volume_ul = require_f64(&args, "volume_ul")?;
        let cycles = require_u64(&args, "cycles")?;

        self.0.check_rate_limit().map_err(safety_err)?;
        self.0.check_actuator_interval().map_err(safety_err)?;
        self.0
            .validate_mix_cycles(cycles as u32)
            .map_err(safety_err)?;
        self.0.validate_volume(volume_ul).map_err(safety_err)?;

        if let Some(rate) = args.get("flow_rate").and_then(|v| v.as_f64()) {
            self.0.validate_flow_rate(rate).map_err(safety_err)?;
        }

        tracing::info!(target, volume_ul, cycles, "mock: mix");

        ToolResult::json(&json!({
            "status": "complete",
            "target": target,
            "cycles_completed": cycles
        }))
    }
}

// ============================================================================
// Tool: move_to
// ============================================================================

struct MoveToTool(Arc<SafetyEnforcer>);

#[async_trait]
impl Tool for MoveToTool {
    fn name(&self) -> &str {
        "move_to"
    }

    fn description(&self) -> &str {
        "Move gantry to absolute position. Validates against enclosure bounds."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "x_mm": { "type": "number", "description": "X position in mm" },
                "y_mm": { "type": "number", "description": "Y position in mm" },
                "z_mm": { "type": "number", "description": "Z position in mm (defaults to safe travel height)" }
            },
            "required": ["x_mm", "y_mm"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let x = require_f64(&args, "x_mm")?;
        let y = require_f64(&args, "y_mm")?;
        let z = args
            .get("z_mm")
            .and_then(|v| v.as_f64())
            .unwrap_or_else(|| self.0.safe_travel_height());

        self.0.check_rate_limit().map_err(safety_err)?;
        self.0.check_actuator_interval().map_err(safety_err)?;
        self.0.validate_position(x, y, z).map_err(safety_err)?;

        tracing::info!(x, y, z, "mock: move to");

        ToolResult::json(&json!({
            "status": "complete",
            "position": { "x_mm": x, "y_mm": y, "z_mm": z }
        }))
    }
}

// ============================================================================
// Tool: set_temperature
// ============================================================================

struct SetTemperatureTool(Arc<SafetyEnforcer>);

#[async_trait]
impl Tool for SetTemperatureTool {
    fn name(&self) -> &str {
        "set_temperature"
    }

    fn description(&self) -> &str {
        "Set a thermal zone to target temperature. PID-controlled with overshoot protection."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "zone": {
                    "type": "string",
                    "enum": ["cold", "warm"],
                    "description": "Thermal zone identifier"
                },
                "target_c": {
                    "type": "number",
                    "description": "Target temperature in Celsius"
                },
                "hold_seconds": {
                    "type": "integer",
                    "description": "Duration to hold at target (optional)"
                }
            },
            "required": ["zone", "target_c"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let zone = require_str(&args, "zone")?;
        let target_c = require_f64(&args, "target_c")?;

        self.0.check_rate_limit().map_err(safety_err)?;
        self.0.check_actuator_interval().map_err(safety_err)?;
        self.0.validate_temperature(target_c).map_err(safety_err)?;

        tracing::info!(zone, target_c, "mock: set temperature");

        ToolResult::json(&json!({
            "status": "complete",
            "zone": zone,
            "current_c": target_c,
            "target_c": target_c,
            "stable": true
        }))
    }
}

// ============================================================================
// Tool: heat_shock
// ============================================================================

struct HeatShockTool(Arc<SafetyEnforcer>);

#[async_trait]
impl Tool for HeatShockTool {
    fn name(&self) -> &str {
        "heat_shock"
    }

    fn description(&self) -> &str {
        "Execute heat shock sequence: ramp up, hold precisely, ramp down. Atomic operation."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "ramp_to_c": {
                    "type": "number",
                    "description": "Target heat shock temperature in Celsius"
                },
                "hold_s": {
                    "type": "integer",
                    "description": "Hold duration in seconds"
                },
                "return_to_c": {
                    "type": "number",
                    "description": "Temperature to return to after hold"
                }
            },
            "required": ["ramp_to_c", "hold_s", "return_to_c"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let ramp_to = require_f64(&args, "ramp_to_c")?;
        let hold_s = require_u64(&args, "hold_s")?;
        let return_to = require_f64(&args, "return_to_c")?;

        self.0.check_rate_limit().map_err(safety_err)?;
        self.0.check_actuator_interval().map_err(safety_err)?;
        self.0.validate_temperature(ramp_to).map_err(safety_err)?;
        self.0.validate_temperature(return_to).map_err(safety_err)?;
        self.0
            .validate_heat_shock_hold_s(hold_s)
            .map_err(safety_err)?;

        tracing::info!(ramp_to, hold_s, return_to, "mock: heat shock");

        ToolResult::json(&json!({
            "status": "complete",
            "actual_hold_s": hold_s as f64 + 0.2,
            "peak_temp_c": ramp_to + 0.3,
            "min_temp_during_hold_c": ramp_to - 0.3,
            "thermal_profile": "bioforge://data/mock/heat_shock.csv"
        }))
    }
}

// ============================================================================
// Tool: incubate
// ============================================================================

struct IncubateTool(Arc<SafetyEnforcer>);

#[async_trait]
impl Tool for IncubateTool {
    fn name(&self) -> &str {
        "incubate"
    }

    fn description(&self) -> &str {
        "Long-duration temperature hold with periodic monitoring and drift alerts."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "zone": {
                    "type": "string",
                    "enum": ["cold", "warm"],
                    "description": "Thermal zone"
                },
                "target_c": {
                    "type": "number",
                    "description": "Incubation temperature in Celsius"
                },
                "duration_hours": {
                    "type": "number",
                    "description": "Incubation duration in hours"
                }
            },
            "required": ["zone", "target_c", "duration_hours"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let zone = require_str(&args, "zone")?;
        let target_c = require_f64(&args, "target_c")?;
        let hours = require_f64(&args, "duration_hours")?;

        self.0.check_rate_limit().map_err(safety_err)?;
        self.0.check_actuator_interval().map_err(safety_err)?;
        self.0.validate_temperature(target_c).map_err(safety_err)?;
        self.0
            .validate_incubation_hours(hours)
            .map_err(safety_err)?;

        tracing::info!(zone, target_c, hours, "mock: incubate");

        ToolResult::json(&json!({
            "status": "complete",
            "zone": zone,
            "target_c": target_c,
            "duration_hours": hours,
            "mean_temp_c": target_c,
            "max_drift_c": 0.2
        }))
    }
}

// ============================================================================
// Tool: capture_plate_image
// ============================================================================

struct CaptureImageTool;

#[async_trait]
impl Tool for CaptureImageTool {
    fn name(&self) -> &str {
        "capture_plate_image"
    }

    fn description(&self) -> &str {
        "Capture high-res image of plate. Modes: white, uv_blue (for GFP), dark_field."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "plate_id": {
                    "type": "string",
                    "description": "Plate identifier"
                },
                "lighting_mode": {
                    "type": "string",
                    "enum": ["white", "uv_blue", "dark_field"],
                    "default": "white",
                    "description": "Illumination mode"
                }
            },
            "required": ["plate_id"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let plate_id = require_str(&args, "plate_id")?;
        let mode = args
            .get("lighting_mode")
            .and_then(|v| v.as_str())
            .unwrap_or("white");

        tracing::info!(plate_id, mode, "mock: capture plate image");

        let image_id = format!("{plate_id}_mock_001");
        ToolResult::json(&json!({
            "status": "complete",
            "image_id": image_id,
            "plate_id": plate_id,
            "lighting_mode": mode,
            "image_path": format!("bioforge://images/{image_id}.png"),
            "resolution": "4608x2592"
        }))
    }
}

// ============================================================================
// Tool: count_colonies
// ============================================================================

struct CountColoniesTool;

#[async_trait]
impl Tool for CountColoniesTool {
    fn name(&self) -> &str {
        "count_colonies"
    }

    fn description(&self) -> &str {
        "Run colony counting pipeline on captured image. Returns count, size distribution, coordinates."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "plate_id": {
                    "type": "string",
                    "description": "Plate identifier"
                },
                "image_id": {
                    "type": "string",
                    "description": "Image identifier from capture_plate_image"
                }
            },
            "required": ["plate_id", "image_id"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let plate_id = require_str(&args, "plate_id")?;
        let image_id = require_str(&args, "image_id")?;

        tracing::info!(plate_id, image_id, "mock: count colonies");

        ToolResult::json(&json!({
            "status": "complete",
            "plate_id": plate_id,
            "colony_count": 42,
            "mean_diameter_px": 15.3,
            "size_distribution": [8.0, 12.0, 15.0, 18.0, 22.0],
            "confidence": 0.94
        }))
    }
}

// ============================================================================
// Tool: load_protocol
// ============================================================================

struct LoadProtocolTool;

#[async_trait]
impl Tool for LoadProtocolTool {
    fn name(&self) -> &str {
        "load_protocol"
    }

    fn description(&self) -> &str {
        "Load a saved protocol TOML file and validate all steps against current hardware config."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "protocol_id": {
                    "type": "string",
                    "description": "Protocol identifier (filename without .toml)"
                }
            },
            "required": ["protocol_id"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let protocol_id = require_str(&args, "protocol_id")?;

        tracing::info!(protocol_id, "mock: load protocol");

        ToolResult::json(&json!({
            "status": "complete",
            "protocol_id": protocol_id,
            "steps": 8,
            "human_gates": 2,
            "validation": "passed"
        }))
    }
}

// ============================================================================
// Tool: get_system_status
// ============================================================================

struct GetSystemStatusTool;

#[async_trait]
impl Tool for GetSystemStatusTool {
    fn name(&self) -> &str {
        "get_system_status"
    }

    fn description(&self) -> &str {
        "Returns all sensor readings, actuator states, reagent inventory, and safety status."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {}
        })
    }

    async fn execute(&self, _args: Value) -> Result<ToolResult> {
        tracing::info!("mock: get system status");

        ToolResult::json(&json!({
            "state": "idle",
            "cold_zone_c": 4.1,
            "warm_zone_c": 22.5,
            "ambient_c": 22.5,
            "ambient_humidity_pct": 45.0,
            "estop_active": false,
            "gantry_position": [0.0, 0.0, 0.0],
            "active_protocol": null,
            "uptime_s": 3600
        }))
    }
}

// ============================================================================
// Tool: request_human_action
// ============================================================================

struct RequestHumanActionTool;

#[async_trait]
impl Tool for RequestHumanActionTool {
    fn name(&self) -> &str {
        "request_human_action"
    }

    fn description(&self) -> &str {
        "Pause execution and request human intervention. Blocks until confirmed via touchscreen or API."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "action_description": {
                    "type": "string",
                    "description": "Description of the required human action"
                },
                "timeout_min": {
                    "type": "integer",
                    "description": "Maximum wait time in minutes before timeout"
                }
            },
            "required": ["action_description", "timeout_min"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let description = require_str(&args, "action_description")?;
        let timeout = require_u64(&args, "timeout_min")?;

        tracing::info!(description, timeout, "mock: request human action");

        ToolResult::json(&json!({
            "status": "pending_human_approval",
            "action_description": description,
            "timeout_min": timeout,
            "mock_note": "In production, this blocks until human confirms via touchscreen"
        }))
    }
}

// ============================================================================
// Tool: emergency_stop
// ============================================================================

struct EmergencyStopTool;

#[async_trait]
impl Tool for EmergencyStopTool {
    fn name(&self) -> &str {
        "emergency_stop"
    }

    fn description(&self) -> &str {
        "Immediately halt all actuators, disable heaters, and safe the system."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {}
        })
    }

    async fn execute(&self, _args: Value) -> Result<ToolResult> {
        tracing::warn!("EMERGENCY STOP activated");

        ToolResult::json(&json!({
            "status": "complete",
            "action": "emergency_stop",
            "all_actuators": "halted",
            "heaters": "disabled",
            "pumps": "stopped",
            "gantry": "locked"
        }))
    }
}
