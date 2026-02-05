//! Safety limit enforcement with stateful tracking.
//!
//! Validates tool parameters against configured limits and tracks cumulative
//! state (dispensed volume, call rate) across a single experiment run.

use std::collections::VecDeque;
use std::sync::Mutex;
use std::time::{Duration, Instant};

use bioforge_types::config::SafetyLimits;
use bioforge_types::error::BioForgeError;

/// Workspace bounds loaded from hardware config.
#[derive(Debug, Clone)]
pub struct WorkspaceBounds {
    pub x_max_mm: f64,
    pub y_max_mm: f64,
    pub z_max_mm: f64,
}

/// Mutable state tracked across tool calls within a single experiment run.
struct EnforcerState {
    /// Cumulative volume dispensed in the current run (microliters).
    cumulative_dispensed_ul: f64,
    /// Timestamp of the most recent actuator command.
    last_actuator_call: Option<Instant>,
    /// Sliding window of recent tool call timestamps for rate limiting.
    call_timestamps: VecDeque<Instant>,
}

impl EnforcerState {
    fn new() -> Self {
        Self {
            cumulative_dispensed_ul: 0.0,
            last_actuator_call: None,
            call_timestamps: VecDeque::new(),
        }
    }
}

/// Validates tool parameters against configured safety limits and tracks
/// cumulative state across a single experiment run.
///
/// Thread-safe: internal state is protected by a `Mutex`. All `&self` methods
/// are safe to call from multiple async tasks concurrently.
pub struct SafetyEnforcer {
    limits: SafetyLimits,
    bounds: WorkspaceBounds,
    state: Mutex<EnforcerState>,
}

/// Reject NaN and infinite floating-point values. These bypass normal
/// comparison operators (NaN < x is always false) and must be caught
/// before any bounds check.
fn require_finite(value: f64, name: &str) -> Result<(), BioForgeError> {
    if value.is_nan() || value.is_infinite() {
        return Err(BioForgeError::SafetyViolation(format!(
            "{name} is not a finite number: {value}"
        )));
    }
    Ok(())
}

impl SafetyEnforcer {
    pub fn new(limits: SafetyLimits, bounds: WorkspaceBounds) -> Self {
        Self {
            limits,
            bounds,
            state: Mutex::new(EnforcerState::new()),
        }
    }

    fn lock_state(&self) -> Result<std::sync::MutexGuard<'_, EnforcerState>, BioForgeError> {
        self.state.lock().map_err(|e| {
            BioForgeError::SafetyViolation(format!("enforcer state mutex poisoned: {e}"))
        })
    }

    // ========================================================================
    // Temperature validation
    // ========================================================================

    /// Validate that a temperature target is within allowed range.
    ///
    /// Checks both the tool-settable range and the hardware absolute maximum
    /// as defense-in-depth against misconfigured tool limits.
    pub fn validate_temperature(&self, target_c: f64) -> Result<(), BioForgeError> {
        require_finite(target_c, "target_c")?;
        if target_c > self.limits.thermal.absolute_max_c {
            return Err(BioForgeError::TemperatureOutOfRange {
                actual_c: target_c,
                limit_c: self.limits.thermal.absolute_max_c,
            });
        }
        if target_c > self.limits.thermal.tool_max_c {
            return Err(BioForgeError::TemperatureOutOfRange {
                actual_c: target_c,
                limit_c: self.limits.thermal.tool_max_c,
            });
        }
        if target_c < self.limits.thermal.tool_min_c {
            return Err(BioForgeError::TemperatureOutOfRange {
                actual_c: target_c,
                limit_c: self.limits.thermal.tool_min_c,
            });
        }
        Ok(())
    }

    /// Validate that an actual temperature reading has not overshot the
    /// target beyond the configured margin.
    pub fn validate_overshoot(&self, actual_c: f64, target_c: f64) -> Result<(), BioForgeError> {
        require_finite(actual_c, "actual_c")?;
        require_finite(target_c, "target_c")?;
        let overshoot = (actual_c - target_c).abs();
        if overshoot > self.limits.thermal.max_overshoot_c {
            return Err(BioForgeError::TemperatureOutOfRange {
                actual_c,
                limit_c: target_c + self.limits.thermal.max_overshoot_c,
            });
        }
        Ok(())
    }

    // ========================================================================
    // Volume validation (stateless single-dispense check)
    // ========================================================================

    /// Validate that a dispense volume is within allowed single-dispense range.
    ///
    /// This is a stateless check. For cumulative tracking, use
    /// [`validate_and_track_dispense`](Self::validate_and_track_dispense).
    pub fn validate_volume(&self, volume_ul: f64) -> Result<(), BioForgeError> {
        require_finite(volume_ul, "volume_ul")?;
        if volume_ul > self.limits.volume.max_dispense_ul {
            return Err(BioForgeError::VolumeOutOfRange {
                actual_ul: volume_ul,
                limit_ul: self.limits.volume.max_dispense_ul,
            });
        }
        if volume_ul < self.limits.volume.min_dispense_ul {
            return Err(BioForgeError::VolumeOutOfRange {
                actual_ul: volume_ul,
                limit_ul: self.limits.volume.min_dispense_ul,
            });
        }
        Ok(())
    }

    /// Validate a dispense volume and track cumulative usage.
    ///
    /// Checks single-dispense bounds, then verifies the cumulative total
    /// would not exceed `max_total_ml`. Only updates cumulative state on
    /// success.
    pub fn validate_and_track_dispense(&self, volume_ul: f64) -> Result<(), BioForgeError> {
        self.validate_volume(volume_ul)?;
        let mut state = self.lock_state()?;
        let new_total_ul = state.cumulative_dispensed_ul + volume_ul;
        let max_ul = self.limits.volume.max_total_ml * 1000.0;
        if new_total_ul > max_ul {
            return Err(BioForgeError::SafetyViolation(format!(
                "cumulative dispense {:.1} uL would exceed run limit {:.1} uL ({} mL)",
                new_total_ul, max_ul, self.limits.volume.max_total_ml
            )));
        }
        state.cumulative_dispensed_ul = new_total_ul;
        Ok(())
    }

    /// Return the cumulative volume dispensed so far in microliters.
    pub fn cumulative_dispensed_ul(&self) -> f64 {
        self.lock_state()
            .map(|s| s.cumulative_dispensed_ul)
            .unwrap_or(0.0)
    }

    // ========================================================================
    // Flow rate validation
    // ========================================================================

    /// Validate that a flow rate is within the allowed range.
    pub fn validate_flow_rate(&self, rate_ul_s: f64) -> Result<(), BioForgeError> {
        require_finite(rate_ul_s, "flow_rate")?;
        if rate_ul_s <= 0.0 {
            return Err(BioForgeError::SafetyViolation(format!(
                "flow rate must be positive, got {rate_ul_s} uL/s"
            )));
        }
        if rate_ul_s > self.limits.volume.max_flow_rate_ul_s {
            return Err(BioForgeError::SafetyViolation(format!(
                "flow rate {rate_ul_s} uL/s exceeds limit {} uL/s",
                self.limits.volume.max_flow_rate_ul_s
            )));
        }
        Ok(())
    }

    // ========================================================================
    // Position validation
    // ========================================================================

    /// Validate that a gantry position is within enclosure bounds.
    pub fn validate_position(&self, x: f64, y: f64, z: f64) -> Result<(), BioForgeError> {
        require_finite(x, "x")?;
        require_finite(y, "y")?;
        require_finite(z, "z")?;
        if x < 0.0
            || x > self.bounds.x_max_mm
            || y < 0.0
            || y > self.bounds.y_max_mm
            || z < 0.0
            || z > self.bounds.z_max_mm
        {
            return Err(BioForgeError::PositionOutOfBounds {
                x,
                y,
                z,
                x_max: self.bounds.x_max_mm,
                y_max: self.bounds.y_max_mm,
                z_max: self.bounds.z_max_mm,
            });
        }
        Ok(())
    }

    // ========================================================================
    // Speed validation
    // ========================================================================

    /// Validate that a speed value is within allowed range.
    pub fn validate_speed(&self, speed_mm_s: f64) -> Result<(), BioForgeError> {
        require_finite(speed_mm_s, "speed_mm_s")?;
        if speed_mm_s < 0.0 || speed_mm_s > self.limits.motion.max_speed_mm_s {
            return Err(BioForgeError::SafetyViolation(format!(
                "speed {speed_mm_s} mm/s exceeds limit {} mm/s",
                self.limits.motion.max_speed_mm_s
            )));
        }
        Ok(())
    }

    // ========================================================================
    // Duration validation
    // ========================================================================

    /// Validate that a duration is within reasonable bounds.
    pub fn validate_duration_s(&self, seconds: f64, max_seconds: f64) -> Result<(), BioForgeError> {
        require_finite(seconds, "duration")?;
        if seconds <= 0.0 {
            return Err(BioForgeError::SafetyViolation(format!(
                "duration must be positive, got {seconds}s"
            )));
        }
        if seconds > max_seconds {
            return Err(BioForgeError::SafetyViolation(format!(
                "duration {seconds}s exceeds maximum {max_seconds}s"
            )));
        }
        Ok(())
    }

    // ========================================================================
    // Operation-specific validation (from config)
    // ========================================================================

    /// Validate incubation duration against the configured maximum.
    pub fn validate_incubation_hours(&self, hours: f64) -> Result<(), BioForgeError> {
        require_finite(hours, "incubation_hours")?;
        if hours <= 0.0 {
            return Err(BioForgeError::SafetyViolation(format!(
                "incubation hours must be positive, got {hours}"
            )));
        }
        if hours > self.limits.operations.max_incubation_hours {
            return Err(BioForgeError::SafetyViolation(format!(
                "incubation {hours}h exceeds maximum {}h",
                self.limits.operations.max_incubation_hours
            )));
        }
        Ok(())
    }

    /// Validate heat shock hold duration against the configured maximum.
    pub fn validate_heat_shock_hold_s(&self, seconds: u64) -> Result<(), BioForgeError> {
        if seconds == 0 {
            return Err(BioForgeError::SafetyViolation(
                "heat shock hold must be > 0s".to_string(),
            ));
        }
        if seconds > self.limits.operations.max_heat_shock_hold_s {
            return Err(BioForgeError::SafetyViolation(format!(
                "heat shock hold {seconds}s exceeds maximum {}s",
                self.limits.operations.max_heat_shock_hold_s
            )));
        }
        Ok(())
    }

    /// Validate mix cycle count against the configured maximum.
    pub fn validate_mix_cycles(&self, cycles: u32) -> Result<(), BioForgeError> {
        if cycles == 0 {
            return Err(BioForgeError::SafetyViolation(
                "mix cycles must be > 0".to_string(),
            ));
        }
        if cycles > self.limits.operations.max_mix_cycles {
            return Err(BioForgeError::SafetyViolation(format!(
                "mix cycles {cycles} exceeds maximum {}",
                self.limits.operations.max_mix_cycles
            )));
        }
        Ok(())
    }

    // ========================================================================
    // Rate limiting (stateful)
    // ========================================================================

    /// Record a tool call and check the per-minute rate limit.
    ///
    /// Must be called once per tool invocation. Returns an error if the
    /// call rate exceeds `max_calls_per_minute`.
    pub fn check_rate_limit(&self) -> Result<(), BioForgeError> {
        let now = Instant::now();
        let mut state = self.lock_state()?;
        let window = Duration::from_secs(60);

        // Prune timestamps older than the 60-second window.
        while state
            .call_timestamps
            .front()
            .is_some_and(|t| now.duration_since(*t) > window)
        {
            state.call_timestamps.pop_front();
        }

        if state.call_timestamps.len() >= self.limits.rate.max_calls_per_minute as usize {
            return Err(BioForgeError::SafetyViolation(format!(
                "rate limit exceeded: {} calls in the last 60s (max {})",
                state.call_timestamps.len(),
                self.limits.rate.max_calls_per_minute
            )));
        }

        state.call_timestamps.push_back(now);
        Ok(())
    }

    /// Check that enough time has elapsed since the last actuator command.
    ///
    /// Must be called before any command that drives physical hardware
    /// (pumps, motors, heaters). Updates the last-call timestamp on success.
    pub fn check_actuator_interval(&self) -> Result<(), BioForgeError> {
        let now = Instant::now();
        let min_gap = Duration::from_millis(self.limits.rate.min_actuator_interval_ms);
        let mut state = self.lock_state()?;

        if let Some(last) = state.last_actuator_call {
            let elapsed = now.duration_since(last);
            if elapsed < min_gap {
                return Err(BioForgeError::SafetyViolation(format!(
                    "actuator interval {:.0}ms < minimum {}ms",
                    elapsed.as_millis(),
                    self.limits.rate.min_actuator_interval_ms
                )));
            }
        }

        state.last_actuator_call = Some(now);
        Ok(())
    }

    // ========================================================================
    // Config accessors
    // ========================================================================

    /// Return the configured safe travel height for Z-axis defaults.
    pub fn safe_travel_height(&self) -> f64 {
        self.limits.operations.safe_travel_height_mm
    }

    /// Access the current safety limits.
    pub fn limits(&self) -> &SafetyLimits {
        &self.limits
    }

    /// Access the workspace bounds.
    pub fn bounds(&self) -> &WorkspaceBounds {
        &self.bounds
    }

    // ========================================================================
    // Run lifecycle
    // ========================================================================

    /// Reset cumulative state for a new experiment run.
    ///
    /// Zeroes the dispensed volume counter and clears rate-limiting history.
    pub fn reset_run(&self) -> Result<(), BioForgeError> {
        let mut state = self.lock_state()?;
        state.cumulative_dispensed_ul = 0.0;
        state.last_actuator_call = None;
        state.call_timestamps.clear();
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use bioforge_types::config::*;

    fn test_limits() -> SafetyLimits {
        SafetyLimits {
            thermal: ThermalLimits {
                absolute_max_c: 60.0,
                tool_max_c: 50.0,
                tool_min_c: -5.0,
                max_overshoot_c: 1.5,
            },
            volume: VolumeLimits {
                max_dispense_ul: 1000.0,
                min_dispense_ul: 1.0,
                max_total_ml: 50.0,
                max_flow_rate_ul_s: 500.0,
            },
            motion: MotionLimits {
                max_speed_mm_s: 50.0,
                max_accel_mm_s2: 100.0,
            },
            rate: RateLimits {
                max_calls_per_minute: 60,
                min_actuator_interval_ms: 100,
            },
            operations: OperationLimits {
                max_incubation_hours: 72.0,
                max_heat_shock_hold_s: 300,
                max_mix_cycles: 20,
                safe_travel_height_mm: 15.0,
            },
        }
    }

    fn test_bounds() -> WorkspaceBounds {
        WorkspaceBounds {
            x_max_mm: 200.0,
            y_max_mm: 150.0,
            z_max_mm: 50.0,
        }
    }

    fn enforcer() -> SafetyEnforcer {
        SafetyEnforcer::new(test_limits(), test_bounds())
    }

    // -- Position validation --

    #[test]
    fn position_valid_origin() {
        assert!(enforcer().validate_position(0.0, 0.0, 0.0).is_ok());
    }

    #[test]
    fn position_valid_max_bounds() {
        assert!(enforcer().validate_position(200.0, 150.0, 50.0).is_ok());
    }

    #[test]
    fn position_valid_mid() {
        assert!(enforcer().validate_position(100.0, 75.0, 25.0).is_ok());
    }

    #[test]
    fn position_rejects_negative_x() {
        assert!(enforcer().validate_position(-1.0, 0.0, 0.0).is_err());
    }

    #[test]
    fn position_rejects_negative_y() {
        assert!(enforcer().validate_position(0.0, -0.1, 0.0).is_err());
    }

    #[test]
    fn position_rejects_negative_z() {
        assert!(enforcer().validate_position(0.0, 0.0, -0.01).is_err());
    }

    #[test]
    fn position_rejects_x_over_bounds() {
        assert!(enforcer().validate_position(200.1, 0.0, 0.0).is_err());
    }

    #[test]
    fn position_rejects_y_over_bounds() {
        assert!(enforcer().validate_position(0.0, 150.1, 0.0).is_err());
    }

    #[test]
    fn position_rejects_z_over_bounds() {
        assert!(enforcer().validate_position(0.0, 0.0, 50.1).is_err());
    }

    #[test]
    fn position_rejects_nan() {
        assert!(enforcer().validate_position(f64::NAN, 0.0, 0.0).is_err());
        assert!(enforcer().validate_position(0.0, f64::NAN, 0.0).is_err());
        assert!(enforcer().validate_position(0.0, 0.0, f64::NAN).is_err());
    }

    #[test]
    fn position_rejects_infinity() {
        assert!(
            enforcer()
                .validate_position(f64::INFINITY, 0.0, 0.0)
                .is_err()
        );
        assert!(
            enforcer()
                .validate_position(0.0, f64::NEG_INFINITY, 0.0)
                .is_err()
        );
    }

    // -- Temperature validation --

    #[test]
    fn temperature_valid_range() {
        assert!(enforcer().validate_temperature(4.0).is_ok());
        assert!(enforcer().validate_temperature(37.0).is_ok());
        assert!(enforcer().validate_temperature(42.0).is_ok());
        assert!(enforcer().validate_temperature(50.0).is_ok());
        assert!(enforcer().validate_temperature(-5.0).is_ok());
    }

    #[test]
    fn temperature_rejects_over_max() {
        assert!(enforcer().validate_temperature(50.1).is_err());
    }

    #[test]
    fn temperature_rejects_under_min() {
        assert!(enforcer().validate_temperature(-5.1).is_err());
    }

    #[test]
    fn temperature_rejects_above_absolute_max() {
        assert!(enforcer().validate_temperature(60.1).is_err());
    }

    #[test]
    fn temperature_accepts_between_tool_and_absolute_max() {
        // tool_max_c = 50.0, absolute_max_c = 60.0
        // Values above tool_max are still rejected
        assert!(enforcer().validate_temperature(55.0).is_err());
    }

    #[test]
    fn temperature_rejects_nan() {
        assert!(enforcer().validate_temperature(f64::NAN).is_err());
    }

    #[test]
    fn temperature_rejects_infinity() {
        assert!(enforcer().validate_temperature(f64::INFINITY).is_err());
    }

    // -- Overshoot validation --

    #[test]
    fn overshoot_within_margin() {
        assert!(enforcer().validate_overshoot(42.5, 42.0).is_ok());
        assert!(enforcer().validate_overshoot(41.5, 42.0).is_ok());
    }

    #[test]
    fn overshoot_at_limit() {
        assert!(enforcer().validate_overshoot(43.5, 42.0).is_ok());
    }

    #[test]
    fn overshoot_beyond_limit() {
        assert!(enforcer().validate_overshoot(43.6, 42.0).is_err());
        assert!(enforcer().validate_overshoot(40.4, 42.0).is_err());
    }

    #[test]
    fn overshoot_rejects_nan_target() {
        assert!(enforcer().validate_overshoot(42.0, f64::NAN).is_err());
    }

    #[test]
    fn overshoot_rejects_nan_actual() {
        assert!(enforcer().validate_overshoot(f64::NAN, 42.0).is_err());
    }

    // -- Volume validation --

    #[test]
    fn volume_valid_range() {
        assert!(enforcer().validate_volume(1.0).is_ok());
        assert!(enforcer().validate_volume(500.0).is_ok());
        assert!(enforcer().validate_volume(1000.0).is_ok());
    }

    #[test]
    fn volume_rejects_too_small() {
        assert!(enforcer().validate_volume(0.5).is_err());
    }

    #[test]
    fn volume_rejects_too_large() {
        assert!(enforcer().validate_volume(1001.0).is_err());
    }

    #[test]
    fn volume_rejects_nan() {
        assert!(enforcer().validate_volume(f64::NAN).is_err());
    }

    // -- Cumulative volume tracking --

    #[test]
    fn cumulative_dispense_tracks_volume() {
        let e = enforcer();
        e.validate_and_track_dispense(100.0).unwrap();
        e.validate_and_track_dispense(200.0).unwrap();
        assert!((e.cumulative_dispensed_ul() - 300.0).abs() < f64::EPSILON);
    }

    #[test]
    fn cumulative_dispense_rejects_over_limit() {
        let e = enforcer();
        // max_total_ml = 50.0 -> 50_000 uL
        // Dispense 49_000 uL in 49 calls
        for _ in 0..49 {
            e.validate_and_track_dispense(1000.0).unwrap();
        }
        // 50th call at 1000 uL would make 50_000 -- exactly at limit, ok
        e.validate_and_track_dispense(1000.0).unwrap();
        // 51st call pushes over limit
        assert!(e.validate_and_track_dispense(1.0).is_err());
    }

    #[test]
    fn cumulative_dispense_resets_on_new_run() {
        let e = enforcer();
        e.validate_and_track_dispense(1000.0).unwrap();
        assert!(e.cumulative_dispensed_ul() > 0.0);
        e.reset_run().unwrap();
        assert!((e.cumulative_dispensed_ul()).abs() < f64::EPSILON);
    }

    // -- Flow rate validation --

    #[test]
    fn flow_rate_valid() {
        assert!(enforcer().validate_flow_rate(100.0).is_ok());
        assert!(enforcer().validate_flow_rate(500.0).is_ok());
    }

    #[test]
    fn flow_rate_rejects_over_max() {
        assert!(enforcer().validate_flow_rate(500.1).is_err());
    }

    #[test]
    fn flow_rate_rejects_zero() {
        assert!(enforcer().validate_flow_rate(0.0).is_err());
    }

    #[test]
    fn flow_rate_rejects_negative() {
        assert!(enforcer().validate_flow_rate(-10.0).is_err());
    }

    #[test]
    fn flow_rate_rejects_nan() {
        assert!(enforcer().validate_flow_rate(f64::NAN).is_err());
    }

    // -- Speed validation --

    #[test]
    fn speed_valid() {
        assert!(enforcer().validate_speed(25.0).is_ok());
        assert!(enforcer().validate_speed(50.0).is_ok());
        assert!(enforcer().validate_speed(0.0).is_ok());
    }

    #[test]
    fn speed_rejects_negative() {
        assert!(enforcer().validate_speed(-1.0).is_err());
    }

    #[test]
    fn speed_rejects_over_max() {
        assert!(enforcer().validate_speed(50.1).is_err());
    }

    // -- Duration validation --

    #[test]
    fn duration_valid() {
        assert!(enforcer().validate_duration_s(45.0, 300.0).is_ok());
    }

    #[test]
    fn duration_rejects_zero() {
        assert!(enforcer().validate_duration_s(0.0, 300.0).is_err());
    }

    #[test]
    fn duration_rejects_negative() {
        assert!(enforcer().validate_duration_s(-1.0, 300.0).is_err());
    }

    #[test]
    fn duration_rejects_over_max() {
        assert!(enforcer().validate_duration_s(301.0, 300.0).is_err());
    }

    // -- Operation-specific limits --

    #[test]
    fn incubation_hours_valid() {
        assert!(enforcer().validate_incubation_hours(24.0).is_ok());
        assert!(enforcer().validate_incubation_hours(72.0).is_ok());
    }

    #[test]
    fn incubation_hours_rejects_over_max() {
        assert!(enforcer().validate_incubation_hours(72.1).is_err());
    }

    #[test]
    fn incubation_hours_rejects_zero() {
        assert!(enforcer().validate_incubation_hours(0.0).is_err());
    }

    #[test]
    fn heat_shock_hold_valid() {
        assert!(enforcer().validate_heat_shock_hold_s(45).is_ok());
        assert!(enforcer().validate_heat_shock_hold_s(300).is_ok());
    }

    #[test]
    fn heat_shock_hold_rejects_over_max() {
        assert!(enforcer().validate_heat_shock_hold_s(301).is_err());
    }

    #[test]
    fn heat_shock_hold_rejects_zero() {
        assert!(enforcer().validate_heat_shock_hold_s(0).is_err());
    }

    #[test]
    fn mix_cycles_valid() {
        assert!(enforcer().validate_mix_cycles(5).is_ok());
        assert!(enforcer().validate_mix_cycles(20).is_ok());
    }

    #[test]
    fn mix_cycles_rejects_over_max() {
        assert!(enforcer().validate_mix_cycles(21).is_err());
    }

    #[test]
    fn mix_cycles_rejects_zero() {
        assert!(enforcer().validate_mix_cycles(0).is_err());
    }

    // -- Rate limiting --

    #[test]
    fn rate_limit_allows_under_max() {
        let e = enforcer();
        // Should be able to make a few calls without hitting the limit
        for _ in 0..5 {
            e.check_rate_limit().unwrap();
        }
    }

    #[test]
    fn rate_limit_rejects_over_max() {
        let mut limits = test_limits();
        limits.rate.max_calls_per_minute = 3;
        let e = SafetyEnforcer::new(limits, test_bounds());

        e.check_rate_limit().unwrap();
        e.check_rate_limit().unwrap();
        e.check_rate_limit().unwrap();
        // 4th call within the same instant should fail
        assert!(e.check_rate_limit().is_err());
    }

    // -- Actuator interval --

    #[test]
    fn actuator_interval_allows_first_call() {
        let e = enforcer();
        assert!(e.check_actuator_interval().is_ok());
    }

    #[test]
    fn actuator_interval_rejects_rapid_calls() {
        let mut limits = test_limits();
        limits.rate.min_actuator_interval_ms = 1000; // 1 second
        let e = SafetyEnforcer::new(limits, test_bounds());

        e.check_actuator_interval().unwrap();
        // Immediate second call should fail (< 1s gap)
        assert!(e.check_actuator_interval().is_err());
    }

    // -- Safe travel height --

    #[test]
    fn safe_travel_height_returns_config_value() {
        assert!((enforcer().safe_travel_height() - 15.0).abs() < f64::EPSILON);
    }

    // -- Reset --

    #[test]
    fn reset_run_clears_all_state() {
        let e = enforcer();
        e.validate_and_track_dispense(500.0).unwrap();
        e.check_rate_limit().unwrap();
        e.check_actuator_interval().unwrap();

        e.reset_run().unwrap();

        assert!((e.cumulative_dispensed_ul()).abs() < f64::EPSILON);
        // Should be able to call actuator immediately after reset
        assert!(e.check_actuator_interval().is_ok());
    }
}
