//! Structured (JSON Lines) audit logging for wrapper invocations.
//!
//! Every invocation produces one JSON object per line recording what was
//! requested, whether it was allowed or blocked, and who asked.
//!
//! Logging is best-effort: a failure is reported once on stderr and never
//! prevents the wrapper from enforcing policy or running the command.
//!
//! Arguments are passed through [`redact_arg`] before being written, so
//! credentials embedded in URLs or HTTP headers (`git clone
//! https://user:token@host/...`, `-c http.extraHeader=Authorization: ...`)
//! do not end up in the log. The file is created `0600` on Unix.

use std::borrow::Cow;
use std::fmt::Write as _;
use std::io::Write as _;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::{SystemTime, UNIX_EPOCH};

/// Default log directory, relative to the home directory.
const DEFAULT_LOG_SUBDIR: &str = ".local/share/wrapper-guard";
/// Log file name.
pub const LOG_FILE: &str = "audit.log";
/// Rotate (rename to `audit.log.1`) above this size.
const MAX_LOG_SIZE_BYTES: u64 = 10 * 1024 * 1024;
/// Environment variable overriding the log directory.
pub const LOG_DIR_ENV: &str = "WRAPPER_GUARD_LOG_DIR";

/// Action taken by the wrapper.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AuditAction {
    Allowed,
    Blocked,
    Error,
}

impl AuditAction {
    fn as_str(self) -> &'static str {
        match self {
            AuditAction::Allowed => "allowed",
            AuditAction::Blocked => "blocked",
            AuditAction::Error => "error",
        }
    }
}

/// A single audit log entry.
#[derive(Debug, Clone)]
pub struct AuditEntry {
    /// RFC 3339 UTC timestamp.
    pub timestamp: String,
    /// Wrapper that generated this entry ("git-guard" or "gh-validator").
    pub wrapper: String,
    /// Action taken.
    pub action: AuditAction,
    /// Arguments with credentials redacted.
    pub args_sanitized: Vec<String>,
    /// Reason for blocking / error detail.
    pub blocked_reason: Option<String>,
    /// PID of the wrapper process.
    pub caller_pid: u32,
    /// Parent PID (0 where unavailable).
    pub caller_ppid: u32,
    /// Executable of the parent process (Linux only).
    pub caller_exe: Option<String>,
    /// Real UID of the caller (0 on non-Unix).
    pub caller_uid: u32,
    /// Path of the real binary being invoked.
    pub real_binary_path: String,
    /// Compile-time source hash of the wrapper.
    pub source_hash: String,
}

impl AuditEntry {
    /// Create an entry with caller information filled in. Arguments are
    /// redacted with [`redact_arg`].
    pub fn new(
        wrapper: &str,
        action: AuditAction,
        args: &[String],
        real_binary_path: &str,
        source_hash: &str,
    ) -> Self {
        let pid = std::process::id();
        let ppid = parent_pid();
        Self {
            timestamp: rfc3339_now(),
            wrapper: wrapper.to_string(),
            action,
            args_sanitized: args.iter().map(|a| redact_arg(a).into_owned()).collect(),
            blocked_reason: None,
            caller_pid: pid,
            caller_ppid: ppid,
            caller_exe: caller_exe(ppid),
            caller_uid: crate::platform::uid(),
            real_binary_path: real_binary_path.to_string(),
            source_hash: source_hash.to_string(),
        }
    }

    /// Attach a reason (for blocked / error entries).
    pub fn with_reason(mut self, reason: impl Into<String>) -> Self {
        self.blocked_reason = Some(reason.into());
        self
    }

    /// Serialize as a single-line JSON object.
    pub fn to_json(&self) -> String {
        let mut out = String::with_capacity(256);
        out.push('{');
        json_field(&mut out, "timestamp", &self.timestamp);
        out.push(',');
        json_field(&mut out, "wrapper", &self.wrapper);
        out.push(',');
        json_field(&mut out, "action", self.action.as_str());
        out.push_str(",\"args_sanitized\":[");
        for (i, arg) in self.args_sanitized.iter().enumerate() {
            if i > 0 {
                out.push(',');
            }
            json_string(&mut out, arg);
        }
        out.push(']');
        if let Some(reason) = &self.blocked_reason {
            out.push(',');
            json_field(&mut out, "blocked_reason", reason);
        }
        let _ = write!(
            out,
            ",\"caller_pid\":{},\"caller_ppid\":{}",
            self.caller_pid, self.caller_ppid
        );
        if let Some(exe) = &self.caller_exe {
            out.push(',');
            json_field(&mut out, "caller_exe", exe);
        }
        let _ = write!(out, ",\"caller_uid\":{},", self.caller_uid);
        json_field(&mut out, "real_binary_path", &self.real_binary_path);
        out.push(',');
        json_field(&mut out, "source_hash", &self.source_hash);
        out.push('}');
        out
    }
}

/// Convenience logger bound to one wrapper invocation.
#[derive(Debug, Clone)]
pub struct Auditor {
    wrapper: &'static str,
    real_binary_path: String,
    source_hash: &'static str,
}

impl Auditor {
    pub fn new(wrapper: &'static str, real_binary: &Path, source_hash: &'static str) -> Self {
        Self {
            wrapper,
            real_binary_path: real_binary.to_string_lossy().into_owned(),
            source_hash,
        }
    }

    /// Log an allowed invocation.
    pub fn allowed(&self, args: &[String]) {
        self.log(AuditAction::Allowed, args, None);
    }

    /// Log a blocked invocation.
    pub fn blocked(&self, args: &[String], reason: &str) {
        self.log(AuditAction::Blocked, args, Some(reason));
    }

    /// Log an invocation that failed inside the wrapper.
    pub fn error(&self, args: &[String], detail: &str) {
        self.log(AuditAction::Error, args, Some(detail));
    }

    fn log(&self, action: AuditAction, args: &[String], reason: Option<&str>) {
        let mut entry = AuditEntry::new(
            self.wrapper,
            action,
            args,
            &self.real_binary_path,
            self.source_hash,
        );
        if let Some(reason) = reason {
            entry = entry.with_reason(reason);
        }
        log_event(&entry);
    }
}

/// Only warn about log failures once per process.
static AUDIT_WARNED: AtomicBool = AtomicBool::new(false);

/// Append an entry to the audit log (best-effort).
pub fn log_event(entry: &AuditEntry) {
    if let Err(e) = write_entry(entry, &resolve_log_dir())
        && !AUDIT_WARNED.swap(true, Ordering::Relaxed)
    {
        eprintln!("[wrapper-guard] Audit log warning: {e} (further warnings suppressed)");
    }
}

/// Append `entry` to `<log_dir>/audit.log`, rotating if needed.
pub fn write_entry(entry: &AuditEntry, log_dir: &Path) -> std::io::Result<()> {
    create_private_dir(log_dir)?;
    let log_path = log_dir.join(LOG_FILE);
    rotate_if_needed(&log_path)?;

    let mut line = entry.to_json();
    line.push('\n');
    // A single write() of the whole line keeps concurrent appends from
    // interleaving (O_APPEND writes are atomic for regular files).
    open_private_append(&log_path)?.write_all(line.as_bytes())
}

fn create_private_dir(dir: &Path) -> std::io::Result<()> {
    let mut builder = std::fs::DirBuilder::new();
    builder.recursive(true);
    #[cfg(unix)]
    {
        use std::os::unix::fs::DirBuilderExt;
        builder.mode(0o700);
    }
    builder.create(dir)
}

fn open_private_append(path: &Path) -> std::io::Result<std::fs::File> {
    let mut opts = std::fs::OpenOptions::new();
    opts.create(true).append(true);
    #[cfg(unix)]
    {
        use std::os::unix::fs::OpenOptionsExt;
        opts.mode(0o600);
    }
    opts.open(path)
}

/// Log directory: `$WRAPPER_GUARD_LOG_DIR`, else
/// `<home>/.local/share/wrapper-guard`, else a per-user temp directory.
pub fn resolve_log_dir() -> PathBuf {
    resolve_log_dir_from(|k| std::env::var_os(k))
}

fn resolve_log_dir_from(get: impl Fn(&str) -> Option<std::ffi::OsString>) -> PathBuf {
    if let Some(dir) = get(LOG_DIR_ENV).filter(|d| !d.is_empty()) {
        return PathBuf::from(dir);
    }
    let home = get("HOME")
        .filter(|h| !h.is_empty())
        .or_else(|| get("USERPROFILE").filter(|h| !h.is_empty()));
    if let Some(home) = home {
        return PathBuf::from(home).join(DEFAULT_LOG_SUBDIR);
    }
    std::env::temp_dir().join(format!("wrapper-guard-{}", crate::platform::uid()))
}

/// Rename `audit.log` to `audit.log.1` once it exceeds the size limit.
fn rotate_if_needed(log_path: &Path) -> std::io::Result<()> {
    if let Ok(meta) = std::fs::metadata(log_path)
        && meta.len() > MAX_LOG_SIZE_BYTES
    {
        let mut rotated = log_path.as_os_str().to_owned();
        rotated.push(".1");
        std::fs::rename(log_path, rotated)?;
    }
    Ok(())
}

/// Redact credentials from a single argument.
///
/// - `scheme://user:secret@host/...` becomes `scheme://***@host/...`
/// - anything after `authorization:` (case-insensitive, as used in
///   `http.extraHeader`) becomes `***`
pub fn redact_arg(arg: &str) -> Cow<'_, str> {
    let mut out = Cow::Borrowed(arg);

    if let Some(pos) = find_ascii_case_insensitive(&out, "authorization:") {
        let keep = pos + "authorization:".len();
        out = Cow::Owned(format!("{} ***", &out[..keep]));
    }

    // Redact userinfo in every URL in the argument.
    let mut result = String::new();
    let mut rest: &str = &out;
    let mut changed = false;
    while let Some(scheme_end) = rest.find("://") {
        let authority_start = scheme_end + 3;
        let authority_len = rest[authority_start..]
            .find(|c: char| c == '/' || c == '?' || c == '#' || c.is_whitespace())
            .unwrap_or(rest.len() - authority_start);
        let authority = &rest[authority_start..authority_start + authority_len];
        result.push_str(&rest[..authority_start]);
        if let Some(at) = authority.rfind('@') {
            result.push_str("***");
            result.push_str(&authority[at..]);
            changed = true;
        } else {
            result.push_str(authority);
        }
        rest = &rest[authority_start + authority_len..];
    }
    if changed {
        result.push_str(rest);
        return Cow::Owned(result);
    }
    out
}

fn find_ascii_case_insensitive(haystack: &str, needle: &str) -> Option<usize> {
    let h = haystack.as_bytes();
    let n = needle.as_bytes();
    if n.len() > h.len() {
        return None;
    }
    (0..=h.len() - n.len()).find(|&i| h[i..i + n.len()].eq_ignore_ascii_case(n))
}

fn json_field(out: &mut String, key: &str, value: &str) {
    json_string(out, key);
    out.push(':');
    json_string(out, value);
}

/// Append `s` as a JSON string literal.
fn json_string(out: &mut String, s: &str) {
    out.push('"');
    for c in s.chars() {
        match c {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            c if (c as u32) < 0x20 || c == '\u{7f}' || c == '\u{2028}' || c == '\u{2029}' => {
                let _ = write!(out, "\\u{:04x}", c as u32);
            },
            c => out.push(c),
        }
    }
    out.push('"');
}

/// Current UTC time as RFC 3339 with microseconds (`2026-01-02T03:04:05.123456Z`).
fn rfc3339_now() -> String {
    let now = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default();
    format_rfc3339(now.as_secs(), now.subsec_micros())
}

fn format_rfc3339(secs: u64, micros: u32) -> String {
    let days = secs / 86_400;
    let rem = secs % 86_400;
    let (y, m, d) = civil_from_days(days as i64);
    format!(
        "{y:04}-{m:02}-{d:02}T{:02}:{:02}:{:02}.{micros:06}Z",
        rem / 3600,
        (rem % 3600) / 60,
        rem % 60
    )
}

/// Days since 1970-01-01 to (year, month, day). Howard Hinnant's algorithm.
fn civil_from_days(z: i64) -> (i64, u32, u32) {
    let z = z + 719_468;
    let era = z.div_euclid(146_097);
    let doe = z.rem_euclid(146_097);
    let yoe = (doe - doe / 1460 + doe / 36_524 - doe / 146_096) / 365;
    let y = yoe + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = (doy - (153 * mp + 2) / 5 + 1) as u32;
    let m = if mp < 10 { mp + 3 } else { mp - 9 } as u32;
    (if m <= 2 { y + 1 } else { y }, m, d)
}

fn parent_pid() -> u32 {
    #[cfg(unix)]
    {
        std::os::unix::process::parent_id()
    }
    #[cfg(not(unix))]
    {
        0
    }
}

#[cfg(target_os = "linux")]
fn caller_exe(ppid: u32) -> Option<String> {
    std::fs::read_link(format!("/proc/{ppid}/exe"))
        .ok()
        .map(|p| p.to_string_lossy().into_owned())
}

#[cfg(not(target_os = "linux"))]
fn caller_exe(_ppid: u32) -> Option<String> {
    None
}

#[cfg(test)]
mod tests {
    use super::*;

    fn entry(action: AuditAction, args: &[&str]) -> AuditEntry {
        let args: Vec<String> = args.iter().map(|s| s.to_string()).collect();
        AuditEntry::new("git-guard", action, &args, "/usr/bin/git", "abc123")
    }

    #[test]
    fn allowed_entry_is_valid_json() {
        let json = entry(AuditAction::Allowed, &["status"]).to_json();
        let v: serde_json::Value = serde_json::from_str(&json).unwrap();
        assert_eq!(v["wrapper"], "git-guard");
        assert_eq!(v["action"], "allowed");
        assert_eq!(v["source_hash"], "abc123");
        assert_eq!(v["args_sanitized"][0], "status");
        assert!(v.get("blocked_reason").is_none());
    }

    #[test]
    fn blocked_entry_has_reason() {
        let json = entry(AuditAction::Blocked, &["push", "--force"])
            .with_reason("Force push blocked")
            .to_json();
        let v: serde_json::Value = serde_json::from_str(&json).unwrap();
        assert_eq!(v["action"], "blocked");
        assert_eq!(v["blocked_reason"], "Force push blocked");
    }

    #[test]
    fn json_escaping_round_trips() {
        let nasty = "quote\" back\\slash\nnew\tline \u{1} \u{7f} \u{2028} \u{1F600}";
        let json = entry(AuditAction::Allowed, &[nasty]).to_json();
        assert!(!json.contains('\n'));
        let v: serde_json::Value = serde_json::from_str(&json).unwrap();
        assert_eq!(v["args_sanitized"][0], nasty);
    }

    #[test]
    fn write_entry_appends_lines() {
        let dir = tempfile::tempdir().unwrap();
        let log_dir = dir.path().join("nested");
        write_entry(&entry(AuditAction::Allowed, &["a"]), &log_dir).unwrap();
        write_entry(&entry(AuditAction::Blocked, &["b"]), &log_dir).unwrap();
        let content = std::fs::read_to_string(log_dir.join(LOG_FILE)).unwrap();
        let lines: Vec<_> = content.lines().collect();
        assert_eq!(lines.len(), 2);
        for line in lines {
            serde_json::from_str::<serde_json::Value>(line).unwrap();
        }
    }

    #[cfg(unix)]
    #[test]
    fn log_file_is_private() {
        use std::os::unix::fs::PermissionsExt;
        let dir = tempfile::tempdir().unwrap();
        write_entry(&entry(AuditAction::Allowed, &["a"]), dir.path()).unwrap();
        let mode = std::fs::metadata(dir.path().join(LOG_FILE))
            .unwrap()
            .permissions()
            .mode();
        assert_eq!(mode & 0o077, 0);
    }

    #[test]
    fn rotation_threshold() {
        let dir = tempfile::tempdir().unwrap();
        let log_path = dir.path().join(LOG_FILE);
        std::fs::write(&log_path, "small").unwrap();
        rotate_if_needed(&log_path).unwrap();
        assert!(log_path.exists());

        let big = std::fs::File::create(&log_path).unwrap();
        big.set_len(MAX_LOG_SIZE_BYTES + 1).unwrap();
        drop(big);
        rotate_if_needed(&log_path).unwrap();
        assert!(!log_path.exists());
        assert!(dir.path().join("audit.log.1").exists());
    }

    #[test]
    fn log_dir_resolution() {
        let env = |pairs: &'static [(&'static str, &'static str)]| {
            move |k: &str| {
                pairs
                    .iter()
                    .find(|(key, _)| *key == k)
                    .map(|(_, v)| std::ffi::OsString::from(v))
            }
        };
        assert_eq!(
            resolve_log_dir_from(env(&[(LOG_DIR_ENV, "/custom"), ("HOME", "/h")])),
            PathBuf::from("/custom")
        );
        assert_eq!(
            resolve_log_dir_from(env(&[("HOME", "/h")])),
            PathBuf::from("/h").join(DEFAULT_LOG_SUBDIR)
        );
        assert_eq!(
            resolve_log_dir_from(env(&[(LOG_DIR_ENV, ""), ("USERPROFILE", "C:/u")])),
            PathBuf::from("C:/u").join(DEFAULT_LOG_SUBDIR)
        );
        assert!(
            resolve_log_dir_from(env(&[]))
                .to_string_lossy()
                .contains("wrapper-guard-")
        );
    }

    #[test]
    fn redacts_url_credentials() {
        assert_eq!(
            redact_arg("https://user:ghp_secret@github.com/o/r.git"),
            "https://***@github.com/o/r.git"
        );
        assert_eq!(
            redact_arg("https://x-access-token:tok@github.com"),
            "https://***@github.com"
        );
        assert_eq!(
            redact_arg("remote.origin.url=https://u:p@h/r https://a:b@c/d"),
            "remote.origin.url=https://***@h/r https://***@c/d"
        );
        // No credentials: borrowed and unchanged.
        assert!(matches!(
            redact_arg("https://github.com/o/r"),
            Cow::Borrowed(_)
        ));
        assert_eq!(
            redact_arg("git@github.com:o/r.git"),
            "git@github.com:o/r.git"
        );
    }

    #[test]
    fn redacts_authorization_headers() {
        assert_eq!(
            redact_arg("http.extraHeader=AUTHORIZATION: basic dG9rZW4="),
            "http.extraHeader=AUTHORIZATION: ***"
        );
    }

    #[test]
    fn timestamp_formatting() {
        assert_eq!(format_rfc3339(0, 0), "1970-01-01T00:00:00.000000Z");
        // 2024-02-29T12:34:56Z (leap day)
        assert_eq!(
            format_rfc3339(1_709_210_096, 42),
            "2024-02-29T12:34:56.000042Z"
        );
        assert_eq!(
            format_rfc3339(4_102_444_799, 0),
            "2099-12-31T23:59:59.000000Z"
        );
    }

    #[cfg(unix)]
    #[test]
    fn caller_info_is_populated() {
        let e = entry(AuditAction::Allowed, &[]);
        assert!(e.caller_pid > 0);
        assert!(e.caller_ppid > 0);
    }
}
