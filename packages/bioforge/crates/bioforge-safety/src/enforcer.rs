//! Safety limit enforcement.

use bioforge_types::config::SafetyLimits;
use bioforge_types::error::BioForgeError;

/// Validates tool parameters against configured safety limits.
pub struct SafetyEnforcer {
    limits: SafetyLimits,
}

impl SafetyEnforcer {
    pub fn new(limits: SafetyLimits) -> Self {
        Self { limits }
    }

    /// Validate that a temperature target is within allowed range.
    pub fn validate_temperature(&self, target_c: f64) -> Result<(), BioForgeError> {
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

    /// Validate that a dispense volume is within allowed range.
    pub fn validate_volume(&self, volume_ul: f64) -> Result<(), BioForgeError> {
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
        if x < 0.0
            || y < 0.0
            || z < 0.0
            || x > self.limits.motion.max_speed_mm_s
            || y > self.limits.motion.max_speed_mm_s
        {
            return Err(BioForgeError::PositionOutOfBounds { x, y, z });
        }
        Ok(())
    }

    /// Access the current safety limits.
    pub fn limits(&self) -> &SafetyLimits {
        &self.limits
    }
}
