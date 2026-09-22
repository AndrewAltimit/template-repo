//! Git operations for applying and committing review fixes.

use anyhow::{Context, Result, bail};
use tracing::{debug, info, warn};

use crate::command::Runner;
use crate::patch::PreparedChange;

/// How a patch ended up being applied.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ApplyMethod {
    /// Plain `git apply`.
    GitApply,
    /// `git apply --ignore-whitespace` (e.g. CRLF files or re-indented context).
    GitApplyIgnoreWhitespace,
    /// `patch -p1` fallback.
    Patch,
}

/// `git apply` argument sets tried in order.
const GIT_APPLY_STRATEGIES: [(&[&str], ApplyMethod); 2] = [
    (&[], ApplyMethod::GitApply),
    (
        &["--ignore-whitespace"],
        ApplyMethod::GitApplyIgnoreWhitespace,
    ),
];

/// Git operations wrapper. In dry-run mode, mutating commands are logged
/// instead of executed; read-only checks still run.
pub struct GitOperations {
    runner: Runner,
    dry_run: bool,
}

impl GitOperations {
    /// Create a git wrapper that runs in the process working directory.
    pub fn new(dry_run: bool) -> Self {
        Self::with_runner(Runner::new(), dry_run)
    }

    /// Create a git wrapper around a specific runner.
    pub fn with_runner(runner: Runner, dry_run: bool) -> Self {
        Self { runner, dry_run }
    }

    fn git(&self, args: &[&str]) -> Result<String> {
        self.runner.run_ok("git", args, None)
    }

    /// Run a mutating git command (skipped in dry-run mode).
    fn git_mut(&self, args: &[&str]) -> Result<String> {
        if self.dry_run {
            info!("[DRY RUN] Would run: git {}", args.join(" "));
            return Ok(String::new());
        }
        self.git(args)
    }

    /// Create and check out a new branch at the current HEAD.
    pub fn create_branch(&self, name: &str) -> Result<()> {
        self.runner
            .run_ok("git", &["check-ref-format", "--branch", name], None)
            .with_context(|| format!("Invalid branch name {name:?}"))?;
        self.git_mut(&["checkout", "-b", name])?;
        Ok(())
    }

    /// Warn about changes whose `original_sha` does not match the working tree.
    ///
    /// The SHA may be abbreviated; comparison is by prefix. A mismatch is not
    /// fatal because `git apply` verifies context lines anyway.
    pub fn check_original_shas(&self, changes: &[PreparedChange]) {
        for change in changes {
            let Some(expected) = change.original_sha.as_deref() else {
                continue;
            };
            match self.git(&["hash-object", "--", &change.path]) {
                Ok(actual) => {
                    let actual = actual.trim();
                    let expected = expected.to_ascii_lowercase();
                    if expected.len() < 4 || !actual.starts_with(&expected) {
                        warn!(
                            path = %change.path,
                            expected = %expected,
                            actual = %actual,
                            "original_sha does not match the working tree; the review may be stale"
                        );
                    }
                },
                Err(e) => debug!(path = %change.path, error = %e, "Could not hash file"),
            }
        }
    }

    /// Apply a combined patch atomically.
    ///
    /// Tries `git apply`, then `git apply --ignore-whitespace`, then
    /// `patch -p1` (if installed). Each strategy is dry-run checked first, so a
    /// patch is either applied completely or not at all. In dry-run mode only
    /// the checks run.
    pub fn apply_patch(&self, patch: &str) -> Result<ApplyMethod> {
        let mut failures = Vec::new();

        for (opts, method) in GIT_APPLY_STRATEGIES {
            let mut check = vec!["apply", "--check"];
            check.extend_from_slice(opts);
            let output = self.runner.run("git", &check, Some(patch))?;
            if !output.success {
                debug!(?method, stderr = %output.stderr.trim(), "Patch check failed");
                failures.push(format!("git {}: {}", check.join(" "), output.stderr.trim()));
                continue;
            }
            if self.dry_run {
                info!(?method, "[DRY RUN] Patch applies cleanly; not applying");
                return Ok(method);
            }
            let mut apply = vec!["apply"];
            apply.extend_from_slice(opts);
            self.runner.run_ok("git", &apply, Some(patch))?;
            return Ok(method);
        }

        if self.runner.is_available("patch") {
            let check = ["-p1", "--forward", "--batch", "--dry-run"];
            let output = self.runner.run("patch", &check, Some(patch))?;
            if output.success {
                if self.dry_run {
                    info!("[DRY RUN] Patch applies with `patch -p1`; not applying");
                } else {
                    self.runner.run_ok("patch", &check[..3], Some(patch))?;
                }
                return Ok(ApplyMethod::Patch);
            }
            failures.push(format!("patch -p1: {}", output.stdout.trim()));
        } else {
            debug!("`patch` is not installed; skipping fallback");
        }

        bail!("Failed to apply review fixes:\n  {}", failures.join("\n  "))
    }

    /// Stage exactly `paths` (including deletions). Never stages unrelated files.
    pub fn stage(&self, paths: &[&str]) -> Result<()> {
        let mut args = vec!["add", "-A", "--"];
        args.extend_from_slice(paths);
        self.git_mut(&args)?;
        Ok(())
    }

    /// Whether the index differs from HEAD for any of `paths`.
    pub fn has_staged_changes(&self, paths: &[&str]) -> Result<bool> {
        if self.dry_run {
            return Ok(true);
        }
        let mut args = vec!["diff", "--cached", "--quiet", "--"];
        args.extend_from_slice(paths);
        let output = self.runner.run("git", &args, None)?;
        Ok(!output.success)
    }

    /// Commit `paths` only (other staged changes are left staged). Returns the
    /// new commit SHA, or `None` if nothing changed (or in dry-run mode).
    pub fn commit(&self, message: &str, paths: &[&str]) -> Result<Option<String>> {
        if !self.has_staged_changes(paths)? {
            info!("No changes to commit");
            return Ok(None);
        }
        let mut args = vec!["commit", "-m", message, "--"];
        args.extend_from_slice(paths);
        self.git_mut(&args)?;
        if self.dry_run {
            return Ok(None);
        }
        Ok(Some(self.git(&["rev-parse", "HEAD"])?.trim().to_string()))
    }

    /// Push the current HEAD to `origin/<branch>` and set upstream.
    pub fn push(&self, branch: &str) -> Result<()> {
        let refspec = format!("HEAD:refs/heads/{branch}");
        self.git_mut(&["push", "-u", "origin", &refspec])?;
        Ok(())
    }

    /// Name of the currently checked-out branch, or `None` when detached.
    pub fn current_branch(&self) -> Result<Option<String>> {
        let output =
            self.runner
                .run("git", &["symbolic-ref", "--quiet", "--short", "HEAD"], None)?;
        Ok(output
            .success
            .then(|| output.stdout.trim().to_string())
            .filter(|b| !b.is_empty()))
    }
}
