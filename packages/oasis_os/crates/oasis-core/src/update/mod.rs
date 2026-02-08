//! Update checker -- version comparison and update status.
//!
//! Reads the current version from `/etc/version` and the latest available
//! version from `/var/update/latest` in the VFS. Provides a terminal
//! command for checking update status.

use crate::error::{OasisError, Result};
use crate::terminal::{Command, CommandOutput, Environment};
use crate::vfs::Vfs;

/// VFS paths for version information.
pub const VERSION_PATH: &str = "/etc/version";
pub const UPDATE_LATEST_PATH: &str = "/var/update/latest";
pub const UPDATE_LOG_PATH: &str = "/var/update/log";

/// Parsed semantic version.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SemVer {
    pub major: u32,
    pub minor: u32,
    pub patch: u32,
}

impl SemVer {
    /// Parse a version string like "0.1.0" or "v0.1.0".
    pub fn parse(s: &str) -> Option<Self> {
        let s = s.trim().strip_prefix('v').unwrap_or(s.trim());
        let parts: Vec<&str> = s.split('.').collect();
        if parts.len() != 3 {
            return None;
        }
        Some(Self {
            major: parts[0].parse().ok()?,
            minor: parts[1].parse().ok()?,
            patch: parts[2].parse().ok()?,
        })
    }

    /// Whether `self` is older than `other`.
    pub fn is_older_than(&self, other: &Self) -> bool {
        (self.major, self.minor, self.patch) < (other.major, other.minor, other.patch)
    }
}

impl std::fmt::Display for SemVer {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}.{}.{}", self.major, self.minor, self.patch)
    }
}

/// Check for updates using VFS-stored version info.
pub fn check_update(vfs: &dyn Vfs) -> Result<UpdateStatus> {
    let current = read_version(vfs, VERSION_PATH)?;
    if !vfs.exists(UPDATE_LATEST_PATH) {
        return Ok(UpdateStatus::NoInfo { current });
    }
    let latest = read_version(vfs, UPDATE_LATEST_PATH)?;
    if current.is_older_than(&latest) {
        Ok(UpdateStatus::Available { current, latest })
    } else {
        Ok(UpdateStatus::UpToDate { current })
    }
}

/// Result of an update check.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum UpdateStatus {
    /// Current version matches or exceeds latest.
    UpToDate { current: SemVer },
    /// A newer version is available.
    Available { current: SemVer, latest: SemVer },
    /// No update information available.
    NoInfo { current: SemVer },
}

impl std::fmt::Display for UpdateStatus {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::UpToDate { current } => write!(f, "Up to date (v{current})"),
            Self::Available { current, latest } => {
                write!(f, "Update available: v{current} -> v{latest}")
            },
            Self::NoInfo { current } => {
                write!(f, "Current: v{current} (no update info available)")
            },
        }
    }
}

fn read_version(vfs: &dyn Vfs, path: &str) -> Result<SemVer> {
    let data = vfs.read(path)?;
    let text = String::from_utf8_lossy(&data);
    SemVer::parse(&text)
        .ok_or_else(|| OasisError::Config(format!("invalid version in {path}: {text}")))
}

// ---------------------------------------------------------------------------
// Terminal command
// ---------------------------------------------------------------------------

pub struct UpdateCmd;

impl Command for UpdateCmd {
    fn name(&self) -> &str {
        "update"
    }
    fn description(&self) -> &str {
        "Check for system updates"
    }
    fn usage(&self) -> &str {
        "update [check|status|log]"
    }
    fn execute(&self, args: &[&str], env: &mut Environment<'_>) -> Result<CommandOutput> {
        let subcmd = args.first().copied().unwrap_or("check");

        match subcmd {
            "check" | "status" => {
                let status = check_update(env.vfs)?;
                Ok(CommandOutput::Text(status.to_string()))
            },
            "log" => {
                if env.vfs.exists(UPDATE_LOG_PATH) {
                    let data = env.vfs.read(UPDATE_LOG_PATH)?;
                    let text = String::from_utf8_lossy(&data).into_owned();
                    if text.trim().is_empty() {
                        Ok(CommandOutput::Text("(no update log entries)".to_string()))
                    } else {
                        Ok(CommandOutput::Text(text))
                    }
                } else {
                    Ok(CommandOutput::Text("(no update log available)".to_string()))
                }
            },
            _ => Err(OasisError::Command(format!(
                "unknown subcommand: {subcmd}\nusage: {}",
                self.usage()
            ))),
        }
    }
}

/// Register update commands.
pub fn register_update_commands(reg: &mut crate::terminal::CommandRegistry) {
    reg.register(Box::new(UpdateCmd));
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::terminal::CommandRegistry;
    use crate::vfs::MemoryVfs;

    fn setup() -> (CommandRegistry, MemoryVfs) {
        let mut reg = CommandRegistry::new();
        register_update_commands(&mut reg);
        let mut vfs = MemoryVfs::new();
        vfs.mkdir("/etc").unwrap();
        vfs.mkdir("/var").unwrap();
        vfs.mkdir("/var/update").unwrap();
        vfs.write(VERSION_PATH, b"0.1.0").unwrap();
        (reg, vfs)
    }

    fn exec(reg: &CommandRegistry, vfs: &mut MemoryVfs, line: &str) -> Result<CommandOutput> {
        let mut env = Environment {
            cwd: "/".to_string(),
            vfs,
            power: None,
            time: None,
            usb: None,
        };
        reg.execute(line, &mut env)
    }

    #[test]
    fn semver_parse_valid() {
        let v = SemVer::parse("1.2.3").unwrap();
        assert_eq!(v.major, 1);
        assert_eq!(v.minor, 2);
        assert_eq!(v.patch, 3);
    }

    #[test]
    fn semver_parse_with_v_prefix() {
        let v = SemVer::parse("v0.1.0").unwrap();
        assert_eq!(v, SemVer::parse("0.1.0").unwrap());
    }

    #[test]
    fn semver_parse_invalid() {
        assert!(SemVer::parse("abc").is_none());
        assert!(SemVer::parse("1.2").is_none());
        assert!(SemVer::parse("").is_none());
    }

    #[test]
    fn semver_comparison() {
        let v1 = SemVer::parse("0.1.0").unwrap();
        let v2 = SemVer::parse("0.2.0").unwrap();
        assert!(v1.is_older_than(&v2));
        assert!(!v2.is_older_than(&v1));
        assert!(!v1.is_older_than(&v1));
    }

    #[test]
    fn semver_display() {
        let v = SemVer::parse("1.2.3").unwrap();
        assert_eq!(v.to_string(), "1.2.3");
    }

    #[test]
    fn check_no_update_info() {
        let (_, vfs) = setup();
        let status = check_update(&vfs).unwrap();
        assert!(matches!(status, UpdateStatus::NoInfo { .. }));
    }

    #[test]
    fn check_up_to_date() {
        let (_, mut vfs) = setup();
        vfs.write(UPDATE_LATEST_PATH, b"0.1.0").unwrap();
        let status = check_update(&vfs).unwrap();
        assert!(matches!(status, UpdateStatus::UpToDate { .. }));
    }

    #[test]
    fn check_update_available() {
        let (_, mut vfs) = setup();
        vfs.write(UPDATE_LATEST_PATH, b"0.2.0").unwrap();
        let status = check_update(&vfs).unwrap();
        match status {
            UpdateStatus::Available { current, latest } => {
                assert_eq!(current.to_string(), "0.1.0");
                assert_eq!(latest.to_string(), "0.2.0");
            },
            _ => panic!("expected Available"),
        }
    }

    #[test]
    fn update_cmd_check() {
        let (reg, mut vfs) = setup();
        match exec(&reg, &mut vfs, "update check").unwrap() {
            CommandOutput::Text(s) => assert!(s.contains("0.1.0")),
            _ => panic!("expected text"),
        }
    }

    #[test]
    fn update_cmd_log_missing() {
        let (reg, mut vfs) = setup();
        match exec(&reg, &mut vfs, "update log").unwrap() {
            CommandOutput::Text(s) => assert!(s.contains("no update log")),
            _ => panic!("expected text"),
        }
    }

    #[test]
    fn update_cmd_log_present() {
        let (reg, mut vfs) = setup();
        vfs.write(UPDATE_LOG_PATH, b"v0.1.0: initial release")
            .unwrap();
        match exec(&reg, &mut vfs, "update log").unwrap() {
            CommandOutput::Text(s) => assert!(s.contains("initial release")),
            _ => panic!("expected text"),
        }
    }

    #[test]
    fn update_cmd_unknown() {
        let (reg, mut vfs) = setup();
        assert!(exec(&reg, &mut vfs, "update badcmd").is_err());
    }

    #[test]
    fn update_status_display() {
        let s = UpdateStatus::Available {
            current: SemVer::parse("0.1.0").unwrap(),
            latest: SemVer::parse("0.2.0").unwrap(),
        };
        let text = s.to_string();
        assert!(text.contains("0.1.0"));
        assert!(text.contains("0.2.0"));
    }
}
