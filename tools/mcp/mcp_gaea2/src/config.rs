//! Configuration and filesystem sandboxing for the Gaea2 MCP server.
//!
//! The server is reachable over the network (it normally runs on a dedicated
//! Windows machine), so every path supplied by a client is resolved through
//! [`Gaea2Config::resolve_path`], which confines it to the output directory
//! plus any explicitly allowed extra roots. Without this, `download_*` would
//! be an arbitrary file read and `run_*`/`repair_*` arbitrary file access.

use std::path::{Component, Path, PathBuf};

use uuid::Uuid;

/// Server configuration.
#[derive(Debug, Clone)]
pub struct Gaea2Config {
    /// Path to Gaea2 executable (Gaea.Swarm.exe), if it exists.
    pub gaea_path: Option<PathBuf>,
    /// Output directory for generated terrain files (canonicalized when possible).
    pub output_dir: PathBuf,
    /// Canonical roots that client-supplied paths may point into.
    allowed_roots: Vec<PathBuf>,
}

/// What a resolved path is expected to be.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PathKind {
    /// An existing regular file.
    ExistingFile,
    /// An existing directory.
    ExistingDir,
    /// A directory that may not exist yet (it will be created).
    NewDir,
}

impl Gaea2Config {
    /// Create a configuration, creating the output directory if needed.
    ///
    /// `extra_allowed_dirs` is an OS path list (`;`-separated on Windows,
    /// `:`-separated elsewhere) of additional directories clients may access.
    pub fn new(
        gaea_path: Option<String>,
        output_dir: String,
        extra_allowed_dirs: Option<String>,
    ) -> Self {
        let gaea_path = gaea_path
            .filter(|p| !p.trim().is_empty())
            .map(PathBuf::from)
            .and_then(|p| {
                if p.is_file() {
                    Some(p)
                } else {
                    tracing::warn!("Gaea2 executable not found at {}", p.display());
                    None
                }
            });

        let output_path = PathBuf::from(&output_dir);
        if let Err(e) = std::fs::create_dir_all(&output_path) {
            tracing::warn!(
                "Failed to create output directory {}: {e}",
                output_path.display()
            );
        }
        let output_dir = canonical_or_self(&output_path);

        let mut allowed_roots = vec![output_dir.clone()];
        if let Some(list) = extra_allowed_dirs {
            for dir in std::env::split_paths(&list) {
                if dir.as_os_str().is_empty() {
                    continue;
                }
                match std::fs::canonicalize(&dir) {
                    Ok(c) => allowed_roots.push(simplify(c)),
                    Err(e) => tracing::warn!("Ignoring allowed directory {}: {e}", dir.display()),
                }
            }
        }

        Self {
            gaea_path,
            output_dir,
            allowed_roots,
        }
    }

    /// Check if Gaea2 CLI is available.
    pub fn has_cli(&self) -> bool {
        self.gaea_path.is_some()
    }

    /// The directories client paths are confined to.
    pub fn allowed_roots(&self) -> &[PathBuf] {
        &self.allowed_roots
    }

    /// Generate a unique output path for a new project.
    ///
    /// The name is sanitized so it can never escape the output directory, and
    /// a timestamp plus random suffix prevents two calls from overwriting each
    /// other.
    pub fn generate_output_path(&self, project_name: &str) -> PathBuf {
        let timestamp = chrono::Utc::now().format("%Y%m%d_%H%M%S");
        let suffix = &Uuid::new_v4().simple().to_string()[..6];
        self.output_dir.join(format!(
            "{}_{timestamp}_{suffix}.terrain",
            sanitize_file_stem(project_name)
        ))
    }

    /// Resolve a client-supplied path and confine it to the allowed roots.
    ///
    /// Relative paths are interpreted relative to the output directory. `..`
    /// components are rejected outright; symlinks are resolved via
    /// canonicalization before the containment check.
    pub fn resolve_path(&self, input: &str, kind: PathKind) -> Result<PathBuf, String> {
        let trimmed = input.trim();
        if trimmed.is_empty() {
            return Err("path must not be empty".to_string());
        }
        if trimmed.contains('\0') {
            return Err("path must not contain NUL bytes".to_string());
        }
        let raw = Path::new(trimmed);
        if raw.components().any(|c| matches!(c, Component::ParentDir)) {
            return Err(format!("path '{trimmed}' must not contain '..'"));
        }
        let joined = if raw.is_absolute() {
            raw.to_path_buf()
        } else {
            self.output_dir.join(raw)
        };

        let resolved = match kind {
            PathKind::ExistingFile | PathKind::ExistingDir => {
                let c = std::fs::canonicalize(&joined)
                    .map_err(|_| format!("path not found: {trimmed}"))?;
                let c = simplify(c);
                if kind == PathKind::ExistingFile && !c.is_file() {
                    return Err(format!("not a file: {trimmed}"));
                }
                if kind == PathKind::ExistingDir && !c.is_dir() {
                    return Err(format!("not a directory: {trimmed}"));
                }
                c
            },
            PathKind::NewDir => resolve_nonexistent(&joined)?,
        };

        if self
            .allowed_roots
            .iter()
            .any(|root| resolved.starts_with(root))
        {
            Ok(resolved)
        } else {
            Err(format!(
                "path '{trimmed}' is outside the allowed directories ({}). Set GAEA2_ALLOWED_DIRS to permit more locations",
                self.allowed_roots
                    .iter()
                    .map(|p| p.display().to_string())
                    .collect::<Vec<_>>()
                    .join(", ")
            ))
        }
    }
}

/// Canonicalize the deepest existing ancestor and re-append the rest.
fn resolve_nonexistent(path: &Path) -> Result<PathBuf, String> {
    let mut existing = path.to_path_buf();
    let mut rest = Vec::new();
    while !existing.exists() {
        match (existing.file_name(), existing.parent()) {
            (Some(name), Some(parent)) => {
                rest.push(name.to_os_string());
                existing = parent.to_path_buf();
            },
            _ => return Err(format!("cannot resolve path {}", path.display())),
        }
    }
    let mut base = simplify(
        std::fs::canonicalize(&existing)
            .map_err(|e| format!("cannot resolve {}: {e}", existing.display()))?,
    );
    for part in rest.into_iter().rev() {
        base.push(part);
    }
    Ok(base)
}

fn canonical_or_self(p: &Path) -> PathBuf {
    std::fs::canonicalize(p)
        .map(simplify)
        .unwrap_or_else(|_| p.to_path_buf())
}

/// Strip the Windows verbatim prefix (`\\?\C:\...`) from canonical paths so
/// they stay readable and are accepted by tools that do not understand it.
/// UNC verbatim paths are left alone.
pub fn simplify(p: PathBuf) -> PathBuf {
    let s = p.to_string_lossy();
    if let Some(rest) = s.strip_prefix(r"\\?\") {
        let bytes = rest.as_bytes();
        if bytes.len() >= 2 && bytes[1] == b':' && bytes[0].is_ascii_alphabetic() {
            return PathBuf::from(rest);
        }
    }
    p
}

/// Make a project name safe to use as a file stem.
pub fn sanitize_file_stem(name: &str) -> String {
    let cleaned: String = name
        .trim()
        .chars()
        .map(|c| {
            if c.is_ascii_alphanumeric() || c == '-' || c == '_' {
                c
            } else {
                '_'
            }
        })
        .take(80)
        .collect();
    let cleaned = cleaned.trim_matches('_').to_string();
    if cleaned.is_empty() {
        "project".to_string()
    } else {
        cleaned
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn cfg(dir: &Path) -> Gaea2Config {
        Gaea2Config::new(None, dir.to_string_lossy().to_string(), None)
    }

    #[test]
    fn sanitizes_names() {
        assert_eq!(sanitize_file_stem("my terrain"), "my_terrain");
        assert_eq!(sanitize_file_stem("../../etc/passwd"), "etc_passwd");
        assert_eq!(sanitize_file_stem("..\\..\\x"), "x");
        assert_eq!(sanitize_file_stem("///"), "project");
        assert_eq!(sanitize_file_stem(&"a".repeat(500)).len(), 80);
    }

    #[test]
    fn output_paths_are_unique_and_contained() {
        let dir = tempfile::tempdir().unwrap();
        let c = cfg(dir.path());
        let a = c.generate_output_path("../evil");
        let b = c.generate_output_path("../evil");
        assert_ne!(a, b);
        assert!(a.starts_with(&c.output_dir));
        assert!(a.to_string_lossy().ends_with(".terrain"));
    }

    #[test]
    fn resolves_inside_and_rejects_outside() {
        let root = tempfile::tempdir().unwrap();
        let out = root.path().join("out");
        std::fs::create_dir_all(&out).unwrap();
        let c = cfg(&out);
        std::fs::write(out.join("a.terrain"), "{}").unwrap();
        std::fs::write(root.path().join("secret.txt"), "x").unwrap();

        // Relative and absolute inside
        assert!(c.resolve_path("a.terrain", PathKind::ExistingFile).is_ok());
        let abs = out.join("a.terrain");
        assert!(c
            .resolve_path(&abs.to_string_lossy(), PathKind::ExistingFile)
            .is_ok());

        // Traversal and outside paths
        assert!(c
            .resolve_path("../secret.txt", PathKind::ExistingFile)
            .is_err());
        let outside = root.path().join("secret.txt");
        let err = c
            .resolve_path(&outside.to_string_lossy(), PathKind::ExistingFile)
            .unwrap_err();
        assert!(err.contains("outside"), "{err}");

        // Missing files and wrong kinds
        assert!(c
            .resolve_path("nope.terrain", PathKind::ExistingFile)
            .is_err());
        assert!(c.resolve_path("a.terrain", PathKind::ExistingDir).is_err());
        assert!(c.resolve_path("", PathKind::ExistingFile).is_err());

        // New directories inside are fine, outside are not
        assert!(c.resolve_path("builds/x", PathKind::NewDir).is_ok());
        let outside_new = root.path().join("elsewhere");
        assert!(c
            .resolve_path(&outside_new.to_string_lossy(), PathKind::NewDir)
            .is_err());
    }

    #[test]
    fn extra_allowed_dirs() {
        let root = tempfile::tempdir().unwrap();
        let out = root.path().join("out");
        let extra = root.path().join("extra");
        std::fs::create_dir_all(&extra).unwrap();
        std::fs::write(extra.join("b.terrain"), "{}").unwrap();
        let c = Gaea2Config::new(
            None,
            out.to_string_lossy().to_string(),
            Some(extra.to_string_lossy().to_string()),
        );
        assert_eq!(c.allowed_roots().len(), 2);
        let p = extra.join("b.terrain");
        assert!(c
            .resolve_path(&p.to_string_lossy(), PathKind::ExistingFile)
            .is_ok());
    }

    #[test]
    fn missing_gaea_path_disables_cli() {
        let dir = tempfile::tempdir().unwrap();
        let c = Gaea2Config::new(
            Some(dir.path().join("nope.exe").to_string_lossy().to_string()),
            dir.path().to_string_lossy().to_string(),
            None,
        );
        assert!(!c.has_cli());
    }

    #[test]
    fn simplify_strips_verbatim_disk_prefix() {
        assert_eq!(
            simplify(PathBuf::from(r"\\?\C:\x\y")),
            PathBuf::from(r"C:\x\y")
        );
        assert_eq!(
            simplify(PathBuf::from(r"\\?\UNC\server\share")),
            PathBuf::from(r"\\?\UNC\server\share")
        );
    }
}
