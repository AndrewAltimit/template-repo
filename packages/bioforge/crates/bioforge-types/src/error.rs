//! Error types for the BioForge platform.

use thiserror::Error;

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

    #[error("temperature out of range: {actual_c}C (limit: {limit_c}C)")]
    TemperatureOutOfRange { actual_c: f64, limit_c: f64 },

    #[error("volume out of range: {actual_ul}uL (limit: {limit_ul}uL)")]
    VolumeOutOfRange { actual_ul: f64, limit_ul: f64 },

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
