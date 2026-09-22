//! Screenshot output location handling.
//!
//! All screenshots are written inside a single output directory. A
//! caller-supplied `output_path` is resolved relative to that directory and
//! may not escape it (no `..`, no absolute paths elsewhere, no symlinked
//! parents), because the HTTP transport would otherwise let any client write
//! files anywhere the server user can.

use std::path::{Component, Path, PathBuf};

use chrono::{DateTime, Utc};

/// Environment variable overriding the output directory.
pub const OUTPUT_DIR_ENV: &str = "DESKTOP_CONTROL_OUTPUT_DIR";
/// Environment variable naming the host-side path of the output directory
/// (for containers with a bind mount); echoed back as `host_path`.
pub const HOST_PATH_ENV: &str = "DESKTOP_CONTROL_HOST_PATH";

/// Where screenshots go.
#[derive(Debug, Clone)]
pub struct OutputConfig {
    /// Directory screenshots are written to.
    pub dir: PathBuf,
    /// Host-side equivalent of `dir`, reported to clients when set.
    pub host_dir: Option<String>,
}

impl OutputConfig {
    /// Resolve from an explicit directory, `DESKTOP_CONTROL_OUTPUT_DIR`, or the
    /// platform data directory (`~/.local/share`, `%LOCALAPPDATA%`, ...).
    pub fn resolve(explicit: Option<PathBuf>) -> Self {
        let dir = explicit
            .or_else(|| {
                std::env::var_os(OUTPUT_DIR_ENV)
                    .filter(|v| !v.is_empty())
                    .map(PathBuf::from)
            })
            .unwrap_or_else(default_dir);
        let host_dir = std::env::var(HOST_PATH_ENV).ok().filter(|v| !v.is_empty());
        Self { dir, host_dir }
    }

    /// Host-side path for a file inside `dir`, if a host path is configured.
    pub fn host_path_for(&self, file: &Path) -> Option<String> {
        let host = self.host_dir.as_ref()?;
        let rel = file.strip_prefix(&self.dir).ok()?;
        let rel = rel.to_string_lossy().replace('\\', "/");
        Some(format!("{}/{}", host.trim_end_matches(['/', '\\']), rel))
    }
}

fn default_dir() -> PathBuf {
    dirs::data_local_dir()
        .or_else(dirs::home_dir)
        .unwrap_or_else(std::env::temp_dir)
        .join("mcp-desktop-control")
        .join("screenshots")
}

/// Default file name: `<prefix>_<UTC timestamp with milliseconds>.png`.
///
/// Millisecond precision avoids silently overwriting a screenshot taken
/// earlier in the same second.
pub fn default_file_name(prefix: &str, now: DateTime<Utc>) -> String {
    format!("{prefix}_{}.png", now.format("%Y%m%d_%H%M%S_%3f"))
}

/// Resolve the file to write, confined to `dir`.
///
/// * `None` -> `dir/<prefix>_<timestamp>.png`
/// * relative path -> `dir/<path>` (sub-directories allowed)
/// * absolute path -> accepted only if it lies inside `dir`
///
/// `..` components are rejected, a missing extension becomes `.png`, and any
/// other extension is an error (the data is always PNG).
pub fn resolve_output_path(
    dir: &Path,
    requested: Option<&str>,
    prefix: &str,
    now: DateTime<Utc>,
) -> Result<PathBuf, String> {
    let Some(requested) = requested.map(str::trim) else {
        return Ok(dir.join(default_file_name(prefix, now)));
    };
    if requested.is_empty() {
        return Ok(dir.join(default_file_name(prefix, now)));
    }
    if requested.contains('\0') {
        return Err("output_path contains a NUL byte".to_string());
    }

    let req = Path::new(requested);
    if req.components().any(|c| matches!(c, Component::ParentDir)) {
        return Err(format!(
            "output_path '{requested}' must not contain '..' components"
        ));
    }

    let candidate = if req.is_absolute() || req.has_root() {
        let dir_abs = absolutize(dir);
        let req_abs = absolutize(req);
        let rel = req_abs.strip_prefix(&dir_abs).map_err(|_| {
            format!(
                "output_path '{requested}' is outside the output directory '{}'; \
                 use a relative path instead",
                dir.display()
            )
        })?;
        dir.join(rel)
    } else {
        // Re-collecting the components normalizes separators (e.g. `a/b` on Windows).
        dir.join(req.iter().collect::<PathBuf>())
    };

    if candidate == dir || candidate.file_name().is_none() {
        return Err("output_path must name a file".to_string());
    }

    match candidate.extension().and_then(|e| e.to_str()) {
        None => Ok(candidate.with_extension("png")),
        Some(ext) if ext.eq_ignore_ascii_case("png") => Ok(candidate),
        Some(ext) => Err(format!(
            "output_path has extension '.{ext}', but screenshots are always PNG; use '.png'"
        )),
    }
}

/// Make a path absolute without touching the filesystem.
fn absolutize(p: &Path) -> PathBuf {
    if p.is_absolute() {
        p.to_path_buf()
    } else {
        std::env::current_dir()
            .map(|cwd| cwd.join(p))
            .unwrap_or_else(|_| p.to_path_buf())
    }
}

/// Write `data` to `path` (which must come from [`resolve_output_path`]),
/// creating parent directories and re-checking confinement after symlink
/// resolution so a symlinked sub-directory cannot redirect the write.
pub fn write_confined(dir: &Path, path: &Path, data: &[u8]) -> Result<(), String> {
    let parent = path
        .parent()
        .ok_or_else(|| format!("Invalid output path '{}'", path.display()))?;
    std::fs::create_dir_all(parent)
        .map_err(|e| format!("Failed to create '{}': {e}", parent.display()))?;
    let real_dir = dir.canonicalize().map_err(|e| {
        format!(
            "Failed to resolve output directory '{}': {e}",
            dir.display()
        )
    })?;
    let real_parent = parent
        .canonicalize()
        .map_err(|e| format!("Failed to resolve '{}': {e}", parent.display()))?;
    if !real_parent.starts_with(&real_dir) {
        return Err(format!(
            "Refusing to write '{}': it resolves outside the output directory",
            path.display()
        ));
    }
    if std::fs::symlink_metadata(path).is_ok_and(|m| m.file_type().is_symlink()) {
        return Err(format!(
            "Refusing to overwrite symlink '{}'",
            path.display()
        ));
    }
    std::fs::write(path, data).map_err(|e| format!("Failed to write '{}': {e}", path.display()))
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::TimeZone;

    fn now() -> DateTime<Utc> {
        Utc.with_ymd_and_hms(2026, 1, 2, 3, 4, 5).unwrap() + chrono::Duration::milliseconds(678)
    }

    #[test]
    fn default_name_has_millisecond_timestamp() {
        assert_eq!(
            default_file_name("screen", now()),
            "screen_20260102_030405_678.png"
        );
    }

    #[test]
    fn none_or_empty_uses_default_name() {
        let dir = Path::new("out");
        assert_eq!(
            resolve_output_path(dir, None, "region", now()).unwrap(),
            dir.join("region_20260102_030405_678.png")
        );
        assert_eq!(
            resolve_output_path(dir, Some("  "), "region", now()).unwrap(),
            dir.join("region_20260102_030405_678.png")
        );
    }

    #[test]
    fn relative_paths_are_joined_and_get_png_extension() {
        let dir = Path::new("out");
        assert_eq!(
            resolve_output_path(dir, Some("shot"), "x", now()).unwrap(),
            dir.join("shot.png")
        );
        assert_eq!(
            resolve_output_path(dir, Some("sub/shot.PNG"), "x", now()).unwrap(),
            dir.join("sub/shot.PNG")
        );
    }

    #[test]
    fn traversal_and_wrong_extensions_are_rejected() {
        let dir = Path::new("out");
        for bad in ["../x.png", "a/../../x.png", "..", "x.jpg", "x\0.png"] {
            assert!(
                resolve_output_path(dir, Some(bad), "x", now()).is_err(),
                "{bad:?} should be rejected"
            );
        }
    }

    #[test]
    fn absolute_paths_must_be_inside_dir() {
        let tmp = tempfile::tempdir().unwrap();
        let dir = tmp.path();
        let inside = dir.join("a").join("b.png");
        assert_eq!(
            resolve_output_path(dir, Some(inside.to_str().unwrap()), "x", now()).unwrap(),
            inside
        );
        let outside = std::env::temp_dir().join("definitely-elsewhere.png");
        let err =
            resolve_output_path(dir, Some(outside.to_str().unwrap()), "x", now()).unwrap_err();
        assert!(err.contains("outside the output directory"), "{err}");
        // The directory itself is not a file.
        assert!(resolve_output_path(dir, Some(dir.to_str().unwrap()), "x", now()).is_err());
    }

    #[test]
    fn write_confined_creates_parents_and_writes() {
        let tmp = tempfile::tempdir().unwrap();
        let dir = tmp.path().join("shots");
        let path = resolve_output_path(&dir, Some("nested/one.png"), "x", now()).unwrap();
        write_confined(&dir, &path, b"data").unwrap();
        assert_eq!(std::fs::read(&path).unwrap(), b"data");
    }

    #[cfg(unix)]
    #[test]
    fn write_confined_rejects_symlinked_parent() {
        let tmp = tempfile::tempdir().unwrap();
        let dir = tmp.path().join("shots");
        let elsewhere = tmp.path().join("elsewhere");
        std::fs::create_dir_all(&dir).unwrap();
        std::fs::create_dir_all(&elsewhere).unwrap();
        std::os::unix::fs::symlink(&elsewhere, dir.join("link")).unwrap();
        let path = resolve_output_path(&dir, Some("link/x.png"), "x", now()).unwrap();
        let err = write_confined(&dir, &path, b"data").unwrap_err();
        assert!(err.contains("outside the output directory"), "{err}");
        assert!(!elsewhere.join("x.png").exists());
    }

    #[test]
    fn host_path_mapping() {
        let cfg = OutputConfig {
            dir: PathBuf::from("/output"),
            host_dir: Some("outputs/desktop-control/".to_string()),
        };
        assert_eq!(
            cfg.host_path_for(Path::new("/output/sub/a.png")).as_deref(),
            Some("outputs/desktop-control/sub/a.png")
        );
        assert_eq!(cfg.host_path_for(Path::new("/elsewhere/a.png")), None);
        let no_host = OutputConfig {
            dir: PathBuf::from("/output"),
            host_dir: None,
        };
        assert_eq!(no_host.host_path_for(Path::new("/output/a.png")), None);
    }
}
