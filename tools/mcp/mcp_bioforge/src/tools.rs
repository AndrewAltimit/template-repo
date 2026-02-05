//! BioForge MCP tool implementations.
//!
//! Phase 1: All tools return mock responses for end-to-end agent integration
//! testing. Real hardware drivers will be wired in subsequent phases.

use std::sync::Arc;

use async_trait::async_trait;
use mcp_core::prelude::*;
use serde_json::{Value, json};

/// Server state shared across all tool implementations.
pub struct BioForgeServer;

impl BioForgeServer {
    pub fn new() -> Self {
        Self
    }

    pub fn tools(&self) -> Vec<BoxedTool> {
        vec![
            Arc::new(DispenseTool),
            Arc::new(AspirateTool),
            Arc::new(MixTool),
            Arc::new(MoveToTool),
            Arc::new(SetTemperatureTool),
            Arc::new(HeatShockTool),
            Arc::new(IncubateTool),
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

struct DispenseTool;

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
        let target = args
            .get("target")
            .and_then(|v| v.as_str())
            .unwrap_or("unknown");
        let volume_ul = args
            .get("volume_ul")
            .and_then(|v| v.as_f64())
            .unwrap_or(0.0);
        let reagent = args
            .get("reagent")
            .and_then(|v| v.as_str())
            .unwrap_or("unknown");

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

struct AspirateTool;

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
        let source = args
            .get("source")
            .and_then(|v| v.as_str())
            .unwrap_or("unknown");
        let volume_ul = args
            .get("volume_ul")
            .and_then(|v| v.as_f64())
            .unwrap_or(0.0);

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

struct MixTool;

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
        let target = args
            .get("target")
            .and_then(|v| v.as_str())
            .unwrap_or("unknown");
        let volume_ul = args
            .get("volume_ul")
            .and_then(|v| v.as_f64())
            .unwrap_or(0.0);
        let cycles = args.get("cycles").and_then(|v| v.as_u64()).unwrap_or(3);

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

struct MoveToTool;

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
                "z_mm": { "type": "number", "description": "Z position in mm (optional)" }
            },
            "required": ["x_mm", "y_mm"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let x = args.get("x_mm").and_then(|v| v.as_f64()).unwrap_or(0.0);
        let y = args.get("y_mm").and_then(|v| v.as_f64()).unwrap_or(0.0);
        let z = args.get("z_mm").and_then(|v| v.as_f64()).unwrap_or(0.0);

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

struct SetTemperatureTool;

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
        let zone = args.get("zone").and_then(|v| v.as_str()).unwrap_or("warm");
        let target_c = args
            .get("target_c")
            .and_then(|v| v.as_f64())
            .unwrap_or(37.0);

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

struct HeatShockTool;

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
        let ramp_to = args
            .get("ramp_to_c")
            .and_then(|v| v.as_f64())
            .unwrap_or(42.0);
        let hold_s = args.get("hold_s").and_then(|v| v.as_u64()).unwrap_or(45);
        let return_to = args
            .get("return_to_c")
            .and_then(|v| v.as_f64())
            .unwrap_or(4.0);

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

struct IncubateTool;

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
        let zone = args.get("zone").and_then(|v| v.as_str()).unwrap_or("warm");
        let target_c = args
            .get("target_c")
            .and_then(|v| v.as_f64())
            .unwrap_or(37.0);
        let hours = args
            .get("duration_hours")
            .and_then(|v| v.as_f64())
            .unwrap_or(16.0);

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
        let plate_id = args
            .get("plate_id")
            .and_then(|v| v.as_str())
            .unwrap_or("plate_1");
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
            "image_path": format!("/tmp/bioforge/images/{image_id}.png"),
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
        let plate_id = args
            .get("plate_id")
            .and_then(|v| v.as_str())
            .unwrap_or("plate_1");
        let image_id = args
            .get("image_id")
            .and_then(|v| v.as_str())
            .unwrap_or("unknown");

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
        let protocol_id = args
            .get("protocol_id")
            .and_then(|v| v.as_str())
            .unwrap_or("unknown");

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
        let description = args
            .get("action_description")
            .and_then(|v| v.as_str())
            .unwrap_or("unknown action");
        let timeout = args
            .get("timeout_min")
            .and_then(|v| v.as_u64())
            .unwrap_or(30);

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
