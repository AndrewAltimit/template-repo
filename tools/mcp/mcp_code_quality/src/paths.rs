//! Path allowlist enforcement.
//!
//! Every path argument that reaches an external tool is resolved through
//! [`PathPolicy::resolve`], which:
//!
//! 1. rejects empty strings and strings containing NUL / control characters,
//! 2. resolves relative paths against an explicit base directory,
//! 3. requires the path to exist and canonicalizes it (resolving `..` and
//!    symlinks, so `/app/../etc` or a symlink pointing outside is caught),
//! 4. checks the canonical path is inside one of the canonical allowed roots.
//!
//! The *canonical absolute* path is what gets passed to subprocesses. Because
//! it always starts with `/` (or a drive prefix on Windows) it can never be
//! mistaken for a command-line option, which closes the argument-injection
//! hole of passing user strings like `--config=/etc/x` straight through.

use std::fmt;
use std::path::{Path, PathBuf};
use tracing::warn;

/// Why a path was rejected.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum PathError {
    /// Empty, NUL-containing, or otherwise malformed input.
    Invalid(String),
    /// The path does not exist (or cannot be accessed).
    NotFound(String),
    /// The path exists but lies outside every allowed root.
    NotAllowed(String),
    /// Exists, but is the wrong kind (file vs directory).
    WrongKind(String),
}

impl fmt::Display for PathError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Invalid(m) | Self::NotFound(m) | Self::NotAllowed(m) | Self::WrongKind(m) => {
                f.write_str(m)
            },
        }
    }
}

/// Canonicalize and strip the Windows verbatim prefix (`\\?\C:\...`) so the
/// result is usable as an argument to ordinary tools. A no-op on Unix.
pub fn canonicalize(path: &Path) -> std::io::Result<PathBuf> {
    let p = path.canonicalize()?;
    #[cfg(windows)]
    {
        let s = p.to_string_lossy();
        if let Some(rest) = s.strip_prefix(r"\\?\")
            && rest.as_bytes().get(1) == Some(&b':')
        {
            return Ok(PathBuf::from(rest.to_string()));
        }
    }
    Ok(p)
}

/// Allowlist of directory roots that tools may operate on.
#[derive(Debug, Clone)]
pub struct PathPolicy {
    /// Canonicalized roots that exist.
    roots: Vec<PathBuf>,
    /// Roots as configured (for error messages / status).
    configured: Vec<String>,
}

impl PathPolicy {
    /// Build a policy. Roots that do not exist are skipped with a warning
    /// (they could never match a canonical path anyway).
    pub fn new(configured: &[String]) -> Self {
        let mut roots = Vec::new();
        for root in configured {
            match canonicalize(Path::new(root)) {
                Ok(p) => roots.push(p),
                Err(e) => warn!(
                    "Allowed path '{}' is unusable and will be ignored: {}",
                    root, e
                ),
            }
        }
        if roots.is_empty() {
            warn!(
                "No usable allowed paths configured; every path-based tool call will be rejected"
            );
        }
        Self {
            roots,
            configured: configured.to_vec(),
        }
    }

    /// Roots exactly as configured.
    pub fn configured(&self) -> &[String] {
        &self.configured
    }

    /// Canonical roots that are actually enforced.
    pub fn effective_roots(&self) -> Vec<String> {
        self.roots.iter().map(|p| p.display().to_string()).collect()
    }

    /// Resolve `input` (relative to `base` when not absolute) to a canonical
    /// path inside the allowlist.
    pub fn resolve(&self, input: &str, base: Option<&Path>) -> Result<PathBuf, PathError> {
        validate_text(input, "path").map_err(PathError::Invalid)?;

        let raw = Path::new(input);
        let joined = match base {
            Some(b) if raw.is_relative() => b.join(raw),
            _ => raw.to_path_buf(),
        };

        let canonical = canonicalize(&joined).map_err(|e| {
            PathError::NotFound(format!(
                "Path does not exist or is not accessible: {input} ({e})"
            ))
        })?;

        if self.roots.iter().any(|root| canonical.starts_with(root)) {
            Ok(canonical)
        } else {
            Err(PathError::NotAllowed(format!(
                "Path not allowed: {input} (resolved to {}); allowed roots: {}",
                canonical.display(),
                self.configured.join(", ")
            )))
        }
    }

    /// Like [`resolve`](Self::resolve) but additionally requires a directory.
    pub fn resolve_dir(&self, input: &str, base: Option<&Path>) -> Result<PathBuf, PathError> {
        let p = self.resolve(input, base)?;
        if p.is_dir() {
            Ok(p)
        } else {
            Err(PathError::WrongKind(format!(
                "Expected a directory: {input}"
            )))
        }
    }

    /// Like [`resolve`](Self::resolve) but additionally requires a regular file.
    pub fn resolve_file(&self, input: &str, base: Option<&Path>) -> Result<PathBuf, PathError> {
        let p = self.resolve(input, base)?;
        if p.is_file() {
            Ok(p)
        } else {
            Err(PathError::WrongKind(format!("Expected a file: {input}")))
        }
    }
}

/// Reject empty strings, overlong strings, and control characters (NUL,
/// newlines, escapes). Used for paths and free-form tool arguments.
pub fn validate_text(value: &str, what: &str) -> Result<(), String> {
    const MAX_LEN: usize = 4096;
    if value.trim().is_empty() {
        return Err(format!("{what} must not be empty"));
    }
    if value.len() > MAX_LEN {
        return Err(format!(
            "{what} is too long ({} > {MAX_LEN} bytes)",
            value.len()
        ));
    }
    if value.chars().any(|c| c.is_control()) {
        return Err(format!("{what} must not contain control characters"));
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;

    fn tmp(name: &str) -> PathBuf {
        let dir = std::env::temp_dir().join(format!(
            "mcp-cq-paths-{}-{}-{}",
            name,
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        fs::create_dir_all(&dir).unwrap();
        dir
    }

    fn policy_for(root: &Path) -> PathPolicy {
        PathPolicy::new(&[root.display().to_string()])
    }

    #[test]
    fn accepts_paths_inside_root() {
        let root = tmp("inside");
        fs::create_dir_all(root.join("src")).unwrap();
        fs::write(root.join("src/a.py"), "x = 1\n").unwrap();
        let p = policy_for(&root);

        let resolved = p.resolve(&root.join("src/a.py").display().to_string(), None);
        assert!(resolved.is_ok(), "{resolved:?}");
        assert!(p.resolve_dir(&root.display().to_string(), None).is_ok());
        assert!(
            p.resolve_file(&root.join("src/a.py").display().to_string(), None)
                .is_ok()
        );
        fs::remove_dir_all(root).ok();
    }

    #[test]
    fn relative_paths_resolve_against_base() {
        let root = tmp("relative");
        fs::write(root.join("b.py"), "").unwrap();
        let p = policy_for(&root);
        assert!(p.resolve("b.py", Some(&root)).is_ok());
        assert!(matches!(
            p.resolve("missing.py", Some(&root)),
            Err(PathError::NotFound(_))
        ));
        fs::remove_dir_all(root).ok();
    }

    #[test]
    fn rejects_dotdot_escape() {
        let root = tmp("escape");
        let inner = root.join("inner");
        fs::create_dir_all(&inner).unwrap();
        let p = policy_for(&inner);
        // inner/.. == root, which is outside the allowlist
        let escaped = inner.join("..").display().to_string();
        assert!(matches!(
            p.resolve(&escaped, None),
            Err(PathError::NotAllowed(_))
        ));
        // Relative escape through base too
        assert!(matches!(
            p.resolve("..", Some(&inner)),
            Err(PathError::NotAllowed(_))
        ));
        fs::remove_dir_all(root).ok();
    }

    #[test]
    fn rejects_sibling_with_common_prefix() {
        // "/tmp/x-allowed" must not admit "/tmp/x-allowed-evil"
        let root = tmp("prefix");
        let allowed = root.join("proj");
        let evil = root.join("proj-evil");
        fs::create_dir_all(&allowed).unwrap();
        fs::create_dir_all(&evil).unwrap();
        let p = policy_for(&allowed);
        assert!(matches!(
            p.resolve(&evil.display().to_string(), None),
            Err(PathError::NotAllowed(_))
        ));
        fs::remove_dir_all(root).ok();
    }

    #[test]
    fn rejects_malformed_input() {
        let root = tmp("malformed");
        let p = policy_for(&root);
        assert!(matches!(p.resolve("", None), Err(PathError::Invalid(_))));
        assert!(matches!(p.resolve("   ", None), Err(PathError::Invalid(_))));
        assert!(matches!(
            p.resolve("a\0b", None),
            Err(PathError::Invalid(_))
        ));
        assert!(matches!(
            p.resolve("a\nb", None),
            Err(PathError::Invalid(_))
        ));
        // Option-looking names that do not exist are simply not found; they are
        // never passed through to a tool un-canonicalized.
        assert!(matches!(
            p.resolve("--config=/etc/passwd", Some(&root)),
            Err(PathError::NotFound(_))
        ));
        fs::remove_dir_all(root).ok();
    }

    #[test]
    fn wrong_kind_is_reported() {
        let root = tmp("kind");
        fs::write(root.join("f.txt"), "").unwrap();
        let p = policy_for(&root);
        let file = root.join("f.txt").display().to_string();
        assert!(matches!(
            p.resolve_dir(&file, None),
            Err(PathError::WrongKind(_))
        ));
        assert!(matches!(
            p.resolve_file(&root.display().to_string(), None),
            Err(PathError::WrongKind(_))
        ));
        fs::remove_dir_all(root).ok();
    }

    #[test]
    fn nonexistent_roots_are_ignored() {
        let p = PathPolicy::new(&["/definitely/not/a/real/root/xyz".to_string()]);
        assert!(p.effective_roots().is_empty());
        assert_eq!(p.configured().len(), 1);
        let here = std::env::current_dir().unwrap().display().to_string();
        assert!(matches!(
            p.resolve(&here, None),
            Err(PathError::NotAllowed(_))
        ));
    }

    #[cfg(unix)]
    #[test]
    fn rejects_symlink_escape() {
        let root = tmp("symlink");
        let allowed = root.join("allowed");
        let outside = root.join("outside");
        fs::create_dir_all(&allowed).unwrap();
        fs::create_dir_all(&outside).unwrap();
        std::os::unix::fs::symlink(&outside, allowed.join("link")).unwrap();
        let p = policy_for(&allowed);
        assert!(matches!(
            p.resolve(&allowed.join("link").display().to_string(), None),
            Err(PathError::NotAllowed(_))
        ));
        fs::remove_dir_all(root).ok();
    }

    #[test]
    fn validate_text_rules() {
        assert!(validate_text("not slow", "markers").is_ok());
        assert!(validate_text("", "markers").is_err());
        assert!(validate_text("a\tb", "markers").is_err());
        assert!(validate_text(&"x".repeat(5000), "markers").is_err());
    }
}
