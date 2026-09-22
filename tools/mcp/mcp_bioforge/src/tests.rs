//! End-to-end tests that drive the tools through `Tool::execute` exactly as
//! the MCP transport does, against simulated or deliberately faulty
//! hardware. No network, hardware or external services are needed.

use std::collections::HashSet;
use std::path::{Path, PathBuf};
use std::sync::Arc;
use std::time::Duration;

use async_trait::async_trait;
use bioforge_hal::pumps::PumpDriver;
use bioforge_hal::thermal::{HeatShockReport, ThermalController, ThermalReading};
use bioforge_safety::{AuditLog, SafetyEnforcer};
use bioforge_types::config::SafetyLimits;
use bioforge_types::error::BioForgeError;
use bioforge_types::protocol::ThermalZone;
use mcp_core::prelude::{BoxedTool, Content, MCPError, ToolResult};
use serde_json::{Value, json};

use crate::config::tests::{test_bounds, test_limits};
use crate::lab::{Hardware, Lab, LabOptions, Timeouts};
use crate::sim::simulated_hardware;
use crate::tools::all_tools;

const GOOD_PROTOCOL: &str = r#"
name = "good"
version = "1.0"
description = "valid test protocol"

[[steps]]
id = 1
name = "Dispense"
human_gate = false
[steps.action]
type = "dispense"
target = "plate_1:A1"
volume_ul = 100.0
reagent = "lb"

[[steps]]
id = 2
name = "Gate"
human_gate = true
[steps.action]
type = "request_human_action"
description = "Load plates"
timeout_min = 5
"#;

struct Harness {
    tools: Vec<BoxedTool>,
    lab: Arc<Lab>,
    dir: tempfile::TempDir,
}

impl Harness {
    fn confirm_dir(&self) -> PathBuf {
        self.dir.path().join("confirm")
    }

    async fn call(&self, name: &str, args: Value) -> mcp_core::Result<ToolResult> {
        let tool = self
            .tools
            .iter()
            .find(|t| t.name() == name)
            .unwrap_or_else(|| panic!("no tool {name}"));
        tool.execute(args).await
    }

    /// Call and expect a successful (non-isError) JSON result.
    async fn ok(&self, name: &str, args: Value) -> Value {
        let r = self
            .call(name, args)
            .await
            .unwrap_or_else(|e| panic!("{name} failed: {e}"));
        assert!(!r.is_error, "{name} returned isError: {}", text(&r));
        serde_json::from_str(&text(&r)).expect("tool output is JSON")
    }

    /// Call and expect an isError result; returns its text.
    async fn refused(&self, name: &str, args: Value) -> String {
        let r = self
            .call(name, args)
            .await
            .unwrap_or_else(|e| panic!("{name} should be refused, got protocol error: {e}"));
        assert!(r.is_error, "{name} should be refused, got: {}", text(&r));
        text(&r)
    }

    /// Call and expect an `InvalidParameters` error; returns its message.
    async fn invalid(&self, name: &str, args: Value) -> String {
        match self.call(name, args).await {
            Err(MCPError::InvalidParameters(msg)) => msg,
            Err(other) => panic!("{name}: expected InvalidParameters, got {other}"),
            Ok(r) => panic!("{name}: expected InvalidParameters, got {}", text(&r)),
        }
    }
}

fn text(r: &ToolResult) -> String {
    match &r.content[0] {
        Content::Text { text } => text.clone(),
        other => panic!("unexpected content {other:?}"),
    }
}

fn harness_with(
    limits: SafetyLimits,
    hw: Hardware,
    timeouts: Timeouts,
    audit: Option<&Path>,
) -> Harness {
    let dir = tempfile::tempdir().unwrap();
    let protocols = dir.path().join("protocols");
    std::fs::create_dir_all(protocols.join("custom")).unwrap();
    std::fs::write(protocols.join("good.toml"), GOOD_PROTOCOL).unwrap();
    std::fs::copy(
        Path::new(env!("CARGO_MANIFEST_DIR"))
            .join("../../../packages/bioforge/protocols/odin_crispr_rpsL.toml"),
        protocols.join("odin_crispr_rpsL.toml"),
    )
    .unwrap();
    let confirm = dir.path().join("confirm");
    std::fs::create_dir_all(&confirm).unwrap();

    let enforcer = Arc::new(SafetyEnforcer::new(limits, test_bounds()));
    let lab = Arc::new(Lab::new(
        enforcer,
        hw,
        LabOptions {
            protocols_dir: protocols,
            confirm_dir: Some(confirm),
            audit_log: audit.map(|p| AuditLog::new(p).unwrap()),
            timeouts,
        },
    ));
    Harness {
        tools: all_tools(lab.clone()),
        lab,
        dir,
    }
}

fn harness() -> Harness {
    harness_with(
        test_limits(),
        simulated_hardware(),
        Timeouts::default(),
        None,
    )
}

// ----------------------------------------------------------------------------
// Faulty hardware doubles
// ----------------------------------------------------------------------------

/// A pump whose operations never complete.
struct HangingPump;

#[async_trait]
impl PumpDriver for HangingPump {
    async fn dispense(&self, _v: f64, _r: Option<f64>) -> Result<f64, BioForgeError> {
        std::future::pending().await
    }
    async fn aspirate(&self, _v: f64, _r: Option<f64>) -> Result<f64, BioForgeError> {
        std::future::pending().await
    }
    async fn prime(&self, _v: f64) -> Result<(), BioForgeError> {
        std::future::pending().await
    }
}

/// A pump that always reports a hardware fault.
struct FaultyPump;

#[async_trait]
impl PumpDriver for FaultyPump {
    async fn dispense(&self, _v: f64, _r: Option<f64>) -> Result<f64, BioForgeError> {
        Err(BioForgeError::HardwareFault("syringe stalled".into()))
    }
    async fn aspirate(&self, _v: f64, _r: Option<f64>) -> Result<f64, BioForgeError> {
        Err(BioForgeError::HardwareFault("syringe stalled".into()))
    }
    async fn prime(&self, _v: f64) -> Result<(), BioForgeError> {
        Ok(())
    }
}

/// A thermal controller that overshoots every heat shock by 5 C.
struct OvershootingThermal;

#[async_trait]
impl ThermalController for OvershootingThermal {
    async fn set_temperature(&self, _z: ThermalZone, _t: f64) -> Result<(), BioForgeError> {
        Ok(())
    }
    async fn read_temperature(&self, zone: ThermalZone) -> Result<ThermalReading, BioForgeError> {
        Ok(ThermalReading {
            zone,
            current_c: 20.0,
            target_c: 20.0,
            stable: false,
        })
    }
    async fn heat_shock(
        &self,
        ramp: f64,
        hold: u64,
        _ret: f64,
    ) -> Result<HeatShockReport, BioForgeError> {
        Ok(HeatShockReport {
            actual_hold_s: hold as f64,
            peak_temp_c: ramp + 5.0,
            min_temp_during_hold_c: ramp,
        })
    }
}

fn hw_with_pump(p: Arc<dyn PumpDriver>) -> Hardware {
    let mut hw = simulated_hardware();
    hw.pumps = p;
    hw
}

// ----------------------------------------------------------------------------
// Tool surface
// ----------------------------------------------------------------------------

#[test]
fn tool_names_are_unique_and_backward_compatible() {
    let h = harness();
    let names: HashSet<&str> = h.tools.iter().map(|t| t.name()).collect();
    assert_eq!(names.len(), h.tools.len());
    for legacy in [
        "dispense",
        "aspirate",
        "mix",
        "move_to",
        "set_temperature",
        "heat_shock",
        "incubate",
        "capture_plate_image",
        "count_colonies",
        "load_protocol",
        "get_system_status",
        "request_human_action",
        "emergency_stop",
    ] {
        assert!(names.contains(legacy), "missing legacy tool {legacy}");
    }
}

#[test]
fn schemas_are_well_formed() {
    let h = harness();
    for t in &h.tools {
        let s = t.schema();
        assert_eq!(s["type"], "object", "{}", t.name());
        let props = s["properties"].as_object().expect("properties object");
        for req in s["required"].as_array().into_iter().flatten() {
            let req = req.as_str().unwrap();
            assert!(
                props.contains_key(req),
                "{}: required {req} not in properties",
                t.name()
            );
        }
        assert!(!t.description().is_empty());
    }
}

// ----------------------------------------------------------------------------
// Argument parsing
// ----------------------------------------------------------------------------

#[tokio::test]
async fn missing_and_mistyped_params_are_invalid_parameters() {
    let h = harness();
    let msg = h
        .invalid("dispense", json!({"target": "p:A1", "volume_ul": 10.0}))
        .await;
    assert!(msg.contains("reagent"), "{msg}");

    let msg = h
        .invalid(
            "dispense",
            json!({"target": "p:A1", "volume_ul": "ten", "reagent": "lb"}),
        )
        .await;
    assert!(msg.contains("dispense"), "{msg}");

    let msg = h
        .invalid("set_temperature", json!({"zone": "hot", "target_c": 30.0}))
        .await;
    assert!(msg.contains("hot") || msg.contains("variant"), "{msg}");

    let msg = h
        .invalid(
            "capture_plate_image",
            json!({"plate_id": "p1", "lighting_mode": "infrared"}),
        )
        .await;
    assert!(msg.contains("infrared") || msg.contains("variant"), "{msg}");
}

#[tokio::test]
async fn mix_cycles_do_not_truncate() {
    // 2^32 + 1 used to be cast to 1 with `as u32` and pass validation.
    let h = harness();
    h.invalid(
        "mix",
        json!({"target": "t", "volume_ul": 10.0, "cycles": 4_294_967_297u64}),
    )
    .await;
    h.invalid(
        "mix",
        json!({"target": "t", "volume_ul": 10.0, "cycles": 2.5}),
    )
    .await;
    h.invalid(
        "mix",
        json!({"target": "t", "volume_ul": 10.0, "cycles": -1}),
    )
    .await;
    let out = h
        .ok(
            "mix",
            json!({"target": "t", "volume_ul": 10.0, "cycles": 3}),
        )
        .await;
    assert_eq!(out["cycles_completed"], 3);
}

#[tokio::test]
async fn integral_floats_are_accepted_for_integer_fields() {
    let h = harness();
    let out = h
        .ok(
            "heat_shock",
            json!({"ramp_to_c": 42.0, "hold_s": 45.0, "return_to_c": 4.0}),
        )
        .await;
    assert_eq!(out["requested_hold_s"], 45);
}

#[tokio::test]
async fn null_arguments_accepted_for_parameterless_tools() {
    let h = harness();
    h.ok("get_system_status", Value::Null).await;
    h.ok("list_protocols", json!({})).await;
}

#[tokio::test]
async fn identifiers_are_validated() {
    let h = harness();
    h.invalid(
        "capture_plate_image",
        json!({"plate_id": "../../etc/passwd"}),
    )
    .await;
    h.invalid(
        "dispense",
        json!({"target": "a;rm -rf", "volume_ul": 10.0, "reagent": "lb"}),
    )
    .await;
    h.invalid(
        "load_protocol",
        json!({"protocol_id": "../config/hardware"}),
    )
    .await;
}

// ----------------------------------------------------------------------------
// Safety enforcement
// ----------------------------------------------------------------------------

#[tokio::test]
async fn safety_limits_are_enforced_as_tool_errors() {
    let h = harness();
    let e = h
        .refused(
            "dispense",
            json!({"target": "p:A1", "volume_ul": 5000.0, "reagent": "lb"}),
        )
        .await;
    assert!(e.contains("volume out of range"), "{e}");
    let e = h
        .refused("set_temperature", json!({"zone": "warm", "target_c": 55.0}))
        .await;
    assert!(e.contains("temperature out of range"), "{e}");
    let e = h
        .refused("move_to", json!({"x_mm": 500.0, "y_mm": 10.0}))
        .await;
    assert!(e.contains("out of bounds"), "{e}");
    let e = h
        .refused(
            "heat_shock",
            json!({"ramp_to_c": 42.0, "hold_s": 301, "return_to_c": 4.0}),
        )
        .await;
    assert!(e.contains("heat shock hold"), "{e}");
    let e = h
        .refused(
            "incubate",
            json!({"zone": "warm", "target_c": 37.0, "duration_hours": 100.0}),
        )
        .await;
    assert!(e.contains("incubation"), "{e}");
}

#[tokio::test]
async fn rejected_flow_rate_does_not_consume_dispense_budget() {
    // Previously the volume was tracked before the flow rate was checked.
    let h = harness();
    h.refused(
        "dispense",
        json!({"target": "p:A1", "volume_ul": 500.0, "reagent": "lb", "flow_rate": 9999.0}),
    )
    .await;
    let st = h.ok("get_system_status", json!({})).await;
    assert_eq!(st["dispense"]["cumulative_dispensed_ul"], 0.0);
}

#[tokio::test]
async fn cumulative_dispense_budget() {
    let mut limits = test_limits();
    limits.volume.max_total_ml = 1.5;
    let h = harness_with(limits, simulated_hardware(), Timeouts::default(), None);
    let out = h
        .ok(
            "dispense",
            json!({"target": "p:A1", "volume_ul": 1000.0, "reagent": "lb"}),
        )
        .await;
    assert_eq!(out["remaining_run_budget_ul"], 500.0);
    let e = h
        .refused(
            "dispense",
            json!({"target": "p:A2", "volume_ul": 1000.0, "reagent": "lb"}),
        )
        .await;
    assert!(e.contains("cumulative dispense"), "{e}");
}

#[tokio::test]
async fn rate_limit_applies_to_actuators_only() {
    let mut limits = test_limits();
    limits.rate.max_calls_per_minute = 2;
    let h = harness_with(limits, simulated_hardware(), Timeouts::default(), None);
    h.ok("move_to", json!({"x_mm": 1.0, "y_mm": 1.0})).await;
    h.ok("move_to", json!({"x_mm": 2.0, "y_mm": 1.0})).await;
    let e = h
        .refused("move_to", json!({"x_mm": 3.0, "y_mm": 1.0}))
        .await;
    assert!(e.contains("rate limit"), "{e}");
    // Status and e-stop are never throttled.
    h.ok("get_system_status", json!({})).await;
    h.ok("emergency_stop", json!({})).await;
}

#[tokio::test]
async fn actuator_interval_is_waited_out_not_rejected() {
    let mut limits = test_limits();
    limits.rate.min_actuator_interval_ms = 50;
    let h = harness_with(limits, simulated_hardware(), Timeouts::default(), None);
    h.ok("move_to", json!({"x_mm": 1.0, "y_mm": 1.0})).await;
    h.ok("move_to", json!({"x_mm": 2.0, "y_mm": 1.0})).await;
}

// ----------------------------------------------------------------------------
// Motion and thermal state
// ----------------------------------------------------------------------------

#[tokio::test]
async fn status_reflects_motion_and_thermal_state() {
    let h = harness();
    let out = h.ok("move_to", json!({"x_mm": 10.0, "y_mm": 20.0})).await;
    assert_eq!(
        out["position"]["z_mm"], 15.0,
        "z defaults to safe travel height"
    );
    h.ok("set_temperature", json!({"zone": "cold", "target_c": 4.0}))
        .await;

    let st = h.ok("get_system_status", json!({})).await;
    assert_eq!(st["gantry_position"], json!([10.0, 20.0, 15.0]));
    assert_eq!(st["cold_zone_c"], 4.0);
    assert_eq!(st["thermal_zones"]["cold"]["setpoint_c"], 4.0);
    assert_eq!(st["simulated"], true);
    assert_eq!(st["state"], "idle");

    h.ok("home_gantry", json!({})).await;
    let st = h.ok("get_system_status", json!({})).await;
    assert_eq!(st["gantry_position"], json!([0.0, 0.0, 0.0]));
}

#[tokio::test]
async fn incubation_is_tracked_and_cancelled_by_setpoint_change() {
    let h = harness();
    let out = h
        .ok(
            "incubate",
            json!({"zone": "warm", "target_c": 37.0, "duration_hours": 16}),
        )
        .await;
    assert_eq!(out["status"], "started");
    let st = h.ok("get_system_status", json!({})).await;
    assert_eq!(st["state"], "incubating");
    assert_eq!(st["warm_zone_c"], 37.0);
    assert!(
        st["thermal_zones"]["warm"]["incubation"]["remaining_s"]
            .as_i64()
            .unwrap()
            > 0
    );

    let out = h
        .ok("set_temperature", json!({"zone": "warm", "target_c": 30.0}))
        .await;
    assert!(out["cancelled_incubation"].is_object());
    let st = h.ok("get_system_status", json!({})).await;
    assert_eq!(st["state"], "idle");
}

#[tokio::test]
async fn heat_shock_out_of_tolerance_is_reported() {
    let mut hw = simulated_hardware();
    hw.thermal = Arc::new(OvershootingThermal);
    let h = harness_with(test_limits(), hw, Timeouts::default(), None);
    let e = h
        .refused(
            "heat_shock",
            json!({"ramp_to_c": 42.0, "hold_s": 45, "return_to_c": 4.0}),
        )
        .await;
    assert!(e.contains("compromised"), "{e}");
}

// ----------------------------------------------------------------------------
// Hardware faults, timeouts, e-stop
// ----------------------------------------------------------------------------

#[tokio::test]
async fn hardware_faults_surface_as_tool_errors() {
    let h = harness_with(
        test_limits(),
        hw_with_pump(Arc::new(FaultyPump)),
        Timeouts::default(),
        None,
    );
    let e = h
        .refused("aspirate", json!({"source": "tube_a", "volume_ul": 10.0}))
        .await;
    assert!(e.contains("syringe stalled"), "{e}");
}

#[tokio::test]
async fn hung_hardware_times_out() {
    let timeouts = Timeouts {
        pump: Duration::from_millis(50),
        ..Timeouts::default()
    };
    let h = harness_with(
        test_limits(),
        hw_with_pump(Arc::new(HangingPump)),
        timeouts,
        None,
    );
    let e = h
        .refused("aspirate", json!({"source": "tube_a", "volume_ul": 10.0}))
        .await;
    assert!(e.contains("did not complete"), "{e}");
}

#[tokio::test]
async fn busy_hardware_times_out_instead_of_queueing_forever() {
    let timeouts = Timeouts {
        hardware_busy: Duration::from_millis(50),
        ..Timeouts::default()
    };
    let h = Arc::new(harness_with(
        test_limits(),
        hw_with_pump(Arc::new(HangingPump)),
        timeouts,
        None,
    ));
    let h2 = h.clone();
    let first = tokio::spawn(async move {
        h2.call("aspirate", json!({"source": "a", "volume_ul": 10.0}))
            .await
    });
    tokio::time::sleep(Duration::from_millis(20)).await;
    let e = h
        .refused("move_to", json!({"x_mm": 1.0, "y_mm": 1.0}))
        .await;
    assert!(e.contains("hardware busy"), "{e}");
    first.abort();
}

#[tokio::test]
async fn emergency_stop_cancels_in_flight_actuation() {
    let h = Arc::new(harness_with(
        test_limits(),
        hw_with_pump(Arc::new(HangingPump)),
        Timeouts::default(),
        None,
    ));
    let h2 = h.clone();
    let inflight = tokio::spawn(async move {
        h2.call(
            "dispense",
            json!({"target": "p:A1", "volume_ul": 10.0, "reagent": "lb"}),
        )
        .await
    });
    tokio::time::sleep(Duration::from_millis(50)).await;
    h.ok("emergency_stop", json!({"reason": "test"})).await;

    let r = tokio::time::timeout(Duration::from_secs(5), inflight)
        .await
        .expect("in-flight call must be cancelled promptly")
        .unwrap()
        .unwrap();
    assert!(r.is_error);
    assert!(text(&r).contains("emergency stop"), "{}", text(&r));
}

#[tokio::test]
async fn emergency_stop_latches() {
    let h = harness();
    h.ok("set_temperature", json!({"zone": "warm", "target_c": 42.0}))
        .await;
    let out = h.ok("emergency_stop", json!({"reason": "smoke"})).await;
    assert_eq!(out["already_active"], false);
    assert_eq!(out["latched"], true);

    for (tool, args) in [
        ("move_to", json!({"x_mm": 1.0, "y_mm": 1.0})),
        (
            "dispense",
            json!({"target": "p:A1", "volume_ul": 10.0, "reagent": "lb"}),
        ),
        ("set_temperature", json!({"zone": "cold", "target_c": 4.0})),
        ("home_gantry", json!({})),
        (
            "request_human_action",
            json!({"description": "x", "timeout_min": 1}),
        ),
    ] {
        let e = h.refused(tool, args).await;
        assert!(e.contains("emergency stop"), "{tool}: {e}");
    }
    // Imaging and status still work so the operator can assess the deck.
    h.ok("capture_plate_image", json!({"plate_id": "p1"})).await;
    let st = h.ok("get_system_status", json!({})).await;
    assert_eq!(st["estop_active"], true);
    assert_eq!(st["state"], "emergency_stopped");
    assert_eq!(st["estop_reason"], "smoke");
    // Heaters safed to ambient.
    assert_eq!(st["warm_zone_c"], crate::sim::SIM_AMBIENT_C);

    let again = h.ok("emergency_stop", json!({})).await;
    assert_eq!(again["already_active"], true);
}

// ----------------------------------------------------------------------------
// Human gates
// ----------------------------------------------------------------------------

#[tokio::test]
async fn human_gate_blocks_actuators_until_confirmed() {
    let h = harness();
    let out = h
        .ok(
            "request_human_action",
            json!({"description": "Load plates", "timeout_min": 30}),
        )
        .await;
    assert_eq!(out["status"], "pending_human_approval");
    let id = out["action_id"].as_str().unwrap().to_string();

    let e = h
        .refused("move_to", json!({"x_mm": 1.0, "y_mm": 1.0}))
        .await;
    assert!(e.contains("human gate pending"), "{e}");
    let e = h
        .refused(
            "request_human_action",
            json!({"description": "again", "timeout_min": 5}),
        )
        .await;
    assert!(e.contains(&id), "{e}");
    let st = h.ok("get_system_status", json!({})).await;
    assert_eq!(st["state"], "awaiting_human");

    std::fs::write(h.confirm_dir().join(format!("{id}.confirmed")), "ok").unwrap();
    let out = h
        .ok(
            "get_human_action_status",
            json!({"action_id": id, "wait_seconds": 2}),
        )
        .await;
    assert_eq!(out["status"], "confirmed");
    h.ok("move_to", json!({"x_mm": 1.0, "y_mm": 1.0})).await;
}

#[tokio::test]
async fn human_gate_expires() {
    let h = harness();
    let out = h
        .ok(
            "request_human_action",
            json!({"description": "Load plates", "timeout_min": 1}),
        )
        .await;
    let id = out["action_id"].as_str().unwrap().to_string();
    h.lab.expire_human_actions_for_test().await;
    let out = h
        .ok("get_human_action_status", json!({"action_id": id}))
        .await;
    assert_eq!(out["status"], "timed_out");
    h.ok("move_to", json!({"x_mm": 1.0, "y_mm": 1.0})).await;
}

#[tokio::test]
async fn human_gate_input_validation() {
    let h = harness();
    h.invalid(
        "request_human_action",
        json!({"description": "x", "timeout_min": 0}),
    )
    .await;
    h.invalid(
        "request_human_action",
        json!({"description": "x", "timeout_min": 5, "wait_seconds": 301}),
    )
    .await;
    h.invalid(
        "request_human_action",
        json!({"description": "  ", "timeout_min": 5}),
    )
    .await;
    h.invalid(
        "get_human_action_status",
        json!({"action_id": "ha_missing"}),
    )
    .await;
    h.invalid("get_human_action_status", json!({"action_id": "../x"}))
        .await;
}

#[tokio::test]
async fn emergency_stop_cancels_open_gate() {
    let h = harness();
    let out = h
        .ok(
            "request_human_action",
            json!({"description": "Load", "timeout_min": 5}),
        )
        .await;
    let id = out["action_id"].as_str().unwrap().to_string();
    h.ok("emergency_stop", json!({})).await;
    let out = h
        .ok("get_human_action_status", json!({"action_id": id}))
        .await;
    assert_eq!(out["status"], "cancelled_by_emergency_stop");
}

// ----------------------------------------------------------------------------
// Imaging
// ----------------------------------------------------------------------------

#[tokio::test]
async fn capture_then_count_latest() {
    let h = harness();
    let a = h
        .ok("capture_plate_image", json!({"plate_id": "plate_a"}))
        .await;
    let b = h
        .ok(
            "capture_plate_image",
            json!({"plate_id": "plate_a", "lighting_mode": "uv_blue"}),
        )
        .await;
    assert_ne!(a["image_id"], b["image_id"], "ids must be unique");
    assert_eq!(b["lighting_mode"], "uv_blue");

    let out = h
        .ok(
            "count_colonies",
            json!({"plate_id": "plate_a", "image_id": "latest"}),
        )
        .await;
    assert_eq!(out["image_id"], b["image_id"]);
    assert!(out["coordinates"].is_array());
    assert_eq!(out["simulated"], true);

    let out = h
        .ok(
            "count_colonies",
            json!({"plate_id": "plate_a", "image_id": a["image_id"]}),
        )
        .await;
    assert_eq!(out["image_id"], a["image_id"]);
}

#[tokio::test]
async fn count_rejects_unknown_or_mismatched_images() {
    let h = harness();
    let msg = h
        .invalid(
            "count_colonies",
            json!({"plate_id": "plate_a", "image_id": "latest"}),
        )
        .await;
    assert!(msg.contains("capture_plate_image"), "{msg}");

    let a = h
        .ok("capture_plate_image", json!({"plate_id": "plate_a"}))
        .await;
    let msg = h
        .invalid(
            "count_colonies",
            json!({"plate_id": "plate_b", "image_id": a["image_id"]}),
        )
        .await;
    assert!(msg.contains("belongs to plate"), "{msg}");

    h.invalid(
        "count_colonies",
        json!({"plate_id": "plate_a", "image_id": "latest", "min_area_px": 100, "max_area_px": 10}),
    )
    .await;
}

// ----------------------------------------------------------------------------
// Protocols
// ----------------------------------------------------------------------------

#[tokio::test]
async fn protocols_list_load_and_reject() {
    let h = harness();
    let list = h.ok("list_protocols", json!({})).await;
    let ids: Vec<&str> = list["protocols"]
        .as_array()
        .unwrap()
        .iter()
        .map(|p| p["protocol_id"].as_str().unwrap())
        .collect();
    assert_eq!(ids, ["good", "odin_crispr_rpsL"]);

    let out = h.ok("load_protocol", json!({"protocol_id": "good"})).await;
    assert_eq!(out["validation"], "passed");
    assert_eq!(out["steps"], 2);
    assert_eq!(out["human_gates"], 1);
    let st = h.ok("get_system_status", json!({})).await;
    assert_eq!(st["active_protocol"], "good");
    assert_eq!(st["state"], "protocol_loaded");

    // The shipped Odin protocol pours 20 mL of agar in one dispense, above
    // the 1 mL single-dispense limit, so it is rejected with per-step issues
    // and the previously loaded protocol stays active.
    let out = h
        .ok("load_protocol", json!({"protocol_id": "odin_crispr_rpsL"}))
        .await;
    assert_eq!(out["validation"], "failed");
    assert_eq!(out["loaded"], false);
    assert!(!out["issues"].as_array().unwrap().is_empty());
    let st = h.ok("get_system_status", json!({})).await;
    assert_eq!(st["active_protocol"], "good");

    // Reloading is allowed (the old state machine made this impossible).
    h.ok("load_protocol", json!({"protocol_id": "good"})).await;

    let msg = h
        .invalid("load_protocol", json!({"protocol_id": "nope"}))
        .await;
    assert!(msg.contains("not found"), "{msg}");
}

// ----------------------------------------------------------------------------
// Audit log
// ----------------------------------------------------------------------------

#[tokio::test]
async fn audit_log_records_mutating_calls_only() {
    let dir = tempfile::tempdir().unwrap();
    let log = dir.path().join("audit").join("bioforge.jsonl");
    let h = harness_with(
        test_limits(),
        simulated_hardware(),
        Timeouts::default(),
        Some(&log),
    );
    h.ok(
        "dispense",
        json!({"target": "p:A1", "volume_ul": 10.0, "reagent": "lb"}),
    )
    .await;
    h.refused("move_to", json!({"x_mm": 999.0, "y_mm": 1.0}))
        .await;
    h.ok("get_system_status", json!({})).await;

    let contents = std::fs::read_to_string(&log).unwrap();
    let lines: Vec<Value> = contents
        .lines()
        .map(|l| serde_json::from_str(l).unwrap())
        .collect();
    assert_eq!(lines.len(), 2, "{contents}");
    assert_eq!(lines[0]["tool"], "dispense");
    assert_eq!(lines[0]["ok"], true);
    assert_eq!(lines[0]["run_id"], h.lab.run_id());
    assert_eq!(lines[1]["tool"], "move_to");
    assert_eq!(lines[1]["ok"], false);
}
