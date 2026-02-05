//! Safety limit enforcement.

use bioforge_types::config::SafetyLimits;
use bioforge_types::error::BioForgeError;

/// Workspace bounds loaded from hardware config.
#[derive(Debug, Clone)]
pub struct WorkspaceBounds {
    pub x_max_mm: f64,
    pub y_max_mm: f64,
    pub z_max_mm: f64,
}

/// Validates tool parameters against configured safety limits.
pub struct SafetyEnforcer {
    limits: SafetyLimits,
    bounds: WorkspaceBounds,
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
        Self { limits, bounds }
    }

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

    /// Validate that a dispense volume is within allowed range.
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

    /// Access the current safety limits.
    pub fn limits(&self) -> &SafetyLimits {
        &self.limits
    }

    /// Access the workspace bounds.
    pub fn bounds(&self) -> &WorkspaceBounds {
        &self.bounds
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
            },
            motion: MotionLimits {
                max_speed_mm_s: 50.0,
                max_accel_mm_s2: 100.0,
            },
            rate: RateLimits {
                max_calls_per_minute: 60,
                min_actuator_interval_ms: 100,
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
        // absolute_max_c = 60.0 (hardware fuse level)
        assert!(enforcer().validate_temperature(60.1).is_err());
    }

    #[test]
    fn temperature_accepts_between_tool_and_absolute_max() {
        // tool_max_c = 50.0, absolute_max_c = 60.0
        // Values above tool_max are still rejected even if below absolute_max
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
}
