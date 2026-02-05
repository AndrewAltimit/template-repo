//! Append-only audit log for all tool calls, sensor readings, and state transitions.

use chrono::{SecondsFormat, Utc};
use serde::Serialize;
use std::fs::{self, OpenOptions};
use std::io::Write;
use std::path::{Path, PathBuf};

/// Append-only audit logger writing JSON Lines.
pub struct AuditLog {
    path: PathBuf,
}

impl AuditLog {
    /// Create a new audit log, ensuring the parent directory exists.
    pub fn new(path: impl Into<PathBuf>) -> std::io::Result<Self> {
        let path = path.into();
        if let Some(parent) = path.parent() {
            fs::create_dir_all(parent)?;
        }
        Ok(Self { path })
    }

    /// Append a structured event to the audit log.
    pub fn log<T: Serialize>(&self, event: &AuditEvent<T>) -> std::io::Result<()> {
        let line = serde_json::to_string(event)
            .map_err(|e| std::io::Error::new(std::io::ErrorKind::InvalidData, e))?;
        let mut file = OpenOptions::new()
            .create(true)
            .append(true)
            .open(&self.path)?;
        writeln!(file, "{line}")?;
        file.sync_data()?;
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
            ts: Utc::now().to_rfc3339_opts(SecondsFormat::Nanos, true),
            event: event.into(),
            run_id: run_id.into(),
            data,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn audit_log_creates_parent_dirs() {
        let dir = tempfile::tempdir().unwrap();
        let log_path = dir.path().join("nested").join("deep").join("audit.jsonl");
        let log = AuditLog::new(&log_path).unwrap();
        assert!(log_path.parent().unwrap().exists());

        let event = AuditEvent::new("test_event", "run_001", json!({"key": "value"}));
        log.log(&event).unwrap();

        let contents = fs::read_to_string(&log_path).unwrap();
        assert!(contents.contains("test_event"));
        assert!(contents.contains("run_001"));
    }

    #[test]
    fn audit_log_appends_multiple_events() {
        let dir = tempfile::tempdir().unwrap();
        let log_path = dir.path().join("audit.jsonl");
        let log = AuditLog::new(&log_path).unwrap();

        log.log(&AuditEvent::new("event_1", "run", json!({})))
            .unwrap();
        log.log(&AuditEvent::new("event_2", "run", json!({})))
            .unwrap();

        let contents = fs::read_to_string(&log_path).unwrap();
        let lines: Vec<&str> = contents.lines().collect();
        assert_eq!(lines.len(), 2);
    }

    #[test]
    fn audit_event_uses_nanosecond_timestamps() {
        let event = AuditEvent::new("test", "run", json!({}));
        // Nanosecond RFC3339 timestamps contain many digits after the decimal
        assert!(
            event.ts.contains('.'),
            "timestamp should have sub-second precision"
        );
    }
}
