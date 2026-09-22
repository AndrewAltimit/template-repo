//! The lab: safety enforcement, hardware access and run state behind every
//! MCP tool.
//!
//! Every actuator operation follows the same pipeline:
//!
//! 1. **Stateless validation** of all inputs (ids, volumes, temperatures,
//!    positions). Nothing stateful has happened yet, so a malformed request
//!    never consumes rate-limit budget, actuator spacing or dispense volume.
//! 2. **Admission** ([`Lab::begin_actuation`]): e-stop latch, pending human
//!    gate, per-minute rate limit, exclusive hardware lock (with a busy
//!    timeout), and the minimum actuator interval (waited out once rather
//!    than rejected, since calls are serialized anyway).
//! 3. **Stateful checks** such as cumulative dispense tracking.
//! 4. **Hardware call** ([`Lab::hal`]) bounded by a timeout and cancelled
//!    immediately if the emergency stop fires while it is in flight.
//!
//! The emergency stop latches for the lifetime of the process: it can only be
//! cleared by restarting the server after the physical system has been
//! inspected. No tool can clear it.

use std::future::Future;
use std::path::PathBuf;
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::{Duration, Instant};

use bioforge_hal::camera::Camera;
use bioforge_hal::motion::MotionController;
use bioforge_hal::pumps::PumpDriver;
use bioforge_hal::sensors::SensorReader;
use bioforge_hal::thermal::ThermalController;
use bioforge_protocol::StateMachine;
use bioforge_safety::{AuditLog, SafetyEnforcer, audit::AuditEvent};
use bioforge_types::error::BioForgeError;
use bioforge_types::protocol::{LightingMode, ProtocolState, ThermalZone};
use bioforge_vision::ColonyCounter;
use chrono::{DateTime, Utc};
use serde_json::{Value, json};
use tokio::sync::{Mutex, MutexGuard, Notify};

use crate::error::{LabError, LabResult, invalid};
use crate::protocols::{self, MAX_HUMAN_TIMEOUT_MIN, ProtocolStore};
use crate::validate;

/// Most images kept in the in-memory registry (oldest are forgotten first).
const MAX_IMAGE_RECORDS: usize = 1000;
/// Most human-action records kept (oldest resolved ones are forgotten first).
const MAX_HUMAN_RECORDS: usize = 100;
/// Longest a tool call may block waiting for a human confirmation.
pub const MAX_WAIT_SECONDS: u64 = 300;
/// Poll interval while waiting for a human confirmation file.
const HUMAN_POLL: Duration = Duration::from_millis(500);

/// Trait objects for every hardware subsystem.
///
/// The server ships with simulated drivers only (see [`crate::sim`]); real
/// drivers implementing the `bioforge-hal` traits can be dropped in here.
pub struct Hardware {
    /// Syringe / peristaltic pumps.
    pub pumps: Arc<dyn PumpDriver>,
    /// Peltier thermal zones.
    pub thermal: Arc<dyn ThermalController>,
    /// XYZ gantry.
    pub motion: Arc<dyn MotionController>,
    /// Plate camera.
    pub camera: Arc<dyn Camera>,
    /// Ambient sensors.
    pub sensors: Arc<dyn SensorReader>,
    /// Whether these drivers are simulations. Echoed in every response so
    /// an agent can never mistake a simulated result for a wet-lab result.
    pub simulated: bool,
}

/// Upper bounds on how long each class of hardware call may take.
#[derive(Debug, Clone)]
pub struct Timeouts {
    /// Pump dispense / aspirate (per stroke).
    pub pump: Duration,
    /// Gantry moves and homing.
    pub motion: Duration,
    /// Thermal setpoint changes and reads.
    pub thermal: Duration,
    /// Added on top of `hold_s` for a heat-shock sequence (ramp up + down).
    pub heat_shock_overhead: Duration,
    /// Image capture.
    pub camera: Duration,
    /// Ambient sensor reads.
    pub sensor: Duration,
    /// Colony-counting analysis.
    pub analysis: Duration,
    /// How long an operation waits for another in-flight operation to
    /// release the hardware before giving up with "hardware busy".
    pub hardware_busy: Duration,
}

impl Default for Timeouts {
    fn default() -> Self {
        Self {
            pump: Duration::from_secs(120),
            motion: Duration::from_secs(60),
            thermal: Duration::from_secs(30),
            heat_shock_overhead: Duration::from_secs(180),
            camera: Duration::from_secs(30),
            sensor: Duration::from_secs(5),
            analysis: Duration::from_secs(60),
            hardware_busy: Duration::from_secs(30),
        }
    }
}

/// Construction options for [`Lab`].
pub struct LabOptions {
    /// Directory containing protocol TOML files.
    pub protocols_dir: PathBuf,
    /// Directory the operator drops `<action_id>.confirmed` files into to
    /// confirm human-action gates. `None` means gates can only expire.
    pub confirm_dir: Option<PathBuf>,
    /// Optional append-only JSONL audit log of mutating tool calls.
    pub audit_log: Option<AuditLog>,
    /// Hardware call timeouts.
    pub timeouts: Timeouts,
}

#[derive(Debug, Clone)]
struct ImageRecord {
    image_id: String,
    plate_id: String,
    path: String,
    lighting_mode: LightingMode,
    width: u32,
    height: u32,
    captured_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum HumanStatus {
    Pending,
    Confirmed,
    TimedOut,
    Cancelled,
}

impl HumanStatus {
    fn as_str(self) -> &'static str {
        match self {
            Self::Pending => "pending_human_approval",
            Self::Confirmed => "confirmed",
            Self::TimedOut => "timed_out",
            Self::Cancelled => "cancelled_by_emergency_stop",
        }
    }
}

#[derive(Debug, Clone)]
struct HumanAction {
    action_id: String,
    description: String,
    timeout_min: u64,
    requested_at: DateTime<Utc>,
    expires_at: DateTime<Utc>,
    status: HumanStatus,
    resolved_at: Option<DateTime<Utc>>,
}

impl HumanAction {
    fn to_json(&self) -> Value {
        json!({
            "action_id": self.action_id,
            "status": self.status.as_str(),
            "description": self.description,
            "timeout_min": self.timeout_min,
            "requested_at": self.requested_at.to_rfc3339(),
            "expires_at": self.expires_at.to_rfc3339(),
            "resolved_at": self.resolved_at.map(|t| t.to_rfc3339()),
        })
    }
}

#[derive(Debug, Clone)]
struct Incubation {
    target_c: f64,
    duration_hours: f64,
    started_at: DateTime<Utc>,
    ends_at: DateTime<Utc>,
}

impl Incubation {
    fn to_json(&self, now: DateTime<Utc>) -> Value {
        let remaining = (self.ends_at - now).num_seconds().max(0);
        json!({
            "target_c": self.target_c,
            "duration_hours": self.duration_hours,
            "started_at": self.started_at.to_rfc3339(),
            "ends_at": self.ends_at.to_rfc3339(),
            "remaining_s": remaining,
            "complete": remaining == 0,
        })
    }
}

#[derive(Debug, Clone)]
struct LoadedProtocol {
    protocol_id: String,
    summary: Value,
}

struct LabState {
    /// Commanded setpoints `[cold, warm]`; `None` = never set / safed.
    setpoints: [Option<f64>; 2],
    incubations: [Option<Incubation>; 2],
    images: Vec<ImageRecord>,
    machine: StateMachine,
    protocol: Option<LoadedProtocol>,
    human_actions: Vec<HumanAction>,
    next_action: u64,
    estop_at: Option<DateTime<Utc>>,
    estop_reason: Option<String>,
}

fn zone_idx(zone: ThermalZone) -> usize {
    match zone {
        ThermalZone::Cold => 0,
        ThermalZone::Warm => 1,
    }
}

fn zone_name(zone: ThermalZone) -> &'static str {
    match zone {
        ThermalZone::Cold => "cold",
        ThermalZone::Warm => "warm",
    }
}

fn lighting_name(mode: LightingMode) -> &'static str {
    match mode {
        LightingMode::White => "white",
        LightingMode::UvBlue => "uv_blue",
        LightingMode::DarkField => "dark_field",
    }
}

/// Kind of hardware access, which decides the admission checks.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum Access {
    /// Drives pumps, motors or heaters: blocked by e-stop and human gates,
    /// subject to the minimum actuator interval.
    Actuator,
    /// Camera / lights only: allowed during e-stop and pending gates, but
    /// still rate limited and serialized with other hardware use.
    Sensor,
}

/// Shared state behind all BioForge tools.
pub struct Lab {
    enforcer: Arc<SafetyEnforcer>,
    hw: Hardware,
    protocols: ProtocolStore,
    confirm_dir: Option<PathBuf>,
    audit: Option<Arc<AuditLog>>,
    timeouts: Timeouts,
    run_id: String,
    started: Instant,
    started_at: DateTime<Utc>,
    estop: AtomicBool,
    estop_notify: Notify,
    hardware_lock: Mutex<()>,
    state: Mutex<LabState>,
}

impl Lab {
    /// Build a lab around a safety enforcer and hardware stack.
    pub fn new(enforcer: Arc<SafetyEnforcer>, hw: Hardware, opts: LabOptions) -> Self {
        let started_at = Utc::now();
        let run_id = format!("run_{}", started_at.format("%Y%m%dT%H%M%S%.3fZ"));
        Self {
            enforcer,
            hw,
            protocols: ProtocolStore::new(opts.protocols_dir),
            confirm_dir: opts.confirm_dir,
            audit: opts.audit_log.map(Arc::new),
            timeouts: opts.timeouts,
            started: Instant::now(),
            started_at,
            estop: AtomicBool::new(false),
            estop_notify: Notify::new(),
            hardware_lock: Mutex::new(()),
            state: Mutex::new(LabState {
                setpoints: [None, None],
                incubations: [None, None],
                images: Vec::new(),
                machine: StateMachine::new(run_id.clone()),
                protocol: None,
                human_actions: Vec::new(),
                next_action: 1,
                estop_at: None,
                estop_reason: None,
            }),
            run_id,
        }
    }

    /// Identifier of this server process's run (used in the audit log).
    pub fn run_id(&self) -> &str {
        &self.run_id
    }

    // ========================================================================
    // Admission and hardware plumbing
    // ========================================================================

    fn ensure_not_stopped(&self) -> LabResult<()> {
        if self.estop.load(Ordering::SeqCst) {
            Err(LabError::Refused(BioForgeError::EmergencyStop))
        } else {
            Ok(())
        }
    }

    /// Resolve pending human actions (confirmation file present or deadline
    /// passed). Must be called with the state lock held.
    async fn resolve_human_actions(&self, st: &mut LabState) {
        let now = Utc::now();
        for action in st
            .human_actions
            .iter_mut()
            .filter(|a| a.status == HumanStatus::Pending)
        {
            if let Some(dir) = &self.confirm_dir {
                let file = dir.join(format!("{}.confirmed", action.action_id));
                if tokio::fs::try_exists(&file).await.unwrap_or(false) {
                    action.status = HumanStatus::Confirmed;
                    action.resolved_at = Some(now);
                    continue;
                }
            }
            if now >= action.expires_at {
                action.status = HumanStatus::TimedOut;
                action.resolved_at = Some(now);
            }
        }
    }

    async fn ensure_no_pending_gate(&self) -> LabResult<()> {
        let mut st = self.state.lock().await;
        self.resolve_human_actions(&mut st).await;
        if let Some(a) = st
            .human_actions
            .iter()
            .find(|a| a.status == HumanStatus::Pending)
        {
            return Err(LabError::Refused(BioForgeError::HumanGatePending {
                action: format!(
                    "{} ('{}'), expires {}",
                    a.action_id,
                    a.description,
                    a.expires_at.to_rfc3339()
                ),
            }));
        }
        Ok(())
    }

    /// Admission control; see the module docs. The returned guard must be
    /// held for the duration of the hardware operation.
    async fn begin(&self, access: Access) -> LabResult<MutexGuard<'_, ()>> {
        if access == Access::Actuator {
            self.ensure_not_stopped()?;
            self.ensure_no_pending_gate().await?;
        }
        self.enforcer.check_rate_limit()?;
        let guard = tokio::time::timeout(self.timeouts.hardware_busy, self.hardware_lock.lock())
            .await
            .map_err(|_| {
                LabError::Refused(BioForgeError::HardwareFault(format!(
                    "hardware busy: another operation did not finish within {:?}",
                    self.timeouts.hardware_busy
                )))
            })?;
        if access == Access::Actuator {
            // The e-stop may have fired while we waited for the lock.
            self.ensure_not_stopped()?;
            if self.enforcer.check_actuator_interval().is_err() {
                // Operations are serialized by the lock, so waiting out one
                // interval is always enough.
                let ms = self.enforcer.limits().rate.min_actuator_interval_ms;
                tokio::time::sleep(Duration::from_millis(ms)).await;
                self.ensure_not_stopped()?;
                self.enforcer.check_actuator_interval()?;
            }
        }
        Ok(guard)
    }

    /// Run a hardware call with a timeout. Actuator calls are additionally
    /// cancelled (dropped) the moment the emergency stop fires.
    async fn hal<T>(
        &self,
        what: &str,
        limit: Duration,
        access: Access,
        fut: impl Future<Output = Result<T, BioForgeError>>,
    ) -> LabResult<T> {
        let notified = self.estop_notify.notified();
        tokio::pin!(notified);
        notified.as_mut().enable();
        if access == Access::Actuator {
            self.ensure_not_stopped()?;
        }
        let timed = tokio::time::timeout(limit, fut);
        let outcome = if access == Access::Actuator {
            tokio::select! {
                biased;
                () = &mut notified => {
                    tracing::warn!(what, "hardware call cancelled by emergency stop");
                    return Err(LabError::Refused(BioForgeError::EmergencyStop));
                }
                r = timed => r,
            }
        } else {
            timed.await
        };
        match outcome {
            Ok(Ok(v)) => Ok(v),
            Ok(Err(e)) => Err(LabError::Refused(e)),
            Err(_) => Err(LabError::Refused(BioForgeError::HardwareFault(format!(
                "{what} did not complete within {limit:?}"
            )))),
        }
    }

    fn remaining_budget_ul(&self) -> LabResult<(f64, f64)> {
        let used = self.enforcer.cumulative_dispensed_ul()?;
        let max = self.enforcer.limits().volume.max_total_ml * 1000.0;
        Ok((used, (max - used).max(0.0)))
    }

    /// Append a tool call to the audit log, if one is configured. Failures
    /// are logged but never fail the tool call.
    pub async fn audit(&self, tool: &str, args: &Value, outcome: Result<&Value, String>) {
        let Some(log) = self.audit.clone() else {
            return;
        };
        let data = match outcome {
            Ok(result) => json!({ "tool": tool, "args": args, "ok": true, "result": result }),
            Err(error) => json!({ "tool": tool, "args": args, "ok": false, "error": error }),
        };
        let event = AuditEvent::new("tool_call", self.run_id.clone(), data);
        match tokio::task::spawn_blocking(move || log.log(&event)).await {
            Ok(Ok(())) => {},
            Ok(Err(e)) => tracing::error!(tool, "failed to write audit log: {e}"),
            Err(e) => tracing::error!(tool, "audit log task failed: {e}"),
        }
    }

    // ========================================================================
    // Liquid handling
    // ========================================================================

    /// Dispense `volume_ul` of `reagent` into `target`.
    pub async fn dispense(
        &self,
        target: &str,
        volume_ul: f64,
        reagent: &str,
        flow_rate: Option<f64>,
    ) -> LabResult<Value> {
        validate::label("target", target).map_err(invalid)?;
        validate::label("reagent", reagent).map_err(invalid)?;
        self.enforcer.validate_volume(volume_ul)?;
        if let Some(r) = flow_rate {
            self.enforcer.validate_flow_rate(r)?;
        }

        let _hw = self.begin(Access::Actuator).await?;
        // Tracked before the pump runs: if the pump then fails part-way the
        // budget is over- rather than under-counted (fail safe).
        self.enforcer.validate_and_track_dispense(volume_ul)?;
        let actual = self
            .hal(
                "dispense",
                self.timeouts.pump,
                Access::Actuator,
                self.hw.pumps.dispense(volume_ul, flow_rate),
            )
            .await?;
        let (used, remaining) = self.remaining_budget_ul()?;

        Ok(json!({
            "status": "complete",
            "target": target,
            "reagent": reagent,
            "requested_volume_ul": volume_ul,
            "actual_volume_ul": actual,
            "flow_rate_ul_s": flow_rate,
            "cumulative_dispensed_ul": used,
            "remaining_run_budget_ul": remaining,
            "simulated": self.hw.simulated,
        }))
    }

    /// Aspirate `volume_ul` from `source`.
    pub async fn aspirate(
        &self,
        source: &str,
        volume_ul: f64,
        flow_rate: Option<f64>,
    ) -> LabResult<Value> {
        validate::label("source", source).map_err(invalid)?;
        self.enforcer.validate_volume(volume_ul)?;
        if let Some(r) = flow_rate {
            self.enforcer.validate_flow_rate(r)?;
        }

        let _hw = self.begin(Access::Actuator).await?;
        let actual = self
            .hal(
                "aspirate",
                self.timeouts.pump,
                Access::Actuator,
                self.hw.pumps.aspirate(volume_ul, flow_rate),
            )
            .await?;

        Ok(json!({
            "status": "complete",
            "source": source,
            "requested_volume_ul": volume_ul,
            "actual_volume_ul": actual,
            "flow_rate_ul_s": flow_rate,
            "simulated": self.hw.simulated,
        }))
    }

    /// Mix in place with `cycles` aspirate/dispense strokes of `volume_ul`.
    ///
    /// Mixing returns liquid to the same well, so it does not count against
    /// the cumulative dispense budget.
    pub async fn mix(
        &self,
        target: &str,
        volume_ul: f64,
        cycles: u32,
        flow_rate: Option<f64>,
    ) -> LabResult<Value> {
        validate::label("target", target).map_err(invalid)?;
        self.enforcer.validate_mix_cycles(cycles)?;
        self.enforcer.validate_volume(volume_ul)?;
        if let Some(r) = flow_rate {
            self.enforcer.validate_flow_rate(r)?;
        }

        let _hw = self.begin(Access::Actuator).await?;
        for cycle in 1..=cycles {
            let stroke = async {
                self.hw.pumps.aspirate(volume_ul, flow_rate).await?;
                self.hw.pumps.dispense(volume_ul, flow_rate).await
            };
            self.hal(
                &format!("mix cycle {cycle}/{cycles}"),
                self.timeouts.pump,
                Access::Actuator,
                stroke,
            )
            .await?;
        }

        Ok(json!({
            "status": "complete",
            "target": target,
            "volume_ul": volume_ul,
            "cycles_completed": cycles,
            "flow_rate_ul_s": flow_rate,
            "simulated": self.hw.simulated,
        }))
    }

    // ========================================================================
    // Motion
    // ========================================================================

    /// Move the gantry to an absolute position (`z` defaults to the safe
    /// travel height).
    pub async fn move_to(&self, x: f64, y: f64, z: Option<f64>) -> LabResult<Value> {
        let z = z.unwrap_or_else(|| self.enforcer.safe_travel_height());
        self.enforcer.validate_position(x, y, z)?;

        let _hw = self.begin(Access::Actuator).await?;
        let pos = self
            .hal(
                "move_to",
                self.timeouts.motion,
                Access::Actuator,
                self.hw.motion.move_to(x, y, Some(z)),
            )
            .await?;

        Ok(json!({
            "status": "complete",
            "position": { "x_mm": pos.x_mm, "y_mm": pos.y_mm, "z_mm": pos.z_mm },
            "simulated": self.hw.simulated,
        }))
    }

    /// Home all gantry axes.
    pub async fn home_gantry(&self) -> LabResult<Value> {
        let _hw = self.begin(Access::Actuator).await?;
        let pos = self
            .hal(
                "home",
                self.timeouts.motion,
                Access::Actuator,
                self.hw.motion.home(),
            )
            .await?;
        Ok(json!({
            "status": "complete",
            "position": { "x_mm": pos.x_mm, "y_mm": pos.y_mm, "z_mm": pos.z_mm },
            "simulated": self.hw.simulated,
        }))
    }

    // ========================================================================
    // Thermal
    // ========================================================================

    /// Command a thermal zone to `target_c` and read it back.
    pub async fn set_temperature(
        &self,
        zone: ThermalZone,
        target_c: f64,
        hold_seconds: Option<u64>,
    ) -> LabResult<Value> {
        self.enforcer.validate_temperature(target_c)?;
        if let Some(h) = hold_seconds {
            let max_s = self.enforcer.limits().operations.max_incubation_hours * 3600.0;
            self.enforcer.validate_duration_s(h as f64, max_s)?;
        }

        let _hw = self.begin(Access::Actuator).await?;
        self.hal(
            "set_temperature",
            self.timeouts.thermal,
            Access::Actuator,
            self.hw.thermal.set_temperature(zone, target_c),
        )
        .await?;
        let cancelled = {
            let mut st = self.state.lock().await;
            st.setpoints[zone_idx(zone)] = Some(target_c);
            st.incubations[zone_idx(zone)].take()
        };
        let reading = self
            .hal(
                "read_temperature",
                self.timeouts.thermal,
                Access::Sensor,
                self.hw.thermal.read_temperature(zone),
            )
            .await?;
        if reading.stable {
            self.enforcer
                .validate_overshoot(reading.current_c, target_c)?;
        }

        let now = Utc::now();
        Ok(json!({
            "status": "complete",
            "zone": zone_name(zone),
            "target_c": target_c,
            "current_c": reading.current_c,
            "stable": reading.stable,
            "hold_seconds": hold_seconds,
            "note": "the setpoint stays active after this call returns; hold_seconds is advisory and not timed by the server",
            "cancelled_incubation": cancelled.map(|i| i.to_json(now)),
            "simulated": self.hw.simulated,
        }))
    }

    /// Run an atomic heat-shock sequence in the warm zone.
    pub async fn heat_shock(
        &self,
        ramp_to_c: f64,
        hold_s: u64,
        return_to_c: f64,
    ) -> LabResult<Value> {
        self.enforcer.validate_temperature(ramp_to_c)?;
        self.enforcer.validate_temperature(return_to_c)?;
        self.enforcer.validate_heat_shock_hold_s(hold_s)?;

        let _hw = self.begin(Access::Actuator).await?;
        let limit = self.timeouts.heat_shock_overhead + Duration::from_secs(hold_s);
        let report = self
            .hal(
                "heat_shock",
                limit,
                Access::Actuator,
                self.hw.thermal.heat_shock(ramp_to_c, hold_s, return_to_c),
            )
            .await?;
        {
            let mut st = self.state.lock().await;
            st.setpoints[zone_idx(ThermalZone::Warm)] = Some(return_to_c);
            st.incubations[zone_idx(ThermalZone::Warm)] = None;
        }

        let max_over = self.enforcer.limits().thermal.max_overshoot_c;
        let peak_ok = self
            .enforcer
            .validate_overshoot(report.peak_temp_c, ramp_to_c)
            .is_ok();
        let min_ok = self
            .enforcer
            .validate_overshoot(report.min_temp_during_hold_c, ramp_to_c)
            .is_ok();
        let within = peak_ok && min_ok;

        let result = json!({
            "status": if within { "complete" } else { "out_of_tolerance" },
            "zone": "warm",
            "ramp_to_c": ramp_to_c,
            "requested_hold_s": hold_s,
            "actual_hold_s": report.actual_hold_s,
            "peak_temp_c": report.peak_temp_c,
            "min_temp_during_hold_c": report.min_temp_during_hold_c,
            "return_to_c": return_to_c,
            "max_deviation_allowed_c": max_over,
            "within_tolerance": within,
            "simulated": self.hw.simulated,
        });
        if within {
            Ok(result)
        } else {
            Err(LabError::Refused(BioForgeError::SafetyViolation(format!(
                "heat shock deviated more than {max_over} C from {ramp_to_c} C; treat the sample as compromised: {result}"
            ))))
        }
    }

    /// Start a long-duration hold. Returns immediately; progress is visible
    /// in `get_system_status`.
    pub async fn incubate(
        &self,
        zone: ThermalZone,
        target_c: f64,
        duration_hours: f64,
    ) -> LabResult<Value> {
        self.enforcer.validate_temperature(target_c)?;
        self.enforcer.validate_incubation_hours(duration_hours)?;

        let _hw = self.begin(Access::Actuator).await?;
        self.hal(
            "incubate",
            self.timeouts.thermal,
            Access::Actuator,
            self.hw.thermal.set_temperature(zone, target_c),
        )
        .await?;

        let now = Utc::now();
        let ends_at =
            now + chrono::Duration::milliseconds((duration_hours * 3_600_000.0).round() as i64);
        let inc = Incubation {
            target_c,
            duration_hours,
            started_at: now,
            ends_at,
        };
        let json_inc = inc.to_json(now);
        let replaced = {
            let mut st = self.state.lock().await;
            st.setpoints[zone_idx(zone)] = Some(target_c);
            st.incubations[zone_idx(zone)].replace(inc)
        };

        Ok(json!({
            "status": "started",
            "zone": zone_name(zone),
            "target_c": target_c,
            "duration_hours": duration_hours,
            "incubation": json_inc,
            "replaced_incubation": replaced.map(|i| i.to_json(now)),
            "note": "the zone holds target_c; poll get_system_status for remaining time",
            "simulated": self.hw.simulated,
        }))
    }

    // ========================================================================
    // Imaging
    // ========================================================================

    /// Capture a plate image and register it for `count_colonies`.
    pub async fn capture_plate_image(
        &self,
        plate_id: &str,
        mode: LightingMode,
    ) -> LabResult<Value> {
        validate::identifier("plate_id", plate_id).map_err(invalid)?;

        let _hw = self.begin(Access::Sensor).await?;
        let img = self
            .hal(
                "capture_plate_image",
                self.timeouts.camera,
                Access::Sensor,
                self.hw.camera.capture(plate_id, mode),
            )
            .await?;

        let mut st = self.state.lock().await;
        // Drivers may produce colliding ids (the mock uses 1 s timestamps).
        let mut image_id = img.image_id.clone();
        let mut n = 2;
        while st.images.iter().any(|r| r.image_id == image_id) {
            image_id = format!("{}_{n}", img.image_id);
            n += 1;
        }
        validate::identifier("image_id", &image_id).map_err(|e| {
            LabError::Refused(BioForgeError::CameraError(format!(
                "driver returned an unusable image id: {e}"
            )))
        })?;
        let rec = ImageRecord {
            image_id: image_id.clone(),
            plate_id: plate_id.to_string(),
            path: img.path,
            lighting_mode: img.lighting_mode,
            width: img.width,
            height: img.height,
            captured_at: Utc::now(),
        };
        let out = json!({
            "status": "complete",
            "image_id": rec.image_id,
            "plate_id": rec.plate_id,
            "lighting_mode": lighting_name(rec.lighting_mode),
            "image_path": rec.path,
            "resolution": format!("{}x{}", rec.width, rec.height),
            "captured_at": rec.captured_at.to_rfc3339(),
            "simulated": self.hw.simulated,
        });
        st.images.push(rec);
        if st.images.len() > MAX_IMAGE_RECORDS {
            let excess = st.images.len() - MAX_IMAGE_RECORDS;
            st.images.drain(..excess);
        }
        Ok(out)
    }

    /// Count colonies on a previously captured image of `plate_id`.
    /// `image_id` may be `"latest"`.
    pub async fn count_colonies(
        &self,
        plate_id: &str,
        image_id: &str,
        min_area_px: Option<u32>,
        max_area_px: Option<u32>,
    ) -> LabResult<Value> {
        validate::identifier("plate_id", plate_id).map_err(invalid)?;
        validate::identifier("image_id", image_id).map_err(invalid)?;
        let counter = match (min_area_px, max_area_px) {
            (None, None) => ColonyCounter::default(),
            (min, max) => ColonyCounter::new(min.unwrap_or(50), max.unwrap_or(5000))
                .map_err(|e| invalid(e.to_string()))?,
        };

        let rec = {
            let st = self.state.lock().await;
            let found = if image_id == "latest" {
                st.images.iter().rev().find(|r| r.plate_id == plate_id)
            } else {
                st.images.iter().find(|r| r.image_id == image_id)
            };
            match found {
                Some(r) if r.plate_id == plate_id => r.clone(),
                Some(r) => {
                    return Err(invalid(format!(
                        "image '{}' belongs to plate '{}', not '{plate_id}'",
                        r.image_id, r.plate_id
                    )));
                },
                None => {
                    return Err(invalid(format!(
                        "no captured image '{image_id}' for plate '{plate_id}'; call capture_plate_image first"
                    )));
                },
            }
        };

        let path = rec.path.clone();
        let analysis = tokio::time::timeout(
            self.timeouts.analysis,
            tokio::task::spawn_blocking(move || counter.count(&path)),
        )
        .await
        .map_err(|_| {
            LabError::Refused(BioForgeError::CameraError(format!(
                "colony analysis did not complete within {:?}",
                self.timeouts.analysis
            )))
        })?
        .map_err(|e| {
            LabError::Refused(BioForgeError::CameraError(format!(
                "colony analysis task failed: {e}"
            )))
        })??;

        Ok(json!({
            "status": "complete",
            "plate_id": plate_id,
            "image_id": rec.image_id,
            "lighting_mode": lighting_name(rec.lighting_mode),
            "colony_count": analysis.colony_count,
            "mean_diameter_px": analysis.mean_diameter_px,
            "size_distribution": analysis.size_distribution,
            "coordinates": analysis
                .coordinates
                .iter()
                .map(|(x, y)| json!([x, y]))
                .collect::<Vec<_>>(),
            // bioforge-vision's counter is still a placeholder that returns a
            // fixed result regardless of the image.
            "simulated": true,
            "note": "colony counting uses the bioforge-vision placeholder pipeline; counts are not derived from the image",
        }))
    }

    // ========================================================================
    // Protocols
    // ========================================================================

    /// List protocol files available to `load_protocol`.
    pub async fn list_protocols(&self) -> LabResult<Value> {
        let list = self.protocols.list().await?;
        Ok(json!({
            "protocols_dir": self.protocols.root().display().to_string(),
            "count": list.len(),
            "protocols": list,
        }))
    }

    /// Load a protocol file, validate every step against the current safety
    /// limits and, if it passes, make it the active protocol.
    pub async fn load_protocol(&self, protocol_id: &str) -> LabResult<Value> {
        let protocol = self.protocols.load(protocol_id).await?;
        let issues = protocols::validate_steps(&protocol, &self.enforcer);
        let human_gates = protocol.steps.iter().filter(|s| s.human_gate).count();
        let steps: Vec<Value> = protocol
            .steps
            .iter()
            .map(|s| {
                json!({
                    "id": s.id,
                    "name": s.name,
                    "type": protocols::action_type(&s.action),
                    "human_gate": s.human_gate,
                    "notes": s.notes,
                })
            })
            .collect();
        let summary = json!({
            "protocol_id": protocol_id,
            "name": protocol.name,
            "version": protocol.version,
            "description": protocol.description,
            "steps": protocol.steps.len(),
            "human_gates": human_gates,
        });

        if !issues.is_empty() {
            let mut out = summary;
            out["status"] = json!("rejected");
            out["validation"] = json!("failed");
            out["loaded"] = json!(false);
            out["issues"] = json!(issues);
            out["step_list"] = json!(steps);
            return Ok(out);
        }

        {
            let mut st = self.state.lock().await;
            // Replacing the active protocol is allowed at any point: the
            // server does not execute protocols itself, it only tracks which
            // one the agent is following.
            st.machine.reset();
            st.machine.load_protocol(protocol)?;
            st.protocol = Some(LoadedProtocol {
                protocol_id: protocol_id.to_string(),
                summary: summary.clone(),
            });
        }

        let mut out = summary;
        out["status"] = json!("complete");
        out["validation"] = json!("passed");
        out["loaded"] = json!(true);
        out["step_list"] = json!(steps);
        Ok(out)
    }

    // ========================================================================
    // Human-in-the-loop gates
    // ========================================================================

    /// Wait (bounded) until `action_id` leaves the pending state.
    async fn wait_for_human(&self, action_id: &str, wait_seconds: u64) -> LabResult<Value> {
        let deadline = Instant::now() + Duration::from_secs(wait_seconds.min(MAX_WAIT_SECONDS));
        loop {
            let snapshot = {
                let mut st = self.state.lock().await;
                self.resolve_human_actions(&mut st).await;
                st.human_actions
                    .iter()
                    .find(|a| a.action_id == action_id)
                    .cloned()
            };
            let Some(action) = snapshot else {
                return Err(invalid(format!("unknown human action id '{action_id}'")));
            };
            if action.status != HumanStatus::Pending || Instant::now() >= deadline {
                let mut out = action.to_json();
                out["confirmation"] = self.confirm_instructions(&action.action_id);
                return Ok(out);
            }
            tokio::time::sleep(HUMAN_POLL).await;
        }
    }

    fn confirm_instructions(&self, action_id: &str) -> Value {
        match &self.confirm_dir {
            Some(dir) => json!({
                "channel": "file",
                "operator_instructions": format!(
                    "the operator confirms by creating {}",
                    dir.join(format!("{action_id}.confirmed")).display()
                ),
            }),
            None => json!({
                "channel": "none",
                "operator_instructions": "no confirmation channel is configured (--confirm-dir / BIOFORGE_CONFIRM_DIR); this gate can only expire",
            }),
        }
    }

    /// Open a human-action gate. While it is pending every actuator tool is
    /// refused. Optionally blocks up to `wait_seconds` for confirmation.
    pub async fn request_human_action(
        &self,
        description: &str,
        timeout_min: u64,
        wait_seconds: u64,
    ) -> LabResult<Value> {
        validate::description("description", description).map_err(invalid)?;
        if timeout_min == 0 || timeout_min > MAX_HUMAN_TIMEOUT_MIN {
            return Err(invalid(format!(
                "timeout_min must be between 1 and {MAX_HUMAN_TIMEOUT_MIN}, got {timeout_min}"
            )));
        }
        if wait_seconds > MAX_WAIT_SECONDS {
            return Err(invalid(format!(
                "wait_seconds must be at most {MAX_WAIT_SECONDS}, got {wait_seconds}"
            )));
        }
        self.ensure_not_stopped()?;

        let action_id = {
            let mut st = self.state.lock().await;
            self.resolve_human_actions(&mut st).await;
            if let Some(p) = st
                .human_actions
                .iter()
                .find(|a| a.status == HumanStatus::Pending)
            {
                return Err(LabError::Refused(BioForgeError::HumanGatePending {
                    action: format!(
                        "{} is still pending; only one human action can be open at a time (check it with get_human_action_status)",
                        p.action_id
                    ),
                }));
            }
            let n = st.next_action;
            st.next_action += 1;
            // Include the process start time so confirmation files left over
            // from a previous run can never confirm a new gate.
            let action_id = format!("ha_{}_{n:04}", self.started_at.format("%Y%m%d%H%M%S"));
            let now = Utc::now();
            st.human_actions.push(HumanAction {
                action_id: action_id.clone(),
                description: description.to_string(),
                timeout_min,
                requested_at: now,
                expires_at: now + chrono::Duration::minutes(timeout_min as i64),
                status: HumanStatus::Pending,
                resolved_at: None,
            });
            if st.human_actions.len() > MAX_HUMAN_RECORDS {
                // Drop the oldest resolved record (the pending one is newest).
                if let Some(pos) = st
                    .human_actions
                    .iter()
                    .position(|a| a.status != HumanStatus::Pending)
                {
                    st.human_actions.remove(pos);
                }
            }
            action_id
        };
        tracing::warn!(action_id, description, "human action requested");
        self.wait_for_human(&action_id, wait_seconds).await
    }

    /// Report (and optionally wait up to `wait_seconds` for) a human action.
    pub async fn human_action_status(
        &self,
        action_id: &str,
        wait_seconds: u64,
    ) -> LabResult<Value> {
        validate::identifier("action_id", action_id).map_err(invalid)?;
        if wait_seconds > MAX_WAIT_SECONDS {
            return Err(invalid(format!(
                "wait_seconds must be at most {MAX_WAIT_SECONDS}, got {wait_seconds}"
            )));
        }
        self.wait_for_human(action_id, wait_seconds).await
    }

    /// Move every pending gate's deadline into the past (tests only).
    #[cfg(test)]
    pub(crate) async fn expire_human_actions_for_test(&self) {
        let mut st = self.state.lock().await;
        let past = Utc::now() - chrono::Duration::seconds(1);
        for a in st.human_actions.iter_mut() {
            a.expires_at = past;
        }
    }

    // ========================================================================
    // Emergency stop and status
    // ========================================================================

    /// Latch the emergency stop: cancel in-flight actuator calls, refuse all
    /// further actuator commands, cancel open human gates and command both
    /// thermal zones to ambient. Never rate limited, never blocked.
    pub async fn emergency_stop(&self, reason: Option<&str>) -> LabResult<Value> {
        let already = self.estop.swap(true, Ordering::SeqCst);
        self.estop_notify.notify_waiters();
        tracing::error!(reason, already_active = already, "EMERGENCY STOP");

        let now = Utc::now();
        let (estop_at, estop_reason) = {
            let mut st = self.state.lock().await;
            if !already {
                st.estop_at = Some(now);
                st.estop_reason = reason.map(str::to_string);
            }
            for a in st
                .human_actions
                .iter_mut()
                .filter(|a| a.status == HumanStatus::Pending)
            {
                a.status = HumanStatus::Cancelled;
                a.resolved_at = Some(now);
            }
            st.incubations = [None, None];
            st.setpoints = [None, None];
            (st.estop_at, st.estop_reason.clone())
        };

        // The HAL has no "heaters off" primitive, so safe the Peltier zones
        // by commanding them to the measured ambient temperature. Deliberately
        // bypasses the hardware lock (an in-flight call was just cancelled).
        let ambient = self
            .hal(
                "read ambient",
                self.timeouts.sensor,
                Access::Sensor,
                self.hw.sensors.read_environment(),
            )
            .await
            .map(|r| r.ambient_temp_c)
            .unwrap_or(crate::sim::SIM_AMBIENT_C);
        let mut thermal = serde_json::Map::new();
        for zone in [ThermalZone::Cold, ThermalZone::Warm] {
            let r = self
                .hal(
                    "safe thermal zone",
                    self.timeouts.thermal,
                    Access::Sensor,
                    self.hw.thermal.set_temperature(zone, ambient),
                )
                .await;
            thermal.insert(
                zone_name(zone).into(),
                match r {
                    Ok(()) => json!(format!("commanded to ambient ({ambient} C)")),
                    Err(e) => json!(format!("FAILED to safe zone: {e}")),
                },
            );
        }

        Ok(json!({
            "status": "complete",
            "action": "emergency_stop",
            "already_active": already,
            "latched": true,
            "estop_at": estop_at.map(|t| t.to_rfc3339()),
            "reason": estop_reason,
            "all_actuators": "halted; in-flight actuator calls cancelled; further actuator commands refused",
            "pumps": "stopped",
            "gantry": "locked",
            "heaters": thermal,
            "human_gates": "cancelled",
            "clear_by": "restart the MCP server after the physical system has been inspected; no tool can clear the latch",
            "simulated": self.hw.simulated,
        }))
    }

    /// Snapshot of sensors, actuator state, run budget, protocol and gates.
    pub async fn system_status(&self) -> LabResult<Value> {
        let estop = self.estop.load(Ordering::SeqCst);
        let now = Utc::now();

        let mut zones = serde_json::Map::new();
        let mut zone_c = [None, None];
        for zone in [ThermalZone::Cold, ThermalZone::Warm] {
            let reading = self
                .hal(
                    "read_temperature",
                    self.timeouts.thermal,
                    Access::Sensor,
                    self.hw.thermal.read_temperature(zone),
                )
                .await;
            let entry = match reading {
                Ok(r) => {
                    zone_c[zone_idx(zone)] = Some(r.current_c);
                    json!({ "current_c": r.current_c, "stable": r.stable })
                },
                Err(e) => json!({ "error": e.to_string() }),
            };
            zones.insert(zone_name(zone).into(), entry);
        }
        let env = self
            .hal(
                "read_environment",
                self.timeouts.sensor,
                Access::Sensor,
                self.hw.sensors.read_environment(),
            )
            .await;
        let pos = self
            .hal(
                "position",
                self.timeouts.motion,
                Access::Sensor,
                self.hw.motion.position(),
            )
            .await;
        let (used, remaining) = self.remaining_budget_ul()?;

        let mut st = self.state.lock().await;
        self.resolve_human_actions(&mut st).await;
        for zone in [ThermalZone::Cold, ThermalZone::Warm] {
            if let Some(z) = zones.get_mut(zone_name(zone)) {
                z["setpoint_c"] = json!(st.setpoints[zone_idx(zone)]);
                z["incubation"] = json!(
                    st.incubations[zone_idx(zone)]
                        .as_ref()
                        .map(|i| i.to_json(now))
                );
            }
        }
        let pending: Vec<Value> = st
            .human_actions
            .iter()
            .filter(|a| a.status == HumanStatus::Pending)
            .map(HumanAction::to_json)
            .collect();
        let incubating = st.incubations.iter().flatten().any(|i| i.ends_at > now);
        let machine_state: ProtocolState = st.machine.state();
        let state = if estop {
            json!("emergency_stopped")
        } else if !pending.is_empty() {
            json!("awaiting_human")
        } else if incubating {
            json!("incubating")
        } else {
            serde_json::to_value(machine_state).unwrap_or(json!("unknown"))
        };
        let limits = self.enforcer.limits();
        let bounds = self.enforcer.bounds();

        Ok(json!({
            "state": state,
            "run_id": self.run_id,
            "simulated": self.hw.simulated,
            "uptime_s": self.started.elapsed().as_secs(),
            "estop_active": estop,
            "estop_at": st.estop_at.map(|t| t.to_rfc3339()),
            "estop_reason": st.estop_reason,
            "cold_zone_c": zone_c[0],
            "warm_zone_c": zone_c[1],
            "thermal_zones": zones,
            "ambient_c": env.as_ref().ok().map(|e| e.ambient_temp_c),
            "ambient_humidity_pct": env.as_ref().ok().map(|e| e.ambient_humidity_pct),
            "ambient_error": env.as_ref().err().map(ToString::to_string),
            "gantry_position": pos.as_ref().ok().map(|p| [p.x_mm, p.y_mm, p.z_mm]),
            "gantry_error": pos.as_ref().err().map(ToString::to_string),
            "active_protocol": st.protocol.as_ref().map(|p| p.protocol_id.clone()),
            "protocol": st.protocol.as_ref().map(|p| {
                let mut s = p.summary.clone();
                s["state"] = json!(machine_state.to_string());
                s
            }),
            "pending_human_actions": pending,
            "images_captured": st.images.len(),
            "latest_image_id": st.images.last().map(|r| r.image_id.clone()),
            "dispense": {
                "cumulative_dispensed_ul": used,
                "run_limit_ul": limits.volume.max_total_ml * 1000.0,
                "remaining_ul": remaining,
            },
            "limits": {
                "temperature_c": [limits.thermal.tool_min_c, limits.thermal.tool_max_c],
                "dispense_ul": [limits.volume.min_dispense_ul, limits.volume.max_dispense_ul],
                "max_flow_rate_ul_s": limits.volume.max_flow_rate_ul_s,
                "workspace_mm": [bounds.x_max_mm, bounds.y_max_mm, bounds.z_max_mm],
                "safe_travel_height_mm": limits.operations.safe_travel_height_mm,
                "max_mix_cycles": limits.operations.max_mix_cycles,
                "max_heat_shock_hold_s": limits.operations.max_heat_shock_hold_s,
                "max_incubation_hours": limits.operations.max_incubation_hours,
                "max_calls_per_minute": limits.rate.max_calls_per_minute,
                "min_actuator_interval_ms": limits.rate.min_actuator_interval_ms,
            },
        }))
    }
}
