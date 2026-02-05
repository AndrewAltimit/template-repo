//! Append-only audit log for all tool calls, sensor readings, and state transitions.

use chrono::Utc;
use serde::Serialize;
use std::fs::OpenOptions;
use std::io::Write;
use std::path::{Path, PathBuf};

/// Append-only audit logger writing JSON Lines.
pub struct AuditLog {
    path: PathBuf,
}

impl AuditLog {
    pub fn new(path: impl Into<PathBuf>) -> Self {
        Self { path: path.into() }
    }

    /// Append a structured event to the audit log.
    pub fn log<T: Serialize>(&self, event: &AuditEvent<T>) -> std::io::Result<()> {
        let line = serde_json::to_string(event)?;
        let mut file = OpenOptions::new()
            .create(true)
            .append(true)
            .open(&self.path)?;
        writeln!(file, "{line}")?;
        Ok(())
    }

    /// Return the log file path.
    pub fn path(&self) -> &Path {
        &self.path
    }
}

/// A single audit log entry.
#[derive(Debug, Clone, Serialize)]
pub struct AuditEvent<T: Serialize> {
    pub ts: String,
    pub event: String,
    pub run_id: String,
    #[serde(flatten)]
    pub data: T,
}

impl<T: Serialize> AuditEvent<T> {
    pub fn new(event: impl Into<String>, run_id: impl Into<String>, data: T) -> Self {
        Self {
            ts: Utc::now().to_rfc3339(),
            event: event.into(),
            run_id: run_id.into(),
            data,
        }
    }
}
