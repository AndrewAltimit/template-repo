//! Structured audit logging for wrapper invocations
//!
//! Every wrapper invocation produces a JSON log entry recording what was
//! executed, whether it was allowed or blocked, and caller identification.
//!
//! Logging is best-effort: failures are reported to stderr but never
//! block the wrapper from executing the command.

use chrono::Utc;
use serde::Serialize;
use std::io::Write;
use std::path::PathBuf;
use std::sync::atomic::{AtomicBool, Ordering};

/// Default log directory under $HOME
const DEFAULT_LOG_SUBDIR: &str = ".local/share/wrapper-guard";
const DEFAULT_LOG_FILE: &str = "audit.log";

/// Maximum log file size before rotation (10 MB)
const MAX_LOG_SIZE_BYTES: u64 = 10 * 1024 * 1024;

/// Environment variable to override log directory
const LOG_DIR_ENV: &str = "WRAPPER_GUARD_LOG_DIR";

/// Action taken by the wrapper
#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "lowercase")]
pub enum AuditAction {
    Allowed,
    Blocked,
    Error,
}

/// A single audit log entry
#[derive(Debug, Clone, Serialize)]
pub struct AuditEntry {
    /// ISO 8601 timestamp
    pub timestamp: String,
    /// Wrapper that generated this entry ("git-guard" or "gh-validator")
    pub wrapper: String,
    /// Action taken
    pub action: AuditAction,
    /// Sanitized arguments (secrets masked)
    pub args_sanitized: Vec<String>,
    /// Reason for blocking (if action is Blocked)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub blocked_reason: Option<String>,
    /// PID of the wrapper process
    pub caller_pid: u32,
    /// Parent PID
    pub caller_ppid: u32,
    /// Path of the parent process executable (Linux only)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub caller_exe: Option<String>,
    /// UID of the calling user
    pub caller_uid: u32,
    /// Path to the real binary being invoked
    pub real_binary_path: String,
    /// Compile-time source hash of the wrapper
    pub source_hash: String,
}

impl AuditEntry {
    /// Create a new audit entry with caller info auto-populated
    pub fn new(
        wrapper: &str,
        action: AuditAction,
        args_sanitized: Vec<String>,
        real_binary_path: &str,
        source_hash: &str,
    ) -> Self {
        let (pid, ppid, uid) = get_process_info();
        let caller_exe = get_caller_exe(ppid);

        Self {
            timestamp: Utc::now().to_rfc3339(),
            wrapper: wrapper.to_string(),
            action,
            args_sanitized,
            blocked_reason: None,
            caller_pid: pid,
            caller_ppid: ppid,
            caller_exe,
            caller_uid: uid,
            real_binary_path: real_binary_path.to_string(),
            source_hash: source_hash.to_string(),
        }
    }

    /// Set the blocked reason
    pub fn with_blocked_reason(mut self, reason: String) -> Self {
        self.blocked_reason = Some(reason);
        self
    }
}

/// Whether we have already warned about audit log failures this process.
/// Prevents flooding stderr with repeated permission warnings on every git operation.
static AUDIT_WARNED: AtomicBool = AtomicBool::new(false);

/// Log an audit entry to the audit log file.
///
/// This is best-effort: the first failure prints a warning to stderr,
/// subsequent failures are silently ignored to avoid flooding output.
pub fn log_event(entry: &AuditEntry) {
    if let Err(e) = try_log_event(entry) {
        // Only warn once per process to avoid flooding stderr
        if !AUDIT_WARNED.swap(true, Ordering::Relaxed) {
            eprintln!(
                "[wrapper-guard] Audit log warning: {} (further warnings suppressed)",
                e
            );
        }
    }
}

/// Attempt to write an audit entry to the log file
fn try_log_event(entry: &AuditEntry) -> std::io::Result<()> {
    let log_dir = resolve_log_dir();
    try_log_event_to(entry, &log_dir)
}

/// Attempt to write an audit entry to a specific directory
fn try_log_event_to(entry: &AuditEntry, log_dir: &std::path::Path) -> std::io::Result<()> {
    std::fs::create_dir_all(log_dir)?;

    let log_path = log_dir.join(DEFAULT_LOG_FILE);

    // Rotate if needed
    rotate_if_needed(&log_path)?;

    // Append JSON line
    let mut file = std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(&log_path)?;

    serde_json::to_writer(&mut file, entry).map_err(std::io::Error::other)?;
    writeln!(file)?;

    Ok(())
}

/// Resolve the log directory path
fn resolve_log_dir() -> PathBuf {
    // Check environment variable override
    if let Ok(dir) = std::env::var(LOG_DIR_ENV) {
        return PathBuf::from(dir);
    }

    // Default: $HOME/.local/share/wrapper-guard/
    if let Ok(home) = std::env::var("HOME") {
        return PathBuf::from(home).join(DEFAULT_LOG_SUBDIR);
    }

    // Last resort fallback
    PathBuf::from("/tmp/wrapper-guard")
}

/// Simple size-based log rotation: rename .log to .log.1
fn rotate_if_needed(log_path: &PathBuf) -> std::io::Result<()> {
    if let Ok(metadata) = std::fs::metadata(log_path) {
        if metadata.len() > MAX_LOG_SIZE_BYTES {
            let rotated = log_path.with_extension("log.1");
            // Rename current to .1 (overwrites previous .1)
            std::fs::rename(log_path, rotated)?;
        }
    }
    Ok(())
}

/// Get current process info (pid, ppid, uid)
#[cfg(unix)]
fn get_process_info() -> (u32, u32, u32) {
    use std::os::unix::process::parent_id;
    let pid = std::process::id();
    let ppid = parent_id();
    let uid = libc_free_getuid();
    (pid, ppid, uid)
}

#[cfg(not(unix))]
fn get_process_info() -> (u32, u32, u32) {
    (std::process::id(), 0, 0)
}

/// Get UID without depending on libc crate
#[cfg(unix)]
fn libc_free_getuid() -> u32 {
    // Read from /proc/self/status which has Uid line
    if let Ok(status) = std::fs::read_to_string("/proc/self/status") {
        for line in status.lines() {
            if let Some(rest) = line.strip_prefix("Uid:") {
                // Format: "Uid:\treal\teffective\tsaved\tfs"
                if let Some(uid_str) = rest.split_whitespace().next() {
                    if let Ok(uid) = uid_str.parse::<u32>() {
                        return uid;
                    }
                }
            }
        }
    }
    0
}

/// Get the executable path of the parent process (Linux only)
#[cfg(target_os = "linux")]
fn get_caller_exe(ppid: u32) -> Option<String> {
    let link = format!("/proc/{}/exe", ppid);
    std::fs::read_link(link)
        .ok()
        .map(|p| p.to_string_lossy().to_string())
}

#[cfg(not(target_os = "linux"))]
fn get_caller_exe(_ppid: u32) -> Option<String> {
    None
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_audit_entry_serializes_to_json() {
        let entry = AuditEntry::new(
            "git-guard",
            AuditAction::Allowed,
            vec!["status".to_string()],
            "/usr/bin/git",
            "abc123",
        );

        let json = serde_json::to_string(&entry).unwrap();
        assert!(json.contains("\"wrapper\":\"git-guard\""));
        assert!(json.contains("\"action\":\"allowed\""));
        assert!(json.contains("\"source_hash\":\"abc123\""));
        // blocked_reason should be absent (skip_serializing_if)
        assert!(!json.contains("blocked_reason"));
    }

    #[test]
    fn test_audit_entry_blocked_serializes() {
        let entry = AuditEntry::new(
            "git-guard",
            AuditAction::Blocked,
            vec!["push".to_string(), "--force".to_string()],
            "/usr/bin/git",
            "abc123",
        )
        .with_blocked_reason("Force push blocked".to_string());

        let json = serde_json::to_string(&entry).unwrap();
        assert!(json.contains("\"action\":\"blocked\""));
        assert!(json.contains("\"blocked_reason\":\"Force push blocked\""));
    }

    #[test]
    fn test_log_event_to_tempdir() {
        let dir = tempfile::tempdir().unwrap();

        let entry = AuditEntry::new(
            "test-wrapper",
            AuditAction::Allowed,
            vec!["test-arg".to_string()],
            "/usr/bin/test",
            "hash123",
        );

        // Use try_log_event_to directly to avoid env var races with parallel tests
        try_log_event_to(&entry, dir.path()).unwrap();

        let log_path = dir.path().join(DEFAULT_LOG_FILE);
        assert!(log_path.exists());

        let content = std::fs::read_to_string(&log_path).unwrap();
        let parsed: serde_json::Value = serde_json::from_str(content.trim()).unwrap();
        assert_eq!(parsed["wrapper"], "test-wrapper");
        assert_eq!(parsed["action"], "allowed");
    }

    #[test]
    fn test_rotation() {
        let dir = tempfile::tempdir().unwrap();
        let log_path = dir.path().join("test.log");

        // Write a small file
        std::fs::write(&log_path, "small content").unwrap();
        rotate_if_needed(&log_path).unwrap();
        // Should NOT rotate (under threshold)
        assert!(log_path.exists());
        assert!(!log_path.with_extension("log.1").exists());
    }

    #[test]
    fn test_resolve_log_dir_with_env() {
        std::env::set_var(LOG_DIR_ENV, "/custom/log/dir");
        let dir = resolve_log_dir();
        assert_eq!(dir, PathBuf::from("/custom/log/dir"));
        std::env::remove_var(LOG_DIR_ENV);
    }

    #[cfg(unix)]
    #[test]
    fn test_process_info() {
        let (pid, ppid, uid) = get_process_info();
        assert!(pid > 0);
        assert!(ppid > 0);
        // uid could be 0 if running as root, but should be populated
        let _ = uid; // Just verify it doesn't panic
    }
}
