//! Configuration and path handling for AI Toolkit MCP server.

use std::path::{Path, PathBuf};
use thiserror::Error;

/// Configuration errors
#[derive(Error, Debug)]
pub enum ConfigError {
    #[error("Invalid path: {0}")]
    InvalidPath(String),
    #[error("Path traversal attempt detected: {0}")]
    PathTraversal(String),
    #[error("Empty path provided")]
    EmptyPath,
    #[error("Absolute path not allowed")]
    AbsolutePath,
    #[error("IO error: {0}")]
    IoError(#[from] std::io::Error),
}

/// AI Toolkit paths configuration
#[derive(Clone)]
pub struct AIToolkitPaths {
    pub base_path: PathBuf,
    pub datasets_path: PathBuf,
    pub outputs_path: PathBuf,
    pub configs_path: PathBuf,
}

impl AIToolkitPaths {
    /// Create paths from environment or defaults
    pub fn from_env() -> Self {
        let base_path = std::env::var("AI_TOOLKIT_PATH")
            .map(PathBuf::from)
            .unwrap_or_else(|_| PathBuf::from("/ai-toolkit"));

        Self {
            datasets_path: base_path.join("datasets"),
            outputs_path: base_path.join("outputs"),
            configs_path: base_path.join("config"),
            base_path,
        }
    }

    /// Ensure all directories exist
    pub fn ensure_directories(&self) -> Result<(), ConfigError> {
        std::fs::create_dir_all(&self.datasets_path)?;
        std::fs::create_dir_all(&self.outputs_path)?;
        std::fs::create_dir_all(&self.configs_path)?;
        Ok(())
    }
}

/// Validate and resolve a user-provided path to prevent traversal attacks.
///
/// # Arguments
/// * `user_path` - User-provided path (must be relative)
/// * `base_dir` - The base directory that the path must be within
/// * `path_type` - Type of path for error messages
///
/// # Returns
/// Resolved safe path within base_dir
pub fn validate_path(
    user_path: &str,
    base_dir: &Path,
    path_type: &str,
) -> Result<PathBuf, ConfigError> {
    // Reject empty paths
    if user_path.is_empty() {
        return Err(ConfigError::EmptyPath);
    }

    let user_path_obj = Path::new(user_path);

    // Reject absolute paths
    if user_path_obj.is_absolute() {
        return Err(ConfigError::AbsolutePath);
    }

    // Reject paths with parent directory references
    if user_path.contains("..") {
        return Err(ConfigError::PathTraversal(format!(
            "Invalid {} path: parent directory references not allowed",
            path_type
        )));
    }

    // Reject current directory references
    if user_path == "." || user_path == "./" {
        return Err(ConfigError::InvalidPath(format!(
            "Invalid {} path: current directory reference not allowed",
            path_type
        )));
    }

    // Check for invalid path components
    for component in user_path_obj.components() {
        match component {
            std::path::Component::Normal(name) => {
                if name.is_empty() {
                    return Err(ConfigError::InvalidPath(format!(
                        "Invalid {} path: empty component",
                        path_type
                    )));
                }
            }
            std::path::Component::CurDir | std::path::Component::ParentDir => {
                return Err(ConfigError::PathTraversal(format!(
                    "Invalid {} path: relative directory reference not allowed",
                    path_type
                )));
            }
            _ => {}
        }
    }

    // Construct the safe path within base_dir
    let safe_path = base_dir.join(user_path);

    // Canonicalize base_dir for comparison (handle symlinks)
    let canonical_base = base_dir
        .canonicalize()
        .unwrap_or_else(|_| base_dir.to_path_buf());

    // If the safe path exists, verify it resolves within base_dir
    if safe_path.exists() {
        let canonical_path = safe_path.canonicalize()?;
        if !canonical_path.starts_with(&canonical_base) {
            return Err(ConfigError::PathTraversal(format!(
                "Invalid {} path: traversal attempt detected",
                path_type
            )));
        }
    }

    Ok(safe_path)
}

/// Validate a filename (no path separators allowed)
#[allow(dead_code)]
pub fn validate_filename(filename: &str, file_type: &str) -> Result<(), ConfigError> {
    if filename.is_empty() {
        return Err(ConfigError::EmptyPath);
    }

    if filename.contains('/') || filename.contains('\\') {
        return Err(ConfigError::InvalidPath(format!(
            "Invalid {} filename: path separators not allowed",
            file_type
        )));
    }

    if filename.contains("..") {
        return Err(ConfigError::PathTraversal(format!(
            "Invalid {} filename: parent directory reference not allowed",
            file_type
        )));
    }

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::PathBuf;

    #[test]
    fn test_validate_path_normal() {
        let base = PathBuf::from("/tmp/test");
        let result = validate_path("config.yaml", &base, "config");
        assert!(result.is_ok());
        assert_eq!(result.unwrap(), PathBuf::from("/tmp/test/config.yaml"));
    }

    #[test]
    fn test_validate_path_subdirectory() {
        let base = PathBuf::from("/tmp/test");
        let result = validate_path("subdir/file.txt", &base, "file");
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_path_traversal() {
        let base = PathBuf::from("/tmp/test");
        let result = validate_path("../etc/passwd", &base, "config");
        assert!(result.is_err());
    }

    #[test]
    fn test_validate_path_absolute() {
        let base = PathBuf::from("/tmp/test");
        let result = validate_path("/etc/passwd", &base, "config");
        assert!(result.is_err());
    }

    #[test]
    fn test_validate_path_empty() {
        let base = PathBuf::from("/tmp/test");
        let result = validate_path("", &base, "config");
        assert!(result.is_err());
    }

    #[test]
    fn test_validate_filename_normal() {
        let result = validate_filename("image.png", "image");
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_filename_with_path() {
        let result = validate_filename("subdir/image.png", "image");
        assert!(result.is_err());
    }
}
