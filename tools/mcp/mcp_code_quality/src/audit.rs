//! Append-only JSON-lines audit log with size-based rotation.
//!
//! Each tool invocation appends one [`AuditEntry`] line. When the file grows
//! past `max_bytes` it is renamed to `<name>.1` (replacing any previous
//! rotation) so the log cannot fill the disk. Writes are serialized through a
//! mutex so concurrent tool calls never interleave partial lines. Failures to
//! write are logged once and otherwise ignored -- auditing must never make a
//! tool call fail.

use crate::types::AuditEntry;
use chrono::Utc;
use std::fs::OpenOptions;
use std::io::Write;
use std::path::{Path, PathBuf};
use std::sync::Mutex;
use std::sync::atomic::{AtomicBool, Ordering};
use tracing::warn;

/// Default rotation threshold (10 MiB).
pub const DEFAULT_MAX_BYTES: u64 = 10 * 1024 * 1024;

/// Upper bound on entries returned by [`AuditLog::read`].
pub const MAX_READ_ENTRIES: usize = 1000;

/// JSON-lines audit log.
#[derive(Debug)]
pub struct AuditLog {
    path: PathBuf,
    max_bytes: u64,
    write_lock: Mutex<()>,
    warned: AtomicBool,
}

impl AuditLog {
    /// Create the log (and its parent directory, best effort).
    pub fn new(path: PathBuf, max_bytes: u64) -> Self {
        if let Some(parent) = path.parent()
            && !parent.as_os_str().is_empty()
            && let Err(e) = std::fs::create_dir_all(parent)
        {
            warn!(
                "Cannot create audit log directory {}: {}",
                parent.display(),
                e
            );
        }
        Self {
            path,
            max_bytes,
            write_lock: Mutex::new(()),
            warned: AtomicBool::new(false),
        }
    }

    /// Log file path.
    pub fn path(&self) -> &Path {
        &self.path
    }

    /// Append an entry.
    pub fn record(&self, operation: &str, path: &str, success: bool, details: serde_json::Value) {
        let entry = AuditEntry {
            timestamp: Utc::now().to_rfc3339(),
            operation: operation.to_string(),
            path: path.to_string(),
            success,
            details,
        };
        let Ok(mut line) = serde_json::to_string(&entry) else {
            return;
        };
        line.push('\n');

        // A poisoned lock only means another writer panicked mid-write; the
        // file itself is still fine, so keep going.
        let _guard = self.write_lock.lock().unwrap_or_else(|e| e.into_inner());
        if let Err(e) = self.append(line.as_bytes())
            && !self.warned.swap(true, Ordering::Relaxed)
        {
            warn!(
                "Audit log {} is not writable ({}); further failures are silent",
                self.path.display(),
                e
            );
        }
    }

    fn append(&self, bytes: &[u8]) -> std::io::Result<()> {
        if let Ok(meta) = std::fs::metadata(&self.path)
            && meta.len() + bytes.len() as u64 > self.max_bytes
        {
            let rotated = rotated_path(&self.path);
            let _ = std::fs::remove_file(&rotated);
            std::fs::rename(&self.path, &rotated)?;
        }
        let mut file = OpenOptions::new()
            .create(true)
            .append(true)
            .open(&self.path)?;
        file.write_all(bytes)
    }

    /// Most recent `limit` entries (oldest first), optionally filtered by
    /// operation name. Reads the current file and, if needed to satisfy
    /// `limit`, the rotated one. Blocking; call via `spawn_blocking`.
    pub fn read(&self, limit: usize, operation: Option<&str>) -> Result<Vec<AuditEntry>, String> {
        let limit = limit.clamp(1, MAX_READ_ENTRIES);
        let mut entries = read_file(&self.path, operation)?;
        if entries.len() < limit {
            let mut older = read_file(&rotated_path(&self.path), operation)?;
            older.append(&mut entries);
            entries = older;
        }
        let skip = entries.len().saturating_sub(limit);
        Ok(entries.split_off(skip))
    }
}

fn rotated_path(path: &Path) -> PathBuf {
    let mut s = path.as_os_str().to_owned();
    s.push(".1");
    PathBuf::from(s)
}

fn read_file(path: &Path, operation: Option<&str>) -> Result<Vec<AuditEntry>, String> {
    match std::fs::read_to_string(path) {
        Ok(content) => Ok(content
            .lines()
            .filter_map(|line| serde_json::from_str::<AuditEntry>(line).ok())
            .filter(|e| operation.is_none_or(|op| e.operation == op))
            .collect()),
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => Ok(Vec::new()),
        Err(e) => Err(format!("Failed to read audit log {}: {e}", path.display())),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn tmp_log(name: &str) -> PathBuf {
        std::env::temp_dir()
            .join(format!(
                "mcp-cq-audit-{}-{}-{}",
                name,
                std::process::id(),
                std::time::SystemTime::now()
                    .duration_since(std::time::UNIX_EPOCH)
                    .unwrap()
                    .as_nanos()
            ))
            .join("audit.log")
    }

    #[test]
    fn record_and_read_back() {
        let path = tmp_log("rw");
        let log = AuditLog::new(path.clone(), DEFAULT_MAX_BYTES);
        log.record("lint", "/a", true, json!({"n": 1}));
        log.record("format_check", "/b", false, json!({}));
        log.record("lint", "/c", true, json!({}));

        let all = log.read(100, None).unwrap();
        assert_eq!(all.len(), 3);
        assert_eq!(all[0].path, "/a");

        let lint = log.read(100, Some("lint")).unwrap();
        assert_eq!(lint.len(), 2);

        let last = log.read(1, None).unwrap();
        assert_eq!(last.len(), 1);
        assert_eq!(last[0].path, "/c");
        std::fs::remove_dir_all(path.parent().unwrap()).ok();
    }

    #[test]
    fn missing_log_reads_empty() {
        let log = AuditLog::new(tmp_log("missing"), DEFAULT_MAX_BYTES);
        assert!(log.read(10, None).unwrap().is_empty());
        std::fs::remove_dir_all(log.path().parent().unwrap()).ok();
    }

    #[test]
    fn rotates_when_too_large() {
        let path = tmp_log("rotate");
        let log = AuditLog::new(path.clone(), 1000);
        for i in 0..40 {
            log.record("lint", &format!("/p{i}"), true, json!({}));
        }
        assert!(rotated_path(&path).exists());
        assert!(std::fs::metadata(&path).unwrap().len() <= 1000);
        // The newest entry is always readable, and reads span the rotation.
        let entries = log.read(5, None).unwrap();
        assert_eq!(entries.last().unwrap().path, "/p39");
        assert_eq!(entries.len(), 5);
        std::fs::remove_dir_all(path.parent().unwrap()).ok();
    }

    #[test]
    fn corrupt_lines_are_skipped() {
        let path = tmp_log("corrupt");
        let log = AuditLog::new(path.clone(), DEFAULT_MAX_BYTES);
        std::fs::write(&path, "not json\n").unwrap();
        log.record("lint", "/ok", true, json!({}));
        let entries = log.read(10, None).unwrap();
        assert_eq!(entries.len(), 1);
        std::fs::remove_dir_all(path.parent().unwrap()).ok();
    }
}
