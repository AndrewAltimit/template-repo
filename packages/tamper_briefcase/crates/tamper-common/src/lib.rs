//! Shared types and configuration for the tamper-responsive briefcase system.
//!
//! This crate defines the event protocol between the sensor daemon and the gate
//! orchestrator, the system state machine, and configuration structures.

use std::fmt;
use std::fs;
use std::path::{Path, PathBuf};

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

// ---------------------------------------------------------------------------
// Events (sensor -> gate via FIFO)
// ---------------------------------------------------------------------------

/// Event types emitted by the sensor daemon.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum EventType {
    /// Hall sensor transitioned from closed to open.
    LidOpened,
    /// Hall sensor transitioned from open to closed.
    LidClosed,
    /// Hall reads closed but light exceeds threshold (possible bypass).
    LightAnomaly,
    /// Periodic liveness signal from the sensor daemon.
    Heartbeat,
}

impl fmt::Display for EventType {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::LidOpened => write!(f, "LID_OPENED"),
            Self::LidClosed => write!(f, "LID_CLOSED"),
            Self::LightAnomaly => write!(f, "LIGHT_ANOMALY"),
            Self::Heartbeat => write!(f, "HEARTBEAT"),
        }
    }
}

/// Confidence level for a tamper event.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum Confidence {
    /// Both sensors agree.
    High,
    /// Hall triggered alone (dark environment).
    Medium,
    /// Sensor disagreement.
    Anomaly,
}

impl fmt::Display for Confidence {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::High => write!(f, "HIGH"),
            Self::Medium => write!(f, "MEDIUM"),
            Self::Anomaly => write!(f, "ANOMALY"),
        }
    }
}

/// Hall effect sensor state.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum HallState {
    /// Magnet detected -- lid is closed.
    Closed,
    /// No magnet -- lid is open.
    Open,
}

impl fmt::Display for HallState {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Closed => write!(f, "CLOSED"),
            Self::Open => write!(f, "OPEN"),
        }
    }
}

/// A tamper event transmitted from sensor daemon to gate orchestrator.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TamperEvent {
    pub timestamp: DateTime<Utc>,
    pub event_type: EventType,
    pub hall_state: HallState,
    pub lux: f64,
    pub confidence: Confidence,
}

// ---------------------------------------------------------------------------
// System state machine (gate orchestrator)
// ---------------------------------------------------------------------------

/// States for the gate orchestrator FSM.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SystemState {
    /// Lid open or recently closed, system not armed.
    Disarmed,
    /// Lid closed, counting down arming delay.
    Arming,
    /// Fully armed -- any lid open triggers challenge.
    Armed,
    /// Password challenge is active.
    Challenging,
    /// Wipe has been authorized.
    Wiping,
}

impl fmt::Display for SystemState {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Disarmed => write!(f, "DISARMED"),
            Self::Arming => write!(f, "ARMING"),
            Self::Armed => write!(f, "ARMED"),
            Self::Challenging => write!(f, "CHALLENGING"),
            Self::Wiping => write!(f, "WIPING"),
        }
    }
}

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

/// System configuration loaded from `/etc/tamper/config.toml` or defaults.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Config {
    /// GPIO pin for the A3144 Hall effect sensor (BCM numbering).
    pub hall_gpio_pin: u8,

    /// I2C address for the BH1750 light sensor.
    pub bh1750_i2c_addr: u16,

    /// I2C bus number (typically 1 on Raspberry Pi).
    pub i2c_bus: u8,

    /// Lux threshold above which light is considered significant.
    pub light_threshold_lux: f64,

    /// Sensor polling interval in milliseconds.
    pub poll_interval_ms: u64,

    /// Path to the event FIFO between sensor and gate.
    pub event_fifo: PathBuf,

    /// Seconds the lid must remain closed before arming.
    pub arming_delay_secs: u64,

    /// Seconds allowed for the password challenge.
    pub challenge_timeout_secs: u64,

    /// Maximum password attempts before wipe.
    pub max_challenge_attempts: u32,

    /// Consecutive light anomalies before forced challenge.
    pub anomaly_escalation_count: u32,

    /// How often the sensor emits a heartbeat event (seconds).
    pub heartbeat_interval_secs: u64,

    /// How long the gate waits without a heartbeat before assuming the sensor
    /// is compromised (seconds). Must be > heartbeat_interval_secs.
    pub heartbeat_timeout_secs: u64,

    /// Path to the challenge binary.
    pub challenge_binary: PathBuf,

    /// Path to the wipe trigger file.
    pub wipe_trigger_file: PathBuf,

    /// Path to the password hash file.
    pub password_hash_file: PathBuf,

    /// Path to the password salt file.
    pub password_salt_file: PathBuf,

    /// LUKS data partition device path.
    pub data_partition: PathBuf,
}

impl Default for Config {
    fn default() -> Self {
        Self {
            hall_gpio_pin: 4,
            bh1750_i2c_addr: 0x23,
            i2c_bus: 1,
            light_threshold_lux: 5.0,
            poll_interval_ms: 250,
            event_fifo: PathBuf::from("/run/tamper/events"),
            arming_delay_secs: 15,
            challenge_timeout_secs: 120,
            max_challenge_attempts: 3,
            anomaly_escalation_count: 10,
            heartbeat_interval_secs: 5,
            heartbeat_timeout_secs: 15,
            challenge_binary: PathBuf::from("/usr/local/bin/tamper-challenge"),
            wipe_trigger_file: PathBuf::from("/run/tamper/wipe-authorized"),
            password_hash_file: PathBuf::from("/etc/tamper/password.hash"),
            password_salt_file: PathBuf::from("/etc/tamper/salt"),
            data_partition: PathBuf::from("/dev/mmcblk0p3"),
        }
    }
}

impl Config {
    /// Default config file path.
    pub const DEFAULT_PATH: &str = "/etc/tamper/config.toml";

    /// Load configuration from a TOML file, falling back to defaults for missing
    /// fields.
    pub fn load(path: &Path) -> Self {
        match fs::read_to_string(path) {
            Ok(contents) => match toml::from_str(&contents) {
                Ok(config) => {
                    log::info!("Loaded configuration from {}", path.display());
                    config
                },
                Err(e) => {
                    log::warn!(
                        "Failed to parse config at {}: {} -- using defaults",
                        path.display(),
                        e
                    );
                    Self::default()
                },
            },
            Err(_) => {
                log::info!("No config file at {} -- using defaults", path.display());
                Self::default()
            },
        }
    }
}

// ---------------------------------------------------------------------------
// Shared constants
// ---------------------------------------------------------------------------

/// BH1750 continuous high-resolution measurement mode command byte.
pub const BH1750_CONTINUOUS_HIGH_RES: u8 = 0x10;

/// BH1750 power-on command byte.
pub const BH1750_POWER_ON: u8 = 0x01;

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    // -- EventType ----------------------------------------------------------

    #[test]
    fn event_type_display() {
        assert_eq!(EventType::LidOpened.to_string(), "LID_OPENED");
        assert_eq!(EventType::LidClosed.to_string(), "LID_CLOSED");
        assert_eq!(EventType::LightAnomaly.to_string(), "LIGHT_ANOMALY");
        assert_eq!(EventType::Heartbeat.to_string(), "HEARTBEAT");
    }

    #[test]
    fn event_type_serde_roundtrip() {
        for variant in [
            EventType::LidOpened,
            EventType::LidClosed,
            EventType::LightAnomaly,
            EventType::Heartbeat,
        ] {
            let json = serde_json::to_string(&variant).unwrap();
            let back: EventType = serde_json::from_str(&json).unwrap();
            assert_eq!(variant, back);
        }
    }

    // -- Confidence ---------------------------------------------------------

    #[test]
    fn confidence_display() {
        assert_eq!(Confidence::High.to_string(), "HIGH");
        assert_eq!(Confidence::Medium.to_string(), "MEDIUM");
        assert_eq!(Confidence::Anomaly.to_string(), "ANOMALY");
    }

    #[test]
    fn confidence_serde_roundtrip() {
        for variant in [Confidence::High, Confidence::Medium, Confidence::Anomaly] {
            let json = serde_json::to_string(&variant).unwrap();
            let back: Confidence = serde_json::from_str(&json).unwrap();
            assert_eq!(variant, back);
        }
    }

    // -- HallState ----------------------------------------------------------

    #[test]
    fn hall_state_display() {
        assert_eq!(HallState::Closed.to_string(), "CLOSED");
        assert_eq!(HallState::Open.to_string(), "OPEN");
    }

    #[test]
    fn hall_state_serde_roundtrip() {
        for variant in [HallState::Closed, HallState::Open] {
            let json = serde_json::to_string(&variant).unwrap();
            let back: HallState = serde_json::from_str(&json).unwrap();
            assert_eq!(variant, back);
        }
    }

    // -- SystemState --------------------------------------------------------

    #[test]
    fn system_state_display() {
        assert_eq!(SystemState::Disarmed.to_string(), "DISARMED");
        assert_eq!(SystemState::Arming.to_string(), "ARMING");
        assert_eq!(SystemState::Armed.to_string(), "ARMED");
        assert_eq!(SystemState::Challenging.to_string(), "CHALLENGING");
        assert_eq!(SystemState::Wiping.to_string(), "WIPING");
    }

    // -- TamperEvent --------------------------------------------------------

    #[test]
    fn tamper_event_serde_roundtrip() {
        let event = TamperEvent {
            timestamp: chrono::Utc::now(),
            event_type: EventType::LidOpened,
            hall_state: HallState::Open,
            lux: 42.5,
            confidence: Confidence::High,
        };

        let json = serde_json::to_string(&event).unwrap();
        let back: TamperEvent = serde_json::from_str(&json).unwrap();

        assert_eq!(back.event_type, event.event_type);
        assert_eq!(back.hall_state, event.hall_state);
        assert!((back.lux - event.lux).abs() < f64::EPSILON);
        assert_eq!(back.confidence, event.confidence);
    }

    #[test]
    fn tamper_event_json_structure() {
        let event = TamperEvent {
            timestamp: chrono::Utc::now(),
            event_type: EventType::Heartbeat,
            hall_state: HallState::Closed,
            lux: 0.83,
            confidence: Confidence::High,
        };

        let json = serde_json::to_string(&event).unwrap();
        let value: serde_json::Value = serde_json::from_str(&json).unwrap();

        assert!(value.get("timestamp").is_some());
        assert_eq!(value["event_type"], "Heartbeat");
        assert_eq!(value["hall_state"], "Closed");
        assert_eq!(value["confidence"], "High");
    }

    // -- Config -------------------------------------------------------------

    #[test]
    fn config_defaults() {
        let config = Config::default();

        assert_eq!(config.hall_gpio_pin, 4);
        assert_eq!(config.bh1750_i2c_addr, 0x23);
        assert_eq!(config.i2c_bus, 1);
        assert!((config.light_threshold_lux - 5.0).abs() < f64::EPSILON);
        assert_eq!(config.poll_interval_ms, 250);
        assert_eq!(config.arming_delay_secs, 15);
        assert_eq!(config.challenge_timeout_secs, 120);
        assert_eq!(config.max_challenge_attempts, 3);
        assert_eq!(config.anomaly_escalation_count, 10);
        assert_eq!(config.heartbeat_interval_secs, 5);
        assert_eq!(config.heartbeat_timeout_secs, 15);
    }

    #[test]
    fn config_load_missing_file_returns_defaults() {
        let config = Config::load(std::path::Path::new("/nonexistent/path/config.toml"));

        // Should fall back to defaults without panicking.
        assert_eq!(config.hall_gpio_pin, 4);
        assert_eq!(config.arming_delay_secs, 15);
    }

    #[test]
    fn config_load_from_toml() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("config.toml");

        std::fs::write(
            &path,
            r#"
hall_gpio_pin = 17
bh1750_i2c_addr = 92
i2c_bus = 2
light_threshold_lux = 10.0
poll_interval_ms = 500
event_fifo = "/tmp/test-fifo"
arming_delay_secs = 30
challenge_timeout_secs = 60
max_challenge_attempts = 5
anomaly_escalation_count = 20
heartbeat_interval_secs = 10
heartbeat_timeout_secs = 30
challenge_binary = "/usr/bin/test-challenge"
wipe_trigger_file = "/tmp/test-wipe"
password_hash_file = "/tmp/test-hash"
password_salt_file = "/tmp/test-salt"
data_partition = "/dev/sda1"
"#,
        )
        .unwrap();

        let config = Config::load(&path);

        assert_eq!(config.hall_gpio_pin, 17);
        assert_eq!(config.bh1750_i2c_addr, 92);
        assert_eq!(config.i2c_bus, 2);
        assert!((config.light_threshold_lux - 10.0).abs() < f64::EPSILON);
        assert_eq!(config.poll_interval_ms, 500);
        assert_eq!(config.arming_delay_secs, 30);
        assert_eq!(config.challenge_timeout_secs, 60);
        assert_eq!(config.max_challenge_attempts, 5);
        assert_eq!(config.anomaly_escalation_count, 20);
        assert_eq!(config.heartbeat_interval_secs, 10);
        assert_eq!(config.heartbeat_timeout_secs, 30);
    }

    #[test]
    fn config_load_invalid_toml_returns_defaults() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("config.toml");

        std::fs::write(&path, "this is not valid toml {{{{").unwrap();

        let config = Config::load(&path);
        assert_eq!(config.hall_gpio_pin, 4);
    }

    #[test]
    fn config_serde_roundtrip() {
        let config = Config::default();
        let toml_str = toml::to_string(&config).unwrap();
        let back: Config = toml::from_str(&toml_str).unwrap();

        assert_eq!(back.hall_gpio_pin, config.hall_gpio_pin);
        assert_eq!(back.arming_delay_secs, config.arming_delay_secs);
        assert_eq!(back.event_fifo, config.event_fifo);
    }

    // -- Constants ----------------------------------------------------------

    #[test]
    fn bh1750_constants() {
        assert_eq!(BH1750_CONTINUOUS_HIGH_RES, 0x10);
        assert_eq!(BH1750_POWER_ON, 0x01);
    }
}
