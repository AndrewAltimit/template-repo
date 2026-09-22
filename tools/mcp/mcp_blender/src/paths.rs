//! Confinement of user-supplied paths to the server's working directories.
//!
//! Every path a client sends (project names, model/HDRI/image/font assets,
//! export names) goes through [`resolve_under`], which guarantees the result
//! stays inside the given base directory: no absolute paths outside it, no
//! `..`, no hidden components, no backslashes or NUL bytes, and no escape via
//! symlinks that already exist on disk.

use std::path::{Component, Path, PathBuf};

/// Longest accepted user path, in bytes.
const MAX_PATH_LEN: usize = 512;
/// Longest accepted file name for projects and exports.
const MAX_NAME_LEN: usize = 128;

/// Why a user-supplied path was rejected.
#[derive(Debug, Clone, PartialEq, Eq, thiserror::Error)]
pub enum PathError {
    /// Empty string.
    #[error("empty path")]
    Empty,
    /// Longer than [`MAX_PATH_LEN`].
    #[error("path is too long (max {MAX_PATH_LEN} bytes)")]
    TooLong,
    /// Contains a NUL byte or backslash.
    #[error("path contains an invalid character (NUL or backslash): {0}")]
    InvalidCharacter(String),
    /// Absolute path outside the base directory.
    #[error("absolute paths are only allowed inside {base}: {path}")]
    OutsideBase {
        /// The rejected path.
        path: String,
        /// The directory it had to be inside.
        base: String,
    },
    /// Contains `..`.
    #[error("parent directory references ('..') are not allowed: {0}")]
    ParentReference(String),
    /// A component starts with a dot.
    #[error("hidden files/directories are not allowed: {0}")]
    Hidden(String),
    /// Resolves (through a symlink) outside the base directory.
    #[error("path resolves outside its allowed directory: {0}")]
    Escapes(String),
    /// Not a valid project/export file name.
    #[error(
        "invalid name '{0}': use 1-128 letters, digits, spaces, '.', '_' or '-', not starting with '.'"
    )]
    InvalidName(String),
}

/// Resolve `user_path` inside `base`.
///
/// Relative paths are joined onto `base`; absolute paths are accepted only if
/// they already point inside `base` (so clients may echo back the full paths
/// the server reported). The file does not need to exist.
pub fn resolve_under(base: &Path, user_path: &str) -> Result<PathBuf, PathError> {
    let trimmed = user_path.trim();
    if trimmed.is_empty() {
        return Err(PathError::Empty);
    }
    if trimmed.len() > MAX_PATH_LEN {
        return Err(PathError::TooLong);
    }
    // Backslashes are ordinary file-name bytes on Unix; reject them so a
    // Windows-style "..\\..\\x" can never be smuggled through as one component.
    if trimmed.contains('\0') || (cfg!(not(windows)) && trimmed.contains('\\')) {
        return Err(PathError::InvalidCharacter(trimmed.to_string()));
    }

    let path = Path::new(trimmed);
    let relative = if path.has_root() || path.is_absolute() {
        path.strip_prefix(base)
            .map_err(|_| PathError::OutsideBase {
                path: trimmed.to_string(),
                base: base.display().to_string(),
            })?
            .to_path_buf()
    } else {
        path.to_path_buf()
    };

    let mut clean = PathBuf::new();
    for component in relative.components() {
        match component {
            Component::Normal(part) => {
                if part.to_string_lossy().starts_with('.') {
                    return Err(PathError::Hidden(trimmed.to_string()));
                }
                clean.push(part);
            },
            Component::CurDir => {},
            Component::ParentDir => return Err(PathError::ParentReference(trimmed.to_string())),
            Component::RootDir | Component::Prefix(_) => {
                return Err(PathError::OutsideBase {
                    path: trimmed.to_string(),
                    base: base.display().to_string(),
                });
            },
        }
    }
    if clean.as_os_str().is_empty() {
        return Err(PathError::Empty);
    }

    let candidate = base.join(&clean);
    ensure_no_symlink_escape(base, &candidate, trimmed)?;
    Ok(candidate)
}

/// Reject candidates whose deepest existing ancestor canonicalizes outside
/// `base` (i.e. a symlink inside the base pointing elsewhere).
fn ensure_no_symlink_escape(
    base: &Path,
    candidate: &Path,
    original: &str,
) -> Result<(), PathError> {
    let Ok(canonical_base) = base.canonicalize() else {
        // Base does not exist yet: nothing inside it can be a symlink.
        return Ok(());
    };
    let mut probe = Some(candidate);
    while let Some(current) = probe {
        if let Ok(resolved) = current.canonicalize() {
            if resolved.starts_with(&canonical_base) {
                return Ok(());
            }
            return Err(PathError::Escapes(original.to_string()));
        }
        probe = current.parent();
    }
    Ok(())
}

/// Validate a bare file name (no directories) for projects and exports.
pub fn validate_file_name(name: &str) -> Result<&str, PathError> {
    let name = name.trim();
    let valid = !name.is_empty()
        && name.len() <= MAX_NAME_LEN
        && !name.starts_with('.')
        && name
            .chars()
            .all(|c| c.is_ascii_alphanumeric() || matches!(c, ' ' | '.' | '_' | '-'));
    if valid {
        Ok(name)
    } else {
        Err(PathError::InvalidName(name.to_string()))
    }
}

/// Append `.blend` unless the path already ends with it (case-insensitive).
pub fn with_blend_extension(path: &str) -> String {
    let trimmed = path.trim();
    if trimmed.to_ascii_lowercase().ends_with(".blend") {
        trimmed.to_string()
    } else {
        format!("{trimmed}.blend")
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::TempDir;

    fn base() -> TempDir {
        TempDir::new().unwrap()
    }

    #[test]
    fn relative_paths_are_joined() {
        let tmp = base();
        assert_eq!(
            resolve_under(tmp.path(), "scene.blend").unwrap(),
            tmp.path().join("scene.blend")
        );
        assert_eq!(
            resolve_under(tmp.path(), "sub/dir/model.fbx").unwrap(),
            tmp.path().join("sub/dir/model.fbx")
        );
        assert_eq!(
            resolve_under(tmp.path(), "./a.blend").unwrap(),
            tmp.path().join("a.blend")
        );
    }

    #[test]
    fn dotted_file_names_are_fine() {
        let tmp = base();
        assert!(resolve_under(tmp.path(), "my.project.blend").is_ok());
        assert!(resolve_under(tmp.path(), "archive.tar.gz").is_ok());
        assert!(resolve_under(tmp.path(), "v1..2.blend").is_ok());
    }

    #[test]
    fn empty_and_oversized_paths_are_rejected() {
        let tmp = base();
        assert_eq!(resolve_under(tmp.path(), ""), Err(PathError::Empty));
        assert_eq!(resolve_under(tmp.path(), "   "), Err(PathError::Empty));
        assert_eq!(resolve_under(tmp.path(), "."), Err(PathError::Empty));
        assert_eq!(resolve_under(tmp.path(), "./"), Err(PathError::Empty));
        assert_eq!(
            resolve_under(tmp.path(), &"a".repeat(600)),
            Err(PathError::TooLong)
        );
    }

    #[test]
    fn traversal_attempts_are_rejected() {
        let tmp = base();
        for attack in [
            "../secret",
            "a/../../etc/passwd",
            "sub/..",
            "..",
            "....//....//etc/passwd",
            "..\\..\\windows",
            "a\0b",
        ] {
            assert!(
                resolve_under(tmp.path(), attack).is_err(),
                "{attack:?} should be rejected"
            );
        }
    }

    #[test]
    fn hidden_components_are_rejected() {
        let tmp = base();
        for hidden in [".env", ".git/config", "sub/.secret", ".hidden/file.txt"] {
            assert!(matches!(
                resolve_under(tmp.path(), hidden),
                Err(PathError::Hidden(_))
            ));
        }
    }

    #[test]
    fn absolute_paths_must_be_inside_base() {
        let tmp = base();
        let inside = tmp.path().join("x.blend");
        assert_eq!(
            resolve_under(tmp.path(), &inside.to_string_lossy()).unwrap(),
            inside
        );
        assert!(matches!(
            resolve_under(tmp.path(), "/etc/passwd"),
            Err(PathError::OutsideBase { .. })
        ));
    }

    #[cfg(unix)]
    #[test]
    fn symlink_escapes_are_rejected() {
        let tmp = base();
        let outside = TempDir::new().unwrap();
        std::os::unix::fs::symlink(outside.path(), tmp.path().join("link")).unwrap();
        assert!(matches!(
            resolve_under(tmp.path(), "link/file.blend"),
            Err(PathError::Escapes(_))
        ));
        assert!(matches!(
            resolve_under(tmp.path(), "link"),
            Err(PathError::Escapes(_))
        ));
    }

    #[test]
    fn nonexistent_base_is_allowed() {
        let tmp = base();
        let missing = tmp.path().join("not-yet");
        assert_eq!(
            resolve_under(&missing, "a/b.blend").unwrap(),
            missing.join("a/b.blend")
        );
    }

    #[test]
    fn file_name_validation() {
        assert_eq!(
            validate_file_name("My Scene_1.v2-final"),
            Ok("My Scene_1.v2-final")
        );
        assert!(validate_file_name("").is_err());
        assert!(validate_file_name(".hidden").is_err());
        assert!(validate_file_name("a/b").is_err());
        assert!(validate_file_name("a\\b").is_err());
        assert!(validate_file_name("semi;colon").is_err());
        assert!(validate_file_name(&"x".repeat(129)).is_err());
    }

    #[test]
    fn blend_extension_is_added_once() {
        assert_eq!(with_blend_extension("scene"), "scene.blend");
        assert_eq!(with_blend_extension("scene.blend"), "scene.blend");
        assert_eq!(with_blend_extension("scene.BLEND"), "scene.BLEND");
    }
}
