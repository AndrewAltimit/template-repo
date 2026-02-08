//! Tamper state monitoring for the briefcase system.
//!
//! Reads the tamper-gate state file to display the current tamper status.
//! This is a read-only display -- OASIS_OS never modifies tamper state
//! directly; it only reads the state file written by `tamper-sensor.service`.

use std::fmt;

use crate::error::Result;
use crate::vfs::Vfs;

/// Path to the tamper state file in the VFS.
pub const TAMPER_STATE_PATH: &str = "/sys/tamper/state";

/// Path to the tamper gate FIFO for sending disarm requests.
pub const TAMPER_GATE_FIFO: &str = "/sys/tamper/gate";

/// Current state of the tamper detection system.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TamperState {
    /// System is disarmed (tamper detection inactive).
    Disarmed,
    /// System is transitioning to armed state (countdown).
    Arming,
    /// System is fully armed (tamper detection active).
    Armed,
    /// Tamper event has been detected.
    Triggered,
    /// State could not be determined (file missing or unreadable).
    Unknown,
}

impl TamperState {
    /// Parse a state string from the tamper state file.
    pub fn parse(s: &str) -> Self {
        match s.trim().to_lowercase().as_str() {
            "disarmed" => Self::Disarmed,
            "arming" => Self::Arming,
            "armed" => Self::Armed,
            "triggered" => Self::Triggered,
            _ => Self::Unknown,
        }
    }

    /// Return a short status indicator for dashboard display.
    pub fn indicator(&self) -> &'static str {
        match self {
            Self::Disarmed => "[DISARMED]",
            Self::Arming => "[ARMING.]",
            Self::Armed => "[ARMED]",
            Self::Triggered => "[!TRIGGERED!]",
            Self::Unknown => "[?]",
        }
    }

    /// Return a color hint for the status indicator.
    /// Returns a CSS-style hex color string for the skin to use.
    pub fn color_hint(&self) -> &'static str {
        match self {
            Self::Disarmed => "#808080",  // gray
            Self::Arming => "#CCAA00",    // amber
            Self::Armed => "#00CC00",     // green
            Self::Triggered => "#FF0000", // red
            Self::Unknown => "#666666",   // dim gray
        }
    }
}

impl fmt::Display for TamperState {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Disarmed => write!(f, "DISARMED"),
            Self::Arming => write!(f, "ARMING"),
            Self::Armed => write!(f, "ARMED"),
            Self::Triggered => write!(f, "TRIGGERED"),
            Self::Unknown => write!(f, "UNKNOWN"),
        }
    }
}

/// Snapshot of the tamper system status.
#[derive(Debug, Clone)]
pub struct TamperStatus {
    /// Current tamper state.
    pub state: TamperState,
    /// Raw content of the state file (for diagnostics).
    pub raw: String,
}

/// Read the current tamper status from the VFS.
///
/// Returns `TamperState::Unknown` if the state file does not exist
/// or cannot be read (e.g., not running on the briefcase Pi).
pub fn read_tamper_status(vfs: &mut dyn Vfs) -> TamperStatus {
    if !vfs.exists(TAMPER_STATE_PATH) {
        return TamperStatus {
            state: TamperState::Unknown,
            raw: String::new(),
        };
    }
    match vfs.read(TAMPER_STATE_PATH) {
        Ok(data) => {
            let raw = String::from_utf8_lossy(&data).into_owned();
            let state = TamperState::parse(&raw);
            TamperStatus { state, raw }
        },
        Err(_) => TamperStatus {
            state: TamperState::Unknown,
            raw: String::new(),
        },
    }
}

/// Write a disarm request to the tamper gate FIFO.
///
/// This sends a message to `tamper-gate.service` requesting disarm.
/// The actual disarm only succeeds if the correct challenge response
/// is provided. Returns `Ok(())` if the write succeeded.
pub fn request_disarm(vfs: &mut dyn Vfs, challenge_response: &str) -> Result<()> {
    vfs.write(TAMPER_GATE_FIFO, challenge_response.as_bytes())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::vfs::{MemoryVfs, Vfs};

    #[test]
    fn parse_states() {
        assert_eq!(TamperState::parse("disarmed"), TamperState::Disarmed);
        assert_eq!(TamperState::parse("ARMING"), TamperState::Arming);
        assert_eq!(TamperState::parse("Armed\n"), TamperState::Armed);
        assert_eq!(TamperState::parse("triggered"), TamperState::Triggered);
        assert_eq!(TamperState::parse("garbage"), TamperState::Unknown);
        assert_eq!(TamperState::parse(""), TamperState::Unknown);
    }

    #[test]
    fn display_states() {
        assert_eq!(TamperState::Disarmed.to_string(), "DISARMED");
        assert_eq!(TamperState::Armed.to_string(), "ARMED");
        assert_eq!(TamperState::Triggered.to_string(), "TRIGGERED");
    }

    #[test]
    fn indicators() {
        assert_eq!(TamperState::Disarmed.indicator(), "[DISARMED]");
        assert_eq!(TamperState::Armed.indicator(), "[ARMED]");
        assert_eq!(TamperState::Triggered.indicator(), "[!TRIGGERED!]");
    }

    #[test]
    fn color_hints() {
        // Armed should be green-ish.
        assert!(TamperState::Armed.color_hint().contains("CC"));
        // Triggered should be red.
        assert!(TamperState::Triggered.color_hint().contains("FF0000"));
    }

    #[test]
    fn read_status_missing_file() {
        let mut vfs = MemoryVfs::new();
        let status = read_tamper_status(&mut vfs);
        assert_eq!(status.state, TamperState::Unknown);
        assert!(status.raw.is_empty());
    }

    #[test]
    fn read_status_armed() {
        let mut vfs = MemoryVfs::new();
        vfs.mkdir("/sys").unwrap();
        vfs.mkdir("/sys/tamper").unwrap();
        vfs.write(TAMPER_STATE_PATH, b"armed\n").unwrap();
        let status = read_tamper_status(&mut vfs);
        assert_eq!(status.state, TamperState::Armed);
    }

    #[test]
    fn read_status_triggered() {
        let mut vfs = MemoryVfs::new();
        vfs.mkdir("/sys").unwrap();
        vfs.mkdir("/sys/tamper").unwrap();
        vfs.write(TAMPER_STATE_PATH, b"triggered").unwrap();
        let status = read_tamper_status(&mut vfs);
        assert_eq!(status.state, TamperState::Triggered);
    }

    #[test]
    fn request_disarm_writes_fifo() {
        let mut vfs = MemoryVfs::new();
        vfs.mkdir("/sys").unwrap();
        vfs.mkdir("/sys/tamper").unwrap();
        request_disarm(&mut vfs, "response-token").unwrap();
        let data = vfs.read(TAMPER_GATE_FIFO).unwrap();
        assert_eq!(data, b"response-token");
    }
}
