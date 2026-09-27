//! Error types for the BioForge platform.

use thiserror::Error;

/// Which limit of an allowed range a value violated.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum LimitBound {
    /// The value is below the minimum.
    Minimum,
    /// The value is above the maximum.
    Maximum,
}

impl LimitBound {
    /// Phrase used in error messages, e.g. "below the minimum".
    pub fn relation(self) -> &'static str {
        match self {
            Self::Minimum => "below the minimum",
            Self::Maximum => "above the maximum",
        }
    }
}

#[derive(Debug, Error)]
pub enum BioForgeError {
    #[error("safety violation: {0}")]
    SafetyViolation(String),

    #[error("hardware fault: {0}")]
    HardwareFault(String),

    #[error("protocol error: {0}")]
    ProtocolError(String),

    #[error("invalid state transition: {from:?} -> {to:?}")]
    InvalidTransition { from: String, to: String },

    #[error("human gate pending: {action}")]
    HumanGatePending { action: String },

    /// `bound` records which side of the range was violated, so an
    /// under-temperature is not reported as if it were an overshoot.
    #[error("temperature out of range: {actual_c}C is {} {limit_c}C", .bound.relation())]
    TemperatureOutOfRange {
        actual_c: f64,
        limit_c: f64,
        bound: LimitBound,
    },

    #[error("volume out of range: {actual_ul}uL is {} {limit_ul}uL", .bound.relation())]
    VolumeOutOfRange {
        actual_ul: f64,
        limit_ul: f64,
        bound: LimitBound,
    },

    #[error("position out of bounds: ({x}, {y}, {z}) outside [{x_max}, {y_max}, {z_max}]")]
    PositionOutOfBounds {
        x: f64,
        y: f64,
        z: f64,
        x_max: f64,
        y_max: f64,
        z_max: f64,
    },

    #[error("emergency stop activated")]
    EmergencyStop,

    #[error("co-processor communication error: {0}")]
    CoprocessorError(String),

    #[error("camera error: {0}")]
    CameraError(String),

    #[error("configuration error: {0}")]
    ConfigError(String),

    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn temperature_error_names_the_violated_bound() {
        let below = BioForgeError::TemperatureOutOfRange {
            actual_c: -10.0,
            limit_c: -5.0,
            bound: LimitBound::Minimum,
        };
        assert_eq!(
            below.to_string(),
            "temperature out of range: -10C is below the minimum -5C"
        );

        let above = BioForgeError::TemperatureOutOfRange {
            actual_c: 55.0,
            limit_c: 50.0,
            bound: LimitBound::Maximum,
        };
        assert_eq!(
            above.to_string(),
            "temperature out of range: 55C is above the maximum 50C"
        );
    }

    #[test]
    fn volume_error_names_the_violated_bound() {
        let below = BioForgeError::VolumeOutOfRange {
            actual_ul: 0.1,
            limit_ul: 1.0,
            bound: LimitBound::Minimum,
        };
        assert!(below.to_string().contains("below the minimum 1uL"));
    }
}
