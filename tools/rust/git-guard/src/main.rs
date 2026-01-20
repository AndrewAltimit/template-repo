//! git-guard: Git CLI wrapper that blocks dangerous operations
//!
//! This binary intercepts `git` commands and blocks dangerous operations
//! to prevent accidental or unauthorized destructive actions.
//!
//! # Usage
//!
//! Install this binary as `git` in a higher-priority PATH directory.
//! It will automatically find and call the real `git` binary.
//!
//! # Blocked Operations
//!
//! - Force push: `--force`, `-f`, `--force-with-lease`, `--force-if-includes`
//! - Skip hooks: `--no-verify`, `-n` (on commit/push)
//! - Push to protected branches: `main`, `master`
//!
//! # Why This Exists
//!
//! AI coding assistants (like Claude Code) may sometimes attempt force pushes,
//! skip verification hooks, or push directly to protected branches. This wrapper
//! blocks these operations entirely to ensure code review workflows are followed.
//!
//! # Emergency Bypass
//!
//! If you absolutely need to perform a blocked operation, use the real git binary:
//!   /usr/bin/git push --force origin main
//!
//! # Architecture
//!
//! The wrapper checks arguments before executing the real git binary.
//! If dangerous flags are detected, it exits with an error message.

use std::env;
use std::process::{exit, Command};

mod error;
mod git_finder;

use error::Error;

/// Force push flags that are blocked
const FORCE_PUSH_FLAGS: &[&str] = &["--force", "-f", "--force-with-lease", "--force-if-includes"];

/// No-verify flags that are blocked (short form -n only applies to specific commands)
const NO_VERIFY_FLAGS: &[&str] = &["--no-verify"];

/// Commands where -n means --no-verify
const COMMANDS_WITH_N_NO_VERIFY: &[&str] = &["commit", "merge", "cherry-pick", "revert"];

/// Subcommands where force flags apply
const PUSH_SUBCOMMANDS: &[&str] = &["push"];

/// Protected branches that cannot be pushed to directly
const PROTECTED_BRANCHES: &[&str] = &["main", "master"];

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

    // Check for push to protected branches
    if subcommand == Some("push") {
        if let Some(target_branch) = detect_push_target_branch(args) {
            if PROTECTED_BRANCHES.contains(&target_branch.as_str()) {
                dangerous.push(DangerousOp {
                    flag: format!("push to {}", target_branch),
                    description: "Direct push to protected branch bypasses PR review",
                });
            }
        }
    }

    dangerous
}

/// Detect the target branch for a git push command
/// Returns None if the target cannot be determined (might be using tracking branch)
fn detect_push_target_branch(args: &[String]) -> Option<String> {
    // Skip the "push" subcommand and find non-flag arguments
    let non_flag_args: Vec<&str> = args
        .iter()
        .skip_while(|a| *a != "push")
        .skip(1) // skip "push" itself
        .filter(|a| !a.starts_with('-'))
        .map(|s| s.as_str())
        .collect();

    // Common patterns:
    // git push origin main          -> remote=origin, branch=main
    // git push origin HEAD:main     -> remote=origin, refspec with target main
    // git push main                  -> could be remote or branch (ambiguous)
    // git push                       -> uses tracking branch (can't detect)

    if non_flag_args.is_empty() {
        return None; // Using tracking branch, can't detect target
    }

    // Check for refspec with colon (e.g., HEAD:main, feature:main)
    for arg in &non_flag_args {
        if let Some(colon_pos) = arg.find(':') {
            let target = &arg[colon_pos + 1..];
            // Handle refs/heads/main format
            let branch = target.strip_prefix("refs/heads/").unwrap_or(target);
            if !branch.is_empty() {
                return Some(branch.to_string());
            }
        }
    }

    // If we have 2+ args after push, second one is typically the branch
    // git push origin main -> ["origin", "main"]
    if non_flag_args.len() >= 2 {
        let potential_branch = non_flag_args[1];
        // Handle refs/heads/main format
        let branch = potential_branch
            .strip_prefix("refs/heads/")
            .unwrap_or(potential_branch);
        return Some(branch.to_string());
    }

    // Single arg could be remote or branch - we can't tell for sure
    // To be safe, don't block (could be `git push origin` which uses tracking)
    None
}

/// Format the error message for blocked operations
fn format_blocked_message(ops: &[DangerousOp]) -> String {
    let mut msg = String::new();
    msg.push('\n');
    msg.push_str("============================================================\n");
    msg.push_str("GIT-GUARD: OPERATION BLOCKED\n");
    msg.push_str("============================================================\n");
    msg.push('\n');
    msg.push_str("The following operation(s) are not allowed:\n");
    msg.push('\n');

    for op in ops {
        msg.push_str(&format!("  - {} : {}\n", op.flag, op.description));
    }

    msg.push('\n');
    msg.push_str("This safety mechanism prevents AI assistants from performing\n");
    msg.push_str("destructive git operations or bypassing code review.\n");
    msg.push('\n');
    msg.push_str("If you absolutely need to perform this operation, use the\n");
    msg.push_str("real git binary directly:\n");
    msg.push('\n');
    msg.push_str("  /usr/bin/git <your command>\n");
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

    if !dangerous_ops.is_empty() {
        // Always block dangerous operations
        eprintln!("{}", format_blocked_message(&dangerous_ops));
        exit(1);
    }

    // Safe operation - execute the real git
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
    fn test_safe_push_to_feature_branch() {
        let args = vec![
            "push".to_string(),
            "origin".to_string(),
            "feature-branch".to_string(),
        ];
        let ops = detect_dangerous_ops(&args);
        assert!(ops.is_empty());
    }

    #[test]
    fn test_push_to_main_blocked() {
        let args = vec!["push".to_string(), "origin".to_string(), "main".to_string()];
        let ops = detect_dangerous_ops(&args);
        assert_eq!(ops.len(), 1);
        assert!(ops[0].flag.contains("main"));
        assert!(ops[0].description.contains("protected branch"));
    }

    #[test]
    fn test_push_to_master_blocked() {
        let args = vec![
            "push".to_string(),
            "origin".to_string(),
            "master".to_string(),
        ];
        let ops = detect_dangerous_ops(&args);
        assert_eq!(ops.len(), 1);
        assert!(ops[0].flag.contains("master"));
    }

    #[test]
    fn test_push_refspec_to_main_blocked() {
        // git push origin HEAD:main
        let args = vec![
            "push".to_string(),
            "origin".to_string(),
            "HEAD:main".to_string(),
        ];
        let ops = detect_dangerous_ops(&args);
        assert_eq!(ops.len(), 1);
        assert!(ops[0].flag.contains("main"));
    }

    #[test]
    fn test_push_refspec_refs_heads_main_blocked() {
        // git push origin HEAD:refs/heads/main
        let args = vec![
            "push".to_string(),
            "origin".to_string(),
            "HEAD:refs/heads/main".to_string(),
        ];
        let ops = detect_dangerous_ops(&args);
        assert_eq!(ops.len(), 1);
        assert!(ops[0].flag.contains("main"));
    }

    #[test]
    fn test_push_without_branch_not_blocked() {
        // git push origin (uses tracking branch - can't determine target)
        let args = vec!["push".to_string(), "origin".to_string()];
        let ops = detect_dangerous_ops(&args);
        assert!(ops.is_empty());
    }

    #[test]
    fn test_push_with_upstream_flag_to_main_blocked() {
        // git push -u origin main
        let args = vec![
            "push".to_string(),
            "-u".to_string(),
            "origin".to_string(),
            "main".to_string(),
        ];
        let ops = detect_dangerous_ops(&args);
        assert_eq!(ops.len(), 1);
        assert!(ops[0].flag.contains("main"));
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
