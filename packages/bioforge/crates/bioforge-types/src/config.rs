//! Hardware and safety configuration types.

use serde::{Deserialize, Serialize};

/// Top-level hardware configuration loaded from hardware.toml.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HardwareConfig {
    pub pi: PiConfig,
    pub coprocessor: CoprocessorConfig,
    pub thermal: ThermalConfig,
    pub motion: MotionConfig,
    pub pumps: PumpConfig,
    pub camera: CameraConfig,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PiConfig {
    /// GPIO pin for the physical E-Stop button.
    pub estop_pin: u8,
    /// PWM pin for LED ring light.
    pub led_pwm_pin: u8,
    /// GPIO pin for DHT22 ambient sensor.
    pub dht22_pin: u8,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CoprocessorConfig {
    /// Serial port path for ESP32/RP2040 co-processor.
    pub serial_port: String,
    /// Baud rate for co-processor communication.
    pub baud_rate: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ThermalConfig {
    /// DS18B20 1-Wire addresses per zone.
    pub cold_zone_sensor: String,
    pub warm_zone_sensor: String,
    /// PID tuning parameters per zone.
    pub cold_zone_pid: PidParams,
    pub warm_zone_pid: PidParams,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PidParams {
    pub kp: f64,
    pub ki: f64,
    pub kd: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MotionConfig {
    /// Steps per mm for X axis.
    pub x_steps_per_mm: f64,
    /// Steps per mm for Y axis.
    pub y_steps_per_mm: f64,
    /// Enclosure bounds in mm.
    pub x_max_mm: f64,
    pub y_max_mm: f64,
    pub z_max_mm: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PumpConfig {
    /// Steps per microliter for each syringe pump.
    pub syringe_steps_per_ul: Vec<f64>,
    /// Max flow rate in uL/s for peristaltic pumps.
    pub peristaltic_max_flow_rate: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CameraConfig {
    /// Resolution width in pixels.
    pub width: u32,
    /// Resolution height in pixels.
    pub height: u32,
    /// Fixed focal distance in mm (for plate imaging).
    pub focal_distance_mm: f64,
}

/// Safety limits loaded from safety_limits.toml.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SafetyLimits {
    pub thermal: ThermalLimits,
    pub volume: VolumeLimits,
    pub motion: MotionLimits,
    pub rate: RateLimits,
    pub operations: OperationLimits,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ThermalLimits {
    /// Absolute maximum temperature in Celsius (hardware fuse level).
    pub absolute_max_c: f64,
    /// Maximum settable temperature via MCP tools.
    pub tool_max_c: f64,
    /// Minimum settable temperature via MCP tools.
    pub tool_min_c: f64,
    /// Maximum allowed overshoot before abort.
    pub max_overshoot_c: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VolumeLimits {
    /// Maximum single dispense volume in uL.
    pub max_dispense_ul: f64,
    /// Minimum single dispense volume in uL.
    pub min_dispense_ul: f64,
    /// Maximum total volume per run in mL.
    pub max_total_ml: f64,
    /// Maximum flow rate for any pump in uL/s.
    pub max_flow_rate_ul_s: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MotionLimits {
    /// Maximum speed in mm/s.
    pub max_speed_mm_s: f64,
    /// Maximum acceleration in mm/s^2.
    pub max_accel_mm_s2: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RateLimits {
    /// Maximum tool calls per minute.
    pub max_calls_per_minute: u32,
    /// Minimum interval between actuator commands in ms.
    pub min_actuator_interval_ms: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OperationLimits {
    /// Maximum incubation duration in hours.
    pub max_incubation_hours: f64,
    /// Maximum heat shock hold in seconds.
    pub max_heat_shock_hold_s: u64,
    /// Maximum mix cycles per operation.
    pub max_mix_cycles: u32,
    /// Default Z height (mm) when Z is omitted from move commands.
    pub safe_travel_height_mm: f64,
}
