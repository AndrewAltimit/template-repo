//! Trusted configuration loading for PR-triggered workflow runs.
//!
//! Thin wrappers over [`trust_common::source`] (shared with automation-cli
//! and board-manager) that route diagnostics to `tracing`. In a
//! pull-request workflow, configuration that steers the agents
//! (`.agents.yaml` including the security allow-list, `review-profiles.yaml`,
//! `.mcp.json`) is read from the PR's base branch when the PR modifies it.

use std::path::Path;

use crate::error::Result;

/// Whether `path` may have been changed by the PR under review.
///
/// Returns `false` outside pull_request workflows. Inside one, an
/// inconclusive comparison is treated as modified (fail closed).
pub fn is_modified_in_pr(path: &str) -> bool {
    trust_common::source::is_modified_in_pr(path)
}

/// Read a configuration file, preferring the base-branch version when the
/// current PR modifies it. A file absent on the base branch is reported as
/// `NotFound` so callers fall back to their defaults.
pub fn read_trusted_file(path: &Path) -> Result<String> {
    Ok(trust_common::source::read_trusted_file(
        path,
        &mut |m: &str| tracing::warn!("{}", m),
    )?)
}

/// [`read_trusted_file`], then inline `@<relative path>` import lines (for
/// example `CLAUDE.md` containing only `@AGENTS.md`) one level deep,
/// confined to the importing file's directory.
pub fn read_trusted_file_with_imports(path: &Path) -> Result<String> {
    Ok(trust_common::source::read_trusted_file_with_imports(
        path,
        &mut |m: &str| tracing::warn!("{}", m),
    )?)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn reads_local_file_outside_pr_runs() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("cfg.yaml");
        std::fs::write(&path, "a: 1\n").unwrap();
        assert_eq!(read_trusted_file(&path).unwrap(), "a: 1\n");
        let missing = read_trusted_file(&dir.path().join("nope.yaml")).unwrap_err();
        assert!(
            matches!(missing, crate::error::Error::Io(ref e) if e.kind() == std::io::ErrorKind::NotFound)
        );
    }

    #[test]
    fn claude_md_import_is_inlined() {
        let dir = tempfile::tempdir().unwrap();
        std::fs::write(dir.path().join("AGENTS.md"), "# Agent rules\n").unwrap();
        std::fs::write(dir.path().join("CLAUDE.md"), "@AGENTS.md\n").unwrap();
        let out = read_trusted_file_with_imports(&dir.path().join("CLAUDE.md")).unwrap();
        assert_eq!(out, "# Agent rules\n");
    }
}
