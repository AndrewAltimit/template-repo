//! Trusted configuration reads for PR-triggered workflow runs.
//!
//! Workflows triggered by pull request events check out PR code, so every
//! file in the working tree is attacker-controllable for a malicious PR.
//! Configuration that steers the agents (`.agents.yaml` including the
//! security allow-list, `review-profiles.yaml`, `.mcp.json`) must not be
//! taken from the PR when the PR modifies it. In such runs, those files are
//! read from the PR's base branch instead.
//!
//! The base branch is taken from `GITHUB_BASE_REF` (set for `pull_request`
//! and `pull_request_target`) or, for other PR events such as
//! `pull_request_review`, from `pull_request.base.ref` in the event payload
//! at `GITHUB_EVENT_PATH`. Outside such runs every function here is a plain
//! filesystem read.

use std::io;
use std::path::{Path, PathBuf};
use std::process::Command;

/// Base branch of the pull request that triggered this run, if any.
pub fn base_ref() -> Option<String> {
    std::env::var("GITHUB_BASE_REF")
        .ok()
        .map(|b| b.trim().to_string())
        .filter(|b| !b.is_empty())
        .or_else(base_ref_from_event)
        .filter(|b| is_safe_ref(b))
}

/// `pull_request.base.ref` from the Actions event payload.
fn base_ref_from_event() -> Option<String> {
    let path = std::env::var("GITHUB_EVENT_PATH").ok()?;
    let content = std::fs::read_to_string(path).ok()?;
    base_ref_from_payload(&content)
}

fn base_ref_from_payload(json: &str) -> Option<String> {
    let value: serde_json::Value = serde_json::from_str(json).ok()?;
    value
        .pointer("/pull_request/base/ref")?
        .as_str()
        .map(str::to_string)
}

/// Reject refs that could be parsed as git options or ranges.
fn is_safe_ref(r: &str) -> bool {
    !r.is_empty()
        && !r.starts_with('-')
        && !r.contains("..")
        && r.chars()
            .all(|c| c.is_ascii_alphanumeric() || matches!(c, '/' | '-' | '_' | '.'))
}

/// Split `path` into the directory git runs in and the file name within it.
fn split(path: &Path) -> Option<(PathBuf, String)> {
    let name = path.file_name()?.to_str()?.to_string();
    let dir = match path.parent() {
        Some(p) if !p.as_os_str().is_empty() => p.to_path_buf(),
        _ => PathBuf::from("."),
    };
    Some((dir, name))
}

/// Compare `name` in `dir` between the PR base and `HEAD`.
///
/// `Some(true)` = modified, `Some(false)` = unchanged, `None` = unknown
/// (git could not compare, e.g. `dir` is not inside the repository).
fn modification_status(dir: &Path, name: &str, base: &str) -> Option<bool> {
    let range = format!("origin/{base}...HEAD");
    let status = Command::new("git")
        .arg("-C")
        .arg(dir)
        .args(["diff", "--quiet", &range, "--", name])
        .status()
        .ok()?;
    match status.code() {
        Some(0) => Some(false),
        Some(1) => Some(true),
        _ => None,
    }
}

/// Whether `path` may have been changed by the PR under review.
///
/// Returns `false` outside pull_request workflows. Inside one, an
/// inconclusive comparison is treated as modified (fail closed).
pub fn is_modified_in_pr(path: impl AsRef<Path>) -> bool {
    let Some(base) = base_ref() else {
        return false;
    };
    split(path.as_ref())
        .and_then(|(dir, name)| modification_status(&dir, &name, &base))
        .unwrap_or(true)
}

/// Read `name` in `dir` from the PR base branch. A file absent on the base
/// branch is reported as `NotFound` so callers fall back to their defaults.
fn read_from_base(
    dir: &Path,
    name: &str,
    base: &str,
    warn: &mut dyn FnMut(&str),
) -> io::Result<String> {
    // `./` makes the path relative to `dir` rather than the repository root.
    let spec = format!("origin/{base}:./{name}");
    let output = Command::new("git")
        .arg("-C")
        .arg(dir)
        .args(["show", &spec])
        .output()?;
    if !output.status.success() {
        warn(&format!(
            "{name} does not exist on base branch '{base}': {}",
            String::from_utf8_lossy(&output.stderr).trim()
        ));
        return Err(io::Error::new(
            io::ErrorKind::NotFound,
            format!("{name} not present on base branch"),
        ));
    }
    Ok(String::from_utf8_lossy(&output.stdout).into_owned())
}

/// Read a configuration file, preferring the base-branch version when the
/// current PR modifies it.
///
/// When the comparison is inconclusive (for example the file lives outside
/// the repository) the local file is used, with a warning, so tools keep
/// working on unusual clones. `warn` receives these diagnostics.
pub fn read_trusted_file(path: &Path, warn: &mut dyn FnMut(&str)) -> io::Result<String> {
    if let Some(base) = base_ref()
        && let Some((dir, name)) = split(path)
    {
        match modification_status(&dir, &name, &base) {
            Some(true) => {
                warn(&format!(
                    "{} is modified by this PR; using the version from base branch '{base}'",
                    path.display()
                ));
                return read_from_base(&dir, &name, &base, warn);
            },
            Some(false) => {},
            None => warn(&format!(
                "Could not compare {} against base branch '{base}'; using working tree copy",
                path.display()
            )),
        }
    }
    std::fs::read_to_string(path)
}

/// Parse a line consisting solely of `@<relative path>` (a Claude Code
/// import directive such as `@AGENTS.md`). Returns the path only when it is
/// relative and stays inside the importing directory: no absolute paths,
/// drive prefixes, `~`, or `..` components.
fn import_target(line: &str) -> Option<PathBuf> {
    let rel = line.trim().strip_prefix('@')?;
    if rel.is_empty() || rel.starts_with('~') || rel.chars().any(char::is_whitespace) {
        return None;
    }
    let path = Path::new(rel);
    let confined = path.components().all(|c| {
        matches!(
            c,
            std::path::Component::Normal(_) | std::path::Component::CurDir
        )
    });
    (confined && path.file_name().is_some()).then(|| path.to_path_buf())
}

/// Replace every `@<relative path>` import line in `content` with the
/// imported file's text (one level: imports inside imported files are left
/// as-is). `read` loads a path relative to the importing directory; a line
/// whose target is unsafe or unreadable is kept verbatim.
fn expand_imports(
    content: &str,
    read: &mut dyn FnMut(&Path) -> io::Result<String>,
    warn: &mut dyn FnMut(&str),
) -> String {
    let mut out = String::with_capacity(content.len());
    for line in content.split_inclusive('\n') {
        let Some(target) = import_target(line) else {
            out.push_str(line);
            continue;
        };
        match read(&target) {
            Ok(text) => {
                out.push_str(&text);
                if line.ends_with('\n') && !text.ends_with('\n') {
                    out.push('\n');
                }
            },
            Err(e) => {
                warn(&format!("cannot resolve import {}: {e}", line.trim()));
                out.push_str(line);
            },
        }
    }
    out
}

/// [`read_trusted_file`], then inline `@<relative path>` import lines (as
/// used by `CLAUDE.md`) one level deep.
///
/// Imports resolve relative to the importing file's directory and may not
/// leave it (lexically, and after resolving symlinks when the file exists
/// locally). Imported files are read through [`read_trusted_file`] too, so
/// a PR cannot redirect reviewer guidance through an import either.
pub fn read_trusted_file_with_imports(
    path: &Path,
    warn: &mut dyn FnMut(&str),
) -> io::Result<String> {
    let content = read_trusted_file(path, warn)?;
    let dir = match path.parent() {
        Some(p) if !p.as_os_str().is_empty() => p.to_path_buf(),
        _ => PathBuf::from("."),
    };
    let mut import_warnings: Vec<String> = Vec::new();
    let mut read = |rel: &Path| -> io::Result<String> {
        let full = dir.join(rel);
        if let (Ok(root), Ok(target)) = (dir.canonicalize(), full.canonicalize())
            && !target.starts_with(&root)
        {
            return Err(io::Error::new(
                io::ErrorKind::PermissionDenied,
                "import resolves outside the importing directory",
            ));
        }
        read_trusted_file(&full, &mut |m: &str| import_warnings.push(m.to_string()))
    };
    let expanded = expand_imports(&content, &mut read, warn);
    for m in &import_warnings {
        warn(m);
    }
    Ok(expanded)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn import_targets_are_confined() {
        assert_eq!(
            import_target("@AGENTS.md"),
            Some(PathBuf::from("AGENTS.md"))
        );
        assert_eq!(
            import_target("  @docs/agents/README.md \n"),
            Some(PathBuf::from("docs/agents/README.md"))
        );
        assert_eq!(import_target("@./x.md"), Some(PathBuf::from("./x.md")));
        for bad in [
            "@",
            "@/etc/passwd",
            "@../secret.md",
            "@docs/../../x",
            "@~/notes.md",
            "@a b.md",
            "email me @ home",
            "see @AGENTS.md for details",
            "AGENTS.md",
            "@.",
        ] {
            assert_eq!(import_target(bad), None, "{bad:?}");
        }
    }

    #[test]
    fn expand_imports_inlines_one_level() {
        let mut read = |p: &Path| -> io::Result<String> {
            match p.to_str() {
                Some("AGENTS.md") => Ok("# Agents\n@NESTED.md\n".to_string()),
                Some("NOEOL.md") => Ok("no newline".to_string()),
                _ => Err(io::Error::new(io::ErrorKind::NotFound, "missing")),
            }
        };
        let mut warnings = Vec::new();
        let out = expand_imports(
            "intro\n@AGENTS.md\n@NOEOL.md\n@MISSING.md\n@../up.md\n",
            &mut read,
            &mut |m: &str| warnings.push(m.to_string()),
        );
        assert_eq!(
            out,
            "intro\n# Agents\n@NESTED.md\nno newline\n@MISSING.md\n@../up.md\n"
        );
        assert_eq!(warnings.len(), 1, "{warnings:?}");
        assert!(warnings[0].contains("@MISSING.md"));
    }

    #[test]
    fn read_with_imports_from_disk() {
        let dir = tempfile::tempdir().unwrap();
        let root = dir.path().join("repo");
        std::fs::create_dir_all(root.join("docs")).unwrap();
        std::fs::write(dir.path().join("outside.md"), "SECRET\n").unwrap();
        std::fs::write(root.join("AGENTS.md"), "agent rules\n").unwrap();
        std::fs::write(root.join("docs/extra.md"), "extra\n").unwrap();
        std::fs::write(
            root.join("CLAUDE.md"),
            "@AGENTS.md\n@docs/extra.md\n@../outside.md\n",
        )
        .unwrap();
        let out =
            read_trusted_file_with_imports(&root.join("CLAUDE.md"), &mut |_: &str| {}).unwrap();
        assert_eq!(out, "agent rules\nextra\n@../outside.md\n");
        assert!(!out.contains("SECRET"));
    }

    #[cfg(unix)]
    #[test]
    fn read_with_imports_rejects_symlink_escape() {
        let dir = tempfile::tempdir().unwrap();
        let root = dir.path().join("repo");
        std::fs::create_dir_all(&root).unwrap();
        std::fs::write(dir.path().join("outside.md"), "SECRET\n").unwrap();
        std::os::unix::fs::symlink(dir.path().join("outside.md"), root.join("link.md")).unwrap();
        std::fs::write(root.join("CLAUDE.md"), "@link.md\n").unwrap();
        let mut warned = false;
        let out =
            read_trusted_file_with_imports(&root.join("CLAUDE.md"), &mut |_: &str| warned = true)
                .unwrap();
        assert_eq!(out, "@link.md\n");
        assert!(warned);
    }

    #[test]
    fn safe_refs() {
        assert!(is_safe_ref("main"));
        assert!(is_safe_ref("release/1.2"));
        assert!(!is_safe_ref(""));
        assert!(!is_safe_ref("--output=/tmp/x"));
        assert!(!is_safe_ref("main..evil"));
        assert!(!is_safe_ref("main;rm"));
    }

    #[test]
    fn base_ref_from_event_payload() {
        let payload = r#"{"action":"submitted","pull_request":{"base":{"ref":"main"}}}"#;
        assert_eq!(base_ref_from_payload(payload).as_deref(), Some("main"));
        assert_eq!(base_ref_from_payload(r#"{"schedule":"0 * * * *"}"#), None);
        assert_eq!(base_ref_from_payload("not json"), None);
    }

    #[test]
    fn split_paths() {
        assert_eq!(
            split(Path::new(".agents.yaml")),
            Some((PathBuf::from("."), ".agents.yaml".to_string()))
        );
        assert_eq!(
            split(Path::new("./a/b.yaml")),
            Some((PathBuf::from("./a"), "b.yaml".to_string()))
        );
        assert_eq!(
            split(Path::new("/repo/.mcp.json")),
            Some((PathBuf::from("/repo"), ".mcp.json".to_string()))
        );
        assert_eq!(split(Path::new("/")), None);
    }
}
