//! Path policy: resolving user-supplied input paths safely, mapping server
//! paths back to host-relative paths, and generating unique output names.

use std::path::{Component, Path, PathBuf};
use std::sync::atomic::{AtomicU64, Ordering};
use std::time::{SystemTime, UNIX_EPOCH};

/// Decides which files tools may read and how output paths are reported.
///
/// Inputs may only come from the project root or the output directory (so a
/// PDF produced by `compile_latex` can be fed to `preview_pdf`). Paths are
/// canonicalized before the check, so `..` segments and symlinks cannot be
/// used to escape.
#[derive(Debug, Clone)]
pub struct PathPolicy {
    project_root: PathBuf,
    output_dir: PathBuf,
    project_root_canon: Option<PathBuf>,
    output_dir_canon: Option<PathBuf>,
    /// Project root as seen by the host (docker-compose sets `$PWD`); absolute
    /// host paths under it are translated to `project_root`.
    host_project_root: Option<PathBuf>,
    /// Host-relative location of `output_dir` (e.g. `outputs/mcp-content`).
    host_output_dir: String,
}

impl PathPolicy {
    /// Build a policy. `output_dir` should already exist so it can be
    /// canonicalized; if it does not, the raw path is used for comparisons.
    pub fn new(
        project_root: PathBuf,
        output_dir: PathBuf,
        host_project_root: Option<PathBuf>,
        host_output_dir: String,
    ) -> Self {
        Self {
            project_root_canon: project_root.canonicalize().ok(),
            output_dir_canon: output_dir.canonicalize().ok(),
            project_root,
            output_dir,
            host_project_root: host_project_root.filter(|p| !p.as_os_str().is_empty()),
            host_output_dir: host_output_dir.trim_end_matches(['/', '\\']).to_string(),
        }
    }

    /// Resolve a user-supplied path to an existing file inside an allowed root.
    ///
    /// Relative paths are resolved against the project root. Absolute paths are
    /// accepted if they (after host-root translation) resolve inside the
    /// project root or the output directory.
    pub fn resolve_input_file(&self, input: &str) -> Result<PathBuf, String> {
        let trimmed = input.trim();
        if trimmed.is_empty() {
            return Err("path must not be empty".to_string());
        }
        if trimmed.contains('\0') {
            return Err("path must not contain NUL bytes".to_string());
        }

        let candidate = self.translate(Path::new(trimmed));
        let canonical = candidate
            .canonicalize()
            .map_err(|_| format!("file not found: {}", input))?;

        if !self.is_allowed(&canonical) {
            return Err(format!(
                "access denied: '{}' resolves outside the project root and output directory",
                input
            ));
        }
        if !canonical.is_file() {
            return Err(format!("not a regular file: {}", input));
        }
        Ok(canonical)
    }

    /// Map a user path to a server path (host-root translation + relative
    /// resolution) without touching the filesystem.
    fn translate(&self, path: &Path) -> PathBuf {
        if path.is_absolute() || path.has_root() {
            if let Some(host_root) = &self.host_project_root
                && let Ok(rel) = path.strip_prefix(host_root)
            {
                return self.project_root.join(rel);
            }
            return path.to_path_buf();
        }
        self.project_root.join(path)
    }

    fn is_allowed(&self, canonical: &Path) -> bool {
        [&self.project_root_canon, &self.output_dir_canon]
            .into_iter()
            .flatten()
            .any(|root| canonical.starts_with(root))
    }

    /// Report a server path the way a user on the host would see it.
    ///
    /// Files under the output directory map to `host_output_dir/...`, files
    /// under the project root map to a project-relative path, and anything
    /// else is returned unchanged. Output always uses forward slashes.
    pub fn to_host_path(&self, path: &Path) -> String {
        let out_roots = [Some(&self.output_dir), self.output_dir_canon.as_ref()];
        for root in out_roots.into_iter().flatten() {
            if let Ok(rel) = path.strip_prefix(root) {
                let rel = slash_path(rel);
                return if rel.is_empty() {
                    self.host_output_dir.clone()
                } else if self.host_output_dir.is_empty() {
                    rel
                } else {
                    format!("{}/{}", self.host_output_dir, rel)
                };
            }
        }
        let project_roots = [Some(&self.project_root), self.project_root_canon.as_ref()];
        for root in project_roots.into_iter().flatten() {
            if let Ok(rel) = path.strip_prefix(root) {
                let rel = slash_path(rel);
                return if rel.is_empty() { ".".to_string() } else { rel };
            }
        }
        slash_path(path)
    }
}

/// Join a path's normal components with `/`, dropping Windows verbatim
/// prefixes. Absolute Unix paths keep their leading slash.
fn slash_path(path: &Path) -> String {
    let mut parts: Vec<String> = Vec::new();
    let mut absolute = false;
    for comp in path.components() {
        match comp {
            Component::RootDir => absolute = true,
            Component::Prefix(p) => parts.push(
                p.as_os_str()
                    .to_string_lossy()
                    .trim_start_matches(r"\\?\")
                    .to_string(),
            ),
            Component::CurDir => {},
            Component::ParentDir => parts.push("..".to_string()),
            Component::Normal(s) => parts.push(s.to_string_lossy().into_owned()),
        }
    }
    let joined = parts.join("/");
    if absolute && !path.components().any(|c| matches!(c, Component::Prefix(_))) {
        format!("/{}", joined)
    } else {
        joined
    }
}

static COUNTER: AtomicU64 = AtomicU64::new(0);

/// Produce a filename stem that is unique across concurrent calls in this
/// process and across processes: `{prefix}_{unix_millis}_{pid}_{seq}`.
pub fn unique_stem(prefix: &str) -> String {
    let millis = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_millis())
        .unwrap_or(0);
    let seq = COUNTER.fetch_add(1, Ordering::Relaxed);
    format!(
        "{}_{}_{}_{}",
        sanitize_stem(prefix),
        millis,
        std::process::id(),
        seq
    )
}

/// Reduce an arbitrary string to a safe filename stem (`[A-Za-z0-9_-]`, at
/// most 40 chars). Returns `"document"` if nothing usable remains.
pub fn sanitize_stem(raw: &str) -> String {
    let cleaned: String = raw
        .chars()
        .map(|c| {
            if c.is_ascii_alphanumeric() || c == '-' || c == '_' {
                c
            } else {
                '_'
            }
        })
        .take(40)
        .collect();
    let cleaned = cleaned.trim_matches('_').to_string();
    if cleaned.is_empty() {
        "document".to_string()
    } else {
        cleaned
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;

    fn policy_for(project: &Path, output: &Path) -> PathPolicy {
        PathPolicy::new(
            project.to_path_buf(),
            output.to_path_buf(),
            None,
            "outputs/mcp-content".to_string(),
        )
    }

    #[test]
    fn host_path_mapping_for_output_and_project() {
        let p = PathPolicy::new(
            PathBuf::from("/app"),
            PathBuf::from("/app/output"),
            None,
            "outputs/mcp-content".to_string(),
        );
        assert_eq!(
            p.to_host_path(Path::new("/app/output/latex/doc.pdf")),
            "outputs/mcp-content/latex/doc.pdf"
        );
        assert_eq!(p.to_host_path(Path::new("/app/file.tex")), "file.tex");
        // String-prefix lookalikes must not be mapped.
        assert_eq!(
            p.to_host_path(Path::new("/application/x.pdf")),
            "/application/x.pdf"
        );
    }

    #[test]
    fn host_path_mapping_for_separate_output_mount() {
        let p = PathPolicy::new(
            PathBuf::from("/app"),
            PathBuf::from("/output"),
            None,
            "outputs/mcp-content/".to_string(),
        );
        assert_eq!(
            p.to_host_path(Path::new("/output/test.pdf")),
            "outputs/mcp-content/test.pdf"
        );
    }

    #[test]
    fn resolves_relative_paths_inside_project() {
        let project = tempfile::tempdir().unwrap();
        let output = tempfile::tempdir().unwrap();
        fs::create_dir_all(project.path().join("docs")).unwrap();
        fs::write(project.path().join("docs/a.tex"), "x").unwrap();
        let p = policy_for(project.path(), output.path());

        let resolved = p.resolve_input_file("docs/a.tex").unwrap();
        assert!(resolved.ends_with("a.tex"));
        assert_eq!(p.to_host_path(&resolved), "docs/a.tex");
    }

    #[test]
    fn rejects_traversal_and_foreign_absolute_paths() {
        let base = tempfile::tempdir().unwrap();
        let project = base.path().join("project");
        let output = base.path().join("output");
        fs::create_dir_all(&project).unwrap();
        fs::create_dir_all(&output).unwrap();
        fs::write(base.path().join("secret.txt"), "s").unwrap();
        let p = policy_for(&project, &output);

        let err = p.resolve_input_file("../secret.txt").unwrap_err();
        assert!(err.contains("access denied"), "{err}");

        let abs = base.path().join("secret.txt");
        let err = p.resolve_input_file(abs.to_str().unwrap()).unwrap_err();
        assert!(err.contains("access denied"), "{err}");
    }

    #[test]
    fn allows_absolute_paths_in_output_dir() {
        let project = tempfile::tempdir().unwrap();
        let output = tempfile::tempdir().unwrap();
        let pdf = output.path().join("doc.pdf");
        fs::write(&pdf, "%PDF").unwrap();
        let p = policy_for(project.path(), output.path());
        assert!(p.resolve_input_file(pdf.to_str().unwrap()).is_ok());
    }

    #[test]
    fn translates_host_project_root() {
        let project = tempfile::tempdir().unwrap();
        let output = tempfile::tempdir().unwrap();
        fs::write(project.path().join("main.tex"), "x").unwrap();
        let host_root = PathBuf::from("/home/user/repo");
        let p = PathPolicy::new(
            project.path().to_path_buf(),
            output.path().to_path_buf(),
            Some(host_root.clone()),
            "out".to_string(),
        );
        let host_path = host_root.join("main.tex");
        assert!(p.resolve_input_file(host_path.to_str().unwrap()).is_ok());
    }

    #[test]
    fn rejects_missing_empty_and_directories() {
        let project = tempfile::tempdir().unwrap();
        let output = tempfile::tempdir().unwrap();
        fs::create_dir_all(project.path().join("sub")).unwrap();
        let p = policy_for(project.path(), output.path());
        assert!(p.resolve_input_file("").is_err());
        assert!(
            p.resolve_input_file("nope.tex")
                .unwrap_err()
                .contains("not found")
        );
        assert!(
            p.resolve_input_file("sub")
                .unwrap_err()
                .contains("not a regular file")
        );
    }

    #[test]
    fn unique_stems_differ() {
        let a = unique_stem("doc");
        let b = unique_stem("doc");
        assert_ne!(a, b);
        assert!(a.starts_with("doc_"));
    }

    #[test]
    fn sanitize_stem_strips_unsafe_characters() {
        assert_eq!(sanitize_stem("../../etc/passwd"), "etc_passwd");
        assert_eq!(sanitize_stem("my paper"), "my_paper");
        assert_eq!(sanitize_stem("///"), "document");
        assert_eq!(sanitize_stem(&"x".repeat(100)).len(), 40);
    }
}
