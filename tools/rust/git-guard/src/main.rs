//! git-guard: Git CLI wrapper that requires sudo for dangerous operations
//!
//! This binary intercepts `git` commands and blocks dangerous operations
//! unless running with elevated privileges (sudo/root).
//!
//! # Usage
//!
//! Install this binary as `git` in a higher-priority PATH directory.
//! It will automatically find and call the real `git` binary.
//!
//! # Blocked Operations (require sudo)
//!
//! - Force push: `--force`, `-f`, `--force-with-lease`, `--force-if-includes`
//! - Skip hooks: `--no-verify`, `-n` (on commit/push)
//!
//! # Why This Exists
//!
//! AI coding assistants (like Claude Code) may sometimes attempt force pushes
//! or skip verification hooks. This wrapper ensures a human must explicitly
//! approve such operations by running with sudo.
//!
//! # Architecture
//!
//! The wrapper checks arguments before executing the real git binary.
//! If dangerous flags are detected and not running as root, it exits
//! with an error message explaining the situation.

#[cfg(unix)]
extern crate libc;

use std::env;
use std::process::{exit, Command};

mod error;
mod git_finder;

use error::Error;

/// Force push flags that require sudo
const FORCE_PUSH_FLAGS: &[&str] = &["--force", "-f", "--force-with-lease", "--force-if-includes"];

/// No-verify flags that require sudo (short form -n only applies to specific commands)
const NO_VERIFY_FLAGS: &[&str] = &["--no-verify"];

/// Commands where -n means --no-verify
const COMMANDS_WITH_N_NO_VERIFY: &[&str] = &["commit", "merge", "cherry-pick", "revert"];

/// Subcommands where force flags apply
const PUSH_SUBCOMMANDS: &[&str] = &["push"];

/// Check if we're running as root/admin
fn is_elevated() -> bool {
    #[cfg(unix)]
    {
        // Check effective UID on Unix
        unsafe { libc::geteuid() == 0 }
    }

    #[cfg(windows)]
    {
        // On Windows, check if running as Administrator
        // This is a simplified check - in production you'd use Windows API
        env::var("USERNAME")
            .map(|u| u.to_lowercase() == "administrator")
            .unwrap_or(false)
            || env::var("SUDO_USER").is_ok()
    }
}

/// Dangerous operation detected
#[derive(Debug)]
struct DangerousOp {
    /// The flag that triggered this
    flag: String,
    /// Human-readable description
    description: &'static str,
}

/// Check if args contain dangerous flags that require sudo
fn detect_dangerous_ops(args: &[String]) -> Vec<DangerousOp> {
    let mut dangerous = Vec::new();

    // Find the git subcommand (first non-flag argument)
    let subcommand = args
        .iter()
        .find(|a| !a.starts_with('-'))
        .map(|s| s.as_str());

    // Check each argument
    for arg in args {
        // Check force push flags (only on push command)
        if subcommand.is_some_and(|cmd| PUSH_SUBCOMMANDS.contains(&cmd)) {
            for &force_flag in FORCE_PUSH_FLAGS {
                if arg == force_flag || arg.starts_with(&format!("{}=", force_flag)) {
                    dangerous.push(DangerousOp {
                        flag: arg.clone(),
                        description: "Force push can overwrite remote history",
                    });
                }
            }
        }

        // Check --no-verify flag
        for &nv_flag in NO_VERIFY_FLAGS {
            if arg == nv_flag {
                dangerous.push(DangerousOp {
                    flag: arg.clone(),
                    description: "Skipping hooks bypasses pre-commit/pre-push checks",
                });
            }
        }

        // Check -n flag (only means --no-verify on specific commands)
        if arg == "-n" {
            if let Some(cmd) = subcommand {
                if COMMANDS_WITH_N_NO_VERIFY.contains(&cmd) {
                    dangerous.push(DangerousOp {
                        flag: "-n (--no-verify)".to_string(),
                        description: "Skipping hooks bypasses pre-commit checks",
                    });
                }
            }
        }
    }

    dangerous
}

/// Format the error message for blocked operations
fn format_blocked_message(ops: &[DangerousOp]) -> String {
    let mut msg = String::new();
    msg.push('\n');
    msg.push_str("============================================================\n");
    msg.push_str("GIT-GUARD: DANGEROUS OPERATION BLOCKED\n");
    msg.push_str("============================================================\n");
    msg.push('\n');
    msg.push_str("The following dangerous operation(s) require elevated privileges:\n");
    msg.push('\n');

    for op in ops {
        msg.push_str(&format!("  - {} : {}\n", op.flag, op.description));
    }

    msg.push('\n');
    msg.push_str("To proceed, run the command with sudo:\n");
    msg.push('\n');
    msg.push_str("  sudo git <your command>\n");
    msg.push('\n');
    msg.push_str("This safety mechanism prevents AI assistants from performing\n");
    msg.push_str("destructive git operations without human approval.\n");
    msg.push('\n');
    msg.push_str("============================================================\n");

    msg
}

/// Run the git-guard logic
fn run() -> Result<(), Error> {
    let args: Vec<String> = env::args().skip(1).collect();

    // Find the real git binary
    let real_git = git_finder::find_real_git()?;

    // Check for dangerous operations
    let dangerous_ops = detect_dangerous_ops(&args);

    if !dangerous_ops.is_empty() && !is_elevated() {
        // Block the operation
        eprintln!("{}", format_blocked_message(&dangerous_ops));
        exit(1);
    }

    // Safe operation or running with sudo - execute the real git
    exec_git(&real_git, &args)?;

    unreachable!("exec should not return");
}

/// Execute the real git binary (replaces current process on Unix)
#[cfg(unix)]
fn exec_git(git_path: &std::path::Path, args: &[String]) -> Result<(), Error> {
    use std::os::unix::process::CommandExt;

    let err = Command::new(git_path).args(args).exec();

    // exec() only returns on error
    Err(Error::ExecFailed(err))
}

/// Execute the real git binary (Windows doesn't have exec, use spawn)
#[cfg(windows)]
fn exec_git(git_path: &std::path::Path, args: &[String]) -> Result<(), Error> {
    let status = Command::new(git_path)
        .args(args)
        .status()
        .map_err(Error::ExecFailed)?;

    exit(status.code().unwrap_or(1));
}

fn main() {
    if let Err(e) = run() {
        eprintln!("ERROR: {}", e);
        if let Some(help) = e.help_text() {
            eprintln!("\n{}", help);
        }
        exit(1);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_detect_force_push() {
        let args = vec!["push".to_string(), "--force".to_string()];
        let ops = detect_dangerous_ops(&args);
        assert_eq!(ops.len(), 1);
        assert_eq!(ops[0].flag, "--force");
    }

    #[test]
    fn test_detect_force_short() {
        let args = vec!["push".to_string(), "-f".to_string()];
        let ops = detect_dangerous_ops(&args);
        assert_eq!(ops.len(), 1);
        assert_eq!(ops[0].flag, "-f");
    }

    #[test]
    fn test_detect_force_with_lease() {
        let args = vec!["push".to_string(), "--force-with-lease".to_string()];
        let ops = detect_dangerous_ops(&args);
        assert_eq!(ops.len(), 1);
        assert_eq!(ops[0].flag, "--force-with-lease");
    }

    #[test]
    fn test_detect_no_verify() {
        let args = vec!["commit".to_string(), "--no-verify".to_string()];
        let ops = detect_dangerous_ops(&args);
        assert_eq!(ops.len(), 1);
        assert_eq!(ops[0].flag, "--no-verify");
    }

    #[test]
    fn test_detect_short_no_verify_commit() {
        let args = vec!["commit".to_string(), "-n".to_string()];
        let ops = detect_dangerous_ops(&args);
        assert_eq!(ops.len(), 1);
        assert!(ops[0].flag.contains("-n"));
    }

    #[test]
    fn test_short_n_not_detected_on_other_commands() {
        // -n on log means --max-count, not --no-verify
        let args = vec!["log".to_string(), "-n".to_string(), "5".to_string()];
        let ops = detect_dangerous_ops(&args);
        assert!(ops.is_empty());
    }

    #[test]
    fn test_safe_push() {
        let args = vec!["push".to_string(), "origin".to_string(), "main".to_string()];
        let ops = detect_dangerous_ops(&args);
        assert!(ops.is_empty());
    }

    #[test]
    fn test_safe_commit() {
        let args = vec![
            "commit".to_string(),
            "-m".to_string(),
            "message".to_string(),
        ];
        let ops = detect_dangerous_ops(&args);
        assert!(ops.is_empty());
    }

    #[test]
    fn test_force_not_detected_on_non_push() {
        // --force on checkout has a different meaning
        let args = vec!["checkout".to_string(), "--force".to_string()];
        let ops = detect_dangerous_ops(&args);
        assert!(ops.is_empty());
    }
}
